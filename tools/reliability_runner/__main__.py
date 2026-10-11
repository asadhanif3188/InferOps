"""Write the plan and the Job of a reliability run, and check a caller record.

    python -m tools.reliability_runner plan --experiment-id ID --run-id ID \\
        --duration-seconds N [--request-ceiling N] [--release-id SHA256]
    python -m tools.reliability_runner manifest --plan FILE --image REPOSITORY@DIGEST
    python -m tools.reliability_runner verify RECORD [--plan FILE]
    python -m tools.reliability_runner rehearse

``plan`` prints the plan of one run of the committed RP-1 profile. Its target is the
API Service of the release, and no option changes it. ``manifest``
prints one ConfigMap and one Job that run a plan. ``verify`` checks a caller record,
which is the log of the pod of a run, and prints a summary of counts. ``rehearse``
runs the loop of the runner against scripted answers and prints the caller record.

**No command contacts a cluster, and no command sends a request.** ``plan``,
``manifest``, and ``rehearse`` write to standard output. A script applies a manifest.

Exit status 0 says that the command printed its result. For ``verify`` it says that
each rule accepted the record. **It does not say that a request succeeded.** Exit
status 3 says that one rule refused, and the message names the rule. Exit status 2
says that the arguments are not usable. Exit status 4 says that the command failed
in a way that no rule names.

See docs/serving/reliability-runner.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    PULL_POLICIES,
    RULE_PLAN,
    RunnerError,
    build_manifest,
    build_plan,
    manifest_text,
    plan_text,
    record_from,
    rehearse,
)
from .incluster import MAXIMUM_REQUEST_CEILING

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.reliability_runner",
        description=(
            "Write the plan and the Job of one RP-1 reliability run, and check a "
            "caller record. The command contacts no cluster."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="print the plan of one run")
    plan.add_argument("--experiment-id", required=True)
    plan.add_argument("--run-id", required=True)
    plan.add_argument("--duration-seconds", required=True, type=int)
    plan.add_argument("--request-ceiling", type=int, default=MAXIMUM_REQUEST_CEILING)
    plan.add_argument(
        "--release-id",
        help="the release identifier that the operator declares for the run",
    )

    manifest = commands.add_parser("manifest", help="print the ConfigMap and the Job")
    manifest.add_argument("--plan", required=True, type=Path)
    manifest.add_argument("--image", required=True)
    manifest.add_argument(
        "--image-pull-policy", choices=PULL_POLICIES, default=PULL_POLICIES[0]
    )

    verify = commands.add_parser("verify", help="check a caller record")
    verify.add_argument("record", type=Path)
    verify.add_argument("--plan", type=Path)

    commands.add_parser("rehearse", help="run the loop against scripted answers")
    return parser


def _run(arguments: argparse.Namespace) -> None:
    out = sys.stdout
    # The plan and the manifest are compared and hashed as bytes with LF.
    if hasattr(out, "reconfigure"):
        out.reconfigure(newline="\n")
    if arguments.command == "plan":
        out.write(
            plan_text(
                build_plan(
                    experiment_id=arguments.experiment_id,
                    run_id=arguments.run_id,
                    duration_seconds=arguments.duration_seconds,
                    request_ceiling=arguments.request_ceiling,
                    release_id=arguments.release_id,
                )
            )
        )
    elif arguments.command == "manifest":
        try:
            plan = json.loads(arguments.plan.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, RecursionError) as error:
            raise RunnerError(RULE_PLAN, "the plan file is unreadable") from error
        out.write(
            manifest_text(
                build_manifest(
                    plan,
                    image=arguments.image,
                    image_pull_policy=arguments.image_pull_policy,
                )
            )
        )
    elif arguments.command == "verify":
        record = record_from(arguments.record, plan_path=arguments.plan)
        out.write(json.dumps(record.summary(), indent=2, sort_keys=True) + "\n")
    else:
        out.write(rehearse())


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        _run(arguments)
    except RunnerError as error:
        print(f"REFUSED  {error}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception:
        print("FAILED   reliability runner: unexpected local failure", file=sys.stderr)
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
