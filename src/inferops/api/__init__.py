"""The user-facing InferOps API: the first component here that answers a request.

`ADR 0010` decided the shape of this API one story before it existed — the
compatibility target, the five endpoints, the frozen request and response
subsets, the strict unknown-member policy, the extension namespace, the declared
capability set, and the mapping from a condition to a canonical code. This
package is that decision executed. Nothing here decides any of it, and every
constant that repeats a row of it is compared against
[the accepted record](../../../docs/serving/inference-api-surface.v1alpha1.json)
by ``tests/serving/test_inference_api_implementation_agreement.py``.

**Three properties are worth reading before the modules.**

*It imports no HTTP framework, because `ADR 0004` forbids one.*
:class:`~inferops.api.application.InferOpsApi` implements the ASGI application
interface directly — a callable over a scope, a receive, and a send. ASGI is a
calling convention rather than a package, so the rule is obeyed without a
framework-shaped hole in the design, in the same way the real adapter's transport
obeys it with :mod:`http.client`. **This repository ships no ASGI server**, so
nothing here has bound a socket; the suites drive the application through its own
interface, which establishes the routing, the translation, and the lifecycle, and
nothing about a network.

*It is the composition point, and it has no default adapter.* The adapter is
handed to the application at construction. A mock that could become the live
adapter by omission is what
[the mock and real boundary](../../../docs/serving/mock-and-real-boundary.md)
rule 5 forbids, so there is nothing to omit. :mod:`~inferops.api.selection` reads
which adapter a deployment serves out of configuration, and it holds the same
rule: the variable is required, an unstated or unrecognised value selects
nothing, and a `real` selection whose settings are missing is refused rather than
answered with a mock.

*It is instrumented, and what it does not emit is named rather than left to be
found.* `/metrics` publishes the metrics the accepted telemetry catalog assigns to
the ``inferops-api`` emitter -- the request counter that closes `ADR 0002` `T7`,
the error counter, the latency histogram, the in-flight gauge, the readiness
counter, the token counter, the two process gauges, and the identity metric --
and every request to the inference endpoint writes one structured record when it
arrives and one when it closes. The metrics the catalog assigns to the serving
adapter and to the contract validator are **not** emitted, no span is produced,
and no exporter, collector, or store is selected; the catalog records which per
metric. Separately, two accepted request members, ``max_tokens`` and
``temperature``, are validated and not forwarded because the serving adapter
interface `V1-S1-002` froze has no parameter for either. Both are recorded in
[the API document](../../../docs/serving/inference-api.md).

Ten modules, one job each:

- :mod:`~inferops.api.application` — the ASGI application itself: the routes, the
  composition point, and the translation between the borrowed shape and the
  domain.
- :mod:`~inferops.api.surface` — the frozen subset, copied from the record that
  decided it, and compared against it by a test.
- :mod:`~inferops.api.identifiers` — where a request and correlation identifier
  come from, and why a supplied one is validated rather than trusted.
- :mod:`~inferops.api.validation` — one request body read against the subset, and
  every refusal it produces.
- :mod:`~inferops.api.responses` — the bodies this API returns, and the rules the
  shapes do not state on their own.
- :mod:`~inferops.api.errors` — the canonical error contract as a table of
  conditions: the code, the ``retryable`` flag, and the status each refusal
  carries, together.
- :mod:`~inferops.api.selection` — which adapter is live, read from configuration
  and refused when it is not stated.
- :mod:`~inferops.api.metrics` — the metrics endpoint, and what it publishes.
- :mod:`~inferops.api.observability` — the instruments this API emits and the
  events it writes, bound to the moments in a request it already had.
- :mod:`~inferops.api.lifecycle` — starting, serving, draining, and stopping, in
  that order, which is the graceful-shutdown equivalent the accepted record chose
  over a remote-stop endpoint.
"""

from __future__ import annotations

from .application import (
    JSON_CONTENT_TYPE,
    MAX_REQUEST_BYTES,
    ApiConfiguration,
    InferOpsApi,
)
from .errors import (
    ADAPTER_KIND_DISAGREEMENT,
    CAPABILITY_UNAVAILABLE,
    CONDITION_FOR_ADAPTER_CODE,
    CONDITIONS,
    CONTRACT_INVALID,
    DRAINING_MESSAGE,
    INTERNAL_ERROR,
    MODEL_NOT_READY,
    RATE_LIMITED,
    REQUEST_TIMEOUT,
    UNEXPECTED_FAILURE_MESSAGE,
    UPSTREAM_TIMEOUT,
    VERSION_UNSUPPORTED,
    Condition,
    RequestRefused,
    condition_for,
)
from .lifecycle import (
    DEFAULT_DRAIN_TIMEOUT_MS,
    ApplicationLifecycle,
    LifecycleState,
    ShuttingDown,
    install_termination_handlers,
)
from .metrics import (
    BOUND_METRIC_NAMES,
    EXPOSITION_CONTENT_TYPE,
)
from .observability import (
    API_METRICS,
    MOCK_EXPOSITION_NOTE,
    NO_MEMORY_SOURCE_NOTE,
    ApiTelemetry,
    ModelRuntimeIdentity,
    outcome_for,
)
from .responses import (
    STATUS_ALIVE,
    STATUS_NOT_READY,
    STATUS_READY,
    completion_body,
    declared_capabilities,
    error_body,
    live_body,
    models_body,
    ready_body,
)
from .selection import (
    ACCEPTED_ADAPTERS,
    ADAPTER_KIND_FOR,
    ADAPTER_MOCK,
    ADAPTER_REAL,
    ENV_ADAPTER,
    ENV_DRAIN_TIMEOUT_MS,
    ENV_MAX_OUTPUT_TOKENS,
    ENV_MODEL_IDENTIFIER,
    ENV_REQUEST_TIMEOUT_MS,
    OPTIONAL_ENVIRONMENT_VARIABLES,
    REQUIRED_ENVIRONMENT_VARIABLES,
    Selection,
    build,
    select,
)
from .surface import (
    ACCEPTED_MESSAGE_ROLES,
    ACCEPTED_REQUEST_FIELDS,
    CONTRACT_VERSION,
    CORRELATION_ID_HEADER,
    ERROR_BODY_FIELDS,
    EXTENSION_MEMBER,
    HEADER_PREFIX,
    NOT_PASSED_THROUGH,
    PATH_PREFIX,
    REQUEST_ID_HEADER,
    REQUIRED_REQUEST_FIELDS,
    ROUTES,
    SURFACE_DATA_REF,
    SURFACE_DECISION_REF,
    SURFACE_DOCUMENT_REF,
    Route,
)
from .validation import (
    SINGLE_MESSAGE_REASON,
    ChatCompletionRequest,
    parse_chat_completion,
)

__all__ = [
    "ACCEPTED_ADAPTERS",
    "ACCEPTED_MESSAGE_ROLES",
    "ACCEPTED_REQUEST_FIELDS",
    "ADAPTER_KIND_DISAGREEMENT",
    "ADAPTER_KIND_FOR",
    "ADAPTER_MOCK",
    "ADAPTER_REAL",
    "API_METRICS",
    "BOUND_METRIC_NAMES",
    "CAPABILITY_UNAVAILABLE",
    "CONDITIONS",
    "CONDITION_FOR_ADAPTER_CODE",
    "CONTRACT_INVALID",
    "CONTRACT_VERSION",
    "CORRELATION_ID_HEADER",
    "DEFAULT_DRAIN_TIMEOUT_MS",
    "DRAINING_MESSAGE",
    "ENV_ADAPTER",
    "ENV_DRAIN_TIMEOUT_MS",
    "ENV_MAX_OUTPUT_TOKENS",
    "ENV_MODEL_IDENTIFIER",
    "ENV_REQUEST_TIMEOUT_MS",
    "ERROR_BODY_FIELDS",
    "EXPOSITION_CONTENT_TYPE",
    "EXTENSION_MEMBER",
    "HEADER_PREFIX",
    "INTERNAL_ERROR",
    "JSON_CONTENT_TYPE",
    "MAX_REQUEST_BYTES",
    "MOCK_EXPOSITION_NOTE",
    "MODEL_NOT_READY",
    "NOT_PASSED_THROUGH",
    "NO_MEMORY_SOURCE_NOTE",
    "OPTIONAL_ENVIRONMENT_VARIABLES",
    "PATH_PREFIX",
    "RATE_LIMITED",
    "REQUEST_ID_HEADER",
    "REQUEST_TIMEOUT",
    "REQUIRED_ENVIRONMENT_VARIABLES",
    "REQUIRED_REQUEST_FIELDS",
    "ROUTES",
    "SINGLE_MESSAGE_REASON",
    "STATUS_ALIVE",
    "STATUS_NOT_READY",
    "STATUS_READY",
    "SURFACE_DATA_REF",
    "SURFACE_DECISION_REF",
    "SURFACE_DOCUMENT_REF",
    "UNEXPECTED_FAILURE_MESSAGE",
    "UPSTREAM_TIMEOUT",
    "VERSION_UNSUPPORTED",
    "ApiConfiguration",
    "ApiTelemetry",
    "ApplicationLifecycle",
    "ChatCompletionRequest",
    "Condition",
    "InferOpsApi",
    "LifecycleState",
    "ModelRuntimeIdentity",
    "RequestRefused",
    "Route",
    "Selection",
    "ShuttingDown",
    "build",
    "completion_body",
    "condition_for",
    "declared_capabilities",
    "error_body",
    "install_termination_handlers",
    "live_body",
    "models_body",
    "outcome_for",
    "parse_chat_completion",
    "ready_body",
    "select",
]
