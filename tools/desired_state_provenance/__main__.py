"""Print the provenance of a desired-state release at one Git commit.

    python -m tools.desired_state_provenance --revision COMMIT [KEY ...]

``COMMIT`` is a full commit identifier: 40 lowercase hexadecimal characters. It is
the commit a GitOps controller reports that it resolved. A branch name, a tag
name, and an abbreviated commit are refused.

``KEY`` selects a desired-state release, as ``<binding name>/<workload>``. Without
a key, every declared release is resolved.

``--root DIRECTORY`` reads another clone of the repository instead of this one.

The command prints one JSON document: a list with one record for each release. A
record holds identifiers and digests, and no timestamp. Exit status is 0 when
every selected release resolved, and 1 when one was refused. A refusal is printed
to the standard error stream, and no record is printed for any release.

**The command reads Git objects and writes nothing.** It contacts no cluster, no
registry, no network, and no model. It does not render the release again, and it
does not establish that the commit is on a branch or was reviewed.
See docs/environment/desired-state-provenance.md.
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

from .core import REPO_ROOT, RULES, ProvenanceRefused, resolve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.desired_state_provenance",
        description=(
            "Print the identities of a desired-state release as one Git commit "
            "holds it."
        ),
    )
    parser.add_argument(
        "--revision",
        required=True,
        metavar="COMMIT",
        help="a full commit identifier, 40 lowercase hexadecimal characters",
    )
    parser.add_argument(
        "keys", nargs="*", metavar="KEY", help="<binding name>/<workload>"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="the repository clone to read (default: this checkout)",
    )
    arguments = parser.parse_args(argv)

    selected = list(DESIRED_STATE_RELEASES)
    if arguments.keys:
        selected = []
        for key in arguments.keys:
            try:
                selected.append(desired_state_release(key))
            except KeyError:
                known = ", ".join(release_key(d) for d in DESIRED_STATE_RELEASES)
                parser.error(
                    f"no desired-state release has the key {key!r}; known: {known}"
                )

    statements = {rule.rule_id: rule.statement for rule in RULES}
    records = []
    status = 0
    for declared in selected:
        try:
            records.append(
                resolve(arguments.revision, declared, arguments.root).as_document()
            )
        except ProvenanceRefused as refused:
            status = 1
            for finding in refused.findings:
                print(f"REFUSED  {finding.rule_id}", file=sys.stderr)
                print(
                    f"         {release_key(declared)}: {finding.subject}: "
                    f"{finding.detail}",
                    file=sys.stderr,
                )
                print(f"         {statements[finding.rule_id]}", file=sys.stderr)
    if status == 0:
        print(json.dumps(records, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
