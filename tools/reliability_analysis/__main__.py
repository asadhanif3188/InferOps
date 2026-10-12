"""Compute the reliability metrics of one run, or the median of one figure of three runs.

    python -m tools.reliability_analysis analyze --declaration FILE --caller FILE
        [--endpoints FILE] [--pods FILE] [--deployments FILE] [--argo FILE]
        [--operator-events FILE]
    python -m tools.reliability_analysis aggregate --metric NAME FILE=STATE ...

``analyze`` reads the declaration and the given evidence files and prints one
analysis document. ``aggregate`` reads analysis documents, each with the result
state of its run, and prints one figure of each run and the median of three
counted runs.

**Exit status 0 says that the command printed a document.** It does not say
that each metric has a value: a document names each metric that has none in
``withoutValue``. It does not say that a run passed. Exit status 3 says that an
input was refused, and nothing is printed for it. Exit status 2 says that the
arguments are not usable.

**The command reads files.** It contacts no cluster and no caller, and it
writes no file. See docs/testing/reliability-analysis.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.experiment_run import RESULT_STATES

from .core import (
    AGGREGATE_METRICS,
    EVENTS,
    INPUTS,
    REFUSED_EXIT,
    RULE_AGGREGATE,
    RULE_DECLARATION_UNREADABLE,
    RULE_INPUT,
    AnalysisRefused,
    aggregate,
    analysis_text,
    analyze,
)


def _emit(text: str) -> None:
    """Write LF bytes on every host."""
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def _text(path: Path, rule: str, name: str) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as fault:
        raise AnalysisRefused(
            rule, f"{name}: the file is not readable UTF-8 text"
        ) from fault


def _no_repeat(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for name, value in pairs:
        if name in document:
            raise ValueError(name)
        document[name] = value
    return document


def _run_argument(value: str) -> tuple[Path, str]:
    path, separator, state = value.rpartition("=")
    if not separator or not path or state not in RESULT_STATES:
        raise argparse.ArgumentTypeError(
            "a run is FILE=STATE, and STATE is one of " + ", ".join(RESULT_STATES)
        )
    return Path(path), state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.reliability_analysis",
        description="Compute the reliability metrics of one experiment run.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    analyzer = commands.add_parser("analyze", help="print the analysis of one run")
    analyzer.add_argument("--declaration", required=True, type=Path)
    for name in INPUTS:
        analyzer.add_argument(
            f"--{name}", type=Path, required=name == "caller", dest=name
        )
    aggregator = commands.add_parser(
        "aggregate", help="print one figure of each run and the median of three"
    )
    aggregator.add_argument("--metric", required=True, choices=tuple(AGGREGATE_METRICS))
    aggregator.add_argument("runs", nargs="+", type=_run_argument, metavar="FILE=STATE")
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "analyze":
            declaration = _text(
                arguments.declaration, RULE_DECLARATION_UNREADABLE, "declaration"
            )
            texts = {
                name: None
                if getattr(arguments, name) is None
                else _text(getattr(arguments, name), RULE_INPUT, name)
                for name in INPUTS
            }
            document = analyze(declaration, texts)
        else:
            runs = []
            for path, state in arguments.runs:
                text = _text(path, RULE_AGGREGATE, path.name)
                try:
                    loaded = json.loads(text, object_pairs_hook=_no_repeat)
                except (ValueError, RecursionError) as fault:
                    raise AnalysisRefused(
                        RULE_AGGREGATE, f"{path.name}: the file is not one JSON object"
                    ) from fault
                runs.append((loaded, state))
            document = aggregate(arguments.metric, runs)
    except AnalysisRefused as refused:
        print(f"REFUSED  {refused}", file=sys.stderr)
        return REFUSED_EXIT
    _emit(analysis_text(document))
    return 0


assert EVENTS in INPUTS

if __name__ == "__main__":
    raise SystemExit(main())
