"""Render the dashboard record as Grafana dashboard JSON.

The record is the authority and this is a projection of it. Nothing here chooses a
query, a unit, or an empty-state text: each is copied from the record, and the suite
regenerates the committed file and fails if the two differ. What is decided here is
only what Grafana needs that the record does not care about -- panel ids, grid
positions, and display options -- and those are derived deterministically so that a
regenerated file is byte-identical.

Three display choices are deliberate rather than defaults:

- **No colour thresholds.** A green stat reads as health. No panel here has a
  threshold that could be read as one, because no health threshold is decided.
- **The no-value text is the record's ``whenMissing``.** Grafana's default for an
  empty result is a dash or ``No data``, which says nothing about why.
- **One data source variable and nothing else.** The collector is release-scoped,
  so choosing a data source chooses the release. There is no namespace or job
  variable for a query to be silently filtered by.

It writes a file. It does not import the dashboard into Grafana, and nothing in this
repository has.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

__all__ = ["DATASOURCE", "render_grafana", "serialise"]

#: Every query panel reads this. ``${datasource}`` is the template variable below.
DATASOURCE: Final[dict[str, str]] = {"type": "prometheus", "uid": "${datasource}"}

GRID_WIDTH: Final = 24
PANELS_PER_LINE: Final = 4
HEIGHT: Final[dict[str, int]] = {"stat": 5, "text": 5, "timeseries": 8, "table": 8}

#: Columns every table panel hides. ``__name__`` and ``job`` are hidden because a job
#: name is release-qualified and the record's scoping rule is that no panel shows or
#: reads one; ``Time`` because a table here is an instant read. ``Value`` is hidden
#: only where the record says so -- an identity row, whose value is always 1.
#: Independent review found the first version hiding it from every table, including
#: the runtime identity table whose value is the count it exists to show.
TABLE_HIDDEN: Final[dict[str, bool]] = {
    "Time": True,
    "__name__": True,
    "job": True,
}


def _mappings(value_text: Mapping[str, str]) -> list[dict[str, Any]]:
    if not value_text:
        return []
    return [
        {
            "type": "value",
            "options": {
                value: {"index": index, "text": text}
                for index, (value, text) in enumerate(sorted(value_text.items()))
            },
        }
    ]


def _text_content(panel: Mapping[str, Any]) -> str:
    return (
        "**Not answerable from current telemetry.**\n\n"
        f"{panel['description']}\n\n"
        f"Would require: {panel['wouldRequire']}."
    )


def _targets(panel: Mapping[str, Any]) -> list[dict[str, Any]]:
    instant = panel["kind"] in {"stat", "table"}
    targets: list[dict[str, Any]] = []
    for query in panel["queries"]:
        target: dict[str, Any] = {
            "datasource": dict(DATASOURCE),
            "expr": query["expr"],
            "instant": instant,
            "legendFormat": query["legend"],
            "range": not instant,
            "refId": query["refId"],
        }
        if panel["kind"] == "table":
            target["format"] = "table"
        targets.append(target)
    return targets


def _options(kind: str) -> dict[str, Any]:
    if kind == "stat":
        return {
            "colorMode": "none",
            "graphMode": "none",
            "justifyMode": "auto",
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "value_and_name",
        }
    if kind == "timeseries":
        return {
            "legend": {
                "displayMode": "list",
                "placement": "bottom",
                "showLegend": True,
            },
            "tooltip": {"mode": "multi", "sort": "none"},
        }
    if kind == "table":
        return {"showHeader": True}
    return {}


def _panel(
    panel: Mapping[str, Any], panel_id: int, grid: dict[str, int]
) -> dict[str, Any]:
    kind = str(panel["kind"])
    rendered: dict[str, Any] = {
        "description": panel["description"],
        "gridPos": grid,
        "id": panel_id,
        "title": panel["title"],
        "type": kind,
    }
    if kind == "text":
        rendered["options"] = {"content": _text_content(panel), "mode": "markdown"}
        return rendered
    defaults: dict[str, Any] = {
        "color": {"mode": "fixed", "fixedColor": "text"},
        "mappings": _mappings(panel.get("valueText") or {}),
        "noValue": panel["whenMissing"],
        "thresholds": {"mode": "absolute", "steps": [{"color": "text", "value": None}]},
    }
    if panel.get("unit"):
        defaults["unit"] = panel["unit"]
    rendered["datasource"] = dict(DATASOURCE)
    rendered["fieldConfig"] = {"defaults": defaults, "overrides": []}
    rendered["options"] = _options(kind)
    rendered["targets"] = _targets(panel)
    if kind == "table":
        hidden = dict(TABLE_HIDDEN)
        if panel.get("hideValueColumn") is True:
            hidden["Value"] = True
        rendered["transformations"] = [
            {"id": "organize", "options": {"excludeByName": hidden}}
        ]
    return rendered


def _layout(
    panels: Sequence[Mapping[str, Any]], first_id: int, top: int
) -> tuple[list[dict[str, Any]], int, int]:
    rendered: list[dict[str, Any]] = []
    panel_id = first_id
    y = top
    for start in range(0, len(panels), PANELS_PER_LINE):
        line = panels[start : start + PANELS_PER_LINE]
        width = GRID_WIDTH // len(line)
        height = max(HEIGHT[str(panel["kind"])] for panel in line)
        for index, panel in enumerate(line):
            grid = {"h": height, "w": width, "x": index * width, "y": y}
            rendered.append(_panel(panel, panel_id, grid))
            panel_id += 1
        y += height
    return rendered, panel_id, y


def render_grafana(record: Mapping[str, Any]) -> dict[str, Any]:
    """The Grafana dashboard model for the record: one row per declared question."""
    renderer = record["renderer"]
    panels: list[dict[str, Any]] = []
    panel_id = 1
    y = 0
    for question in record["questions"]:
        panels.append(
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": GRID_WIDTH, "x": 0, "y": y},
                "id": panel_id,
                "panels": [],
                "title": question["question"],
                "type": "row",
            }
        )
        panel_id += 1
        y += 1
        members = [
            panel
            for panel in record["panels"]
            if panel["questionId"] == question["questionId"]
        ]
        rendered, panel_id, y = _layout(members, panel_id, y)
        panels.extend(rendered)

    return {
        "annotations": {"list": []},
        "description": record["description"],
        "editable": False,
        "graphTooltip": 1,
        "links": [],
        "panels": panels,
        "refresh": "30s",
        "schemaVersion": renderer["schemaVersion"],
        "tags": ["inferops", "v1alpha1"],
        "templating": {
            "list": [
                {
                    "current": {},
                    "hide": 0,
                    "includeAll": False,
                    "label": "Release collector",
                    "multi": False,
                    "name": record["dataSource"]["grafanaVariable"],
                    "options": [],
                    "query": "prometheus",
                    "refresh": 1,
                    "regex": "",
                    "type": "datasource",
                }
            ]
        },
        "time": {"from": "now-1h", "to": "now"},
        "timepicker": {},
        "timezone": "utc",
        "title": "InferOps inference operations",
        "uid": renderer["uid"],
        "version": 1,
    }


def serialise(dashboard: Mapping[str, Any]) -> str:
    """The committed form: two-space indentation, sorted keys, one trailing newline."""
    return json.dumps(dashboard, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
