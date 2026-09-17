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
somebody wrote -- and replays every alert it can over the telemetry two real failure
experiments recorded, so that what an alert would have done during a measured failure
is a result rather than an intention.

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
    check_alerts,
    evaluate_alerts,
    firing_instants,
    load_alert_record,
    runbook_anchors,
)
from .render import GROUP_NAME, render_rules, serialise
from .replay import CAPTURE_PATHS, Replay, load_capture, reconstruct, replay_alerts

__all__ = [
    "ALERT_RECORD_PATH",
    "CAPTURE_PATHS",
    "FIXTURE_DIR",
    "GROUP_NAME",
    "RENDER_PATHS",
    "RULE_IDS",
    "SIGNALS",
    "Finding",
    "Replay",
    "check_alerts",
    "evaluate_alerts",
    "firing_instants",
    "load_alert_record",
    "load_capture",
    "reconstruct",
    "render_rules",
    "replay_alerts",
    "runbook_anchors",
    "serialise",
]
