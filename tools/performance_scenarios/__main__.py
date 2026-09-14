"""Commands for the performance scenario matrix.

`check` and `fields` read committed files. `repository`, `facts`, and `record` read
files the shell workflow wrote and write files beside them. `telemetry` is the only
command that contacts anything: the release's collector, through a loopback forward.
`verify` regenerates a committed record from its committed inputs and compares.

None of them contacts Kubernetes, installs anything, or sends inference load. That
is `scripts/environment/performance-scenarios.sh`, which calls these.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.llm_load import core as load

from .core import (
    REPO_ROOT,
    ScenarioError,
    build_record,
    descriptor_fields,
    dumps,
    executed_file_digests,
    extract_environment,
    extract_facts,
    load_descriptor,
    parse_samples,
    parse_windows,
    read_json,
    samples_jsonl,
)
from .live import capture_telemetry, http_asker

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 3
EXIT_NOT_USABLE = 6

#: The committed names of a record's inputs and of the record, without a prefix.
RECORD_FILES = {
    "environment": "environment.v1alpha1.json",
    "windows": "windows.v1alpha1.json",
    "samples": "resource-samples.v1alpha1.jsonl",
    "telemetry": "telemetry.v1alpha1.json",
    "record": "performance-record.v1alpha1.json",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _read(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ScenarioError(f"the {what} is unreadable") from error


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise ScenarioError(f"git {arguments[0]} failed")
    return completed.stdout


def _raw_names(windows_document: object) -> list[str]:
    runs = windows_document["runs"] if isinstance(windows_document, dict) else []
    return [str(run["rawFile"]) for run in runs]


def _build(
    directory: Path, prefix: str, *, raw_directory: Path
) -> tuple[dict[str, Any], dict[str, str]]:
    descriptor = load_descriptor()
    texts = {
        key: _read(directory / f"{prefix}{name}", key)
        for key, name in RECORD_FILES.items()
        if key != "record"
    }
    windows_document = read_json(
        directory / f"{prefix}{RECORD_FILES['windows']}", "windows"
    )
    raw_texts = {
        name: _read(raw_directory / f"{prefix}{name}", name)
        for name in _raw_names(windows_document)
    }
    record = build_record(
        descriptor,
        environment_text=texts["environment"],
        windows_text=texts["windows"],
        raw_texts=raw_texts,
        samples_text=texts["samples"],
        telemetry_text=texts["telemetry"],
    )
    return record, texts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.performance_scenarios",
        description=(
            "Validate the performance scenario matrix, derive its load facts and "
            "environment from what the cluster reported, capture the collector's "
            "readings, and build or verify its record. No figure it records is a "
            "portable capacity figure, a production SLO, or a benchmark."
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
        default=None,
        help="the run directory the shell workflow writes",
    )
    parser.add_argument(
        "--collector-url",
        default=None,
        help="loopback URL of the collector forward (telemetry only)",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="directory holding a committed record (verify only)",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="file name prefix of a committed record (verify only)",
    )
    arguments = parser.parse_args(argv)

    try:
        descriptor = load_descriptor()
        command = arguments.command
        if command == "check":
            scenarios = ", ".join(
                f"{scenario.scenario_id}={scenario.concurrency} ({scenario.role})"
                for scenario in descriptor.scenarios
            )
            print(
                f"descriptor   {descriptor.document['experimentId']} {descriptor.document['experimentVersion']} sha256:{descriptor.sha256}"
            )
            print(f"load profile sha256:{descriptor.profile.profile_sha256}")
            print(f"scenarios    {scenarios}")
            print(
                f"schedule     {descriptor.repetitions} repetition(s); idle {descriptor.idle_seconds} s; "
                f"settle {descriptor.settle_between_seconds} s between, {descriptor.settle_after_seconds} s after"
            )
            print(
                f"resources    node cgroup v1 every {descriptor.sample_interval_ms} ms"
            )
            print(
                f"telemetry    {len(descriptor.series)} series; {len(descriptor.reconciliation)} reconciliation check(s)"
            )
            print(
                "claim        bounded observations; not capacity, an SLO, or a benchmark; saturation not judged"
            )
            return EXIT_OK
        if command == "fields":
            if not arguments.paths:
                raise ScenarioError("fields needs at least one dotted path")
            for value in descriptor_fields(descriptor, arguments.paths):
                print(value)
            return EXIT_OK
        if command == "verify":
            if arguments.dir is None:
                raise ScenarioError("verify requires --dir")
            record, _ = _build(
                arguments.dir, arguments.prefix, raw_directory=arguments.dir
            )
            committed = _read(
                arguments.dir / f"{arguments.prefix}{RECORD_FILES['record']}",
                "committed record",
            )
            if dumps(record) != committed.replace("\r\n", "\n"):
                print(
                    "REFUSED performance record: the committed record is not what its inputs produce",
                    file=sys.stderr,
                )
                return EXIT_FAILED
            print(
                f"ok           the committed record regenerates from its inputs; usable={record['usable']}"
            )
            return EXIT_OK

        if arguments.run_dir is None:
            raise ScenarioError(f"{command} requires --run-dir")
        run_dir: Path = arguments.run_dir
        cluster_dir = run_dir / "cluster"
        if command == "repository":
            status = _git("status", "--porcelain")
            document = {
                "revision": _git("rev-parse", "HEAD").strip(),
                "trackedChangesPresent": any(
                    line and not line.startswith("??") for line in status.splitlines()
                ),
                "untrackedFilesPresent": any(
                    line.startswith("??") for line in status.splitlines()
                ),
                "executedFiles": executed_file_digests(),
            }
            _write(cluster_dir / "repository.json", dumps(document))
            print(
                "repository   recorded the revision and the digests of the files a run executes"
            )
            return EXIT_OK
        if command == "facts":
            facts = extract_facts(cluster_dir, descriptor)
            load.parse_facts(facts)
            _write(run_dir / "facts.json", dumps(facts))
            print(
                "facts        derived from the cluster's answers and checked against this repository"
            )
            return EXIT_OK
        windows = parse_windows(
            read_json(
                run_dir / str(descriptor.document["evidence"]["windowsFile"]), "windows"
            ),
            descriptor,
        )
        raws = [
            load.read_raw(run_dir / "load" / str(run["rawFile"]))
            for run in windows["runs"]
        ]
        if command == "telemetry":
            if arguments.collector_url is None:
                raise ScenarioError("telemetry requires --collector-url")
            captured = capture_telemetry(
                descriptor, windows, raws, http_asker(arguments.collector_url)
            )
            _write(
                run_dir / str(descriptor.document["evidence"]["telemetryFile"]),
                dumps(captured),
            )
            print(
                f"telemetry    {len(captured['series'])} series, {len(captured['instants'])} counter reads, {len(captured['dashboard'])} dashboard captures"
            )
            return EXIT_OK

        # record
        evidence = descriptor.document["evidence"]
        out = run_dir / str(evidence["recordDirectory"])
        environment = extract_environment(cluster_dir, descriptor)
        _write(out / RECORD_FILES["environment"], dumps(environment))
        _write(
            out / RECORD_FILES["windows"],
            _read(run_dir / str(evidence["windowsFile"]), "windows").replace(
                "\r\n", "\n"
            ),
        )
        _write(
            out / RECORD_FILES["samples"],
            samples_jsonl(
                parse_samples(_read(run_dir / str(evidence["samplesFile"]), "samples"))
            ),
        )
        _write(
            out / RECORD_FILES["telemetry"],
            _read(run_dir / str(evidence["telemetryFile"]), "telemetry").replace(
                "\r\n", "\n"
            ),
        )
        for run in windows["runs"]:
            name = str(run["rawFile"])
            _write(
                out / name, _read(run_dir / "load" / name, name).replace("\r\n", "\n")
            )
        record, _ = _build(out, "", raw_directory=out)
        _write(out / RECORD_FILES["record"], dumps(record))
        failed = [check["checkId"] for check in record["checks"] if not check["passed"]]
        print(f"record       {out.as_posix()}/{RECORD_FILES['record']}")
        print(
            f"usable       {record['usable']}{'' if not failed else ' (failed: ' + ', '.join(failed) + ')'}"
        )
        print(
            "claim        bounded observations; not capacity, an SLO, or a benchmark; saturation not judged"
        )
        return EXIT_OK if record["usable"] else EXIT_NOT_USABLE
    except (ScenarioError, load.LoadError) as error:
        print(f"REFUSED performance scenarios: {error}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
