"""Figures derived from one committed performance record, and nothing judged from them.

A performance record places each phase's latency, rates, and resources side by side
and compares none of them. The analysis that does compare them needs a handful of
further figures: each level against its own run's baseline, how far apart successive
completions were, what the collector's gauges read inside each phase, and what the
counters the record did not reconcile say. This module computes exactly those, by
integer arithmetic, from the record's committed inputs.

It refuses to start unless the record regenerates byte for byte from those inputs
under `tools.performance_scenarios`, so every figure here is traceable to the same raw
evidence the record is. It never states where a setup degraded. The findings carry
`saturationJudged: false`; a degradation statement belongs to the analysis document
that cites them (ADR 0013 D4).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

from tools.llm_load import core as load
from tools.performance_scenarios.core import (
    REPO_ROOT,
    Descriptor,
    ScenarioError,
    build_record,
    dumps,
    refuse_private,
    text_digest,
)

SCHEMA = "inferops.io/v1alpha1"
KIND = "inferops-performance-findings"
RECORD_KIND = "inferops-performance-scenarios-record"
BOUNDARY = (
    "Figures derived from one committed performance record, on the provider, host, "
    "model, runtime, release, and load profile that record names. They are not a "
    "portable capacity figure, a production SLO, or a benchmark of Kubernetes, the "
    "model, the runtime, or any provider, and no tool judged saturation from them."
)

#: The committed names of a record's inputs, without a prefix.
INPUT_FILES = {
    "environment": "environment.v1alpha1.json",
    "windows": "windows.v1alpha1.json",
    "samples": "resource-samples.v1alpha1.jsonl",
    "telemetry": "telemetry.v1alpha1.json",
    "record": "performance-record.v1alpha1.json",
}

SERIES_PROCESSING = "runtime-requests-processing"
SERIES_DEFERRED = "runtime-requests-deferred"
SERIES_IN_FLIGHT = "api-requests-in-flight"
SERIES_API_TOKENS = "api-tokens-by-direction"
SERIES_PROMPT_TOKENS = "runtime-prompt-tokens"
CHECK_API_OUTPUT = "api-output-tokens-equal-recorded"

ROLE_WARM_UP = "warm-up"
ROLE_BASELINE = "baseline"

QUANTITY = re.compile(r"(?P<number>[0-9]+)(?P<unit>m|Ki|Mi|Gi)?")
BINARY_UNITS = {None: 1, "Ki": 1024, "Mi": 1024**2, "Gi": 1024**3}


class FindingsError(RuntimeError):
    """A record, or an input it was built from, cannot be analysed."""


class FindingsRefused(FindingsError):
    """The record is not one whose figures may be derived."""


@dataclass(frozen=True, slots=True)
class RecordInputs:
    """The committed record and every input it was built from, as text."""

    record_name: str
    record_text: str
    environment_text: str
    windows_text: str
    samples_text: str
    telemetry_text: str
    raw_texts: Mapping[str, str]


# --------------------------------------------------------------------------
# Small readers
# --------------------------------------------------------------------------


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FindingsError(f"'{field}' must be an object")
    return cast(dict[str, Any], value)


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise FindingsError(f"'{field}' must be a list")
    return value


def _integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise FindingsError(f"'{field}' must be an integer")
    return value


def _whole_string(value: Any, field: str) -> int:
    """A configuration value or runtime argument that must be a whole number."""
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise FindingsError(f"'{field}' must be a whole number")
    return int(value)


def _number(value: Any, field: str) -> float:
    """A collector value, which Prometheus writes as a string, as a float."""
    if not isinstance(value, str | int | float) or isinstance(value, bool):
        raise FindingsError(f"'{field}' must be a number")
    try:
        return float(value)
    except ValueError as error:
        raise FindingsError(f"'{field}' must be a number") from error


def _read(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeError) as error:
        raise FindingsError(f"the {what} is unreadable") from error


def _json(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise FindingsError(f"the {what} is not valid JSON") from error


def ratio_milli(numerator: int, denominator: int) -> int:
    """numerator / denominator in thousandths, rounded half up, by integer arithmetic."""
    if denominator <= 0 or numerator < 0:
        raise FindingsError("a ratio needs a positive denominator")
    return (numerator * 1000 + denominator // 2) // denominator


def cpu_millicores(quantity: str) -> int:
    """A Kubernetes CPU quantity such as '6' or '500m', in millicores."""
    match = QUANTITY.fullmatch(quantity)
    if match is None or match.group("unit") not in (None, "m"):
        raise FindingsError(f"'{quantity}' is not a CPU quantity this reader accepts")
    number = int(match.group("number"))
    return number if match.group("unit") == "m" else number * 1000


def memory_bytes(quantity: str) -> int:
    """A Kubernetes memory quantity such as '3Gi' or '512Mi', in bytes."""
    match = QUANTITY.fullmatch(quantity)
    if match is None or match.group("unit") == "m":
        raise FindingsError(
            f"'{quantity}' is not a memory quantity this reader accepts"
        )
    return int(match.group("number")) * BINARY_UNITS[match.group("unit")]


def argument_value(arguments: Sequence[str], flag: str) -> str:
    """The value following a flag in a container's argument list."""
    positions = [index for index, value in enumerate(arguments) if value == flag]
    if len(positions) != 1 or positions[0] + 1 >= len(arguments):
        raise FindingsError(f"the runtime's arguments do not set '{flag}' exactly once")
    return arguments[positions[0] + 1]


# --------------------------------------------------------------------------
# Reading and checking the record
# --------------------------------------------------------------------------


def read_inputs(directory: Path, prefix: str) -> RecordInputs:
    """The committed record under a prefix, and every input it names."""
    texts = {
        key: _read(directory / f"{prefix}{name}", key)
        for key, name in INPUT_FILES.items()
    }
    windows = _object(_json(texts["windows"], "windows"), "windows")
    raw_names = [
        str(_object(run, "run").get("rawFile"))
        for run in _list(windows.get("runs"), "runs")
    ]
    raw_texts = {name: _read(directory / f"{prefix}{name}", name) for name in raw_names}
    return RecordInputs(
        record_name=f"{prefix}{INPUT_FILES['record']}",
        record_text=texts["record"],
        environment_text=texts["environment"],
        windows_text=texts["windows"],
        samples_text=texts["samples"],
        telemetry_text=texts["telemetry"],
        raw_texts=raw_texts,
    )


def checked_record(
    descriptor: Descriptor, inputs: RecordInputs, *, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    """The record, once it is shown to be usable, bounded, and regenerable."""
    record = _object(_json(inputs.record_text, "performance record"), "record")
    if record.get("schemaVersion") != SCHEMA or record.get("kind") != RECORD_KIND:
        raise FindingsRefused("the file is not a performance scenarios record")
    for flag in ("productionBenchmark", "portableCapacityClaim", "saturationJudged"):
        if record.get(flag) is not False:
            raise FindingsRefused(
                f"the record's '{flag}' is not false; figures are derived only from a "
                "record that claims no benchmark, no capacity, and no saturation"
            )
    boundary = record.get("boundary")
    if not isinstance(boundary, str) or not boundary.strip():
        raise FindingsRefused("the record carries no boundary sentence")
    if record.get("usable") is not True:
        raise FindingsRefused(
            "the record is not usable; no figure is derived from a run whose own "
            "checks failed"
        )
    try:
        regenerated = build_record(
            descriptor,
            environment_text=inputs.environment_text,
            windows_text=inputs.windows_text,
            raw_texts=inputs.raw_texts,
            samples_text=inputs.samples_text,
            telemetry_text=inputs.telemetry_text,
            repo_root=repo_root,
        )
    except (ScenarioError, load.LoadError) as error:
        raise FindingsRefused(
            f"the record's inputs do not build a record: {error}"
        ) from error
    if dumps(regenerated) != inputs.record_text:
        raise FindingsRefused(
            "the committed record does not regenerate from its committed inputs, so "
            "nothing derived from those inputs would describe it"
        )
    return record


# --------------------------------------------------------------------------
# Derivations
# --------------------------------------------------------------------------


def completion_gaps_ms(records: Sequence[load.RequestRecord]) -> list[int]:
    """Milliseconds between successive completions within one phase.

    A request's completion is its dispatch offset plus its latency, both measured
    from the phase's own start. Gaps are taken in completion order.
    """
    if len(records) < 2:
        raise FindingsError(
            "a phase with fewer than two completions has no completion gap"
        )
    completions = sorted(
        record.dispatch_offset_ms + record.latency_ms for record in records
    )
    return [later - earlier for earlier, later in pairwise(completions)]


def fastest_position(records: Sequence[load.RequestRecord]) -> int:
    """The dispatch position, within its phase, of the fastest successful request."""
    ordered = sorted(records, key=lambda record: record.sequence)
    successes = [
        (record.latency_ms, index)
        for index, record in enumerate(ordered)
        if record.outcome == load.OUTCOME_SUCCESS
    ]
    if not successes:
        raise FindingsError("a phase with no successful request has no fastest one")
    return min(successes)[1]


def _points(
    telemetry: Mapping[str, Any], series_id: str, labels: Mapping[str, str]
) -> list[tuple[int, int]]:
    """A range series' (epoch ms, whole value) points for one label set."""
    for series in _list(telemetry.get("series"), "series"):
        entry = _object(series, "series")
        if entry.get("seriesId") != series_id:
            continue
        if entry.get("status") != "success":
            raise FindingsError(f"the collector refused the series '{series_id}'")
        for result in _list(entry.get("result"), "result"):
            row = _object(result, "result")
            if row.get("labels") != dict(labels):
                continue
            points = []
            for pair in _list(row.get("values"), "values"):
                point = _list(pair, "value")
                if len(point) != 2:
                    raise FindingsError(f"a reading of '{series_id}' is not a pair")
                number = _number(point[1], series_id)
                if not math.isfinite(number) or number != int(number):
                    raise FindingsError(
                        f"a reading of '{series_id}' is not a whole number"
                    )
                points.append((round(_number(point[0], series_id) * 1000), int(number)))
            return points
        return []
    raise FindingsError(f"the telemetry holds no series '{series_id}'")


def gauge_maximum(
    points: Sequence[tuple[int, int]], start_ms: int, end_ms: int
) -> dict[str, int | None]:
    """The largest reading at a range step inside [start, end], and how many there were."""
    inside = [value for moment, value in points if start_ms <= moment <= end_ms]
    return {"points": len(inside), "maximum": max(inside) if inside else None}


def reading_at(points: Sequence[tuple[int, int]], moment_ms: int) -> int | None:
    """The last range-step reading at or before a moment, or None if there is none."""
    earlier = [value for at, value in points if at <= moment_ms]
    return earlier[-1] if earlier else None


def instant_total(
    telemetry: Mapping[str, Any],
    series_id: str,
    repetition: int,
    position: str,
    labels: Mapping[str, str],
) -> int | None:
    """A counter read at a scheduled moment, for one label set, or None if absent."""
    matches = [
        _object(entry, "instant")
        for entry in _list(telemetry.get("instants"), "instants")
        if _object(entry, "instant").get("seriesId") == series_id
        and _object(entry, "instant").get("repetition") == repetition
        and _object(entry, "instant").get("position") == position
    ]
    if len(matches) != 1:
        raise FindingsError(
            f"the telemetry does not hold exactly one '{series_id}' read {position} "
            f"run {repetition}"
        )
    if matches[0].get("status") != "success":
        raise FindingsError(f"the collector refused the '{series_id}' read")
    rows = [
        _object(row, "row")
        for row in _list(matches[0].get("rows"), "rows")
        if _object(_object(row, "row").get("labels"), "labels") == dict(labels)
    ]
    if not rows:
        return None
    if len(rows) != 1:
        raise FindingsError(f"the '{series_id}' read holds more than one matching row")
    number = _number(rows[0].get("value"), series_id)
    if not math.isfinite(number) or number != int(number):
        raise FindingsError(f"a read of '{series_id}' is not a whole number")
    return int(number)


def _single_reading(
    readings: Mapping[str, Any], reading_id: str, scale: int
) -> int | None:
    """One dashboard query's single row, scaled and rounded half up, or None if empty."""
    entry = readings.get(reading_id)
    if entry is None:
        return None
    rows = _list(_object(entry, reading_id).get("rows"), reading_id)
    if not rows:
        return None
    if len(rows) != 1:
        raise FindingsError(
            f"the dashboard reading '{reading_id}' holds more than one row"
        )
    number = _number(_object(rows[0], "row").get("value"), reading_id)
    if not math.isfinite(number):
        return None
    return math.floor(number * scale + 0.5)


def dashboard_at_phase_ends(telemetry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The latency-quantile and request-rate panels, as read at each phase end.

    Both panels take a five-minute rate window, so a reading at a phase end covers
    that phase and whatever preceded it inside the window.
    """
    captures = []
    for capture in _list(telemetry.get("dashboard"), "dashboard"):
        entry = _object(capture, "capture")
        readings = _object(entry.get("readings"), "readings")
        captures.append(
            {
                "repetition": _integer(entry.get("repetition"), "repetition"),
                "scenarioId": entry.get("scenarioId"),
                "latencyQuantilesMs": {
                    "p50": _single_reading(
                        readings, "request-latency-quantiles/A", 1000
                    ),
                    "p95": _single_reading(
                        readings, "request-latency-quantiles/B", 1000
                    ),
                    "p99": _single_reading(
                        readings, "request-latency-quantiles/C", 1000
                    ),
                },
                "requestsPerSecondMilli": _single_reading(
                    readings, "request-rate-by-outcome/A", 1000
                ),
            }
        )
    return captures


def _range(values: Sequence[int]) -> list[int]:
    return [min(values), max(values)]


def _runtime_container(environment: Mapping[str, Any]) -> dict[str, Any]:
    workloads = _object(environment.get("workloads"), "workloads")
    runtime = _object(workloads.get("runtime"), "workloads.runtime")
    containers = [
        _object(container, "container")
        for container in _list(runtime.get("containers"), "containers")
        if _object(container, "container").get("name") == "runtime"
    ]
    if len(containers) != 1:
        raise FindingsError(
            "the environment does not hold exactly one runtime container"
        )
    return containers[0]


def _setup(record: Mapping[str, Any]) -> dict[str, Any]:
    environment = _object(record.get("environment"), "environment")
    container = _runtime_container(environment)
    arguments = [str(value) for value in _list(container.get("args"), "args")]
    limits = _object(
        _object(container.get("resources"), "resources").get("limits"), "limits"
    )
    configuration = _object(environment.get("configuration"), "configuration")
    node = _object(environment.get("node"), "node")
    engine = _object(environment.get("engine"), "engine")
    runs = _list(record.get("runs"), "runs")
    served = _object(_object(runs[0], "run").get("served"), "served")
    generator = _object(_object(runs[0], "run").get("generatorHost"), "generatorHost")
    return {
        "provider": environment.get("provider"),
        "kubernetesServerVersion": _object(
            environment.get("kubernetes"), "kubernetes"
        ).get("serverVersion"),
        "nodeAllocatable": node.get("allocatable"),
        "nodeKernel": node.get("kernelVersion"),
        "engine": {
            "serverVersion": engine.get("serverVersion"),
            "cpus": engine.get("cpus"),
            "memoryBytes": engine.get("memoryBytes"),
        },
        "generatorHost": generator,
        "chart": _object(environment.get("release"), "release").get("chart"),
        "model": {
            "id": served.get("modelId"),
            "revision": served.get("modelRevision"),
        },
        "runtime": {
            "image": container.get("image"),
            "parallelSlots": _whole_string(
                argument_value(arguments, "--parallel"), "--parallel"
            ),
            "threads": _whole_string(
                argument_value(arguments, "--threads"), "--threads"
            ),
            "contextSize": _whole_string(
                argument_value(arguments, "--ctx-size"), "--ctx-size"
            ),
            "cpuLimitMillicores": cpu_millicores(str(limits.get("cpu"))),
            "memoryLimitBytes": memory_bytes(str(limits.get("memory"))),
            "replicas": _object(
                _object(environment.get("workloads"), "workloads").get("runtime"),
                "runtime",
            ).get("desiredReplicas"),
        },
        "maxOutputTokens": _whole_string(
            configuration.get("INFEROPS_MAX_OUTPUT_TOKENS"),
            "INFEROPS_MAX_OUTPUT_TOKENS",
        ),
        "requestTimeoutMs": _whole_string(
            configuration.get("INFEROPS_REQUEST_TIMEOUT_MS"),
            "INFEROPS_REQUEST_TIMEOUT_MS",
        ),
        "loadProfileSha256": record.get("loadProfileSha256"),
        "descriptorSha256": record.get("descriptorSha256"),
        "evidenceClass": record.get("evidenceClass"),
    }


def derive_findings(
    descriptor: Descriptor, inputs: RecordInputs, *, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    """The findings document, as a pure function of a checked record's inputs."""
    record = checked_record(descriptor, inputs, repo_root=repo_root)
    setup = _setup(record)
    telemetry = _object(_json(inputs.telemetry_text, "telemetry"), "telemetry")
    processing = _points(telemetry, SERIES_PROCESSING, {})
    deferred = _points(telemetry, SERIES_DEFERRED, {})
    in_flight = _points(telemetry, SERIES_IN_FLIGHT, {})
    input_labels = {"inferops_token_direction": "input"}
    prompt_tokens = _points(telemetry, SERIES_PROMPT_TOKENS, {})
    schedule = _object(record.get("schedule"), "schedule")
    scheduled_runs = _list(schedule.get("runs"), "schedule.runs")
    settled = _integer(schedule.get("settledEpochMs"), "settledEpochMs")
    role_of = {scenario.scenario_id: scenario.role for scenario in descriptor.scenarios}

    phases: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    for index, run_document in enumerate(_list(record.get("runs"), "runs")):
        run = _object(run_document, "run")
        repetition = _integer(run.get("repetition"), "repetition")
        raw = load.parse_raw(
            inputs.raw_texts[str(run.get("rawFile"))], repo_root=repo_root
        )
        record_phases = [
            _object(phase, "phase") for phase in _list(run.get("phases"), "phases")
        ]
        baseline = [
            phase for phase in record_phases if phase.get("role") == ROLE_BASELINE
        ]
        if len(baseline) != 1:
            raise FindingsError(
                f"run {repetition} does not hold exactly one baseline phase"
            )
        baseline_load = _object(baseline[0].get("load"), "load")
        baseline_p50 = _integer(
            _object(baseline_load.get("latencyOfSuccesses"), "latency").get("p50Ms"),
            "p50Ms",
        )
        baseline_p95 = _integer(
            _object(baseline_load.get("latencyOfSuccesses"), "latency").get("p95Ms"),
            "p95Ms",
        )
        baseline_rate = _integer(
            baseline_load.get("successfulRequestsPerSecondMilli"), "rate"
        )
        baseline_resources = _object(baseline[0].get("resources"), "resources")
        baseline_cpu = _integer(
            _object(baseline_resources.get("cpuMillicores"), "cpuMillicores").get(
                "runtime"
            ),
            "runtime cpu",
        )
        warm_up: dict[str, Any] | None = None
        for phase in record_phases:
            scenario_id = str(phase.get("scenarioId"))
            phase_load = _object(phase.get("load"), "load")
            resources = _object(phase.get("resources"), "resources")
            latency = _object(phase_load.get("latencyOfSuccesses"), "latency")
            requests = [
                request for request in raw.records if request.level_id == scenario_id
            ]
            if len(requests) != _integer(phase_load.get("dispatched"), "dispatched"):
                raise FindingsError(
                    f"run {repetition} phase '{scenario_id}' holds a different number "
                    "of requests than the record dispatched"
                )
            start = _integer(phase.get("startEpochMs"), "startEpochMs")
            end = _integer(phase.get("endEpochMs"), "endEpochMs")
            ordered = sorted(requests, key=lambda request: request.sequence)
            if role_of.get(scenario_id) == ROLE_WARM_UP:
                latencies = [request.latency_ms for request in ordered]
                warm_up = {
                    "latenciesMsInDispatchOrder": latencies,
                    "firstSlowerThanOthersMsRange": _range(
                        [latencies[0] - later for later in latencies[1:]]
                    )
                    if len(latencies) > 1
                    else None,
                }
                continue
            gaps = completion_gaps_ms(requests)
            p50 = _integer(latency.get("p50Ms"), "p50Ms")
            p95 = _integer(latency.get("p95Ms"), "p95Ms")
            rate = _integer(phase_load.get("successfulRequestsPerSecondMilli"), "rate")
            cpu = _object(resources.get("cpuMillicores"), "cpuMillicores")
            memory = _object(
                resources.get("memoryPeakWorkingSetBytes"), "memoryPeakWorkingSetBytes"
            )
            runtime_cpu = _integer(cpu.get("runtime"), "runtime cpu")
            runtime_memory = _integer(memory.get("runtime"), "runtime memory")
            phases.append(
                {
                    "repetition": repetition,
                    "scenarioId": scenario_id,
                    "role": role_of.get(scenario_id),
                    "concurrency": _integer(phase.get("concurrency"), "concurrency"),
                    "requests": {
                        "dispatched": _integer(
                            phase_load.get("dispatched"), "dispatched"
                        ),
                        "successful": _integer(
                            phase_load.get("successful"), "successful"
                        ),
                        "unsuccessful": _integer(
                            phase_load.get("unsuccessful"), "unsuccessful"
                        ),
                    },
                    "latencyMs": {
                        key: _integer(latency.get(key), key)
                        for key in ("p50Ms", "p95Ms", "p99Ms", "minMs", "maxMs")
                    },
                    "p50ToBaselineMilli": ratio_milli(p50, baseline_p50),
                    "p95ToBaselineMilli": ratio_milli(p95, baseline_p95),
                    "fastestRequestPosition": fastest_position(requests),
                    "successfulRequestsPerSecondMilli": rate,
                    "rateToBaselineMilli": ratio_milli(rate, baseline_rate),
                    "completionGapMs": {
                        "count": len(gaps),
                        "minMs": min(gaps),
                        "p50Ms": load.percentile_ms(gaps, 50),
                        "maxMs": max(gaps),
                    },
                    "collector": {
                        "runtimeRequestsProcessing": gauge_maximum(
                            processing, start, end
                        ),
                        "runtimeRequestsDeferred": gauge_maximum(deferred, start, end),
                        "apiRequestsInFlight": gauge_maximum(in_flight, start, end),
                    },
                    "runtimeCpu": {
                        "millicores": runtime_cpu,
                        "ofLimitMilli": ratio_milli(
                            runtime_cpu, setup["runtime"]["cpuLimitMillicores"]
                        ),
                        "minusBaselineMillicores": runtime_cpu - baseline_cpu,
                    },
                    "runtimeMemory": {
                        "peakWorkingSetBytes": runtime_memory,
                        "ofLimitMilli": ratio_milli(
                            runtime_memory, setup["runtime"]["memoryLimitBytes"]
                        ),
                    },
                    "nodeOutsideReleaseCpuMillicores": _integer(
                        cpu.get("nodeOutsideRelease"), "nodeOutsideRelease"
                    ),
                }
            )

        launched = _integer(
            _object(scheduled_runs[index], "run").get("launchedEpochMs"),
            "launchedEpochMs",
        )
        after = (
            _integer(
                _object(scheduled_runs[index + 1], "run").get("launchedEpochMs"),
                "launchedEpochMs",
            )
            if index + 1 < len(scheduled_runs)
            else settled
        )
        absent_as_zero = any(
            _object(check, "check").get("checkId") == CHECK_API_OUTPUT
            and _object(check, "check").get("absentBeforeReadAsZero") is True
            for check in _list(run.get("reconciliation"), "reconciliation")
        )
        input_before = instant_total(
            telemetry, SERIES_API_TOKENS, repetition, "before", input_labels
        )
        input_before_read = (
            0 if input_before is None and absent_as_zero else input_before
        )
        input_after = instant_total(
            telemetry, SERIES_API_TOKENS, repetition, "after", input_labels
        )
        prompt_before = reading_at(prompt_tokens, launched)
        prompt_after = reading_at(prompt_tokens, after)
        input_sent = sum(request.input_tokens or 0 for request in raw.records)
        input_increase = (
            None
            if input_before_read is None or input_after is None
            else input_after - input_before_read
        )
        runs.append(
            {
                "repetition": repetition,
                "runId": run.get("runId"),
                "warmUp": warm_up,
                "tokens": {
                    "inputSentByRawSet": input_sent,
                    "outputRecordedByRawSet": sum(
                        request.output_tokens or 0 for request in raw.records
                    ),
                    "apiInputCounter": {
                        "before": input_before,
                        "absentBeforeReadAsZero": input_before is None
                        and absent_as_zero,
                        "after": input_after,
                        "increase": input_increase,
                        "agreesWithRawSet": input_increase == input_sent,
                    },
                    "runtimePromptTokens": {
                        "before": prompt_before,
                        "after": prompt_after,
                        "increase": None
                        if prompt_before is None or prompt_after is None
                        else prompt_after - prompt_before,
                    },
                    "distinctInputTokenCounts": sorted(
                        {
                            request.input_tokens
                            for request in raw.records
                            if request.input_tokens is not None
                        }
                    ),
                    "distinctOutputTokenCounts": sorted(
                        {
                            request.output_tokens
                            for request in raw.records
                            if request.output_tokens is not None
                        }
                    ),
                    "finishReasons": sorted(
                        {
                            request.finish_reason
                            for request in raw.records
                            if request.finish_reason is not None
                        }
                    ),
                },
            }
        )

    levels = []
    measured_ids = [
        scenario.scenario_id
        for scenario in descriptor.scenarios
        if scenario.role != ROLE_WARM_UP
    ]
    for scenario_id in measured_ids:
        chosen = [phase for phase in phases if phase["scenarioId"] == scenario_id]
        rates = [phase["successfulRequestsPerSecondMilli"] for phase in chosen]
        levels.append(
            {
                "scenarioId": scenario_id,
                "concurrency": chosen[0]["concurrency"],
                "p50MsRange": _range([phase["latencyMs"]["p50Ms"] for phase in chosen]),
                "p95MsRange": _range([phase["latencyMs"]["p95Ms"] for phase in chosen]),
                "p99MsRange": _range([phase["latencyMs"]["p99Ms"] for phase in chosen]),
                "successfulRequestsPerSecondMilliRange": _range(rates),
                "betweenRunsRateDifferenceMilli": max(rates) - min(rates),
                "betweenRunsDifferenceMs": {
                    key: max(phase["latencyMs"][f"{key}Ms"] for phase in chosen)
                    - min(phase["latencyMs"][f"{key}Ms"] for phase in chosen)
                    for key in ("p50", "p95", "p99")
                },
                "runtimeCpuMillicoresRange": _range(
                    [phase["runtimeCpu"]["millicores"] for phase in chosen]
                ),
            }
        )
    all_rates = [phase["successfulRequestsPerSecondMilli"] for phase in phases]
    baseline_runtime_cpu = [
        phase["runtimeCpu"]["millicores"]
        for phase in phases
        if phase["role"] == ROLE_BASELINE
    ]
    findings = {
        "schemaVersion": SCHEMA,
        "kind": KIND,
        "boundary": BOUNDARY,
        "productionBenchmark": False,
        "portableCapacityClaim": False,
        "saturationJudged": False,
        "evidenceClass": record.get("evidenceClass"),
        "source": {
            "recordFile": inputs.record_name,
            "recordSha256": text_digest(inputs.record_text),
            "regeneratedFromInputs": True,
        },
        "setup": setup,
        "phases": phases,
        "runs": runs,
        "levels": levels,
        "dashboardAtPhaseEnd": dashboard_at_phase_ends(telemetry),
        "acrossMeasuredPhases": {
            "successfulRequestsPerSecondMilliRange": _range(all_rates),
            "successfulRequestsPerSecondSpreadMilli": max(all_rates) - min(all_rates),
            "higherLoadRuntimeCpuMinusBaselineMillicoresRange": _range(
                [
                    phase["runtimeCpu"]["minusBaselineMillicores"]
                    for phase in phases
                    if phase["role"] != ROLE_BASELINE
                ]
            ),
            "largestBetweenRunsRateDifferenceMilli": max(
                level["betweenRunsRateDifferenceMilli"] for level in levels
            ),
            "baselineRuntimeCpuMillicoresRange": _range(baseline_runtime_cpu),
            "requests": sum(phase["requests"]["dispatched"] for phase in phases),
            "unsuccessful": sum(phase["requests"]["unsuccessful"] for phase in phases),
        },
        "method": [
            "Latency percentiles and rates are copied from the record, which takes them from the raw sets: nearest-rank over successful requests, and rates in thousandths per second over each phase's own window, truncated rather than rounded.",
            "A ratio to baseline divides a phase's figure by the same run's c1 figure, in thousandths, rounded half up.",
            "A completion gap is the time between successive completions inside one phase, where a completion is the request's dispatch offset plus its latency, both from the phase's start.",
            "A collector gauge's maximum is the largest reading at a 15-second range step inside the phase window. The collector scrapes every 30 seconds, so a gauge can miss a shorter excursion.",
            "A dashboard reading is the panel's own expression evaluated at a phase end, in milliseconds or thousandths per second, rounded half up. Its five-minute window covers earlier phases too; a panel with no row reads null.",
            "The API input-token counter is read at the same scheduled moments as the record's reconciled counters. Where it is absent before the first run, it is read as zero only when the record read the API output-token counter the same way, on the assumption that both directions of that counter family appear with the first completed request.",
            "The runtime prompt-token counter, which the record does not read at those moments, is the last 15-second range-step reading at or before a run's launch, and at or before the next run's launch or the final settle.",
        ],
    }
    refuse_private(dumps(findings), "findings")
    return findings
