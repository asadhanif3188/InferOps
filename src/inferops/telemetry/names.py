"""Every telemetry name this distribution emits, copied from the accepted catalog.

`ADR 0006` published the attribute names, the metric names, the label sets, and
the cardinality budget one story before anything could emit them.
[The catalog](../../../docs/telemetry/telemetry-catalog.v1alpha1.json) is where
that decision lives, and every constant in this module is a **copy** of a row in
it. ``tests/telemetry/test_api_telemetry_agreement.py`` reads the accepted file
and fails when a copy drifts, which is the same treatment the runtime pins and
the API surface constants already get, for the same reason: a constant nobody
compares to its source is a constant that drifts.

Nothing here decides anything. A new signal is a change to the catalog first and
to this module second, in that order.

**Two lists carry the whole placement rule into code.**
:data:`LABEL_SAFE_ATTRIBUTES` is every attribute the catalog permits as an
operational metric label, and :data:`NEVER_A_LABEL` is every attribute this
distribution can produce that it forbids there -- a correlation identifier, a
trace identifier, a workload version, a measured duration, and every identity
attribute. Both are compared against the catalog by the agreement suite rather
than believed, and :class:`~inferops.telemetry.registry.MetricRegistry` refuses a
declaration that uses a name outside the first list. The prohibition that used to
be a rule about a document is now a rule a metric declaration cannot get past.
"""

from __future__ import annotations

# -- resource attributes ----------------------------------------------------

#: Which component emitted this. A singleton: one value per emitting process, and
#: this is the process the catalog calls ``inferops-api``.
SERVICE_NAME = "service.name"

#: Which build of that component. Unbounded over history, so it is an identity
#: attribute and reaches metrics only through the identity metric.
SERVICE_VERSION = "service.version"

#: Which environment this is. The failure it prevents is a figure from a laptop
#: being read as a figure from somewhere else.
DEPLOYMENT_ENVIRONMENT = "deployment.environment"

#: Which declared capability this process is serving.
CAPABILITY_ID = "inferops.capability.id"

#: Which release installed this.
RELEASE_ID = "inferops.release.id"

#: Which replica produced this record. Unbounded -- a restarted pod is a new name
#: -- so it is a log field and never a label.
POD_NAME = "k8s.pod.name"

#: Which immutable model revision produced this, given that a model identifier
#: alone does not pin one.
MODEL_REVISION = "inferops.model.revision"

#: Which runtime image, by digest rather than by a tag somebody can move.
RUNTIME_IMAGE_DIGEST = "inferops.runtime.image.digest"

#: Which kind of adapter this deployment was composed with, from the domain's
#: closed vocabulary. Identity rather than an operational dimension: it does not
#: vary within a process, and ``inferops.runtime.id`` already carries the mock
#: runtime's registered identifier into the operational series.
ADAPTER_KIND = "inferops.adapter.kind"

# -- request attributes -----------------------------------------------------

#: Which workload this request is for. A metric label, bounded by how many
#: workloads a deployment serves.
WORKLOAD_ID = "inferops.workload.id"

#: Which version of that workload document was in force. Deliberately not a
#: metric label: workload versions accumulate for as long as the workload exists.
WORKLOAD_VERSION = "inferops.workload.version"

#: Who is accountable for this workload. Not a metric label -- ownership is a
#: property of the workload and joins to it.
OWNER_ID = "inferops.owner.id"

#: Which model served this.
MODEL_ID = "inferops.model.id"

#: Which serving runtime answered. The registered identifier the compatibility
#: matrix uses, including the mock runtime, which is how a mock series stays
#: visibly a mock series.
RUNTIME_ID = "inferops.runtime.id"

#: Did this succeed, and if not, was the fault the caller's, ours, or a timeout?
OUTCOME = "inferops.outcome"

#: Which named failure it was, in the vocabulary the caller was given. A
#: canonical code, never a message and never a runtime's text.
ERROR_CODE = "inferops.error.code"

#: Which internal component failed a readiness check.
COMPONENT = "inferops.component"

#: Were these tokens read or written?
TOKEN_DIRECTION = "inferops.token.direction"

#: Why generation stopped. Carried by no metric, on purpose.
FINISH_REASON = "inferops.finish.reason"

#: Which pieces of work belong to the same request. A log field, never a label.
CORRELATION_ID = "inferops.correlation.id"

#: One synchronous request, as the API minted or accepted it. A log field, never
#: a label.
REQUEST_ID = "inferops.request.id"

# -- record fields ----------------------------------------------------------

#: When this happened. RFC 3339, UTC, millisecond precision.
TIMESTAMP = "timestamp"

#: How urgent this record is.
LEVEL = "level"

#: What kind of thing happened, in a form a query can match. There is no
#: free-form message field, which is `ADR 0006` `D5`.
EVENT = "inferops.event"

#: How long this operation took. A measurement, so a value and never a key.
DURATION_MS = "inferops.duration.ms"

#: What the caller actually received.
HTTP_STATUS = "http.response.status_code"

# -- the placement rule, in code --------------------------------------------

#: Every attribute the catalog permits as an operational metric label.
#: :meth:`~inferops.telemetry.registry.MetricRegistry.declare` refuses any other
#: name, so a label the catalog forbids is a construction error rather than a
#: series somebody has to notice in a store.
LABEL_SAFE_ATTRIBUTES: frozenset[str] = frozenset(
    {
        DEPLOYMENT_ENVIRONMENT,
        WORKLOAD_ID,
        MODEL_ID,
        RUNTIME_ID,
        OUTCOME,
        ERROR_CODE,
        COMPONENT,
        TOKEN_DIRECTION,
    }
)

#: Every attribute the catalog marks identity-only: it may label the identity
#: metric and no operational one. Splitting this out of :data:`NEVER_A_LABEL`
#: is what lets the registry check an identity metric's labels rather than skip
#: them -- an identity metric may carry these, and it still may not carry a
#: correlation identifier or a measured duration.
IDENTITY_ATTRIBUTES: frozenset[str] = frozenset(
    {
        SERVICE_VERSION,
        CAPABILITY_ID,
        RELEASE_ID,
        MODEL_REVISION,
        RUNTIME_IMAGE_DIGEST,
        ADAPTER_KIND,
    }
)

#: Every attribute this distribution can produce that may **not** key an
#: operational series. The identity attributes are here too, because that is what
#: the catalog's ``identity-belongs-on-an-identity-metric`` says: they belong on
#: the identity metric and nowhere else.
NEVER_A_LABEL: frozenset[str] = frozenset(
    {
        CORRELATION_ID,
        REQUEST_ID,
        WORKLOAD_VERSION,
        OWNER_ID,
        POD_NAME,
        FINISH_REASON,
        DURATION_MS,
        HTTP_STATUS,
        TIMESTAMP,
        SERVICE_VERSION,
        CAPABILITY_ID,
        RELEASE_ID,
        MODEL_REVISION,
        RUNTIME_IMAGE_DIGEST,
        ADAPTER_KIND,
    }
)

# -- metric names -----------------------------------------------------------

#: The identity metric. Always 1; its labels are the immutable versions, and
#: putting them here rather than on every operational metric is the difference
#: between recording a release history and multiplying every series by it.
BUILD_INFO = "inferops_build_info"

#: The counter the selected runtime does not have. `ADR 0002` `T7` records that
#: gap, and the component that receives the requests is where it is closed.
INFERENCE_REQUESTS = "inferops_inference_requests_total"

#: A second counter rather than an error-code label on the first, because
#: carrying both on one counter multiplies to tens of thousands of series.
INFERENCE_ERRORS = "inferops_inference_errors_total"

#: End-to-end request latency, at the tail rather than on average.
INFERENCE_REQUEST_DURATION = "inferops_inference_request_duration_seconds"

#: How much work is in progress right now.
INFERENCE_REQUESTS_IN_FLIGHT = "inferops_inference_requests_in_flight"

#: Tokens read and written, counted from the usage the adapter reported and
#: absent rather than estimated where it reported none.
INFERENCE_TOKENS = "inferops_inference_tokens_total"

#: Which component is failing its readiness check when the platform refuses.
READINESS_CHECK_FAILURES = "inferops_readiness_check_failures_total"

#: The emitting process's own memory, from its own view. Declared in the catalog
#: against this emitter and **not emitted**: the only per-process memory figure
#: the standard library exposes is a file, and a module under ``src/inferops`` may
#: not read one. See :mod:`inferops.telemetry.process`.
PROCESS_RESIDENT_MEMORY = "inferops_process_resident_memory_bytes"

#: The emitting process's own processor time.
PROCESS_CPU = "inferops_process_cpu_seconds_total"

#: Every metric this distribution emits, in the order the endpoint publishes
#: them. Every other metric in the catalog belongs to the serving-runtime adapter,
#: to the contract validator, or -- in the one case of
#: :data:`PROCESS_RESIDENT_MEMORY` -- to this emitter with no source it may read;
#: the catalog records which, and why, per metric.
EMITTED_METRICS: tuple[str, ...] = (
    BUILD_INFO,
    INFERENCE_REQUESTS,
    INFERENCE_ERRORS,
    INFERENCE_REQUEST_DURATION,
    INFERENCE_REQUESTS_IN_FLIGHT,
    INFERENCE_TOKENS,
    READINESS_CHECK_FAILURES,
    PROCESS_CPU,
)

# -- bounded value sets -----------------------------------------------------

#: The four values ``inferops.outcome`` takes. A timeout is separated from a
#: server error because the two are operated differently and averaging them
#: hides both.
OUTCOME_SUCCESS = "success"
OUTCOME_CLIENT_ERROR = "client-error"
OUTCOME_SERVER_ERROR = "server-error"
OUTCOME_TIMEOUT = "timeout"

OUTCOMES: tuple[str, ...] = (
    OUTCOME_SUCCESS,
    OUTCOME_CLIENT_ERROR,
    OUTCOME_SERVER_ERROR,
    OUTCOME_TIMEOUT,
)

#: The two values ``inferops.token.direction`` takes.
TOKEN_INPUT = "input"
TOKEN_OUTPUT = "output"

TOKEN_DIRECTIONS: tuple[str, ...] = (TOKEN_INPUT, TOKEN_OUTPUT)

#: The five levels a record carries.
LEVEL_DEBUG = "debug"
LEVEL_INFO = "info"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"
LEVEL_FATAL = "fatal"

LEVELS: tuple[str, ...] = (
    LEVEL_DEBUG,
    LEVEL_INFO,
    LEVEL_WARN,
    LEVEL_ERROR,
    LEVEL_FATAL,
)

#: The four environments ``deployment.environment`` accepts. V1 has exactly one,
#: ``dev``; the other three exist so that a deployment somewhere else has a value
#: to state rather than a field to leave blank. The catalog bounds this attribute
#: at four distinct values and the agreement suite compares that bound to this
#: tuple, so a fifth environment is a catalog change rather than a string.
ENVIRONMENT_LOCAL = "local"
ENVIRONMENT_DEV = "dev"
ENVIRONMENT_STAGING = "staging"
ENVIRONMENT_PRODUCTION = "production"

ENVIRONMENTS: tuple[str, ...] = (
    ENVIRONMENT_LOCAL,
    ENVIRONMENT_DEV,
    ENVIRONMENT_STAGING,
    ENVIRONMENT_PRODUCTION,
)

# -- the events a record is identified by -----------------------------------

#: The deployment finished starting and began accepting work.
EVENT_DEPLOYMENT_STARTED = "deployment.started"

#: The deployment stopped accepting work and began draining.
EVENT_DEPLOYMENT_DRAINING = "deployment.draining"

#: The deployment finished draining and released the adapter.
EVENT_DEPLOYMENT_STOPPED = "deployment.stopped"

#: A request arrived and was routed. Written before anything can fail, so that a
#: refusal that never reached a handler is still findable.
EVENT_REQUEST_RECEIVED = "request.received"

#: A request closed with a success.
EVENT_REQUEST_COMPLETED = "request.completed"

#: A request closed with a canonical refusal.
EVENT_REQUEST_REFUSED = "request.refused"

#: A readiness check answered no, naming the component that answered it.
EVENT_READINESS_FAILED = "readiness.failed"

#: Every event this distribution writes. Bounded on purpose: ``inferops.event``
#: is a ``bounded-small`` attribute, and its value set is this tuple.
EVENTS: tuple[str, ...] = (
    EVENT_DEPLOYMENT_STARTED,
    EVENT_DEPLOYMENT_DRAINING,
    EVENT_DEPLOYMENT_STOPPED,
    EVENT_REQUEST_RECEIVED,
    EVENT_REQUEST_COMPLETED,
    EVENT_REQUEST_REFUSED,
    EVENT_READINESS_FAILED,
)

#: The component names ``inferops.component`` takes on a readiness failure. Two,
#: because readiness is the conjunction of two answers and an operator needs to
#: know which half said no.
COMPONENT_API = "api"
COMPONENT_ADAPTER = "serving-adapter"

COMPONENTS: tuple[str, ...] = (COMPONENT_API, COMPONENT_ADAPTER)

# -- where the names came from ----------------------------------------------

CATALOG_DATA_REF = "docs/telemetry/telemetry-catalog.v1alpha1.json"
CATALOG_DOCUMENT_REF = "docs/telemetry/telemetry-catalog.md"
CATALOG_DECISION_REF = (
    "docs/architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md"
)
REDACTION_REF = "docs/telemetry/redaction.md"
INSTRUMENTATION_REF = "docs/telemetry/api-instrumentation.md"
