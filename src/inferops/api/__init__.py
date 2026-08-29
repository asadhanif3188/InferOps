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
rule 5 forbids, so there is nothing to omit. Selecting an adapter from
configuration is `V1-S1-005-PR2`'s.

*What it does not finish is named rather than left to be found.* The canonical
error body is served in a deliberate subset — a code, a message, and the two
identifiers — because `V1-S1-005-PR2` standardises the rest of it; `/metrics`
serves an exposition with no series because the accepted telemetry catalog
records that nothing in this repository emits a metric and the telemetry work
owns instrumenting this API; and two accepted request members, ``max_tokens`` and
``temperature``, are validated and not forwarded because the serving adapter
interface `V1-S1-002` froze has no parameter for either. All three are recorded
in [the API document](../../../docs/serving/inference-api.md).

Eight modules, one job each:

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
- :mod:`~inferops.api.errors` — the codes an edge refusal produces and the status
  each failure carries, provisional until `V1-S1-005-PR2`.
- :mod:`~inferops.api.metrics` — the metrics endpoint, and why it publishes no
  series.
- :mod:`~inferops.api.lifecycle` — starting, serving, draining, and stopping, in
  that order, which is the graceful-shutdown equivalent the accepted record chose
  over a remote-stop endpoint.
"""

from __future__ import annotations

from .application import (
    ADAPTER_KIND_DISAGREEMENT,
    DRAINING_MESSAGE,
    JSON_CONTENT_TYPE,
    MAX_REQUEST_BYTES,
    UNEXPECTED_FAILURE_MESSAGE,
    ApiConfiguration,
    InferOpsApi,
)
from .errors import (
    CAPABILITY_UNAVAILABLE,
    CONTRACT_INVALID,
    EDGE_REFUSAL_STATUS,
    STATUS_FOR_CANONICAL_CODE,
    RequestRefused,
    status_for,
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
    exposition,
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
from .surface import (
    ACCEPTED_MESSAGE_ROLES,
    ACCEPTED_REQUEST_FIELDS,
    CONTRACT_VERSION,
    CORRELATION_ID_HEADER,
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
    "ACCEPTED_MESSAGE_ROLES",
    "ACCEPTED_REQUEST_FIELDS",
    "ADAPTER_KIND_DISAGREEMENT",
    "BOUND_METRIC_NAMES",
    "CAPABILITY_UNAVAILABLE",
    "CONTRACT_INVALID",
    "CONTRACT_VERSION",
    "CORRELATION_ID_HEADER",
    "DEFAULT_DRAIN_TIMEOUT_MS",
    "DRAINING_MESSAGE",
    "EDGE_REFUSAL_STATUS",
    "EXPOSITION_CONTENT_TYPE",
    "EXTENSION_MEMBER",
    "HEADER_PREFIX",
    "JSON_CONTENT_TYPE",
    "MAX_REQUEST_BYTES",
    "NOT_PASSED_THROUGH",
    "PATH_PREFIX",
    "REQUEST_ID_HEADER",
    "REQUIRED_REQUEST_FIELDS",
    "ROUTES",
    "SINGLE_MESSAGE_REASON",
    "STATUS_ALIVE",
    "STATUS_FOR_CANONICAL_CODE",
    "STATUS_NOT_READY",
    "STATUS_READY",
    "SURFACE_DATA_REF",
    "SURFACE_DECISION_REF",
    "SURFACE_DOCUMENT_REF",
    "UNEXPECTED_FAILURE_MESSAGE",
    "ApiConfiguration",
    "ApplicationLifecycle",
    "ChatCompletionRequest",
    "InferOpsApi",
    "LifecycleState",
    "RequestRefused",
    "Route",
    "ShuttingDown",
    "completion_body",
    "declared_capabilities",
    "error_body",
    "exposition",
    "install_termination_handlers",
    "live_body",
    "models_body",
    "parse_chat_completion",
    "ready_body",
    "status_for",
]
