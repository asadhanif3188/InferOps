"""Package and smoke-check the selected runtime through a bounded Docker seam.

The committed package descriptor is the authority for the container boundary.
The default checks parse it, compare it with the selected runtime profile, and
exercise orchestration through injected command and HTTP seams. Real execution
is opt-in and never downloads a model or image implicitly.
"""

from __future__ import annotations

import json
import socket
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tools.model_acquisition import (
    ModelAcquisitionError,
    load_manifest,
    verify_artifact,
)
from tools.runtime_configuration import RuntimeProfile, load_runtime_profile

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = REPO_ROOT / "deploy/serving/runtime/container-package.v1.json"
EXPECTED_SCHEMA_VERSION = "inferops.io/v1alpha1"
EXPECTED_PACKAGE_ID = "llama-cpp-local-runtime"
EXPECTED_ENGINE = "docker"
EXPECTED_PROFILE_REF = "docs/serving/runtime-profile.local.v1.json"
EXPECTED_CONTAINER_NAME = "inferops-llama-server"
OWNERSHIP_LABEL = "io.inferops.package"
COMPONENT_LABEL = "io.inferops.component"
EXPECTED_COMPONENT = "serving-runtime"
MODEL_SOURCE_SENTINEL = "profile:model-cache-artifact"
ENGINE_COMMAND_TIMEOUT_SECONDS = 30.0


class RuntimePackagingError(RuntimeError):
    """A package invariant or bounded runtime operation failed."""


class RuntimeEndpointUnavailable(RuntimePackagingError):
    """The loopback readiness endpoint could not yet be reached."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """The result of one container-engine command, with output kept internal."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    """The command boundary used by the package lifecycle."""

    def run(self, arguments: Sequence[str]) -> CommandResult: ...


class SubprocessRunner:
    """Run Docker without a shell and capture text that is never passed through."""

    def __init__(
        self, *, timeout_seconds: float = ENGINE_COMMAND_TIMEOUT_SECONDS
    ) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: Sequence[str]) -> CommandResult:
        try:
            completed = subprocess.run(
                list(arguments),
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimePackagingError(
                "the container engine command exceeded its deadline"
            ) from error
        except OSError as error:
            raise RuntimePackagingError(
                "the container engine could not be executed"
            ) from error
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """The status and parsed body retained from a local runtime response."""

    status: int
    body: object | None = None


HttpGet = Callable[[str, float], HttpResponse]
HttpPost = Callable[[str, Mapping[str, object], float], HttpResponse]
Clock = Callable[[], float]
Sleeper = Callable[[float], None]
TcpProbe = Callable[[str, int, float], bool]


@dataclass(frozen=True, slots=True)
class RuntimePackage:
    """The selected container package after validation against its profile."""

    schema_version: str
    package_id: str
    engine: str
    profile_ref: str
    container_name: str
    image_reference: str
    pull_policy: str
    entrypoint: str
    user: str
    read_only_root_filesystem: bool
    restart_policy: str
    labels: Mapping[str, str]
    model_source: str
    model_target: str
    model_read_only: bool
    temporary_target: str
    temporary_size_mib: int
    temporary_options: tuple[str, ...]
    published_host: str
    published_port: int
    container_port: int
    cpu_request_cores: int
    cpu_limit_cores: int
    memory_request_mib: int
    memory_limit_mib: int
    pids_limit: int
    accelerator_kind: str
    accelerator_count: int
    no_new_privileges: bool
    capabilities_drop: tuple[str, ...]
    embedded_secrets: tuple[str, ...]
    stop_timeout_seconds: int
    startup_budget_ms: int
    poll_interval_ms: int
    loading_status: int
    ready_status: int
    readiness_path: str
    liveness_kind: str
    liveness_port: int
    smoke_request_path: str
    smoke_request_timeout_ms: int
    smoke_max_output_tokens: int
    smoke_temperature: float
    smoke_prompt: str
    smoke_enable_thinking: bool

    @property
    def base_url(self) -> str:
        """The loopback-only endpoint exposed by the standalone package."""
        return f"http://{self.published_host}:{self.published_port}"

    @property
    def readiness_url(self) -> str:
        return f"{self.base_url}{self.readiness_path}"

    @property
    def smoke_url(self) -> str:
        return f"{self.base_url}{self.smoke_request_path}"


@dataclass(frozen=True, slots=True)
class ReadinessTrace:
    """Sanitized readiness observations from one bounded wait."""

    statuses: tuple[int, ...]
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class SmokeResult:
    """A completed local-real startup, inference probe, and shutdown."""

    readiness: ReadinessTrace
    inference_status: int
    stopped: bool


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimePackagingError(f"package field '{field}' must be an object")
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimePackagingError(f"package field '{field}' must be a string")
    return value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise RuntimePackagingError(
            f"package field '{field}' must be an integer of at least {minimum}"
        )
    return value


def _number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RuntimePackagingError(f"package field '{field}' must be a number")
    return float(value)


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimePackagingError(f"package field '{field}' must be a boolean")
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RuntimePackagingError(f"package field '{field}' must be a string list")
    return tuple(value)


def _string_mapping(value: Any, field: str) -> Mapping[str, str]:
    record = _object(value, field)
    if any(not isinstance(value, str) for value in record.values()):
        raise RuntimePackagingError(f"package field '{field}' must map strings")
    return cast(dict[str, str], record)


def _require_keys(value: Mapping[str, Any], field: str, expected: set[str]) -> None:
    if set(value) != expected:
        raise RuntimePackagingError(
            f"package field '{field}' has missing or unsupported members"
        )


def _read(path: Path) -> dict[str, Any]:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimePackagingError("the runtime package is unreadable") from error
    return _object(value, "root")


def load_runtime_package(path: Path = PACKAGE_PATH) -> RuntimePackage:
    """Load the package descriptor and validate it against the runtime profile."""
    record = _read(path)
    container = _object(record.get("container"), "container")
    model = _object(record.get("modelMount"), "modelMount")
    temporary = _object(record.get("temporaryFilesystem"), "temporaryFilesystem")
    network = _object(record.get("network"), "network")
    resources = _object(record.get("resources"), "resources")
    accelerator = _object(resources.get("accelerator"), "resources.accelerator")
    security = _object(record.get("security"), "security")
    lifecycle = _object(record.get("lifecycle"), "lifecycle")
    liveness = _object(lifecycle.get("liveness"), "lifecycle.liveness")
    smoke = _object(record.get("smoke"), "smoke")
    chat_template = _object(smoke.get("chatTemplate"), "smoke.chatTemplate")

    _require_keys(
        record,
        "root",
        {
            "schemaVersion",
            "packageId",
            "engine",
            "profileRef",
            "container",
            "modelMount",
            "temporaryFilesystem",
            "network",
            "resources",
            "security",
            "lifecycle",
            "smoke",
        },
    )
    _require_keys(
        container,
        "container",
        {
            "name",
            "imageReference",
            "pullPolicy",
            "entrypoint",
            "user",
            "readOnlyRootFilesystem",
            "restartPolicy",
            "labels",
        },
    )
    _require_keys(model, "modelMount", {"source", "target", "readOnly"})
    _require_keys(temporary, "temporaryFilesystem", {"target", "sizeMiB", "options"})
    _require_keys(
        network, "network", {"publishedHost", "publishedPort", "containerPort"}
    )
    _require_keys(
        resources,
        "resources",
        {
            "cpuRequestCores",
            "cpuLimitCores",
            "memoryRequestMiB",
            "memoryLimitMiB",
            "pidsLimit",
            "accelerator",
        },
    )
    _require_keys(accelerator, "resources.accelerator", {"kind", "count"})
    _require_keys(
        security,
        "security",
        {"noNewPrivileges", "capabilitiesDrop", "embeddedSecrets"},
    )
    _require_keys(
        lifecycle,
        "lifecycle",
        {
            "stopTimeoutSeconds",
            "startupBudgetMs",
            "pollIntervalMs",
            "loadingStatus",
            "readyStatus",
            "readinessPath",
            "liveness",
        },
    )
    _require_keys(liveness, "lifecycle.liveness", {"kind", "port"})
    _require_keys(
        smoke,
        "smoke",
        {
            "requestPath",
            "requestTimeoutMs",
            "maxOutputTokens",
            "temperature",
            "prompt",
            "chatTemplate",
        },
    )
    _require_keys(chat_template, "smoke.chatTemplate", {"enableThinking"})

    package = RuntimePackage(
        schema_version=_string(record.get("schemaVersion"), "schemaVersion"),
        package_id=_string(record.get("packageId"), "packageId"),
        engine=_string(record.get("engine"), "engine"),
        profile_ref=_string(record.get("profileRef"), "profileRef"),
        container_name=_string(container.get("name"), "container.name"),
        image_reference=_string(
            container.get("imageReference"), "container.imageReference"
        ),
        pull_policy=_string(container.get("pullPolicy"), "container.pullPolicy"),
        entrypoint=_string(container.get("entrypoint"), "container.entrypoint"),
        user=_string(container.get("user"), "container.user"),
        read_only_root_filesystem=_boolean(
            container.get("readOnlyRootFilesystem"),
            "container.readOnlyRootFilesystem",
        ),
        restart_policy=_string(
            container.get("restartPolicy"), "container.restartPolicy"
        ),
        labels=_string_mapping(container.get("labels"), "container.labels"),
        model_source=_string(model.get("source"), "modelMount.source"),
        model_target=_string(model.get("target"), "modelMount.target"),
        model_read_only=_boolean(model.get("readOnly"), "modelMount.readOnly"),
        temporary_target=_string(temporary.get("target"), "temporaryFilesystem.target"),
        temporary_size_mib=_integer(
            temporary.get("sizeMiB"), "temporaryFilesystem.sizeMiB"
        ),
        temporary_options=_strings(
            temporary.get("options"), "temporaryFilesystem.options"
        ),
        published_host=_string(network.get("publishedHost"), "network.publishedHost"),
        published_port=_integer(network.get("publishedPort"), "network.publishedPort"),
        container_port=_integer(network.get("containerPort"), "network.containerPort"),
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
        pids_limit=_integer(resources.get("pidsLimit"), "resources.pidsLimit"),
        accelerator_kind=_string(accelerator.get("kind"), "resources.accelerator.kind"),
        accelerator_count=_integer(
            accelerator.get("count"), "resources.accelerator.count", minimum=0
        ),
        no_new_privileges=_boolean(
            security.get("noNewPrivileges"), "security.noNewPrivileges"
        ),
        capabilities_drop=_strings(
            security.get("capabilitiesDrop"), "security.capabilitiesDrop"
        ),
        embedded_secrets=_strings(
            security.get("embeddedSecrets"), "security.embeddedSecrets"
        ),
        stop_timeout_seconds=_integer(
            lifecycle.get("stopTimeoutSeconds"), "lifecycle.stopTimeoutSeconds"
        ),
        startup_budget_ms=_integer(
            lifecycle.get("startupBudgetMs"), "lifecycle.startupBudgetMs"
        ),
        poll_interval_ms=_integer(
            lifecycle.get("pollIntervalMs"), "lifecycle.pollIntervalMs"
        ),
        loading_status=_integer(
            lifecycle.get("loadingStatus"), "lifecycle.loadingStatus"
        ),
        ready_status=_integer(lifecycle.get("readyStatus"), "lifecycle.readyStatus"),
        readiness_path=_string(
            lifecycle.get("readinessPath"), "lifecycle.readinessPath"
        ),
        liveness_kind=_string(liveness.get("kind"), "lifecycle.liveness.kind"),
        liveness_port=_integer(liveness.get("port"), "lifecycle.liveness.port"),
        smoke_request_path=_string(smoke.get("requestPath"), "smoke.requestPath"),
        smoke_request_timeout_ms=_integer(
            smoke.get("requestTimeoutMs"), "smoke.requestTimeoutMs"
        ),
        smoke_max_output_tokens=_integer(
            smoke.get("maxOutputTokens"), "smoke.maxOutputTokens"
        ),
        smoke_temperature=_number(smoke.get("temperature"), "smoke.temperature"),
        smoke_prompt=_string(smoke.get("prompt"), "smoke.prompt"),
        smoke_enable_thinking=_boolean(
            chat_template.get("enableThinking"), "smoke.chatTemplate.enableThinking"
        ),
    )
    _validate(package, load_runtime_profile())
    return package


def _validate(package: RuntimePackage, profile: RuntimeProfile) -> None:
    if (
        package.schema_version != EXPECTED_SCHEMA_VERSION
        or package.package_id != EXPECTED_PACKAGE_ID
        or package.engine != EXPECTED_ENGINE
        or package.profile_ref != EXPECTED_PROFILE_REF
        or package.container_name != EXPECTED_CONTAINER_NAME
    ):
        raise RuntimePackagingError("the runtime package identity is unsupported")
    if (
        package.image_reference != profile.image_reference
        or package.entrypoint != profile.command
        or package.pull_policy != "never"
    ):
        raise RuntimePackagingError("the runtime package has drifted from its pin")
    if (
        package.model_source != MODEL_SOURCE_SENTINEL
        or package.model_target != profile.model_container_path
        or not package.model_read_only
    ):
        raise RuntimePackagingError(
            "the package must mount the selected cache artifact read-only"
        )
    if (
        package.user != "65534:65534"
        or not package.read_only_root_filesystem
        or package.restart_policy != "no"
        or not package.no_new_privileges
        or package.capabilities_drop != ("ALL",)
        or package.embedded_secrets
    ):
        raise RuntimePackagingError("the package has weakened its container boundary")
    if package.labels != {
        COMPONENT_LABEL: EXPECTED_COMPONENT,
        OWNERSHIP_LABEL: EXPECTED_PACKAGE_ID,
    }:
        raise RuntimePackagingError("the package ownership labels are incomplete")
    expected_tmp_options = (
        "rw",
        "noexec",
        "nosuid",
        "nodev",
        "uid=65534",
        "gid=65534",
    )
    if (
        package.temporary_target != "/tmp"
        or package.temporary_size_mib != 64
        or package.temporary_options != expected_tmp_options
    ):
        raise RuntimePackagingError("the package temporary filesystem is unsupported")
    if (
        package.published_host != "127.0.0.1"
        or package.published_port != profile.container_port
        or package.container_port != profile.container_port
    ):
        raise RuntimePackagingError(
            "the package must expose only the selected loopback port"
        )
    if (
        package.cpu_request_cores != profile.cpu_request_cores
        or package.cpu_limit_cores != profile.cpu_limit_cores
        or package.memory_request_mib != profile.memory_request_mib
        or package.memory_limit_mib != profile.memory_limit_mib
        or package.accelerator_kind != profile.accelerator_kind
        or package.accelerator_count != profile.accelerator_count
    ):
        raise RuntimePackagingError(
            "the package resources have drifted from the profile"
        )
    if package.pids_limit < 2:
        raise RuntimePackagingError("the package process limit is too small")
    if (
        package.stop_timeout_seconds * 1000 != profile.drain_budget_ms
        or package.startup_budget_ms != profile.startup_budget_ms
        or package.loading_status != profile.startup_loading_status
        or package.ready_status != profile.startup_ready_status
        or package.readiness_path != profile.startup_path
        or package.liveness_kind != profile.liveness_kind
        or package.liveness_port != profile.liveness_port
    ):
        raise RuntimePackagingError(
            "the package lifecycle has drifted from the profile"
        )
    if package.poll_interval_ms > package.startup_budget_ms:
        raise RuntimePackagingError("the readiness interval exceeds the startup budget")
    if (
        package.smoke_request_path != "/v1/chat/completions"
        or package.smoke_request_timeout_ms != profile.request_budget_ms
        or package.smoke_max_output_tokens > profile.default_max_output_tokens
        or package.smoke_temperature != profile.default_temperature
        or package.smoke_enable_thinking
    ):
        raise RuntimePackagingError(
            "the smoke request is incompatible with the profile"
        )


def model_artifact_path(
    package: RuntimePackage,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Resolve the selected artifact from its validated workspace cache record."""
    del package
    manifest = load_manifest()
    return manifest.artifact_path(repo_root).resolve()


def docker_run_command(
    package: RuntimePackage,
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    """Build the exact shell-free startup command for the selected package."""
    profile = load_runtime_profile()
    artifact = model_artifact_path(package, repo_root=repo_root)
    mount = f"type=bind,src={artifact},dst={package.model_target},readonly"
    temporary = f"{package.temporary_target}:" + ",".join(
        (*package.temporary_options, f"size={package.temporary_size_mib}m")
    )
    command = [
        package.engine,
        "run",
        "--detach",
        "--name",
        package.container_name,
        "--pull",
        package.pull_policy,
        "--restart",
        package.restart_policy,
        "--user",
        package.user,
        "--read-only",
        "--security-opt",
        "no-new-privileges=true",
        "--cap-drop",
        "ALL",
        "--pids-limit",
        str(package.pids_limit),
        "--cpus",
        str(package.cpu_limit_cores),
        "--memory",
        f"{package.memory_limit_mib}m",
        "--mount",
        mount,
        "--tmpfs",
        temporary,
        "--publish",
        f"{package.published_host}:{package.published_port}:{package.container_port}",
    ]
    for key, value in sorted(package.labels.items()):
        command.extend(("--label", f"{key}={value}"))
    command.extend(("--entrypoint", package.entrypoint, package.image_reference))
    command.extend(profile.arguments)
    return tuple(command)


def _require_confirmation(confirmed: bool) -> None:
    if not confirmed:
        raise RuntimePackagingError(
            "real runtime execution requires --confirm-real-runtime"
        )


def _docker_ok(runner: CommandRunner, arguments: Sequence[str], message: str) -> str:
    result = runner.run(arguments)
    if result.returncode != 0:
        raise RuntimePackagingError(message)
    return result.stdout.strip()


def owned_container_exists(package: RuntimePackage, runner: CommandRunner) -> bool:
    """Return whether the exact package-owned container exists."""
    result = runner.run(
        (
            package.engine,
            "container",
            "inspect",
            "--format",
            f'{{{{index .Config.Labels "{OWNERSHIP_LABEL}"}}}}',
            package.container_name,
        )
    )
    if result.returncode != 0:
        listing = runner.run(
            (
                package.engine,
                "container",
                "ls",
                "--all",
                "--filter",
                f"name=^/{package.container_name}$",
                "--format",
                "{{.Names}}",
            )
        )
        if listing.returncode != 0:
            raise RuntimePackagingError("container ownership could not be verified")
        names = {line.strip() for line in listing.stdout.splitlines() if line.strip()}
        if package.container_name in names:
            raise RuntimePackagingError("container ownership could not be verified")
        if names:
            raise RuntimePackagingError("the container inventory was unexpected")
        return False
    if result.stdout.strip() != package.package_id:
        raise RuntimePackagingError(
            "the selected container name is owned by something else"
        )
    return True


def container_is_running(package: RuntimePackage, runner: CommandRunner) -> bool:
    """Return the startup process guard, independently of model readiness."""
    result = runner.run(
        (
            package.engine,
            "container",
            "inspect",
            "--format",
            "{{.State.Running}}",
            package.container_name,
        )
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def tcp_is_live(
    package: RuntimePackage,
    *,
    probe: TcpProbe | None = None,
    timeout_seconds: float = 1.0,
) -> bool:
    """Apply the profile's independent TCP liveness rule."""
    if probe is not None:
        return probe(package.published_host, package.liveness_port, timeout_seconds)
    try:
        connection = socket.create_connection(
            (package.published_host, package.liveness_port),
            timeout=timeout_seconds,
        )
    except OSError:
        return False
    connection.close()
    return True


def preflight(
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Require Docker, the pinned image, and hash-verified cached model bytes."""
    _docker_ok(
        runner,
        (package.engine, "version", "--format", "{{.Server.Version}}"),
        "the Docker engine is unavailable",
    )
    _docker_ok(
        runner,
        (package.engine, "image", "inspect", package.image_reference),
        "the pinned runtime image is not local; pull it explicitly before execution",
    )
    manifest = load_manifest()
    artifact = model_artifact_path(package, repo_root=repo_root)
    try:
        verify_artifact(artifact, manifest)
    except ModelAcquisitionError as error:
        raise RuntimePackagingError(
            "the selected model is not present and hash-verified in the cache"
        ) from error
    return artifact


def start(
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    confirmed: bool,
    repo_root: Path = REPO_ROOT,
) -> None:
    """Start the owned container after all non-network prerequisites pass."""
    _require_confirmation(confirmed)
    preflight(package, runner, repo_root=repo_root)
    if owned_container_exists(package, runner):
        raise RuntimePackagingError(
            "the owned runtime container already exists; stop it before starting"
        )
    _docker_ok(
        runner,
        docker_run_command(package, repo_root=repo_root),
        "the runtime container did not start",
    )
    if not container_is_running(package, runner):
        if owned_container_exists(package, runner):
            _docker_ok(
                runner,
                (package.engine, "rm", package.container_name),
                "the exited runtime container could not be removed",
            )
        raise RuntimePackagingError("the runtime container exited during startup")


def wait_ready(
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    confirmed: bool,
    http_get: HttpGet,
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
) -> ReadinessTrace:
    """Wait through 503 loading responses until 200, bounded by the profile."""
    _require_confirmation(confirmed)
    if not owned_container_exists(package, runner):
        raise RuntimePackagingError("the owned runtime container is absent")
    started = clock()
    deadline = started + package.startup_budget_ms / 1000
    statuses: list[int] = []
    while True:
        if not container_is_running(package, runner):
            raise RuntimePackagingError(
                "the runtime container stopped before becoming ready"
            )
        try:
            response = http_get(
                package.readiness_url,
                min(package.poll_interval_ms / 1000, max(deadline - clock(), 0.001)),
            )
        except RuntimeEndpointUnavailable:
            response = HttpResponse(0)
        statuses.append(response.status)
        if response.status == package.ready_status:
            return ReadinessTrace(
                statuses=tuple(statuses),
                elapsed_ms=max(0, round((clock() - started) * 1000)),
            )
        if response.status not in (0, package.loading_status):
            raise RuntimePackagingError(
                "the runtime returned an unexpected readiness status"
            )
        if clock() >= deadline:
            raise RuntimePackagingError(
                "the runtime did not become ready within the startup budget"
            )
        sleeper(min(package.poll_interval_ms / 1000, deadline - clock()))


def inference_probe(
    package: RuntimePackage,
    *,
    http_post: HttpPost,
) -> int:
    """Issue one bounded direct-runtime probe and retain no generated content."""
    body: dict[str, object] = {
        "model": load_runtime_profile().model_alias,
        "messages": [{"role": "user", "content": package.smoke_prompt}],
        "temperature": package.smoke_temperature,
        "max_tokens": package.smoke_max_output_tokens,
        "chat_template_kwargs": {
            "enable_thinking": package.smoke_enable_thinking,
        },
    }
    response = http_post(
        package.smoke_url,
        body,
        package.smoke_request_timeout_ms / 1000,
    )
    if response.status != 200 or not isinstance(response.body, Mapping):
        raise RuntimePackagingError("the bounded inference probe did not succeed")
    choices = response.body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimePackagingError("the inference probe returned no completion choice")
    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise RuntimePackagingError(
            "the inference probe returned no completion message"
        )
    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise RuntimePackagingError(
            "the inference probe returned no completion message"
        )
    content = message.get("content")
    if not isinstance(content, str) or not content:
        raise RuntimePackagingError(
            "the inference probe returned no completion content"
        )
    return response.status


def stop(
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    confirmed: bool,
) -> bool:
    """Stop and remove only the container carrying this package's ownership label."""
    _require_confirmation(confirmed)
    if not owned_container_exists(package, runner):
        return False
    _docker_ok(
        runner,
        (
            package.engine,
            "stop",
            "--time",
            str(package.stop_timeout_seconds),
            package.container_name,
        ),
        "the owned runtime container did not stop",
    )
    _docker_ok(
        runner,
        (package.engine, "rm", package.container_name),
        "the stopped runtime container could not be removed",
    )
    return True


def smoke(
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    confirmed: bool,
    http_get: HttpGet,
    http_post: HttpPost,
    repo_root: Path = REPO_ROOT,
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
) -> SmokeResult:
    """Start, wait, prove one direct inference, and always attempt shutdown."""
    _require_confirmation(confirmed)
    started = False
    readiness: ReadinessTrace | None = None
    inference_status = 0
    stopped = False
    try:
        start(package, runner, confirmed=True, repo_root=repo_root)
        started = True
        readiness = wait_ready(
            package,
            runner,
            confirmed=True,
            http_get=http_get,
            clock=clock,
            sleeper=sleeper,
        )
        inference_status = inference_probe(package, http_post=http_post)
    finally:
        if started:
            stopped = stop(package, runner, confirmed=True)
            if not stopped:
                raise RuntimePackagingError(
                    "the runtime smoke could not verify complete shutdown"
                )
    if readiness is None:
        raise RuntimePackagingError("the runtime smoke did not reach readiness")
    return SmokeResult(readiness, inference_status, stopped)


def http_get(url: str, timeout_seconds: float) -> HttpResponse:
    """GET a local runtime endpoint and discard all response content."""
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return HttpResponse(response.status)
    except HTTPError as error:
        return HttpResponse(error.code)
    except (OSError, URLError) as error:
        raise RuntimeEndpointUnavailable(
            "the local runtime endpoint is unreachable"
        ) from error


def http_post(
    url: str,
    body: Mapping[str, object],
    timeout_seconds: float,
) -> HttpResponse:
    """POST JSON to the local runtime, parsing only the bounded response body."""
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload: object = json.loads(response.read().decode("utf-8"))
            return HttpResponse(response.status, payload)
    except (HTTPError, OSError, URLError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimePackagingError("the bounded inference probe failed") from error
