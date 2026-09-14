"""The performance scenario matrix: its descriptor, its readers, and its record.

Nothing here sends load, installs anything, or contacts a cluster. The raw load sets
are produced by `tools.llm_load.execute` against an injected transport and a fake
clock, the cluster's answers are JSON written into a temporary directory, and the
collector is a function. No figure in this suite describes serving.

It is heaviest where a performance record goes wrong without anyone noticing:

- **drift** -- a scenario matrix that no longer matches the load profile it pins, or
  whose schedule, sampling, or telemetry would quietly change what a run measures;
- **placement** -- a phase placed against samples taken outside its window, or a CPU
  figure computed from anything but the counters' own increase;
- **the record** -- a run whose pods were replaced, whose counters disagree with the
  raw sets, or whose samples leave a gap must be recorded as not usable, and a
  committed record must regenerate exactly from its committed inputs.
"""

from __future__ import annotations

import copy
import http.server
import json
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.llm_load import core as load
from tools.llm_load.core import HostRecord, HttpAnswer
from tools.model_acquisition import load_manifest
from tools.performance_scenarios import __main__ as cli
from tools.performance_scenarios import core, live
from tools.performance_scenarios.core import (
    DESCRIPTOR_PATH,
    ScenarioError,
    ScenarioRefused,
    build_record,
    descriptor_fields,
    dumps,
    extract_environment,
    extract_facts,
    load_descriptor,
    parse_sample_line,
    parse_samples,
    refuse_private,
    resource_usage,
    samples_jsonl,
    validate_descriptor,
)
from tools.runtime_packaging import load_runtime_package

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR = load_descriptor()
DOCUMENT: dict[str, Any] = json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
PROFILE = DESCRIPTOR.profile
MODEL = "qwen3-1-7b-q8-0"
REVISION = load_manifest().revision
HOST = HostRecord("TestOS", "1", "x86_64", 4, None, "3.12.0")
API_IMAGE = "localhost/inferops-api@sha256:" + "a" * 64
RUNTIME_IMAGE = load_runtime_package().image_reference
COLLECTOR_IMAGE = "prom/prometheus@sha256:" + "c" * 64

PROOF_DIR = REPO_ROOT / "docs/proof/serving"
PROOF_PREFIX = "v1-s4-004-pr1-"
COMMITTED_RECORD = PROOF_DIR / f"{PROOF_PREFIX}performance-record.v1alpha1.json"
VALIDATION_RECORD = PROOF_DIR / "v1-s4-004-pr1-validation.md"
PROCEDURE = REPO_ROOT / "docs/serving/performance-scenarios.md"
DECISION = (
    REPO_ROOT
    / "docs/architecture/decisions/ADR-0013-bounded-local-performance-observations.md"
)
SCRIPT = REPO_ROOT / "scripts/environment/performance-scenarios.sh"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def validate(document: dict[str, Any]) -> core.Descriptor:
    return validate_descriptor(document, sha256="0" * 64, profile=PROFILE)


def chart_name() -> str:
    chart = yaml.safe_load(
        (REPO_ROOT / "charts/inferops-llm/Chart.yaml").read_text(encoding="utf-8")
    )
    return f"{chart['name']}-{chart['version']}"


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.lock = threading.Lock()

    def __call__(self) -> float:
        with self.lock:
            return self.now

    def advance(self, seconds: float) -> None:
        with self.lock:
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


def real_raw(origin_ms: int) -> str:
    """A real-mode raw set whose phases start at known epoch milliseconds."""
    clock = Clock()

    def transport(
        method: str, url: str, body: Any, headers: Any, timeout: float
    ) -> HttpAnswer:
        if method == "GET":
            return IDENTITY["/" + url.split("/", 3)[3]]
        clock.advance(1.0)
        return completion_answer()

    facts = {
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
    run = load.execute(
        replace(PROFILE, max_requests_per_level=4, duration_seconds=600),
        base_url="http://127.0.0.1:18093",
        mode=load.MODE_REAL,
        confirmed=True,
        facts=load.parse_facts(facts),
        transport=transport,
        clock=clock,
        epoch_ms=lambda: origin_ms,
        host=HOST,
    )
    return "\n".join(load.raw_lines(run)) + "\n"


def pod(
    role: str,
    uid: str,
    *,
    restarts: int = 0,
    image_ids: list[str] | None = None,
    phase: str = "Running",
) -> dict[str, Any]:
    component = core.ROLE_COMPONENTS[role]
    images = {"api": API_IMAGE, "runtime": RUNTIME_IMAGE, "collector": COLLECTOR_IMAGE}
    return {
        "metadata": {
            "name": f"inferops-{role}-0",
            "uid": uid,
            "namespace": "inferops-release",
            "labels": {"app.kubernetes.io/component": component},
        },
        "status": {
            "phase": phase,
            "containerStatuses": [
                {"ready": True, "restartCount": restarts, "imageID": image_id}
                for image_id in (image_ids or [images[role]])
            ],
        },
    }


def deployment(
    name: str, container: str, image: str, *, available: int = 1
) -> dict[str, Any]:
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
                            "args": ["--threads", "6"],
                        }
                    ]
                }
            },
        },
        "status": {"availableReplicas": available},
    }


def write_cluster(tmp_path: Path, **overrides: Any) -> Path:
    cluster = tmp_path / "cluster"
    cluster.mkdir(parents=True, exist_ok=True)
    pods = [
        pod("api", "u-api"),
        pod("runtime", "u-runtime"),
        pod("collector", "u-collector"),
    ]
    documents: dict[str, Any] = {
        "target.json": {
            "provider": "docker-desktop",
            "cluster": "docker-desktop",
            "context": "docker-desktop",
            "verifiedAt": "2026-09-14T00:00:00Z",
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
            "vmLogicalCpus": 12,
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
        "pods-before.json": {"items": [*pods, pod("api", "u-hook", phase="Succeeded")]},
        "pods-after.json": {"items": pods},
        "running-pods.json": {
            "items": [
                *pods,
                {"metadata": {"name": "other", "namespace": "another-project"}},
                {"metadata": {"name": "other2", "namespace": "another-project"}},
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


def sample_line(
    epoch_ms: int,
    *,
    node_cpu_ns: int,
    runtime_cpu_ns: int | None,
    busy: int,
    total: int,
) -> str:
    runtime = (
        "missing,missing,missing"
        if runtime_cpu_ns is None
        else f"{runtime_cpu_ns},3000,1000"
    )
    micros = epoch_ms * 1000
    return (
        f"{micros - 100_000} {micros + 100_000} node_ns={epoch_ms * 1_000_000} "
        f"vm={busy},0,0,{total - busy},0,0,0,0 node={node_cpu_ns},9000,1000 "
        f"api=100,2000,500 runtime={runtime} collector=200,4000,1000"
    )


def synthetic_samples(
    start_ms: int,
    end_ms: int,
    *,
    step_ms: int = 2000,
    gap: tuple[int, int] | None = None,
) -> str:
    """Counters that grow exactly: node one core, runtime half a core, VM 25% of 12 CPUs."""
    lines = []
    for epoch_ms in range(start_ms, end_ms + step_ms, step_ms):
        if gap is not None and gap[0] <= epoch_ms <= gap[1]:
            continue
        elapsed = epoch_ms - start_ms
        lines.append(
            sample_line(
                epoch_ms,
                node_cpu_ns=elapsed * 1_000_000,
                runtime_cpu_ns=elapsed * 500_000,
                busy=elapsed,
                total=elapsed * 4,
            )
        )
    return "\n".join(lines) + "\n"


class Scenario:
    """A complete, consistent set of record inputs."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.origins = [1_800_000_000_000, 1_800_000_200_000]
        self.raws = {
            f"run-{index}-raw.jsonl": real_raw(origin)
            for index, origin in enumerate(self.origins, start=1)
        }
        parsed = [load.parse_raw(text) for text in self.raws.values()]
        self.dispatched = [len(raw.records) for raw in parsed]
        self.tokens = [
            sum(record.output_tokens or 0 for record in raw.records) for raw in parsed
        ]
        idle_start = self.origins[0] - 70_000
        runs = []
        for index, (origin, raw) in enumerate(
            zip(self.origins, parsed, strict=True), start=1
        ):
            runs.append(
                {
                    "repetition": index,
                    "rawFile": f"run-{index}-raw.jsonl",
                    "launchedEpochMs": origin - 2000,
                    "exitedEpochMs": origin + raw.end["elapsedMs"] + 1000,
                    "exitCode": 0,
                }
            )
        self.windows = {
            "idleBaseline": {
                "startEpochMs": idle_start,
                "endEpochMs": self.origins[0] - 5000,
            },
            "runs": runs,
            "settledEpochMs": runs[-1]["exitedEpochMs"] + 90_000,
        }
        self.samples = samples_jsonl(
            parse_samples(
                synthetic_samples(
                    idle_start - 1000, self.windows["settledEpochMs"], step_ms=250
                )
            )
        )
        self.environment = extract_environment(write_cluster(tmp_path), DESCRIPTOR)
        self.telemetry = self.make_telemetry()

    def make_telemetry(self, *, api_offset: int = 0) -> dict[str, Any]:
        cumulative = {"requests": [0], "tokens": [0]}
        for dispatched, tokens in zip(self.dispatched, self.tokens, strict=True):
            cumulative["requests"].append(cumulative["requests"][-1] + dispatched)
            cumulative["tokens"].append(cumulative["tokens"][-1] + tokens)
        windows = core.parse_windows(self.windows, DESCRIPTOR)
        instants = []
        for repetition, position, at_ms in core.instants_for(windows):
            index = repetition - 1 + (1 if position == "after" else 0)
            values: dict[str, list[tuple[dict[str, str], int]]] = {
                "api-requests-by-outcome": [
                    (
                        {"inferops_outcome": "success"},
                        cumulative["requests"][index]
                        + (api_offset if position == "after" else 0),
                    )
                ],
                "api-tokens-by-direction": [
                    (
                        {"inferops_token_direction": "output"},
                        cumulative["tokens"][index],
                    ),
                    ({"inferops_token_direction": "input"}, 999),
                ],
                "runtime-tokens-predicted": [({}, cumulative["tokens"][index])],
            }
            for series_id, rows in values.items():
                instants.append(
                    {
                        "repetition": repetition,
                        "position": position,
                        "atEpochMs": at_ms,
                        "seriesId": series_id,
                        "status": "success",
                        "rows": [
                            {"labels": labels, "value": str(value)}
                            for labels, value in rows
                        ],
                    }
                )
        return {
            "collectorVersion": "3.5.0",
            "series": [
                {"seriesId": series_id, "expr": expr, "status": "success", "result": []}
                for series_id, expr in DESCRIPTOR.series
            ],
            "instants": instants,
            "dashboard": [],
        }

    def build(self, **overrides: Any) -> dict[str, Any]:
        inputs: dict[str, Any] = {
            "environment_text": dumps(self.environment),
            "windows_text": dumps(self.windows),
            "raw_texts": self.raws,
            "samples_text": self.samples,
            "telemetry_text": dumps(self.telemetry),
        }
        inputs.update(overrides)
        return build_record(DESCRIPTOR, **inputs)


@pytest.fixture
def scenario(tmp_path: Path) -> Scenario:
    return Scenario(tmp_path)


def check(record: dict[str, Any], check_id: str) -> dict[str, Any]:
    return next(item for item in record["checks"] if item["checkId"] == check_id)


# --------------------------------------------------------------------------
# The committed descriptor
# --------------------------------------------------------------------------


def test_the_committed_descriptor_is_the_load_profiles_matrix() -> None:
    assert [(s.scenario_id, s.role, s.concurrency) for s in DESCRIPTOR.scenarios] == [
        ("warmup", "warm-up", PROFILE.warmup_concurrency),
        ("c1", "baseline", 1),
        ("c2", "higher-load", 2),
        ("c4", "higher-load", 4),
    ]
    assert DOCUMENT["load"]["profileSha256"] == PROFILE.profile_sha256
    assert DOCUMENT["productionBenchmark"] is False
    assert DOCUMENT["portableCapacityClaim"] is False
    assert DOCUMENT["evidenceClass"] == "local-real-cpu"
    assert [
        provider["providerId"] for provider in DOCUMENT["cluster"]["providers"]
    ] == ["docker-desktop"]
    assert DOCUMENT["stability"]["cpuThresholdApplied"] is False


def test_every_telemetry_series_is_aggregated_away_from_per_target_labels() -> None:
    for series_id, expression in DESCRIPTOR.series:
        assert expression.startswith("sum"), series_id


MUTATIONS: list[tuple[str, Any]] = [
    ("benchmark claimed", lambda d: d.update(productionBenchmark=True)),
    ("capacity claimed", lambda d: d.update(portableCapacityClaim=True)),
    ("boundary weakened", lambda d: d.update(boundary="A bounded observation.")),
    ("another evidence class", lambda d: d.update(evidenceClass="mock")),
    ("another lane", lambda d: d.update(lane="capacity")),
    ("stale profile digest", lambda d: d["load"].update(profileSha256="0" * 64)),
    ("another load module", lambda d: d["load"].update(module="tools.other")),
    (
        "reference provider dropped",
        lambda d: d["cluster"].update(
            providers=[{"providerId": "kind", "name": "x", "context": "y"}]
        ),
    ),
    (
        "unpublished provider",
        lambda d: d["cluster"]["providers"].append(
            {"providerId": "minikube", "name": "m", "context": "m"}
        ),
    ),
    ("level concurrency drift", lambda d: d["scenarios"][3].update(concurrency=8)),
    ("levels reordered", lambda d: d["scenarios"].insert(1, d["scenarios"].pop(2))),
    ("no warm-up", lambda d: d["scenarios"].pop(0)),
    ("baseline not first", lambda d: d["scenarios"][1].update(role="higher-load")),
    ("two replicas", lambda d: d["release"].update(apiReplicas=2)),
    ("namespace prefix", lambda d: d["release"].update(namespace="default")),
    ("too many repetitions", lambda d: d["schedule"].update(repetitions=4)),
    ("idle too short", lambda d: d["schedule"].update(idleBaselineSeconds=5)),
    (
        "settle under two scrapes",
        lambda d: d["schedule"].update(settleBetweenRunsSeconds=59),
    ),
    (
        "cpu threshold applied",
        lambda d: d["stability"].update(cpuThresholdApplied=True),
    ),
    (
        "restarts tolerated",
        lambda d: d["stability"].update(requireZeroContainerRestarts=False),
    ),
    ("busy sampler", lambda d: d["resources"].update(sampleIntervalMs=500)),
    ("gap below two intervals", lambda d: d["resources"].update(maximumGapMs=3000)),
    (
        "another resource source",
        lambda d: d["resources"].update(source="metrics-server"),
    ),
    (
        "scrape interval drift",
        lambda d: d["telemetry"].update(scrapeIntervalSeconds=15),
    ),
    ("step above scrape", lambda d: d["telemetry"].update(rangeStepSeconds=60)),
    (
        "unaggregated series",
        lambda d: d["telemetry"]["series"][0].update(
            expr="inferops_inference_requests_total"
        ),
    ),
    (
        "duplicate series",
        lambda d: d["telemetry"]["series"].append(dict(d["telemetry"]["series"][0])),
    ),
    (
        "unknown reconciliation series",
        lambda d: d["telemetry"]["reconciliation"][0].update(seriesId="nope"),
    ),
    (
        "reconciliation against nothing",
        lambda d: d["telemetry"]["reconciliation"][0].update(compareWith="latency"),
    ),
    (
        "half a label filter",
        lambda d: d["telemetry"]["reconciliation"][1].pop("labelValue"),
    ),
    (
        "no dashboard capture",
        lambda d: d["telemetry"].update(dashboardCaptureAt="never"),
    ),
    ("forward not loopback", lambda d: d["forwards"].update(host="0.0.0.0")),
    (
        "forwards share a port",
        lambda d: d["forwards"].update(collectorPort=d["forwards"]["apiPort"]),
    ),
    (
        "evidence outside the cache",
        lambda d: d["evidence"].update(directory="docs/proof"),
    ),
    (
        "evidence file with a path",
        lambda d: d["evidence"].update(samplesFile="../x.txt"),
    ),
    (
        "generated text retained",
        lambda d: d["evidence"].update(retainGeneratedText=True),
    ),
    ("claim removed", lambda d: d["cleanup"].update(removesModelCacheClaim=True)),
    ("release kept", lambda d: d["cleanup"].update(uninstallsRelease=False)),
    ("no limitations", lambda d: d.update(limitations=[])),
    (
        "missing decision",
        lambda d: d.update(decisionRef="docs/architecture/decisions/ADR-9999.md"),
    ),
]


@pytest.mark.parametrize(
    "mutate", [m for _, m in MUTATIONS], ids=[name for name, _ in MUTATIONS]
)
def test_a_drifted_descriptor_is_refused(mutate: Any) -> None:
    document = copy.deepcopy(DOCUMENT)
    mutate(document)
    with pytest.raises((ScenarioError, load.LoadError)):
        validate(document)


def test_the_worst_case_schedule_is_bounded_by_a_ceiling_in_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(core, "MAXIMUM_TOTAL_SECONDS", 100)
    with pytest.raises(ScenarioError, match="worst case"):
        validate(copy.deepcopy(DOCUMENT))


def test_fields_reads_scalars_and_refuses_anything_else() -> None:
    assert descriptor_fields(DESCRIPTOR, ["release.namespace", "forwards.apiPort"]) == [
        "inferops-release",
        "18093",
    ]
    for path in (
        "scenarios",
        "release.missing",
        "release",
        "../x",
        "stability.cpuThresholdApplied",
    ):
        with pytest.raises(ScenarioError):
            descriptor_fields(DESCRIPTOR, [path])


# --------------------------------------------------------------------------
# Resource samples
# --------------------------------------------------------------------------


def test_a_sample_line_is_parsed_into_integers() -> None:
    sample = parse_sample_line(
        sample_line(10_000, node_cpu_ns=5, runtime_cpu_ns=7, busy=3, total=12)
    )
    assert sample["hostEpochMs"] == 10_000
    assert sample["hostReadMs"] == 200
    assert sample["nodeClockNs"] == 10_000_000_000
    assert sample["virtualMachine"] == {"busyJiffies": 3, "totalJiffies": 12}
    assert sample["node"] == {"cpuNs": 5, "memoryWorkingSetBytes": 8000}
    assert sample["pods"]["runtime"] == {"cpuNs": 7, "memoryWorkingSetBytes": 2000}


def test_a_missing_tier_reads_none_rather_than_zero() -> None:
    sample = parse_sample_line(
        sample_line(10_000, node_cpu_ns=5, runtime_cpu_ns=None, busy=3, total=12)
    )
    assert sample["pods"]["runtime"] == {"cpuNs": None, "memoryWorkingSetBytes": None}


@pytest.mark.parametrize(
    "line",
    [
        "",
        "2 1 node_ns=1 vm=1,1,1,1,1,1,1,1 node=1,1,1 api=1,1,1 runtime=1,1,1 collector=1,1,1",
        "1 2 node_ns=1 vm=1,1,1 node=1,1,1 api=1,1,1 runtime=1,1,1 collector=1,1,1",
        "1 2 node_ns=1 vm=1,1,1,1,1,1,1,1 node=1,1,1 api=1,1,1 runtime=1,1,1",
        "1 2 node_ns=1 vm=1,1,1,1,1,1,1,1 node=1,1,1 api=1,1,1 runtime=1,1,1 collector=1,1,1 extra=1,1,1",
        "1 2 node_ns=1 vm=1,1,1,1,1,1,1,1 node=1,-1,1 api=1,1,1 runtime=1,1,1 collector=1,1,1",
        "1 2 node_ns=missing vm=1,1,1,1,1,1,1,1 node=1,1,1 api=1,1,1 runtime=1,1,1 collector=1,1,1",
        "1 2 node_ns=1 vm=1,1,1,1,1,1,1,1 node=1,1 api=1,1,1 runtime=1,1,1 collector=1,1,1",
    ],
)
def test_a_malformed_sample_line_is_refused(line: str) -> None:
    with pytest.raises(ScenarioError):
        parse_sample_line(line)


def test_samples_out_of_time_order_are_refused() -> None:
    text = "\n".join(
        sample_line(ms, node_cpu_ns=1, runtime_cpu_ns=1, busy=1, total=2)
        for ms in (5000, 3000)
    )
    with pytest.raises(ScenarioError, match="time order"):
        parse_samples(text)


def test_cpu_is_the_counters_increase_over_the_node_clock_inside_the_window() -> None:
    samples = parse_samples(synthetic_samples(1_000_000, 1_060_000))
    usage = resource_usage(samples, 1_010_000, 1_030_000, vm_cpus=12, minimum_samples=3)
    assert usage["samples"] == 11
    assert usage["coveredMs"] == 20_000
    assert usage["cpuMillicores"]["node"] == 1000
    assert usage["cpuMillicores"]["runtime"] == 500
    assert usage["cpuMillicores"]["api"] == 0
    assert usage["cpuMillicores"]["virtualMachine"] == 3000
    assert usage["cpuMillicores"]["nodeOutsideRelease"] == 500
    assert usage["memoryPeakWorkingSetBytes"] == {
        "node": 8000,
        "api": 1500,
        "runtime": 2000,
        "collector": 3000,
    }


def test_a_window_with_too_few_samples_has_no_cpu_figure() -> None:
    samples = parse_samples(synthetic_samples(1_000_000, 1_060_000, step_ms=10_000))
    usage = resource_usage(samples, 1_010_500, 1_019_500, vm_cpus=12, minimum_samples=3)
    assert usage["samples"] == 0
    assert usage["sufficient"] is False
    assert usage["cpuMillicores"] is None


# --------------------------------------------------------------------------
# What the cluster reported
# --------------------------------------------------------------------------


def test_facts_are_derived_from_the_clusters_answers_and_pass_the_load_tools_checks(
    tmp_path: Path,
) -> None:
    facts = extract_facts(write_cluster(tmp_path), DESCRIPTOR)
    assert facts["apiImage"] == API_IMAGE
    assert facts["runtimeImage"] == RUNTIME_IMAGE
    assert facts["releaseRevision"] == 1
    assert facts["repositoryRevision"] == "b" * 40
    load.parse_facts(facts)


def test_facts_refuse_a_pod_that_runs_another_image(tmp_path: Path) -> None:
    pods = {
        "items": [
            pod(
                "api", "u-api", image_ids=["localhost/inferops-api@sha256:" + "f" * 64]
            ),
            pod("runtime", "u-runtime"),
            pod("collector", "u-collector"),
        ]
    }
    with pytest.raises(ScenarioRefused, match="not the one its template"):
        extract_facts(write_cluster(tmp_path, **{"pods-before.json": pods}), DESCRIPTOR)


def test_one_image_under_two_index_digests_binds_through_the_nodes_own_answer(
    tmp_path: Path,
) -> None:
    """What the first real attempt refused, wrongly.

    The API build had been imported twice. Both OCI index digests name one image in
    the node, and the pod reported the older one while its template named the newer.
    A digest comparison refused a pod running the right bytes; the node's own record
    of the template reference binds them.
    """
    older = "localhost/inferops-api@sha256:" + "7" * 64
    pods = {
        "items": [
            pod("api", "u-api", image_ids=[older]),
            pod("runtime", "u-runtime"),
            pod("collector", "u-collector"),
        ]
    }
    image = {"status": {"id": "sha256:" + "1" * 64, "repoDigests": [older, API_IMAGE]}}
    cluster = write_cluster(
        tmp_path, **{"pods-before.json": pods, "image-api.json": image}
    )
    assert extract_facts(cluster, DESCRIPTOR)["apiImage"] == API_IMAGE
    environment = extract_environment(cluster, DESCRIPTOR)
    assert environment["images"]["api"]["podImageIds"] == [older]
    assert environment["images"]["api"]["configId"] == "sha256:" + "1" * 64


def test_a_template_reference_the_node_does_not_carry_is_refused(
    tmp_path: Path,
) -> None:
    image = {
        "status": {
            "id": "sha256:" + "1" * 64,
            "repoDigests": ["localhost/inferops-api@sha256:" + "9" * 64],
        }
    }
    with pytest.raises(ScenarioRefused, match="does not carry"):
        extract_facts(write_cluster(tmp_path, **{"image-api.json": image}), DESCRIPTOR)


def test_two_running_pods_of_one_tier_are_refused(tmp_path: Path) -> None:
    pods = {
        "items": [
            pod("api", "u-api"),
            pod("runtime", "u-runtime"),
            pod("runtime", "u-runtime-2"),
            pod("collector", "u-collector"),
        ]
    }
    with pytest.raises(ScenarioRefused, match="exactly one"):
        extract_facts(write_cluster(tmp_path, **{"pods-before.json": pods}), DESCRIPTOR)


def test_the_environment_keeps_counts_of_other_workloads_and_not_their_names(
    tmp_path: Path,
) -> None:
    environment = extract_environment(write_cluster(tmp_path), DESCRIPTOR)
    assert environment["background"] == {
        "runningPodsOutsideRelease": 2,
        "namespacesWithRunningPodsOutsideRelease": 1,
    }
    text = dumps(environment)
    assert "another-project" not in text
    # The endpoint carrying a cluster address is not an allowlisted key.
    assert "INFEROPS_LLAMA_SERVER_ENDPOINT" not in text
    assert "192.0.2.10" not in text
    assert [pod["role"] for pod in environment["podsBefore"]] == [
        "api",
        "runtime",
        "collector",
    ]


# The path samples are assembled rather than written out, because the security
# baseline refuses any committed file that carries a personal filesystem path, and a
# test sample of one is still one.
USER_DIRECTORY = "Users"
HOME_DIRECTORY = "home"


@pytest.mark.parametrize(
    "value",
    [
        "C:\\" + USER_DIRECTORY + "\\operator\\x",
        "Z:/cache/model.gguf",
        "/" + HOME_DIRECTORY + "/operator/.kube",
        "198.51.100.7:8090",
        "node at 192.0.2.10",
    ],
)
def test_a_private_value_is_refused(value: str) -> None:
    with pytest.raises(ScenarioRefused):
        refuse_private(json.dumps({"value": value}), "document")


@pytest.mark.parametrize(
    "value",
    [
        "http://127.0.0.1:18093",
        "0.0.0.0",
        "v1.34.3",
        "sha256:" + "a" * 64,
        "5.15.146.1-microsoft-standard-WSL2",
        "/models/Qwen3-1.7B-Q8_0.gguf",
    ],
)
def test_ordinary_values_are_not_mistaken_for_private_ones(value: str) -> None:
    refuse_private(json.dumps({"value": value}), "document")


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


def test_a_consistent_run_is_usable_and_places_every_phase(scenario: Scenario) -> None:
    record = scenario.build()
    assert record["usable"] is True, [c for c in record["checks"] if not c["passed"]]
    assert record["productionBenchmark"] is False
    assert record["portableCapacityClaim"] is False
    assert record["saturationJudged"] is False
    assert [run["repetition"] for run in record["runs"]] == [1, 2]
    run = record["runs"][0]
    assert [phase["scenarioId"] for phase in run["phases"]] == [
        "warmup",
        "c1",
        "c2",
        "c4",
    ]
    for phase in run["phases"]:
        assert phase["startEpochMs"] >= scenario.origins[0]
        assert phase["resources"]["sufficient"] is True
        assert phase["resources"]["cpuMillicores"]["runtime"] == 500
    assert all(item["agrees"] for item in run["reconciliation"])
    assert record["observations"] == []


def test_the_record_is_a_pure_function_of_its_inputs(scenario: Scenario) -> None:
    assert dumps(scenario.build()) == dumps(scenario.build())


def test_a_counter_that_disagrees_with_the_raw_sets_makes_the_record_unusable(
    scenario: Scenario,
) -> None:
    record = scenario.build(telemetry_text=dumps(scenario.make_telemetry(api_offset=1)))
    assert record["usable"] is False
    assert check(record, "counters-reconcile-with-raw-records")["passed"] is False
    assert any(
        "api-requests-equal-dispatched" in line for line in record["observations"]
    )


def test_a_replaced_pod_makes_the_record_unusable(scenario: Scenario) -> None:
    environment = copy.deepcopy(scenario.environment)
    environment["podsAfter"][1]["uid"] = "u-runtime-replacement"
    record = scenario.build(environment_text=dumps(environment))
    assert check(record, "same-pods-throughout")["passed"] is False
    assert record["usable"] is False


def test_a_container_restart_makes_the_record_unusable(scenario: Scenario) -> None:
    environment = copy.deepcopy(scenario.environment)
    environment["podsAfter"][1]["restartCount"] = 1
    assert (
        check(
            scenario.build(environment_text=dumps(environment)),
            "zero-container-restarts",
        )["passed"]
        is False
    )


def test_a_restart_before_the_runs_is_counted_once_and_still_fails(
    scenario: Scenario,
) -> None:
    """A lifetime restart counter read twice is one restart, not two."""
    environment = copy.deepcopy(scenario.environment)
    environment["podsBefore"][1]["restartCount"] = 1
    environment["podsAfter"][1]["restartCount"] = 1
    record = scenario.build(environment_text=dumps(environment))
    restarts = check(record, "zero-container-restarts")
    assert restarts["passed"] is False
    assert restarts["detail"].startswith("1 container restart")


def test_a_non_finite_counter_read_is_refused_not_raised(scenario: Scenario) -> None:
    telemetry = scenario.make_telemetry()
    telemetry["instants"][1]["rows"][0]["value"] = "NaN"
    with pytest.raises(ScenarioError, match="whole number"):
        scenario.build(telemetry_text=dumps(telemetry))


def test_an_absent_counter_is_not_read_as_zero_when_the_runtime_had_decoded(
    scenario: Scenario,
) -> None:
    telemetry = empty_api_reads(scenario.make_telemetry(), 1)
    for entry in telemetry["instants"]:
        if (
            entry["repetition"] == 1
            and entry["position"] == "before"
            and entry["seriesId"] == "runtime-tokens-predicted"
        ):
            entry["rows"] = [{"labels": {}, "value": "17"}]
    record = scenario.build(telemetry_text=dumps(telemetry))
    assert record["runs"][0]["reconciliation"][0]["absentBeforeReadAsZero"] is False
    assert check(record, "counters-reconcile-with-raw-records")["passed"] is False


def test_a_private_value_in_a_raw_set_is_refused(scenario: Scenario) -> None:
    raws = dict(scenario.raws)
    raws["run-2-raw.jsonl"] = raws["run-2-raw.jsonl"].replace(
        '"TestOS"', '"198.51.100.4"'
    )
    with pytest.raises(ScenarioRefused):
        scenario.build(raw_texts=raws)


def test_a_missing_node_read_fails_coverage(scenario: Scenario) -> None:
    samples = [json.loads(line) for line in scenario.samples.splitlines()]
    samples[len(samples) // 2]["node"]["cpuNs"] = None
    text = "".join(json.dumps(sample, sort_keys=True) + "\n" for sample in samples)
    record = scenario.build(samples_text=text)
    assert check(record, "resource-samples-cover-every-phase")["passed"] is False


def test_the_script_checks_for_a_release_before_applying_prerequisites() -> None:
    assert SCRIPT_TEXT.index("inferops::target_helm status") < SCRIPT_TEXT.index(
        'terraform-prerequisites.sh" apply'
    )
    assert "roles,rolebindings" in SCRIPT_TEXT
    assert "wait_bounded" in SCRIPT_TEXT


def test_a_gap_in_the_samples_makes_the_record_unusable(scenario: Scenario) -> None:
    start = scenario.windows["idleBaseline"]["startEpochMs"] - 1000
    gap_start = scenario.origins[0] + 1000
    text = samples_jsonl(
        parse_samples(
            synthetic_samples(
                start,
                scenario.windows["settledEpochMs"],
                gap=(gap_start, gap_start + 20_000),
            )
        )
    )
    record = scenario.build(samples_text=text)
    assert check(record, "resource-samples-cover-every-phase")["passed"] is False


def test_a_refused_series_makes_the_record_unusable(scenario: Scenario) -> None:
    telemetry = scenario.make_telemetry()
    telemetry["series"][0]["status"] = "refused"
    assert (
        check(
            scenario.build(telemetry_text=dumps(telemetry)), "telemetry-series-answered"
        )["passed"]
        is False
    )


def test_a_raw_set_without_a_millisecond_origin_cannot_be_placed(
    scenario: Scenario,
) -> None:
    lines = scenario.raws["run-1-raw.jsonl"].splitlines()
    header = json.loads(lines[0])
    del header["startedAtEpochMs"]
    raws = dict(scenario.raws)
    raws["run-1-raw.jsonl"] = "\n".join([json.dumps(header), *lines[1:]]) + "\n"
    with pytest.raises(ScenarioRefused, match="startedAtEpochMs"):
        scenario.build(raw_texts=raws)


def test_a_counter_read_at_another_moment_is_refused(scenario: Scenario) -> None:
    telemetry = scenario.make_telemetry()
    telemetry["instants"][0]["atEpochMs"] += 1
    with pytest.raises(ScenarioError, match="moment the schedule defines"):
        scenario.build(telemetry_text=dumps(telemetry))


def test_a_private_value_in_an_input_is_refused(scenario: Scenario) -> None:
    telemetry = scenario.make_telemetry()
    telemetry["dashboard"] = [
        {"readings": {"x": {"rows": [{"labels": {"instance": "198.51.100.9:8090"}}]}}}
    ]
    with pytest.raises(ScenarioRefused):
        scenario.build(telemetry_text=dumps(telemetry))


def test_a_rehearsal_raw_set_is_not_accepted(scenario: Scenario) -> None:
    rehearsal = (
        REPO_ROOT / "docs/proof/serving/v1-s4-003-pr1-rehearsal-raw.jsonl"
    ).read_text(encoding="utf-8")
    raws = dict(scenario.raws)
    raws["run-1-raw.jsonl"] = rehearsal
    with pytest.raises((ScenarioRefused, ScenarioError)):
        scenario.build(raw_texts=raws)


def test_windows_out_of_order_are_refused(scenario: Scenario) -> None:
    windows = copy.deepcopy(scenario.windows)
    windows["runs"][1]["launchedEpochMs"] = windows["runs"][0]["exitedEpochMs"] - 1
    with pytest.raises(ScenarioError):
        scenario.build(windows_text=dumps(windows))


# --------------------------------------------------------------------------
# The collector capture
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:19093",
        "https://127.0.0.1:19093",
        "http://127.0.0.1",
        "http://127.0.0.1:19093/api",
        "http://u:p@127.0.0.1:1",
        "http://198.51.100.1:9090",
    ],
)
def test_the_collector_url_must_be_a_loopback_forward(url: str) -> None:
    with pytest.raises(ScenarioRefused):
        live.require_loopback(url)


def test_the_capture_reads_counters_at_the_scheduled_moments_and_the_dashboard_at_each_phase_end(
    scenario: Scenario,
) -> None:
    asked: list[tuple[str, dict[str, str]]] = []

    def ask(path: str, parameters: Any) -> dict[str, Any]:
        asked.append((path, dict(parameters)))
        if path == "/api/v1/status/buildinfo":
            return {"status": "success", "data": {"version": "3.5.0"}}
        if path == "/api/v1/query_range":
            return {
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [{"metric": {"le": "1"}, "values": [[1.5, "2"]]}],
                },
            }
        return {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [{"metric": {}, "value": [1.0, "3"]}],
            },
        }

    windows = core.parse_windows(scenario.windows, DESCRIPTOR)
    raws = [load.parse_raw(text) for text in scenario.raws.values()]
    captured = live.capture_telemetry(DESCRIPTOR, windows, raws, ask)
    assert captured["collectorVersion"] == "3.5.0"
    assert [entry["seriesId"] for entry in captured["series"]] == [
        series_id for series_id, _ in DESCRIPTOR.series
    ]
    expected_moments = {at for _, _, at in core.instants_for(windows)}
    assert {entry["atEpochMs"] for entry in captured["instants"]} == expected_moments
    assert len(captured["dashboard"]) == 2 * len(DESCRIPTOR.scenarios)
    phase_ends = {
        placed["endEpochMs"]
        for raw in raws
        for placed in core.phase_windows(raw, DESCRIPTOR)
    }
    assert {entry["atEpochMs"] for entry in captured["dashboard"]} == phase_ends
    range_queries = [
        parameters for path, parameters in asked if path == "/api/v1/query_range"
    ]
    assert all(
        parameters["step"] == f"{DESCRIPTOR.range_step_seconds}s"
        for parameters in range_queries
    )


def empty_api_reads(telemetry: dict[str, Any], repetition: int) -> dict[str, Any]:
    """The API's labelled counters answering with no series before one run."""
    for entry in telemetry["instants"]:
        if (
            entry["repetition"] == repetition
            and entry["position"] == "before"
            and entry["seriesId"].startswith("api-")
        ):
            entry["rows"] = []
    return telemetry


def test_an_absent_api_counter_before_the_first_run_is_read_as_zero_and_says_so(
    scenario: Scenario,
) -> None:
    """What the second real attempt showed: before any request, the series is absent."""
    record = scenario.build(
        telemetry_text=dumps(empty_api_reads(scenario.make_telemetry(), 1))
    )
    assert record["usable"] is True
    first = {item["checkId"]: item for item in record["runs"][0]["reconciliation"]}
    assert first["api-requests-equal-dispatched"]["absentBeforeReadAsZero"] is True
    assert first["api-requests-equal-dispatched"]["before"] == 0
    assert (
        first["runtime-output-tokens-equal-recorded"]["absentBeforeReadAsZero"] is False
    )


def test_an_absent_counter_before_a_later_run_is_not_read_as_zero(
    scenario: Scenario,
) -> None:
    record = scenario.build(
        telemetry_text=dumps(empty_api_reads(scenario.make_telemetry(), 2))
    )
    assert check(record, "counters-reconcile-with-raw-records")["passed"] is False
    second = record["runs"][1]["reconciliation"][0]
    assert second["absentBeforeReadAsZero"] is False
    assert second["increase"] is None


def test_an_absent_counter_is_not_read_as_zero_when_a_pod_was_replaced(
    scenario: Scenario,
) -> None:
    environment = copy.deepcopy(scenario.environment)
    environment["podsAfter"][0]["uid"] = "u-api-replacement"
    record = scenario.build(
        environment_text=dumps(environment),
        telemetry_text=dumps(empty_api_reads(scenario.make_telemetry(), 1)),
    )
    assert record["runs"][0]["reconciliation"][0]["absentBeforeReadAsZero"] is False
    assert check(record, "counters-reconcile-with-raw-records")["passed"] is False


def test_the_collector_is_asked_by_get_without_parameters_and_by_post_with_them() -> (
    None
):
    """Prometheus answers a POST to a status endpoint with an empty 405.

    The second real attempt met exactly that, after both load runs had completed.
    """
    seen: list[tuple[str, str]] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def answer(self) -> None:
            seen.append((self.command, self.path))
            if self.command == "POST" and self.path.startswith("/api/v1/status"):
                self.send_response(405)
                self.end_headers()
                return
            body = json.dumps(
                {"status": "success", "data": {"version": "3.5.0"}}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = answer
        do_POST = answer

        def log_message(self, *_: Any) -> None:
            return None

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ask = live.http_asker(f"http://127.0.0.1:{server.server_address[1]}")
        assert ask("/api/v1/status/buildinfo", {})["status"] == "success"
        assert ask("/api/v1/query", {"query": "up"})["status"] == "success"
    finally:
        server.shutdown()
        server.server_close()
    assert seen == [("GET", "/api/v1/status/buildinfo"), ("POST", "/api/v1/query")]


def test_a_refused_range_query_is_recorded_as_refused_not_as_empty() -> None:
    assert (
        live._range_result({"status": "error", "error": "bad"})["status"] == "refused"
    )
    with pytest.raises(ScenarioError, match="matrix"):
        live._range_result(
            {"status": "success", "data": {"resultType": "vector", "result": []}}
        )


# --------------------------------------------------------------------------
# The load tool's millisecond origin
# --------------------------------------------------------------------------


def test_the_load_run_records_the_epoch_millisecond_of_its_offset_origin(
    scenario: Scenario,
) -> None:
    header = json.loads(scenario.raws["run-1-raw.jsonl"].splitlines()[0])
    assert header["startedAtEpochMs"] == scenario.origins[0]


def test_a_raw_set_written_before_the_origin_existed_still_reads() -> None:
    rehearsal = REPO_ROOT / "docs/proof/serving/v1-s4-003-pr1-rehearsal-raw.jsonl"
    assert (
        "startedAtEpochMs" not in rehearsal.read_text(encoding="utf-8").splitlines()[0]
    )
    load.read_raw(rehearsal)


@pytest.mark.parametrize("value", ["1800000000000", 0, True, 1.5])
def test_an_unusable_origin_is_refused(scenario: Scenario, value: Any) -> None:
    lines = scenario.raws["run-1-raw.jsonl"].splitlines()
    header = json.loads(lines[0])
    header["startedAtEpochMs"] = value
    with pytest.raises(load.LoadError):
        load.parse_raw("\n".join([json.dumps(header), *lines[1:]]) + "\n")


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def test_check_and_fields_read_committed_files_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["check"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "saturation not judged" in out
    assert cli.main(["fields", "release.apiDeploymentName"]) == cli.EXIT_OK
    assert capsys.readouterr().out.strip() == "inferops-inferops-llm"


def test_a_command_without_its_inputs_is_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for argv in (["fields"], ["facts"], ["record"], ["telemetry"], ["verify"]):
        assert cli.main(argv) == cli.EXIT_REFUSED, argv
    capsys.readouterr()


def test_the_record_command_builds_from_a_run_directory(
    tmp_path: Path, scenario: Scenario, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = tmp_path / "run"
    write_cluster(run_dir)
    (run_dir / "load").mkdir()
    for name, text in scenario.raws.items():
        (run_dir / "load" / name).write_text(text, encoding="utf-8")
    (run_dir / "windows.json").write_text(dumps(scenario.windows), encoding="utf-8")
    start = scenario.windows["idleBaseline"]["startEpochMs"] - 1000
    (run_dir / "resource-samples.txt").write_text(
        synthetic_samples(start, scenario.windows["settledEpochMs"]), encoding="utf-8"
    )
    (run_dir / "telemetry.json").write_text(dumps(scenario.telemetry), encoding="utf-8")
    assert cli.main(["record", "--run-dir", str(run_dir)]) == cli.EXIT_OK
    assert "usable       True" in capsys.readouterr().out
    out = run_dir / "record"
    assert cli.main(["verify", "--dir", str(out)]) == cli.EXIT_OK
    record = json.loads(
        (out / "performance-record.v1alpha1.json").read_text(encoding="utf-8")
    )
    record["usable"] = False
    (out / "performance-record.v1alpha1.json").write_text(
        dumps(record), encoding="utf-8"
    )
    assert cli.main(["verify", "--dir", str(out)]) == cli.EXIT_FAILED
    capsys.readouterr()


# --------------------------------------------------------------------------
# The script
# --------------------------------------------------------------------------


SCRIPT_TEXT = SCRIPT.read_text(encoding="utf-8")


def test_the_script_verifies_the_target_before_any_mutation() -> None:
    resolve = SCRIPT_TEXT.index("inferops::resolve_target")
    for mutation in (
        'terraform-prerequisites.sh" apply',
        "inferops::target_helm install",
        "port-forward",
    ):
        assert resolve < SCRIPT_TEXT.index(mutation), mutation


def test_the_script_refuses_without_confirmation_and_values_before_contacting_anything() -> (
    None
):
    confirmation = SCRIPT_TEXT.index("run needs --confirm-real-kubernetes")
    assert confirmation < SCRIPT_TEXT.index("inferops::resolve_target")
    assert SCRIPT_TEXT.index("--values is required") < SCRIPT_TEXT.index(
        "inferops::resolve_target"
    )


def test_the_script_never_removes_what_outlives_a_release() -> None:
    code = [
        line for line in SCRIPT_TEXT.splitlines() if not line.lstrip().startswith("#")
    ]
    body = "\n".join(code)
    assert 'terraform-prerequisites.sh" destroy' not in body
    assert "delete pvc" not in body and "delete namespace" not in body
    assert "--create-namespace" not in body
    assert body.count("inferops::target_helm uninstall") == 1


def test_the_sampler_only_reads_inside_the_node() -> None:
    start = SCRIPT_TEXT.index("readonly SAMPLE_SCRIPT='")
    end = SCRIPT_TEXT.index("\n'\n", start)
    sampler = SCRIPT_TEXT[start:end]
    for writer in (">/sys", "> /sys", "echo ", "tee ", "rm ", "kill ", "mkdir"):
        assert writer not in sampler, writer
    assert "cat " in sampler


def test_the_forwards_bind_loopback_and_the_run_dir_is_never_overwritten() -> None:
    assert '--address "${forward_host}"' in SCRIPT_TEXT
    assert '[ "${forward_host}" = "127.0.0.1" ]' in SCRIPT_TEXT
    assert "already exists. Move it aside" in SCRIPT_TEXT


# --------------------------------------------------------------------------
# Committed evidence
# --------------------------------------------------------------------------


committed = pytest.mark.skipif(
    not COMMITTED_RECORD.exists(), reason="no committed performance record"
)


@committed
def test_the_committed_record_regenerates_from_its_committed_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        cli.main(["verify", "--dir", str(PROOF_DIR), "--prefix", PROOF_PREFIX])
        == cli.EXIT_OK
    )
    capsys.readouterr()


@committed
def test_the_committed_record_is_labelled_and_bounded() -> None:
    record = json.loads(COMMITTED_RECORD.read_text(encoding="utf-8"))
    assert record["evidenceClass"] == "local-real-cpu"
    assert record["productionBenchmark"] is False
    assert record["portableCapacityClaim"] is False
    assert record["saturationJudged"] is False
    assert record["environment"]["provider"] == "docker-desktop"
    assert len(record["runs"]) == DESCRIPTOR.repetitions
    for run in record["runs"]:
        assert [phase["scenarioId"] for phase in run["phases"]] == [
            s.scenario_id for s in DESCRIPTOR.scenarios
        ]


@committed
def test_no_committed_input_carries_generated_text_or_a_private_value() -> None:
    for path in sorted(PROOF_DIR.glob(f"{PROOF_PREFIX}*")):
        if path.suffix not in (".json", ".jsonl"):
            continue
        text = path.read_text(encoding="utf-8")
        refuse_private(text, path.name)
        assert PROFILE.fixture.messages[0]["content"] not in text, path.name
        assert '"content"' not in text, path.name


@committed
def test_the_validation_record_quotes_the_committed_record_faithfully() -> None:
    record = json.loads(COMMITTED_RECORD.read_text(encoding="utf-8"))
    text = VALIDATION_RECORD.read_text(encoding="utf-8")
    assert record["descriptorSha256"] in text
    for run in record["runs"]:
        assert run["runId"] in text
        for phase in run["phases"]:
            latency = phase["load"]["latencyOfSuccesses"]
            if phase["scenarioId"] != "warmup" and latency["p50Ms"] is not None:
                assert (
                    f"{latency['p50Ms']:,}".replace(",", " ") in text
                    or str(latency["p50Ms"]) in text
                ), (
                    run["repetition"],
                    phase["scenarioId"],
                )


def test_the_procedure_and_decision_name_the_boundary() -> None:
    procedure = PROCEDURE.read_text(encoding="utf-8")
    decision = DECISION.read_text(encoding="utf-8")
    for text in (procedure, decision):
        assert "portable capacity" in text
        assert "benchmark" in text
    assert "scripts/environment/performance-scenarios.sh" in procedure
    assert "sustained-throughput-and-capacity-under-load" in decision
