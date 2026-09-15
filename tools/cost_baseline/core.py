"""The V1 cost baseline: estimated cost records taken from committed measured samples.

[ADR 0014](../../docs/architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md)
D3 states how a usage value is taken from the committed samples of a declared
experiment. Until this module, nothing applied it: every usage value in a calculation
input was typed in by hand. This module is the reader. For each run of one committed
performance scenarios record it writes a `CostCalculationInput` whose every usage
value is computed here from the record's committed inputs, and hands that input,
unchanged, to `tools.cost_calculation`.

It refuses to start unless the performance record regenerates byte for byte from its
committed inputs (`tools.performance_findings.checked_record`), is `local-real-cpu`
evidence, and passed every one of its own checks. So each value below is traceable to
the same raw evidence the record is, and the input names that record by digest.

The rules, as D3 states them:

- the **window** is placed by the samples' host instants. It opens on the last sample
  taken at or before the run's first phase starts and closes on the first sample taken
  at or after its last phase ends, so the samples bound it exactly and cover it end to
  end;
- **processor seconds** are the increase of each pod's cumulative cgroup counter
  between those two samples, summed over the workload's pods. A counter that falls
  between consecutive samples inside the window has reset, and the value is null with
  the reason `input-conflict`; no reset is stitched;
- **memory byte-seconds** are each pod's working-set bytes integrated trapezoidally
  between consecutive samples inside the window, summed over its pods. Because the
  window's ends are samples, nothing is extrapolated;
- **requests and tokens** are the counts of the run's raw records, every one of which
  must lie inside the window. A count the record's reconciliation shows disagreeing
  with the collector's counter is null with `input-conflict`;
- **accelerator seconds** are not applicable: the release reserves no device.

What the tool does not decide is also stated in what it writes. The workload is the
request path, the API and runtime pods. The release's collector is platform overhead,
which the method's shared-cost rule makes environment cost, so it is not listed and
its measured use lands on the unallocated line, where the derivation record reports
it beside the node's use outside the release and the capacity nobody used.

Nothing here contacts anything, and nothing here makes a figure publishable: the
only committed rate card is synthetic, so every record has confidence `none`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

import yaml

from tools.cost_calculation import core as calculation
from tools.llm_load import core as load
from tools.performance_findings.core import (
    FindingsError,
    RecordInputs,
    checked_record,
    read_inputs,
)
from tools.performance_scenarios.core import (
    REPO_ROOT,
    Descriptor,
    ScenarioError,
    dumps,
    file_digest,
    read_samples_jsonl,
    refuse_private,
    text_digest,
)

SCHEMA_VERSION = "inferops.io/v1alpha1"
DERIVATION_KIND = "CostBaselineDerivation"
EVIDENCE_CLASS = "local-real-cpu"
EVIDENCE_ROOT = "docs/proof/"
PRICE_SOURCE_ID = "synthetic-illustrative-v1"
BASIS = "estimated"

#: The values file the release was installed from; its digest must match the one the
#: record's environment captured as executed, or the owner it declares is not trusted.
VALUES_FILE = "charts/inferops-llm/ci/real-values.yaml"

#: Release pods on the request path, whose use is the workload's.
WORKLOAD_ROLES = ("api", "runtime")
#: Release pods that are platform overhead: environment cost, never spread.
PLATFORM_ROLES = ("collector",)
ROLES = (*WORKLOAD_ROLES, *PLATFORM_ROLES)

#: Collector labels an identity is observed from, and the record field each fills.
IDENTITY_LABELS = (
    ("inferops_workload_id", "workloadId"),
    ("inferops_model_id", "modelId"),
    ("inferops_runtime_id", "runtimeId"),
    ("deployment_environment", "environment"),
)

#: The record's own checks the derivation depends on. Each must have passed.
REQUIRED_CHECKS = (
    "every-deployment-available",
    "same-pods-throughout",
    "zero-container-restarts",
    "counters-reconcile-with-raw-records",
    "resource-samples-cover-every-phase",
)
CHECK_REQUESTS = "api-requests-equal-dispatched"
CHECK_OUTPUT_TOKENS = (
    "api-output-tokens-equal-recorded",
    "runtime-output-tokens-equal-recorded",
)

INPUT_CONFLICT = "input-conflict"
NANOSECONDS = 10**9
MILLISECONDS = 1000

BOUNDARY = (
    "Usage values taken from one committed performance record's samples and raw "
    "records under ADR 0014 D3, and the estimated cost records the committed "
    "calculation produces from them. The use is measured on one local host; every "
    "price is from the synthetic rate card, so no amount here is what anything costs, "
    "and none is a bill, an allocation, or a published cost figure."
)


class CostBaselineError(RuntimeError):
    """The evidence a baseline is taken from is not what ADR 0014 D3 requires."""


class CostBaselineRefused(CostBaselineError):
    """Evidence a baseline may not be taken from, refused before anything is written."""


# --------------------------------------------------------------------------
# Small readers
# --------------------------------------------------------------------------


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CostBaselineError(f"'{field}' must be an object")
    return cast(dict[str, Any], value)


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise CostBaselineError(f"'{field}' must be a list")
    return value


def _integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise CostBaselineError(f"'{field}' must be an integer")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CostBaselineError(f"'{field}' must be a non-empty string")
    return value


def exact_decimal(value: Fraction, field: str) -> str:
    """An exact non-negative rational as a decimal string, never rounded.

    Every quantity here is a count of nanoseconds, bytes, or milliseconds divided by a
    power of ten or two, so it terminates. One that does not is refused rather than
    rounded, because a rounded usage value is a second rounding the method forbids.
    """
    if value < 0:
        raise CostBaselineError(f"{field} is negative")
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise CostBaselineError(f"{field} has no exact decimal form")
    places = max(twos, fives)
    scaled = value * 10**places
    digits = str(scaled.numerator // scaled.denominator)
    if places == 0:
        return digits
    digits = digits.rjust(places + 1, "0")
    return f"{digits[:-places]}.{digits[-places:]}".rstrip("0").rstrip(".")


def instant(epoch_ms: int) -> str:
    """A host millisecond instant as RFC 3339 in UTC with a Z, at millisecond precision."""
    moment = datetime.fromtimestamp(epoch_ms // MILLISECONDS, tz=UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{epoch_ms % MILLISECONDS:03d}Z"


# --------------------------------------------------------------------------
# The evidence
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Sources:
    """A checked performance record, its parsed inputs, and where it is committed."""

    record_ref: str
    record_sha256: str
    record: Mapping[str, Any]
    environment: Mapping[str, Any]
    telemetry: Mapping[str, Any]
    samples: Sequence[Mapping[str, Any]]
    raw_sets: Mapping[str, load.RawSet]
    values_text: str


def _repository_path(path: Path, repo_root: Path) -> str:
    try:
        relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as error:
        raise CostBaselineRefused(
            "the performance record is not inside this repository"
        ) from error
    if not relative.startswith(EVIDENCE_ROOT):
        raise CostBaselineRefused(
            f"the performance record is not committed evidence under {EVIDENCE_ROOT}"
        )
    return relative


def read_sources(
    descriptor: Descriptor,
    record_dir: Path,
    record_prefix: str,
    *,
    repo_root: Path = REPO_ROOT,
) -> Sources:
    """The record and its inputs, refused unless they regenerate and passed every check."""
    try:
        inputs: RecordInputs = read_inputs(record_dir, record_prefix)
        record = checked_record(descriptor, inputs, repo_root=repo_root)
    except (FindingsError, ScenarioError, load.LoadError) as error:
        raise CostBaselineRefused(
            f"the performance record cannot be read from: {error}"
        ) from error
    record_ref = _repository_path(record_dir / inputs.record_name, repo_root)
    if record.get("evidenceClass") != EVIDENCE_CLASS:
        raise CostBaselineRefused(
            f"the performance record is '{record.get('evidenceClass')}' evidence; a "
            f"baseline is taken only from '{EVIDENCE_CLASS}' evidence"
        )
    passed = {
        _string(check.get("checkId"), "checkId"): check.get("passed")
        for check in (
            _object(item, "check") for item in _list(record.get("checks"), "checks")
        )
    }
    for check_id in REQUIRED_CHECKS:
        if passed.get(check_id) is not True:
            raise CostBaselineRefused(
                f"the performance record's check '{check_id}' did not pass; usage is not "
                "taken from a run whose own checks failed"
            )
    record_inputs = _object(record.get("inputs"), "inputs")
    if record_inputs.get("resourceSamples") != text_digest(inputs.samples_text):
        raise CostBaselineRefused(
            "the resource samples are not the ones the performance record names"
        )
    try:
        values_text = (repo_root / VALUES_FILE).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise CostBaselineRefused(f"'{VALUES_FILE}' is unreadable") from error
    executed = _object(
        _object(
            _object(record.get("environment"), "environment").get("repository"),
            "repository",
        ).get("executedFiles"),
        "executedFiles",
    )
    if executed.get(VALUES_FILE) != file_digest(repo_root / VALUES_FILE):
        raise CostBaselineRefused(
            f"'{VALUES_FILE}' is not the file the experiment executed; the owner it "
            "declares cannot be attributed to the run"
        )
    # The same texts were parsed once already, inside the regeneration check. They are
    # parsed again with the same readers, and still inside a refusal, so that a parse
    # failure here is never a traceback even if the two call sites drift apart.
    try:
        refuse_private(values_text, "values file")
        samples = read_samples_jsonl(inputs.samples_text)
        raw_sets = {
            name: load.parse_raw(text, repo_root=repo_root)
            for name, text in sorted(inputs.raw_texts.items())
        }
        environment = _object(json.loads(inputs.environment_text), "environment")
        telemetry = _object(json.loads(inputs.telemetry_text), "telemetry")
    except (ScenarioError, load.LoadError, json.JSONDecodeError) as error:
        raise CostBaselineRefused(
            f"the performance record's inputs cannot be parsed: {error}"
        ) from error
    return Sources(
        record_ref=record_ref,
        record_sha256=text_digest(inputs.record_text),
        record=record,
        environment=environment,
        telemetry=telemetry,
        samples=samples,
        raw_sets=raw_sets,
        values_text=values_text.replace("\r\n", "\n"),
    )


# --------------------------------------------------------------------------
# ADR 0014 D3, applied
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SampleWindow:
    """The samples that bound a load span, and every sample between them."""

    samples: tuple[Mapping[str, Any], ...]
    load_start_ms: int
    load_end_ms: int

    @property
    def start_ms(self) -> int:
        return _integer(self.samples[0]["hostEpochMs"], "hostEpochMs")

    @property
    def end_ms(self) -> int:
        return _integer(self.samples[-1]["hostEpochMs"], "hostEpochMs")

    @property
    def seconds(self) -> Fraction:
        return Fraction(self.end_ms - self.start_ms, MILLISECONDS)

    @property
    def node_clock_seconds(self) -> Fraction:
        return Fraction(
            _integer(self.samples[-1]["nodeClockNs"], "nodeClockNs")
            - _integer(self.samples[0]["nodeClockNs"], "nodeClockNs"),
            NANOSECONDS,
        )


def sample_window(
    samples: Sequence[Mapping[str, Any]], load_start_ms: int, load_end_ms: int
) -> SampleWindow:
    """The window the samples bound: last at or before the start, first at or after the end."""
    if load_end_ms <= load_start_ms:
        raise CostBaselineError("a load span must end after it starts")
    instants = [
        _integer(sample.get("hostEpochMs"), "hostEpochMs") for sample in samples
    ]
    if any(later < earlier for earlier, later in pairwise(instants)):
        raise CostBaselineError("the resource samples are not in time order")
    before = [index for index, at in enumerate(instants) if at <= load_start_ms]
    after = [index for index, at in enumerate(instants) if at >= load_end_ms]
    if not before or not after:
        raise CostBaselineRefused(
            "the samples do not cover the load span end to end: no sample was taken "
            f"{'at or before its start' if not before else 'at or after its end'}"
        )
    first, last = before[-1], after[0]
    return SampleWindow(
        samples=tuple(samples[first : last + 1]),
        load_start_ms=load_start_ms,
        load_end_ms=load_end_ms,
    )


def _reading(sample: Mapping[str, Any], role: str, key: str) -> int:
    pods = _object(sample.get("pods"), "pods")
    value = _object(pods.get(role), f"pods.{role}").get(key)
    if value is None:
        raise CostBaselineRefused(
            f"a sample inside the window has no {key} reading for '{role}'; a missing "
            "reading is not interpolated"
        )
    return _integer(value, f"pods.{role}.{key}")


def pod_cpu_seconds(window: SampleWindow, role: str) -> Fraction | None:
    """The counter's increase between the bounding samples; None when it reset inside."""
    readings = [_reading(sample, role, "cpuNs") for sample in window.samples]
    if any(later < earlier for earlier, later in pairwise(readings)):
        return None
    return Fraction(readings[-1] - readings[0], NANOSECONDS)


def pod_memory_byte_seconds(window: SampleWindow, role: str) -> Fraction:
    """Working-set bytes integrated trapezoidally over consecutive samples, on host time."""
    total = Fraction(0)
    for earlier, later in pairwise(window.samples):
        elapsed_ms = _integer(later["hostEpochMs"], "hostEpochMs") - _integer(
            earlier["hostEpochMs"], "hostEpochMs"
        )
        heights = _reading(earlier, role, "memoryWorkingSetBytes") + _reading(
            later, role, "memoryWorkingSetBytes"
        )
        total += Fraction(elapsed_ms * heights, 2 * MILLISECONDS)
    return total


def node_cpu_seconds(window: SampleWindow) -> Fraction:
    readings = [
        _integer(_object(sample.get("node"), "node").get("cpuNs"), "node.cpuNs")
        for sample in window.samples
    ]
    if any(later < earlier for earlier, later in pairwise(readings)):
        raise CostBaselineRefused(
            "the node's processor counter reset inside the window"
        )
    return Fraction(readings[-1] - readings[0], NANOSECONDS)


def node_memory_byte_seconds(window: SampleWindow) -> Fraction:
    total = Fraction(0)
    for earlier, later in pairwise(window.samples):
        elapsed_ms = later["hostEpochMs"] - earlier["hostEpochMs"]
        heights = _integer(
            _object(earlier.get("node"), "node").get("memoryWorkingSetBytes"),
            "node memory",
        ) + _integer(
            _object(later.get("node"), "node").get("memoryWorkingSetBytes"),
            "node memory",
        )
        total += Fraction(elapsed_ms * heights, 2 * MILLISECONDS)
    return total


@dataclass(frozen=True, slots=True)
class RunTraffic:
    requests: int
    successful: int
    input_tokens: int
    output_tokens: int
    first_dispatch_ms: int
    last_completion_ms: int


def run_traffic(raw: load.RawSet, window: SampleWindow) -> RunTraffic:
    """Every raw record of the run, placed on host time and required inside the window."""
    origin = raw.header.get("startedAtEpochMs")
    if not isinstance(origin, int) or isinstance(origin, bool):
        raise CostBaselineRefused(
            "the raw record set carries no startedAtEpochMs, so its requests cannot be placed"
        )
    phases = {phase.level_id: phase for phase in raw.phases}
    dispatches: list[int] = []
    completions: list[int] = []
    input_tokens = output_tokens = successful = 0
    for request in raw.records:
        phase = phases.get(request.level_id)
        if phase is None:
            raise CostBaselineError(
                f"request {request.sequence} names a phase the raw set does not hold"
            )
        dispatched = origin + phase.started_offset_ms + request.dispatch_offset_ms
        dispatches.append(dispatched)
        completions.append(dispatched + request.latency_ms)
        if request.outcome == load.OUTCOME_SUCCESS:
            if request.input_tokens is None or request.output_tokens is None:
                raise CostBaselineRefused(
                    f"successful request {request.sequence} carries no token counts"
                )
            successful += 1
            input_tokens += request.input_tokens
            output_tokens += request.output_tokens
    if not dispatches:
        raise CostBaselineRefused("the run holds no request")
    if min(dispatches) < window.start_ms or max(completions) > window.end_ms:
        raise CostBaselineRefused(
            "a request of the run lies outside the window its samples bound"
        )
    return RunTraffic(
        requests=len(raw.records),
        successful=successful,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        first_dispatch_ms=min(dispatches),
        last_completion_ms=max(completions),
    )


# --------------------------------------------------------------------------
# Identity, declaration, and capacity
# --------------------------------------------------------------------------


def observed_identity(telemetry: Mapping[str, Any], values_text: str) -> dict[str, str]:
    """Identity from the collector's own labels, and the owner from the executed values."""
    seen: dict[str, set[str]] = {label: set() for label, _ in IDENTITY_LABELS}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            labels = node.get("labels")
            if isinstance(labels, dict):
                for label in seen:
                    if isinstance(labels.get(label), str):
                        seen[label].add(labels[label])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(telemetry)
    identity: dict[str, str] = {}
    for label, field in IDENTITY_LABELS:
        values = sorted(seen[label])
        if len(values) != 1:
            raise CostBaselineRefused(
                f"the collector's series carry {len(values)} value(s) for '{label}'; an "
                "identity is taken only from a label with exactly one"
            )
        identity[field] = values[0]
    try:
        values = yaml.safe_load(values_text)
    except yaml.YAMLError as error:
        raise CostBaselineRefused(f"'{VALUES_FILE}' is not YAML") from error
    ownership = _object(_object(values, "values").get("ownership"), "ownership")
    identity["ownerId"] = _string(ownership.get("owner"), "ownership.owner")
    declared = _object(_object(values, "values").get("telemetry"), "telemetry").get(
        "deploymentEnvironment"
    )
    if declared != identity["environment"]:
        raise CostBaselineRefused(
            "the environment the collector observed is not the one the executed values declare"
        )
    if ownership.get("workloadId") != identity["workloadId"]:
        raise CostBaselineRefused(
            "the workload the collector observed is not the one the executed values declare"
        )
    return identity


def _container_requests(
    workload: Mapping[str, Any], role: str
) -> tuple[Fraction, Fraction]:
    cores = Fraction(0)
    memory = Fraction(0)
    for container in _list(workload.get("containers"), f"{role}.containers"):
        requests = _object(
            _object(_object(container, "container").get("resources"), "resources").get(
                "requests"
            ),
            f"{role} requests",
        )
        cores += calculation.parse_quantity(requests.get("cpu"), f"{role} cpu request")
        memory += calculation.parse_quantity(
            requests.get("memory"), f"{role} memory request"
        )
    return cores, memory


def workload_declaration(environment: Mapping[str, Any]) -> dict[str, Any]:
    """The request path's reservation per replica: the API and runtime pods' requests summed.

    A declaration is one pod shape times a replica count. The request path is two
    deployments, so it is written as one replica of both, which holds only while
    both run the same number of replicas; a release where they differ is refused.
    """
    workloads = _object(environment.get("workloads"), "workloads")
    replicas: set[int] = set()
    cores = Fraction(0)
    memory = Fraction(0)
    for role in WORKLOAD_ROLES:
        workload = _object(workloads.get(role), f"workloads.{role}")
        desired = _integer(workload.get("desiredReplicas"), f"{role}.desiredReplicas")
        if workload.get("availableReplicas") != desired:
            raise CostBaselineRefused(
                f"'{role}' did not have its desired replicas available"
            )
        replicas.add(desired)
        role_cores, role_memory = _container_requests(workload, role)
        cores += role_cores
        memory += role_memory
    if len(replicas) != 1:
        raise CostBaselineRefused(
            "the API and runtime run different replica counts, so the request path has no "
            "single pod shape to declare"
        )
    if memory.denominator != 1:
        raise CostBaselineError("a memory request is not a whole number of bytes")
    return {
        "cpuRequest": f"{exact_decimal(cores * 1000, 'cpu request')}m",
        "memoryRequest": str(memory.numerator),
        "acceleratorType": "none",
        "acceleratorCount": 0,
        "replicas": replicas.pop(),
    }


def node_capacity(environment: Mapping[str, Any]) -> dict[str, Any]:
    allocatable = _object(
        _object(environment.get("node"), "node").get("allocatable"), "node.allocatable"
    )
    cores = calculation.parse_quantity(allocatable.get("cpu"), "node allocatable cpu")
    gibibytes = calculation.memory_gibibytes(
        allocatable.get("memory"), "node allocatable memory"
    )
    return {
        "cpuCores": exact_decimal(cores, "node cores"),
        "memoryGibibytes": exact_decimal(gibibytes, "node gibibytes"),
        "acceleratorDevices": 0,
    }


# --------------------------------------------------------------------------
# The baseline
# --------------------------------------------------------------------------


def _reconciled(run: Mapping[str, Any], check_ids: Sequence[str]) -> bool:
    rows = {
        _string(row.get("checkId"), "checkId"): row
        for row in (
            _object(item, "reconciliation")
            for item in _list(run.get("reconciliation"), "reconciliation")
        )
    }
    return all(rows.get(check_id, {}).get("agrees") is True for check_id in check_ids)


def _run_span(run: Mapping[str, Any]) -> tuple[int, int]:
    phases = [_object(phase, "phase") for phase in _list(run.get("phases"), "phases")]
    if not phases:
        raise CostBaselineError("a run holds no phase")
    return (
        min(_integer(phase.get("startEpochMs"), "startEpochMs") for phase in phases),
        max(_integer(phase.get("endEpochMs"), "endEpochMs") for phase in phases),
    )


def _record_id(identity: Mapping[str, str], repetition: int) -> str:
    return f"baseline-run-{repetition}-{identity['workloadId']}"


def _millicores(seconds: Fraction, window: Fraction) -> int:
    return int(seconds * 1000 / window)


def derive_run(
    sources: Sources, run: Mapping[str, Any], identity: Mapping[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One run's calculation input and the derivation that explains every value in it."""
    repetition = _integer(run.get("repetition"), "repetition")
    raw_name = _string(run.get("rawFile"), "rawFile")
    raw = sources.raw_sets.get(raw_name)
    if raw is None:
        raise CostBaselineError(f"the raw record set '{raw_name}' was not read")
    load_start, load_end = _run_span(run)
    window = sample_window(sources.samples, load_start, load_end)
    traffic = run_traffic(raw, window)

    pod_cpu = {role: pod_cpu_seconds(window, role) for role in ROLES}
    pod_memory = {role: pod_memory_byte_seconds(window, role) for role in ROLES}
    workload_cpu: Fraction | None = Fraction(0)
    for role in WORKLOAD_ROLES:
        value = pod_cpu[role]
        workload_cpu = (
            None if value is None or workload_cpu is None else workload_cpu + value
        )
    workload_memory = sum((pod_memory[role] for role in WORKLOAD_ROLES), Fraction(0))

    unavailable: dict[str, str] = {}
    if workload_cpu is None:
        unavailable["cpu-seconds"] = INPUT_CONFLICT
    requests: int | None = traffic.requests
    if not _reconciled(run, (CHECK_REQUESTS,)):
        requests = None
        unavailable["requests"] = INPUT_CONFLICT
    output_tokens: int | None = traffic.output_tokens
    if not _reconciled(run, CHECK_OUTPUT_TOKENS):
        output_tokens = None
        unavailable["output-tokens"] = INPUT_CONFLICT

    record_id = _record_id(identity, repetition)
    capacity = node_capacity(sources.environment)
    document: dict[str, Any] = {
        "schemaVersion": calculation.SCHEMA_VERSION,
        "kind": calculation.INPUT_KIND,
        "classification": EVIDENCE_CLASS,
        "usageEvidence": {"path": sources.record_ref, "sha256": sources.record_sha256},
        "warning": (
            f"Measured use of run {repetition} of a declared local experiment, derived by "
            "tools/cost_baseline from the committed samples and raw records under ADR 0014 "
            "D3 and not typed in. Priced from the synthetic rate card, so the amounts are "
            "economically meaningless and no figure here is published."
        ),
        "environmentId": identity["environment"],
        "basis": BASIS,
        "priceSourceId": PRICE_SOURCE_ID,
        "window": {"start": instant(window.start_ms), "end": instant(window.end_ms)},
        "capacity": capacity,
        "prerequisites": [],
        "workloads": [
            {
                "recordId": record_id,
                "identity": {
                    "workloadId": identity["workloadId"],
                    "ownerId": identity["ownerId"],
                    "environment": identity["environment"],
                    "modelId": identity["modelId"],
                    "runtimeId": identity["runtimeId"],
                },
                "declaration": workload_declaration(sources.environment),
                "presentForWholeWindow": True,
                "shapeChangedInWindow": False,
                "usage": {
                    "requests": requests,
                    "inputTokens": traffic.input_tokens,
                    "outputTokens": output_tokens,
                    "cpuSeconds": None
                    if workload_cpu is None
                    else exact_decimal(workload_cpu, "cpu seconds"),
                    "memoryByteSeconds": exact_decimal(
                        workload_memory, "memory byte-seconds"
                    ),
                    "acceleratorSeconds": None,
                },
                "unavailable": dict(sorted(unavailable.items())),
            }
        ],
    }

    capacity_core_seconds = Fraction(capacity["cpuCores"]) * window.seconds
    capacity_byte_seconds = (
        Fraction(capacity["memoryGibibytes"]) * 2**30 * window.seconds
    )
    node_cpu = node_cpu_seconds(window)
    node_memory = node_memory_byte_seconds(window)
    release_cpu = (
        None
        if any(pod_cpu[role] is None for role in ROLES)
        else sum((cast(Fraction, pod_cpu[role]) for role in ROLES), Fraction(0))
    )
    release_memory = sum((pod_memory[role] for role in ROLES), Fraction(0))

    def optional(value: Fraction | None, field: str) -> str | None:
        return None if value is None else exact_decimal(value, field)

    gaps = [
        later["hostEpochMs"] - earlier["hostEpochMs"]
        for earlier, later in pairwise(window.samples)
    ]
    phase_runtime = [
        _integer(
            _object(_object(phase, "phase").get("resources"), "resources")[
                "cpuMillicores"
            ]["runtime"],
            "runtime millicores",
        )
        for phase in _list(run.get("phases"), "phases")
    ]
    derivation: dict[str, Any] = {
        "repetition": repetition,
        "rawFile": raw_name,
        "recordId": record_id,
        "window": {
            "start": document["window"]["start"],
            "end": document["window"]["end"],
            "startEpochMs": window.start_ms,
            "endEpochMs": window.end_ms,
            "hostSeconds": exact_decimal(window.seconds, "host seconds"),
            "nodeClockSeconds": exact_decimal(
                window.node_clock_seconds, "node seconds"
            ),
            "loadStartEpochMs": load_start,
            "loadEndEpochMs": load_end,
            "openedBeforeLoadMs": load_start - window.start_ms,
            "closedAfterLoadMs": window.end_ms - load_end,
            "samples": len(window.samples),
            "largestSampleGapMs": max(gaps),
            "longestSampleReadMs": max(
                _integer(sample.get("hostReadMs"), "hostReadMs")
                for sample in window.samples
            ),
        },
        "pods": {
            role: {
                "attributedTo": "workload" if role in WORKLOAD_ROLES else "unallocated",
                "cpuSeconds": optional(pod_cpu[role], f"{role} cpu seconds"),
                "counterReset": pod_cpu[role] is None,
                "memoryByteSeconds": exact_decimal(pod_memory[role], f"{role} memory"),
            }
            for role in ROLES
        },
        "traffic": {
            "requests": traffic.requests,
            "successful": traffic.successful,
            "inputTokens": traffic.input_tokens,
            "outputTokens": traffic.output_tokens,
            "firstDispatchEpochMs": traffic.first_dispatch_ms,
            "lastCompletionEpochMs": traffic.last_completion_ms,
            "requestsReconciled": _reconciled(run, (CHECK_REQUESTS,)),
            "outputTokensReconciled": _reconciled(run, CHECK_OUTPUT_TOKENS),
            "inputTokensReconciled": False,
        },
        "unallocatedUse": {
            "meaning": (
                "What the unallocated line holds, in the units it is priced from. Every "
                "row is measured except idle, which is capacity less the node's measured use."
            ),
            "processorSeconds": {
                "capacity": exact_decimal(
                    capacity_core_seconds, "capacity core-seconds"
                ),
                "workload": optional(workload_cpu, "workload core-seconds"),
                "releasePlatformPods": optional(
                    None
                    if any(pod_cpu[role] is None for role in PLATFORM_ROLES)
                    else sum(
                        (cast(Fraction, pod_cpu[role]) for role in PLATFORM_ROLES),
                        Fraction(0),
                    ),
                    "platform core-seconds",
                ),
                "nodeOutsideRelease": optional(
                    None if release_cpu is None else node_cpu - release_cpu,
                    "outside core-seconds",
                ),
                "idle": exact_decimal(
                    capacity_core_seconds - node_cpu, "idle core-seconds"
                ),
            },
            "memoryByteSeconds": {
                "capacity": exact_decimal(
                    capacity_byte_seconds, "capacity byte-seconds"
                ),
                "workload": exact_decimal(workload_memory, "workload byte-seconds"),
                "releasePlatformPods": exact_decimal(
                    sum((pod_memory[role] for role in PLATFORM_ROLES), Fraction(0)),
                    "platform byte-seconds",
                ),
                "nodeOutsideRelease": exact_decimal(
                    node_memory - release_memory, "outside byte-seconds"
                ),
                "notInWorkingSet": exact_decimal(
                    capacity_byte_seconds - node_memory, "free byte-seconds"
                ),
            },
        },
        "crossCheck": {
            "meaning": (
                "The runtime pod's average processor use over the window, beside the "
                "per-phase figures the performance record computed independently from "
                "the samples inside each phase."
            ),
            "runtimeWindowMillicores": None
            if pod_cpu["runtime"] is None
            else _millicores(pod_cpu["runtime"], window.seconds),
            "runtimePhaseMillicores": phase_runtime,
        },
    }
    return document, derivation


def derive_baseline(
    sources: Sources, method: Mapping[str, Any], prefix: str
) -> dict[str, str]:
    """Every file the baseline commits, by name, as the text it is committed as."""
    identity = observed_identity(sources.telemetry, sources.values_text)
    files: dict[str, str] = {}
    runs: list[dict[str, Any]] = []
    for run in (
        _object(item, "run") for item in _list(sources.record.get("runs"), "runs")
    ):
        if run.get("usable") is not True:
            raise CostBaselineRefused(
                f"run {run.get('repetition')} is not usable; no baseline is taken from it"
            )
        document, derivation = derive_run(sources, run, identity)
        result = calculation.calculate(document, method)
        stem = f"{prefix}baseline-run-{derivation['repetition']}"
        files[f"{stem}.input.json"] = calculation.dumps(document)
        files[f"{stem}.result.json"] = calculation.dumps(result)
        derivation["inputFile"] = f"{stem}.input.json"
        derivation["resultFile"] = f"{stem}.result.json"
        runs.append(derivation)
    record = _object(sources.record, "record")
    environment = _object(record.get("environment"), "environment")
    values_digest = text_digest(sources.values_text)
    derivation_document = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": DERIVATION_KIND,
        "boundary": BOUNDARY,
        "publishedCostFigure": False,
        "decisionRef": calculation.DECISION_REFS[1],
        "usageEvidence": {
            "path": sources.record_ref,
            "sha256": sources.record_sha256,
            "evidenceClass": record["evidenceClass"],
            "regeneratesFromInputs": True,
            "resourceSamplesSha256": _object(record.get("inputs"), "inputs")[
                "resourceSamples"
            ],
            "checksRequired": list(REQUIRED_CHECKS),
        },
        "environment": {
            "provider": environment.get("provider"),
            "kubernetesServerVersion": _object(
                environment.get("kubernetes"), "kubernetes"
            ).get("serverVersion"),
            "nodeAllocatable": _object(environment.get("node"), "node").get(
                "allocatable"
            ),
            "virtualMachineLogicalCpus": _object(
                environment.get("virtualMachine"), "virtualMachine"
            ).get("logicalCpus"),
            "cgroupVersion": _object(
                environment.get("virtualMachine"), "virtualMachine"
            ).get("cgroupVersion"),
        },
        "identity": {
            "observedFromCollectorLabels": [label for label, _ in IDENTITY_LABELS],
            "ownerFrom": VALUES_FILE,
            "valuesSha256": values_digest,
        },
        "attribution": {
            "workloadPods": list(WORKLOAD_ROLES),
            "platformPods": list(PLATFORM_ROLES),
            "rule": (
                "The request path's pods are the workload. The release's collector is "
                "platform overhead, which the method's shared-cost rule makes environment "
                "cost; it is not listed, so its use is on the unallocated line."
            ),
        },
        "rules": [
            "The window opens on the last sample at or before the run's first phase starts and closes on the first sample at or after its last phase ends, placed by host instant.",
            "Processor seconds are each workload pod's cgroup counter increase between the window's bounding samples, summed; a counter that falls inside the window is null with input-conflict.",
            "Memory byte-seconds are each workload pod's working set integrated trapezoidally between consecutive samples on host time, summed; nothing is extrapolated.",
            "Requests are every raw record of the run, and tokens are summed over its successful records; every request must lie inside the window, and a count its reconciliation shows disagreeing is null with input-conflict.",
            "Accelerator seconds are not applicable; no device is reserved.",
        ],
        "notDerived": [
            "Node capacity and the reservation are read from the environment the experiment captured, not from the samples.",
            "The owner is declared by the executed values file; the collector's series carry no owner label.",
            "No prerequisite is listed: the model cache claim's size is not in the record, so its storage is not priced.",
            "Input tokens are not reconciled against a counter by the record.",
        ],
        "runs": runs,
    }
    refuse_private(json.dumps(derivation_document), "derivation")
    files[f"{prefix}baseline-derivation.v1alpha1.json"] = dumps(derivation_document)
    return files
