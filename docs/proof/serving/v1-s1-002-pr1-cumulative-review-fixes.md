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
7. ✅ Made adapter conformance tests genuinely adapter-neutral
8. ✅ Fixed strict mypy failures
9. ✅ Fixed all formatting-gate failures
10. ✅ Added public traceability and validation evidence

**Revision note.** An earlier revision of this document reported finding 7 as fixed and mypy as passing when neither was true: the conformance suite still read `adapter.initialized`, wrote `adapter.model_ready`, and asserted `adapter_kind == "mock"`, and the gate counts quoted here did not match what the tools reported. Sections 7, 8, 9 and the validation results below have been rewritten against actual command output. The overclaim was a defect in the evidence, and it is recorded rather than quietly corrected.

## Key Changes

### 1. Streaming Capability Handling (V1 Synchronous-Only Enforcement)

**Finding:** ADR-0010 D6 explicitly states V1 has no streaming method.

**Fix:**
- Removed `ServingAdapter.stream()` from the protocol entirely
- Streaming capability is now ALWAYS declared as unsupported (no configuration flag)
- `should_support_streaming` flag removed from test double
- Added test verifying no stream method exists on the protocol
- Streaming capability must always report `supported=false` per V1 contract
- Synchronous-only constraint is now enforced at the implementation level

**Files changed:**
- `src/inferops/domain/serving/contract.py`
- `src/inferops/domain/serving/test_double.py`
- `tests/domain/test_serving_adapter_conformance.py`

### 2. Credential Validation Agreement (Exact Heuristic Alignment)

**Finding:** Domain validator diverged from published validator in two ways:
1. Used different delimiters for splitting segments: `[/_:-]` instead of `[/#:._\-]`
2. Omitted Shannon entropy threshold check, using only character-type checks

This caused false rejections: `Aa1Aa1Aa1Aa1Aa1Aa1Aa1` (repetitive, low entropy) was rejected by domain but accepted by published.

**Fix:** ✅ RESOLVED in previous session
- Added ALL 40 credential prefixes from published validator
- Replaced character-type-only heuristic with exact published algorithm:
  - Correct delimiter pattern: `[/#:._\-]` (splits by forward slash, hash, colon, dot, underscore, hyphen)
  - Added Shannon entropy calculation and threshold check (minimum 3.5 bits/character)
  - Kept 20-character minimum and mixed-case/digit requirements
- Domain validator mirrors published validator exactly
- Test case `Aa1Aa1Aa1Aa1Aa1Aa1Aa1` correctly passes

**Files changed:**
- `src/inferops/domain/workload/validation.py`
- `tests/domain/test_workload_validation.py`

### 3. Adapter-Kind Provenance (Closed Vocabulary)

**Finding:** Inference results lacked adapter identification. Format validation alone ("banana" would pass) weakens
mock/real boundary enforcement needed for validation evidence.

**Fix:**
- Added required `adapter_kind` field to `InferenceResult`
- `adapter_kind` is a CLOSED VOCABULARY: only "mock" and "real" accepted
- Not just format validation (kebab-case); actual values checked against allowlist
- Validated at construction time with explicit whitelist
- Test double always returns `adapter_kind="mock"`
- Tests verify adapter kind is always present and must be accepted value
- Test added to ensure invalid kinds like "banana" are rejected despite valid format

**Files changed:**
- `src/inferops/domain/serving/values.py`
- `src/inferops/domain/serving/test_double.py`
- `tests/domain/test_serving_adapter_conformance.py`

### 4. Telemetry Mapping Contract (Catalog Validation, Not Naming Rules)

**Finding:** TelemetryMapping accepted arbitrary metric identifiers like "banana" through naming-pattern validation, without checking against the actual accepted platform catalog. This inverted the constraint: valid-format names were accepted while reserved platform metrics were rejected by prefix.

**Fix:**
- Defined `ACCEPTED_ADAPTER_METRICS` constant: the actual platform catalog of metrics adapters may report
- Changed validation from "naming regex + reserved-prefix check" to "catalog membership check"
- Adapters can report ONLY metrics in `ACCEPTED_ADAPTER_METRICS`
- Per ADR-0002 and ADR-0006, `inferops_*` and `platform_*` metrics are platform-owned and not in the adapter catalog
- "banana" now rejected: not in accepted catalog
- `inferops_inference_requests_total` also rejected: platform-owned (not for adapters)
- Empty catalog for V1 reflects deferred adapter-reportable metrics (test double reports empty tuple)
- `platform_metric_ids` remains immutable tuple type (frozen dataclass)
- Tests validate catalog membership rather than naming patterns

**Files changed:**
- `src/inferops/domain/serving/values.py` (catalog validation instead of pattern matching)
- `tests/domain/test_serving_adapter_conformance.py` (new tests for catalog validation)

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

### 6. Request Context Propagation (Including Error Mapping)

**Finding:** Adapter errors discarded supplied context. map_error_to_canonical() had no context parameter,
so unknown runtime exceptions became InternalErrors with empty context, losing requestId/correlationId.

**Fix:**
- Added optional `context` parameter to `map_error_to_canonical()` protocol method
- All error constructors accept optional `context` parameter
- ModelNotReadyError, errors from infer() preserve context
- Unknown exceptions mapped via map_error_to_canonical(error, context) preserve supplied context
- Error `as_dict()` includes context identifiers
- Test double passes context through to mapped errors
- Tests verify both requestId and correlationId survive error mapping and serialization
- Offline (no-context) case remains valid and doesn't invent IDs

**Files changed:**
- `src/inferops/domain/serving/test_double.py`
- `src/inferops/domain/serving/errors.py`
- `tests/domain/test_serving_adapter_conformance.py`

### 7. Reusable Conformance Harness (Truly Adapter-Neutral)

**Finding:** The conformance suite was described as adapter-neutral but was not. It read `adapter.initialized`, wrote `adapter.model_ready`, and asserted `result.adapter_kind == "mock"`. None of those members are declared on `ServingAdapter`, so strict mypy reported three errors, and a real adapter supplied through `adapter_factory` would have failed the suite despite conforming.

An earlier revision of this document claimed these accesses had been removed. They had not been; the claim was wrong and is corrected here.

**Fix:**
- Every test in the suite now touches only members `ServingAdapter` declares. No test reads or writes `initialized`, `model_ready`, or `should_support_token_counting`.
- `test_initialization_succeeds_with_valid_config` asserts through the protocol: after `initialize()`, `get_model_metadata()` reports the configured model.
- `test_shutdown_completes` asserts that shutdown returns rather than raising. The protocol publishes no post-shutdown state to inspect.
- `test_infer_result_includes_adapter_kind` asserts membership in `ACCEPTED_ADAPTER_KINDS` rather than equality with `"mock"`. A real adapter reporting `"real"` passes unchanged.
- `test_error_preserves_request_context_from_infer` needed a not-ready adapter, which the protocol offers no way to produce. It moved to the adapter-specific suite rather than being dropped.
- `ACCEPTED_ADAPTER_KINDS` moved from `test_double.py` to `values.py`, where `InferenceResult` validation already hardcoded the same set inline. One definition now, exported from `inferops.domain.serving`, so a conformance suite need not import from the test double.

**State-driven coverage retained, not deleted:** the scenarios that cannot be expressed through the protocol are now in `tests/domain/test_serving_test_double.py` (9 tests), bound to `MinimalTestDouble` deliberately: initialization and shutdown bookkeeping, readiness reporting, inference against a loading model, context preservation on errors raised by `infer()`, token-counting declared and undeclared, and the double's `"mock"` provenance. A real adapter drives the same scenarios through its own means and carries its own file alongside the shared suite. This restores the four tests a previous revision removed outright.

**Overriding the adapter under test:** `tests/domain/conftest.py` provides the `adapter_factory` fixture:
  ```python
  @pytest.fixture
  def adapter_factory():
      from my_adapter import MyRealAdapter

      return MyRealAdapter
  ```

**Files changed:**
- `src/inferops/domain/serving/values.py` (`ACCEPTED_ADAPTER_KINDS` defined here)
- `src/inferops/domain/serving/test_double.py` (constant removed, imported from values)
- `src/inferops/domain/serving/__init__.py` (exports both catalog constants)
- `tests/domain/conftest.py` (adapter_factory fixture)
- `tests/domain/test_serving_adapter_conformance.py` (protocol-only assertions)
- `tests/domain/test_serving_test_double.py` (new; adapter-specific state tests)

### 8. Type Safety (Mypy)

**Finding:** Eight `no-any-return` errors in workload validation (from an earlier session), then three `attr-defined` errors in the conformance suite from the three protocol violations described in section 7.

**Fix:**
- Added type guards in `CompatibilityMatrixLoader` (earlier session)
- Conformance tests now reference only protocol-declared members, which removes the `attr-defined` errors at their cause rather than silencing them

**Files changed:**
- `src/inferops/domain/workload/validation.py` (earlier session)
- `tests/domain/test_serving_adapter_conformance.py`

**Validation** — the configured invocation (`[tool.mypy]` in `pyproject.toml`: `strict = true`, `warn_unreachable = true`, `ignore_missing_imports = false`, over `src`, `tools`, `tests`, `conftest.py`):
```
$ uv run --frozen --group dev mypy
Success: no issues found in 37 source files
```

The file count is 37 rather than the 36 seen at review time because `tests/domain/test_serving_test_double.py` is new. Type stubs (`types-PyYAML`, `types-jsonschema`) come from the `checks` dependency group; running a bare `mypy` outside that environment reports missing-stub errors that are an artifact of the environment, not of the code.

### 9. Code Formatting

**Finding:** Ruff formatting needed on code changes. A previous revision of this document reported a file count that did not match what ruff actually checks.

**Fix:** Applied the formatter to the modified files. The tree is now clean under `--check`, so the gate passes without the formatter having to write anything.

**Validation:**
```
$ uv run --frozen --group dev ruff format --check .
112 files already formatted

$ uv run --frozen --group dev ruff check .
All checks passed!
```

112 rather than the 111 seen at review time: `tests/domain/test_serving_test_double.py` is new.

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

Every command below was run in the repository's locked environment (`uv run --frozen --group dev`), and the output is quoted as it was returned.

```
$ mypy
Success: no issues found in 37 source files

$ ruff format --check .
112 files already formatted

$ ruff check .
All checks passed!

$ python -m pytest tests/domain -q
398 passed, 18 skipped in 6.34s

$ python -m pytest tests/domain/test_serving_adapter_conformance.py -q
24 passed in 0.17s

$ python -m pytest tests/domain/test_serving_test_double.py -q
9 passed in 0.10s

$ python -m pytest -q
2950 passed, 25 skipped in 15.43s
```

Domain tests rose from 390 to 398: the four state-driven tests a previous revision removed are restored in the adapter-specific suite, along with four more covering readiness, capability declaration, and provenance. The conformance suite is 24 tests rather than 25 because the infer-error context test moved to that suite rather than being counted twice.

### Test Coverage

Conformance harness, `tests/domain/test_serving_adapter_conformance.py` (24 tests, protocol members only, valid for any adapter):
- Initialization completes and the configured model is reported back through `get_model_metadata()`
- Configuration validation rejects an empty model identifier
- Capability discovery returns declared capabilities including streaming and token-counting
- Streaming is ALWAYS declared unsupported (V1 constraint, not configurable)
- No `stream()` method exists on the protocol
- Readiness reporting returns a boolean
- Inference returns an `InferenceResult` with content, model, and provenance
- Adapter kind is drawn from `ACCEPTED_ADAPTER_KINDS`, not assumed to be `"mock"`
- Adapter kind rejects wrong case, empty, and well-formed-but-unaccepted values like "banana"
- Model and runtime metadata are returned as domain types
- Shutdown completes without raising
- Error mapping returns canonical errors and passes canonical errors through unchanged
- Error mapping does not leak sensitive text
- Error mapping preserves a supplied requestId and correlationId
- Telemetry mapping uses only canonical error codes
- Telemetry metric identifiers are an immutable tuple
- Telemetry metric identifiers are validated against catalog membership
- Request counter is not in the adapter's metric list (InferOps owns it, per ADR-0002)
- An adapter cannot report an arbitrary name like "banana" (not in the catalog)
- An adapter cannot report a reserved platform metric (`inferops_*`, `platform_*`)

Adapter-specific suite, `tests/domain/test_serving_test_double.py` (9 tests, `MinimalTestDouble` only):
- `initialize()` and `shutdown()` move the double's initialization state
- `is_ready()` reports the state the double was constructed with
- Inference against a loading model raises `ModelNotReadyError`
- An error raised by `infer()` carries the supplied requestId and correlationId
- Token-counting capability declaration follows construction
- Token usage is present when the capability is declared
- Token usage is None when it is not — absence preserved, not a missing field
- The double reports `"mock"` provenance and never claims to be real

These belong here and not in the conformance harness because the protocol offers no way to put an arbitrary adapter into a not-ready state or to switch an optional capability off. A real adapter reaches the same scenarios by other means and gets its own file.

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
✅ **Conformance suite references only protocol members, so a real adapter passes it unchanged**  
✅ **All repository-approved validation gates pass, with output quoted above**  
✅ **Public diff contains no private material or sensitive data**

Ready for code review and merge.
