"""The standalone runtime package, lifecycle, and bounded startup workflow.

Every lifecycle test injects a command runner and HTTP seam. The package is
never started, no Docker daemon is contacted, and no model byte is read. These
are local-static and synthetic checks, not local-real runtime evidence.
"""

from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tools.runtime_configuration import load_runtime_profile
from tools.runtime_packaging import (
    PACKAGE_PATH,
    CommandResult,
    HttpResponse,
    ReadinessTrace,
    RuntimeEndpointUnavailable,
    RuntimePackagingError,
    SubprocessRunner,
    container_is_running,
    docker_run_command,
    inference_probe,
    load_runtime_package,
    preflight,
    smoke,
    start,
    stop,
    tcp_is_live,
    wait_ready,
)
from tools.runtime_packaging.__main__ import main

pytestmark = pytest.mark.docs

PACKAGE_DOCUMENT: dict[str, Any] = json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))


class ScriptedRunner:
    """Return one result per command and retain the exact argument vectors."""

    def __init__(self, results: Sequence[CommandResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: Sequence[str]) -> CommandResult:
        self.calls.append(tuple(arguments))
        if not self.results:
            raise AssertionError(f"unexpected command: {arguments}")
        return self.results.pop(0)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _write_package(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "container-package.v1.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _mutated(path: tuple[str, ...], value: object) -> dict[str, Any]:
    document = copy.deepcopy(PACKAGE_DOCUMENT)
    cursor: Any = document
    for member in path[:-1]:
        cursor = cursor[member]
    cursor[path[-1]] = value
    return document


def test_the_package_matches_the_selected_runtime_profile() -> None:
    package = load_runtime_package()
    profile = load_runtime_profile()

    assert package.image_reference == profile.image_reference
    assert package.entrypoint == profile.command
    assert package.model_target == profile.model_container_path
    assert package.cpu_request_cores == profile.cpu_request_cores
    assert package.cpu_limit_cores == profile.cpu_limit_cores
    assert package.memory_request_mib == profile.memory_request_mib
    assert package.memory_limit_mib == profile.memory_limit_mib
    assert package.startup_budget_ms == profile.startup_budget_ms
    assert package.ready_status == profile.startup_ready_status
    assert package.loading_status == profile.startup_loading_status


def test_the_start_command_is_pinned_hardened_and_uses_no_network_pull(
    tmp_path: Path,
) -> None:
    package = load_runtime_package()
    profile = load_runtime_profile()
    command = docker_run_command(package, repo_root=tmp_path)

    assert command[:3] == ("docker", "run", "--detach")
    assert command[command.index("--pull") :][:2] == ("--pull", "never")
    assert command[command.index("--user") :][:2] == ("--user", "65534:65534")
    assert "--read-only" in command
    assert "no-new-privileges=true" in command
    assert command[command.index("--cap-drop") :][:2] == ("--cap-drop", "ALL")
    assert command[command.index("--restart") :][:2] == ("--restart", "no")
    assert command[command.index("--publish") :][:2] == (
        "--publish",
        "127.0.0.1:8080:8080",
    )
    mount = command[command.index("--mount") + 1]
    assert mount.startswith(f"type=bind,src={tmp_path.resolve()}")
    assert f"dst={profile.model_container_path}" in mount
    assert mount.endswith(",readonly")
    assert command[command.index("--entrypoint") + 1] == profile.command
    assert command[command.index(profile.image_reference) + 1 :] == profile.arguments
    assert not any(member in command for member in ("pull", "login", "build"))


def test_readiness_observes_loading_then_ready_without_treating_it_as_liveness() -> (
    None
):
    package = load_runtime_package()
    runner = ScriptedRunner(
        [
            CommandResult(0, f"{package.package_id}\n"),
            CommandResult(0, "true\n"),
            CommandResult(0, "true\n"),
        ]
    )
    statuses = iter((503, 200))
    clock = FakeClock()

    trace = wait_ready(
        package,
        runner,
        confirmed=True,
        http_get=lambda _url, _timeout: HttpResponse(next(statuses)),
        clock=clock,
        sleeper=clock.sleep,
    )

    assert trace.statuses == (503, 200)
    assert trace.elapsed_ms == 1000
    assert all("{{.State.Running}}" in call for call in runner.calls[1:])


def test_a_container_exit_during_model_load_fails_the_startup_guard() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner(
        [CommandResult(0, f"{package.package_id}\n"), CommandResult(0, "false\n")]
    )

    with pytest.raises(RuntimePackagingError, match="stopped before becoming ready"):
        wait_ready(
            package,
            runner,
            confirmed=True,
            http_get=lambda _url, _timeout: HttpResponse(503),
        )


def test_readiness_refuses_a_foreign_container_before_contacting_http() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner([CommandResult(0, "another-package\n")])

    with pytest.raises(RuntimePackagingError, match="owned by something else"):
        wait_ready(
            package,
            runner,
            confirmed=True,
            http_get=lambda *_: pytest.fail("HTTP must not be contacted"),
        )


def test_an_initially_unavailable_health_socket_remains_inside_startup_budget() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner(
        [
            CommandResult(0, f"{package.package_id}\n"),
            CommandResult(0, "true\n"),
            CommandResult(0, "true\n"),
        ]
    )
    responses = iter(
        (RuntimeEndpointUnavailable("synthetic unavailable"), HttpResponse(200))
    )
    clock = FakeClock()

    def get(_url: str, _timeout: float) -> HttpResponse:
        response = next(responses)
        if isinstance(response, RuntimePackagingError):
            raise response
        return response

    trace = wait_ready(
        package,
        runner,
        confirmed=True,
        http_get=get,
        clock=clock,
        sleeper=clock.sleep,
    )

    assert trace.statuses == (0, 200)
    assert trace.elapsed_ms == 1000


def test_the_readiness_wait_is_bounded() -> None:
    package = replace(
        load_runtime_package(),
        startup_budget_ms=1000,
        poll_interval_ms=1000,
    )
    runner = ScriptedRunner(
        [
            CommandResult(0, f"{package.package_id}\n"),
            CommandResult(0, "true\n"),
            CommandResult(0, "true\n"),
        ]
    )
    clock = FakeClock()

    with pytest.raises(RuntimePackagingError, match="within the startup budget"):
        wait_ready(
            package,
            runner,
            confirmed=True,
            http_get=lambda _url, _timeout: HttpResponse(503),
            clock=clock,
            sleeper=clock.sleep,
        )


def test_the_direct_inference_probe_discards_generated_content() -> None:
    package = load_runtime_package()
    observed: dict[str, object] = {}

    def post(
        url: str,
        body: Mapping[str, object],
        timeout_seconds: float,
    ) -> HttpResponse:
        observed.update({"url": url, "body": body, "timeout": timeout_seconds})
        return HttpResponse(200, {"choices": [{"message": {"content": "discarded"}}]})

    assert inference_probe(package, http_post=post) == 200
    request = observed["body"]
    assert isinstance(request, dict)
    assert request["max_tokens"] == 1
    assert request["temperature"] == 0
    assert observed["timeout"] == 120.0


def test_the_direct_inference_probe_requires_nonempty_completion_content() -> None:
    package = load_runtime_package()

    with pytest.raises(RuntimePackagingError, match="no completion content"):
        inference_probe(
            package,
            http_post=lambda *_: HttpResponse(
                200, {"choices": [{"message": {"content": ""}}]}
            ),
        )


def test_shutdown_removes_only_the_owned_container() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner(
        [
            CommandResult(0, f"{package.package_id}\n"),
            CommandResult(0),
            CommandResult(0),
        ]
    )

    assert stop(package, runner, confirmed=True) is True
    assert runner.calls[1] == (
        "docker",
        "stop",
        "--time",
        "15",
        package.container_name,
    )
    assert runner.calls[2] == ("docker", "rm", package.container_name)


def test_shutdown_refuses_a_container_owned_by_something_else() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner([CommandResult(0, "another-package\n")])

    with pytest.raises(RuntimePackagingError, match="owned by something else"):
        stop(package, runner, confirmed=True)

    assert len(runner.calls) == 1


def test_shutdown_does_not_treat_engine_failure_as_container_absence() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner(
        [CommandResult(1, stderr="synthetic daemon failure"), CommandResult(1)]
    )

    with pytest.raises(RuntimePackagingError, match="ownership could not be verified"):
        stop(package, runner, confirmed=True)


def test_shutdown_returns_absent_only_after_a_successful_container_inventory() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner([CommandResult(1), CommandResult(0, "")])

    assert stop(package, runner, confirmed=True) is False
    assert "container" in runner.calls[1]
    assert "ls" in runner.calls[1]


def test_smoke_fails_when_shutdown_cannot_be_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = load_runtime_package()
    runner = ScriptedRunner([])

    def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    def ready(*_args: object, **_kwargs: object) -> ReadinessTrace:
        return ReadinessTrace((200,), 0)

    monkeypatch.setattr("tools.runtime_packaging.core.start", no_op)
    monkeypatch.setattr("tools.runtime_packaging.core.wait_ready", ready)
    monkeypatch.setattr(
        "tools.runtime_packaging.core.inference_probe", lambda *_args, **_: 200
    )
    monkeypatch.setattr("tools.runtime_packaging.core.stop", lambda *_args, **_: False)

    with pytest.raises(RuntimePackagingError, match="complete shutdown"):
        smoke(
            package,
            runner,
            confirmed=True,
            http_get=lambda *_: HttpResponse(200),
            http_post=lambda *_: HttpResponse(200),
        )


def test_container_engine_commands_have_a_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def expire(*_args: object, **kwargs: object) -> None:
        observed["timeout"] = kwargs["timeout"]
        raise subprocess.TimeoutExpired(cmd=["docker", "version"], timeout=0.25)

    monkeypatch.setattr("tools.runtime_packaging.core.subprocess.run", expire)

    with pytest.raises(RuntimePackagingError, match="exceeded its deadline"):
        SubprocessRunner(timeout_seconds=0.25).run(("docker", "version"))

    assert observed == {"timeout": 0.25}


def test_real_operations_require_explicit_confirmation() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner([])

    with pytest.raises(RuntimePackagingError, match="confirm-real-runtime"):
        wait_ready(
            package,
            runner,
            confirmed=False,
            http_get=lambda _url, _timeout: HttpResponse(200),
        )
    assert runner.calls == []


def test_preflight_refuses_an_absent_model_before_starting_a_container(
    tmp_path: Path,
) -> None:
    package = load_runtime_package()
    runner = ScriptedRunner([CommandResult(0, "27.0\n"), CommandResult(0, "[]\n")])

    with pytest.raises(RuntimePackagingError, match="hash-verified"):
        preflight(package, runner, repo_root=tmp_path)

    assert all("run" not in call for call in runner.calls)


def test_startup_process_guard_uses_only_the_engine_state() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner([CommandResult(0, "true\n")])

    assert container_is_running(package, runner) is True
    assert package.readiness_path not in runner.calls[0]


def test_profile_liveness_is_an_independent_tcp_probe() -> None:
    package = load_runtime_package()
    observed: list[tuple[str, int, float]] = []

    def probe(host: str, port: int, timeout: float) -> bool:
        observed.append((host, port, timeout))
        return True

    assert tcp_is_live(package, probe=probe) is True
    assert observed == [("127.0.0.1", 8080, 1.0)]


def test_an_immediate_startup_exit_is_removed_when_ownership_is_proven(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package = load_runtime_package()
    runner = ScriptedRunner(
        [
            CommandResult(0),  # preflight engine
            CommandResult(0),  # preflight image
            CommandResult(1),  # no existing container
            CommandResult(0, ""),  # successful inventory confirms absence
            CommandResult(0, "container-id\n"),
            CommandResult(0, "false\n"),
            CommandResult(0, f"{package.package_id}\n"),
            CommandResult(0),
        ]
    )
    monkeypatch.setattr("tools.runtime_packaging.core.verify_artifact", lambda *_: None)

    with pytest.raises(RuntimePackagingError, match="exited during startup"):
        start(package, runner, confirmed=True, repo_root=tmp_path)

    assert runner.calls[-1] == ("docker", "rm", package.container_name)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("container", "imageReference"), "runtime:latest", "drifted"),
        (("container", "pullPolicy"), "always", "drifted"),
        (("container", "user"), "0:0", "container boundary"),
        (("container", "readOnlyRootFilesystem"), False, "container boundary"),
        (("container", "restartPolicy"), "always", "container boundary"),
        (("modelMount", "readOnly"), False, "read-only"),
        (("network", "publishedHost"), "0.0.0.0", "loopback"),
        (("security", "noNewPrivileges"), False, "container boundary"),
        (("security", "embeddedSecrets"), ["synthetic-value"], "container boundary"),
        (("lifecycle", "liveness", "kind"), "http", "lifecycle"),
        (("lifecycle", "loadingStatus"), 200, "lifecycle"),
    ],
)
def test_unsafe_or_drifting_packages_are_refused(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
    message: str,
) -> None:
    target = _write_package(tmp_path, _mutated(path, value))
    with pytest.raises(RuntimePackagingError, match=message) as caught:
        load_runtime_package(target)
    assert "synthetic-value" not in str(caught.value)


def test_offline_check_starts_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check"]) == 0
    output = capsys.readouterr().out
    assert "offline package validation only" in output
    assert "external verified cache artifact" in output
