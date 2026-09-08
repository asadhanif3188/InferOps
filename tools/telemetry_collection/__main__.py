"""Check a rendered telemetry scrape configuration against the telemetry catalog.

    python -m tools.telemetry_collection charts/inferops-llm/ci/rendered

Every path is one bundle: all the documents in all the files named by one
invocation are read together, because a scrape job and the recording rule that
makes its absence visible are in the same ConfigMap and neither answers for the
other on its own. Naming a directory reads every `.yaml` under it.

Exit status is 0 when nothing is refused and 1 when anything is, so the command is
usable as a gate. `--json` produces a stable document a reviewer can diff between
runs.

The suite under `tests/telemetry/test_kubernetes_telemetry_collection.py` is the
authoritative check and runs in the default lane. This entry point exists so that
the same rules can be applied to output that is not a committed render -- a
`helm template` of a values file somebody is about to install, for instance --
without writing a test to do it.

**It reads a file.** It contacts no cluster, loads no collector, and scrapes
nothing, so a passing result says a configuration describes a collection that would
be permitted and says nothing about a collection that happened. Nothing scrapes
either InferOps endpoint. See docs/telemetry/kubernetes-telemetry-collection.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from .core import check_documents


def _files(paths: list[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(path.rglob("*.yaml"))
            yield from sorted(path.rglob("*.yml"))
        else:
            yield path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.telemetry_collection",
        description=(
            "Check a rendered telemetry scrape configuration against the accepted "
            "telemetry catalog: no target label the catalog bars from a metric, "
            "every barred label dropped, no recorded name that collides with a "
            "declared metric, no native runtime series that was never observed, "
            "and one absence rule per scrape job."
        ),
    )
    parser.add_argument(
        "paths", nargs="+", type=Path, help="manifest files or directories"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit findings as JSON instead of aligned text",
    )
    args = parser.parse_args(argv)

    documents: list[Any] = []
    sources: list[str] = []
    unreadable: list[dict[str, str]] = []

    for path in _files(args.paths):
        try:
            loaded = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, yaml.YAMLError) as error:
            reason = f"{type(error).__name__}: could not be read as a manifest"
            unreadable.append({"document": path.as_posix(), "unreadable": reason})
            continue
        documents.extend(loaded)
        sources.append(path.as_posix())

    findings = check_documents(documents)

    if args.json:
        print(
            json.dumps(
                {
                    "sources": sources,
                    "unreadable": unreadable,
                    "valid": not findings and not unreadable,
                    "findings": [f.as_dict() for f in findings],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        lines = [
            f"ERROR   {row['document']}  {row['unreadable']}" for row in unreadable
        ]
        if findings:
            lines.append(
                f"REFUSED {len(sources)} file(s)  ({len(findings)} finding(s))"
            )
            lines.extend(f"        {finding}" for finding in findings)
        elif not unreadable:
            lines.append(
                f"ok      {len(sources)} file(s) satisfy the collection policy"
            )
        print("\n".join(lines))

    return 1 if findings or unreadable else 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    sys.exit(main())
