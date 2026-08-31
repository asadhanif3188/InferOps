"""The metrics endpoint, and what it now publishes.

`ADR 0010` put ``/metrics`` in the endpoint subset this API serves. Until this
change it answered with an exposition carrying **no metric family and no sample**,
and the reason was recorded here rather than left to be inferred: nothing in this
repository emitted a metric, the accepted catalog said so, and publishing a
partial counter would have made that record false in the same change that
implemented an endpoint.

**That is the gap this module now closes.** The API is the component that receives
an inference request, so it is the component positioned to count one -- which is
the closure `ADR 0002` `T7` records for the request counter the selected runtime
does not have. The series come from :class:`~inferops.api.observability.ApiTelemetry`,
which declares the metrics the catalog assigns to the ``inferops-api`` emitter and
nothing else.

**What is still absent is absent on the record, not by omission.** The metrics
whose emitter is the serving-runtime adapter or the contract validator are not
emitted here, no exporter, collector, store, dashboard, or alert is selected, and
no span is produced. The catalog carries an ``emission`` field per metric so that
a reader finds out which is which from the accepted record rather than by
scraping and comparing.

This module holds the endpoint's constants. The registry, the label rules, and the
exposition format live in :mod:`inferops.telemetry`, so that the thing that
answers a route and the thing that owns a series stay separable.
"""

from __future__ import annotations

from ..telemetry import names
from ..telemetry.registry import EXPOSITION_CONTENT_TYPE

__all__ = [
    "BOUND_METRIC_NAMES",
    "CATALOG_REF",
    "EXPOSITION_CONTENT_TYPE",
    "SURFACE_REF",
]

#: Every metric name this endpoint publishes. It is the catalog's ``inferops-api``
#: emitter set, in the order the exposition writes it, and the two the accepted
#: API surface binds to this endpoint --
#: ``inferops_inference_requests_total`` and ``inferops_inference_errors_total`` --
#: are both in it.
BOUND_METRIC_NAMES: tuple[str, ...] = names.EMITTED_METRICS

#: Where the metric names, their labels, and the cardinality budget are decided.
CATALOG_REF = names.CATALOG_DATA_REF

#: Where this endpoint's place in the accepted API surface is published.
SURFACE_REF = "docs/serving/inference-api-surface.v1alpha1.json"
