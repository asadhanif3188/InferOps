"""Commands for the V1 cost calculation.

`calculate` reads one input document and writes the result the cost method produces
from it. `verify` calculates again and fails if a committed result differs in any byte
after line endings are normalized to LF. Both refuse an input the method forbids a
calculation from, before any figure is written.

Neither contacts anything and neither reads a price from anywhere but the committed
cost method. Neither publishes a figure: a result carries its boundary and
`publishedCostFigure: false`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import CostCalculationError, calculate, dumps, load_method, read_json

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.cost_calculation",
        description=(
            "Calculate an estimated cost record from one input document and the committed "
            "cost method. No price is fetched, and no result is a published cost figure."
        ),
    )
    parser.add_argument("command", choices=("calculate", "verify"))
    parser.add_argument(
        "--input", type=Path, required=True, help="the calculation input document"
    )
    parser.add_argument(
        "--result",
        type=Path,
        required=True,
        help="the result file to write (calculate) or compare (verify)",
    )
    arguments = parser.parse_args(argv)

    try:
        method = load_method()
        text = dumps(calculate(read_json(arguments.input, "calculation input"), method))
        path: Path = arguments.result
        if arguments.command == "calculate":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"result       {path.as_posix()}")
            print(
                "claim        an estimated cost record; not a bill, not an allocation, not a published figure"
            )
            return EXIT_OK
        try:
            committed = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeError) as error:
            raise CostCalculationError("the committed result is unreadable") from error
        if committed != text:
            print(
                "FAILED cost calculation: the committed result is not what the input and the method produce",
                file=sys.stderr,
            )
            return EXIT_FAILED
        print(
            "ok           the committed result regenerates from its input and the committed method"
        )
        return EXIT_OK
    except CostCalculationError as error:
        print(f"REFUSED cost calculation: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
