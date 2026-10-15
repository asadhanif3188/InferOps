"""Print the Q1 record of one qualification directory, or check the committed ones.

    python -m tools.environment_qualification DIRECTORY
    python -m tools.environment_qualification --check

``DIRECTORY`` is what the frozen Q1 driver wrote. The command prints one JSON
record. **Exit status 0 says that the result is QUALIFIED.** Exit status 5 says
that the result is REFUSED, and the record states each rule that refuses. Exit
status 1 says that no record was printed: the directory is not a qualification
directory.

``--check`` builds the record of each committed directory again, and compares
it with the committed record. Exit status is 1 when one differs.

Exit status is 2 when the arguments are not usable.

**The command reads files and writes nothing.** It contacts no cluster, and no
option changes the target release, the topology, the provider, or the model.
See docs/environment/environment-qualification.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    QUALIFIED,
    REFUSED_EXIT,
    CollectionRefused,
    build_record,
    check_committed,
    committed_runs,
    record_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.environment_qualification",
        description=(
            "Print the Q1 environment and identity qualification of one "
            "directory, and the state of each rule."
        ),
    )
    parser.add_argument(
        "directory", nargs="?", type=Path, help="the directory the Q1 driver wrote"
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
            f"PASSED: {len(committed_runs())} committed qualification(s), each "
            "record is what its directory gives"
        )
        return 0

    try:
        record = build_record(arguments.directory)
    except CollectionRefused as refused:
        print(f"REFUSED  not-a-collection: {refused}", file=sys.stderr)
        return 1
    sys.stdout.write(record_text(record))
    return 0 if record["result"] == QUALIFIED else REFUSED_EXIT


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
