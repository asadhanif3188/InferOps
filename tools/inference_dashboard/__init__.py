"""The V1 inference operations dashboard policy, and its Grafana rendering.

It reads the committed dashboard record, holds every panel expression to the
correlation query policy in :mod:`tools.telemetry_correlation`, refuses a panel that
would show missing telemetry as a number or scrape reachability as readiness, and
renders the record as Grafana dashboard JSON.

It contacts no cluster, starts no Grafana, and evaluates nothing against a store that
has ever held a sample. The rendered JSON has not been imported anywhere.
"""

from .core import (
    DASHBOARD_RECORD_PATH,
    RENDER_PATH,
    RULE_IDS,
    Finding,
    check_dashboard,
    evaluate_dashboard,
    load_dashboard_record,
    panel_queries,
)
from .grafana import DATASOURCE, render_grafana, serialise

__all__ = [
    "DASHBOARD_RECORD_PATH",
    "DATASOURCE",
    "RENDER_PATH",
    "RULE_IDS",
    "Finding",
    "check_dashboard",
    "evaluate_dashboard",
    "load_dashboard_record",
    "panel_queries",
    "render_grafana",
    "serialise",
]
