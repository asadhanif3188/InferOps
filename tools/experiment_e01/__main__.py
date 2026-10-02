"""Run the static parts of V2-E01 once, or check the committed runs.

    PYTHONHASHSEED=1 python -m tools.experiment_e01 --run RUN_ID
    python -m tools.experiment_e01 --check

``--run`` executes E01-A, E01-B, and E01-C as the E01 family freeze record registers
them, and writes one evidence directory under docs/proof/experiments/v2-e01/runs/.
It starts only with ``PYTHONHASHSEED=1``, the seed of the process that writes
render-a; the second render runs in a process with seed 2. ``--merged-ref`` names the
branch the executing commit must be merged into, ``origin/main`` by default.
``--prelude FILE`` copies the operator's preparation commands into commands.txt,
marked as stated by the operator. Exit status is 0 when every part PASSED, 1 when a
part has another outcome, and 2 when nothing was written.

``--check`` computes the verdicts of every committed run again from its raw evidence
and compares them with the outcomes, criteria, file digests, and result page the run
recorded. It writes nothing and runs no part. Exit status is 0 when every run agrees
with its evidence and 1 when one does not.

``--root DIRECTORY`` names the repository to read and write; the default is this
checkout. See docs/proof/experiments/README.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from .core import (
    HASH_SEEDS,
    PARTS,
    REPO_ROOT,
    check_run,
    committed_runs,
    execute_run,
    render_second,
)


def _check(root: Path) -> int:
    runs = committed_runs(root)
    findings = [finding for run in runs for finding in check_run(run, root)]
    for finding in findings:
        print(f"MISMATCH  {finding.run}  {finding.location}: {finding.detail}")
    if findings:
        print(f"FAILED: {len(findings)} finding(s) across {len(runs)} run(s)")
        return 1
    print(f"PASSED: {len(runs)} run(s), each agrees with its own evidence")
    return 0


#: Options whose value may name a file on the operator's host. commands.txt records
#: the option and withholds an absolute value, so no local path enters the evidence.
_WITHHELD = {"--prelude": "<preparation commands file>", "--root": "<repository root>"}


def _host_path(value: str) -> bool:
    return Path(value).is_absolute() or value.startswith(("/", "\\"))


def _shown(argv: Sequence[str]) -> str:
    """The command line as commands.txt records it, with host paths withheld."""
    shown: list[str] = []
    withhold_next: str | None = None
    for argument in argv:
        option, equals, value = argument.partition("=")
        if withhold_next is not None and _host_path(argument):
            shown.append(withhold_next)
        elif option in _WITHHELD and equals and _host_path(value):
            shown.append(f"{option}={_WITHHELD[option]}")
        else:
            shown.append(argument)
        withhold_next = _WITHHELD.get(argument)
    return " ".join(shown)


def _run(
    root: Path,
    run_id: str,
    merged_ref: str,
    prelude: Path | None,
    argv: Sequence[str],
) -> int:
    seed = os.environ.get("PYTHONHASHSEED")
    if seed != HASH_SEEDS["render-a"]:
        print(
            f"NOT STARTED: PYTHONHASHSEED is {seed!r}; a run starts with "
            f"PYTHONHASHSEED={HASH_SEEDS['render-a']}. Nothing was written."
        )
        return 2
    stated = (
        []
        if prelude is None
        else [line for line in prelude.read_text(encoding="utf-8").splitlines() if line]
    )
    package = (__spec__.parent if __spec__ else None) or "tools.experiment_e01"
    invocation = f"PYTHONHASHSEED={seed} python -m {package} {_shown(argv)}"
    try:
        evidence, judgement = execute_run(
            root,
            run_id,
            merged_ref=merged_ref,
            prelude=stated,
            invocation=invocation,
            package=package,
        )
    except (ValueError, FileExistsError) as error:
        print(f"NOT STARTED: {error}. Nothing was written.")
        return 2
    for part in PARTS:
        print(f"{judgement.outcomes[part]:<12}  {part}")
    print(f"evidence: {evidence.relative_to(root).as_posix()}")
    return 0 if all(o == "PASSED" for o in judgement.outcomes.values()) else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.experiment_e01")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", metavar="RUN_ID", help="run E01-A, E01-B, and E01-C")
    mode.add_argument("--check", action="store_true", help="check every committed run")
    # The second E01-A render, started by --run in its own process.
    mode.add_argument("--render-second", metavar="DIRECTORY", help=argparse.SUPPRESS)
    parser.add_argument("--merged-ref", default="origin/main", help=argparse.SUPPRESS)
    parser.add_argument("--prelude", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--revision", help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    if arguments.check:
        return _check(root)
    if arguments.render_second:
        reported = render_second(
            root, arguments.revision, root / arguments.render_second
        )
        print(json.dumps(reported))
        return 0
    return _run(
        root,
        arguments.run,
        arguments.merged_ref,
        arguments.prelude,
        sys.argv[1:] if argv is None else argv,
    )


if __name__ == "__main__":
    sys.exit(main())
