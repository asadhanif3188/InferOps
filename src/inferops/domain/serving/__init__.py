"""Serving adapter domain module.

This module defines the runtime-neutral interface between InferOps platform
concepts and serving-runtime implementations. All serving adapters (mock and
real) must implement the ServingAdapter protocol defined here.

**Key exports:**

- :class:`ServingAdapter`: The protocol all adapters must implement
- :class:`AdapterConfiguration`: Configuration for adapter initialization
- :class:`InferenceResult`: Result of a successful inference
- :class:`ModelMetadata`, :class:`RuntimeMetadata`: Runtime state
- Canonical error types: :class:`ModelNotReadyError`, :class:`RequestTimeoutError`, etc.

**For testing:**

- :class:`ServingAdapterTestDouble`: A minimal in-memory implementation
- Conformance tests in tests module
"""
from .contract import ServingAdapter
from .errors import (
    CanonicalError,
    CapabilityUnavailableError,
    DomainError,
    InternalError,
    InvalidAdapterConfigError,
    InvalidValueError,
    ModelNotReadyError,
    RateLimitedError,
    RequestTimeoutError,
    ServingAdapterError,
    UpstreamTimeoutError,
)
from .test_double import (
    MinimalTestDouble,
    ServingAdapterTestDouble,
)
from .values import (
    AdapterCapability,
    AdapterConfiguration,
    InferenceResult,
    ModelMetadata,
    RuntimeMetadata,
    TokenUsage,
)

__all__ = [
    "AdapterCapability",
    "AdapterConfiguration",
    "CanonicalError",
    "CapabilityUnavailableError",
    "DomainError",
    "InferenceResult",
    "InternalError",
    "InvalidAdapterConfigError",
    "InvalidValueError",
    "MinimalTestDouble",
    "ModelMetadata",
    "ModelNotReadyError",
    "RateLimitedError",
    "RequestTimeoutError",
    "RuntimeMetadata",
    "ServingAdapter",
    "ServingAdapterError",
    "ServingAdapterTestDouble",
    "TokenUsage",
    "UpstreamTimeoutError",
]
