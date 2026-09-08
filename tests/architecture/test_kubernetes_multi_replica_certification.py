"""The multi-replica Kubernetes certification, its guards, and its script.

Every check here reads committed files, drives the workflow through documents a
real run would have written, or executes one of the three programs the operating
script embeds. No cluster is contacted, no release is installed, no Job is
created, no model byte is read, and no `kubectl`, `helm`, or `terraform` command
runs. These results are `local-static` and synthetic.

Three of the checks deserve their names said out loud.

*The capacity arithmetic.* The descriptor declares what two API replicas and one
runtime replica request and what they may peak at, and those figures are the
chart's own resource blocks multiplied by the replica counts. Nothing stops the
two drifting except this suite, and a capacity gate computed from stale figures
is a gate that passes a host which cannot hold the release.

*The three round trips.* The script collects capacity, cluster facts, and the
correlation into JSON documents and the Python tool reads them back. Both halves
of each pair can look right and disagree -- that is exactly the defect
independent review found in `V1-S3-006-PR1`, where `helm list -o json` reports a
revision as a string and the reader demanded an integer. So each embedded program
is extracted from the script and executed here against representative input, and
its output is fed to the reader that consumes it.

*The correlation refusals.* The one claim this PR adds is that successful
requests reached more than one replica. Every way that claim could be made on
weaker evidence -- a request nobody recorded, a request two replicas both claim,
a record from a pod that was never a ready replica, every record from a single
pod -- is written out below as a refusal, because a positive test alone would
pass on a workflow that asserted nothing.

What none of this establishes is that any of it works. Whether a release
installs with two replicas, whether both load the model inside their budgets,
whether a Service distributes anything, and whether a teardown leaves no residue
are runtime questions, and only an authorized run of
`scripts/environment/kubernetes-multi-replica-certification.sh certify
--confirm-real-kubernetes` answers them.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.api.surface import CHAT_COMPLETIONS_PATH, EXTENSION_ADAPTER_KIND
from inferops.telemetry import names
from tools.kubernetes_certification import core, multi_replica
from tools.kubernetes_certification.multi_replica_cli import (
    EXIT_CAPACITY,
    EXIT_FAILED,
    EXIT_OK,
    EXIT_REFUSED,
    main,
)
from tools.model_acquisition import load_manifest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPO_ROOT / "scripts" / "environment" / "kubernetes-multi-replica-certification.sh"
)
SINGLE_SCRIPT_PATH = (
    REPO_ROOT / "scripts" / "environment" / "kubernetes-certification.sh"
)
LIB_PATH = REPO_ROOT / "scripts" / "environment" / "lib.sh"
CHART_VALUES_PATH = REPO_ROOT / "charts" / "inferops-llm" / "values.yaml"
RENDERED_REAL_PATH = (
    REPO_ROOT / "charts" / "inferops-llm" / "ci" / "rendered" / "real.expected.yaml"
)
PROCEDURE_PATH = (
    REPO_ROOT / "docs" / "serving" / "kubernetes-multi-replica-certification.md"
)

DESCRIPTOR: dict[str, Any] = json.loads(
    multi_replica.MULTI_REPLICA_CERTIFICATION_PATH.read_text(encoding="utf-8")
)
SCRIPT_TEXT = SCRIPT_PATH.read_text(encoding="utf-8")
LIB_TEXT = LIB_PATH.read_text(encoding="utf-8")
CHART_VALUES: dict[str, Any] = yaml.safe_load(
    CHART_VALUES_PATH.read_text(encoding="utf-8")
)

MODEL_IDENTIFIER = "qwen3-1-7b-q8-0"
API_IMAGE = (
    "localhost/inferops-api@sha256:"
    "7961c9f9ce773095461498774bc2f25053bcba6d01c40d8448da65e217091e50"
)
RUNTIME_IMAGE = (
    "ghcr.io/ggml-org/llama.cpp@sha256:"
    "100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"
)
VERIFY_IMAGE = (
    "docker.io/library/busybox@sha256:"
    "9db7b59979c38555a39def84a31fb98b5296952f9e3afd4f6f11f05b07adfab0"
)

API_POD_ONE = "inferops-inferops-llm-6d4b7c9f8a-aaaaa"
API_POD_TWO = "inferops-inferops-llm-6d4b7c9f8a-bbbbb"
RUNTIME_POD = "inferops-inferops-llm-runtime-5c8f9d7b6a-ccccc"


def lib_constant(name: str) -> str:
    match = re.search(
        rf'^readonly {re.escape(name)}="([^"]*)"', LIB_TEXT, flags=re.MULTILINE
    )
    assert match is not None, f"lib.sh does not define {name}"
    return match.group(1)


def kube_context() -> str:
    return lib_constant("INFEROPS_KUBE_CONTEXT").replace(
        "${INFEROPS_CLUSTER_NAME}", lib_constant("INFEROPS_CLUSTER_NAME")
    )


def rendered_objects() -> list[dict[str, Any]]:
    return [
        document
        for document in yaml.safe_load_all(
            RENDERED_REAL_PATH.read_text(encoding="utf-8")
        )
        if document
    ]


def rendered(kind: str, component: str) -> dict[str, Any]:
    matches = [
        document
        for document in rendered_objects()
        if document.get("kind") == kind
        and document.get("metadata", {})
        .get("labels", {})
        .get("app.kubernetes.io/component")
        == component
    ]
    assert len(matches) == 1, (kind, component, len(matches))
    return matches[0]


# --------------------------------------------------------------------------
# Fixtures: the documents a real run would have written
# --------------------------------------------------------------------------


def capacity_facts_document(**overrides: Any) -> dict[str, Any]:
    """A host that comfortably holds the profile."""
    document: dict[str, Any] = {
        "engine": {"cpus": 8, "memoryBytes": 12 * 1024**3},
        "cluster": {
            "schedulableNodes": 1,
            "allocatableCpuMillis": 8000,
            "allocatableMemoryBytes": 12 * 1024**3,
            "committedCpuMillis": 950,
            "committedMemoryBytes": 400 * 1024**2,
        },
    }
    for key, value in overrides.items():
        section, _, member = key.partition("_")
        document[section][member] = value
    return document


def facts_document() -> dict[str, Any]:
    """Two ready API replicas, one ready runtime replica, everything pinned."""
    manifest = load_manifest()
    return {
        "cluster": {
            "name": lib_constant("INFEROPS_CLUSTER_NAME"),
            "context": kube_context(),
            "serverVersion": "v1.34.8",
            "nodeImageDigest": lib_constant("INFEROPS_NODE_IMAGE_DIGEST"),
        },
        "tooling": {
            "helm": "v3.19.0+g3d8990f",
            "kubectl": "v1.36.1",
            "terraform": "1.15.8",
        },
        "release": {
            "name": "inferops",
            "namespace": "inferops-release",
            "revision": "1",
            "status": "deployed",
            "chart": "inferops-llm-0.2.0",
            "profile": "real",
            "testPassed": True,
        },
        "workloads": [
            {
                "name": "inferops-inferops-llm",
                "component": "platform-api",
                "images": [API_IMAGE],
                "replicasDesired": 2,
                "replicasReady": 2,
            },
            {
                "name": "inferops-inferops-llm-runtime",
                "component": "serving-runtime",
                "images": [VERIFY_IMAGE, RUNTIME_IMAGE],
                "replicasDesired": 1,
                "replicasReady": 1,
            },
        ],
        "replicas": [
            {
                "podName": API_POD_ONE,
                "component": "platform-api",
                "ready": True,
                "readyAfterMs": 4200,
                "restarts": 0,
            },
            {
                "podName": API_POD_TWO,
                "component": "platform-api",
                "ready": True,
                "readyAfterMs": 5100,
                "restarts": 0,
            },
            {
                "podName": RUNTIME_POD,
                "component": "serving-runtime",
                "ready": True,
                "readyAfterMs": 271000,
                "restarts": 0,
            },
        ],
        "modelCache": {
            "claimName": "inferops-model-cache",
            "volumeReadOnly": True,
            "mountReadOnly": True,
            "initContainers": ["verify-model"],
            "artifactHashCompared": True,
        },
        "configuration": {
            "serviceVersion": "",
            "modelIdentifier": MODEL_IDENTIFIER,
            "modelRevision": manifest.revision,
            "deploymentEnvironment": "dev",
        },
        "timings": {
            "prerequisitesMs": 18000,
            "installMs": 3400,
            "apiReadyMs": 9000,
            "runtimeReadyMs": 271000,
            "releaseTestMs": 4200,
        },
    }


def request_entry(index: int, **overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "requestId": f"v1-s3-006-pr2-request-{index:03d}",
        "status": 200,
        "adapterKind": "real",
        "modelIdentifier": MODEL_IDENTIFIER,
        "promptTokens": 18,
        "completionTokens": 42,
        "totalTokens": 60,
    }
    entry.update(overrides)
    return entry


def record_entry(index: int, pod_name: str, **overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "podName": pod_name,
        "requestId": f"v1-s3-006-pr2-request-{index:03d}",
        "event": names.EVENT_REQUEST_COMPLETED,
        "outcome": names.OUTCOME_SUCCESS,
        "httpStatus": 200,
        "adapterKind": "real",
        "modelIdentifier": MODEL_IDENTIFIER,
        "modelRevision": load_manifest().revision,
        "runtimeId": "llama.cpp llama-server",
        "durationMs": 8123,
    }
    entry.update(overrides)
    return entry


def observations_document() -> dict[str, Any]:
    """Ten successful requests, alternating between the two ready replicas."""
    pods = (API_POD_ONE, API_POD_TWO)
    return {
        "startedAt": "2026-09-08T12:00:00Z",
        "endedAt": "2026-09-08T12:04:30Z",
        "elapsedMs": 270000,
        "requests": [request_entry(index) for index in range(1, 11)],
        "records": [record_entry(index, pods[index % 2]) for index in range(1, 11)],
    }


def cleanup_document() -> dict[str, Any]:
    return {
        "releaseUninstalled": True,
        "driverRemoved": True,
        "residueObjects": 0,
        "helmReleaseAbsent": True,
        "namespaceSurvives": True,
        "claimsBefore": 1,
        "claimsAfter": 1,
        "uninstallMs": 12000,
    }


def artifact_root(
    tmp_path: Path,
    *,
    capacity: Mapping[str, Any] | None = None,
    facts: Mapping[str, Any] | None = None,
    observations: Mapping[str, Any] | None = None,
    cleanup: Mapping[str, Any] | None = None,
) -> Path:
    """Write the collected documents where the descriptor says they must be."""
    certification = multi_replica.load_multi_replica_certification()
    for document, member in (
        (capacity, certification.capacity_file),
        (facts, certification.facts_file),
        (observations, certification.observations_file),
        (cleanup, certification.cleanup_file),
    ):
        if document is None:
            continue
        target = tmp_path / member
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return tmp_path


def loaded() -> multi_replica.MultiReplicaCertification:
    return multi_replica.load_multi_replica_certification()


def refused(document: Mapping[str, Any], tmp_path: Path) -> str:
    """Load a mutated descriptor from a temporary file and return the refusal."""
    path = tmp_path / "descriptor.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(core.CertificationError) as caught:
        multi_replica.load_multi_replica_certification(path)
    return str(caught.value)


def mutated(**sections: Mapping[str, Any]) -> dict[str, Any]:
    document = copy.deepcopy(DESCRIPTOR)
    for section, members in sections.items():
        document[section].update(members)
    return document


# --------------------------------------------------------------------------
# The descriptor loads, and says what it is
# --------------------------------------------------------------------------


def test_the_committed_descriptor_validates() -> None:
    certification = loaded()

    assert certification.certification_id == multi_replica.EXPECTED_ID
    assert certification.certification_level == "C2"
    assert certification.evidence_label == "local real Kubernetes"
    assert certification.release.api_replicas >= multi_replica.MINIMUM_REPLICAS
    assert certification.distribution.minimum_distinct_replicas >= 2


def test_the_planned_request_identifiers_are_derived_rather_than_listed() -> None:
    plan = loaded().distribution

    assert plan.request_ids[0] == f"{plan.request_id_prefix}-001"
    assert len(plan.request_ids) == plan.request_count
    assert len(set(plan.request_ids)) == plan.request_count


def test_every_planned_identifier_is_one_the_api_would_accept() -> None:
    """A request identifier the API replaces cannot correlate anything.

    `inferops.api.identifiers` validates a supplied identifier and silently
    generates a fresh one when it does not match. A prefix that produced an
    identifier outside that pattern would leave every record naming a UUID this
    workflow never sent, and the run would fail at correlation for a reason
    that has nothing to do with replicas.
    """
    from inferops.api.identifiers import IDENTIFIER

    plan = loaded().distribution
    for request_id in plan.request_ids:
        assert IDENTIFIER.fullmatch(request_id) is not None, request_id
    assert IDENTIFIER.fullmatch(plan.correlation_id) is not None


def test_the_two_certifications_describe_one_release(tmp_path: Path) -> None:
    single = core.load_certification()
    certification = loaded()

    assert certification.release.name == single.release.name
    assert certification.release.namespace == single.release.namespace
    assert certification.release.api_service_name == single.release.api_service_name
    assert certification.model_cache == single.model_cache
    assert certification.result_file != single.result_file
    assert certification.diagnostics_file != single.diagnostics_file


@pytest.mark.parametrize(
    ("section", "member", "value", "expected"),
    (
        ("release", "apiReplicas", 1, "at least 2 API replicas"),
        ("release", "namespace", "other-release", "a release the single-replica"),
        ("release", "profile", "mock", "a release the single-replica"),
        ("release", "name", "somethingelse", "a release the single-replica"),
        ("cluster", "name", "someone-elses", "a cluster the single-replica"),
        ("distribution", "mechanism", "response-header", "correlation mechanism"),
        ("distribution", "minimumDistinctReplicas", 3, "more replicas than it"),
        ("distribution", "driverImage", "busybox:1.37.0", "named by digest"),
        ("distribution", "path", "/v1/completions", "not a served route"),
        ("distribution", "prompt", "two\nlines", "must be one line"),
        ("capacity", "peakMemoryBytes", 1, "below the memory the same pods"),
        ("readiness", "distributionBudgetMs", 1000, "cannot contain the request"),
        ("readiness", "installBudgetMs", 1, "disagree about a budget"),
        ("evidence", "retainGeneratedText", True, "evidence location is unsafe"),
        ("evidence", "resultFile", "k8s-real-inference.json", "location is unsafe"),
        ("evidence", "factsFile", ".artifacts/elsewhere.json", "location is unsafe"),
        ("cleanup", "removesPrerequisites", True, "neither the prerequisites"),
        ("cleanup", "removesCluster", True, "neither the prerequisites"),
        ("cleanup", "removesRequestDriver", False, "must remove the release"),
        ("cleanup", "uninstallsRelease", False, "must remove the release"),
        ("prerequisites", "requiresCapacityPreflight", False, "waive a prerequisite"),
        ("assertions", "requirePerReplicaCorrelation", False, "waive a real"),
        ("assertions", "requireEveryReplicaReady", False, "waive a real"),
        ("assertions", "requireEveryRequestSuccessful", False, "waive a real"),
        ("modelCache", "requireArtifactHashCompared", False, "how the model cache"),
    ),
)
def test_the_descriptor_refuses_a_weakened_member(
    section: str, member: str, value: Any, expected: str, tmp_path: Path
) -> None:
    """Each of these is a way the record could claim more than a run measured."""
    message = refused(mutated(**{section: {member: value}}), tmp_path)

    assert expected in message, message


def test_a_descriptor_sending_fewer_requests_than_replicas_is_refused(
    tmp_path: Path,
) -> None:
    """Unreachable at two replicas, and a rule a wider profile would need.

    With two API replicas the minimum distinct count is also two and the request
    count may not be below two, so the only way to reach this refusal is to raise
    all three -- which is exactly the edit a future three-replica profile makes.
    """
    document = mutated(
        release={"apiReplicas": 3},
        distribution={"minimumDistinctReplicas": 3, "requestCount": 2},
    )

    assert "fewer requests than the replicas" in refused(document, tmp_path)


def test_a_descriptor_with_an_unknown_member_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(DESCRIPTOR)
    document["distribution"]["retries"] = 3

    assert "missing or unsupported" in refused(document, tmp_path)


def test_a_descriptor_that_lists_no_limitations_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(DESCRIPTOR)
    document["limitations"] = []

    assert "names nothing" in refused(document, tmp_path)


# --------------------------------------------------------------------------
# The descriptor against the records that already decide it
# --------------------------------------------------------------------------


def resources(section: Mapping[str, Any]) -> tuple[int, int, int]:
    """One resource block as (request millicores, request bytes, limit bytes)."""

    def quantity(value: str) -> int:
        text = str(value)
        for suffix, factor in (("Gi", 1024**3), ("Mi", 1024**2), ("Ki", 1024)):
            if text.endswith(suffix):
                return int(float(text[: -len(suffix)]) * factor)
        return int(float(text))

    def millicores(value: str) -> int:
        text = str(value)
        if text.endswith("m"):
            return int(text[:-1])
        return int(float(text) * 1000)

    return (
        millicores(section["requests"]["cpu"]),
        quantity(section["requests"]["memory"]),
        quantity(section["limits"]["memory"]),
    )


def test_the_declared_capacity_is_the_charts_own_resources_times_the_replicas() -> None:
    """A capacity gate computed from stale figures passes a host that is too small.

    The chart decides what one API pod and one runtime pod request; the
    descriptor decides how many of each this profile installs. The product is
    what has to be free before anything is created, and nothing but this check
    keeps the two in step.
    """
    certification = loaded()
    capacity = certification.capacity
    release = certification.release

    api_cpu, api_memory, api_limit = resources(CHART_VALUES["api"]["resources"])
    runtime_cpu, runtime_memory, runtime_limit = resources(
        CHART_VALUES["runtime"]["resources"]
    )
    verify_cpu, verify_memory, _ = resources(
        CHART_VALUES["model"]["integrity"]["resources"]
    )
    driver_cpu, driver_memory, driver_limit = resources(
        CHART_VALUES["tests"]["resources"]
    )

    # A pod's effective request is the larger of its containers together and its
    # largest init container alone, because the init container runs first and by
    # itself.
    runtime_pod_cpu = max(runtime_cpu, verify_cpu)
    runtime_pod_memory = max(runtime_memory, verify_memory)

    assert capacity.requested_cpu_millis == (
        release.api_replicas * api_cpu
        + release.runtime_replicas * runtime_pod_cpu
        + driver_cpu
    )
    assert capacity.requested_memory_bytes == (
        release.api_replicas * api_memory
        + release.runtime_replicas * runtime_pod_memory
        + driver_memory
    )
    assert capacity.peak_memory_bytes == (
        release.api_replicas * api_limit
        + release.runtime_replicas * runtime_limit
        + driver_limit
    )


def test_the_engine_minimums_are_the_ones_lib_sh_already_enforces() -> None:
    """One tier, stated in one place. ADR 0001 D7 decides it and `lib.sh` holds it."""
    capacity = loaded().capacity

    assert capacity.minimum_engine_memory_bytes == int(
        lib_constant("INFEROPS_MIN_ENGINE_MEM_BYTES")
    )
    assert capacity.minimum_engine_cpus == int(lib_constant("INFEROPS_MIN_ENGINE_CPUS"))


def test_the_cluster_target_is_the_one_these_scripts_operate() -> None:
    certification = loaded()

    assert certification.cluster_name == lib_constant("INFEROPS_CLUSTER_NAME")
    assert certification.cluster_context == kube_context()
    assert certification.node_image_digest == lib_constant("INFEROPS_NODE_IMAGE_DIGEST")
    assert certification.release.name == lib_constant("INFEROPS_RELEASE_NAME")
    assert certification.release.namespace == lib_constant("INFEROPS_RELEASE_NAMESPACE")


def test_the_request_driver_reuses_the_pin_the_chart_already_carries() -> None:
    """One BusyBox pin, not several. The chart's own test image is that pin."""
    plan = loaded().distribution
    chart_test_image = CHART_VALUES["tests"]["image"]

    assert plan.driver_image == (
        f"{chart_test_image['repository']}@{chart_test_image['digest']}"
    )


def test_the_driver_wears_the_policy_identity_the_chart_wrote_a_rule_for() -> None:
    """The release-test component label is what the committed policy describes.

    The default-deny selects every pod carrying the release's name and instance,
    so a driver labelled anything else would either be denied its egress on a
    policy-enforcing plugin or fall outside the API's ingress rule. The chart
    already renders one egress allowance describing an in-cluster client of both
    Services, and this is it.
    """
    plan = loaded().distribution
    policy = [
        document
        for document in rendered_objects()
        if document.get("kind") == "NetworkPolicy"
        and document.get("metadata", {}).get("name", "").endswith("-release-test")
    ]
    assert len(policy) == 1
    selector = policy[0]["spec"]["podSelector"]["matchLabels"]

    assert selector["app.kubernetes.io/component"] == plan.driver_component


def test_the_service_and_workload_names_are_the_ones_the_chart_renders() -> None:
    certification = loaded()
    release = certification.release
    service = rendered("Service", "platform-api")
    deployment = rendered("Deployment", "platform-api")
    runtime = rendered("Deployment", "serving-runtime")

    assert release.api_service_name == service["metadata"]["name"]
    assert release.api_service_port == service["spec"]["ports"][0]["port"]
    assert release.api_deployment_name == deployment["metadata"]["name"]
    assert release.runtime_deployment_name == runtime["metadata"]["name"]
    assert release.api_component == "platform-api"
    assert release.runtime_component == "serving-runtime"


def test_the_request_path_is_a_route_the_api_actually_serves() -> None:
    assert loaded().distribution.path == CHAT_COMPLETIONS_PATH


def test_the_rollout_budgets_are_the_charts_progress_deadlines() -> None:
    budgets = loaded().budgets

    assert budgets.api_rollout_ms == (
        CHART_VALUES["api"]["lifecycle"]["progressDeadlineSeconds"] * 1000
    )
    assert budgets.runtime_rollout_ms == (
        CHART_VALUES["runtime"]["lifecycle"]["progressDeadlineSeconds"] * 1000
    )


def test_the_prompt_names_nothing_private() -> None:
    """A committed prompt is published text, and it is checked as such."""
    prompt = loaded().distribution.prompt

    assert "InferOps-Planning" not in prompt
    assert ":\\" not in prompt and "/home/" not in prompt
    assert prompt.strip() == prompt


# --------------------------------------------------------------------------
# Capacity: what refuses before anything is installed
# --------------------------------------------------------------------------


def test_a_capable_host_produces_no_findings(tmp_path: Path) -> None:
    certification = loaded()
    root = artifact_root(tmp_path, capacity=capacity_facts_document())
    facts = multi_replica.load_capacity_facts(certification, repo_root=root)

    assert multi_replica.assess_capacity(certification, facts) == ()
    multi_replica.require_capacity(certification, facts)


@pytest.mark.parametrize(
    ("override", "resource"),
    (
        ({"engine_cpus": 2}, "container engine processors"),
        ({"engine_memoryBytes": 2 * 1024**3}, "container engine memory"),
        ({"cluster_allocatableCpuMillis": 1000}, "uncommitted cluster processor"),
        (
            {"cluster_allocatableMemoryBytes": 2 * 1024**3},
            "uncommitted cluster memory",
        ),
    ),
)
def test_each_shortfall_is_found_and_named(
    override: dict[str, Any], resource: str, tmp_path: Path
) -> None:
    certification = loaded()
    root = artifact_root(tmp_path, capacity=capacity_facts_document(**override))
    facts = multi_replica.load_capacity_facts(certification, repo_root=root)

    findings = multi_replica.assess_capacity(certification, facts)

    assert [finding.resource for finding in findings] == [resource]
    assert findings[0].remedy
    with pytest.raises(multi_replica.CapacityUnmet) as caught:
        multi_replica.require_capacity(certification, facts)
    assert caught.value.stage == multi_replica.STAGE_CAPACITY


def test_every_shortfall_is_reported_at_once(tmp_path: Path) -> None:
    """A preflight that stopped at the first one costs a model load per attempt."""
    certification = loaded()
    root = artifact_root(
        tmp_path,
        capacity=capacity_facts_document(
            engine_cpus=1,
            engine_memoryBytes=1024**3,
            cluster_allocatableCpuMillis=100,
            cluster_allocatableMemoryBytes=1024**3,
        ),
    )
    facts = multi_replica.load_capacity_facts(certification, repo_root=root)

    assert len(multi_replica.assess_capacity(certification, facts)) == 4


def test_a_cluster_whose_capacity_is_already_committed_is_refused(
    tmp_path: Path,
) -> None:
    """Allocatable is not free. What is already requested is already spent."""
    certification = loaded()
    root = artifact_root(
        tmp_path,
        capacity=capacity_facts_document(cluster_committedMemoryBytes=11 * 1024**3),
    )
    facts = multi_replica.load_capacity_facts(certification, repo_root=root)

    findings = multi_replica.assess_capacity(certification, facts)

    assert [finding.resource for finding in findings] == ["uncommitted cluster memory"]


def test_unreadable_capacity_facts_refuse_at_the_capacity_stage(
    tmp_path: Path,
) -> None:
    certification = loaded()
    target = tmp_path / certification.capacity_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("not json", encoding="utf-8")

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_capacity_facts(certification, repo_root=tmp_path)

    assert caught.value.stage == multi_replica.STAGE_CAPACITY


# --------------------------------------------------------------------------
# The cluster facts are held to the descriptor rather than trusted
# --------------------------------------------------------------------------


def test_the_collected_facts_load(tmp_path: Path) -> None:
    certification = loaded()
    root = artifact_root(tmp_path, facts=facts_document())

    facts = multi_replica.load_cluster_facts(certification, repo_root=root)

    assert facts.ready_pods("platform-api") == (API_POD_ONE, API_POD_TWO)
    assert facts.release_revision == 1


def mutate_facts(**changes: Any) -> dict[str, Any]:
    document = facts_document()
    for path, value in changes.items():
        cursor: Any = document
        members = path.split("__")
        for member in members[:-1]:
            cursor = cursor[int(member)] if member.isdigit() else cursor[member]
        last = members[-1]
        if last.isdigit():
            cursor[int(last)] = value
        else:
            cursor[last] = value
    return document


@pytest.mark.parametrize(
    ("document", "stage", "expected"),
    (
        (
            mutate_facts(cluster__name="someone-elses-cluster"),
            multi_replica.STAGE_PREREQUISITES,
            "a cluster this certification does not name",
        ),
        (
            mutate_facts(cluster__nodeImageDigest="sha256:" + "0" * 64),
            multi_replica.STAGE_PREREQUISITES,
            "not the pinned one",
        ),
        (
            mutate_facts(release__namespace="inferops-other"),
            multi_replica.STAGE_RELEASE,
            "not the one this certification describes",
        ),
        (
            mutate_facts(release__status="pending-install"),
            multi_replica.STAGE_RELEASE,
            "rather than deployed",
        ),
        (
            mutate_facts(release__testPassed=False),
            multi_replica.STAGE_READINESS,
            "in-cluster connection test did not pass",
        ),
        (
            mutate_facts(configuration__modelRevision="0" * 40),
            multi_replica.STAGE_RELEASE,
            "not the pinned one",
        ),
        (
            mutate_facts(configuration__modelIdentifier="mock-model"),
            multi_replica.STAGE_RELEASE,
            "mock identity metadata",
        ),
        (
            mutate_facts(modelCache__artifactHashCompared=False),
            multi_replica.STAGE_RELEASE,
            "did not compare the model artifact",
        ),
        (
            mutate_facts(modelCache__mountReadOnly=False),
            multi_replica.STAGE_RELEASE,
            "not mounted read-only",
        ),
        (
            mutate_facts(timings__runtimeReadyMs=10**9),
            multi_replica.STAGE_READINESS,
            "over the",
        ),
    ),
)
def test_the_facts_are_refused_when_they_disagree_with_the_descriptor(
    document: dict[str, Any], stage: str, expected: str, tmp_path: Path
) -> None:
    certification = loaded()
    root = artifact_root(tmp_path, facts=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_cluster_facts(certification, repo_root=root)

    assert caught.value.stage == stage
    assert expected in str(caught.value)


def test_a_release_that_ran_one_api_replica_is_refused(tmp_path: Path) -> None:
    """The single-replica fallback, refused where it would actually appear.

    A descriptor asking for one replica is refused at load. This is the other
    half: a descriptor asking for two and a cluster that ran one.
    """
    document = facts_document()
    document["workloads"][0]["replicasDesired"] = 1
    document["workloads"][0]["replicasReady"] = 1
    document["replicas"] = document["replicas"][1:]
    root = artifact_root(tmp_path, facts=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_cluster_facts(loaded(), repo_root=root)

    assert "runs 1 replicas and this certification requests 2" in str(caught.value)


def test_a_replica_that_never_became_ready_is_refused(tmp_path: Path) -> None:
    document = facts_document()
    document["replicas"][1]["ready"] = False
    root = artifact_root(tmp_path, facts=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_cluster_facts(loaded(), repo_root=root)

    assert "never became ready" in str(caught.value)
    assert caught.value.stage == multi_replica.STAGE_READINESS


def test_a_summary_count_cannot_stand_in_for_the_pods(tmp_path: Path) -> None:
    """`status.readyReplicas` is a controller's count, not a per-replica fact."""
    document = facts_document()
    document["replicas"] = [
        replica for replica in document["replicas"] if replica["podName"] != API_POD_TWO
    ]
    root = artifact_root(tmp_path, facts=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_cluster_facts(loaded(), repo_root=root)

    assert "reported 1 platform API pods" in str(caught.value)


def test_a_pod_named_twice_is_refused(tmp_path: Path) -> None:
    """Two entries for one pod would make one replica look like two."""
    document = facts_document()
    document["replicas"][1]["podName"] = API_POD_ONE
    root = artifact_root(tmp_path, facts=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_cluster_facts(loaded(), repo_root=root)

    assert "one pod more than once" in str(caught.value)


def test_a_replica_of_an_undescribed_component_is_refused(tmp_path: Path) -> None:
    document = facts_document()
    document["replicas"].append(
        {
            "podName": "inferops-inferops-llm-test-connection",
            "component": "release-test",
            "ready": True,
            "readyAfterMs": 900,
            "restarts": 0,
        }
    )
    root = artifact_root(tmp_path, facts=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_cluster_facts(loaded(), repo_root=root)

    assert "a component this certification does not describe" in str(caught.value)


def test_a_replica_slower_than_its_rollout_budget_is_refused(tmp_path: Path) -> None:
    document = facts_document()
    document["replicas"][0]["readyAfterMs"] = 10**9
    root = artifact_root(tmp_path, facts=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_cluster_facts(loaded(), repo_root=root)

    assert "over the" in str(caught.value)


def test_a_tag_pinned_image_is_refused(tmp_path: Path) -> None:
    document = facts_document()
    document["workloads"][0]["images"] = ["localhost/inferops-api:latest"]
    root = artifact_root(tmp_path, facts=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_cluster_facts(loaded(), repo_root=root)

    assert "not digest-pinned" in str(caught.value)


# --------------------------------------------------------------------------
# The request set
# --------------------------------------------------------------------------


def test_the_collected_observations_load(tmp_path: Path) -> None:
    certification = loaded()
    root = artifact_root(tmp_path, observations=observations_document())

    observations = multi_replica.load_observations(certification, repo_root=root)

    assert len(observations.requests) == certification.distribution.request_count
    assert observations.started_at.endswith("Z")


@pytest.mark.parametrize(
    ("change", "expected"),
    (
        ({"status": 503}, "answered 503 rather than 200"),
        ({"adapterKind": "stub"}, "adapter kind rather than"),
        ({"modelIdentifier": "mock-model"}, "mock identity metadata"),
        ({"completionTokens": 0}, "absent or inconsistent"),
        ({"totalTokens": 999}, "absent or inconsistent"),
    ),
)
def test_one_bad_answer_stops_the_request_set(
    change: dict[str, Any], expected: str, tmp_path: Path
) -> None:
    document = observations_document()
    document["requests"][3].update(change)
    root = artifact_root(tmp_path, observations=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_observations(loaded(), repo_root=root)

    assert expected in str(caught.value)
    assert caught.value.stage == multi_replica.STAGE_DISTRIBUTION


def test_a_request_set_that_is_not_the_planned_one_is_refused(tmp_path: Path) -> None:
    document = observations_document()
    document["requests"] = document["requests"][:-1]
    root = artifact_root(tmp_path, observations=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_observations(loaded(), repo_root=root)

    assert "did not send exactly the planned request set" in str(caught.value)


def test_a_repeated_request_identifier_is_refused(tmp_path: Path) -> None:
    document = observations_document()
    document["requests"][1]["requestId"] = document["requests"][0]["requestId"]
    root = artifact_root(tmp_path, observations=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_observations(loaded(), repo_root=root)

    assert "more than once" in str(caught.value)


def test_a_request_set_over_its_budget_is_refused(tmp_path: Path) -> None:
    document = observations_document()
    document["elapsedMs"] = 10**9
    root = artifact_root(tmp_path, observations=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_observations(loaded(), repo_root=root)

    assert "over the" in str(caught.value)


# --------------------------------------------------------------------------
# The correlation, which is the claim this PR adds
# --------------------------------------------------------------------------


def correlated(
    tmp_path: Path, observations: Mapping[str, Any] | None = None
) -> tuple[multi_replica.ReplicaDistribution, ...]:
    certification = loaded()
    root = artifact_root(
        tmp_path,
        facts=facts_document(),
        observations=dict(observations or observations_document()),
    )
    facts = multi_replica.load_cluster_facts(certification, repo_root=root)
    seen = multi_replica.load_observations(certification, repo_root=root)
    return multi_replica.correlate(certification, facts, seen)


def test_successful_requests_correlate_to_the_replicas_that_recorded_them(
    tmp_path: Path,
) -> None:
    distribution = correlated(tmp_path)

    assert [replica.pod_name for replica in distribution] == [
        API_POD_ONE,
        API_POD_TWO,
    ]
    assert sum(replica.request_count for replica in distribution) == 10
    assert all(replica.ready_after_ms > 0 for replica in distribution)


def test_a_request_no_replica_recorded_is_a_missing_correlation(
    tmp_path: Path,
) -> None:
    """The failure the story names: a request count is not a distribution."""
    document = observations_document()
    document["records"] = document["records"][:-1]

    with pytest.raises(core.CertificationFailed) as caught:
        correlated(tmp_path, document)

    assert "nothing correlates them to a serving replica" in str(caught.value)
    assert caught.value.stage == multi_replica.STAGE_CORRELATION


def test_every_record_landing_on_one_replica_is_not_a_multi_replica_result(
    tmp_path: Path,
) -> None:
    """A run that certified this would be certifying a single-replica release."""
    document = observations_document()
    document["records"] = [record_entry(index, API_POD_ONE) for index in range(1, 11)]

    with pytest.raises(core.CertificationFailed) as caught:
        correlated(tmp_path, document)

    assert "reached 1 distinct serving replicas" in str(caught.value)


def test_a_request_two_replicas_both_claim_is_refused(tmp_path: Path) -> None:
    document = observations_document()
    document["records"].append(record_entry(1, API_POD_TWO))
    document["records"].append(record_entry(2, API_POD_ONE))

    with pytest.raises(core.CertificationFailed) as caught:
        correlated(tmp_path, document)

    assert "was recorded by two replicas" in str(caught.value)


def test_a_record_from_a_pod_that_was_never_a_ready_replica_is_refused(
    tmp_path: Path,
) -> None:
    document = observations_document()
    document["records"][0]["podName"] = "inferops-inferops-llm-somethingelse"

    with pytest.raises(core.CertificationFailed) as caught:
        correlated(tmp_path, document)

    assert "not one of the ready platform API replicas" in str(caught.value)


@pytest.mark.parametrize(
    ("change", "expected"),
    (
        ({"outcome": "server-error"}, "recorded with outcome"),
        ({"httpStatus": 500}, "recorded with outcome"),
        ({"adapterKind": "stub"}, "adapter kind on the certified path"),
        ({"runtimeId": "mock-runtime"}, "mock identity metadata"),
        ({"modelRevision": "0" * 40}, "model revision that is not the pinned one"),
        ({"modelIdentifier": "another-model"}, "not configured with"),
        ({"event": "request.refused"}, "rather than a completion"),
    ),
)
def test_a_record_that_does_not_describe_a_real_completion_is_refused(
    change: dict[str, Any], expected: str, tmp_path: Path
) -> None:
    document = observations_document()
    document["records"][2].update(change)

    with pytest.raises(core.CertificationFailed) as caught:
        correlated(tmp_path, document)

    assert expected in str(caught.value)


# --------------------------------------------------------------------------
# Cleanup
# --------------------------------------------------------------------------


def test_the_cleanup_facts_load(tmp_path: Path) -> None:
    root = artifact_root(tmp_path, cleanup=cleanup_document())

    facts = multi_replica.load_cleanup_facts(loaded(), repo_root=root)

    assert facts.release_uninstalled and facts.driver_removed


@pytest.mark.parametrize(
    ("change", "expected"),
    (
        ({"releaseUninstalled": False}, "was not uninstalled"),
        ({"driverRemoved": False}, "request driver was left"),
        ({"residueObjects": 2}, "survived the uninstall"),
        ({"helmReleaseAbsent": False}, "survived the uninstall"),
        ({"namespaceSurvives": False}, "must outlive the release"),
        ({"claimsAfter": 0}, "claim count changed"),
        ({"uninstallMs": 10**9}, "over the"),
    ),
)
def test_an_unsafe_cleanup_is_refused(
    change: dict[str, Any], expected: str, tmp_path: Path
) -> None:
    document = cleanup_document()
    document.update(change)
    root = artifact_root(tmp_path, cleanup=document)

    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.load_cleanup_facts(loaded(), repo_root=root)

    assert expected in str(caught.value)
    assert caught.value.stage == multi_replica.STAGE_CLEANUP


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


def certified(tmp_path: Path, *, with_cleanup: bool) -> dict[str, Any]:
    certification = loaded()
    root = artifact_root(
        tmp_path,
        capacity=capacity_facts_document(),
        facts=facts_document(),
        observations=observations_document(),
        cleanup=cleanup_document(),
    )
    result = multi_replica.certify_multi_replica(
        certification, confirmed=True, repo_root=root
    )
    if with_cleanup:
        result = multi_replica.MultiReplicaResult(
            certification=result.certification,
            capacity=result.capacity,
            facts=result.facts,
            observations=result.observations,
            distribution=result.distribution,
            cleanup=multi_replica.load_cleanup_facts(certification, repo_root=root),
        )
    return multi_replica.result_document(result)


def test_the_record_states_what_was_requested_and_what_was_reached(
    tmp_path: Path,
) -> None:
    document = certified(tmp_path, with_cleanup=False)
    replicas = document["replicas"]

    assert replicas["apiRequested"] == 2
    assert replicas["apiReady"] == 2
    assert replicas["distinctReplicasReached"] == 2
    assert len(replicas["perReplicaReadiness"]) == 3
    assert document["distribution"]["successfulRequests"] == 10
    assert len(document["distribution"]["perReplica"]) == 2
    assert document["evidenceLabel"] == "local real Kubernetes"


def test_the_record_carries_the_limitations_rather_than_leaving_them_to_a_reader(
    tmp_path: Path,
) -> None:
    document = certified(tmp_path, with_cleanup=False)

    assert document["limitations"] == list(loaded().limitations)
    assert any("high availability" in line for line in document["limitations"])
    assert any("one replica" in line for line in document["limitations"])


def test_the_record_names_the_time_window_and_the_resource_profile(
    tmp_path: Path,
) -> None:
    document = certified(tmp_path, with_cleanup=False)

    assert document["distribution"]["startedAt"] == "2026-09-08T12:00:00Z"
    assert document["distribution"]["endedAt"] == "2026-09-08T12:04:30Z"
    assert document["resources"]["sufficient"] is True
    assert document["resources"]["cluster"]["freeMemoryBytes"] > 0


def test_a_record_written_before_the_teardown_says_cleanup_has_not_happened(
    tmp_path: Path,
) -> None:
    """The assertions run first so a failure leaves the release standing."""
    assert certified(tmp_path, with_cleanup=False)["cleanup"] == {"performed": False}


def test_the_second_write_adds_the_cleanup_outcome(tmp_path: Path) -> None:
    cleanup = certified(tmp_path, with_cleanup=True)["cleanup"]

    assert cleanup["performed"] is True
    assert cleanup["requestDriverRemoved"] is True
    assert cleanup["prerequisitesRemoved"] is False
    assert cleanup["clusterRemoved"] is False


def test_the_record_carries_no_prompt_and_no_completion(tmp_path: Path) -> None:
    document = certified(tmp_path, with_cleanup=True)
    serialised = json.dumps(document)

    assert loaded().distribution.prompt not in serialised
    assert document["distribution"]["generatedTextRetained"] is False


def test_the_record_names_the_single_replica_certification_it_extends(
    tmp_path: Path,
) -> None:
    document = certified(tmp_path, with_cleanup=False)

    assert document["provenance"]["singleReplicaCertificationRef"] == (
        multi_replica.EXPECTED_SINGLE_REPLICA_REF
    )
    assert document["provenance"]["modelHashComparedInCluster"] == "true"


def test_an_unconfirmed_run_observes_nothing(tmp_path: Path) -> None:
    with pytest.raises(core.CertificationFailed) as caught:
        multi_replica.certify_multi_replica(
            loaded(), confirmed=False, repo_root=tmp_path
        )

    assert "--confirm-real-kubernetes" in str(caught.value)


def test_a_redirected_evidence_directory_is_refused(tmp_path: Path) -> None:
    """The same guard `core.py` applies, applied to the second workflow's files."""
    directory = tmp_path / ".cache" / "inferops"
    directory.mkdir(parents=True)
    try:
        (directory / "certification").symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - unprivileged host
        pytest.skip("this host does not allow creating a symlink")

    with pytest.raises(core.EvidenceUnwritable):
        multi_replica.MultiReplicaEvidence(loaded(), repo_root=tmp_path)


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------


def test_check_contacts_nothing_and_succeeds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["check"]) == EXIT_OK
    assert "not started" in capsys.readouterr().out


def test_a_capacity_shortfall_has_its_own_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "This host is too small" and "the platform did not certify" are different.

    A caller that could not tell them apart would report a laptop as a defect.
    """
    root = artifact_root(tmp_path, capacity=capacity_facts_document(engine_cpus=1))
    monkeypatch.setattr(multi_replica, "REPO_ROOT", root)

    assert main(["preflight", "--confirm-real-kubernetes"]) == EXIT_CAPACITY


def test_a_failed_correlation_exits_as_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = observations_document()
    document["records"] = [record_entry(index, API_POD_ONE) for index in range(1, 11)]
    root = artifact_root(
        tmp_path,
        capacity=capacity_facts_document(),
        facts=facts_document(),
        observations=document,
    )
    monkeypatch.setattr(multi_replica, "REPO_ROOT", root)

    assert main(["certify", "--confirm-real-kubernetes"]) == EXIT_FAILED
    diagnostics = json.loads(
        (
            root
            / ".cache/inferops/certification/k8s-multi-replica-inference-diagnostics.json"
        ).read_text(encoding="utf-8")
    )
    assert diagnostics["outcome"] == "not-certified"
    assert diagnostics["stage"] == multi_replica.STAGE_CORRELATION


def test_an_unconfirmed_certify_is_refused_and_leaves_no_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(multi_replica, "REPO_ROOT", tmp_path)

    assert main(["certify"]) == EXIT_FAILED
    assert not (tmp_path / ".cache").exists()


def test_a_descriptor_that_does_not_load_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        multi_replica, "MULTI_REPLICA_CERTIFICATION_PATH", tmp_path / "absent.json"
    )
    monkeypatch.setattr(
        "tools.kubernetes_certification.multi_replica_cli."
        "load_multi_replica_certification",
        lambda: multi_replica.load_multi_replica_certification(
            tmp_path / "absent.json"
        ),
    )

    assert main(["check"]) == EXIT_REFUSED


# --------------------------------------------------------------------------
# The programs the script embeds are the programs the reader accepts
# --------------------------------------------------------------------------


def embedded(marker: str) -> str:
    """One heredoc program the operating script embeds, as source.

    Extracted rather than duplicated, because a copy here would test the copy.
    These are the parts that turn real command output into the documents
    everything downstream reads, and reading both halves is exactly what failed
    to catch the type mismatch independent review found in PR1.
    """
    opening = f"<<'{marker}'\n"
    start = SCRIPT_TEXT.index(opening) + len(opening)
    return SCRIPT_TEXT[start : SCRIPT_TEXT.index(f"\n{marker}\n", start)]


def run_embedded(
    marker: str, environment: Mapping[str, str], target: Path
) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-", str(target)],
        input=embedded(marker),
        capture_output=True,
        text=True,
        env={"PATH": "", "SYSTEMROOT": "", **environment},
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(target.read_text(encoding="utf-8"))


def test_the_embedded_capacity_writer_produces_what_the_reader_accepts(
    tmp_path: Path,
) -> None:
    """Kubernetes quantities are their own grammar, and this is where it is read."""
    nodes = {
        "items": [
            {
                "metadata": {"name": "inferops-dev-control-plane"},
                "spec": {},
                "status": {"allocatable": {"cpu": "8", "memory": "12000000Ki"}},
            },
            {
                "metadata": {"name": "cordoned"},
                "spec": {"unschedulable": True},
                "status": {"allocatable": {"cpu": "4", "memory": "4Gi"}},
            },
        ]
    }
    pods = {
        "items": [
            {
                "status": {"phase": "Running"},
                "spec": {
                    "containers": [
                        {"resources": {"requests": {"cpu": "100m", "memory": "70Mi"}}},
                        {"resources": {"requests": {"cpu": "250m"}}},
                    ],
                    "initContainers": [
                        {"resources": {"requests": {"cpu": "500m", "memory": "1Gi"}}}
                    ],
                },
            },
            {
                # Finished, so it holds nothing.
                "status": {"phase": "Succeeded"},
                "spec": {
                    "containers": [
                        {"resources": {"requests": {"cpu": "2", "memory": "4Gi"}}}
                    ]
                },
            },
            {
                # No requests at all, which is not an error.
                "status": {"phase": "Running"},
                "spec": {"containers": [{"resources": {}}]},
            },
        ]
    }
    target = tmp_path / "capacity.json"

    document = run_embedded(
        "CAPACITY_PYTHON",
        {
            "INFEROPS_CAPACITY_ENGINE_CPUS": "8",
            "INFEROPS_CAPACITY_ENGINE_MEMORY": str(12 * 1024**3),
            "INFEROPS_CAPACITY_NODES": json.dumps(nodes),
            "INFEROPS_CAPACITY_PODS": json.dumps(pods),
        },
        target,
    )

    assert document["cluster"]["schedulableNodes"] == 1
    assert document["cluster"]["allocatableCpuMillis"] == 8000
    assert document["cluster"]["allocatableMemoryBytes"] == 12000000 * 1024
    # 500m init against 350m of containers, and 1Gi init against 70Mi.
    assert document["cluster"]["committedCpuMillis"] == 500
    assert document["cluster"]["committedMemoryBytes"] == 1024**3

    certification = loaded()
    root = artifact_root(tmp_path, capacity=document)
    facts = multi_replica.load_capacity_facts(certification, repo_root=root)

    assert facts.free_cpu_millis == 7500


def test_the_embedded_facts_writer_produces_what_the_reader_accepts(
    tmp_path: Path,
) -> None:
    manifest = load_manifest()
    digest = manifest.sha256.removeprefix("sha256:")
    verification = (
        "set -eu\n"
        "artifact='/models/Qwen3-1.7B-Q8_0.gguf'\n"
        f'echo "{digest}  $artifact" | sha256sum -c -\n'
    )
    pods = {
        "items": [
            {
                "metadata": {
                    "name": API_POD_TWO,
                    "labels": {"app.kubernetes.io/component": "platform-api"},
                },
                "status": {
                    "phase": "Running",
                    "startTime": "2026-09-08T12:00:00Z",
                    "conditions": [
                        {
                            "type": "Ready",
                            "status": "True",
                            "lastTransitionTime": "2026-09-08T12:00:05Z",
                        }
                    ],
                    "containerStatuses": [{"restartCount": 0}],
                },
            },
            {
                "metadata": {
                    "name": API_POD_ONE,
                    "labels": {"app.kubernetes.io/component": "platform-api"},
                },
                "status": {
                    "phase": "Running",
                    "startTime": "2026-09-08T12:00:00Z",
                    "conditions": [
                        {
                            "type": "Ready",
                            "status": "True",
                            "lastTransitionTime": "2026-09-08T12:00:04Z",
                        }
                    ],
                    "containerStatuses": [{"restartCount": 1}],
                },
            },
            {
                "metadata": {
                    "name": RUNTIME_POD,
                    "labels": {"app.kubernetes.io/component": "serving-runtime"},
                },
                "status": {
                    "phase": "Running",
                    "startTime": "2026-09-08T12:00:00Z",
                    "conditions": [
                        {
                            "type": "Ready",
                            "status": "True",
                            "lastTransitionTime": "2026-09-08T12:04:31Z",
                        }
                    ],
                    "containerStatuses": [{"restartCount": 0}],
                },
            },
            {
                # The `helm test` hook pod carries the release's instance label
                # and is not a serving replica.
                "metadata": {
                    "name": "inferops-inferops-llm-test-connection",
                    "labels": {"app.kubernetes.io/component": "release-test"},
                },
                "status": {"phase": "Succeeded", "conditions": []},
            },
        ]
    }
    environment = {
        "INFEROPS_FACT_CLUSTER_NAME": lib_constant("INFEROPS_CLUSTER_NAME"),
        "INFEROPS_FACT_CONTEXT": kube_context(),
        "INFEROPS_FACT_SERVER_VERSION": "v1.34.8",
        "INFEROPS_FACT_NODE_DIGEST": lib_constant("INFEROPS_NODE_IMAGE_DIGEST"),
        "INFEROPS_FACT_HELM": "v3.19.0+g3d8990f",
        "INFEROPS_FACT_KUBECTL": "v1.36.1",
        "INFEROPS_FACT_TERRAFORM": json.dumps({"terraform_version": "1.15.8"}),
        "INFEROPS_FACT_RELEASE_NAME": "inferops",
        "INFEROPS_FACT_NAMESPACE": "inferops-release",
        # The real shape: `helm list -o json` is an array whose revision is a
        # string.
        "INFEROPS_FACT_RELEASE_JSON": json.dumps(
            [
                {
                    "name": "inferops",
                    "namespace": "inferops-release",
                    "revision": "1",
                    "status": "deployed",
                    "chart": "inferops-llm-0.2.0",
                }
            ]
        ),
        "INFEROPS_FACT_PROFILE": "real",
        "INFEROPS_FACT_SERVICE_VERSION": "",
        "INFEROPS_FACT_MODEL_IDENTIFIER": MODEL_IDENTIFIER,
        "INFEROPS_FACT_MODEL_REVISION": manifest.revision,
        "INFEROPS_FACT_ENVIRONMENT": "dev",
        "INFEROPS_FACT_API_NAME": "inferops-inferops-llm",
        "INFEROPS_FACT_API_COMPONENT": "platform-api",
        "INFEROPS_FACT_API_IMAGES": f" {API_IMAGE}",
        "INFEROPS_FACT_API_DESIRED": "2",
        "INFEROPS_FACT_API_READY": "2",
        "INFEROPS_FACT_RUNTIME_NAME": "inferops-inferops-llm-runtime",
        "INFEROPS_FACT_RUNTIME_COMPONENT": "serving-runtime",
        "INFEROPS_FACT_RUNTIME_IMAGES": f"{VERIFY_IMAGE} {RUNTIME_IMAGE}",
        "INFEROPS_FACT_RUNTIME_DESIRED": "1",
        "INFEROPS_FACT_RUNTIME_READY": "1",
        "INFEROPS_FACT_CLAIM_NAME": "inferops-model-cache",
        "INFEROPS_FACT_VOLUME_READ_ONLY": "true",
        "INFEROPS_FACT_MOUNT_READ_ONLY": "true",
        "INFEROPS_FACT_INIT_CONTAINERS": "verify-model",
        "INFEROPS_FACT_INIT_COMMAND": verification,
        "INFEROPS_FACT_MODEL_SHA256": manifest.sha256,
        "INFEROPS_FACT_PODS_JSON": json.dumps(pods),
        "INFEROPS_FACT_API_COMPONENT_NAME": "platform-api",
        "INFEROPS_FACT_RUNTIME_COMPONENT_NAME": "serving-runtime",
        "INFEROPS_FACT_PREREQUISITES_MS": "18000",
        "INFEROPS_FACT_INSTALL_MS": "3400",
        "INFEROPS_FACT_API_READY_MS": "9000",
        "INFEROPS_FACT_RUNTIME_READY_MS": "271000",
        "INFEROPS_FACT_RELEASE_TEST_MS": "4200",
        "INFEROPS_FACT_RELEASE_TEST_PASSED": "true",
    }
    target = tmp_path / "facts.json"

    document = run_embedded("FACTS_PYTHON", environment, target)

    assert [replica["podName"] for replica in document["replicas"]] == [
        API_POD_ONE,
        API_POD_TWO,
        RUNTIME_POD,
    ]
    assert document["replicas"][0]["readyAfterMs"] == 4000
    assert document["replicas"][0]["restarts"] == 1
    assert document["replicas"][2]["readyAfterMs"] == 271000

    certification = loaded()
    root = artifact_root(tmp_path, facts=document)
    facts = multi_replica.load_cluster_facts(certification, repo_root=root)

    assert facts.release_revision == 1
    assert facts.ready_pods("platform-api") == (API_POD_ONE, API_POD_TWO)


def test_the_embedded_observations_writer_produces_what_the_reader_accepts(
    tmp_path: Path,
) -> None:
    manifest = load_manifest()
    driver_log = "\n".join(
        [
            "Connecting to inferops-inferops-llm:8090",
            *(
                "inferops-request "
                f"requestId=v1-s3-006-pr2-request-{index:03d} status=200 "
                "adapterKind=real "
                f"modelIdentifier={MODEL_IDENTIFIER} promptTokens=18 "
                "completionTokens=42 totalTokens=60"
                for index in range(1, 11)
            ),
        ]
    )
    pods = (API_POD_ONE, API_POD_TWO)
    records = [
        json.dumps(
            {
                "timestamp": "2026-09-08T12:00:10.500Z",
                "level": "info",
                names.EVENT: names.EVENT_REQUEST_COMPLETED,
                names.SERVICE_NAME: "inferops-api",
                names.CORRELATION_ID: "v1-s3-006-pr2-k8s-multi-replica-inference",
                names.POD_NAME: pods[index % 2],
                names.REQUEST_ID: f"v1-s3-006-pr2-request-{index:03d}",
                names.OUTCOME: names.OUTCOME_SUCCESS,
                names.HTTP_STATUS: 200,
                names.ADAPTER_KIND: "real",
                names.MODEL_ID: MODEL_IDENTIFIER,
                names.MODEL_REVISION: manifest.revision,
                names.RUNTIME_ID: "llama.cpp llama-server",
                names.DURATION_MS: 8123.5,
            },
            separators=(",", ":"),
        )
        for index in range(1, 11)
    ]
    noise = [
        "not json at all",
        json.dumps(
            {
                names.EVENT: names.EVENT_REQUEST_RECEIVED,
                names.REQUEST_ID: "v1-s3-006-pr2-request-001",
                names.POD_NAME: API_POD_ONE,
            }
        ),
        json.dumps(
            {
                names.EVENT: names.EVENT_REQUEST_COMPLETED,
                names.REQUEST_ID: "somebody-elses-request",
                names.POD_NAME: API_POD_ONE,
            }
        ),
    ]
    target = tmp_path / "observations.json"

    document = run_embedded(
        "OBSERVATIONS_PYTHON",
        {
            "INFEROPS_OBSERVE_DRIVER_LOG": driver_log,
            "INFEROPS_OBSERVE_RECORDS_LOG": "\n".join(records + noise),
            "INFEROPS_OBSERVE_STARTED_AT": "2026-09-08T12:00:00Z",
            "INFEROPS_OBSERVE_ENDED_AT": "2026-09-08T12:04:30Z",
            "INFEROPS_OBSERVE_ELAPSED_MS": "270000",
            "INFEROPS_OBSERVE_PREFIX": "v1-s3-006-pr2-request",
        },
        target,
    )

    assert len(document["requests"]) == 10
    # Ten completions, and neither the `request.received` record, the record
    # about somebody else's request, nor the line that is not JSON.
    assert len(document["records"]) == 10
    assert document["records"][0]["durationMs"] == 8123

    certification = loaded()
    root = artifact_root(tmp_path, facts=facts_document(), observations=document)
    facts = multi_replica.load_cluster_facts(certification, repo_root=root)
    observations = multi_replica.load_observations(certification, repo_root=root)
    distribution = multi_replica.correlate(certification, facts, observations)

    assert len(distribution) == 2


def test_the_observation_writer_reads_the_field_names_the_catalog_publishes() -> None:
    """The writer copies the names because it runs as a standalone program.

    A rename in `inferops.telemetry.names` and not here would produce a writer
    that silently collected nothing, and a run that failed at correlation for a
    reason that has nothing to do with replicas.
    """
    source = embedded("OBSERVATIONS_PYTHON")

    for name in (
        names.POD_NAME,
        names.REQUEST_ID,
        names.EVENT,
        names.OUTCOME,
        names.HTTP_STATUS,
        names.ADAPTER_KIND,
        names.MODEL_ID,
        names.MODEL_REVISION,
        names.RUNTIME_ID,
        names.DURATION_MS,
        names.EVENT_REQUEST_COMPLETED,
    ):
        assert f'"{name}"' in source, name


def test_the_embedded_cleanup_writer_produces_what_the_reader_accepts(
    tmp_path: Path,
) -> None:
    target = tmp_path / "cleanup.json"

    document = run_embedded(
        "CLEANUP_PYTHON",
        {
            "INFEROPS_CLEANUP_RELEASE_UNINSTALLED": "true",
            "INFEROPS_CLEANUP_DRIVER_REMOVED": "true",
            "INFEROPS_CLEANUP_RESIDUE": "0",
            "INFEROPS_CLEANUP_HELM_ABSENT": "true",
            "INFEROPS_CLEANUP_NAMESPACE": "true",
            "INFEROPS_CLEANUP_CLAIMS_BEFORE": "1",
            "INFEROPS_CLEANUP_CLAIMS_AFTER": "1",
            "INFEROPS_CLEANUP_UNINSTALL_MS": "12000",
        },
        target,
    )

    root = artifact_root(tmp_path, cleanup=document)
    facts = multi_replica.load_cleanup_facts(loaded(), repo_root=root)

    assert facts.uninstall_ms == 12000


# --------------------------------------------------------------------------
# The operating script's own safety properties
# --------------------------------------------------------------------------


def script_positions(*fragments: str) -> list[int]:
    positions = []
    for fragment in fragments:
        assert fragment in SCRIPT_TEXT, fragment
        positions.append(SCRIPT_TEXT.index(fragment))
    return positions


def descriptor_reads() -> tuple[list[str], list[str], list[str]]:
    start = SCRIPT_TEXT.index("read_descriptor \\")
    arguments = SCRIPT_TEXT[start : SCRIPT_TEXT.index(')"; then', start)]
    fields = [word for word in arguments.replace("\\", " ").split() if "." in word]

    block_end = SCRIPT_TEXT.index('} <<<"${descriptor_fields}"')
    variables = re.findall(r"^  read -r (\w+)$", SCRIPT_TEXT[:block_end], re.M)

    loop_start = SCRIPT_TEXT.index("for field in ")
    guard = (
        SCRIPT_TEXT[loop_start : SCRIPT_TEXT.index("; do", loop_start)]
        .replace("for field in", "")
        .replace("\\", " ")
        .split()
    )
    return fields, variables, guard


def test_the_descriptor_read_and_the_assignment_agree() -> None:
    """Positional reads shift silently when one list grows and the other does not.

    The script asks for N descriptor fields and assigns them to N variables in
    order. A field added to one list and not the other moves every value after
    it -- a budget receives a Service name, a name receives a number -- and no
    linter sees it.
    """
    fields, variables, guard = descriptor_reads()

    assert len(fields) == len(variables), list(zip(fields, variables, strict=False))
    assert set(guard) == set(variables), set(guard).symmetric_difference(variables)


def test_the_script_holds_every_number_it_computes_with_to_being_a_number() -> None:
    """A descriptor field reaching shell arithmetic is checked where it is used."""
    start = SCRIPT_TEXT.index("for number in ")
    checked = set(
        SCRIPT_TEXT[start : SCRIPT_TEXT.index("; do", start)]
        .replace("for number in", "")
        .replace("\\", " ")
        .split()
    )
    arithmetic = set(re.findall(r"\$\(\((\w+) / 1000\)\)", SCRIPT_TEXT))

    assert arithmetic
    assert arithmetic <= checked, arithmetic - checked


def test_the_capacity_preflight_happens_before_anything_is_installed() -> None:
    preflight, prerequisites, install = script_positions(
        'python -m "${INFEROPS_MULTI_MODULE}" preflight',
        'bash "${INFEROPS_ROOT}/scripts/environment/terraform-prerequisites.sh"',
        "inferops::helm install",
    )

    assert preflight < prerequisites < install


def test_the_assertions_happen_before_the_teardown() -> None:
    """A failed assertion has to leave the release standing to be looked at."""
    certify, remove_driver, uninstall = script_positions(
        'python -m "${INFEROPS_MULTI_MODULE}" certify',
        'inferops::section "Removing the request driver"',
        "inferops::helm uninstall",
    )

    assert certify < remove_driver < uninstall


def test_the_replica_counts_are_set_from_the_descriptor() -> None:
    """A values file saying `replicaCount: 1` must not decide this profile."""
    assert '--set "api.replicaCount=${api_replicas}"' in SCRIPT_TEXT
    assert '--set "runtime.replicaCount=${runtime_replicas}"' in SCRIPT_TEXT


def test_the_script_refuses_a_descriptor_asking_for_one_replica() -> None:
    """Restated where the count is handed to Helm, not only in the validator."""
    assert '[ "${api_replicas}" -ge 2 ]' in SCRIPT_TEXT
    assert "does not reduce the count to fit a host" in SCRIPT_TEXT


def test_the_install_creates_no_namespace_and_does_not_wait() -> None:
    install = re.search(r"inferops::helm install.*?--timeout", SCRIPT_TEXT, re.S)
    assert install is not None

    assert "--create-namespace" not in install.group(0)
    assert "--wait" not in install.group(0)


@pytest.mark.parametrize(
    "forbidden",
    (
        "terraform destroy",
        "kind delete",
        "delete namespace",
        "delete pvc",
        "delete persistentvolumeclaim",
    ),
)
def test_the_script_removes_nothing_it_does_not_own(forbidden: str) -> None:
    """The prerequisites, the claim, and the cluster outlive every release."""
    assert forbidden not in SCRIPT_TEXT


def test_the_driver_manifest_is_bounded_and_unprivileged() -> None:
    """The one object this workflow creates outside the chart, read as a manifest."""
    manifest = SCRIPT_TEXT[
        SCRIPT_TEXT.index("cat <<DRIVER") : SCRIPT_TEXT.index("\nDRIVER\n")
    ]

    assert "backoffLimit: 0" in manifest
    assert "restartPolicy: Never" in manifest
    assert "activeDeadlineSeconds: $((distribution_budget_ms / 1000))" in manifest
    assert "automountServiceAccountToken: false" in manifest
    assert "readOnlyRootFilesystem: true" in manifest
    assert "allowPrivilegeEscalation: false" in manifest
    assert "runAsNonRoot: true" in manifest
    assert "drop:\n                - ALL" in manifest
    assert "medium: Memory" in manifest
    assert "image: ${driver_image}" in manifest


def test_the_driver_never_prints_a_response_body() -> None:
    """The generated text is not this workflow's to retain, anywhere.

    The body is written to the pod's own scratch directory, matched, and left
    there. A `cat` of it would put a completion into `kubectl logs`, into
    `.artifacts/`, and from there into anything that reads them.
    """
    manifest = SCRIPT_TEXT[
        SCRIPT_TEXT.index("cat <<DRIVER") : SCRIPT_TEXT.index("\nDRIVER\n")
    ]

    assert "cat /scratch/body.json" not in manifest
    assert "-O -" not in manifest
    assert "rm -f /scratch/body.json" in manifest


def test_the_driver_matches_the_extension_member_the_api_serialises() -> None:
    """A rename of the extension member must break this, not silently pass."""
    manifest = SCRIPT_TEXT[
        SCRIPT_TEXT.index("cat <<DRIVER") : SCRIPT_TEXT.index("\nDRIVER\n")
    ]

    assert f'"{EXTENSION_ADAPTER_KIND}":' in manifest
    assert multi_replica.adapter_kind_marker().rstrip('"') in manifest


def test_the_single_replica_workflow_is_untouched_and_still_its_own_command() -> None:
    """PR1's certification stays independently runnable, and says the same thing."""
    single = SINGLE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "k8s-real-inference.v1.json" in single
    assert "k8s-multi-replica-inference" not in single
    assert "multi_replica" not in single


def test_a_failed_driver_is_noticed_rather_than_waited_out() -> None:
    """`kubectl wait --for=condition=complete` cannot see a Job that failed.

    It watches one condition becoming true and has no notion of "finished either
    way". The driver is `backoffLimit: 0` and `restartPolicy: Never`, so any
    crash of its shell fails the Job at once -- and that call would have blocked
    for the whole distribution budget before reporting it. Half an hour to report
    a failure that happened in the first second is a hang with a timeout on it,
    not a bounded failure. Independent review found this before the workflow was
    ever run.
    """
    assert '--for=condition=complete "job/' not in SCRIPT_TEXT
    assert '*"Complete=True"*)' in SCRIPT_TEXT
    assert '*"Failed=True"*)' in SCRIPT_TEXT
    assert 'driver_outcome="failed"' in SCRIPT_TEXT
    # And an unanswered query is not a Job that is still running.
    assert 'if ! driver_state="$(driver_conditions)"; then' in SCRIPT_TEXT


def test_a_driver_that_would_not_go_is_reported_as_itself() -> None:
    """A leftover driver Job would otherwise be misread as release residue.

    It carries this release's instance label on purpose -- that is what makes the
    release's own NetworkPolicy describe it -- and that is the label the residue
    check after the uninstall selects on, with `jobs` in its resource list. A
    delete that was accepted but had not finished would be counted as an object
    of the release surviving its own uninstall, and the run would fail blaming
    the teardown for this workflow's own artifact.
    """
    removal = SCRIPT_TEXT[
        SCRIPT_TEXT.index("remove_driver() {") : SCRIPT_TEXT.index("on_exit() {")
    ]

    # The delete's status decides the function's, and `driver_created` is cleared
    # only when the object is actually gone.
    assert "--ignore-not-found --wait" in removal
    assert "|| true" not in removal
    assert "    driver_created=0\n    return 0" in removal
    assert "  return 1\n}" in removal

    # The success path refuses and the already-failing trap continues, and
    # both say so rather than going quiet. Both are written as
    # `if ! remove_driver; then` rather than as `remove_driver || inferops::…`,
    # because a line that both removes an object and prints about it is a line
    # the lifecycle safety suite reads as a deletion -- and it is right to.
    assert SCRIPT_TEXT.count("if ! remove_driver; then") == 2
    assert 'inferops::fail "the request driver Job' in SCRIPT_TEXT
    assert 'inferops::warn "the request driver Job' in SCRIPT_TEXT

    # And neither message spells a bare `kubectl delete`. The deletion rules
    # in tests/architecture/test_cluster_lifecycle_safety.py have no message
    # exemption, and widening one to fit a message would be weakening a
    # deletion rule for convenience.
    printed = [
        line
        for line in SCRIPT_TEXT.splitlines()
        if line.strip().startswith(("inferops::warn", "inferops::fail"))
    ]
    assert not [line for line in printed if "kubectl delete" in line]


def published_figures() -> tuple[str, str, str]:
    """The capacity figures as the documents are required to state them.

    Mebibytes rather than gibibytes, and derived from the descriptor rather than
    written out, because the first published version of these sentences rounded
    2,320 MiB to "2.25 GiB" -- a percent low, in three files, with nothing
    comparing prose to data. Independent review found that too.
    """
    capacity = loaded().capacity
    return (
        f"{capacity.requested_cpu_millis:,} millicores",
        f"{capacity.requested_memory_bytes // 1024**2:,} MiB",
        f"{capacity.peak_memory_bytes // 1024**2:,} MiB",
    )


@pytest.mark.parametrize(
    "relative",
    (
        "docs/serving/kubernetes-multi-replica-certification.md",
        "docs/proof/serving/v1-s3-006-pr2-validation.md",
        "CHANGELOG.md",
    ),
)
def test_every_published_capacity_figure_is_the_descriptors_own(
    relative: str,
) -> None:
    """A rounded figure in prose is a claim, and it drifted before it was checked."""
    published = (REPO_ROOT / relative).read_text(encoding="utf-8")

    for figure in published_figures():
        assert figure in published, (relative, figure)


def test_the_ownership_document_accounts_for_the_object_this_workflow_creates() -> None:
    """One `batch/v1` Job is created by neither Terraform nor the chart.

    It is transient in the same sense the `helm test` hook pod is, so it is not a
    row in any ownership table -- and a resource in the namespace that no
    document mentions at all is exactly what that document exists to prevent.
    """
    published = (
        REPO_ROOT / "docs" / "architecture" / "resource-ownership.md"
    ).read_text(encoding="utf-8")

    assert "kubernetes-multi-replica-certification.sh" in published
    assert "Three procedures now install and uninstall the same release" in published
    assert "batch/v1 Job" in published


def test_the_procedure_document_states_what_the_record_does_not_support() -> None:
    published = PROCEDURE_PATH.read_text(encoding="utf-8")

    for expected in (
        "high availability",
        "kube-proxy",
        "port-forward",
        "single-replica",
        "k8s.pod.name",
    ):
        assert expected in published, expected


def test_the_procedure_document_names_no_private_path() -> None:
    published = PROCEDURE_PATH.read_text(encoding="utf-8")

    assert "InferOps-Planning" not in published
    assert "15.InferOps-Workspace" not in published
