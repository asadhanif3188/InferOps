"""Print the evidence record of one reconciliation observation.

    python -m tools.reconciliation_evidence DIRECTORY [--key KEY] [--root CLONE]

``DIRECTORY`` is what the Application procedure's ``observe`` operation wrote.

``--key KEY`` selects the desired-state release to compare each sample with, as
``<binding name>/<workload>``. Without it, the one declared release is used.
``--no-provenance`` makes no comparison.

``--root CLONE`` reads the commits from another clone of the repository.

The command prints one JSON document. Exit status is 0 when a record was
printed. **Exit status 0 does not say that the controller reported anything.** A
record of unanswered reads is a record, and the record says which fields were not
reported. Exit status is 1 when the directory is not a collection, and 2 when the
arguments are not usable.

**The command reads files and Git objects and writes nothing.** It contacts no
cluster. See docs/environment/reconciliation-evidence.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.gitops_desired_state import (
    DESIRED_STATE_RELEASES,
    desired_state_release,
    release_key,
)

from .core import REPO_ROOT, CollectionRefused, build_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.reconciliation_evidence",
        description=(
            "Print what a GitOps controller reported in one bounded observation, "
            "and what it did not report."
        ),
    )
    parser.add_argument(
        "directory", type=Path, help="the directory the observe operation wrote"
    )
    parser.add_argument("--key", help="<binding name>/<workload>")
    parser.add_argument(
        "--no-provenance",
        action="store_true",
        help="compare no sample with a desired-state release",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="the repository clone to read commits from (default: this checkout)",
    )
    arguments = parser.parse_args(argv)

    declared = None
    if arguments.no_provenance:
        if arguments.key:
            parser.error("--key and --no-provenance are not used together")
    elif arguments.key:
        try:
            declared = desired_state_release(arguments.key)
        except KeyError:
            known = ", ".join(release_key(d) for d in DESIRED_STATE_RELEASES)
            parser.error(
                f"no desired-state release has the key {arguments.key!r}; "
                f"known: {known}"
            )
    elif len(DESIRED_STATE_RELEASES) == 1:
        declared = DESIRED_STATE_RELEASES[0]
    else:
        parser.error("more than one desired-state release is declared; give --key")

    try:
        record = build_record(arguments.directory, declared, arguments.root)
    except CollectionRefused as refused:
        print(f"REFUSED  not-a-collection: {refused}", file=sys.stderr)
        return 1
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
