"""Check, evaluate, and render the committed inference operations dashboard.

    python -m tools.inference_dashboard
    python -m tools.inference_dashboard --json
    python -m tools.inference_dashboard --evaluate
    python -m tools.inference_dashboard --grafana

The first two apply the dashboard policy. Exit status is 0 when nothing is refused
and 1 when anything is, so the command is usable as a gate. ``--evaluate`` runs every
panel query against every committed scenario fixture and prints what it returned.
``--grafana`` prints the Grafana dashboard JSON the committed file under
``deploy/grafana/`` is compared against; nothing is written, and a record the policy
refuses renders nothing.

**It reads files.** It starts no Grafana and no Prometheus. See
docs/telemetry/inference-operations-dashboard.md.
"""

from __future__ import annotations

import argparse
import json
import sys

from tools.telemetry_correlation import FIXTURE_DIR, load_fixture, load_query_record

from .core import check_dashboard, evaluate_dashboard, load_dashboard_record
from .grafana import render_grafana, serialise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.inference_dashboard",
        description=(
            "Apply the dashboard policy to the committed dashboard record, evaluate "
            "its panels against the committed scenarios, or print its Grafana JSON."
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="emit findings as JSON")
    group.add_argument(
        "--evaluate",
        action="store_true",
        help="run every panel query against every scenario and print the result",
    )
    group.add_argument(
        "--grafana", action="store_true", help="print the Grafana dashboard JSON"
    )
    arguments = parser.parse_args(argv)

    record = load_dashboard_record()
    findings = check_dashboard(record)

    if (arguments.evaluate or arguments.grafana) and findings:
        print(
            "REFUSED  the dashboard record does not satisfy the dashboard policy",
            file=sys.stderr,
        )
        return 1

    if arguments.grafana:
        print(serialise(render_grafana(record)), end="")
        return 0

    if arguments.evaluate:
        for scenario in load_query_record()["scenarios"]:
            fixture = load_fixture(FIXTURE_DIR / f"{scenario['scenarioId']}.yaml")
            results = evaluate_dashboard(record, fixture)
            print(f"== {scenario['scenarioId']} ({scenario['profile']})")
            for key in sorted(results):
                rows = results[key]
                if rows:
                    print(f"   {key}")
                    for row in rows:
                        print(f"       {row}")
                else:
                    print(f"   {key}  (empty)")
        return 0

    if arguments.json:
        print(
            json.dumps(
                {
                    "record": "docs/telemetry/inference-operations-dashboard.v1alpha1.json",
                    "panels": len(record["panels"]),
                    "valid": not findings,
                    "findings": [finding.as_dict() for finding in findings],
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif findings:
        print(f"REFUSED {len(record['panels'])} panel(s)  ({len(findings)} finding(s))")
        for finding in findings:
            print(f"        {finding}")
    else:
        print(f"ok      {len(record['panels'])} panel(s) satisfy the dashboard policy")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    sys.exit(main())
