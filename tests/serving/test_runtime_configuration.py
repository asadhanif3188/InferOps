"""The selected local runtime profile and its offline validation.

The committed JSON file is the fixture under test. Mutated copies live only in
pytest's temporary directory. No runtime, container, model, network, or cluster
is used; these checks establish local-static configuration consistency only.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from inferops.adapters.llama_cpp import (
    HEALTH_LOADING_STATUS,
    HEALTH_PATH,
    HEALTH_READY_STATUS,
    PINNED_IMAGE_REFERENCE,
    PINNED_MODEL_FILE,
    LlamaServerSettings,
)
from inferops.api.selection import ENV_ADAPTER
from tools.model_acquisition import load_manifest
from tools.runtime_configuration import (
    PINNED_COMMAND,
    PINNED_SOURCE_REVISION,
    RUNTIME_PROFILE_PATH,
    RuntimeConfigurationError,
    load_runtime_profile,
)
from tools.runtime_configuration.__main__ import main

pytestmark = pytest.mark.docs

PROFILE_DOCUMENT: dict[str, Any] = json.loads(
    RUNTIME_PROFILE_PATH.read_text(encoding="utf-8")
)


def _write_profile(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "runtime-profile.local.v1.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _mutated(path: tuple[str, ...], value: object) -> dict[str, Any]:
    document = copy.deepcopy(PROFILE_DOCUMENT)
    cursor: Any = document
    for member in path[:-1]:
        cursor = cursor[member]
    cursor[path[-1]] = value
    return document


def test_the_runtime_image_source_revision_and_executable_are_pinned() -> None:
    profile = load_runtime_profile()

    assert profile.image_reference == PINNED_IMAGE_REFERENCE
    assert profile.source_revision == PINNED_SOURCE_REVISION
    assert profile.command == PINNED_COMMAND
    assert profile.startup_command() == (
        "/app/llama-server",
        "--model",
        f"/models/{PINNED_MODEL_FILE}",
        "--alias",
        "qwen3-1.7b-q8_0",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
        "--ctx-size",
        "4096",
        "--threads",
        "6",
        "--parallel",
        "1",
        "--n-predict",
        "128",
        "--temp",
        "0",
        "--metrics",
    )


def test_the_verified_cache_artifact_is_external_and_read_only() -> None:
    profile = load_runtime_profile()
    source = load_manifest()

    assert profile.model_cache_root == source.cache_path
    assert profile.model_artifact_relative_path == source.artifact_relative_path
    assert profile.model_container_path == f"/models/{source.file}"
    assert profile.model_read_only is True
    assert profile.model_embedded_in_image is False


def test_ports_resources_context_generation_and_timeouts_are_explicit() -> None:
    profile = load_runtime_profile()

    assert profile.container_port == 8080
    assert (profile.cpu_request_cores, profile.cpu_limit_cores) == (1, 6)
    assert (profile.memory_request_mib, profile.memory_limit_mib) == (2048, 3072)
    assert (profile.accelerator_kind, profile.accelerator_count) == ("none", 0)
    assert profile.context_size_tokens == 4096
    assert profile.default_max_output_tokens == 128
    assert profile.default_temperature == 0
    assert profile.parallel_slots == 1
    assert profile.threads == 6
    assert (
        profile.startup_budget_ms,
        profile.request_budget_ms,
        profile.drain_budget_ms,
    ) == (300000, 120000, 15000)


def test_the_profile_translates_losslessly_to_the_real_adapter_environment() -> None:
    profile = load_runtime_profile()
    environment = profile.adapter_environment()
    settings = LlamaServerSettings.from_environment(environment)

    assert environment[ENV_ADAPTER] == "real"
    assert environment["INFEROPS_MAX_OUTPUT_TOKENS"] == "128"
    assert environment["INFEROPS_REQUEST_TIMEOUT_MS"] == "120000"
    assert settings.model_path == profile.model_container_path
    assert settings.context_size == profile.context_size_tokens
    assert settings.threads == profile.threads
    assert settings.startup_budget_ms == profile.startup_budget_ms
    assert settings.metrics_enabled is True


def test_readiness_waits_for_model_load_and_liveness_does_not() -> None:
    profile = load_runtime_profile()

    assert profile.startup_path == HEALTH_PATH
    assert profile.readiness_path == HEALTH_PATH
    assert profile.startup_ready_status == HEALTH_READY_STATUS
    assert profile.readiness_ready_status == HEALTH_READY_STATUS
    assert profile.startup_loading_status == HEALTH_LOADING_STATUS
    assert profile.readiness_loading_status == HEALTH_LOADING_STATUS
    assert profile.liveness_kind == "tcp"
    assert profile.metrics_enabled is True
    assert profile.metrics_path == "/metrics"


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("runtime", "imageReference"), "ghcr.io/example/runtime:latest", "drifted"),
        (("runtime", "command"), "/bin/sh", "drifted"),
        (("model", "sourceRecord"), "../private/model.json", "source record"),
        (("model", "readOnly"), False, "mounted read-only"),
        (("model", "embeddedInImage"), True, "mounted read-only"),
        (("resources", "cpuRequestCores"), 7, "CPU request"),
        (("resources", "memoryRequestMiB"), 4096, "memory request"),
        (("network", "adapterEndpoint"), "http://llama-server:8081", "network"),
        (("network", "adapterEndpoint"), "http://llama-server:99999", "invalid port"),
        (("serving", "defaultMaxOutputTokens"), 4097, "output-token"),
        (("health", "readiness", "loadingStatus"), 200, "model loading"),
        (("health", "liveness", "kind"), "http", "liveness"),
    ],
    ids=(
        "mutable-image-tag",
        "different-command",
        "source-path-traversal",
        "writable-model",
        "model-in-image",
        "cpu-request-over-limit",
        "memory-request-over-limit",
        "endpoint-port-disagreement",
        "invalid-endpoint-port",
        "output-over-context",
        "loading-reported-ready",
        "readiness-used-for-liveness",
    ),
)
def test_unsafe_or_inconsistent_profiles_are_refused(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
    message: str,
) -> None:
    profile_path = _write_profile(tmp_path, _mutated(path, value))

    with pytest.raises(RuntimeConfigurationError, match=message):
        load_runtime_profile(profile_path)


def test_embedded_secret_values_are_refused_without_repeating_them(
    tmp_path: Path,
) -> None:
    sensitive_fixture = "synthetic-sensitive-value"
    profile_path = _write_profile(
        tmp_path,
        _mutated(("secrets", "embeddedValues"), [sensitive_fixture]),
    )

    with pytest.raises(RuntimeConfigurationError) as caught:
        load_runtime_profile(profile_path)

    assert "embedded secret" in str(caught.value)
    assert sensitive_fixture not in str(caught.value)


def test_an_unrecognised_field_cannot_hide_a_secret(
    tmp_path: Path,
) -> None:
    sensitive_fixture = "synthetic-sensitive-value"
    document = copy.deepcopy(PROFILE_DOCUMENT)
    document["runtime"]["apiToken"] = sensitive_fixture
    profile_path = _write_profile(tmp_path, document)

    with pytest.raises(RuntimeConfigurationError) as caught:
        load_runtime_profile(profile_path)

    assert "unsupported members" in str(caught.value)
    assert sensitive_fixture not in str(caught.value)


def test_the_check_command_is_offline_and_labels_its_evidence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["check"]) == 0

    output = capsys.readouterr().out
    assert PINNED_IMAGE_REFERENCE in output
    assert "read-only" in output
    assert "execution    not started (offline validation only)" in output
