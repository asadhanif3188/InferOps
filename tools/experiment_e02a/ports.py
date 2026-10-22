"""The ports of the control: the repository, the live cluster, and a scenario.

:class:`LocalRepository` reads the checkout and runs the checks of P1. It reads no
network: P2 of a run reads the remote main through :class:`LivePort`.

:class:`LivePort` runs each cluster read and each cluster act as one verb of the
E02A driver, ``docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt``. The
driver is the one file through which the control issues a cluster command, and the
scripts that it calls issue their own. This package names no delivery controller
and no script. Each command and what it printed are kept for ``commands.txt`` and
``transcript.txt``. The output of a verb goes to a file and not to a pipe, so a
process that a verb leaves behind cannot hold the control.

:class:`LiveFault` deletes one pod through the fault verb of the driver. It is
constructed for a run identifier and never for a dry run.

:class:`ScenarioPort` answers each cluster read from a scenario file and executes
no cluster command. It is the port of a dry run, and it has no fault. A scenario
that states no repository member reads that member from the checkout: it runs
``git`` and the checks of P1, which read files and contact no network.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import IO, Any, Final

from tools.experiment_freeze.core import content_digest

from . import core
from .control import CONTROL_FILE, P1_CHECKS
from .core import Plan

__all__ = [
    "SCENARIO_SCHEMA",
    "LiveFault",
    "LivePort",
    "LocalRepository",
    "ScenarioPort",
    "ScenarioRefused",
]

SCENARIO_SCHEMA: Final = "inferops.io/experiment-e02a-dry-run-scenario/v1alpha1"

#: Where the work directories of runs and of dry runs are kept. Git ignores both.
RUNS_WORK: Final = ".artifacts/v2-e02a/runs"
DRY_RUNS_WORK: Final = ".artifacts/v2-e02a/dry-runs"

#: Where the collectors and the runner leave what a run keeps.
TIMELINE_STREAMS: Final = ".artifacts/experiment-timeline/collections/{run}/streams"
TELEMETRY_STREAMS: Final = ".artifacts/experiment-telemetry/collections/{run}/streams"
RUNNER_RUN: Final = ".artifacts/reliability-runner/runs/{run}"
CAPACITY_RECORD: Final = (
    ".artifacts/capacity-preflight/collections/{name}/record.v1alpha1.json"
)

GIT_TIMEOUT_SECONDS: Final = 120
CHECK_TIMEOUT_SECONDS: Final = 900
VERB_TIMEOUT_SECONDS: Final = 3600
FAULT_TIMEOUT_SECONDS: Final = 300


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


@dataclass
class LocalRepository:
    """The reads of the checkout. Each git call has a timeout, and none reads the network."""

    root: Path
    plan: Plan

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[bytes] | None:
        try:
            return subprocess.run(
                ["git", "-c", "core.quotepath=off", *arguments],
                cwd=self.root,
                capture_output=True,
                timeout=GIT_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

    def head(self) -> str | None:
        done = self._git("rev-parse", "HEAD")
        if done is None or done.returncode != 0:
            return None
        return done.stdout.decode("ascii", "replace").strip()

    def clean(self) -> bool | None:
        done = self._git("status", "--porcelain", "--untracked-files=all")
        if done is None or done.returncode != 0:
            return None
        return not done.stdout.strip()

    def check(self, module: str) -> int | None:
        if module not in P1_CHECKS:
            raise ValueError(f"{module} is not a check of P1")
        return self._python(module, "--check")

    def changes(self, record: str) -> int | None:
        return self._python("tools.experiment_freeze", "--changes", record)

    def _python(self, module: str, *arguments: str) -> int | None:
        try:
            done = subprocess.run(
                [sys.executable, "-m", module, *arguments],
                cwd=self.root,
                capture_output=True,
                timeout=CHECK_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return done.returncode

    def tracking_main(self) -> str | None:
        """The commit of the local tracking branch of the remote main. No fetch."""
        done = self._git(
            "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main^{commit}"
        )
        if done is None or done.returncode != 0:
            return None
        return done.stdout.decode("ascii", "replace").strip()

    def delivery_paths_equal(self, desired: str) -> bool | None:
        """Whether the chart, the desired-state tree, and the controller manifests of
        the checkout equal those of ``desired``."""
        manifests = PurePosixPath(self.plan.controller_manifest).parent.as_posix()
        done = self._git(
            "diff",
            "--quiet",
            desired,
            "HEAD",
            "--",
            self.plan.chart,
            "gitops",
            manifests,
        )
        if done is None or done.returncode not in (0, 1):
            return None
        return done.returncode == 0

    def desired_state_digests(
        self, desired: str, directory: str
    ) -> dict[str, str | None]:
        """The digest of each file of ``directory`` at ``desired``, read from Git."""
        listed = self._git("ls-tree", "--name-only", f"{desired}:{directory}")
        if listed is None or listed.returncode != 0:
            return {}
        digests: dict[str, str | None] = {}
        for name in listed.stdout.decode("utf-8", "replace").splitlines():
            blob = self._git("cat-file", "blob", f"{desired}:{directory}/{name}")
            digests[name] = (
                None
                if blob is None or blob.returncode != 0
                else content_digest(blob.stdout)
            )
        return digests


def taken_identifiers(root: Path) -> list[str]:
    """Every run identifier that a work directory or a committed run directory holds."""
    names: set[str] = set()
    for directory in (root / RUNS_WORK, root / core.DIRECTORY / "runs"):
        if directory.is_dir():
            names.update(entry.name for entry in directory.iterdir())
    return sorted(names)


def runs_under(root: Path, record: str) -> int:
    """How many runs started under ``record``: a work directory or a committed run."""
    runs: set[str] = set()
    for path in (root / RUNS_WORK).glob(f"*/{CONTROL_FILE}"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            runs.add(path.parent.name)
            continue
        if (
            not isinstance(document, dict)
            or core._pointer(document, "/freezeRecord/path") == record
        ):
            runs.add(path.parent.name)
    for path in (root / core.DIRECTORY / "runs").glob("*/run.v1alpha1.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            runs.add(path.parent.name)
            continue
        if core._pointer(document, "/metadata/spec/freezeRecord") == record:
            runs.add(path.parent.name)
    return len(runs)


# --------------------------------------------------------------------------
# The live port
# --------------------------------------------------------------------------


@dataclass
class _Process:
    """A collector that the driver started, with its output in a file."""

    process: subprocess.Popen[bytes]
    log: Path

    def alive(self) -> bool:
        return self.process.poll() is None

    def output(self) -> str:
        try:
            return self.log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def wait(self, seconds: float) -> int | None:
        try:
            return self.process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            return None

    def stop(self) -> None:
        if not self.alive():
            return
        if sys.platform == "win32":
            # terminate() ends the collector bash alone on Windows. Its kubectl and
            # sleep children would survive it, so the whole tree is ended.
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(self.process.pid)],
                capture_output=True,
                timeout=60,
                check=False,
            )
        else:
            self.process.terminate()
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill()


@dataclass
class LivePort:
    """The port of a run: the checkout, and each cluster command as one verb of the driver."""

    root: Path
    plan: Plan
    driver: Path
    bash: str
    work: Path
    repository: LocalRepository = field(init=False)
    _commands: list[str] = field(default_factory=list, init=False)
    _transcript: list[str] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.repository = LocalRepository(self.root, self.plan)

    # The checkout -------------------------------------------------------

    def head(self) -> str | None:
        return self.repository.head()

    def clean(self) -> bool | None:
        return self.repository.clean()

    def check(self, module: str) -> int | None:
        status = self.repository.check(module)
        self._log([sys.executable, "-m", module, "--check"], status, b"")
        return status

    def changes(self, record: str) -> int | None:
        status = self.repository.changes(record)
        self._log(
            [sys.executable, "-m", "tools.experiment_freeze", "--changes", record],
            status,
            b"",
        )
        return status

    def desired_revision(self) -> str | None:
        """P2 reads the remote main: ``git ls-remote origin refs/heads/main``."""
        done = self.repository._git("ls-remote", "origin", "refs/heads/main")
        self._log(
            ["git", "ls-remote", "origin", "refs/heads/main"],
            None if done is None else done.returncode,
            b"" if done is None else done.stdout,
        )
        if done is None or done.returncode != 0:
            return None
        fields = done.stdout.decode("ascii", "replace").split()
        return fields[0] if fields else None

    def delivery_paths_equal(self, desired: str) -> bool | None:
        return self.repository.delivery_paths_equal(desired)

    def desired_state_digests(
        self, desired: str, directory: str
    ) -> dict[str, str | None]:
        return self.repository.desired_state_digests(desired, directory)

    def taken_identifiers(self) -> list[str]:
        return taken_identifiers(self.root)

    def runs_under(self, record: str) -> int:
        return runs_under(self.root, record)

    # The cluster, through the driver -------------------------------------

    def _argv(self, phase: str, name: str, arguments: Sequence[str]) -> list[str]:
        return [self.bash, str(self.driver), phase, name, *arguments]

    def _verb(self, name: str, arguments: Sequence[str]) -> tuple[int | None, bytes]:
        argv = self._argv("verb", name, arguments)
        return self._command(argv, VERB_TIMEOUT_SECONDS)

    def _command(self, argv: list[str], timeout: float) -> tuple[int | None, bytes]:
        """Run one command with its output in files, and keep it in the transcript."""
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                process = subprocess.Popen(argv, cwd=self.root, stdout=out, stderr=err)
            except OSError:
                self._log(argv, None, b"")
                return None, b""
            try:
                status: int | None = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _Process(process, Path(os.devnull)).stop()
                status = None
            out.seek(0)
            err.seek(0)
            printed, problems = out.read(), err.read()
        self._log(argv, status, printed + problems)
        return status, printed

    def read(self, name: str, *arguments: str) -> str | None:
        status, output = self._verb(name, arguments)
        if status != 0:
            return None
        return _lf(output).decode("utf-8", "replace")

    def status(self, name: str, *arguments: str) -> int | None:
        return self._verb(name, arguments)[0]

    def act(self, name: str, *arguments: str) -> int:
        status = self._verb(name, arguments)[0]
        return 1 if status is None else status

    def caller_record(self, run_id: str) -> str | None:
        """The caller record that the runner script collected, or None."""
        path = self.root / RUNNER_RUN.format(run=run_id) / "caller.jsonl"
        try:
            return _lf(path.read_bytes()).decode("utf-8", "replace")
        except OSError:
            return None

    def start(self, name: str, *arguments: str) -> _Process:
        argv = self._argv("verb", name, arguments)
        log = self.work / f"{name}.log"
        handle: IO[bytes] = log.open("wb")
        process = subprocess.Popen(
            argv, cwd=self.root, stdout=handle, stderr=subprocess.STDOUT
        )
        handle.close()
        self._log(
            argv, None, f"started in the background, output in {log.name}\n".encode()
        )
        return _Process(process, log)

    # The host -------------------------------------------------------------

    def now(self) -> datetime:
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    # What a run keeps ------------------------------------------------------

    def _clean_text(self, text: str) -> str:
        """Text with the host path of the checkout replaced, LF line ends, and no
        trailing whitespace.

        The path is replaced in its Windows forms and, on a drive, in the form that
        Git Bash prints, ``/d/...``. The longest form is replaced first.
        """
        forms = {str(self.root), self.root.as_posix()}
        drive = self.root.drive
        if len(drive) == 2 and drive[1] == ":":
            forms.add(f"/{drive[0].lower()}{self.root.as_posix()[2:]}")
        for form in sorted(forms, key=len, reverse=True):
            text = text.replace(form, "<repository>")
        return "\n".join(line.rstrip() for line in text.replace("\r", "").split("\n"))

    def _log(self, argv: Sequence[str], status: int | None, output: bytes) -> None:
        command = self._clean_text(" ".join(str(part) for part in argv))
        self._commands.append(command)
        printed = self._clean_text(output.decode("utf-8", "replace")).rstrip("\n")
        self._transcript.append(
            f"$ {command}\n{printed}\n[exit {status if status is not None else 'none'}]"
            if printed
            else f"$ {command}\n[exit {status if status is not None else 'none'}]"
        )
        if self.work.is_dir():
            self._flush()

    def _flush(self) -> None:
        (self.work / "commands.txt").write_bytes(
            ("\n".join(self._commands) + "\n").encode("utf-8")
        )
        (self.work / "transcript.txt").write_bytes(
            ("\n".join(self._transcript) + "\n").encode("utf-8")
        )

    def keep(self, run_id: str, work: Path) -> list[str]:
        """Copy the streams, the caller record, its plan, and the capacity records into
        ``work/evidence``, with LF line ends."""
        evidence = work / "evidence"
        evidence.mkdir(exist_ok=True)
        sources: list[Path] = []
        for pattern in (TIMELINE_STREAMS, TELEMETRY_STREAMS):
            directory = self.root / pattern.format(run=run_id)
            sources.extend(sorted(directory.glob("*.jsonl")))
        runner = self.root / RUNNER_RUN.format(run=run_id)
        sources.extend(
            path
            for path in (
                runner / "caller.jsonl",
                runner / "caller.refused.jsonl",
                runner / "plan.json",
            )
            if path.is_file()
        )
        kept = []
        for source in sources:
            (evidence / source.name).write_bytes(_lf(source.read_bytes()))
            kept.append(f"evidence/{source.name}")
        for reading in ("before-install", "before-apply"):
            record = self.root / CAPACITY_RECORD.format(name=f"{run_id}-{reading}")
            if record.is_file():
                target = evidence / f"capacity-{reading}.json"
                target.write_bytes(_lf(record.read_bytes()))
                kept.append(f"evidence/{target.name}")
        self._flush()
        return kept


@dataclass
class LiveFault:
    """The fault of a run: one delete of one pod, through the fault phase of the driver."""

    root: Path
    driver: Path
    bash: str
    run_id: str
    port: LivePort

    def __post_init__(self) -> None:
        if core.RUN_ID.fullmatch(self.run_id) is None:
            raise ValueError("a fault is constructed for a run identifier e02a-N alone")

    def delete(self, pod: str) -> int:
        argv = [self.bash, str(self.driver), "fault", self.run_id, pod]
        status = self.port._command(argv, FAULT_TIMEOUT_SECONDS)[0]
        return 1 if status is None else status


# --------------------------------------------------------------------------
# The scenario port of a dry run
# --------------------------------------------------------------------------


#: What the log of a dry run states after each act and each start.
NOT_EXECUTED: Final = ": not executed in a dry run"


def _entry(kind: str, name: str, arguments: Sequence[str]) -> str:
    """One line of the log of a dry run: the kind, the verb, and its arguments."""
    return " ".join((kind, name, *arguments))


class ScenarioRefused(ValueError):
    """A scenario file is not usable."""


@dataclass
class _Quiet:
    """A collector of a dry run: it starts sampling at once and ends when waited for."""

    def alive(self) -> bool:
        return True

    def output(self) -> str:
        return "samples: dry run\n"

    def wait(self, seconds: float) -> int | None:
        return 0

    def stop(self) -> None:
        return None


@dataclass
class ScenarioPort:
    """The port of a dry run: each answer comes from a scenario, on a virtual clock.

    It executes no command. An act is recorded as not executed and answers the exit
    status that the scenario states for it, 0 when it states none. The repository
    reads come from the scenario when it states them, and from the checkout
    otherwise, without the network.
    """

    scenario: Mapping[str, Any]
    repository: LocalRepository | None
    clock: datetime = field(init=False)
    acted: dict[str, datetime] = field(default_factory=dict, init=False)
    log: list[str] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.scenario.get("schema") != SCENARIO_SCHEMA:
            raise ScenarioRefused(f"a scenario states the schema {SCENARIO_SCHEMA}")
        start = core.parse_instant(self.scenario.get("start"))
        if start is None:
            raise ScenarioRefused("a scenario states its start as a UTC instant")
        self.clock = start
        self.acted["start"] = start
        caller = self.scenario.get("caller")
        if caller is not None:
            every = caller.get("everyMs", 2000) if isinstance(caller, Mapping) else None
            delay = (
                caller.get("podStartsAfterSeconds", 5)
                if isinstance(caller, Mapping)
                else None
            )
            if not (
                type(every) is int and every >= 1 and type(delay) is int and delay >= 0
            ):
                raise ScenarioRefused(
                    "a scenario states the caller with everyMs of at least 1 and "
                    "podStartsAfterSeconds of at least 0, each an integer"
                )

    # The checkout -------------------------------------------------------

    def _stated(self, member: str) -> tuple[bool, Any]:
        """Whether the scenario states a repository member, and its value."""
        stated = self.scenario.get("repository", {})
        if isinstance(stated, Mapping) and member in stated:
            return True, stated[member]
        return False, None

    def _checkout(self, member: str) -> LocalRepository:
        if self.repository is None:
            raise ScenarioRefused(f"the scenario states no repository member {member}")
        return self.repository

    def head(self) -> str | None:
        stated, value = self._stated("head")
        if not stated:
            return self._checkout("head").head()
        return value if isinstance(value, str) else None

    def clean(self) -> bool | None:
        stated, value = self._stated("clean")
        if not stated:
            return self._checkout("clean").clean()
        return value if isinstance(value, bool) else None

    def check(self, module: str) -> int | None:
        stated, value = self._stated("checks")
        if not stated:
            return self._checkout("checks").check(module)
        status = value.get(module) if isinstance(value, Mapping) else None
        return status if isinstance(status, int) else None

    def changes(self, record: str) -> int | None:
        stated, value = self._stated("changes")
        if not stated:
            return self._checkout("changes").changes(record)
        return value if isinstance(value, int) else None

    def desired_revision(self) -> str | None:
        stated, value = self._stated("desiredRevision")
        if not stated:
            return self._checkout("desiredRevision").tracking_main()
        return value if isinstance(value, str) else None

    def delivery_paths_equal(self, desired: str) -> bool | None:
        stated, value = self._stated("deliveryPathsEqual")
        if not stated:
            return self._checkout("deliveryPathsEqual").delivery_paths_equal(desired)
        return value if isinstance(value, bool) else None

    def desired_state_digests(
        self, desired: str, directory: str
    ) -> dict[str, str | None]:
        stated, value = self._stated("desiredStateFiles")
        if not stated:
            return self._checkout("desiredStateFiles").desired_state_digests(
                desired, directory
            )
        return dict(value) if isinstance(value, Mapping) else {}

    def taken_identifiers(self) -> list[str]:
        return list(self.scenario.get("taken", []))

    def runs_under(self, record: str) -> int:
        return int(self.scenario.get("runsUnderRevision", 0))

    # The cluster ------------------------------------------------------------

    def _answer(self, name: str, arguments: Sequence[str]) -> Mapping[str, Any] | None:
        """The answer of the latest entry whose act happened, at least ``from``
        seconds before now."""
        reads = self.scenario.get("reads", {})
        entries = reads.get(name) if isinstance(reads, Mapping) else None
        if entries is None:
            return None
        if isinstance(entries, Mapping):
            entries = [entries]
        chosen = None
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            after = entry.get("after", "start")
            if after not in self.acted:
                continue
            if self.clock - self.acted[after] < timedelta(seconds=entry.get("from", 0)):
                continue
            argument = entry.get("argument")
            if argument is not None and argument not in arguments:
                continue
            chosen = entry
        return chosen

    def read(self, name: str, *arguments: str) -> str | None:
        self.log.append(_entry("read", name, arguments))
        reads = self.scenario.get("reads", {})
        stated = isinstance(reads, Mapping) and name in reads
        if name == "runner-log" and not stated:
            return self._caller_text(arguments[0])
        if name == "runner-pod" and not stated:
            return self._runner_pod()
        answer = self._answer(name, arguments)
        if answer is None or answer.get("exit", 0) != 0:
            return None
        if "json" in answer:
            return json.dumps(answer["json"])
        text = answer.get("text")
        return text if isinstance(text, str) else None

    def status(self, name: str, *arguments: str) -> int | None:
        self.log.append(_entry("status", name, arguments))
        answer = self._answer(name, arguments)
        if answer is None:
            return None
        status = answer.get("exit", 0)
        return status if isinstance(status, int) else None

    def act(self, name: str, *arguments: str) -> int:
        self.log.append(_entry("act", name, arguments) + NOT_EXECUTED)
        self.acted[name] = self.clock
        acts = self.scenario.get("acts", {})
        status = acts.get(name, 0) if isinstance(acts, Mapping) else 0
        return status if isinstance(status, int) else 1

    def start(self, name: str, *arguments: str) -> _Quiet:
        self.log.append(_entry("start", name, arguments) + NOT_EXECUTED)
        return _Quiet()

    # The caller of a dry run --------------------------------------------------

    def _runner_pod(self) -> str | None:
        caller = self.scenario.get("caller")
        if not isinstance(caller, Mapping) or "runner-start" not in self.acted:
            return None
        starts = self.acted["runner-start"] + timedelta(
            seconds=int(caller.get("podStartsAfterSeconds", 5))
        )
        if self.clock < starts:
            return json.dumps({"items": []})
        pod = {
            "metadata": {"name": "runner"},
            "status": {
                "phase": "Running",
                "startTime": starts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "containerStatuses": [{"restartCount": 0}],
            },
        }
        return json.dumps({"items": [pod]})

    def _caller_text(self, run_id: str) -> str | None:
        """The request lines that a runner would have written by now.

        A request finishes every ``everyMs`` from the start of the pod, and it fails
        inside each interval of ``failing``, in seconds after the pod start.
        """
        caller = self.scenario.get("caller")
        if not isinstance(caller, Mapping) or "runner-start" not in self.acted:
            return None
        starts = self.acted["runner-start"] + timedelta(
            seconds=int(caller.get("podStartsAfterSeconds", 5))
        )
        every = timedelta(milliseconds=int(caller.get("everyMs", 2000)))
        failing = [
            (timedelta(seconds=low), timedelta(seconds=high))
            for low, high in caller.get("failing", [])
        ]
        lines = [json.dumps({"record": "header", "runId": run_id})]
        finished = starts + every
        sequence = 1
        while finished <= self.clock:
            offset = finished - starts
            success = not any(low <= offset < high for low, high in failing)
            lines.append(
                json.dumps(
                    {
                        "record": "request",
                        "runId": run_id,
                        "sequence": sequence,
                        "finishedAt": core.format_instant(finished),
                        "success": success,
                    }
                )
            )
            finished += every
            sequence += 1
        return "\n".join(lines) + "\n"

    # The host ---------------------------------------------------------------

    def now(self) -> datetime:
        return self.clock

    def sleep(self, seconds: float) -> None:
        self.clock += timedelta(seconds=max(seconds, 0.001))

    def caller_record(self, run_id: str) -> str | None:
        reads = self.scenario.get("reads", {})
        if isinstance(reads, Mapping) and "caller-record" in reads:
            return self.read("caller-record", run_id)
        return self._caller_text(run_id)

    def keep(self, run_id: str, work: Path) -> list[str]:
        (work / "dry-run.txt").write_bytes(("\n".join(self.log) + "\n").encode("utf-8"))
        return ["dry-run.txt"]


def load_scenario(path: Path) -> dict[str, Any]:
    """A scenario file.

    Raises:
        ScenarioRefused: the file is absent, not JSON, or not a scenario.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ScenarioRefused(f"{path.name} is not a readable JSON file") from error
    if not isinstance(document, dict):
        raise ScenarioRefused(f"{path.name} is not an object")
    return document


def find_bash() -> str | None:
    """The bash of the driver: the one that started it, then the one on PATH.

    On Windows ``subprocess`` searches the system directory before PATH, where
    ``bash.exe`` starts another system. So the path is resolved here.
    """
    stated = os.environ.get("INFEROPS_E02A_BASH")
    if stated and Path(stated).is_file():
        return stated
    return shutil.which("bash")
