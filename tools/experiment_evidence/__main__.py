"""Check the directories of experiment runs from the command line.

    python -m tools.experiment_evidence check path/to/runs/<runId>
    python -m tools.experiment_evidence repository
    python -m tools.experiment_evidence digests path/to/a/directory

``check`` holds each run directory it is given to its manifest and to the layout.
``repository`` checks every run directory under ``docs/proof/experiments``: a
directory whose manifest the pre-schema register names is listed and not checked.
``digests`` prints one ``<sha256>  <path>`` line for each file of a directory that
can be an evidence file, with the layout's digest, for the writer of a manifest.
``check`` checks a directory that the register names too, and refuses it at its
manifest.

Exit status 0 says that nothing was refused. Exit status 3 says that a rule refused
a directory or a file, and the output names the rule. Exit status 2 says that the
argument parser refused the arguments. Exit status 4 says that the command failed
in a way that no rule names.

**The command reads files and writes nothing.** It contacts no cluster, reads no
Git object, and judges no result. See docs/testing/experiment-evidence-layout.md.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from tools.experiment_run.core import CONFORMING, PRE_SCHEMA, REPO_ROOT

from .core import (
    REFUSED,
    Finding,
    RunReport,
    check_run,
    digest_lines,
    printable,
    repository_report,
)

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4


def _refusal(name: str, findings: Iterable[Finding]) -> list[str]:
    listed = list(findings)
    lines = [f"REFUSED    {name}  ({len(listed)} finding(s))"]
    lines.extend(f"           {f.rule}  {f.path}  {f.message}" for f in listed)
    return lines


def _run_lines(report: RunReport) -> list[str]:
    if report.status == REFUSED:
        return _refusal(report.path, report.findings)
    if report.digests is None:
        return [f"pre-schema {report.path}  (not checked)"]
    return [
        f"ok         {report.path}  ({report.files} evidence file(s), "
        f"{report.raw_files} raw, {report.corrections} correction(s))",
        f"           raw evidence  {report.digests.raw or 'none'}",
        f"           evidence set  {report.digests.evidence_set}",
    ]


def _check(paths: list[Path], root: Path) -> int:
    refused = False
    for path in sorted(paths):
        report = check_run(path, root)
        refused = refused or report.status == REFUSED
        print("\n".join(_run_lines(report)))
    return EXIT_REFUSED if refused else EXIT_OK


def _repository(root: Path) -> int:
    report = repository_report(root)
    if report.findings:
        print("\n".join(_refusal("the proof tree", report.findings)))
    for run in report.runs:
        print("\n".join(_run_lines(run)))
    counts = {
        status: sum(1 for run in report.runs if run.status == status)
        for status in (PRE_SCHEMA, CONFORMING, REFUSED)
    }
    print(
        f"runs       {len(report.runs)}: {counts[PRE_SCHEMA]} pre-schema and not "
        f"checked, {counts[CONFORMING]} conforming, {counts[REFUSED]} refused"
    )
    return EXIT_REFUSED if report.refused else EXIT_OK


def _digests(directory: Path) -> int:
    lines, findings = digest_lines(directory)
    if lines:
        print("\n".join(lines))
    if findings:
        print("\n".join(_refusal(printable(directory.as_posix()), findings)))
    return EXIT_REFUSED if findings else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.experiment_evidence",
        description=(
            "Check the directories of experiment runs. The command reads "
            "files and writes nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check the run directories named")
    check.add_argument("paths", nargs="+", type=Path, help="run directories")
    check.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="the root of the tree that holds docs/proof/experiments",
    )
    commands.add_parser(
        "repository", help="check every run directory under docs/proof/experiments"
    )
    digests = commands.add_parser(
        "digests", help="print the layout's digest of each file of a directory"
    )
    digests.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return _check(args.paths, args.root)
        if args.command == "digests":
            return _digests(args.directory)
        return _repository(REPO_ROOT)
    except Exception:
        print(
            "FAILED     experiment evidence: unexpected local failure", file=sys.stderr
        )
        return EXIT_FAILED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
