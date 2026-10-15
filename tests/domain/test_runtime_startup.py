"""Q2, the runtime startup characterization: the rules, the refusals, and S.

Every directory here is written by this suite under pytest's temporary
directory, beside a stand-in for the record of the qualification q1-1 and for
the Q2 freeze record. The suite gives the tool one defect at a time and holds
the rule that the defect breaks, its category, and the result: REFUSED for a
precondition, INCONCLUSIVE for a rule of the measurement. It holds S to the
maximum of the observations, and to no value when the result is not
CHARACTERIZED. It also holds the tool to the freeze record, the page, and the
driver, and the one committed characterization to what its directory gives,
when one is committed.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tools import runtime_startup as q2
from tools.environment_qualification import core as q1
from tools.experiment_freeze import core as freeze
from tools.runtime_startup import __main__ as cli

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs/environment/runtime-startup-characterization.md"
DRIVER = ROOT / "docs/proof/experiments/v2-q2/procedure/q2-driver.txt"
Q1_DRIVER = ROOT / "docs/proof/experiments/v2-q1/procedure/q1-driver.txt"
FREEZE = ROOT / q2.FREEZE_RECORD

COMMIT = "1" * 39 + "2"
DESIRED = "3" * 39 + "4"
RELEASE_ID = "5" * 64
API_DIGEST = "sha256:" + "6" * 64
RUNTIME_DIGEST = "sha256:" + "7" * 64
RUNTIME_IMAGE = f"ghcr.io/ggml-org/llama.cpp@{RUNTIME_DIGEST}"
API_IMAGE = f"localhost/inferops-api@{API_DIGEST}"
NODE = "desktop-control-plane"
FREEZE_TEXT = '{"stand-in": "the Q2 freeze record"}\n'

#: The start of each restart, and the two intervals of its replacements, in
#: seconds: from creation to Initialized, and from Initialized to Ready.
TIMING = {
    "r1": (datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC), ((20, 31), (19, 33))),
    "r2": (datetime(2026, 10, 15, 10, 10, 0, tzinfo=UTC), ((21, 40), (20, 30))),
    "r3": (datetime(2026, 10, 15, 10, 20, 0, tzinfo=UTC), ((22, 29), (20, 31))),
}

RULE_CATEGORIES = {
    "preparation-completed": "preparation",
    "working-tree-clean": "desired-state",
    "procedure-frozen": "desired-state",
    "desired-revision-known": "desired-state",
    "environment-qualified": "environment",
    "release-qualified": "release-identity",
    "topology-ready": "topology",
    "three-restarts": "measurement",
    "stable-before-each-restart": "topology",
    "stream-complete": "evidence",
    "two-replacements": "measurement",
    "one-at-a-time": "measurement",
    "ready-held": "readiness",
    "model-verified": "readiness",
    "ready-serves": "readiness",
    "readings-in-order": "evidence",
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


def _environment() -> dict[str, Any]:
    return {
        "provider": "docker-desktop",
        "kubernetesServerVersion": "v1.36.1",
        "containerEngine": {"cpus": 12, "memoryBytes": 10_429_960_192},
    }


def _capacity() -> dict[str, Any]:
    return {
        "schema": q2.core.CAPACITY_SCHEMA,
        "result": "ACCEPTED",
        "collection": {"releaseKey": q2.TARGET_RELEASE_KEY},
        "footprint": {"topology": {"apiReplicas": 2, "runtimeReplicas": 2}},
        "environment": _environment(),
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


def _environment_sha() -> str:
    """The digest that the Q1 tool computes for the capacity record above."""
    sources = q1.Sources(
        header={},
        capacity=q1.Source("capacity", value=_capacity()),
        provenance=q1.Source("", problem="absent"),
        reconciliation=q1.Source("", problem="absent"),
        deployments=q1.Source("", problem="absent"),
        endpoints=q1.Source("", problem="absent"),
        model_cache=q1.Source("", problem="absent"),
        plan=q1.Source("", problem="absent"),
        caller_text=None,
        caller_refused=False,
        root=ROOT,
        directory=ROOT,
    )
    environment = q1.environment_identity(sources)
    assert environment is not None
    return q1.environment_digest(environment)


def _qualification() -> dict[str, Any]:
    return {
        "schema": q2.core.QUALIFICATION_SCHEMA,
        "result": "QUALIFIED",
        "collection": {"qualificationId": "q1-1"},
        "environmentSha256": _environment_sha(),
        "identities": {
            "releaseId": RELEASE_ID,
            "apiImageDigest": API_DIGEST,
            "runtimeImage": {"digest": RUNTIME_DIGEST, "reference": RUNTIME_IMAGE},
        },
    }


def _deployment(component: str, replicas: int = 2, image: str = "") -> dict[str, Any]:
    container = "api" if component == "platform-api" else "runtime"
    return {
        "kind": "Deployment",
        "metadata": {
            "name": f"inferops-{component}",
            "generation": 3,
            "labels": _labels(component),
        },
        "spec": {
            "replicas": replicas,
            "template": {"spec": {"containers": [{"name": container, "image": image}]}},
        },
        "status": {
            "observedGeneration": 3,
            "replicas": replicas,
            "readyReplicas": replicas,
            "availableReplicas": replicas,
            "updatedReplicas": replicas,
        },
    }


def _pod(
    number: int,
    created: datetime,
    *,
    initialized: datetime | None = None,
    ready: datetime | None = None,
    deleting: bool = False,
) -> dict[str, Any]:
    conditions = [
        {
            "type": "PodScheduled",
            "status": "True",
            "lastTransitionTime": _stamp(created),
        }
    ]
    if initialized is not None:
        conditions.append(
            {
                "type": "Initialized",
                "status": "True",
                "lastTransitionTime": _stamp(initialized),
            }
        )
    conditions.append(
        {
            "type": "Ready",
            "status": "True" if ready is not None else "False",
            "lastTransitionTime": _stamp(ready or created),
        }
    )
    metadata: dict[str, Any] = {
        "name": f"inferops-inferops-llm-runtime-abc12-p{number:04d}",
        "uid": _uid(number),
        "creationTimestamp": _stamp(created),
        "labels": _labels("serving-runtime"),
    }
    if deleting:
        metadata["deletionTimestamp"] = _stamp(created + timedelta(hours=1))
    running = (
        {"running": {"startedAt": _stamp(initialized)}}
        if initialized
        else {"waiting": {}}
    )
    return {
        "kind": "Pod",
        "metadata": metadata,
        "spec": {"containers": [{"name": "runtime", "image": RUNTIME_IMAGE}]},
        "status": {
            "conditions": conditions,
            "initContainerStatuses": [
                {
                    "name": "verify-model",
                    "restartCount": 0,
                    "state": {"terminated": {"exitCode": 0}}
                    if initialized
                    else {"running": {}},
                }
            ],
            "containerStatuses": [
                {
                    "name": "runtime",
                    "restartCount": 0,
                    "imageID": RUNTIME_IMAGE,
                    "state": running,
                }
            ],
        },
    }


def _event(kind: str, pod: dict[str, Any]) -> str:
    return json.dumps({"type": kind, "object": pod}, separators=(",", ":"))


def _restart(directory: Path, name: str, first: int) -> None:
    """Write one restart: two pods before, two replacements, one after the other."""
    start, intervals = TIMING[name]
    base = directory / "restarts" / name
    old = [
        _pod(
            number,
            start - timedelta(minutes=5),
            initialized=start - timedelta(minutes=4),
            ready=start - timedelta(minutes=3),
        )
        for number in (first, first + 1)
    ]
    events = [_event("ADDED", pod) for pod in old]
    created = start + timedelta(seconds=1)
    replacements = []
    for index, (to_initialized, to_ready) in enumerate(intervals):
        number = first + 2 + index
        doomed = copy.deepcopy(old[index])
        doomed["metadata"]["deletionTimestamp"] = _stamp(created)
        events.append(_event("MODIFIED", doomed))
        initialized = created + timedelta(seconds=to_initialized)
        ready = initialized + timedelta(seconds=to_ready)
        events.append(_event("ADDED", _pod(number, created)))
        events.append(
            _event("MODIFIED", _pod(number, created, initialized=initialized))
        )
        final = _pod(number, created, initialized=initialized, ready=ready)
        events.append(_event("MODIFIED", final))
        events.append(_event("DELETED", doomed))
        replacements.append(final)
        created = ready + timedelta(seconds=1)
    _write(base / "watch.jsonl", "\n".join(events) + "\n")
    _write(base / "before.pods.json", {"kind": "List", "items": old})
    _write(base / "after.pods.json", {"kind": "List", "items": replacements})
    _write(
        base / "before.deployment.json",
        _deployment("serving-runtime", image=RUNTIME_IMAGE),
    )
    requested = start
    rolled = created + timedelta(seconds=2)
    _write(
        base / "restart.json",
        {
            "schema": q2.RESTART_SCHEMA,
            "restart": name,
            "requestedAt": _host(requested),
            "restartExit": 0,
            "rolloutExit": 0,
            "rolledOutAt": _host(rolled),
            "watchStoppedAt": _host(rolled + timedelta(seconds=45)),
        },
    )
    for pod in replacements:
        _write(
            base / f"completion.{pod['metadata']['name']}.json",
            {
                "httpStatus": 200,
                "model": "qwen3-1.7b-q8_0",
                "finishReason": "stop",
                "promptTokens": 14,
                "completionTokens": 3,
            },
        )


def _header() -> dict[str, Any]:
    return {
        "schema": q2.COLLECTION_SCHEMA,
        "characterizationId": "q2-1",
        "provider": "docker-desktop",
        "releaseKey": q2.TARGET_RELEASE_KEY,
        "executingCommit": COMMIT,
        "upExecutingCommit": COMMIT,
        "desiredRevision": DESIRED,
        "workingTree": "clean",
        "desiredStateDiff": "none",
        "freezeRecord": q2.FREEZE_RECORD,
        "freezeRecordSha256": q2.lf_digest(FREEZE_TEXT.encode()),
        "freezeChanges": "none",
        "qualificationFreezeChanges": "none",
        "apiImageDigest": API_DIGEST,
        "targetRefusal": None,
        "upRefusal": None,
        "upStartedAt": "2026-10-15T09:30:00Z",
        "startedAt": "2026-10-15T09:59:00.000Z",
        "finishedAt": "2026-10-15T10:40:00.000Z",
    }


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A checkout that holds the stand-in freeze record and the record of q1-1."""
    checkout = tmp_path / "checkout"
    _write(checkout / q2.FREEZE_RECORD, FREEZE_TEXT)
    _write(checkout / q2.QUALIFICATION_RECORD, _qualification())
    return checkout


def _directory(tmp_path: Path) -> Path:
    directory = tmp_path / "q2-1"
    _write(directory / "run.json", _header())
    _write(directory / "capacity/record.v1alpha1.json", _capacity())
    _write(
        directory / "provenance.json",
        [
            {
                "schema": q2.core.PROVENANCE_SCHEMA,
                "git": {"revision": DESIRED},
                "desiredState": {"key": q2.TARGET_RELEASE_KEY},
                "release": {"releaseId": RELEASE_ID},
            }
        ],
    )
    _write(
        directory / "deployments.json",
        {
            "kind": "List",
            "items": [
                _deployment("platform-api", image=API_IMAGE),
                _deployment("serving-runtime", image=RUNTIME_IMAGE),
            ],
        },
    )
    for offset, name in enumerate(q2.RESTARTS):
        _restart(directory, name, 10 * (offset + 1))
    return directory


def _record(directory: Path, root: Path) -> dict[str, Any]:
    return q2.build_record(directory, root)


def _state(record: dict[str, Any], rule: str) -> str:
    return next(item["state"] for item in record["findings"] if item["ruleId"] == rule)


# --------------------------------------------------------------------------
# The record of a directory at its state
# --------------------------------------------------------------------------


def test_a_directory_with_every_source_at_its_state_is_characterized(
    tmp_path: Path, root: Path
) -> None:
    record = _record(_directory(tmp_path), root)
    assert record["result"] == q2.CHARACTERIZED, [
        item for item in record["findings"] if item["state"] != q2.HELD
    ]
    assert record["notHeld"] == {"categories": [], "rules": []}
    assert [item["ruleId"] for item in record["findings"]] == [
        rule.rule_id for rule in q2.RULES
    ]


def test_each_replacement_is_one_observation_and_s_is_their_maximum(
    tmp_path: Path, root: Path
) -> None:
    record = _record(_directory(tmp_path), root)
    rows = record["observations"]
    expected = [
        (name, order, (a + b) * 1000, a * 1000, b * 1000)
        for name in q2.RESTARTS
        for order, (a, b) in enumerate(TIMING[name][1], start=1)
    ]
    assert [
        (
            row["restart"],
            row["order"],
            row["startToReadyMs"],
            row["createdToInitializedMs"],
            row["initializedToReadyMs"],
        )
        for row in rows
    ] == expected
    assert record["bound"] == {
        "symbol": "S",
        "rule": "the maximum startToReadyMs of every observation",
        "valueMs": 61_000,
        "observations": 6,
        "firstObservedAt": {"restart": "r2", "pod": rows[2]["pod"]},
    }


def test_s_is_the_maximum_and_never_an_average(tmp_path: Path, root: Path) -> None:
    """The longest interval is S, however short the others are."""
    record = _record(_directory(tmp_path), root)
    values = [row["startToReadyMs"] for row in record["observations"]]
    assert record["bound"]["valueMs"] == max(values)
    assert record["bound"]["valueMs"] != sum(values) // len(values)

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {k for item in value.values() for k in keys(item)}
        if isinstance(value, list):
            return {k for item in value for k in keys(item)}
        return set()

    for word in ("mean", "average", "median", "percentile", "rate"):
        assert not [key for key in keys(record) if word in key.lower()], word


def test_the_record_states_the_measurement_and_its_resolution(
    tmp_path: Path, root: Path
) -> None:
    record = _record(_directory(tmp_path), root)
    assert record["measurement"]["resolutionMs"] == 1000
    assert record["target"] == {
        "releaseKey": q2.TARGET_RELEASE_KEY,
        "apiReplicas": 2,
        "runtimeReplicas": 2,
        "provider": "docker-desktop",
        "restarts": 3,
        "replacementsPerRestart": 2,
    }


def test_the_record_states_the_identities_of_q1_1(tmp_path: Path, root: Path) -> None:
    identities = _record(_directory(tmp_path), root)["identities"]
    assert identities["releaseId"] == RELEASE_ID
    assert identities["apiImageDigest"] == API_DIGEST
    assert identities["runtimeImage"] == RUNTIME_IMAGE
    assert identities["environmentSha256"] == _environment_sha()
    assert identities["qualification"]["path"] == q2.QUALIFICATION_RECORD
    assert identities["qualification"]["contentSha256"] == q2.lf_digest(
        (root / q2.QUALIFICATION_RECORD).read_bytes()
    )
    assert identities["freezeRecord"] == {
        "path": q2.FREEZE_RECORD,
        "contentSha256": q2.lf_digest(FREEZE_TEXT.encode()),
    }


def test_the_record_lists_each_file_it_read_by_its_digest(
    tmp_path: Path, root: Path
) -> None:
    directory = _directory(tmp_path)
    files = _record(directory, root)["files"]
    names = [item["name"] for item in files]
    assert names[:4] == [
        "run.json",
        "capacity/record.v1alpha1.json",
        "provenance.json",
        "deployments.json",
    ]
    assert len(names) == 4 + 3 * (len(q2.RESTART_FILES) + 2)
    for item in files:
        assert item["sha256"] == q2.lf_digest((directory / item["name"]).read_bytes())


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


def _lines(
    name: str, change: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
) -> Callable[[Path, Path], None]:
    """Edit the watch stream of one restart, event by event."""

    def apply(directory: Path, root: Path) -> None:
        path = directory / "restarts" / name / "watch.jsonl"
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
        path = root / q2.QUALIFICATION_RECORD
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


def _copy(source: str, target: str) -> Callable[[Path, Path], None]:
    def apply(directory: Path, root: Path) -> None:
        shutil.copytree(directory / source, directory / target)

    return apply


def _second_ready_flaps(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The first replacement leaves Ready after it was Ready."""
    replacement = _uid(12)
    ready = [e for e in events if e["object"]["metadata"]["uid"] == replacement][-1]
    flap = copy.deepcopy(ready)
    flap["type"] = "MODIFIED"
    for condition in flap["object"]["status"]["conditions"]:
        if condition["type"] == "Ready":
            condition["status"] = "False"
    return [*events, flap]


def _overlap(directory: Path, root: Path) -> None:
    """The second replacement of r1 is created while the first still loads."""
    path = directory / "restarts/r1/watch.jsonl"
    text = path.read_text(encoding="utf-8")
    start = TIMING["r1"][0]
    second = start + timedelta(seconds=1 + 20 + 31 + 1)
    _write(
        path,
        text.replace(
            f'"creationTimestamp":"{_stamp(second)}"',
            f'"creationTimestamp":"{_stamp(start + timedelta(seconds=30))}"',
        ),
    )


def _third_replacement(directory: Path, root: Path) -> None:
    path = directory / "restarts/r2/watch.jsonl"
    extra = _pod(99, TIMING["r2"][0] + timedelta(seconds=200))
    _write(path, path.read_text(encoding="utf-8") + _event("ADDED", extra) + "\n")


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
                freezeRecord="docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json"
            ),
        ),
        ("other content", _header_set(freezeRecordSha256="9" * 64)),
        ("a Q2 change", _header_set(freezeChanges="listed")),
        ("a Q1 change", _header_set(qualificationFreezeChanges="listed")),
    ],
    "desired-revision-known": [
        ("delivery paths differ", _header_set(desiredStateDiff="differs")),
    ],
    "environment-qualified": [
        ("q1-1 refused", _qualification_set(lambda r: r.update(result="REFUSED"))),
        (
            "another node",
            _edit(
                "capacity/record.v1alpha1.json",
                lambda r: r["nodes"][0]["allocatable"].update(cpuMillis=8000),
            ),
        ),
        (
            "a refused gate",
            _edit(
                "capacity/record.v1alpha1.json", lambda r: r.update(result="REFUSED")
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
            "another revision",
            _edit("provenance.json", lambda r: r[0]["git"].update(revision="b" * 40)),
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
            "an older generation",
            _edit(
                "deployments.json",
                lambda r: r["items"][1]["status"].update(observedGeneration=2),
            ),
        ),
    ],
    "three-restarts": [
        ("no r3", _remove("restarts/r3")),
        (
            "a fourth",
            _copy("restarts/r1", "restarts/r4"),
        ),
        (
            "a failed rollout",
            _edit(
                "restarts/r2/restart.json",
                lambda r: r.update(rolloutExit=1, rolledOutAt=None),
            ),
        ),
    ],
    "stable-before-each-restart": [
        (
            "one Ready replica",
            _edit(
                "restarts/r2/before.deployment.json",
                lambda r: r["status"].update(readyReplicas=1),
            ),
        ),
        (
            "a deleted pod",
            _edit(
                "restarts/r3/before.pods.json",
                lambda r: r["items"][0]["metadata"].update(
                    deletionTimestamp="2026-10-15T10:19:00Z"
                ),
            ),
        ),
    ],
    "stream-complete": [
        (
            "an ERROR event",
            _lines("r1", lambda e: [*e, {"type": "ERROR", "object": e[0]["object"]}]),
        ),
        ("opens with another pod", _lines("r2", lambda e: e[1:])),
        (
            "stopped before the rollout",
            _edit(
                "restarts/r3/restart.json",
                lambda r: r.update(watchStoppedAt="2026-10-15T10:20:30.000Z"),
            ),
        ),
    ],
    "two-replacements": [
        ("a third pod", _third_replacement),
        (
            "the reading after lists an old pod",
            _edit(
                "restarts/r1/after.pods.json",
                lambda r: r["items"].append(
                    r["items"][0]
                    | {"metadata": r["items"][0]["metadata"] | {"uid": _uid(10)}}
                ),
            ),
        ),
    ],
    "one-at-a-time": [("an overlap", _overlap)],
    "ready-held": [
        ("Ready lost", _lines("r1", _second_ready_flaps)),
        (
            "a runtime restart",
            _edit(
                "restarts/r2/after.pods.json",
                lambda r: r["items"][0]["status"]["containerStatuses"][0].update(
                    restartCount=1
                ),
            ),
        ),
    ],
    "model-verified": [
        (
            "verification failed",
            _edit(
                "restarts/r3/after.pods.json",
                lambda r: r["items"][1]["status"]["initContainerStatuses"][0].update(
                    state={"terminated": {"exitCode": 1}}
                ),
            ),
        ),
        (
            "another image digest",
            _edit(
                "restarts/r1/after.pods.json",
                lambda r: r["items"][0]["status"]["containerStatuses"][0].update(
                    imageID="ghcr.io/x@sha256:" + "e" * 64
                ),
            ),
        ),
    ],
    "ready-serves": [
        (
            "a 503",
            lambda d, r: _edit(
                next((d / "restarts/r2").glob("completion.*.json"))
                .relative_to(d)
                .as_posix(),
                lambda c: c.update(httpStatus=503),
            )(d, r),
        ),
        (
            "no completion",
            lambda d, r: next((d / "restarts/r1").glob("completion.*.json")).unlink(),
        ),
    ],
    "readings-in-order": [
        ("up after", _header_set(upStartedAt="2026-10-15T10:00:00Z")),
        (
            "r2 before r1 rolled out",
            _edit(
                "restarts/r2/restart.json",
                lambda r: r.update(requestedAt="2026-10-15T10:01:00.000Z"),
            ),
        ),
    ],
}


#: The defects whose rule is not observed rather than not held: the source the
#: rule reads is absent.
NOT_OBSERVED_CASES = frozenset(
    {("three-restarts", "no r3"), ("ready-serves", "no completion")}
)

#: The other rules that a defect also breaks, measured. Every other defect breaks
#: its own rule and no other, so a rule weakened to pass it is visible here.
ALSO_NOT_HELD: dict[tuple[str, str], set[str]] = {
    ("environment-qualified", "q1-1 refused"): {"release-qualified", "model-verified"},
    ("three-restarts", "no r3"): {
        "model-verified",
        "one-at-a-time",
        "readings-in-order",
        "ready-held",
        "ready-serves",
        "stable-before-each-restart",
        "stream-complete",
        "two-replacements",
    },
    ("three-restarts", "a failed rollout"): {"readings-in-order", "stream-complete"},
    ("two-replacements", "a third pod"): {
        "model-verified",
        "one-at-a-time",
        "ready-held",
        "ready-serves",
    },
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
        q2.NOT_OBSERVED if (rule, label) in NOT_OBSERVED_CASES else q2.NOT_HELD
    )
    assert _state(record, rule) == expected_state, rule
    others = {
        item["ruleId"]
        for item in record["findings"]
        if item["state"] != q2.HELD and item["ruleId"] != rule
    }
    assert others == ALSO_NOT_HELD.get((rule, label), set())
    assert RULE_CATEGORIES[rule] in record["notHeld"]["categories"]
    expected = q2.REFUSED if rule in q2.PRECONDITION_RULES else q2.INCONCLUSIVE
    if rule not in q2.PRECONDITION_RULES:
        # A defect of the measurement leaves every precondition held.
        assert not set(record["notHeld"]["rules"]) & set(q2.PRECONDITION_RULES)
    assert record["result"] == expected
    assert record["bound"]["valueMs"] is None
    assert record["bound"]["observations"] is None


def test_each_rule_has_a_defect_in_this_suite() -> None:
    assert sorted(DEFECTS) == sorted(rule.rule_id for rule in q2.RULES)
    assert {rule.rule_id: rule.category for rule in q2.RULES} == RULE_CATEGORIES


def test_the_categories_are_listed_in_their_order(tmp_path: Path, root: Path) -> None:
    directory = _directory(tmp_path)
    _header_set(workingTree="dirty")(directory, root)
    _edit(
        "restarts/r1/restart.json", lambda r: r.update(rolloutExit=1, rolledOutAt=None)
    )(directory, root)
    _header_set(upRefusal="capacity")(directory, root)
    categories = _record(directory, root)["notHeld"]["categories"]
    assert categories == [c for c in q2.CATEGORIES if c in categories]
    assert categories[:2] == ["preparation", "desired-state"]


def test_the_preconditions_are_the_rules_that_refuse() -> None:
    assert tuple(rule.rule_id for rule in q2.RULES[:7]) == q2.PRECONDITION_RULES


def test_an_absent_source_is_not_observed(tmp_path: Path, root: Path) -> None:
    for name, rule in (
        ("provenance.json", "release-qualified"),
        ("capacity", "environment-qualified"),
        ("restarts/r2/before.deployment.json", "stable-before-each-restart"),
        ("restarts/r1/watch.jsonl", "stream-complete"),
    ):
        directory = _directory(tmp_path / name.replace("/", "-"))
        _remove(name)(directory, root)
        assert _state(_record(directory, root), rule) == q2.NOT_OBSERVED, name


def test_an_absent_record_of_q1_1_refuses(tmp_path: Path, root: Path) -> None:
    (root / q2.QUALIFICATION_RECORD).unlink()
    record = _record(_directory(tmp_path), root)
    assert _state(record, "environment-qualified") == q2.NOT_OBSERVED
    assert record["result"] == q2.REFUSED


def test_a_directory_with_no_restart_is_refused_when_a_precondition_fails(
    tmp_path: Path, root: Path
) -> None:
    """The driver requests no restart after a refusal. The record is REFUSED, and
    the rules of the measurement are not observed."""
    directory = _directory(tmp_path)
    shutil.rmtree(directory / "restarts")
    _header_set(workingTree="dirty")(directory, root)
    record = _record(directory, root)
    assert record["result"] == q2.REFUSED
    assert record["observations"] == []
    assert _state(record, "three-restarts") == q2.NOT_OBSERVED


def test_a_malformed_member_refuses_and_does_not_raise(
    tmp_path: Path, root: Path
) -> None:
    for name, value in (
        ("restarts/r1/after.pods.json", {"items": "none"}),
        ("restarts/r2/before.pods.json", []),
        ("restarts/r3/restart.json", {"schema": q2.RESTART_SCHEMA}),
        ("deployments.json", {"items": [1, 2]}),
    ):
        directory = _directory(tmp_path / name.replace("/", "-"))
        _write(directory / name, value)
        assert _record(directory, root)["result"] != q2.CHARACTERIZED, name


def test_a_stream_line_that_is_not_an_event_is_refused() -> None:
    assert (
        q2.read_stream(b'{"type":"ADDED","object":{}}\nnot json\n').problem
        == "line 2 is not JSON"
    )
    assert (
        q2.read_stream(b'{"type":"BOOKMARK","object":{}}\n').problem
        == "line 1 is not a watch event"
    )
    assert q2.read_stream(b"\n").problem == "the stream holds no event"
    assert q2.read_stream(None).problem == "absent"
    assert q2.read_stream(b'{"type":"ADDED","object":{}}\r\n').events[0].kind == "ADDED"


def test_a_header_with_another_member_is_not_a_collection(
    tmp_path: Path, root: Path
) -> None:
    for change in (
        lambda h: h.update(context="docker-desktop"),
        lambda h: h.pop("upStartedAt"),
        lambda h: h.update(characterizationId="q1-1"),
        lambda h: h.update(upRefusal="tired"),
    ):
        directory = _directory(tmp_path)
        _edit("run.json", change)(directory, root)
        with pytest.raises(q2.CollectionRefused):
            _record(directory, root)
        shutil.rmtree(directory)


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_exits_0_5_and_6(
    tmp_path: Path,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(q2.core, "REPO_ROOT", root)
    directory = _directory(tmp_path)
    original = q2.core.build_record
    monkeypatch.setattr(cli, "build_record", lambda d: original(d, root))
    monkeypatch.setattr(cli, "preconditions", lambda d: q2.core.preconditions(d, root))
    assert cli.main([str(directory)]) == 0
    assert json.loads(capsys.readouterr().out)["result"] == q2.CHARACTERIZED
    assert cli.main(["--preconditions", str(directory)]) == 0
    assert capsys.readouterr().out.count("held ") == len(q2.PRECONDITION_RULES)
    _edit("restarts/r1/restart.json", lambda r: r.update(restartExit=1))(
        directory, root
    )
    assert cli.main([str(directory)]) == 6
    assert cli.main(["--preconditions", str(directory)]) == 0
    _header_set(workingTree="dirty")(directory, root)
    assert cli.main([str(directory)]) == 5
    assert cli.main(["--preconditions", str(directory)]) == 5
    capsys.readouterr()
    assert cli.main([str(tmp_path / "absent")]) == 1


def test_the_command_has_no_option_for_the_target() -> None:
    text = (ROOT / "tools/runtime_startup/__main__.py").read_text(encoding="utf-8")
    options = sorted(set(re.findall(r'"(--[a-z-]+)"', text)))
    assert options == ["--check", "--preconditions"]


def test_the_command_runs_as_a_module_and_refuses_usage(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.runtime_startup"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    result = subprocess.run(
        [sys.executable, "-m", "tools.runtime_startup", str(tmp_path)],
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
    directory = root / "docs/proof/experiments/v2-q2/runs/q2-1"
    shutil.copytree(_directory(tmp_path), directory)
    _write(directory / "record.v1alpha1.json", q2.record_text(_record(directory, root)))
    assert q2.check_committed(root) == []
    _edit("restarts/r1/restart.json", lambda r: r.update(restartExit=1))(
        directory, root
    )
    assert q2.check_committed(root) == [
        "docs/proof/experiments/v2-q2/runs/q2-1: record.v1alpha1.json is not what the directory gives"
    ]
    (directory / "record.v1alpha1.json").unlink()
    assert q2.check_committed(root) == [
        "docs/proof/experiments/v2-q2/runs/q2-1: no record.v1alpha1.json"
    ]


def test_each_committed_characterization_is_what_its_directory_gives() -> None:
    assert q2.check_committed() == []


# --------------------------------------------------------------------------
# The freeze record, the page, and the driver
# --------------------------------------------------------------------------


def _freeze() -> dict[str, Any]:
    return json.loads(FREEZE.read_text(encoding="utf-8"))


def test_each_rule_is_one_acceptance_criterion_of_the_freeze_record() -> None:
    (entry,) = _freeze()["fields"]["acceptanceCriteria"]
    assert entry["value"] == [
        {"id": rule.criterion, "statement": rule.statement} for rule in q2.RULES
    ]
    assert [rule.criterion for rule in q2.RULES] == [
        f"Q2-AC{n}" for n in range(1, len(q2.RULES) + 1)
    ]


def test_the_freeze_record_freezes_the_target_and_states_no_value_of_s() -> None:
    record = _freeze()
    assert record["metadata"]["experiment"] == q2.EXPERIMENT_ID
    (topology,) = record["fields"]["topology"]
    assert topology["value"]["releaseKey"] == q2.TARGET_RELEASE_KEY
    assert (topology["value"]["apiReplicas"], topology["value"]["runtimeReplicas"]) == (
        2,
        2,
    )
    assert topology["value"]["runtimeRollout"] == {"maxUnavailable": 1, "maxSurge": 0}
    (fault,) = record["fields"]["fault"]
    assert fault["status"] == "not-applicable"
    (bounds,) = record["fields"]["derivedNumericBounds"]
    assert "states no value" in bounds["value"]["S"]
    assert sorted(bounds["value"]) == ["S", "derivedLater"]


def test_revision_2_supersedes_revision_1_and_changes_one_criterion() -> None:
    """Revision 1 held the API image to the digest of q1-1, which a build of the
    same inputs does not report again. No characterization ran under it. Revision 2
    changes that one criterion and classifies the two pins that moved."""
    r1_path = "docs/proof/experiments/v2-q2/freeze-r1.v1alpha1.json"
    assert q2.FREEZE_RECORD == "docs/proof/experiments/v2-q2/freeze-r2.v1alpha1.json"
    r1 = json.loads((ROOT / r1_path).read_text(encoding="utf-8"))
    r2 = _freeze()
    assert r2["metadata"]["revision"] == 2
    assert r2["metadata"]["supersedes"] == {
        "path": r1_path,
        "contentSha256": freeze.content_digest((ROOT / r1_path).read_bytes()),
    }
    (before,) = r1["fields"]["acceptanceCriteria"]
    (after,) = r2["fields"]["acceptanceCriteria"]
    changed = [
        old["id"]
        for old, new in zip(before["value"], after["value"], strict=True)
        if old != new
    ]
    assert changed == ["Q2-AC6"]
    assert (
        "q1-1 states and that the phase up declared" in before["value"][5]["statement"]
    )
    assert sorted(item["path"] for item in r2["inputChanges"]) == [
        "docs/proof/experiments/v2-q2/procedure/q2-driver.txt",
        "tools/runtime_startup/core.py",
    ]


def test_an_api_image_other_than_that_of_q1_1_is_held_when_it_is_declared(
    tmp_path: Path, root: Path
) -> None:
    """The phase up builds the API image again. The rule holds the Deployment to
    the digest that the phase up declared, whatever digest q1-1 states."""
    directory = _directory(tmp_path)
    other = "sha256:" + "f" * 64
    _header_set(apiImageDigest=other)(directory, root)
    _edit(
        "deployments.json",
        lambda r: r["items"][0]["spec"]["template"]["spec"]["containers"][0].update(
            image=f"localhost/inferops-api@{other}"
        ),
    )(directory, root)
    record = _record(directory, root)
    assert _state(record, "release-qualified") == q2.HELD
    assert record["result"] == q2.CHARACTERIZED


def test_the_freeze_record_holds_every_rule_of_the_freeze_check() -> None:
    assert freeze.check_record(_freeze(), q2.FREEZE_RECORD) == []


def test_the_freeze_record_pins_the_tool_the_drivers_and_q1_1() -> None:
    pinned = {item["path"] for item in _freeze()["pinnedInputs"]}
    for path in (
        "tools/runtime_startup/core.py",
        "tools/runtime_startup/__main__.py",
        "tools/environment_qualification/core.py",
        "docs/proof/experiments/v2-q2/procedure/q2-driver.txt",
        "docs/proof/experiments/v2-q1/procedure/q1-driver.txt",
        q2.QUALIFICATION_FREEZE_RECORD,
        q2.QUALIFICATION_RECORD,
        "charts/inferops-llm/values.yaml",
    ):
        assert path in pinned, path


def test_the_scope_of_q2_holds_the_scope_of_q1() -> None:
    q1_record = json.loads(
        (ROOT / q2.QUALIFICATION_FREEZE_RECORD).read_text(encoding="utf-8")
    )
    scope = _freeze()["materialScope"]
    assert set(q1_record["materialScope"]["paths"]) <= set(scope["paths"])
    assert set(q1_record["materialScope"]["entryModules"]) <= set(scope["entryModules"])


def test_the_freeze_record_lists_no_changed_material_file() -> None:
    assert freeze.changed_inputs(_freeze()) == []


def test_the_qualification_record_is_q1_1_and_qualified() -> None:
    record = json.loads((ROOT / q2.QUALIFICATION_RECORD).read_text(encoding="utf-8"))
    assert record["result"] == "QUALIFIED"
    assert record["collection"]["qualificationId"] == q2.QUALIFICATION_ID
    assert record["environmentSha256"] == (
        "sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461"
    )


def test_the_page_restates_each_rule_and_each_category() -> None:
    text = PAGE.read_text(encoding="utf-8")
    for rule in q2.RULES:
        assert f"| `{rule.rule_id}` | {rule.criterion} | `{rule.category}` |" in text, (
            rule.rule_id
        )
    for category in q2.CATEGORIES:
        assert f"`{category}`" in text


def _driver() -> str:
    return DRIVER.read_text(encoding="utf-8")


def test_the_driver_names_the_freeze_records_the_experiment_and_each_file() -> None:
    text = _driver()
    assert f'FREEZE_RECORD="{q2.FREEZE_RECORD}"' in text
    assert f'Q1_FREEZE_RECORD="{q2.QUALIFICATION_FREEZE_RECORD}"' in text
    assert f'EXPERIMENT="{q2.EXPERIMENT_ID}"' in text
    assert f'RESTARTS="{" ".join(q2.RESTARTS)}"' in text
    for name in (
        q2.HEADER_FILE,
        q2.PROVENANCE_FILE,
        q2.DEPLOYMENTS_FILE,
        q2.RESTART_FILE,
        q2.BEFORE_DEPLOYMENT_FILE,
        q2.BEFORE_PODS_FILE,
        q2.WATCH_FILE,
        q2.AFTER_PODS_FILE,
        q2.RECORD_FILE,
    ):
        assert f'="{name}"' in text, name
    assert q2.COLLECTION_SCHEMA in text
    assert q2.RESTART_SCHEMA in text


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
    """A restart is a rollout restart. The driver deletes nothing by name, scales
    nothing, patches nothing, and sets no Helm value."""
    code = "\n".join(
        line for line in _driver().splitlines() if not line.lstrip().startswith("#")
    )
    for word in (
        " delete ",
        " scale ",
        " patch ",
        " edit ",
        " apply ",
        "--set",
        "helm ",
    ):
        assert word not in code, word
    assert code.count("rollout restart") == 1
    assert '--timeout="${ROLLOUT_BOUND_SECONDS}s"' in code


def test_the_driver_requests_a_restart_only_after_the_preconditions() -> None:
    text = _driver()
    asked = text.index("python -m tools.runtime_startup --preconditions")
    loop = text.index("for name in ${RESTARTS}; do")
    assert asked < loop
    assert "if ! restart_one" in text
    assert "No later restart is requested." in text


def test_the_driver_keeps_the_record_of_each_result() -> None:
    assert "0 | 5 | 6) tr -d" in _driver()


def test_the_driver_refuses_a_reused_identifier() -> None:
    text = _driver()
    assert "^q2-[1-9][0-9]?$" in text
    assert "One characterization identifier is one characterization." in text


def test_each_sentence_of_what_a_record_does_not_establish_says_so() -> None:
    for sentence in q2.DOES_NOT_ESTABLISH:
        assert sentence.startswith("A record does not establish "), sentence


def test_the_record_text_is_sorted_indented_json_with_one_final_lf(
    tmp_path: Path, root: Path
) -> None:
    text = q2.record_text(_record(_directory(tmp_path), root))
    assert text.endswith("}\n") and not text.endswith("\n\n")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_the_tool_imports_no_network_or_process_module() -> None:
    for name in ("core.py", "__main__.py", "__init__.py"):
        text = (ROOT / "tools/runtime_startup" / name).read_text(encoding="utf-8")
        for module in ("subprocess", "socket", "urllib", "http", "requests"):
            assert not re.search(rf"^\s*(import|from)\s+{module}\b", text, re.MULTILINE)


def test_the_committed_characterization_q2_1_is_characterized_with_s_of_11000_ms() -> (
    None
):
    """V2-S6-002-PR1 ran q2-1 once under revision 2. Its record is what its
    directory gives, each rule is held, and S is the maximum of its six intervals."""
    directory = ROOT / "docs/proof/experiments/v2-q2/runs/q2-1"
    assert q2.committed_runs() == [directory]
    record = json.loads(
        (directory / "record.v1alpha1.json").read_text(encoding="utf-8")
    )
    assert record["result"] == q2.CHARACTERIZED
    assert {item["state"] for item in record["findings"]} == {q2.HELD}
    values = [row["startToReadyMs"] for row in record["observations"]]
    assert values == [11_000, 11_000, 11_000, 11_000, 10_000, 11_000]
    assert record["bound"]["valueMs"] == max(values) == 11_000
    assert record["collection"]["freezeRecord"] == q2.FREEZE_RECORD
    assert record["identities"]["environmentSha256"] == (
        "sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461"
    )
    assert not (directory / "capacity/pods.json").exists()


# --------------------------------------------------------------------------
# Boundaries and measured gaps, from the independent review
# --------------------------------------------------------------------------


def test_one_at_a_time_holds_for_an_equal_second(tmp_path: Path, root: Path) -> None:
    """The second replacement may be created in the second the first became Ready.
    In q2-1 that happened in each restart, so the rule does not order them."""
    record = _record(_directory(tmp_path), root)
    rows = [row for row in record["observations"] if row["restart"] == "r1"]
    assert rows[1]["createdAt"] != rows[0]["readyAt"]
    directory = _directory(tmp_path / "equal")
    path = directory / "restarts/r1/watch.jsonl"
    start = TIMING["r1"][0]
    second = start + timedelta(seconds=1 + 20 + 31 + 1)
    ready = start + timedelta(seconds=1 + 20 + 31)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            f'"creationTimestamp":"{_stamp(second)}"',
            f'"creationTimestamp":"{_stamp(ready)}"',
        ),
        encoding="utf-8",
        newline="\n",
    )
    assert _state(_record(directory, root), "one-at-a-time") == q2.HELD


def test_a_deleted_event_after_ready_is_not_held(tmp_path: Path, root: Path) -> None:
    def deleted(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        last = next(
            e for e in reversed(events) if e["object"]["metadata"]["uid"] == _uid(13)
        )
        return [*events, {"type": "DELETED", "object": last["object"]}]

    directory = _directory(tmp_path)
    _lines("r1", deleted)(directory, root)
    assert _state(_record(directory, root), "ready-held") == q2.NOT_HELD


def test_an_image_identifier_without_the_reference_is_not_held(
    tmp_path: Path, root: Path
) -> None:
    directory = _directory(tmp_path)
    _edit(
        "restarts/r2/after.pods.json",
        lambda r: r["items"][1]["status"]["containerStatuses"][0].update(
            imageID=RUNTIME_DIGEST
        ),
    )(directory, root)
    assert _state(_record(directory, root), "model-verified") == q2.NOT_HELD


def test_a_status_of_true_is_not_a_status_of_200(tmp_path: Path, root: Path) -> None:
    directory = _directory(tmp_path)
    path = next((directory / "restarts/r3").glob("completion.*.json"))
    _edit(path.relative_to(directory).as_posix(), lambda c: c.update(httpStatus=True))(
        directory, root
    )
    assert _state(_record(directory, root), "ready-serves") == q2.NOT_HELD


@pytest.mark.parametrize(
    ("member", "rule"),
    [
        ("freezeChanges", "procedure-frozen"),
        ("qualificationFreezeChanges", "procedure-frozen"),
        ("desiredStateDiff", "desired-revision-known"),
        ("workingTree", "working-tree-clean"),
    ],
)
def test_a_header_state_that_was_not_read_is_not_observed(
    tmp_path: Path, root: Path, member: str, rule: str
) -> None:
    directory = _directory(tmp_path)
    _header_set(**{member: "unread"})(directory, root)
    record = _record(directory, root)
    assert _state(record, rule) == q2.NOT_OBSERVED
    assert record["result"] == q2.REFUSED


def test_a_pod_identifier_of_another_form_raises_a_measured_gap(
    tmp_path: Path, root: Path
) -> None:
    """A measured gap of the tool, which the page states: a list as a pod
    identifier in the reading after a restart raises instead of refusing. kubectl
    writes no such identifier. The tool is a pinned input of revision 2, so the gap
    stays until a later revision, and this test fails when it is closed."""
    directory = _directory(tmp_path)
    _edit(
        "restarts/r1/after.pods.json",
        lambda r: r["items"][0]["metadata"].update(uid=[_uid(12)]),
    )(directory, root)
    with pytest.raises(TypeError):
        _record(directory, root)


def test_the_driver_restarts_only_inside_the_branch_of_held_preconditions() -> None:
    """The loop of restarts is the body of the branch that the exit status 0 of the
    precondition check opens, and the branch of a refusal of the phase up reads no
    cluster state."""
    text = _driver()
    guard = (
        'run uv run --locked python -m tools.runtime_startup --preconditions "${A}"\n'
        '    if [ "${LAST}" -eq 0 ]; then\n'
        "      for name in ${RESTARTS}; do\n"
    )
    assert guard in text
    refusal = text.index('if [ -e "${Q1_WORK}/up-refusal" ]; then')
    provenance = text.index("tools.desired_state_provenance")
    assert refusal < text.index('  else\n    step "S1.', refusal) < provenance
