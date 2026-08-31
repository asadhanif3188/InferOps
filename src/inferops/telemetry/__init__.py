"""Telemetry: the names the catalog decided, and the machinery that emits them.

This package is the first thing in this repository that emits a signal. Until it
existed, [the telemetry catalog](../../../docs/telemetry/telemetry-catalog.v1alpha1.json)
recorded ``emissionStatus`` as ``nothing-emits`` and every rule in it was a
property of one committed document checked against another. What changes here is
narrow and worth stating exactly: **the InferOps API now emits the metrics the
catalog assigns to it and writes the structured records the catalog specifies.**
The adapter's metrics, the validator's metric, spans, and any exporter, collector,
or store are all still absent, and the catalog records each one per metric rather
than leaving a reader to infer it.

Four modules, and the split between them is the catalog's own layering:

| Module | What it holds |
|---|---|
| :mod:`~inferops.telemetry.names` | Every attribute, metric, event, and bounded value set, copied from the accepted catalog |
| :mod:`~inferops.telemetry.registry` | An in-process metric registry and the Prometheus text exposition it renders |
| :mod:`~inferops.telemetry.records` | Structured log records, and the field allowlist that is the redacting sink |
| :mod:`~inferops.telemetry.resource` | What one emitting process is, read from configuration and validated |

The instrument set the API binds to these is one layer up, in
:mod:`inferops.api.observability`, because which moments in a request are
instrumented is the API's decision and not this package's.

**Three properties hold structurally rather than by convention.**

*A forbidden field has no name to be written under.* A record is built through an
allowlist of the catalog's published attribute names, and there is no name in it
for a prompt, a completion, a provider error body, a secret, an authorization
header, or a value read out of a submitted document. There is no free-form
message field, no ``extra`` mapping, and no pass-through to the encoder.

*A request-scoped or unbounded identifier cannot become a metric label.* The
registry refuses a label name outside the set the catalog permits, so a
correlation identifier, a request identifier, a trace identifier, a workload
version, a tenant identifier, or a measured duration is a construction error
rather than a series somebody finds in a bill.

*Nothing here selects a telemetry vendor.* `ADR 0006` `D8` left the SDK, the
exporter, the collector, and the store open, and this package leaves them open: a
pull endpoint needs no exporter, and where log records go is an argument the
composition point supplies.
"""

from __future__ import annotations

from . import names, process
from .records import (
    ALLOWED_FIELDS,
    DISCARDING_SINK,
    REQUIRED_FIELDS,
    Sink,
    StructuredLogEmitter,
    encode,
    record,
    stderr_sink,
    stream_sink,
    timestamp,
)
from .registry import (
    EXPOSITION_CONTENT_TYPE,
    LABEL_VALUE,
    REQUEST_DURATION_BUCKETS,
    UNKNOWN,
    Metric,
    MetricRegistry,
    MetricSpec,
)
from .resource import (
    SERVICE_NAME,
    TELEMETRY_ENVIRONMENT_VARIABLES,
    ResourceAttributes,
    WorkloadIdentity,
    from_environment,
)

__all__ = [
    "ALLOWED_FIELDS",
    "DISCARDING_SINK",
    "EXPOSITION_CONTENT_TYPE",
    "LABEL_VALUE",
    "REQUEST_DURATION_BUCKETS",
    "REQUIRED_FIELDS",
    "SERVICE_NAME",
    "TELEMETRY_ENVIRONMENT_VARIABLES",
    "UNKNOWN",
    "Metric",
    "MetricRegistry",
    "MetricSpec",
    "ResourceAttributes",
    "Sink",
    "StructuredLogEmitter",
    "WorkloadIdentity",
    "encode",
    "from_environment",
    "names",
    "process",
    "record",
    "stderr_sink",
    "stream_sink",
    "timestamp",
]
