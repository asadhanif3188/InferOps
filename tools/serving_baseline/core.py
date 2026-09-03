"""Register, execute, and summarize the local LLM serving baseline experiment.

The committed descriptor is the authority for what the baseline measures. Loading
it performs no I/O beyond reading committed files: the fixture, the generation
settings, and the execution envelope are cross-checked against the local
composition, the runtime profile, the runtime package, and the selected model's
source record, so a drift between any of them is a refusal at load time rather
than a number nobody can reproduce afterwards.

Execution is deliberately separate from every other operation here. It requires
explicit confirmation, composes the pinned runtime and the explicitly real
InferOps API through the existing local-composition workflow, discards a fixed
warm-up, sends one fixed request shape for a bounded count, and refuses any answer
carrying mock identity. Its output is labelled `local-real-cpu`.

Summarizing is a pure function of the raw record set. It reads no clock, contacts
nothing, and uses integer nearest-rank percentiles, so the same raw file always
produces the same summary. That is the property that lets a later change publish a
summary alongside the raw records it came from, and lets a reader regenerate one
from the other rather than trusting it.

Nothing here may publish a benchmark. The project boundaries forbid a throughput,
latency, or capacity claim drawn from V1, and every record this module writes
carries `productionBenchmark: false` for that reason.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import statistics
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from inferops.api.surface import (
    CHAT_COMPLETIONS_PATH,
    CORRELATION_ID_HEADER,
    EXTENSION_ADAPTER_KIND,
    EXTENSION_MEMBER,
    EXTENSION_MODEL_REF,
    REQUEST_ID_HEADER,
)
from tools.local_composition import (
    LocalComposition,
    load_composition,
    run_foreground,
)
from tools.model_acquisition import load_manifest
from tools.runtime_configuration import load_runtime_profile
from tools.runtime_packaging import (
    CommandRunner,
    RuntimePackage,
    SubprocessRunner,
    load_runtime_package,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_PATH = REPO_ROOT / "deploy/serving/baseline/local-baseline.v1.json"

EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_ID = "inferops-local-serving-baseline"
EXPECTED_EVIDENCE_CLASS = "local-real-cpu"
EXPECTED_EVIDENCE_LABEL = "local real runtime"
EXPECTED_CEILING = "C2"
EXPECTED_COMPOSITION_REF = "deploy/serving/local/composition.v1.json"
EXPECTED_BOUNDARIES_REF = "docs/architecture/project-boundaries.md"
EXPECTED_RESULT_DIRECTORY = Path(".cache/inferops/baseline")
EXPECTED_PERCENTILE_METHOD = "nearest-rank"
EXPECTED_PERCENTILES = (50, 95, 99)
ADAPTER_MOCK = "mock"

#: The ceiling on a measured phase. It is a floor on the descriptor rather than a
#: value read from it, so a longer run cannot be authorized by editing the record
#: that is supposed to bound it.
MAXIMUM_MEASURED_REQUESTS = 200

#: The ceiling on a raw result file this module reads back. A summary is computed
#: in memory, and an unbounded input file is how that stops being true.
MAXIMUM_RAW_RECORDS = 10_000

#: The outcome labels a raw record may carry. Every request lands on exactly one.
#: `refused` covers an answer the API returned that the success criteria reject;
#: `transport-error` covers a request that produced no answer at all. Collapsing
#: the two would make a runtime that refuses indistinguishable from one that died.
OUTCOME_SUCCESS = "success"
OUTCOME_REFUSED = "refused"
OUTCOME_TRANSPORT = "transport-error"

OUTCOMES = (OUTCOME_SUCCESS, OUTCOME_REFUSED, OUTCOME_TRANSPORT)

#: The phases a request belongs to. Only `measured` records reach a percentile;
#: warm-up latencies are recorded and then deliberately excluded, because a
#: distribution that includes a cold cache describes the cache.
PHASE_WARMUP = "warmup"
PHASE_MEASURED = "measured"

PHASES = (PHASE_WARMUP, PHASE_MEASURED)


class BaselineError(RuntimeError):
    """The baseline descriptor, a bounded step, or a raw record set failed."""


class BaselineRefused(BaselineError):
    """A precondition for a measured run was not satisfied."""


@dataclass(frozen=True, slots=True)
class Fixture:
    """The one request shape every baseline request sends, byte for byte."""

    fixture_id: str
    request_path: str
    model: str
    stream: bool
    messages: tuple[Mapping[str, str], ...]

    def body(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [dict(message) for message in self.messages],
            "stream": self.stream,
        }


@dataclass(frozen=True, slots=True)
class Experiment:
    """The committed baseline descriptor after every field has been validated."""

    schema_version: str
    experiment_id: str
    evidence_class: str
    evidence_label: str
    certification_ceiling: str
    production_benchmark: bool
    composition_ref: str
    boundaries_ref: str
    fixture: Fixture
    max_output_tokens: int
    temperature: float
    context_size_tokens: int
    parallel_slots: int
    warmup_requests: int
    measured_requests: int
    concurrency: int
    max_duration_seconds: int
    request_timeout_ms: int
    resource_sample_every_requests: int
    minimum_successful_requests: int
    maximum_failed_requests: int
    required_adapter_kind: str
    required_model_ref: str
    required_completion_status: int
    result_directory: Path
    raw_file: str
    summary_file: str
    raw_format: str
    summary_format: str
    percentile_method: str
    reported_percentiles: tuple[int, ...]

    @property
    def total_requests(self) -> int:
        return self.warmup_requests + self.measured_requests


@dataclass(frozen=True, slots=True)
class RequestRecord:
    """One request, as it is written to the raw result set."""

    sequence: int
    phase: str
    outcome: str
    status: int
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    adapter_kind: str | None
    model_ref: str | None
    error_code: str | None

    def document(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "phase": self.phase,
            "outcome": self.outcome,
            "status": self.status,
            "latencyMs": self.latency_ms,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "adapterKind": self.adapter_kind,
            "modelRef": self.model_ref,
            "errorCode": self.error_code,
        }


@dataclass(frozen=True, slots=True)
class ResourceSample:
    """One container resource observation, as the engine reported it."""

    sequence: int
    cpu_percent: float
    memory_bytes: int

    def document(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "cpuPercent": self.cpu_percent,
            "memoryBytes": self.memory_bytes,
        }


@dataclass(frozen=True, slots=True)
class Environment:
    """The sanitized host and provenance record a raw result set depends on."""

    operating_system: str
    release: str
    architecture: str
    processor_family: str
    logical_cpus: int
    total_memory_bytes: int | None
    free_disk_bytes: int | None
    python_version: str
    container_engine_version: str | None
    accelerator: str
    image_reference: str
    model_repository: str
    model_revision: str
    model_artifact_sha256: str
    runtime_source_revision: str

    def document(self) -> dict[str, Any]:
        return {
            "operatingSystem": self.operating_system,
            "release": self.release,
            "architecture": self.architecture,
            "processorFamily": self.processor_family,
            "logicalCpus": self.logical_cpus,
            "totalMemoryBytes": self.total_memory_bytes,
            "freeDiskBytes": self.free_disk_bytes,
            "pythonVersion": self.python_version,
            "containerEngineVersion": self.container_engine_version,
            "accelerator": self.accelerator,
            "imageReference": self.image_reference,
            "modelRepository": self.model_repository,
            "modelRevision": self.model_revision,
            "modelArtifactSha256": self.model_artifact_sha256,
            "runtimeSourceRevision": self.runtime_source_revision,
        }


@dataclass(frozen=True, slots=True)
class BaselineRun:
    """Everything one authorized execution produced, before it is summarized."""

    experiment_id: str
    evidence_class: str
    environment: Environment
    model_load_ms: int
    api_ready_ms: int
    records: tuple[RequestRecord, ...]
    samples: tuple[ResourceSample, ...]
    measured_window_ms: int


@dataclass(frozen=True, slots=True)
class PostResponse:
    """A status and parsed body from the loopback InferOps API."""

    status: int
    body: object | None = None


JsonPost = Callable[[str, Mapping[str, Any], Mapping[str, str], float], PostResponse]


# --------------------------------------------------------------------------
# Loading the committed descriptor
# --------------------------------------------------------------------------


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BaselineError(f"baseline field '{field}' must be an object")
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BaselineError(f"baseline field '{field}' must be a string")
    return value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise BaselineError(
            f"baseline field '{field}' must be an integer of at least {minimum}"
        )
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise BaselineError(f"baseline field '{field}' must be a boolean")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BaselineError(f"baseline field '{field}' must be a number")
    return float(value)


def _require_keys(record: Mapping[str, Any], field: str, expected: set[str]) -> None:
    if set(record) != expected:
        raise BaselineError(
            f"baseline field '{field}' has missing or unsupported members"
        )


def _messages(value: Any, field: str) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list) or not value:
        raise BaselineError(f"baseline field '{field}' must be a non-empty list")
    messages: list[Mapping[str, str]] = []
    for index, item in enumerate(value):
        message = _object(item, f"{field}[{index}]")
        _require_keys(message, f"{field}[{index}]", {"role", "content"})
        role = _string(message.get("role"), f"{field}[{index}].role")
        content = _string(message.get("content"), f"{field}[{index}].content")
        if role not in ("system", "user"):
            raise BaselineError(
                f"baseline field '{field}[{index}].role' must be system or user"
            )
        messages.append({"role": role, "content": content})
    return tuple(messages)


def _percentiles(value: Any, field: str) -> tuple[int, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, int) or isinstance(item, bool) or not 1 <= item <= 99
        for item in value
    ):
        raise BaselineError(f"baseline field '{field}' must list percentiles 1-99")
    return tuple(cast(list[int], value))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), "root")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BaselineError(
            "the baseline experiment descriptor is unreadable"
        ) from error


def load_experiment(path: Path = EXPERIMENT_PATH) -> Experiment:
    """Load and cross-check the baseline descriptor without performing any run."""
    record = _read_json(path)
    _require_keys(
        record,
        "root",
        {
            "schemaVersion",
            "experimentId",
            "evidenceClass",
            "evidenceLabel",
            "certificationCeiling",
            "productionBenchmark",
            "compositionRef",
            "boundariesRef",
            "fixture",
            "generation",
            "execution",
            "success",
            "results",
        },
    )
    fixture_record = _object(record.get("fixture"), "fixture")
    generation = _object(record.get("generation"), "generation")
    execution = _object(record.get("execution"), "execution")
    success = _object(record.get("success"), "success")
    results = _object(record.get("results"), "results")
    _require_keys(
        fixture_record,
        "fixture",
        {"fixtureId", "requestPath", "model", "stream", "messages"},
    )
    _require_keys(
        generation,
        "generation",
        {"maxOutputTokens", "temperature", "contextSizeTokens", "parallelSlots"},
    )
    _require_keys(
        execution,
        "execution",
        {
            "warmupRequests",
            "measuredRequests",
            "concurrency",
            "maxDurationSeconds",
            "requestTimeoutMs",
            "resourceSampleEveryRequests",
        },
    )
    _require_keys(
        success,
        "success",
        {
            "minimumSuccessfulRequests",
            "maximumFailedRequests",
            "requiredAdapterKind",
            "requiredModelRef",
            "requiredCompletionStatus",
        },
    )
    _require_keys(
        results,
        "results",
        {
            "directory",
            "rawFile",
            "summaryFile",
            "rawFormat",
            "summaryFormat",
            "percentileMethod",
            "reportedPercentiles",
        },
    )
    experiment = Experiment(
        schema_version=_string(record.get("schemaVersion"), "schemaVersion"),
        experiment_id=_string(record.get("experimentId"), "experimentId"),
        evidence_class=_string(record.get("evidenceClass"), "evidenceClass"),
        evidence_label=_string(record.get("evidenceLabel"), "evidenceLabel"),
        certification_ceiling=_string(
            record.get("certificationCeiling"), "certificationCeiling"
        ),
        production_benchmark=_boolean(
            record.get("productionBenchmark"), "productionBenchmark"
        ),
        composition_ref=_string(record.get("compositionRef"), "compositionRef"),
        boundaries_ref=_string(record.get("boundariesRef"), "boundariesRef"),
        fixture=Fixture(
            fixture_id=_string(fixture_record.get("fixtureId"), "fixture.fixtureId"),
            request_path=_string(
                fixture_record.get("requestPath"), "fixture.requestPath"
            ),
            model=_string(fixture_record.get("model"), "fixture.model"),
            stream=_boolean(fixture_record.get("stream"), "fixture.stream"),
            messages=_messages(fixture_record.get("messages"), "fixture.messages"),
        ),
        max_output_tokens=_integer(
            generation.get("maxOutputTokens"), "generation.maxOutputTokens"
        ),
        temperature=_number(generation.get("temperature"), "generation.temperature"),
        context_size_tokens=_integer(
            generation.get("contextSizeTokens"), "generation.contextSizeTokens"
        ),
        parallel_slots=_integer(
            generation.get("parallelSlots"), "generation.parallelSlots"
        ),
        warmup_requests=_integer(
            execution.get("warmupRequests"), "execution.warmupRequests"
        ),
        measured_requests=_integer(
            execution.get("measuredRequests"), "execution.measuredRequests"
        ),
        concurrency=_integer(execution.get("concurrency"), "execution.concurrency"),
        max_duration_seconds=_integer(
            execution.get("maxDurationSeconds"), "execution.maxDurationSeconds"
        ),
        request_timeout_ms=_integer(
            execution.get("requestTimeoutMs"), "execution.requestTimeoutMs"
        ),
        resource_sample_every_requests=_integer(
            execution.get("resourceSampleEveryRequests"),
            "execution.resourceSampleEveryRequests",
        ),
        minimum_successful_requests=_integer(
            success.get("minimumSuccessfulRequests"),
            "success.minimumSuccessfulRequests",
        ),
        maximum_failed_requests=_integer(
            success.get("maximumFailedRequests"),
            "success.maximumFailedRequests",
            minimum=0,
        ),
        required_adapter_kind=_string(
            success.get("requiredAdapterKind"), "success.requiredAdapterKind"
        ),
        required_model_ref=_string(
            success.get("requiredModelRef"), "success.requiredModelRef"
        ),
        required_completion_status=_integer(
            success.get("requiredCompletionStatus"),
            "success.requiredCompletionStatus",
        ),
        result_directory=Path(_string(results.get("directory"), "results.directory")),
        raw_file=_string(results.get("rawFile"), "results.rawFile"),
        summary_file=_string(results.get("summaryFile"), "results.summaryFile"),
        raw_format=_string(results.get("rawFormat"), "results.rawFormat"),
        summary_format=_string(results.get("summaryFormat"), "results.summaryFormat"),
        percentile_method=_string(
            results.get("percentileMethod"), "results.percentileMethod"
        ),
        reported_percentiles=_percentiles(
            results.get("reportedPercentiles"), "results.reportedPercentiles"
        ),
    )
    _validate(experiment, load_composition())
    return experiment


def _validate(experiment: Experiment, composition: LocalComposition) -> None:
    profile = load_runtime_profile()
    package = load_runtime_package()
    manifest = load_manifest()
    if (
        experiment.schema_version != EXPECTED_SCHEMA
        or experiment.experiment_id != EXPECTED_ID
        or experiment.evidence_class != EXPECTED_EVIDENCE_CLASS
        or experiment.evidence_label != EXPECTED_EVIDENCE_LABEL
        or experiment.certification_ceiling != EXPECTED_CEILING
    ):
        raise BaselineError("the baseline experiment identity is unsupported")
    if experiment.production_benchmark:
        raise BaselineError(
            "the baseline may not declare itself a production benchmark"
        )
    if (
        experiment.composition_ref != EXPECTED_COMPOSITION_REF
        or experiment.boundaries_ref != EXPECTED_BOUNDARIES_REF
    ):
        raise BaselineError("the baseline references an unexpected document")
    if (
        experiment.fixture.request_path != CHAT_COMPLETIONS_PATH
        or experiment.fixture.stream
        or experiment.fixture.model != profile.platform_identifier
    ):
        raise BaselineError("the baseline fixture does not match the served model")
    if (
        experiment.max_output_tokens != profile.default_max_output_tokens
        or experiment.temperature != profile.default_temperature
        or experiment.context_size_tokens != profile.context_size_tokens
        or experiment.parallel_slots != profile.parallel_slots
    ):
        raise BaselineError("the baseline generation settings have drifted")
    if experiment.max_output_tokens != int(
        composition.environment["INFEROPS_MAX_OUTPUT_TOKENS"]
    ) or experiment.request_timeout_ms != int(
        composition.environment["INFEROPS_REQUEST_TIMEOUT_MS"]
    ):
        raise BaselineError("the baseline request envelope contradicts the composition")
    if experiment.concurrency != experiment.parallel_slots:
        raise BaselineError(
            "the baseline concurrency must equal the runtime's parallel slots"
        )
    if (
        experiment.measured_requests > MAXIMUM_MEASURED_REQUESTS
        or experiment.minimum_successful_requests != experiment.measured_requests
        or experiment.resource_sample_every_requests > experiment.measured_requests
    ):
        raise BaselineError("the baseline execution envelope is unsupported")
    # The duration bound is a stop condition, and a stop condition is only
    # meaningful between two lines. Below one full request timeout it fires
    # before any request can finish and the run measures nothing; above the whole
    # sequence's timeout budget it can never fire and is decorative.
    if not (
        experiment.request_timeout_ms
        <= experiment.max_duration_seconds * 1000
        <= (experiment.total_requests * experiment.request_timeout_ms)
        // experiment.concurrency
    ):
        raise BaselineError(
            "the baseline duration bound cannot stop this request sequence"
        )
    if (
        experiment.required_adapter_kind != composition.adapter_selection
        or experiment.required_adapter_kind == ADAPTER_MOCK
        or experiment.required_model_ref != profile.platform_identifier
        or experiment.required_completion_status != 200
    ):
        raise BaselineError("the baseline must require an explicitly real answer")
    if (
        experiment.result_directory != EXPECTED_RESULT_DIRECTORY
        or "/" in experiment.raw_file
        or "/" in experiment.summary_file
        or experiment.raw_format != "application/jsonl"
        or experiment.summary_format != "application/json"
        or experiment.percentile_method != EXPECTED_PERCENTILE_METHOD
        or experiment.reported_percentiles != EXPECTED_PERCENTILES
    ):
        raise BaselineError("the baseline result layout is unsupported")
    if package.image_reference != profile.image_reference:
        raise BaselineError("the baseline runtime pins disagree")
    if manifest.revision != composition.environment["INFEROPS_MODEL_REVISION"]:
        raise BaselineError(
            "the baseline model revision disagrees with the composition"
        )


# --------------------------------------------------------------------------
# Environment capture
# --------------------------------------------------------------------------


def _engine_version(package: RuntimePackage, runner: CommandRunner) -> str | None:
    try:
        result = runner.run(
            (package.engine, "version", "--format", "{{.Server.Version}}")
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    lines = result.stdout.strip().splitlines()
    return lines[0][:64] if lines else None


def total_memory_bytes() -> int | None:
    """The host's physical memory, or ``None`` where it cannot be read.

    Two mechanisms, because the baseline is expected to run on more than one kind
    of host and a memory figure missing from an environment record is a gap in
    every resource claim drawn from that run. Neither path guesses: a host that
    answers neither is recorded as unknown rather than as zero.
    """
    # `os.sysconf` exists only on POSIX, and the type stubs know it, so it is
    # reached through `getattr` rather than through a platform assertion this
    # module would then have to keep true.
    sysconf: Callable[[str], int] | None = getattr(os, "sysconf", None)
    if sysconf is not None:
        try:
            return int(sysconf("SC_PAGE_SIZE")) * int(sysconf("SC_PHYS_PAGES"))
        except (ValueError, OSError):
            pass
    try:
        import ctypes

        class _MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        kernel32 = getattr(ctypes, "windll", None)
        if kernel32 is None:
            return None
        if not kernel32.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullTotalPhys) or None
    except Exception:
        return None


def capture_environment(
    *,
    runner: CommandRunner | None = None,
    repo_root: Path = REPO_ROOT,
) -> Environment:
    """Record the host and the immutable pins a result set would depend on.

    Only non-identifying host properties are recorded. The machine's name, its
    user, its network identity, and every absolute path stay out, because an
    environment record is committed and a hostname is the thing that turns a
    measurement into a statement about somebody's laptop.
    """
    package = load_runtime_package()
    profile = load_runtime_profile()
    manifest = load_manifest()
    free_disk: int | None
    try:
        free_disk = shutil.disk_usage(repo_root).free
    except OSError:
        free_disk = None
    accelerator = (
        "none; CPU only"
        if profile.accelerator_kind == "none"
        else f"{profile.accelerator_kind} x{profile.accelerator_count}"
    )
    return Environment(
        operating_system=platform.system(),
        release=platform.release(),
        architecture=platform.machine(),
        processor_family=platform.machine() or "unknown",
        logical_cpus=os.cpu_count() or 0,
        total_memory_bytes=total_memory_bytes(),
        free_disk_bytes=free_disk,
        python_version=platform.python_version(),
        container_engine_version=_engine_version(
            package, runner or SubprocessRunner(timeout_seconds=30)
        ),
        accelerator=accelerator,
        image_reference=package.image_reference,
        model_repository=manifest.repository,
        model_revision=manifest.revision,
        model_artifact_sha256=manifest.sha256,
        runtime_source_revision=profile.source_revision,
    )


# --------------------------------------------------------------------------
# Resource sampling
# --------------------------------------------------------------------------

#: The suffixes a container engine uses in a `MemUsage` column. Longest first at
#: the comparison site, because `B` is a suffix of every one of the others.
MEMORY_UNITS: Mapping[str, int] = {
    "B": 1,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "KIB": 1024,
    "MIB": 1024**2,
    "GIB": 1024**3,
}


def parse_memory_bytes(value: str) -> int | None:
    """Parse the usage half of an engine `USAGE / LIMIT` column into bytes."""
    text = value.split("/", 1)[0].strip().upper()
    for suffix in sorted(MEMORY_UNITS, key=len, reverse=True):
        if text.endswith(suffix):
            try:
                return int(float(text[: -len(suffix)].strip()) * MEMORY_UNITS[suffix])
            except ValueError:
                return None
    return None


def sample_resources(
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    sequence: int,
) -> ResourceSample | None:
    """Observe the owned container's CPU and memory without changing it.

    A sample that cannot be taken is absent rather than zero. A zero here would be
    indistinguishable from an idle container and would silently understate the
    resource cost the baseline exists to record.
    """
    try:
        result = runner.run(
            (
                package.engine,
                "stats",
                "--no-stream",
                "--format",
                "{{.CPUPerc}}\t{{.MemUsage}}",
                package.container_name,
            )
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    lines = result.stdout.strip().splitlines()
    if not lines:
        return None
    parts = lines[0].split("\t")
    if len(parts) != 2:
        return None
    try:
        cpu_percent = float(parts[0].strip().rstrip("%"))
    except ValueError:
        return None
    memory_bytes = parse_memory_bytes(parts[1])
    if memory_bytes is None or cpu_percent < 0:
        return None
    return ResourceSample(
        sequence=sequence, cpu_percent=cpu_percent, memory_bytes=memory_bytes
    )


# --------------------------------------------------------------------------
# The measured request
# --------------------------------------------------------------------------


def json_post(
    url: str,
    body: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> PostResponse:
    """POST one fixture request to the loopback API and parse what came back."""
    payload = json.dumps(dict(body)).encode("utf-8")
    request = Request(url, data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            parsed: object = json.loads(response.read().decode("utf-8"))
            return PostResponse(response.status, parsed)
    except HTTPError as error:
        try:
            parsed = json.loads(error.read().decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            parsed = None
        return PostResponse(error.code, parsed)
    except (OSError, URLError, UnicodeError, json.JSONDecodeError) as error:
        raise BaselineError("the loopback InferOps API is unreachable") from error


def _identity(body: object) -> Mapping[str, Any]:
    """The extension members carrying adapter and model identity, if present.

    A completion carries them under the extension member and a canonical error
    carries them under `details`. Both are read, because a refusal's identity is
    exactly what decides whether a failed request came from the real runtime.
    """
    if not isinstance(body, dict):
        return {}
    extension = body.get(EXTENSION_MEMBER)
    if isinstance(extension, dict):
        return cast(dict[str, Any], extension)
    details = body.get("details")
    if isinstance(details, dict):
        return cast(dict[str, Any], details)
    return {}


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _usage(body: object) -> tuple[int | None, int | None]:
    if not isinstance(body, dict):
        return (None, None)
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return (None, None)
    return (_count(usage.get("prompt_tokens")), _count(usage.get("completion_tokens")))


def _error_code(body: object) -> str | None:
    if isinstance(body, dict):
        code = body.get("code")
        if isinstance(code, str):
            return code[:64]
    return None


def send_request(
    experiment: Experiment,
    composition: LocalComposition,
    *,
    sequence: int,
    phase: str,
    post: JsonPost = json_post,
    clock: Callable[[], float] = time.monotonic,
) -> RequestRecord:
    """Send one fixture request and retain only non-identifying observations.

    The completion text is never retained. The baseline records how long an answer
    took and how many tokens it carried; a committed transcript of what a model
    said is a different artifact with different rules.
    """
    if phase not in PHASES:
        raise BaselineError("a baseline request must be warm-up or measured")
    url = f"{composition.api_base_url}{experiment.fixture.request_path}"
    headers = {
        REQUEST_ID_HEADER: f"baseline-{experiment.fixture.fixture_id}-{sequence:04d}",
        CORRELATION_ID_HEADER: f"baseline-{experiment.experiment_id}",
    }
    started = clock()
    try:
        response = post(
            url,
            experiment.fixture.body(),
            headers,
            experiment.request_timeout_ms / 1000,
        )
    except BaselineError:
        return RequestRecord(
            sequence=sequence,
            phase=phase,
            outcome=OUTCOME_TRANSPORT,
            status=0,
            latency_ms=max(0, round((clock() - started) * 1000)),
            input_tokens=None,
            output_tokens=None,
            adapter_kind=None,
            model_ref=None,
            error_code=None,
        )
    latency_ms = max(0, round((clock() - started) * 1000))
    identity = _identity(response.body)
    adapter_kind = identity.get(EXTENSION_ADAPTER_KIND)
    model_ref = identity.get(EXTENSION_MODEL_REF)
    if adapter_kind == ADAPTER_MOCK:
        raise BaselineRefused(
            "the baseline received a mock answer and cannot record it as real"
        )
    input_tokens, output_tokens = _usage(response.body)
    success = (
        response.status == experiment.required_completion_status
        and adapter_kind == experiment.required_adapter_kind
        and model_ref == experiment.required_model_ref
    )
    return RequestRecord(
        sequence=sequence,
        phase=phase,
        outcome=OUTCOME_SUCCESS if success else OUTCOME_REFUSED,
        status=response.status,
        latency_ms=latency_ms,
        input_tokens=input_tokens if success else None,
        output_tokens=output_tokens if success else None,
        adapter_kind=adapter_kind if isinstance(adapter_kind, str) else None,
        model_ref=model_ref if isinstance(model_ref, str) else None,
        error_code=None if success else _error_code(response.body),
    )


# --------------------------------------------------------------------------
# The deterministic summary
# --------------------------------------------------------------------------


def percentile_ms(latencies: Sequence[int], percentile: int) -> int:
    """The nearest-rank percentile of a latency sample, in whole milliseconds.

    Nearest rank is chosen over interpolation because it returns a value that was
    actually observed. An interpolated P99 over thirty requests is a number no
    request produced, and a baseline whose headline figure is synthetic is the
    confusion the evidence classes exist to prevent.
    """
    if not 1 <= percentile <= 99:
        raise BaselineError("a reported percentile must be between 1 and 99")
    if not latencies:
        raise BaselineError("a percentile needs at least one observation")
    ordered = sorted(latencies)
    rank = -((-percentile * len(ordered)) // 100)
    return ordered[max(1, rank) - 1]


def summarize(experiment: Experiment, run: BaselineRun) -> dict[str, Any]:
    """Reduce one run's raw records to the summary, with no I/O and no clock.

    The same records always produce the same document. Warm-up records are counted
    and then excluded from every distribution; only the measured phase reaches a
    percentile. Rates are reported in thousandths of a unit per second as integers,
    because a float rate in a committed record differs between platforms and a
    figure that differs between platforms cannot be compared to itself.
    """
    measured = [record for record in run.records if record.phase == PHASE_MEASURED]
    warmup = [record for record in run.records if record.phase == PHASE_WARMUP]
    successes = [record for record in measured if record.outcome == OUTCOME_SUCCESS]
    latencies = [record.latency_ms for record in successes]
    failures = len(measured) - len(successes)
    outcomes = {
        outcome: sum(1 for record in measured if record.outcome == outcome)
        for outcome in OUTCOMES
    }
    output_tokens = [
        record.output_tokens for record in successes if record.output_tokens is not None
    ]
    input_tokens = [
        record.input_tokens for record in successes if record.input_tokens is not None
    ]
    window_ms = run.measured_window_ms
    latency: dict[str, Any] = (
        {
            f"p{percentile}Ms": percentile_ms(latencies, percentile)
            for percentile in experiment.reported_percentiles
        }
        if latencies
        else {f"p{p}Ms": None for p in experiment.reported_percentiles}
    )
    latency["minMs"] = min(latencies) if latencies else None
    latency["maxMs"] = max(latencies) if latencies else None
    latency["meanMs"] = round(statistics.fmean(latencies)) if latencies else None
    return {
        "schemaVersion": EXPECTED_SCHEMA,
        "experimentId": run.experiment_id,
        "evidenceClass": run.evidence_class,
        "evidenceLabel": EXPECTED_EVIDENCE_LABEL,
        "certificationCeiling": EXPECTED_CEILING,
        "productionBenchmark": False,
        "notABenchmark": (
            "Descriptive local measurement on one CPU host at concurrency "
            f"{experiment.concurrency}. It is not a production benchmark and no "
            "figure here may be published as one."
        ),
        "fixtureId": experiment.fixture.fixture_id,
        "percentileMethod": experiment.percentile_method,
        "environment": run.environment.document(),
        "startup": {
            "modelLoadMs": run.model_load_ms,
            "apiReadyMs": run.api_ready_ms,
        },
        "requests": {
            "warmup": len(warmup),
            "measured": len(measured),
            "successful": len(successes),
            "failed": failures,
            "outcomes": outcomes,
        },
        "latency": latency,
        "throughput": {
            "measuredWindowMs": window_ms,
            "requestsPerSecondMilli": (
                (len(successes) * 1_000_000) // window_ms if window_ms > 0 else None
            ),
            "outputTokensPerSecondMilli": (
                (sum(output_tokens) * 1_000_000) // window_ms
                if window_ms > 0 and output_tokens
                else None
            ),
        },
        "tokens": {
            "available": bool(output_tokens),
            "inputTotal": sum(input_tokens) if input_tokens else None,
            "outputTotal": sum(output_tokens) if output_tokens else None,
            "outputMin": min(output_tokens) if output_tokens else None,
            "outputMax": max(output_tokens) if output_tokens else None,
        },
        "resources": {
            "samples": len(run.samples),
            "cpuPercentMax": (
                max(sample.cpu_percent for sample in run.samples)
                if run.samples
                else None
            ),
            "memoryBytesMax": (
                max(sample.memory_bytes for sample in run.samples)
                if run.samples
                else None
            ),
        },
        "successCriteria": {
            "minimumSuccessfulRequests": experiment.minimum_successful_requests,
            "maximumFailedRequests": experiment.maximum_failed_requests,
            "met": (
                len(successes) >= experiment.minimum_successful_requests
                and failures <= experiment.maximum_failed_requests
            ),
        },
    }


# --------------------------------------------------------------------------
# Raw result persistence
# --------------------------------------------------------------------------


def result_directory(experiment: Experiment, repo_root: Path = REPO_ROOT) -> Path:
    """The workspace-scoped result directory, after refusing an unsafe path."""
    root = repo_root.resolve()
    if experiment.result_directory != EXPECTED_RESULT_DIRECTORY:
        raise BaselineError("the baseline result path is unsafe")
    candidate = root
    for part in EXPECTED_RESULT_DIRECTORY.parts:
        candidate = candidate / part
        if candidate.is_symlink() or os.path.isjunction(candidate):
            raise BaselineError("the baseline result path is unsafe")
    directory = root / experiment.result_directory
    if not directory.resolve().is_relative_to(root):
        raise BaselineError("the baseline result path is unsafe")
    return directory


def write_raw(
    experiment: Experiment,
    run: BaselineRun,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Write the run header, one record per request, and the resource samples."""
    directory = result_directory(experiment, repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    result_directory(experiment, repo_root)
    path = directory / experiment.raw_file
    lines = [
        json.dumps(
            {
                "record": "run",
                "experimentId": run.experiment_id,
                "evidenceClass": run.evidence_class,
                "fixtureId": experiment.fixture.fixture_id,
                "productionBenchmark": False,
                "modelLoadMs": run.model_load_ms,
                "apiReadyMs": run.api_ready_ms,
                "measuredWindowMs": run.measured_window_ms,
                "environment": run.environment.document(),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    ]
    lines.extend(
        json.dumps(
            {"record": "request", **record.document()},
            separators=(",", ":"),
            sort_keys=True,
        )
        for record in run.records
    )
    lines.extend(
        json.dumps(
            {"record": "resource", **sample.document()},
            separators=(",", ":"),
            sort_keys=True,
        )
        for sample in run.samples
    )
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    except OSError as error:
        raise BaselineError(
            "the baseline raw result set could not be written"
        ) from error
    return path


def read_raw(
    experiment: Experiment,
    *,
    repo_root: Path = REPO_ROOT,
    path: Path | None = None,
) -> BaselineRun:
    """Read a raw result set back into the run a summary is computed from."""
    source = (
        path
        if path is not None
        else result_directory(experiment, repo_root) / experiment.raw_file
    )
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise BaselineError("the baseline raw result set is unreadable") from error
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or len(lines) > MAXIMUM_RAW_RECORDS:
        raise BaselineError("the baseline raw result set is empty or too large")
    header: dict[str, Any] | None = None
    records: list[RequestRecord] = []
    samples: list[ResourceSample] = []
    for line in lines:
        try:
            document = _object(json.loads(line), "record")
        except json.JSONDecodeError as error:
            raise BaselineError("a baseline raw record is not valid JSON") from error
        kind = document.get("record")
        if kind == "run":
            if header is not None:
                raise BaselineError("the baseline raw result set has two run records")
            header = document
        elif kind == "request":
            records.append(_request_record(document))
        elif kind == "resource":
            samples.append(
                ResourceSample(
                    sequence=_integer(document.get("sequence"), "sequence", minimum=0),
                    cpu_percent=_number(document.get("cpuPercent"), "cpuPercent"),
                    memory_bytes=_integer(
                        document.get("memoryBytes"), "memoryBytes", minimum=0
                    ),
                )
            )
        else:
            raise BaselineError("a baseline raw record has an unsupported kind")
    if header is None or not records:
        raise BaselineError("the baseline raw result set has no run or no request")
    if header.get("productionBenchmark") is not False:
        raise BaselineError("a baseline raw result set may not claim to be a benchmark")
    return BaselineRun(
        experiment_id=_string(header.get("experimentId"), "experimentId"),
        evidence_class=_string(header.get("evidenceClass"), "evidenceClass"),
        environment=_environment(_object(header.get("environment"), "environment")),
        model_load_ms=_integer(header.get("modelLoadMs"), "modelLoadMs", minimum=0),
        api_ready_ms=_integer(header.get("apiReadyMs"), "apiReadyMs", minimum=0),
        records=tuple(records),
        samples=tuple(samples),
        measured_window_ms=_integer(
            header.get("measuredWindowMs"), "measuredWindowMs", minimum=0
        ),
    )


def _optional_integer(
    document: Mapping[str, Any], field: str, *, minimum: int = 0
) -> int | None:
    value = document.get(field)
    return None if value is None else _integer(value, field, minimum=minimum)


def _optional_string(document: Mapping[str, Any], field: str) -> str | None:
    value = document.get(field)
    return None if value is None else _string(value, field)


def _request_record(document: Mapping[str, Any]) -> RequestRecord:
    phase = _string(document.get("phase"), "phase")
    outcome = _string(document.get("outcome"), "outcome")
    if phase not in PHASES or outcome not in OUTCOMES:
        raise BaselineError("a baseline raw record has an unsupported phase or outcome")
    return RequestRecord(
        sequence=_integer(document.get("sequence"), "sequence", minimum=0),
        phase=phase,
        outcome=outcome,
        status=_integer(document.get("status"), "status", minimum=0),
        latency_ms=_integer(document.get("latencyMs"), "latencyMs", minimum=0),
        input_tokens=_optional_integer(document, "inputTokens"),
        output_tokens=_optional_integer(document, "outputTokens"),
        adapter_kind=_optional_string(document, "adapterKind"),
        model_ref=_optional_string(document, "modelRef"),
        error_code=_optional_string(document, "errorCode"),
    )


def _environment(document: Mapping[str, Any]) -> Environment:
    return Environment(
        operating_system=_string(document.get("operatingSystem"), "operatingSystem"),
        release=_string(document.get("release"), "release"),
        architecture=_string(document.get("architecture"), "architecture"),
        processor_family=_string(document.get("processorFamily"), "processorFamily"),
        logical_cpus=_integer(document.get("logicalCpus"), "logicalCpus", minimum=0),
        total_memory_bytes=_optional_integer(document, "totalMemoryBytes"),
        free_disk_bytes=_optional_integer(document, "freeDiskBytes"),
        python_version=_string(document.get("pythonVersion"), "pythonVersion"),
        container_engine_version=_optional_string(document, "containerEngineVersion"),
        accelerator=_string(document.get("accelerator"), "accelerator"),
        image_reference=_string(document.get("imageReference"), "imageReference"),
        model_repository=_string(document.get("modelRepository"), "modelRepository"),
        model_revision=_string(document.get("modelRevision"), "modelRevision"),
        model_artifact_sha256=_string(
            document.get("modelArtifactSha256"), "modelArtifactSha256"
        ),
        runtime_source_revision=_string(
            document.get("runtimeSourceRevision"), "runtimeSourceRevision"
        ),
    )


def write_summary(
    experiment: Experiment,
    summary: Mapping[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Write the deterministic summary beside the raw records it came from."""
    directory = result_directory(experiment, repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    result_directory(experiment, repo_root)
    path = directory / experiment.summary_file
    try:
        path.write_text(
            json.dumps(dict(summary), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except OSError as error:
        raise BaselineError("the baseline summary could not be written") from error
    return path


# --------------------------------------------------------------------------
# The authorized run
# --------------------------------------------------------------------------


def _require_confirmation(confirmed: bool) -> None:
    if not confirmed:
        raise BaselineRefused("a measured baseline run requires --confirm-real-runtime")


def execute(
    experiment: Experiment,
    *,
    confirmed: bool,
    repo_root: Path = REPO_ROOT,
    runner: CommandRunner | None = None,
    post: JsonPost = json_post,
    clock: Callable[[], float] = time.monotonic,
    composition: LocalComposition | None = None,
    compose: Callable[..., Any] = run_foreground,
) -> BaselineRun:
    """Compose the real stack, discard the warm-up, and measure the fixed load.

    The composition is started through the existing local-composition workflow, so
    readiness ordering, drain, and ownership-scoped cleanup stay owned in one
    place. This function contributes the warm-up, the measured phase, and the
    resource samples, and nothing else. Model-load time is the runtime readiness
    the composition measured; it is not measured a second time here.
    """
    _require_confirmation(confirmed)
    active = composition if composition is not None else load_composition()
    active_runner = runner or SubprocessRunner(
        timeout_seconds=active.engine_command_timeout_seconds
    )
    package = load_runtime_package()
    environment = capture_environment(runner=active_runner, repo_root=repo_root)
    records: list[RequestRecord] = []
    samples: list[ResourceSample] = []
    timings = {"modelLoadMs": 0, "apiReadyMs": 0, "windowMs": 0}

    def on_ready(runtime_ms: int, api_ms: int) -> None:
        timings["modelLoadMs"] = runtime_ms
        timings["apiReadyMs"] = api_ms
        started = clock()
        for index in range(experiment.warmup_requests):
            records.append(
                send_request(
                    experiment,
                    active,
                    sequence=index,
                    phase=PHASE_WARMUP,
                    post=post,
                    clock=clock,
                )
            )
        window_started = clock()
        for index in range(experiment.measured_requests):
            records.append(
                send_request(
                    experiment,
                    active,
                    sequence=experiment.warmup_requests + index,
                    phase=PHASE_MEASURED,
                    post=post,
                    clock=clock,
                )
            )
            if (index + 1) % experiment.resource_sample_every_requests == 0:
                sample = sample_resources(
                    package,
                    active_runner,
                    sequence=experiment.warmup_requests + index,
                )
                if sample is not None:
                    samples.append(sample)
            if clock() - started >= experiment.max_duration_seconds:
                break
        timings["windowMs"] = max(0, round((clock() - window_started) * 1000))

    compose(
        active,
        confirmed=True,
        repo_root=repo_root,
        runner=active_runner,
        on_ready=on_ready,
    )
    if not records:
        raise BaselineError("the baseline run produced no request record")
    return BaselineRun(
        experiment_id=experiment.experiment_id,
        evidence_class=experiment.evidence_class,
        environment=environment,
        model_load_ms=timings["modelLoadMs"],
        api_ready_ms=timings["apiReadyMs"],
        records=tuple(records),
        samples=tuple(samples),
        measured_window_ms=timings["windowMs"],
    )
