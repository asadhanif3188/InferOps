"""Constrained value objects used in the serving adapter contract.

Every value here was chosen at parse time against the format the contract publishes
for it. Values are immutable and hashable. Absence is preserved: ``None`` means a
value was not provided, never that a default applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import InvalidValueError

# Platform metric identifiers adapters are permitted to report.
# Per ADR-0006 and ADR-0002, InferOps owns platform metrics like
# inferops_inference_requests_total. Adapters report only optional custom
# metrics from the accepted catalog. V1 defers adapter-reportable metrics;
# this set is empty, requiring adapters to report no custom metrics.
ACCEPTED_ADAPTER_METRICS: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    """Metadata about a model reported by the serving runtime.

    Attributes:
        identifier: The model identifier or reference used by the runtime.
        revision: Optional revision identifier (commit hash, version tag, etc).
    """

    identifier: str
    revision: str | None = None

    def __post_init__(self) -> None:
        if not self.identifier:
            raise InvalidValueError("model identifier must not be empty")


@dataclass(frozen=True, slots=True)
class RuntimeMetadata:
    """Metadata about the serving runtime.

    Attributes:
        name: Name of the serving runtime (e.g., "llama.cpp").
        version: Version of the serving runtime.
    """

    name: str
    version: str

    def __post_init__(self) -> None:
        if not self.name:
            raise InvalidValueError("runtime name must not be empty")
        if not self.version:
            raise InvalidValueError("runtime version must not be empty")


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage metrics for an inference request.

    Attributes:
        input_tokens: Number of tokens in the input prompt.
        output_tokens: Number of tokens generated in the output.
    """

    input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if self.input_tokens < 0:
            raise InvalidValueError("input_tokens must be non-negative")
        if self.output_tokens < 0:
            raise InvalidValueError("output_tokens must be non-negative")

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """Result of a successful inference operation.

    Attributes:
        content: The generated content as a string.
        model: The model used for inference.
        adapter_kind: Which adapter kind (e.g., "mock", "real") served this result.
        usage: Token usage for this request (may be None if token tracking is not a declared capability).
        finish_reason: Why generation stopped (e.g., "stop", "length").
    """

    content: str
    model: str
    adapter_kind: str
    usage: TokenUsage | None = None
    finish_reason: str | None = None

    def __post_init__(self) -> None:
        if self.content is None:
            raise InvalidValueError("content must not be None")
        if not self.model:
            raise InvalidValueError("model must not be empty")
        if not self.adapter_kind:
            raise InvalidValueError("adapter_kind must not be empty")

        # Adapter kind must be from closed vocabulary (mock, real, etc)
        accepted_kinds = {"mock", "real"}
        if self.adapter_kind not in accepted_kinds:
            raise InvalidValueError(
                f"adapter_kind must be one of {accepted_kinds}, got {self.adapter_kind}"
            )


@dataclass(frozen=True, slots=True)
class AdapterCapability:
    """A declared capability of the serving adapter.

    Attributes:
        name: Capability identifier (e.g., "streaming", "token-counting").
        supported: Whether this capability is supported by the adapter.
        version: Optional capability version.
    """

    name: str
    supported: bool
    version: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise InvalidValueError("capability name must not be empty")
        if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]$", self.name):
            raise InvalidValueError(
                f"capability name must be lowercase kebab-case: {self.name}"
            )


@dataclass(frozen=True, slots=True)
class AdapterConfiguration:
    """Configuration passed to an adapter at initialization.

    Attributes:
        model_identifier: The model identifier to load (e.g., model name, path).
        timeout_ms: Request timeout in milliseconds.
        max_tokens: Maximum tokens to generate per request (optional).
    """

    model_identifier: str
    timeout_ms: int
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.model_identifier:
            raise InvalidValueError("model_identifier must not be empty")
        if self.timeout_ms <= 0:
            raise InvalidValueError("timeout_ms must be positive")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise InvalidValueError("max_tokens must be positive")


@dataclass(frozen=True, slots=True)
class TelemetryMapping:
    """Platform telemetry responsibilities and adapter capabilities.

    Per ADR-0002: InferOps (not the adapter/runtime) owns production of
    inferops_inference_requests_total. This object maps adapter-reported
    metrics to platform canonical identifiers only.

    Attributes:
        platform_metric_ids: Immutable tuple of accepted canonical metric identifiers
                            the adapter may report (from platform telemetry catalog).
        error_code: Optional canonical error code when mapping runtime errors.
        token_usage: Whether adapter supports optional token usage reporting.
    """

    platform_metric_ids: tuple[str, ...] = ()
    error_code: str | None = None
    token_usage: bool | None = None

    def __post_init__(self) -> None:
        # Ensure platform_metric_ids is a tuple (immutable)
        if not isinstance(self.platform_metric_ids, tuple):
            raise InvalidValueError("platform_metric_ids must be a tuple (immutable)")
        if not all(isinstance(mid, str) for mid in self.platform_metric_ids):
            raise InvalidValueError("all platform_metric_ids must be strings")

        # Validate against accepted platform metric catalog.
        # Per ADR-0002 and ADR-0006, adapters report only metrics from the
        # accepted catalog. Arbitrary identifiers (even valid-format ones like
        # "banana") are rejected. Reserved prefixes (inferops_, platform_) are
        # platform-owned and not available for adapter reporting.
        for metric_id in self.platform_metric_ids:
            if not metric_id:
                raise InvalidValueError("metric_id must not be empty string")
            if metric_id not in ACCEPTED_ADAPTER_METRICS:
                raise InvalidValueError(
                    f"metric_id '{metric_id}' is not in accepted platform catalog"
                )

        if self.error_code is not None and not self.error_code:
            raise InvalidValueError("error_code must not be empty string")

        allowed_error_codes = {
            "model-not-ready",
            "request-timeout",
            "upstream-timeout",
            "rate-limited",
            "capability-unavailable",
            "internal-error",
        }
        if self.error_code is not None and self.error_code not in allowed_error_codes:
            raise InvalidValueError(
                f"error_code must be one of {allowed_error_codes}, got {self.error_code}"
            )
