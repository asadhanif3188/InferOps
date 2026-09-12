"""Deterministic checks over the Helm upgrade and rollback experiment.

Every check here reads files from this repository, or drives the experiment's
own readers against documents this module writes. No network, no cluster, no
container engine, no real clock, no randomness, and nothing is installed,
upgraded, broken, or rolled back. The shell script is read as text.

Three questions are asked, and they are different questions.

**Does the descriptor agree with the records that already decide it?** The
cluster, the release, the request, and eight budgets belong to the Kubernetes
real-inference certification; the injected byte count belongs to the selected
model's source record; the values path the fault takes has to be one the chart's
schema accepts and the chart's own validation refuses at zero. A descriptor that
disagreed with any of those would install something the certified workflow does
not describe, or inject a fault Helm would refuse before anything reached a
cluster -- and a run that never installed its own fault would report a detection
it did not make.

**Can a run be made to look successful on weaker evidence than it claims?** This
is most of the module. A rollback Helm recorded, a configuration that never went
back, a failure read off the wrong workload, a deadline reached sooner than a
healthy rollout is allowed, a pod that was never a replica, a candidate that
never scheduled, a recovery clock that runs backwards, and a mock answering after
the rollback are each provoked and each has to stop the run.

**Is the operating script written the way this project requires?** It validates
before it installs, asserts the target cluster, bounds every wait, forwards only
to loopback, injects only the two values paths the descriptor names, and removes
neither the prerequisites, the claim, nor the cluster.

What this module establishes is that the workflow is written and asserted the way
the descriptor says. It establishes nothing about what happens when it is run:
no release has been installed, no candidate has failed, and no rollback has been
performed. That is the real-runtime lane's question, and it has not been asked.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from inferops.adapters.llama_cpp import LLAMA_SERVER_RUNTIME_NAME
from inferops.api.surface import (
    CAPABILITY_TOKEN_USAGE,
    CORRELATION_ID_HEADER,
    EXTENSION_ADAPTER_KIND,
    EXTENSION_MEMBER,
    EXTENSION_MODEL_REF,
    REQUEST_ID_HEADER,
)
from tools.helm_upgrade_rollback import core
from tools.helm_upgrade_rollback.core import (
    EvidenceUnwritable,
    ExperimentError,
    ExperimentFailed,
    ExperimentInconclusive,
    ExperimentRefused,
    evaluate,
    load_experiment,
    merge_cleanup,
    result_document,
)
from tools.kubernetes_certification.core import ApiResponse, load_certification
from tools.model_acquisition import load_manifest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR_PATH = (
    REPO_ROOT / "deploy" / "serving" / "experiments" / "helm-upgrade-rollback.v1.json"
)
CERTIFICATION_PATH = (
    REPO_ROOT / "deploy" / "serving" / "certification" / "k8s-real-inference.v1.json"
)
SCRIPT_PATH = REPO_ROOT / "scripts" / "environment" / "helm-upgrade-rollback.sh"
LIB_PATH = REPO_ROOT / "scripts" / "environment" / "lib.sh"
CHART_VALUES_PATH = REPO_ROOT / "charts" / "inferops-llm" / "values.yaml"
CHART_SCHEMA_PATH = REPO_ROOT / "charts" / "inferops-llm" / "values.schema.json"
VALIDATE_PATH = REPO_ROOT / "charts" / "inferops-llm" / "templates" / "_validate.tpl"
HELPERS_PATH = REPO_ROOT / "charts" / "inferops-llm" / "templates" / "_helpers.tpl"
PROCEDURE_PATH = REPO_ROOT / "docs" / "environment" / "helm-upgrade-rollback.md"

EXPERIMENT = load_experiment()
CERTIFICATION = load_certification()

# The two entries of the experiment's provider list. V1-S3-011-PR2 ported the
# operating script off the kind-pinned target, so a run's facts now name
# whichever provider was verified, and both entries have to hold up as fixtures.
#
# `KIND_TARGET` carries an InferOps-owned node-image pin; `DOCKER_DESKTOP_TARGET`
# carries none, because Docker Desktop chooses its own node image and InferOps
# does not select it. The default fixtures below are built from the kind entry so
# that the pin assertions have something to assert against; the docker-desktop
# entry is exercised where the difference is the point.
(KIND_TARGET,) = [entry for entry in EXPERIMENT.clusters if entry.provider_id == "kind"]
(DOCKER_DESKTOP_TARGET,) = [
    entry for entry in EXPERIMENT.clusters if entry.provider_id == "docker-desktop"
]
MANIFEST = load_manifest()
SCRIPT_TEXT = SCRIPT_PATH.read_text(encoding="utf-8")
LIB_TEXT = LIB_PATH.read_text(encoding="utf-8")

BASE_URL = "http://127.0.0.1:18091"


def descriptor_document() -> dict[str, Any]:
    return json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))


def mutated(**sections: Mapping[str, Any]) -> dict[str, Any]:
    """The committed descriptor with one member of one section replaced."""
    document = descriptor_document()
    for name, members in sections.items():
        document[name] = {**document[name], **members}
    return document


def refused(document: Mapping[str, Any], tmp_path: Path) -> str:
    """Load a mutated descriptor and return the refusal it produced."""
    path = tmp_path / "descriptor.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ExperimentError) as raised:
        load_experiment(path, baseline=CERTIFICATION)
    return str(raised.value)


def lib_constant(name: str) -> str:
    """One constant from lib.sh, with the one constant it interpolates resolved.

    `INFEROPS_KUBE_CONTEXT` is written as `kind-${INFEROPS_CLUSTER_NAME}`,
    because kind derives the context name from the cluster name. Comparing the
    literal would compare a template against a value and always fail, and
    hard-coding the resolved form here would put a third copy of the cluster name
    in the repository.
    """
    match = re.search(
        rf'^readonly {re.escape(name)}="([^"]*)"', LIB_TEXT, flags=re.MULTILINE
    )
    assert match is not None, f"lib.sh does not define {name}"
    value = match.group(1)
    for referenced in re.findall(r"\$\{(\w+)\}", value):
        value = value.replace(f"${{{referenced}}}", lib_constant(referenced))
    return value


def logical_lines(text: str) -> list[str]:
    """Every command in a script as one line, with comments dropped.

    A `kubectl rollout status` and the `--timeout` that bounds it are routinely
    written across two lines, and a rule that read them separately would see an
    unbounded wait every time. Comments are dropped because the prose in these
    files quotes the very commands it explains.
    """
    lines: list[str] = []
    pending: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not pending and (not stripped or stripped.startswith("#")):
            continue
        pending.append(stripped.removesuffix("\\").strip())
        if stripped.endswith("\\"):
            continue
        lines.append(" ".join(pending))
        pending = []
    if pending:
        lines.append(" ".join(pending))
    return lines


SCRIPT_LINES = logical_lines(SCRIPT_TEXT)


# --------------------------------------------------------------------------
# The descriptor against the records that already decide it
# --------------------------------------------------------------------------


def test_the_descriptor_loads_and_identifies_itself() -> None:
    assert EXPERIMENT.experiment_id == "inferops-helm-upgrade-rollback"
    assert EXPERIMENT.certification_ceiling == "C2"
    assert EXPERIMENT.evidence_label == "local real Kubernetes"
    assert EXPERIMENT.lane == "real-runtime"
    assert EXPERIMENT.declared_stages == core.DECLARED_STAGES


def test_the_experiment_and_the_certification_describe_one_release() -> None:
    """One chart, one namespace, one release, reached through one forward.

    Equality rather than a field-by-field comparison, because the failure this
    prevents is the quiet one: an experiment that waited on a Deployment, or
    forwarded to a Service, the certified workflow does not know about, and then
    reported a rollback of "the release".
    """
    assert EXPERIMENT.clusters == CERTIFICATION.clusters
    assert EXPERIMENT.release == CERTIFICATION.release
    assert EXPERIMENT.request_host == CERTIFICATION.request_host
    assert EXPERIMENT.request_path == CERTIFICATION.request_path
    assert EXPERIMENT.models_path == CERTIFICATION.models_path
    assert EXPERIMENT.readiness_path == CERTIFICATION.readiness_path
    assert EXPERIMENT.request_timeout_ms == CERTIFICATION.request_timeout_ms


@pytest.mark.parametrize(
    "member",
    (
        "install_ms",
        "runtime_startup_ms",
        "runtime_rollout_ms",
        "api_startup_ms",
        "api_rollout_ms",
        "release_test_ms",
        "forward_ms",
        "uninstall_ms",
    ),
)
def test_a_shared_budget_is_the_certifications(member: str) -> None:
    assert getattr(EXPERIMENT.budgets, member) == getattr(CERTIFICATION.budgets, member)


def test_the_descriptor_names_the_cluster_the_scripts_operate() -> None:
    assert KIND_TARGET.name == lib_constant("INFEROPS_CLUSTER_NAME")
    assert KIND_TARGET.context == lib_constant("INFEROPS_KUBE_CONTEXT")
    assert KIND_TARGET.node_image_digest == lib_constant("INFEROPS_NODE_IMAGE_DIGEST")
    assert EXPERIMENT.release.name == lib_constant("INFEROPS_RELEASE_NAME")
    assert EXPERIMENT.release.namespace == lib_constant("INFEROPS_RELEASE_NAMESPACE")


def test_the_controlled_change_reaches_the_pod_template() -> None:
    """`telemetry.serviceVersion` is in the chart's derived environment.

    That is the whole reason it is the change this experiment makes. The
    ConfigMap's contents are hashed into every pod template's annotation, so an
    upgrade that sets it produces a rollout; a value outside that block would
    produce a revision Helm records and Kubernetes never acts on, and rolling
    that back would prove nothing about whether the workload followed.
    """
    helpers = HELPERS_PATH.read_text(encoding="utf-8")
    derived = helpers[helpers.index('define "inferops-llm.derivedEnv"') :]
    derived = derived[: derived.index("{{- end -}}")]
    assert f"{EXPERIMENT.candidate.config_map_key}:" in derived
    assert ".Values.telemetry.serviceVersion" in derived
    assert (
        'inferops.io/configuration-checksum: {{ include "inferops-llm.derivedEnv"'
        in (
            (
                REPO_ROOT / "charts/inferops-llm/templates/runtime-deployment.yaml"
            ).read_text(encoding="utf-8")
        )
    )


def test_the_injected_fault_is_not_the_pinned_byte_count() -> None:
    assert EXPERIMENT.fault.injected_size_bytes != MANIFEST.expected_size_bytes


def test_the_injected_fault_is_a_value_the_chart_accepts() -> None:
    """The fault has to fail in the cluster, not in Helm's own validation.

    A value the schema rejected, or one `_validate.tpl` refuses, would stop
    `helm upgrade` before anything reached the cluster -- and a run that never
    installed its candidate would report a detection it never made.
    """
    schema = json.loads(CHART_SCHEMA_PATH.read_text(encoding="utf-8"))
    size = schema["properties"]["model"]["properties"]["artifact"]["properties"][
        "sizeBytes"
    ]
    assert size["type"] == "integer"
    assert EXPERIMENT.fault.injected_size_bytes >= size["minimum"]
    # The chart refuses a zero under the real profile, so the descriptor's own
    # floor has to be above it rather than at it.
    assert "model.artifact.sizeBytes is required under the real profile" in (
        VALIDATE_PATH.read_text(encoding="utf-8")
    )
    assert EXPERIMENT.fault.injected_size_bytes > 0


def test_the_fault_is_compared_by_the_container_the_descriptor_names() -> None:
    """The chart's verification script compares the byte count before the hash.

    That ordering is why this fault is the one injected: it fails at the first
    check, before a 1.83 GB read, so the failure is fast and its reason is
    printed by the container that made it.
    """
    helpers = HELPERS_PATH.read_text(encoding="utf-8")
    script = helpers[helpers.index('define "inferops-llm.model.verifyScript"') :]
    script = script[: script.index('define "inferops-llm.model.verifyInitContainer"')]
    assert "does not match the pinned byte count" in script
    assert script.index("sizeBytes") < script.index("sha256sum")
    assert f"- name: {EXPERIMENT.fault.fails_in_container}" in helpers


def test_the_fault_reaches_only_the_serving_runtime() -> None:
    """The claim that the platform API is not rolled by the fault, checked.

    It is what makes the impact measurement mean anything: if the fault rolled
    the API too, every readiness probe during the failure window would be asking
    a tier that was itself being replaced, and "no caller saw a failure" would be
    a statement about two rollouts rather than one.

    The chart is the proof. `model.artifact.sizeBytes` appears in exactly one
    template outside the validation helper — the verification script — which only
    the serving runtime's Deployment includes; and it is absent from
    `inferops-llm.derivedEnv`, so the ConfigMap every pod template is checksummed
    against does not change either.
    """
    helpers = HELPERS_PATH.read_text(encoding="utf-8")
    templates = sorted(
        path
        for path in (REPO_ROOT / "charts" / "inferops-llm" / "templates").rglob("*")
        if path.is_file() and path.name != "_validate.tpl"
    )
    naming = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in templates
        if "model.artifact.sizeBytes" in path.read_text(encoding="utf-8")
    ]
    assert naming == ["charts/inferops-llm/templates/_helpers.tpl"], naming

    derived = helpers[helpers.index('define "inferops-llm.derivedEnv"') :]
    derived = derived[: derived.index("{{- end -}}")]
    assert "sizeBytes" not in derived

    verify = helpers[helpers.index('define "inferops-llm.model.verifyInitContainer"') :]
    verify = verify[: verify.index("{{- end -}}")]
    runtime = (
        REPO_ROOT / "charts/inferops-llm/templates/runtime-deployment.yaml"
    ).read_text(encoding="utf-8")
    api = (REPO_ROOT / "charts/inferops-llm/templates/api-deployment.yaml").read_text(
        encoding="utf-8"
    )
    assert "inferops-llm.model.verifyInitContainer" in runtime
    assert "inferops-llm.model.verifyInitContainer" not in api
    assert "initContainers" not in api


def test_the_fault_touches_no_image_and_no_cluster_scoped_object() -> None:
    fault = EXPERIMENT.fault
    assert fault.scope == "release"
    assert fault.reversible_by == "helm-rollback"
    assert fault.pulls_no_image
    assert fault.changes_no_image_reference
    assert fault.changes_no_cluster_scoped_object
    assert fault.changes_no_persistent_volume_claim
    assert fault.creates_no_object_outside_release


def test_the_probe_asks_the_path_the_chart_publishes() -> None:
    values = CHART_VALUES_PATH.read_text(encoding="utf-8")
    assert f"readinessPath: {EXPERIMENT.impact.probe_path}" in values
    assert EXPERIMENT.impact.probe_path == CERTIFICATION.readiness_path


def test_the_evidence_directory_is_ignored_by_version_control() -> None:
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert f"/{EXPERIMENT.evidence_directory.as_posix()}/" in ignored


def test_the_descriptor_points_at_documents_that_exist() -> None:
    for reference in (
        EXPERIMENT.chart_ref,
        EXPERIMENT.certification_ref,
        EXPERIMENT.procedure_ref,
        EXPERIMENT.baseline_certification_ref,
    ):
        assert (REPO_ROOT / reference).exists(), reference


# --------------------------------------------------------------------------
# What the descriptor may not say
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "section,member,value,expected",
    (
        ("candidate", "valuesPath", "api.replicaCount", "leaves the pod template"),
        ("candidate", "candidateValue", "; rm -rf /", "plain identifier"),
        ("candidate", "requireReleaseTest", False, "may not waive"),
        ("candidate", "requireRealInference", False, "may not waive"),
        ("faultInjection", "valuesPath", "runtime.image.digest", "only fault"),
        ("faultInjection", "mechanism", "image-digest-unresolvable", "only fault"),
        ("faultInjection", "failsInWorkload", "platform-api", "declared to fail"),
        ("faultInjection", "pullsNoImage", False, "keeps it reversible"),
        ("faultInjection", "scope", "cluster", "scoped to the release"),
        ("faultInjection", "reversibleBy", "second-upgrade", "scoped to the release"),
        ("detection", "requireDecisiveSignal", False, "did not read off"),
        ("detection", "deadlineSignal", "timeout", "deadline signal must be"),
        ("rollback", "target", "revision-one", "last known-good revision"),
        ("rollback", "requireConfigurationRestored", False, "Helm's bookkeeping"),
        ("rollback", "requireRealInference", False, "Helm's bookkeeping"),
        ("impact", "probePath", "/metrics", "own readiness path"),
        ("impact", "probeTimeoutMs", 60000, "outlive its interval"),
        ("impact", "requireProbeRecord", False, "record what it asked"),
        ("cleanup", "removesPrerequisites", True, "neither the prerequisites"),
        ("cleanup", "removesModelCacheClaim", True, "neither the prerequisites"),
        ("cleanup", "uninstallsRelease", False, "must remove the release"),
        ("evidence", "retainGeneratedText", True, "evidence location is unsafe"),
        ("evidence", "directory", ".cache", "evidence location is unsafe"),
        ("evidence", "resultFile", "../escape.json", "evidence location is unsafe"),
        ("readiness", "failureDetectionBudgetMs", 60000, "slow start"),
        ("readiness", "upgradeBudgetMs", 60000, "shorter than the runtime rollout"),
        ("readiness", "rollbackBudgetMs", 60000, "shorter than the rollout"),
        ("readiness", "recoveryBudgetMs", 900001, "cannot contain the rollback"),
        ("assertions", "requireUsageCounts", False, "cannot be waived"),
        ("assertions", "requirePinnedNodeImage", False, "cannot be waived"),
        ("assertions", "requireRecoveryRecorded", False, "cannot be waived"),
        ("prerequisites", "requiresHealthyBaseline", False, "cannot be waived"),
    ),
)
def test_a_descriptor_that_weakens_the_experiment_is_refused(
    section: str, member: str, value: Any, expected: str, tmp_path: Path
) -> None:
    message = refused(mutated(**{section: {member: value}}), tmp_path)
    assert expected in message, message


def test_a_fault_injecting_the_real_byte_count_is_refused(tmp_path: Path) -> None:
    """A "fault" that is the pin produces a healthy candidate and no detection."""
    document = mutated(
        faultInjection={"injectedSizeBytes": MANIFEST.expected_size_bytes}
    )
    assert "nothing would be detected" in refused(document, tmp_path)


def test_a_fault_the_chart_refuses_before_installing_is_refused(
    tmp_path: Path,
) -> None:
    """Zero is refused here, because the chart would refuse it there.

    This is the module's own floor, not the chart's: nothing is rendered in this
    suite. The floor exists so that the descriptor cannot name the one byte count
    `_validate.tpl` rejects outright — a fault Helm refuses is a run that never
    installed its own fault, and it would then report a detection it did not
    make. The test above reads the validation template to establish that the
    chart really does refuse it.
    """
    document = mutated(faultInjection={"injectedSizeBytes": 0})
    assert "not an integer of at least 1" in refused(document, tmp_path)


def test_a_descriptor_disagreeing_with_the_certification_is_refused(
    tmp_path: Path,
) -> None:
    document = descriptor_document()
    document["release"] = {**document["release"], "namespace": "inferops-other"}
    assert "different releases" in refused(document, tmp_path)


def test_a_descriptor_writing_over_the_certifications_record_is_refused(
    tmp_path: Path,
) -> None:
    document = mutated(evidence={"resultFile": Path(CERTIFICATION.result_file).name})
    assert "write over the certification" in refused(document, tmp_path)


def test_a_descriptor_with_an_unknown_member_is_refused(tmp_path: Path) -> None:
    document = descriptor_document()
    document["detection"] = {**document["detection"], "requireDecisiveSignalX": False}
    assert "missing or unsupported" in refused(document, tmp_path)


def test_a_descriptor_that_lists_too_few_limitations_is_refused(
    tmp_path: Path,
) -> None:
    document = descriptor_document()
    document["limitations"] = document["limitations"][:2]
    assert "fewer than four limitations" in refused(document, tmp_path)


def test_a_descriptor_that_renames_a_stage_is_refused(tmp_path: Path) -> None:
    document = descriptor_document()
    document["stages"] = ["baseline", "candidate", "rollback", "cleanup"]
    assert "different experiments" in refused(document, tmp_path)


# --------------------------------------------------------------------------
# The collected facts, held to the descriptor rather than trusted
# --------------------------------------------------------------------------


def stage_document(stage: str, **overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "baseline": {
            "revision": "1",
            "status": "deployed",
            "outcome": "healthy",
            "serviceVersion": "",
            "artifactSizeBytes": MANIFEST.expected_size_bytes,
            "elapsedMs": 310_000,
            "readyMs": 240_000,
            "releaseTestPassed": True,
            "runtimePod": "inferops-runtime-aaa",
            "apiPod": "inferops-api-aaa",
        },
        "candidate": {
            "revision": "2",
            "status": "deployed",
            "outcome": "healthy",
            "serviceVersion": EXPERIMENT.candidate.candidate_value,
            "artifactSizeBytes": MANIFEST.expected_size_bytes,
            "elapsedMs": 300_000,
            "readyMs": 230_000,
            "releaseTestPassed": True,
            "runtimePod": "inferops-runtime-bbb",
            "apiPod": "inferops-api-bbb",
        },
        "unhealthy-candidate": {
            "revision": "3",
            "status": "failed",
            "outcome": "failed",
            "serviceVersion": EXPERIMENT.candidate.candidate_value,
            "artifactSizeBytes": EXPERIMENT.fault.injected_size_bytes,
            "elapsedMs": 42_000,
            "readyMs": 0,
            "releaseTestPassed": False,
            "runtimePod": "inferops-runtime-bbb",
            "apiPod": "inferops-api-bbb",
        },
        "rollback": {
            "revision": "4",
            "status": "deployed",
            "outcome": "healthy",
            "serviceVersion": EXPERIMENT.candidate.candidate_value,
            "artifactSizeBytes": MANIFEST.expected_size_bytes,
            "elapsedMs": 18_000,
            "readyMs": 4_000,
            "releaseTestPassed": True,
            "runtimePod": "inferops-runtime-bbb",
            "apiPod": "inferops-api-bbb",
        },
    }[stage]
    return {"stage": stage, **defaults, **overrides}


def lifecycle_document(
    *, stages: list[dict[str, Any]] | None = None, **sections: Mapping[str, Any]
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "cluster": {
            "provider": KIND_TARGET.provider_id,
            "name": KIND_TARGET.name,
            "context": KIND_TARGET.context,
            "serverVersion": "v1.34.8",
            "nodeImageDigest": KIND_TARGET.node_image_digest,
        },
        "tooling": {"helm": "v3.16.3+g1234567", "kubectl": "v1.34.1"},
        "release": {
            "name": EXPERIMENT.release.name,
            "namespace": EXPERIMENT.release.namespace,
            "chart": "inferops-llm-0.1.0",
            "profile": EXPERIMENT.release.profile,
        },
        "configuration": {
            "modelIdentifier": "qwen3-1-7b-q8-0",
            "modelRevision": MANIFEST.revision,
            "deploymentEnvironment": "dev",
        },
        "stages": stages
        if stages is not None
        else [
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback"),
        ],
        "detection": {
            "signal": "init-container-nonzero-exit",
            "workload": EXPERIMENT.fault.fails_in_workload,
            "container": EXPERIMENT.fault.fails_in_container,
            "exitCode": 1,
            "reason": "Error",
            "detectedAfterMs": 21_000,
            "candidatePod": "inferops-runtime-ccc",
            "servingPod": "inferops-runtime-bbb",
        },
        "recovery": {
            "injectedAtMs": 0,
            "detectedAtMs": 21_000,
            "rollbackStartedAtMs": 42_000,
            "rollbackFinishedAtMs": 54_000,
            "verifiedAtMs": 61_000,
        },
    }
    for name, members in sections.items():
        document[name] = {**document[name], **members}
    return document


def impact_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "probePath": EXPERIMENT.impact.probe_path,
        "window": {"startedMs": 0, "endedMs": 40_000},
        "probes": [
            {"atMs": at, "status": 200, "ok": True}
            for at in (0, 5_000, 10_000, 15_000, 20_000, 25_000)
        ],
    }
    document.update(overrides)
    return document


def cleanup_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "uninstallMs": 24_000,
        "releaseObjectsRemaining": 0,
        "helmReleasePresent": False,
        "namespacePresent": True,
        "claimsBefore": 1,
        "claimsAfter": 1,
    }
    document.update(overrides)
    return document


def artifact_root(
    tmp_path: Path,
    *,
    lifecycle: Mapping[str, Any] | None = None,
    impact: Mapping[str, Any] | None = None,
    cleanup: Mapping[str, Any] | None = None,
) -> Path:
    """Write the collected documents where the descriptor says they must be."""
    written = {
        EXPERIMENT.lifecycle_file: lifecycle
        if lifecycle is not None
        else lifecycle_document(),
        EXPERIMENT.impact_file: impact if impact is not None else impact_document(),
        EXPERIMENT.cleanup_file: cleanup if cleanup is not None else cleanup_document(),
    }
    for member, document in written.items():
        target = tmp_path / member
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return tmp_path


# -- the answers a restored release gives ------------------------------------


def models_body(**overrides: Any) -> dict[str, Any]:
    extension: dict[str, Any] = {
        EXTENSION_ADAPTER_KIND: "real",
        "runtime": {
            "name": LLAMA_SERVER_RUNTIME_NAME,
            "version": "b4123",
            "modelRevision": MANIFEST.revision,
        },
        "capabilities": {CAPABILITY_TOKEN_USAGE: True},
    }
    for member, value in overrides.items():
        if member in extension and isinstance(extension[member], dict):
            extension[member] = {**extension[member], **value}
        else:
            extension[member] = value
    return {
        "object": "list",
        "data": [{"id": "qwen3-1-7b-q8-0"}],
        EXTENSION_MEMBER: extension,
    }


def completion_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "choices": [{"message": {"role": "assistant", "content": "The last one."}}],
        "usage": {
            "prompt_tokens": 19,
            "completion_tokens": 12,
            "total_tokens": 31,
        },
        EXTENSION_MEMBER: {
            EXTENSION_ADAPTER_KIND: "real",
            EXTENSION_MODEL_REF: "qwen3-1-7b-q8-0",
        },
    }
    body.update(overrides)
    return body


def seams(
    *,
    models: Mapping[str, Any] | None = None,
    completion: Mapping[str, Any] | None = None,
    ready_status: int = 200,
    completion_status: int = 200,
) -> tuple[Any, Any]:
    """A get and a post that answer the way a restored real release would."""

    def get(url: str, timeout_seconds: float) -> ApiResponse:
        if url.endswith(EXPERIMENT.readiness_path):
            return ApiResponse(ready_status, {"status": "ready"}, {})
        return ApiResponse(200, models if models is not None else models_body(), {})

    def post(
        url: str,
        body: Mapping[str, object],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> ApiResponse:
        return ApiResponse(
            completion_status,
            completion if completion is not None else completion_body(),
            {
                REQUEST_ID_HEADER: headers[REQUEST_ID_HEADER],
                CORRELATION_ID_HEADER: headers[CORRELATION_ID_HEADER],
            },
        )

    return get, post


def run(tmp_path: Path, **kwargs: Any) -> Any:
    """Evaluate against documents this module wrote and answers it controls."""
    seam_names = {"models", "completion", "ready_status", "completion_status"}
    seam_kwargs = {k: v for k, v in kwargs.items() if k in seam_names}
    root_kwargs = {k: v for k, v in kwargs.items() if k not in seam_names}
    root = artifact_root(tmp_path, **root_kwargs)
    get, post = seams(**seam_kwargs)
    return evaluate(
        EXPERIMENT,
        confirmed=True,
        base_url=BASE_URL,
        repo_root=root,
        baseline=CERTIFICATION,
        get=get,
        post=post,
        clock=iter([0.0, 4.5]).__next__,
    )


def record_of(result: Any) -> Any:
    """The record as plain JSON, which is how anything else would read it.

    Round-tripping through `json` rather than reading the mapping directly is
    two checks in one: it establishes that the document really is serialisable —
    the operating script writes it with `json.dumps` and a value that was not
    would fail there instead of here — and it lets a test read a nested member
    without annotating every level of a `dict[str, object]`.
    """
    return json.loads(json.dumps(result_document(result)))


def stopped(tmp_path: Path, **kwargs: Any) -> str:
    with pytest.raises(ExperimentError) as raised:
        run(tmp_path, **kwargs)
    return str(raised.value)


# --------------------------------------------------------------------------
# A run that behaved
# --------------------------------------------------------------------------


def test_a_complete_run_is_accepted(tmp_path: Path) -> None:
    result = run(tmp_path)
    assert result.facts.stage("rollback").revision == 4
    assert result.facts.recovery.recovery_ms == 40_000
    assert result.facts.recovery.rollback_ms == 12_000
    assert result.identity.adapter_kind == "real"
    assert result.completion.total_tokens == 31
    assert result.impact.answered == 6
    assert result.impact.refused == 0


def test_the_record_carries_no_prompt_and_no_completion(tmp_path: Path) -> None:
    """The one thing a record of a real model's answer must never keep."""
    document = record_of(run(tmp_path))
    serialised = json.dumps(document)
    assert EXPERIMENT.prompt not in serialised
    assert "The last one." not in serialised
    assert document["restoredCompletion"]["generatedTextRetained"] is False
    assert document["restoredCompletion"]["completionCharacters"] == 13


def test_the_record_names_the_versions_and_the_recovery(tmp_path: Path) -> None:
    """ "Version and recovery timing are recorded" is a claim about the record."""
    document = record_of(run(tmp_path))
    stages = {stage["stage"]: stage["revision"] for stage in document["stages"]}
    assert stages == {
        "baseline": 1,
        "candidate": 2,
        "unhealthy-candidate": 3,
        "rollback": 4,
    }
    assert document["recovery"]["restoredRevision"] == 4
    assert document["recovery"]["restoredFromRevision"] == 2
    assert document["recovery"]["recoveryMs"] == 40_000
    assert document["recovery"]["detectionMs"] == 21_000
    assert document["provenance"]["modelRevision"] == MANIFEST.revision
    assert document["cleanup"] is None
    assert document["limitations"] == list(EXPERIMENT.limitations)


def test_the_record_says_whether_the_runtime_had_to_reload(tmp_path: Path) -> None:
    """A rollback to a revision whose pod never went away reloads no model.

    It is recorded rather than assumed, because it is the difference between a
    recovery measured in seconds and one measured in minutes, and which of the
    two happened depends on whether the surging rollout ever displaced the pod
    that was serving.
    """
    assert record_of(run(tmp_path))["recovery"]["runtimeReloaded"] is False
    reloaded = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback", runtimePod="inferops-runtime-ddd"),
        ]
    )
    document = record_of(run(tmp_path, lifecycle=reloaded))
    assert document["recovery"]["runtimeReloaded"] is True


def test_a_revision_helm_serialised_as_a_string_is_read(tmp_path: Path) -> None:
    """`helm list -o json` serialises a revision as a string, and always has."""
    assert run(tmp_path).facts.stage("baseline").revision == 1


# --------------------------------------------------------------------------
# Every way the run could be made to look better than it was
# --------------------------------------------------------------------------


def test_an_unconfirmed_run_is_refused(tmp_path: Path) -> None:
    get, post = seams()
    with pytest.raises(ExperimentRefused) as raised:
        evaluate(
            EXPERIMENT,
            confirmed=False,
            base_url=BASE_URL,
            repo_root=artifact_root(tmp_path),
            baseline=CERTIFICATION,
            get=get,
            post=post,
        )
    assert "--confirm-real-kubernetes" in str(raised.value)


@pytest.mark.parametrize(
    "base_url",
    (
        "https://127.0.0.1:18091",
        "http://inferops.example.com:18091",
        "http://127.0.0.1",
        "http://127.0.0.1:18091/v1",
    ),
)
def test_a_forward_that_is_not_loopback_is_refused(
    base_url: str, tmp_path: Path
) -> None:
    get, post = seams()
    with pytest.raises(ExperimentRefused):
        evaluate(
            EXPERIMENT,
            confirmed=True,
            base_url=base_url,
            repo_root=artifact_root(tmp_path),
            baseline=CERTIFICATION,
            get=get,
            post=post,
        )


def test_another_cluster_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(cluster={"name": "somebody-elses"})
    assert "not this project's" in stopped(tmp_path, lifecycle=facts)


def test_an_unpinned_node_image_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(cluster={"nodeImageDigest": "sha256:" + "0" * 64})
    assert "pinned node image" in stopped(tmp_path, lifecycle=facts)


def test_a_provider_the_descriptor_does_not_describe_stops_the_run(
    tmp_path: Path,
) -> None:
    """V1-S3-011-PR2. The kind-only refusal is gone; this is what replaced it.

    Widening the workflow from one provider to the ones the descriptor describes
    is not the same as widening it to any provider at all. A target nothing
    describes is still a refusal.
    """
    facts = lifecycle_document(cluster={"provider": "some-cloud"})
    assert "does not describe" in stopped(tmp_path, lifecycle=facts)


def test_the_reference_provider_is_accepted_with_its_own_node_image(
    tmp_path: Path,
) -> None:
    """A provider-owned node image is recorded, not enforced as an InferOps pin.

    Docker Desktop chooses its own node image and InferOps neither selects nor
    pins it, so its descriptor entry says `pinned: false`. A digest that differs
    from the kind entry's pin is therefore a fact about the operator's cluster
    rather than a mismatch, and refusing it would refuse the reference provider
    for running the image its vendor gave it.
    """
    assert DOCKER_DESKTOP_TARGET.node_image_pinned is False
    facts = lifecycle_document(
        cluster={
            "provider": DOCKER_DESKTOP_TARGET.provider_id,
            "name": DOCKER_DESKTOP_TARGET.name,
            "context": DOCKER_DESKTOP_TARGET.context,
            "nodeImageDigest": "sha256:" + "a" * 64,
        }
    )
    result = run(tmp_path, lifecycle=facts)
    assert result.facts.provider == DOCKER_DESKTOP_TARGET.provider_id
    assert result.facts.node_image_digest == "sha256:" + "a" * 64


def test_the_reference_provider_still_has_to_name_a_node_image(
    tmp_path: Path,
) -> None:
    """Unpinned is not unrecorded. A record names the cluster it ran on."""
    facts = lifecycle_document(
        cluster={
            "provider": DOCKER_DESKTOP_TARGET.provider_id,
            "name": DOCKER_DESKTOP_TARGET.name,
            "context": DOCKER_DESKTOP_TARGET.context,
            "nodeImageDigest": "",
        }
    )
    assert "do not name the node image" in stopped(tmp_path, lifecycle=facts)


def test_a_providers_cluster_identity_is_not_borrowed_from_another(
    tmp_path: Path,
) -> None:
    """Naming one provider and another provider's cluster is still a refusal."""
    facts = lifecycle_document(
        cluster={
            "provider": DOCKER_DESKTOP_TARGET.provider_id,
            "name": KIND_TARGET.name,
            "context": KIND_TARGET.context,
        }
    )
    assert "not this project's" in stopped(tmp_path, lifecycle=facts)


def test_an_unpinned_model_revision_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(configuration={"modelRevision": "0" * 40})
    assert "pinned model revision" in stopped(tmp_path, lifecycle=facts)


def test_a_baseline_that_was_never_healthy_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline", releaseTestPassed=False),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback"),
        ]
    )
    assert "known-good state" in stopped(tmp_path, lifecycle=facts)


def test_a_baseline_already_carrying_the_candidate_value_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document(
                "baseline", serviceVersion=EXPERIMENT.candidate.candidate_value
            ),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback"),
        ]
    )
    assert "would change nothing" in stopped(tmp_path, lifecycle=facts)


def test_a_candidate_the_cluster_never_applied_stops_the_run(tmp_path: Path) -> None:
    """A revision Helm recorded and Kubernetes never acted on is not an upgrade."""
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate", serviceVersion=""),
            stage_document("unhealthy-candidate"),
            stage_document("rollback"),
        ]
    )
    assert "did not reach the rendered configuration" in stopped(
        tmp_path, lifecycle=facts
    )


def test_a_candidate_served_by_the_same_pod_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate", runtimePod="inferops-runtime-aaa"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback"),
        ]
    )
    assert "reached the ConfigMap and not the workload" in stopped(
        tmp_path, lifecycle=facts
    )


def test_a_healthy_unhealthy_candidate_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate", outcome="healthy"),
            stage_document("rollback"),
        ]
    )
    assert "not a fault" in stopped(tmp_path, lifecycle=facts)


def test_an_unhealthy_candidate_without_the_injected_value_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document(
                "unhealthy-candidate", artifactSizeBytes=MANIFEST.expected_size_bytes
            ),
            stage_document("rollback"),
        ]
    )
    assert "declared injected byte count" in stopped(tmp_path, lifecycle=facts)


def test_a_deadline_detection_stops_the_run(tmp_path: Path) -> None:
    """A deadline says a rollout stopped progressing, not that it is unhealthy."""
    facts = lifecycle_document(
        detection={"signal": "progress-deadline-exceeded", "exitCode": 0}
    )
    assert "not decisive" in stopped(tmp_path, lifecycle=facts)


def test_a_decisive_signal_with_a_zero_exit_code_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(detection={"exitCode": 0})
    assert "container that succeeded" in stopped(tmp_path, lifecycle=facts)


def test_a_failure_read_off_another_workload_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(detection={"workload": "platform-api"})
    assert "rather than the" in stopped(tmp_path, lifecycle=facts)


def test_a_candidate_that_never_scheduled_is_inconclusive(tmp_path: Path) -> None:
    """A pod the host could not place never ran the fault this run injected."""
    facts = lifecycle_document(
        detection={"signal": "candidate-pod-unschedulable", "exitCode": 0}
    )
    with pytest.raises(ExperimentInconclusive) as raised:
        run(tmp_path, lifecycle=facts)
    assert "observed its own capacity" in str(raised.value)


def test_a_failing_pod_that_was_the_serving_pod_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(detection={"candidatePod": "inferops-runtime-bbb"})
    assert "not surging" in stopped(tmp_path, lifecycle=facts)


def test_a_detection_over_budget_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(
        detection={"detectedAfterMs": EXPERIMENT.budgets.failure_detection_ms + 1},
        recovery={
            "detectedAtMs": EXPERIMENT.budgets.failure_detection_ms + 1,
            "rollbackStartedAtMs": EXPERIMENT.budgets.failure_detection_ms + 2,
            "rollbackFinishedAtMs": EXPERIMENT.budgets.failure_detection_ms + 3,
            "verifiedAtMs": EXPERIMENT.budgets.failure_detection_ms + 4,
        },
    )
    assert "over the" in stopped(tmp_path, lifecycle=facts)


def test_a_rollback_that_left_the_fault_in_place_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document(
                "rollback", artifactSizeBytes=EXPERIMENT.fault.injected_size_bytes
            ),
        ]
    )
    assert "left the injected byte count" in stopped(tmp_path, lifecycle=facts)


def test_a_rollback_to_the_wrong_revision_stops_the_run(tmp_path: Path) -> None:
    """Rolling back past the controlled change is not the last known-good one."""
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback", serviceVersion=""),
        ]
    )
    assert "other than the last known-good" in stopped(tmp_path, lifecycle=facts)


def test_a_rollback_recorded_as_the_revision_it_restored_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback", revision="2"),
        ]
    )
    assert "do not increase" in stopped(tmp_path, lifecycle=facts)


def test_a_rollback_that_failed_its_release_test_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback", releaseTestPassed=False),
        ]
    )
    assert "did not pass the release's own test" in stopped(tmp_path, lifecycle=facts)


def test_a_recovery_clock_that_runs_backwards_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(recovery={"verifiedAtMs": 10_000})
    assert "does not run forwards" in stopped(tmp_path, lifecycle=facts)


def test_two_clocks_disagreeing_about_the_detection_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(recovery={"detectedAtMs": 22_000})
    assert "disagree about when" in stopped(tmp_path, lifecycle=facts)


def test_a_window_nobody_sampled_stops_the_run(tmp_path: Path) -> None:
    observations = impact_document(
        probes=[{"atMs": 0, "status": 200, "ok": True}],
        window={"startedMs": 0, "endedMs": 40_000},
    )
    assert "fewer than the" in stopped(tmp_path, impact=observations)


def test_a_window_that_closed_before_the_detection_stops_the_run(
    tmp_path: Path,
) -> None:
    observations = impact_document(
        window={"startedMs": 0, "endedMs": 10_000},
        probes=[{"atMs": at, "status": 200, "ok": True} for at in (0, 5_000, 10_000)],
    )
    assert "before the failure was detected" in stopped(tmp_path, impact=observations)


def test_a_probe_outside_its_own_window_stops_the_run(tmp_path: Path) -> None:
    observations = impact_document(
        probes=[
            {"atMs": at, "status": 200, "ok": True} for at in (0, 5_000, 10_000, 99_000)
        ]
    )
    assert "outside its own window" in stopped(tmp_path, impact=observations)


def test_a_refused_probe_is_recorded_rather_than_refusing_the_run(
    tmp_path: Path,
) -> None:
    """User impact is measured, not assumed. A caller that saw a failure is a
    result of the experiment rather than a failure of it."""
    observations = impact_document(
        probes=[
            {"atMs": 0, "status": 200, "ok": True},
            {"atMs": 5_000, "status": 503, "ok": False},
            {"atMs": 10_000, "status": 200, "ok": True},
        ]
    )
    result = run(tmp_path, impact=observations)
    assert result.impact.refused == 1
    assert result.impact.first_failure_at_ms == 5_000
    assert record_of(result)["impact"]["firstFailureAtMs"] == 5_000


def test_collected_stages_that_are_not_the_four_stop_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("rollback"),
        ]
    )
    assert "rather than" in stopped(tmp_path, lifecycle=facts)


def test_a_baseline_slower_than_a_healthy_rollout_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document(
                "baseline", readyMs=EXPERIMENT.budgets.runtime_rollout_ms + 1
            ),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback"),
        ]
    )
    assert "over the" in stopped(tmp_path, lifecycle=facts)


def test_a_controlled_upgrade_over_budget_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate", elapsedMs=EXPERIMENT.budgets.upgrade_ms + 1),
            stage_document("unhealthy-candidate"),
            stage_document("rollback"),
        ]
    )
    assert "over the" in stopped(tmp_path, lifecycle=facts)


def test_a_release_test_passing_against_a_failed_candidate_stops_the_run(
    tmp_path: Path,
) -> None:
    """Two observations of one candidate, and they cannot both be right."""
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate", releaseTestPassed=True),
            stage_document("rollback"),
        ]
    )
    assert "One of the two observations is wrong" in stopped(tmp_path, lifecycle=facts)


def test_an_unhealthy_stage_shorter_than_its_own_detection_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate", elapsedMs=1_000),
            stage_document("rollback"),
        ]
    )
    assert "the two clocks disagree" in stopped(tmp_path, lifecycle=facts)


def test_a_rollback_over_budget_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback", elapsedMs=EXPERIMENT.budgets.rollback_ms + 1),
        ]
    )
    assert "over the" in stopped(tmp_path, lifecycle=facts)


def test_a_rollback_to_a_third_byte_count_stops_the_run(tmp_path: Path) -> None:
    """Neither the injected value nor the pin is not a rollback of the fault."""
    facts = lifecycle_document(
        stages=[
            stage_document("baseline"),
            stage_document("candidate"),
            stage_document("unhealthy-candidate"),
            stage_document("rollback", artifactSizeBytes=12_345),
        ]
    )
    assert "neither the injected one nor the pinned one" in stopped(
        tmp_path, lifecycle=facts
    )


def test_a_run_that_recorded_no_recovery_stops(tmp_path: Path) -> None:
    """The one figure this experiment exists to produce may not be absent."""
    facts = lifecycle_document(
        detection={"detectedAfterMs": 0},
        recovery={
            "injectedAtMs": 0,
            "detectedAtMs": 0,
            "rollbackStartedAtMs": 0,
            "rollbackFinishedAtMs": 0,
            "verifiedAtMs": 0,
        },
    )
    assert "measured nothing it was run to measure" in stopped(
        tmp_path, lifecycle=facts
    )


def test_an_impact_window_that_does_not_run_forwards_stops_the_run(
    tmp_path: Path,
) -> None:
    observations = impact_document(
        window={"startedMs": 30_000, "endedMs": 10_000},
        probes=[
            {"atMs": at, "status": 200, "ok": True} for at in (30_000, 31_000, 32_000)
        ],
    )
    assert "does not run forwards" in stopped(tmp_path, impact=observations)


# -- what the restored release answered --------------------------------------


def test_a_release_that_is_not_ready_after_the_rollback_stops_the_run(
    tmp_path: Path,
) -> None:
    assert "reporting itself ready" in stopped(tmp_path, ready_status=503)


def test_a_mock_answering_after_the_rollback_stops_the_run(tmp_path: Path) -> None:
    body = models_body(runtime={"name": "inferops-mock-serving"})
    assert "unselected runtime" in stopped(tmp_path, models=body)


def test_a_mock_adapter_kind_after_the_rollback_stops_the_run(
    tmp_path: Path,
) -> None:
    body = models_body(**{EXTENSION_ADAPTER_KIND: "mock"})
    assert "adapter kind" in stopped(tmp_path, models=body)


def test_a_release_declaring_no_token_usage_stops_the_run(tmp_path: Path) -> None:
    body = models_body(capabilities={CAPABILITY_TOKEN_USAGE: False})
    assert "mock capability metadata" in stopped(tmp_path, models=body)


def test_a_model_the_configuration_does_not_name_stops_the_run(
    tmp_path: Path,
) -> None:
    body = models_body()
    body["data"] = [{"id": "some-other-model"}]
    assert "does not name" in stopped(tmp_path, models=body)


def test_an_empty_completion_after_the_rollback_stops_the_run(
    tmp_path: Path,
) -> None:
    body = completion_body(
        choices=[{"message": {"role": "assistant", "content": "   "}}]
    )
    assert "is empty" in stopped(tmp_path, completion=body)


def test_a_completion_the_release_refused_stops_the_run(tmp_path: Path) -> None:
    assert "restored a release rather than real inference" in stopped(
        tmp_path, completion_status=503
    )


def test_completion_counts_that_do_not_add_up_stop_the_run(tmp_path: Path) -> None:
    body = completion_body(
        usage={"prompt_tokens": 19, "completion_tokens": 12, "total_tokens": 99}
    )
    assert "absent or inconsistent" in stopped(tmp_path, completion=body)


def test_a_completion_from_the_mock_adapter_stops_the_run(tmp_path: Path) -> None:
    body = completion_body(
        **{EXTENSION_MEMBER: {EXTENSION_ADAPTER_KIND: "mock", EXTENSION_MODEL_REF: "x"}}
    )
    assert "not served by the real adapter" in stopped(tmp_path, completion=body)


# -- the teardown ------------------------------------------------------------


def written_record(tmp_path: Path, document: Mapping[str, Any]) -> Path:
    directory = tmp_path / EXPERIMENT.evidence_directory
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / EXPERIMENT.result_file
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def test_the_cleanup_outcome_is_added_to_the_record(tmp_path: Path) -> None:
    root = artifact_root(tmp_path)
    written_record(root, record_of(run(tmp_path)))
    merged = merge_cleanup(EXPERIMENT, repo_root=root)
    assert merged["cleanup"] == {
        "uninstallMs": 24_000,
        "releaseObjectsRemaining": 0,
        "namespacePresent": True,
        "claimsBefore": 1,
        "claimsAfter": 1,
    }


@pytest.mark.parametrize(
    "override,expected",
    (
        ({"releaseObjectsRemaining": 2}, "left the release behind"),
        ({"helmReleasePresent": True}, "left the release behind"),
        ({"namespacePresent": False}, "removed the release namespace"),
        ({"claimsAfter": 0}, "claim count changed"),
        ({"uninstallMs": 600_001}, "over the"),
    ),
)
def test_a_teardown_that_removed_the_wrong_thing_is_refused(
    override: dict[str, Any], expected: str, tmp_path: Path
) -> None:
    record = record_of(run(tmp_path))
    # After the run, because `run` writes the default documents over this path.
    root = artifact_root(tmp_path, cleanup=cleanup_document(**override))
    written_record(root, record)
    with pytest.raises(ExperimentFailed) as raised:
        merge_cleanup(EXPERIMENT, repo_root=root)
    assert expected in str(raised.value)


def test_a_second_teardown_may_not_replace_the_first(tmp_path: Path) -> None:
    root = artifact_root(tmp_path)
    document = copy.deepcopy(record_of(run(tmp_path)))
    document["cleanup"] = {"uninstallMs": 1}
    written_record(root, document)
    with pytest.raises(ExperimentFailed) as raised:
        merge_cleanup(EXPERIMENT, repo_root=root)
    assert "already carries a cleanup outcome" in str(raised.value)


def test_a_cleanup_with_no_record_to_attach_to_is_refused(tmp_path: Path) -> None:
    root = artifact_root(tmp_path)
    with pytest.raises(ExperimentFailed) as raised:
        merge_cleanup(EXPERIMENT, repo_root=root)
    assert "no record to add a cleanup outcome to" in str(raised.value)


def test_a_record_belonging_to_another_experiment_is_refused(tmp_path: Path) -> None:
    root = artifact_root(tmp_path)
    written_record(root, {"experimentId": "something-else", "cleanup": None})
    with pytest.raises(ExperimentFailed) as raised:
        merge_cleanup(EXPERIMENT, repo_root=root)
    assert "belongs to another experiment" in str(raised.value)


def test_a_redirected_evidence_directory_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "root"
    directory = root / EXPERIMENT.evidence_directory
    directory.parent.mkdir(parents=True, exist_ok=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    try:
        directory.symlink_to(elsewhere, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - needs privilege
        pytest.skip("this host does not permit creating a symlink")
    with pytest.raises(EvidenceUnwritable):
        core.EvidenceDirectory(EXPERIMENT, repo_root=root)


# --------------------------------------------------------------------------
# The operating script, read as text
# --------------------------------------------------------------------------


def test_the_script_sources_the_shared_library() -> None:
    assert 'source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"' in SCRIPT_TEXT


def test_the_script_validates_before_it_installs() -> None:
    """A descriptor is checked before anything is installed, not afterwards."""
    check = SCRIPT_TEXT.index('python -m "${INFEROPS_EXPERIMENT_MODULE}" check')
    install = SCRIPT_TEXT.index("inferops::target_helm install")
    assert check < install


def test_the_script_asserts_the_target_cluster_before_it_acts() -> None:
    """V1-S3-010-PR2 put the provider-aware inferops::resolve_target here in
    place of the kind-pinned inferops::assert_target_cluster; V1-S3-011-PR2 made
    the rest of the script act on the target it verifies."""
    assert "inferops::resolve_target" in SCRIPT_TEXT
    assert SCRIPT_TEXT.index("inferops::resolve_target") < SCRIPT_TEXT.index(
        "inferops::target_helm install"
    )


def test_the_script_requires_the_confirmation_flag() -> None:
    assert "--confirm-real-kubernetes" in SCRIPT_TEXT
    guard = SCRIPT_TEXT.index('[ "${confirmed}" -eq 1 ]')
    assert guard < SCRIPT_TEXT.index("inferops::target_helm install")


def test_the_script_never_creates_the_namespace_it_installs_into() -> None:
    for line in SCRIPT_TEXT.splitlines():
        assert "--create-namespace" not in line or line.strip().startswith("#"), line


def test_every_helm_call_goes_through_the_wrapper_and_names_a_namespace() -> None:
    mutating = ("install", "upgrade", "uninstall", "rollback", "test")
    calls = [
        line
        for line in SCRIPT_LINES
        if re.search(rf"inferops::target_helm\s+({'|'.join(mutating)})\b", line)
    ]
    assert len(calls) >= 6, calls
    for line in calls:
        assert "--namespace" in line, line
    bare = [
        line
        for line in SCRIPT_LINES
        if re.search(rf"(?<!::)\bhelm\s+({'|'.join(mutating)})\b", line)
        and "inferops::target_helm" not in line
        and not line.startswith("inferops::")
    ]
    assert not bare, bare


def test_the_script_only_sets_the_values_paths_the_descriptor_names() -> None:
    """A `--set` whose left-hand side came from a document could set anything.

    Three, and the third earns its place. `fault_scope_values_path` is
    `model.acquisition.enabled`, set false on the one upgrade that carries the
    fault, because the injected byte count renders into the acquisition hook as
    well as into the workload and the hook runs first. Each of the three is
    additionally compared against the single literal this script may set it to,
    a few lines after the descriptor is read.
    """
    assigned = set(re.findall(r'--set "\$\{(\w+)\}=', SCRIPT_TEXT))
    assert assigned == {
        "candidate_values_path",
        "fault_values_path",
        "fault_scope_values_path",
    }
    assert '[ "${fault_scope_values_path}" = "model.acquisition.enabled" ]' in (
        SCRIPT_TEXT
    )
    assert '[ "${fault_scope_value}" = "false" ]' in SCRIPT_TEXT


def test_the_fault_is_aimed_at_the_workload_it_declares() -> None:
    """V1-S3-011-PR2, found by executing this experiment for the first time.

    The model acquisition hook is rendered from the same
    `model.artifact.sizeBytes` the fault injects, and it runs `pre-upgrade` at
    weight -5 -- before any workload object is updated. The first real run
    therefore failed in the hook, created no unhealthy serving pod, detected
    nothing at the workload, and had nothing to recover.
    """
    assert EXPERIMENT.fault.scoped_to_workload_by_values_path == (
        "model.acquisition.enabled"
    )
    assert EXPERIMENT.fault.scoped_to_workload_by_value == "false"
    scope = SCRIPT_TEXT.index('--set "${fault_scope_values_path}=')
    fault = SCRIPT_TEXT.index('--set "${fault_values_path}=${fault_size_bytes}"')
    # Both on the same upgrade: the scoping value is useless on any other one,
    # and harmful on the candidate, which must stay a healthy release.
    assert 0 < scope - fault < 200
    assert SCRIPT_TEXT.count('--set "${fault_scope_values_path}=') == 1


def test_an_unscoped_fault_is_refused(tmp_path: Path) -> None:
    """The scoping is a rule, not a convention the script happens to follow."""
    document = mutated(faultInjection={"scopedToWorkloadByValuesPath": "model.cache"})
    assert "scoped to the serving runtime" in refused(document, tmp_path)


def test_each_values_path_is_compared_against_the_one_literal_it_may_be() -> None:
    """Three `--set` paths, and each held to exactly one literal at its use site.

    These assertions used to sit at the end of the test above, where an inserted
    test left them documented by the wrong docstring.
    """
    assert '[ "${candidate_values_path}" = "telemetry.serviceVersion" ]' in SCRIPT_TEXT
    assert '[ "${fault_values_path}" = "model.artifact.sizeBytes" ]' in SCRIPT_TEXT
    assert '[ "${fault_scope_values_path}" = "model.acquisition.enabled" ]' in (
        SCRIPT_TEXT
    )
    assert '[ "${fault_scope_value}" = "false" ]' in SCRIPT_TEXT
    assert '[ "${candidate_values_path}" = "telemetry.serviceVersion" ]' in SCRIPT_TEXT
    assert '[ "${fault_values_path}" = "model.artifact.sizeBytes" ]' in SCRIPT_TEXT


def test_the_script_refuses_a_candidate_value_that_is_not_an_identifier() -> None:
    assert "*[!A-Za-z0-9._-]*)" in SCRIPT_TEXT


def test_the_script_forwards_only_to_the_descriptors_loopback_host() -> None:
    assert '--address "${descriptor_host}"' in SCRIPT_TEXT
    assert 'base_url="http://${descriptor_host}:${forward_port}"' in SCRIPT_TEXT


def test_the_script_bounds_every_wait() -> None:
    unbounded = [
        line
        for line in SCRIPT_LINES
        if "rollout status" in line and "--timeout" not in line
    ]
    assert not unbounded, unbounded
    assert SCRIPT_TEXT.count("--timeout") >= 10


def test_the_script_does_not_wait_out_the_failing_upgrade() -> None:
    """Waiting for the broken candidate would make detection a timeout.

    Which is the one reading this experiment refuses: a deadline is a statement
    about elapsed time, and a slow model load and a broken container reach it the
    same way.
    """
    assert "expected to fail, and waiting for it would turn the detection" in (
        SCRIPT_TEXT
    )
    fault = SCRIPT_TEXT.index('--set "${fault_values_path}=')
    following = SCRIPT_TEXT[fault : fault + 400]
    assert "--wait" not in following


def test_the_script_removes_neither_the_prerequisites_nor_the_cluster() -> None:
    assert "kind delete cluster" not in SCRIPT_TEXT
    assert "terraform-prerequisites.sh destroy" not in SCRIPT_TEXT
    assert "delete namespace" not in SCRIPT_TEXT
    assert "delete pvc" not in SCRIPT_TEXT


def test_the_script_deletes_nothing_inside_the_cluster() -> None:
    """The only removal this experiment performs is its own `helm uninstall`."""
    assert "kubectl delete" not in SCRIPT_TEXT


def test_the_script_leaves_a_failed_run_in_place() -> None:
    assert "the release was left in place" in SCRIPT_TEXT
    assert "collect_diagnostics" in SCRIPT_TEXT


def test_every_backgrounded_process_is_in_the_cleanup_path() -> None:
    """A process outliving the run would keep touching a real release.

    Derived from the script rather than listed here: every `x_pid="$!"` capture
    is found, and each name has to appear inside `stop_background`. The one this
    caught was the deliberately-failing `helm upgrade` — a run that ended between
    backgrounding it and waiting for it would have left it writing to the
    release's history while the script printed the `helm uninstall` that would
    race it.
    """
    captured = set(re.findall(r'(\w+_pid)="\$!"', SCRIPT_TEXT))
    assert captured == {"forward_pid", "prober_pid", "fault_upgrade_pid"}, captured
    body = SCRIPT_TEXT[
        SCRIPT_TEXT.index("stop_background() {") : SCRIPT_TEXT.index("on_exit() {")
    ]
    for name in captured:
        assert name in body, name
        # Initialised before the trap can reach it: under `nounset` a cleanup
        # function naming an unassigned variable is itself an error, and that
        # error would fire instead of the cleanup.
        assert f'{name}=""' in SCRIPT_TEXT, name


def test_the_exit_trap_names_the_signals_the_siblings_name() -> None:
    """Bash usually runs an EXIT trap on a signal; on Git Bash, usually is not
    a guarantee, and this script leaves more behind than either sibling."""
    assert "trap on_exit INT TERM EXIT" in SCRIPT_TEXT
    for sibling in (
        "kubernetes-certification.sh",
        "kubernetes-multi-replica-certification.sh",
    ):
        text = (REPO_ROOT / "scripts" / "environment" / sibling).read_text(
            encoding="utf-8"
        )
        assert "trap on_exit INT TERM EXIT" in text, sibling


def test_no_query_is_piped_straight_into_a_parser() -> None:
    """A parser reading a query that failed prints a traceback over the refusal.

    Both still abort the run, so this is about what the operator is shown: two
    failures for one cause reads as two causes.
    """
    offenders = [
        line
        for line in SCRIPT_LINES
        if "require_query" in line and "| python" in line.replace("|\n", "|")
    ]
    assert not offenders, offenders


def test_no_collected_value_falls_back_to_empty_on_an_unanswered_query() -> None:
    """An unanswered query is not an empty value.

    `record_stage` used to write `|| value=""` for four fields. Three of them may
    legitimately be empty — the service version before the upgrade, and either
    pod name while nothing of that component is ready — so an API server that
    refused the query was indistinguishable from the release genuinely having
    nothing to report, and the run would then have reported that the upgrade
    never reached the workload.
    """
    body = SCRIPT_TEXT[
        SCRIPT_TEXT.index("record_stage() {") : SCRIPT_TEXT.index(
            "# --- the known-good release"
        )
    ]
    assert '|| service_version=""' not in body
    assert '|| verify_command=""' not in body
    assert '|| runtime_pod=""' not in body
    assert '|| api_pod=""' not in body
    assert body.count("An unanswered query is not") >= 3


def test_the_script_reads_the_byte_count_off_the_workload() -> None:
    """`helm get values` is Helm's bookkeeping; the init container is the cluster."""
    assert "runtime_verify_command" in SCRIPT_TEXT
    assert "initContainers[?(@.name==" in SCRIPT_TEXT
    assert not [line for line in SCRIPT_LINES if "helm get values" in line]


def test_the_script_only_inspects_pods_that_are_not_ready() -> None:
    """The serving pod has a succeeded init container of the same name.

    Reading its terminated state would report a zero exit code as a detection,
    which the module refuses -- but the refusal would name the wrong problem.
    """
    assert "Only pods that are NOT ready are inspected" in SCRIPT_TEXT


def test_the_procedure_document_states_every_limitation() -> None:
    """A limitation in the descriptor and not in the document is not published.

    The descriptor is machine-readable and nobody reads it; the procedure is what
    a contributor opens. Whitespace is collapsed before the comparison because
    the document is wrapped and the descriptor is not.
    """
    procedure = " ".join(PROCEDURE_PATH.read_text(encoding="utf-8").split())
    assert "deploy/serving/experiments/helm-upgrade-rollback.v1.json" in procedure
    assert "scripts/environment/helm-upgrade-rollback.sh" in procedure
    for limitation in EXPERIMENT.limitations:
        assert " ".join(limitation.split()) in procedure, limitation


def test_the_script_carries_no_kind_only_refusal() -> None:
    """V1-S3-011-PR2. The workflow selected the provider and then refused it.

    The guard that did so is removed rather than relaxed: what replaces it is the
    descriptor lookup below, which refuses a provider the experiment cannot
    describe. Asserting the absence of the old comparison is the only way to
    catch a re-introduction, because a re-introduced one would pass every other
    test in this file.
    """
    assert not re.findall(r"\$\{INFEROPS_CLUSTER_NAME\}", SCRIPT_TEXT)
    assert not re.findall(r"\$\{INFEROPS_KUBE_CONTEXT\}", SCRIPT_TEXT)
    assert "Porting this workflow to a provider-neutral target" not in SCRIPT_TEXT


def test_the_script_reads_the_descriptor_entry_for_the_verified_provider() -> None:
    """The descriptor describes several providers; a run uses the one it is on."""
    assert "read_provider_target" in SCRIPT_TEXT
    lookup = SCRIPT_TEXT.index('read_provider_target "${INFEROPS_TARGET_PROVIDER}"')
    assert SCRIPT_TEXT.index("inferops::resolve_target") < lookup
    assert lookup < SCRIPT_TEXT.index("inferops::target_helm install")
    assert '${descriptor_cluster}" = "${INFEROPS_TARGET_CLUSTER_NAME}' in SCRIPT_TEXT
    assert '${descriptor_context}" = "${INFEROPS_TARGET_CONTEXT}' in SCRIPT_TEXT


def test_every_kubectl_call_goes_through_the_verified_target_wrapper() -> None:
    """The same argument the helm test above makes, for the client that reads.

    `inferops::kubectl` is pinned to this repository's own kind kubeconfig. A
    call left on it during a docker-desktop run would read one cluster while the
    release was installed into another, and every assertion downstream would be
    about the wrong cluster.
    """
    assert "inferops::kubectl" not in SCRIPT_TEXT
    assert "inferops::running_node_digest" not in SCRIPT_TEXT
    bare = [
        line
        for line in SCRIPT_LINES
        if re.search(r"(?<!::)\bkubectl\s+\w", line)
        and "inferops::target_kubectl" not in line
        and not line.lstrip().startswith("#")
    ]
    assert not bare, bare


def test_the_record_names_the_provider_that_was_verified() -> None:
    """Not a constant, and not the provider the descriptor happens to list first."""
    assert 'INFEROPS_PROVIDER_FACT="${INFEROPS_TARGET_PROVIDER}"' in SCRIPT_TEXT
    assert 'INFEROPS_CLUSTER_NAME_FACT="${INFEROPS_TARGET_CLUSTER_NAME}"' in SCRIPT_TEXT
    assert 'INFEROPS_CONTEXT="${INFEROPS_TARGET_CONTEXT}"' in SCRIPT_TEXT
    assert 'node_digest="${INFEROPS_TARGET_NODE_IMAGE_DIGEST}"' in SCRIPT_TEXT


def test_the_script_reads_the_one_configmap_the_descriptor_names() -> None:
    """V1-S3-011-PR2, found by the first complete run of this experiment.

    Both reads of the rendered configuration named a label selector, which was
    right when the release carried one ConfigMap and wrong once it carried three:
    the runtime configuration, the telemetry scrape configuration, and the
    collector's. `items[*]` concatenates across all of them, and `items[0]` takes
    whichever sorts first -- the collector's, which carries none of these fields.
    The run reached the end of a successful rollback and then failed writing its
    record, saying only that `release.profile` was not a string.
    """
    reads = [
        line
        for line in SCRIPT_LINES
        if "get configmap" in line and not line.lstrip().startswith("#")
    ]
    assert reads, "the script no longer reads a ConfigMap"
    for line in reads:
        if "all,configmap" in line:
            # The diagnostics dump, which deliberately collects everything.
            continue
        assert '"${descriptor_configmap}"' in line, line
        assert "RELEASE_SELECTOR" not in line, line


def test_the_residue_check_waits_for_the_garbage_collector() -> None:
    """V1-S3-011-PR2, and the same defect both certifications already fixed.

    `helm uninstall --wait` waits for the objects Helm deleted itself. A
    Deployment's pods are not among them: the garbage collector removes them once
    their owner is gone, on the controller manager's schedule. Asking once, the
    instant Helm returns, reports terminating pods as residue -- which is how the
    first complete run of this experiment ended, with two objects that were gone
    moments later and every other stage already passed.
    """
    residue = SCRIPT_TEXT.index("deployments,replicasets,services,configmaps")
    loop = SCRIPT_TEXT.rindex("residue_deadline=$((SECONDS +", 0, residue)
    assert loop < residue, "the residue check is not inside a bounded retry"
    assert "uninstall_budget_ms" in SCRIPT_TEXT[loop:residue], (
        "the residue retry does not reuse the uninstall budget"
    )
