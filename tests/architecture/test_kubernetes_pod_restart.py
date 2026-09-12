"""The Kubernetes pod-restart persistence experiment, held to its own rules.

Every test here runs offline against synthetic documents. Nothing installs a
release, deletes a pod, or contacts a cluster: what is under test is the
descriptor, the assertions over a collected run, and the operating script read as
text.

The question the experiment answers is narrower than "did the pod come back", and
most of this file exists to keep it narrow. A pod comes back whether or not
anything survived, so each test below names one way a run could look successful
without the model having survived, and asserts that the run is refused.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from inferops.api.surface import CORRELATION_ID_HEADER, REQUEST_ID_HEADER
from tools.kubernetes_certification.core import load_certification
from tools.kubernetes_pod_restart import (
    ExperimentError,
    ExperimentFailed,
    ExperimentRefused,
    evaluate,
    load_experiment,
    result_document,
)
from tools.model_acquisition import load_manifest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR_PATH = (
    REPO_ROOT / "deploy" / "serving" / "experiments" / "kubernetes-pod-restart.v1.json"
)
SCRIPT_PATH = REPO_ROOT / "scripts" / "environment" / "kubernetes-pod-restart.sh"
PROCEDURE_PATH = (
    REPO_ROOT / "docs" / "serving" / "kubernetes-pod-restart-persistence.md"
)

EXPERIMENT = load_experiment()
CERTIFICATION = load_certification()
MANIFEST = load_manifest()
SCRIPT_TEXT = SCRIPT_PATH.read_text(encoding="utf-8")
SCRIPT_LINES = SCRIPT_TEXT.splitlines()

(KIND_TARGET,) = [e for e in EXPERIMENT.clusters if e.provider_id == "kind"]
(DOCKER_DESKTOP_TARGET,) = [
    e for e in EXPERIMENT.clusters if e.provider_id == "docker-desktop"
]

BASE_URL = "http://127.0.0.1:18092"
SUB_PATH = f"Qwen--Qwen3-1.7B-GGUF/{MANIFEST.revision}"


# --------------------------------------------------------------------------
# Synthetic documents
# --------------------------------------------------------------------------


def descriptor_document() -> dict[str, Any]:
    return json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))


def mutated(**sections: Mapping[str, Any]) -> dict[str, Any]:
    document = descriptor_document()
    for name, members in sections.items():
        document[name] = {**document[name], **members}
    return document


def refused(document: Mapping[str, Any], tmp_path: Path) -> str:
    path = tmp_path / "descriptor.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ExperimentError) as raised:
        load_experiment(path, baseline=CERTIFICATION)
    return str(raised.value)


def pod_document(**overrides: Any) -> dict[str, Any]:
    document = {
        "name": "inferops-runtime-aaa",
        "uid": "11111111-1111-1111-1111-111111111111",
        "ownerKind": "ReplicaSet",
        "ownerName": "inferops-inferops-llm-runtime-abc",
        "nodeName": "a-node",
        "claimName": EXPERIMENT.model_cache.claim_name,
        "claimReadOnly": True,
        "boundVolumeName": "model-cache",
        "initContainer": EXPERIMENT.model_cache.verification_init_container,
        "initExitCode": 0,
        "initFinished": True,
        "artifactPath": "/models/Qwen3-1.7B-Q8_0.gguf",
        "artifactSubPath": SUB_PATH,
        "artifactSizeBytes": MANIFEST.expected_size_bytes,
        "artifactSha256": MANIFEST.sha256,
        "artifactInode": "4242",
        "artifactMtimeEpoch": 1_760_000_000,
        "ready": True,
    }
    return {**document, **overrides}


def lifecycle_document(
    *,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    **sections: Mapping[str, Any],
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "cluster": {
            "provider": KIND_TARGET.provider_id,
            "name": KIND_TARGET.name,
            "context": KIND_TARGET.context,
            "serverVersion": "v1.34.8",
            "nodeImageDigest": KIND_TARGET.node_image_digest,
        },
        "tooling": {"helm": "v3.19.0+g3d8990f", "kubectl": "v1.34.3"},
        "release": {
            "name": EXPERIMENT.release.name,
            "namespace": EXPERIMENT.release.namespace,
            "chart": "inferops-llm-0.3.0",
            "profile": EXPERIMENT.release.profile,
            "revisionBefore": 1,
            "revisionAfter": 1,
        },
        "configuration": {
            "modelIdentifier": "qwen3-1-7b-q8-0",
            "modelRevision": MANIFEST.revision,
        },
        "claim": {
            "uid": "claim-uid",
            "boundVolumeBefore": "pvc-0000",
            "boundVolumeAfter": "pvc-0000",
        },
        "before": pod_document(**(before or {})),
        "after": pod_document(
            **{
                "name": "inferops-runtime-bbb",
                "uid": "22222222-2222-2222-2222-222222222222",
                **(after or {}),
            }
        ),
        "acquisition": {
            "jobCountBefore": 0,
            "jobCountAfter": 0,
            "jobUidBefore": "",
            "jobUidAfter": "",
            "installLog": "",
        },
        "timings": {
            "deletedAtMs": 0,
            "replacementScheduledAtMs": 1_000,
            "replacementReadyAtMs": 20_000,
            "recoveredAtMs": 25_000,
        },
    }
    for name, members in sections.items():
        document[name] = {**document[name], **members}
    return document


def readiness_document(samples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "samples": samples
        if samples is not None
        else [
            {"atMs": 0, "readyReplicas": 0, "podName": ""},
            {"atMs": 2_000, "readyReplicas": 0, "podName": "inferops-runtime-bbb"},
            {"atMs": 20_000, "readyReplicas": 1, "podName": "inferops-runtime-bbb"},
        ]
    }


def baseline_document(**overrides: Any) -> dict[str, Any]:
    document = {
        "status": 200,
        "adapterKind": "real",
        "modelIdentifier": "qwen3-1-7b-q8-0",
        "promptTokens": 12,
        "completionTokens": 19,
        "totalTokens": 31,
        "generatedTextRetained": False,
    }
    return {**document, **overrides}


def models_body() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": "qwen3-1-7b-q8-0", "object": "model"}],
        "x_inferops": {
            "adapterKind": "real",
            "runtime": {
                "name": "llama.cpp llama-server",
                "version": "b4667",
                "modelRevision": MANIFEST.revision,
            },
            "capabilities": {"tokenUsage": True},
        },
    }


def completion_body() -> dict[str, Any]:
    return {
        "object": "chat.completion",
        "choices": [
            {"message": {"role": "assistant", "content": "It preserves data."}}
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 19, "total_tokens": 31},
        "x_inferops": {
            "adapterKind": "real",
            "modelRef": "qwen3-1-7b-q8-0",
        },
    }


class _Response:
    def __init__(self, status: int, body: Any, headers: Mapping[str, str]) -> None:
        self.status = status
        self.body = body
        self.headers = dict(headers)


def seams(
    *, models: Any = None, completion: Any = None, status: int = 200
) -> tuple[Any, Any]:
    def get(url: str, timeout: float) -> Any:
        if url.endswith(EXPERIMENT.readiness_path):
            return _Response(200, {"status": "ready"}, {})
        return _Response(status, models if models is not None else models_body(), {})

    def post(
        url: str, body: Mapping[str, object], headers: Mapping[str, str], timeout: float
    ) -> Any:
        return _Response(
            status,
            completion if completion is not None else completion_body(),
            {
                REQUEST_ID_HEADER: headers.get(REQUEST_ID_HEADER, ""),
                CORRELATION_ID_HEADER: headers.get(CORRELATION_ID_HEADER, ""),
            },
        )

    return get, post


def artifact_root(
    tmp_path: Path,
    *,
    lifecycle: Mapping[str, Any] | None = None,
    readiness: Mapping[str, Any] | None = None,
    baseline: Mapping[str, Any] | None = None,
    cleanup: Mapping[str, Any] | None = None,
) -> Path:
    """One repository-shaped directory holding what a run would have written."""
    for relative, document in (
        (EXPERIMENT.lifecycle_file, lifecycle or lifecycle_document()),
        (EXPERIMENT.readiness_file, readiness or readiness_document()),
        (EXPERIMENT.baseline_completion_file, baseline or baseline_document()),
        (EXPERIMENT.cleanup_file, cleanup),
    ):
        if document is None:
            continue
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document), encoding="utf-8")
    return tmp_path


def run(tmp_path: Path, **kwargs: Any) -> Any:
    get, post = kwargs.pop("seams", None) or seams()
    return evaluate(
        EXPERIMENT,
        confirmed=True,
        base_url=BASE_URL,
        repo_root=artifact_root(tmp_path, **kwargs),
        baseline=CERTIFICATION,
        get=get,
        post=post,
    )


def stopped(tmp_path: Path, **kwargs: Any) -> str:
    with pytest.raises(ExperimentError) as raised:
        run(tmp_path, **kwargs)
    return str(raised.value)


# --------------------------------------------------------------------------
# The descriptor
# --------------------------------------------------------------------------


def test_the_committed_descriptor_loads() -> None:
    assert EXPERIMENT.experiment_id == "inferops-kubernetes-pod-restart-persistence"
    assert EXPERIMENT.evidence_class == "local-real-cpu"
    assert EXPERIMENT.certification_ceiling == "C2"
    assert not EXPERIMENT.retain_generated_text


def test_the_descriptor_agrees_with_the_certification_about_the_release() -> None:
    """One release, described once. A second set of numbers is a second release."""
    assert EXPERIMENT.release == CERTIFICATION.release
    assert EXPERIMENT.clusters == CERTIFICATION.clusters
    assert EXPERIMENT.request_host == CERTIFICATION.request_host
    assert EXPERIMENT.budgets.uninstall_ms == CERTIFICATION.budgets.uninstall_ms


def test_a_descriptor_describing_another_release_is_refused(tmp_path: Path) -> None:
    document = mutated(release={"namespace": "somewhere-else"})
    assert "different releases" in refused(document, tmp_path)


def test_a_disruption_that_deletes_a_declared_object_is_refused(
    tmp_path: Path,
) -> None:
    document = mutated(disruption={"deletesDeclaredObject": True})
    assert "not a declared object" in refused(document, tmp_path)


def test_a_disruption_this_experiment_does_not_perform_is_refused(
    tmp_path: Path,
) -> None:
    document = mutated(disruption={"mechanism": "drain-the-node"})
    assert "only disruption" in refused(document, tmp_path)


def test_a_replacement_this_workflow_made_itself_is_refused(tmp_path: Path) -> None:
    """A replacement this script created would be this script testing itself."""
    document = mutated(disruption={"reversedBy": "the-operating-script"})
    assert "Deployment controller" in refused(document, tmp_path)


def test_a_descriptor_that_would_remove_a_prerequisite_is_refused(
    tmp_path: Path,
) -> None:
    document = mutated(cleanup={"removesModelCacheClaim": True})
    assert "removes the release and nothing else" in refused(document, tmp_path)


def test_a_descriptor_that_would_not_compare_the_artifact_is_refused(
    tmp_path: Path,
) -> None:
    document = mutated(modelCache={"requireArtifactDigestUnchanged": False})
    assert "would be a restart experiment" in refused(document, tmp_path)


def test_a_descriptor_that_would_not_require_a_different_pod_is_refused(
    tmp_path: Path,
) -> None:
    document = mutated(replacement={"requireDifferentPodUid": False})
    assert "one layer down" in refused(document, tmp_path)


def test_a_replacement_budget_shorter_than_a_healthy_rollout_is_refused(
    tmp_path: Path,
) -> None:
    """Otherwise a slow but correct replacement is recorded as a failure."""
    document = mutated(readiness={"replacementBudgetMs": 1_000})
    assert "shorter than a healthy rollout" in refused(document, tmp_path)


def test_a_busy_poll_interval_is_refused(tmp_path: Path) -> None:
    document = mutated(observation={"pollIntervalMs": 100})
    assert "spins against the API server" in refused(document, tmp_path)


def test_an_evidence_path_version_control_does_not_ignore_is_refused(
    tmp_path: Path,
) -> None:
    document = mutated(evidence={"directory": "docs/proof"})
    assert "evidence locations are fixed" in refused(document, tmp_path)


def test_the_already_present_signal_is_the_line_the_chart_prints() -> None:
    """A signal nothing emits is an assertion that can never fire."""
    helpers = (
        REPO_ROOT / "charts" / "inferops-llm" / "templates" / "_helpers.tpl"
    ).read_text(encoding="utf-8")
    assert EXPERIMENT.acquisition.already_present_signal in helpers


# --------------------------------------------------------------------------
# A run that behaved
# --------------------------------------------------------------------------


def test_a_complete_run_is_accepted(tmp_path: Path) -> None:
    result = run(tmp_path)
    assert result.facts.before.uid != result.facts.after.uid
    assert result.facts.timings.replacement_ms == 20_000
    assert result.facts.timings.recovery_ms == 25_000
    assert result.identity.adapter_kind == "real"
    assert result.completion.total_tokens == 31
    assert result.readiness.observed_not_ready == 2
    assert result.readiness.observed_ready == 1


def test_the_record_carries_no_prompt_and_no_completion(tmp_path: Path) -> None:
    """The one thing a record of a real model's answer must never keep."""
    document = result_document(run(tmp_path))
    serialised = json.dumps(document)
    assert EXPERIMENT.prompt not in serialised
    assert "It preserves data." not in serialised
    assert document["completion"]["generatedTextRetained"] is False


def test_the_record_names_the_provider_and_says_who_pinned_the_node_image(
    tmp_path: Path,
) -> None:
    document = result_document(run(tmp_path))
    assert document["cluster"]["provider"] == "kind"
    assert document["cluster"]["nodeImagePinnedByInferOps"] is True


def test_the_record_states_the_timings_are_not_a_benchmark(tmp_path: Path) -> None:
    document = result_document(run(tmp_path))
    assert "not a benchmark" in document["timings"]["note"].lower()


# --------------------------------------------------------------------------
# Ways a run could look successful without the model having survived
# --------------------------------------------------------------------------


def test_an_unconfirmed_run_observes_nothing(tmp_path: Path) -> None:
    get, post = seams()
    with pytest.raises(ExperimentRefused):
        evaluate(
            EXPERIMENT,
            confirmed=False,
            base_url=BASE_URL,
            repo_root=artifact_root(tmp_path),
            baseline=CERTIFICATION,
            get=get,
            post=post,
        )


def test_a_base_url_that_is_not_the_loopback_forward_is_refused(
    tmp_path: Path,
) -> None:
    get, post = seams()
    with pytest.raises(ExperimentRefused):
        evaluate(
            EXPERIMENT,
            confirmed=True,
            base_url="http://an-external-host:8090",
            repo_root=artifact_root(tmp_path),
            baseline=CERTIFICATION,
            get=get,
            post=post,
        )


def test_the_same_pod_coming_back_is_not_a_replacement(tmp_path: Path) -> None:
    """A container that restarted in place is the Sprint 2 experiment."""
    facts = lifecycle_document(after={"name": "inferops-runtime-aaa"})
    assert "so nothing was replaced" in stopped(tmp_path, lifecycle=facts)


def test_the_same_pod_uid_is_not_a_replacement(tmp_path: Path) -> None:
    facts = lifecycle_document(after={"uid": "11111111-1111-1111-1111-111111111111"})
    assert "one layer down" in stopped(tmp_path, lifecycle=facts)


def test_a_replacement_created_by_another_workload_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(after={"ownerName": "somebody-elses-replicaset"})
    assert "not created by the workload" in stopped(tmp_path, lifecycle=facts)


def test_a_different_claim_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(after={"claimName": "another-claim"})
    assert "different claim" in stopped(tmp_path, lifecycle=facts)


def test_a_rebound_claim_stops_the_run(tmp_path: Path) -> None:
    """A claim bound to a new PersistentVolume preserved nothing."""
    facts = lifecycle_document(claim={"boundVolumeAfter": "pvc-9999"})
    assert "different PersistentVolume" in stopped(tmp_path, lifecycle=facts)


def test_a_replacement_mounting_a_different_volume_name_stops_the_run(
    tmp_path: Path,
) -> None:
    """Distinct from the claim's binding, and the first real run confused them.

    `boundVolumeName` is the handle the *pod* gives the volume in its own spec.
    The claim's bound PersistentVolume is a cluster-scoped name. Comparing one
    against the other refuses a replacement that mounted exactly the right
    volume, which is what the first real run of this experiment did.
    """
    facts = lifecycle_document(after={"boundVolumeName": "a-different-handle"})
    assert "different volume name" in stopped(tmp_path, lifecycle=facts)


def test_a_writable_remount_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(after={"claimReadOnly": False})
    assert "mounted the model cache writable" in stopped(tmp_path, lifecycle=facts)


def test_a_changed_digest_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(after={"artifactSha256": "sha256:" + "0" * 64})
    assert "SHA-256 changed" in stopped(tmp_path, lifecycle=facts)


def test_a_changed_byte_count_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(after={"artifactSizeBytes": 4_096})
    assert "byte count changed" in stopped(tmp_path, lifecycle=facts)


def test_a_reacquired_artifact_stops_the_run(tmp_path: Path) -> None:
    """The half that is invisible without this check.

    A re-acquired artifact has the same size and the same digest as the one it
    replaced -- that is what "acquire the pinned artifact" means. What it cannot
    have is the same inode, because an acquisition writes a temporary file and
    renames it over the artifact.
    """
    facts = lifecycle_document(after={"artifactInode": "9999"})
    assert "different inode" in stopped(tmp_path, lifecycle=facts)


def test_a_rewritten_artifact_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(after={"artifactMtimeEpoch": 1_760_009_999})
    assert "modification time moved" in stopped(tmp_path, lifecycle=facts)


def test_an_acquisition_job_that_appeared_stops_the_run(tmp_path: Path) -> None:
    """A pod deletion is neither an install nor an upgrade, so no hook may run."""
    facts = lifecycle_document(acquisition={"jobCountAfter": 1})
    assert "no hook may have run" in stopped(tmp_path, lifecycle=facts)


def test_an_acquisition_job_with_a_new_identity_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(
        acquisition={"jobCountBefore": 1, "jobCountAfter": 1, "jobUidAfter": "new"}
    )
    assert "the hook ran again" in stopped(tmp_path, lifecycle=facts)


def test_an_init_container_that_did_not_run_stops_the_run(tmp_path: Path) -> None:
    """Nothing compared the surviving bytes against the pins inside the cluster."""
    facts = lifecycle_document(after={"initFinished": False, "initExitCode": -1})
    assert "integrity init container" in stopped(tmp_path, lifecycle=facts)


def test_a_moved_release_revision_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(release={"revisionAfter": 2})
    assert "release revision moved" in stopped(tmp_path, lifecycle=facts)


def test_readiness_that_never_dropped_stops_the_run(tmp_path: Path) -> None:
    """A replacement nobody saw happen is a replacement this record cannot make."""
    samples = readiness_document(
        [
            {"atMs": 0, "readyReplicas": 1, "podName": ""},
            {"atMs": 2_000, "readyReplicas": 1, "podName": "inferops-runtime-bbb"},
            {"atMs": 4_000, "readyReplicas": 1, "podName": "inferops-runtime-bbb"},
        ]
    )
    assert "never observed at zero" in stopped(tmp_path, readiness=samples)


def test_too_few_readiness_samples_stop_the_run(tmp_path: Path) -> None:
    samples = readiness_document([{"atMs": 0, "readyReplicas": 0, "podName": ""}])
    assert "requires at least" in stopped(tmp_path, readiness=samples)


def test_a_baseline_that_never_answered_stops_the_run(tmp_path: Path) -> None:
    """ "Succeeds again" needs a before, and `helm test` is not one."""
    assert "no working inference to recover" in stopped(
        tmp_path, baseline=baseline_document(status=503)
    )


def test_a_baseline_served_by_a_mock_stops_the_run(tmp_path: Path) -> None:
    assert "not served by the real adapter" in stopped(
        tmp_path, baseline=baseline_document(adapterKind="mock")
    )


def test_a_baseline_pod_that_was_never_ready_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(before={"ready": False})
    assert "no known-good state" in stopped(tmp_path, lifecycle=facts)


def test_an_unpinned_baseline_artifact_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(before={"artifactSizeBytes": 4_096})
    assert "not the pinned byte count" in stopped(tmp_path, lifecycle=facts)


def test_a_mount_that_is_not_revision_scoped_stops_the_run(tmp_path: Path) -> None:
    """The scoping is the mount's `subPath`; the container sees a flat path."""
    facts = lifecycle_document(
        before={"artifactSubPath": "Qwen--Qwen3-1.7B-GGUF"},
        after={"artifactSubPath": "Qwen--Qwen3-1.7B-GGUF"},
    )
    assert "subPath scoped to the declared" in stopped(tmp_path, lifecycle=facts)


def test_timings_out_of_order_stop_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(
        timings={"replacementReadyAtMs": 30_000, "recoveredAtMs": 25_000}
    )
    assert "not in the order" in stopped(tmp_path, lifecycle=facts)


def test_a_replacement_beyond_its_budget_stops_the_run(tmp_path: Path) -> None:
    facts = lifecycle_document(
        timings={"replacementReadyAtMs": 1_000_000, "recoveredAtMs": 1_100_000}
    )
    assert "longer than its budget" in stopped(tmp_path, lifecycle=facts)


def test_a_mock_answer_after_the_replacement_stops_the_run(tmp_path: Path) -> None:
    body = models_body()
    body["x_inferops"]["adapterKind"] = "mock"
    assert "adapter kind" in stopped(tmp_path, seams=seams(models=body))


def test_an_answer_with_no_usage_counts_stops_the_run(tmp_path: Path) -> None:
    body = completion_body()
    body["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    assert "reported no usage" in stopped(tmp_path, seams=seams(completion=body))


def test_an_answer_with_no_content_stops_the_run(tmp_path: Path) -> None:
    body = completion_body()
    body["choices"][0]["message"]["content"] = "   "
    assert "carries no content" in stopped(tmp_path, seams=seams(completion=body))


def test_a_provider_the_descriptor_does_not_describe_stops_the_run(
    tmp_path: Path,
) -> None:
    facts = lifecycle_document(cluster={"provider": "some-cloud"})
    assert "does not describe" in stopped(tmp_path, lifecycle=facts)


def test_the_reference_provider_is_accepted_with_its_own_node_image(
    tmp_path: Path,
) -> None:
    """Docker Desktop chooses its own node image; InferOps does not pin it."""
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
    assert result.facts.provider == "docker-desktop"
    document = result_document(result)
    assert document["cluster"]["nodeImagePinnedByInferOps"] is False


# --------------------------------------------------------------------------
# Cleanup
# --------------------------------------------------------------------------


def test_a_cleanup_that_removed_a_prerequisite_is_refused(tmp_path: Path) -> None:
    from tools.kubernetes_pod_restart import load_cleanup_facts
    from tools.kubernetes_pod_restart.core import _check_cleanup

    root = artifact_root(
        tmp_path,
        cleanup={
            "releaseRemoved": True,
            "releaseObjectsRemaining": 0,
            "claimPresent": False,
            "namespacePresent": True,
        },
    )
    cleanup = load_cleanup_facts(EXPERIMENT, repo_root=root)
    with pytest.raises(ExperimentFailed) as raised:
        _check_cleanup(EXPERIMENT, cleanup)
    assert "removes the release and nothing else" in str(raised.value)


def test_release_residue_is_refused(tmp_path: Path) -> None:
    from tools.kubernetes_pod_restart import load_cleanup_facts
    from tools.kubernetes_pod_restart.core import _check_cleanup

    root = artifact_root(
        tmp_path,
        cleanup={
            "releaseRemoved": True,
            "releaseObjectsRemaining": 2,
            "claimPresent": True,
            "namespacePresent": True,
        },
    )
    cleanup = load_cleanup_facts(EXPERIMENT, repo_root=root)
    with pytest.raises(ExperimentFailed) as raised:
        _check_cleanup(EXPERIMENT, cleanup)
    assert "remained after the uninstall" in str(raised.value)


# --------------------------------------------------------------------------
# The operating script, read as text
# --------------------------------------------------------------------------


def test_the_script_sources_the_shared_library() -> None:
    assert 'source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"' in SCRIPT_TEXT


def test_the_script_verifies_the_target_before_it_installs() -> None:
    assert "inferops::resolve_target" in SCRIPT_TEXT
    assert SCRIPT_TEXT.index("inferops::resolve_target") < SCRIPT_TEXT.index(
        "inferops::target_helm install"
    )


def test_the_script_requires_the_confirmation_flag() -> None:
    assert "--confirm-real-kubernetes" in SCRIPT_TEXT
    guard = SCRIPT_TEXT.index('[ "${confirmed}" -eq 1 ]')
    assert guard < SCRIPT_TEXT.index("inferops::target_helm install")


def test_the_script_never_creates_the_namespace_it_installs_into() -> None:
    for line in SCRIPT_LINES:
        assert "--create-namespace" not in line or line.strip().startswith("#"), line


def test_every_helm_and_kubectl_call_goes_through_the_target_wrappers() -> None:
    """A call on the kind-pinned wrapper would read the wrong cluster."""
    assert "inferops::kubectl" not in SCRIPT_TEXT
    assert "inferops::helm " not in SCRIPT_TEXT
    # Quoted text is blanked first. Several messages name `helm uninstall` and
    # `kubectl` in prose -- telling an operator what to run is not this script
    # running it -- and matching those would make this test assert about English.
    bare = [
        line
        for line in SCRIPT_LINES
        if re.search(r"(?<!::)\b(kubectl|helm)\s+\w", re.sub(r'"[^"]*"', '""', line))
        and "inferops::target_" not in line
        and not line.lstrip().startswith("#")
    ]
    assert not bare, bare


def test_the_script_deletes_exactly_one_pod_and_nothing_else() -> None:
    """The whole safety argument of this experiment, read off the script."""
    deletes = [
        line
        for line in SCRIPT_LINES
        if re.search(r"inferops::target_kubectl delete\b", line)
        and not line.lstrip().startswith("#")
    ]
    assert len(deletes) == 1, deletes
    assert "delete pod" in deletes[0]
    assert '"${baseline_pod}"' in deletes[0]
    assert "--all" not in deletes[0]
    assert "-l " not in deletes[0]


def test_the_script_never_deletes_a_namespace_a_claim_or_a_cluster() -> None:
    for forbidden in (
        "delete namespace",
        "delete pvc",
        "delete persistentvolumeclaim",
        "kind delete cluster",
        "terraform destroy",
    ):
        assert forbidden not in SCRIPT_TEXT, forbidden


def test_the_script_reads_the_descriptor_entry_for_the_verified_provider() -> None:
    assert "read_provider_target" in SCRIPT_TEXT
    assert '${descriptor_cluster}" = "${INFEROPS_TARGET_CLUSTER_NAME}' in SCRIPT_TEXT
    assert '${descriptor_context}" = "${INFEROPS_TARGET_CONTEXT}' in SCRIPT_TEXT


def test_the_script_computes_the_digest_rather_than_repeating_the_pin() -> None:
    """Reading the pin into both sides of a comparison compares a file to itself."""
    assert "sha256sum" in SCRIPT_TEXT
    assert "stat -c %i" in SCRIPT_TEXT
    assert "stat -c %Y" in SCRIPT_TEXT


def test_the_script_reads_the_mount_off_the_serving_container() -> None:
    """The acquisition hook mounts the same claim writable, by design.

    A read-only check that looked at any mount of the claim would find the
    hook's and report the wrong answer for the serving runtime's.
    """
    assert 'container.get("name") != "runtime"' in SCRIPT_TEXT


def test_the_script_uninstalls_the_release_it_installed() -> None:
    assert "inferops::target_helm uninstall" in SCRIPT_TEXT
    assert SCRIPT_TEXT.index("inferops::target_helm install") < SCRIPT_TEXT.index(
        "inferops::target_helm uninstall"
    )


def test_the_procedure_document_states_every_limitation() -> None:
    """A limitation in the descriptor and not in the document is not published."""
    procedure = " ".join(PROCEDURE_PATH.read_text(encoding="utf-8").split())
    assert "deploy/serving/experiments/kubernetes-pod-restart.v1.json" in procedure
    assert "scripts/environment/kubernetes-pod-restart.sh" in procedure
    for limitation in EXPERIMENT.limitations:
        assert " ".join(limitation.split()) in procedure, limitation
