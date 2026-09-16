"""Losing the inference pod under load: its descriptor, its script, and its record.

Nothing here deletes anything, installs anything, sends load, or contacts a cluster.
The raw load sets are produced by `tools.llm_load.execute` against an injected
transport and a fake clock, the cluster's answers are JSON written into a temporary
directory, the collector's answers are a dictionary, and the operating script is read
as text. No figure in this suite describes serving or recovery.

It is heaviest in the three places this experiment can be wrong without failing:

- **the one delete** -- the whole safety argument is that exactly one pod, named by
  the cluster, is removed and nothing else is touched. That argument lives in a shell
  script, so it is read off the script rather than trusted;
- **where an interval begins and ends** -- an independent review of `V1-S3-003-PR2`
  found two published figures stamped from the wrong end, and both of those shapes
  recur here under traffic. A recovery stamped from a forward accepting a connection
  and a replacement stamped from the Deployment's aggregate are each refused by name;
- **the record** -- a run whose pod was not replaced, whose traffic did not span the
  disruption, or whose registered absences turned out to answer must be recorded as
  not usable, and a committed record must regenerate exactly from its inputs.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.inference_pod_recovery import __main__ as cli
from tools.inference_pod_recovery import core
from tools.inference_pod_recovery.core import (
    DESCRIPTOR_PATH,
    RecoveryError,
    RecoveryRefused,
    build_record,
    descriptor_fields,
    extract_environment,
    extract_facts,
    load_descriptor,
    parse_lifecycle,
    parse_readiness,
    place_requests,
    summary_lines,
    validate_descriptor,
)
from tools.llm_load import core as load
from tools.llm_load.core import HostRecord, HttpAnswer
from tools.model_acquisition import load_manifest
from tools.performance_scenarios.core import dumps, refuse_private
from tools.runtime_packaging import load_runtime_package

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR = load_descriptor()
DESCRIPTOR_TEXT = DESCRIPTOR_PATH.read_text(encoding="utf-8")
DOCUMENT: dict[str, Any] = json.loads(DESCRIPTOR_TEXT)
PROFILE = DESCRIPTOR.profile
MODEL = "qwen3-1-7b-q8-0"
REVISION = load_manifest().revision
HOST = HostRecord("TestOS", "1", "x86_64", 4, None, "3.12.0")
API_IMAGE = "localhost/inferops-api@sha256:" + "a" * 64
RUNTIME_IMAGE = load_runtime_package().image_reference
COLLECTOR_IMAGE = "prom/prometheus@sha256:" + "c" * 64

BASELINE_POD = "inferops-inferops-llm-runtime-aaaaaaaaaa-11111"
REPLACEMENT_POD = "inferops-inferops-llm-runtime-aaaaaaaaaa-22222"

SCRIPT = REPO_ROOT / "scripts/environment/inference-pod-recovery.sh"
SCRIPT_TEXT = SCRIPT.read_text(encoding="utf-8")
SCRIPT_LINES = SCRIPT_TEXT.splitlines()
PROCEDURE = REPO_ROOT / "docs/serving/inference-pod-recovery.md"
DECISION = (
    REPO_ROOT
    / "docs/architecture/decisions/ADR-0013-bounded-local-performance-observations.md"
)
EXTENDS = REPO_ROOT / "docs/proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md"

PROOF_DIR = REPO_ROOT / "docs/proof/serving"
PROOF_PREFIX = "v1-s4-006-pr1-"
COMMITTED_RECORD = PROOF_DIR / f"{PROOF_PREFIX}recovery-record.v1alpha1.json"
REPORT = PROOF_DIR / "v1-s4-006-pr1-inference-pod-recovery.md"
TEMPLATE = PROOF_DIR / "TEMPLATE-inference-pod-recovery.md"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def validate(document: dict[str, Any]) -> core.Descriptor:
    return validate_descriptor(document, DESCRIPTOR_TEXT)


def chart_name() -> str:
    chart = yaml.safe_load(
        (REPO_ROOT / "charts/inferops-llm/Chart.yaml").read_text(encoding="utf-8")
    )
    return f"{chart['name']}-{chart['version']}"


class Clock:
    """A clock nothing waits on, advanced by the transport one request at a time."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def completion_answer() -> HttpAnswer:
    return HttpAnswer(
        200,
        {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "x"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 30, "completion_tokens": 17, "total_tokens": 47},
            "x_inferops": {"adapterKind": "real", "modelRef": MODEL},
        },
    )


def refusal_answer() -> HttpAnswer:
    """What the API answers while the tier it calls has no ready endpoint."""
    return HttpAnswer(
        503,
        {
            "code": "upstream-unavailable",
            "message": "the serving runtime did not accept the request",
            "details": {"conditionId": "runtime-unreachable"},
        },
    )


IDENTITY = {
    "/health/ready": HttpAnswer(
        200, {"status": "ready", "adapterKind": "real", "state": "ready"}
    ),
    "/v1/models": HttpAnswer(
        200,
        {
            "object": "list",
            "data": [{"id": MODEL}],
            "x_inferops": {
                "adapterKind": "real",
                "runtime": {
                    "name": "llama.cpp llama-server",
                    "version": "b1",
                    "modelRevision": REVISION,
                },
            },
        },
    ),
}

#: Which requests the API refuses, by dispatch order: every one from the seventh
#: on, which is the shape a lost pod really produces. A refusal returns far faster
#: than a completion, so the run spends its whole remaining request budget in
#: seconds and ends before anything is ready again.
REFUSED_SEQUENCES = range(6, 500)


def facts_document() -> dict[str, Any]:
    return {
        "provider": "docker-desktop",
        "kubernetesServerVersion": "v1.34.3",
        "chart": chart_name(),
        "releaseRevision": 1,
        "apiImage": API_IMAGE,
        "runtimeImage": RUNTIME_IMAGE,
        "modelRevision": REVISION,
        "apiReplicas": 1,
        "runtimeReplicas": 1,
        "repositoryRevision": "b" * 40,
    }


def real_raw(origin_ms: int, *, refuse: range = REFUSED_SEQUENCES) -> str:
    """A real-mode raw set in which a run of requests in the measured phase refuses."""
    clock = Clock()
    dispatched = 0

    def transport(
        method: str, url: str, body: Any, headers: Any, timeout: float
    ) -> HttpAnswer:
        nonlocal dispatched
        if method == "GET":
            return IDENTITY["/" + url.split("/", 3)[3]]
        clock.advance(1.0)
        answer = refusal_answer() if dispatched in refuse else completion_answer()
        dispatched += 1
        return answer

    run = load.execute(
        replace(PROFILE, max_requests_per_level=12, duration_seconds=600),
        base_url="http://127.0.0.1:18094",
        mode=load.MODE_REAL,
        confirmed=True,
        facts=load.parse_facts(facts_document()),
        transport=transport,
        clock=clock,
        epoch_ms=lambda: origin_ms,
        host=HOST,
    )
    return "\n".join(load.raw_lines(run)) + "\n"


def pod(
    role: str,
    name: str,
    uid: str,
    *,
    restarts: int = 0,
    image_ids: list[str] | None = None,
    phase: str = "Running",
    ready: bool = True,
) -> dict[str, Any]:
    component = core.ROLE_COMPONENTS[role]
    images = {"api": API_IMAGE, "runtime": RUNTIME_IMAGE, "collector": COLLECTOR_IMAGE}
    return {
        "metadata": {
            "name": name,
            "uid": uid,
            "namespace": "inferops-release",
            "labels": {"app.kubernetes.io/component": component},
        },
        "status": {
            "phase": phase,
            "containerStatuses": [
                {"ready": ready, "restartCount": restarts, "imageID": image_id}
                for image_id in (image_ids or [images[role]])
            ],
        },
    }


def deployment(name: str, container: str, image: str) -> dict[str, Any]:
    return {
        "metadata": {"name": name, "labels": {}},
        "spec": {
            "replicas": 1,
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": container,
                            "image": image,
                            "resources": {
                                "limits": {"cpu": "6"},
                                "requests": {"cpu": "1"},
                            },
                        }
                    ]
                }
            },
        },
        "status": {"availableReplicas": 1},
    }


def write_cluster(tmp_path: Path, **overrides: Any) -> Path:
    cluster = tmp_path / "cluster"
    cluster.mkdir(parents=True, exist_ok=True)
    api = pod("api", "inferops-inferops-llm-bbbb-1", "u-api")
    collector = pod(
        "collector", "inferops-inferops-llm-collector-cccc-1", "u-collector"
    )
    before = pod("runtime", BASELINE_POD, "u-runtime-1")
    after = pod("runtime", REPLACEMENT_POD, "u-runtime-2")
    documents: dict[str, Any] = {
        "target.json": {
            "provider": "docker-desktop",
            "cluster": "docker-desktop",
            "context": "docker-desktop",
            "verifiedAt": "2026-09-16T00:00:00Z",
            "nodeImageDigest": "sha256:" + "d" * 64,
            "helmVersion": "v3.19.0",
        },
        "version.json": {
            "clientVersion": {"gitVersion": "v1.34.3"},
            "serverVersion": {"gitVersion": "v1.34.3"},
        },
        "node.json": {
            "metadata": {"name": "desktop-control-plane"},
            "status": {
                "nodeInfo": {
                    "osImage": "Debian",
                    "kernelVersion": "5.15",
                    "containerRuntimeVersion": "containerd://2.2.0",
                    "kubeletVersion": "v1.34.3",
                },
                "capacity": {"cpu": "12", "memory": "10188024Ki"},
                "allocatable": {"cpu": "12", "memory": "10188024Ki"},
                "addresses": [{"type": "InternalIP", "address": "192.0.2.10"}],
            },
        },
        "engine.json": {
            "serverVersion": "29.7.2",
            "cpus": 12,
            "memoryBytes": 10432536576,
        },
        "helm-release.json": [
            {
                "name": "inferops",
                "chart": chart_name(),
                "app_version": "0.1.0",
                "revision": "1",
                "status": "deployed",
            }
        ],
        "deployments.json": {
            "items": [
                deployment("inferops-inferops-llm", "api", API_IMAGE),
                deployment("inferops-inferops-llm-runtime", "runtime", RUNTIME_IMAGE),
                deployment(
                    "inferops-inferops-llm-collector", "prometheus", COLLECTOR_IMAGE
                ),
            ]
        },
        "configmap.json": {
            "data": {
                "INFEROPS_MODEL_REVISION": REVISION,
                "INFEROPS_REQUEST_TIMEOUT_MS": "120000",
                "INFEROPS_LLAMA_SERVER_ENDPOINT": "http://198.51.100.12:8080",
            }
        },
        "pods-before.json": {"items": [api, before, collector]},
        "pods-after.json": {"items": [api, after, collector]},
        "running-pods.json": {
            "items": [
                api,
                after,
                collector,
                {"metadata": {"name": "other", "namespace": "another-project"}},
            ]
        },
        "image-api.json": {
            "status": {"id": "sha256:" + "1" * 64, "repoDigests": [API_IMAGE]}
        },
        "image-runtime.json": {
            "status": {"id": "sha256:" + "2" * 64, "repoDigests": [RUNTIME_IMAGE]}
        },
        "repository.json": {
            "revision": "b" * 40,
            "trackedChangesPresent": True,
            "untrackedFilesPresent": False,
            "executedFiles": {"tools/llm_load/core.py": "e" * 64},
        },
    }
    documents.update(overrides)
    for name, document in documents.items():
        (cluster / name).write_text(json.dumps(document), encoding="utf-8")
    return cluster


class Run:
    """A complete, consistent set of record inputs for one disrupted load run."""

    def __init__(self, tmp_path: Path) -> None:
        self.origin = 1_760_000_000_000
        self.disrupted_raw_text = real_raw(self.origin)
        placed = place_requests(load.parse_raw(self.disrupted_raw_text))
        failures = [
            entry for entry in placed if entry.record.outcome != load.OUTCOME_SUCCESS
        ]
        assert failures, "the fixture must contain refused requests"
        self.deleted = failures[0].dispatched_at_ms
        self.launched = self.origin - 500
        self.observed = self.deleted + 2_000
        self.ready = self.deleted + 12_000
        self.disrupted_exited = max(entry.completed_at_ms for entry in placed) + 1_000
        # The recovered run starts after the replacement is ready and after the
        # disrupted one has exited, exactly as the operating script sequences them.
        self.recovered_launched = max(self.ready, self.disrupted_exited) + 30_000
        self.recovered_origin = self.recovered_launched + 500
        self.recovered_raw_text = real_raw(self.recovered_origin, refuse=range(0, 0))
        recovered_placed = place_requests(load.parse_raw(self.recovered_raw_text))
        self.recovered_exited = (
            max(entry.completed_at_ms for entry in recovered_placed) + 1_000
        )
        self.settled = self.recovered_exited + 90_000
        self.cluster = write_cluster(tmp_path)
        self.environment_text = dumps(extract_environment(self.cluster, DESCRIPTOR))
        self.lifecycle_text = dumps(self.lifecycle())
        self.readiness_text = dumps(self.readiness())
        self.telemetry_text = dumps(self.telemetry())

    def lifecycle(self) -> dict[str, Any]:
        return {
            "idleBaseline": {
                "startEpochMs": self.launched - 60_000,
                "endEpochMs": self.launched,
            },
            "runs": [
                {
                    "role": "disrupted",
                    "rawFile": "run-1-raw.jsonl",
                    "launchedEpochMs": self.launched,
                    "exitedEpochMs": self.disrupted_exited,
                    "exitCode": 0,
                },
                {
                    "role": "recovered",
                    "rawFile": "run-2-raw.jsonl",
                    "launchedEpochMs": self.recovered_launched,
                    "exitedEpochMs": self.recovered_exited,
                    "exitCode": 0,
                },
            ],
            "settledEpochMs": self.settled,
            "deletion": {
                "name": BASELINE_POD,
                "uid": "u-runtime-1",
                "ownerKind": "ReplicaSet",
                "ownerName": "inferops-inferops-llm-runtime-aaaaaaaaaa",
                "nodeName": "desktop-control-plane",
                "issuedEpochMs": self.deleted,
                "requestedAfterLoadStartMs": DESCRIPTOR.disruption_offset_ms,
                "podsMatchingSelector": 1,
            },
            "replacement": {
                "name": REPLACEMENT_POD,
                "uid": "u-runtime-2",
                "ownerKind": "ReplicaSet",
                "ownerName": "inferops-inferops-llm-runtime-aaaaaaaaaa",
                "nodeName": "desktop-control-plane",
                "observedEpochMs": self.observed,
                "readyEpochMs": self.ready,
                "containerStartedAt": "2026-09-16T10:00:03Z",
                "readyConditionAt": "2026-09-16T10:00:14Z",
                "initContainerName": "verify-model",
                "initExitCode": 0,
                "restartCount": 0,
            },
            "release": {"revisionBefore": 1, "revisionAfter": 1},
            "acquisition": {"jobCountBefore": 0, "jobCountAfter": 0},
            "claims": {"countBefore": 1, "countAfter": 1},
            "interventionsAfterDeletion": [],
        }

    def readiness(self) -> dict[str, Any]:
        samples = []
        at = self.deleted
        while at <= self.ready + 4 * DESCRIPTOR.poll_interval_ms:
            replaced = at >= self.observed
            live_pod = REPLACEMENT_POD if replaced else BASELINE_POD
            samples.append(
                {
                    "atEpochMs": at,
                    "readTookMs": 300,
                    "runtimeEndpointsReady": 1 if at >= self.ready else 0,
                    "runtimePodsReady": 1 if at >= self.ready else 0,
                    "runtimePodNames": [live_pod],
                }
            )
            at += DESCRIPTOR.poll_interval_ms
        return {"samples": samples}

    def telemetry(self) -> dict[str, Any]:
        start = self.launched - DESCRIPTOR.scrape_interval_seconds * 1000
        series: list[dict[str, Any]] = []
        for registered in DESCRIPTOR.series:
            if registered.exposure in ("nothing-emits", "no-source"):
                series.append(
                    {
                        "seriesId": registered.series_id,
                        "expr": registered.expr,
                        "status": "success",
                        "result": [],
                    }
                )
                continue
            series.append(
                {
                    "seriesId": registered.series_id,
                    "expr": registered.expr,
                    "status": "success",
                    "result": [
                        {
                            "labels": {"job": "inferops"},
                            "values": [
                                [start / 1000, "1"],
                                [self.deleted / 1000, "2"],
                                [self.settled / 1000, "3"],
                            ],
                        }
                    ],
                }
            )
        return {
            "collectorVersion": "3.7.3",
            "range": {
                "startEpochMs": start,
                "endEpochMs": self.settled,
                "stepSeconds": DESCRIPTOR.range_step_seconds,
            },
            "series": series,
        }

    def texts(self, **overrides: str) -> dict[str, str]:
        texts = {
            "environment": self.environment_text,
            "lifecycle": self.lifecycle_text,
            "readiness": self.readiness_text,
            "telemetry": self.telemetry_text,
            "disruptedRaw": self.disrupted_raw_text,
            "recoveredRaw": self.recovered_raw_text,
        }
        texts.update(overrides)
        return texts

    def build(self, **overrides: str) -> dict[str, Any]:
        texts = self.texts(**overrides)
        return build_record(
            DESCRIPTOR,
            environment_text=texts["environment"],
            lifecycle_text=texts["lifecycle"],
            readiness_text=texts["readiness"],
            telemetry_text=texts["telemetry"],
            disrupted_raw_text=texts["disruptedRaw"],
            recovered_raw_text=texts["recoveredRaw"],
        )


@pytest.fixture
def run(tmp_path: Path) -> Run:
    return Run(tmp_path)


def check(record: dict[str, Any], check_id: str) -> dict[str, Any]:
    for entry in record["checks"]:
        if entry["checkId"] == check_id:
            return entry
    raise AssertionError(f"no check named {check_id!r}")


def window(record: dict[str, Any], name: str) -> dict[str, Any]:
    for entry in record["callerImpact"]["windows"]:
        if entry["window"] == name:
            return entry
    raise AssertionError(f"no window named {name!r}")


# --------------------------------------------------------------------------
# The descriptor
# --------------------------------------------------------------------------


def test_the_committed_descriptor_validates() -> None:
    assert DOCUMENT["experimentId"] == core.EXPECTED_EXPERIMENT_ID
    assert DESCRIPTOR.disrupted_scenario_id == "c1"
    assert DESCRIPTOR.profile_sha256 == DOCUMENT["load"]["profileSha256"]


def test_the_descriptor_carries_the_boundary_and_refuses_three_claims() -> None:
    """A record without these is one whose figures could be read as an SLO."""
    for flag in ("productionBenchmark", "portableCapacityClaim", "availabilityClaim"):
        assert DOCUMENT[flag] is False, flag
    for word in ("availability", "benchmark", "portable capacity"):
        assert word in DOCUMENT["boundary"], word


@pytest.mark.parametrize(
    "field",
    ("productionBenchmark", "portableCapacityClaim", "availabilityClaim"),
)
def test_a_descriptor_claiming_more_than_it_may_is_refused(field: str) -> None:
    document = copy.deepcopy(DOCUMENT)
    document[field] = True
    with pytest.raises(RecoveryError):
        validate(document)


def test_a_boundary_that_drops_a_refusal_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["boundary"] = "Bounded observations of one run."
    with pytest.raises(RecoveryError, match="boundary"):
        validate(document)


def test_the_scenarios_are_the_phases_the_committed_load_profile_sends() -> None:
    """Drift here would place a request against a phase the profile never sent."""
    expected = ["warmup"] + [level.level_id for level in PROFILE.levels]
    assert list(DESCRIPTOR.scenario_ids) == expected


def test_a_scenario_matrix_that_no_longer_matches_the_profile_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["scenarios"][1]["concurrency"] = 3
    with pytest.raises(RecoveryError, match="load profile"):
        validate(document)


def test_a_load_profile_digest_that_is_not_the_committed_one_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["load"]["profileSha256"] = "0" * 64
    with pytest.raises(RecoveryError, match="digest"):
        validate(document)


def test_a_disruption_mechanism_this_module_does_not_own_is_refused() -> None:
    """The pod-restart experiment's mechanism must not be readable as this one."""
    document = copy.deepcopy(DOCUMENT)
    document["disruption"]["mechanism"] = "delete-serving-runtime-pod"
    with pytest.raises(RecoveryError, match="mechanism"):
        validate(document)


def test_a_disruption_registered_for_the_warm_up_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["disruption"]["duringScenarioId"] = "warmup"
    with pytest.raises(RecoveryError, match="measured"):
        validate(document)


@pytest.mark.parametrize("offset", (0, 5_000, 600_001))
def test_a_disruption_offset_outside_the_ceilings_is_refused(offset: int) -> None:
    document = copy.deepcopy(DOCUMENT)
    document["disruption"]["issueAfterLoadStartMs"] = offset
    with pytest.raises(RecoveryError, match="issueAfterLoadStartMs"):
        validate(document)


def test_a_termination_grace_period_set_by_the_experiment_is_refused() -> None:
    """A grace period this experiment chose would be a second thing its figures depend on."""
    document = copy.deepcopy(DOCUMENT)
    document["disruption"]["gracePeriodSeconds"] = 0
    with pytest.raises(RecoveryError, match="grace period"):
        validate(document)


def test_an_experiment_expecting_a_human_to_rescue_it_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["humanAction"]["recoveryInterventionExpected"] = True
    with pytest.raises(RecoveryError, match="recoveryInterventionExpected"):
        validate(document)


def test_a_second_runtime_replica_is_refused() -> None:
    """Two replicas would change what a caller saw, and this is defined for one."""
    document = copy.deepcopy(DOCUMENT)
    document["release"]["runtimeReplicas"] = 2
    with pytest.raises(RecoveryError, match="one replica"):
        validate(document)


def test_a_recovery_stamped_from_anything_but_a_served_completion_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["recovery"]["firstServedCompletionFrom"] = "forward-accepted"
    with pytest.raises(RecoveryError, match="firstServedCompletionFrom"):
        validate(document)


def test_a_replacement_stamped_from_the_deployment_aggregate_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["recovery"]["replacementReadyFrom"] = "deployment-ready-replicas"
    with pytest.raises(RecoveryError, match="replacementReadyFrom"):
        validate(document)


def test_a_telemetry_row_pairing_an_impossible_answerability_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["telemetry"]["series"][0]["answerability"] = "no-source"
    with pytest.raises(RecoveryError, match="cannot both be true"):
        validate(document)


def test_a_telemetry_set_naming_only_signals_that_work_is_refused() -> None:
    """A classification needs a row registered as not exposing the event."""
    document = copy.deepcopy(DOCUMENT)
    for entry in document["telemetry"]["series"]:
        if entry["exposure"] == "expected-not-to-expose":
            entry["exposure"] = "expected-to-expose"
    with pytest.raises(RecoveryError, match="not to expose"):
        validate(document)


def test_the_descriptor_registers_the_signals_sprint_3_found_absent() -> None:
    """Both were observed empty in V1-S3-011-PR2 and both are asked again here."""
    registered = {entry.series_id: entry for entry in DESCRIPTOR.series}
    assert registered["model-readiness-by-workload"].exposure == "nothing-emits"
    assert registered["pod-container-restarts"].exposure == "no-source"


def test_a_third_load_run_is_refused() -> None:
    """Two runs is the design; a third would be a repetition study, which this is not."""
    document = copy.deepcopy(DOCUMENT)
    document["schedule"]["repetitions"] = 3
    with pytest.raises(RecoveryError, match="load runs"):
        validate(document)


def test_run_roles_this_module_does_not_record_against_are_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["schedule"]["runRoles"] = ["first", "second"]
    with pytest.raises(RecoveryError, match="run roles"):
        validate(document)


def test_a_recovered_run_that_does_not_wait_for_readiness_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["recovery"]["recoveredRunStartsWhen"] = "immediately"
    with pytest.raises(RecoveryError, match="recoveredRunStartsWhen"):
        validate(document)


def test_a_recovered_run_launched_before_the_replacement_was_ready_is_refused(
    run: Run,
) -> None:
    """It would be measuring something other than a recovered service."""
    lifecycle = run.lifecycle()
    lifecycle["runs"][1]["launchedEpochMs"] = run.ready - 1
    with pytest.raises(RecoveryError, match="launchedEpochMs"):
        run.build(lifecycle=dumps(lifecycle))


def test_evidence_written_outside_the_ignored_tree_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["evidence"]["directory"] = "docs/proof/serving"
    with pytest.raises(RecoveryError, match=re.escape(".cache/inferops/experiments")):
        validate(document)


def test_a_forward_that_is_not_loopback_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["forwards"]["host"] = "0.0.0.0"
    with pytest.raises(RecoveryError, match=re.escape("127.0.0.1")):
        validate(document)


def test_a_cleanup_that_removes_a_prerequisite_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["cleanup"]["removesModelCacheClaim"] = True
    with pytest.raises(RecoveryError, match="removesModelCacheClaim"):
        validate(document)


def test_a_recovery_budget_inside_the_replacement_budget_is_refused() -> None:
    document = copy.deepcopy(DOCUMENT)
    document["readiness"]["recoveryBudgetMs"] = document["readiness"][
        "replacementBudgetMs"
    ]
    with pytest.raises(RecoveryError, match="recovery budget"):
        validate(document)


def test_the_descriptor_fields_the_script_reads_all_resolve() -> None:
    """A field the script reads and the descriptor lacks is an empty shell variable."""
    start = SCRIPT_TEXT.index('"${INFEROPS_EXPERIMENT_MODULE}" fields')
    block = SCRIPT_TEXT[start : SCRIPT_TEXT.index(')"; then', start)]
    asked = [
        path
        for path in re.findall(r"\b([a-z]+\.[a-zA-Z]+)\b", block)
        if path.split(".")[0] in DOCUMENT
    ]
    assert len(asked) >= 25, asked
    assert descriptor_fields(DESCRIPTOR, asked)


def test_a_dotted_path_naming_a_structure_is_refused() -> None:
    with pytest.raises(RecoveryError, match="not a value a shell can read"):
        descriptor_fields(DESCRIPTOR, ["release"])


def test_the_summary_always_states_what_the_experiment_may_not_claim() -> None:
    joined = " ".join(summary_lines(DESCRIPTOR))
    for word in ("availability", "SLO", "error budget", "benchmark"):
        assert word in joined, word


# --------------------------------------------------------------------------
# The operating script: the one delete, and what it never touches
# --------------------------------------------------------------------------


def code_lines() -> list[str]:
    return [line for line in SCRIPT_LINES if not line.lstrip().startswith("#")]


def test_the_script_deletes_exactly_one_pod_and_nothing_else() -> None:
    """The whole safety argument of this experiment, read off the script."""
    deletes = [
        line
        for line in code_lines()
        if re.search(r"inferops::target_kubectl delete\b", line)
    ]
    assert len(deletes) == 1, deletes
    assert "delete pod" in deletes[0]
    assert '"${baseline_pod}"' in deletes[0]
    assert "--all" not in deletes[0]
    assert "-l " not in deletes[0]


def test_the_script_never_removes_what_outlives_a_release() -> None:
    body = "\n".join(code_lines())
    for forbidden in (
        "delete namespace",
        "delete pvc",
        "delete persistentvolumeclaim",
        "kind delete cluster",
        "terraform destroy",
        "--create-namespace",
    ):
        assert forbidden not in body, forbidden
    assert body.count("inferops::target_helm uninstall") == 1


def test_every_helm_and_kubectl_call_goes_through_the_target_wrappers() -> None:
    """A call on the kind-pinned wrapper would read the wrong cluster."""
    assert "inferops::kubectl" not in SCRIPT_TEXT
    assert "inferops::helm " not in SCRIPT_TEXT
    # Quoted text is blanked first: several messages name `helm uninstall` in prose,
    # and telling an operator what to run is not this script running it.
    bare = [
        line
        for line in code_lines()
        if re.search(r"(?<!::)\b(kubectl|helm)\s+\w", re.sub(r'"[^"]*"', '""', line))
        and "inferops::target_" not in line
    ]
    assert not bare, bare


def test_the_script_refuses_before_it_contacts_anything() -> None:
    body = SCRIPT_TEXT
    confirm = body.index("run needs --confirm-real-kubernetes")
    values = body.index("--values is required")
    resolve = body.index("inferops::resolve_target")
    for later in (
        'terraform-prerequisites.sh" apply',
        "inferops::target_helm install",
        "port-forward",
        "inferops::target_kubectl delete pod",
    ):
        assert confirm < body.index(later), later
        assert values < body.index(later), later
        assert resolve < body.index(later), later


def test_the_forwards_bind_loopback_and_the_run_directory_is_never_overwritten() -> (
    None
):
    assert "These forwards bind 127.0.0.1 only" in SCRIPT_TEXT
    assert "already exists. Move it aside before a new run" in SCRIPT_TEXT


def test_the_script_stamps_the_replacement_from_the_pod_own_condition() -> None:
    """The Deployment aggregate still counts a pod inside its termination grace period.

    An independent review of `V1-S3-003-PR2` found a loop breaking on that aggregate
    while its own comment claimed otherwise, so the aggregate is refused here by name.
    """
    body = "\n".join(code_lines())
    assert "readyReplicas" not in body
    assert 'conditions[?(@.type=="Ready")]' in body


def test_the_script_passes_no_timeout_beside_a_no_wait_delete() -> None:
    """`--timeout` beside `--wait=false` bounds nothing and reads like a control."""
    deletes = [line for line in code_lines() if "delete pod" in line]
    assert deletes and all("--timeout" not in line for line in deletes)


def test_nothing_mutating_runs_between_the_delete_and_the_uninstall() -> None:
    """What lets the record say the Deployment controller did the recovering.

    The record writes `interventionsAfterDeletion` as an empty list. That claim is
    only worth something if the script cannot have intervened, which is read here
    rather than trusted.
    """
    body = "\n".join(code_lines())
    start = body.index("inferops::target_kubectl delete pod")
    end = body.index("inferops::target_helm uninstall")
    between = body[start:end].splitlines()[1:]
    mutating = re.compile(
        r"target_kubectl\s+(annotate|apply|cordon|cp|create|delete|drain|edit|exec"
        r"|label|patch|replace|scale|taint|uncordon)\b"
        r"|target_helm\s+(install|upgrade|uninstall|delete|rollback|test)\b"
    )
    offenders = [line.strip() for line in between if mutating.search(line)]
    assert not offenders, offenders


def test_the_script_clears_the_load_generators_output_path_before_each_run() -> None:
    """A raw set left by an earlier run would otherwise be copied as this run's."""
    body = "\n".join(code_lines())
    assert body.index('rm -f "${load_raw}"') < body.index(
        "python -m tools.llm_load run"
    )
    assert body.count("start_load") == 3  # the definition, and one call per run


def test_the_script_sends_the_profile_twice_and_deletes_during_the_first() -> None:
    body = "\n".join(code_lines())
    first = body.index("start_load\n")
    delete = body.index("inferops::target_kubectl delete pod")
    second = body.index("recovered_launched=")
    assert first < delete < second, (first, delete, second)


def test_the_script_refuses_an_argument_it_does_not_understand() -> None:
    assert 'inferops::fail "unknown argument' in SCRIPT_TEXT


def test_the_script_is_listed_among_the_lifecycle_entry_points() -> None:
    """The lifecycle safety suite reads a fixed list; a script absent from it is unchecked."""
    safety = (
        REPO_ROOT / "tests/architecture/test_cluster_lifecycle_safety.py"
    ).read_text(encoding="utf-8")
    assert '"inference-pod-recovery.sh",' in safety


# --------------------------------------------------------------------------
# Placing requests, and the record
# --------------------------------------------------------------------------


def test_a_raw_set_without_an_absolute_origin_cannot_be_placed(run: Run) -> None:
    lines = run.disrupted_raw_text.splitlines()
    header = json.loads(lines[0])
    header.pop("startedAtEpochMs")
    lines[0] = json.dumps(header)
    with pytest.raises(RecoveryRefused, match="startedAtEpochMs"):
        place_requests(load.parse_raw("\n".join(lines) + "\n"))


def test_a_request_is_placed_from_its_phase_start_and_not_the_run_origin(
    run: Run,
) -> None:
    raw = load.parse_raw(run.disrupted_raw_text)
    placed = place_requests(raw)
    measured = next(entry for entry in placed if entry.record.level_id == "c1")
    phase = next(phase for phase in raw.phases if phase.level_id == "c1")
    assert measured.dispatched_at_ms == (
        run.origin + phase.started_offset_ms + measured.record.dispatch_offset_ms
    )


def test_a_consistent_run_produces_a_usable_record(run: Run) -> None:
    record = run.build()
    failed = [entry["checkId"] for entry in record["checks"] if not entry["passed"]]
    assert failed == [], failed
    assert record["usable"] is True
    assert record["kind"] == core.RECORD_KIND
    assert record["evidenceClass"] == "local-real-cpu"


def test_the_record_refuses_the_three_claims_it_may_not_make(run: Run) -> None:
    record = run.build()
    for flag in ("productionBenchmark", "portableCapacityClaim", "availabilityClaim"):
        assert record[flag] is False, flag
    assert "availability" in record["timings"]["note"]


def test_traffic_is_recorded_before_during_and_after_the_disruption(run: Run) -> None:
    record = run.build()
    assert window(record, "before")["successful"] > 0
    assert window(record, "during")["unsuccessful"] > 0
    assert window(record, "afterRecovery")["successful"] > 0


def test_the_disruption_is_recorded_as_landing_in_the_registered_phase(
    run: Run,
) -> None:
    record = run.build()
    assert record["disruption"]["landedInScenarioId"] == "c1"
    assert check(record, "disruption-landed-in-the-intended-scenario")["passed"]


def test_the_outage_begins_at_the_first_request_that_was_not_served(run: Run) -> None:
    """Not at the delete: the pod that is going away goes on serving for a while.

    The first execution of this experiment found exactly that -- a request dispatched
    166 ms after the delete came back served by the draining pod -- and an earlier
    version of the record stamped that completion as the recovery, which published two
    negative intervals.
    """
    record = run.build()
    placed = place_requests(load.parse_raw(run.disrupted_raw_text))
    lost = min(
        (
            entry
            for entry in placed
            if entry.dispatched_at_ms >= run.deleted
            and entry.record.outcome != load.OUTCOME_SUCCESS
        ),
        key=lambda entry: entry.dispatched_at_ms,
    )
    assert record["timings"]["firstUnservedCompletionEpochMs"] == lost.completed_at_ms
    assert (
        record["timings"]["deletionToFirstUnservedCompletionMs"]
        == lost.completed_at_ms - run.deleted
    )


def test_the_service_is_restored_at_the_next_request_that_was_served(run: Run) -> None:
    record = run.build()
    placed = place_requests(load.parse_raw(run.recovered_raw_text))
    expected = min(
        entry.completed_at_ms
        for entry in placed
        if entry.record.outcome == load.OUTCOME_SUCCESS
    )
    assert record["timings"]["serviceRestoredEpochMs"] == expected
    assert record["timings"]["serviceRestoredObservedIn"] == "recovered-run"
    assert record["timings"]["deletionToServiceRestoredMs"] == expected - run.deleted
    assert record["timings"]["callerVisibleOutageMs"] >= 0


def test_no_published_interval_is_ever_negative(run: Run) -> None:
    """The check that exists because the first execution published two that were."""
    record = run.build()
    assert check(record, "no-published-interval-is-negative")["passed"]
    for name, value in record["timings"].items():
        if name.endswith("Ms") and isinstance(value, int):
            if name == "serviceRestoredRelativeToObservedReadyMs":
                continue  # deliberately signed; it bounds this workflow's poll
            assert value >= 0, (name, value)


def test_a_run_in_which_nothing_was_served_afterwards_is_not_usable(
    run: Run,
) -> None:
    """Every request in both runs after the delete refuses, so nothing is restored."""
    record = run.build(
        recoveredRaw=real_raw(run.recovered_origin, refuse=range(0, 500))
    )
    assert record["usable"] is False
    assert not check(record, "the-service-was-restored-to-a-caller")["passed"]
    assert record["timings"]["serviceRestoredObservedIn"] == "nowhere"


def test_a_restoration_seen_in_the_disrupted_run_is_recorded_as_such(run: Run) -> None:
    """If the disrupted run outlives the outage, its own completion restores service."""
    record = run.build(disruptedRaw=real_raw(run.origin, refuse=range(6, 9)))
    assert record["timings"]["serviceRestoredObservedIn"] == "disrupted-run"
    assert window(record, "afterInTheDisruptedRun")["successful"] > 0


def test_what_the_draining_pod_served_is_kept_in_its_own_window(run: Run) -> None:
    """Folding it into the outage would overstate it; into `before` would misattribute it."""
    record = run.build(disruptedRaw=real_raw(run.origin, refuse=range(8, 500)))
    draining = window(record, "servedWhileDraining")
    assert draining["dispatched"] >= 1
    assert draining["unsuccessful"] == 0
    assert record["timings"]["lastCompletionServedWhileDrainingMs"] >= 0


def test_a_replacement_carrying_the_same_identity_is_not_usable(run: Run) -> None:
    lifecycle = run.lifecycle()
    lifecycle["replacement"]["name"] = BASELINE_POD
    lifecycle["replacement"]["uid"] = "u-runtime-1"
    record = run.build(lifecycle=dumps(lifecycle))
    assert not check(record, "replacement-is-a-different-pod")["passed"]
    assert record["usable"] is False


def test_a_selector_matching_two_pods_is_not_usable(run: Run) -> None:
    lifecycle = run.lifecycle()
    lifecycle["deletion"]["podsMatchingSelector"] = 2
    record = run.build(lifecycle=dumps(lifecycle))
    assert not check(record, "deleted-exactly-one-pod")["passed"]


def test_an_acquisition_job_appearing_across_the_replacement_is_not_usable(
    run: Run,
) -> None:
    lifecycle = run.lifecycle()
    lifecycle["acquisition"]["jobCountAfter"] = 1
    record = run.build(lifecycle=dumps(lifecycle))
    assert not check(record, "no-new-acquisition-job")["passed"]


def test_a_release_revision_that_moved_is_not_usable(run: Run) -> None:
    lifecycle = run.lifecycle()
    lifecycle["release"]["revisionAfter"] = 2
    record = run.build(lifecycle=dumps(lifecycle))
    assert not check(record, "no-release-revision-change")["passed"]


def test_an_intervention_after_the_deletion_is_recorded_and_refused(run: Run) -> None:
    lifecycle = run.lifecycle()
    lifecycle["interventionsAfterDeletion"] = ["restarted-a-workload"]
    record = run.build(lifecycle=dumps(lifecycle))
    assert not check(record, "no-intervention-after-the-deletion")["passed"]
    assert record["humanAction"]["recoveryIntervention"] == "restarted-a-workload"


def test_an_intervention_outside_the_vocabulary_is_refused(run: Run) -> None:
    lifecycle = run.lifecycle()
    lifecycle["interventionsAfterDeletion"] = ["waved-at-it"]
    with pytest.raises(RecoveryError, match="must be one of"):
        run.build(lifecycle=dumps(lifecycle))


def test_a_delete_issued_at_an_unregistered_offset_is_refused(run: Run) -> None:
    lifecycle = run.lifecycle()
    lifecycle["deletion"]["requestedAfterLoadStartMs"] = 45_000
    with pytest.raises(RecoveryRefused, match="offset"):
        run.build(lifecycle=dumps(lifecycle))


def test_instants_out_of_order_are_refused(run: Run) -> None:
    lifecycle = run.lifecycle()
    lifecycle["replacement"]["readyEpochMs"] = run.deleted - 1
    with pytest.raises(RecoveryError):
        run.build(lifecycle=dumps(lifecycle))


def test_a_service_that_never_lost_an_endpoint_is_not_usable(run: Run) -> None:
    readiness = run.readiness()
    for sample in readiness["samples"]:
        sample["runtimeEndpointsReady"] = 1
    record = run.build(readiness=dumps(readiness))
    assert not check(record, "the-runtime-service-lost-every-ready-endpoint")["passed"]


def test_a_gap_in_the_readiness_samples_is_not_usable(run: Run) -> None:
    """A window nothing sampled is a window this record cannot describe."""
    readiness = run.readiness()
    samples = readiness["samples"]
    # Every sample between the deletion and the replacement being ready is dropped
    # but the first, which leaves more than the minimum number of samples and a gap
    # across the very window the record is about.
    readiness["samples"] = [samples[0], *samples[-5:]]
    assert len(readiness["samples"]) >= DESCRIPTOR.minimum_samples
    record = run.build(readiness=dumps(readiness))
    assert not check(record, "readiness-samples-cover-the-replacement")["passed"]


def test_too_few_readiness_samples_are_refused(run: Run) -> None:
    readiness = run.readiness()
    readiness["samples"] = readiness["samples"][:2]
    with pytest.raises(RecoveryRefused, match="readiness sample"):
        run.build(readiness=dumps(readiness))


def test_a_registered_absence_that_answered_is_not_usable(run: Run) -> None:
    """A signal recorded as emitting nothing, which emitted something, is a finding."""
    telemetry = run.telemetry()
    for entry in telemetry["series"]:
        if entry["seriesId"] == "model-readiness-by-workload":
            entry["result"] = [{"labels": {}, "values": [[run.settled / 1000, "1"]]}]
    record = run.build(telemetry=dumps(telemetry))
    assert not check(record, "telemetry-registered-absences-are-absent")["passed"]


def test_a_registered_signal_that_did_not_answer_is_not_usable(run: Run) -> None:
    telemetry = run.telemetry()
    for entry in telemetry["series"]:
        if entry["seriesId"] == "api-requests-by-outcome":
            entry["status"] = "refused"
            entry["result"] = []
    record = run.build(telemetry=dumps(telemetry))
    assert not check(record, "telemetry-registered-signals-answered")["passed"]


def test_an_expression_the_descriptor_does_not_register_is_refused(run: Run) -> None:
    telemetry = run.telemetry()
    telemetry["series"][0]["expr"] = "up"
    with pytest.raises(RecoveryRefused, match="expression"):
        run.build(telemetry=dumps(telemetry))


def test_the_record_does_not_decide_whether_a_signal_exposed_the_event(
    run: Run,
) -> None:
    """ADR 0013 D4 keeps a statement like that in a reviewed document, not a tool."""
    record = run.build()
    text = dumps(record)
    assert "exposedTheEvent" not in text
    assert "not decided here" in record["telemetry"]["note"]
    for row in record["telemetry"]["series"]:
        assert set(row) >= {"exposure", "expectation", "readingBeforeDeletion"}


def test_an_untouched_tier_that_restarted_is_not_usable(
    run: Run, tmp_path: Path
) -> None:
    cluster = write_cluster(
        tmp_path / "restarted",
        **{
            "pods-after.json": {
                "items": [
                    pod("api", "inferops-inferops-llm-bbbb-1", "u-api", restarts=1),
                    pod("runtime", REPLACEMENT_POD, "u-runtime-2"),
                    pod(
                        "collector",
                        "inferops-inferops-llm-collector-cccc-1",
                        "u-collector",
                    ),
                ]
            }
        },
    )
    environment = dumps(extract_environment(cluster, DESCRIPTOR))
    record = run.build(environment=environment)
    assert not check(record, "the-tiers-that-were-not-deleted-did-not-restart")[
        "passed"
    ]


def keys_of(document: Any) -> set[str]:
    """Every member name anywhere in a record, so a claim cannot hide in a nested one."""
    found: set[str] = set()
    if isinstance(document, dict):
        for key, value in document.items():
            found.add(str(key))
            found |= keys_of(value)
    elif isinstance(document, list):
        for value in document:
            found |= keys_of(value)
    return found


def test_the_record_does_not_claim_the_artifact_survived(run: Run) -> None:
    """Persistence is V1-S3-003-PR2's result and this experiment does not repeat it.

    The prose says so; what this checks is that no *field* reports an artifact
    identity, because a field is what a later document would quote as a finding.
    """
    record = run.build()
    for key in keys_of(record):
        lowered = key.lower()
        for absent in ("inode", "mtime", "artifactsha", "artifactbyte"):
            assert absent not in lowered, key
    assert any("V1-S3-003-PR2" in line for line in record["observations"])


def test_the_in_flight_requests_at_the_deletion_are_counted(run: Run) -> None:
    record = run.build()
    assert "inFlightAtDeletion" in record["callerImpact"]
    assert record["callerImpact"]["inFlightAtDeletion"]["dispatched"] >= 0


def test_the_same_phase_comparison_says_whether_it_is_available(run: Run) -> None:
    record = run.build()
    comparison = record["callerImpact"]["withinTheDisruptedScenario"]
    assert comparison["scenarioId"] == "c1"
    assert isinstance(comparison["comparable"], bool)


@pytest.mark.parametrize(
    "name",
    (
        "environment",
        "lifecycle",
        "readiness",
        "telemetry",
        "disruptedRaw",
        "recoveredRaw",
    ),
)
def test_an_input_carrying_a_private_value_is_refused(run: Run, name: str) -> None:
    text = run.texts()[name]
    # The value has no name segment after it on purpose: the security baseline
    # refuses a committed "/home/<name>/" shape anywhere, including in a test
    # sample, and this only has to trip the record's own private-shape check.
    stray = chr(10) + '{"strayNote": "/home/"}' + chr(10)
    with pytest.raises(RecoveryRefused, match="host path"):
        run.build(**{name: text + stray})


def test_the_record_pins_every_input_by_digest(run: Run) -> None:
    record = run.build()
    assert set(record["inputs"]) == {
        "environment",
        "lifecycle",
        "readiness",
        "telemetry",
        "disruptedRaw",
        "recoveredRaw",
    }
    assert all(len(value) == 64 for value in record["inputs"].values())


# --------------------------------------------------------------------------
# The readers the shell workflow drives
# --------------------------------------------------------------------------


def test_the_facts_file_is_the_one_the_load_generator_accepts(tmp_path: Path) -> None:
    cluster = write_cluster(tmp_path)
    facts = extract_facts(cluster, DESCRIPTOR)
    assert load.parse_facts(facts).provider == "docker-desktop"


def test_a_release_with_two_runtime_pods_is_refused(tmp_path: Path) -> None:
    cluster = write_cluster(
        tmp_path,
        **{
            "pods-before.json": {
                "items": [
                    pod("api", "inferops-inferops-llm-bbbb-1", "u-api"),
                    pod("runtime", BASELINE_POD, "u-runtime-1"),
                    pod("runtime", REPLACEMENT_POD, "u-runtime-2"),
                    pod(
                        "collector",
                        "inferops-inferops-llm-collector-cccc-1",
                        "u-collector",
                    ),
                ]
            }
        },
    )
    with pytest.raises(RecoveryRefused, match="exactly one of each"):
        extract_environment(cluster, DESCRIPTOR)


def test_a_pod_running_an_image_its_template_does_not_resolve_to_is_refused(
    tmp_path: Path,
) -> None:
    cluster = write_cluster(
        tmp_path,
        **{
            "image-runtime.json": {
                "status": {
                    "id": "sha256:" + "2" * 64,
                    "repoDigests": ["other@sha256:" + "9" * 64],
                }
            }
        },
    )
    with pytest.raises(RecoveryRefused, match="digest"):
        extract_environment(cluster, DESCRIPTOR)


def test_the_environment_keeps_other_workloads_as_a_count_and_never_a_name(
    tmp_path: Path,
) -> None:
    environment = extract_environment(write_cluster(tmp_path), DESCRIPTOR)
    assert environment["background"]["runningPodsOutsideRelease"] == 1
    assert "another-project" not in dumps(environment)


def test_the_readiness_reader_refuses_samples_out_of_order(run: Run) -> None:
    readiness = run.readiness()
    readiness["samples"][1]["atEpochMs"] = readiness["samples"][0]["atEpochMs"] - 1
    with pytest.raises(RecoveryError):
        parse_readiness(readiness, DESCRIPTOR)


def test_the_lifecycle_reader_derives_the_offset_it_does_not_take_it(run: Run) -> None:
    parsed = parse_lifecycle(run.lifecycle(), DESCRIPTOR)
    assert parsed["deletion"]["issuedAfterLoadStartMs"] == run.deleted - run.launched


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------


def test_check_prints_the_summary_and_contacts_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["check"]) == cli.EXIT_OK
    printed = capsys.readouterr().out
    assert "not started" in printed
    assert "availability" in printed


def test_fields_without_a_path_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["fields"]) == cli.EXIT_FAILED
    assert "at least one dotted path" in capsys.readouterr().err


@pytest.mark.parametrize("command", ("repository", "facts", "telemetry", "record"))
def test_a_command_without_its_run_directory_is_refused(command: str) -> None:
    assert cli.main([command]) == cli.EXIT_FAILED


def test_verify_without_a_directory_is_refused() -> None:
    assert cli.main(["verify"]) == cli.EXIT_FAILED


def test_record_writes_its_inputs_and_its_record(run: Run, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "cluster").mkdir(parents=True)
    for source in run.cluster.iterdir():
        (run_dir / "cluster" / source.name).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )
    (run_dir / "lifecycle.json").write_text(run.lifecycle_text, encoding="utf-8")
    (run_dir / "readiness.json").write_text(run.readiness_text, encoding="utf-8")
    (run_dir / "telemetry.json").write_text(run.telemetry_text, encoding="utf-8")
    (run_dir / "run-1-raw.jsonl").write_text(run.disrupted_raw_text, encoding="utf-8")
    (run_dir / "run-2-raw.jsonl").write_text(run.recovered_raw_text, encoding="utf-8")
    assert cli.main(["record", "--run-dir", str(run_dir)]) == cli.EXIT_OK
    record_dir = run_dir / "record"
    for name in cli.RECORD_FILES.values():
        assert (record_dir / name).exists(), name
    assert cli.main(["verify", "--dir", str(record_dir)]) == cli.EXIT_OK


def test_verify_refuses_a_record_its_inputs_do_not_produce(
    run: Run, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "committed"
    directory.mkdir()
    texts = run.texts()
    for name in cli.INPUT_NAMES:
        (directory / cli.RECORD_FILES[name]).write_text(texts[name], encoding="utf-8")
    record = run.build()
    record["usable"] = False
    (directory / cli.RECORD_FILES["record"]).write_text(dumps(record), encoding="utf-8")
    assert cli.main(["verify", "--dir", str(directory)]) == cli.EXIT_FAILED
    assert "is not what its inputs produce" in capsys.readouterr().err


# --------------------------------------------------------------------------
# The documents this experiment publishes
# --------------------------------------------------------------------------


def test_the_procedure_document_states_every_limitation() -> None:
    """A limitation in the descriptor and not in the document is not published."""
    procedure = " ".join(PROCEDURE.read_text(encoding="utf-8").split())
    assert "deploy/serving/experiments/inference-pod-recovery.v1.json" in procedure
    assert "scripts/environment/inference-pod-recovery.sh" in procedure
    for limitation in DESCRIPTOR.limitations:
        assert " ".join(limitation.split()) in procedure, limitation


def test_the_procedure_and_the_decision_name_the_boundary() -> None:
    procedure = PROCEDURE.read_text(encoding="utf-8")
    for word in ("availability", "service-level objective", "benchmark"):
        assert word in procedure, word
    assert "portable capacity" in DECISION.read_text(encoding="utf-8")


def test_the_report_template_is_a_template_and_holds_no_result() -> None:
    """A template edited to hold a result is a record nobody registered in advance."""
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "<" in template and ">" in template
    for section in (
        "## Classification",
        "## Provenance",
        "## Environment",
        "## Method",
        "## Results",
        "## Limitations",
        "## Authorisation",
    ):
        assert section in template, section
    assert DOCUMENT["reportTemplateRef"].endswith(TEMPLATE.name)


def test_the_experiment_says_which_record_it_extends() -> None:
    assert EXTENDS.exists()
    assert (
        DOCUMENT["extendsRef"]
        == "docs/proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md"
    )
    extended = EXTENDS.read_text(encoding="utf-8")
    assert "Nothing here measures that outage from a caller's side" in extended


# --------------------------------------------------------------------------
# The committed record, when there is one
# --------------------------------------------------------------------------

committed = pytest.mark.skipif(
    not COMMITTED_RECORD.exists(), reason="no committed recovery record"
)


@committed
def test_the_committed_record_regenerates_from_its_committed_inputs() -> None:
    assert (
        cli.main(["verify", "--dir", str(PROOF_DIR), "--prefix", PROOF_PREFIX])
        == cli.EXIT_OK
    )


@committed
def test_the_committed_record_is_labelled_and_bounded() -> None:
    record = json.loads(COMMITTED_RECORD.read_text(encoding="utf-8"))
    assert record["evidenceClass"] == "local-real-cpu"
    assert record["certificationCeiling"] == "C2"
    for flag in ("productionBenchmark", "portableCapacityClaim", "availabilityClaim"):
        assert record[flag] is False, flag
    assert record["usable"] is True


@committed
def test_no_committed_input_carries_generated_text_or_a_private_value() -> None:
    for name in cli.RECORD_FILES.values():
        path = PROOF_DIR / f"{PROOF_PREFIX}{name}"
        text = path.read_text(encoding="utf-8")
        refuse_private(text, path.name)
        assert PROFILE.fixture.messages[0]["content"] not in text
        assert '"content"' not in text


@committed
def test_the_report_quotes_the_record_faithfully() -> None:
    record = json.loads(COMMITTED_RECORD.read_text(encoding="utf-8"))
    report = REPORT.read_text(encoding="utf-8")
    assert record["descriptorSha256"] in report
    assert record["disruption"]["pod"]["name"] in report
    assert record["replacement"]["pod"]["name"] in report
    for key in (
        "deletionToReplacementReadyMs",
        "deletionToServiceRestoredMs",
        "callerVisibleOutageMs",
    ):
        value = record["timings"][key]
        # Digit groups are separated in prose and not in the record. Every
        # separator this repository's records use is stripped, in either form.
        thinned = re.sub(r"(?<=\d)[\s,\u2009](?=\d)", "", report)
        assert str(value) in thinned, key
