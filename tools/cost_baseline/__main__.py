"""Commands for the V1 cost baseline.

`derive` reads one committed performance record, takes each run's usage from its
samples and raw records under ADR 0014 D3, and writes one calculation input and one
result per run, plus the derivation record explaining every value. `verify` derives
them again and fails if any committed file differs in any byte after line endings are
normalized to LF. Both refuse a record that does not regenerate from its inputs, is
not local real evidence, or failed one of its own checks, before anything is written.

Neither contacts anything and neither publishes a figure: every result is priced from
the synthetic rate card and carries `publishedCostFigure: false`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.cost_calculation import CostCalculationError, load_method
from tools.llm_load import core as load
from tools.performance_scenarios.core import ScenarioError, load_descriptor

from .core import CostBaselineError, derive_baseline, read_sources

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.cost_baseline",
        description=(
            "Take measured use from a committed performance record under ADR 0014 D3 and "
            "calculate estimated cost records from it. Every price is synthetic, and no "
            "result is a published cost figure."
        ),
    )
    parser.add_argument("command", choices=("derive", "verify"))
    parser.add_argument(
        "--record-dir",
        type=Path,
        required=True,
        help="directory holding the committed performance record and its inputs",
    )
    parser.add_argument(
        "--record-prefix",
        required=True,
        help="file name prefix of the committed performance record",
    )
    parser.add_argument(
        "--dir", type=Path, required=True, help="directory the baseline is written to"
    )
    parser.add_argument(
        "--prefix", required=True, help="file name prefix of the baseline's files"
    )
    arguments = parser.parse_args(argv)

    try:
        sources = read_sources(
            load_descriptor(), arguments.record_dir, arguments.record_prefix
        )
        files = derive_baseline(sources, load_method(), arguments.prefix)
        directory: Path = arguments.dir
        if arguments.command == "derive":
            directory.mkdir(parents=True, exist_ok=True)
            for name, text in files.items():
                (directory / name).write_text(text, encoding="utf-8", newline="\n")
                print(f"wrote        {(directory / name).as_posix()}")
            print(
                "claim        measured use, synthetic prices; not a bill, not an allocation, not a published figure"
            )
            return EXIT_OK
        stale: list[str] = []
        for name, text in files.items():
            try:
                committed = (
                    (directory / name).read_text(encoding="utf-8").replace("\r\n", "\n")
                )
            except (OSError, UnicodeError):
                stale.append(name)
                continue
            if committed != text:
                stale.append(name)
        if stale:
            print(
                "FAILED cost baseline: not what the committed evidence produces: "
                + ", ".join(stale),
                file=sys.stderr,
            )
            return EXIT_FAILED
        print(
            f"ok           {len(files)} committed baseline file(s) regenerate from a record that regenerates from its inputs"
        )
        return EXIT_OK
    except (
        CostBaselineError,
        CostCalculationError,
        ScenarioError,
        load.LoadError,
    ) as error:
        print(f"REFUSED cost baseline: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
