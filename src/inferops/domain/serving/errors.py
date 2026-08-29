"""Canonical errors in the serving adapter contract.

These errors represent the intersection of what a serving runtime can report and
what InferOps platform semantics require. They are introduced by this story.

**Error codes are authoritative in the contract and API only.** This module defines
the Python domain objects. A message never carries a value read from a request or
from runtime state; it names the field or condition and describes the constraint
in the contract's own published vocabulary.

The canonical error codes are:
- model-not-ready: the model is not yet ready to serve requests
- request-timeout: the request did not complete within the configured timeout
- upstream-timeout: a timeout in an upstream component (runtime, model)
- rate-limited: the adapter or runtime rate-limited this request
- capability-unavailable: a declared capability is not supported
- internal-error: an unexpected error occurred in the adapter or runtime
"""

from __future__ import annotations

from ..context import NO_REQUEST_CONTEXT, RequestContext


class DomainError(Exception):
    """Base class for every failure this domain raises."""


class ServingAdapterError(DomainError):
    """A serving adapter failed to meet a contract requirement.

    Carries where the failure is, why, and the request-scoped identifiers a caller
    supplied — ``requestId`` and ``correlationId`` when there was a request, and
    an empty context when there was not.
    """

    def __init__(
        self,
        field: str,
        reason: str,
        *,
        context: RequestContext = NO_REQUEST_CONTEXT,
    ) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason
        self.context = context

    def as_dict(self) -> dict[str, object]:
        """A safe, structured form: field, reason, and any identifiers supplied."""
        return {"field": self.field, "reason": self.reason, **self.context.as_dict()}


class InvalidAdapterConfigError(ServingAdapterError):
    """An adapter configuration cannot satisfy the contract."""


class InvalidValueError(DomainError):
    """A constrained value refused itself at construction.

    It carries the constraint that was not met and no field location, because a
    value object does not know where in a document it came from. A caller catches
    this and re-raises it with the field path and the request context attached,
    which is the division of labour: this module knows the constraints, the caller
    knows the addresses.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class CanonicalError(DomainError):
    """A request failed with a canonical error code.

    Carries the error code and a message safe to return to a caller. The message
    does not contain values read from the request.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, object]:
        """A structured form: error code and message."""
        return {"code": self.code, "message": self.message}


class ModelNotReadyError(CanonicalError):
    """The model is not yet ready to serve requests."""

    def __init__(self, message: str = "model-not-ready") -> None:
        super().__init__("model-not-ready", message)


class RequestTimeoutError(CanonicalError):
    """The request did not complete within the configured timeout."""

    def __init__(self, message: str = "request-timeout") -> None:
        super().__init__("request-timeout", message)


class UpstreamTimeoutError(CanonicalError):
    """A timeout occurred in an upstream component."""

    def __init__(self, message: str = "upstream-timeout") -> None:
        super().__init__("upstream-timeout", message)


class RateLimitedError(CanonicalError):
    """The adapter or runtime rate-limited this request."""

    def __init__(self, message: str = "rate-limited") -> None:
        super().__init__("rate-limited", message)


class CapabilityUnavailableError(CanonicalError):
    """A declared capability is not supported."""

    def __init__(self, message: str = "capability-unavailable") -> None:
        super().__init__("capability-unavailable", message)


class InternalError(CanonicalError):
    """An unexpected error occurred in the adapter or runtime."""

    def __init__(self, message: str = "internal-error") -> None:
        super().__init__("internal-error", message)
