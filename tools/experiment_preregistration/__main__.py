"""Check the preregistration of the reliability experiments against its sources.

    python -m tools.experiment_preregistration --check

``--root DIRECTORY`` reads a copy of the repository instead of this checkout. The
suite uses it to plant defects without touching the committed files.

``--check`` reads the latest freeze record of V2-E02A, V2-E02B, V2-E02C, V2-E04,
and V2-E05, and compares each with the qualification, the bound record, and the
baseline comparison that it names, and with the other records. Exit status is 0
when every rule holds and 1 when one does not, so the command is usable as a
precondition of a run.

**It reads files only.** It writes no file, runs no experiment, and contacts no
cluster, registry, or network. See docs/proof/experiments/README.md.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .core import EXPERIMENTS, REPO_ROOT, RULES, check_repository


def _check(root: Path) -> int:
    findings = check_repository(root)
    for finding in findings:
        print(f"REFUSED  {finding.record}  {finding.rule_id}")
        print(f"         {finding.location}: {finding.detail}")
        print(f"         {RULES[finding.rule_id]}")
    if findings:
        print(
            f"FAILED: {len(findings)} finding(s) across {len(EXPERIMENTS)} experiment(s)"
        )
        return 1
    print(f"PASSED: {len(EXPERIMENTS)} experiment record(s), every rule held")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.experiment_preregistration")
    parser.add_argument(
        "--check", action="store_true", required=True, help="check the five records"
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    return _check(arguments.root)


if __name__ == "__main__":
    sys.exit(main())
