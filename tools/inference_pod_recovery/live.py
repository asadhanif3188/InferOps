"""Asking the release's own collector what it saw while the inference pod was lost.

The only module in this package that contacts anything. It sends one Prometheus range
query per registered expression over the whole run and nothing else: no instant query,
no dashboard capture, and nothing written to the cluster. The loopback-only asker is
`tools.performance_scenarios.live`'s, reused rather than written a second time, so
there is one place where this repository decides what a collector URL may look like.

Every expression in the descriptor is asked, including the two registered as having
nothing to emit and no source. Asking them is the point: a record that left them out
would be a record of the signals that happened to work.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tools.performance_scenarios.live import Asker, http_asker, require_loopback

from .core import Descriptor, RecoveryError

__all__ = ["Asker", "capture_telemetry", "http_asker", "require_loopback"]


def _range_result(response: Mapping[str, Any]) -> dict[str, Any]:
    """One range answer, as a status and a sorted list of labelled value series."""
    if response.get("status") != "success":
        return {
            "status": "refused",
            "error": str(response.get("error", "")),
            "result": [],
        }
    data = response.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "matrix":
        raise RecoveryError("a range query did not answer with a matrix")
    result: list[dict[str, Any]] = []
    elements = data.get("result") or []
    if not isinstance(elements, list):
        raise RecoveryError("a range query answered with a result that is not a list")
    for element in elements:
        if not isinstance(element, dict):
            raise RecoveryError(
                "a range query answered with an element that is not an object"
            )
        labels = {
            str(key): str(value) for key, value in (element.get("metric") or {}).items()
        }
        values = [
            [float(point[0]), str(point[1])] for point in element.get("values") or []
        ]
        result.append({"labels": dict(sorted(labels.items())), "values": values})
    result.sort(key=lambda entry: sorted(entry["labels"].items()))
    return {"status": "success", "result": result}


def _seconds(epoch_ms: int) -> str:
    return f"{epoch_ms / 1000:.3f}"


def capture_telemetry(
    descriptor: Descriptor,
    *,
    start_epoch_ms: int,
    end_epoch_ms: int,
    ask: Asker,
) -> dict[str, Any]:
    """Every registered expression over the run, keyed so the record can find it.

    The window is widened by one scrape interval on the way in, because a counter
    first appears at whatever it counted before its first scrape and a reading taken
    exactly at the disruption would otherwise have nothing before it to be compared
    against.
    """
    version: str | None = None
    build = ask("/api/v1/status/buildinfo", {})
    if build.get("status") == "success" and isinstance(build.get("data"), dict):
        version = str(build["data"].get("version")) or None

    start = start_epoch_ms - descriptor.scrape_interval_seconds * 1000
    step = descriptor.range_step_seconds
    series = []
    for registered in descriptor.series:
        answer = _range_result(
            ask(
                "/api/v1/query_range",
                {
                    "query": registered.expr,
                    "start": _seconds(start),
                    "end": _seconds(end_epoch_ms),
                    "step": f"{step}s",
                },
            )
        )
        series.append(
            {"seriesId": registered.series_id, "expr": registered.expr, **answer}
        )

    return {
        "collectorVersion": version,
        "range": {
            "startEpochMs": start,
            "endEpochMs": end_epoch_ms,
            "stepSeconds": step,
        },
        "series": series,
    }
