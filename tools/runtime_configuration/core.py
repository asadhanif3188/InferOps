"""Load and validate the selected local ``llama-server`` profile.

The profile is configuration, not packaging: this module reads committed JSON,
checks it against the accepted runtime/model pins and the real adapter, and
derives the environment that later composition work can supply. It never starts
a process, opens a socket, resolves an image tag, or reads model bytes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from inferops.adapters.llama_cpp import (
    ENV_CONTEXT_SIZE,
    ENV_ENDPOINT,
    ENV_METRICS_ENABLED,
    ENV_MODEL_ALIAS,
    ENV_MODEL_PATH,
    ENV_STARTUP_BUDGET_MS,
    ENV_THREADS,
    HEALTH_LOADING_STATUS,
    HEALTH_PATH,
    HEALTH_READY_STATUS,
    LLAMA_SERVER_RUNTIME_ID,
    METRICS_PATH,
    PINNED_IMAGE_REFERENCE,
    PINNED_MODEL_FILE,
    PINNED_RUNTIME_SOURCE_REVISION,
    LlamaServerSettings,
)
from inferops.api.lifecycle import DEFAULT_DRAIN_TIMEOUT_MS
from inferops.api.selection import (
    ADAPTER_REAL,
    ENV_ADAPTER,
    ENV_DRAIN_TIMEOUT_MS,
    ENV_MAX_OUTPUT_TOKENS,
    ENV_MODEL_IDENTIFIER,
    ENV_REQUEST_TIMEOUT_MS,
)
from inferops.domain.serving import AdapterConfiguration, InvalidAdapterConfigError
from tools.model_acquisition import ModelAcquisitionError, load_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PROFILE_PATH = REPO_ROOT / "docs/serving/runtime-profile.local.v1.json"
EXPECTED_SCHEMA_VERSION = "inferops.io/v1alpha1"
EXPECTED_PROFILE_ID = "llama-cpp-local-cpu"
EXPECTED_ENVIRONMENT = "local"
EXPECTED_EVIDENCE_CLASS = "local-static"
PINNED_SOURCE_REVISION = PINNED_RUNTIME_SOURCE_REVISION
PINNED_COMMAND = "/app/llama-server"
EXPECTED_MODEL_SOURCE_REF = "docs/serving/model-source.v1.json"
EXPECTED_CONTAINER_DIRECTORY = "/models"
EXPECTED_ACCELERATOR_KIND = "none"
EXPECTED_LISTEN_HOST = "0.0.0.0"
EXPECTED_ADAPTER_HOST = "llama-server"


class RuntimeConfigurationError(RuntimeError):
    """A committed runtime-profile invariant was not met."""


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    """The local CPU profile after every field has been validated."""

    schema_version: str
    profile_id: str
    environment: str
    evidence_class: str
    runtime_id: str
    image_reference: str
    source_revision: str
    command: str
    arguments: tuple[str, ...]
    model_source_record: str
    model_cache_root: Path
    model_artifact_relative_path: Path
    model_container_path: str
    model_read_only: bool
    model_embedded_in_image: bool
    model_alias: str
    platform_identifier: str
    listen_host: str
    container_port: int
    adapter_endpoint: str
    cpu_request_cores: int
    cpu_limit_cores: int
    memory_request_mib: int
    memory_limit_mib: int
    accelerator_kind: str
    accelerator_count: int
    context_size_tokens: int
    default_max_output_tokens: int
    default_temperature: float
    threads: int
    parallel_slots: int
    startup_budget_ms: int
    request_budget_ms: int
    drain_budget_ms: int
    startup_kind: str
    startup_path: str
    startup_port: int
    startup_ready_status: int
    startup_loading_status: int
    readiness_kind: str
    readiness_path: str
    readiness_port: int
    readiness_ready_status: int
    readiness_loading_status: int
    liveness_kind: str
    liveness_port: int
    metrics_enabled: bool
    metrics_path: str
    metrics_port: int
    secrets_external_only: bool
    embedded_secret_values: tuple[str, ...]

    def adapter_environment(self) -> dict[str, str]:
        """Return the explicit environment understood by the real adapter/API."""
        return {
            ENV_ADAPTER: ADAPTER_REAL,
            ENV_MODEL_IDENTIFIER: self.platform_identifier,
            ENV_REQUEST_TIMEOUT_MS: str(self.request_budget_ms),
            ENV_MAX_OUTPUT_TOKENS: str(self.default_max_output_tokens),
            ENV_DRAIN_TIMEOUT_MS: str(self.drain_budget_ms),
            ENV_ENDPOINT: self.adapter_endpoint,
            ENV_MODEL_PATH: self.model_container_path,
            ENV_MODEL_ALIAS: self.model_alias,
            ENV_CONTEXT_SIZE: str(self.context_size_tokens),
            ENV_THREADS: str(self.threads),
            ENV_STARTUP_BUDGET_MS: str(self.startup_budget_ms),
            ENV_METRICS_ENABLED: str(self.metrics_enabled).lower(),
        }

    def startup_command(self) -> tuple[str, ...]:
        """Return the exact pinned executable and arguments."""
        return (self.command, *self.arguments)


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeConfigurationError(
            f"runtime profile field '{field}' must be an object"
        )
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeConfigurationError(
            f"runtime profile field '{field}' must be a string"
        )
    return value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise RuntimeConfigurationError(
            f"runtime profile field '{field}' must be an integer of at least {minimum}"
        )
    return value


def _number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RuntimeConfigurationError(
            f"runtime profile field '{field}' must be a number"
        )
    return float(value)


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeConfigurationError(
            f"runtime profile field '{field}' must be a boolean"
        )
    return value


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RuntimeConfigurationError(
            f"runtime profile field '{field}' must be a list of strings"
        )
    return tuple(value)


def _require_keys(value: Mapping[str, Any], field: str, expected: set[str]) -> None:
    if set(value) != expected:
        raise RuntimeConfigurationError(
            f"runtime profile field '{field}' has missing or unsupported members"
        )


def _read_profile(path: Path) -> dict[str, Any]:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeConfigurationError(
            "the committed runtime profile is unreadable"
        ) from error
    return _object(value, "root")


def load_runtime_profile(path: Path = RUNTIME_PROFILE_PATH) -> RuntimeProfile:
    """Load the profile and refuse unsafe values or drift from public pins."""
    record = _read_profile(path)
    runtime = _object(record.get("runtime"), "runtime")
    model = _object(record.get("model"), "model")
    network = _object(record.get("network"), "network")
    resources = _object(record.get("resources"), "resources")
    accelerator = _object(resources.get("accelerator"), "resources.accelerator")
    serving = _object(record.get("serving"), "serving")
    timeouts = _object(record.get("timeouts"), "timeouts")
    health = _object(record.get("health"), "health")
    startup = _object(health.get("startup"), "health.startup")
    readiness = _object(health.get("readiness"), "health.readiness")
    liveness = _object(health.get("liveness"), "health.liveness")
    metrics = _object(record.get("metrics"), "metrics")
    secrets = _object(record.get("secrets"), "secrets")

    _require_keys(
        record,
        "root",
        {
            "schemaVersion",
            "profileId",
            "environment",
            "evidenceClass",
            "runtime",
            "model",
            "network",
            "resources",
            "serving",
            "timeouts",
            "health",
            "metrics",
            "secrets",
        },
    )
    _require_keys(
        runtime,
        "runtime",
        {"runtimeId", "imageReference", "sourceRevision", "command", "arguments"},
    )
    _require_keys(
        model,
        "model",
        {
            "sourceRecord",
            "cacheRoot",
            "artifactRelativePath",
            "containerPath",
            "readOnly",
            "embeddedInImage",
            "alias",
            "platformIdentifier",
        },
    )
    _require_keys(
        network,
        "network",
        {"listenHost", "containerPort", "adapterEndpoint"},
    )
    _require_keys(
        resources,
        "resources",
        {
            "cpuRequestCores",
            "cpuLimitCores",
            "memoryRequestMiB",
            "memoryLimitMiB",
            "accelerator",
        },
    )
    _require_keys(accelerator, "resources.accelerator", {"kind", "count"})
    _require_keys(
        serving,
        "serving",
        {
            "contextSizeTokens",
            "defaultMaxOutputTokens",
            "defaultTemperature",
            "threads",
            "parallelSlots",
        },
    )
    _require_keys(
        timeouts,
        "timeouts",
        {"startupBudgetMs", "requestBudgetMs", "drainBudgetMs"},
    )
    _require_keys(health, "health", {"startup", "readiness", "liveness"})
    probe_keys = {"kind", "path", "port", "readyStatus", "loadingStatus"}
    _require_keys(startup, "health.startup", probe_keys)
    _require_keys(readiness, "health.readiness", probe_keys)
    _require_keys(liveness, "health.liveness", {"kind", "port"})
    _require_keys(metrics, "metrics", {"enabled", "path", "port"})
    _require_keys(secrets, "secrets", {"externalOnly", "embeddedValues"})

    profile = RuntimeProfile(
        schema_version=_string(record.get("schemaVersion"), "schemaVersion"),
        profile_id=_string(record.get("profileId"), "profileId"),
        environment=_string(record.get("environment"), "environment"),
        evidence_class=_string(record.get("evidenceClass"), "evidenceClass"),
        runtime_id=_string(runtime.get("runtimeId"), "runtime.runtimeId"),
        image_reference=_string(
            runtime.get("imageReference"), "runtime.imageReference"
        ),
        source_revision=_string(
            runtime.get("sourceRevision"), "runtime.sourceRevision"
        ),
        command=_string(runtime.get("command"), "runtime.command"),
        arguments=_string_list(runtime.get("arguments"), "runtime.arguments"),
        model_source_record=_string(model.get("sourceRecord"), "model.sourceRecord"),
        model_cache_root=Path(_string(model.get("cacheRoot"), "model.cacheRoot")),
        model_artifact_relative_path=Path(
            _string(model.get("artifactRelativePath"), "model.artifactRelativePath")
        ),
        model_container_path=_string(model.get("containerPath"), "model.containerPath"),
        model_read_only=_boolean(model.get("readOnly"), "model.readOnly"),
        model_embedded_in_image=_boolean(
            model.get("embeddedInImage"), "model.embeddedInImage"
        ),
        model_alias=_string(model.get("alias"), "model.alias"),
        platform_identifier=_string(
            model.get("platformIdentifier"), "model.platformIdentifier"
        ),
        listen_host=_string(network.get("listenHost"), "network.listenHost"),
        container_port=_integer(network.get("containerPort"), "network.containerPort"),
        adapter_endpoint=_string(
            network.get("adapterEndpoint"), "network.adapterEndpoint"
        ),
        cpu_request_cores=_integer(
            resources.get("cpuRequestCores"), "resources.cpuRequestCores"
        ),
        cpu_limit_cores=_integer(
            resources.get("cpuLimitCores"), "resources.cpuLimitCores"
        ),
        memory_request_mib=_integer(
            resources.get("memoryRequestMiB"), "resources.memoryRequestMiB"
        ),
        memory_limit_mib=_integer(
            resources.get("memoryLimitMiB"), "resources.memoryLimitMiB"
        ),
        accelerator_kind=_string(accelerator.get("kind"), "resources.accelerator.kind"),
        accelerator_count=_integer(
            accelerator.get("count"), "resources.accelerator.count", minimum=0
        ),
        context_size_tokens=_integer(
            serving.get("contextSizeTokens"), "serving.contextSizeTokens"
        ),
        default_max_output_tokens=_integer(
            serving.get("defaultMaxOutputTokens"), "serving.defaultMaxOutputTokens"
        ),
        default_temperature=_number(
            serving.get("defaultTemperature"), "serving.defaultTemperature"
        ),
        threads=_integer(serving.get("threads"), "serving.threads"),
        parallel_slots=_integer(serving.get("parallelSlots"), "serving.parallelSlots"),
        startup_budget_ms=_integer(
            timeouts.get("startupBudgetMs"), "timeouts.startupBudgetMs"
        ),
        request_budget_ms=_integer(
            timeouts.get("requestBudgetMs"), "timeouts.requestBudgetMs"
        ),
        drain_budget_ms=_integer(
            timeouts.get("drainBudgetMs"), "timeouts.drainBudgetMs"
        ),
        startup_kind=_string(startup.get("kind"), "health.startup.kind"),
        startup_path=_string(startup.get("path"), "health.startup.path"),
        startup_port=_integer(startup.get("port"), "health.startup.port"),
        startup_ready_status=_integer(
            startup.get("readyStatus"), "health.startup.readyStatus"
        ),
        startup_loading_status=_integer(
            startup.get("loadingStatus"), "health.startup.loadingStatus"
        ),
        readiness_kind=_string(readiness.get("kind"), "health.readiness.kind"),
        readiness_path=_string(readiness.get("path"), "health.readiness.path"),
        readiness_port=_integer(readiness.get("port"), "health.readiness.port"),
        readiness_ready_status=_integer(
            readiness.get("readyStatus"), "health.readiness.readyStatus"
        ),
        readiness_loading_status=_integer(
            readiness.get("loadingStatus"), "health.readiness.loadingStatus"
        ),
        liveness_kind=_string(liveness.get("kind"), "health.liveness.kind"),
        liveness_port=_integer(liveness.get("port"), "health.liveness.port"),
        metrics_enabled=_boolean(metrics.get("enabled"), "metrics.enabled"),
        metrics_path=_string(metrics.get("path"), "metrics.path"),
        metrics_port=_integer(metrics.get("port"), "metrics.port"),
        secrets_external_only=_boolean(
            secrets.get("externalOnly"), "secrets.externalOnly"
        ),
        embedded_secret_values=_string_list(
            secrets.get("embeddedValues"), "secrets.embeddedValues"
        ),
    )
    _validate_profile(profile)
    return profile


def _expected_arguments(profile: RuntimeProfile) -> tuple[str, ...]:
    temperature = f"{profile.default_temperature:g}"
    arguments = (
        "--model",
        profile.model_container_path,
        "--alias",
        profile.model_alias,
        "--host",
        profile.listen_host,
        "--port",
        str(profile.container_port),
        "--ctx-size",
        str(profile.context_size_tokens),
        "--threads",
        str(profile.threads),
        "--parallel",
        str(profile.parallel_slots),
        "--n-predict",
        str(profile.default_max_output_tokens),
        "--temp",
        temperature,
    )
    return (*arguments, "--metrics") if profile.metrics_enabled else arguments


def _validate_profile(profile: RuntimeProfile) -> None:
    if (
        profile.schema_version != EXPECTED_SCHEMA_VERSION
        or profile.profile_id != EXPECTED_PROFILE_ID
        or profile.environment != EXPECTED_ENVIRONMENT
        or profile.evidence_class != EXPECTED_EVIDENCE_CLASS
    ):
        raise RuntimeConfigurationError("the runtime profile identity is unsupported")
    if (
        profile.runtime_id != LLAMA_SERVER_RUNTIME_ID
        or profile.image_reference != PINNED_IMAGE_REFERENCE
        or profile.source_revision != PINNED_SOURCE_REVISION
        or profile.command != PINNED_COMMAND
    ):
        raise RuntimeConfigurationError(
            "the runtime profile has drifted from the runtime pin"
        )

    if profile.model_source_record != EXPECTED_MODEL_SOURCE_REF:
        raise RuntimeConfigurationError(
            "the runtime profile must name the committed model source record"
        )
    try:
        manifest = load_manifest(REPO_ROOT / EXPECTED_MODEL_SOURCE_REF)
    except ModelAcquisitionError as error:
        raise RuntimeConfigurationError(
            "the committed model source record is incompatible with the runtime profile"
        ) from error
    if (
        profile.model_cache_root != manifest.cache_path
        or profile.model_artifact_relative_path != manifest.artifact_relative_path
        or profile.model_cache_root.is_absolute()
        or profile.model_artifact_relative_path.is_absolute()
        or ".." in profile.model_artifact_relative_path.parts
        or profile.model_container_path
        != f"{EXPECTED_CONTAINER_DIRECTORY}/{PINNED_MODEL_FILE}"
        or not profile.model_read_only
        or profile.model_embedded_in_image
    ):
        raise RuntimeConfigurationError(
            "the model must be the pinned external cache artifact mounted read-only"
        )
    if not (1 <= profile.container_port <= 65535):
        raise RuntimeConfigurationError("the runtime port must be between 1 and 65535")
    endpoint = urlsplit(profile.adapter_endpoint)
    try:
        endpoint_port = endpoint.port
    except ValueError:
        raise RuntimeConfigurationError(
            "the local adapter endpoint has an invalid port"
        ) from None
    if (
        profile.listen_host != EXPECTED_LISTEN_HOST
        or endpoint.scheme != "http"
        or endpoint.hostname != EXPECTED_ADAPTER_HOST
        or endpoint_port != profile.container_port
    ):
        raise RuntimeConfigurationError(
            "the local bind and adapter endpoint must match the selected network profile"
        )
    if profile.cpu_request_cores > profile.cpu_limit_cores:
        raise RuntimeConfigurationError("the CPU request must not exceed the CPU limit")
    if profile.memory_request_mib > profile.memory_limit_mib:
        raise RuntimeConfigurationError(
            "the memory request must not exceed the memory limit"
        )
    if (
        profile.accelerator_kind != EXPECTED_ACCELERATOR_KIND
        or profile.accelerator_count != 0
    ):
        raise RuntimeConfigurationError(
            "the selected local CPU profile must not claim an accelerator"
        )
    if profile.default_max_output_tokens > profile.context_size_tokens:
        raise RuntimeConfigurationError(
            "the default output-token limit must not exceed the context limit"
        )
    if not 0 <= profile.default_temperature <= 2:
        raise RuntimeConfigurationError(
            "the default temperature must be between zero and two"
        )
    if profile.drain_budget_ms != DEFAULT_DRAIN_TIMEOUT_MS:
        raise RuntimeConfigurationError(
            "the drain budget must match the API lifecycle default"
        )
    if (
        profile.startup_kind != "http"
        or profile.startup_path != HEALTH_PATH
        or profile.startup_ready_status != HEALTH_READY_STATUS
        or profile.startup_loading_status != HEALTH_LOADING_STATUS
        or profile.readiness_kind != "http"
        or profile.readiness_path != HEALTH_PATH
        or profile.readiness_ready_status != HEALTH_READY_STATUS
        or profile.readiness_loading_status != HEALTH_LOADING_STATUS
    ):
        raise RuntimeConfigurationError(
            "startup and readiness must distinguish model loading from ready"
        )
    if profile.liveness_kind != "tcp":
        raise RuntimeConfigurationError(
            "liveness must not use model readiness while the model is loading"
        )
    if not profile.metrics_enabled or profile.metrics_path != METRICS_PATH:
        raise RuntimeConfigurationError("the selected runtime metrics must be enabled")
    ports = {
        profile.startup_port,
        profile.readiness_port,
        profile.liveness_port,
        profile.metrics_port,
    }
    if ports != {profile.container_port}:
        raise RuntimeConfigurationError(
            "every health and metrics endpoint must use the configured runtime port"
        )
    if not profile.secrets_external_only or profile.embedded_secret_values:
        raise RuntimeConfigurationError(
            "the runtime profile must not contain embedded secret values"
        )
    if profile.arguments != _expected_arguments(profile):
        raise RuntimeConfigurationError(
            "the pinned startup arguments do not match the selected profile values"
        )

    environment: Mapping[str, str] = profile.adapter_environment()
    try:
        settings = LlamaServerSettings.from_environment(environment)
        AdapterConfiguration(
            model_identifier=profile.platform_identifier,
            timeout_ms=profile.request_budget_ms,
            max_tokens=profile.default_max_output_tokens,
        )
    except (InvalidAdapterConfigError, ValueError) as error:
        raise RuntimeConfigurationError(
            "the runtime profile is incompatible with the real adapter"
        ) from error
    if (
        settings.model_path != profile.model_container_path
        or settings.context_size != profile.context_size_tokens
        or settings.threads != profile.threads
        or settings.startup_budget_ms != profile.startup_budget_ms
        or settings.metrics_enabled is not profile.metrics_enabled
    ):
        raise RuntimeConfigurationError(
            "the runtime profile does not translate losslessly to adapter settings"
        )


def validate_runtime_profile(path: Path = RUNTIME_PROFILE_PATH) -> RuntimeProfile:
    """Public validation entry point used by tests and the repository CLI."""
    return load_runtime_profile(path)
