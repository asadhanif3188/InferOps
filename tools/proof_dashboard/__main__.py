"""Check, print, or regenerate the V1 proof dashboard.

    python -m tools.proof_dashboard
    python -m tools.proof_dashboard --json
    python -m tools.proof_dashboard --page
    python -m tools.proof_dashboard --check
    python -m tools.proof_dashboard --write

The first two apply the dashboard rules to the claim register. Exit status is 0
when nothing is refused and 1 when anything is, so the command is usable as a
gate. ``--page`` prints the page the register produces today and writes nothing.
``--check`` compares that against the committed ``docs/proof/dashboard.md`` and
reports the first line where they diverge. ``--write`` is the only mode that
touches a file, and it writes that one page.

A refused register renders nothing. That is the point of the ordering: the rules
run first, and a page is never produced from a register that broke one, because a
published page is exactly where a broken rule stops being visible.

**Every mode reads files.** None contacts a cluster, a Prometheus, a runtime, or a
model. See docs/proof/dashboard.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .core import DASHBOARD_PATH, RULES, Finding, check_view, load_record
from .render import render_dashboard


def _report(findings: list[Finding]) -> None:
    statements = {rule.rule_id: rule.statement for rule in RULES}
    for finding in findings:
        print(f"REFUSED  {finding.rule_id}")
        print(f"         {finding.subject}: {finding.detail}")
        print(f"         {statements.get(finding.rule_id, '')}")


def _check(page: str) -> int:
    """Compare the committed page with the one the register produces today."""
    if not DASHBOARD_PATH.exists():
        print(f"MISSING  {DASHBOARD_PATH}")
        print("         regenerate with: python -m tools.proof_dashboard --write")
        return 1

    # Read in text mode on purpose: the comparison is of content, and a checkout
    # that gave the file CRLF is not a difference in what the page says.
    committed = DASHBOARD_PATH.read_text(encoding="utf-8")
    if committed == page:
        print(f"OK       {DASHBOARD_PATH.name} is what the register produces")
        return 0

    committed_lines = committed.splitlines()
    page_lines = page.splitlines()
    pairs = zip(committed_lines, page_lines, strict=False)
    for number, (left, right) in enumerate(pairs, start=1):
        if left != right:
            print(f"DRIFTED  {DASHBOARD_PATH.name} line {number}")
            print(f"         committed: {left}")
            print(f"         register:  {right}")
            break
    else:
        print(
            f"DRIFTED  {DASHBOARD_PATH.name} has {len(committed_lines)} lines; "
            f"the register produces {len(page_lines)}"
        )
    print("         regenerate with: python -m tools.proof_dashboard --write")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.proof_dashboard",
        description=(
            "Apply the dashboard rules to the claim and evidence register, print "
            "the page it produces, or regenerate the committed page."
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="emit findings as JSON")
    group.add_argument(
        "--page",
        action="store_true",
        help="print the page the register produces, without writing it",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="compare the committed page with the register's",
    )
    group.add_argument(
        "--write",
        action="store_true",
        help="regenerate the committed page",
    )
    arguments = parser.parse_args(argv)

    record = load_record()
    findings = check_view(record)

    if findings and (arguments.page or arguments.check or arguments.write):
        print(
            "REFUSED  the register does not satisfy the dashboard rules; no page "
            "was produced",
            file=sys.stderr,
        )
        _report(findings)
        return 1

    if arguments.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
        return 1 if findings else 0

    page = render_dashboard(record) if not findings else ""

    if arguments.page:
        print(page, end="")
        return 0

    if arguments.check:
        return _check(page)

    if arguments.write:
        # Newlines are pinned rather than left to the platform: the committed page
        # is compared with this output, and a generator that writes CRLF on one
        # machine and LF on another turns a no-op into a whole-file diff.
        with DASHBOARD_PATH.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(page)
        print(f"WROTE    {DASHBOARD_PATH}")
        return 0

    if findings:
        _report(findings)
        print(f"{len(findings)} refused")
        return 1

    claims = len(record["claims"])
    print(
        f"OK       {claims} claims satisfy {len(RULES)} dashboard rules; "
        f"run --check to compare the committed page"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
