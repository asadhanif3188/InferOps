"""Print the gate record of one collection, the declared footprint, or a check.

    python -m tools.capacity_preflight DIRECTORY [--as-collected]
    python -m tools.capacity_preflight --footprint [--key KEY]
    python -m tools.capacity_preflight --check

``DIRECTORY`` is what a collector wrote. The command prints one JSON record.
**Exit status 0 says that the result is ACCEPTED.** Exit status 5 says that the
result is REFUSED, and the record states each rule that refuses. Exit status 1
says that no record was printed: the directory is not a collection, its
footprint is not the footprint that the files of this tree give now, or this
tree gives no footprint.

``--as-collected`` prints the record of a collection whose footprint an earlier
tree declared. It does not compare the footprint with this tree. **With this
option, exit status 0 says only that a record was printed.** It does not say
that the result is ACCEPTED, because the footprint was not compared.

``--footprint`` prints the footprint that the files of this tree declare for one
desired-state release. A collector stores it before the first read that it
collects. Exit status is 1 when the files give no footprint.

``--check`` builds the record of each committed collection again, and compares
it with the committed record. Exit status is 1 when one differs.

Exit status is 2 when the arguments are not usable.

**The command reads files and writes nothing.** It contacts no cluster. See
docs/environment/capacity-preflight.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    ACCEPTED,
    REFUSED_EXIT,
    CollectionRefused,
    FootprintRefused,
    build_record,
    check_committed,
    committed_collections,
    declared_footprint,
    footprint_text,
    record_text,
    stale_footprint,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.capacity_preflight",
        description=(
            "Print whether one collected cluster can hold the two-replica release, "
            "and the state of each rule."
        ),
    )
    parser.add_argument(
        "directory", nargs="?", type=Path, help="the directory a collector wrote"
    )
    parser.add_argument(
        "--as-collected",
        action="store_true",
        help="do not compare the stored footprint with this tree",
    )
    parser.add_argument(
        "--footprint",
        action="store_true",
        help="print the footprint the committed files declare",
    )
    parser.add_argument("--key", help="<binding name>/<workload>, with --footprint")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare each committed record with its collection",
    )
    arguments = parser.parse_args(argv)

    chosen = sum(
        (arguments.directory is not None, arguments.footprint, arguments.check)
    )
    if chosen != 1:
        parser.error("give one of DIRECTORY, --footprint, and --check")
    if arguments.key and not arguments.footprint:
        parser.error("--key is used with --footprint")
    if arguments.as_collected and arguments.directory is None:
        parser.error("--as-collected is used with DIRECTORY")

    if arguments.footprint:
        try:
            footprint = declared_footprint(arguments.key)
        except FootprintRefused as refused:
            print(f"REFUSED  no-footprint: {refused}", file=sys.stderr)
            return 1
        sys.stdout.write(footprint_text(footprint))
        return 0

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
        if not arguments.as_collected:
            stale = stale_footprint(arguments.directory)
            if stale is not None:
                print(f"REFUSED  footprint-not-current: {stale}", file=sys.stderr)
                return 1
        record = build_record(arguments.directory)
    except CollectionRefused as refused:
        print(f"REFUSED  not-a-collection: {refused}", file=sys.stderr)
        return 1
    except FootprintRefused as refused:
        print(f"REFUSED  no-footprint: {refused}", file=sys.stderr)
        return 1
    sys.stdout.write(record_text(record))
    if arguments.as_collected:
        return 0
    return 0 if record["result"] == ACCEPTED else REFUSED_EXIT


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
