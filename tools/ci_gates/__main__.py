"""Run the expected-failure controls and report what each command did.

    python -m tools.ci_gates expected-failures
    python -m tools.ci_gates kubernetes-failures
    python -m tools.ci_gates terraform-failures
    python -m tools.ci_gates no-skips helm

Exit status is 0 when every control produced the exit status the repository
requires of it and 1 when any did not, so each command is usable as a gate.
`--json` produces a stable document a reviewer can diff between runs.

`expected-failures` runs modules from this repository against files in it and
contacts nothing. `kubernetes-failures` and `terraform-failures` run the pinned
`helm`, `kubeconform`, `terraform`, and `tflint`, and refuse to start unless all
of them are present at the pinned version; they reach no cluster, and two of the
tools read over the network - kubeconform its schemas, terraform its provider.
`no-skips` runs one tool-backed test module and fails on any skipped test.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import infrastructure, suites
from .core import REPO_ROOT, Result, controls, run, shortfalls

PREFIX = "[inferops-ci-gates]"


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


def _expected_failures(as_json: bool) -> int:
    found = controls()
    missing = shortfalls(found)
    if missing:
        for line in missing:
            print(f"{PREFIX} FAILED: {line}", file=sys.stderr)
        return 1

    results = list(run(found))

    if as_json:
        print(json.dumps(_report(results), indent=2, sort_keys=True))
    else:
        for result in results:
            verdict = "ok" if result.passed else "FAILED"
            print(
                f"{PREFIX} {verdict} {result.control.controlId} "
                f"expected exit {result.control.expected_exit}, "
                f"got {result.actual_exit}"
            )
            # Only for a control that went the wrong way. A gate that reports
            # nothing but two numbers is a gate somebody has to reproduce by
            # hand before they can begin to read it.
            if not result.passed:
                print(f"  command: {result.control.published_command}")
                for stream, text in (
                    ("stdout", result.stdout),
                    ("stderr", result.stderr),
                ):
                    for line in text.splitlines():
                        print(f"  {stream}: {line}")

    return _verdict(sum(not r.passed for r in results), len(results))


def _tool_failures(family: str, as_json: bool) -> int:
    found = infrastructure.controls(family)
    missing = infrastructure.shortfalls(family, found)
    tools, problems = infrastructure.tool_problems(family)
    for line in [*missing, *problems]:
        print(f"{PREFIX} FAILED: {line}", file=sys.stderr)
    if missing or problems:
        return 1

    results = list(infrastructure.run(found, tools))

    if as_json:
        report = {
            "gate": f"{family}-failures",
            "pinnedVersions": {
                tool: infrastructure.PINNED_VERSIONS[tool]
                for tool in infrastructure.TOOLS_BY_FAMILY[family]
            },
            "controls": [
                {
                    "controlId": result.control.controlId,
                    "failsAt": result.control.fails_at,
                    "exits": list(result.exits),
                    "passed": result.passed,
                }
                for result in results
            ],
            "passed": all(result.passed for result in results),
        }
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for result in results:
            verdict = "ok" if result.passed else "FAILED"
            expected = (
                "every stage succeeds"
                if result.control.fails_at is None
                else f"stage {result.control.fails_at + 1} refuses"
            )
            print(
                f"{PREFIX} {verdict} {result.control.controlId} "
                f"expected {expected}, exits {list(result.exits)}"
            )
            if not result.passed:
                print(f"  command: {result.control.published_command}")
                if result.control.reason is not None:
                    print(f"  required in the refusal: {result.control.reason}")
                for line in result.output.splitlines():
                    print(f"  output: {line}")

    return _verdict(sum(not r.passed for r in results), len(results))


def _no_skips(tool: str) -> int:
    report = suites.run([tool])
    for name in report.skipped:
        print(f"{PREFIX} SKIPPED: {name}", file=sys.stderr)
    if not report.passed:
        print(
            f"{PREFIX} FAILED: {suites.TOOL_BACKED_SUITES[tool]} ran "
            f"{report.tests} tests with {report.failures} failures, "
            f"{report.errors} errors, and {len(report.skipped)} skips; the gate "
            "installs the tool, so a skip here is a check that did not run",
            file=sys.stderr,
        )
        return 1
    print(
        f"{PREFIX} {suites.TOOL_BACKED_SUITES[tool]} ran {report.tests} tests "
        "with none skipped",
        file=sys.stderr,
    )
    return 0


def _verdict(failed: int, total: int) -> int:
    if failed:
        print(
            f"{PREFIX} FAILED: {failed} of {total} controls did not produce the "
            "required exit status",
            file=sys.stderr,
        )
        return 1
    print(
        f"{PREFIX} {total} controls produced the exit status the repository "
        "requires of them",
        file=sys.stderr,
    )
    return 0


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
        choices=[
            "expected-failures",
            "kubernetes-failures",
            "terraform-failures",
            "no-skips",
        ],
        help="the gate to run",
    )
    parser.add_argument(
        "tool",
        nargs="?",
        choices=sorted(suites.TOOL_BACKED_SUITES),
        help="for no-skips: the tool whose suite must run without a skip",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit a machine-readable report"
    )
    arguments = parser.parse_args(argv)

    if arguments.gate == "no-skips":
        if arguments.tool is None:
            parser.error("no-skips needs a tool: helm or terraform")
        return _no_skips(arguments.tool)
    if arguments.tool is not None:
        parser.error(f"{arguments.gate} takes no tool argument")
    if arguments.gate == "expected-failures":
        return _expected_failures(arguments.json)
    family = arguments.gate.removesuffix("-failures")
    return _tool_failures(family, arguments.json)


if __name__ == "__main__":
    raise SystemExit(main())
