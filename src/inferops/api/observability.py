"""The instruments the InferOps API emits, and the events it writes.

The catalog assigns each metric to an emitter. This module declares the ones
whose emitter is ``inferops-api`` and binds them to the moments in a request the
API already has: a request arriving, a request closing, a refusal, a readiness
check answering no. Every metric belonging to ``inferops-adapter`` or to
``inferops-validator`` is deliberately **not** here, and the catalog records per
metric which are emitted and why the rest are not.

**One object holds a process's telemetry.** :class:`ApiTelemetry` owns the
registry, the instruments, the log emitter, and the identity. A request path that
had to remember to increment three counters would eventually forget one, so the
counters move together in :meth:`ApiTelemetry.request_closed` and the call sites
choose an outcome rather than a set of instruments.

**Model and runtime identity is resolved from the adapter, not configured.** A
model identifier in a variable beside the adapter would be a second place for the
truth to live, and the one that is wrong is the one nobody notices. So
:meth:`ApiTelemetry.bind_identity` is called on startup with what the adapter
reported, and until it has been, the model and runtime labels are empty.

**Mock telemetry says it is mock in three places.** ``inferops.runtime.id``
carries the mock runtime's registered identifier onto every operational series,
``inferops.adapter.kind`` carries ``mock`` on the identity metric and on every log
record, and the exposition opens with a comment naming the mock. That is
[the mock and real boundary](../../../docs/serving/mock-and-real-boundary.md)
rule 1 -- a label in the contents rather than in the directory name -- applied to
a scrape, which is the surface most likely to be copied into a dashboard nobody
labels afterwards.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..adapters import MOCK_ADAPTER_KIND
from ..telemetry import names, process
from ..telemetry.records import DISCARDING_SINK, Sink, StructuredLogEmitter
from ..telemetry.registry import (
    COUNTER,
    GAUGE,
    HISTOGRAM,
    REQUEST_DURATION_BUCKETS,
    UNKNOWN,
    MetricRegistry,
    MetricSpec,
)
from ..telemetry.resource import ResourceAttributes, WorkloadIdentity
from .errors import CALLER_DEADLINE, RUNTIME_TIMEOUT, Condition

#: The eight metrics this API emits, each carrying the question the catalog says
#: it answers as its ``HELP`` line. A ninth would be a catalog change first.
#:
#: ``inferops_process_resident_memory_bytes`` is the one metric the catalog
#: assigns to this emitter that is absent here, and the catalog records why: the
#: only per-process memory figure the standard library exposes is a file, and a
#: module under ``src/inferops`` may not read one.
API_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        name=names.BUILD_INFO,
        instrument=GAUGE,
        unit="1",
        help_text=(
            "Exactly which build, model revision, and runtime image produced "
            "every other series on this endpoint."
        ),
        labels=(
            names.SERVICE_VERSION,
            names.CAPABILITY_ID,
            names.RELEASE_ID,
            names.DEPLOYMENT_ENVIRONMENT,
            names.ADAPTER_KIND,
            names.MODEL_ID,
            names.MODEL_REVISION,
            names.RUNTIME_ID,
            names.RUNTIME_IMAGE_DIGEST,
        ),
        identity=True,
    ),
    MetricSpec(
        name=names.INFERENCE_REQUESTS,
        instrument=COUNTER,
        unit="1",
        help_text=(
            "Is the platform serving requests, what fraction of them succeed, "
            "and how many complete per unit of time."
        ),
        labels=(names.WORKLOAD_ID, names.MODEL_ID, names.OUTCOME),
    ),
    MetricSpec(
        name=names.INFERENCE_ERRORS,
        instrument=COUNTER,
        unit="1",
        help_text=(
            "Which named failure is responsible for the failures, and for which "
            "workload."
        ),
        labels=(names.WORKLOAD_ID, names.ERROR_CODE),
    ),
    MetricSpec(
        name=names.INFERENCE_REQUEST_DURATION,
        instrument=HISTOGRAM,
        unit="s",
        help_text=(
            "How long a request takes end to end, at the tail rather than on average."
        ),
        labels=(names.WORKLOAD_ID, names.MODEL_ID),
        buckets=REQUEST_DURATION_BUCKETS,
    ),
    MetricSpec(
        name=names.INFERENCE_REQUESTS_IN_FLIGHT,
        instrument=GAUGE,
        unit="1",
        help_text="How much work is in progress right now, and is it saturating.",
        labels=(names.WORKLOAD_ID, names.MODEL_ID),
    ),
    MetricSpec(
        name=names.INFERENCE_TOKENS,
        instrument=COUNTER,
        unit="1",
        help_text=(
            "How many tokens were read and written, where the runtime reports them."
        ),
        labels=(names.WORKLOAD_ID, names.MODEL_ID, names.TOKEN_DIRECTION),
    ),
    MetricSpec(
        name=names.READINESS_CHECK_FAILURES,
        instrument=COUNTER,
        unit="1",
        help_text=(
            "Which component is failing its readiness check, when the platform "
            "is refusing traffic."
        ),
        labels=(names.WORKLOAD_ID, names.COMPONENT),
    ),
    MetricSpec(
        name=names.PROCESS_CPU,
        instrument=COUNTER,
        unit="s",
        help_text="How much processor time the emitting process is consuming.",
    ),
)

#: What the exposition says about the one metric assigned to this emitter that it
#: does not publish. A comment, because a comment is not a metric: it tells a
#: reader of a scrape why a declared metric is missing rather than leaving them to
#: compare the endpoint against the catalog to find out.
NO_MEMORY_SOURCE_NOTE = (
    f"{names.PROCESS_RESIDENT_MEMORY} is specified and not emitted: the only "
    "per-process memory figure the standard library exposes is a file, and a "
    "module in this distribution may not read one."
)

#: What the exposition opens with when the deployment behind it is the mock.
MOCK_EXPOSITION_NOTE = (
    "This deployment serves the committed mock serving adapter. Every series "
    "below describes a fixture replay and certifies no serving runtime."
)

#: Where a reader of a scrape finds out what these names mean.
EXPOSITION_CATALOG_NOTE = (
    f"Metric names, labels, and the cardinality budget: {names.CATALOG_DATA_REF}"
)


#: The two conditions whose outcome is a timeout rather than an error. The
#: catalog separates a timeout from a server error because the two are operated
#: differently -- one means add capacity or raise a deadline, the other means
#: something is broken -- and averaging them hides both. Naming the conditions
#: rather than the statuses is what keeps that separation true: a caller's
#: deadline elapsing and a runtime's deadline elapsing carry different statuses
#: and are the same operational event.
TIMEOUT_CONDITIONS: frozenset[str] = frozenset(
    {RUNTIME_TIMEOUT.condition_id, CALLER_DEADLINE.condition_id}
)


def outcome_for(condition: Condition | None, status: int | None) -> str:
    """Which of the four outcomes one closed request had.

    A request that named no condition and sent a status below 400 succeeded.
    Everything else is attributed by the condition where one was named and by the
    status otherwise, and a response that was never sent is a server error --
    because it is.
    """
    if condition is not None:
        if condition.condition_id in TIMEOUT_CONDITIONS:
            return names.OUTCOME_TIMEOUT
        return (
            names.OUTCOME_CLIENT_ERROR
            if int(condition.status) < 500
            else names.OUTCOME_SERVER_ERROR
        )
    if status is None:
        return names.OUTCOME_SERVER_ERROR
    if status < 400:
        return names.OUTCOME_SUCCESS
    return names.OUTCOME_CLIENT_ERROR if status < 500 else names.OUTCOME_SERVER_ERROR


@dataclass(frozen=True, slots=True)
class ModelRuntimeIdentity:
    """What the adapter reported about the model and runtime behind this process.

    Empty until :meth:`ApiTelemetry.bind_identity` has been called on startup,
    which is honest rather than tidy: before the adapter has been initialized,
    this process does not know which model it is in front of.
    """

    model_id: str = UNKNOWN
    model_revision: str = UNKNOWN
    runtime_id: str = UNKNOWN


class ApiTelemetry:
    """One process's metrics, log records, and identity.

    Construct one per application. It performs no I/O at construction: the
    registry is in memory, the log sink is whatever the composition point handed
    it, and the process samplers are read at scrape time.
    """

    def __init__(
        self,
        *,
        resource: ResourceAttributes | None = None,
        workload: WorkloadIdentity | None = None,
        sink: Sink = DISCARDING_SINK,
        clock: Callable[[], float],
        cpu_seconds: Callable[[], float] = process.cpu_seconds,
    ) -> None:
        self._resource = resource or ResourceAttributes()
        self._workload = workload or WorkloadIdentity()
        self._identity = ModelRuntimeIdentity(
            model_revision=self._resource.model_revision
        )
        self._registry = MetricRegistry()
        for spec in API_METRICS:
            self._registry.declare(spec)
        self._logs = StructuredLogEmitter(
            resource=self._resource,
            workload=self._workload,
            sink=sink,
            clock=clock,
        )
        self._cpu_seconds = cpu_seconds
        self._publish_build_info()

    # -- what this process is -----------------------------------------------

    @property
    def registry(self) -> MetricRegistry:
        """The registry ``/metrics`` renders."""
        return self._registry

    @property
    def logs(self) -> StructuredLogEmitter:
        """The record emitter, for a call site that writes one directly."""
        return self._logs

    @property
    def resource(self) -> ResourceAttributes:
        return self._resource

    @property
    def workload(self) -> WorkloadIdentity:
        return self._workload

    @property
    def identity(self) -> ModelRuntimeIdentity:
        """What the adapter reported, once startup has bound it."""
        return self._identity

    def bind_identity(
        self,
        *,
        model_id: str,
        model_revision: str | None,
        runtime_id: str,
    ) -> None:
        """Record the model and runtime the adapter reported, on startup.

        The model revision a deployment configured wins over an absent one from
        the adapter and loses to one the adapter actually reported, because the
        adapter is looking at the artifact and the configuration is describing it.
        """
        self._identity = ModelRuntimeIdentity(
            model_id=model_id,
            model_revision=model_revision or self._resource.model_revision,
            runtime_id=runtime_id,
        )
        self._publish_build_info()

    def _publish_build_info(self) -> None:
        """Publish the identity series: one per process, always 1."""
        self._registry[names.BUILD_INFO].set(
            1.0,
            {
                names.SERVICE_VERSION: self._resource.service_version,
                names.CAPABILITY_ID: self._resource.capability_id,
                names.RELEASE_ID: self._resource.release_id,
                names.DEPLOYMENT_ENVIRONMENT: self._resource.deployment_environment,
                names.ADAPTER_KIND: self._resource.adapter_kind,
                names.MODEL_ID: self._identity.model_id,
                names.MODEL_REVISION: self._identity.model_revision,
                names.RUNTIME_ID: self._identity.runtime_id,
                names.RUNTIME_IMAGE_DIGEST: self._resource.runtime_image_digest,
            },
        )

    # -- the labels every operational series carries ------------------------

    def _request_labels(self) -> dict[str, str]:
        return {
            names.WORKLOAD_ID: self._workload.workload_id,
            names.MODEL_ID: self._identity.model_id,
        }

    # -- the moments in a request -------------------------------------------

    def request_started(self, *, correlation_id: str, request_id: str) -> None:
        """A request arrived: count it in flight and write the record.

        The record is written before anything can fail, which is the case the
        catalog's assignment rule exists for -- an unhandled request that never
        reached a handler is the one nobody can find afterwards.
        """
        self._registry[names.INFERENCE_REQUESTS_IN_FLIGHT].adjust(
            1.0, self._request_labels()
        )
        self._logs.emit(
            names.EVENT_REQUEST_RECEIVED,
            correlation_id=correlation_id,
            fields={
                names.REQUEST_ID: request_id,
                names.RUNTIME_ID: self._identity.runtime_id or None,
            },
        )

    def request_closed(
        self,
        *,
        correlation_id: str,
        request_id: str,
        outcome: str,
        duration_seconds: float,
        http_status: int | None = None,
        error_code: str | None = None,
        finish_reason: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        """A request closed: every counter it touches, and one record.

        The instruments move together on purpose. Three call sites each
        remembering to increment a different counter is three chances to forget
        one, and the counter nobody incremented is invisible in exactly the
        incident it was added for.
        """
        if outcome not in names.OUTCOMES:
            raise ValueError(f"{outcome!r} is not a declared outcome")
        labels = self._request_labels()
        self._registry[names.INFERENCE_REQUESTS_IN_FLIGHT].adjust(-1.0, labels)
        self._registry[names.INFERENCE_REQUESTS].add(
            1.0, dict(labels, **{names.OUTCOME: outcome})
        )
        self._registry[names.INFERENCE_REQUEST_DURATION].observe(
            duration_seconds, labels
        )
        if error_code is not None:
            self._registry[names.INFERENCE_ERRORS].add(
                1.0,
                {
                    names.WORKLOAD_ID: self._workload.workload_id,
                    names.ERROR_CODE: error_code,
                },
            )
        # Tokens are counted from what the adapter reported and are absent rather
        # than estimated where it reported none. A count derived by tokenising a
        # prompt here would be an estimate, and an estimate certifies nothing.
        for direction, count in (
            (names.TOKEN_INPUT, input_tokens),
            (names.TOKEN_OUTPUT, output_tokens),
        ):
            if count is not None:
                self._registry[names.INFERENCE_TOKENS].add(
                    float(count),
                    dict(labels, **{names.TOKEN_DIRECTION: direction}),
                )

        succeeded = outcome == names.OUTCOME_SUCCESS
        self._logs.emit(
            names.EVENT_REQUEST_COMPLETED if succeeded else names.EVENT_REQUEST_REFUSED,
            level=names.LEVEL_INFO if succeeded else names.LEVEL_WARN,
            correlation_id=correlation_id,
            fields={
                names.REQUEST_ID: request_id,
                names.MODEL_ID: self._identity.model_id or None,
                names.RUNTIME_ID: self._identity.runtime_id or None,
                names.OUTCOME: outcome,
                names.ERROR_CODE: error_code,
                names.FINISH_REASON: finish_reason,
                names.HTTP_STATUS: http_status,
                names.DURATION_MS: round(duration_seconds * 1000, 3),
            },
        )

    def readiness_failed(self, *, correlation_id: str, component: str) -> None:
        """A readiness check answered no, naming the half that said so."""
        if component not in names.COMPONENTS:
            raise ValueError(f"{component!r} is not a declared component")
        self._registry[names.READINESS_CHECK_FAILURES].add(
            1.0,
            {
                names.WORKLOAD_ID: self._workload.workload_id,
                names.COMPONENT: component,
            },
        )
        self._logs.emit(
            names.EVENT_READINESS_FAILED,
            level=names.LEVEL_WARN,
            correlation_id=correlation_id,
            fields={
                names.COMPONENT: component,
                names.RUNTIME_ID: self._identity.runtime_id or None,
            },
        )

    def deployment_event(self, event: str, *, correlation_id: str) -> None:
        """One of the three lifecycle records: started, draining, stopped."""
        self._logs.emit(
            event,
            correlation_id=correlation_id,
            fields={
                names.MODEL_ID: self._identity.model_id or None,
                names.RUNTIME_ID: self._identity.runtime_id or None,
            },
        )

    # -- what a scrape reads -------------------------------------------------

    def exposition(self) -> str:
        """Sample the process instruments, then render every series it holds.

        The two resource-use instruments are read here rather than on a timer,
        because a scrape is the only moment their value is wanted and a timer
        would be a background task this process does not otherwise need.
        """
        self._registry[names.PROCESS_CPU].sample(self._cpu_seconds())

        preamble = [EXPOSITION_CATALOG_NOTE, NO_MEMORY_SOURCE_NOTE]
        if self._resource.adapter_kind == MOCK_ADAPTER_KIND:
            preamble.insert(0, MOCK_EXPOSITION_NOTE)
        return self._registry.exposition(preamble=preamble)
