"""Q3, the stable caller characterization: the rules, the refusals, and G.

Every directory here is written by this suite under pytest's temporary
directory, beside a stand-in for the record of the qualification that the
current revision names, q1-2, and for
the Q3 freeze record. Each caller record is written by the runner's own loop
against scripted answers, with a clock that the suite advances. The suite gives
the tool one defect at a time and holds the rule that the defect breaks, its
category, and the result: REFUSED for a precondition, INCONCLUSIVE for a rule
of the measurement. It holds G to the nearest-rank p99 of the gaps between
successive successes, to the maximum gap with fewer than 100 successes, and to
no value when the result is not CHARACTERIZED. It also holds the tool to the
freeze record, the page, and the driver, and each committed characterization
to what its directory gives.
"""

from __future__ import annotations

import copy
import io
import itertools
import json
import math
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tools import caller_characterization as q3
from tools import experiment_bounds as q4
from tools.caller_characterization import __main__ as cli
from tools.environment_qualification import core as q1
from tools.experiment_freeze import core as freeze
from tools.reliability_runner import core as runner
from tools.reliability_runner import incluster
from tools.reliability_runner.core import CallerRecord

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs/environment/stable-caller-characterization.md"
DRIVER = ROOT / "docs/proof/experiments/v2-q3/procedure/q3-driver.txt"
FREEZE = ROOT / q3.FREEZE_RECORD

COMMIT = "1" * 39 + "2"
DESIRED = "3" * 39 + "4"
RELEASE_ID = "5" * 64
API_DIGEST = "sha256:" + "6" * 64
RUNTIME_DIGEST = "sha256:" + "7" * 64
RUNTIME_IMAGE = f"ghcr.io/ggml-org/llama.cpp@{RUNTIME_DIGEST}"
API_IMAGE = f"localhost/inferops-api@{API_DIGEST}"
NODE = "desktop-control-plane"
FREEZE_TEXT = '{"stand-in": "the Q3 freeze record"}\n'

#: The wall-clock instant at which each scripted caller run starts.
CALLER_START = datetime(2026, 10, 16, 10, 0, 0, tzinfo=UTC)

RULE_CATEGORIES = {
    "preparation-completed": "preparation",
    "working-tree-clean": "desired-state",
    "procedure-frozen": "desired-state",
    "desired-revision-known": "desired-state",
    "environment-qualified": "environment",
    "release-qualified": "release-identity",
    "topology-ready": "topology",
    "caller-run-completed": "caller",
    "caller-record-accepted": "caller",
    "five-minutes-run": "measurement",
    "gaps-observed": "measurement",
    "stream-complete": "evidence",
    "topology-held": "topology",
    "readings-in-order": "evidence",
}

SUCCESS_BODY = {
    "choices": [{"finish_reason": "stop", "message": {"content": "x"}}],
    "usage": {"prompt_tokens": 30, "completion_tokens": 40},
    "x_inferops": {"adapterKind": "real", "modelRef": "qwen3-1-7b-q8-0"},
}


def _stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _host(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _uid(number: int) -> str:
    return f"{number:08x}-0000-4000-8000-{number:012x}"


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = value if isinstance(value, str) else json.dumps(value, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _labels(component: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/instance": "inferops",
        "app.kubernetes.io/component": component,
    }


def _capacity() -> dict[str, Any]:
    return {
        "schema": q3.core.CAPACITY_SCHEMA,
        "result": "ACCEPTED",
        "collection": {"releaseKey": q3.TARGET_RELEASE_KEY},
        "footprint": {"topology": {"apiReplicas": 2, "runtimeReplicas": 2}},
        "environment": {
            "provider": "docker-desktop",
            "kubernetesServerVersion": "v1.36.1",
            "containerEngine": {"cpus": 12, "memoryBytes": 10_429_960_192},
        },
        "nodes": [
            {
                "name": NODE,
                "kubeletVersion": "v1.36.1",
                "allocatable": {
                    "cpuMillis": 12_000,
                    "memoryBytes": 10_429_960_192,
                    "pods": 110,
                },
            }
        ],
    }


def _environment_sha(
    identity: Callable[[q1.Sources], dict[str, Any] | None] = (
        q1.stable_environment_identity
    ),
    capacity: dict[str, Any] | None = None,
) -> str:
    """The digest that the Q1 tool computes for the capacity record above: the
    stable identity of the current lineage, unless another identity is given."""
    absent = q1.Source("", problem="absent")
    sources = q1.Sources(
        header={},
        capacity=q1.Source("capacity", value=capacity or _capacity()),
        provenance=absent,
        reconciliation=absent,
        deployments=absent,
        endpoints=absent,
        model_cache=absent,
        plan=absent,
        caller_text=None,
        caller_refused=False,
        root=ROOT,
        directory=ROOT,
    )
    environment = identity(sources)
    assert environment is not None
    return q1.environment_digest(environment)


def _qualification(
    qualification_id: str = q3.QUALIFICATION_ID,
    freeze_record: str = q3.QUALIFICATION_FREEZE_RECORD,
    environment_sha: str | None = None,
) -> dict[str, Any]:
    """A stand-in for the record of the qualification of the current lineage."""
    return {
        "schema": q3.core.QUALIFICATION_SCHEMA,
        "result": "QUALIFIED",
        "collection": {
            "qualificationId": qualification_id,
            "freezeRecord": freeze_record,
        },
        "environmentSha256": environment_sha or _environment_sha(),
        "identities": {
            "releaseId": RELEASE_ID,
            "apiImageDigest": API_DIGEST,
            "runtimeImage": {"digest": RUNTIME_DIGEST, "reference": RUNTIME_IMAGE},
        },
    }


def _deployment(component: str, image: str, generation: int = 3) -> dict[str, Any]:
    container = "api" if component == "platform-api" else "runtime"
    return {
        "kind": "Deployment",
        "metadata": {
            "name": f"inferops-{component}",
            "generation": generation,
            "labels": _labels(component),
        },
        "spec": {
            "replicas": 2,
            "template": {"spec": {"containers": [{"name": container, "image": image}]}},
        },
        "status": {
            "observedGeneration": generation,
            "replicas": 2,
            "readyReplicas": 2,
            "availableReplicas": 2,
            "updatedReplicas": 2,
        },
    }


def _deployments() -> dict[str, Any]:
    return {
        "kind": "List",
        "items": [
            _deployment("platform-api", API_IMAGE),
            _deployment("serving-runtime", RUNTIME_IMAGE),
        ],
    }


def _pod(number: int, component: str, *, ready: bool = True) -> dict[str, Any]:
    created = CALLER_START - timedelta(minutes=10)
    container = "api" if component == "platform-api" else "runtime"
    status: dict[str, Any] = {
        "conditions": [
            {
                "type": "PodScheduled",
                "status": "True",
                "lastTransitionTime": _stamp(created),
            },
            {
                "type": "Ready",
                "status": "True" if ready else "False",
                "lastTransitionTime": _stamp(created + timedelta(minutes=1)),
            },
        ],
        "containerStatuses": [{"name": container, "restartCount": 0}],
    }
    if component == "serving-runtime":
        status["initContainerStatuses"] = [{"name": "verify-model", "restartCount": 0}]
    return {
        "kind": "Pod",
        "metadata": {
            "name": f"inferops-{component}-p{number:04d}",
            "uid": _uid(number),
            "creationTimestamp": _stamp(created),
            "labels": _labels(component),
        },
        "status": status,
    }


def _pods() -> list[dict[str, Any]]:
    return [
        _pod(1, "platform-api"),
        _pod(2, "platform-api"),
        _pod(3, "serving-runtime"),
        _pod(4, "serving-runtime"),
    ]


def _event(kind: str, pod: dict[str, Any]) -> str:
    return json.dumps({"type": kind, "object": pod}, separators=(",", ":"))


def _watch(pods: list[dict[str, Any]]) -> str:
    """The pods that exist, then one status update of each that stays Ready."""
    events = [_event("ADDED", pod) for pod in pods]
    events.extend(_event("MODIFIED", pod) for pod in pods)
    return "\n".join(events) + "\n"


def caller(
    *,
    step: float = 3.0,
    answer: Callable[[int], tuple[int, object]] | None = None,
    stop_after: int | None = None,
    **changes: Any,
) -> tuple[str, str]:
    """A plan and the caller record that the runner's own loop writes for it.

    Each request advances the shared clock by ``step`` seconds, and the wall clock
    follows it, so a run of 360 s holds about 360 / ``step`` requests.
    """
    arguments: dict[str, Any] = {
        "experiment_id": q3.EXPERIMENT_ID,
        "run_id": "q3-1",
        "duration_seconds": q3.CALLER_DURATION_SECONDS,
        "request_ceiling": q3.CALLER_REQUEST_CEILING,
        "release_id": RELEASE_ID,
    }
    arguments.update(changes)
    plan = runner.build_plan(**arguments)
    text = runner.plan_text(plan)
    out = io.StringIO()
    lock = threading.Lock()
    now = [0.0]
    calls = [0]
    holder: list[incluster.Run] = []

    def clock() -> float:
        with lock:
            return now[0]

    def wall() -> datetime:
        with lock:
            return CALLER_START + timedelta(seconds=now[0])

    def transport(*_: object) -> tuple[int, object]:
        with lock:
            now[0] += step
            calls[0] += 1
            number = calls[0]
        if stop_after is not None and number >= stop_after:
            holder[0].stop()
        return answer(number) if answer is not None else (200, SUCCESS_BODY)

    run = incluster.Run(
        plan,
        out=out,
        runner_sha256=runner.runner_digest(),
        plan_sha256=runner.plan_digest(text),
        transport=transport,
        clock=clock,
        wall=wall,
        sleep=lambda _: None,
    )
    holder.append(run)
    run.execute()
    return text, out.getvalue()


#: One caller run of the default kind, written once: the runner's loop has two
#: threads, so two runs need not give the same lines.
_DEFAULT_CALLER: dict[str, tuple[str, str]] = {}


def _default_caller() -> tuple[str, str]:
    if "run" not in _DEFAULT_CALLER:
        _DEFAULT_CALLER["run"] = caller()
    return _DEFAULT_CALLER["run"]


def _header() -> dict[str, Any]:
    return {
        "schema": q3.COLLECTION_SCHEMA,
        "characterizationId": "q3-1",
        "provider": "docker-desktop",
        "releaseKey": q3.TARGET_RELEASE_KEY,
        "executingCommit": COMMIT,
        "upExecutingCommit": COMMIT,
        "desiredRevision": DESIRED,
        "workingTree": "clean",
        "desiredStateDiff": "none",
        "freezeRecord": q3.FREEZE_RECORD,
        "freezeRecordSha256": q3.lf_digest(FREEZE_TEXT.encode()),
        "freezeChanges": "none",
        "qualificationFreezeChanges": "none",
        "apiImageDigest": API_DIGEST,
        "targetRefusal": None,
        "upRefusal": None,
        "upStartedAt": "2026-10-16T09:30:00Z",
        "startedAt": "2026-10-16T09:58:00.000Z",
        "finishedAt": "2026-10-16T10:20:00.000Z",
    }


def _caller_run() -> dict[str, Any]:
    return {
        "schema": q3.CALLER_RUN_SCHEMA,
        "requestedAt": _host(CALLER_START - timedelta(seconds=20)),
        "startExit": 0,
        "jobState": "succeeded",
        "jobEndedAt": _host(CALLER_START + timedelta(seconds=400)),
        "collectExit": 0,
        "cleanupExit": 0,
        "watchStartedAt": _host(CALLER_START - timedelta(seconds=30)),
        "watchStoppedAt": _host(CALLER_START + timedelta(seconds=430)),
    }


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A checkout that holds the stand-in freeze record and the record of q1-2."""
    checkout = tmp_path / "checkout"
    _write(checkout / q3.FREEZE_RECORD, FREEZE_TEXT)
    _write(checkout / q3.QUALIFICATION_RECORD, _qualification())
    return checkout


def _directory(
    tmp_path: Path, calls: tuple[str, str] | None = None, name: str = "q3-1"
) -> Path:
    directory = tmp_path / name
    plan_text, caller_text = calls if calls is not None else _default_caller()
    _write(directory / "run.json", _header())
    _write(directory / "capacity/record.v1alpha1.json", _capacity())
    _write(
        directory / "provenance.json",
        [
            {
                "schema": q3.core.PROVENANCE_SCHEMA,
                "git": {"revision": DESIRED},
                "desiredState": {"key": q3.TARGET_RELEASE_KEY},
                "release": {"releaseId": RELEASE_ID},
            }
        ],
    )
    _write(directory / "deployments.json", _deployments())
    _write(directory / "before.pods.json", {"kind": "List", "items": _pods()})
    _write(directory / "watch.jsonl", _watch(_pods()))
    _write(directory / "caller-run.json", _caller_run())
    _write(directory / "plan.json", plan_text)
    _write(directory / "caller.jsonl", caller_text)
    _write(directory / "after.deployments.json", _deployments())
    _write(directory / "after.pods.json", {"kind": "List", "items": _pods()})
    return directory


def _record(directory: Path, root: Path) -> dict[str, Any]:
    return q3.build_record(directory, root)


def _state(record: dict[str, Any], rule: str) -> str:
    return next(item["state"] for item in record["findings"] if item["ruleId"] == rule)


def _accepted(calls: tuple[str, str]) -> CallerRecord:
    plan_text, caller_text = calls
    return runner.read_record(caller_text, plan=plan_text)


# --------------------------------------------------------------------------
# The record of a directory at its state
# --------------------------------------------------------------------------


def test_a_directory_with_every_source_at_its_state_is_characterized(
    tmp_path: Path, root: Path
) -> None:
    record = _record(_directory(tmp_path), root)
    assert record["result"] == q3.CHARACTERIZED, [
        item for item in record["findings"] if item["state"] != q3.HELD
    ]
    assert record["notHeld"] == {"categories": [], "rules": []}
    assert [item["ruleId"] for item in record["findings"]] == [
        rule.rule_id for rule in q3.RULES
    ]


def test_g_is_the_nearest_rank_p99_of_the_gaps_with_100_successes_or_more(
    tmp_path: Path, root: Path
) -> None:
    record = _record(_directory(tmp_path), root)
    accepted = _accepted(_default_caller())
    gaps = sorted(q3.success_gaps(accepted))
    successes = sum(1 for r in accepted.requests if r["success"])
    assert successes >= 100
    rank = -(-99 * len(gaps) // 100)
    assert record["bound"] == {
        "symbol": "G",
        "rule": "p99",
        "valueMs": gaps[rank - 1],
        "percentile": 99,
        "method": record["bound"]["method"],
        "minimumSuccessesForPercentile": 100,
        "percentileMeaningful": True,
        "successes": successes,
        "gaps": successes - 1,
    }
    assert "nearest-rank" in record["bound"]["method"]


def test_g_is_the_maximum_gap_with_fewer_than_100_successes(
    tmp_path: Path, root: Path
) -> None:
    calls = caller(step=4.0)
    accepted = _accepted(calls)
    successes = sum(1 for r in accepted.requests if r["success"])
    assert 2 <= successes < 100
    record = _record(_directory(tmp_path, calls), root)
    assert record["result"] == q3.CHARACTERIZED
    assert record["bound"]["rule"] == "maximum"
    assert record["bound"]["percentileMeaningful"] is False
    assert record["bound"]["valueMs"] == max(q3.success_gaps(accepted))


def test_a_gap_is_from_one_success_to_the_next_and_skips_a_failure() -> None:
    """The completion instants of the successes, in their order. A failure between
    two successes lengthens the gap, and the time before the first success is not
    a gap."""

    def line(sequence: int, seconds: float, success: bool) -> dict[str, Any]:
        return {
            "sequence": sequence,
            "success": success,
            "finishedAt": _host(CALLER_START + timedelta(seconds=seconds)),
        }

    record = CallerRecord(
        header={},
        requests=(
            line(1, 5.0, True),
            line(3, 9.5, False),
            line(2, 8.0, True),
            line(4, 14.25, True),
            line(5, 14.25, True),
        ),
        end={},
    )
    assert q3.success_gaps(record) == [3000, 6250, 0]


@pytest.mark.parametrize(
    ("values", "percentile", "expected"),
    [
        ([], 99, None),
        ([7], 99, 7),
        (list(range(1, 101)), 99, 99),
        (list(range(1, 101)), 50, 50),
        (list(range(1, 201)), 99, 198),
        (list(range(1, 102)), 99, 100),
        ([5, 1, 3], 50, 3),
    ],
)
def test_the_nearest_rank_percentile(
    values: list[int], percentile: int, expected: int | None
) -> None:
    assert q3.nearest_rank(values, percentile) == expected


def test_the_record_states_what_the_caller_saw(tmp_path: Path, root: Path) -> None:
    record = _record(_directory(tmp_path), root)
    accepted = _accepted(_default_caller())
    caller_part = record["caller"]
    assert caller_part["requests"] == len(accepted.requests)
    assert caller_part["successes"] == caller_part["outcomes"]["success"]
    assert caller_part["canonicalErrors"] == {}
    assert caller_part["endState"] == "duration"
    assert caller_part["elapsedMs"] >= 360_000
    latencies = [r["latencyMs"] for r in accepted.requests if r["success"]]
    assert caller_part["successLatency"]["maxMs"] == max(latencies)
    assert caller_part["successLatency"]["p50Ms"] == q3.nearest_rank(latencies, 50)
    assert caller_part["gaps"]["count"] == caller_part["successes"] - 1


def test_a_canonical_error_is_counted_and_does_not_refuse(
    tmp_path: Path, root: Path
) -> None:
    """A request that fails while the topology holds is a caller result."""

    def answer(number: int) -> tuple[int, object]:
        if number % 25 == 0:
            return 503, {"code": "adapter-unavailable"}
        return 200, SUCCESS_BODY

    record = _record(_directory(tmp_path, caller(answer=answer)), root)
    assert record["result"] == q3.CHARACTERIZED
    assert record["caller"]["outcomes"]["http-error"] >= 1
    assert record["caller"]["canonicalErrors"] == {
        "adapter-unavailable": record["caller"]["outcomes"]["http-error"]
    }


def test_the_record_states_the_identities_of_q1_1_and_of_the_caller(
    tmp_path: Path, root: Path
) -> None:
    identities = _record(_directory(tmp_path), root)["identities"]
    assert identities["releaseId"] == RELEASE_ID
    assert identities["apiImageDigest"] == API_DIGEST
    assert identities["runtimeImage"] == RUNTIME_IMAGE
    assert identities["environmentSha256"] == _environment_sha()
    assert identities["callerProfile"]["profileId"] == "RP-1"
    assert identities["runnerSha256"] == runner.runner_digest()
    assert identities["planSha256"] == runner.plan_digest(_default_caller()[0])
    assert identities["freezeRecord"] == {
        "path": q3.FREEZE_RECORD,
        "contentSha256": q3.lf_digest(FREEZE_TEXT.encode()),
    }


def test_the_record_lists_each_file_it_read_by_its_digest(
    tmp_path: Path, root: Path
) -> None:
    directory = _directory(tmp_path)
    files = _record(directory, root)["files"]
    assert [item["name"] for item in files] == [
        name for name in q3.SOURCE_FILES if name != q3.CALLER_REFUSED_FILE
    ]
    for item in files:
        assert item["sha256"] == q3.lf_digest((directory / item["name"]).read_bytes())


def test_the_record_states_the_target_and_no_rate(tmp_path: Path, root: Path) -> None:
    record = _record(_directory(tmp_path), root)
    assert record["target"] == {
        "releaseKey": q3.TARGET_RELEASE_KEY,
        "apiReplicas": 2,
        "runtimeReplicas": 2,
        "provider": "docker-desktop",
        "callerDurationSeconds": 360,
        "callerRequestCeiling": 2000,
        "minimumRunMs": 300_000,
    }

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {k for item in value.values() for k in keys(item)}
        if isinstance(value, list):
            return {k for item in value for k in keys(item)}
        return set()

    for word in ("rate", "throughput", "persecond", "average"):
        assert not [key for key in keys(record) if word in key.lower()], word


# --------------------------------------------------------------------------
# One defect refuses one rule
# --------------------------------------------------------------------------


def _edit(
    name: str, change: Callable[[Any], Any | None]
) -> Callable[[Path, Path], None]:
    """Edit one JSON file of the directory. A change that returns a value replaces it."""

    def apply(directory: Path, root: Path) -> None:
        path = directory / name
        value = _read(path)
        replaced = change(value)
        _write(path, value if replaced is None else replaced)

    return apply


def _header_set(**members: Any) -> Callable[[Path, Path], None]:
    return _edit("run.json", lambda header: header.update(members))


def _run_set(**members: Any) -> Callable[[Path, Path], None]:
    return _edit("caller-run.json", lambda run: run.update(members))


def _events(
    change: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> Callable[[Path, Path], None]:
    """Edit the watch stream, event by event."""

    def apply(directory: Path, root: Path) -> None:
        path = directory / "watch.jsonl"
        events = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        _write(path, "\n".join(json.dumps(event) for event in change(events)) + "\n")

    return apply


def _qualification_set(
    change: Callable[[dict[str, Any]], None],
) -> Callable[[Path, Path], None]:
    def apply(directory: Path, root: Path) -> None:
        path = root / q3.QUALIFICATION_RECORD
        value = _read(path)
        change(value)
        _write(path, value)

    return apply


def _remove(name: str) -> Callable[[Path, Path], None]:
    def apply(directory: Path, root: Path) -> None:
        target = directory / name
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    return apply


def _calls(**arguments: Any) -> Callable[[Path, Path], None]:
    """Write the plan and the record of another scripted caller run."""

    def apply(directory: Path, root: Path) -> None:
        plan_text, caller_text = caller(**arguments)
        _write(directory / "plan.json", plan_text)
        _write(directory / "caller.jsonl", caller_text)

    return apply


def _refused_record(directory: Path, root: Path) -> None:
    (directory / "caller.jsonl").rename(directory / "caller.refused.jsonl")


def _not_ready(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A runtime pod leaves Ready while the caller runs."""
    flap = copy.deepcopy(events[-1])
    for condition in flap["object"]["status"]["conditions"]:
        if condition["type"] == "Ready":
            condition["status"] = "False"
    return [*events, flap]


def _new_pod(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [*events, {"type": "ADDED", "object": _pod(9, "serving-runtime")}]


def _deleted_pod(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [*events, {"type": "DELETED", "object": copy.deepcopy(events[3]["object"])}]


def _one_failure_only(number: int) -> tuple[int, object]:
    return (
        (200, SUCCESS_BODY) if number == 1 else (503, {"code": "adapter-unavailable"})
    )


DEFECTS: dict[str, list[tuple[str, Callable[[Path, Path], None]]]] = {
    "preparation-completed": [
        ("up refused", _header_set(upRefusal="capacity")),
        ("target refused", _header_set(targetRefusal="provider-mismatch")),
        ("up at another commit", _header_set(upExecutingCommit="8" * 40)),
    ],
    "working-tree-clean": [("dirty tree", _header_set(workingTree="dirty"))],
    "procedure-frozen": [
        (
            "another freeze record",
            _header_set(
                freezeRecord="docs/proof/experiments/v2-q2/freeze-r2.v1alpha1.json"
            ),
        ),
        ("other content", _header_set(freezeRecordSha256="9" * 64)),
        ("a Q3 change", _header_set(freezeChanges="listed")),
        ("a Q1 change", _header_set(qualificationFreezeChanges="listed")),
    ],
    "desired-revision-known": [
        ("delivery paths differ", _header_set(desiredStateDiff="differs")),
    ],
    "environment-qualified": [
        (
            "the qualification refused",
            _qualification_set(lambda r: r.update(result="REFUSED")),
        ),
        (
            "a qualification of revision 1 of the Q1 freeze record",
            _qualification_set(
                lambda r: r["collection"].update(
                    freezeRecord="docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json"
                )
            ),
        ),
        (
            "another node",
            _edit(
                "capacity/record.v1alpha1.json",
                lambda r: r["nodes"][0]["allocatable"].update(cpuMillis=8000),
            ),
        ),
        (
            "one runtime replica",
            _edit(
                "capacity/record.v1alpha1.json",
                lambda r: r["footprint"]["topology"].update(runtimeReplicas=1),
            ),
        ),
    ],
    "release-qualified": [
        (
            "another release",
            _edit(
                "provenance.json", lambda r: r[0]["release"].update(releaseId="a" * 64)
            ),
        ),
        (
            "another declared API image",
            _header_set(apiImageDigest="sha256:" + "c" * 64),
        ),
        (
            "another runtime image",
            _edit(
                "deployments.json",
                lambda r: r["items"][1]["spec"]["template"]["spec"]["containers"][
                    0
                ].update(image="ghcr.io/x/y@sha256:" + "d" * 64),
            ),
        ),
    ],
    "topology-ready": [
        (
            "one Ready API replica",
            _edit(
                "deployments.json",
                lambda r: r["items"][0]["status"].update(readyReplicas=1),
            ),
        ),
        (
            "a pod that is not Ready",
            _edit(
                "before.pods.json",
                lambda r: r["items"][2]["status"]["conditions"][1].update(
                    status="False"
                ),
            ),
        ),
        (
            "a third runtime pod",
            _edit(
                "before.pods.json",
                lambda r: r["items"].append(_pod(9, "serving-runtime")),
            ),
        ),
    ],
    "caller-run-completed": [
        ("the Job failed", _run_set(jobState="failed")),
        ("not collected", _run_set(collectExit=5)),
        ("not cleaned up", _run_set(cleanupExit=1)),
    ],
    "caller-record-accepted": [
        ("kept as refused", _refused_record),
        ("another experiment", _calls(experiment_id="v2-q1-environment-qualification")),
        ("another release declared", _calls(release_id="e" * 64)),
        ("another ceiling", _calls(request_ceiling=1000)),
        (
            "a plan of another run",
            lambda d, r: _write(d / "plan.json", caller(run_id="q3-9")[0]),
        ),
    ],
    "five-minutes-run": [("a stop request", _calls(stop_after=40))],
    "gaps-observed": [("one success", _calls(answer=_one_failure_only))],
    "stream-complete": [
        (
            "an ERROR event",
            _events(lambda e: [*e, {"type": "ERROR", "object": e[0]["object"]}]),
        ),
        ("opens with another pod", _events(lambda e: e[1:])),
        (
            "started after the request",
            _run_set(watchStartedAt=_host(CALLER_START)),
        ),
        (
            "stopped before the Job ended",
            _run_set(watchStoppedAt=_host(CALLER_START + timedelta(seconds=390))),
        ),
    ],
    "topology-held": [
        ("a pod left Ready", _events(_not_ready)),
        ("a pod was added", _events(_new_pod)),
        ("a pod was deleted", _events(_deleted_pod)),
        (
            "a container restarted",
            _edit(
                "after.pods.json",
                lambda r: r["items"][3]["status"]["containerStatuses"][0].update(
                    restartCount=1
                ),
            ),
        ),
        (
            "a new generation after",
            _edit(
                "after.deployments.json",
                lambda r: r["items"].__setitem__(
                    1, _deployment("serving-runtime", RUNTIME_IMAGE, generation=4)
                ),
            ),
        ),
    ],
    "readings-in-order": [
        ("up after", _header_set(upStartedAt="2026-10-16T09:59:00Z")),
        (
            "requested before the characterization",
            _run_set(
                requestedAt="2026-10-16T09:50:00.000Z",
                watchStartedAt="2026-10-16T09:49:00.000Z",
            ),
        ),
        (
            "the Job ended after the characterization",
            _header_set(finishedAt=_host(CALLER_START + timedelta(seconds=300))),
        ),
    ],
}

#: The defects whose rule is not observed rather than not held: the source the
#: rule reads is absent.
NOT_OBSERVED_CASES: frozenset[tuple[str, str]] = frozenset()

#: The other rules that a defect also breaks, measured. Every other defect breaks
#: its own rule and no other, so a rule weakened to pass it is visible here.
ALSO_NOT_HELD: dict[tuple[str, str], set[str]] = {
    ("environment-qualified", "the qualification refused"): {"release-qualified"},
    ("release-qualified", "another release"): {"caller-record-accepted"},
    ("caller-record-accepted", "kept as refused"): {
        "five-minutes-run",
        "gaps-observed",
    },
    ("caller-record-accepted", "another ceiling"): set(),
    ("caller-record-accepted", "a plan of another run"): {
        "five-minutes-run",
        "gaps-observed",
    },
    ("topology-ready", "a third runtime pod"): {"stream-complete", "topology-held"},
    ("stream-complete", "opens with another pod"): set(),
}

CASES = [
    pytest.param(rule, label, apply, id=f"{rule}: {label}")
    for rule, defects in DEFECTS.items()
    for label, apply in defects
]


@pytest.mark.parametrize(("rule", "label", "apply"), CASES)
def test_one_defect_refuses_its_rule_with_its_category(
    tmp_path: Path,
    root: Path,
    rule: str,
    label: str,
    apply: Callable[[Path, Path], None],
) -> None:
    directory = _directory(tmp_path)
    apply(directory, root)
    record = _record(directory, root)
    expected_state = (
        q3.NOT_OBSERVED if (rule, label) in NOT_OBSERVED_CASES else q3.NOT_HELD
    )
    assert _state(record, rule) == expected_state, rule
    others = {
        item["ruleId"]
        for item in record["findings"]
        if item["state"] != q3.HELD and item["ruleId"] != rule
    }
    assert others == ALSO_NOT_HELD.get((rule, label), set())
    assert RULE_CATEGORIES[rule] in record["notHeld"]["categories"]
    expected = q3.REFUSED if rule in q3.PRECONDITION_RULES else q3.INCONCLUSIVE
    if rule not in q3.PRECONDITION_RULES:
        # A defect of the measurement leaves every precondition held.
        assert not set(record["notHeld"]["rules"]) & set(q3.PRECONDITION_RULES)
    assert record["result"] == expected
    assert record["bound"]["valueMs"] is None
    assert record["bound"]["rule"] is None


def test_each_rule_has_a_defect_in_this_suite() -> None:
    assert sorted(DEFECTS) == sorted(rule.rule_id for rule in q3.RULES)
    assert {rule.rule_id: rule.category for rule in q3.RULES} == RULE_CATEGORIES


def test_the_preconditions_are_the_rules_that_refuse() -> None:
    assert tuple(rule.rule_id for rule in q3.RULES[:7]) == q3.PRECONDITION_RULES


def test_an_absent_source_is_not_observed(tmp_path: Path, root: Path) -> None:
    for name, rule in (
        ("provenance.json", "release-qualified"),
        ("capacity", "environment-qualified"),
        ("before.pods.json", "topology-ready"),
        ("caller-run.json", "caller-run-completed"),
        ("caller.jsonl", "caller-record-accepted"),
        ("plan.json", "caller-record-accepted"),
        ("watch.jsonl", "stream-complete"),
        ("after.deployments.json", "topology-held"),
        ("after.pods.json", "topology-held"),
    ):
        directory = _directory(tmp_path / name.replace("/", "-"))
        _remove(name)(directory, root)
        assert _state(_record(directory, root), rule) == q3.NOT_OBSERVED, name


def test_a_directory_with_no_caller_is_refused_when_a_precondition_fails(
    tmp_path: Path, root: Path
) -> None:
    """The driver starts no caller after a refusal. The record is REFUSED, the
    rules of the measurement are not observed, and the record states no caller."""
    directory = _directory(tmp_path)
    for name in (
        "watch.jsonl",
        "caller-run.json",
        "plan.json",
        "caller.jsonl",
        "after.deployments.json",
        "after.pods.json",
    ):
        (directory / name).unlink()
    _header_set(workingTree="dirty")(directory, root)
    record = _record(directory, root)
    assert record["result"] == q3.REFUSED
    assert record["caller"] is None
    for rule in ("caller-run-completed", "five-minutes-run", "topology-held"):
        assert _state(record, rule) == q3.NOT_OBSERVED, rule


def test_a_malformed_member_refuses_and_does_not_raise(
    tmp_path: Path, root: Path
) -> None:
    for name, value in (
        ("after.pods.json", {"items": "none"}),
        ("before.pods.json", []),
        ("caller-run.json", {"schema": q3.CALLER_RUN_SCHEMA}),
        ("deployments.json", {"items": [1, 2]}),
        ("caller.jsonl", "not a record\n"),
        (
            "after.pods.json",
            {"items": [{"metadata": {"uid": ["a"]}, "status": {}}]},
        ),
    ):
        directory = _directory(tmp_path / name.replace("/", "-"))
        _write(directory / name, value)
        assert _record(directory, root)["result"] != q3.CHARACTERIZED, name
        shutil.rmtree(directory)


def test_a_header_with_another_member_is_not_a_collection(
    tmp_path: Path, root: Path
) -> None:
    for change in (
        lambda h: h.update(context="docker-desktop"),
        lambda h: h.pop("upStartedAt"),
        lambda h: h.update(characterizationId="q2-1"),
        lambda h: h.update(upRefusal="tired"),
    ):
        directory = _directory(tmp_path)
        _edit("run.json", change)(directory, root)
        with pytest.raises(q3.CollectionRefused):
            _record(directory, root)
        shutil.rmtree(directory)


def test_a_record_of_revision_1_is_built_under_revision_1(
    tmp_path: Path, root: Path
) -> None:
    """A record is built under the revision that its header names, so revision 2
    does not refuse, and does not reinterpret, a characterization of revision 1:
    it is held to q1-1, its Q1 freeze revision, and the exact identity."""
    lineage = q3.LINEAGES[q3.FREEZE_RECORD_R1]
    _write(root / q3.FREEZE_RECORD_R1, FREEZE_TEXT)
    _write(
        root / lineage.qualification_record,
        _qualification(
            "q1-1",
            lineage.qualification_freeze_record,
            _environment_sha(q1.environment_identity),
        ),
    )
    directory = _directory(tmp_path)
    _header_set(freezeRecord=q3.FREEZE_RECORD_R1)(directory, root)
    record = _record(directory, root)
    assert record["result"] == q3.CHARACTERIZED
    assert record["identities"]["qualification"]["qualificationId"] == "q1-1"
    assert record["identities"]["freezeRecord"]["path"] == q3.FREEZE_RECORD_R1
    assert record["environment"]["containerEngine"]["memoryBytes"] == 10_429_960_192
    _edit(
        "capacity/record.v1alpha1.json",
        lambda r: r["environment"]["containerEngine"].update(
            memoryBytes=10_429_972_480
        ),
    )(directory, root)
    record = _record(directory, root)
    assert _state(record, "environment-qualified") == q3.NOT_HELD
    assert record["result"] == q3.REFUSED


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_exits_0_5_and_6(
    tmp_path: Path,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    directory = _directory(tmp_path)
    original = q3.core.build_record
    monkeypatch.setattr(cli, "build_record", lambda d: original(d, root))
    monkeypatch.setattr(cli, "preconditions", lambda d: q3.core.preconditions(d, root))
    assert cli.main([str(directory)]) == 0
    assert json.loads(capsys.readouterr().out)["result"] == q3.CHARACTERIZED
    assert cli.main(["--preconditions", str(directory)]) == 0
    assert capsys.readouterr().out.count("held ") == len(q3.PRECONDITION_RULES)
    _run_set(cleanupExit=1)(directory, root)
    assert cli.main([str(directory)]) == 6
    assert cli.main(["--preconditions", str(directory)]) == 0
    _header_set(workingTree="dirty")(directory, root)
    assert cli.main([str(directory)]) == 5
    assert cli.main(["--preconditions", str(directory)]) == 5
    capsys.readouterr()
    assert cli.main([str(tmp_path / "absent")]) == 1


def test_the_command_has_no_option_for_the_target() -> None:
    text = (ROOT / "tools/caller_characterization/__main__.py").read_text(
        encoding="utf-8"
    )
    options = sorted(set(re.findall(r'"(--[a-z-]+)"', text)))
    assert options == ["--check", "--preconditions"]


def test_the_command_runs_as_a_module_and_refuses_usage(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.caller_characterization"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    result = subprocess.run(
        [sys.executable, "-m", "tools.caller_characterization", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "not-a-collection" in result.stderr


def test_check_compares_each_committed_record_with_its_directory(
    tmp_path: Path, root: Path
) -> None:
    directory = root / "docs/proof/experiments/v2-q3/runs/q3-1"
    shutil.copytree(_directory(tmp_path), directory)
    _write(directory / "record.v1alpha1.json", q3.record_text(_record(directory, root)))
    assert q3.check_committed(root) == []
    _run_set(cleanupExit=1)(directory, root)
    assert q3.check_committed(root) == [
        "docs/proof/experiments/v2-q3/runs/q3-1: record.v1alpha1.json is not what the directory gives"
    ]
    (directory / "record.v1alpha1.json").unlink()
    assert q3.check_committed(root) == [
        "docs/proof/experiments/v2-q3/runs/q3-1: no record.v1alpha1.json"
    ]


def test_each_committed_characterization_is_what_its_directory_gives() -> None:
    assert q3.check_committed() == []


# --------------------------------------------------------------------------
# The freeze record, the page, and the driver
# --------------------------------------------------------------------------


def _freeze() -> dict[str, Any]:
    return json.loads(FREEZE.read_text(encoding="utf-8"))


def test_each_rule_is_one_acceptance_criterion_of_the_freeze_record() -> None:
    (entry,) = _freeze()["fields"]["acceptanceCriteria"]
    assert entry["value"] == [
        {"id": rule.criterion, "statement": rule.statement} for rule in q3.RULES
    ]
    assert [rule.criterion for rule in q3.RULES] == [
        f"Q3-AC{n}" for n in range(1, len(q3.RULES) + 1)
    ]


def test_the_freeze_record_freezes_the_rule_of_g_and_the_q4_formulas() -> None:
    """The rule of G and the four formulas are fixed before any characterization,
    and the record states no value of G or of a bound."""
    record = _freeze()
    assert record["metadata"]["experiment"] == q3.EXPERIMENT_ID
    assert record["metadata"]["revision"] == 2
    (bounds,) = record["fields"]["derivedNumericBounds"]
    value = bounds["value"]
    assert sorted(value) == ["G", "Q4"]
    assert "nearest-rank" in value["G"] and "fewer than 100" in value["G"]
    assert "states no value" in value["G"]
    assert value["Q4"]["formulas"] == dict(q4.FORMULAS)
    assert value["Q4"]["tool"] == "tools/experiment_bounds"
    (profile,) = record["fields"]["callerProfileRevision"]
    assert profile["value"]["profileId"] == "RP-1"
    assert profile["value"]["profileRevision"] == 1
    (topology,) = record["fields"]["topology"]
    assert (topology["value"]["apiReplicas"], topology["value"]["runtimeReplicas"]) == (
        2,
        2,
    )
    (fault,) = record["fields"]["fault"]
    assert fault["status"] == "not-applicable"


def test_the_freeze_record_holds_every_rule_of_the_freeze_check() -> None:
    assert freeze.check_record(_freeze(), q3.FREEZE_RECORD) == []


def test_the_freeze_record_pins_the_tools_the_drivers_and_the_q1_freeze() -> None:
    """Revision 2 pins revision 2 of the Q1 freeze record and no qualification
    record: q1-2 does not exist when it is registered."""
    pinned = {item["path"] for item in _freeze()["pinnedInputs"]}
    for path in (
        "tools/caller_characterization/core.py",
        "tools/caller_characterization/__main__.py",
        "tools/experiment_bounds/core.py",
        "tools/experiment_bounds/__main__.py",
        "tools/environment_qualification/core.py",
        "tools/reliability_runner/core.py",
        "tools/reliability_runner/incluster.py",
        "tools/runtime_startup/core.py",
        "docs/proof/experiments/v2-q3/procedure/q3-driver.txt",
        "docs/proof/experiments/v2-q1/procedure/q1-driver.txt",
        "deploy/serving/reliability/rp-1-profile.v1.json",
        "scripts/environment/reliability-runner.sh",
        q3.QUALIFICATION_FREEZE_RECORD,
        "charts/inferops-llm/values.yaml",
    ):
        assert path in pinned, path
    assert q3.QUALIFICATION_FREEZE_RECORD.endswith("/freeze-r2.v1alpha1.json")
    assert not [path for path in pinned if "/runs/" in path]


def test_the_scope_of_q3_holds_the_scope_of_q1() -> None:
    q1_record = json.loads(
        (ROOT / q3.QUALIFICATION_FREEZE_RECORD).read_text(encoding="utf-8")
    )
    scope = _freeze()["materialScope"]
    assert set(q1_record["materialScope"]["paths"]) <= set(scope["paths"])
    assert set(q1_record["materialScope"]["entryModules"]) <= set(scope["entryModules"])


def test_the_freeze_record_lists_no_changed_material_file() -> None:
    assert freeze.changed_inputs(_freeze()) == []


def test_the_page_restates_each_rule_and_each_category() -> None:
    text = PAGE.read_text(encoding="utf-8")
    for rule in q3.RULES:
        assert f"| `{rule.rule_id}` | {rule.criterion} | `{rule.category}` |" in text, (
            rule.rule_id
        )
    for category in q3.CATEGORIES:
        assert f"`{category}`" in text


def _driver() -> str:
    return DRIVER.read_text(encoding="utf-8")


def test_the_driver_names_the_freeze_records_the_experiment_and_each_file() -> None:
    text = _driver()
    assert f'FREEZE_RECORD="{q3.FREEZE_RECORD}"' in text
    assert f'Q1_FREEZE_RECORD="{q3.QUALIFICATION_FREEZE_RECORD}"' in text
    assert f'EXPERIMENT="{q3.EXPERIMENT_ID}"' in text
    assert f"CALLER_DURATION_SECONDS={q3.CALLER_DURATION_SECONDS}\n" in text
    assert f"CALLER_REQUEST_CEILING={q3.CALLER_REQUEST_CEILING}\n" in text
    for name in (
        q3.HEADER_FILE,
        q3.PROVENANCE_FILE,
        q3.DEPLOYMENTS_FILE,
        q3.BEFORE_PODS_FILE,
        q3.WATCH_FILE,
        q3.CALLER_RUN_FILE,
        q3.PLAN_FILE,
        q3.CALLER_FILE,
        q3.CALLER_REFUSED_FILE,
        q3.AFTER_DEPLOYMENTS_FILE,
        q3.AFTER_PODS_FILE,
        q3.RECORD_FILE,
    ):
        assert f'="{name}"' in text, name
    assert q3.COLLECTION_SCHEMA in text
    assert q3.CALLER_RUN_SCHEMA in text
    for state in q3.JOB_STATES:
        assert f'"{state}"' in text, state


def test_the_driver_is_valid_bash_with_lf_line_ends() -> None:
    data = DRIVER.read_bytes()
    assert b"\r\n" not in data
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not installed")
    result = subprocess.run([bash, "-n", str(DRIVER)], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr


def test_the_driver_runs_the_phases_of_the_q1_driver_without_a_change() -> None:
    text = _driver()
    assert 'Q1_DRIVER="docs/proof/experiments/v2-q1/procedure/q1-driver.txt"' in text
    assert 'run bash "${Q1_DRIVER}" up "${RUN}"' in text
    assert 'run bash "${Q1_DRIVER}" down "${RUN}"' in text
    assert text.count("${Q1_DRIVER}") == 3


def test_the_driver_deletes_no_pod_and_changes_no_value() -> None:
    """The driver deletes nothing of the release, scales nothing, patches nothing,
    restarts nothing, and sets no Helm value. The cleanup action of the runner
    script removes the objects of the caller run."""
    code = "\n".join(
        line for line in _driver().splitlines() if not line.lstrip().startswith("#")
    )
    for word in (
        " delete ",
        " scale ",
        " patch ",
        " edit ",
        " apply ",
        "rollout",
        "--set",
        "helm ",
    ):
        assert word not in code, word
    assert code.count('"${RUNNER_SCRIPT}" start') == 1
    assert code.count('"${RUNNER_SCRIPT}" cleanup') == 1


def test_the_driver_starts_the_caller_only_after_the_preconditions() -> None:
    text = _driver()
    asked = text.index("python -m tools.caller_characterization --preconditions")
    started = text.rindex("caller_run\n")
    assert asked < started
    assert "No caller is started." in text


def test_the_driver_starts_the_watch_before_the_caller_and_stops_it_after() -> None:
    text = _driver()
    body = text[text.index("caller_run() {") :]
    watch = body.index("--watch --output-watch-events")
    start = body.index('"${RUNNER_SCRIPT}" start')
    cleanup = body.index('"${RUNNER_SCRIPT}" cleanup')
    stop = body.index('kill "${watch}"')
    assert watch < start < cleanup < stop
    assert "trap stop_watch EXIT" in text


def test_the_driver_keeps_the_record_of_each_result() -> None:
    assert "0 | 5 | 6) tr -d" in _driver()


def test_the_driver_refuses_a_reused_identifier() -> None:
    text = _driver()
    assert "^q3-[1-9][0-9]?$" in text
    assert "One characterization identifier is one characterization." in text


def test_each_sentence_of_what_a_record_does_not_establish_says_so() -> None:
    for sentence in q3.DOES_NOT_ESTABLISH:
        assert sentence.startswith("A record does not establish "), sentence


def test_the_record_text_is_sorted_indented_json_with_one_final_lf(
    tmp_path: Path, root: Path
) -> None:
    text = q3.record_text(_record(_directory(tmp_path), root))
    assert text.endswith("}\n") and not text.endswith("\n\n")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_the_tool_imports_no_network_or_process_module() -> None:
    for name in ("core.py", "__main__.py", "__init__.py"):
        text = (ROOT / "tools/caller_characterization" / name).read_text(
            encoding="utf-8"
        )
        for module in ("subprocess", "socket", "urllib", "http", "requests"):
            assert not re.search(rf"^\s*(import|from)\s+{module}\b", text, re.MULTILINE)


def test_the_committed_characterization_q3_1_is_refused_on_the_environment() -> None:
    """V2-S6-002-PR2 ran q3-1 once under revision 1. Its record is what its
    directory gives. Only environment-qualified refused it: the memory of the engine
    and the node differed from q1-1 after the virtual machine booted again. No caller
    ran, so the record states no caller and no G, and no bound record names it."""
    directory = ROOT / "docs/proof/experiments/v2-q3/runs/q3-1"
    assert directory in q3.committed_runs()
    record = json.loads((directory / q3.RECORD_FILE).read_text(encoding="utf-8"))
    assert record["result"] == q3.REFUSED
    states = {item["ruleId"]: item["state"] for item in record["findings"]}
    assert [rule for rule in q3.PRECONDITION_RULES if states[rule] != q3.HELD] == [
        "environment-qualified"
    ]
    assert {
        rule.rule_id: states[rule.rule_id]
        for rule in q3.RULES
        if rule.rule_id not in q3.PRECONDITION_RULES
    } == {
        rule.rule_id: q3.NOT_OBSERVED
        for rule in q3.RULES
        if rule.rule_id not in q3.PRECONDITION_RULES
    }
    assert record["caller"] is None
    assert record["bound"]["valueMs"] is None
    assert record["collection"]["freezeRecord"] == q3.FREEZE_RECORD_R1
    assert record["identities"]["qualification"]["qualificationId"] == "q1-1"
    environment = record["environment"]
    assert environment["containerEngine"]["memoryBytes"] == 10_429_972_480
    assert record["identities"]["environmentSha256"] == (
        "sha256:ac3a1022e86facb519bb0820b57d7a7fb32c0c6ea1011a59e88b8c1aa4efd087"
    )
    for name in ("watch.jsonl", "caller-run.json", "caller.jsonl", "plan.json"):
        assert not (directory / name).exists(), name
    assert not (directory / "capacity/pods.json").exists()
    (path,) = q4.committed_records()
    assert path.name == "bounds-r1.v1alpha1.json"
    bound = json.loads(path.read_text(encoding="utf-8"))
    assert bound["inputs"]["G"]["characterizationId"] == "q3-2"


def test_the_committed_characterization_q3_2_states_g_under_revision_2() -> None:
    """V2-S6-004-PR2 ran q3-2 once under revision 2, after q1-2 was QUALIFIED and
    q2-2 was CHARACTERIZED. Its record is what its directory gives, each rule is
    held, and G is the nearest-rank p99 of its gaps, recomputed here from the
    committed caller record. It is bound to q1-2 and to the stable identity."""
    runs = ROOT / "docs/proof/experiments/v2-q3/runs"
    directory = runs / "q3-2"
    assert q3.committed_runs() == [runs / "q3-1", directory]
    record = json.loads((directory / q3.RECORD_FILE).read_text(encoding="utf-8"))
    assert record["result"] == q3.CHARACTERIZED
    assert {item["state"] for item in record["findings"]} == {q3.HELD}
    assert record["collection"]["freezeRecord"] == q3.FREEZE_RECORD
    assert record["identities"]["qualification"]["qualificationId"] == "q1-2"
    assert record["identities"]["environmentSha256"] == (
        "sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c"
    )
    assert record["caller"]["outcomes"]["success"] == record["caller"]["requests"]
    assert record["caller"]["requests"] == 153
    finished = sorted(
        datetime.fromisoformat(line["finishedAt"].replace("Z", "+00:00"))
        for line in map(
            json.loads,
            (directory / "caller.jsonl").read_text(encoding="utf-8").splitlines(),
        )
        if line.get("outcome") == "success"
    )
    gaps = sorted(
        round((later - earlier).total_seconds() * 1000)
        for earlier, later in itertools.pairwise(finished)
    )
    assert len(gaps) == 152
    assert gaps[math.ceil(0.99 * len(gaps)) - 1] == 10_113
    assert record["bound"] == {
        **record["bound"],
        "rule": "p99",
        "percentileMeaningful": True,
        "successes": 153,
        "gaps": 152,
        "valueMs": 10_113,
    }
    assert not (directory / "capacity/pods.json").exists()
    assert q3.check_committed() == []


# --------------------------------------------------------------------------
# Revision 2: the stable environment identity of q1-2, and revision 1 kept
# --------------------------------------------------------------------------


def test_the_lineages_name_q1_1_for_revision_1_and_q1_2_for_revision_2() -> None:
    assert (
        q3.FREEZE_RECORDS
        == tuple(q3.LINEAGES)
        == (
            "docs/proof/experiments/v2-q3/freeze-r1.v1alpha1.json",
            "docs/proof/experiments/v2-q3/freeze-r2.v1alpha1.json",
        )
    )
    r1 = q3.LINEAGES[q3.FREEZE_RECORD_R1]
    r2 = q3.LINEAGES[q3.FREEZE_RECORD]
    assert (r1.qualification_id, r1.qualification_freeze_record) == (
        "q1-1",
        "docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json",
    )
    assert (r2.qualification_id, r2.qualification_freeze_record) == (
        "q1-2",
        "docs/proof/experiments/v2-q1/freeze-r2.v1alpha1.json",
    )
    assert r1.rules == q3.RULES_R1
    assert r2.rules == q3.RULES
    # Since V2-S6-004-PR2 the record of q1-2 is committed. The revision does not pin
    # it; each characterization states its digest.
    assert (ROOT / r2.qualification_record).is_file()


@pytest.mark.parametrize("memory", [10_429_960_192, 10_429_972_480, 10_429_956_096])
def test_another_memory_reading_holds_the_environment_under_revision_2(
    tmp_path: Path, root: Path, memory: int
) -> None:
    directory = _directory(tmp_path)

    def other_memory(record: dict[str, Any]) -> None:
        record["environment"]["containerEngine"]["memoryBytes"] = memory
        record["nodes"][0]["allocatable"]["memoryBytes"] = memory

    _edit("capacity/record.v1alpha1.json", other_memory)(directory, root)
    record = _record(directory, root)
    assert _state(record, "environment-qualified") == q3.HELD
    assert record["result"] == q3.CHARACTERIZED


def test_a_refused_gate_refuses_although_the_stable_identity_matches(
    tmp_path: Path, root: Path
) -> None:
    directory = _directory(tmp_path)

    def insufficient(record: dict[str, Any]) -> None:
        record["result"] = "REFUSED"
        record["refusal"] = {"categories": ["capacity"], "rules": ["memory-limits-fit"]}
        record["environment"]["containerEngine"]["memoryBytes"] = 8 * 2**30
        record["nodes"][0]["allocatable"]["memoryBytes"] = 8 * 2**30

    _edit("capacity/record.v1alpha1.json", insufficient)(directory, root)
    capacity = _read(directory / "capacity/record.v1alpha1.json")
    assert _environment_sha(capacity=capacity) == _environment_sha()
    record = _record(directory, root)
    assert _state(record, "environment-qualified") == q3.NOT_HELD
    assert record["result"] == q3.REFUSED
    assert record["bound"]["valueMs"] is None


def test_the_committed_readings_of_q1_1_and_q3_1_have_one_stable_identity() -> None:
    """The observed drift under the decided semantics. The capacity readings of
    q1-1 and q3-1 differ by 12,288 bytes of memory and in nothing else that an
    identity reads: their exact identities differ, and their stable identities
    are one. q3-1 is still built under revision 1, and it stays REFUSED."""

    def identities(run: str) -> tuple[str, str]:
        capacity = _read(ROOT / run / "capacity/record.v1alpha1.json")
        return (
            _environment_sha(q1.environment_identity, capacity),
            _environment_sha(q1.stable_environment_identity, capacity),
        )

    q1_exact, q1_stable = identities("docs/proof/experiments/v2-q1/runs/q1-1")
    q3_exact, q3_stable = identities("docs/proof/experiments/v2-q3/runs/q3-1")
    assert q1_exact == (
        "sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461"
    )
    assert q3_exact == (
        "sha256:ac3a1022e86facb519bb0820b57d7a7fb32c0c6ea1011a59e88b8c1aa4efd087"
    )
    assert q1_stable == q3_stable
    record = _read(ROOT / "docs/proof/experiments/v2-q3/runs/q3-1/record.v1alpha1.json")
    assert record["result"] == q3.REFUSED
    assert q3.check_committed() == []


def test_revision_2_supersedes_revision_1_and_keeps_g_and_the_q4_formulas() -> None:
    r1 = json.loads((ROOT / q3.FREEZE_RECORD_R1).read_text(encoding="utf-8"))
    r2 = _freeze()
    assert r2["metadata"]["revision"] == 2
    assert r2["metadata"]["registeredBy"] == "V2-S6-004-PR1"
    assert r2["metadata"]["supersedes"] == {
        "path": q3.FREEZE_RECORD_R1,
        "contentSha256": freeze.content_digest(
            (ROOT / q3.FREEZE_RECORD_R1).read_bytes()
        ),
    }
    (before,) = r1["fields"]["acceptanceCriteria"]
    (after,) = r2["fields"]["acceptanceCriteria"]
    changed = [
        old["id"]
        for old, new in zip(before["value"], after["value"], strict=True)
        if old != new
    ]
    assert changed == ["Q3-AC5", "Q3-AC6"]
    assert "q1-1" not in json.dumps(after["value"])
    for name in ("healthy", "measurement", "derivation", "bounds"):
        assert r2["definition"][name] == r1["definition"][name]
    (old_bounds,) = r1["fields"]["derivedNumericBounds"]
    (new_bounds,) = r2["fields"]["derivedNumericBounds"]
    assert new_bounds["value"]["G"] == old_bounds["value"]["G"]
    assert (
        new_bounds["value"]["Q4"]["formulas"] == old_bounds["value"]["Q4"]["formulas"]
    )
    assert "freeze-r3.v1alpha1.json" in new_bounds["value"]["Q4"]["inputs"]
    material = {item["path"]: item["material"] for item in r2["inputChanges"]}
    assert material["tools/caller_characterization/core.py"] is True
    assert material["tools/experiment_bounds/core.py"] is True
    assert material["tools/runtime_startup/core.py"] is False
