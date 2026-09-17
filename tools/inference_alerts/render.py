"""The alert record as a Prometheus alerting-rule file, one per profile.

Prometheus's rule format is a format, not a service. Rendering into it commits
nothing about who evaluates the file, who receives what it produces, or whether
anybody is on the other end -- none of which is decided. What it does commit to is
that every field an operator needs travels with the alert rather than living in a
document beside it: the owner, the severity, what the caller sees, what to do, and
the link to the section that says how.

Two files, because one of the alerts reads a recorded series the chart renders only
under the real profile. A single file would have carried, into a mock release, an
expression that can only ever be empty -- an alert that never fires, which is the
one failure an alert file must not have.

The record is authoritative and this is a projection of it. Nothing here reads a
cluster, installs a rule file, or knows what a receiver is.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

import yaml

__all__ = ["GROUP_NAME", "render_rules", "serialise"]


class _Block(str):
    """A string the dumper writes as a literal block rather than folding it.

    Prose belongs on its own lines. An annotation folded to fit a column reflows
    the moment a word changes, which turns a one-word edit into a paragraph-sized
    diff, and an expression folded across a line break is the one value in this
    file that has to be read exactly as written.
    """


class _Dumper(yaml.SafeDumper):
    pass


def _block(dumper: yaml.SafeDumper, data: _Block) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


_Dumper.add_representer(_Block, _block)

GROUP_NAME: Final = "inferops-inference-alerts"


def _duration(seconds: int) -> str:
    """One duration, as Prometheus spells it.

    The rest of this repository spells seconds. The conversion is exact: a window
    that is a whole number of minutes is written in minutes, and one that is not is
    written in seconds rather than rounded into a window nobody wrote.
    """
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def _rule(alert: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "alert": alert["name"],
        "expr": alert["expr"],
        "for": _duration(int(alert["forSeconds"])),
        "labels": {
            "severity": alert["severity"],
            "owner": alert["owner"],
            "signal": alert["signal"],
            "inferops_alert_id": alert["alertId"],
        },
        "annotations": {
            "summary": _Block(alert["condition"]),
            "impact": _Block(alert["userImpact"]),
            "action": _Block(alert["operatorAction"]),
            "blind_spot": _Block(alert["whatItCannotSee"]),
            "runbook": alert["runbookRef"],
            "evidence": ", ".join(alert.get("evidenceRefs") or []),
            "not_routed": _Block(str(record["routing"]["statement"])),
        },
    }


def render_rules(record: Mapping[str, Any], profile: str) -> dict[str, Any]:
    """The rule group for one profile, as the data a YAML dump writes."""
    interval = int(record["evaluation"]["ruleEvaluationIntervalSeconds"])
    rules = [
        _rule(alert, record)
        for alert in record["alerts"]
        if profile in (alert.get("profiles") or ["mock", "real"])
    ]
    return {
        "groups": [
            {"name": GROUP_NAME, "interval": _duration(interval), "rules": rules}
        ]
    }


def serialise(
    document: Mapping[str, Any], profile: str, record: Mapping[str, Any]
) -> str:
    """The rule file as text, with the header that says what it is not.

    Key order is the order :func:`render_rules` builds, not alphabetical, because a
    rule reads as ``alert``, ``expr``, ``for``, then the labels and annotations, and
    a file sorted by key reads as none of those things.
    """
    header = (
        f"# InferOps inference alerts, {profile} profile. GENERATED -- do not edit.\n"
        f"#\n"
        f"# Generated from {record['$id'].rsplit('/', 1)[-1]} by\n"
        f"# python -m tools.inference_alerts --rules {profile}\n"
        f"# and compared against it by tests/telemetry/test_inference_alerts.py.\n"
        f"#\n"
        f"# {record['routing']['statement']}\n"
    )
    body = yaml.dump(
        document,
        Dumper=_Dumper,
        sort_keys=False,
        default_flow_style=False,
        width=10_000,
        allow_unicode=False,
    )
    return header + body
