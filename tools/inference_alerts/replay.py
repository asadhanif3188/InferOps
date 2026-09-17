"""Replay the alerts against what a real collector returned during an experiment.

The fixtures say what an alert does over telemetry somebody wrote. This says what
each alert would have done over telemetry a real Prometheus actually returned, on a
real cluster, while a real failure was happening -- which is a different and stronger
question, and the one the acceptance criterion asks.

**What a capture is.** The failure experiments committed the answers to a handful of
range queries: an expression, and for each series it returned, its label set and its
samples. That is a set of *query results*, not the store they came from, so replaying
an alert over one needs a declared reconstruction:

``sum(metric)`` and ``sum by (...) (metric)``
    The value of ``metric`` summed over the labels the query kept. A store holding
    one series per returned result, named ``metric`` and carrying those labels,
    gives an alert reading ``metric`` the same number it would have read from the
    real store -- as a sum over fewer series. The output can carry fewer labels than
    it would have; an alert's verdict is a comparison, so it does not depend on them.

a bare selector
    Taken as the metric itself, with the labels the result carried.

anything else
    Refused, and named in the result. ``a / b`` is two metrics divided and cannot be
    read back as either; ``count by (...)`` is a number of series rather than their
    value. A reconstruction that guessed at one of those would be a fabricated store
    wearing a measurement's name.

**And what it is not.** No Prometheus evaluated an alerting rule during either
experiment -- no rule file existed then and none is loaded now. This is a replay
performed by this repository's own evaluator over a reconstruction this module
performs. It is stronger than a fixture, because the numbers were measured, and
weaker than an alert that fired, because nothing fired.

An alert whose expression reads a series no capture holds is reported as
``not-in-the-capture`` rather than as silent. The two answers are not the same, and a
replay that spelled them the same would be worthless.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from tools.telemetry_correlation import Series, Store, evaluate, metrics_read, parse
from tools.telemetry_correlation.evaluate import NAME_LABEL

__all__ = [
    "CAPTURE_PATHS",
    "Replay",
    "load_capture",
    "reconstruct",
    "replay_alerts",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The committed experiment captures an alert may be replayed against. Both are
#: range-query answers recorded by a real collector on the `docker-desktop`
#: provider, during a real failure, on one host.
CAPTURE_PATHS: Final[dict[str, Path]] = {
    "v1-s4-006-pr1": REPO_ROOT
    / "docs/proof/serving/v1-s4-006-pr1-telemetry.v1alpha1.json",
    "v1-s4-007-pr1": REPO_ROOT
    / "docs/proof/serving/v1-s4-007-pr1-telemetry.v1alpha1.json",
}

#: ``sum(metric)``, ``sum by (a, b) (metric)``, or a bare selector with or without
#: matchers. Deliberately narrow: what it does not match is refused rather than
#: approximated.
RECONSTRUCTABLE: Final = re.compile(
    r"^\s*(?:"
    r"sum\s*(?:by\s*\([^)]*\)\s*)?\(\s*(?P<aggregated>[A-Za-z_:][A-Za-z0-9_:]*)\s*\)"
    r"|(?P<bare>[A-Za-z_:][A-Za-z0-9_:]*)\s*(?:\{[^}]*\})?"
    r")\s*$"
)

HISTOGRAM_SUFFIX: Final = re.compile(r"_(bucket|count|sum)$")


@dataclass(frozen=True)
class Replay:
    """What one alert did over one capture.

    ``verdict`` is ``fires``, ``silent``, or ``not-in-the-capture``.

    ``held_instants`` is the longest run of consecutive evaluations the condition
    was true for and ``held_seconds`` is the span that run covers, which is what
    makes a near miss legible: a condition true for 20 consecutive evaluations
    against a window needing 21 did not fire, and ``0`` instants and ``1`` are
    different answers that a span alone spells the same.
    """

    alert_id: str
    verdict: str
    held_instants: int
    held_seconds: float
    window_seconds: float
    first_firing_instant: float | None
    missing: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "alertId": self.alert_id,
            "verdict": self.verdict,
            "heldInstants": self.held_instants,
            "heldSeconds": self.held_seconds,
            "windowSeconds": self.window_seconds,
            "firstFiringInstant": self.first_firing_instant,
            "seriesTheCaptureDoesNotHold": list(self.missing),
        }


def load_capture(path: Path) -> dict[str, Any]:
    """One committed experiment telemetry record."""
    capture: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return capture


def _metric_of(expression: str) -> str | None:
    match = RECONSTRUCTABLE.match(expression)
    if match is None:
        return None
    return match.group("aggregated") or match.group("bare")


def reconstruct(capture: Mapping[str, Any]) -> tuple[list[Series], set[str], list[str]]:
    """The capture as series, the metric names it holds, and what was refused.

    A name appears in the second element only when the capture actually asked for
    it, whatever it returned: an expression that returned nothing is a measurement
    that the series was absent, and an alert reading it is answerable from this
    capture and silent, not unanswerable.
    """
    series: list[Series] = []
    held: set[str] = set()
    refused: list[str] = []
    for entry in capture.get("series") or []:
        expression = str(entry.get("expr", ""))
        metric = _metric_of(expression)
        if metric is None:
            refused.append(expression)
            continue
        held.add(metric)
        for result in entry.get("result") or []:
            labels = {
                key: str(value)
                for key, value in (result.get("labels") or {}).items()
                if key != NAME_LABEL
            }
            labels[NAME_LABEL] = metric
            points = tuple(
                (float(instant), float(value))
                for instant, value in (result.get("values") or [])
            )
            if points:
                series.append(Series(tuple(sorted(labels.items())), points))
    return series, held, refused


def _instants(capture: Mapping[str, Any], window: float) -> list[float]:
    """Every instant the replay evaluates at: one per step, once the window is full."""
    span = capture["range"]
    step = float(span["stepSeconds"])
    start = float(span["startEpochMs"]) / 1000.0
    end = float(span["endEpochMs"]) / 1000.0
    instants: list[float] = []
    instant = start + window
    while instant <= end + 1e-9:
        instants.append(instant)
        instant += step
    return instants


def _longest_run(flags: Sequence[bool]) -> int:
    """The longest run of consecutive evaluations the condition was true for."""
    longest = 0
    run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    return longest


def replay_alerts(
    record: Mapping[str, Any], capture: Mapping[str, Any]
) -> list[Replay]:
    """Every alert's verdict over one capture, in the record's own order."""
    series, available, _ = reconstruct(capture)
    step = float(capture["range"]["stepSeconds"])
    results: list[Replay] = []
    for alert in record.get("alerts") or []:
        expression = str(alert["expr"])
        window = float(alert["forSeconds"])
        names = {
            HISTOGRAM_SUFFIX.sub("", name) for name in metrics_read(parse(expression))
        }
        missing = tuple(sorted(names - available))
        if missing:
            results.append(
                Replay(
                    str(alert["alertId"]),
                    "not-in-the-capture",
                    0,
                    0.0,
                    window,
                    None,
                    missing,
                )
            )
            continue
        node = parse(expression)
        instants = _instants(capture, window=0.0)
        flags = [bool(evaluate(Store(tuple(series), at), node)) for at in instants]
        needed = round(window / step)
        firing = [
            instants[index]
            for index in range(len(instants))
            if index >= needed and all(flags[index - needed : index + 1])
        ]
        run = _longest_run(flags)
        results.append(
            Replay(
                str(alert["alertId"]),
                "fires" if firing else "silent",
                run,
                max(0.0, (run - 1) * step),
                window,
                firing[0] if firing else None,
                (),
            )
        )
    return results
