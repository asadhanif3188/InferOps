"""Certify the C2 real-runtime smoke path for the selected runtime and model.

The committed certification descriptor is the authority for what a `C2` run
checks. Loading it performs no I/O beyond reading committed files: it is
cross-checked against the local composition, the runtime package, the runtime
profile, and the selected model's source record, so a drift between any of them
is a refusal rather than a surprise during an authorized run.

Execution is deliberately separate. It requires explicit confirmation, refuses
before it starts when a host prerequisite is unmet, waits for measured readiness
with the bounded budgets the composition already publishes, sends one fixed
request through the InferOps API rather than to the runtime directly, and refuses
any answer carrying mock identity or mock capability metadata. Its result is
labelled `local-real-cpu`; nothing here may relabel a synthetic run as a real one.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from inferops.adapters.llama_cpp import (
    LLAMA_SERVER_ADAPTER_KIND,
    LLAMA_SERVER_RUNTIME_NAME,
)
from inferops.api.surface import (
    CAPABILITY_TOKEN_USAGE,
    CHAT_COMPLETIONS_PATH,
    CORRELATION_ID_HEADER,
    EXTENSION_ADAPTER_KIND,
    EXTENSION_MEMBER,
    EXTENSION_MODEL_REF,
    MODELS_PATH,
    REQUEST_ID_HEADER,
)
from tools.local_composition import (
    CompositionError,
    LocalComposition,
    load_composition,
    run_foreground,
)
from tools.local_composition.core import ApiServer
from tools.local_composition.http_server import LocalApiServer
from tools.model_acquisition import ModelManifest, load_manifest
from tools.runtime_configuration import load_runtime_profile
from tools.runtime_packaging import (
    CommandRunner,
    RuntimePackage,
    SubprocessRunner,
    load_runtime_package,
    preflight,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CERTIFICATION_PATH = REPO_ROOT / "deploy/serving/certification/c2-smoke.v1.json"

EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_ID = "inferops-c2-real-runtime-smoke"
EXPECTED_LEVEL = "C2"
EXPECTED_EVIDENCE_CLASS = "local-real-cpu"
EXPECTED_EVIDENCE_LABEL = "local real runtime"
EXPECTED_LANE = "real-runtime"
EXPECTED_COMPOSITION_REF = "deploy/serving/local/composition.v1.json"
EXPECTED_CERTIFICATION_REF = "docs/testing/certification.md"
EXPECTED_EVIDENCE_DIRECTORY = Path(".cache/inferops/certification")

#: The smallest disk headroom a certification run may start with, on the volume
#: holding the verified model cache. It is a floor on the descriptor rather than
#: a value read from it, so a run cannot be authorized by lowering the record.
MINIMUM_DISK_FLOOR_BYTES = 1024 * 1024 * 1024

#: The stages a run passes through, in order. A diagnostics record names the one
#: it stopped in, which is what turns a failure into a place to look.
STAGE_LOAD = "load"
STAGE_PREREQUISITES = "prerequisites"
STAGE_COMPOSE = "compose"
STAGE_IDENTITY = "identity"
STAGE_INFERENCE = "inference"
STAGE_CLEANUP = "cleanup"


class CertificationError(RuntimeError):
    """The certification descriptor or a bounded certification step failed."""

    stage = STAGE_LOAD


class PrerequisiteUnmet(CertificationError):
    """A host, engine, image, or model prerequisite was not satisfied."""

    stage = STAGE_PREREQUISITES

    def __init__(self, message: str, report: PrerequisiteReport | None = None) -> None:
        super().__init__(message)
        self.report = report


class CertificationFailed(CertificationError):
    """The workflow ran and the real runtime did not certify."""

    def __init__(self, message: str, stage: str = STAGE_COMPOSE) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True, slots=True)
class Certification:
    """The committed C2 descriptor after every field has been validated."""

    schema_version: str
    certification_id: str
    certification_level: str
    evidence_class: str
    evidence_label: str
    lane: str
    composition_ref: str
    certification_ref: str
    minimum_logical_cpus: int
    minimum_engine_memory_bytes: int
    minimum_free_disk_bytes: int
    requires_verified_model_cache: bool
    requires_pinned_runtime_image: bool
    requires_container_engine: bool
    runtime_budget_ms: int
    api_budget_ms: int
    request_path: str
    models_path: str
    prompt: str
    request_id: str
    correlation_id: str
    request_timeout_ms: int
    required_adapter_kind: str
    prohibited_identity_substring: str
    require_usage_counts: bool
    require_nonempty_content: bool
    require_pinned_model_revision: bool
    evidence_directory: Path
    result_file: str
    diagnostics_file: str
    retain_generated_text: bool


@dataclass(frozen=True, slots=True)
class HostFacts:
    """Safe, non-identifying host facts a certification record may publish."""

    operating_system: str
    release: str
    machine: str
    python_version: str
    engine_logical_cpus: int
    engine_memory_bytes: int
    free_disk_bytes: int


@dataclass(frozen=True, slots=True)
class PrerequisiteCheck:
    """One named prerequisite, what it required, and what was observed."""

    name: str
    required: int
    observed: int
    satisfied: bool


@dataclass(frozen=True, slots=True)
class PrerequisiteReport:
    """Everything established before any container is created."""

    host: HostFacts
    checks: tuple[PrerequisiteCheck, ...]
    model_artifact_verified: bool
    runtime_image_present: bool

    @property
    def satisfied(self) -> bool:
        return all(check.satisfied for check in self.checks)


@dataclass(frozen=True, slots=True)
class ObservedIdentity:
    """The model and runtime identity the API published about itself."""

    adapter_kind: str
    model_identifier: str
    runtime_name: str
    runtime_version: str
    model_revision: str
    token_usage_declared: bool


@dataclass(frozen=True, slots=True)
class InferenceObservation:
    """One completed request, with generated text deliberately not retained."""

    status: int
    elapsed_ms: int
    completion_characters: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    request_id_echoed: bool
    correlation_id_echoed: bool


@dataclass(frozen=True, slots=True)
class CertificationResult:
    """A completed C2 run, in the shape the evidence record is written from."""

    certification_id: str
    certification_level: str
    evidence_class: str
    evidence_label: str
    host: HostFacts
    prerequisites: tuple[PrerequisiteCheck, ...]
    provenance: Mapping[str, str]
    runtime_readiness_ms: int
    api_readiness_ms: int
    identity: ObservedIdentity
    inference: InferenceObservation
    api_drained: bool
    runtime_removed: bool


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Why a run stopped, in the stage vocabulary this workflow publishes."""

    stage: str
    reason: str
    host: HostFacts | None = None
    prerequisites: tuple[PrerequisiteCheck, ...] = ()
    runtime_readiness_ms: int | None = None
    api_readiness_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """The status, parsed body, and headers retained from one loopback call."""

    status: int
    body: object | None
    headers: Mapping[str, str]


ApiGet = Callable[[str, float], ApiResponse]
ApiPost = Callable[[str, Mapping[str, object], Mapping[str, str], float], ApiResponse]
FreeBytes = Callable[[Path], int]


# -- reading the descriptor -------------------------------------------------


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CertificationError(f"certification field '{field}' must be an object")
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise CertificationError(f"certification field '{field}' must be a string")
    return value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise CertificationError(
            f"certification field '{field}' must be an integer of at least {minimum}"
        )
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise CertificationError(f"certification field '{field}' must be a boolean")
    return value


def _require_keys(record: Mapping[str, Any], field: str, expected: set[str]) -> None:
    if set(record) != expected:
        raise CertificationError(
            f"certification field '{field}' has missing or unsupported members"
        )


def load_certification(path: Path = CERTIFICATION_PATH) -> Certification:
    """Load and cross-check the C2 descriptor without performing any real I/O."""
    try:
        record = _object(json.loads(path.read_text(encoding="utf-8")), "root")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CertificationError(
            "the certification descriptor is unreadable"
        ) from error

    prerequisites = _object(record.get("prerequisites"), "prerequisites")
    readiness = _object(record.get("readiness"), "readiness")
    request = _object(record.get("request"), "request")
    assertions = _object(record.get("assertions"), "assertions")
    evidence = _object(record.get("evidence"), "evidence")
    _require_keys(
        record,
        "root",
        {
            "schemaVersion",
            "certificationId",
            "certificationLevel",
            "evidenceClass",
            "evidenceLabel",
            "lane",
            "compositionRef",
            "certificationRef",
            "prerequisites",
            "readiness",
            "request",
            "assertions",
            "evidence",
        },
    )
    _require_keys(
        prerequisites,
        "prerequisites",
        {
            "minimumLogicalCpus",
            "minimumEngineMemoryBytes",
            "minimumFreeDiskBytes",
            "requiresVerifiedModelCache",
            "requiresPinnedRuntimeImage",
            "requiresContainerEngine",
        },
    )
    _require_keys(readiness, "readiness", {"runtimeBudgetMs", "apiBudgetMs"})
    _require_keys(
        request,
        "request",
        {"path", "modelsPath", "prompt", "requestId", "correlationId", "timeoutMs"},
    )
    _require_keys(
        assertions,
        "assertions",
        {
            "requiredAdapterKind",
            "prohibitedIdentitySubstring",
            "requireUsageCounts",
            "requireNonEmptyContent",
            "requirePinnedModelRevision",
        },
    )
    _require_keys(
        evidence,
        "evidence",
        {"directory", "resultFile", "diagnosticsFile", "retainGeneratedText"},
    )

    certification = Certification(
        schema_version=_string(record.get("schemaVersion"), "schemaVersion"),
        certification_id=_string(record.get("certificationId"), "certificationId"),
        certification_level=_string(
            record.get("certificationLevel"), "certificationLevel"
        ),
        evidence_class=_string(record.get("evidenceClass"), "evidenceClass"),
        evidence_label=_string(record.get("evidenceLabel"), "evidenceLabel"),
        lane=_string(record.get("lane"), "lane"),
        composition_ref=_string(record.get("compositionRef"), "compositionRef"),
        certification_ref=_string(record.get("certificationRef"), "certificationRef"),
        minimum_logical_cpus=_integer(
            prerequisites.get("minimumLogicalCpus"),
            "prerequisites.minimumLogicalCpus",
        ),
        minimum_engine_memory_bytes=_integer(
            prerequisites.get("minimumEngineMemoryBytes"),
            "prerequisites.minimumEngineMemoryBytes",
        ),
        minimum_free_disk_bytes=_integer(
            prerequisites.get("minimumFreeDiskBytes"),
            "prerequisites.minimumFreeDiskBytes",
        ),
        requires_verified_model_cache=_boolean(
            prerequisites.get("requiresVerifiedModelCache"),
            "prerequisites.requiresVerifiedModelCache",
        ),
        requires_pinned_runtime_image=_boolean(
            prerequisites.get("requiresPinnedRuntimeImage"),
            "prerequisites.requiresPinnedRuntimeImage",
        ),
        requires_container_engine=_boolean(
            prerequisites.get("requiresContainerEngine"),
            "prerequisites.requiresContainerEngine",
        ),
        runtime_budget_ms=_integer(
            readiness.get("runtimeBudgetMs"), "readiness.runtimeBudgetMs"
        ),
        api_budget_ms=_integer(readiness.get("apiBudgetMs"), "readiness.apiBudgetMs"),
        request_path=_string(request.get("path"), "request.path"),
        models_path=_string(request.get("modelsPath"), "request.modelsPath"),
        prompt=_string(request.get("prompt"), "request.prompt"),
        request_id=_string(request.get("requestId"), "request.requestId"),
        correlation_id=_string(request.get("correlationId"), "request.correlationId"),
        request_timeout_ms=_integer(request.get("timeoutMs"), "request.timeoutMs"),
        required_adapter_kind=_string(
            assertions.get("requiredAdapterKind"), "assertions.requiredAdapterKind"
        ),
        prohibited_identity_substring=_string(
            assertions.get("prohibitedIdentitySubstring"),
            "assertions.prohibitedIdentitySubstring",
        ),
        require_usage_counts=_boolean(
            assertions.get("requireUsageCounts"), "assertions.requireUsageCounts"
        ),
        require_nonempty_content=_boolean(
            assertions.get("requireNonEmptyContent"),
            "assertions.requireNonEmptyContent",
        ),
        require_pinned_model_revision=_boolean(
            assertions.get("requirePinnedModelRevision"),
            "assertions.requirePinnedModelRevision",
        ),
        evidence_directory=Path(
            _string(evidence.get("directory"), "evidence.directory")
        ),
        result_file=_string(evidence.get("resultFile"), "evidence.resultFile"),
        diagnostics_file=_string(
            evidence.get("diagnosticsFile"), "evidence.diagnosticsFile"
        ),
        retain_generated_text=_boolean(
            evidence.get("retainGeneratedText"), "evidence.retainGeneratedText"
        ),
    )
    _validate(certification, load_composition(), load_runtime_package())
    return certification


def _validate(
    certification: Certification,
    composition: LocalComposition,
    package: RuntimePackage,
) -> None:
    profile = load_runtime_profile()
    if (
        certification.schema_version != EXPECTED_SCHEMA
        or certification.certification_id != EXPECTED_ID
        or certification.certification_level != EXPECTED_LEVEL
        or certification.evidence_class != EXPECTED_EVIDENCE_CLASS
        or certification.evidence_label != EXPECTED_EVIDENCE_LABEL
        or certification.lane != EXPECTED_LANE
        or certification.composition_ref != EXPECTED_COMPOSITION_REF
        or certification.certification_ref != EXPECTED_CERTIFICATION_REF
    ):
        raise CertificationError("the certification identity is unsupported")
    if not (
        certification.requires_container_engine
        and certification.requires_pinned_runtime_image
        and certification.requires_verified_model_cache
    ):
        raise CertificationError(
            "a certification run may not waive an engine, image, or model prerequisite"
        )
    if (
        certification.minimum_logical_cpus < package.cpu_limit_cores
        or certification.minimum_engine_memory_bytes
        < package.memory_limit_mib * 1024 * 1024
        or certification.minimum_free_disk_bytes < MINIMUM_DISK_FLOOR_BYTES
    ):
        raise CertificationError(
            "the certification prerequisites are below the selected package's needs"
        )
    if (
        certification.runtime_budget_ms != package.startup_budget_ms
        or certification.api_budget_ms != composition.response_budget_ms
        or certification.request_timeout_ms != profile.request_budget_ms
    ):
        raise CertificationError("the certification budgets disagree with the profile")
    if (
        certification.request_path != CHAT_COMPLETIONS_PATH
        or certification.models_path != MODELS_PATH
    ):
        raise CertificationError("the certification request path is not a served route")
    if any(character in certification.prompt for character in "\r\n"):
        raise CertificationError("the certification prompt must be one line")
    if (
        certification.required_adapter_kind != LLAMA_SERVER_ADAPTER_KIND
        or composition.adapter_selection != LLAMA_SERVER_ADAPTER_KIND
        or composition.mock_fallback
        or not certification.prohibited_identity_substring
    ):
        raise CertificationError("a certification run may certify only the real path")
    if not (
        certification.require_usage_counts
        and certification.require_nonempty_content
        and certification.require_pinned_model_revision
    ):
        raise CertificationError("a certification run may not waive a real assertion")
    if (
        certification.evidence_directory != EXPECTED_EVIDENCE_DIRECTORY
        or certification.retain_generated_text
        or Path(certification.result_file).name != certification.result_file
        or Path(certification.diagnostics_file).name != certification.diagnostics_file
        or certification.result_file == certification.diagnostics_file
    ):
        raise CertificationError("the certification evidence location is unsafe")


# -- prerequisites ----------------------------------------------------------


def free_disk_bytes(path: Path) -> int:
    """Free bytes on the volume holding one existing directory."""
    return shutil.disk_usage(path).free


def _engine_capacity(package: RuntimePackage, runner: CommandRunner) -> tuple[int, int]:
    """Read the CPUs and memory the container engine itself reports.

    The engine's own figures are read rather than the host's, because on Windows
    and macOS the memory reaching the container virtual machine is the limit that
    binds and it is routinely a fraction of installed memory.
    """
    result = runner.run((package.engine, "info", "--format", "{{.NCPU}} {{.MemTotal}}"))
    if result.returncode != 0:
        raise PrerequisiteUnmet("the container engine is unavailable")
    fields = result.stdout.split()
    if len(fields) != 2:
        raise PrerequisiteUnmet("the container engine reported no capacity")
    try:
        return int(fields[0]), int(fields[1])
    except ValueError as error:
        raise PrerequisiteUnmet(
            "the container engine reported an unreadable capacity"
        ) from error


def _existing_volume(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def _host_facts(
    package: RuntimePackage,
    runner: CommandRunner,
    manifest: ModelManifest,
    *,
    repo_root: Path,
    free_bytes: FreeBytes,
) -> HostFacts:
    logical_cpus, engine_memory = _engine_capacity(package, runner)
    volume = _existing_volume(manifest.artifact_path(repo_root).parent)
    try:
        free_disk = free_bytes(volume)
    except OSError as error:
        raise PrerequisiteUnmet(
            "free space on the model cache volume could not be measured"
        ) from error
    return HostFacts(
        operating_system=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        python_version=platform.python_version(),
        engine_logical_cpus=logical_cpus,
        engine_memory_bytes=engine_memory,
        free_disk_bytes=free_disk,
    )


def check_prerequisites(
    certification: Certification,
    runner: CommandRunner,
    *,
    repo_root: Path = REPO_ROOT,
    free_bytes: FreeBytes = free_disk_bytes,
) -> PrerequisiteReport:
    """Establish capacity, image, and model prerequisites before anything starts.

    Capacity is measured first because it is cheap, and verifying the cached model
    hashes nearly two gigabytes: a host that cannot serve the workload learns so
    before paying for that.
    """
    if not ((3, 12) <= sys.version_info[:2] < (3, 13)):
        raise PrerequisiteUnmet("Python 3.12 is required by the repository toolchain")
    package = load_runtime_package()
    manifest = load_manifest()
    host = _host_facts(
        package, runner, manifest, repo_root=repo_root, free_bytes=free_bytes
    )
    checks = (
        PrerequisiteCheck(
            name="engine-logical-cpus",
            required=certification.minimum_logical_cpus,
            observed=host.engine_logical_cpus,
            satisfied=host.engine_logical_cpus >= certification.minimum_logical_cpus,
        ),
        PrerequisiteCheck(
            name="engine-memory-bytes",
            required=certification.minimum_engine_memory_bytes,
            observed=host.engine_memory_bytes,
            satisfied=(
                host.engine_memory_bytes >= certification.minimum_engine_memory_bytes
            ),
        ),
        PrerequisiteCheck(
            name="model-cache-free-disk-bytes",
            required=certification.minimum_free_disk_bytes,
            observed=host.free_disk_bytes,
            satisfied=host.free_disk_bytes >= certification.minimum_free_disk_bytes,
        ),
    )
    unmet = tuple(check.name for check in checks if not check.satisfied)
    if unmet:
        raise PrerequisiteUnmet(
            "the host does not meet the certification prerequisites: "
            + ", ".join(unmet),
            PrerequisiteReport(
                host=host,
                checks=checks,
                model_artifact_verified=False,
                runtime_image_present=False,
            ),
        )
    try:
        preflight(package, runner, repo_root=repo_root)
    except Exception as error:
        raise PrerequisiteUnmet(
            "the pinned image or hash-verified model artifact is not available",
            PrerequisiteReport(
                host=host,
                checks=checks,
                model_artifact_verified=False,
                runtime_image_present=False,
            ),
        ) from error
    return PrerequisiteReport(
        host=host,
        checks=checks,
        model_artifact_verified=True,
        runtime_image_present=True,
    )


# -- the loopback client ----------------------------------------------------


def _response(status: int, payload: bytes, headers: Mapping[str, str]) -> ApiResponse:
    try:
        body: object | None = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        body = None
    return ApiResponse(status, body, dict(headers))


def api_get(url: str, timeout_seconds: float) -> ApiResponse:
    """GET one loopback InferOps endpoint and parse only its JSON body."""
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout_seconds) as response:
            return _response(response.status, response.read(), dict(response.headers))
    except HTTPError as error:
        return _response(error.code, error.read(), dict(error.headers))
    except (OSError, URLError) as error:
        raise CertificationFailed(
            "the loopback InferOps API could not be reached", STAGE_IDENTITY
        ) from error


def api_post(
    url: str,
    body: Mapping[str, object],
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> ApiResponse:
    """POST one bounded JSON request to the loopback InferOps API."""
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return _response(response.status, response.read(), dict(response.headers))
    except HTTPError as error:
        return _response(error.code, error.read(), dict(error.headers))
    except (OSError, URLError) as error:
        raise CertificationFailed(
            "the loopback InferOps API could not be reached", STAGE_INFERENCE
        ) from error


# -- the assertions ---------------------------------------------------------


def _mapping_member(value: object, field: str, stage: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CertificationFailed(
            f"the API response member '{field}' is not an object", stage
        )
    return cast(Mapping[str, object], value)


def _string_member(value: object, field: str, stage: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CertificationFailed(
            f"the API response member '{field}' is not a non-empty string", stage
        )
    return value


def _refuse_mock_identity(certification: Certification, values: Sequence[str]) -> None:
    marker = certification.prohibited_identity_substring.casefold()
    for value in values:
        if marker in value.casefold():
            raise CertificationFailed(
                "the API reported mock identity metadata on the certified path",
                STAGE_IDENTITY,
            )


def observe_identity(
    certification: Certification,
    composition: LocalComposition,
    manifest: ModelManifest,
    *,
    get: ApiGet,
) -> ObservedIdentity:
    """Read the model and runtime identity the API publishes about itself."""
    stage = STAGE_IDENTITY
    response = get(
        f"{composition.api_base_url}{certification.models_path}",
        certification.request_timeout_ms / 1000,
    )
    if response.status != 200:
        raise CertificationFailed(
            "the model list did not answer with a description", stage
        )
    body = _mapping_member(response.body, "root", stage)
    extension = _mapping_member(body.get(EXTENSION_MEMBER), EXTENSION_MEMBER, stage)
    runtime = _mapping_member(extension.get("runtime"), "runtime", stage)
    capabilities = _mapping_member(extension.get("capabilities"), "capabilities", stage)
    entries = body.get("data")
    if not isinstance(entries, list) or len(entries) != 1:
        raise CertificationFailed(
            "the certified deployment must serve exactly one model", stage
        )
    identity = ObservedIdentity(
        adapter_kind=_string_member(
            extension.get(EXTENSION_ADAPTER_KIND), EXTENSION_ADAPTER_KIND, stage
        ),
        model_identifier=_string_member(
            _mapping_member(entries[0], "data[0]", stage).get("id"), "data[0].id", stage
        ),
        runtime_name=_string_member(runtime.get("name"), "runtime.name", stage),
        runtime_version=_string_member(
            runtime.get("version"), "runtime.version", stage
        ),
        model_revision=_string_member(
            runtime.get("modelRevision"), "runtime.modelRevision", stage
        ),
        token_usage_declared=capabilities.get(CAPABILITY_TOKEN_USAGE) is True,
    )
    expected_model = composition.environment["INFEROPS_MODEL_IDENTIFIER"]
    if identity.adapter_kind != certification.required_adapter_kind:
        raise CertificationFailed(
            "the model list did not report the required adapter kind", stage
        )
    if identity.runtime_name != LLAMA_SERVER_RUNTIME_NAME:
        raise CertificationFailed("the model list named an unselected runtime", stage)
    if identity.model_identifier != expected_model:
        raise CertificationFailed("the model list named an unconfigured model", stage)
    if (
        certification.require_pinned_model_revision
        and identity.model_revision != manifest.revision
    ):
        raise CertificationFailed(
            "the model list did not name the pinned model revision", stage
        )
    if not identity.token_usage_declared:
        # The selected real adapter declares token counting supported and the
        # committed mock declares it unsupported, so an absent or false
        # declaration here is mock capability metadata whatever else agreed.
        raise CertificationFailed(
            "the certified path declares token usage unsupported, which is mock "
            "capability metadata",
            stage,
        )
    _refuse_mock_identity(
        certification,
        (
            identity.adapter_kind,
            identity.model_identifier,
            identity.runtime_name,
            identity.runtime_version,
            identity.model_revision,
        ),
    )
    return identity


def observe_inference(
    certification: Certification,
    composition: LocalComposition,
    *,
    post: ApiPost,
    clock: Callable[[], float] = time.monotonic,
) -> InferenceObservation:
    """Send the one fixed request and hold its answer to every real assertion."""
    stage = STAGE_INFERENCE
    expected_model = composition.environment["INFEROPS_MODEL_IDENTIFIER"]
    started = clock()
    response = post(
        f"{composition.api_base_url}{certification.request_path}",
        {
            "model": expected_model,
            "messages": [{"role": "user", "content": certification.prompt}],
        },
        {
            REQUEST_ID_HEADER: certification.request_id,
            CORRELATION_ID_HEADER: certification.correlation_id,
        },
        certification.request_timeout_ms / 1000,
    )
    elapsed_ms = max(0, round((clock() - started) * 1000))
    if response.status != 200:
        raise CertificationFailed(
            "the certified request did not return a completion", stage
        )
    body = _mapping_member(response.body, "root", stage)
    extension = _mapping_member(body.get(EXTENSION_MEMBER), EXTENSION_MEMBER, stage)
    if extension.get(EXTENSION_ADAPTER_KIND) != certification.required_adapter_kind:
        raise CertificationFailed(
            "the completion did not report the required adapter kind", stage
        )
    if extension.get(EXTENSION_MODEL_REF) != expected_model:
        raise CertificationFailed("the completion named an unconfigured model", stage)
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise CertificationFailed("the completion carried no single choice", stage)
    message = _mapping_member(
        _mapping_member(choices[0], "choices[0]", stage).get("message"),
        "choices[0].message",
        stage,
    )
    content = message.get("content")
    if not isinstance(content, str) or (
        certification.require_nonempty_content and not content.strip()
    ):
        raise CertificationFailed(
            "the real model returned no completion content", stage
        )
    counts = _mapping_member(body.get("usage"), "usage", stage)
    prompt_tokens = counts.get("prompt_tokens")
    completion_tokens = counts.get("completion_tokens")
    total_tokens = counts.get("total_tokens")
    if not (
        isinstance(prompt_tokens, int)
        and isinstance(completion_tokens, int)
        and isinstance(total_tokens, int)
        and prompt_tokens > 0
        and completion_tokens > 0
        and total_tokens == prompt_tokens + completion_tokens
    ):
        raise CertificationFailed(
            "the completion counts are absent or inconsistent", stage
        )
    return InferenceObservation(
        status=response.status,
        elapsed_ms=elapsed_ms,
        completion_characters=len(content),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        request_id_echoed=(
            response.headers.get(REQUEST_ID_HEADER) == certification.request_id
        ),
        correlation_id_echoed=(
            response.headers.get(CORRELATION_ID_HEADER) == certification.correlation_id
        ),
    )


# -- the evidence directory -------------------------------------------------


class EvidenceDirectory:
    """Write only this workflow's own records to the fixed ignored location."""

    def __init__(
        self, certification: Certification, *, repo_root: Path = REPO_ROOT
    ) -> None:
        if certification.evidence_directory != EXPECTED_EVIDENCE_DIRECTORY:
            raise CertificationError("the certification evidence path is unsafe")
        self.root = repo_root.resolve()
        self.directory = self.root / certification.evidence_directory
        self.result_path = self.directory / certification.result_file
        self.diagnostics_path = self.directory / certification.diagnostics_file
        self._ensure_safe()

    def _ensure_safe(self) -> None:
        candidate = self.root
        for part in EXPECTED_EVIDENCE_DIRECTORY.parts:
            candidate = candidate / part
            if candidate.is_symlink() or os.path.isjunction(candidate):
                raise CertificationError("the certification evidence path is unsafe")
        for target in (self.result_path, self.diagnostics_path):
            if target.is_symlink() or os.path.isjunction(target):
                raise CertificationError("the certification evidence path is unsafe")
            if not target.resolve().is_relative_to(self.root):
                raise CertificationError("the certification evidence path is unsafe")

    def write(self, target: Path, document: Mapping[str, object]) -> Path:
        """Write one whole record, refusing an unsafe path before and after mkdir."""
        self._ensure_safe()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._ensure_safe()
        try:
            target.write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        except OSError as error:
            raise CertificationError(
                "the certification evidence could not be written"
            ) from error
        return target


def _checks_document(checks: Sequence[PrerequisiteCheck]) -> list[dict[str, object]]:
    return [
        {
            "name": check.name,
            "required": check.required,
            "observed": check.observed,
            "satisfied": check.satisfied,
        }
        for check in checks
    ]


def _host_document(host: HostFacts) -> dict[str, object]:
    return {
        "operatingSystem": host.operating_system,
        "release": host.release,
        "machine": host.machine,
        "pythonVersion": host.python_version,
        "engineLogicalCpus": host.engine_logical_cpus,
        "engineMemoryBytes": host.engine_memory_bytes,
        "modelCacheFreeDiskBytes": host.free_disk_bytes,
    }


def result_document(result: CertificationResult) -> dict[str, object]:
    """The machine-readable C2 record, carrying no generated text."""
    return {
        "certificationId": result.certification_id,
        "certificationLevel": result.certification_level,
        "evidenceClass": result.evidence_class,
        "evidenceLabel": result.evidence_label,
        "outcome": "certified",
        "host": _host_document(result.host),
        "prerequisites": _checks_document(result.prerequisites),
        "provenance": dict(result.provenance),
        "readiness": {
            "runtimeReadyMs": result.runtime_readiness_ms,
            "apiReadyMs": result.api_readiness_ms,
        },
        "identity": {
            "adapterKind": result.identity.adapter_kind,
            "modelIdentifier": result.identity.model_identifier,
            "runtimeName": result.identity.runtime_name,
            "runtimeVersion": result.identity.runtime_version,
            "modelRevision": result.identity.model_revision,
            "tokenUsageDeclared": result.identity.token_usage_declared,
        },
        "inference": {
            "status": result.inference.status,
            "elapsedMs": result.inference.elapsed_ms,
            "completionCharacters": result.inference.completion_characters,
            "promptTokens": result.inference.prompt_tokens,
            "completionTokens": result.inference.completion_tokens,
            "totalTokens": result.inference.total_tokens,
            "requestIdEchoed": result.inference.request_id_echoed,
            "correlationIdEchoed": result.inference.correlation_id_echoed,
            "generatedTextRetained": False,
        },
        "cleanup": {
            "apiDrained": result.api_drained,
            "runtimeRemoved": result.runtime_removed,
        },
    }


def diagnostics_document(diagnostics: Diagnostics) -> dict[str, object]:
    """What a failed run leaves behind, in this workflow's stage vocabulary."""
    return {
        "certificationId": EXPECTED_ID,
        "certificationLevel": EXPECTED_LEVEL,
        "outcome": "not-certified",
        "stage": diagnostics.stage,
        "reason": diagnostics.reason,
        "host": None if diagnostics.host is None else _host_document(diagnostics.host),
        "prerequisites": _checks_document(diagnostics.prerequisites),
        "readiness": {
            "runtimeReadyMs": diagnostics.runtime_readiness_ms,
            "apiReadyMs": diagnostics.api_readiness_ms,
        },
    }


def provenance(
    composition: LocalComposition,
    package: RuntimePackage,
    manifest: ModelManifest,
) -> dict[str, str]:
    """The immutable inputs a C2 record must name, and nothing host-specific."""
    return {
        "compositionId": composition.composition_id,
        "runtimeImage": package.image_reference,
        "modelRepository": manifest.repository,
        "modelRevision": manifest.revision,
        "modelFile": manifest.file,
        "modelSha256": manifest.sha256,
        "apiBaseUrl": composition.api_base_url,
        "runtimeBaseUrl": package.base_url,
    }


# -- the workflow -----------------------------------------------------------


def _require_confirmation(confirmed: bool) -> None:
    if not confirmed:
        raise PrerequisiteUnmet(
            "C2 real-runtime certification requires --confirm-real-runtime"
        )


def certify(
    certification: Certification,
    *,
    confirmed: bool,
    repo_root: Path = REPO_ROOT,
    runner: CommandRunner | None = None,
    server_factory: Callable[..., ApiServer] = LocalApiServer,
    get: ApiGet = api_get,
    post: ApiPost = api_post,
    free_bytes: FreeBytes = free_disk_bytes,
    clock: Callable[[], float] = time.monotonic,
) -> CertificationResult:
    """Run the whole C2 path, or raise carrying the stage a diagnostics record names.

    The composition owns starting the runtime before the API, waiting for both
    readiness boundaries, and tearing down in reverse order; this function supplies
    what happens between the second readiness and that teardown.
    """
    _require_confirmation(confirmed)
    composition = load_composition()
    package = load_runtime_package()
    manifest = load_manifest()
    active_runner = runner or SubprocessRunner(
        timeout_seconds=composition.engine_command_timeout_seconds
    )
    report = check_prerequisites(
        certification, active_runner, repo_root=repo_root, free_bytes=free_bytes
    )

    servers: list[ApiServer] = []
    identities: list[ObservedIdentity] = []
    inferences: list[InferenceObservation] = []
    failures: list[Exception] = []

    def capture(application: Any, **keywords: Any) -> ApiServer:
        server = server_factory(application, **keywords)
        servers.append(server)
        return server

    def on_ready(_runtime_ms: int, _api_ms: int) -> None:
        try:
            identities.append(
                observe_identity(certification, composition, manifest, get=get)
            )
            inferences.append(
                observe_inference(certification, composition, post=post, clock=clock)
            )
        except Exception as error:
            failures.append(error)
        finally:
            for server in servers:
                server.request_stop()

    try:
        run = run_foreground(
            composition,
            confirmed=True,
            repo_root=repo_root,
            runner=active_runner,
            server_factory=capture,
            on_ready=on_ready,
        )
    except CompositionError as error:
        # A cleanup that also failed must not overwrite the reason the run did
        # not certify. `run_foreground` raises out of its own `finally`, so a
        # refused assertion followed by an imperfect teardown arrives here as a
        # composition error carrying none of what was actually observed.
        if failures:
            raise failures[0] from error
        # Nothing was observed, so the stage is decided by how far the ordered
        # startup reached rather than by the wording of the composition's error.
        reached_readiness = bool(identities and inferences)
        raise CertificationFailed(
            "the certified composition could not complete its ordered cleanup"
            if reached_readiness
            else "the certified composition did not start or become ready",
            STAGE_CLEANUP if reached_readiness else STAGE_COMPOSE,
        ) from error
    if failures:
        raise failures[0]
    if not identities or not inferences:
        raise CertificationFailed(
            "the certification produced no observation", STAGE_COMPOSE
        )
    if not (run.api_drained and run.runtime_removed):
        raise CertificationFailed(
            "the certification could not verify its own cleanup", STAGE_CLEANUP
        )
    return CertificationResult(
        certification_id=certification.certification_id,
        certification_level=certification.certification_level,
        evidence_class=certification.evidence_class,
        evidence_label=certification.evidence_label,
        host=report.host,
        prerequisites=report.checks,
        provenance=provenance(composition, package, manifest),
        runtime_readiness_ms=run.runtime_readiness_ms,
        api_readiness_ms=run.api_readiness_ms,
        identity=identities[0],
        inference=inferences[0],
        api_drained=run.api_drained,
        runtime_removed=run.runtime_removed,
    )
