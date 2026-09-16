"""A model that does not become ready: its descriptor, its script, and its record.

Nothing here installs anything, upgrades anything, sends a request, or contacts a
cluster. The cluster's answers are JSON written into a temporary directory, the probe
record set and the diagnostics are strings this module builds, the collector's answers
are a dictionary, and the operating script is read as text. No figure in this suite
describes serving, readiness, or recovery.

It is heaviest in the four places this experiment can be wrong without failing:

- **the disruption** -- the whole argument that this is not `V1-S3-008` rests on the
  overlay touching no model value and on the integrity init container having passed.
  The overlay is therefore read as text as well as digested, and a record whose init
  container did not exit zero is refused;
- **readiness** -- "the model never became ready" is a claim about every sample in a
  window, not about two of them. A window with a gap in it, a window shorter than the
  one that was registered, or a sample reporting a ready pod each make the record
  unusable;
- **the restart count** -- the point of a TCP liveness probe is that a healthy process
  loading a model is not killed. That is only established if the count was read, and
  only bounded if the window fits inside the startup probe's own budget, so both are
  enforced here rather than assumed;
- **the canonical refusal** -- which of the two 503 codes `ADR 0010 D8` maps to this
  situation a caller actually met is a *result*. A record that decided it in advance,
  or that accepted a code outside the registered vocabulary, would be an arrangement.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.performance_scenarios.core import dumps
from tools.unready_model_recovery import __main__ as cli
from tools.unready_model_recovery import core
from tools.unready_model_recovery.core import (
    DESCRIPTOR_PATH,
    RUNTIME_STARTUP_BUDGET_MS,
    UnreadyError,
    UnreadyRefused,
    build_record,
    descriptor_fields,
    extract_environment,
    load_descriptor,
    parse_diagnostics,
    parse_lifecycle,
    parse_probes,
    parse_readiness,
    probe_lines,
    summary_lines,
    validate_descriptor,
)

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR = load_descriptor()
DESCRIPTOR_TEXT = DESCRIPTOR_PATH.read_text(encoding="utf-8")
DOCUMENT: dict[str, Any] = json.loads(DESCRIPTOR_TEXT)

OVERLAY = REPO_ROOT / DOCUMENT["disruption"]["valuesOverlayRef"]
SCRIPT = REPO_ROOT / "scripts/environment/unready-model-recovery.sh"
SCRIPT_TEXT = SCRIPT.read_text(encoding="utf-8")
SCRIPT_LINES = SCRIPT_TEXT.splitlines()
PROCEDURE = REPO_ROOT / "docs/serving/unready-model-recovery.md"
DECISION = (
    REPO_ROOT
    / "docs/architecture/decisions/ADR-0010-inference-api-compatibility-surface.md"
)
EXTENDS = REPO_ROOT / "docs/serving/mock-and-real-boundary.md"
TEMPLATE = REPO_ROOT / "docs/proof/serving/TEMPLATE-unready-model-recovery.md"

PROOF_DIR = REPO_ROOT / "docs/proof/serving"
PROOF_PREFIX = "v1-s4-007-pr1-"

UNREADY_POD = "inferops-inferops-llm-runtime-aaaaaaaaaa-11111"
RECOVERED_POD = "inferops-inferops-llm-runtime-bbbbbbbbbb-22222"
API_POD = "inferops-inferops-llm-cccccccccc-33333"
COLLECTOR_POD = "inferops-inferops-llm-collector-dddddddddd-44444"
API_IMAGE = "localhost/inferops-api@sha256:" + "a" * 64
RUNTIME_IMAGE = "ghcr.io/ggml-org/llama.cpp@sha256:" + "b" * 64
COLLECTOR_IMAGE = "prom/prometheus@sha256:" + "c" * 64

# One millisecond origin the whole synthetic run hangs off, so that every instant in
# this module is a readable offset from it rather than a literal.
ORIGIN = 1_750_000_000_000


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def validate(document: dict[str, Any]) -> core.Descriptor:
    return validate_descriptor(document, DESCRIPTOR_TEXT)


def mutated(**changes: Any) -> dict[str, Any]:
    """A deep copy of the committed descriptor with one branch replaced."""
    document = copy.deepcopy(DOCUMENT)
    for dotted, value in changes.items():
        cursor: Any = document
        members = dotted.split("__")
        for member in members[:-1]:
            cursor = cursor[member]
        cursor[members[-1]] = value
    return document


#: The helpers that print prose for a person to read. A line that quotes a command
#: inside one of them is documentation, not a call, and every rule below that looks
#: for a command skips them for the same reason `test_cluster_lifecycle_safety` does.
PROSE = ("inferops::log", "inferops::warn", "inferops::fail", "inferops::section")


def code_lines(*, joined: bool = False) -> list[tuple[int, str]]:
    """The script's executable lines, with comments and blank lines dropped.

    With ``joined``, a backslash continuation is folded into the line it continues, so
    that a command written across four lines is read as the one command it is.
    """
    rows: list[tuple[int, str]] = []
    for number, line in enumerate(SCRIPT_LINES, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if joined and rows and rows[-1][1].rstrip().endswith("\\"):
            start, previous = rows[-1]
            rows[-1] = (start, previous.rstrip()[:-1] + " " + line.strip())
            continue
        rows.append((number, line))
    return rows


def prose(line: str) -> bool:
    return any(helper in line for helper in PROSE)


# -- the cluster's answers, as files a run would have written ---------------


def _pod(
    name: str,
    component: str,
    *,
    ready: bool,
    restarts: int = 0,
    init_exit: int = 0,
) -> dict[str, Any]:
    return {
        "metadata": {
            "name": name,
            "uid": f"uid-{name}",
            "namespace": "inferops-release",
            "labels": {"app.kubernetes.io/component": component},
        },
        "status": {
            "phase": "Running",
            "conditions": [{"type": "Ready", "status": "True" if ready else "False"}],
            "initContainerStatuses": [
                {
                    "name": "verify-model",
                    "state": {"terminated": {"exitCode": init_exit}},
                }
            ],
            "containerStatuses": [
                {
                    "name": component.split("-")[-1],
                    "ready": ready,
                    "started": True,
                    "restartCount": restarts,
                    "imageID": RUNTIME_IMAGE,
                }
            ],
        },
    }


def _deployment(name: str, container: str, image: str, cpu: str) -> dict[str, Any]:
    return {
        "metadata": {"name": name},
        "spec": {
            "replicas": 1,
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": container,
                            "image": image,
                            "resources": {
                                "requests": {"cpu": cpu, "memory": "2Gi"},
                                "limits": {"cpu": cpu, "memory": "3Gi"},
                            },
                        }
                    ]
                }
            },
        },
        "status": {"availableReplicas": 1},
    }


def _deployments(cpu: str) -> dict[str, Any]:
    return {
        "items": [
            _deployment("inferops-inferops-llm", "api", API_IMAGE, "1"),
            _deployment("inferops-inferops-llm-runtime", "runtime", RUNTIME_IMAGE, cpu),
            _deployment(
                "inferops-inferops-llm-collector", "collector", COLLECTOR_IMAGE, "1"
            ),
        ]
    }


def write_cluster(directory: Path, *, init_exit: int = 0) -> Path:
    """Everything `extract_environment` reads, as one consistent synthetic run."""
    cluster = directory / "cluster"
    cluster.mkdir(parents=True, exist_ok=True)
    documents: dict[str, Any] = {
        "target.json": {
            "provider": "docker-desktop",
            "cluster": "docker-desktop",
            "context": "docker-desktop",
            "verifiedAt": "2026-09-16T10:00:00Z",
            "nodeImageDigest": "sha256:" + "d" * 64,
            "helmVersion": "v3.19.0",
        },
        "version.json": {
            "clientVersion": {"gitVersion": "v1.34.3"},
            "serverVersion": {"gitVersion": "v1.34.3"},
        },
        "node.json": {
            "metadata": {"name": "desktop-control-plane"},
            "status": {
                "nodeInfo": {
                    "osImage": "Debian GNU/Linux 12",
                    "kernelVersion": "6.6.0",
                    "containerRuntimeVersion": "containerd://2.0.0",
                    "kubeletVersion": "v1.34.3",
                },
                "capacity": {"cpu": "8", "memory": "16Gi"},
                "allocatable": {"cpu": "8", "memory": "15Gi"},
            },
        },
        "engine.json": {
            "serverVersion": "29.7.2",
            "cpus": 8,
            "memoryBytes": 17179869184,
        },
        "helm-release.json": [
            {
                "name": "inferops",
                "chart": "inferops-llm-0.1.0",
                "app_version": "0.1.0",
                "revision": "2",
                "status": "deployed",
            }
        ],
        "configmap.json": {
            "data": {
                "INFEROPS_SERVING_ADAPTER": "real",
                "INFEROPS_REQUEST_TIMEOUT_MS": "60000",
                "INFEROPS_MAX_OUTPUT_TOKENS": "256",
                "INFEROPS_MODEL_IDENTIFIER": "qwen3-1-7b-q8-0",
                "INFEROPS_MODEL_REVISION": "90862c4b9d2787eaed51d12237eafdfe7c5f6077",
                "INFEROPS_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
                "INFEROPS_LLAMA_SERVER_CONTEXT_SIZE": "4096",
                "INFEROPS_LLAMA_SERVER_THREADS": "6",
                "INFEROPS_LLAMA_SERVER_METRICS_ENABLED": "true",
            }
        },
        "deployments-unready.json": _deployments("10m"),
        "deployments-recovered.json": _deployments("6"),
        "pods-unready.json": {
            "items": [
                _pod(UNREADY_POD, "serving-runtime", ready=False, init_exit=init_exit),
                _pod(API_POD, "platform-api", ready=False),
                _pod(COLLECTOR_POD, "telemetry-collector", ready=True),
            ]
        },
        "pods-recovered.json": {
            "items": [
                _pod(RECOVERED_POD, "serving-runtime", ready=True),
                _pod(API_POD, "platform-api", ready=True),
                _pod(COLLECTOR_POD, "telemetry-collector", ready=True),
            ]
        },
        "running-pods.json": {
            "items": [
                {"metadata": {"namespace": "inferops-release", "name": API_POD}},
                {"metadata": {"namespace": "kube-system", "name": "coredns-1"}},
            ]
        },
        "repository.json": {
            "revision": "0" * 40,
            "trackedChangesPresent": False,
            "untrackedFilesPresent": False,
            "executedFiles": {name: "e" * 64 for name in core.EXECUTED_FILES},
        },
    }
    for name, document in documents.items():
        (cluster / name).write_text(dumps(document), encoding="utf-8", newline="\n")
    return cluster


# -- the six inputs ---------------------------------------------------------


def lifecycle_document(**overrides: Any) -> dict[str, Any]:
    window = DESCRIPTOR.unready_window_seconds * 1000
    document: dict[str, Any] = {
        "install": {
            "issuedEpochMs": ORIGIN,
            "runtimeContainerRunningEpochMs": ORIGIN + 30_000,
            "runtimeSocketOpenEpochMs": ORIGIN + 35_000,
            "runtimePodName": UNREADY_POD,
            "runtimePodUid": f"uid-{UNREADY_POD}",
            "runtimeContainerStartedAt": "2026-09-16T10:01:30Z",
            "initContainerName": "verify-model",
            "initExitCode": 0,
        },
        "idleBaseline": {
            "startEpochMs": ORIGIN + 36_000,
            "endEpochMs": ORIGIN + 96_000,
        },
        "unreadyWindow": {
            "startEpochMs": ORIGIN + 100_000,
            "endEpochMs": ORIGIN + 100_000 + window,
        },
        "upgrade": {
            "issuedEpochMs": ORIGIN + 120_000 + window,
            "runtimeReadyEpochMs": ORIGIN + 300_000 + window,
            "apiReadyEpochMs": ORIGIN + 310_000 + window,
            "runtimePodName": RECOVERED_POD,
            "runtimePodUid": f"uid-{RECOVERED_POD}",
            "initContainerName": "verify-model",
            "initExitCode": 0,
        },
        "recoveredWindow": {
            "startEpochMs": ORIGIN + 320_000 + window,
            "endEpochMs": ORIGIN + 380_000 + window,
        },
        "settledEpochMs": ORIGIN + 470_000 + window,
        "release": {"revisionBefore": 1, "revisionAfter": 2},
        "acquisition": {"jobCountBefore": 0, "jobCountAfter": 1},
        "claims": {"countBefore": 1, "countAfter": 1},
        "interventions": ["corrected-the-values-and-upgraded"],
    }
    for dotted, value in overrides.items():
        cursor: Any = document
        members = dotted.split("__")
        for member in members[:-1]:
            cursor = cursor[member]
        cursor[members[-1]] = value
    return document


def readiness_document(
    *,
    unready_samples: int = 8,
    ready_while_unready: bool = False,
    restarts: int = 0,
    gap_after: int | None = None,
) -> dict[str, Any]:
    poll = DESCRIPTOR.poll_interval_ms
    samples = []
    at = ORIGIN + 100_000
    for index in range(unready_samples):
        samples.append(
            {
                "atEpochMs": at,
                "readTookMs": 40,
                "phase": "unready",
                "runtimePodsPresent": 1,
                "runtimePodsReady": 1 if (ready_while_unready and index == 2) else 0,
                "runtimeEndpointsReady": 0,
                "apiPodsReady": 0,
                "apiEndpointsReady": 0,
                "runtimeRestartCount": restarts,
                "apiRestartCount": 0,
            }
        )
        at += poll * (10 if gap_after is not None and index == gap_after else 1)
    window = DESCRIPTOR.unready_window_seconds * 1000
    at = ORIGIN + 320_000 + window
    for _ in range(4):
        samples.append(
            {
                "atEpochMs": at,
                "readTookMs": 40,
                "phase": "recovered",
                "runtimePodsPresent": 1,
                "runtimePodsReady": 1,
                "runtimeEndpointsReady": 1,
                "apiPodsReady": 1,
                "apiEndpointsReady": 1,
                "runtimeRestartCount": restarts,
                "apiRestartCount": 0,
            }
        )
        at += poll
    return {"readiness": {"samples": samples}}


def probe_line(
    *,
    phase: str,
    round_number: int,
    probe_id: str,
    at: int,
    status: int,
    code: str | None = None,
    retryable: bool | None = None,
    detail: str = "detail",
    tokens: int | None = None,
    condition: str | None = None,
) -> str:
    surface = next(item for item in DESCRIPTOR.surfaces if item.probe_id == probe_id)
    return json.dumps(
        {
            "phase": phase,
            "round": round_number,
            "probeId": probe_id,
            "tier": surface.tier,
            "method": surface.method,
            "path": surface.path,
            "atEpochMs": at,
            "latencyMs": 12,
            "status": status,
            "errorCode": code,
            "conditionId": condition,
            "retryable": retryable,
            "detail": detail,
            "bodyBytes": 75,
            "bodySha256": "f" * 64,
            "outputTokens": tokens,
        },
        sort_keys=True,
    )


def probes_text(
    *,
    rounds: int = 4,
    unready_code: str = "model-not-ready",
    unready_status: int = 503,
    retryable: bool | None = True,
    served_tokens: int | None = 9,
    recovered_rounds: int = 2,
) -> str:
    window = DESCRIPTOR.unready_window_seconds * 1000
    lines = []
    at = ORIGIN + 100_000
    for round_number in range(1, rounds + 1):
        lines.append(
            probe_line(
                phase="unready",
                round_number=round_number,
                probe_id="runtime-health",
                at=at,
                status=503,
                detail="Loading model",
            )
        )
        lines.append(
            probe_line(
                phase="unready",
                round_number=round_number,
                probe_id="api-liveness",
                at=at + 1,
                status=200,
                detail="alive",
            )
        )
        lines.append(
            probe_line(
                phase="unready",
                round_number=round_number,
                probe_id="api-readiness",
                at=at + 2,
                status=503,
                detail="not-ready",
            )
        )
        lines.append(
            probe_line(
                phase="unready",
                round_number=round_number,
                probe_id="api-completion",
                at=at + 3,
                status=unready_status,
                code=unready_code,
                retryable=retryable,
                detail="the selected backend is not ready to serve a request",
            )
        )
        at += DESCRIPTOR.round_interval_ms
    at = ORIGIN + 320_000 + window
    for round_number in range(1, recovered_rounds + 1):
        lines.append(
            probe_line(
                phase="recovered",
                round_number=round_number,
                probe_id="runtime-health",
                at=at,
                status=200,
                detail="ok",
            )
        )
        lines.append(
            probe_line(
                phase="recovered",
                round_number=round_number,
                probe_id="api-liveness",
                at=at + 1,
                status=200,
                detail="alive",
            )
        )
        lines.append(
            probe_line(
                phase="recovered",
                round_number=round_number,
                probe_id="api-readiness",
                at=at + 2,
                status=200,
                detail="ready",
            )
        )
        lines.append(
            probe_line(
                phase="recovered",
                round_number=round_number,
                probe_id="api-completion",
                at=at + 3,
                status=200,
                detail="served, finish_reason=stop",
                tokens=served_tokens,
            )
        )
        at += DESCRIPTOR.round_interval_ms
    return "\n".join(lines) + "\n"


#: A capture longer than the excerpt ceiling, so that the synthetic document exercises
#: the truncation the reconciliation is about rather than the trivial case.
SYNTHETIC_CAPTURE_LINES = 14


def diagnostics_document(*, empty: str | None = None) -> dict[str, Any]:
    """Captures whose published accounting adds up, as a real one's must.

    ``excerptLinesKept + excerptLinesWithheld`` has to equal the number of lines the
    builder considered, which is ``min(lines, excerptLines)``. A builder here that
    produced a one-line excerpt from a fourteen-line capture would be describing a
    redaction nobody performed, and the record now refuses it.
    """
    ceiling = DESCRIPTOR.excerpt_lines
    kept = min(SYNTHETIC_CAPTURE_LINES, ceiling)
    excerpt = "\n".join(
        [f"load_model: loading model, line {index}" for index in range(kept)]
    )
    captures = []
    for capture in DESCRIPTOR.captures:
        blank = capture.capture_id == empty
        captures.append(
            {
                "captureId": capture.capture_id,
                "phase": "unready",
                "lines": 0 if blank else SYNTHETIC_CAPTURE_LINES,
                "bytes": 0 if blank else 900,
                "sha256": "a" * 64,
                "excerptLinesWithheld": 0,
                "excerpt": core.EMPTY_EXCERPT if blank else excerpt,
            }
        )
    return {"diagnostics": {"captures": captures}}


def telemetry_document(
    *,
    absent_answers: bool = False,
    present_silent: bool = False,
    wrong_expr: str | None = None,
) -> dict[str, Any]:
    window = DESCRIPTOR.unready_window_seconds * 1000
    series = []
    for registered in DESCRIPTOR.series:
        expr = registered.expr
        if wrong_expr == registered.series_id:
            expr = "something_else"
        silent = registered.exposure in ("nothing-emits", "no-source")
        if silent and not absent_answers:
            result: list[dict[str, Any]] = []
        elif not silent and present_silent:
            result = []
        else:
            result = [
                {
                    "labels": {"job": "inferops-inferops-llm-platform-api"},
                    "values": [
                        [(ORIGIN + 100_000) / 1000, "0"],
                        [(ORIGIN + 100_000 + window) / 1000, "4"],
                        [(ORIGIN + 470_000 + window) / 1000, "7"],
                    ],
                }
            ]
        series.append(
            {
                "seriesId": registered.series_id,
                "expr": expr,
                "status": "success",
                "result": result,
            }
        )
    return {
        "collectorVersion": "3.0.0",
        "range": {
            "startEpochMs": ORIGIN,
            "endEpochMs": ORIGIN + 470_000 + window,
            "stepSeconds": DESCRIPTOR.range_step_seconds,
        },
        "series": series,
    }


def record_from(
    tmp_path: Path,
    *,
    lifecycle: dict[str, Any] | None = None,
    readiness: dict[str, Any] | None = None,
    probes: str | None = None,
    diagnostics: dict[str, Any] | None = None,
    telemetry: dict[str, Any] | None = None,
    init_exit: int = 0,
) -> dict[str, Any]:
    cluster = write_cluster(tmp_path, init_exit=init_exit)
    environment = extract_environment(cluster, DESCRIPTOR)
    return build_record(
        DESCRIPTOR,
        environment_text=dumps(environment),
        lifecycle_text=dumps(
            lifecycle if lifecycle is not None else lifecycle_document()
        ),
        readiness_text=dumps(
            readiness if readiness is not None else readiness_document()
        ),
        probes_text=probes if probes is not None else probes_text(),
        diagnostics_text=dumps(
            diagnostics if diagnostics is not None else diagnostics_document()
        ),
        telemetry_text=dumps(
            telemetry if telemetry is not None else telemetry_document()
        ),
    )


def failed(record: dict[str, Any]) -> set[str]:
    return {check["checkId"] for check in record["checks"] if not check["passed"]}


# --------------------------------------------------------------------------
# The descriptor
# --------------------------------------------------------------------------


def test_the_committed_descriptor_validates() -> None:
    assert DESCRIPTOR.document["experimentId"] == "inferops-unready-model-recovery"


def test_the_descriptor_carries_the_boundary_and_refuses_four_claims() -> None:
    for flag in ("productionBenchmark", "portableCapacityClaim", "availabilityClaim"):
        assert DOCUMENT[flag] is False
    for word in ("availability", "benchmark", "portable capacity", "recovery-time"):
        assert word in DOCUMENT["boundary"]


@pytest.mark.parametrize(
    "flag", ["productionBenchmark", "portableCapacityClaim", "availabilityClaim"]
)
def test_a_descriptor_claiming_more_than_it_may_is_refused(flag: str) -> None:
    with pytest.raises(UnreadyError):
        validate(mutated(**{flag: True}))


def test_a_boundary_that_drops_a_refusal_is_refused() -> None:
    weakened = DOCUMENT["boundary"].replace("recovery-time objective, ", "")
    with pytest.raises(UnreadyError, match="recovery-time"):
        validate(mutated(boundary=weakened))


def test_a_disruption_mechanism_this_module_does_not_own_is_refused() -> None:
    with pytest.raises(UnreadyError, match="mechanism"):
        validate(mutated(disruption__mechanism="delete-serving-runtime-pod-under-load"))


def test_an_overlay_that_sets_anything_but_the_processor_values_is_refused() -> None:
    with pytest.raises(UnreadyError, match="processor"):
        validate(mutated(disruption__overlaySetsOnly=["model.artifact.sizeBytes"]))


def test_a_descriptor_that_does_not_say_what_it_rejected_is_refused() -> None:
    """The choice of disruption is this experiment's design decision.

    A descriptor stating only the mechanism that was taken hides the argument that it
    is not `V1-S3-008`'s and not a crash loop.
    """
    with pytest.raises(UnreadyError, match="rejected mechanisms"):
        validate(mutated(disruption__rejectedMechanisms=["one", "two"]))


def test_the_committed_overlay_touches_no_model_value() -> None:
    """Read as text, not only digested. The digest would not have noticed."""
    body = "\n".join(
        line
        for line in OVERLAY.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    document = yaml.safe_load(body)
    assert set(document) == {"runtime"}
    assert set(document["runtime"]) == {"resources"}
    assert set(document["runtime"]["resources"]["requests"]) == {"cpu"}
    assert set(document["runtime"]["resources"]["limits"]) == {"cpu"}


def test_an_overlay_that_is_not_committed_is_refused(tmp_path: Path) -> None:
    with pytest.raises(UnreadyError, match="not committed"):
        validate_descriptor(
            mutated(disruption__valuesOverlayRef="deploy/nope.yaml"),
            DESCRIPTOR_TEXT,
            repo_root=tmp_path,
        )


def test_the_descriptor_pins_the_overlay_by_digest() -> None:
    assert re.fullmatch(r"[0-9a-f]{64}", DESCRIPTOR.overlay_sha256)


def test_an_unready_window_past_the_startup_probe_budget_is_refused() -> None:
    """Past it the kubelet restarts the container, and the count stops being the
    model's."""
    with pytest.raises(UnreadyError, match=r"at most|startup"):
        validate(
            mutated(observation__unreadyWindowSeconds=RUNTIME_STARTUP_BUDGET_MS // 1000)
        )


def test_an_unready_window_too_short_to_hold_three_probe_rounds_is_refused() -> None:
    with pytest.raises(UnreadyError, match="three probe rounds"):
        validate(
            mutated(
                observation__unreadyWindowSeconds=60,
                probes__roundIntervalMs=30_000,
                observation__minimumSamples=4,
                observation__pollIntervalMs=5_000,
            )
        )


def test_an_experiment_that_expects_no_intervention_is_refused() -> None:
    """The opposite of `V1-S4-006`, and deliberately so.

    A deleted pod is replaced by a controller. A model that cannot load is not, and a
    descriptor claiming it expected nobody to act would be claiming a self-healing
    property this platform does not have.
    """
    with pytest.raises(UnreadyError, match="recoveryInterventionExpected"):
        validate(mutated(humanAction__recoveryInterventionExpected=False))


def test_a_mock_release_is_refused() -> None:
    with pytest.raises(UnreadyError, match="mock"):
        validate(mutated(release__profile="mock"))


def test_a_second_runtime_replica_is_refused() -> None:
    with pytest.raises(UnreadyError, match="one replica"):
        validate(mutated(release__runtimeReplicas=2))


def test_an_experiment_that_never_asks_the_runtime_itself_is_refused() -> None:
    surfaces = [
        surface
        for surface in copy.deepcopy(DOCUMENT["probes"]["surfaces"])
        if surface["tier"] != "serving-runtime"
    ]
    with pytest.raises(UnreadyError, match="serving runtime directly"):
        validate(mutated(probes__surfaces=surfaces))


def test_a_surface_asked_in_only_one_phase_is_refused() -> None:
    surfaces = copy.deepcopy(DOCUMENT["probes"]["surfaces"])
    surfaces[0]["phases"] = ["unready"]
    with pytest.raises(UnreadyError, match="both phases"):
        validate(mutated(probes__surfaces=surfaces))


def test_a_completion_not_expected_to_be_served_after_the_fix_is_refused() -> None:
    surfaces = copy.deepcopy(DOCUMENT["probes"]["surfaces"])
    for surface in surfaces:
        if surface["method"] == "POST":
            surface["expectedRecoveredStatus"] = 503
    with pytest.raises(UnreadyError, match="recovered"):
        validate(mutated(probes__surfaces=surfaces))


@pytest.mark.parametrize("code", ["model-not-ready", "capability-unavailable"])
def test_a_refusal_vocabulary_omitting_either_mapped_code_is_refused(code: str) -> None:
    """Both are what `ADR 0010 D8` maps this situation to, and which one arrives is
    the result rather than the arrangement."""
    codes = [
        entry for entry in DOCUMENT["probes"]["canonicalRefusalCodes"] if entry != code
    ]
    with pytest.raises(UnreadyError, match=code):
        validate(mutated(probes__canonicalRefusalCodes=codes))


def test_a_telemetry_row_pairing_an_impossible_answerability_is_refused() -> None:
    series = copy.deepcopy(DOCUMENT["telemetry"]["series"])
    series[0]["answerability"] = "no-source"
    with pytest.raises(UnreadyError, match="cannot both be true"):
        validate(mutated(telemetry__series=series))


def test_a_telemetry_set_that_does_not_ask_model_ready_is_refused() -> None:
    """The one metric whose declared question is this experiment's question."""
    series = [
        entry
        for entry in copy.deepcopy(DOCUMENT["telemetry"]["series"])
        if entry["expr"] != "inferops_model_ready"
    ]
    with pytest.raises(UnreadyError, match="inferops_model_ready"):
        validate(mutated(telemetry__series=series))


def test_a_telemetry_set_naming_only_signals_that_work_is_refused() -> None:
    series = copy.deepcopy(DOCUMENT["telemetry"]["series"])
    for entry in series:
        if entry["exposure"] == "expected-not-to-expose":
            entry["exposure"] = "expected-to-expose"
    with pytest.raises(UnreadyError, match="not a classification"):
        validate(mutated(telemetry__series=series))


def test_a_diagnostic_set_naming_no_cause_is_refused() -> None:
    captures = copy.deepcopy(DOCUMENT["diagnostics"]["captures"])
    for capture in captures:
        capture["identifiesCause"] = "partial"
    with pytest.raises(UnreadyError, match="naming the cause"):
        validate(mutated(diagnostics__captures=captures))


def test_evidence_written_outside_the_ignored_tree_is_refused() -> None:
    with pytest.raises(UnreadyError, match=r"\.cache/inferops/experiments"):
        validate(mutated(evidence__directory="docs/proof/serving"))


def test_a_forward_that_is_not_loopback_is_refused() -> None:
    with pytest.raises(UnreadyError, match=r"loopback|127"):
        validate(mutated(forwards__host="0.0.0.0"))


def test_a_cleanup_that_removes_a_prerequisite_is_refused() -> None:
    with pytest.raises(UnreadyError, match="removesModelCacheClaim"):
        validate(mutated(cleanup__removesModelCacheClaim=True))


def test_a_recovery_budget_inside_the_rollout_budget_is_refused() -> None:
    with pytest.raises(UnreadyError, match="recovery budget"):
        validate(mutated(readiness__recoveryBudgetMs=1000))


def test_the_descriptor_fields_the_script_reads_all_resolve() -> None:
    """Every dotted path the operating script asks for exists and is a scalar."""
    asked = re.search(r"fields \\\n(.*?)\)\"; then", SCRIPT_TEXT, re.S)
    assert asked is not None
    paths = [
        token
        for token in asked.group(1).replace("\\", " ").split()
        if core.DOTTED_PATH.fullmatch(token)
    ]
    assert len(paths) > 20
    assert descriptor_fields(DESCRIPTOR, paths)


def test_a_dotted_path_naming_a_structure_is_refused() -> None:
    with pytest.raises(UnreadyError, match="not a value a shell can read"):
        descriptor_fields(DESCRIPTOR, ["telemetry"])


def test_the_summary_always_states_what_the_experiment_may_not_claim() -> None:
    text = "\n".join(summary_lines(DESCRIPTOR))
    for word in (
        "availability",
        "error budget",
        "recovery-time objective",
        "benchmark",
    ):
        assert word in text


def test_the_probe_rows_the_shell_loops_over_are_the_registered_surfaces() -> None:
    rows = probe_lines(DESCRIPTOR)
    assert len(rows) == len(DESCRIPTOR.surfaces)
    for row, surface in zip(rows, DESCRIPTOR.surfaces, strict=True):
        assert row.split() == [
            surface.probe_id,
            surface.tier,
            surface.method,
            surface.path,
            str(surface.unready_status),
            str(surface.recovered_status),
        ]


# --------------------------------------------------------------------------
# The operating script, read as text
# --------------------------------------------------------------------------


def test_the_script_deletes_nothing() -> None:
    """The one safety property that separates this from every other experiment here.

    Nothing is deleted while the release is up. The only removal is the uninstall that
    ends the run, and `helm uninstall` is not a delete of an object this script names.
    """
    offenders = [
        f"{number}: {line}"
        for number, line in code_lines()
        if re.search(r"kubectl\s+delete\b", line) and not prose(line)
    ]
    assert not offenders, offenders


def test_the_script_never_removes_what_outlives_a_release() -> None:
    forbidden = (
        "delete namespace",
        "delete pvc",
        "delete ns",
        "terraform-prerequisites.sh destroy",
    )
    for number, line in code_lines():
        if prose(line):
            continue
        for token in forbidden:
            assert token not in line, f"{number}: {line}"


def test_every_mutating_helm_and_kubectl_call_goes_through_the_target_wrappers() -> (
    None
):
    """A bare call could act on whichever cluster the operator's context names.

    Stated in terms of the verbs that change something, for the reason
    `test_cluster_lifecycle_safety` states it that way: a warning that quotes
    `helm uninstall` for an operator to read is prose, not a call.
    """
    mutating = re.compile(
        r"(?<!::target_)\b(?:kubectl\s+(?:annotate|apply|create|delete|edit|label|"
        r"patch|replace|scale)|helm\s+(?:install|upgrade|rollback|uninstall))\b"
    )
    offenders = [
        f"{number}: {line.strip()}"
        for number, line in code_lines()
        if mutating.search(line) and not prose(line)
    ]
    assert not offenders, offenders


def test_the_script_refuses_before_it_contacts_anything() -> None:
    def first(pattern: str) -> int:
        for number, line in code_lines():
            if re.search(pattern, line):
                return number
        raise AssertionError(pattern)

    confirmed = first(r'\[ "\$\{confirmed\}" -eq 1 \]')
    resolved = first(r"inferops::resolve_target")
    installed = first(r"inferops::target_helm install")
    assert confirmed < resolved < installed


def test_the_forwards_bind_loopback_and_the_run_directory_is_never_overwritten() -> (
    None
):
    assert '[ "${forward_host}" = "127.0.0.1" ]' in SCRIPT_TEXT
    assert "the run directory ${evidence_rel} already exists" in SCRIPT_TEXT


def test_the_forwards_address_pods_and_not_the_workload_services() -> None:
    """A release whose model is not ready has no ready endpoint on either Service."""
    assert 'open_forward "pod/${api_pod}"' in SCRIPT_TEXT
    assert 'open_forward "pod/${runtime_pod}"' in SCRIPT_TEXT
    assert 'open_forward "service/${collector_service}"' in SCRIPT_TEXT


def test_the_script_does_not_wait_on_a_rollout_that_cannot_complete() -> None:
    """`rollout status` completes when a pod is *ready*, and neither will be."""
    rollouts = [
        line
        for _, line in code_lines(joined=True)
        if "rollout status" in line and not prose(line)
    ]
    assert len(rollouts) == 1
    assert "collector_deployment" in rollouts[0]


def test_exactly_two_mutating_commands_follow_the_install() -> None:
    """What the record's single registered intervention rests on.

    The upgrade that corrects the values and the uninstall that ends the run. Anything
    else between them would make the intervention list a description of one command
    while two had run.
    """
    start = next(
        number
        for number, line in code_lines(joined=True)
        if "inferops::target_helm install" in line and not prose(line)
    )
    mutating = re.compile(
        r"inferops::target_(kubectl\s+(annotate|apply|create|delete|edit|label|patch|"
        r"replace|scale)|helm\s+(install|upgrade|rollback|uninstall))"
    )
    after = [
        f"{number}: {line.strip()}"
        for number, line in code_lines(joined=True)
        if number > start and mutating.search(line) and not prose(line)
    ]
    assert len(after) == 2, after
    assert "helm upgrade" in after[0]
    assert "helm uninstall" in after[1]


def test_the_upgrade_drops_the_overlay_and_keeps_everything_else() -> None:
    upgrade = next(
        line
        for _, line in code_lines(joined=True)
        if "inferops::target_helm upgrade" in line and not prose(line)
    )
    assert "values_arguments" in upgrade
    assert "overlay_argument" not in upgrade


def test_the_install_passes_the_committed_overlay_and_the_script_supplies_it() -> None:
    install = next(
        line
        for _, line in code_lines(joined=True)
        if "inferops::target_helm install" in line and not prose(line)
    )
    assert "overlay_argument" in install
    assert "unready-model-values.v1.yaml" in SCRIPT_TEXT


def test_the_script_never_keeps_a_completion_body() -> None:
    """`retainGeneratedText` is false, and a completion body is generated text.

    Three assertions, and the third is the one that means anything. An earlier version
    asserted only that a *comment* saying the text is not read appeared in the script,
    which independent review rightly called an overclaim: a comment establishes nothing
    about behaviour. What is asserted now is the classifier's own source — that the one
    place a completion body is parsed reads `finish_reason` and `completion_tokens` and
    never reaches for the message, the content, or the text — and the shape of every
    record it may write.
    """
    assert DOCUMENT["probes"]["retainGeneratedText"] is False

    classifier = SCRIPT_TEXT[
        SCRIPT_TEXT.index("PROBE_PYTHON") : SCRIPT_TEXT.rindex("PROBE_PYTHON")
    ]
    assert 'choice.get("finish_reason")' in classifier
    assert 'usage.get("completion_tokens")' in classifier
    # `error.get("message")` is allowed and used: an API error message is the platform's
    # own words about a refusal, not anything a model generated. What may not appear is
    # a reach into a *choice* for what it said.
    for reach in ('"content"', '"text"', '["message"]', 'choice.get("message")'):
        assert reach not in classifier, reach

    # And the line it writes: a fixed set of keys, none of which can hold a completion.
    line = classifier[classifier.index("line = {") : classifier.index("sys.stdout")]
    keys = set(re.findall(r'"([A-Za-z0-9]+)":', line))
    assert keys == {
        "phase",
        "round",
        "probeId",
        "tier",
        "method",
        "path",
        "atEpochMs",
        "latencyMs",
        "status",
        "errorCode",
        "conditionId",
        "retryable",
        "detail",
        "bodyBytes",
        "bodySha256",
        "outputTokens",
    }, sorted(keys)


def test_no_committed_probe_record_carries_a_completion() -> None:
    """The published probe set, read key by key against the same fixed shape."""
    committed = (PROOF_DIR / f"{PROOF_PREFIX}probes.v1alpha1.jsonl").read_text(
        encoding="utf-8"
    )
    allowed = {
        "phase",
        "round",
        "probeId",
        "tier",
        "method",
        "path",
        "atEpochMs",
        "latencyMs",
        "status",
        "errorCode",
        "conditionId",
        "retryable",
        "detail",
        "bodyBytes",
        "bodySha256",
        "outputTokens",
    }
    rows = [json.loads(line) for line in committed.splitlines() if line.strip()]
    assert rows
    for row in rows:
        assert set(row) == allowed, sorted(set(row) ^ allowed)
        # The detail of a served completion names its finish reason and nothing it said.
        if row["status"] == 200 and row["probeId"] == "api-completion":
            assert row["detail"].startswith("served, finish_reason=")


def test_the_script_records_exactly_the_one_intervention_it_registers() -> None:
    assert '"interventions": ["corrected-the-values-and-upgraded"],' in SCRIPT_TEXT


def test_the_script_refuses_an_argument_it_does_not_understand() -> None:
    assert 'inferops::fail "unknown argument' in SCRIPT_TEXT


def test_the_script_is_listed_among_the_lifecycle_entry_points() -> None:
    from tests.architecture.test_cluster_lifecycle_safety import ENTRY_POINTS

    assert "unready-model-recovery.sh" in ENTRY_POINTS


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


def test_a_consistent_run_produces_a_usable_record(tmp_path: Path) -> None:
    record = record_from(tmp_path)
    assert record["usable"], failed(record)


def test_the_record_refuses_the_three_claims_it_may_not_make(tmp_path: Path) -> None:
    record = record_from(tmp_path)
    for flag in ("productionBenchmark", "portableCapacityClaim", "availabilityClaim"):
        assert record[flag] is False


def test_the_record_states_the_code_a_caller_actually_met(tmp_path: Path) -> None:
    record = record_from(
        tmp_path, probes=probes_text(unready_code="capability-unavailable")
    )
    assert record["callerSurface"]["canonicalCodesObserved"] == [
        "capability-unavailable"
    ]
    assert record["usable"], failed(record)


def test_two_different_codes_across_the_window_are_not_usable(tmp_path: Path) -> None:
    """A caller could not have been told the same thing twice."""
    mixed = probes_text().replace(
        '"errorCode": "model-not-ready"', '"errorCode": "capability-unavailable"', 1
    )
    record = record_from(tmp_path, probes=mixed)
    assert "one-canonical-code-answered-the-whole-unready-window" in failed(record)


def test_a_code_outside_the_registered_vocabulary_is_refused(tmp_path: Path) -> None:
    rogue = probes_text().replace('"model-not-ready"', '"everything-is-fine"')
    with pytest.raises(UnreadyRefused, match="vocabulary"):
        record_from(tmp_path, probes=rogue)


def test_a_probe_naming_a_surface_the_descriptor_does_not_register_is_refused(
    tmp_path: Path,
) -> None:
    rogue = probes_text().replace('"api-liveness"', '"api-secret-backdoor"')
    with pytest.raises(UnreadyRefused, match=r"which the descriptor does not"):
        record_from(tmp_path, probes=rogue)


def test_a_probe_sent_to_a_path_the_descriptor_does_not_register_is_refused(
    tmp_path: Path,
) -> None:
    rogue = probes_text().replace('"/health/live"', '"/admin"')
    with pytest.raises(UnreadyRefused, match="path"):
        record_from(tmp_path, probes=rogue)


def test_a_ready_sample_inside_the_unready_window_is_not_usable(tmp_path: Path) -> None:
    record = record_from(
        tmp_path, readiness=readiness_document(ready_while_unready=True)
    )
    assert "readiness-was-false-for-the-whole-unready-window" in failed(record)


def test_a_restarted_runtime_container_is_not_usable(tmp_path: Path) -> None:
    """The point of a TCP liveness probe is that this does not happen."""
    record = record_from(tmp_path, readiness=readiness_document(restarts=1))
    assert "liveness-did-not-restart-a-healthy-process" in failed(record)


def test_a_gap_in_the_readiness_samples_is_not_usable(tmp_path: Path) -> None:
    record = record_from(tmp_path, readiness=readiness_document(gap_after=3))
    assert "readiness-samples-cover-the-unready-window" in failed(record)


def test_too_few_readiness_samples_inside_the_window_are_refused(
    tmp_path: Path,
) -> None:
    """Counted over the unready window, not over the file.

    Samples taken after the fix do not support a claim that readiness stayed false
    before it, however many of them there are -- and the builder below keeps four of
    them, so a run with two unready samples still has six in the file.
    """
    with pytest.raises(UnreadyRefused, match="inside the unready window"):
        record_from(tmp_path, readiness=readiness_document(unready_samples=2))


def test_a_window_held_for_less_than_the_registered_one_is_refused(
    tmp_path: Path,
) -> None:
    short = lifecycle_document(unreadyWindow__endEpochMs=ORIGIN + 130_000)
    with pytest.raises(UnreadyRefused, match="unready window was held"):
        record_from(tmp_path, lifecycle=short)


def test_an_integrity_check_that_did_not_pass_is_not_usable(tmp_path: Path) -> None:
    """Without it, this would be V1-S3-008's artifact fault wearing another name."""
    record = record_from(
        tmp_path,
        lifecycle=lifecycle_document(install__initExitCode=1),
        init_exit=1,
    )
    assert "the-model-artifact-was-never-in-question" in failed(record)


def test_a_release_revision_that_did_not_move_is_not_usable(tmp_path: Path) -> None:
    record = record_from(
        tmp_path, lifecycle=lifecycle_document(release__revisionAfter=1)
    )
    assert "the-fix-moved-the-release-revision" in failed(record)


def test_a_completion_answered_200_with_no_tokens_is_not_usable(tmp_path: Path) -> None:
    """A 200 with nothing in it is a status, not a served completion."""
    record = record_from(tmp_path, probes=probes_text(served_tokens=0))
    assert "a-real-completion-came-back-after-the-fix" in failed(record)


def test_a_refusal_that_was_not_retryable_is_not_usable(tmp_path: Path) -> None:
    record = record_from(tmp_path, probes=probes_text(retryable=False))
    assert "every-canonical-refusal-was-retryable" in failed(record)


def test_a_completion_answered_with_an_unregistered_status_is_not_usable(
    tmp_path: Path,
) -> None:
    record = record_from(tmp_path, probes=probes_text(unready_status=500))
    assert "every-completion-while-unready-was-refused-canonically" in failed(record)


def test_an_empty_diagnostic_capture_is_not_usable(tmp_path: Path) -> None:
    record = record_from(
        tmp_path, diagnostics=diagnostics_document(empty="runtime-log")
    )
    assert "every-registered-diagnostic-was-captured" in failed(record)
    assert "a-diagnostic-registered-as-naming-the-cause-was-captured" in failed(record)


def test_a_capture_the_descriptor_registers_and_the_run_skipped_is_refused(
    tmp_path: Path,
) -> None:
    document = diagnostics_document()
    document["diagnostics"]["captures"] = document["diagnostics"]["captures"][1:]
    with pytest.raises(UnreadyRefused, match="captured no"):
        record_from(tmp_path, diagnostics=document)


def test_an_intervention_the_experiment_did_not_register_is_not_usable(
    tmp_path: Path,
) -> None:
    record = record_from(
        tmp_path, lifecycle=lifecycle_document(interventions=["restarted-a-workload"])
    )
    assert "the-only-intervention-was-the-registered-fix" in failed(record)


def test_an_intervention_outside_the_vocabulary_is_refused(tmp_path: Path) -> None:
    with pytest.raises(UnreadyError, match="must be one of"):
        record_from(
            tmp_path, lifecycle=lifecycle_document(interventions=["improvised"])
        )


def test_instants_out_of_order_are_refused(tmp_path: Path) -> None:
    with pytest.raises(UnreadyError, match="at least"):
        record_from(
            tmp_path, lifecycle=lifecycle_document(upgrade__runtimeReadyEpochMs=ORIGIN)
        )


@pytest.mark.parametrize(
    ("dotted", "value"),
    [
        ("install__runtimeContainerRunningEpochMs", ORIGIN - 1),
        ("install__runtimeSocketOpenEpochMs", ORIGIN + 29_000),
        ("idleBaseline__startEpochMs", ORIGIN + 34_000),
        ("unreadyWindow__endEpochMs", ORIGIN + 95_000),
        ("upgrade__runtimeReadyEpochMs", ORIGIN + 100),
        ("upgrade__apiReadyEpochMs", ORIGIN + 100),
    ],
)
def test_the_lifecycle_reader_refuses_every_ordering_inversion(
    dotted: str, value: int
) -> None:
    """Where `no-published-interval-is-negative` is actually guaranteed.

    That check is a tripwire on the derivation and cannot fail for a record whose
    inputs this reader accepted — every instant its differences are taken between
    carries an ordering minimum here. Independent review asked for a negative control
    on the check; the honest one is a control per inversion on the thing that makes the
    check unreachable, because weakening any of these is what would reach it.
    """
    with pytest.raises(UnreadyError, match="at least"):
        parse_lifecycle(lifecycle_document(**{dotted: value}), DESCRIPTOR)


def test_no_published_interval_is_ever_negative(tmp_path: Path) -> None:
    record = record_from(tmp_path)
    for name in (
        "installToRuntimeContainerRunningMs",
        "runtimeContainerRunningToSocketAnsweredCeilingMs",
        "unreadyWindowHeldMs",
        "upgradeToRuntimeReadyMs",
        "upgradeToApiReadyMs",
        "upgradeToFirstServedCompletionMs",
        "upgradeToRecoveredWindowOpenMs",
        "recoveredWindowOpenToFirstServedCompletionMs",
    ):
        assert record["timings"][name] >= 0
    assert "no-published-interval-is-negative" not in failed(record)


def test_the_record_bounds_the_window_against_the_startup_probe_budget(
    tmp_path: Path,
) -> None:
    """A restart count is only a fact about liveness inside the budget that would
    otherwise have produced one."""
    record = record_from(tmp_path)
    timings = record["timings"]
    assert timings["runtimeStartupProbeBudgetMs"] == RUNTIME_STARTUP_BUDGET_MS
    assert 0 < timings["unreadyWindowAsShareOfStartupBudget"] < 1


def test_the_misconfiguration_is_read_from_the_cluster_and_not_the_values_file(
    tmp_path: Path,
) -> None:
    record = record_from(tmp_path)
    cpu = record["disruption"]["servingRuntimeCpu"]
    assert cpu["unready"]["limit"] == "10m"
    assert cpu["recovered"]["limit"] == "6"


def test_the_record_names_the_mechanisms_it_rejected(tmp_path: Path) -> None:
    record = record_from(tmp_path)
    assert len(record["disruption"]["rejectedMechanisms"]) >= 3


# --------------------------------------------------------------------------
# Telemetry
# --------------------------------------------------------------------------


def test_a_registered_absence_that_answered_is_not_usable(tmp_path: Path) -> None:
    record = record_from(tmp_path, telemetry=telemetry_document(absent_answers=True))
    assert "telemetry-registered-absences-are-absent" in failed(record)


def test_a_registered_signal_that_did_not_answer_is_not_usable(tmp_path: Path) -> None:
    record = record_from(tmp_path, telemetry=telemetry_document(present_silent=True))
    assert "telemetry-registered-signals-answered" in failed(record)


def test_an_expression_the_descriptor_does_not_register_is_refused(
    tmp_path: Path,
) -> None:
    with pytest.raises(UnreadyRefused, match="does not register"):
        record_from(
            tmp_path, telemetry=telemetry_document(wrong_expr="api-errors-by-code")
        )


def test_the_record_does_not_decide_whether_a_signal_exposed_the_state(
    tmp_path: Path,
) -> None:
    """ADR 0013 D4 keeps that judgement in a reviewed document, not in a tool."""
    record = record_from(tmp_path)
    for row in record["telemetry"]["series"]:
        assert set(row) >= {"exposure", "expectation", "readingWhileUnready"}
        assert "exposedIt" not in row
        assert "verdict" not in row


def test_the_model_ready_gauge_is_asked_and_answers_nothing(tmp_path: Path) -> None:
    record = record_from(tmp_path)
    row = next(
        entry
        for entry in record["telemetry"]["series"]
        if entry["expr"] == "inferops_model_ready"
    )
    assert row["answerability"] == "not-answerable-nothing-emits"
    assert row["seriesReturned"] == 0


# --------------------------------------------------------------------------
# Privacy, digests, readers, CLI
# --------------------------------------------------------------------------


#: The three shapes a committed record may not carry, assembled here rather than
#: written out. The security baseline refuses a personal filesystem path in *any*
#: committed file and does not exempt a test that is demonstrating one, which is the
#: right rule and which this suite would otherwise break -- so the negative controls
#: are built from parts and no committed line contains one.
PRIVATE_POISON = (
    "Z:" + "\\" + "some-cache" + "\\" + "models",
    "/c/" + "Users" + "/someone/models",
    "192.168." + "1.44",
)

#: An address of the shape `kubectl describe pod` prints, assembled the same way and
#: deliberately not one any run of this experiment observed. A fixture that happened to
#: be a real pod's address would be the thing this suite exists to refuse, written into
#: the suite.
POD_ADDRESS_SHAPE = "10.244." + "203.17"


@pytest.mark.parametrize("poison", PRIVATE_POISON)
def test_an_input_carrying_a_private_value_is_refused(
    tmp_path: Path, poison: str
) -> None:
    """It matters more here than anywhere else: one input is a diagnostic bundle."""
    document = diagnostics_document()
    document["diagnostics"]["captures"][0]["excerpt"] = poison
    with pytest.raises(UnreadyRefused):
        record_from(tmp_path, diagnostics=document)


def test_the_record_pins_every_input_by_digest(tmp_path: Path) -> None:
    record = record_from(tmp_path)
    assert set(record["inputs"]) == {
        "environment",
        "lifecycle",
        "readiness",
        "probes",
        "diagnostics",
        "telemetry",
    }
    for digest in record["inputs"].values():
        assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_the_record_pins_the_descriptor_and_the_overlay(tmp_path: Path) -> None:
    record = record_from(tmp_path)
    assert record["descriptorSha256"] == DESCRIPTOR.sha256
    assert record["valuesOverlaySha256"] == DESCRIPTOR.overlay_sha256


def test_the_environment_keeps_other_workloads_as_a_count_and_never_a_name(
    tmp_path: Path,
) -> None:
    environment = extract_environment(write_cluster(tmp_path), DESCRIPTOR)
    assert environment["background"] == {
        "runningPodsOutsideRelease": 1,
        "namespacesWithRunningPodsOutsideRelease": 1,
    }
    assert "coredns-1" not in dumps(environment)


def test_the_environment_keeps_a_pod_that_was_never_ready(tmp_path: Path) -> None:
    """Every other experiment here keeps running pods only. This one has none."""
    environment = extract_environment(write_cluster(tmp_path), DESCRIPTOR)
    runtime = next(
        pod for pod in environment["podsUnready"] if pod["role"] == "runtime"
    )
    assert runtime["ready"] is False
    assert runtime["containersStarted"] is True


def test_a_sample_labelled_with_a_phase_it_was_not_taken_in_is_refused(
    tmp_path: Path,
) -> None:
    """The hole independent review found, and the record it produced.

    A sample taken five seconds into the unready window, relabelled `recovered` and
    given a ready pod, used to satisfy `the-runtime-became-ready-after-the-fix` from
    205 seconds before the recovered window opened — with `usable: True` and no failed
    check. A row's phase is a claim about *when* it was taken, and it is now checked
    against the window that phase opened and closed.
    """
    document = readiness_document()
    early = document["readiness"]["samples"][1]
    assert early["phase"] == "unready"
    early["phase"] = "recovered"
    early["runtimePodsReady"] = 1
    with pytest.raises(UnreadyRefused, match="outside the recovered window"):
        record_from(tmp_path, readiness=document)


def test_a_sample_stamped_before_its_own_window_opened_is_refused(
    tmp_path: Path,
) -> None:
    document = readiness_document()
    document["readiness"]["samples"][0]["atEpochMs"] = ORIGIN + 96_000 - 1
    with pytest.raises(UnreadyRefused, match="outside the unready window"):
        record_from(tmp_path, readiness=document)


def test_a_probe_labelled_with_a_phase_it_was_not_sent_in_is_refused(
    tmp_path: Path,
) -> None:
    """The same hole on the surface that decides what a caller was told."""
    rogue = probes_text().replace('"phase": "unready"', '"phase": "recovered"', 1)
    with pytest.raises(UnreadyRefused, match="outside the recovered window"):
        record_from(tmp_path, probes=rogue)


def test_a_row_stamped_just_after_its_window_closed_is_accepted() -> None:
    """One poll of slack, forwards only, and none backwards.

    The sampling loop reads the clock before it writes and the window is closed by the
    next statement, so a row can land fractionally late through no fault of the run.
    Nothing is allowed early, which is the direction the relabelling hole ran in. Asked
    of the reader rather than of a whole record, because the record's other rules are
    about coverage and this one is about the bound.
    """
    lifecycle = parse_lifecycle(lifecycle_document(), DESCRIPTOR)
    end = int(lifecycle["unreadyWindow"]["endEpochMs"])
    document = readiness_document()
    unready = [s for s in document["readiness"]["samples"] if s["phase"] == "unready"]
    late = dict(unready[-1])
    late["atEpochMs"] = end + DESCRIPTOR.poll_interval_ms - 1
    document["readiness"]["samples"] = [*unready, late]
    assert parse_readiness(document, DESCRIPTOR, lifecycle)

    too_late = dict(late)
    too_late["atEpochMs"] = end + DESCRIPTOR.poll_interval_ms + 1
    document["readiness"]["samples"] = [*unready, too_late]
    with pytest.raises(UnreadyRefused, match="outside the unready window"):
        parse_readiness(document, DESCRIPTOR, lifecycle)


def test_the_readiness_reader_refuses_samples_out_of_order(tmp_path: Path) -> None:
    document = readiness_document()
    document["readiness"]["samples"][3]["atEpochMs"] = ORIGIN
    with pytest.raises(UnreadyError, match="at least"):
        parse_readiness(document, DESCRIPTOR)


def test_the_probe_reader_refuses_an_empty_record_set() -> None:
    with pytest.raises(UnreadyRefused, match="empty"):
        parse_probes("\n\n", DESCRIPTOR)


def test_the_probe_reader_accepts_windows_line_endings() -> None:
    rows = parse_probes(probes_text().replace("\n", "\r\n"), DESCRIPTOR)
    assert rows


def test_the_lifecycle_reader_derives_the_window_it_does_not_take_it() -> None:
    parsed = parse_lifecycle(lifecycle_document(), DESCRIPTOR)
    assert (
        parsed["unreadyWindow"]["heldMs"]
        == parsed["unreadyWindow"]["endEpochMs"]
        - parsed["unreadyWindow"]["startEpochMs"]
    )


def test_a_capture_excerpt_carrying_a_private_value_is_not_publishable(
    tmp_path: Path,
) -> None:
    """The first complete run was refused here, by its own privacy check.

    `kubectl describe pod` prints the pod's address. The excerpt now withholds the
    lines that carry one and counts them, and this is the check that would notice if
    a filtered excerpt ever carried one anyway -- so the negative control below asks
    for the refusal that still applies to the whole document.
    """
    document = diagnostics_document()
    document["diagnostics"]["captures"][0]["excerpt"] = f"IP: {POD_ADDRESS_SHAPE}"
    with pytest.raises(UnreadyRefused):
        record_from(tmp_path, diagnostics=document)


def test_the_record_publishes_what_was_kept_as_well_as_what_was_withheld(
    tmp_path: Path,
) -> None:
    """`lines` is the whole capture; `excerptLinesKept` is what a reader sees.

    Independent review found the published table quoting the first as the second and
    overstating one capture's published content about thirteenfold, so the record now
    carries both and the reconciliation below ties them together.
    """
    record = record_from(tmp_path)
    row = record["diagnostics"]["captures"][0]
    assert row["lines"] == SYNTHETIC_CAPTURE_LINES
    assert row["excerptLinesKept"] == len(row["excerpt"].splitlines())
    assert (
        row["excerptLinesKept"] + row["excerptLinesWithheld"]
        == row["excerptLinesConsidered"]
    )
    assert record["usable"], failed(record)


def test_a_withheld_count_that_does_not_reconcile_is_not_usable(
    tmp_path: Path,
) -> None:
    """What replaced a check that could not fail.

    `every-capture-excerpt-is-publishable` asked whether an excerpt carried a private
    value, which `build_record` already refuses over the same text before any check
    runs — so it could only ever pass and it inflated `usable`. The refusal stays; the
    check now asks the reachable question.
    """
    document = diagnostics_document()
    document["diagnostics"]["captures"][0]["excerptLinesWithheld"] = 3
    record = record_from(tmp_path, diagnostics=document)
    assert "the-withheld-line-accounting-reconciles" in failed(record)


def test_the_excerpt_ceiling_is_the_descriptors(tmp_path: Path) -> None:
    """One decision, one home: the shell no longer carries its own copy."""
    assert DESCRIPTOR.excerpt_lines == DOCUMENT["diagnostics"]["excerptLines"]
    assert "INFEROPS_EXCERPT_LINES" not in SCRIPT_TEXT
    assert "diagnostics.excerptLines" in SCRIPT_TEXT


def test_the_diagnostics_builder_withholds_a_line_with_an_address(
    tmp_path: Path,
) -> None:
    """A line is kept entire or withheld entire; nothing is masked."""
    capture = tmp_path / "runtime-describe.txt"
    capture.write_text(
        f"Events:\n  Pulled image\n  IP: {POD_ADDRESS_SHAPE}\n  Started container\n",
        encoding="utf-8",
        newline="\n",
    )
    index = tmp_path / "index.txt"
    index.write_text(
        f"runtime-describe unready {capture}\n", encoding="utf-8", newline="\n"
    )
    document = core.build_diagnostics(index, excerpt_lines=12)
    entry = document["diagnostics"]["captures"][0]
    assert entry["excerptLinesWithheld"] == 1
    assert POD_ADDRESS_SHAPE not in entry["excerpt"]
    assert "Started container" in entry["excerpt"]
    assert entry["lines"] == 4


def test_the_diagnostics_reader_carries_the_registered_expectation_through() -> None:
    rows = parse_diagnostics(diagnostics_document(), DESCRIPTOR)
    for row, registered in zip(rows, DESCRIPTOR.captures, strict=True):
        assert row["expectation"] == registered.expectation
        assert row["identifiesCause"] == registered.identifies_cause


def test_check_prints_the_summary_and_contacts_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["check"]) == cli.EXIT_OK
    printed = capsys.readouterr().out
    assert "offline descriptor validation only" in printed
    assert "availability" in printed


def test_surfaces_prints_one_row_per_registered_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["surfaces"]) == cli.EXIT_OK
    assert len(capsys.readouterr().out.strip().splitlines()) == len(DESCRIPTOR.surfaces)


def test_fields_without_a_path_is_refused() -> None:
    assert cli.main(["fields"]) == cli.EXIT_FAILED


def test_a_command_without_its_run_directory_is_refused() -> None:
    assert cli.main(["record"]) == cli.EXIT_FAILED


def test_verify_without_a_directory_is_refused() -> None:
    assert cli.main(["verify"]) == cli.EXIT_FAILED


def test_record_writes_its_inputs_and_its_record(tmp_path: Path) -> None:
    write_cluster(tmp_path)
    (tmp_path / "lifecycle.json").write_text(
        dumps(lifecycle_document()), encoding="utf-8", newline="\n"
    )
    (tmp_path / "readiness.json").write_text(
        dumps(readiness_document()), encoding="utf-8", newline="\n"
    )
    (tmp_path / "probes.jsonl").write_text(
        probes_text(), encoding="utf-8", newline="\n"
    )
    (tmp_path / "diagnostics.json").write_text(
        dumps(diagnostics_document()), encoding="utf-8", newline="\n"
    )
    (tmp_path / "telemetry.json").write_text(
        dumps(telemetry_document()), encoding="utf-8", newline="\n"
    )
    assert cli.main(["record", "--run-dir", str(tmp_path)]) == cli.EXIT_OK
    written = tmp_path / "record"
    for name in cli.RECORD_FILES.values():
        assert (written / name).is_file(), name


def test_verify_refuses_a_record_its_inputs_do_not_produce(tmp_path: Path) -> None:
    for name, text in (
        ("environment.v1alpha1.json", None),
        ("lifecycle.v1alpha1.json", dumps(lifecycle_document())),
        ("readiness.v1alpha1.json", dumps(readiness_document())),
        ("probes.v1alpha1.jsonl", probes_text()),
        ("diagnostics.v1alpha1.json", dumps(diagnostics_document())),
        ("telemetry.v1alpha1.json", dumps(telemetry_document())),
    ):
        if text is None:
            text = dumps(extract_environment(write_cluster(tmp_path), DESCRIPTOR))
        (tmp_path / name).write_text(text, encoding="utf-8", newline="\n")
    (tmp_path / "unready-model-record.v1alpha1.json").write_text(
        dumps({"not": "the record"}), encoding="utf-8", newline="\n"
    )
    assert cli.main(["verify", "--dir", str(tmp_path)]) == cli.EXIT_FAILED


# --------------------------------------------------------------------------
# The documents beside the data
# --------------------------------------------------------------------------


def test_the_procedure_document_states_every_limitation() -> None:
    text = PROCEDURE.read_text(encoding="utf-8")
    for limitation in DESCRIPTOR.limitations:
        assert limitation in text, limitation[:60]


def test_the_procedure_names_the_decision_it_extends() -> None:
    text = PROCEDURE.read_text(encoding="utf-8")
    assert "ADR-0010" in text or "ADR 0010" in text
    assert DECISION.is_file()
    assert EXTENDS.is_file()


def test_the_procedure_says_why_the_forwards_address_pods() -> None:
    text = PROCEDURE.read_text(encoding="utf-8")
    assert "no ready endpoint" in text


def test_the_report_template_is_a_template_and_holds_no_result() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "This is a template" in text
    assert "<STORY-ID>" in text
    # A template that carried a figure would be a result nobody ran.
    assert not re.search(r"\b\d{4,} ms\b", text)


def test_the_experiment_says_which_boundary_it_is_not_allowed_to_lean_on() -> None:
    """The mock adapter's MODEL_NOT_READY scenario is the thing this replaces."""
    assert "mock-and-real-boundary" in DOCUMENT["extendsRef"]
    assert "MockScenario.MODEL_NOT_READY" in DOCUMENT["distinctProofQuestion"]


def test_the_descriptor_says_it_is_neither_of_the_two_experiments_it_resembles() -> (
    None
):
    question = DOCUMENT["distinctProofQuestion"]
    assert "V1-S3-008" in question
    assert "V1-S4-006" in question
