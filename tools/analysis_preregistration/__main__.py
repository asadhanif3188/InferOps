"""Check the preregistration of the two analysis experiments against its sources.

    python -m tools.analysis_preregistration --check

``--root DIRECTORY`` reads a copy of the repository instead of this checkout. The
suite uses it to plant defects without touching the committed files.

``--check`` reads every committed freeze record of V2-E03 and V2-E06. It checks
the latest revision of each in full, against the latest freeze records of its
source experiments, and each superseded revision against every rule except that
its sources are the latest ones. Exit status is 0 when every rule holds and 1
when one does not, so the command is usable as a precondition of an analysis.

**It reads files only.** It writes no file, runs no analysis, computes no
figure, and contacts no cluster, registry, or network. See
docs/proof/experiments/README.md.
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
            f"FAILED: {len(findings)} finding(s) across {len(EXPERIMENTS)} "
            "analysis experiment(s)"
        )
        return 1
    print(f"PASSED: {len(EXPERIMENTS)} analysis experiment(s), every rule held")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.analysis_preregistration")
    parser.add_argument(
        "--check", action="store_true", required=True, help="check the two records"
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    return _check(arguments.root)


if __name__ == "__main__":
    sys.exit(main())
