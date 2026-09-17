"""Check, evaluate, and render the committed V1 inference alerts.

    python -m tools.inference_alerts
    python -m tools.inference_alerts --json
    python -m tools.inference_alerts --evaluate
    python -m tools.inference_alerts --rules real
    python -m tools.inference_alerts --rules mock

The first two apply the alert policy. Exit status is 0 when nothing is refused and
1 when anything is, so the command is usable as a gate. ``--evaluate`` runs every
alert across every committed scenario fixture and prints, for each, what its
expression returns at the fixture's last instant and whether the alert would have
been firing there -- the second is the answer the fixtures exist for, because it is
the one that needs the whole ``for`` window rather than one instant.

``--rules`` prints the Prometheus alerting-rule file for one profile, which is what
the committed file under ``deploy/prometheus/`` is compared against. Nothing is
written, and a record the policy refuses renders nothing.

**Every mode reads files.** None starts a Prometheus, loads a rule file, or knows
what a receiver is. See docs/telemetry/inference-alerts.md.
"""

from __future__ import annotations

import argparse
import json
import sys

from tools.telemetry_correlation import load_fixture

from .core import (
    FIXTURE_DIR,
    check_alerts,
    evaluate_alerts,
    firing_instants,
    load_alert_record,
)
from .render import render_rules, serialise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.inference_alerts",
        description=(
            "Apply the alert policy to the committed alert record, evaluate its "
            "alerts across the committed scenarios, or print a Prometheus rule file."
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="emit findings as JSON")
    group.add_argument(
        "--evaluate",
        action="store_true",
        help="run every alert across every scenario and print what it does",
    )
    group.add_argument(
        "--rules",
        choices=("mock", "real"),
        help="print the Prometheus alerting-rule file for this profile",
    )
    arguments = parser.parse_args(argv)

    record = load_alert_record()
    findings = check_alerts(record)

    if (arguments.evaluate or arguments.rules) and findings:
        print(
            "REFUSED  the alert record does not satisfy the alert policy",
            file=sys.stderr,
        )
        return 1

    if arguments.rules:
        print(
            serialise(render_rules(record, arguments.rules), arguments.rules, record),
            end="",
        )
        return 0

    if arguments.evaluate:
        for scenario in record["scenarios"]:
            fixture = load_fixture(FIXTURE_DIR / f"{scenario['scenarioId']}.yaml")
            results = evaluate_alerts(record, fixture)
            print(f"== {scenario['scenarioId']} ({scenario['profile']})")
            for alert in record["alerts"]:
                key = str(alert["alertId"])
                if key not in results:
                    continue
                firing = firing_instants(alert, fixture)
                expected = (alert.get("scenarioExpectations") or {}).get(
                    scenario["scenarioId"]
                )
                verdict = "FIRING " if firing else "silent "
                agrees = (
                    "ok" if (bool(firing) == (expected == "fires")) else "DISAGREES"
                )
                print(f"   {verdict} {key}  (expected {expected}: {agrees})")
                for row in results[key]:
                    print(f"       {row}")
        return 0

    if arguments.json:
        print(
            json.dumps(
                {
                    "record": "docs/telemetry/inference-alerts.v1alpha1.json",
                    "alerts": len(record["alerts"]),
                    "deferred": len(record["deferredAlerts"]),
                    "valid": not findings,
                    "findings": [finding.as_dict() for finding in findings],
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif findings:
        print(f"REFUSED {len(record['alerts'])} alert(s)  ({len(findings)} finding(s))")
        for finding in findings:
            print(f"        {finding}")
    else:
        print(f"ok      {len(record['alerts'])} alert(s) satisfy the alert policy")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    sys.exit(main())
