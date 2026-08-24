"""Validate WorkloadContract documents from the command line.

    python -m tools.contract_validation contracts/workload/examples/valid/*.yaml

Exit status is 0 when every document validates and 1 when any is refused, so the
command is usable as a gate. Output is deterministic: findings are sorted, and
`--json` produces a stable document that a reviewer can diff between runs.

The suite under `tests/contracts/` is the authoritative check. This entry point
exists so that the same rules can be applied to a document that is not a committed
fixture, without writing a test to do it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from .workload import validate


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _render_text(path: Path, findings: list[Any]) -> list[str]:
    if not findings:
        return [f"ok      {path.as_posix()}"]
    lines = [f"REFUSED {path.as_posix()}  ({len(findings)} finding(s))"]
    lines.extend(
        f"        {f.code}  {f.rule}  {f.field}  {f.message}" for f in findings
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.contract_validation",
        description="Validate WorkloadContract documents against the published "
        "schema and the semantic rules JSON Schema cannot express.",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="documents to validate")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit findings as JSON instead of aligned text",
    )
    args = parser.parse_args(argv)

    report: list[dict[str, Any]] = []
    lines: list[str] = []
    refused = 0

    for path in sorted(args.paths):
        try:
            document = _load(path)
        except (OSError, ValueError, yaml.YAMLError) as error:
            refused += 1
            reason = f"{type(error).__name__}: could not be read as a contract document"
            report.append({"document": path.as_posix(), "unreadable": reason})
            lines.append(f"ERROR   {path.as_posix()}  {reason}")
            continue

        findings = validate(document)
        refused += bool(findings)
        report.append(
            {
                "document": path.as_posix(),
                "valid": not findings,
                "findings": [f.as_dict() for f in findings],
            }
        )
        lines.extend(_render_text(path, findings))

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("\n".join(lines))
    return 1 if refused else 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    sys.exit(main())
