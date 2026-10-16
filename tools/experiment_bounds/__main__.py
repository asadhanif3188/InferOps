"""Print the Q4 bound record of two characterizations, or check the committed ones.

    python -m tools.experiment_bounds STARTUP_RECORD CALLER_RECORD
    python -m tools.experiment_bounds --check

``STARTUP_RECORD`` is the repository path of a committed Q2 record, and
``CALLER_RECORD`` that of a committed Q3 record. The command prints one JSON
record with the four bounds. **Exit status 0 says that the record was printed.**
Exit status 5 says that a rule refused the sources, and no record was printed.

``--check`` builds each committed bound record again from the two source records
that it names, and compares the bytes. Exit status is 1 when one differs.

Exit status is 2 when the arguments are not usable.

**The command reads files and writes nothing.** No option changes a formula.
See docs/proof/experiments/README.md.
"""

from __future__ import annotations

import argparse
import sys

from .core import (
    REFUSED_EXIT,
    BoundsRefused,
    build_record,
    check_committed,
    committed_records,
    record_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.experiment_bounds",
        description="Print the Q4 derived experiment bounds of two characterizations.",
    )
    parser.add_argument(
        "records",
        nargs="*",
        help="the repository paths of a Q2 record and a Q3 record, in that order",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare each committed bound record with its source records",
    )
    arguments = parser.parse_args(argv)

    if arguments.check == bool(arguments.records):
        parser.error("give two record paths or --check")
    if not arguments.check and len(arguments.records) != 2:
        parser.error("give exactly two record paths: a Q2 record and a Q3 record")

    if arguments.check:
        findings = check_committed()
        for finding in findings:
            print(f"FAILED   {finding}", file=sys.stderr)
        if findings:
            return 1
        print(
            f"PASSED: {len(committed_records())} committed bound record(s), each "
            "is what its source records give"
        )
        return 0

    try:
        record = build_record(*arguments.records)
    except BoundsRefused as refused:
        print(f"REFUSED  {refused}", file=sys.stderr)
        return REFUSED_EXIT
    sys.stdout.write(record_text(record))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
