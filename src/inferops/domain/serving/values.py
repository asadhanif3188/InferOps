"""Constrained value objects used in the serving adapter contract.

Every value here was chosen at parse time against the format the contract publishes
for it. Values are immutable and hashable. Absence is preserved: ``None`` means a
value was not provided, never that a default applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import InvalidValueError


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
        usage: Token usage for this request (may be None if token tracking is not a declared capability).
        finish_reason: Why generation stopped (e.g., "stop", "length").
    """

    content: str
    model: str
    usage: TokenUsage | None = None
    finish_reason: str | None = None

    def __post_init__(self) -> None:
        if self.content is None:
            raise InvalidValueError("content must not be None")
        if not self.model:
            raise InvalidValueError("model must not be empty")


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
