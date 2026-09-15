"""Commands for the figures derived from a committed performance record.

`derive` writes the findings document for a committed record. `verify` derives it
again and fails if the committed findings differ in any byte after line endings are
normalized to LF. Both refuse a record that does not regenerate from its committed
inputs, that is not usable, or that does not carry its boundary.

Neither contacts anything. Neither states where a setup degraded: that statement is
made, and reviewed, in the analysis document that cites the findings.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.llm_load import core as load
from tools.performance_scenarios.core import ScenarioError, dumps, load_descriptor

from .core import FindingsError, derive_findings, read_inputs

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.performance_findings",
        description=(
            "Derive comparison figures from a committed performance record that "
            "regenerates from its inputs. No figure is a portable capacity figure, a "
            "production SLO, or a benchmark, and no saturation is judged."
        ),
    )
    parser.add_argument("command", choices=("derive", "verify"))
    parser.add_argument(
        "--dir", type=Path, required=True, help="directory holding the committed record"
    )
    parser.add_argument(
        "--record-prefix",
        required=True,
        help="file name prefix of the committed record and its inputs",
    )
    parser.add_argument(
        "--findings",
        type=Path,
        required=True,
        help="the findings file to write (derive) or compare (verify)",
    )
    arguments = parser.parse_args(argv)

    try:
        descriptor = load_descriptor()
        inputs = read_inputs(arguments.dir, arguments.record_prefix)
        text = dumps(derive_findings(descriptor, inputs))
        path: Path = arguments.findings
        if arguments.command == "derive":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"findings     {path.as_posix()}")
            print(
                "claim        derived figures only; not capacity, an SLO, or a benchmark; saturation not judged"
            )
            return EXIT_OK
        try:
            committed = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeError) as error:
            raise FindingsError("the committed findings are unreadable") from error
        if committed != text:
            print(
                "REFUSED performance findings: the committed findings are not what the record's inputs produce",
                file=sys.stderr,
            )
            return EXIT_FAILED
        print(
            "ok           the committed findings regenerate from a record that regenerates from its inputs"
        )
        return EXIT_OK
    except (FindingsError, ScenarioError, load.LoadError) as error:
        print(f"REFUSED performance findings: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
