"""Print the comparison record of the baseline, check the committed profile, or write it.

    python -m tools.baseline_profile --record
    python -m tools.baseline_profile --check
    python -m tools.baseline_profile --write

``--root DIRECTORY`` reads, and writes, a copy of the repository instead of this
checkout. The suite uses it to plant defects without touching the committed files.

``--record`` prints one JSON record: the differences between the baseline and the
target in each layer, the state of each rule, and each finding. **Exit status 0
says that the result is COMPARABLE.** Exit status 5 says that the result is
REFUSED, and the record states each rule that refuses.

``--check`` verifies the committed profile: that the comparison is COMPARABLE,
that the committed baseline release is byte for byte what its declared sources
derive, and that the committed record is the record this tree gives. Exit status
is 0 when no rule is broken and 1 when one is. ``--check`` writes nothing and
repairs nothing.

``--write`` is the only mode that touches a file. It writes the baseline release
and the comparison record again. It refuses to write when the comparison is
REFUSED. Read the ``--check`` output first, because a write replaces a hand edit
without asking.

Exit status is 2 when the arguments are not usable.

**Every mode reads files of the tree only.** None contacts a cluster, a registry,
a network, or a model, and none runs Helm or Git. See
docs/environment/single-runtime-baseline-profile.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.generated_release import RegenerationRefused

from .core import (
    CHECK_RULES,
    COMPARABLE,
    PROFILE_DIRECTORY,
    RECORD_PATH,
    REFUSED_EXIT,
    REPO_ROOT,
    RULES,
    TARGET_KEY,
    WriteRefused,
    build_record,
    record_text,
    target_release,
    verify_profile,
    write_profile,
)


def _record(root: Path) -> int:
    record = build_record(root)
    sys.stdout.write(record_text(record))
    return 0 if record["result"] == COMPARABLE else REFUSED_EXIT


def _check(root: Path) -> int:
    findings = verify_profile(root)
    if not findings:
        print(f"OK       {PROFILE_DIRECTORY}")
        print(f"OK       {RECORD_PATH}")
        print(
            "OK       the baseline differs from the target only at the permitted paths"
        )
        return 0
    statements = {rule.rule_id: rule.statement for rule in (*RULES, *CHECK_RULES)}
    for finding in findings:
        print(f"REFUSED  {finding.rule_id}")
        print(f"         {finding.subject}: {finding.detail}")
        print(f"         {statements[finding.rule_id]}")
    print(f"{len(findings)} findings in the baseline profile")
    return 1


def _write(root: Path) -> int:
    try:
        release_written, record_written = write_profile(root)
    except (WriteRefused, RegenerationRefused) as refused:
        print("REFUSED  nothing was written")
        for finding in refused.findings:
            print(f"         {finding.rule_id}  {finding.subject}: {finding.detail}")
        return 1
    except OSError as error:
        # The error's own text names a path of this host, so it is not printed.
        print(f"FAILED   {type(error).__name__}: {error.strerror or 'no reason given'}")
        print(
            "         the release and the record may be out of step, or the profile "
            "directory absent; run --check, then --write again, or restore both "
            "from Git"
        )
        return 1
    print(f"{'WROTE    ' if release_written else 'UNCHANGED'} {PROFILE_DIRECTORY}")
    print(f"{'WROTE    ' if record_written else 'UNCHANGED'} {RECORD_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.baseline_profile",
        description=(
            "Compare the single-runtime baseline profile with the target release, "
            "and refuse a difference that is not the runtime replica count."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--record", action="store_true", help="print the comparison record"
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="verify the committed profile; writes nothing",
    )
    group.add_argument(
        "--write",
        action="store_true",
        help="write the baseline release and the comparison record again",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="the repository copy to read and write (default: this checkout)",
    )
    arguments = parser.parse_args(argv)

    try:
        target_release()
    except KeyError:
        print(f"REFUSED  no desired-state release has the key {TARGET_KEY}")
        return 1
    if arguments.record:
        return _record(arguments.root)
    if arguments.check:
        return _check(arguments.root)
    return _write(arguments.root)


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
