"""The C2 certification descriptor, guards, assertions, and evidence output.

Every check here reads committed files or drives the workflow through injected
command, HTTP, capacity, and server seams. No container is created, no image is
inspected, no model byte is read, and no real runtime answers anything. These
results are `local-static` and synthetic: they establish that the certification
mechanism refuses what it must and records what it observes, and they establish
nothing about a real model. Only an authorized run of
`python -m tools.runtime_certification certify --confirm-real-runtime` produces
`local-real-cpu` evidence.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from inferops.api import InferOpsApi
from tools.local_composition import RunResult, load_composition
from tools.model_acquisition import load_manifest
from tools.runtime_certification import core
from tools.runtime_certification.__main__ import main
from tools.runtime_packaging import CommandResult, load_runtime_package

pytestmark = pytest.mark.docs

CERTIFICATION_DOCUMENT: dict[str, Any] = json.loads(
    core.CERTIFICATION_PATH.read_text(encoding="utf-8")
)

MODEL_IDENTIFIER = "qwen3-1-7b-q8-0"
RUNTIME_NAME = "llama.cpp llama-server"
RUNTIME_VERSION = "b10588-70adb1b4c"


def _mutated(path: tuple[str, ...], value: object) -> dict[str, Any]:
    document = copy.deepcopy(CERTIFICATION_DOCUMENT)
    cursor: Any = document
    for member in path[:-1]:
        cursor = cursor[member]
    cursor[path[-1]] = value
    return document


def _written(tmp_path: Path, document: Mapping[str, Any]) -> Path:
    candidate = tmp_path / "c2-smoke.v1.json"
    candidate.write_text(json.dumps(document), encoding="utf-8")
    return candidate


class CapacityRunner:
    """Answer `docker info` with a chosen capacity and refuse everything else."""

    def __init__(self, cpus: int = 8, memory_bytes: int = 8 * 1024**3) -> None:
        self.stdout = f"{cpus} {memory_bytes}"
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: Sequence[str]) -> CommandResult:
        self.calls.append(tuple(arguments))
        if arguments[1] == "info":
            return CommandResult(0, self.stdout)
        raise AssertionError(f"unexpected command: {arguments}")


class UnavailableEngineRunner:
    def run(self, arguments: Sequence[str]) -> CommandResult:
        del arguments
        return CommandResult(1, "", "")


def _models_body(
    *,
    adapter_kind: str = "real",
    runtime_name: str = RUNTIME_NAME,
    model_revision: str | None = None,
    token_usage: bool | None = True,
    model_identifier: str = MODEL_IDENTIFIER,
) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": model_identifier,
                "object": "model",
                "created": 1,
                "owned_by": "inferops",
            }
        ],
        "x_inferops": {
            "contractVersion": "inferops.io/v1alpha1",
            "adapterKind": adapter_kind,
            "runtime": {
                "name": runtime_name,
                "version": RUNTIME_VERSION,
                "modelRevision": model_revision or load_manifest().revision,
            },
            "capabilities": {
                "streaming": False,
                "tokenUsage": token_usage,
                "deterministicSampling": None,
                "multiModel": False,
            },
        },
    }


def _completion_body(
    *,
    adapter_kind: str = "real",
    content: str = "Kubernetes orchestrates containers across a cluster.",
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": MODEL_IDENTIFIER,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": (
            {"prompt_tokens": 17, "completion_tokens": 21, "total_tokens": 38}
            if usage is None
            else usage
        ),
        "x_inferops": {
            "requestId": CERTIFICATION_DOCUMENT["request"]["requestId"],
            "correlationId": CERTIFICATION_DOCUMENT["request"]["correlationId"],
            "contractVersion": "inferops.io/v1alpha1",
            "adapterKind": adapter_kind,
            "modelRef": MODEL_IDENTIFIER,
        },
    }


def _headers() -> dict[str, str]:
    return {
        "X-InferOps-Request-ID": CERTIFICATION_DOCUMENT["request"]["requestId"],
        "X-InferOps-Correlation-ID": CERTIFICATION_DOCUMENT["request"]["correlationId"],
    }


def _get(body: Mapping[str, Any], status: int = 200) -> core.ApiGet:
    def get(url: str, timeout_seconds: float) -> core.ApiResponse:
        assert url.endswith(CERTIFICATION_DOCUMENT["request"]["modelsPath"])
        assert timeout_seconds > 0
        return core.ApiResponse(status, dict(body), _headers())

    return get


def _post(body: Mapping[str, Any], status: int = 200) -> core.ApiPost:
    def post(
        url: str,
        payload: Mapping[str, object],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> core.ApiResponse:
        assert url.endswith(CERTIFICATION_DOCUMENT["request"]["path"])
        assert payload["model"] == MODEL_IDENTIFIER
        assert headers["X-InferOps-Request-ID"]
        assert timeout_seconds > 0
        return core.ApiResponse(status, dict(body), _headers())

    return post


# -- the committed descriptor -----------------------------------------------


def test_the_descriptor_certifies_c2_against_the_composed_real_path() -> None:
    certification = core.load_certification()
    composition = load_composition()

    assert certification.certification_level == "C2"
    assert certification.evidence_class == "local-real-cpu"
    assert certification.evidence_label == "local real runtime"
    assert certification.lane == "real-runtime"
    assert certification.required_adapter_kind == "real"
    assert certification.request_path == "/v1/chat/completions"
    assert certification.api_budget_ms == composition.response_budget_ms
    assert certification.retain_generated_text is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("certificationLevel",), "C1"),
        (("evidenceClass",), "mock"),
        (("evidenceClass",), "synthetic"),
        (("lane",), "default-checks"),
        (("assertions", "requiredAdapterKind"), "mock"),
        (("assertions", "requireUsageCounts"), False),
        (("assertions", "requireNonEmptyContent"), False),
        (("assertions", "requirePinnedModelRevision"), False),
        (("prerequisites", "minimumLogicalCpus"), 1),
        (("prerequisites", "minimumEngineMemoryBytes"), 1024),
        (("prerequisites", "minimumFreeDiskBytes"), 1024),
        (("prerequisites", "requiresVerifiedModelCache"), False),
        (("prerequisites", "requiresPinnedRuntimeImage"), False),
        (("prerequisites", "requiresContainerEngine"), False),
        (("readiness", "apiBudgetMs"), 1000),
        (("readiness", "runtimeBudgetMs"), 1000),
        (("request", "path"), "/v1/completions"),
        (("request", "timeoutMs"), 5),
        (("evidence", "retainGeneratedText"), True),
        (("evidence", "resultFile"), "../escape.json"),
        (("evidence", "directory"), ".cache/inferops"),
    ],
)
def test_a_weakened_or_unsafe_descriptor_is_refused(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    """Every lever that would lower the bar or move the output is a refusal.

    A `C2` claim is only worth what its weakest accepted descriptor allows, so
    the descriptor cannot relabel its own evidence class, waive an assertion,
    reduce a prerequisite below the selected package's needs, or write outside
    the ignored evidence directory.
    """
    with pytest.raises(core.CertificationError):
        core.load_certification(_written(tmp_path, _mutated(path, value)))


def test_an_unreadable_descriptor_is_refused(tmp_path: Path) -> None:
    candidate = tmp_path / "c2-smoke.v1.json"
    candidate.write_text("{not json", encoding="utf-8")

    with pytest.raises(core.CertificationError, match="unreadable"):
        core.load_certification(candidate)


# -- prerequisites ----------------------------------------------------------


def test_the_workflow_refuses_a_host_below_the_hardware_prerequisites() -> None:
    """The first acceptance criterion, and the reason it runs before the hash.

    Verifying the cached artifact reads nearly two gigabytes. A host that cannot
    serve the workload is told so before it pays for that, and the refusal names
    every unmet check rather than the first one.
    """
    certification = core.load_certification()
    runner = CapacityRunner(cpus=2, memory_bytes=1024**3)

    with pytest.raises(core.PrerequisiteUnmet) as refusal:
        core.check_prerequisites(certification, runner, free_bytes=lambda _path: 1024)

    assert "engine-logical-cpus" in str(refusal.value)
    assert "engine-memory-bytes" in str(refusal.value)
    assert "model-cache-free-disk-bytes" in str(refusal.value)
    assert refusal.value.report is not None
    assert refusal.value.report.satisfied is False
    assert refusal.value.report.model_artifact_verified is False
    assert [call[1] for call in runner.calls] == ["info"]


def test_an_unavailable_container_engine_is_a_prerequisite_refusal() -> None:
    certification = core.load_certification()

    with pytest.raises(core.PrerequisiteUnmet, match="engine is unavailable"):
        core.check_prerequisites(
            certification, UnavailableEngineRunner(), free_bytes=lambda _path: 1024**4
        )


def test_a_capable_host_still_requires_the_image_and_the_verified_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capacity alone certifies nothing; the pinned inputs are checked next."""
    certification = core.load_certification()

    def refuse(*_args: object, **_keywords: object) -> Path:
        raise RuntimeError("the pinned runtime image is not local")

    monkeypatch.setattr(core, "preflight", refuse)

    with pytest.raises(core.PrerequisiteUnmet, match="hash-verified model"):
        core.check_prerequisites(
            certification, CapacityRunner(), free_bytes=lambda _path: 1024**4
        )


def test_the_host_record_carries_no_identifying_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A record naming a hostname or a personal path is a leak, not evidence."""
    certification = core.load_certification()
    monkeypatch.setattr(core, "preflight", lambda *_a, **_k: Path("/models/pinned"))

    report = core.check_prerequisites(
        certification, CapacityRunner(), free_bytes=lambda _path: 1024**4
    )
    published = core.diagnostics_document(
        core.Diagnostics(stage=core.STAGE_PREREQUISITES, reason="", host=report.host)
    )["host"]

    assert report.satisfied is True
    assert isinstance(published, dict)
    assert set(published) == {
        "operatingSystem",
        "release",
        "machine",
        "pythonVersion",
        "engineLogicalCpus",
        "engineMemoryBytes",
        "modelCacheFreeDiskBytes",
    }


# -- the assertions ---------------------------------------------------------


def test_a_real_identity_and_completion_certify() -> None:
    certification = core.load_certification()
    composition = load_composition()

    identity = core.observe_identity(
        certification, composition, load_manifest(), get=_get(_models_body())
    )
    inference = core.observe_inference(
        certification, composition, post=_post(_completion_body())
    )

    assert identity.adapter_kind == "real"
    assert identity.runtime_name == RUNTIME_NAME
    assert identity.model_revision == load_manifest().revision
    assert identity.token_usage_declared is True
    assert inference.status == 200
    assert inference.total_tokens == 38
    assert inference.request_id_echoed is True
    assert inference.correlation_id_echoed is True


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (_models_body(adapter_kind="mock"), "required adapter kind"),
        (_models_body(token_usage=False), "mock capability metadata"),
        (_models_body(token_usage=None), "mock capability metadata"),
        (_models_body(runtime_name="mock-serving"), "unselected runtime"),
        (_models_body(model_revision="0" * 40), "pinned model revision"),
        (_models_body(model_identifier="mock-llm"), "unconfigured model"),
    ],
)
def test_mock_or_drifting_identity_metadata_is_refused(
    body: Mapping[str, Any], expected: str
) -> None:
    """Prohibiting mock metadata is what stops a C1 result wearing a C2 label."""
    with pytest.raises(core.CertificationFailed, match=expected) as failure:
        core.observe_identity(
            core.load_certification(),
            load_composition(),
            load_manifest(),
            get=_get(body),
        )

    assert failure.value.stage == core.STAGE_IDENTITY


def test_a_model_identity_carrying_the_prohibited_marker_is_refused() -> None:
    body = _models_body()
    body["x_inferops"]["runtime"]["version"] = "mock-build"

    with pytest.raises(core.CertificationFailed, match="mock identity metadata"):
        core.observe_identity(
            core.load_certification(),
            load_composition(),
            load_manifest(),
            get=_get(body),
        )


@pytest.mark.parametrize(
    ("body", "status", "expected"),
    [
        (_completion_body(), 503, "did not return a completion"),
        (_completion_body(adapter_kind="mock"), 200, "required adapter kind"),
        (_completion_body(content="   "), 200, "no completion content"),
        (
            _completion_body(
                usage={"prompt_tokens": 3, "completion_tokens": 0, "total_tokens": 3}
            ),
            200,
            "absent or inconsistent",
        ),
        (
            _completion_body(
                usage={"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 99}
            ),
            200,
            "absent or inconsistent",
        ),
    ],
)
def test_an_answer_that_is_not_a_real_completion_is_refused(
    body: Mapping[str, Any], status: int, expected: str
) -> None:
    with pytest.raises(core.CertificationFailed, match=expected) as failure:
        core.observe_inference(
            core.load_certification(), load_composition(), post=_post(body, status)
        )

    assert failure.value.stage == core.STAGE_INFERENCE


# -- the workflow -----------------------------------------------------------


class FakeServer:
    """An attached server that records only the stop the certification asks for."""

    application: InferOpsApi

    def __init__(self) -> None:
        self.stopped = False

    def start(self) -> None: ...

    def serve_in_background(self) -> None: ...

    def request_stop(self) -> None:
        self.stopped = True

    def join(self) -> None: ...

    def close(self) -> None: ...


def _fake_run_foreground(
    *, drained: bool = True, removed: bool = True
) -> tuple[Any, list[FakeServer]]:
    servers: list[FakeServer] = []

    def run_foreground(
        composition: object,
        *,
        confirmed: bool,
        repo_root: Path,
        runner: object,
        server_factory: Any,
        on_ready: Any,
    ) -> RunResult:
        del composition, repo_root, runner
        assert confirmed is True
        servers.append(
            server_factory(
                object(),
                host="127.0.0.1",
                port=8090,
                request_body_limit_bytes=1,
                response_timeout_seconds=1.0,
                shutdown_timeout_seconds=1.0,
            )
        )
        on_ready(4_211, 37)
        return RunResult(
            runtime_readiness_ms=4_211,
            api_readiness_ms=37,
            api_drained=drained,
            runtime_removed=removed,
        )

    return run_foreground, servers


def test_a_full_run_records_a_labelled_local_real_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The composed order, the observations, and the label they may carry.

    The seams here are synthetic, so this test proves the workflow's shape and
    its record; the record's `local-real-cpu` label is only truthful when the
    same code runs against the real runtime on an authorized host.
    """
    certification = core.load_certification()
    run_foreground, servers = _fake_run_foreground()
    monkeypatch.setattr(core, "run_foreground", run_foreground)
    monkeypatch.setattr(core, "preflight", lambda *_a, **_k: Path("/models/pinned"))

    result = core.certify(
        certification,
        confirmed=True,
        runner=CapacityRunner(),
        server_factory=lambda *_a, **_k: FakeServer(),
        get=_get(_models_body()),
        post=_post(_completion_body()),
        free_bytes=lambda _path: 1024**4,
    )
    document = core.result_document(result)

    assert servers[0].stopped is True
    assert document["outcome"] == "certified"
    assert document["certificationLevel"] == "C2"
    assert document["evidenceClass"] == "local-real-cpu"
    assert document["evidenceLabel"] == "local real runtime"
    assert document["readiness"] == {"runtimeReadyMs": 4_211, "apiReadyMs": 37}
    assert document["cleanup"] == {"apiDrained": True, "runtimeRemoved": True}
    assert isinstance(document["inference"], dict)
    assert document["inference"]["generatedTextRetained"] is False


def test_the_record_never_carries_the_prompt_or_the_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A record is published; a generated answer is not this workflow's to publish."""
    certification = core.load_certification()
    run_foreground, _servers = _fake_run_foreground()
    monkeypatch.setattr(core, "run_foreground", run_foreground)
    monkeypatch.setattr(core, "preflight", lambda *_a, **_k: Path("/models/pinned"))
    content = "Kubernetes orchestrates containers across a cluster."

    result = core.certify(
        certification,
        confirmed=True,
        runner=CapacityRunner(),
        server_factory=lambda *_a, **_k: FakeServer(),
        get=_get(_models_body()),
        post=_post(_completion_body(content=content)),
        free_bytes=lambda _path: 1024**4,
    )
    document = json.dumps(core.result_document(result))

    assert content not in document
    assert certification.prompt not in document
    assert result.inference.completion_characters == len(content)


def test_a_run_that_cannot_verify_its_cleanup_does_not_certify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_foreground, _servers = _fake_run_foreground(removed=False)
    monkeypatch.setattr(core, "run_foreground", run_foreground)
    monkeypatch.setattr(core, "preflight", lambda *_a, **_k: Path("/models/pinned"))

    with pytest.raises(core.CertificationFailed, match="cleanup") as failure:
        core.certify(
            core.load_certification(),
            confirmed=True,
            runner=CapacityRunner(),
            server_factory=lambda *_a, **_k: FakeServer(),
            get=_get(_models_body()),
            post=_post(_completion_body()),
            free_bytes=lambda _path: 1024**4,
        )

    assert failure.value.stage == core.STAGE_CLEANUP


def test_a_failed_assertion_still_stops_the_attached_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refusal mid-run must not leave the composition attached forever."""
    run_foreground, servers = _fake_run_foreground()
    monkeypatch.setattr(core, "run_foreground", run_foreground)
    monkeypatch.setattr(core, "preflight", lambda *_a, **_k: Path("/models/pinned"))

    with pytest.raises(core.CertificationFailed):
        core.certify(
            core.load_certification(),
            confirmed=True,
            runner=CapacityRunner(),
            server_factory=lambda *_a, **_k: FakeServer(),
            get=_get(_models_body(adapter_kind="mock")),
            post=_post(_completion_body()),
            free_bytes=lambda _path: 1024**4,
        )

    assert servers[0].stopped is True


def test_real_certification_requires_explicit_confirmation() -> None:
    with pytest.raises(core.PrerequisiteUnmet, match="confirm-real-runtime"):
        core.certify(core.load_certification(), confirmed=False)


# -- evidence and diagnostics -----------------------------------------------


def test_the_evidence_directory_refuses_a_linked_component(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    linked = tmp_path.resolve() / ".cache" / "inferops" / "certification"
    original = Path.is_symlink

    def is_linked(self: Path) -> bool:
        return self == linked or original(self)

    monkeypatch.setattr(Path, "is_symlink", is_linked)

    with pytest.raises(core.CertificationError, match="evidence path is unsafe"):
        core.EvidenceDirectory(core.load_certification(), repo_root=tmp_path)


def test_diagnostics_name_the_stage_and_the_unmet_checks(tmp_path: Path) -> None:
    """The last acceptance criterion: a failure leaves something worth reading."""
    certification = core.load_certification()
    checks = (
        core.PrerequisiteCheck(
            name="engine-memory-bytes",
            required=4 * 1024**3,
            observed=1024**3,
            satisfied=False,
        ),
    )
    evidence = core.EvidenceDirectory(certification, repo_root=tmp_path)
    written = evidence.write(
        evidence.diagnostics_path,
        core.diagnostics_document(
            core.Diagnostics(
                stage=core.STAGE_PREREQUISITES,
                reason="the host does not meet the certification prerequisites",
                prerequisites=checks,
            )
        ),
    )
    document = json.loads(written.read_text(encoding="utf-8"))

    assert written == (
        tmp_path.resolve() / ".cache/inferops/certification/c2-smoke-diagnostics.json"
    )
    assert document["outcome"] == "not-certified"
    assert document["stage"] == "prerequisites"
    assert document["prerequisites"][0]["name"] == "engine-memory-bytes"
    assert document["prerequisites"][0]["satisfied"] is False


def test_provenance_names_the_immutable_inputs_a_c2_record_must_carry() -> None:
    record = core.provenance(
        load_composition(), load_runtime_package(), load_manifest()
    )

    assert record["runtimeImage"].startswith("ghcr.io/ggml-org/llama.cpp@sha256:")
    assert record["modelRevision"] == load_manifest().revision
    assert record["modelSha256"].startswith("sha256:")


# -- the command ------------------------------------------------------------


def test_the_offline_check_contacts_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check"]) == 0

    printed = capsys.readouterr().out
    assert "C2; local-real-cpu" in printed
    assert "real-runtime; outside the default check lane" in printed
    assert "not started (offline certification validation only)" in printed


def test_the_command_refuses_an_unconfirmed_certification(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["certify"]) == 3

    printed = capsys.readouterr().err
    assert "REFUSED C2 certification at stage prerequisites" in printed
    assert "confirm-real-runtime" in printed
