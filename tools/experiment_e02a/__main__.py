"""Print the plan of a V2-E02A run, dry-run the procedure, or run it.

    python -m tools.experiment_e02a plan
    python -m tools.experiment_e02a dry-run --run-id dry-run-N --scenario FILE
    python -m tools.experiment_e02a run --run-id e02a-N --controller-namespace NAME

``plan`` reads the latest registered V2-E02A freeze record, holds it to its
registry pin and to the phrases that this control restates, and prints what a run
takes from it. It reads no cluster.

``dry-run`` runs the procedure against a scenario file on a virtual clock. It
executes no cluster command, constructs no fault, records no fault event, and
takes an identifier ``dry-run-N``, never a run identifier. It writes under
``.artifacts/v2-e02a/dry-runs/``. A scenario that states no repository member
reads that member from the checkout: it runs ``git`` and the checks of P1, which
read files and contact no network.

``run`` runs the procedure on the cluster. It refuses to start unless the E02A
driver started it: each cluster command is a verb of that driver. Start it with
``bash docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt run e02a-N``.
It writes under ``.artifacts/v2-e02a/runs/``.

**Exit status 0 says that the control finished and wrote what it decided.** It
does not say that a precondition held or that a run is valid: a refusal and an
abort are results, and ``control.json`` states them. Exit status 4 says that the
control stopped on an error that the procedure does not decide, after the cleanup
that it could run; ``control.json`` states the state STOPPED. Exit status 3 says
that the record, the identifier, or the scenario cannot be used, and nothing was
written. Exit status 2 says that the arguments are not usable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .control import STOPPED, Control, IdentifierRefused
from .core import REPO_ROOT, PlanRefused, load_plan
from .ports import (
    DRY_RUNS_WORK,
    RUNS_WORK,
    LiveFault,
    LivePort,
    LocalRepository,
    ScenarioPort,
    ScenarioRefused,
    find_bash,
    load_scenario,
)

REFUSED_EXIT = 3
STOPPED_EXIT = 4


def _emit(text: str) -> None:
    """Write LF bytes on every host."""
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.experiment_e02a",
        description="Run the procedure of the latest V2-E02A freeze record.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="print what a run takes from the record")
    dry = commands.add_parser(
        "dry-run", help="run against a scenario, executing nothing"
    )
    dry.add_argument("--run-id", required=True, help="dry-run-N")
    dry.add_argument("--scenario", required=True, type=Path, help="a scenario file")
    live = commands.add_parser("run", help="run on the cluster, from the driver")
    live.add_argument("--run-id", required=True, help="e02a-N")
    live.add_argument(
        "--controller-namespace",
        required=True,
        help="the namespace of the delivery controller, as the driver names it",
    )
    arguments = parser.parse_args(argv)

    try:
        plan = load_plan(REPO_ROOT)
    except PlanRefused as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return REFUSED_EXIT

    if arguments.command == "plan":
        document = {
            "freezeRecord": {
                "path": plan.record_path,
                "revision": plan.revision,
                "contentSha256": plan.record_sha256,
            },
            "topology": {
                "apiReplicas": plan.api_replicas,
                "runtimeReplicas": plan.runtime_replicas,
            },
            "desiredStatePath": plan.desired_state_path,
            "desiredStateFiles": dict(plan.desired_state_files),
            "releaseId": plan.release_id,
            "environmentSha256": plan.environment_sha256,
            "callerRun": {
                "durationSeconds": plan.duration_seconds,
                "requestCeiling": plan.request_ceiling,
            },
        }
        _emit(json.dumps(document, indent=2, sort_keys=True) + "\n")
        return 0

    if arguments.command == "dry-run":
        try:
            scenario = load_scenario(arguments.scenario)
            port = ScenarioPort(scenario, LocalRepository(REPO_ROOT, plan))
        except ScenarioRefused as error:
            print(f"REFUSED: {error}", file=sys.stderr)
            return REFUSED_EXIT
        namespace = scenario.get("controllerNamespace")
        if not isinstance(namespace, str) or not namespace:
            print(
                "REFUSED: the scenario states no controllerNamespace", file=sys.stderr
            )
            return REFUSED_EXIT
        control = Control(
            plan,
            port,
            run_id=arguments.run_id,
            work_root=REPO_ROOT / DRY_RUNS_WORK,
            controller_namespace=namespace,
            fault=None,
        )
    else:
        driver = os.environ.get("INFEROPS_E02A_DRIVER")
        bash = find_bash()
        if not driver or not Path(driver).is_file() or bash is None:
            print(
                "REFUSED: a run starts from the E02A driver, which names each "
                "cluster command",
                file=sys.stderr,
            )
            return REFUSED_EXIT
        work_root = REPO_ROOT / RUNS_WORK
        live_port = LivePort(
            REPO_ROOT, plan, Path(driver), bash, work_root / arguments.run_id
        )
        try:
            fault = LiveFault(
                REPO_ROOT, Path(driver), bash, arguments.run_id, live_port
            )
        except ValueError as error:
            print(f"REFUSED: {error}", file=sys.stderr)
            return REFUSED_EXIT
        control = Control(
            plan,
            live_port,
            run_id=arguments.run_id,
            work_root=work_root,
            controller_namespace=arguments.controller_namespace,
            fault=fault,
        )

    try:
        outcome = control.run()
    except IdentifierRefused as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return REFUSED_EXIT
    relative = outcome.work.relative_to(REPO_ROOT).as_posix()
    _emit(
        f"{outcome.state}"
        + (f" ({outcome.reason}, at {outcome.step})" if outcome.reason else "")
        + f": {relative}/control.json\n"
    )
    return STOPPED_EXIT if outcome.state == STOPPED else 0


if __name__ == "__main__":
    raise SystemExit(main())
