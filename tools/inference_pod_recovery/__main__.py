"""The inference pod recovery experiment, from the command line.

`check` and `fields` read committed files. `repository`, `facts`, and `record` read
files the shell workflow wrote into its own run directory. `telemetry` is the only
command that contacts anything, and it contacts one loopback collector forward.
`verify` regenerates a committed record from its committed inputs and compares the
two, which is what makes a promoted record checkable without a cluster.

No command installs a release, deletes a pod, opens a forward, or sends load. Those
belong to `scripts/environment/inference-pod-recovery.sh`, which owns every contact
with the cluster and the one delete this experiment makes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.llm_load import core as load
from tools.performance_scenarios.core import ScenarioError, dumps

from . import core, live

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 3
EXIT_NOT_USABLE = 6

#: The committed name of every file a promoted record is made of, under its prefix.
#: The two raw sets are the disrupted run and the run that measures what callers get
#: back; `core.build_record` explains why there are two.
RECORD_FILES = {
    "environment": "environment.v1alpha1.json",
    "lifecycle": "lifecycle.v1alpha1.json",
    "readiness": "readiness.v1alpha1.json",
    "telemetry": "telemetry.v1alpha1.json",
    "disruptedRaw": "run-1-raw.jsonl",
    "recoveredRaw": "run-2-raw.jsonl",
    "record": "recovery-record.v1alpha1.json",
}

#: The inputs, in the order a reader meets them. The record file is not an input.
INPUT_NAMES = tuple(name for name in RECORD_FILES if name != "record")


def _read(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise core.RecoveryError(f"the {what} is unreadable") from error


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _run_paths(descriptor: core.Descriptor, run_dir: Path) -> dict[str, Path]:
    evidence = descriptor.document["evidence"]
    return {
        "cluster": run_dir / "cluster",
        "facts": run_dir / "facts.json",
        "environment": run_dir / str(evidence["environmentFile"]),
        "lifecycle": run_dir / str(evidence["lifecycleFile"]),
        "readiness": run_dir / str(evidence["readinessFile"]),
        "telemetry": run_dir / str(evidence["telemetryFile"]),
        "disruptedRaw": run_dir / str(evidence["disruptedRawFile"]),
        "recoveredRaw": run_dir / str(evidence["recoveredRawFile"]),
        "record": run_dir / str(evidence["recordDirectory"]),
    }


def _build(descriptor: core.Descriptor, texts: dict[str, str]) -> dict[str, Any]:
    return core.build_record(
        descriptor,
        environment_text=texts["environment"],
        lifecycle_text=texts["lifecycle"],
        readiness_text=texts["readiness"],
        telemetry_text=texts["telemetry"],
        disrupted_raw_text=texts["disruptedRaw"],
        recovered_raw_text=texts["recoveredRaw"],
    )


def _print_result(record: dict[str, Any], location: str) -> None:
    timings = record["timings"]
    failed = [check["checkId"] for check in record["checks"] if not check["passed"]]
    print(f"record       {location}")
    print(f"usable       {str(record['usable']).lower()}")
    if failed:
        print(f"failed       {', '.join(failed)}")
    print(
        "deleted      "
        f"{record['disruption']['pod']['name']} in phase "
        f"{record['disruption']['landedInScenarioId']}"
    )
    print(f"replaced by  {record['replacement']['pod']['name']}")
    print(
        "replacement  "
        f"ready {timings['deletionToReplacementReadyMs']} ms after the delete"
    )
    print(
        "outage       "
        f"{timings['callerVisibleOutageMs']} ms of it was caller-visible; the service "
        f"was restored {timings['deletionToServiceRestoredMs']} ms after the delete, "
        f"seen in the {timings['serviceRestoredObservedIn']}"
    )
    for window in record["callerImpact"]["windows"]:
        print(
            f"{window['window']:<22} {window['dispatched']} dispatched, "
            f"{window['successful']} served, {window['unsuccessful']} not"
        )
    print(f"claim        {record['boundary']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.inference_pod_recovery",
        description=(
            "Validate, drive, or evaluate the inference pod recovery experiment. No "
            "command installs a release, deletes a pod, opens a forward, or sends "
            "load, and `check` contacts nothing."
        ),
    )
    parser.add_argument(
        "command",
        choices=(
            "check",
            "fields",
            "repository",
            "facts",
            "telemetry",
            "record",
            "verify",
        ),
    )
    parser.add_argument(
        "paths", nargs="*", help="dotted descriptor paths (fields only)"
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="the run directory the shell workflow writes into",
    )
    parser.add_argument(
        "--collector-url",
        default="",
        help="loopback URL of the collector forward (telemetry only)",
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
        raise core.RecoveryError(f"{command} requires --run-dir")
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
                raise core.RecoveryError("fields needs at least one dotted path")
            for value in core.descriptor_fields(descriptor, list(arguments.paths)):
                print(value)
            return EXIT_OK

        if command == "verify":
            if arguments.dir is None:
                raise core.RecoveryError("verify requires --dir")
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
                    "REFUSED inference pod recovery: the committed record is not what "
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

        if command == "facts":
            facts = core.extract_facts(paths["cluster"], descriptor)
            # Round-tripped through the load generator's own validator rather than
            # trusted: a facts file this experiment wrote and tools.llm_load would
            # refuse is a file that fails halfway through a real run.
            load.parse_facts(facts)
            _write(paths["facts"], dumps(facts))
            print(f"facts        {paths['facts'].name}")
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
                "telemetry": _read(paths["telemetry"], "telemetry record"),
                "disruptedRaw": _read(
                    paths["disruptedRaw"], "disrupted raw load record set"
                ),
                "recoveredRaw": _read(
                    paths["recoveredRaw"], "recovered raw load record set"
                ),
            }
            record_dir = paths["record"]
            for name in INPUT_NAMES:
                _write(record_dir / RECORD_FILES[name], texts[name])
            record = _build(descriptor, texts)
            _write(record_dir / RECORD_FILES["record"], dumps(record))
            _print_result(record, str((record_dir / RECORD_FILES["record"]).as_posix()))
            return EXIT_OK if record["usable"] else EXIT_NOT_USABLE

        raise core.RecoveryError(f"unhandled command '{command}'")
    except core.RecoveryError as error:
        outcome = "REFUSED" if isinstance(error, core.RecoveryRefused) else "FAILED"
        print(f"{outcome} inference pod recovery: {error}", file=sys.stderr)
        return EXIT_REFUSED if isinstance(error, core.RecoveryRefused) else EXIT_FAILED
    except (load.LoadError, ScenarioError) as error:
        print(f"REFUSED inference pod recovery: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    raise SystemExit(main())
