"""Check, evaluate, and render the committed inference operations dashboard.

    python -m tools.inference_dashboard
    python -m tools.inference_dashboard --json
    python -m tools.inference_dashboard --evaluate
    python -m tools.inference_dashboard --grafana
    python -m tools.inference_dashboard --capture URL [--at UNIX_SECONDS]

The first two apply the dashboard policy. Exit status is 0 when nothing is refused
and 1 when anything is, so the command is usable as a gate. ``--evaluate`` runs every
panel query against every committed scenario fixture and prints what it returned.
``--grafana`` prints the Grafana dashboard JSON the committed file under
``deploy/grafana/`` is compared against; nothing is written, and a record the policy
refuses renders nothing.

``--capture`` asks one running Prometheus every panel expression as an instant query
and prints how each reads. It is the only mode that contacts anything: one POST per
expression to the http or https URL it is given, with no proxy and no redirect. A
collector it cannot reach exits 1 with nothing printed on standard output.

**The other modes read files.** None starts a Grafana or a Prometheus. See
docs/telemetry/inference-operations-dashboard.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from tools.telemetry_correlation import FIXTURE_DIR, load_fixture, load_query_record

from .core import check_dashboard, evaluate_dashboard, load_dashboard_record
from .grafana import render_grafana, serialise
from .live import CaptureFailed, capture, http_query


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
    group.add_argument(
        "--capture",
        metavar="URL",
        help=(
            "ask the Prometheus at URL every panel expression and print each "
            "reading as JSON; sends no inference request and changes nothing"
        ),
    )
    parser.add_argument(
        "--at",
        type=float,
        metavar="UNIX_SECONDS",
        help="with --capture, evaluate every expression at this one instant",
    )
    arguments = parser.parse_args(argv)
    if arguments.at is not None and arguments.capture is None:
        parser.error("--at is only meaningful with --capture")
    if arguments.capture is not None and not arguments.capture.strip():
        parser.error("--capture needs a Prometheus URL")

    record = load_dashboard_record()
    findings = check_dashboard(record)

    capturing = arguments.capture is not None
    if (arguments.evaluate or arguments.grafana or capturing) and findings:
        print(
            "REFUSED  the dashboard record does not satisfy the dashboard policy",
            file=sys.stderr,
        )
        return 1

    if arguments.grafana:
        print(serialise(render_grafana(record)), end="")
        return 0

    if capturing:
        at = arguments.at if arguments.at is not None else time.time()
        try:
            readings = capture(record, http_query(arguments.capture, at=at))
        except CaptureFailed as failure:
            print(f"REFUSED  no capture: {failure}", file=sys.stderr)
            return 1
        print(json.dumps({"at": round(at, 3), "readings": readings}, indent=2))
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
