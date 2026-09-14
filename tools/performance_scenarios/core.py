"""The performance scenario matrix: what it runs, what it reads, and what it records.

`scripts/environment/performance-scenarios.sh` owns every contact with the cluster:
it verifies the target, installs the release, dumps what the cluster reports, reads
the node's resource counters, runs the load, and removes the release. This module
owns everything that can be decided without a cluster:

- the **descriptor** -- the committed scenario matrix, checked against the load
  profile it pins by digest, the chart's collector pacing, and ceilings kept here;
- the **environment** -- the fields a record keeps out of the cluster's own JSON, and
  the load facts file derived from the same JSON rather than typed by an operator;
- the **resource samples** -- one line per node read, parsed into integers;
- the **record** -- a pure function of the committed inputs. It places every load
  phase against the resource samples and the collector's counters, checks that the
  environment stayed the one it started as, and lists what it saw for later analysis.

It judges no saturation. A level's latency and a tier's CPU are placed side by side
and nothing here says what they mean together.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from tools.llm_load import core as load

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR_PATH = (
    REPO_ROOT / "deploy" / "serving" / "experiments" / "performance-scenarios.v1.json"
)

EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_EXPERIMENT_ID = "inferops-performance-scenarios"
EXPECTED_EVIDENCE_CLASS = "local-real-cpu"
EXPECTED_EVIDENCE_LABEL = "local real Kubernetes"
EXPECTED_CEILING = "C2"
EXPECTED_LANE = "real-runtime"
EXPECTED_LOAD_MODULE = "tools.llm_load"
EXPECTED_RESOURCE_SOURCE = "node-cgroup-v1"
EXPECTED_TIERS = ("virtual-machine", "node", "release-pods")
RECORD_SCHEMA = "inferops.io/v1alpha1"
RECORD_KIND = "inferops-performance-scenarios-record"

#: The runtime counter whose zero shows nothing was decoded before the first run.
RUNTIME_TOKENS_SERIES = "runtime-tokens-predicted"

#: The release tiers a sample reads, by the component label the chart gives them.
ROLE_COMPONENTS: dict[str, str] = {
    "api": "platform-api",
    "runtime": "serving-runtime",
    "collector": "telemetry-collector",
}
ROLES: tuple[str, ...] = tuple(ROLE_COMPONENTS)

#: The configuration keys a record keeps. Everything else in the ConfigMap stays in
#: the cluster: the record names what shapes a measurement, not the whole release.
CONFIGURATION_KEYS: tuple[str, ...] = (
    "INFEROPS_SERVING_ADAPTER",
    "INFEROPS_REQUEST_TIMEOUT_MS",
    "INFEROPS_MAX_OUTPUT_TOKENS",
    "INFEROPS_MODEL_IDENTIFIER",
    "INFEROPS_MODEL_REVISION",
    "INFEROPS_RUNTIME_IMAGE_DIGEST",
    "INFEROPS_LLAMA_SERVER_CONTEXT_SIZE",
    "INFEROPS_LLAMA_SERVER_THREADS",
    "INFEROPS_LLAMA_SERVER_METRICS_ENABLED",
)

#: The files whose content decides what a run did. Their digests are recorded at run
#: time, so a record can say which code produced it even from an uncommitted tree.
EXECUTED_FILES: tuple[str, ...] = (
    "deploy/serving/experiments/performance-scenarios.v1.json",
    "deploy/serving/load/llm-load-profile.v1.json",
    "scripts/environment/performance-scenarios.sh",
    "scripts/environment/lib.sh",
    "tools/llm_load/core.py",
    "tools/llm_load/__main__.py",
    "tools/performance_scenarios/core.py",
    "tools/performance_scenarios/live.py",
    "tools/performance_scenarios/__main__.py",
    "charts/inferops-llm/Chart.yaml",
    "charts/inferops-llm/values.yaml",
    "charts/inferops-llm/ci/real-values.yaml",
)

# Ceilings kept in code, for the reason tools.llm_load keeps its own: a heavier run
# must not be authorizable by editing the record that is supposed to bound it.
MAXIMUM_REPETITIONS = 3
MAXIMUM_IDLE_SECONDS = 600
MINIMUM_IDLE_SECONDS = 30
MAXIMUM_SETTLE_SECONDS = 600
MINIMUM_SAMPLE_INTERVAL_MS = 1000
MAXIMUM_SAMPLE_INTERVAL_MS = 10_000
MAXIMUM_TOTAL_SECONDS = 7200
MAXIMUM_SERIES = 20

DNS_LABEL = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
SERIES_ID = re.compile(r"[a-z][a-z0-9-]{1,62}")
DOTTED_PATH = re.compile(r"[A-Za-z][A-Za-z0-9]*(\.[A-Za-z][A-Za-z0-9]*)*")
CGROUP_TOKEN = re.compile(r"(?P<role>[a-z]+)=(?P<values>[0-9a-z,]+)")

#: What a committed record may not carry: a host filesystem path, a user directory,
#: or an address other than loopback and the any-address a container binds.
PRIVATE_SHAPES = (
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"),
    re.compile(r"[\\/](Users|home)[\\/]", re.IGNORECASE),
    re.compile(
        r"(?<![0-9.])(?!127\.0\.0\.1(?![0-9]))(?!0\.0\.0\.0(?![0-9]))"
        # Not followed by a hyphen and a letter: a kernel release such as
        # 5.15.146.1-microsoft-standard-WSL2 has four dotted numbers and is no address.
        r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])(?!-[A-Za-z])"
    ),
)


class ScenarioError(RuntimeError):
    """The scenario matrix, its evidence, or its record is not what it must be."""


class ScenarioRefused(ScenarioError):
    """A precondition refused before anything was recorded as a result."""


# --------------------------------------------------------------------------
# Small readers
# --------------------------------------------------------------------------


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScenarioError(f"'{field}' must be an object")
    return cast(dict[str, Any], value)


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ScenarioError(f"'{field}' must be a list")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScenarioError(f"'{field}' must be a non-empty string")
    return value


def _integer(
    value: Any, field: str, *, minimum: int = 0, maximum: int | None = None
) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ScenarioError(f"'{field}' must be an integer of at least {minimum}")
    if maximum is not None and value > maximum:
        raise ScenarioError(f"'{field}' must be at most {maximum}")
    return value


def _true(value: Any, field: str) -> None:
    if value is not True:
        raise ScenarioError(f"'{field}' must be true")


def _false(value: Any, field: str) -> None:
    if value is not False:
        raise ScenarioError(f"'{field}' must be false")


def _read_json_text(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ScenarioError(f"the {what} is not valid JSON") from error


def read_json(path: Path, what: str) -> Any:
    """A JSON file, or a named refusal instead of a traceback."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ScenarioError(f"the {what} is unreadable") from error
    return _read_json_text(text, what)


def text_digest(text: str) -> str:
    """The SHA-256 of text with line endings normalized to LF."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    """The SHA-256 of a file's bytes with line endings normalized to LF."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ScenarioError(f"'{path.name}' is unreadable") from error
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def dumps(document: Any) -> str:
    """The one serialization every committed JSON document here uses."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def refuse_private(text: str, what: str) -> None:
    """Refuse a document that carries a host path, a user directory, or an address."""
    for shape in PRIVATE_SHAPES:
        match = shape.search(text)
        if match is not None:
            raise ScenarioRefused(
                f"the {what} carries a value shaped like a host path, a user "
                f"directory, or a network address ('{match.group(0)}'); a committed "
                "record may not"
            )


# --------------------------------------------------------------------------
# The descriptor
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    role: str
    load_phase: str
    concurrency: int


@dataclass(frozen=True, slots=True)
class Reconciliation:
    check_id: str
    series_id: str
    compare_with: str
    label: str | None
    label_value: str | None


@dataclass(frozen=True, slots=True)
class Descriptor:
    """The validated descriptor, and the document it was read from."""

    document: dict[str, Any]
    sha256: str
    scenarios: tuple[Scenario, ...]
    repetitions: int
    idle_seconds: int
    settle_between_seconds: int
    settle_after_seconds: int
    sample_interval_ms: int
    maximum_gap_ms: int
    minimum_samples: int
    scrape_interval_seconds: int
    range_step_seconds: int
    series: tuple[tuple[str, str], ...]
    reconciliation: tuple[Reconciliation, ...]
    profile: load.Profile

    @property
    def series_expressions(self) -> dict[str, str]:
        return dict(self.series)


def _chart_scrape_interval(repo_root: Path) -> int:
    merged: dict[str, Any] = {}
    for relative in (
        "charts/inferops-llm/values.yaml",
        "charts/inferops-llm/ci/real-values.yaml",
    ):
        try:
            loaded = yaml.safe_load((repo_root / relative).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            raise ScenarioError(f"'{relative}' is unreadable") from error
        telemetry = _object(loaded or {}, relative).get("telemetry")
        if isinstance(telemetry, dict):
            collection = telemetry.get("collection")
            if isinstance(collection, dict) and "scrapeIntervalSeconds" in collection:
                merged["interval"] = collection["scrapeIntervalSeconds"]
    return _integer(
        merged.get("interval"), "telemetry.collection.scrapeIntervalSeconds", minimum=1
    )


def validate_descriptor(
    document: Mapping[str, Any],
    *,
    sha256: str,
    repo_root: Path = REPO_ROOT,
    profile: load.Profile | None = None,
) -> Descriptor:
    """Refuse a scenario matrix that drifted from what it pins or exceeds its ceilings."""
    record = dict(document)
    if record.get("schemaVersion") != EXPECTED_SCHEMA:
        raise ScenarioError("the descriptor has an unsupported schema")
    if record.get("experimentId") != EXPECTED_EXPERIMENT_ID:
        raise ScenarioError("the descriptor names another experiment")
    _string(record.get("experimentVersion"), "experimentVersion")
    if (
        record.get("evidenceClass") != EXPECTED_EVIDENCE_CLASS
        or record.get("evidenceLabel") != EXPECTED_EVIDENCE_LABEL
        or record.get("certificationCeiling") != EXPECTED_CEILING
    ):
        raise ScenarioError(
            "the descriptor carries the wrong evidence class, label, or ceiling"
        )
    if record.get("lane") != EXPECTED_LANE:
        raise ScenarioError("the descriptor must run in the real-runtime lane")
    _false(record.get("productionBenchmark"), "productionBenchmark")
    _false(record.get("portableCapacityClaim"), "portableCapacityClaim")
    boundary = _string(record.get("boundary"), "boundary")
    for phrase in ("portable capacity", "production SLO", "benchmark"):
        if phrase not in boundary:
            raise ScenarioError(
                f"the descriptor's boundary no longer refuses '{phrase}'"
            )
    for reference in ("decisionRef", "procedureRef", "chartRef"):
        if not (repo_root / _string(record.get(reference), reference)).exists():
            raise ScenarioError(
                f"the descriptor's '{reference}' names nothing committed"
            )

    loaded_profile = (
        profile if profile is not None else load.load_profile(repo_root=repo_root)
    )
    load_section = _object(record.get("load"), "load")
    profile_ref = _string(load_section.get("profileRef"), "load.profileRef")
    if load.profile_digest(repo_root / profile_ref) != load_section.get(
        "profileSha256"
    ):
        raise ScenarioError(
            "the descriptor pins a load profile digest the profile no longer has"
        )
    if loaded_profile.profile_sha256 != load_section.get("profileSha256"):
        raise ScenarioError(
            "the descriptor pins a load profile other than the loaded one"
        )
    if load_section.get("module") != EXPECTED_LOAD_MODULE:
        raise ScenarioError(
            "the descriptor names a load module other than tools.llm_load"
        )

    supported = load.supported_providers(repo_root)
    providers = _list(
        _object(record.get("cluster"), "cluster").get("providers"), "cluster.providers"
    )
    if not providers:
        raise ScenarioError("the descriptor describes no provider")
    for entry in providers:
        provider = _object(entry, "cluster.providers[]")
        if provider.get("providerId") not in supported:
            raise ScenarioError(
                "the descriptor describes a provider the contract does not publish"
            )
        _string(provider.get("name"), "providers[].name")
        _string(provider.get("context"), "providers[].context")
    if "docker-desktop" not in {
        _object(entry, "providers[]").get("providerId") for entry in providers
    }:
        raise ScenarioError(
            "the descriptor does not describe the V1 reference provider"
        )

    release = _object(record.get("release"), "release")
    for name in (
        "name",
        "apiServiceName",
        "apiDeploymentName",
        "runtimeDeploymentName",
        "collectorServiceName",
        "collectorDeploymentName",
        "configMapName",
    ):
        if DNS_LABEL.fullmatch(_string(release.get(name), f"release.{name}")) is None:
            raise ScenarioError(f"'release.{name}' is not a Kubernetes name")
    if not _string(release.get("namespace"), "release.namespace").startswith(
        "inferops-"
    ):
        raise ScenarioError("the release namespace must carry the inferops- prefix")
    for port in ("apiServicePort", "collectorServicePort"):
        _integer(release.get(port), f"release.{port}", minimum=1, maximum=65535)
    for replicas in ("apiReplicas", "runtimeReplicas"):
        if release.get(replicas) != 1:
            raise ScenarioError(
                f"'release.{replicas}' must be 1; the forward reaches one pod and a record "
                "of more replicas would say nothing about them"
            )

    scenarios = tuple(
        Scenario(
            scenario_id=_string(
                _object(entry, "scenarios[]").get("scenarioId"), "scenarioId"
            ),
            role=_string(entry.get("role"), "role"),
            load_phase=_string(entry.get("loadPhase"), "loadPhase"),
            concurrency=_integer(entry.get("concurrency"), "concurrency", minimum=1),
        )
        for entry in _list(record.get("scenarios"), "scenarios")
    )
    expected = [("warmup", load.PHASE_WARMUP, loaded_profile.warmup_concurrency)] + [
        (level.level_id, load.PHASE_MEASURED, level.concurrency)
        for level in loaded_profile.levels
    ]
    if [(s.scenario_id, s.load_phase, s.concurrency) for s in scenarios] != expected:
        raise ScenarioError(
            "the scenarios must be the load profile's warm-up and levels, in order, with "
            "the same concurrency"
        )
    if scenarios[0].role != "warm-up":
        raise ScenarioError("the first scenario must be the warm-up")
    measured = scenarios[1:]
    if not measured or measured[0].role != "baseline":
        raise ScenarioError("the first measured scenario must be the baseline")
    if any(s.role != "higher-load" for s in measured[1:]) or len(measured) < 2:
        raise ScenarioError(
            "every measured scenario after the baseline must be higher-load"
        )
    if any(
        later.concurrency <= earlier.concurrency
        for earlier, later in itertools.pairwise(measured)
    ):
        raise ScenarioError("each higher-load scenario must raise the concurrency")

    schedule = _object(record.get("schedule"), "schedule")
    repetitions = _integer(
        schedule.get("repetitions"),
        "schedule.repetitions",
        minimum=1,
        maximum=MAXIMUM_REPETITIONS,
    )
    idle = _integer(
        schedule.get("idleBaselineSeconds"),
        "schedule.idleBaselineSeconds",
        minimum=MINIMUM_IDLE_SECONDS,
        maximum=MAXIMUM_IDLE_SECONDS,
    )
    telemetry = _object(record.get("telemetry"), "telemetry")
    scrape = _integer(
        telemetry.get("scrapeIntervalSeconds"),
        "telemetry.scrapeIntervalSeconds",
        minimum=1,
    )
    if scrape != _chart_scrape_interval(repo_root):
        raise ScenarioError("the descriptor's scrape interval is not the chart's")
    settle_floor = 2 * scrape
    between = _integer(
        schedule.get("settleBetweenRunsSeconds"),
        "schedule.settleBetweenRunsSeconds",
        minimum=settle_floor,
        maximum=MAXIMUM_SETTLE_SECONDS,
    )
    after = _integer(
        schedule.get("settleAfterLastRunSeconds"),
        "schedule.settleAfterLastRunSeconds",
        minimum=settle_floor,
        maximum=MAXIMUM_SETTLE_SECONDS,
    )
    total = (
        idle
        + repetitions * loaded_profile.worst_case_seconds()
        + (repetitions - 1) * between
        + after
    )
    if total > MAXIMUM_TOTAL_SECONDS:
        raise ScenarioError(
            f"the schedule's worst case is {total} s, above the {MAXIMUM_TOTAL_SECONDS} s ceiling"
        )

    stability = _object(record.get("stability"), "stability")
    for flag in (
        "requireEveryDeploymentAvailable",
        "requireZeroContainerRestarts",
        "requireSamePodsThroughout",
        "requireCompletedLoadRuns",
    ):
        _true(stability.get(flag), f"stability.{flag}")
    _false(stability.get("cpuThresholdApplied"), "stability.cpuThresholdApplied")

    resources = _object(record.get("resources"), "resources")
    if resources.get("source") != EXPECTED_RESOURCE_SOURCE:
        raise ScenarioError(
            "the descriptor names a resource source this module does not parse"
        )
    interval = _integer(
        resources.get("sampleIntervalMs"),
        "resources.sampleIntervalMs",
        minimum=MINIMUM_SAMPLE_INTERVAL_MS,
        maximum=MAXIMUM_SAMPLE_INTERVAL_MS,
    )
    gap = _integer(
        resources.get("maximumGapMs"), "resources.maximumGapMs", minimum=2 * interval
    )
    minimum_samples = _integer(
        resources.get("minimumSamplesPerPhase"),
        "resources.minimumSamplesPerPhase",
        minimum=2,
    )
    if tuple(_list(resources.get("tiers"), "resources.tiers")) != EXPECTED_TIERS:
        raise ScenarioError("the descriptor's resource tiers are not the ones sampled")

    step = _integer(
        telemetry.get("rangeStepSeconds"),
        "telemetry.rangeStepSeconds",
        minimum=1,
        maximum=scrape,
    )
    series_entries = _list(telemetry.get("series"), "telemetry.series")
    if not series_entries or len(series_entries) > MAXIMUM_SERIES:
        raise ScenarioError(
            f"the descriptor must name between 1 and {MAXIMUM_SERIES} series"
        )
    series: list[tuple[str, str]] = []
    for entry in series_entries:
        item = _object(entry, "telemetry.series[]")
        series_id = _string(item.get("seriesId"), "seriesId")
        expression = _string(item.get("expr"), "expr")
        if SERIES_ID.fullmatch(series_id) is None:
            raise ScenarioError(f"series id '{series_id}' is not a plain identifier")
        # Aggregated, so that a reading never carries a per-target label such as a
        # pod address. What a sum drops is what a committed record must not hold.
        if not expression.startswith("sum"):
            raise ScenarioError(
                f"series '{series_id}' must be an explicit sum aggregation"
            )
        series.append((series_id, expression))
    if len({series_id for series_id, _ in series}) != len(series):
        raise ScenarioError("the descriptor names a series id twice")
    known = {series_id for series_id, _ in series}
    checks: list[Reconciliation] = []
    for entry in _list(telemetry.get("reconciliation"), "telemetry.reconciliation"):
        item = _object(entry, "telemetry.reconciliation[]")
        check = Reconciliation(
            check_id=_string(item.get("checkId"), "checkId"),
            series_id=_string(item.get("seriesId"), "seriesId"),
            compare_with=_string(item.get("compareWith"), "compareWith"),
            label=item.get("label"),
            label_value=item.get("labelValue"),
        )
        if check.series_id not in known:
            raise ScenarioError(
                f"reconciliation '{check.check_id}' names an unknown series"
            )
        if check.compare_with not in ("dispatched", "output-tokens"):
            raise ScenarioError(
                f"reconciliation '{check.check_id}' compares with nothing recorded"
            )
        if (check.label is None) != (check.label_value is None):
            raise ScenarioError(
                f"reconciliation '{check.check_id}' names half a label filter"
            )
        checks.append(check)
    if telemetry.get("dashboardCaptureAt") != "each-phase-end":
        raise ScenarioError(
            "the descriptor must capture the dashboard at each phase end"
        )

    readiness = _object(record.get("readiness"), "readiness")
    for budget in (
        "runtimeRolloutBudgetMs",
        "apiRolloutBudgetMs",
        "collectorRolloutBudgetMs",
        "forwardBudgetMs",
        "uninstallBudgetMs",
    ):
        _integer(
            readiness.get(budget),
            f"readiness.{budget}",
            minimum=1000,
            maximum=1_800_000,
        )

    forwards = _object(record.get("forwards"), "forwards")
    if forwards.get("host") != "127.0.0.1":
        raise ScenarioError(
            "every forward must bind 127.0.0.1; the API behind it is unauthenticated"
        )
    api_port = _integer(
        forwards.get("apiPort"), "forwards.apiPort", minimum=1024, maximum=65535
    )
    collector_port = _integer(
        forwards.get("collectorPort"),
        "forwards.collectorPort",
        minimum=1024,
        maximum=65535,
    )
    if api_port == collector_port:
        raise ScenarioError("the two forwards must use different ports")

    evidence = _object(record.get("evidence"), "evidence")
    if not _string(evidence.get("directory"), "evidence.directory").startswith(
        ".cache/inferops/experiments/"
    ):
        raise ScenarioError(
            "run evidence must be written under .cache/inferops/experiments/"
        )
    for name in (
        "environmentFile",
        "windowsFile",
        "samplesFile",
        "telemetryFile",
        "recordDirectory",
    ):
        if "/" in _string(evidence.get(name), f"evidence.{name}"):
            raise ScenarioError(f"'evidence.{name}' must be a plain file name")
    _false(evidence.get("retainGeneratedText"), "evidence.retainGeneratedText")

    cleanup = _object(record.get("cleanup"), "cleanup")
    _true(cleanup.get("uninstallsRelease"), "cleanup.uninstallsRelease")
    for flag in ("removesPrerequisites", "removesCluster", "removesModelCacheClaim"):
        _false(cleanup.get(flag), f"cleanup.{flag}")
    if not _list(record.get("limitations"), "limitations"):
        raise ScenarioError("the descriptor must state its limitations")

    return Descriptor(
        document=dict(record),
        sha256=sha256,
        scenarios=scenarios,
        repetitions=repetitions,
        idle_seconds=idle,
        settle_between_seconds=between,
        settle_after_seconds=after,
        sample_interval_ms=interval,
        maximum_gap_ms=gap,
        minimum_samples=minimum_samples,
        scrape_interval_seconds=scrape,
        range_step_seconds=step,
        series=tuple(series),
        reconciliation=tuple(checks),
        profile=loaded_profile,
    )


def load_descriptor(
    path: Path = DESCRIPTOR_PATH, *, repo_root: Path = REPO_ROOT
) -> Descriptor:
    """Load and validate the committed descriptor without contacting anything."""
    return validate_descriptor(
        _object(read_json(path, "performance scenario descriptor"), "root"),
        sha256=file_digest(path),
        repo_root=repo_root,
    )


def descriptor_fields(descriptor: Descriptor, paths: Sequence[str]) -> list[str]:
    """Scalar descriptor values by dotted path, for the shell workflow to read."""
    values: list[str] = []
    for path in paths:
        if DOTTED_PATH.fullmatch(path) is None:
            raise ScenarioError(f"'{path}' is not a dotted descriptor path")
        cursor: Any = descriptor.document
        for member in path.split("."):
            if not isinstance(cursor, dict) or member not in cursor:
                raise ScenarioError(f"the descriptor has no '{path}'")
            cursor = cursor[member]
        if isinstance(cursor, bool) or not isinstance(cursor, str | int):
            raise ScenarioError(f"'{path}' is not a scalar string or integer")
        values.append(str(cursor))
    return values


# --------------------------------------------------------------------------
# What the cluster reported
# --------------------------------------------------------------------------


def _cluster_json(cluster_dir: Path, name: str) -> Any:
    return read_json(cluster_dir / name, f"cluster reading '{name}'")


def _items(document: Any, what: str) -> list[dict[str, Any]]:
    return [
        _object(item, f"{what}.items[]")
        for item in _list(_object(document, what).get("items"), f"{what}.items")
    ]


def _component(item: Mapping[str, Any]) -> str | None:
    labels = _object(item.get("metadata"), "metadata").get("labels") or {}
    value = (
        labels.get("app.kubernetes.io/component") if isinstance(labels, dict) else None
    )
    return value if isinstance(value, str) else None


def _role_of(item: Mapping[str, Any]) -> str | None:
    component = _component(item)
    for role, expected in ROLE_COMPONENTS.items():
        if component == expected:
            return role
    return None


def _pods(document: Any) -> list[dict[str, Any]]:
    """The release's running tier pods, one entry each, ordered by role."""
    pods: list[dict[str, Any]] = []
    for item in _items(document, "pods"):
        role = _role_of(item)
        status = _object(item.get("status"), "pod.status")
        if role is None or status.get("phase") != "Running":
            continue
        statuses = [
            _object(entry, "containerStatuses[]")
            for entry in status.get("containerStatuses") or []
        ]
        metadata = _object(item.get("metadata"), "pod.metadata")
        pods.append(
            {
                "role": role,
                "name": _string(metadata.get("name"), "pod.name"),
                "uid": _string(metadata.get("uid"), "pod.uid"),
                "ready": bool(statuses)
                and all(entry.get("ready") is True for entry in statuses),
                "restartCount": sum(
                    _integer(entry.get("restartCount"), "restartCount")
                    for entry in statuses
                ),
                "imageIds": sorted(
                    _string(entry.get("imageID"), "imageID") for entry in statuses
                ),
            }
        )
    roles = [pod["role"] for pod in pods]
    for role in ROLES:
        if roles.count(role) != 1:
            raise ScenarioRefused(
                f"the release has {roles.count(role)} running '{role}' pod(s); this "
                "experiment is defined for exactly one of each"
            )
    return sorted(pods, key=lambda pod: ROLES.index(pod["role"]))


def _containers(deployment: Mapping[str, Any]) -> list[dict[str, Any]]:
    spec = _object(
        _object(
            _object(deployment.get("spec"), "spec").get("template"), "template"
        ).get("spec"),
        "podSpec",
    )
    containers = []
    for entry in _list(spec.get("containers"), "containers"):
        container = _object(entry, "containers[]")
        resources = container.get("resources") or {}
        containers.append(
            {
                "name": _string(container.get("name"), "container.name"),
                "image": _string(container.get("image"), "container.image"),
                "resources": {
                    "requests": dict(sorted((resources.get("requests") or {}).items())),
                    "limits": dict(sorted((resources.get("limits") or {}).items())),
                },
                "args": [str(argument) for argument in container.get("args") or []],
            }
        )
    return containers


def _workloads(document: Any, descriptor: Descriptor) -> dict[str, Any]:
    release = descriptor.document["release"]
    names = {
        "api": release["apiDeploymentName"],
        "runtime": release["runtimeDeploymentName"],
        "collector": release["collectorDeploymentName"],
    }
    by_name = {
        _object(item.get("metadata"), "metadata").get("name"): item
        for item in _items(document, "deployments")
    }
    workloads: dict[str, Any] = {}
    for role, name in names.items():
        if name not in by_name:
            raise ScenarioRefused(f"the release has no Deployment named '{name}'")
        deployment = by_name[name]
        status = deployment.get("status") or {}
        workloads[role] = {
            "deployment": name,
            "desiredReplicas": _integer(
                _object(deployment.get("spec"), "spec").get("replicas"), "replicas"
            ),
            "availableReplicas": int(status.get("availableReplicas") or 0),
            "containers": _containers(deployment),
        }
    return workloads


def _image_by_container(workloads: Mapping[str, Any], role: str, container: str) -> str:
    for entry in workloads[role]["containers"]:
        if entry["name"] == container:
            return str(entry["image"])
    raise ScenarioRefused(f"the {role} Deployment has no container named '{container}'")


#: The tiers whose image a record binds to the pod that ran it, and the file holding
#: the node container runtime's own description of each template reference.
IMAGE_RECORDS: dict[str, str] = {
    "api": "image-api.json",
    "runtime": "image-runtime.json",
}


def _resolved_image(
    cluster_dir: Path, pods: Sequence[Mapping[str, Any]], role: str, image: str
) -> dict[str, Any]:
    """Bind a tier's template reference to the image its pod actually runs.

    A pod's ``imageID`` is not enough on its own. The node's container runtime reports
    one repository digest for an image, and one image can carry several: the same API
    build imported twice under two OCI index digests is one image with two names, and
    the pod then reports whichever name came first. What binds the two is the node's
    own answer for the template reference -- the image it resolves to, and every
    digest that image carries. A pod whose ``imageID`` is not among them is refused.
    """
    if "@sha256:" not in image:
        raise ScenarioRefused(f"the {role} image is not pinned by digest")
    pod = next(pod for pod in pods if pod["role"] == role)
    status = _object(
        _object(_cluster_json(cluster_dir, IMAGE_RECORDS[role]), "image").get("status"),
        "image.status",
    )
    config_id = _string(status.get("id"), "image.status.id")
    repo_digests = sorted(
        _string(entry, "repoDigests[]")
        for entry in _list(status.get("repoDigests"), "image.status.repoDigests")
    )
    if image not in repo_digests:
        raise ScenarioRefused(
            f"the node resolves the {role} template reference to an image that does not "
            "carry that reference's digest"
        )
    if not set(pod["imageIds"]) & set(repo_digests):
        raise ScenarioRefused(
            f"the {role} pod reports a container image that is not the one its template "
            "reference resolves to"
        )
    return {
        "template": image,
        "podImageIds": list(pod["imageIds"]),
        "configId": config_id,
        "repoDigests": repo_digests,
    }


def extract_facts(cluster_dir: Path, descriptor: Descriptor) -> dict[str, Any]:
    """The load facts file, read out of the cluster's own answers rather than typed."""
    target = _object(_cluster_json(cluster_dir, "target.json"), "target")
    version = _object(_cluster_json(cluster_dir, "version.json"), "version")
    releases = _list(_cluster_json(cluster_dir, "helm-release.json"), "helm release")
    if len(releases) != 1:
        raise ScenarioRefused(
            "helm reports other than exactly one release under the expected name"
        )
    release = _object(releases[0], "helm release[]")
    workloads = _workloads(_cluster_json(cluster_dir, "deployments.json"), descriptor)
    pods = _pods(_cluster_json(cluster_dir, "pods-before.json"))
    configuration = _object(
        _object(_cluster_json(cluster_dir, "configmap.json"), "configmap").get("data"),
        "data",
    )
    repository = _object(_cluster_json(cluster_dir, "repository.json"), "repository")
    api_image = _image_by_container(workloads, "api", "api")
    runtime_image = _image_by_container(workloads, "runtime", "runtime")
    _resolved_image(cluster_dir, pods, "api", api_image)
    _resolved_image(cluster_dir, pods, "runtime", runtime_image)
    revision = str(release.get("revision", ""))
    if not revision.isdigit():
        raise ScenarioRefused("helm reports a release revision that is not a number")
    return {
        "provider": _string(target.get("provider"), "target.provider"),
        "kubernetesServerVersion": _string(
            _object(version.get("serverVersion"), "serverVersion").get("gitVersion"),
            "serverVersion.gitVersion",
        ),
        "chart": _string(release.get("chart"), "helm release chart"),
        "releaseRevision": int(revision),
        "apiImage": api_image,
        "runtimeImage": runtime_image,
        "modelRevision": _string(
            configuration.get("INFEROPS_MODEL_REVISION"), "INFEROPS_MODEL_REVISION"
        ),
        "apiReplicas": workloads["api"]["desiredReplicas"],
        "runtimeReplicas": workloads["runtime"]["desiredReplicas"],
        "repositoryRevision": _string(
            repository.get("revision"), "repository.revision"
        ),
    }


def executed_file_digests(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """The LF-normalized digest of every file that decides what a run does."""
    return {relative: file_digest(repo_root / relative) for relative in EXECUTED_FILES}


def extract_environment(cluster_dir: Path, descriptor: Descriptor) -> dict[str, Any]:
    """The environment a record keeps, and nothing else the cluster reported."""
    target = _object(_cluster_json(cluster_dir, "target.json"), "target")
    version = _object(_cluster_json(cluster_dir, "version.json"), "version")
    node = _object(_cluster_json(cluster_dir, "node.json"), "node")
    engine = _object(_cluster_json(cluster_dir, "engine.json"), "engine")
    releases = _list(_cluster_json(cluster_dir, "helm-release.json"), "helm release")
    repository = _object(_cluster_json(cluster_dir, "repository.json"), "repository")
    configuration = _object(
        _object(_cluster_json(cluster_dir, "configmap.json"), "configmap").get("data"),
        "data",
    )
    background = _items(_cluster_json(cluster_dir, "running-pods.json"), "running pods")
    namespace = descriptor.document["release"]["namespace"]
    node_status = _object(node.get("status"), "node.status")
    node_info = _object(node_status.get("nodeInfo"), "nodeInfo")
    outside = [
        item
        for item in background
        if _object(item.get("metadata"), "metadata").get("namespace") != namespace
    ]
    release = _object(releases[0], "helm release[]") if len(releases) == 1 else {}
    workloads = _workloads(_cluster_json(cluster_dir, "deployments.json"), descriptor)
    pods_before = _pods(_cluster_json(cluster_dir, "pods-before.json"))
    images = {
        role: _resolved_image(
            cluster_dir,
            pods_before,
            role,
            _image_by_container(workloads, role, role),
        )
        for role in IMAGE_RECORDS
    }
    environment = {
        "provider": _string(target.get("provider"), "target.provider"),
        "cluster": _string(target.get("cluster"), "target.cluster"),
        "context": _string(target.get("context"), "target.context"),
        "verifiedAt": _string(target.get("verifiedAt"), "target.verifiedAt"),
        "kubernetes": {
            "serverVersion": _object(version.get("serverVersion"), "serverVersion").get(
                "gitVersion"
            ),
            "kubectlVersion": _object(
                version.get("clientVersion"), "clientVersion"
            ).get("gitVersion"),
            "helmVersion": _string(target.get("helmVersion"), "target.helmVersion"),
        },
        "node": {
            "name": _object(node.get("metadata"), "node.metadata").get("name"),
            "imageDigest": target.get("nodeImageDigest") or None,
            "osImage": node_info.get("osImage"),
            "kernelVersion": node_info.get("kernelVersion"),
            "containerRuntimeVersion": node_info.get("containerRuntimeVersion"),
            "kubeletVersion": node_info.get("kubeletVersion"),
            "capacity": {
                key: node_status["capacity"][key] for key in ("cpu", "memory")
            },
            "allocatable": {
                key: node_status["allocatable"][key] for key in ("cpu", "memory")
            },
        },
        "engine": {
            "serverVersion": _string(
                engine.get("serverVersion"), "engine.serverVersion"
            ),
            "cpus": _integer(engine.get("cpus"), "engine.cpus", minimum=1),
            "memoryBytes": _integer(
                engine.get("memoryBytes"), "engine.memoryBytes", minimum=1
            ),
        },
        "virtualMachine": {
            "logicalCpus": _integer(
                engine.get("vmLogicalCpus"), "engine.vmLogicalCpus", minimum=1
            ),
            "cgroupVersion": 1,
        },
        "release": {
            "name": release.get("name"),
            "namespace": namespace,
            "chart": release.get("chart"),
            "appVersion": release.get("app_version"),
            "revision": int(str(release.get("revision", "0"))),
            "status": release.get("status"),
        },
        "configuration": {key: configuration.get(key) for key in CONFIGURATION_KEYS},
        "workloads": workloads,
        "images": images,
        "podsBefore": pods_before,
        "podsAfter": _pods(_cluster_json(cluster_dir, "pods-after.json")),
        "background": {
            "runningPodsOutsideRelease": len(outside),
            "namespacesWithRunningPodsOutsideRelease": len(
                {
                    _object(item.get("metadata"), "metadata").get("namespace")
                    for item in outside
                }
            ),
        },
        "repository": {
            "revision": _string(repository.get("revision"), "repository.revision"),
            "trackedChangesPresent": bool(repository.get("trackedChangesPresent")),
            "untrackedFilesPresent": bool(repository.get("untrackedFilesPresent")),
            "executedFiles": dict(
                sorted(
                    _object(repository.get("executedFiles"), "executedFiles").items()
                )
            ),
        },
    }
    refuse_private(dumps(environment), "environment")
    return environment


# --------------------------------------------------------------------------
# Resource samples
# --------------------------------------------------------------------------


def _counter(value: str, field: str) -> int | None:
    if value == "missing":
        return None
    if not value.isdigit():
        raise ScenarioError(f"resource sample field '{field}' is not a counter")
    return int(value)


def parse_sample_line(line: str) -> dict[str, Any]:
    """One node read, as the shell sampler wrote it, parsed into integers.

    The line is ``<host µs before> <host µs after> node_ns=<ns> vm=<eight jiffy
    counters> node=<cpu ns>,<memory usage>,<inactive file>`` followed by one such
    triple per release tier. A tier whose cgroup has gone reads ``missing``.
    """
    fields = line.split()
    if len(fields) < 5:
        raise ScenarioError("a resource sample line is too short")
    before, after = fields[0], fields[1]
    if not (before.isdigit() and after.isdigit()) or int(after) < int(before):
        raise ScenarioError("a resource sample carries unusable host timestamps")
    values: dict[str, str] = {}
    for token in fields[2:]:
        match = CGROUP_TOKEN.fullmatch(token.replace("node_ns", "nodens"))
        if match is None:
            raise ScenarioError("a resource sample carries an unrecognized field")
        values[match.group("role")] = match.group("values")
    expected = {"nodens", "vm", "node", *ROLES}
    if set(values) != expected:
        raise ScenarioError("a resource sample does not read every tier exactly once")
    jiffies = values["vm"].split(",")
    if len(jiffies) != 8 or not all(value.isdigit() for value in jiffies):
        raise ScenarioError(
            "a resource sample's virtual machine counters are malformed"
        )
    user, nice, system, idle, iowait, irq, softirq, steal = (
        int(value) for value in jiffies
    )
    node_clock = _counter(values["nodens"], "node_ns")
    if node_clock is None:
        raise ScenarioError("a resource sample carries no node clock")

    def tier(name: str) -> dict[str, int | None]:
        parts = values[name].split(",")
        if len(parts) != 3:
            raise ScenarioError(f"resource sample tier '{name}' is malformed")
        cpu, usage, inactive = (_counter(part, name) for part in parts)
        working_set = (
            None if usage is None or inactive is None else max(usage - inactive, 0)
        )
        return {"cpuNs": cpu, "memoryWorkingSetBytes": working_set}

    micro_before, micro_after = int(before), int(after)
    return {
        "hostEpochMs": (micro_before + micro_after) // 2000,
        "hostReadMs": (micro_after - micro_before) // 1000,
        "nodeClockNs": node_clock,
        "virtualMachine": {
            "busyJiffies": user + nice + system + irq + softirq + steal,
            "totalJiffies": user
            + nice
            + system
            + idle
            + iowait
            + irq
            + softirq
            + steal,
        },
        "node": tier("node"),
        "pods": {role: tier(role) for role in ROLES},
    }


def parse_samples(text: str) -> list[dict[str, Any]]:
    """Every sample line, in the order taken; blank lines are ignored."""
    samples = [parse_sample_line(line) for line in text.splitlines() if line.strip()]
    if not samples:
        raise ScenarioError("there are no resource samples")
    if any(
        later["hostEpochMs"] < earlier["hostEpochMs"]
        for earlier, later in itertools.pairwise(samples)
    ):
        raise ScenarioError("the resource samples are not in time order")
    return samples


def samples_jsonl(samples: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(sample, sort_keys=True, separators=(",", ":")) + "\n"
        for sample in samples
    )


def read_samples_jsonl(text: str) -> list[dict[str, Any]]:
    samples = [
        _object(_read_json_text(line, "resource sample"), "sample")
        for line in text.splitlines()
        if line.strip()
    ]
    if not samples:
        raise ScenarioError("there are no resource samples")
    return samples


def _cores_milli(delta_ns: int | None, elapsed_ns: int) -> int | None:
    if delta_ns is None or elapsed_ns <= 0:
        return None
    return (delta_ns * 1000) // elapsed_ns


def resource_usage(
    samples: Sequence[Mapping[str, Any]],
    start_ms: int,
    end_ms: int,
    *,
    vm_cpus: int,
    minimum_samples: int,
) -> dict[str, Any]:
    """CPU and memory of each tier over the samples taken inside one window.

    Only samples whose host midpoint lies inside the window are used, so a figure
    never borrows a counter read before the window opened or after it closed. The
    CPU of a tier is its cgroup counter's increase over the node clock between the
    first and last of them; memory is the largest working set any of them read.
    """
    inner = [
        sample for sample in samples if start_ms <= sample["hostEpochMs"] <= end_ms
    ]
    result: dict[str, Any] = {
        "samples": len(inner),
        "sufficient": len(inner) >= minimum_samples,
        "coveredMs": (inner[-1]["hostEpochMs"] - inner[0]["hostEpochMs"])
        if len(inner) >= 2
        else 0,
        "windowMs": end_ms - start_ms,
    }
    if len(inner) < 2:
        result.update({"cpuMillicores": None, "memoryPeakWorkingSetBytes": None})
        return result
    first, last = inner[0], inner[-1]
    elapsed = last["nodeClockNs"] - first["nodeClockNs"]

    def delta(read: Any) -> int | None:
        a, b = read(first), read(last)
        return None if a is None or b is None else b - a

    def peak(read: Any) -> int | None:
        readings = [read(sample) for sample in inner]
        return None if any(value is None for value in readings) else max(readings)

    vm_busy = (
        last["virtualMachine"]["busyJiffies"] - first["virtualMachine"]["busyJiffies"]
    )
    vm_total = (
        last["virtualMachine"]["totalJiffies"] - first["virtualMachine"]["totalJiffies"]
    )
    cpu: dict[str, int | None] = {
        "virtualMachine": (vm_busy * vm_cpus * 1000) // vm_total
        if vm_total > 0
        else None,
        "node": _cores_milli(delta(lambda s: s["node"]["cpuNs"]), elapsed),
    }
    memory: dict[str, int | None] = {
        "node": peak(lambda s: s["node"]["memoryWorkingSetBytes"])
    }
    for role in ROLES:
        cpu[role] = _cores_milli(
            delta(lambda s, r=role: s["pods"][r]["cpuNs"]), elapsed
        )
        memory[role] = peak(lambda s, r=role: s["pods"][r]["memoryWorkingSetBytes"])
    pods_cpu = [cpu[role] for role in ROLES]
    cpu["nodeOutsideRelease"] = (
        None
        if cpu["node"] is None or any(value is None for value in pods_cpu)
        else cpu["node"] - sum(cast(list[int], pods_cpu))
    )
    result.update({"cpuMillicores": cpu, "memoryPeakWorkingSetBytes": memory})
    return result


# --------------------------------------------------------------------------
# Windows, telemetry, and the record
# --------------------------------------------------------------------------


def parse_windows(document: Any, descriptor: Descriptor) -> dict[str, Any]:
    """The schedule the shell workflow actually kept, checked for order."""
    windows = _object(document, "windows")
    idle = _object(windows.get("idleBaseline"), "idleBaseline")
    idle_start = _integer(
        idle.get("startEpochMs"), "idleBaseline.startEpochMs", minimum=1
    )
    idle_end = _integer(
        idle.get("endEpochMs"), "idleBaseline.endEpochMs", minimum=idle_start
    )
    runs = [_object(entry, "runs[]") for entry in _list(windows.get("runs"), "runs")]
    if len(runs) != descriptor.repetitions:
        raise ScenarioError(
            f"the windows record {len(runs)} run(s) and the descriptor asks for {descriptor.repetitions}"
        )
    previous = idle_end
    for index, run in enumerate(runs, start=1):
        if run.get("repetition") != index:
            raise ScenarioError("the runs are not numbered in order")
        launched = _integer(
            run.get("launchedEpochMs"), "launchedEpochMs", minimum=previous
        )
        exited = _integer(run.get("exitedEpochMs"), "exitedEpochMs", minimum=launched)
        _integer(run.get("exitCode"), "exitCode", minimum=0, maximum=255)
        if not re.fullmatch(
            r"run-[1-9]-raw\.jsonl", _string(run.get("rawFile"), "rawFile")
        ):
            raise ScenarioError("a run names a raw file outside the expected names")
        previous = exited
    settled = _integer(
        windows.get("settledEpochMs"), "settledEpochMs", minimum=previous
    )
    return {
        "idleStartMs": idle_start,
        "idleEndMs": idle_end,
        "runs": runs,
        "settledMs": settled,
    }


def instants_for(windows: Mapping[str, Any]) -> list[tuple[int, str, int]]:
    """(repetition, position, epoch ms) of every counter read reconciliation needs.

    Before a run is the moment it was launched, which follows an idle window or a
    settle; after it is the next run's launch, or the final settle.
    """
    runs = windows["runs"]
    instants: list[tuple[int, str, int]] = []
    for index, run in enumerate(runs):
        after = (
            runs[index + 1]["launchedEpochMs"]
            if index + 1 < len(runs)
            else windows["settledMs"]
        )
        instants.append((run["repetition"], "before", run["launchedEpochMs"]))
        instants.append((run["repetition"], "after", after))
    return instants


def phase_windows(raw: load.RawSet, descriptor: Descriptor) -> list[dict[str, Any]]:
    """Each phase's epoch window, from the raw set's millisecond origin."""
    origin = raw.header.get("startedAtEpochMs")
    if not isinstance(origin, int) or isinstance(origin, bool):
        raise ScenarioRefused(
            "the raw load record set carries no startedAtEpochMs, so its phases cannot "
            "be placed against resource samples"
        )
    scenario_by_id = {
        scenario.scenario_id: scenario for scenario in descriptor.scenarios
    }
    windows = []
    for phase in raw.phases:
        scenario = scenario_by_id.get(phase.level_id)
        if scenario is None or scenario.concurrency != phase.concurrency:
            raise ScenarioRefused(
                f"the raw set's phase '{phase.level_id}' is not a descriptor scenario"
            )
        start = origin + phase.started_offset_ms
        windows.append(
            {
                "scenario": scenario,
                "phase": phase,
                "startEpochMs": start,
                "endEpochMs": start + phase.window_ms,
            }
        )
    return windows


def _instant_total(entry: Mapping[str, Any], check: Reconciliation) -> int | None:
    if entry.get("status") != "success":
        return None
    rows = [_object(row, "row") for row in _list(entry.get("rows"), "rows")]
    if check.label is not None:
        rows = [
            row
            for row in rows
            if _object(row.get("labels"), "labels").get(check.label)
            == check.label_value
        ]
    if not rows:
        return None
    total = sum(float(_string(row.get("value"), "value")) for row in rows)
    # A counter read is a whole number. NaN and infinity are readings Prometheus can
    # give, and int() would raise on them rather than refuse.
    if not math.isfinite(total) or total != int(total):
        raise ScenarioError(
            f"a counter read for '{check.check_id}' is not a whole number"
        )
    return int(total)


def _checks(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"checkId": name, "passed": passed, "detail": detail}


def build_record(
    descriptor: Descriptor,
    *,
    environment_text: str,
    windows_text: str,
    raw_texts: Mapping[str, str],
    samples_text: str,
    telemetry_text: str,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """The record, as a pure function of the committed inputs.

    Every figure below is either copied from the load summary the raw set reduces to,
    or computed here from the resource samples and counter reads by integer
    arithmetic. The same inputs always give the same record, and a test regenerates
    the committed record from the committed inputs.
    """
    for text, what in (
        (environment_text, "environment"),
        (windows_text, "windows"),
        (telemetry_text, "telemetry"),
        (samples_text, "resource samples"),
        *((raw_text, raw_name) for raw_name, raw_text in sorted(raw_texts.items())),
    ):
        refuse_private(text, what)
    environment = _object(
        _read_json_text(environment_text, "environment"), "environment"
    )
    windows = parse_windows(_read_json_text(windows_text, "windows"), descriptor)
    telemetry = _object(_read_json_text(telemetry_text, "telemetry"), "telemetry")
    samples = read_samples_jsonl(samples_text)
    vm_cpus = _integer(
        _object(environment.get("virtualMachine"), "virtualMachine").get("logicalCpus"),
        "logicalCpus",
        minimum=1,
    )

    checks: list[dict[str, Any]] = []
    observations: list[str] = []

    workloads = _object(environment.get("workloads"), "workloads")
    unavailable = [
        role
        for role in ROLES
        if workloads[role]["availableReplicas"] != workloads[role]["desiredReplicas"]
    ]
    checks.append(
        _checks(
            "every-deployment-available",
            not unavailable,
            "every tier had its desired replicas available before load"
            if not unavailable
            else f"not available before load: {', '.join(unavailable)}",
        )
    )
    pods_before = {(pod["role"], pod["uid"]) for pod in environment["podsBefore"]}
    pods_after = {(pod["role"], pod["uid"]) for pod in environment["podsAfter"]}
    pods_unchanged = pods_before == pods_after
    checks.append(
        _checks(
            "same-pods-throughout",
            pods_unchanged,
            "the same pod served each tier before and after every run"
            if pods_unchanged
            else "a tier's pod was replaced during the experiment",
        )
    )
    # restartCount is a pod's lifetime counter, so the before and after readings of an
    # unchanged pod are not added together: the larger of the two is that pod's count.
    # A restart during model loading, before any load, still fails the check.
    restart_counts: dict[tuple[str, str], int] = {}
    for pod in [*environment["podsBefore"], *environment["podsAfter"]]:
        key = (pod["role"], pod["uid"])
        restart_counts[key] = max(restart_counts.get(key, 0), pod["restartCount"])
    restarts = sum(restart_counts.values())
    checks.append(
        _checks(
            "zero-container-restarts",
            restarts == 0,
            "no container restarted before or during the runs"
            if restarts == 0
            else f"{restarts} container restart(s) counted across the before and after readings",
        )
    )

    idle_usage = resource_usage(
        samples,
        windows["idleStartMs"],
        windows["idleEndMs"],
        vm_cpus=vm_cpus,
        minimum_samples=descriptor.minimum_samples,
    )

    telemetry_series = {
        _string(_object(entry, "series[]").get("seriesId"), "seriesId"): entry
        for entry in _list(telemetry.get("series"), "series")
    }
    refused_series = sorted(
        series_id
        for series_id, _ in descriptor.series
        if _object(telemetry_series.get(series_id), f"series '{series_id}'").get(
            "status"
        )
        != "success"
    )
    checks.append(
        _checks(
            "telemetry-series-answered",
            not refused_series,
            "the collector answered every range query"
            if not refused_series
            else f"the collector refused: {', '.join(refused_series)}",
        )
    )
    instants = {
        (
            int(entry["repetition"]),
            str(entry["position"]),
            str(entry["seriesId"]),
        ): entry
        for entry in (
            _object(item, "instants[]")
            for item in _list(telemetry.get("instants"), "instants")
        )
    }
    expected_at = {
        (repetition, position): at for repetition, position, at in instants_for(windows)
    }

    runs: list[dict[str, Any]] = []
    last_end = windows["idleEndMs"]
    all_phase_samples_sufficient = True
    for run in windows["runs"]:
        repetition = run["repetition"]
        raw_name = run["rawFile"]
        if raw_name not in raw_texts:
            raise ScenarioError(
                f"the raw load record set '{raw_name}' was not provided"
            )
        raw = load.parse_raw(raw_texts[raw_name], repo_root=repo_root)
        if raw.header.get("mode") != load.MODE_REAL:
            raise ScenarioRefused("a performance record accepts real load runs only")
        if (
            _object(raw.header.get("profile"), "profile").get("profileSha256")
            != descriptor.profile.profile_sha256
        ):
            raise ScenarioRefused(
                "a raw load record set was produced from another load profile"
            )
        facts = _object(
            _object(raw.header.get("environment"), "environment").get("facts"), "facts"
        )
        if facts.get("provider") != environment["provider"]:
            raise ScenarioRefused(
                "a raw load record set names another provider than the environment"
            )
        summary = load.summarize(raw)
        completed = raw.end["state"] == load.END_COMPLETED and run["exitCode"] == 0
        checks.append(
            _checks(
                f"run-{repetition}-completed",
                completed,
                f"run {repetition} ended '{raw.end['state']}' with exit code {run['exitCode']}",
            )
        )
        phases = []
        for placed, phase_summary in zip(
            phase_windows(raw, descriptor),
            [summary["warmup"], *summary["levels"]],
            strict=True,
        ):
            scenario: Scenario = placed["scenario"]
            usage = resource_usage(
                samples,
                placed["startEpochMs"],
                placed["endEpochMs"],
                vm_cpus=vm_cpus,
                minimum_samples=descriptor.minimum_samples,
            )
            if scenario.load_phase == load.PHASE_MEASURED and not usage["sufficient"]:
                all_phase_samples_sufficient = False
            unsuccessful = phase_summary["unsuccessful"]
            if unsuccessful:
                observations.append(
                    f"run {repetition} {scenario.scenario_id}: {unsuccessful} of "
                    f"{phase_summary['dispatched']} request(s) were not successes "
                    f"(outcomes {json.dumps(phase_summary['outcomes'], sort_keys=True)})"
                )
            if (
                scenario.load_phase == load.PHASE_MEASURED
                and phase_summary["stopReason"] != load.STOP_CEILING
            ):
                observations.append(
                    f"run {repetition} {scenario.scenario_id}: stopped by '{phase_summary['stopReason']}' "
                    f"after {phase_summary['dispatched']} request(s), not by its request ceiling"
                )
            phases.append(
                {
                    "scenarioId": scenario.scenario_id,
                    "role": scenario.role,
                    "concurrency": scenario.concurrency,
                    "startEpochMs": placed["startEpochMs"],
                    "endEpochMs": placed["endEpochMs"],
                    "load": {
                        key: value
                        for key, value in phase_summary.items()
                        if key not in ("levelId",)
                    },
                    "resources": usage,
                }
            )
            last_end = max(last_end, placed["endEpochMs"])
        records = raw.records
        expected_values = {
            "dispatched": len(records),
            "output-tokens": sum(
                record.output_tokens or 0
                for record in records
                if record.outcome == load.OUTCOME_SUCCESS
            ),
        }
        # The workflow sends no inference request before the first run, and the code
        # cannot see the workflow. What it can see is the runtime's own predicted-token
        # counter, which exists from the runtime's start: at zero, the runtime has
        # decoded nothing, so the API has served no completion either.
        runtime_before = instants.get((repetition, "before", RUNTIME_TOKENS_SERIES))
        runtime_idle_before_first_run = (
            runtime_before is not None
            and runtime_before.get("status") == "success"
            and [
                _object(row, "row").get("value")
                for row in _list(runtime_before.get("rows"), "rows")
            ]
            == ["0"]
        )
        reconciliation = []
        for check in descriptor.reconciliation:
            reads: dict[str, int | None] = {}
            answered_empty: dict[str, bool] = {}
            for position in ("before", "after"):
                entry = instants.get((repetition, position, check.series_id))
                if entry is None:
                    raise ScenarioError(
                        f"no {position} counter read for run {repetition} '{check.series_id}'"
                    )
                if entry.get("atEpochMs") != expected_at[(repetition, position)]:
                    raise ScenarioError(
                        f"the {position} counter read for run {repetition} was not taken at the "
                        "moment the schedule defines"
                    )
                reads[position] = _instant_total(entry, check)
                answered_empty[position] = (
                    entry.get("status") == "success" and reads[position] is None
                )
            # A labelled counter series does not exist until its first increment, so
            # before the first run the API's counters answer with no series at all.
            # Absent is not zero in general. It is read as zero here only where it
            # cannot be anything else: the first run, whose pods are the ones the
            # workflow installed and never replaced or restarted, and which the
            # workflow sends no inference request before. Anywhere else an absent
            # series leaves the check unreconciled. The record says which applied.
            absent_before_read_as_zero = (
                repetition == 1
                and answered_empty["before"]
                and pods_unchanged
                and restarts == 0
                and runtime_idle_before_first_run
            )
            if absent_before_read_as_zero:
                reads["before"] = 0
            observed = (
                None
                if reads["before"] is None or reads["after"] is None
                else reads["after"] - reads["before"]
            )
            expected_value = expected_values[check.compare_with]
            agrees = observed == expected_value
            reconciliation.append(
                {
                    "checkId": check.check_id,
                    "before": reads["before"],
                    "after": reads["after"],
                    "increase": observed,
                    "expected": expected_value,
                    "comparedWith": check.compare_with,
                    "absentBeforeReadAsZero": absent_before_read_as_zero,
                    "agrees": agrees,
                }
            )
            if not agrees:
                observations.append(
                    f"run {repetition} {check.check_id}: the counter increased by {observed} "
                    f"and the raw set records {expected_value}"
                )
        runs.append(
            {
                "repetition": repetition,
                "runId": raw.header["runId"],
                "rawFile": raw_name,
                "rawSha256": text_digest(raw_texts[raw_name]),
                "startedAtEpochMs": raw.header["startedAtEpochMs"],
                "end": summary["end"],
                "usable": summary["usable"],
                "exitCode": run["exitCode"],
                "accounting": summary["accounting"],
                "generatorHost": raw.header["environment"]["generatorHost"],
                "served": raw.header["environment"]["served"],
                "phases": phases,
                "reconciliation": reconciliation,
            }
        )

    reconciled = all(item["agrees"] for run in runs for item in run["reconciliation"])
    checks.append(
        _checks(
            "counters-reconcile-with-raw-records",
            reconciled,
            "every counter increase equals what the raw sets record"
            if reconciled
            else "at least one counter increase differs from the raw sets; see observations",
        )
    )

    gaps = [
        later["hostEpochMs"] - earlier["hostEpochMs"]
        for earlier, later in itertools.pairwise(samples)
    ]
    largest_gap = max(gaps) if gaps else 0
    covers = (
        samples[0]["hostEpochMs"] <= windows["idleStartMs"] + descriptor.maximum_gap_ms
        and samples[-1]["hostEpochMs"] >= last_end
    )
    missing_reads = sum(
        1
        for sample in samples
        if windows["idleStartMs"] <= sample["hostEpochMs"] <= last_end
        and (
            sample["node"]["cpuNs"] is None
            or any(sample["pods"][role]["cpuNs"] is None for role in ROLES)
        )
    )
    sampled = (
        covers
        and largest_gap <= descriptor.maximum_gap_ms
        and missing_reads == 0
        and all_phase_samples_sufficient
        and idle_usage["sufficient"]
    )
    checks.append(
        _checks(
            "resource-samples-cover-every-phase",
            sampled,
            f"{len(samples)} samples; largest gap {largest_gap} ms against {descriptor.maximum_gap_ms} ms allowed; "
            f"{missing_reads} read(s) with a tier missing; every measured phase and the idle window "
            f"{'had' if all_phase_samples_sufficient and idle_usage['sufficient'] else 'did not all have'} "
            f"at least {descriptor.minimum_samples} samples",
        )
    )

    usable = all(check["passed"] for check in checks)
    return {
        "schemaVersion": RECORD_SCHEMA,
        "kind": RECORD_KIND,
        "experimentId": descriptor.document["experimentId"],
        "experimentVersion": descriptor.document["experimentVersion"],
        "descriptorSha256": descriptor.sha256,
        "loadProfileSha256": descriptor.profile.profile_sha256,
        "evidenceClass": descriptor.document["evidenceClass"],
        "evidenceLabel": descriptor.document["evidenceLabel"],
        "certificationCeiling": descriptor.document["certificationCeiling"],
        "productionBenchmark": False,
        "portableCapacityClaim": False,
        "boundary": descriptor.document["boundary"],
        "saturationJudged": False,
        "environment": environment,
        "schedule": {
            "idleBaseline": {
                "startEpochMs": windows["idleStartMs"],
                "endEpochMs": windows["idleEndMs"],
            },
            "runs": windows["runs"],
            "settledEpochMs": windows["settledMs"],
        },
        "idleBaseline": idle_usage,
        "runs": runs,
        "telemetry": {
            "collectorVersion": telemetry.get("collectorVersion"),
            "scrapeIntervalSeconds": descriptor.scrape_interval_seconds,
            "rangeStepSeconds": descriptor.range_step_seconds,
            "seriesAnswered": sorted(set(telemetry_series) - set(refused_series)),
            "dashboardCaptures": len(_list(telemetry.get("dashboard"), "dashboard")),
        },
        "checks": checks,
        "usable": usable,
        "observations": observations,
        "inputs": {
            "environment": text_digest(environment_text),
            "windows": text_digest(windows_text),
            "resourceSamples": text_digest(samples_text),
            "telemetry": text_digest(telemetry_text),
            **{name: text_digest(text) for name, text in sorted(raw_texts.items())},
        },
        "limitations": descriptor.document["limitations"],
    }
