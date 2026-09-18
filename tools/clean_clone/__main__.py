"""Commands behind the clean-clone workflow.

    python -m tools.clean_clone check
    python -m tools.clean_clone plan
    python -m tools.clean_clone checkout [--fresh]
    python -m tools.clean_clone begin --mode MODE [--provider P] [--cluster-name N]
                                      [--authorize ID ...] --started-ms MS [--restart]
    python -m tools.clean_clone resume --mode MODE [--provider P] [--cluster-name N]
                                       [--authorize ID ...]
    python -m tools.clean_clone pending
    python -m tools.clean_clone requires [--step ID]
    python -m tools.clean_clone record --step ID --outcome O --exit-code N
                                       --started-ms MS --finished-ms MS [--reason TEXT]
    python -m tools.clean_clone note --description TEXT [--step ID] [--at-ms MS]
    python -m tools.clean_clone summary [--json]
    python -m tools.clean_clone values --output PATH VALUES [VALUES ...]
    python -m tools.clean_clone runtime-image

``check``, ``plan``, and ``checkout`` read files and ``git`` and write nothing.
``begin``, ``record``, and ``note`` write one file, the run's ledger under
``.artifacts/clean-clone/``, which version control ignores. ``begin --restart``
moves a previous ledger aside under a timestamped name; nothing here deletes one.
``values`` writes one merged values file where it is told to, and
``runtime-image`` prints the pinned serving runtime reference a step pulls.

Exit status: 0 succeeded, 1 a check found a problem, 3 refused -- a precondition
was not met and nothing was written. None of these commands contacts a cluster, a
runtime, a network, or a model. See docs/environment/clean-clone.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from .core import (
    DESCRIPTOR_PATH,
    LEDGER_PATH,
    MODES,
    OUTCOMES,
    REPO_ROOT,
    CleanCloneError,
    assert_same_run,
    begin,
    check_authorizations,
    checkout_problems,
    descriptor_problems,
    load_descriptor,
    load_ledger,
    merge_values,
    note,
    pending_steps,
    record,
    repository_revision,
    step_by_id,
    steps,
    summarise,
    write_ledger,
)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 3


def _workflow_problems(descriptor: dict[str, Any]) -> list[str]:
    """Every script and tool module a step names must exist in this checkout."""
    problems: list[str] = []
    for entry in descriptor["steps"]:
        for ref in entry["runs"]:
            if ref.startswith("tools."):
                module = REPO_ROOT / Path(*ref.split("."))
                if not (module / "__main__.py").is_file():
                    problems.append(
                        f"{entry['stepId']}: tool module {ref} does not exist"
                    )
            elif not (REPO_ROOT / ref).is_file():
                problems.append(f"{entry['stepId']}: {ref} does not exist")
    return problems


def _plan(descriptor: dict[str, Any]) -> None:
    by_id = {entry["stepId"]: entry for entry in descriptor["steps"]}
    for number, step in enumerate(steps(descriptor), start=1):
        entry = by_id[step.step_id]
        auth = ", ".join(step.requires_authorization) or "none"
        print(f"{number:>2}. {step.step_id}  [{step.kind}]")
        print(f"    {step.title}")
        print(f"    runs:          {', '.join(entry['runs'])}")
        print(f"    authorization: {auth}")
        print(f"    evidence:      {step.evidence_label}")
        print(
            f"    resumable:     {'yes' if step.resumable else 'no, asked again every time'}"
        )


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.clean_clone",
        description=(
            "Check the clean-clone checklist, and keep the ledger of one run of it. "
            "Nothing here contacts a cluster, a runtime, a network, or a model."
        ),
    )
    parser.add_argument(
        "--descriptor", type=Path, default=DESCRIPTOR_PATH, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--ledger", type=Path, default=LEDGER_PATH, help=argparse.SUPPRESS
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser(
        "check", help="check the checklist against itself and the repository"
    )
    commands.add_parser("plan", help="print the checklist")

    checkout = commands.add_parser(
        "checkout", help="can this checkout stand for a clean clone"
    )
    checkout.add_argument(
        "--fresh", action="store_true", help="also refuse previous-run state"
    )

    start = commands.add_parser("begin", help="start a ledger for a new run")
    start.add_argument("--mode", choices=MODES, required=True)
    start.add_argument("--provider")
    start.add_argument("--cluster-name")
    start.add_argument("--authorize", action="append", default=[])
    start.add_argument("--started-ms", type=int, required=True)
    start.add_argument(
        "--restart", action="store_true", help="move an existing ledger aside"
    )

    again = commands.add_parser("resume", help="confirm a ledger may be continued here")
    again.add_argument("--mode", choices=MODES, required=True)
    again.add_argument("--provider")
    again.add_argument("--cluster-name")
    again.add_argument("--authorize", action="append", default=[])

    commands.add_parser(
        "pending", help="the steps the forward path should run, in order"
    )

    needs = commands.add_parser(
        "requires",
        help="the authorizations one step needs, or every step's with no --step",
    )
    needs.add_argument("--step")

    result = commands.add_parser("record", help="append one step attempt")
    result.add_argument("--step", required=True)
    result.add_argument("--outcome", choices=OUTCOMES, required=True)
    result.add_argument("--exit-code", type=int, required=True)
    result.add_argument("--started-ms", type=int, required=True)
    result.add_argument("--finished-ms", type=int, required=True)
    result.add_argument("--reason")

    manual = commands.add_parser("note", help="record a manual action")
    manual.add_argument("--description", required=True)
    manual.add_argument("--step")
    manual.add_argument("--at-ms", type=int)

    summary = commands.add_parser(
        "summary", help="what the ledger may be read as saying"
    )
    summary.add_argument("--json", action="store_true")

    layered = commands.add_parser(
        "values", help="merge values files the way helm -f does"
    )
    layered.add_argument("--output", type=Path, required=True)
    layered.add_argument("files", type=Path, nargs="+")

    commands.add_parser("runtime-image", help="print the pinned serving runtime image")

    arguments = parser.parse_args(argv)
    descriptor = load_descriptor(arguments.descriptor)
    ledger_path: Path = arguments.ledger

    if arguments.command == "check":
        problems = descriptor_problems(descriptor) + _workflow_problems(descriptor)
        for problem in problems:
            print(f"PROBLEM  {problem}")
        if problems:
            return EXIT_FAILED
        print(
            f"OK       {len(descriptor['steps'])} steps; every workflow they name exists"
        )
        return EXIT_OK

    if arguments.command == "plan":
        _plan(descriptor)
        return EXIT_OK

    if arguments.command == "runtime-image":
        from tools.runtime_packaging import load_runtime_package

        print(load_runtime_package().image_reference)
        return EXIT_OK

    try:
        if arguments.command == "requires":
            if arguments.step is None:
                for step in steps(descriptor):
                    print(" ".join((step.step_id, *step.requires_authorization)))
                return EXIT_OK
            for auth in step_by_id(descriptor, arguments.step).requires_authorization:
                print(auth)
            return EXIT_OK

        if arguments.command == "checkout":
            problems = checkout_problems(fresh=arguments.fresh)
            for problem in problems:
                print(f"REFUSED  {problem}")
            if problems:
                return EXIT_REFUSED
            print(
                "OK       no uncommitted change"
                + (" and no previous-run state" if arguments.fresh else "")
            )
            return EXIT_OK

        if arguments.command == "values":
            import yaml

            documents = []
            for path in arguments.files:
                if not path.is_file():
                    raise CleanCloneError(f"no values file at {path.as_posix()}")
                documents.append(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
            merged = merge_values(documents)
            output: Path = arguments.output
            output.parent.mkdir(parents=True, exist_ok=True)
            header = (
                "# Merged by python -m tools.clean_clone values, in this order:\n"
                + "".join(f"#   {path.as_posix()}\n" for path in arguments.files)
                + "# Host state, not evidence. Version control ignores .artifacts/.\n"
            )
            output.write_text(
                header + yaml.safe_dump(merged, sort_keys=False),
                encoding="utf-8",
                newline="\n",
            )
            print(f"WROTE    {output.as_posix()} from {len(arguments.files)} file(s)")
            return EXIT_OK

        if arguments.command == "begin":
            if ledger_path.exists():
                if not arguments.restart:
                    raise CleanCloneError(
                        f"{ledger_path.as_posix()} already exists; resume it, or restart "
                        "to move it aside and begin again"
                    )
                stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
                aside = ledger_path.with_name(f"ledger.{stamp}.v1alpha1.json")
                ledger_path.replace(aside)
                print(f"MOVED    the previous ledger to {aside.name}")
            ledger = begin(
                descriptor,
                mode=arguments.mode,
                provider=arguments.provider,
                cluster_name=arguments.cluster_name,
                revision=repository_revision(),
                authorizations=arguments.authorize,
                started_epoch_ms=arguments.started_ms,
            )
            write_ledger(ledger, ledger_path)
            print(f"BEGAN    {arguments.mode} run at {ledger['repositoryRevision']}")
            return EXIT_OK

        ledger = load_ledger(ledger_path)

        if arguments.command == "resume":
            check_authorizations(
                descriptor, mode=arguments.mode, authorizations=arguments.authorize
            )
            assert_same_run(
                ledger,
                mode=arguments.mode,
                revision=repository_revision(),
                provider=arguments.provider,
                cluster_name=arguments.cluster_name,
            )
            print(f"RESUMING {ledger['mode']} run begun {ledger['startedAt']}")
            return EXIT_OK

        if arguments.command == "pending":
            for step_id in pending_steps(ledger, descriptor):
                print(step_id)
            return EXIT_OK

        if arguments.command == "record":
            updated = record(
                ledger,
                descriptor,
                step_id=arguments.step,
                outcome=arguments.outcome,
                exit_code=arguments.exit_code,
                started_epoch_ms=arguments.started_ms,
                finished_epoch_ms=arguments.finished_ms,
                reason=arguments.reason,
            )
            write_ledger(updated, ledger_path)
            print(f"RECORDED {arguments.step} {arguments.outcome}")
            return EXIT_OK

        if arguments.command == "note":
            updated = note(
                ledger,
                descriptor,
                description=arguments.description,
                at_epoch_ms=arguments.at_ms
                if arguments.at_ms is not None
                else _now_ms(),
                step_id=arguments.step,
            )
            write_ledger(updated, ledger_path)
            print("NOTED    manual action recorded")
            return EXIT_OK

        view = summarise(ledger, descriptor)
        if arguments.json:
            print(json.dumps(view, indent=2))
            return EXIT_OK
        print(f"status        {view['status']}")
        print(f"mode          {view['mode']}")
        print(f"provider      {view['provider'] or 'none selected'}")
        print(
            f"certifies     {'yes' if view['certifiesProvider'] else 'no'} "
            f"(certification requires a complete run on {view['certifiedProvider']})"
        )
        print(f"revision      {view['repositoryRevision']}")
        print(f"wall clock    {view['wallClockMs']} ms")
        print(f"manual steps  {view['manualActions']}")
        for row in view["steps"]:
            outcome = row["outcome"] or "not reached"
            elapsed = "" if row["elapsedMs"] is None else f"  {row['elapsedMs']} ms"
            print(f"  {row['stepId']:<28} {outcome:<12}{elapsed}")
        return EXIT_OK
    except CleanCloneError as error:
        print(f"REFUSED  {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
