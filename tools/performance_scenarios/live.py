"""Asking the release's own collector what it recorded while the scenarios ran.

The only code in this package that contacts anything. It sends Prometheus HTTP API
queries to one loopback URL: range queries for the descriptor's series over the
whole schedule, instant queries at the moments reconciliation compares, and the
dashboard's panel expressions at the end of every phase. Proxies in the environment
are ignored and redirects refused. It writes nothing to the cluster.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from tools.inference_dashboard.core import load_dashboard_record
from tools.inference_dashboard.live import capture, classify
from tools.llm_load import core as load

from .core import (
    Descriptor,
    ScenarioError,
    ScenarioRefused,
    instants_for,
    phase_windows,
)

QUERY_TIMEOUT_SECONDS = 30.0

#: (API path, form parameters) -> decoded JSON body.
Asker = Callable[[str, Mapping[str, str]], Mapping[str, Any]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_: Any, **__: Any) -> None:
        return None


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def require_loopback(base_url: str) -> str:
    """Accept only ``http://127.0.0.1:<port>``, with no path, query, or credentials."""
    parts = urllib.parse.urlsplit(base_url)
    try:
        port = parts.port
    except ValueError as error:
        raise ScenarioRefused("the collector URL carries an unusable port") from error
    if (
        parts.scheme != "http"
        or parts.hostname != "127.0.0.1"
        or port is None
        or parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise ScenarioRefused(
            "the collector URL must be http://127.0.0.1:<port> and nothing else"
        )
    return f"http://127.0.0.1:{port}"


def http_asker(base_url: str) -> Asker:
    """Ask the collector at ``base_url``; refuse anything but JSON.

    A query with parameters is a form POST. One without is a GET: Prometheus serves
    its status endpoints to GET only, and answers a POST there with an empty 405,
    which is what the first complete run of this workflow met.
    """
    root = require_loopback(base_url)

    def ask(path: str, parameters: Mapping[str, str]) -> Mapping[str, Any]:
        if parameters:
            request = urllib.request.Request(
                root + path,
                data=urllib.parse.urlencode(dict(parameters)).encode("ascii"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        else:
            request = urllib.request.Request(root + path, method="GET")
        try:
            with _OPENER.open(request, timeout=QUERY_TIMEOUT_SECONDS) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            body = error.read()
            try:
                refused: Mapping[str, Any] = json.loads(body)
            except ValueError:
                raise ScenarioError(
                    f"HTTP {error.code} from the collector without a JSON body"
                ) from error
            if refused.get("status") != "error":
                raise ScenarioError(
                    f"HTTP {error.code} from the collector without a Prometheus error"
                ) from error
            return refused
        except (urllib.error.URLError, TimeoutError) as error:
            raise ScenarioError(f"could not reach the collector: {error}") from error
        try:
            decoded: Mapping[str, Any] = json.loads(body)
        except ValueError as error:
            raise ScenarioError(
                "the collector answered with a body that is not JSON"
            ) from error
        return decoded

    return ask


def _range_result(response: Mapping[str, Any]) -> dict[str, Any]:
    if response.get("status") != "success":
        return {
            "status": "refused",
            "error": str(response.get("error", "")),
            "result": [],
        }
    data = response.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "matrix":
        raise ScenarioError("a range query did not answer with a matrix")
    result: list[dict[str, Any]] = []
    for element in data.get("result") or []:
        labels = {
            str(key): str(value) for key, value in (element.get("metric") or {}).items()
        }
        values = [
            [float(point[0]), str(point[1])] for point in element.get("values") or []
        ]
        result.append({"labels": dict(sorted(labels.items())), "values": values})
    result.sort(key=lambda item: sorted(item["labels"].items()))
    return {"status": "success", "result": result}


def _seconds(epoch_ms: int) -> str:
    return f"{epoch_ms / 1000:.3f}"


def capture_telemetry(
    descriptor: Descriptor,
    windows: Mapping[str, Any],
    raws: Sequence[load.RawSet],
    ask: Asker,
) -> dict[str, Any]:
    """Every collector reading the record needs, keyed so the record can find it."""
    version: str | None = None
    build = ask("/api/v1/status/buildinfo", {})
    if build.get("status") == "success" and isinstance(build.get("data"), dict):
        version = str(build["data"].get("version")) or None

    step = descriptor.range_step_seconds
    start_ms = windows["idleStartMs"] - descriptor.scrape_interval_seconds * 1000
    end_ms = windows["settledMs"]
    series = []
    for series_id, expression in descriptor.series:
        answer = _range_result(
            ask(
                "/api/v1/query_range",
                {
                    "query": expression,
                    "start": _seconds(start_ms),
                    "end": _seconds(end_ms),
                    "step": f"{step}s",
                },
            )
        )
        series.append({"seriesId": series_id, "expr": expression, **answer})

    expressions = descriptor.series_expressions
    instants = []
    for repetition, position, at_ms in instants_for(windows):
        for series_id in sorted(
            {check.series_id for check in descriptor.reconciliation}
        ):
            reading = classify(
                ask(
                    "/api/v1/query",
                    {"query": expressions[series_id], "time": _seconds(at_ms)},
                )
            )
            instants.append(
                {
                    "repetition": repetition,
                    "position": position,
                    "atEpochMs": at_ms,
                    "seriesId": series_id,
                    "status": "success"
                    if reading["reading"] != "refused"
                    else "refused",
                    "rows": reading["rows"],
                }
            )

    record = load_dashboard_record()
    dashboard = []
    for repetition, raw in enumerate(raws, start=1):
        for placed in phase_windows(raw, descriptor):
            at_ms = placed["endEpochMs"]

            def pinned(expression: str, at: int = at_ms) -> Mapping[str, Any]:
                return ask("/api/v1/query", {"query": expression, "time": _seconds(at)})

            dashboard.append(
                {
                    "repetition": repetition,
                    "scenarioId": placed["scenario"].scenario_id,
                    "atEpochMs": at_ms,
                    "readings": capture(record, pinned),
                }
            )

    return {
        "collectorVersion": version,
        "range": {"startEpochMs": start_ms, "endEpochMs": end_ms, "stepSeconds": step},
        "series": series,
        "instants": instants,
        "dashboard": dashboard,
    }
