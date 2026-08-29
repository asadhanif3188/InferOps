"""The metrics endpoint, and the reason it publishes no series.

`ADR 0010` puts `/metrics` in the endpoint subset this API serves, so the route
exists and answers. What it answers with is an exposition carrying **no metric
family and no sample**, and that is a decision rather than an unfinished edge.

**Nothing in this repository emits a metric, and the accepted catalog says so.**
[The telemetry catalog](../../../docs/telemetry/telemetry-catalog.v1alpha1.json)
records ``emissionStatus`` as ``nothing-emits``, and every metric in it —
including the two this surface binds to this endpoint,
``inferops_inference_requests_total`` and ``inferops_inference_errors_total`` —
carries ``v1Status: specified``. Publishing a sample from here would make that
record false in the same change that implements an endpoint, and it would publish
a counter under a name whose accepted label set this API cannot populate: the
request counter is labelled by workload identity, and no workload identity
reaches this API yet.

**Instrumenting this API is the telemetry work**, which depends on this API
existing for exactly this reason. That is where the label set, the collector, the
`ADR 0002` `T7` obligation the request counter discharges, and the catalog's
``emissionStatus`` are settled together. Serving an endpoint here and leaving the
signal to the work that owns it keeps the two separable; emitting a partial
counter now would make the endpoint look instrumented and would have to be
unpicked.

So the body below is a valid exposition that a scraper accepts and that reports
zero families, with a comment naming what is not there and where it is owned. A
comment is not a metric: no ``HELP`` line, no ``TYPE`` line, and no sample is
written, so nothing here registers a family with zero series either.
"""

from __future__ import annotations

#: The content type of the Prometheus text exposition format. The version
#: parameter is part of the media type rather than decoration; a scraper reads it
#: to decide how to parse what follows.
EXPOSITION_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

#: The two metric names the accepted API surface binds to this endpoint. They are
#: named in the body so that a reader scraping this endpoint finds out what is
#: missing from the endpoint itself, and they are named as text rather than
#: written as families for the reason in the module docstring.
BOUND_METRIC_NAMES: tuple[str, ...] = (
    "inferops_inference_requests_total",
    "inferops_inference_errors_total",
)

#: Where the obligation to emit them is recorded, and where it is owned.
CATALOG_REF = "docs/telemetry/telemetry-catalog.v1alpha1.json"
SURFACE_REF = "docs/serving/inference-api-surface.v1alpha1.json"


def exposition() -> str:
    """The exposition this endpoint returns: no family, no sample, and a reason.

    Every line is a comment, and the format permits a body of comments alone. A
    scraper reading it records zero series from this target, which is an accurate
    description of a component that emits nothing.
    """
    lines = [
        "# InferOps serves this endpoint and emits no metric.",
        f"# The accepted telemetry catalog ({CATALOG_REF}) records emissionStatus",
        "# as nothing-emits, and every metric in it is specified rather than",
        "# emitted. The two the accepted API surface binds to this endpoint are:",
    ]
    lines += [f"#   {name}" for name in BOUND_METRIC_NAMES]
    lines += [
        f"# Both are published in {SURFACE_REF} and neither is produced here.",
        "# Instrumenting this API is the telemetry work, which depends on this",
        "# API existing. Neither counter is emitted by anything today.",
    ]
    return "\n".join(lines) + "\n"
