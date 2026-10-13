"""The reliability metrics of an experiment run, from evidence built here.

``tools.reliability_analysis`` reads a caller record, timeline streams, a log
of operator events, and a declaration, and it returns one analysis document.
This suite builds the inputs. The timeline tool builds each stream from a
collection that the suite invents, and the events tool writes each log. The
suite writes each caller record itself, and the runner's reader accepts it. No
runner wrote one. The suite reads no cluster and sends no request.

The suite holds the tool to these properties.

*Each definition is held to its instants, and an interval states its ends.* A
failure episode starts at the completion of its first failed request and ends
at the completion of the next successful request. A success gap is between two
consecutive successful completions. An episode, a gap, an interval, a lag, and
a stabilization span name the request or the reading at each end. A
disagreement time and a total are sums and name no end.

*A sampled state has two figures.* The inner figure is between the first and
the last consecutive read that gave the state. The outer figure is between the
nearest reads on each side that gave another state.

*A value that was not read is not a value.* An open episode has no duration. A
reading that did not answer, a count that the API omitted, and a stream that
was not given are not zero and are not healthy.

*The analysis decides no result.* An analysis document holds no result state,
no percentage, and no confidence interval. An aggregate document repeats the
result state that it was given for each run. The aggregate is the median of three
counted runs, and a counted run with no value is not dropped.

*A result state alone leaves no run out.* A run in the state INCONCLUSIVE,
REFUSED, or ABORTED is not counted only for a reason that its exclusion reasons
register for the experiment, the state, and the run. The aggregate states that
reason. A reason that is absent, changed, or registered for another state,
another run, or another experiment refuses the aggregate, and so does a state
with no reason at all.

Six cases are committed under ``tests/domain/fixtures/reliability-analysis``:
zero failure, concurrency, missing signal, open episode, clock ties, and abort.
Each is the inputs and the analysis document. The suite builds each case again
and compares it with the committed files. To write the files again, run this
module as a script.

These tests show what the tool computes from files. Each file is synthetic. No
test here is evidence of a run, of a failure, or of a recovery.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT))

from tools import experiment_events as events  # noqa: E402
from tools import experiment_timeline as timeline  # noqa: E402
from tools import reliability_analysis as analysis  # noqa: E402
from tools.experiment_evidence import DERIVED, ROLES  # noqa: E402
from tools.reliability_analysis.__main__ import main  # noqa: E402
from tools.reliability_runner import build_plan, read_record  # noqa: E402

pytestmark = pytest.mark.unit

PAGE = REPO_ROOT / "docs" / "testing" / "reliability-analysis.md"
FIXTURES = REPO_ROOT / "tests" / "domain" / "fixtures" / "reliability-analysis"

EXPERIMENT = "example-experiment"
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
WINDOW_MS = 150_000


def at(offset_ms: int) -> str:
    return timeline.format_instant(T0 + timedelta(milliseconds=offset_ms))


# --------------------------------------------------------------------------
# A caller record
# --------------------------------------------------------------------------


def request(
    sequence: int, worker: int, start: int, finish: int, ok: bool = True
) -> dict[str, Any]:
    """One request, with its two instants as milliseconds after ``T0``."""
    return {
        "sequence": sequence,
        "worker": worker,
        "start": start,
        "finish": finish,
        "ok": ok,
    }


def caller_text(
    run_id: str,
    requests: list[dict[str, Any]],
    *,
    started: int = 0,
    finished: int = WINDOW_MS,
    interrupted: bool = False,
    experiment_id: str = EXPERIMENT,
) -> str:
    """A caller record with one line for each request, in the order given."""
    plan = build_plan(
        experiment_id=experiment_id,
        run_id=run_id,
        duration_seconds=max(1, (finished - started) // 1000),
    )
    header: dict[str, Any] = {
        "record": "header",
        "schemaVersion": "inferops.io/reliability-caller-record/v1alpha1",
        **{
            name: plan[name]
            for name in (
                "mode",
                "experimentId",
                "runId",
                "boundary",
                "profile",
                "release",
                "target",
                "success",
                "bounds",
            )
        },
        "concurrency": plan["caller"]["concurrency"],
        "requestTimeoutMs": plan["timeouts"]["requestTimeoutMs"],
        "planSha256": "1" * 64,
        "runnerSha256": "2" * 64,
        "promptText": False,
        "completionText": False,
        "startedAt": at(started),
    }
    model = header["success"]["requiredModelRef"]
    lines: list[dict[str, Any]] = [header]
    outcomes = {"success": 0, "http-error": 0}
    for entry in requests:
        ok = entry["ok"]
        outcomes["success" if ok else "http-error"] += 1
        lines.append(
            {
                "record": "request",
                "sequence": entry["sequence"],
                "worker": entry["worker"],
                "requestId": f"{run_id}-{entry['sequence']:05d}",
                "experimentId": experiment_id,
                "runId": run_id,
                "releaseId": None,
                "startedAt": at(entry["start"]),
                "finishedAt": at(entry["finish"]),
                "latencyMs": entry["finish"] - entry["start"],
                "success": ok,
                "outcome": "success" if ok else "http-error",
                "httpStatus": 200 if ok else 503,
                "errorCode": None if ok else "adapter-unavailable",
                "errorCondition": None if ok else "runtime-unreachable",
                "finishReason": "stop" if ok else None,
                "inputTokens": 30 if ok else None,
                "outputTokens": 40 if ok else None,
                "adapterKind": "real",
                "modelRef": model,
            }
        )
    lines.append(
        {
            "record": "end",
            "experimentId": experiment_id,
            "runId": run_id,
            "endState": "interrupted" if interrupted else "duration",
            "dispatched": len(requests),
            "recorded": len(requests),
            "outcomes": {
                "success": outcomes["success"],
                "http-error": outcomes["http-error"],
                "invalid-response": 0,
                "timeout": 0,
                "transport-error": 0,
                "identity-refused": 0,
            },
            "elapsedMs": finished - started,
            "finishedAt": at(finished),
        }
    )
    text = "".join(
        json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n" for line in lines
    )
    read_record(text)
    return text


def closed_loop(
    end: int,
    fails: Callable[[int, int], bool] = lambda worker, start: False,
    *,
    offsets: tuple[int, int] = (0, 500),
    latency: int = 3000,
    failure_latency: int = 200,
) -> list[dict[str, Any]]:
    """The requests of two closed-loop workers, in the order of completion.

    A request takes ``latency`` when it succeeds. A request that
    ``fails(worker, start)`` takes ``failure_latency``, and its worker then
    waits 1,000 ms. A request that would finish after ``end`` is not sent.
    """
    sent: list[tuple[int, int, int, bool]] = []
    for worker, offset in enumerate(offsets):
        start = offset
        while True:
            failed = fails(worker, start)
            finish = start + (failure_latency if failed else latency)
            if finish > end:
                break
            sent.append((start, worker, finish, not failed))
            start = finish + (1000 if failed else 0)
    numbered = {
        (start, worker): number
        for number, (start, worker, _, _) in enumerate(sorted(sent), start=1)
    }
    return [
        request(numbered[start, worker], worker, start, finish, ok)
        for start, worker, finish, ok in sorted(sent, key=lambda e: (e[2], e[1]))
    ]


# --------------------------------------------------------------------------
# Timeline streams, built by the timeline tool from a collection
# --------------------------------------------------------------------------


def uid(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012d}"


def labels(tier: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/instance": RELEASE,
        "app.kubernetes.io/component": tier,
    }


def _tier_objects(
    name: str, tier: str, base: int, ready: int, replicas: int | None
) -> list[dict[str, Any]]:
    """The objects of one tier with two pods, of which ``ready`` are Ready.

    ``replicas`` is the readyReplicas count of the Deployment. None leaves the
    count out, as the API does for a count of zero.
    """
    pods = [(f"{tier}-a", base + 1, ready >= 1), (f"{tier}-b", base + 2, ready >= 2)]
    status: dict[str, Any] = {
        "observedGeneration": 3,
        "replicas": 2,
        "updatedReplicas": 2,
    }
    if replicas is not None:
        status["readyReplicas"] = replicas
        status["availableReplicas"] = replicas
    return [
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": NAMESPACE, "labels": labels(tier)},
            "spec": {"type": "ClusterIP", "clusterIP": "10.96.0.7"},
        },
        {
            "apiVersion": "discovery.k8s.io/v1",
            "kind": "EndpointSlice",
            "metadata": {
                "name": f"{name}-abcde",
                "namespace": NAMESPACE,
                "labels": {
                    "kubernetes.io/service-name": name,
                    "endpointslice.kubernetes.io/managed-by": (
                        "endpointslice-controller.k8s.io"
                    ),
                },
            },
            "addressType": "IPv4",
            "endpoints": [
                {
                    "addresses": ["10.1.0.7"],
                    "conditions": {
                        "ready": is_ready,
                        "serving": is_ready,
                        "terminating": False,
                    },
                    "targetRef": {
                        "kind": "Pod",
                        "name": pod,
                        "namespace": NAMESPACE,
                        "uid": uid(number),
                    },
                }
                for pod, number, is_ready in pods
            ],
        },
        {
            "apiVersion": "apps/v1",
            "kind": "ReplicaSet",
            "metadata": {
                "name": f"{tier}-rs",
                "namespace": NAMESPACE,
                "uid": uid(base + 100),
                "labels": labels(tier),
                "annotations": {"deployment.kubernetes.io/revision": "4"},
            },
        },
        *[
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": pod,
                    "namespace": NAMESPACE,
                    "uid": uid(number),
                    "creationTimestamp": "2026-10-12T07:59:00Z",
                    "labels": labels(tier) | {"pod-template-hash": "5d4f8c7b9"},
                    "ownerReferences": [
                        {
                            "kind": "ReplicaSet",
                            "name": f"{tier}-rs",
                            "uid": uid(base + 100),
                            "controller": True,
                        }
                    ],
                },
                "spec": {"containers": [{"name": "main"}]},
                "status": {
                    "phase": "Running",
                    "conditions": [
                        {
                            "type": "Ready",
                            "status": "True" if is_ready else "False",
                            "lastTransitionTime": "2026-10-12T07:59:30Z",
                        }
                    ],
                    "containerStatuses": [
                        {"name": "main", "ready": is_ready, "restartCount": 0}
                    ],
                },
            }
            for pod, number, is_ready in pods
        ],
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": NAMESPACE,
                "uid": uid(base + 200),
                "generation": 3,
                "labels": labels(tier),
                "annotations": {"deployment.kubernetes.io/revision": "4"},
            },
            "spec": {"replicas": 2},
            "status": status,
        },
    ]


_SAME = object()


def sample(
    *,
    runtime: int = 2,
    api: int = 2,
    runtime_replicas: object = _SAME,
    sync: str | None = "Synced",
    health: str | None = "Healthy",
    revision: str = COMMIT,
    workload: bool = True,
    application: bool = True,
) -> dict[str, Any]:
    """One sample: the Ready counts of the two tiers, and the Application.

    The readyReplicas count of the runtime Deployment is the Ready count, and
    it is left out when that count is zero. ``workload`` and ``application``
    say whether each read answered.
    """
    if runtime_replicas is _SAME:
        runtime_replicas = runtime or None
    assert runtime_replicas is None or isinstance(runtime_replicas, int)
    status: dict[str, Any] = {"sync": {"revision": revision}}
    if sync is not None:
        status["sync"]["status"] = sync
    if health is not None:
        status["health"] = {"status": health}
    return {
        "workload": [
            *_tier_objects(API_NAME, API, 0, api, api or None),
            *_tier_objects(RUNTIME_NAME, RUNTIME, 10, runtime, runtime_replicas),
        ]
        if workload
        else None,
        "application": {
            "kind": "Application",
            "metadata": {"name": APPLICATION, "namespace": APPLICATION_NAMESPACE},
            "spec": {"source": {"targetRevision": "main"}},
            "status": status,
        }
        if application
        else None,
    }


def streams(
    root: Path,
    run_id: str,
    samples: list[dict[str, Any]],
    *,
    times: list[int] | None = None,
    experiment_id: str = EXPERIMENT,
) -> dict[str, str]:
    """The four streams of one collection, as the timeline tool builds them.

    Sample ``k`` is read at ``times[k]``, or at ``k`` times 10 seconds. The
    workload read takes 200 ms. The Application read starts 250 ms after the
    start of the sample and takes 150 ms.
    """
    directory = Path(tempfile.mkdtemp(dir=root))
    head = {
        "schema": timeline.COLLECTION_SCHEMA,
        "experimentId": experiment_id,
        "runId": run_id,
        "provider": "docker-desktop",
        "serverVersion": "v1.36.1",
        "namespace": NAMESPACE,
        "release": RELEASE,
        "application": APPLICATION,
        "applicationNamespace": APPLICATION_NAMESPACE,
        "executingCommit": COMMIT,
        "procedureSha256": "1" * 64,
        "librarySha256": "2" * 64,
        "requestedSamples": len(samples),
        "intervalSeconds": 10,
        "requestTimeoutSeconds": 10,
    }
    (directory / timeline.HEADER_FILE).write_text(json.dumps(head), "utf-8")
    for number, entry in enumerate(samples, start=1):
        stem = timeline.SAMPLE_STEM.format(index=number)
        base = (number - 1) * 10_000 if times is None else times[number - 1]
        meta = {
            "workloadRead": "answered",
            "workloadStartedAt": at(base),
            "workloadFinishedAt": at(base + 200),
            "applicationRead": "answered",
            "applicationStartedAt": at(base + 250),
            "applicationFinishedAt": at(base + 400),
        }
        for name, suffix in (
            ("workload", timeline.WORKLOAD_SUFFIX),
            ("application", timeline.APPLICATION_SUFFIX),
        ):
            answer = entry[name]
            if answer is None:
                meta[f"{name}Read"] = "unanswered"
                continue
            if isinstance(answer, list):
                answer = {"apiVersion": "v1", "kind": "List", "items": answer}
            (directory / f"{stem}{suffix}").write_text(json.dumps(answer), "utf-8")
        (directory / f"{stem}{timeline.META_SUFFIX}").write_text(
            "".join(f"{key}={value}\n" for key, value in meta.items()), "utf-8"
        )
    (directory / timeline.END_FILE).write_text(
        f"completedSamples={len(samples)}\n", "utf-8"
    )
    built = timeline.build_streams(directory)
    return {name: timeline.stream_text(lines) for name, lines in built.items()}


# --------------------------------------------------------------------------
# A log of operator events, written by the events tool
# --------------------------------------------------------------------------


def events_text(
    root: Path,
    run_id: str,
    recorded: list[tuple[int, str, str | None]],
    *,
    closed: int = WINDOW_MS,
    experiment_id: str = EXPERIMENT,
) -> str:
    """A closed log. Each event is an instant, a kind, and a code."""
    path = Path(tempfile.mkdtemp(dir=root)) / "operator-events.jsonl"

    def clock(offset: int) -> Callable[[], datetime]:
        return lambda: T0 + timedelta(milliseconds=offset)

    events.open_log(path, experiment_id, run_id, now=clock(0))
    for offset, kind, code in recorded:
        actor = "operator" if kind in events.OPERATOR_ONLY else "control-process"
        events.record(path, kind, actor, code=code, now=clock(offset))
    events.close_log(path, now=clock(closed))
    return path.read_bytes().decode("utf-8")


def fault_events(started: int, finished: int) -> list[tuple[int, str, str | None]]:
    return [
        (started, "fault-injection-started", "delete-runtime-pod"),
        (finished, "fault-injection-finished", "delete-runtime-pod"),
    ]


# --------------------------------------------------------------------------
# A declaration
# --------------------------------------------------------------------------

RUNTIME_ENDPOINTS = {
    "id": "runtime-ready-endpoints",
    "source": "endpoints-ready",
    "tier": RUNTIME,
    "problemBelow": 2,
}
RUNTIME_PODS = {
    "id": "runtime-ready-pods",
    "source": "pods-ready",
    "tier": RUNTIME,
    "problemBelow": 2,
}
RUNTIME_REPLICAS = {
    "id": "runtime-ready-replicas",
    "source": "deployment-ready-replicas",
    "tier": RUNTIME,
    "problemBelow": 2,
}
SYNC = {
    "id": "application-sync",
    "source": "application-sync-status",
    "healthyValues": ["Synced"],
}
HEALTH = {
    "id": "application-health",
    "source": "application-health-status",
    "healthyValues": ["Healthy"],
}


def declaration(
    run_id: str,
    signals: list[dict[str, Any]] | None = None,
    *,
    window: tuple[int, int] = (0, WINDOW_MS),
    **changed: Any,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema": analysis.DECLARATION_SCHEMA,
        "experimentId": EXPERIMENT,
        "runId": run_id,
        "window": {"from": at(window[0]), "to": at(window[1])},
        "expected": {
            "desiredRevision": COMMIT,
            "readyReplicas": {API: 2, RUNTIME: 2},
            "runtimeReadyEndpoints": 2,
        },
        "signals": copy.deepcopy(signals or []),
    }
    document.update(changed)
    return document


def text_of(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def analyze(
    root: Path,
    requests: list[dict[str, Any]],
    samples: list[dict[str, Any]] | None = None,
    *,
    signals: list[dict[str, Any]] | None = None,
    recorded: list[tuple[int, str, str | None]] | None = None,
    window: tuple[int, int] = (0, WINDOW_MS),
    times: list[int] | None = None,
    record: tuple[int, int] | None = None,
    without: tuple[str, ...] = (),
) -> dict[str, Any]:
    """The analysis of one small run that a test states."""
    run_id = "run-1"
    started, finished = record or window
    texts: dict[str, str | None] = {
        "caller": caller_text(run_id, requests, started=started, finished=finished)
    }
    if samples is not None:
        texts.update(streams(root, run_id, samples, times=times))
    if recorded is not None:
        texts[analysis.EVENTS] = events_text(root, run_id, recorded)
    for name in without:
        texts[name] = None
    return analysis.analyze(text_of(declaration(run_id, signals, window=window)), texts)


def steady(end: int = WINDOW_MS) -> list[dict[str, Any]]:
    """Two workers that succeed every 3 seconds."""
    return closed_loop(end)


def healthy(count: int = 15) -> list[dict[str, Any]]:
    return [sample() for _ in range(count)]


# --------------------------------------------------------------------------
# The six committed cases
# --------------------------------------------------------------------------


def _outage(first: int, last: int, count: int = 15) -> list[dict[str, Any]]:
    """Samples in which the runtime Service has no Ready endpoint from ``first``
    to ``last``, and one in the sample after."""
    return [
        sample(runtime=0)
        if first <= number <= last
        else sample(runtime=1)
        if number == last + 1
        else sample()
        for number in range(count)
    ]


def case_zero_failure(root: Path) -> dict[str, str]:
    """One runtime pod is lost, and no request fails.

    The runtime Service has one Ready endpoint in the samples at 40 and at 50
    seconds. The caller succeeds every 3 seconds.
    """
    run_id = "zero-failure-1"
    samples = [
        sample(runtime=1) if number in (4, 5) else sample() for number in range(15)
    ]
    return {
        "declaration.json": text_of(
            declaration(run_id, [RUNTIME_ENDPOINTS, RUNTIME_REPLICAS, SYNC, HEALTH])
        ),
        "caller.jsonl": caller_text(run_id, steady()),
        **_named(streams(root, run_id, samples), without=("pods",)),
        "operator-events.jsonl": events_text(
            root, run_id, fault_events(32_000, 32_300)
        ),
    }


def _failing_from(first: int, last: int) -> Callable[[int, int], bool]:
    return lambda worker, start: first <= start < last


def case_concurrency(root: Path) -> dict[str, str]:
    """Both runtime pods are lost for 20 seconds, with two workers.

    A request that starts from 39.5 to 60 seconds fails after 200 ms. The
    request that worker 1 sends at 39.5 seconds is the first to fail. Worker 0
    sent a request at 39 seconds, before the failure, and it succeeds at 42
    seconds. So the first episode ends there.
    """
    run_id = "concurrency-1"
    return {
        "declaration.json": text_of(
            declaration(
                run_id, [RUNTIME_ENDPOINTS, RUNTIME_PODS, RUNTIME_REPLICAS, HEALTH]
            )
        ),
        "caller.jsonl": caller_text(
            run_id, closed_loop(WINDOW_MS, _failing_from(39_500, 60_000))
        ),
        **_named(streams(root, run_id, _outage(4, 5))),
        "operator-events.jsonl": events_text(
            root, run_id, fault_events(39_000, 39_400)
        ),
    }


def case_missing_signal(root: Path) -> dict[str, str]:
    """The same outage, with evidence that is not complete.

    The argo stream is not given. The workload read of the sample at 50 seconds
    did not answer. The Deployment states no readyReplicas while the count is
    zero.
    """
    run_id = "missing-signal-1"
    samples = _outage(4, 5)
    samples[5] = sample(workload=False)
    return {
        "declaration.json": text_of(
            declaration(
                run_id,
                [RUNTIME_ENDPOINTS, {**RUNTIME_REPLICAS, "problemBelow": 1}, SYNC],
            )
        ),
        "caller.jsonl": caller_text(
            run_id, closed_loop(WINDOW_MS, _failing_from(39_500, 60_000))
        ),
        **_named(streams(root, run_id, samples), without=("pods", "argo")),
        "operator-events.jsonl": events_text(
            root, run_id, fault_events(39_000, 39_400)
        ),
    }


def case_open_episode(root: Path) -> dict[str, str]:
    """The runtime does not come back, and no request succeeds again."""
    run_id = "open-episode-1"
    return {
        "declaration.json": text_of(declaration(run_id, [RUNTIME_ENDPOINTS, HEALTH])),
        "caller.jsonl": caller_text(
            run_id, closed_loop(WINDOW_MS, _failing_from(39_500, WINDOW_MS))
        ),
        **_named(streams(root, run_id, _outage(4, 14)), without=("pods",)),
        "operator-events.jsonl": events_text(
            root, run_id, fault_events(39_000, 39_400)
        ),
    }


def tied_requests() -> list[dict[str, Any]]:
    """Two workers whose requests complete at the same instants, every 3 seconds.

    At 30 seconds the line of the failed request is before the line of the
    successful one. At 42 seconds the line of the successful request is first.
    """
    lines: list[dict[str, Any]] = []
    for step in range(1, 21):
        finish = step * 3000
        pair = [
            request(2 * step - 1, 0, finish - 3000, finish),
            request(2 * step, 1, finish - 3000, finish),
        ]
        if finish == 30_000:
            pair[0]["ok"] = False
        if finish == 42_000:
            pair[0]["ok"] = False
            pair.reverse()
        lines.extend(pair)
    return lines


def case_clock_ties(root: Path) -> dict[str, str]:
    """A failed and a successful request complete at one instant, twice."""
    run_id = "clock-ties-1"
    return {
        "declaration.json": text_of(
            declaration(run_id, [RUNTIME_ENDPOINTS], window=(0, 60_000))
        ),
        "caller.jsonl": caller_text(run_id, tied_requests(), finished=60_000),
        **_named(streams(root, run_id, healthy(6)), without=("pods",)),
    }


def case_abort(root: Path) -> dict[str, str]:
    """The runtime does not come back, and the run is aborted at 80 seconds."""
    run_id = "abort-1"
    recorded = [*fault_events(39_000, 39_400), (80_000, "run-aborted", "safety-limit")]
    return {
        "declaration.json": text_of(declaration(run_id, [RUNTIME_ENDPOINTS])),
        "caller.jsonl": caller_text(
            run_id,
            closed_loop(82_000, _failing_from(39_500, WINDOW_MS)),
            finished=82_000,
            interrupted=True,
        ),
        **_named(streams(root, run_id, _outage(4, 8, count=9)), without=("pods",)),
        "operator-events.jsonl": events_text(root, run_id, recorded, closed=85_000),
    }


def _named(built: dict[str, str], without: tuple[str, ...] = ()) -> dict[str, str]:
    return {
        f"{name}.jsonl": text for name, text in built.items() if name not in without
    }


CASES: dict[str, Callable[[Path], dict[str, str]]] = {
    "zero-failure": case_zero_failure,
    "concurrency": case_concurrency,
    "missing-signal": case_missing_signal,
    "open-episode": case_open_episode,
    "clock-ties": case_clock_ties,
    "abort": case_abort,
}


def analysis_of(files: dict[str, str]) -> dict[str, Any]:
    """The analysis of the files of one case, each given under its input name."""
    texts: dict[str, str | None] = {
        name: files.get(f"{name}.jsonl") for name in analysis.INPUTS
    }
    return analysis.analyze(files["declaration.json"], texts)


def committed(case: str) -> dict[str, str]:
    return {
        path.name: path.read_bytes().decode("utf-8")
        for path in sorted((FIXTURES / case).iterdir())
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, str]]:
    root = tmp_path_factory.mktemp("cases")
    return {name: build(root) for name, build in CASES.items()}


def test_the_committed_cases_are_the_six_cases() -> None:
    assert sorted(path.name for path in FIXTURES.iterdir()) == sorted(CASES)


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_committed_case_is_what_the_suite_builds(
    case: str, built: dict[str, dict[str, str]]
) -> None:
    """The committed inputs are what the builders of this suite give, byte for byte."""
    files = committed(case)
    stored = files.pop("analysis.json")
    assert files == built[case]
    assert stored == analysis.analysis_text(analysis_of(files))


def stored_analysis(case: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(committed(case)["analysis.json"])
    return document


def signal_of(document: dict[str, Any], identifier: str) -> dict[str, Any]:
    [found] = [s for s in document["signals"] if s["id"] == identifier]
    return dict(found)


def test_zero_failure_states_no_episode_and_a_stabilized_recovery() -> None:
    document = stored_analysis("zero-failure")
    caller = document["caller"]
    assert caller["requests"] == {
        "completed": 99,
        "successful": 99,
        "failed": 0,
        "outsideWindow": 0,
        "largestTimeWithNoCompletionMs": 3000,
    }
    assert caller["failureEpisodes"]["count"] == 0
    assert caller["failureEpisodes"]["callerFailureEpisodeMs"] == 0
    assert caller["firstImpact"]["state"] == "none"
    # The two workers complete 500 ms and 2,500 ms apart, in turn.
    assert caller["maxSuccessGap"]["ms"] == 2500
    runtime = document["zeroReadyEndpoints"]["tiers"][RUNTIME]
    assert (runtime["state"], runtime["count"]) == ("observed", 0)
    assert runtime["totalOuterMs"] == 0
    # One Ready endpoint is a problem for the declared signal and is not zero.
    endpoints = signal_of(document, "runtime-ready-endpoints")
    assert endpoints["byState"] == {"healthy": 13, "problem": 2, "not-observed": 0}
    assert endpoints["detectionLag"]["reason"] == "no-caller-impact"
    assert endpoints["detectionLag"]["lagNotAboveMs"] is None
    assert endpoints["detectionLag"]["notBefore"] == at(30_000)
    assert endpoints["detectionLag"]["notAfter"] == at(40_200)
    assert endpoints["falseHealthy"]["callerMs"] == 0
    # The signal gave the problem at the reads of 40 and of 50 seconds: from
    # the finish of the first to the start of the last, and from the start of
    # the read before to the finish of the read after.
    assert endpoints["falseUnavailable"]["innerMs"] == 50_000 - 40_200
    assert endpoints["falseUnavailable"]["outerMs"] == 60_200 - 30_000
    recovery = document["stabilizedRecovery"]
    assert recovery["stabilized"] is True
    # The last read that did not hold finished at 50,200 ms. The first
    # completion after it is at 51,000 ms, and the span is 60 seconds.
    assert recovery["span"]["first"]["finishedAt"] == at(51_000)
    assert recovery["stabilizedAt"] == at(111_000)
    assert recovery["span"]["ms"] == 60_000
    assert recovery["span"]["successes"] == 41
    assert recovery["sinceFault"]["fromFaultStartedMs"] == 111_000 - 32_000
    assert recovery["sinceFault"]["fromFaultFinishedMs"] == 111_000 - 32_300
    assert recovery["requestsFailedSinceFault"] == 0
    assert document["withoutValue"] == [
        "signals.runtime-ready-endpoints.detectionLag",
        "signals.runtime-ready-replicas.detectionLag",
        "signals.application-sync.detectionLag",
        "signals.application-health.detectionLag",
    ]


def test_concurrency_ends_an_episode_at_a_request_that_was_sent_before_it() -> None:
    document = stored_analysis("concurrency")
    episodes = document["caller"]["failureEpisodes"]["episodes"]
    first = episodes[0]
    # Worker 1 fails at 39,700 ms. Worker 0 sent its request at 39,000 ms and
    # succeeds at 42,000 ms.
    assert first["start"]["finishedAt"] == at(39_700)
    assert first["end"]["finishedAt"] == at(42_000)
    assert first["ms"] == 2300
    records = {
        line["sequence"]: line
        for line in map(
            json.loads, committed("concurrency")["caller.jsonl"].split("\n")[1:-2]
        )
    }
    closing = records[first["end"]["sequence"]]
    assert closing["startedAt"] == at(39_000) < first["start"]["finishedAt"]
    assert closing["worker"] != records[first["start"]["sequence"]]["worker"]
    assert len(episodes) == 2
    assert document["caller"]["failureEpisodes"]["callerFailureEpisodeMs"] == max(
        episode["ms"] for episode in episodes
    )
    assert document["caller"]["firstImpact"]["finishedAt"] == at(39_700)
    runtime = document["zeroReadyEndpoints"]["tiers"][RUNTIME]
    assert runtime["count"] == 1
    assert runtime["intervals"][0]["firstReading"]["startedAt"] == at(40_000)
    assert runtime["intervals"][0]["lastReading"]["startedAt"] == at(50_000)
    assert runtime["intervals"][0]["boundedBefore"]["startedAt"] == at(30_000)
    assert runtime["intervals"][0]["boundedAfter"]["finishedAt"] == at(60_200)
    assert (runtime["totalInnerMs"], runtime["maxInnerMs"]) == (9800, 9800)
    assert (runtime["totalOuterMs"], runtime["maxOuterMs"]) == (30_200, 30_200)
    assert document["zeroReadyEndpoints"]["tiers"][API]["count"] == 0
    endpoints = signal_of(document, "runtime-ready-endpoints")
    lag = endpoints["detectionLag"]
    assert lag["state"] == "computed"
    assert lag["firstIndication"]["index"] == 5
    assert lag["lagNotBelowMs"] == 30_000 - 39_700
    assert lag["lagNotAboveMs"] == 40_200 - 39_700
    assert lag["order"] == "not-established"
    assert document["stabilizedRecovery"]["stabilized"] is True


def test_missing_signal_gives_no_value_and_no_healthy_state() -> None:
    document = stored_analysis("missing-signal")
    assert document["inputs"]["argo"] == "not-given"
    sync = signal_of(document, "application-sync")
    assert (sync["state"], sync["reason"]) == ("not-computable", "stream-not-given")
    assert sync["falseHealthy"] is None
    # The count is omitted while it is zero, and one read did not answer. The
    # signal never states the problem, and it is not healthy in those readings.
    replicas = signal_of(document, "runtime-ready-replicas")
    assert replicas["byState"]["not-observed"] == 2
    assert replicas["detectionLag"]["state"] == "not-computable"
    assert replicas["falseHealthy"]["signalNotObservedMs"] > 0
    # The signal is healthy to the read of 30 seconds and from the read of 60
    # seconds. The second episode ends at 63,000 ms, so 2,800 ms of it are
    # between two consecutive healthy reads. The first commit stated 23,200 ms.
    assert replicas["falseHealthy"]["innerMs"] == 63_000 - 60_200
    runtime = document["zeroReadyEndpoints"]["tiers"][RUNTIME]
    # One reading states zero. The reading after it states nothing, so the
    # interval is bounded by the reading at 60 seconds.
    assert runtime["readings"]["withoutValue"] == 1
    assert runtime["intervals"][0]["readings"] == 1
    assert runtime["intervals"][0]["innerMs"] == 0
    assert runtime["intervals"][0]["outerMs"] == 60_200 - 30_000
    recovery = document["stabilizedRecovery"]
    assert (recovery["state"], recovery["reason"]) == (
        "not-computable",
        "stream-not-given",
    )
    assert recovery["stabilized"] is None
    assert "stabilizedRecovery" in document["withoutValue"]
    assert "signals.application-sync" in document["withoutValue"]


def test_open_episode_has_no_duration() -> None:
    document = stored_analysis("open-episode")
    episodes = document["caller"]["failureEpisodes"]
    assert episodes["open"] == 1
    last = episodes["episodes"][-1]
    assert (last["open"], last["end"], last["ms"]) == (True, None, None)
    assert episodes["callerFailureEpisodeMs"] is None
    assert "caller.failureEpisodes.callerFailureEpisodeMs" in document["withoutValue"]
    recovery = document["stabilizedRecovery"]
    assert (recovery["state"], recovery["stabilized"]) == ("computed", False)
    assert recovery["stabilizedAt"] is None
    runtime = document["zeroReadyEndpoints"]["tiers"][RUNTIME]
    # The interval has no reading after it, so the window bounds it.
    assert runtime["intervals"][0]["boundedAfter"] is None
    assert runtime["intervals"][0]["outerMs"] == WINDOW_MS - 30_000


def test_clock_ties_are_ordered_by_the_position_of_the_lines() -> None:
    document = stored_analysis("clock-ties")
    assert document["caller"]["order"]["completionsSharingAnInstant"] == 40
    first, second = document["caller"]["failureEpisodes"]["episodes"]
    # At 30 seconds the failed line is first: the episode ends at the same
    # instant. At 42 seconds the successful line is first: the episode lasts
    # until the next completion.
    assert (first["ms"], first["start"]["tied"], first["end"]["tied"]) == (
        0,
        True,
        True,
    )
    assert (second["ms"], second["start"]["tied"], second["end"]["tied"]) == (
        3000,
        True,
        False,
    )


def test_abort_ends_the_window_and_leaves_the_episode_open() -> None:
    document = stored_analysis("abort")
    assert document["window"]["effectiveTo"] == at(80_000)
    assert document["window"]["endedBy"] == "run-aborted"
    assert document["aborts"] == [
        {"index": 3, "recordedAt": at(80_000), "code": "safety-limit"}
    ]
    caller = document["caller"]
    assert caller["record"]["endState"] == "interrupted"
    assert caller["requests"]["outsideWindow"] > 0
    assert caller["failureEpisodes"]["open"] == 1
    assert caller["failureEpisodes"]["callerFailureEpisodeMs"] is None
    last = caller["failureEpisodes"]["episodes"][-1]
    assert (last["open"], last["end"], last["ms"]) == (True, None, None)
    # The reading at 80 seconds finishes after the abort and is not read.
    endpoints = signal_of(document, "runtime-ready-endpoints")
    assert endpoints["readings"]["inWindow"] == 8
    assert endpoints["readings"]["outsideWindow"] == 1
    assert document["stabilizedRecovery"]["stabilized"] is False


# --------------------------------------------------------------------------
# Caller failure episodes and the maximum success gap
# --------------------------------------------------------------------------


def small(*entries: tuple[int, bool]) -> list[dict[str, Any]]:
    """One worker. Each entry is a completion instant and whether it succeeded."""
    return [
        request(number, 0, finish - 100, finish, ok)
        for number, (finish, ok) in enumerate(entries, start=1)
    ]


def test_an_episode_starts_at_the_first_failure_and_ends_at_the_next_success(
    tmp_path: Path,
) -> None:
    requests = small(
        (1000, True), (2000, False), (2500, False), (4000, True), (5000, True)
    )
    document = analyze(tmp_path, requests, window=(0, 6000))
    [episode] = document["caller"]["failureEpisodes"]["episodes"]
    assert episode == {
        "index": 1,
        "open": False,
        "start": {"sequence": 2, "finishedAt": at(2000), "tied": False},
        "end": {"sequence": 4, "finishedAt": at(4000), "tied": False},
        "ms": 2000,
        "failedRequests": 2,
        "successAfterWindow": None,
    }
    assert document["caller"]["failureEpisodes"]["callerFailureEpisodeMs"] == 2000
    assert document["caller"]["firstImpact"] == {
        "state": "observed",
        "searchedFrom": at(0),
        "sequence": 2,
        "startedAt": at(1900),
        "finishedAt": at(2000),
        "outcome": "http-error",
    }


def test_the_figure_is_the_longest_of_several_episodes(tmp_path: Path) -> None:
    requests = small(
        (1000, False),
        (1300, True),
        (2000, False),
        (2900, True),
        (3000, False),
        (3100, True),
    )
    episodes = analyze(tmp_path, requests, window=(0, 4000))["caller"][
        "failureEpisodes"
    ]
    assert [episode["ms"] for episode in episodes["episodes"]] == [300, 900, 100]
    assert episodes["callerFailureEpisodeMs"] == 900


def test_the_maximum_success_gap_names_its_two_completions(tmp_path: Path) -> None:
    requests = small(
        (1000, True), (2000, True), (2500, False), (5500, True), (6000, True)
    )
    gap = analyze(tmp_path, requests, window=(0, 7000))["caller"]["maxSuccessGap"]
    assert gap == {
        "state": "computed",
        "reason": None,
        "successes": 4,
        "ms": 3500,
        "from": {"sequence": 2, "finishedAt": at(2000)},
        "to": {"sequence": 4, "finishedAt": at(5500)},
    }


@pytest.mark.parametrize("successes", [0, 1])
def test_fewer_than_two_successes_give_no_gap_and_not_zero(
    tmp_path: Path, successes: int
) -> None:
    requests = small((1000, False), *[(2000, True)] * successes)
    document = analyze(tmp_path, requests, window=(0, 3000))
    gap = document["caller"]["maxSuccessGap"]
    assert (gap["state"], gap["reason"]) == (
        "not-computable",
        "fewer-than-two-successes",
    )
    assert gap["ms"] is None
    assert "caller.maxSuccessGap" in document["withoutValue"]


def test_the_edges_of_the_window_are_not_ends_of_a_gap(tmp_path: Path) -> None:
    requests = small((40_000, True), (41_000, True))
    gap = analyze(tmp_path, requests, window=(0, 100_000))["caller"]["maxSuccessGap"]
    assert gap["ms"] == 1000


def test_a_completion_outside_the_window_is_not_read(tmp_path: Path) -> None:
    requests = small(
        (1000, False), (2000, True), (3000, False), (4000, True), (9000, False)
    )
    document = analyze(tmp_path, requests, window=(2500, 8000), record=(0, 10_000))
    caller = document["caller"]
    assert caller["requests"] == {
        "completed": 2,
        "successful": 1,
        "failed": 1,
        "outsideWindow": 3,
        "largestTimeWithNoCompletionMs": 4000,
    }
    assert [e["ms"] for e in caller["failureEpisodes"]["episodes"]] == [1000]


def test_a_completion_at_an_edge_of_the_window_is_read(tmp_path: Path) -> None:
    requests = small((1000, False), (5000, True))
    document = analyze(tmp_path, requests, window=(1000, 5000), record=(0, 6000))
    assert document["caller"]["failureEpisodes"]["callerFailureEpisodeMs"] == 4000


@pytest.mark.parametrize("record", [(1, 10_000), (0, 9999)])
def test_a_record_that_does_not_cover_the_window_gives_no_caller_metric(
    tmp_path: Path, record: tuple[int, int]
) -> None:
    """A window with no failed request is not a window in which none failed."""
    requests = small((2000, True), (3000, True))
    document = analyze(
        tmp_path,
        requests,
        healthy(1),
        signals=[RUNTIME_ENDPOINTS],
        window=(0, 10_000),
        record=record,
    )
    caller = document["caller"]
    assert (caller["state"], caller["reason"]) == (
        "not-computable",
        "caller-record-does-not-cover-window",
    )
    assert caller["failureEpisodes"] is None
    assert caller["maxSuccessGap"] is None
    assert document["withoutValue"][0] == "caller"
    signal = signal_of(document, "runtime-ready-endpoints")
    for name in ("detectionLag", "falseHealthy", "falseUnavailable"):
        assert signal[name]["reason"] == "caller-not-computable"
    assert document["stabilizedRecovery"]["reason"] == "caller-not-computable"


def test_swapping_two_tied_lines_changes_the_episode(tmp_path: Path) -> None:
    """The instants do not order two completions of one millisecond."""
    failed_first = [
        request(1, 0, 0, 1000),
        request(2, 0, 1000, 2000, ok=False),
        request(3, 1, 1000, 2000),
        request(4, 0, 3000, 5000),
    ]
    success_first = [failed_first[0], failed_first[2], failed_first[1], failed_first[3]]
    one = analyze(tmp_path, failed_first, window=(0, 6000))["caller"]
    other = analyze(tmp_path, success_first, window=(0, 6000))["caller"]
    assert one["failureEpisodes"]["callerFailureEpisodeMs"] == 0
    assert other["failureEpisodes"]["callerFailureEpisodeMs"] == 3000
    assert one["order"]["rule"] == analysis.COMPLETION_ORDER


def test_lines_that_are_not_tied_are_ordered_by_their_instants(tmp_path: Path) -> None:
    """The line order decides only between two completions of one instant."""
    requests = small((1000, True), (2000, False), (4000, True))
    shuffled = [requests[2], requests[0], requests[1]]
    assert (
        analyze(tmp_path, requests, window=(0, 5000))["caller"]["failureEpisodes"]
        == analyze(tmp_path, shuffled, window=(0, 5000))["caller"]["failureEpisodes"]
    )


# --------------------------------------------------------------------------
# The fault and the abort
# --------------------------------------------------------------------------


def test_the_first_impact_is_searched_from_the_fault(tmp_path: Path) -> None:
    requests = small((1000, False), (2000, True), (6000, False), (7000, True))
    document = analyze(
        tmp_path, requests, recorded=fault_events(5000, 5200), window=(0, 8000)
    )
    assert document["fault"] == {
        "state": "stated",
        "notBefore": at(5000),
        "notAfter": at(5200),
        "code": "delete-runtime-pod",
    }
    assert document["caller"]["firstImpact"]["sequence"] == 3
    assert document["caller"]["firstImpact"]["searchedFrom"] == at(5000)
    # The episode before the fault is still an episode of the window.
    assert document["caller"]["failureEpisodes"]["count"] == 2


@pytest.mark.parametrize(
    "recorded",
    [
        [(5000, "fault-injection-started", "delete-runtime-pod")],
        [(5000, "fault-injection-finished", "delete-runtime-pod")],
        [*fault_events(5000, 5200), *fault_events(6000, 6200)],
        [
            (5000, "fault-injection-started", "delete-runtime-pod"),
            (5200, "fault-injection-finished", "delete-api-pod"),
        ],
        [
            (5000, "fault-injection-finished", "delete-runtime-pod"),
            (5200, "fault-injection-started", "delete-runtime-pod"),
        ],
    ],
)
def test_a_fault_that_is_not_one_pair_of_events_is_ambiguous(
    tmp_path: Path, recorded: list[tuple[int, str, str | None]]
) -> None:
    requests = small((6000, False), (7000, True))
    document = analyze(
        tmp_path,
        requests,
        healthy(1),
        signals=[RUNTIME_ENDPOINTS],
        recorded=recorded,
        window=(0, 8000),
    )
    assert document["fault"]["state"] == "ambiguous"
    assert document["fault"]["notBefore"] is None
    signal = signal_of(document, "runtime-ready-endpoints")
    assert signal["detectionLag"]["reason"] == "fault-ambiguous"
    assert document["stabilizedRecovery"]["reason"] == "fault-ambiguous"


def test_a_log_with_no_fault_event_states_that(tmp_path: Path) -> None:
    document = analyze(
        tmp_path, small((1000, True), (2000, True)), recorded=[], window=(0, 3000)
    )
    assert document["fault"]["state"] == "not-recorded"
    assert document["inputs"][analysis.EVENTS] == "read"


def test_no_log_states_that_the_fault_was_not_given(tmp_path: Path) -> None:
    document = analyze(tmp_path, small((1000, True), (2000, True)), window=(0, 3000))
    assert document["fault"]["state"] == "not-given"
    assert document["inputs"][analysis.EVENTS] == "not-given"
    assert document["aborts"] == []


def test_a_manual_action_is_listed(tmp_path: Path) -> None:
    document = analyze(
        tmp_path,
        small((1000, True), (2000, True)),
        recorded=[(1500, "manual-action", "restart-collector")],
        window=(0, 3000),
    )
    assert document["manualActions"] == [
        {"index": 1, "recordedAt": at(1500), "code": "restart-collector"}
    ]


def test_an_abort_before_the_window_is_refused(tmp_path: Path) -> None:
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analyze(
            tmp_path,
            small((6000, True)),
            recorded=[(1000, "run-aborted", "safety-limit")],
            window=(5000, 9000),
            record=(0, 9000),
        )
    assert refused.value.rule == "analysis-window-invalid"


def test_an_abort_after_the_window_does_not_change_it(tmp_path: Path) -> None:
    document = analyze(
        tmp_path,
        small((1000, True), (2000, True)),
        recorded=[(9000, "run-aborted", "safety-limit")],
        window=(0, 3000),
    )
    assert document["window"]["endedBy"] == "declared"
    assert document["window"]["effectiveTo"] == at(3000)
    assert len(document["aborts"]) == 1


# --------------------------------------------------------------------------
# Zero Ready endpoints
# --------------------------------------------------------------------------


def zero_ready(
    tmp_path: Path, samples: list[dict[str, Any]], **options: Any
) -> dict[str, Any]:
    document = analyze(tmp_path, steady(), samples, **options)
    return dict(document["zeroReadyEndpoints"])


def test_an_interval_states_the_readings_at_each_end(tmp_path: Path) -> None:
    samples = [
        sample(),
        sample(runtime=0),
        sample(runtime=0),
        sample(runtime=0),
        sample(),
    ]
    tier = zero_ready(tmp_path, samples)["tiers"][RUNTIME]
    assert tier["intervals"] == [
        {
            "firstReading": {
                "index": 2,
                "startedAt": at(10_000),
                "finishedAt": at(10_200),
            },
            "lastReading": {
                "index": 4,
                "startedAt": at(30_000),
                "finishedAt": at(30_200),
            },
            "readings": 3,
            "notObservedReadingsInside": 0,
            "boundedBefore": {
                "index": 1,
                "startedAt": at(0),
                "finishedAt": at(200),
            },
            "boundedAfter": {
                "index": 5,
                "startedAt": at(40_000),
                "finishedAt": at(40_200),
            },
            "innerMs": 30_000 - 10_200,
            "outerMs": 40_200 - 0,
        }
    ]


def test_one_reading_of_zero_has_an_inner_figure_of_zero(tmp_path: Path) -> None:
    tier = zero_ready(tmp_path, [sample(), sample(runtime=0), sample()])["tiers"][
        RUNTIME
    ]
    assert (tier["count"], tier["totalInnerMs"], tier["maxInnerMs"]) == (1, 0, 0)
    assert tier["totalOuterMs"] == 20_200


def test_two_intervals_have_a_total_and_a_maximum(tmp_path: Path) -> None:
    samples = [
        sample(),
        sample(runtime=0),
        sample(),
        sample(runtime=0),
        sample(runtime=0),
        sample(runtime=0),
        sample(),
    ]
    tier = zero_ready(tmp_path, samples)["tiers"][RUNTIME]
    assert tier["count"] == 2
    assert (tier["totalInnerMs"], tier["maxInnerMs"]) == (19_800, 19_800)
    # The two outer figures share the read at 20 seconds, and the total counts
    # that read once.
    assert tier["maxOuterMs"] == 60_200 - 20_000
    assert tier["totalOuterMs"] == 60_200


def test_no_reading_of_zero_gives_a_count_of_zero(tmp_path: Path) -> None:
    result = zero_ready(tmp_path, [sample(runtime=1), sample(runtime=2)])
    assert result["state"] == "computed"
    tier = result["tiers"][RUNTIME]
    assert (tier["state"], tier["count"], tier["totalOuterMs"]) == ("observed", 0, 0)


def test_a_read_that_did_not_answer_is_not_a_reading_of_zero(tmp_path: Path) -> None:
    samples = [sample(), sample(workload=False), sample(workload=False), sample()]
    tier = zero_ready(tmp_path, samples)["tiers"][RUNTIME]
    assert tier["count"] == 0
    assert tier["readings"] == {
        "inWindow": 4,
        "withValue": 2,
        "withoutValue": 2,
        "outsideWindow": 0,
        "largestTimeBetweenReadsMs": 30_000 - 200,
    }
    # The time with no value: before the first read, between the two reads
    # with a value, and after the last read.
    assert tier["notObservedMs"] == 0 + (30_000 - 200) + (WINDOW_MS - 30_200)


def test_a_reading_with_no_value_inside_an_interval_is_counted(tmp_path: Path) -> None:
    samples = [
        sample(),
        sample(runtime=0),
        sample(workload=False),
        sample(runtime=0),
        sample(),
    ]
    [interval] = zero_ready(tmp_path, samples)["tiers"][RUNTIME]["intervals"]
    assert interval["readings"] == 2
    assert interval["notObservedReadingsInside"] == 1
    # The reading with no value divides the run into two parts of one read
    # each, so no time is between two consecutive reads of zero.
    assert interval["innerMs"] == 0
    assert interval["outerMs"] == 40_200


def test_a_reading_with_no_value_does_not_bound_an_interval(tmp_path: Path) -> None:
    samples = [
        sample(),
        sample(workload=False),
        sample(runtime=0),
        sample(workload=False),
        sample(),
    ]
    [interval] = zero_ready(tmp_path, samples)["tiers"][RUNTIME]["intervals"]
    assert interval["boundedBefore"]["index"] == 1
    assert interval["boundedAfter"]["index"] == 5
    assert interval["outerMs"] == 40_200


def test_a_tier_with_no_value_is_not_observed_and_has_no_count(tmp_path: Path) -> None:
    document = analyze(
        tmp_path, steady(), [sample(workload=False), sample(workload=False)]
    )
    tier = document["zeroReadyEndpoints"]["tiers"][RUNTIME]
    assert tier["state"] == "not-observed"
    assert (tier["count"], tier["intervals"]) == (None, [])
    assert (tier["totalInnerMs"], tier["totalOuterMs"]) == (None, None)
    assert tier["notObservedMs"] == WINDOW_MS
    assert f"zeroReadyEndpoints.tiers.{RUNTIME}" in document["withoutValue"]


def test_an_interval_at_the_edges_of_the_window_is_bounded_by_the_window(
    tmp_path: Path,
) -> None:
    [interval] = zero_ready(tmp_path, [sample(runtime=0), sample(runtime=0)])["tiers"][
        RUNTIME
    ]["intervals"]
    assert (interval["boundedBefore"], interval["boundedAfter"]) == (None, None)
    assert interval["outerMs"] == WINDOW_MS
    assert interval["innerMs"] == 10_000 - 200


def test_without_the_endpoints_stream_the_metric_has_no_value(tmp_path: Path) -> None:
    document = analyze(tmp_path, steady(), healthy(2), without=("endpoints",))
    assert document["zeroReadyEndpoints"] == {
        "state": "not-computable",
        "reason": "stream-not-given",
        "tiers": None,
    }
    assert "zeroReadyEndpoints" in document["withoutValue"]


def test_a_reading_outside_the_window_is_not_read(tmp_path: Path) -> None:
    samples = [sample(runtime=0), sample(), sample(), sample(runtime=0)]
    result = zero_ready(tmp_path, samples, window=(5000, 25_000), record=(0, WINDOW_MS))
    tier = result["tiers"][RUNTIME]
    assert tier["count"] == 0
    assert tier["readings"]["inWindow"] == 2
    assert tier["readings"]["outsideWindow"] == 2


def test_readings_that_are_out_of_order_give_no_value(tmp_path: Path) -> None:
    result = zero_ready(
        tmp_path, [sample(), sample(), sample()], times=[0, 20_000, 10_000]
    )
    assert (result["state"], result["reason"]) == (
        "not-computable",
        "readings-out-of-order",
    )


# --------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------


def outage_requests() -> list[dict[str, Any]]:
    """One worker that fails from 22 to 41 seconds.

    The first failed request completes at 22,000 ms, and the first successful
    request after it completes at 45,000 ms.
    """
    return small(
        (10_000, True),
        (20_000, True),
        (22_000, False),
        (30_000, False),
        (41_000, False),
        (45_000, True),
        (55_000, True),
    )


def test_the_detection_lag_states_both_bounds(tmp_path: Path) -> None:
    samples = [
        sample(),
        sample(),
        sample(),
        sample(runtime=0),
        sample(runtime=0),
        sample(),
    ]
    document = analyze(
        tmp_path,
        outage_requests(),
        samples,
        signals=[RUNTIME_ENDPOINTS],
        window=(0, 60_000),
    )
    lag = signal_of(document, "runtime-ready-endpoints")["detectionLag"]
    # The caller impact is at 22,000 ms. The signal was healthy at the read
    # that started at 20,000 ms and stated the problem at the read that
    # finished at 30,200 ms.
    assert lag == {
        "state": "computed",
        "reason": None,
        "firstIndication": {
            "index": 4,
            "startedAt": at(30_000),
            "finishedAt": at(30_200),
        },
        "notBefore": at(20_000),
        "notAfter": at(30_200),
        "lagNotBelowMs": -2000,
        "lagNotAboveMs": 8200,
        "order": "not-established",
    }


@pytest.mark.parametrize(
    ("first_problem", "order", "below", "above"),
    [(1, "signal-first", -22_000, -11_800), (4, "caller-first", 8000, 18_200)],
)
def test_the_order_follows_the_two_bounds(
    tmp_path: Path, first_problem: int, order: str, below: int, above: int
) -> None:
    samples = [
        sample(runtime=0) if number >= first_problem else sample()
        for number in range(6)
    ]
    document = analyze(
        tmp_path,
        outage_requests(),
        samples,
        signals=[RUNTIME_ENDPOINTS],
        window=(0, 60_000),
    )
    lag = signal_of(document, "runtime-ready-endpoints")["detectionLag"]
    assert (lag["order"], lag["lagNotBelowMs"], lag["lagNotAboveMs"]) == (
        order,
        below,
        above,
    )


def test_a_signal_that_never_states_the_problem_has_no_lag(tmp_path: Path) -> None:
    document = analyze(
        tmp_path,
        outage_requests(),
        healthy(6),
        signals=[RUNTIME_ENDPOINTS],
        window=(0, 60_000),
    )
    signal = signal_of(document, "runtime-ready-endpoints")
    assert signal["changed"] is False
    assert signal["detectionLag"]["reason"] == "never-indicated"
    assert signal["detectionLag"]["lagNotAboveMs"] is None
    assert "signals.runtime-ready-endpoints.detectionLag" in document["withoutValue"]


def test_a_problem_at_the_first_reading_has_no_lower_bound(tmp_path: Path) -> None:
    samples = [sample(runtime=0), sample(runtime=0), sample()]
    document = analyze(
        tmp_path,
        outage_requests(),
        samples,
        signals=[RUNTIME_ENDPOINTS],
        window=(0, 60_000),
    )
    lag = signal_of(document, "runtime-ready-endpoints")["detectionLag"]
    assert (lag["notBefore"], lag["lagNotBelowMs"]) == (None, None)
    assert lag["lagNotAboveMs"] == 200 - 22_000
    assert lag["order"] == "signal-first"


def test_a_problem_that_predates_the_fault_is_not_a_first_indication(
    tmp_path: Path,
) -> None:
    samples = [
        sample(),
        sample(runtime=0),
        sample(runtime=0),
        sample(runtime=0),
        sample(),
    ]
    document = analyze(
        tmp_path,
        outage_requests(),
        samples,
        signals=[RUNTIME_ENDPOINTS],
        recorded=fault_events(21_000, 21_300),
        window=(0, 60_000),
    )
    lag = signal_of(document, "runtime-ready-endpoints")["detectionLag"]
    assert lag["reason"] == "indicated-before-search-start"
    assert lag["firstIndication"]["index"] == 4
    assert lag["lagNotAboveMs"] is None


def test_the_false_healthy_time_is_inside_the_failure_episode(tmp_path: Path) -> None:
    """The caller fails from 22,000 to 45,000 ms.

    The signal is healthy at the reads of 0, 10, 20, and 50 seconds, and it
    states the problem at the reads of 30 and 40 seconds.
    """
    samples = [
        sample(),
        sample(),
        sample(),
        sample(runtime=0),
        sample(runtime=0),
        sample(),
    ]
    document = analyze(
        tmp_path,
        outage_requests(),
        samples,
        signals=[RUNTIME_ENDPOINTS],
        window=(0, 60_000),
    )
    signal = signal_of(document, "runtime-ready-endpoints")
    assert signal["byState"] == {"healthy": 4, "problem": 2, "not-observed": 0}
    assert signal["changed"] is True
    assert signal["falseHealthy"] == {
        "state": "computed",
        "reason": None,
        "callerMs": 45_000 - 22_000,
        # No two consecutive healthy reads have time between them inside the
        # episode.
        "innerMs": 0,
        # Healthy can hold until the read of 30 seconds finishes, and from the
        # start of the read of 40 seconds.
        "outerMs": (30_200 - 22_000) + (45_000 - 40_000),
        "signalNotObservedMs": 0,
    }
    # The caller succeeds from 10,000 to 20,000 ms and from 45,000 to 55,000
    # ms. The problem can hold from 20,000 to 50,200 ms. No read is after
    # 50,200 ms, so the stream states nothing from there.
    assert signal["falseUnavailable"] == {
        "state": "computed",
        "reason": None,
        "callerMs": 20_000,
        "innerMs": 0,
        "outerMs": 50_200 - 45_000,
        "signalNotObservedMs": 55_000 - 50_200,
    }


def test_a_signal_that_stays_healthy_is_false_healthy_for_the_episode(
    tmp_path: Path,
) -> None:
    document = analyze(
        tmp_path,
        outage_requests(),
        healthy(6),
        signals=[RUNTIME_ENDPOINTS],
        window=(0, 60_000),
    )
    false_healthy = signal_of(document, "runtime-ready-endpoints")["falseHealthy"]
    # Inner: from the finish of the first read to the start of the last one.
    # Outer: no read bounds the state, so the window does.
    assert false_healthy["innerMs"] == 45_000 - 22_000
    assert false_healthy["outerMs"] == 45_000 - 22_000


def test_a_reading_with_no_value_is_not_counted_as_healthy(tmp_path: Path) -> None:
    samples = [
        sample(),
        sample(),
        sample(),
        sample(workload=False),
        sample(workload=False),
        sample(),
    ]
    document = analyze(
        tmp_path,
        outage_requests(),
        samples,
        signals=[RUNTIME_ENDPOINTS],
        window=(0, 60_000),
    )
    signal = signal_of(document, "runtime-ready-endpoints")
    assert signal["byState"] == {"healthy": 4, "problem": 0, "not-observed": 2}
    # The stream states no value from 20,200 to 50,000 ms, and that time is
    # not in the inner figure.
    assert signal["falseHealthy"]["signalNotObservedMs"] == 45_000 - 22_000
    assert signal["falseHealthy"]["innerMs"] == 0
    assert signal["falseHealthy"]["outerMs"] == 45_000 - 22_000
    assert signal["detectionLag"]["reason"] == "never-indicated"


def test_an_open_episode_is_failing_to_the_end_of_the_window(tmp_path: Path) -> None:
    requests = small((10_000, True), (20_000, True), (22_000, False), (30_000, False))
    document = analyze(
        tmp_path, requests, healthy(6), signals=[RUNTIME_ENDPOINTS], window=(0, 60_000)
    )
    false_healthy = signal_of(document, "runtime-ready-endpoints")["falseHealthy"]
    assert false_healthy["callerMs"] == 60_000 - 22_000


def test_an_omitted_deployment_count_is_not_a_count_of_zero(tmp_path: Path) -> None:
    samples = [sample(), sample(runtime=0), sample(runtime=1), sample()]
    document = analyze(
        tmp_path,
        outage_requests(),
        samples,
        signals=[
            RUNTIME_REPLICAS,
            {
                **RUNTIME_REPLICAS,
                "id": "available",
                "source": "deployment-available-replicas",
            },
        ],
        window=(0, 60_000),
    )
    for identifier in ("runtime-ready-replicas", "available"):
        signal = signal_of(document, identifier)
        assert signal["byState"] == {"healthy": 2, "problem": 1, "not-observed": 1}
        assert signal["detectionLag"]["firstIndication"]["index"] == 3


def test_a_pod_with_no_ready_condition_leaves_the_pod_count_without_a_value(
    tmp_path: Path,
) -> None:
    run_id = "run-1"
    samples = [sample(), sample(runtime=1), sample()]
    del samples[2]["workload"][-2]["status"]["conditions"]
    texts: dict[str, str | None] = {
        "caller": caller_text(run_id, outage_requests(), finished=60_000),
        **streams(tmp_path, run_id, samples),
    }
    document = analysis.analyze(
        text_of(declaration(run_id, [RUNTIME_PODS], window=(0, 60_000))), texts
    )
    assert signal_of(document, "runtime-ready-pods")["byState"] == {
        "healthy": 1,
        "problem": 1,
        "not-observed": 1,
    }


@pytest.mark.parametrize(
    ("signal", "changed", "states"),
    [
        (SYNC, {"sync": "OutOfSync"}, {"healthy": 2, "problem": 1, "not-observed": 0}),
        (
            HEALTH,
            {"health": "Degraded"},
            {"healthy": 2, "problem": 1, "not-observed": 0},
        ),
        (SYNC, {"sync": None}, {"healthy": 2, "problem": 0, "not-observed": 1}),
        (HEALTH, {"health": None}, {"healthy": 2, "problem": 0, "not-observed": 1}),
        (SYNC, {"application": False}, {"healthy": 2, "problem": 0, "not-observed": 1}),
    ],
)
def test_an_application_signal_reads_the_reported_word(
    tmp_path: Path,
    signal: dict[str, Any],
    changed: dict[str, Any],
    states: dict[str, int],
) -> None:
    samples = [sample(), sample(**changed), sample()]
    document = analyze(
        tmp_path, outage_requests(), samples, signals=[signal], window=(0, 60_000)
    )
    assert signal_of(document, signal["id"])["byState"] == states


def test_a_signal_with_no_value_in_any_reading_is_not_computable(
    tmp_path: Path,
) -> None:
    samples = [sample(health=None), sample(health=None)]
    document = analyze(
        tmp_path, outage_requests(), samples, signals=[HEALTH], window=(0, 60_000)
    )
    signal = signal_of(document, "application-health")
    assert (signal["state"], signal["reason"]) == (
        "not-computable",
        "signal-never-observed",
    )
    assert signal["falseHealthy"] is None
    assert "signals.application-health" in document["withoutValue"]


def test_the_document_repeats_what_a_signal_declared(tmp_path: Path) -> None:
    document = analyze(
        tmp_path, steady(), healthy(2), signals=[RUNTIME_ENDPOINTS, SYNC]
    )
    assert signal_of(document, "runtime-ready-endpoints")["declared"] == {
        "tier": RUNTIME,
        "problemBelow": 2,
    }
    assert signal_of(document, "application-sync")["declared"] == {
        "healthyValues": ["Synced"]
    }
    assert signal_of(document, "application-sync")["stream"] == "argo"


# --------------------------------------------------------------------------
# Stabilized recovery
# --------------------------------------------------------------------------


def recovery_of(
    tmp_path: Path,
    requests: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    **options: Any,
) -> dict[str, Any]:
    document = analyze(tmp_path, requests, samples, **options)
    return dict(document["stabilizedRecovery"])


def spaced(count: int, step: int, first: int = 10_000) -> list[tuple[int, bool]]:
    return [(first + number * step, True) for number in range(count)]


def test_ten_successes_over_sixty_seconds_with_held_readings_stabilize(
    tmp_path: Path,
) -> None:
    requests = small(*spaced(10, 7000))
    recovery = recovery_of(tmp_path, requests, healthy(10), window=(0, 100_000))
    assert recovery["stabilized"] is True
    assert recovery["stabilizedAt"] == at(73_000)
    assert recovery["span"] == {
        "first": {"sequence": 1, "finishedAt": at(10_000)},
        "last": {"sequence": 10, "finishedAt": at(73_000)},
        "successes": 10,
        "ms": 63_000,
        "readingsInside": {
            "desiredRevision": 7,
            "readyReplicas": 7,
            "runtimeReadyEndpoints": 7,
        },
        "largestTimeWithNoReadingMs": {
            "desiredRevision": 9850,
            "readyReplicas": 9800,
            "runtimeReadyEndpoints": 9800,
        },
    }
    assert recovery["rule"]["consecutiveSuccesses"] == 10
    assert recovery["rule"]["spanMs"] == 60_000
    assert recovery["sinceFault"] is None
    assert recovery["requestsFailedSinceFault"] is None


def test_nine_successes_do_not_stabilize(tmp_path: Path) -> None:
    recovery = recovery_of(
        tmp_path, small(*spaced(9, 9000)), healthy(10), window=(0, 100_000)
    )
    assert (recovery["state"], recovery["stabilized"]) == ("computed", False)
    assert recovery["longestSuccessRun"] == {"successes": 9, "spanMs": 72_000}


@pytest.mark.parametrize(("last", "stabilized"), [(69_999, False), (70_000, True)])
def test_the_span_is_sixty_seconds_and_not_one_millisecond_less(
    tmp_path: Path, last: int, stabilized: bool
) -> None:
    entries = [*spaced(9, 1000), (last, True)]
    recovery = recovery_of(tmp_path, small(*entries), healthy(10), window=(0, 100_000))
    assert recovery["stabilized"] is stabilized


def test_a_failure_starts_the_count_again(tmp_path: Path) -> None:
    entries = [*spaced(9, 7000), (73_000, False), *spaced(10, 7000, first=74_000)]
    recovery = recovery_of(tmp_path, small(*entries), healthy(15), window=(0, 150_000))
    assert recovery["span"]["first"]["finishedAt"] == at(74_000)
    assert recovery["stabilizedAt"] == at(137_000)


@pytest.mark.parametrize(
    "changed",
    [
        {"runtime": 1, "runtime_replicas": 2},
        {"runtime": 2, "runtime_replicas": 1},
        {"api": 1},
        {"sync": "OutOfSync"},
        {"revision": OTHER_COMMIT},
    ],
)
def test_a_reading_that_does_not_hold_moves_the_start_of_the_span(
    tmp_path: Path, changed: dict[str, Any]
) -> None:
    """The reading at 20 seconds does not hold. The span starts after it."""
    samples = healthy(12)
    samples[2] = sample(**changed)
    recovery = recovery_of(
        tmp_path, small(*spaced(20, 5000)), samples, window=(0, 120_000)
    )
    assert recovery["stabilized"] is True
    assert recovery["span"]["first"]["finishedAt"] == at(25_000)
    assert recovery["stabilizedAt"] == at(85_000)
    assert sum(entry["notHeld"] for entry in recovery["conditions"].values()) == 1


@pytest.mark.parametrize(
    "changed", [{"workload": False}, {"application": False}, {"sync": None}]
)
def test_a_reading_with_no_value_is_not_a_reading_that_holds(
    tmp_path: Path, changed: dict[str, Any]
) -> None:
    """The reading at 20 seconds has no value. No value is stated from the read
    before it to the read after it, so the span starts after 30 seconds."""
    samples = healthy(12)
    samples[2] = sample(**changed)
    recovery = recovery_of(
        tmp_path, small(*spaced(20, 5000)), samples, window=(0, 120_000)
    )
    assert recovery["span"]["first"]["finishedAt"] == at(35_000)
    assert recovery["stabilizedAt"] == at(95_000)


def test_no_value_at_the_last_reading_does_not_stabilize(tmp_path: Path) -> None:
    samples = [*healthy(3), *[sample(workload=False) for _ in range(9)]]
    recovery = recovery_of(
        tmp_path, small(*spaced(20, 5000)), samples, window=(0, 120_000)
    )
    assert recovery["stabilized"] is False


def test_a_span_with_no_reading_inside_does_not_stabilize(tmp_path: Path) -> None:
    """Each condition holds at one read, and the caller succeeds for 60 seconds
    after it. The streams state nothing about that time."""
    recovery = recovery_of(
        tmp_path, small(*spaced(10, 7000)), healthy(1), window=(0, 100_000)
    )
    assert (recovery["state"], recovery["stabilized"]) == ("computed", False)


@pytest.mark.parametrize("missing", ["argo", "deployments", "endpoints"])
def test_without_a_stream_of_the_expected_state_nothing_is_stabilized(
    tmp_path: Path, missing: str
) -> None:
    recovery = recovery_of(
        tmp_path,
        small(*spaced(10, 7000)),
        healthy(10),
        window=(0, 100_000),
        without=(missing,),
    )
    assert (recovery["state"], recovery["reason"]) == (
        "not-computable",
        "stream-not-given",
    )
    assert recovery["stabilized"] is None
    assert recovery["stabilizedAt"] is None


def test_the_search_starts_when_the_fault_command_returned(tmp_path: Path) -> None:
    entries = [(4000, False), *spaced(20, 5000, first=5000)]
    recovery = recovery_of(
        tmp_path,
        small(*entries),
        healthy(12),
        recorded=fault_events(18_000, 21_000),
        window=(0, 120_000),
    )
    assert recovery["searchedFrom"] == at(21_000)
    assert recovery["span"]["first"]["finishedAt"] == at(25_000)
    assert recovery["stabilizedAt"] == at(85_000)
    assert recovery["sinceFault"] == {
        "faultStartedAt": at(18_000),
        "faultFinishedAt": at(21_000),
        "fromFaultStartedMs": 67_000,
        "fromFaultFinishedMs": 64_000,
    }
    # The request that failed before the fault is not counted.
    assert recovery["requestsFailedSinceFault"] == 0


def test_the_failed_requests_since_the_fault_are_counted(tmp_path: Path) -> None:
    entries = [
        (5000, True),
        (12_000, False),
        (14_000, False),
        *spaced(10, 7000, first=20_000),
    ]
    recovery = recovery_of(
        tmp_path,
        small(*entries),
        healthy(10),
        recorded=fault_events(10_000, 10_500),
        window=(0, 100_000),
    )
    assert recovery["stabilizedAt"] == at(83_000)
    assert recovery["requestsFailedSinceFault"] == 2


# --------------------------------------------------------------------------
# Refusals
# --------------------------------------------------------------------------


def _mutated(change: Callable[[dict[str, Any]], None]) -> str:
    document = declaration("run-1", [RUNTIME_ENDPOINTS, SYNC])
    change(document)
    return json.dumps(document)


def _set(path: tuple[Any, ...], value: Any) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        target: Any = document
        for name in path[:-1]:
            target = target[name]
        target[path[-1]] = value

    return change


def _drop(path: tuple[Any, ...]) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        target: Any = document
        for name in path[:-1]:
            target = target[name]
        del target[path[-1]]

    return change


DECLARATION_FAULTS: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
    ("analysis-declaration-unsupported", _set(("note",), "free text")),
    ("analysis-declaration-unsupported", _drop(("signals",))),
    ("analysis-declaration-unsupported", _set(("schema",), "another/v1")),
    ("analysis-declaration-unsupported", _set(("runId",), "has a space")),
    ("analysis-declaration-unsupported", _set(("experimentId",), 7)),
    ("analysis-declaration-unsupported", _set(("expected",), None)),
    ("analysis-declaration-unsupported", _set(("expected", "desiredRevision"), "main")),
    ("analysis-declaration-unsupported", _set(("expected", "desiredRevision"), None)),
    ("analysis-declaration-unsupported", _drop(("expected", "readyReplicas", API))),
    ("analysis-declaration-unsupported", _set(("expected", "readyReplicas", API), 0)),
    (
        "analysis-declaration-unsupported",
        _set(("expected", "readyReplicas", API), True),
    ),
    ("analysis-declaration-unsupported", _set(("expected", "readyReplicas", API), 2.0)),
    (
        "analysis-declaration-unsupported",
        _set(("expected", "runtimeReadyEndpoints"), 65),
    ),
    ("analysis-declaration-unsupported", _set(("expected", "tiers"), {})),
    ("analysis-window-invalid", _set(("window",), None)),
    ("analysis-window-invalid", _set(("window", "note"), "x")),
    ("analysis-window-invalid", _set(("window", "from"), "2026-10-12T08:00:00Z")),
    (
        "analysis-window-invalid",
        _set(("window", "to"), "2026-10-12T10:00:00.000+02:00"),
    ),
    ("analysis-window-invalid", _set(("window", "to"), "2026-10-12T08:00:00.000Z")),
    ("analysis-window-invalid", _set(("window", "to"), "2026-10-12T07:00:00.000Z")),
    ("analysis-window-invalid", _set(("window", "from"), "2026-02-30T08:00:00.000Z")),
    ("analysis-signal-unsupported", _set(("signals",), {})),
    ("analysis-signal-unsupported", _set(("signals",), [RUNTIME_ENDPOINTS] * 2)),
    ("analysis-signal-unsupported", _set(("signals", 0), "runtime")),
    ("analysis-signal-unsupported", _set(("signals", 0, "id"), "Has Upper")),
    ("analysis-signal-unsupported", _set(("signals", 0, "source"), "request-rate")),
    ("analysis-signal-unsupported", _set(("signals", 0, "tier"), "another-tier")),
    ("analysis-signal-unsupported", _set(("signals", 0, "tier"), [RUNTIME])),
    ("analysis-signal-unsupported", _set(("signals", 0, "problemBelow"), 0)),
    ("analysis-signal-unsupported", _set(("signals", 0, "problemBelow"), "2")),
    ("analysis-signal-unsupported", _set(("signals", 0, "healthyValues"), ["Synced"])),
    ("analysis-signal-unsupported", _drop(("signals", 0, "tier"))),
    ("analysis-signal-unsupported", _set(("signals", 1, "healthyValues"), [])),
    ("analysis-signal-unsupported", _set(("signals", 1, "healthyValues"), "Synced")),
    ("analysis-signal-unsupported", _set(("signals", 1, "healthyValues"), ["a b"])),
    ("analysis-signal-unsupported", _set(("signals", 1, "healthyValues"), ["A", "A"])),
    ("analysis-signal-unsupported", _set(("signals", 1, "tier"), RUNTIME)),
    (
        "analysis-signal-unsupported",
        _set(("signals",), [{**SYNC, "id": f"s{n}"} for n in range(17)]),
    ),
]


@pytest.mark.parametrize(
    ("rule", "change"),
    DECLARATION_FAULTS,
    ids=[f"{rule}-{number}" for number, (rule, _) in enumerate(DECLARATION_FAULTS)],
)
def test_a_declaration_that_does_not_hold_a_rule_is_refused(
    rule: str, change: Callable[[dict[str, Any]], None]
) -> None:
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.read_declaration(_mutated(change))
    assert refused.value.rule == rule


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[]",
        "not json",
        '{"schema": 1, "schema": 2}',
        "[" * 100_000,
    ],
    ids=["empty", "list", "not-json", "member-twice", "nested"],
)
def test_a_declaration_that_is_not_one_object_is_refused(text: str) -> None:
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.read_declaration(text)
    assert refused.value.rule == "analysis-declaration-unreadable"


def test_a_declaration_that_holds_each_rule_is_read() -> None:
    document = declaration("run-1", list(_each_source()))
    assert analysis.read_declaration(json.dumps(document)) == document


def _each_source() -> Iterator[dict[str, Any]]:
    for number, (source, (_, form, _)) in enumerate(analysis.SIGNAL_SOURCES.items()):
        if form == "count":
            yield {"id": f"s{number}", "source": source, "tier": API, "problemBelow": 1}
        else:
            yield {"id": f"s{number}", "source": source, "healthyValues": ["Ok"]}


def _inputs(tmp_path: Path) -> dict[str, str | None]:
    return {
        "caller": caller_text("run-1", steady()),
        **streams(tmp_path, "run-1", healthy(2)),
        analysis.EVENTS: events_text(tmp_path, "run-1", []),
    }


def test_each_input_is_read_when_each_is_given(tmp_path: Path) -> None:
    document = analysis.analyze(text_of(declaration("run-1")), _inputs(tmp_path))
    assert document["inputs"] == dict.fromkeys(analysis.INPUTS, "read")


@pytest.mark.parametrize(
    ("name", "text", "stated"),
    [
        (
            "caller",
            '{"record":"header"}\n',
            "caller: caller-record-members-unsupported",
        ),
        ("caller", "not json\n", "caller: caller-record-unreadable"),
        (
            "endpoints",
            '{"record":"header"}\n',
            "endpoints: timeline-members-unsupported",
        ),
        ("argo", "", "argo: timeline-header-unsupported"),
        (
            "operator-events",
            '{"record":"header"}\n',
            "operator-events: events-members-unsupported",
        ),
    ],
)
def test_an_input_that_its_tool_refuses_is_refused_by_the_rule_of_that_tool(
    tmp_path: Path, name: str, text: str, stated: str
) -> None:
    texts = {**_inputs(tmp_path), name: text}
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.analyze(text_of(declaration("run-1")), texts)
    assert refused.value.rule == "analysis-input-refused"
    assert refused.value.message == stated


def test_a_refusal_does_not_repeat_a_value_of_the_refused_file(tmp_path: Path) -> None:
    """The reader of another tool can quote a value. The analysis names its rule."""
    lines = _inputs(tmp_path)["caller"]
    assert lines is not None
    hostile = lines.replace('"worker":0', '"worker":0,"prompt":"a private sentence"', 1)
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.analyze(
            text_of(declaration("run-1")), {**_inputs(tmp_path), "caller": hostile}
        )
    assert "private" not in str(refused.value)
    assert refused.value.message == "caller: caller-record-members-unsupported"


def test_an_open_log_of_events_is_refused(tmp_path: Path) -> None:
    texts = _inputs(tmp_path)
    log = texts[analysis.EVENTS]
    assert log is not None
    texts[analysis.EVENTS] = "".join(log.splitlines(keepends=True)[:-1])
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.analyze(text_of(declaration("run-1")), texts)
    assert refused.value.message == "operator-events: events-end-missing"


def test_no_caller_record_is_refused(tmp_path: Path) -> None:
    texts = {**_inputs(tmp_path), "caller": None}
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.analyze(text_of(declaration("run-1")), texts)
    assert refused.value.rule == "analysis-input-refused"


def test_a_stream_under_another_name_is_refused(tmp_path: Path) -> None:
    texts = _inputs(tmp_path)
    texts["endpoints"], texts["pods"] = texts["pods"], texts["endpoints"]
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.analyze(text_of(declaration("run-1")), texts)
    assert refused.value.rule == "analysis-input-misnamed"


def test_an_input_with_an_unregistered_name_is_refused(tmp_path: Path) -> None:
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.analyze(
            text_of(declaration("run-1")), {**_inputs(tmp_path), "telemetry": "x"}
        )
    assert refused.value.rule == "analysis-input-misnamed"


@pytest.mark.parametrize("name", list(analysis.INPUTS))
def test_an_input_of_another_run_is_refused(tmp_path: Path, name: str) -> None:
    texts = _inputs(tmp_path)
    other = {
        "caller": caller_text("run-2", steady()),
        **streams(tmp_path, "run-2", healthy(2)),
        analysis.EVENTS: events_text(tmp_path, "run-2", []),
    }
    texts[name] = other[name]
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.analyze(text_of(declaration("run-1")), texts)
    assert refused.value.rule == "analysis-identity-differs"
    assert refused.value.message.startswith(name)


def test_an_input_of_another_experiment_is_refused(tmp_path: Path) -> None:
    texts = _inputs(tmp_path)
    texts["caller"] = caller_text("run-1", steady(), experiment_id="another-experiment")
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.analyze(text_of(declaration("run-1")), texts)
    assert refused.value.rule == "analysis-identity-differs"


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------

#: Words of a figure that the analysis does not compute.
BARRED = re.compile(
    r"percent|availability|confidence|significan|p9[59]|percentile|\bslo\b|"
    r"errorRate|passed|verdict",
    re.IGNORECASE,
)


def _names(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for name, inner in value.items():
            yield name
            yield from _names(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _names(inner)


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_document_has_no_member_for_a_figure_that_is_not_computed(case: str) -> None:
    document = stored_analysis(case)
    assert [name for name in _names(document) if BARRED.search(name)] == []
    assert "resultState" not in set(_names(document))
    assert document["limitations"] == list(analysis.LIMITATIONS)
    assert document["doesNotEstablish"] == list(analysis.DOES_NOT_ESTABLISH)
    assert document["clocks"]["skew"] == "not-measured"


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_document_holds_no_request_identifier_and_no_pod_identity(case: str) -> None:
    files = committed(case)
    text = files["analysis.json"]
    run_id = json.loads(text)["runId"]
    assert f"{run_id}-00001" in files["caller.jsonl"]
    assert "requestId" not in text
    assert re.search(rf"{run_id}-\d{{5}}", text) is None
    for number in (1, 2, 11, 12, 100, 110, 200, 210):
        assert uid(number) not in text
    for tier in (API, RUNTIME):
        for suffix in ("a", "b", "rs"):
            assert f"{tier}-{suffix}" not in text


@pytest.mark.parametrize("case", sorted(CASES))
def test_each_metric_with_no_value_states_a_registered_reason(case: str) -> None:
    def reasons(value: Any) -> Iterator[str]:
        if isinstance(value, dict):
            if value.get("state") == analysis.NOT_COMPUTABLE:
                yield value["reason"]
            for inner in value.values():
                yield from reasons(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from reasons(inner)

    document = stored_analysis(case)
    found = set(reasons(document))
    assert found <= set(analysis.REASONS)
    if case == "missing-signal":
        assert {"stream-not-given", "never-indicated"} <= found
    figure = document["caller"]["failureEpisodes"]
    assert (figure["callerFailureEpisodeMs"] is None) is (figure["reason"] is not None)
    assert figure["reason"] is None or figure["reason"] in analysis.REASONS


def test_the_text_of_a_document_is_the_same_each_time(tmp_path: Path) -> None:
    files = case_concurrency(tmp_path)
    again = case_concurrency(tmp_path)
    assert files == again
    one = analysis.analysis_text(analysis_of(files))
    assert one == analysis.analysis_text(analysis_of(again))
    assert one.endswith("}\n") and "\r" not in one
    assert json.loads(one) == analysis_of(files)


def test_the_analysis_role_of_the_evidence_layout_is_a_derived_role() -> None:
    assert ROLES["analysis"].kind == DERIVED


# --------------------------------------------------------------------------
# The aggregate
# --------------------------------------------------------------------------


def run_document(run_id: str, episode_ms: int | None) -> dict[str, Any]:
    return {
        "schema": analysis.SCHEMA,
        "experimentId": EXPERIMENT,
        "runId": run_id,
        "caller": {"failureEpisodes": {"callerFailureEpisodeMs": episode_ms}},
    }


METRIC = "caller-failure-episode-ms"


def test_the_aggregate_of_three_counted_runs_is_the_median() -> None:
    document = analysis.aggregate(
        METRIC,
        [
            (run_document("run-3", 900), "FAILED"),
            (run_document("run-1", 100), "PASSED"),
            (run_document("run-2", 20_000), "PASSED"),
        ],
    )
    assert document == {
        "schema": analysis.AGGREGATE_SCHEMA,
        "experimentId": EXPERIMENT,
        "metric": METRIC,
        "path": ["caller", "failureEpisodes", "callerFailureEpisodeMs"],
        "rule": "median-of-three",
        "runs": [
            {
                "runId": "run-1",
                "resultState": "PASSED",
                "counted": True,
                "exclusion": None,
                "value": 100,
            },
            {
                "runId": "run-2",
                "resultState": "PASSED",
                "counted": True,
                "exclusion": None,
                "value": 20_000,
            },
            {
                "runId": "run-3",
                "resultState": "FAILED",
                "counted": True,
                "exclusion": None,
                "value": 900,
            },
        ],
        "countedRuns": 3,
        "state": "computed",
        "reason": None,
        "median": 900,
        "statement": analysis.AGGREGATE_STATEMENT,
    }
    assert [name for name in _names(document) if BARRED.search(name)] == []
    assert "mean" not in document and "average" not in document


def test_a_failed_run_is_counted_and_is_not_dropped() -> None:
    """A run that worsens the figure stays in it."""
    runs = [
        (run_document("run-1", 100), "PASSED"),
        (run_document("run-2", 200), "PASSED"),
        (run_document("run-3", 90_000), "FAILED"),
    ]
    assert analysis.aggregate(METRIC, runs)["median"] == 200
    assert all(entry["counted"] for entry in analysis.aggregate(METRIC, runs)["runs"])


REASONS = {
    "INCONCLUSIVE": "The evidence decides no criterion. This text is synthetic.",
    "REFUSED": "A precondition did not hold. This text is synthetic.",
    "ABORTED": "An abort condition stopped the run. This text is synthetic.",
}
PREREGISTRATION = {
    "freezeRecord": "docs/proof/experiments/example/freeze-r1.v1alpha1.json",
    "freezeRevision": 1,
    "freezeContentSha256": "a" * 64,
}


def exclusion_reasons(**changes: Any) -> dict[str, Any]:
    """Synthetic exclusion reasons: one for each state that is not counted."""
    policy: dict[str, Any] = {
        "experimentId": EXPERIMENT,
        "reasons": [
            {"id": f"reason-{state.lower()}", "resultState": state, "reason": text}
            for state, text in REASONS.items()
        ],
    }
    policy.update(changes)
    return policy


def excluded(state: str, **changes: Any) -> analysis.RunResult:
    """The result of a run that is not counted, with its registered reason."""
    members: dict[str, Any] = {
        "reason": REASONS[state],
        "exclusion_reasons": exclusion_reasons(),
        "preregistration": PREREGISTRATION,
    }
    members.update(changes)
    return analysis.RunResult(state, **members)


def three_and(result: str | analysis.RunResult) -> list[tuple[dict[str, Any], Any]]:
    return [
        (run_document("run-1", 100), "PASSED"),
        (run_document("run-2", 200), "PASSED"),
        (run_document("run-3", 300), "FAILED"),
        (run_document("run-4", 5), result),
    ]


def refused_exclusion(result: str | analysis.RunResult) -> analysis.AnalysisRefused:
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.aggregate(METRIC, three_and(result))
    return refused.value


@pytest.mark.parametrize("state", list(analysis.EXCLUDED_STATES))
def test_an_excluded_run_is_listed_with_its_registered_reason(state: str) -> None:
    document = analysis.aggregate(METRIC, three_and(excluded(state)))
    assert document["median"] == 200
    assert document["countedRuns"] == 3
    assert document["runs"][3] == {
        "runId": "run-4",
        "resultState": state,
        "counted": False,
        "exclusion": {
            "reasonId": f"reason-{state.lower()}",
            "reason": REASONS[state],
            "preregistration": PREREGISTRATION,
        },
        "value": 5,
    }
    assert document["schema"] == "inferops.io/reliability-aggregate/v1alpha2"


@pytest.mark.parametrize("state", list(analysis.EXCLUDED_STATES))
def test_a_result_state_alone_leaves_no_run_out(state: str) -> None:
    """Before this change a state alone left a run out, with a generic reason."""
    refused = refused_exclusion(state)
    assert refused.rule == "analysis-exclusion-unregistered"
    assert "no exclusion reason is registered" in refused.message
    # A record that registers no reason is the same refusal.
    refused = refused_exclusion(excluded(state, exclusion_reasons=None))
    assert refused.rule == "analysis-exclusion-unregistered"
    refused = refused_exclusion(
        excluded(state, exclusion_reasons=exclusion_reasons(reasons=[]))
    )
    assert refused.rule == "analysis-exclusion-unregistered"


@pytest.mark.parametrize("reason", [None, "", 7, ["reason"], {"reason": "text"}])
def test_a_run_that_is_not_counted_and_states_no_reason_is_refused(
    reason: Any,
) -> None:
    refused = refused_exclusion(excluded("ABORTED", reason=reason))
    assert refused.rule == "analysis-exclusion-unregistered"
    assert "states no reason" in refused.message


@pytest.mark.parametrize(
    "change",
    [
        lambda text: text + " ",
        lambda text: " " + text,
        lambda text: text.lower(),
        lambda text: text[:-1],
        lambda text: text.replace("This text", "This  text"),
        lambda text: text + " Excluded after inspection.",
        lambda text: "Excluded after inspection. No preregistered reason exists.",
    ],
)
def test_a_reason_that_is_not_the_registered_text_is_refused(
    change: Callable[[str], str],
) -> None:
    """The comparison is character for character. No reason is read as near."""
    reason = change(REASONS["INCONCLUSIVE"])
    assert reason != REASONS["INCONCLUSIVE"]
    refused = refused_exclusion(excluded("INCONCLUSIVE", reason=reason))
    assert refused.rule == "analysis-exclusion-unregistered"
    assert "is not a registered exclusion reason" in refused.message


def test_a_reason_of_another_result_state_is_refused() -> None:
    refused = refused_exclusion(excluded("INCONCLUSIVE", reason=REASONS["ABORTED"]))
    assert refused.rule == "analysis-exclusion-unregistered"
    assert "another result state" in refused.message


def test_a_reason_of_another_experiment_is_refused() -> None:
    policy = exclusion_reasons(experimentId="another-experiment")
    refused = refused_exclusion(excluded("REFUSED", exclusion_reasons=policy))
    assert refused.rule == "analysis-exclusion-unregistered"
    assert "another experiment" in refused.message


def test_a_reason_that_is_registered_for_named_runs_is_held_to_them() -> None:
    policy = exclusion_reasons()
    policy["reasons"][2]["runIds"] = ["run-9", "run-4"]
    document = analysis.aggregate(
        METRIC, three_and(excluded("ABORTED", exclusion_reasons=policy))
    )
    assert document["runs"][3]["exclusion"]["reasonId"] == "reason-aborted"
    policy["reasons"][2]["runIds"] = ["run-9"]
    refused = refused_exclusion(excluded("ABORTED", exclusion_reasons=policy))
    assert refused.rule == "analysis-exclusion-unregistered"
    assert "other runs" in refused.message


def _other_members(policy: dict[str, Any]) -> None:
    policy["note"] = "another member"


def _no_reasons(policy: dict[str, Any]) -> None:
    del policy["reasons"]


def _reason_entry(**changes: Any) -> Callable[[dict[str, Any]], None]:
    def change(policy: dict[str, Any]) -> None:
        for name, value in changes.items():
            if value is ...:
                del policy["reasons"][0][name]
            else:
                policy["reasons"][0][name] = value

    return change


def _repeat_identifier(policy: dict[str, Any]) -> None:
    policy["reasons"][1]["id"] = policy["reasons"][0]["id"]


def _repeat_text(policy: dict[str, Any]) -> None:
    policy["reasons"].append({**policy["reasons"][0], "id": "second"})


def _too_many(policy: dict[str, Any]) -> None:
    policy["reasons"] = [
        {"id": f"reason-{n}", "resultState": "ABORTED", "reason": f"Reason {n}."}
        for n in range(analysis.MAX_EXCLUSION_REASONS + 1)
    ]


UNSUPPORTED_REASONS: dict[str, Callable[[dict[str, Any]], None]] = {
    "another member": _other_members,
    "no list of reasons": _no_reasons,
    "an experiment that is no identifier": lambda p: p.update(experimentId="a b"),
    "an experiment that is no text": lambda p: p.update(experimentId=7),
    "reasons that are no list": lambda p: p.update(reasons={"id": "x"}),
    "a reason that is no object": lambda p: p["reasons"].append("text"),
    "a reason with another member": _reason_entry(note="x"),
    "a reason with no identifier": _reason_entry(id=...),
    "a reason with an identifier that is no text": _reason_entry(id=1),
    "a reason for a counted state": _reason_entry(resultState="FAILED"),
    "a reason for a passed run": _reason_entry(resultState="PASSED"),
    "a reason for a state that is no text": _reason_entry(resultState=["ABORTED"]),
    "a reason with no text": _reason_entry(reason=""),
    "a reason that is no text": _reason_entry(reason=None),
    "a reason with white space at an end": _reason_entry(reason="A reason. "),
    "a reason that is too long": _reason_entry(reason="x" * 2001),
    "runs that are no list": _reason_entry(runIds="run-4"),
    "no run": _reason_entry(runIds=[]),
    "a run that is no identifier": _reason_entry(runIds=["run 4"]),
    "a run that is no text": _reason_entry(runIds=[4]),
    "a run twice": _reason_entry(runIds=["run-4", "run-4"]),
    "one identifier twice": _repeat_identifier,
    "one text twice for one state": _repeat_text,
    "too many reasons": _too_many,
}


@pytest.mark.parametrize("name", sorted(UNSUPPORTED_REASONS))
def test_exclusion_reasons_in_another_form_are_refused(name: str) -> None:
    """A record that is not in its form registers no reason, for any run."""
    policy = exclusion_reasons()
    UNSUPPORTED_REASONS[name](policy)
    refused = refused_exclusion(excluded("ABORTED", exclusion_reasons=policy))
    assert refused.rule == "analysis-exclusion-reasons-unsupported"


@pytest.mark.parametrize("policy", ["text", ["list"], 7, True])
def test_exclusion_reasons_that_are_no_object_are_refused(policy: Any) -> None:
    refused = refused_exclusion(excluded("ABORTED", exclusion_reasons=policy))
    assert refused.rule == "analysis-exclusion-reasons-unsupported"


def test_one_reason_text_can_be_registered_for_two_states() -> None:
    policy = exclusion_reasons()
    policy["reasons"][1]["reason"] = REASONS["ABORTED"]
    document = analysis.aggregate(
        METRIC,
        three_and(
            excluded("REFUSED", reason=REASONS["ABORTED"], exclusion_reasons=policy)
        ),
    )
    assert document["runs"][3]["exclusion"]["reasonId"] == "reason-refused"


@pytest.mark.parametrize("state", ["PASSED", "FAILED"])
def test_a_counted_run_is_counted_whatever_reason_it_states(state: str) -> None:
    """A registered reason beside a counted state does not leave the run out."""
    result = analysis.RunResult(
        state, REASONS["ABORTED"], exclusion_reasons(), PREREGISTRATION
    )
    document = analysis.aggregate(
        METRIC,
        [
            (run_document("run-1", 100), "PASSED"),
            (run_document("run-2", 200), "PASSED"),
            (run_document("run-3", 90_000), result),
        ],
    )
    assert document["runs"][2] == {
        "runId": "run-3",
        "resultState": state,
        "counted": True,
        "exclusion": None,
        "value": 90_000,
    }
    assert (document["countedRuns"], document["median"]) == (3, 200)


def test_a_refusal_of_an_exclusion_repeats_no_text_of_a_reason() -> None:
    marker = "MARKER-7f3a"
    policy = exclusion_reasons()
    policy["reasons"][0]["reason"] = f"A registered reason with {marker}."
    for result in (
        excluded("ABORTED", reason=f"A stated reason with {marker}."),
        excluded("ABORTED", reason=f"A registered reason with {marker}."),
        excluded("INCONCLUSIVE", reason=marker, exclusion_reasons=policy),
        excluded("ABORTED", exclusion_reasons={**policy, "experimentId": marker}),
        excluded("ABORTED", exclusion_reasons={**policy, marker: marker}),
    ):
        refused = refused_exclusion(result)
        assert marker not in str(refused)
        assert "run-4" in refused.message


def test_an_excluded_run_with_no_value_stays_listed_and_a_counted_one_is_not_dropped() -> (
    None
):
    """An exclusion does not hide a counted run that has no value."""
    document = analysis.aggregate(
        METRIC,
        [
            (run_document("run-1", 100), "PASSED"),
            (run_document("run-2", None), "FAILED"),
            (run_document("run-3", 300), "PASSED"),
            (run_document("run-4", None), excluded("ABORTED")),
        ],
    )
    assert (document["countedRuns"], document["reason"], document["median"]) == (
        3,
        "counted-run-without-value",
        None,
    )
    assert [entry["counted"] for entry in document["runs"]] == [True, True, True, False]


def test_the_preregistration_of_an_exclusion_is_repeated_and_is_not_read() -> None:
    result = excluded("ABORTED", preregistration=None)
    document = analysis.aggregate(METRIC, three_and(result))
    assert document["runs"][3]["exclusion"]["preregistration"] is None
    given = dict(PREREGISTRATION)
    document = analysis.aggregate(
        METRIC, three_and(excluded("ABORTED", preregistration=given))
    )
    stated = document["runs"][3]["exclusion"]["preregistration"]
    assert stated == given and stated is not given
    for other in (5, ["freeze"], "freeze-r1"):
        refused = refused_exclusion(excluded("ABORTED", preregistration=other))
        assert refused.rule == "analysis-aggregate-unsupported"


def test_a_counted_run_with_no_value_leaves_no_median() -> None:
    """An open episode in one run is not a run that is left out."""
    document = analysis.aggregate(
        METRIC,
        [
            (run_document("run-1", 100), "PASSED"),
            (run_document("run-2", None), "FAILED"),
            (run_document("run-3", 300), "PASSED"),
        ],
    )
    assert (document["state"], document["reason"], document["median"]) == (
        "not-computable",
        "counted-run-without-value",
        None,
    )
    assert [entry["value"] for entry in document["runs"]] == [100, None, 300]


@pytest.mark.parametrize("count", [1, 2, 4])
def test_another_number_of_counted_runs_has_no_median(count: int) -> None:
    runs = [(run_document(f"run-{n}", 100 * n), "PASSED") for n in range(1, count + 1)]
    document = analysis.aggregate(METRIC, runs)
    assert (document["reason"], document["median"]) == ("not-three-counted-runs", None)
    assert len(document["runs"]) == count


def test_an_exclusion_that_leaves_two_runs_leaves_no_median() -> None:
    document = analysis.aggregate(
        METRIC,
        [
            (run_document("run-1", 100), "PASSED"),
            (run_document("run-2", 200), excluded("INCONCLUSIVE")),
            (run_document("run-3", 300), "PASSED"),
        ],
    )
    assert (document["countedRuns"], document["median"]) == (2, None)


@pytest.mark.parametrize("value", [True, 1.5, "100", [100], {"ms": 100}])
def test_a_value_that_is_not_a_whole_number_is_no_value(value: Any) -> None:
    runs = [
        (run_document("run-1", 100), "PASSED"),
        (run_document("run-2", value), "PASSED"),
        (run_document("run-3", 300), "PASSED"),
    ]
    document = analysis.aggregate(METRIC, runs)
    assert document["runs"][1]["value"] is None
    assert document["median"] is None


@pytest.mark.parametrize(
    "runs",
    [
        [],
        [(run_document("run-1", 1), "PASSED"), (run_document("run-1", 2), "PASSED")],
        [(run_document("run-1", 1), "SUCCEEDED")],
        [(run_document("run-1", 1), analysis.RunResult("SUCCEEDED"))],
        [(run_document("run-1", 1), analysis.RunResult(["ABORTED"]))],  # type: ignore[arg-type]
        [({**run_document("run-1", 1), "schema": "another/v1"}, "PASSED")],
        [({**run_document("run-1", 1), "runId": 7}, "PASSED")],
        [
            (run_document("run-1", 1), "PASSED"),
            ({**run_document("run-2", 1), "experimentId": "another"}, "PASSED"),
        ],
    ],
)
def test_an_aggregate_that_does_not_hold_its_rule_is_refused(
    runs: list[tuple[dict[str, Any], str | analysis.RunResult]],
) -> None:
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analysis.aggregate(METRIC, runs)
    assert refused.value.rule == "analysis-aggregate-unsupported"


def test_an_unregistered_metric_is_refused() -> None:
    with pytest.raises(analysis.AnalysisRefused):
        analysis.aggregate(
            "availability-percent", [(run_document("run-1", 1), "PASSED")]
        )


@pytest.mark.parametrize("metric", sorted(analysis.AGGREGATE_METRICS))
def test_each_registered_metric_is_a_figure_of_an_analysis_document(
    metric: str,
) -> None:
    """The path of each metric leads to a whole number in a committed case."""
    document: Any = stored_analysis("concurrency")
    for name in analysis.AGGREGATE_METRICS[metric]:
        document = document[name]
    assert type(document) is int


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def _case_arguments(case: str) -> list[str]:
    directory = FIXTURES / case
    arguments = ["analyze", "--declaration", str(directory / "declaration.json")]
    for name in analysis.INPUTS:
        path = directory / f"{name}.jsonl"
        if path.is_file():
            arguments += [f"--{name}", str(path)]
    return arguments


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_command_prints_the_committed_analysis(
    case: str, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    assert main(_case_arguments(case)) == 0
    printed = capfdbinary.readouterr().out
    assert printed == (FIXTURES / case / "analysis.json").read_bytes()
    assert b"\r" not in printed


def test_the_command_refuses_an_input_with_exit_status_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _case_arguments("abort")
    broken = tmp_path / "caller.jsonl"
    broken.write_text("not a record\n", "utf-8")
    arguments[arguments.index("--caller") + 1] = str(broken)
    assert main(arguments) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "REFUSED  analysis-input-refused: caller: caller-record-unreadable\n"
    )


def test_the_command_refuses_a_file_that_is_not_there(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _case_arguments("abort")
    arguments[arguments.index("--endpoints") + 1] = str(tmp_path / "absent.jsonl")
    assert main(arguments) == 3
    assert "endpoints: the file is not readable UTF-8 text" in capsys.readouterr().err
    arguments = _case_arguments("abort")
    arguments[arguments.index("--declaration") + 1] = str(tmp_path / "absent.json")
    assert main(arguments) == 3
    assert "analysis-declaration-unreadable" in capsys.readouterr().err


def test_the_command_needs_a_caller_record() -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["analyze", "--declaration", "declaration.json"])
    assert stopped.value.code == 2


def test_the_command_has_no_option_for_a_result_or_a_bound() -> None:
    """The command computes figures. It takes no bound to compare one with."""
    with pytest.raises(SystemExit) as stopped:
        main([*_case_arguments("abort"), "--bound-ms", "5000"])
    assert stopped.value.code == 2


def test_the_command_prints_the_aggregate_of_three_documents(
    tmp_path: Path, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    arguments = ["aggregate", "--metric", "requests-failed-in-window"]
    for number, case in enumerate(("zero-failure", "concurrency", "open-episode")):
        document = stored_analysis(case)
        document["experimentId"], document["runId"] = EXPERIMENT, f"run-{number}"
        path = tmp_path / f"{case}.json"
        path.write_text(json.dumps(document), "utf-8")
        arguments.append(f"{path}={'FAILED' if number else 'PASSED'}")
    assert main(arguments) == 0
    printed = json.loads(capfdbinary.readouterr().out)
    values = [entry["value"] for entry in printed["runs"]]
    assert printed["median"] == sorted(values)[1]
    assert values[0] == 0


def test_the_aggregate_command_refuses_a_file_that_is_not_a_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "analysis.json"
    path.write_text('{"schema": 1, "schema": 2}', "utf-8")
    assert main(["aggregate", "--metric", METRIC, f"{path}=PASSED"]) == 3
    assert "analysis-aggregate-unsupported" in capsys.readouterr().err


@pytest.mark.parametrize("state", list(analysis.EXCLUDED_STATES))
def test_the_aggregate_command_leaves_no_run_out(
    state: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command reads no freeze record, so it has no reason for an exclusion."""
    arguments = ["aggregate", "--metric", METRIC]
    for number in range(1, 5):
        path = tmp_path / f"run-{number}.json"
        path.write_text(
            json.dumps(run_document(f"run-{number}", 100 * number)), "utf-8"
        )
        arguments.append(f"{path}={state if number == 4 else 'FAILED'}")
    assert main(arguments) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("REFUSED  analysis-exclusion-unregistered: ")
    with pytest.raises(SystemExit) as stopped:
        main([*arguments, "--reason", "A reason of the command line."])
    assert stopped.value.code == 2


@pytest.mark.parametrize("run", ["analysis.json", "analysis.json=DONE", "=PASSED"])
def test_the_aggregate_command_needs_a_file_and_a_registered_state(run: str) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["aggregate", "--metric", METRIC, run])
    assert stopped.value.code == 2


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------


def page() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_the_page_states_each_rule_each_reason_and_each_source() -> None:
    text = page()
    for rule in analysis.RULES:
        assert f"`{rule}`" in text
    for reason in analysis.REASONS:
        assert f"`{reason}`" in text
    for source in analysis.SIGNAL_SOURCES:
        assert f"`{source}`" in text
    for metric in analysis.AGGREGATE_METRICS:
        assert f"`{metric}`" in text
    for case in CASES:
        assert f"`{case}`" in text


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_the_page_states_each_limitation_and_each_boundary() -> None:
    text = _flat(page())
    for statement in (*analysis.LIMITATIONS, *analysis.DOES_NOT_ESTABLISH):
        assert _flat(statement) in text
    assert _flat(analysis.COMPLETION_ORDER) in text
    assert _flat(analysis.REVISION_PRESENT) in text
    assert _flat(analysis.AGGREGATE_STATEMENT) in text


def test_the_page_states_the_figures_of_the_stabilization_rule() -> None:
    text = page()
    assert f"{analysis.STABILIZATION_SUCCESSES} consecutive" in text
    assert f"{analysis.STABILIZATION_SPAN_MS // 1000} seconds" in text


def write_cases() -> None:
    """Write the six cases under the fixtures directory, with LF bytes."""
    with tempfile.TemporaryDirectory() as scratch:
        for name, build in CASES.items():
            files = build(Path(scratch))
            files["analysis.json"] = analysis.analysis_text(analysis_of(files))
            directory = FIXTURES / name
            directory.mkdir(parents=True, exist_ok=True)
            for stale in directory.iterdir():
                stale.unlink()
            for file_name, text in files.items():
                (directory / file_name).write_bytes(text.encode("utf-8"))


# --------------------------------------------------------------------------
# Corrections of the independent review
# --------------------------------------------------------------------------


def test_the_inner_figure_does_not_cross_a_reading_with_no_value(
    tmp_path: Path,
) -> None:
    """The caller fails from 15,000 to 58,000 ms.

    The signal is healthy at the reads of 0, 10, 20, and 50 seconds, and the
    reads of 30 and 40 seconds did not answer. The first commit stated an
    inner figure of 35,000 ms: it counted the time across the two reads as
    healthy.
    """
    requests = small((10_000, True), (15_000, False), (58_000, True), (59_000, True))
    samples = [
        sample(),
        sample(),
        sample(),
        sample(workload=False),
        sample(workload=False),
        sample(),
    ]
    document = analyze(
        tmp_path, requests, samples, signals=[RUNTIME_ENDPOINTS], window=(0, 60_000)
    )
    false_healthy = signal_of(document, "runtime-ready-endpoints")["falseHealthy"]
    assert false_healthy == {
        "state": "computed",
        "reason": None,
        "callerMs": 43_000,
        # Healthy between consecutive reads: from 15,000 to the start of the
        # read of 20 seconds. The read of 50 seconds is one read.
        "innerMs": 20_000 - 15_000,
        "outerMs": 43_000,
        "signalNotObservedMs": (50_000 - 20_200) + (58_000 - 50_200),
    }


def test_the_inner_figure_of_an_interval_is_the_sum_of_its_parts(
    tmp_path: Path,
) -> None:
    samples = [
        sample(),
        sample(runtime=0),
        sample(runtime=0),
        sample(workload=False),
        sample(runtime=0),
        sample(runtime=0),
        sample(runtime=0),
        sample(),
    ]
    [interval] = zero_ready(tmp_path, samples)["tiers"][RUNTIME]["intervals"]
    assert interval["readings"] == 5
    assert interval["notObservedReadingsInside"] == 1
    # Two parts: the reads of 10 and 20 seconds, and the reads of 40 to 60.
    assert interval["innerMs"] == (20_000 - 10_200) + (60_000 - 40_200)
    assert interval["outerMs"] == 70_200


def test_a_window_with_no_completion_gives_no_caller_metric(tmp_path: Path) -> None:
    """The record covers the window, and no request completes inside it."""
    requests = small((3000, True), (6000, True), (103_000, True))
    document = analyze(
        tmp_path, requests, window=(10_000, 90_000), record=(0, WINDOW_MS)
    )
    caller = document["caller"]
    assert caller["record"]["coversWindow"] is True
    assert (caller["state"], caller["reason"]) == (
        "not-computable",
        "no-completion-in-window",
    )
    assert caller["failureEpisodes"] is None
    assert caller["requests"] is None
    assert document["withoutValue"][0] == "caller"


def test_the_longest_time_with_no_completion_is_stated(tmp_path: Path) -> None:
    requests = small((3000, True), (6000, True), (103_000, True))
    document = analyze(tmp_path, requests, window=(0, WINDOW_MS))
    caller = document["caller"]
    assert caller["failureEpisodes"]["callerFailureEpisodeMs"] == 0
    assert caller["requests"]["largestTimeWithNoCompletionMs"] == 97_000
    # The edges of the window are ends of that time.
    late = analyze(tmp_path, small((140_000, True)), window=(0, WINDOW_MS))
    assert late["caller"]["requests"]["largestTimeWithNoCompletionMs"] == 140_000


def test_a_window_that_starts_inside_an_episode_has_no_episode_figure(
    tmp_path: Path,
) -> None:
    """A request fails at 8 seconds and the next succeeds at 12. The window
    starts at 10 seconds, so it holds the end of an episode and not its start."""
    requests = small((5000, True), (8000, False), (12_000, True), (20_000, True))
    document = analyze(tmp_path, requests, window=(10_000, 30_000), record=(0, 30_000))
    episodes = document["caller"]["failureEpisodes"]
    assert episodes["startsBeforeWindow"] is True
    assert (episodes["count"], episodes["callerFailureEpisodeMs"]) == (0, None)
    assert episodes["reason"] == "episode-starts-before-window"
    assert "caller.failureEpisodes.callerFailureEpisodeMs" in document["withoutValue"]
    whole = analyze(tmp_path, requests, window=(0, 30_000))
    assert whole["caller"]["failureEpisodes"]["startsBeforeWindow"] is False
    assert whole["caller"]["failureEpisodes"]["callerFailureEpisodeMs"] == 4000


def test_a_success_after_the_window_is_stated_and_does_not_close_the_episode(
    tmp_path: Path,
) -> None:
    requests = small((5000, True), (95_000, False), (120_000, True))
    document = analyze(tmp_path, requests, window=(0, 100_000), record=(0, WINDOW_MS))
    episodes = document["caller"]["failureEpisodes"]
    [episode] = episodes["episodes"]
    assert (episode["open"], episode["end"], episode["ms"]) == (True, None, None)
    assert episode["successAfterWindow"] == {
        "sequence": 3,
        "finishedAt": at(120_000),
    }
    assert episodes["callerFailureEpisodeMs"] is None
    assert episodes["reason"] == "episode-open"


def test_the_earliest_abort_ends_the_window(tmp_path: Path) -> None:
    """The events tool accepts a log whose instants are not in line order."""
    recorded: list[tuple[int, str, str | None]] = [
        (100_000, "run-aborted", "safety-limit"),
        (60_000, "run-aborted", "safety-limit"),
    ]
    document = analyze(tmp_path, steady(), recorded=recorded)
    assert document["window"]["effectiveTo"] == at(60_000)
    assert len(document["aborts"]) == 2
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analyze(
            tmp_path,
            steady(),
            recorded=[(100_000, "run-aborted", "a"), (5000, "run-aborted", "a")],
            window=(5000, WINDOW_MS),
            record=(0, WINDOW_MS),
        )
    assert refused.value.rule == "analysis-window-invalid"


def test_an_abort_at_the_start_of_the_window_is_refused(tmp_path: Path) -> None:
    with pytest.raises(analysis.AnalysisRefused) as refused:
        analyze(
            tmp_path,
            steady(),
            recorded=[(5000, "run-aborted", "safety-limit")],
            window=(5000, WINDOW_MS),
            record=(0, WINDOW_MS),
        )
    assert refused.value.rule == "analysis-window-invalid"


def test_a_span_states_the_longest_time_with_no_reading(tmp_path: Path) -> None:
    """Two reads at 5 and at 6 seconds hold. The rule needs one reading inside
    the span and sets no limit for the rest, so the run is stabilized. The
    document states that 57 seconds of the span have no reading."""
    recovery = recovery_of(
        tmp_path, steady(), healthy(2), times=[5000, 6000], window=(0, WINDOW_MS)
    )
    assert recovery["stabilized"] is True
    assert recovery["span"]["first"]["finishedAt"] == at(3000)
    assert recovery["span"]["last"]["finishedAt"] == at(63_000)
    assert recovery["span"]["largestTimeWithNoReadingMs"] == {
        "desiredRevision": 63_000 - 6400,
        "readyReplicas": 63_000 - 6200,
        "runtimeReadyEndpoints": 63_000 - 6200,
    }


def test_an_ambiguous_fault_leaves_the_impact_search_at_the_window_start(
    tmp_path: Path,
) -> None:
    requests = small((1000, False), (2000, True), (6000, False), (7000, True))
    document = analyze(
        tmp_path,
        requests,
        recorded=[(5000, "fault-injection-started", "delete-runtime-pod")],
        window=(0, 8000),
    )
    assert document["fault"]["state"] == "ambiguous"
    assert document["caller"]["firstImpact"]["searchedFrom"] == at(0)
    assert document["caller"]["firstImpact"]["sequence"] == 1


def test_a_fault_before_the_window_leaves_the_search_at_the_window_start(
    tmp_path: Path,
) -> None:
    requests = small((6000, False), (7000, True))
    document = analyze(
        tmp_path,
        requests,
        recorded=fault_events(1000, 1200),
        window=(5000, 8000),
        record=(0, 8000),
    )
    assert document["fault"]["state"] == "stated"
    assert document["caller"]["firstImpact"]["searchedFrom"] == at(5000)


def test_a_tier_with_no_count_states_its_reason(tmp_path: Path) -> None:
    document = analyze(tmp_path, steady(), [sample(workload=False)])
    tier = document["zeroReadyEndpoints"]["tiers"][RUNTIME]
    assert (tier["state"], tier["reason"]) == ("not-observed", "no-count-in-window")
    observed = analyze(tmp_path, steady(), healthy(1))
    assert observed["zeroReadyEndpoints"]["tiers"][RUNTIME]["reason"] is None


def test_the_command_prints_the_same_text_under_two_hash_seeds() -> None:
    """A second process, so that the order of a set cannot hide in one run."""
    printed = []
    for seed in ("1", "2"):
        done = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.reliability_analysis",
                *_case_arguments("concurrency"),
            ],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            check=True,
        )
        printed.append(done.stdout)
    assert printed[0] == printed[1]
    assert printed[0] == (FIXTURES / "concurrency" / "analysis.json").read_bytes()


def test_the_tool_imports_no_module_that_reaches_a_network_or_a_process() -> None:
    """The command reads files. No module of the tool can contact a cluster."""
    barred = {"socket", "urllib", "http", "subprocess", "ssl", "asyncio", "requests"}
    for path in sorted((REPO_ROOT / "tools" / "reliability_analysis").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        assert names & barred == set(), path.name


def test_the_tool_opens_no_file_for_writing() -> None:
    for path in sorted((REPO_ROOT / "tools" / "reliability_analysis").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for word in ("write_text", "write_bytes", ".open(", "open(", "mkdir", "unlink"):
            assert word not in text, (path.name, word)


if __name__ == "__main__":
    write_cases()
