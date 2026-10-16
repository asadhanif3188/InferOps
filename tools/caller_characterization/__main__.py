"""Print the Q3 record of one characterization directory, or check the committed ones.

    python -m tools.caller_characterization DIRECTORY
    python -m tools.caller_characterization --preconditions DIRECTORY
    python -m tools.caller_characterization --check

``DIRECTORY`` is what the frozen Q3 driver wrote. The command prints one JSON
record. **Exit status 0 says that the result is CHARACTERIZED**, and the record
states G. Exit status 5 says that the result is REFUSED, and exit status 6 says
that it is INCONCLUSIVE. Each of the two states each rule that is not held, and
no G. Exit status 1 says that no record was printed: the directory is not a
characterization directory.

``--preconditions`` prints the state of each rule that refuses, and exits 0 when
each is held and 5 when one is not. The driver asks it before it starts the
caller.

``--check`` builds the record of each committed directory again, and compares
it with the committed record. Exit status is 1 when one differs.

Exit status is 2 when the arguments are not usable.

**The command reads files and writes nothing.** It contacts no cluster, and no
option changes the target release, the topology, the provider, the caller
bounds, or the qualification that it compares with.
See docs/environment/stable-caller-characterization.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    CHARACTERIZED,
    HELD,
    INCONCLUSIVE_EXIT,
    REFUSED,
    REFUSED_EXIT,
    CollectionRefused,
    build_record,
    check_committed,
    committed_runs,
    preconditions,
    record_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.caller_characterization",
        description=(
            "Print the Q3 stable caller characterization of one directory, and "
            "the state of each rule."
        ),
    )
    parser.add_argument(
        "directory", nargs="?", type=Path, help="the directory the Q3 driver wrote"
    )
    parser.add_argument(
        "--preconditions",
        action="store_true",
        help="print only the rules that refuse, before the caller is started",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare each committed record with its directory",
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
            f"PASSED: {len(committed_runs())} committed characterization(s), each "
            "record is what its directory gives"
        )
        return 0

    try:
        if arguments.preconditions:
            states = preconditions(arguments.directory)
            for item in states:
                print(
                    f"{item['state'].ljust(13)} {item['criterion'].ljust(8)} "
                    f"{item['ruleId']}: {item['detail']}"
                )
            return 0 if all(item["state"] == HELD for item in states) else REFUSED_EXIT
        record = build_record(arguments.directory)
    except CollectionRefused as refused:
        print(f"REFUSED  not-a-collection: {refused}", file=sys.stderr)
        return 1
    sys.stdout.write(record_text(record))
    if record["result"] == CHARACTERIZED:
        return 0
    return REFUSED_EXIT if record["result"] == REFUSED else INCONCLUSIVE_EXIT


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
