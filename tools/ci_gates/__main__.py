"""Run the expected-failure controls and report what each command did.

    python -m tools.ci_gates expected-failures

Exit status is 0 when every control produced the exit status the repository
requires of it and 1 when any did not, so the command is usable as a gate.
`--json` produces a stable document a reviewer can diff between runs.

It runs modules from this repository against files in it. Nothing here contacts
a network, a cluster, a registry, or a model.
"""

from __future__ import annotations

import argparse
import json
import sys

from .core import REPO_ROOT, Result, controls, run, shortfalls


def _report(results: list[Result]) -> dict[str, object]:
    return {
        "gate": "expected-failures",
        "controls": [
            {
                "controlId": result.control.controlId,
                "module": result.control.module,
                "target": result.control.target.relative_to(REPO_ROOT).as_posix(),
                "expectedExit": result.control.expected_exit,
                "actualExit": result.actual_exit,
                "passed": result.passed,
            }
            for result in results
        ],
        "passed": all(result.passed for result in results),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.ci_gates",
        description=(
            "Run the published validation commands against the fixtures this "
            "repository requires them to refuse, and against the ones it "
            "requires them to accept."
        ),
    )
    parser.add_argument(
        "gate",
        choices=["expected-failures"],
        help="the gate to run",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit a machine-readable report"
    )
    arguments = parser.parse_args(argv)

    found = controls()
    missing = shortfalls(found)
    if missing:
        for line in missing:
            print(f"[inferops-ci-gates] FAILED: {line}", file=sys.stderr)
        return 1

    results = list(run(found))

    if arguments.json:
        print(json.dumps(_report(results), indent=2, sort_keys=True))
    else:
        for result in results:
            verdict = "ok" if result.passed else "FAILED"
            print(
                f"[inferops-ci-gates] {verdict} {result.control.controlId} "
                f"expected exit {result.control.expected_exit}, "
                f"got {result.actual_exit}"
            )

    failed = [result for result in results if not result.passed]
    if failed:
        print(
            f"[inferops-ci-gates] FAILED: {len(failed)} of {len(results)} "
            "controls did not produce the required exit status",
            file=sys.stderr,
        )
        return 1
    print(
        f"[inferops-ci-gates] {len(results)} controls produced the exit status "
        "the repository requires of them",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
