"""Ask a running Prometheus every panel expression, and say how each one reads.

The policy in :mod:`.core` holds a panel to what its record says, and
:func:`.core.evaluate_dashboard` runs it over hand-written fixtures. Neither can say
what a real collector returns, and the review of the first dashboard found two
properties of a real Prometheus -- a counter born at what it counted before its first
scrape, a rate outliving an outage --
that no fixture modelled. This module is the part that asks.

It sends each expression, verbatim, to one Prometheus HTTP API as an instant query
and classifies the answer in the dashboard's own terms:

``empty``
    No sample. The panel shows its missing, not-emitted, or no-value text.
``zero``
    Every sample reads exactly ``0``.
``value``
    At least one sample reads a number other than ``0``, an infinity included.
``nan``
    At least one sample reads ``NaN`` and none reads a non-zero number: an
    idle latency window, drawn as a gap rather than as the missing text.
``refused``
    Prometheus did not evaluate the expression. The error type and message are kept.

**It records labels as they are returned.** A panel may only name labels the catalog
permits, and the collector drops the rest before storage, so a returned label set is
already bounded by those two checks; the suite checks every committed reading against
the barred label list anyway. It contacts only the URL it is given, sends no
inference request, and changes nothing.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from .core import panel_queries

__all__ = [
    "READINGS",
    "capture",
    "classify",
    "http_query",
]

#: Every reading :func:`classify` can return, in the order the evidence reports them.
READINGS: tuple[str, ...] = ("empty", "zero", "value", "nan", "refused")

#: What a query function returns: Prometheus's decoded ``/api/v1/query`` response.
QueryFunction = Callable[[str], Mapping[str, Any]]

#: How long one instant query may take. Every expression here is a small aggregation
#: over one release's series; a query that takes longer than this is a fault.
QUERY_TIMEOUT_SECONDS = 30.0


def http_query(base_url: str, *, at: float | None = None) -> QueryFunction:
    """A query function asking the Prometheus at ``base_url``, optionally at one instant.

    Passing ``at`` pins every expression of one capture to the same evaluation time,
    so a capture is one moment rather than thirty neighbouring ones.
    """
    endpoint = base_url.rstrip("/") + "/api/v1/query"

    def ask(expression: str) -> Mapping[str, Any]:
        parameters = {"query": expression}
        if at is not None:
            parameters["time"] = f"{at:.3f}"
        request = urllib.request.Request(
            endpoint,
            data=urllib.parse.urlencode(parameters).encode("ascii"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(
                request, timeout=QUERY_TIMEOUT_SECONDS
            ) as response:
                decoded: Mapping[str, Any] = json.loads(response.read())
        except urllib.error.HTTPError as error:
            # Prometheus answers a query it cannot parse or evaluate with 400 or 422
            # and a JSON body naming the error. That is a reading, not a crash.
            decoded = json.loads(error.read())
        return decoded

    return ask


def _samples(data: Mapping[str, Any]) -> list[tuple[dict[str, str], str]]:
    result_type = data.get("resultType")
    result = data.get("result")
    if result_type == "scalar" and isinstance(result, list):
        return [({}, str(result[1]))]
    if result_type != "vector" or not isinstance(result, list):
        raise ValueError(f"unsupported instant result type {result_type!r}")
    samples = []
    for element in result:
        labels = {str(key): str(value) for key, value in element["metric"].items()}
        samples.append((labels, str(element["value"][1])))
    return samples


def classify(response: Mapping[str, Any]) -> dict[str, Any]:
    """One Prometheus instant-query response, as a reading and its rows."""
    if response.get("status") != "success":
        return {
            "reading": "refused",
            "errorType": str(response.get("errorType", "")),
            "error": str(response.get("error", "")),
            "rows": [],
        }
    samples = _samples(response["data"])
    rows = [
        {"labels": dict(sorted(labels.items())), "value": value}
        for labels, value in sorted(samples, key=lambda item: sorted(item[0].items()))
    ]
    if not samples:
        reading = "empty"
    else:
        numbers = [float(value) for _, value in samples]
        # An infinity is a number an operator reads, not a zero: only NaN is set aside.
        if any(not math.isnan(number) and number != 0 for number in numbers):
            reading = "value"
        elif any(math.isnan(number) for number in numbers):
            reading = "nan"
        else:
            reading = "zero"
    return {"reading": reading, "rows": rows}


def capture(record: Mapping[str, Any], ask: QueryFunction) -> dict[str, dict[str, Any]]:
    """Every panel expression's reading, keyed ``panel/refId``, asked through ``ask``.

    Every query is sent whatever its profiles, because the Grafana JSON sends every
    query whatever the profile: a runtime query against a mock release is asked and
    reads ``empty``, which is what an operator would see.
    """
    return {
        query["queryId"]: classify(ask(str(query["expr"])))
        for query in panel_queries(record)
    }
