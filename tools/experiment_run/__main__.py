"""Validate ExperimentRun manifests from the command line.

    python -m tools.experiment_run check path/to/run.v1alpha1.json
    python -m tools.experiment_run repository

``check`` validates each file it is given against the published schema and the
semantic rules. ``repository`` reads every run manifest under
``docs/proof/experiments``: a manifest that the pre-schema register names must have
its registered content, and every other manifest must validate.

Exit status 0 says that nothing was refused. Exit status 3 says that a rule refused
a manifest or the register, and the output names the rule. A path that names no
file, a directory, or a file that is not JSON is refused by a rule, so it gives 3.
Exit status 2 says that the argument parser refused the arguments. Exit status 4
says that the command failed in a way that no rule names.

``check`` prints each path as it was given, with each character that is not
printable replaced by a question mark.

**The command reads files and writes nothing.** It opens no evidence file, contacts
no cluster, and judges no result. See docs/contracts/experiment-run.md.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from tools.contract_validation.errors import CONTRACT_INVALID, Finding

from .core import (
    CONFORMING,
    PRE_SCHEMA,
    REPO_ROOT,
    RunDocumentError,
    read_document,
    repository_report,
    validate,
)

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4

_LABELS = {CONFORMING: "ok        ", PRE_SCHEMA: "pre-schema"}


def _printable(name: str) -> str:
    """A path for one output line: a line break in a name cannot start a line."""
    return "".join(c if c.isprintable() else "?" for c in name)


def _refusal(name: str, findings: Iterable[Finding]) -> list[str]:
    listed = list(findings)
    lines = [f"REFUSED    {name}  ({len(listed)} finding(s))"]
    lines.extend(
        f"           {f.code}  {f.rule}  {f.field}  {f.message}" for f in listed
    )
    return lines


def _check(paths: list[Path]) -> int:
    refused = False
    for path in sorted(paths):
        name = _printable(path.as_posix())
        try:
            findings = validate(read_document(path))
        except RunDocumentError as error:
            findings = [
                Finding(
                    field="$",
                    rule=error.rule,
                    code=CONTRACT_INVALID,
                    message=error.message,
                )
            ]
        if findings:
            refused = True
            print("\n".join(_refusal(name, findings)))
        else:
            print(f"{_LABELS[CONFORMING]} {name}")
    return EXIT_REFUSED if refused else EXIT_OK


def _repository(root: Path) -> int:
    report = repository_report(root)
    if report.findings:
        print("\n".join(_refusal("the pre-schema register", report.findings)))
    for entry in report.manifests:
        if entry.findings:
            print("\n".join(_refusal(entry.path, entry.findings)))
        else:
            print(f"{_LABELS[entry.status]} {entry.path}")
    counts = {
        status: sum(1 for entry in report.manifests if entry.status == status)
        for status in (PRE_SCHEMA, CONFORMING)
    }
    print(
        f"manifests  {len(report.manifests)}: {counts[PRE_SCHEMA]} pre-schema, "
        f"{counts[CONFORMING]} conforming, "
        f"{len(report.manifests) - counts[PRE_SCHEMA] - counts[CONFORMING]} refused"
    )
    return EXIT_REFUSED if report.refused else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.experiment_run",
        description=(
            "Validate ExperimentRun v1alpha1 manifests. The command reads files and "
            "writes nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="validate the manifests named")
    check.add_argument("paths", nargs="+", type=Path, help="manifests to validate")
    commands.add_parser(
        "repository",
        help="read every run manifest under docs/proof/experiments",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return _check(args.paths)
        return _repository(REPO_ROOT)
    except Exception:
        print("FAILED     experiment run: unexpected local failure", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
