"""Print the endpoint-state record of one collection, or check the committed ones.

    python -m tools.service_endpoint_state DIRECTORY
    python -m tools.service_endpoint_state --check

``DIRECTORY`` is what a collector wrote. The command prints one JSON record.
**Exit status 0 says that the result is OBSERVED.** It does not say that a
Service has a Ready endpoint: a record with zero Ready endpoints is OBSERVED.
Exit status 5 says that the result is REFUSED, and the record states each rule
that refuses. Exit status 1 says that no record was printed: the directory is
not a collection.

``--check`` builds the record of each committed collection again, and compares
it with the committed record. Exit status is 1 when one differs.

Exit status is 2 when the arguments are not usable.

**The command reads files and writes nothing.** It contacts no cluster. See
docs/environment/service-endpoint-state.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    OBSERVED,
    REFUSED_EXIT,
    CollectionRefused,
    build_record,
    check_committed,
    committed_collections,
    record_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.service_endpoint_state",
        description=(
            "Print the Ready endpoint state of the API Service and the runtime "
            "Service in one collection, and the state of each rule."
        ),
    )
    parser.add_argument(
        "directory", nargs="?", type=Path, help="the directory a collector wrote"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare each committed record with its collection",
    )
    arguments = parser.parse_args(argv)

    if (arguments.directory is not None) == arguments.check:
        parser.error("give one of DIRECTORY and --check")

    if arguments.check:
        findings = check_committed()
        for finding in findings:
            print(f"FAILED   {finding}", file=sys.stderr)
        if findings:
            return 1
        print(
            f"PASSED: {len(committed_collections())} committed collection(s), each "
            "record is what its collection gives"
        )
        return 0

    try:
        record = build_record(arguments.directory)
    except CollectionRefused as refused:
        print(f"REFUSED  not-a-collection: {refused}", file=sys.stderr)
        return 1
    sys.stdout.write(record_text(record))
    return 0 if record["result"] == OBSERVED else REFUSED_EXIT


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
