"""The infrastructure timeline streams of an experiment run, from collections built here.

``tools.experiment_timeline`` reads the directory that a collector wrote and
returns four streams: ``endpoints``, ``pods``, ``deployments``, and ``argo``.
This suite builds each collection in a temporary directory. It reads no cluster,
and it commits no collection: an answer of a cluster holds addresses and the
environment of each pod.

The suite holds the tool to these properties.

*Absence of a signal is not a value.* A count that the API omitted, a pod with
no Ready condition, a pod with no container status, and a field of the
Application that the controller did not write are each ``missing``. None is
zero, false, or healthy. A read that did not answer gives a reading with no
value.

*One time basis.* Each reading states the two instants of its read in UTC to
one millisecond. A cluster instant is normalised to UTC and keeps its
resolution.

*The Application is read on its own.* A workload read that did not answer does
not change the ``argo`` stream, and an Application read that did not answer does
not change the three workload streams.

*A stream holds an allowlist.* No address, node name, image, environment
variable, message, or repository address of a collection reaches a stream.

*A stream is deterministic and can be read back.* One collection gives one text,
and ``read_stream`` refuses a text that does not have the form.

These tests show what the tool does with a directory. They do not show what a
cluster does, and no test here is evidence of a timeline of a real run.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tools import experiment_timeline as timeline
from tools.experiment_evidence import EVIDENCE_SUFFIXES, RAW, ROLES
from tools.experiment_timeline.__main__ import main

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE = REPO_ROOT / "docs" / "environment" / "experiment-timelines.md"

NAMESPACE = "inferops-release"
RELEASE = "inferops"
APPLICATION = "local-docker-desktop-support-assistant"
APPLICATION_NAMESPACE = "argocd"
API = "platform-api"
RUNTIME = "serving-runtime"
API_NAME = "inferops-inferops-llm"
RUNTIME_NAME = "inferops-inferops-llm-runtime"
COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40
T0 = datetime(2026, 10, 12, 8, 0, 0, tzinfo=UTC)

# Values that a stream must never hold. Each is in an answer of the default
# collection, in a member that the allowlist does not read.
HOSTILE = (
    "10.1.0.7",
    "desktop-control-plane",
    "ghcr.io/example/runtime@sha256:" + "c" * 64,
    "MODEL_TOKEN",
    "hunter2-not-a-real-value",
    "https://user:secret@example.invalid/repo.git",
    "back-off 5m0s restarting failed container",
    "ComparisonError: rpc error",
)


def uid(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012d}"


def instant(offset_ms: int) -> str:
    return timeline.format_instant(T0 + timedelta(milliseconds=offset_ms))


def labels(tier: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/instance": RELEASE,
        "app.kubernetes.io/component": tier,
    }


def a_service(name: str, tier: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "namespace": NAMESPACE, "labels": labels(tier)},
        "spec": {"type": "ClusterIP", "clusterIP": "10.96.0.7"},
    }


def a_slice(service: str, pods: list[tuple[str, int, bool]]) -> dict[str, Any]:
    return {
        "apiVersion": "discovery.k8s.io/v1",
        "kind": "EndpointSlice",
        "metadata": {
            "name": f"{service}-abcde",
            "namespace": NAMESPACE,
            "labels": {
                "kubernetes.io/service-name": service,
                "endpointslice.kubernetes.io/managed-by": (
                    "endpointslice-controller.k8s.io"
                ),
            },
        },
        "addressType": "IPv4",
        "endpoints": [
            {
                "addresses": ["10.1.0.7"],
                "nodeName": "desktop-control-plane",
                "conditions": {"ready": ready, "serving": ready, "terminating": False},
                "targetRef": {
                    "kind": "Pod",
                    "name": name,
                    "namespace": NAMESPACE,
                    "uid": uid(number),
                },
            }
            for name, number, ready in pods
        ],
    }


def a_replica_set(name: str, number: int, tier: str, revision: str) -> dict[str, Any]:
    return {
        "apiVersion": "apps/v1",
        "kind": "ReplicaSet",
        "metadata": {
            "name": name,
            "namespace": NAMESPACE,
            "uid": uid(number),
            "labels": labels(tier),
            "annotations": {"deployment.kubernetes.io/revision": revision},
        },
    }


def a_pod(
    name: str,
    number: int,
    tier: str,
    *,
    owner: tuple[str, int] | None,
    ready: str | None = "True",
    restarts: int | None = 0,
) -> dict[str, Any]:
    status: dict[str, Any] = {
        "phase": "Running",
        "hostIP": "10.1.0.7",
        "podIP": "10.1.0.7",
        "conditions": [
            {"type": "PodScheduled", "status": "True"},
        ],
    }
    if ready is not None:
        status["conditions"].append(
            {
                "type": "Ready",
                "status": ready,
                "lastTransitionTime": "2026-10-12T07:59:30Z",
                "message": "back-off 5m0s restarting failed container",
            }
        )
    if restarts is not None:
        status["containerStatuses"] = [
            {
                "name": "main",
                "ready": ready == "True",
                "started": True,
                "restartCount": restarts,
                "image": "ghcr.io/example/runtime@sha256:" + "c" * 64,
            }
        ]
    metadata: dict[str, Any] = {
        "name": name,
        "namespace": NAMESPACE,
        "uid": uid(number),
        "creationTimestamp": "2026-10-12T07:59:00Z",
        "labels": {**labels(tier), "pod-template-hash": "5d4f8c7b9"},
    }
    if owner is not None:
        metadata["ownerReferences"] = [
            {
                "kind": "ReplicaSet",
                "name": owner[0],
                "uid": uid(owner[1]),
                "controller": True,
            }
        ]
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": metadata,
        "spec": {
            "nodeName": "desktop-control-plane",
            "containers": [
                {
                    "name": "main",
                    "image": "ghcr.io/example/runtime@sha256:" + "c" * 64,
                    "env": [
                        {"name": "MODEL_TOKEN", "value": "hunter2-not-a-real-value"}
                    ],
                }
            ],
        },
        "status": status,
    }


def a_deployment(
    name: str, number: int, tier: str, *, ready: int | None = 2
) -> dict[str, Any]:
    status: dict[str, Any] = {
        "observedGeneration": 3,
        "replicas": 2,
        "updatedReplicas": 2,
        "conditions": [
            {
                "type": "Available",
                "status": "True",
                "reason": "MinimumReplicasAvailable",
                "lastTransitionTime": "2026-10-12T07:59:40Z",
                "lastUpdateTime": "2026-10-12T07:59:40Z",
                "message": "Deployment has minimum availability.",
            }
        ],
    }
    if ready is not None:
        status["readyReplicas"] = ready
        status["availableReplicas"] = ready
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "namespace": NAMESPACE,
            "uid": uid(number),
            "generation": 3,
            "labels": labels(tier),
            "annotations": {"deployment.kubernetes.io/revision": "4"},
        },
        "spec": {"replicas": 2},
        "status": status,
    }


def an_application(
    *, sync: str | None = "Synced", health: str | None = "Healthy"
) -> dict[str, Any]:
    status: dict[str, Any] = {
        "reconciledAt": "2026-10-12T07:58:00Z",
        "operationState": {
            "phase": "Succeeded",
            "startedAt": "2026-10-12T07:57:00Z",
            "finishedAt": "2026-10-12T07:57:30Z",
            "message": "ComparisonError: rpc error",
            "syncResult": {"revision": COMMIT},
        },
        "history": [
            {"id": 7, "revision": COMMIT, "deployedAt": "2026-10-12T07:57:30Z"}
        ],
        "sync": {"revision": COMMIT},
    }
    if sync is not None:
        status["sync"]["status"] = sync
    if health is not None:
        status["health"] = {"status": health}
    return {
        "kind": "Application",
        "metadata": {"name": APPLICATION, "namespace": APPLICATION_NAMESPACE},
        "spec": {
            "source": {
                "repoURL": "https://user:secret@example.invalid/repo.git",
                "targetRevision": "main",
            }
        },
        "status": status,
    }


def workload(
    *,
    runtime_ready: tuple[bool, bool] = (True, True),
    runtime_deployment_ready: int | None = 2,
) -> list[dict[str, Any]]:
    """The items of one workload read: two tiers, two pods for each."""
    first, second = runtime_ready
    return [
        a_service(API_NAME, API),
        a_service(RUNTIME_NAME, RUNTIME),
        a_slice(API_NAME, [("api-a", 1, True), ("api-b", 2, True)]),
        a_slice(RUNTIME_NAME, [("runtime-a", 11, first), ("runtime-b", 12, second)]),
        a_replica_set("api-rs", 101, API, "4"),
        a_replica_set("runtime-rs", 111, RUNTIME, "4"),
        a_pod("api-a", 1, API, owner=("api-rs", 101)),
        a_pod("api-b", 2, API, owner=("api-rs", 101)),
        a_pod(
            "runtime-a",
            11,
            RUNTIME,
            owner=("runtime-rs", 111),
            ready="True" if first else "False",
        ),
        a_pod(
            "runtime-b",
            12,
            RUNTIME,
            owner=("runtime-rs", 111),
            ready="True" if second else "False",
        ),
        a_deployment(API_NAME, 201, API),
        a_deployment(RUNTIME_NAME, 211, RUNTIME, ready=runtime_deployment_ready),
    ]


def header(**changed: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema": timeline.COLLECTION_SCHEMA,
        "experimentId": "example-experiment",
        "runId": "run-1",
        "provider": "docker-desktop",
        "serverVersion": "v1.36.1",
        "namespace": NAMESPACE,
        "release": RELEASE,
        "application": APPLICATION,
        "applicationNamespace": APPLICATION_NAMESPACE,
        "executingCommit": COMMIT,
        "procedureSha256": "1" * 64,
        "librarySha256": "2" * 64,
        "requestedSamples": 1,
        "intervalSeconds": 5,
        "readTimeoutSeconds": 10,
    }
    document.update(changed)
    return document


_DEFAULT = object()


def write_collection(
    root: Path,
    samples: list[dict[str, Any]],
    *,
    head: dict[str, Any] | None = None,
    end: str | object | None = _DEFAULT,
) -> Path:
    """One collection directory, as the collector writes it.

    A sample states ``workload`` and ``application``. A list or an object is
    written as the answer. ``None`` is a read that did not answer. A text is
    written as it is. A sample may state ``meta`` to replace lines of its status
    file, and ``skip`` to write no file at all.
    """
    directory = root / "collection"
    directory.mkdir()
    head = head or header(requestedSamples=len(samples))
    (directory / timeline.HEADER_FILE).write_text(json.dumps(head), "utf-8")
    for number, sample in enumerate(samples, start=1):
        if sample.get("skip"):
            continue
        stem = timeline.SAMPLE_STEM.format(index=number)
        base = (number - 1) * 5000
        meta = {
            "workloadRead": "answered",
            "workloadStartedAt": instant(base),
            "workloadFinishedAt": instant(base + 200),
            "applicationRead": "answered",
            "applicationStartedAt": instant(base + 250),
            "applicationFinishedAt": instant(base + 400),
        }
        for name, suffix in (
            ("workload", timeline.WORKLOAD_SUFFIX),
            ("application", timeline.APPLICATION_SUFFIX),
        ):
            answer = sample.get(name, workload() if name == "workload" else None)
            if name == "application" and name not in sample:
                answer = an_application()
            if answer is None:
                meta[f"{name}Read"] = "unanswered"
                continue
            if isinstance(answer, list):
                answer = {"apiVersion": "v1", "kind": "List", "items": answer}
            text = answer if isinstance(answer, str) else json.dumps(answer)
            (directory / f"{stem}{suffix}").write_text(text, "utf-8")
        meta.update(sample.get("meta", {}))
        (directory / f"{stem}{timeline.META_SUFFIX}").write_text(
            "".join(f"{key}={value}\n" for key, value in meta.items()), "utf-8"
        )
    if end is _DEFAULT:
        end = f"completedSamples={len(samples)}\n"
    if end is not None:
        assert isinstance(end, str)
        (directory / timeline.END_FILE).write_text(end, "utf-8")
    return directory


def streams_of(root: Path, samples: list[dict[str, Any]], **options: Any) -> dict:
    return timeline.build_streams(write_collection(root, samples, **options))


def readings(stream: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return stream[1:-1]


def tier_of(reading: dict[str, Any], tier: str) -> dict[str, Any]:
    [found] = [entry for entry in reading["tiers"] if entry["tier"] == tier]
    return found


def pod_of(reading: dict[str, Any], name: str) -> dict[str, Any]:
    [found] = [entry for entry in reading["pods"] if entry["name"] == name]
    return found


def reported(value: Any) -> dict[str, Any]:
    return {"state": "reported", "value": value}


MISSING = {"state": "missing"}
MALFORMED = {"state": "malformed"}


# --------------------------------------------------------------------------
# Instants
# --------------------------------------------------------------------------


def test_a_collector_instant_has_one_form() -> None:
    assert timeline.collector_instant("2026-10-12T08:00:00.123Z") == T0 + timedelta(
        milliseconds=123
    )
    for value in (
        "2026-10-12T08:00:00Z",
        "2026-10-12T08:00:00.12Z",
        "2026-10-12T08:00:00.1234Z",
        "2026-10-12T08:00:00.123+00:00",
        "2026-10-12 08:00:00.123Z",
        "2026-02-30T08:00:00.123Z",
        "2026-10-12T08:00:00.123Z\n",
        "2026-10-12T08:00:00.3NZ",
        "",
        None,
        1760256000,
    ):
        assert timeline.collector_instant(value) is None, value


@pytest.mark.parametrize(
    "stated,value,resolution",
    [
        ("2026-10-12T08:00:00Z", "2026-10-12T08:00:00Z", "second"),
        ("2026-10-12T13:00:00+05:00", "2026-10-12T08:00:00Z", "second"),
        ("2026-10-12T03:30:00-04:30", "2026-10-12T08:00:00Z", "second"),
        ("2026-10-13T00:30:00+05:00", "2026-10-12T19:30:00Z", "second"),
        ("2026-10-12t08:00:00z", "2026-10-12T08:00:00Z", "second"),
        ("2026-10-12T08:00:00.5Z", "2026-10-12T08:00:00.500Z", "millisecond"),
        ("2026-10-12T08:00:00.123999Z", "2026-10-12T08:00:00.123Z", "millisecond"),
        ("2026-10-12T08:00:00.000Z", "2026-10-12T08:00:00.000Z", "millisecond"),
    ],
)
def test_a_cluster_instant_is_normalised_to_utc_and_keeps_its_resolution(
    stated: str, value: str, resolution: str
) -> None:
    """A fraction is cut and not rounded, and a second stays a second."""
    assert timeline.cluster_instant(stated) == {
        "state": "reported",
        "value": value,
        "resolution": resolution,
    }


@pytest.mark.parametrize(
    "stated",
    [
        "2026-10-12T08:00:00",
        "2026-10-12",
        "2026-13-01T00:00:00Z",
        "2026-10-12T24:00:00Z",
        "2026-10-12T08:00:60Z",
        "2026-10-12T08:00:00+24:00",
        "2026-10-12T08:00:00+05",
        "0001-01-01T00:00:00+05:00",
        "yesterday",
        "",
        1760256000,
        True,
        ["2026-10-12T08:00:00Z"],
    ],
)
def test_a_cluster_instant_of_another_form_is_malformed_and_has_no_value(
    stated: object,
) -> None:
    assert timeline.cluster_instant(stated) == MALFORMED


def test_a_cluster_instant_that_is_absent_is_missing() -> None:
    assert timeline.cluster_instant(None) == MISSING


# --------------------------------------------------------------------------
# The collection
# --------------------------------------------------------------------------


def test_a_directory_with_no_header_is_not_a_collection(tmp_path: Path) -> None:
    with pytest.raises(timeline.CollectionRefused, match=r"holds no collection\.json"):
        timeline.build_streams(tmp_path)
    with pytest.raises(timeline.CollectionRefused, match="not a directory"):
        timeline.build_streams(tmp_path / "absent")


@pytest.mark.parametrize(
    "changed,message",
    [
        ({"schema": "inferops.io/other/v1"}, "another schema"),
        ({"experimentId": "has space"}, "no usable experimentId"),
        ({"experimentId": "x\n"}, "no usable experimentId"),
        ({"runId": ""}, "no usable runId"),
        ({"runId": 7}, "no usable runId"),
        ({"provider": "Docker"}, "no usable provider"),
        ({"namespace": "a/b"}, "no usable namespace"),
        ({"executingCommit": "abc"}, "no usable executingCommit"),
        ({"procedureSha256": "1" * 63}, "no usable procedureSha256"),
        ({"requestedSamples": 0}, "requestedSamples"),
        ({"requestedSamples": timeline.MAX_SAMPLES + 1}, "requestedSamples"),
        ({"requestedSamples": "1"}, "requestedSamples"),
        ({"requestedSamples": True}, "requestedSamples"),
        ({"intervalSeconds": timeline.MAX_INTERVAL_SECONDS + 1}, "intervalSeconds"),
        ({"readTimeoutSeconds": 0}, "readTimeoutSeconds"),
        ({"serverVersion": None}, "no usable serverVersion"),
    ],
)
def test_a_header_with_a_member_of_another_form_is_refused(
    tmp_path: Path, changed: dict[str, Any], message: str
) -> None:
    directory = write_collection(tmp_path, [{}], head=header(**changed))
    with pytest.raises(timeline.CollectionRefused, match=message):
        timeline.build_streams(directory)


def test_a_header_with_another_member_set_is_refused(tmp_path: Path) -> None:
    extra = header()
    extra["context"] = "kind-inferops-dev"
    (tmp_path / "a").mkdir()
    with pytest.raises(timeline.CollectionRefused, match="holds the members"):
        timeline.build_streams(write_collection(tmp_path / "a", [{}], head=extra))
    fewer = header()
    del fewer["runId"]
    (tmp_path / "b").mkdir()
    with pytest.raises(timeline.CollectionRefused, match="holds the members"):
        timeline.build_streams(write_collection(tmp_path / "b", [{}], head=fewer))


def test_a_header_that_is_not_one_object_is_refused(tmp_path: Path) -> None:
    directory = write_collection(tmp_path, [{}])
    for text in ("[]", "{", "\xff", "[" * 100_000):
        (directory / timeline.HEADER_FILE).write_text(text, "latin-1")
        with pytest.raises(timeline.CollectionRefused, match="not one JSON object"):
            timeline.build_streams(directory)


def test_a_sample_that_the_header_did_not_ask_for_is_refused(tmp_path: Path) -> None:
    directory = write_collection(tmp_path, [{}, {}], head=header(requestedSamples=1))
    with pytest.raises(timeline.CollectionRefused, match=r"sample-0002\.meta"):
        timeline.build_streams(directory)


def test_a_server_version_that_was_not_read_is_missing(tmp_path: Path) -> None:
    streams = streams_of(tmp_path, [{}], head=header(serverVersion=""))
    assert streams["pods"][0]["collection"]["serverVersion"] == MISSING
    (tmp_path / "b").mkdir()
    streams = streams_of(tmp_path / "b", [{}], head=header(serverVersion="1.36 beta"))
    assert streams["pods"][0]["collection"]["serverVersion"] == MALFORMED


def test_a_collection_is_complete_only_when_the_collector_said_so(
    tmp_path: Path,
) -> None:
    def complete(name: str, samples: list[dict[str, Any]], **options: Any) -> Any:
        (tmp_path / name).mkdir()
        streams = streams_of(tmp_path / name, samples, **options)
        return streams["argo"][0]["collection"]

    done = complete("done", [{}, {}])
    assert done["complete"] is True
    assert done["completedSamples"] == reported(2)

    interrupted = complete("interrupted", [{}, {}], end=None)
    assert interrupted["complete"] is False
    assert interrupted["completedSamples"] == MISSING

    fewer = complete("fewer", [{}, {}], end="completedSamples=1\n")
    assert fewer["complete"] is False

    unusable = complete("unusable", [{}, {}], end="completedSamples=two\n")
    assert unusable["complete"] is False
    assert unusable["completedSamples"] == MALFORMED

    gap = complete("gap", [{}, {"skip": True}])
    assert gap["complete"] is False


# --------------------------------------------------------------------------
# The four streams of an answered sample
# --------------------------------------------------------------------------


def test_each_stream_has_a_header_one_reading_for_each_sample_and_an_end(
    tmp_path: Path,
) -> None:
    streams = streams_of(tmp_path, [{}, {}, {}])
    assert (
        tuple(streams)
        == timeline.STREAMS
        == ("endpoints", "pods", "deployments", "argo")
    )
    for name, lines in streams.items():
        head, end = lines[0], lines[-1]
        assert head["record"] == "header"
        assert head["schema"] == timeline.STREAM_SCHEMA
        assert head["stream"] == name
        assert (head["experimentId"], head["runId"]) == ("example-experiment", "run-1")
        assert head["omitted"] == list(timeline.OMITTED)
        assert head["limitations"] == list(timeline.LIMITATIONS)
        assert head["doesNotEstablish"] == list(timeline.DOES_NOT_ESTABLISH)
        assert head["clock"]["skew"] == "not-measured"
        assert [reading["index"] for reading in readings(lines)] == [1, 2, 3]
        assert end["record"] == "end"
        assert end["readings"] == 3
        assert end["byReadState"]["answered"] == 3


def test_each_reading_states_the_two_instants_of_its_own_read(tmp_path: Path) -> None:
    streams = streams_of(tmp_path, [{}, {}])
    for name in ("endpoints", "pods", "deployments"):
        assert [reading["read"] for reading in readings(streams[name])] == [
            {"state": "answered", "startedAt": instant(0), "finishedAt": instant(200)},
            {
                "state": "answered",
                "startedAt": instant(5000),
                "finishedAt": instant(5200),
            },
        ]
    assert readings(streams["argo"])[0]["read"] == {
        "state": "answered",
        "startedAt": instant(250),
        "finishedAt": instant(400),
    }
    assert instant(0) == "2026-10-12T08:00:00.000Z"


def test_the_endpoints_stream_states_the_ready_endpoints_of_each_tier(
    tmp_path: Path,
) -> None:
    streams = streams_of(
        tmp_path, [{"workload": workload(runtime_ready=(True, False))}]
    )
    [reading] = readings(streams["endpoints"])
    assert reading["faults"] == []
    api, runtime = tier_of(reading, API), tier_of(reading, RUNTIME)
    assert api["endpoints"]["ready"] == 2
    assert runtime["service"] == RUNTIME_NAME
    assert runtime["endpoints"] == {
        "total": 2,
        "ready": 1,
        "notReady": 1,
        "serving": 1,
        "terminating": 0,
    }
    assert runtime["ready"] == [{"podName": "runtime-a", "podUid": uid(11)}]
    assert [pod["podUid"] for pod in runtime["notReady"]] == [uid(12)]


def test_the_pods_stream_states_identity_revision_readiness_and_restarts(
    tmp_path: Path,
) -> None:
    streams = streams_of(tmp_path, [{}])
    [reading] = readings(streams["pods"])
    assert reading["otherPods"] == 0
    assert [pod["name"] for pod in reading["pods"]] == [
        "api-a",
        "api-b",
        "runtime-a",
        "runtime-b",
    ]
    assert pod_of(reading, "runtime-a") == {
        "name": "runtime-a",
        "uid": uid(11),
        "tier": RUNTIME,
        "templateHash": reported("5d4f8c7b9"),
        "owner": reported({"kind": "ReplicaSet", "name": "runtime-rs"}),
        "revision": reported(4),
        "phase": reported("Running"),
        "ready": reported("True"),
        "readyTransitionAt": {
            "state": "reported",
            "value": "2026-10-12T07:59:30Z",
            "resolution": "second",
        },
        "containers": reported(
            [
                {
                    "name": reported("main"),
                    "ready": reported(True),
                    "started": reported(True),
                    "restartCount": reported(0),
                }
            ]
        ),
        "restartCount": reported(0),
        "createdAt": {
            "state": "reported",
            "value": "2026-10-12T07:59:00Z",
            "resolution": "second",
        },
        "deletionTimestamp": MISSING,
        "deletionGracePeriodSeconds": MISSING,
    }


def test_the_deployments_stream_states_the_counts_and_the_revision(
    tmp_path: Path,
) -> None:
    streams = streams_of(tmp_path, [{}])
    [reading] = readings(streams["deployments"])
    runtime = tier_of(reading, RUNTIME)
    assert runtime["state"] == "observed"
    assert (runtime["name"], runtime["uid"]) == (RUNTIME_NAME, uid(211))
    assert runtime["revision"] == reported(4)
    assert {name: runtime[name] for name in timeline.DEPLOYMENT_COUNTS} == {
        "generation": reported(3),
        "observedGeneration": reported(3),
        "specReplicas": reported(2),
        "replicas": reported(2),
        "updatedReplicas": reported(2),
        "readyReplicas": reported(2),
        "availableReplicas": reported(2),
        "unavailableReplicas": MISSING,
    }
    available = runtime["conditions"]["Available"]["value"]
    assert available["status"] == reported("True")
    assert available["reason"] == reported("MinimumReplicasAvailable")
    assert available["lastTransitionTime"]["value"] == "2026-10-12T07:59:40Z"
    assert runtime["conditions"]["Progressing"] == MISSING


def test_the_argo_stream_states_what_the_controller_reported(tmp_path: Path) -> None:
    streams = streams_of(tmp_path, [{}])
    [reading] = readings(streams["argo"])
    assert reading["faults"] == []
    second = "second"
    assert reading["application"] == {
        "followedRevision": reported("main"),
        "syncStatus": reported("Synced"),
        "resolvedRevision": reported(COMMIT),
        "healthStatus": reported("Healthy"),
        "operationPhase": reported("Succeeded"),
        "operationRevision": reported(COMMIT),
        "operationStartedAt": {
            "state": "reported",
            "value": "2026-10-12T07:57:00Z",
            "resolution": second,
        },
        "operationFinishedAt": {
            "state": "reported",
            "value": "2026-10-12T07:57:30Z",
            "resolution": second,
        },
        "reconciledAt": {
            "state": "reported",
            "value": "2026-10-12T07:58:00Z",
            "resolution": second,
        },
        "deletionTimestamp": MISSING,
        "historyId": reported(7),
        "historyRevision": reported(COMMIT),
        "historyDeployedAt": {
            "state": "reported",
            "value": "2026-10-12T07:57:30Z",
            "resolution": second,
        },
    }


# --------------------------------------------------------------------------
# Absence of a signal is not a value
# --------------------------------------------------------------------------


def test_a_count_that_the_api_omitted_is_missing_and_not_zero(tmp_path: Path) -> None:
    """Kubernetes omits a zero count, and it omits a count that was not written.

    The reading cannot tell the two apart from the field, so it states neither.
    """
    streams = streams_of(
        tmp_path, [{"workload": workload(runtime_deployment_ready=None)}]
    )
    runtime = tier_of(readings(streams["deployments"])[0], RUNTIME)
    assert runtime["readyReplicas"] == MISSING
    assert runtime["availableReplicas"] == MISSING
    assert "value" not in runtime["readyReplicas"]
    # The tier that reported its count keeps it.
    assert tier_of(readings(streams["deployments"])[0], API)[
        "readyReplicas"
    ] == reported(2)


def test_a_deployment_with_no_status_states_no_count(tmp_path: Path) -> None:
    items = workload()
    del items[-1]["status"]
    runtime = tier_of(
        readings(streams_of(tmp_path, [{"workload": items}])["deployments"])[0], RUNTIME
    )
    assert runtime["state"] == "observed"
    for name in ("observedGeneration", "replicas", "readyReplicas"):
        assert runtime[name] == MISSING, name
    assert runtime["specReplicas"] == reported(2)
    assert runtime["conditions"] == {"Available": MISSING, "Progressing": MISSING}


@pytest.mark.parametrize("value", [-1, 2.0, "2", True, None, [2], 10**9])
def test_a_count_of_another_type_is_not_a_count(tmp_path: Path, value: object) -> None:
    items = workload()
    items[-1]["status"]["readyReplicas"] = value
    runtime = tier_of(
        readings(streams_of(tmp_path, [{"workload": items}])["deployments"])[0], RUNTIME
    )
    assert runtime["readyReplicas"] == (MISSING if value is None else MALFORMED)


def test_a_pod_with_no_ready_condition_is_not_read_as_not_ready(tmp_path: Path) -> None:
    items = workload()
    items[8] = a_pod("runtime-a", 11, RUNTIME, owner=("runtime-rs", 111), ready=None)
    pod = pod_of(
        readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0], "runtime-a"
    )
    assert pod["ready"] == MISSING
    assert pod["readyTransitionAt"] == MISSING


def test_a_ready_condition_of_unknown_keeps_that_value(tmp_path: Path) -> None:
    items = workload()
    items[8] = a_pod(
        "runtime-a", 11, RUNTIME, owner=("runtime-rs", 111), ready="Unknown"
    )
    pod = pod_of(
        readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0], "runtime-a"
    )
    assert pod["ready"] == reported("Unknown")


def test_a_ready_condition_with_another_status_is_malformed(tmp_path: Path) -> None:
    items = workload()
    items[8]["status"]["conditions"][1]["status"] = "true"
    pod = pod_of(
        readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0], "runtime-a"
    )
    assert pod["ready"] == MALFORMED


def test_a_pod_with_no_container_status_has_no_restart_count(tmp_path: Path) -> None:
    """A pod that was not started yet did not restart zero times: it said nothing."""
    items = workload()
    items[8] = a_pod("runtime-a", 11, RUNTIME, owner=("runtime-rs", 111), restarts=None)
    pod = pod_of(
        readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0], "runtime-a"
    )
    assert pod["restartCount"] == MISSING
    assert pod["containers"] == MISSING


def test_a_container_with_no_restart_count_gives_no_sum(tmp_path: Path) -> None:
    items = workload()
    statuses = items[8]["status"]["containerStatuses"]
    statuses.append({"name": "sidecar", "ready": True, "started": True})
    statuses[0]["restartCount"] = 3
    pod = pod_of(
        readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0], "runtime-a"
    )
    assert pod["restartCount"] == MALFORMED
    assert pod["containers"]["value"][0]["restartCount"] == reported(3)
    assert pod["containers"]["value"][1]["restartCount"] == MISSING


def test_the_restart_count_of_a_pod_is_the_sum_of_its_containers(
    tmp_path: Path,
) -> None:
    items = workload()
    statuses = items[8]["status"]["containerStatuses"]
    statuses[0]["restartCount"] = 3
    statuses.append(
        {"name": "sidecar", "ready": True, "started": True, "restartCount": 2}
    )
    pod = pod_of(
        readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0], "runtime-a"
    )
    assert pod["restartCount"] == reported(5)


def test_a_pod_whose_replica_set_is_not_in_the_read_has_no_revision(
    tmp_path: Path,
) -> None:
    items = [item for item in workload() if item["metadata"]["name"] != "runtime-rs"]
    reading = readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0]
    assert pod_of(reading, "runtime-a")["revision"] == MISSING
    assert pod_of(reading, "runtime-a")["owner"] == reported(
        {"kind": "ReplicaSet", "name": "runtime-rs"}
    )
    assert pod_of(reading, "api-a")["revision"] == reported(4)


def test_a_pod_with_no_owner_has_no_revision(tmp_path: Path) -> None:
    items = workload()
    items[8] = a_pod("runtime-a", 11, RUNTIME, owner=None)
    pod = pod_of(
        readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0], "runtime-a"
    )
    assert pod["owner"] == MISSING
    assert pod["revision"] == MISSING


def test_a_revision_that_is_not_a_number_is_malformed(tmp_path: Path) -> None:
    items = workload()
    items[5]["metadata"]["annotations"]["deployment.kubernetes.io/revision"] = "four"
    items[-1]["metadata"]["annotations"] = {}
    streams = streams_of(tmp_path, [{"workload": items}])
    assert pod_of(readings(streams["pods"])[0], "runtime-a")["revision"] == MALFORMED
    assert tier_of(readings(streams["deployments"])[0], RUNTIME)["revision"] == MISSING


def test_a_pod_that_is_being_deleted_states_its_deletion_timestamp(
    tmp_path: Path,
) -> None:
    items = workload()
    items[8]["metadata"]["deletionTimestamp"] = "2026-10-12T08:00:03Z"
    items[8]["metadata"]["deletionGracePeriodSeconds"] = 30
    pod = pod_of(
        readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0], "runtime-a"
    )
    assert pod["deletionTimestamp"] == {
        "state": "reported",
        "value": "2026-10-12T08:00:03Z",
        "resolution": "second",
    }


def test_a_field_that_the_controller_did_not_write_is_missing(tmp_path: Path) -> None:
    """An Application with no health state is not healthy and not unhealthy."""
    streams = streams_of(
        tmp_path, [{"application": an_application(health=None, sync=None)}]
    )
    application = readings(streams["argo"])[0]["application"]
    assert application["healthStatus"] == MISSING
    assert application["syncStatus"] == MISSING
    assert application["resolvedRevision"] == reported(COMMIT)


def test_an_application_with_no_status_states_no_field_but_what_it_follows(
    tmp_path: Path,
) -> None:
    document = an_application()
    del document["status"]
    application = readings(streams_of(tmp_path, [{"application": document}])["argo"])[
        0
    ]["application"]
    assert application.pop("followedRevision") == reported("main")
    assert set(map(json.dumps, application.values())) == {json.dumps(MISSING)}


@pytest.mark.parametrize(
    "path,value,field",
    [
        (("status", "sync", "status"), "Out Of Sync", "syncStatus"),
        (("status", "sync", "status"), 1, "syncStatus"),
        (("status", "sync", "revision"), "main", "resolvedRevision"),
        (("status", "sync", "revision"), "A" * 40, "resolvedRevision"),
        (("status", "health"), "Healthy", "healthStatus"),
        (("status", "reconciledAt"), "soon", "reconciledAt"),
        (("status", "history"), {"id": 7}, "historyId"),
        (("status", "history"), ["seven"], "historyRevision"),
        (("spec", "source", "targetRevision"), "main branch", "followedRevision"),
    ],
)
def test_a_field_of_the_application_of_another_form_is_malformed(
    tmp_path: Path, path: tuple[str, ...], value: object, field: str
) -> None:
    document = an_application()
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    application = readings(streams_of(tmp_path, [{"application": document}])["argo"])[
        0
    ]["application"]
    assert application[field] == MALFORMED


def test_an_empty_history_is_missing(tmp_path: Path) -> None:
    document = an_application()
    document["status"]["history"] = []
    application = readings(streams_of(tmp_path, [{"application": document}])["argo"])[
        0
    ]["application"]
    for name in timeline.APPLICATION_HISTORY_FIELDS:
        assert application[name] == MISSING


# --------------------------------------------------------------------------
# A read that gave no usable answer
# --------------------------------------------------------------------------


def test_a_workload_read_that_did_not_answer_gives_no_value(tmp_path: Path) -> None:
    streams = streams_of(tmp_path, [{}, {"workload": None}, {}])
    for name, member in (
        ("endpoints", "tiers"),
        ("pods", "pods"),
        ("deployments", "tiers"),
    ):
        reading = readings(streams[name])[1]
        assert reading["read"] == {
            "state": "unanswered",
            "startedAt": instant(5000),
            "finishedAt": instant(5200),
        }
        assert reading[member] is None
        assert reading["faults"] == []
        assert streams[name][-1]["byReadState"] == {
            "answered": 2,
            "absent": 0,
            "unanswered": 1,
            "unreadable": 0,
            "not-taken": 0,
        }
    assert readings(streams["pods"])[1]["otherPods"] is None


def test_the_application_is_read_independently_of_the_workload(tmp_path: Path) -> None:
    """One read that did not answer leaves the other read's stream as it was."""
    whole = streams_of(tmp_path, [{}, {}])
    (tmp_path / "w").mkdir()
    no_workload = streams_of(tmp_path / "w", [{}, {"workload": None}])
    (tmp_path / "a").mkdir()
    no_application = streams_of(tmp_path / "a", [{}, {"application": None}])

    assert readings(no_workload["argo"]) == readings(whole["argo"])
    for name in ("endpoints", "pods", "deployments"):
        assert readings(no_application[name]) == readings(whole[name])
    reading = readings(no_application["argo"])[1]
    assert reading["read"]["state"] == "unanswered"
    assert reading["application"] is None


def test_an_application_that_is_absent_is_an_answer_with_no_object(
    tmp_path: Path,
) -> None:
    streams = streams_of(tmp_path, [{"application": ""}, {"application": "\n"}])
    for reading in readings(streams["argo"]):
        assert reading["read"]["state"] == "absent"
        assert reading["application"] is None
        assert reading["faults"] == []
    assert streams["argo"][-1]["byReadState"]["absent"] == 2


def test_an_empty_workload_answer_is_not_an_empty_namespace(tmp_path: Path) -> None:
    """Only the Application read answers an absent object with no output."""
    reading = readings(streams_of(tmp_path, [{"workload": ""}])["pods"])[0]
    assert reading["read"]["state"] == "unreadable"
    assert reading["pods"] is None
    assert reading["faults"] == ["the answer is not one JSON object"]


def test_a_namespace_with_no_object_is_a_reading(tmp_path: Path) -> None:
    """An answered list with no item is a reading: no pod, and two refused tiers."""
    streams = streams_of(tmp_path, [{"workload": []}])
    pods = readings(streams["pods"])[0]
    assert (pods["pods"], pods["otherPods"], pods["faults"]) == ([], 0, [])
    deployments = readings(streams["deployments"])[0]
    assert [tier["state"] for tier in deployments["tiers"]] == ["refused", "refused"]
    assert set(deployments["tiers"][0]) == {"tier", "state"}
    assert len(deployments["faults"]) == 2
    endpoints = readings(streams["endpoints"])[0]
    assert [tier["state"] for tier in endpoints["tiers"]] == ["refused", "refused"]
    assert endpoints["tiers"][0]["endpoints"] is None


@pytest.mark.parametrize(
    "answer,fault",
    [
        ("{", "the answer is not one JSON object"),
        ("[]", "the answer is not one JSON object"),
        ('{"kind": "PodList", "items": []}', "the answer is not a list of objects"),
        ('{"kind": "List"}', "the answer is not a list of objects"),
        (
            '{"kind": "List", "items": [{"kind": "Secret"}]}',
            "item 0 is not an object of a kind that was asked for",
        ),
        (
            '{"kind": "List", "items": ["pod"]}',
            "item 0 is not an object of a kind that was asked for",
        ),
    ],
)
def test_a_workload_answer_that_is_not_a_list_of_the_kinds_gives_no_value(
    tmp_path: Path, answer: str, fault: str
) -> None:
    streams = streams_of(tmp_path, [{"workload": answer}])
    for name, member in (
        ("endpoints", "tiers"),
        ("pods", "pods"),
        ("deployments", "tiers"),
    ):
        reading = readings(streams[name])[0]
        assert reading[member] is None
        assert reading["faults"] == [fault]


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "AppProject"},
        {"metadata": {"name": "another", "namespace": APPLICATION_NAMESPACE}},
        {"metadata": {"name": APPLICATION, "namespace": "default"}},
        {"metadata": None},
    ],
)
def test_an_answer_that_is_not_the_named_application_gives_no_field(
    tmp_path: Path, change: dict[str, Any]
) -> None:
    reading = readings(
        streams_of(tmp_path, [{"application": {**an_application(), **change}}])["argo"]
    )[0]
    assert reading["read"]["state"] == "answered"
    assert reading["application"] is None
    assert reading["faults"] == [
        "the answer is not the Application that the collection names"
    ]


@pytest.mark.parametrize(
    "meta",
    [
        {"workloadStartedAt": "2026-10-12T08:00:00Z"},
        {"workloadFinishedAt": ""},
        {"workloadStartedAt": instant(900), "workloadFinishedAt": instant(100)},
        {"workloadStartedAt": "2026-10-12T08:00:00.3NZ"},
    ],
)
def test_a_read_with_no_usable_instants_has_no_place_on_a_timeline(
    tmp_path: Path, meta: dict[str, str]
) -> None:
    streams = streams_of(tmp_path, [{"meta": meta}])
    reading = readings(streams["pods"])[0]
    assert reading["read"] == {
        "state": "unreadable",
        "startedAt": None,
        "finishedAt": None,
    }
    assert reading["pods"] is None
    assert reading["faults"] == ["the sample states no usable instants for this read"]
    assert readings(streams["argo"])[0]["read"]["state"] == "answered"


def test_a_read_whose_state_the_sample_does_not_give_is_unreadable(
    tmp_path: Path,
) -> None:
    streams = streams_of(tmp_path, [{"meta": {"workloadRead": "ok"}}])
    reading = readings(streams["endpoints"])[0]
    assert reading["read"]["state"] == "unreadable"
    assert reading["tiers"] is None


def test_an_answer_the_sample_states_and_the_directory_lacks_is_unreadable(
    tmp_path: Path,
) -> None:
    directory = write_collection(tmp_path, [{}])
    (directory / "sample-0001.workload.json").unlink()
    reading = readings(timeline.build_streams(directory)["deployments"])[0]
    assert reading["read"]["state"] == "unreadable"
    assert reading["tiers"] is None


def test_a_sample_that_was_not_taken_is_a_reading_with_no_instant(
    tmp_path: Path,
) -> None:
    streams = streams_of(tmp_path, [{}, {"skip": True}, {}])
    for name in timeline.STREAMS:
        reading = readings(streams[name])[1]
        assert reading["read"] == {
            "state": "not-taken",
            "startedAt": None,
            "finishedAt": None,
        }
        assert streams[name][-1]["byReadState"]["not-taken"] == 1


# --------------------------------------------------------------------------
# Objects that cannot be read without a guess
# --------------------------------------------------------------------------


def _pod_fault(change: Any) -> list[dict[str, Any]]:
    items = workload()
    change(items)
    return items


@pytest.mark.parametrize(
    "change",
    [
        lambda items: items[8]["metadata"].update(uid="not-a-uid"),
        lambda items: items[8]["metadata"].update(name="Runtime_A"),
        lambda items: items[8]["metadata"].update(namespace="default"),
        lambda items: items[8].update(metadata=None),
        lambda items: items[8]["metadata"].update(labels=["a"]),
        lambda items: items[8]["metadata"].update(labels={"a": 1}),
        lambda items: items[9]["metadata"].update(uid=uid(11)),
        lambda items: items[9]["metadata"].update(name="runtime-a"),
        lambda items: items[5]["metadata"].update(uid="x"),
    ],
)
def test_a_pod_read_with_an_object_that_has_no_identity_states_no_pod(
    tmp_path: Path, change: Any
) -> None:
    streams = streams_of(tmp_path, [{"workload": _pod_fault(change)}])
    reading = readings(streams["pods"])[0]
    assert reading["read"]["state"] == "answered"
    assert reading["pods"] is None
    assert reading["otherPods"] is None
    assert reading["faults"]
    # The Deployment read of the same sample is not refused by a pod.
    assert readings(streams["deployments"])[0]["tiers"] is not None


def test_a_reading_with_more_pods_than_the_bound_states_no_pod(tmp_path: Path) -> None:
    items = workload() + [
        a_pod(f"extra-{number}", 1000 + number, API, owner=None)
        for number in range(timeline.MAX_PODS - 3)
    ]
    reading = readings(streams_of(tmp_path, [{"workload": items}])["pods"])[0]
    assert reading["pods"] is None
    assert reading["faults"] == [
        f"the read holds {timeline.MAX_PODS + 1} pods of the two tiers"
    ]
    (tmp_path / "b").mkdir()
    reading = readings(streams_of(tmp_path / "b", [{"workload": items[:-1]}])["pods"])[
        0
    ]
    assert len(reading["pods"]) == timeline.MAX_PODS


def test_a_pod_that_is_not_of_the_two_tiers_is_counted_and_not_listed(
    tmp_path: Path,
) -> None:
    job = a_pod("acquire-model-x", 31, "model-acquisition", owner=None)
    other = a_pod("stranger", 32, API, owner=None)
    other["metadata"]["labels"]["app.kubernetes.io/instance"] = "another-release"
    bare = a_pod("bare", 33, API, owner=None)
    del bare["metadata"]["labels"]
    reading = readings(
        streams_of(tmp_path, [{"workload": [*workload(), job, other, bare]}])["pods"]
    )[0]
    assert reading["otherPods"] == 3
    assert len(reading["pods"]) == 4
    assert "acquire-model-x" not in json.dumps(reading)


def test_a_tier_with_no_one_deployment_states_no_count(tmp_path: Path) -> None:
    none = [item for item in workload() if item["metadata"].get("uid") != uid(211)]
    reading = readings(streams_of(tmp_path, [{"workload": none}])["deployments"])[0]
    assert tier_of(reading, RUNTIME) == {"tier": RUNTIME, "state": "refused"}
    assert tier_of(reading, API)["state"] == "observed"
    assert reading["faults"] == [
        "serving-runtime: no Deployment of the release inferops carry this component label"
    ]
    (tmp_path / "b").mkdir()
    two = [*workload(), a_deployment("second", 212, RUNTIME)]
    reading = readings(streams_of(tmp_path / "b", [{"workload": two}])["deployments"])[
        0
    ]
    assert tier_of(reading, RUNTIME) == {"tier": RUNTIME, "state": "refused"}
    assert "2 Deployments" in reading["faults"][0]


def test_an_endpoint_refusal_of_one_tier_is_stated_with_its_rule(
    tmp_path: Path,
) -> None:
    items = [
        item
        for item in workload()
        if not (
            item["kind"] == "EndpointSlice"
            and item["metadata"]["name"].startswith(RUNTIME_NAME)
        )
    ]
    reading = readings(streams_of(tmp_path, [{"workload": items}])["endpoints"])[0]
    assert tier_of(reading, RUNTIME)["state"] == "refused"
    assert tier_of(reading, RUNTIME)["endpoints"] is None
    assert tier_of(reading, API)["endpoints"]["ready"] == 2
    assert reading["faults"][0].startswith("the-service-has-a-slice: serving-runtime")


def test_an_endpoint_that_does_not_state_ready_is_not_read_as_ready(
    tmp_path: Path,
) -> None:
    items = workload()
    del items[3]["endpoints"][0]["conditions"]["ready"]
    reading = readings(streams_of(tmp_path, [{"workload": items}])["endpoints"])[0]
    assert tier_of(reading, RUNTIME)["state"] == "refused"
    assert reading["faults"][0].startswith("each-endpoint-states-its-conditions")


def test_the_faults_of_a_reading_are_bounded_and_hold_fixed_characters(
    tmp_path: Path,
) -> None:
    items = workload()
    for number in range(30):
        pod = a_pod(f"p-{number}", 500 + number, API, owner=None)
        pod["metadata"]["namespace"] = "elsewhere"
        items.append(pod)
    items[0]["metadata"]["labels"]["x" * 400 + chr(0x2028) + "<script>"] = 7
    streams = streams_of(tmp_path, [{"workload": items}])
    pod_faults = readings(streams["pods"])[0]["faults"]
    assert len(pod_faults) == 11
    assert pod_faults[-1] == "20 more fault(s) are not listed"
    for fault in readings(streams["endpoints"])[0]["faults"]:
        assert len(fault) <= 240
        assert re.fullmatch(r"[A-Za-z0-9 .,:;_/'()?-]+", fault), fault


# --------------------------------------------------------------------------
# Safe identities
# --------------------------------------------------------------------------


def test_no_stream_holds_a_value_that_the_allowlist_does_not_read(
    tmp_path: Path,
) -> None:
    directory = write_collection(tmp_path, [{}, {}])
    answers = "".join(
        path.read_text("utf-8") for path in sorted(directory.glob("sample-*.json"))
    )
    text = "".join(
        timeline.stream_text(lines)
        for lines in timeline.build_streams(directory).values()
    )
    for value in HOSTILE:
        assert value in answers, value
        assert value not in text, value
    assert "kind-inferops-dev" not in text
    assert "context" not in {
        key for line in text.splitlines() for key in json.loads(line)
    }


def test_a_text_value_of_another_form_is_not_copied_into_a_stream(
    tmp_path: Path,
) -> None:
    """A value the allowlist reads is still held to a form before it is stored."""
    secret = "ghp_" + "A1b2" * 9
    items = workload()
    items[8]["metadata"]["labels"]["pod-template-hash"] = secret
    items[8]["status"]["phase"] = secret
    items[8]["status"]["containerStatuses"][0]["name"] = secret
    items[8]["metadata"]["ownerReferences"][0]["name"] = secret
    items[-1]["status"]["conditions"][0]["reason"] = "has spaces " + secret
    document = an_application()
    document["status"]["health"]["status"] = "x " + secret
    document["spec"]["source"]["targetRevision"] = "https://user:" + secret + "@host/x"
    streams = streams_of(tmp_path, [{"workload": items, "application": document}])
    text = "".join(timeline.stream_text(lines) for lines in streams.values())
    assert secret not in text
    pod = pod_of(readings(streams["pods"])[0], "runtime-a")
    assert pod["templateHash"] == pod["phase"] == pod["owner"] == MALFORMED
    assert pod["containers"]["value"][0]["name"] == MALFORMED


# --------------------------------------------------------------------------
# The stored text, and reading it back
# --------------------------------------------------------------------------


def test_one_collection_gives_one_text(tmp_path: Path) -> None:
    directory = write_collection(
        tmp_path, [{}, {"workload": None}, {"application": ""}]
    )
    first = {
        name: timeline.stream_text(lines)
        for name, lines in timeline.build_streams(directory).items()
    }
    second = {
        name: timeline.stream_text(lines)
        for name, lines in timeline.build_streams(directory).items()
    }
    assert first == second
    for text in first.values():
        assert text.endswith("\n") and "\r" not in text
        lines = text.splitlines()
        assert len(lines) == 5
        for line in lines:
            document = json.loads(line)
            assert line == json.dumps(document, sort_keys=True, separators=(",", ":"))


def test_the_order_of_the_objects_in_an_answer_does_not_change_a_stream(
    tmp_path: Path,
) -> None:
    forwards = streams_of(tmp_path, [{"workload": workload()}])
    (tmp_path / "b").mkdir()
    backwards = streams_of(tmp_path / "b", [{"workload": workload()[::-1]}])
    assert forwards == backwards


def test_each_built_stream_is_read_back(tmp_path: Path) -> None:
    streams = streams_of(tmp_path, [{}, {"workload": None}, {"skip": True}])
    for name, lines in streams.items():
        stored = timeline.read_stream(timeline.stream_text(lines))
        assert stored.name == name
        assert list(stored.readings) == readings(lines)
        assert stored.end == lines[-1]
    assert (
        timeline.read_stream(timeline.stream_text(streams["pods"])).summary()
        == "pods: 3 reading(s): 1 answered, 1 unanswered, 1 not-taken"
    )


def _stored_lines(tmp_path: Path) -> list[dict[str, Any]]:
    return copy.deepcopy(streams_of(tmp_path, [{}, {}])["pods"])


def _text(lines: list[dict[str, Any]]) -> str:
    return timeline.stream_text(lines)


@pytest.mark.parametrize(
    "rule,change",
    [
        ("timeline-stream-unreadable", lambda lines: _text(lines) + "{\n"),
        ("timeline-stream-unreadable", lambda lines: _text(lines) + "[]\n"),
        (
            "timeline-stream-unreadable",
            lambda lines: _text(lines).replace('{"faults"', '{"index":1,"faults"', 1),
        ),
        ("timeline-header-unsupported", lambda lines: ""),
        ("timeline-header-unsupported", lambda lines: _text(lines[1:])),
        (
            "timeline-header-unsupported",
            lambda lines: _text([{**lines[0], "schema": "x"}, *lines[1:]]),
        ),
        (
            "timeline-header-unsupported",
            lambda lines: _text([{**lines[0], "stream": "nodes"}, *lines[1:]]),
        ),
        (
            "timeline-header-unsupported",
            lambda lines: _text([{**lines[0], "runId": "a b"}, *lines[1:]]),
        ),
        (
            "timeline-members-unsupported",
            lambda lines: _text([{**lines[0], "note": "x"}, *lines[1:]]),
        ),
        (
            "timeline-members-unsupported",
            lambda lines: _text([lines[0], {**lines[1], "nodes": []}, *lines[2:]]),
        ),
        (
            "timeline-members-unsupported",
            lambda lines: _text(
                [
                    lines[0],
                    {k: v for k, v in lines[1].items() if k != "otherPods"},
                    *lines[2:],
                ]
            ),
        ),
        (
            "timeline-members-unsupported",
            lambda lines: _text(
                [lines[0], {**lines[1], "read": {"state": "answered"}}, *lines[2:]]
            ),
        ),
        (
            "timeline-members-unsupported",
            lambda lines: _text([*lines[:-1], {**lines[-1], "verdict": "ok"}]),
        ),
        (
            "timeline-reading-out-of-sequence",
            lambda lines: _text([lines[0], lines[2], lines[1], lines[3]]),
        ),
        (
            "timeline-reading-out-of-sequence",
            lambda lines: _text([lines[0], lines[2], lines[3]]),
        ),
        (
            "timeline-reading-out-of-sequence",
            lambda lines: _text([lines[0], lines[1], lines[3], lines[2], lines[3]]),
        ),
        (
            "timeline-read-state-unsupported",
            lambda lines: _text(
                [
                    lines[0],
                    {**lines[1], "read": {**lines[1]["read"], "state": "healthy"}},
                    *lines[2:],
                ]
            ),
        ),
        (
            "timeline-instant-invalid",
            lambda lines: _text(
                [
                    lines[0],
                    {
                        **lines[1],
                        "read": {
                            **lines[1]["read"],
                            "startedAt": "2026-10-12T08:00:00Z",
                        },
                    },
                    *lines[2:],
                ]
            ),
        ),
        (
            "timeline-instant-invalid",
            lambda lines: _text(
                [
                    lines[0],
                    {**lines[1], "read": {**lines[1]["read"], "finishedAt": None}},
                    *lines[2:],
                ]
            ),
        ),
        (
            "timeline-instant-invalid",
            lambda lines: _text(
                [
                    lines[0],
                    {
                        **lines[1],
                        "read": {
                            **lines[1]["read"],
                            "finishedAt": "2026-10-12T07:00:00.000Z",
                        },
                    },
                    *lines[2:],
                ]
            ),
        ),
        ("timeline-end-missing", lambda lines: _text(lines[:-1])),
        ("timeline-end-missing", lambda lines: _text(lines[:1])),
        (
            "timeline-counts-differ",
            lambda lines: _text([*lines[:-1], {**lines[-1], "readings": 3}]),
        ),
        (
            "timeline-counts-differ",
            lambda lines: _text(
                [
                    *lines[:-1],
                    {
                        **lines[-1],
                        "byReadState": {**lines[-1]["byReadState"], "answered": 1},
                    },
                ]
            ),
        ),
    ],
)
def test_a_text_that_does_not_have_the_form_of_a_stream_is_refused(
    tmp_path: Path, rule: str, change: Any
) -> None:
    with pytest.raises(timeline.StreamRefused) as refused:
        timeline.read_stream(change(_stored_lines(tmp_path)))
    assert refused.value.rule == rule
    assert rule in timeline.RULES


def test_each_rule_has_a_case_that_refuses_by_it() -> None:
    marks = test_a_text_that_does_not_have_the_form_of_a_stream_is_refused.pytestmark
    [cases] = [mark.args[1] for mark in marks if mark.name == "parametrize"]
    assert {case[0] for case in cases} == set(timeline.RULES)


# --------------------------------------------------------------------------
# The two clock observations of the end line
# --------------------------------------------------------------------------


def test_the_end_line_counts_cluster_instants_later_than_their_read(
    tmp_path: Path,
) -> None:
    """A cluster instant after the read that returned it shows two clocks.

    A deletion timestamp is not counted: it is the end of a grace period, so it
    is later than the read on one clock too.
    """
    items = workload()
    items[8]["status"]["conditions"][1]["lastTransitionTime"] = "2026-10-12T08:00:03Z"
    items[9]["metadata"]["deletionTimestamp"] = "2026-10-12T08:00:30Z"
    streams = streams_of(tmp_path, [{"workload": items}])
    assert streams["pods"][-1]["clusterInstantsAfterRead"] == {
        "count": 1,
        "largestMilliseconds": 2800,
    }
    assert streams["deployments"][-1]["clusterInstantsAfterRead"] == {
        "count": 0,
        "largestMilliseconds": None,
    }
    assert streams["endpoints"][-1]["clusterInstantsAfterRead"]["count"] == 0


def test_the_end_line_names_each_reading_that_starts_before_the_one_before_finished(
    tmp_path: Path,
) -> None:
    back = {"workloadStartedAt": instant(100), "workloadFinishedAt": instant(150)}
    streams = streams_of(tmp_path, [{}, {"meta": back}, {}])
    assert streams["pods"][-1]["instantsOutOfOrder"] == [2]
    assert streams["argo"][-1]["instantsOutOfOrder"] == []


# --------------------------------------------------------------------------
# Changes
# --------------------------------------------------------------------------


def changes_of(tmp_path: Path, samples: list[dict[str, Any]], name: str) -> list[dict]:
    lines = streams_of(tmp_path, samples)[name]
    document = timeline.changes(timeline.read_stream(timeline.stream_text(lines)))
    assert document["schema"] == timeline.CHANGES_SCHEMA
    assert document["stream"] == name
    assert document["readings"] == len(samples)
    return document["changes"]


def test_a_stream_with_no_difference_has_no_change(tmp_path: Path) -> None:
    for position, name in enumerate(timeline.STREAMS):
        (tmp_path / str(position)).mkdir()
        assert changes_of(tmp_path / str(position), [{}, {}, {}], name) == []


def test_an_endpoint_change_is_bounded_by_the_two_reads(tmp_path: Path) -> None:
    found = changes_of(
        tmp_path,
        [{}, {"workload": workload(runtime_ready=(True, False))}, {}],
        "endpoints",
    )
    ready = [change for change in found if change["field"] == "ready"]
    assert ready == [
        {
            "subject": RUNTIME,
            "field": "ready",
            "fromReading": 1,
            "toReading": 2,
            "notBefore": instant(0),
            "notAfter": instant(5200),
            "from": reported(2),
            "to": reported(1),
        },
        {
            "subject": RUNTIME,
            "field": "ready",
            "fromReading": 2,
            "toReading": 3,
            "notBefore": instant(5000),
            "notAfter": instant(10200),
            "from": reported(1),
            "to": reported(2),
        },
    ]
    pods = [change for change in found if change["field"] == "readyPods"]
    assert pods[0]["from"] == reported([uid(11), uid(12)])
    assert pods[0]["to"] == reported([uid(11)])
    assert {change["subject"] for change in found} == {RUNTIME}


def test_a_pod_that_left_and_a_pod_that_entered_are_two_changes(tmp_path: Path) -> None:
    """No change says that one pod replaced the other."""
    after = [item for item in workload() if item["metadata"]["name"] != "runtime-b"]
    after.append(
        a_pod("runtime-c", 13, RUNTIME, owner=("runtime-rs", 111), ready="False")
    )
    found = changes_of(tmp_path, [{}, {"workload": after}], "pods")
    assert [(change["subject"], change["field"]) for change in found] == [
        (uid(12), "present"),
        (uid(13), "present"),
    ]
    left, entered = found
    assert left["from"] == reported({"name": "runtime-b", "tier": RUNTIME})
    assert left["to"] == {"state": "absent"}
    assert entered["from"] == {"state": "absent"}
    assert entered["to"] == reported({"name": "runtime-c", "tier": RUNTIME})
    assert "replac" not in json.dumps(found)


def test_a_restart_and_a_readiness_change_of_one_pod_are_changes(
    tmp_path: Path,
) -> None:
    after = workload(runtime_ready=(False, True))
    after[8]["status"]["containerStatuses"][0]["restartCount"] = 1
    after[8]["metadata"]["deletionTimestamp"] = "2026-10-12T08:00:04Z"
    found = changes_of(tmp_path, [{}, {"workload": after}], "pods")
    assert {change["field"]: (change["from"], change["to"]) for change in found} == {
        "ready": (reported("True"), reported("False")),
        "restartCount": (reported(0), reported(1)),
        "deletionTimestamp": (
            MISSING,
            {
                "state": "reported",
                "value": "2026-10-12T08:00:04Z",
                "resolution": "second",
            },
        ),
    }
    assert {change["subject"] for change in found} == {uid(11)}


def test_no_value_is_carried_across_a_read_that_did_not_answer(tmp_path: Path) -> None:
    found = changes_of(tmp_path, [{}, {"workload": None}, {}], "deployments")
    ready = [
        change
        for change in found
        if (change["subject"], change["field"]) == (RUNTIME, "readyReplicas")
    ]
    assert [(change["from"], change["to"]) for change in ready] == [
        (reported(2), {"state": "not-collected"}),
        ({"state": "not-collected"}, reported(2)),
    ]
    assert ready[0]["notAfter"] == instant(5200)


def test_two_readings_with_no_value_have_no_change_between_them(tmp_path: Path) -> None:
    found = changes_of(tmp_path, [{"workload": None}, {"workload": "{"}], "pods")
    assert found == []


def test_a_count_that_stops_being_reported_is_a_change_to_missing(
    tmp_path: Path,
) -> None:
    """The change does not say that the count became zero."""
    found = changes_of(
        tmp_path,
        [{}, {"workload": workload(runtime_deployment_ready=None)}],
        "deployments",
    )
    assert {change["field"]: change["to"] for change in found} == {
        "readyReplicas": MISSING,
        "availableReplicas": MISSING,
    }


def test_a_tier_that_becomes_refused_states_no_count(tmp_path: Path) -> None:
    none = [item for item in workload() if item["metadata"].get("uid") != uid(211)]
    found = changes_of(tmp_path, [{}, {"workload": none}], "deployments")
    by_field = {change["field"]: change["to"] for change in found}
    assert by_field["state"] == reported("refused")
    assert by_field["readyReplicas"] == {"state": "refused"}


def test_a_sync_change_and_an_absent_application_are_changes(tmp_path: Path) -> None:
    drifted = an_application(sync="OutOfSync", health="Degraded")
    drifted["status"]["sync"]["revision"] = OTHER_COMMIT
    found = changes_of(
        tmp_path, [{}, {"application": drifted}, {"application": ""}], "argo"
    )
    first = {c["field"]: (c["from"], c["to"]) for c in found if c["toReading"] == 2}
    assert first == {
        "syncStatus": (reported("Synced"), reported("OutOfSync")),
        "healthStatus": (reported("Healthy"), reported("Degraded")),
        "resolvedRevision": (reported(COMMIT), reported(OTHER_COMMIT)),
    }
    assert first and found[0]["notBefore"] == instant(250)
    second = [c for c in found if c["toReading"] == 3]
    assert [(c["field"], c["from"], c["to"]) for c in second] == [
        ("present", reported(True), reported(False))
    ]


def test_an_application_read_that_is_refused_carries_no_value(tmp_path: Path) -> None:
    other = {**an_application(), "kind": "AppProject"}
    found = changes_of(tmp_path, [{}, {"application": other}], "argo")
    assert {json.dumps(change["to"]) for change in found} == {'{"state": "refused"}'}
    assert ("application", "syncStatus") in {
        (change["subject"], change["field"]) for change in found
    }


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_prints_one_stream_in_lf_bytes(
    tmp_path: Path, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    directory = write_collection(tmp_path, [{}, {"workload": None}])
    for name in timeline.STREAMS:
        assert main(["stream", str(directory), name]) == 0
        printed = capfdbinary.readouterr().out
        assert b"\r" not in printed
        assert printed.decode("utf-8") == timeline.stream_text(
            timeline.build_streams(directory)[name]
        )


def test_the_command_refuses_a_directory_that_is_not_a_collection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["stream", str(tmp_path), "pods"]) == timeline.REFUSED_EXIT == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "REFUSED  not-a-collection" in captured.err


def test_the_command_checks_and_prints_changes_of_stored_streams(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    streams = streams_of(
        tmp_path, [{}, {"workload": workload(runtime_ready=(True, False))}]
    )
    files = []
    for name, lines in streams.items():
        path = tmp_path / timeline.STREAM_FILES[name]
        path.write_bytes(timeline.stream_text(lines).encode("utf-8"))
        files.append(str(path))
    assert main(["check", *files]) == 0
    printed = capfd.readouterr().out
    assert "READ     endpoints: 2 reading(s): 2 answered" in printed
    assert printed.count("READ") == 4

    assert main(["changes", files[0]]) == 0
    document = json.loads(capfd.readouterr().out)
    assert document["stream"] == "endpoints"
    assert document["changes"]

    broken = tmp_path / "broken.jsonl"
    broken.write_text("{}\n", "utf-8")
    binary = tmp_path / "binary.jsonl"
    binary.write_bytes(b"\xff\xfe")
    assert main(["check", files[0], str(broken), str(binary)]) == 3
    captured = capfd.readouterr()
    assert "READ     endpoints" in captured.out
    assert "REFUSED  broken.jsonl: timeline-header-unsupported" in captured.err
    assert "REFUSED  binary.jsonl: timeline-stream-unreadable" in captured.err
    assert main(["changes", str(tmp_path / "absent.jsonl")]) == 3


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["stream"],
        ["stream", "x"],
        ["stream", "x", "nodes"],
        ["check"],
        ["build", "x"],
    ],
)
def test_arguments_that_are_not_usable_exit_2(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(arguments)
    assert stopped.value.code == 2


# --------------------------------------------------------------------------
# The evidence layout, and the published page
# --------------------------------------------------------------------------


def test_each_stream_is_a_registered_raw_role_with_a_hashed_suffix() -> None:
    """A run directory can name each stream file under a role of the same name."""
    for name in timeline.STREAMS:
        assert ROLES[name].kind == RAW, name
        assert Path(timeline.STREAM_FILES[name]).suffix in EVIDENCE_SUFFIXES


def _flat(text: str) -> str:
    return " ".join(text.replace("`", "").split())


def test_the_page_publishes_each_rule_limit_and_boundary_of_the_tool() -> None:
    page = _flat(PAGE.read_text(encoding="utf-8"))
    for rule, statement in timeline.RULES.items():
        assert rule in page, rule
        assert _flat(statement) in page, rule
    for statement in (
        *timeline.LIMITATIONS,
        *timeline.DOES_NOT_ESTABLISH,
        *timeline.OMITTED,
    ):
        assert _flat(statement) in page, statement
    for name in (
        *timeline.STREAMS,
        *timeline.READ_STATES,
        *timeline.FIELD_STATES,
        *timeline.APPLICATION_FIELDS,
        *timeline.APPLICATION_HISTORY_FIELDS,
        *timeline.DEPLOYMENT_COUNTS,
        *timeline.POD_CHANGE_FIELDS,
    ):
        assert re.search(
            rf"(?<![A-Za-z0-9-]){re.escape(name)}(?![A-Za-z0-9-])", page
        ), name
    for bound in (
        timeline.MAX_SAMPLES,
        timeline.MAX_INTERVAL_SECONDS,
        timeline.MAX_PODS,
        timeline.MAX_CONTAINERS,
    ):
        assert str(bound) in page, bound
