"""The V1 alert policy, and the Prometheus rule files it renders.

It reads the committed alert record, holds every alert expression to the
correlation query policy in :mod:`tools.telemetry_correlation`, and then refuses an
alert that would mislead the operator it wakes: one whose threshold is a number
nothing declares, one that reads scrape reachability and claims to see the
workload, one whose runbook link points at a section that is not there, one whose
window is short enough for a single missed evaluation to fire, and one that has
never been shown both to fire and to stay silent over the committed scenarios.

It then evaluates every accepted alert across each scenario fixture instant by
instant, so that ``for`` is a property the fixtures establish rather than a field
somebody wrote.

It contacts no cluster and scrapes nothing. **No receiver, routing tree, or on-call
rotation is selected in V1**, so an alert this accepts is an alert nothing evaluates
and nobody is told about.
"""

from .core import (
    ALERT_RECORD_PATH,
    FIXTURE_DIR,
    RENDER_PATHS,
    RULE_IDS,
    SIGNALS,
    Finding,
    alert_queries,
    check_alerts,
    evaluate_alerts,
    firing_instants,
    load_alert_record,
    runbook_anchors,
)
from .render import GROUP_NAME, render_rules, serialise

__all__ = [
    "ALERT_RECORD_PATH",
    "FIXTURE_DIR",
    "GROUP_NAME",
    "RENDER_PATHS",
    "RULE_IDS",
    "SIGNALS",
    "Finding",
    "alert_queries",
    "check_alerts",
    "evaluate_alerts",
    "firing_instants",
    "load_alert_record",
    "render_rules",
    "runbook_anchors",
    "serialise",
]
