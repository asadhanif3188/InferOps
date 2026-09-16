"""The unready model recovery experiment, from the command line.

`check`, `fields`, and `surfaces` read committed files. `repository`, `telemetry`, and
`record` read files the shell workflow wrote into its own run directory. `telemetry`
is the only command that contacts anything, and it contacts one loopback collector
forward. `verify` regenerates a committed record from its committed inputs and
compares the two, which is what makes a promoted record checkable without a cluster.

No command installs a release, upgrades one, opens a forward, or sends a request.
Those belong to `scripts/environment/unready-model-recovery.sh`, which owns every
contact with the cluster and the two mutating commands this experiment issues after
the install: the corrected upgrade and the uninstall.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.performance_scenarios.core import ScenarioError, dumps

from . import core, live

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 3
EXIT_NOT_USABLE = 6

#: The committed name of every file a promoted record is made of, under its prefix.
RECORD_FILES = {
    "environment": "environment.v1alpha1.json",
    "lifecycle": "lifecycle.v1alpha1.json",
    "readiness": "readiness.v1alpha1.json",
    "probes": "probes.v1alpha1.jsonl",
    "diagnostics": "diagnostics.v1alpha1.json",
    "telemetry": "telemetry.v1alpha1.json",
    "record": "unready-model-record.v1alpha1.json",
}

#: The inputs, in the order a reader meets them. The record file is not an input.
INPUT_NAMES = tuple(name for name in RECORD_FILES if name != "record")


def _read(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise core.UnreadyError(f"the {what} is unreadable") from error


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _run_paths(descriptor: core.Descriptor, run_dir: Path) -> dict[str, Path]:
    evidence = descriptor.document["evidence"]
    return {
        "cluster": run_dir / "cluster",
        "environment": run_dir / str(evidence["environmentFile"]),
        "lifecycle": run_dir / str(evidence["lifecycleFile"]),
        "readiness": run_dir / str(evidence["readinessFile"]),
        "probes": run_dir / str(evidence["probesFile"]),
        "diagnostics": run_dir / str(evidence["diagnosticsFile"]),
        "telemetry": run_dir / str(evidence["telemetryFile"]),
        "record": run_dir / str(evidence["recordDirectory"]),
    }


def _build(descriptor: core.Descriptor, texts: dict[str, str]) -> dict[str, Any]:
    return core.build_record(
        descriptor,
        environment_text=texts["environment"],
        lifecycle_text=texts["lifecycle"],
        readiness_text=texts["readiness"],
        probes_text=texts["probes"],
        diagnostics_text=texts["diagnostics"],
        telemetry_text=texts["telemetry"],
    )


def _print_result(record: dict[str, Any], location: str) -> None:
    timings = record["timings"]
    failed = [check["checkId"] for check in record["checks"] if not check["passed"]]
    codes = record["callerSurface"]["canonicalCodesObserved"]
    unready = record["readinessAcrossTheWindow"]["unready"]
    print(f"record       {location}")
    print(f"usable       {str(record['usable']).lower()}")
    if failed:
        print(f"failed       {', '.join(failed)}")
    print(
        "unready      held "
        f"{timings['unreadyWindowHeldMs']} ms; the serving runtime container restarted "
        f"{unready['highestRuntimeRestartCount']} time(s)"
    )
    print(f"callers got  {', '.join(codes) or 'no canonical code'}")
    print(
        "recovered    runtime ready "
        f"{timings['upgradeToRuntimeReadyMs']} ms after the upgrade; a completion came "
        f"back {timings['upgradeToFirstServedCompletionMs']} ms after it"
    )
    for surface in record["callerSurface"]["surfaces"]:
        print(
            f"{surface['probeId']:<16} unready {surface['unready']['statuses']} -> "
            f"recovered {surface['recovered']['statuses']}"
        )
    print(f"claim        {record['boundary']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.unready_model_recovery",
        description=(
            "Validate, drive, or evaluate the unready model recovery experiment. No "
            "command installs a release, upgrades one, opens a forward, or sends a "
            "request, and `check` contacts nothing."
        ),
    )
    parser.add_argument(
        "command",
        choices=(
            "check",
            "fields",
            "surfaces",
            "repository",
            "diagnostics",
            "telemetry",
            "record",
            "verify",
        ),
    )
    parser.add_argument(
        "paths", nargs="*", help="dotted descriptor paths (fields only)"
    )
    parser.add_argument(
        "--run-dir", type=Path, help="the run directory the shell workflow writes into"
    )
    parser.add_argument(
        "--collector-url",
        default="",
        help="loopback URL of the collector forward (telemetry only)",
    )
    parser.add_argument(
        "--excerpt-lines",
        type=int,
        default=12,
        help="how many trailing lines of each capture the record excerpts",
    )
    parser.add_argument(
        "--dir", type=Path, help="directory holding a committed record (verify only)"
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="file name prefix of a committed record (verify only)",
    )
    return parser


def _require_run_dir(arguments: argparse.Namespace, command: str) -> Path:
    if arguments.run_dir is None:
        raise core.UnreadyError(f"{command} requires --run-dir")
    return Path(arguments.run_dir)


def _repository(run_dir: Path) -> None:
    """What the repository was when the run happened, including what it executed."""
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=core.REPO_ROOT,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
        cwd=core.REPO_ROOT,
    ).stdout.splitlines()
    document = {
        "revision": revision,
        "trackedChangesPresent": any(
            not line.startswith("??") for line in status if line.strip()
        ),
        "untrackedFilesPresent": any(line.startswith("??") for line in status),
        "executedFiles": core.executed_file_digests(),
    }
    _write(run_dir / "cluster" / "repository.json", dumps(document))
    print(f"repository   {revision}")


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    command = str(arguments.command)
    try:
        descriptor = core.load_descriptor()

        if command == "check":
            for line in core.summary_lines(descriptor):
                print(line)
            print("execution    not started (offline descriptor validation only)")
            return EXIT_OK

        if command == "fields":
            if not arguments.paths:
                raise core.UnreadyError("fields needs at least one dotted path")
            for value in core.descriptor_fields(descriptor, list(arguments.paths)):
                print(value)
            return EXIT_OK

        if command == "surfaces":
            for line in core.probe_lines(descriptor):
                print(line)
            return EXIT_OK

        if command == "verify":
            if arguments.dir is None:
                raise core.UnreadyError("verify requires --dir")
            directory = Path(arguments.dir)
            prefix = str(arguments.prefix)
            texts = {
                name: _read(
                    directory / f"{prefix}{RECORD_FILES[name]}", f"committed {name}"
                )
                for name in INPUT_NAMES
            }
            rebuilt = _build(descriptor, texts)
            committed = _read(
                directory / f"{prefix}{RECORD_FILES['record']}", "committed record"
            )
            if dumps(rebuilt) != committed.replace("\r\n", "\n"):
                print(
                    "REFUSED unready model recovery: the committed record is not what "
                    "its inputs produce",
                    file=sys.stderr,
                )
                return EXIT_FAILED
            print(
                "ok           the committed record regenerates from its inputs; "
                f"usable={rebuilt['usable']}"
            )
            return EXIT_OK

        run_dir = _require_run_dir(arguments, command)
        paths = _run_paths(descriptor, run_dir)

        if command == "repository":
            _repository(run_dir)
            return EXIT_OK

        if command == "diagnostics":
            document = core.build_diagnostics(
                paths["cluster"].parent / "captures" / "index.txt",
                excerpt_lines=int(arguments.excerpt_lines),
            )
            _write(paths["diagnostics"], dumps(document))
            withheld = sum(
                int(entry["excerptLinesWithheld"])
                for entry in document["diagnostics"]["captures"]
            )
            print(
                f"diagnostics  {len(document['diagnostics']['captures'])} capture(s); "
                f"{withheld} excerpt line(s) withheld as unpublishable"
            )
            return EXIT_OK

        if command == "telemetry":
            lifecycle = core.parse_lifecycle(
                json.loads(_read(paths["lifecycle"], "lifecycle record")), descriptor
            )
            captured = live.capture_telemetry(
                descriptor,
                start_epoch_ms=int(lifecycle["idleBaseline"]["startEpochMs"]),
                end_epoch_ms=int(lifecycle["settledEpochMs"]),
                ask=live.http_asker(str(arguments.collector_url)),
            )
            _write(paths["telemetry"], dumps(captured))
            answered = sum(
                1 for entry in captured["series"] if entry["status"] == "success"
            )
            print(
                f"telemetry    {answered} of {len(captured['series'])} expressions "
                "answered"
            )
            return EXIT_OK

        if command == "record":
            environment = core.extract_environment(paths["cluster"], descriptor)
            _write(paths["environment"], dumps(environment))
            texts = {
                "environment": dumps(environment),
                "lifecycle": _read(paths["lifecycle"], "lifecycle record"),
                "readiness": _read(paths["readiness"], "readiness record"),
                "probes": _read(paths["probes"], "probe record set"),
                "diagnostics": _read(paths["diagnostics"], "diagnostics record"),
                "telemetry": _read(paths["telemetry"], "telemetry record"),
            }
            record_dir = paths["record"]
            for name in INPUT_NAMES:
                _write(record_dir / RECORD_FILES[name], texts[name])
            record = _build(descriptor, texts)
            _write(record_dir / RECORD_FILES["record"], dumps(record))
            _print_result(record, str((record_dir / RECORD_FILES["record"]).as_posix()))
            return EXIT_OK if record["usable"] else EXIT_NOT_USABLE

        raise core.UnreadyError(f"unhandled command '{command}'")
    except core.UnreadyError as error:
        outcome = "REFUSED" if isinstance(error, core.UnreadyRefused) else "FAILED"
        print(f"{outcome} unready model recovery: {error}", file=sys.stderr)
        return EXIT_REFUSED if isinstance(error, core.UnreadyRefused) else EXIT_FAILED
    except ScenarioError as error:
        print(f"REFUSED unready model recovery: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    raise SystemExit(main())
