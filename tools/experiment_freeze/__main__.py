"""Check the committed experiment freeze records, or list a record's moved inputs.

    python -m tools.experiment_freeze --check
    python -m tools.experiment_freeze --changes RECORD

``--root DIRECTORY`` reads a copy of the repository instead of this checkout. The
suite uses it to plant defects without touching the committed files.

``--check`` checks every committed freeze record: every freeze field answered, every
record pinned and unchanged since it was pinned, and every revision following the one
before it. Exit status is 0 when every record holds every rule and 1 when one does
not, so the command is usable as a gate.

``--changes`` lists every pinned input of one record whose content differs from its
pin. Exit status is 0 when none differs and 1 when one does. It says nothing about
whether a change is material: a merged revision of the record decides that.

**Both modes read files only.** Neither writes a file, runs an experiment, or
contacts a cluster, a registry, or a network. See docs/proof/experiments/README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .core import REPO_ROOT, RULES, changed_inputs, check_repository, record_paths


def _check(root: Path) -> int:
    findings = check_repository(root)
    statements = {rule.rule_id: rule.statement for rule in RULES}
    for finding in findings:
        print(f"REFUSED  {finding.record}  {finding.rule_id}")
        print(f"         {finding.location}: {finding.detail}")
        print(f"         {statements[finding.rule_id]}")
    records = record_paths(root)
    if findings:
        print(
            f"FAILED: {len(findings)} finding(s) across {len(records)} freeze record(s)"
        )
        return 1
    print(f"PASSED: {len(records)} freeze record(s), every rule held")
    return 0


def _changes(root: Path, record: str) -> int:
    try:
        document = json.loads((root / record).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(
            f"REFUSED: {record} cannot be read as a freeze record: {type(error).__name__}"
        )
        return 2
    changes = changed_inputs(document, root)
    for change in changes:
        actual = change.actual if change.actual is not None else "(absent)"
        print(f"CHANGED  {change.path}")
        print(f"         pinned {change.pinned}")
        print(f"         now    {actual}")
    if changes:
        print(
            f"{len(changes)} pinned input(s) differ from {record}. A run refuses to start "
            "until a merged revision classifies each one."
        )
        return 1
    print(f"UNCHANGED: every pinned input of {record} has its pinned content")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.experiment_freeze")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="check every committed record"
    )
    mode.add_argument(
        "--changes", metavar="RECORD", help="list a record's moved inputs"
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments.check:
        return _check(arguments.root)
    return _changes(arguments.root, arguments.changes)


if __name__ == "__main__":
    sys.exit(main())
