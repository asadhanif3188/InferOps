"""Print the record of one model cache observation, or check the committed ones.

    python -m tools.runtime_model_cache DIRECTORY
    python -m tools.runtime_model_cache --expected [--key KEY]
    python -m tools.runtime_model_cache --check

``DIRECTORY`` is what a run driver wrote. The command prints one JSON record.
Exit status is 0 when a record was printed. **Exit status 0 does not say that a
rule is held.** The record states the result and the state of each rule. Exit
status is 1 when the directory is not a collection.

``--expected`` prints the identity that the committed files declare for each
runtime replica of one desired-state release. A run stores it before it reads a
pod. Exit status is 1 when the release and the two pin records disagree.

``--check`` builds the record of each committed run again from the committed
collection, and compares it with the committed record. Exit status is 1 when one
differs.

Exit status is 2 when the arguments are not usable.

**The command reads files and writes nothing.** It contacts no cluster. See
docs/environment/runtime-model-cache-observation.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    CollectionRefused,
    ExpectedRefused,
    build_record,
    check_committed_runs,
    committed_runs,
    expected_identity,
    pin_findings,
    record_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.runtime_model_cache",
        description=(
            "Print what the serving runtime replicas read from the model cache in "
            "one collection, and the state of each rule."
        ),
    )
    parser.add_argument(
        "directory", nargs="?", type=Path, help="the directory a run driver wrote"
    )
    parser.add_argument(
        "--expected",
        action="store_true",
        help="print the identity the committed files declare",
    )
    parser.add_argument("--key", help="<binding name>/<workload>, with --expected")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare each committed record with its collection",
    )
    arguments = parser.parse_args(argv)

    chosen = sum((arguments.directory is not None, arguments.expected, arguments.check))
    if chosen != 1:
        parser.error("give one of DIRECTORY, --expected, and --check")
    if arguments.key and not arguments.expected:
        parser.error("--key is used with --expected")

    if arguments.expected:
        try:
            expected = expected_identity(arguments.key)
        except ExpectedRefused as refused:
            print(f"REFUSED  no-expected-identity: {refused}", file=sys.stderr)
            return 1
        findings = pin_findings(expected)
        for finding in findings:
            print(f"REFUSED  pin-disagreement: {finding}", file=sys.stderr)
        if findings:
            return 1
        print(json.dumps(expected, indent=2, sort_keys=True))
        return 0

    if arguments.check:
        findings = check_committed_runs()
        for finding in findings:
            print(f"FAILED   {finding}", file=sys.stderr)
        if findings:
            return 1
        print(
            f"PASSED: {len(committed_runs())} committed run(s), each record is what "
            "its collection gives"
        )
        return 0

    try:
        record = build_record(arguments.directory)
    except CollectionRefused as refused:
        print(f"REFUSED  not-a-collection: {refused}", file=sys.stderr)
        return 1
    sys.stdout.write(record_text(record))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
