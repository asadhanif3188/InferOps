"""Print the classification of the V2-E02A runs, or check the committed record.

    python -m tools.comparison_eligibility
    python -m tools.comparison_eligibility --adjudicated
    python -m tools.comparison_eligibility --check

With no option the command prints one JSON record, the classification. **Exit status 0 says that the
record was printed.** It does not say that the set is eligible: the record states the
verdict. Exit status 5 says that a rule refused a record or a run directory, and no
record was printed.

``--adjudicated`` prints the record that states the current verdict. It reads the
committed classification record, the adjudication input, and the raw streams.

``--check`` builds both records again and compares each with its committed file, it
holds each run to the desired state and the record of its executing commit, and it
holds each current page to the current verdict. Exit status is 1 when one differs. A clone that does not hold an executing commit cannot
compare that commit: the command says so and does not fail, so a shallow clone passes
with less compared.

Exit status is 2 when the arguments are not usable.

**The command reads files and Git objects, and it writes nothing.** No option
changes the rule. See docs/testing/comparison-eligibility.md.
"""

from __future__ import annotations

import argparse
import json
import sys

from tools.analysis_replay import ReplayRefused
from tools.analysis_replay.__main__ import history

from .core import (
    ADJUDICATED_PATH,
    RECORD_PATH,
    REFUSED_EXIT,
    REPO_ROOT,
    EligibilityRefused,
    build_adjudicated_record,
    build_record,
    check_adjudicated,
    check_committed,
    check_executing_commits,
    record_text,
)


def _check() -> int:
    findings = check_committed()
    missing: list[str] = []
    if not findings:
        record = json.loads((REPO_ROOT / RECORD_PATH).read_text(encoding="utf-8"))
        found, missing = check_executing_commits(record, history())
        findings.extend(found)
    findings.extend(check_adjudicated())
    for finding in findings:
        print(f"FAILED   {finding}", file=sys.stderr)
    if findings:
        return 1
    for revision in missing:
        print(f"NOT COMPARED: this clone does not hold the commit {revision}")
    print(f"PASSED: {RECORD_PATH} is what the runs give")
    print(f"PASSED: {ADJUDICATED_PATH} states the current verdict")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.comparison_eligibility",
        description="Print the classification of the V2-E02A runs.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--adjudicated",
        action="store_true",
        help="print the record that states the current verdict",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="compare the committed records with the runs, and hold the current pages",
    )
    arguments = parser.parse_args(argv)
    if arguments.check:
        return _check()
    try:
        record = build_adjudicated_record() if arguments.adjudicated else build_record()
    except (EligibilityRefused, ReplayRefused) as refused:
        print(f"REFUSED  {refused}", file=sys.stderr)
        return REFUSED_EXIT
    sys.stdout.write(record_text(record))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
