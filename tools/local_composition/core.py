"""Validate and operate the host-local real InferOps composition.

Offline loading proves that the descriptor agrees with the pinned runtime
profile and that the API selection is explicitly real. Runtime execution stays
behind an explicit confirmation and composes the existing owned Docker runtime
with a loopback-only ASGI carrier.
"""

from __future__ import annotations

import json
import threading
import time
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from inferops.api import MAX_REQUEST_BYTES, InferOpsApi
from inferops.api.selection import ADAPTER_REAL, build, select
from inferops.telemetry.resource import (
    ENV_CAPABILITY_ID,
    ENV_DEPLOYMENT_ENVIRONMENT,
    ENV_MODEL_REVISION,
    ENV_RUNTIME_IMAGE_DIGEST,
    ENV_SERVICE_VERSION,
)
from tools.model_acquisition import load_manifest
from tools.runtime_configuration import RuntimeProfile, load_runtime_profile
from tools.runtime_packaging import (
    CommandRunner,
    HttpResponse,
    RuntimePackage,
    SubprocessRunner,
    container_is_running,
    http_get,
    load_runtime_package,
    owned_container_exists,
    tcp_is_live,
)
from tools.runtime_packaging import (
    start as start_runtime,
)
from tools.runtime_packaging import (
    stop as stop_runtime,
)
from tools.runtime_packaging import (
    wait_ready as wait_runtime_ready,
)

from .http_server import LocalApiServer

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSITION_PATH = REPO_ROOT / "deploy/serving/local/composition.v1.json"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_ID = "inferops-local-real"
EXPECTED_EVIDENCE_CLASS = "local-static"
EXPECTED_RUNTIME_REF = "deploy/serving/runtime/container-package.v1.json"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_API_PORT = 8090
EXPECTED_LOG_PATH = Path(".cache/inferops/composition/local-real.jsonl")
EXPECTED_STARTUP_ORDER = (
    "runtime",
    "runtime-readiness",
    "api",
    "api-readiness",
)
EXPECTED_SHUTDOWN_ORDER = ("api", "runtime")
EXPECTED_CAPABILITY = "inferops-native-serving"
READY_BODY = {"status": "ready", "adapterKind": "real", "state": "serving"}


class CompositionError(RuntimeError):
    """The composition descriptor or an operation failed safely."""


@dataclass(frozen=True, slots=True)
class LocalComposition:
    schema_version: str
    composition_id: str
    evidence_class: str
    runtime_package_ref: str
    api_host: str
    api_port: int
    request_body_limit_bytes: int
    response_budget_ms: int
    readiness_path: str
    ready_status: int
    not_ready_status: int
    adapter_selection: str
    mock_fallback: bool
    environment: Mapping[str, str]
    startup_order: tuple[str, ...]
    shutdown_order: tuple[str, ...]
    engine_command_timeout_seconds: int
    log_path: Path
    loopback_only: bool
    embedded_secrets: tuple[str, ...]

    @property
    def api_base_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def api_readiness_url(self) -> str:
        return f"{self.api_base_url}{self.readiness_path}"


@dataclass(frozen=True, slots=True)
class StatusResult:
    profile: str
    adapter: str
    runtime_owned: bool
    runtime_running: bool
    runtime_live: bool
    runtime_ready: bool
    api_ready: bool

    @property
    def ready(self) -> bool:
        return self.runtime_ready and self.api_ready


@dataclass(frozen=True, slots=True)
class RunResult:
    runtime_readiness_ms: int
    api_readiness_ms: int
    api_drained: bool
    runtime_removed: bool


class ApiServer(Protocol):
    application: InferOpsApi

    def start(self) -> None: ...

    def serve_in_background(self) -> None: ...

    def request_stop(self) -> None: ...

    def join(self) -> None: ...

    def close(self) -> None: ...


class ServerFactory(Protocol):
    def __call__(
        self,
        application: InferOpsApi,
        *,
        host: str,
        port: int,
        request_body_limit_bytes: int,
        response_timeout_seconds: float,
        shutdown_timeout_seconds: float,
    ) -> ApiServer: ...


JsonGet = Callable[[str, float], HttpResponse]
ReadyCallback = Callable[[int, int], None]


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompositionError(f"composition field '{field}' must be an object")
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise CompositionError(f"composition field '{field}' must be a string")
    return value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise CompositionError(
            f"composition field '{field}' must be an integer of at least {minimum}"
        )
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise CompositionError(f"composition field '{field}' must be a boolean")
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CompositionError(f"composition field '{field}' must be a string list")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, str]:
    record = _object(value, field)
    if any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in record.items()
    ):
        raise CompositionError(f"composition field '{field}' must map strings")
    return cast(dict[str, str], record)


def _require_keys(record: Mapping[str, Any], field: str, expected: set[str]) -> None:
    if set(record) != expected:
        raise CompositionError(
            f"composition field '{field}' has missing or unsupported members"
        )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), "root")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CompositionError(
            "the local composition descriptor is unreadable"
        ) from error


def load_composition(path: Path = COMPOSITION_PATH) -> LocalComposition:
    """Load and cross-check the local-real descriptor without performing I/O."""
    record = _read_json(path)
    api = _object(record.get("api"), "api")
    adapter = _object(record.get("adapter"), "adapter")
    lifecycle = _object(record.get("lifecycle"), "lifecycle")
    security = _object(record.get("security"), "security")
    _require_keys(
        record,
        "root",
        {
            "schemaVersion",
            "compositionId",
            "evidenceClass",
            "runtimePackageRef",
            "api",
            "adapter",
            "lifecycle",
            "security",
        },
    )
    _require_keys(
        api,
        "api",
        {
            "host",
            "port",
            "requestBodyLimitBytes",
            "responseBudgetMs",
            "readinessPath",
            "readyStatus",
            "notReadyStatus",
        },
    )
    _require_keys(adapter, "adapter", {"selection", "mockFallback", "environment"})
    _require_keys(
        lifecycle,
        "lifecycle",
        {
            "startupOrder",
            "shutdownOrder",
            "engineCommandTimeoutSeconds",
            "logPath",
        },
    )
    _require_keys(security, "security", {"loopbackOnly", "embeddedSecrets"})
    composition = LocalComposition(
        schema_version=_string(record.get("schemaVersion"), "schemaVersion"),
        composition_id=_string(record.get("compositionId"), "compositionId"),
        evidence_class=_string(record.get("evidenceClass"), "evidenceClass"),
        runtime_package_ref=_string(
            record.get("runtimePackageRef"), "runtimePackageRef"
        ),
        api_host=_string(api.get("host"), "api.host"),
        api_port=_integer(api.get("port"), "api.port"),
        request_body_limit_bytes=_integer(
            api.get("requestBodyLimitBytes"), "api.requestBodyLimitBytes"
        ),
        response_budget_ms=_integer(
            api.get("responseBudgetMs"), "api.responseBudgetMs"
        ),
        readiness_path=_string(api.get("readinessPath"), "api.readinessPath"),
        ready_status=_integer(api.get("readyStatus"), "api.readyStatus"),
        not_ready_status=_integer(api.get("notReadyStatus"), "api.notReadyStatus"),
        adapter_selection=_string(adapter.get("selection"), "adapter.selection"),
        mock_fallback=_boolean(adapter.get("mockFallback"), "adapter.mockFallback"),
        environment=_mapping(adapter.get("environment"), "adapter.environment"),
        startup_order=_strings(lifecycle.get("startupOrder"), "lifecycle.startupOrder"),
        shutdown_order=_strings(
            lifecycle.get("shutdownOrder"), "lifecycle.shutdownOrder"
        ),
        engine_command_timeout_seconds=_integer(
            lifecycle.get("engineCommandTimeoutSeconds"),
            "lifecycle.engineCommandTimeoutSeconds",
        ),
        log_path=Path(_string(lifecycle.get("logPath"), "lifecycle.logPath")),
        loopback_only=_boolean(security.get("loopbackOnly"), "security.loopbackOnly"),
        embedded_secrets=_strings(
            security.get("embeddedSecrets"), "security.embeddedSecrets"
        ),
    )
    _validate(composition, load_runtime_profile(), load_runtime_package())
    return composition


def _api_version() -> str:
    try:
        with PYPROJECT_PATH.open("rb") as stream:
            document: Any = tomllib.load(stream)
        return _string(document["project"]["version"], "project.version")
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise CompositionError("the InferOps package version is unreadable") from error


def _expected_environment(
    profile: RuntimeProfile, package: RuntimePackage
) -> dict[str, str]:
    environment = profile.adapter_environment()
    environment["INFEROPS_LLAMA_SERVER_ENDPOINT"] = package.base_url
    environment.update(
        {
            ENV_SERVICE_VERSION: _api_version(),
            ENV_DEPLOYMENT_ENVIRONMENT: profile.environment,
            ENV_CAPABILITY_ID: EXPECTED_CAPABILITY,
            ENV_MODEL_REVISION: load_manifest().revision,
            ENV_RUNTIME_IMAGE_DIGEST: package.image_reference.split("@", 1)[1],
        }
    )
    return environment


def _validate(
    composition: LocalComposition,
    profile: RuntimeProfile,
    package: RuntimePackage,
) -> None:
    if (
        composition.schema_version != EXPECTED_SCHEMA
        or composition.composition_id != EXPECTED_ID
        or composition.evidence_class != EXPECTED_EVIDENCE_CLASS
        or composition.runtime_package_ref != EXPECTED_RUNTIME_REF
    ):
        raise CompositionError("the local composition identity is unsupported")
    if (
        composition.api_host != EXPECTED_HOST
        or composition.api_port != EXPECTED_API_PORT
        or not composition.loopback_only
        or composition.api_port == package.published_port
    ):
        raise CompositionError("the InferOps API must use its selected loopback port")
    if (
        composition.request_body_limit_bytes != MAX_REQUEST_BYTES
        or composition.response_budget_ms < profile.request_budget_ms
        or composition.response_budget_ms > profile.request_budget_ms + 2_000
        or composition.readiness_path != "/health/ready"
        or composition.ready_status != 200
        or composition.not_ready_status != 503
    ):
        raise CompositionError("the InferOps API boundary has drifted")
    if (
        composition.adapter_selection != ADAPTER_REAL
        or composition.mock_fallback
        or composition.environment != _expected_environment(profile, package)
    ):
        raise CompositionError("the composition must select only the real adapter")
    selected = select(composition.environment)
    if selected.selected != ADAPTER_REAL or selected.is_mock:
        raise CompositionError("the composition resolved something other than real")
    if (
        composition.startup_order != EXPECTED_STARTUP_ORDER
        or composition.shutdown_order != EXPECTED_SHUTDOWN_ORDER
        or composition.engine_command_timeout_seconds != 30
        or composition.log_path != EXPECTED_LOG_PATH
    ):
        raise CompositionError("the local composition lifecycle has drifted")
    if composition.embedded_secrets:
        raise CompositionError("the local composition must contain no secret value")


def composition_environment(composition: LocalComposition) -> dict[str, str]:
    """Return a copy of the validated, explicitly real API environment."""
    return dict(composition.environment)


class CompositionLog:
    """Write only structured, bounded local records to the fixed ignored path."""

    def __init__(
        self, composition: LocalComposition, *, repo_root: Path = REPO_ROOT
    ) -> None:
        self.path = (repo_root / composition.log_path).resolve()
        expected = (repo_root.resolve() / EXPECTED_LOG_PATH).resolve()
        if self.path != expected or self.path.is_symlink():
            raise CompositionError("the composition log path is unsafe")
        self._lock = threading.Lock()

    def reset(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def __call__(self, line: str) -> None:
        if "\n" in line or "\r" in line:
            raise CompositionError("a composition log record must be one line")
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{line}\n")

    def event(self, name: str, **fields: object) -> None:
        self(
            json.dumps({"event": name, **fields}, separators=(",", ":"), sort_keys=True)
        )


def read_logs(
    composition: LocalComposition,
    *,
    repo_root: Path = REPO_ROOT,
    lines: int = 100,
) -> tuple[str, ...]:
    """Read a bounded tail of the composition-owned structured log."""
    if lines < 1 or lines > 1_000:
        raise CompositionError("the log line count must be between 1 and 1000")
    log = CompositionLog(composition, repo_root=repo_root)
    if not log.path.exists():
        return ()
    try:
        if log.path.stat().st_size > 1_048_576:
            raise CompositionError(
                "the composition log exceeds its readable size bound"
            )
        return tuple(log.path.read_text(encoding="utf-8").splitlines()[-lines:])
    except (OSError, UnicodeError) as error:
        raise CompositionError("the composition log is unreadable") from error


def json_get(url: str, timeout_seconds: float) -> HttpResponse:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body: object = json.loads(response.read().decode("utf-8"))
            return HttpResponse(response.status, body)
    except HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            body = None
        return HttpResponse(error.code, body)
    except (OSError, URLError, UnicodeError, json.JSONDecodeError) as error:
        raise CompositionError("the loopback InferOps API is unreachable") from error


def wait_api_ready(
    composition: LocalComposition,
    *,
    get: JsonGet = json_get,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    """Wait for API readiness, which probes the selected real runtime."""
    started = clock()
    budget_seconds = composition.response_budget_ms / 1000
    deadline = started + budget_seconds
    while True:
        try:
            response = get(
                composition.api_readiness_url,
                min(1.0, max(deadline - clock(), 0.001)),
            )
        except CompositionError:
            response = HttpResponse(0)
        if response.status == composition.ready_status:
            if response.body != READY_BODY:
                raise CompositionError(
                    "the InferOps API readiness identity is not explicitly real"
                )
            return max(0, round((clock() - started) * 1000))
        if response.status not in (0, composition.not_ready_status):
            raise CompositionError(
                "the InferOps API returned an unexpected readiness status"
            )
        if clock() >= deadline:
            raise CompositionError(
                "the InferOps API did not become ready within its budget"
            )
        sleeper(min(1.0, deadline - clock()))


def status(
    composition: LocalComposition,
    runner: CommandRunner,
    *,
    confirmed: bool,
    runtime_get: JsonGet = http_get,
    api_get: JsonGet = json_get,
) -> StatusResult:
    """Inspect both explicitly real components without changing either."""
    _require_confirmation(confirmed)
    package = load_runtime_package()
    owned = owned_container_exists(package, runner)
    running = owned and container_is_running(package, runner)
    live = running and tcp_is_live(package)
    runtime_ready = False
    if live:
        try:
            runtime_ready = (
                runtime_get(package.readiness_url, 1.0).status == package.ready_status
            )
        except Exception:
            runtime_ready = False
    api_ready = False
    try:
        api_response = api_get(composition.api_readiness_url, 1.0)
        api_ready = (
            api_response.status == composition.ready_status
            and api_response.body == READY_BODY
        )
    except Exception:
        api_ready = False
    return StatusResult(
        profile=composition.composition_id,
        adapter=composition.adapter_selection,
        runtime_owned=owned,
        runtime_running=running,
        runtime_live=live,
        runtime_ready=runtime_ready,
        api_ready=api_ready,
    )


def cleanup(
    composition: LocalComposition,
    runner: CommandRunner,
    *,
    confirmed: bool,
) -> bool:
    """Remove only residual runtime state after the foreground API has exited."""
    _require_confirmation(confirmed)
    if composition.shutdown_order != EXPECTED_SHUTDOWN_ORDER:
        raise CompositionError("the local composition shutdown order is unsupported")
    return stop_runtime(load_runtime_package(), runner, confirmed=True)


def _require_confirmation(confirmed: bool) -> None:
    if not confirmed:
        raise CompositionError("local-real execution requires --confirm-real-runtime")


def run_foreground(
    composition: LocalComposition,
    *,
    confirmed: bool,
    repo_root: Path = REPO_ROOT,
    runner: CommandRunner | None = None,
    server_factory: ServerFactory = LocalApiServer,
    runtime_get: JsonGet = http_get,
    api_get: JsonGet = json_get,
    on_ready: ReadyCallback | None = None,
) -> RunResult:
    """Start runtime then API, remain attached, and tear down in reverse order."""
    _require_confirmation(confirmed)
    active_runner = runner or SubprocessRunner(
        timeout_seconds=composition.engine_command_timeout_seconds
    )
    package = load_runtime_package()
    log = CompositionLog(composition, repo_root=repo_root)
    log.reset()
    runtime_started = False
    server: ApiServer | None = None
    api_started = False
    runtime_removed = False
    runtime_readiness_ms = 0
    api_readiness_ms = 0
    try:
        log.event(
            "composition.starting", adapter="real", profile=composition.composition_id
        )
        start_runtime(package, active_runner, confirmed=True, repo_root=repo_root)
        runtime_started = True
        runtime_trace = wait_runtime_ready(
            package,
            active_runner,
            confirmed=True,
            http_get=runtime_get,
        )
        runtime_readiness_ms = runtime_trace.elapsed_ms
        log.event(
            "composition.runtime.ready",
            elapsedMs=runtime_readiness_ms,
            observations=len(runtime_trace.statuses),
        )
        application = build(composition_environment(composition), sink=log)
        server = server_factory(
            application,
            host=composition.api_host,
            port=composition.api_port,
            request_body_limit_bytes=composition.request_body_limit_bytes,
            response_timeout_seconds=composition.response_budget_ms / 1000,
            shutdown_timeout_seconds=(
                int(composition.environment["INFEROPS_DRAIN_TIMEOUT_MS"]) / 1000 + 5
            ),
        )
        server.start()
        api_started = True
        server.serve_in_background()
        api_readiness_ms = wait_api_ready(composition, get=api_get)
        log.event("composition.api.ready", adapter="real", elapsedMs=api_readiness_ms)
        if on_ready is not None:
            on_ready(runtime_readiness_ms, api_readiness_ms)
        server.join()
    finally:
        api_failure: Exception | None = None
        if api_started and server is not None:
            server.request_stop()
            server.join()
            try:
                server.close()
            except Exception as error:
                api_failure = error
            log.event(
                "composition.api.stopped",
                drained=server.application.drained_cleanly is True,
            )
        if runtime_started:
            runtime_removed = stop_runtime(package, active_runner, confirmed=True)
            log.event("composition.runtime.removed", removed=runtime_removed)
            if not runtime_removed:
                raise CompositionError("runtime cleanup could not be verified")
        if api_failure is not None:
            raise CompositionError(
                "InferOps API cleanup was incomplete"
            ) from api_failure
    return RunResult(
        runtime_readiness_ms=runtime_readiness_ms,
        api_readiness_ms=api_readiness_ms,
        api_drained=server is not None and server.application.drained_cleanly is True,
        runtime_removed=runtime_removed,
    )
