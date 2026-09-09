"""The Kubernetes certification descriptor, its guards, and its operating script.

Every check here reads committed files, drives the workflow through injected HTTP
and clock seams, or executes the one program the script embeds. No cluster is
contacted, no release is installed, no forward is opened, no model byte is read,
and no `kubectl`, `helm`, or `terraform` command runs. These results are
`local-static` and synthetic.

Two of the checks below deserve their names said out loud, because independent
review found the defects they now defend against and neither was reachable by
reading either file alone:

*The facts round trip.* The script collects what the cluster reported into a JSON
document and `tools.kubernetes_certification` reads it back. Both halves looked
right and disagreed anyway -- `helm list -o json` reports a release revision as a
**string**, and the reader demanded an integer, so a real run would have failed at
the readiness stage for a reason that had nothing to do with readiness. So the
embedded writer is extracted from the script and executed here against a
representative environment, and its output is fed to the reader that consumes it.

*The descriptor read alignment.* The script asks for a list of descriptor fields
and assigns them positionally. A field added to one list and not the other
silently shifts every value after it, and no linter sees it. The two lists are
compared.

What none of this establishes is that any of it works. Whether a release
installs, whether a model loads inside its budget, whether a completion returns,
and whether a teardown leaves no residue are runtime questions, and only an
authorized run of `scripts/environment/kubernetes-certification.sh certify
--confirm-real-kubernetes` answers them.
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.api.surface import (
    CORRELATION_ID_HEADER,
    READY_PATH,
    REQUEST_ID_HEADER,
)
from tools.kubernetes_certification import core
from tools.kubernetes_certification.__main__ import main
from tools.model_acquisition import load_manifest
from tools.runtime_configuration import load_runtime_profile
from tools.runtime_packaging import load_runtime_package

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "environment" / "kubernetes-certification.sh"
LIB_PATH = REPO_ROOT / "scripts" / "environment" / "lib.sh"
CHART_VALUES_PATH = REPO_ROOT / "charts" / "inferops-llm" / "values.yaml"
REAL_VALUES_PATH = REPO_ROOT / "charts" / "inferops-llm" / "ci" / "real-values.yaml"
RENDERED_REAL_PATH = (
    REPO_ROOT / "charts" / "inferops-llm" / "ci" / "rendered" / "real.expected.yaml"
)
PROCEDURE_PATH = (
    REPO_ROOT / "docs" / "serving" / "kubernetes-real-inference-certification.md"
)
TERRAFORM_VARIABLES_PATH = (
    REPO_ROOT / "infra" / "terraform" / "environments" / "local" / "variables.tf"
)

CERTIFICATION_DOCUMENT: dict[str, Any] = json.loads(
    core.CERTIFICATION_PATH.read_text(encoding="utf-8")
)

SCRIPT_TEXT = SCRIPT_PATH.read_text(encoding="utf-8")
LIB_TEXT = LIB_PATH.read_text(encoding="utf-8")
CHART_VALUES: dict[str, Any] = yaml.safe_load(
    CHART_VALUES_PATH.read_text(encoding="utf-8")
)

MODEL_IDENTIFIER = "qwen3-1-7b-q8-0"
RUNTIME_NAME = "llama.cpp llama-server"
RUNTIME_VERSION = "b10588-70adb1b4c"
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
        if document["kind"] == kind
        and document["metadata"]["labels"].get("app.kubernetes.io/component")
        == component
    ]
    assert len(matches) == 1, f"expected one {kind} for {component}, found {matches}"
    return matches[0]


def _mutated(path: tuple[str, ...], value: object) -> dict[str, Any]:
    document = copy.deepcopy(CERTIFICATION_DOCUMENT)
    cursor: Any = document
    for member in path[:-1]:
        cursor = cursor[member]
    cursor[path[-1]] = value
    return document


def _written(tmp_path: Path, document: Mapping[str, Any]) -> Path:
    candidate = tmp_path / "k8s-real-inference.v1.json"
    candidate.write_text(json.dumps(document), encoding="utf-8")
    return candidate


# -- the facts an authorized run would collect -------------------------------


def facts_document(**overrides: Any) -> dict[str, Any]:
    """One well-formed collection, in the shape the operating script writes.

    `release.revision` is a **string** here, because that is what
    `helm list -o json` emits. Fabricating an integer is what let a real defect
    through review once already.
    """
    document: dict[str, Any] = {
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
                "replicasDesired": 1,
                "replicasReady": 1,
            },
            {
                "name": "inferops-inferops-llm-runtime",
                "component": "serving-runtime",
                "images": [VERIFY_IMAGE, RUNTIME_IMAGE],
                "replicasDesired": 1,
                "replicasReady": 1,
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
            "modelRevision": load_manifest().revision,
            "deploymentEnvironment": "dev",
        },
        "timings": {
            "prerequisitesMs": 4_200,
            "installMs": 1_800,
            "apiReadyMs": 9_500,
            "runtimeReadyMs": 358_735,
            "releaseTestMs": 6_000,
        },
    }
    for path, value in overrides.items():
        cursor: Any = document
        members = path.split(".")
        for member in members[:-1]:
            cursor = cursor[member]
        cursor[members[-1]] = value
    return document


def facts_root(tmp_path: Path, document: Mapping[str, Any]) -> Path:
    """Write the facts where the descriptor says they must be, and return the root."""
    target = tmp_path / core.EXPECTED_FACTS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document), encoding="utf-8")
    return tmp_path


# -- the answers a real release would give -----------------------------------


def models_body(
    *,
    adapter_kind: str = "real",
    runtime_name: str = RUNTIME_NAME,
    model_revision: str | None = None,
    token_usage: bool | None = True,
    model_identifier: str = MODEL_IDENTIFIER,
    entries: int = 1,
) -> dict[str, Any]:
    capabilities: dict[str, Any] = {"streaming": False, "multiModel": False}
    if token_usage is not None:
        capabilities["tokenUsage"] = token_usage
    return {
        "object": "list",
        "data": [
            {"id": model_identifier, "object": "model", "created": 1}
            for _ in range(entries)
        ],
        "x_inferops": {
            "adapterKind": adapter_kind,
            "contractVersion": "inferops.io/v1alpha1",
            "runtime": {
                "name": runtime_name,
                "version": RUNTIME_VERSION,
                "modelRevision": model_revision or load_manifest().revision,
            },
            "capabilities": capabilities,
        },
    }


def completion_body(
    *,
    adapter_kind: str = "real",
    content: str = "Kubernetes orchestrates containers across a cluster.",
    prompt_tokens: int = 11,
    completion_tokens: int = 9,
    total_tokens: int | None = None,
    model_identifier: str = MODEL_IDENTIFIER,
) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": model_identifier,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": (
                prompt_tokens + completion_tokens
                if total_tokens is None
                else total_tokens
            ),
        },
        "x_inferops": {
            "adapterKind": adapter_kind,
            "modelRef": model_identifier,
            "contractVersion": "inferops.io/v1alpha1",
        },
    }


class Answers:
    """Recorded GET and POST answers standing in for the forwarded Service."""

    def __init__(
        self,
        *,
        models: Mapping[str, Any] | None = None,
        completion: Mapping[str, Any] | None = None,
        models_status: int = 200,
        completion_status: int = 200,
        ready_status: int = 200,
        echo_headers: bool = True,
    ) -> None:
        self.models = models_body() if models is None else models
        self.completion = completion_body() if completion is None else completion
        self.models_status = models_status
        self.completion_status = completion_status
        self.ready_status = ready_status
        self.echo_headers = echo_headers
        self.urls: list[str] = []
        self.bodies: list[Mapping[str, object]] = []

    def get(self, url: str, timeout_seconds: float) -> core.ApiResponse:
        del timeout_seconds
        self.urls.append(url)
        if url.endswith(READY_PATH):
            return core.ApiResponse(self.ready_status, {"status": "ready"}, {})
        return core.ApiResponse(self.models_status, self.models, {})

    def post(
        self,
        url: str,
        body: Mapping[str, object],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> core.ApiResponse:
        del timeout_seconds
        self.urls.append(url)
        self.bodies.append(body)
        echoed = dict(headers) if self.echo_headers else {}
        return core.ApiResponse(self.completion_status, self.completion, echoed)


# --------------------------------------------------------------------------
# The descriptor is the authority, and it agrees with what already decides it
# --------------------------------------------------------------------------


def test_the_committed_descriptor_loads() -> None:
    certification = core.load_certification()

    assert certification.certification_id == core.EXPECTED_ID
    assert certification.certification_level == "C2"
    assert certification.evidence_class == "local-real-cpu"
    assert certification.evidence_label == "local real Kubernetes"


def test_the_evidence_label_is_published_and_the_class_is_not_a_new_one() -> None:
    """A new label is not a new evidence class, and only one of the two is free.

    `docs/testing/certification.md` fixes the evidence classes and the ceiling
    each one carries. This workflow runs the real component on a contributor's
    own machine on CPU, which is `local-real-cpu` exactly as the composed C2 run
    is; what differs is that it ran through Kubernetes, and that is what the
    label says. Inventing a class here would have raised a ceiling by writing a
    string -- so the class is checked against the published set, and the label
    against the vocabulary the other documents publish, because an unregistered
    label is a word with no definition behind it.
    """
    certification = core.load_certification()
    published = json.loads(
        (REPO_ROOT / "docs/testing/test-strategy.v1alpha1.json").read_text(
            encoding="utf-8"
        )
    )
    classes = {entry["classId"] for entry in published["evidenceClasses"]}
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    boundary = (REPO_ROOT / "docs/serving/mock-and-real-boundary.md").read_text(
        encoding="utf-8"
    )

    assert certification.evidence_class in classes
    assert certification.evidence_label in contributing
    assert certification.evidence_label in boundary


def test_the_descriptor_names_the_cluster_these_scripts_operate() -> None:
    certification = core.load_certification()

    assert certification.cluster.name == lib_constant("INFEROPS_CLUSTER_NAME")
    assert certification.cluster.context == kube_context()


def test_the_descriptor_names_the_pinned_node_image() -> None:
    """`lib.sh` states the rule: a pin checked one way at creation and another
    way afterwards is two pins."""
    assert core.load_certification().cluster.node_image_digest == lib_constant(
        "INFEROPS_NODE_IMAGE_DIGEST"
    )


def test_the_descriptor_names_the_release_these_scripts_operate() -> None:
    certification = core.load_certification()

    assert certification.release.name == lib_constant("INFEROPS_RELEASE_NAME")
    assert certification.release.namespace == lib_constant("INFEROPS_RELEASE_NAMESPACE")
    assert certification.chart_ref == lib_constant("INFEROPS_CHART_PATH")
    assert certification.release.instance_selector == lib_constant(
        "INFEROPS_RELEASE_SELECTOR"
    ).replace("${INFEROPS_RELEASE_NAME}", certification.release.name)


def test_the_descriptor_names_the_objects_the_chart_actually_renders() -> None:
    """A Service name guessed rather than read is a forward to nothing."""
    certification = core.load_certification()

    assert (
        rendered("Service", "platform-api")["metadata"]["name"]
        == certification.release.api_service_name
    )
    assert (
        rendered("Deployment", "platform-api")["metadata"]["name"]
        == certification.release.api_deployment_name
    )
    assert (
        rendered("Deployment", "serving-runtime")["metadata"]["name"]
        == certification.release.runtime_deployment_name
    )
    assert (
        rendered("ConfigMap", "runtime-configuration")["metadata"]["name"]
        == certification.release.config_map_name
    )


def test_the_descriptor_names_the_port_the_chart_publishes() -> None:
    assert (
        core.load_certification().release.api_service_port
        == CHART_VALUES["api"]["service"]["port"]
    )


def test_the_descriptor_names_the_components_the_chart_labels() -> None:
    certification = core.load_certification()
    labelled = {
        document["metadata"]["labels"].get("app.kubernetes.io/component")
        for document in rendered_objects()
        if document["kind"] == "Deployment"
    }

    named = {
        certification.release.api_component,
        certification.release.runtime_component,
    }
    assert named <= labelled, (
        f"the descriptor names a component the chart does not label: {named - labelled}"
    )
    # The chart renders one Deployment this certification is deliberately not
    # about. The collector observes the release; certifying it as part of the
    # serving path would be certifying the instrument along with the measurement.
    assert labelled - named == {"telemetry-collector"}, labelled - named


def test_the_descriptor_names_the_replica_count_the_chart_defaults_to() -> None:
    """This PR's whole boundary turns on this number, and it is written twice.

    A chart default raised to two would otherwise fail at run time, after a
    model load, rather than at build time.
    """
    certification = core.load_certification()

    assert certification.release.replicas == CHART_VALUES["api"]["replicaCount"]
    assert certification.release.replicas == CHART_VALUES["runtime"]["replicaCount"]


def test_the_descriptor_describes_the_profile_the_values_fixture_selects() -> None:
    values = yaml.safe_load(REAL_VALUES_PATH.read_text(encoding="utf-8"))

    assert core.load_certification().release.profile == values["profile"]


def test_the_descriptor_names_the_claim_terraform_provisions() -> None:
    """The chart mounts it and Terraform owns it. Three records, one name."""
    certification = core.load_certification()
    values = yaml.safe_load(REAL_VALUES_PATH.read_text(encoding="utf-8"))
    terraform = TERRAFORM_VARIABLES_PATH.read_text(encoding="utf-8")

    assert certification.model_cache.claim_name == values["model"]["cache"]["claimName"]
    assert f'default     = "{certification.model_cache.claim_name}"' in terraform


def test_the_descriptor_names_the_init_container_the_chart_renders() -> None:
    runtime = rendered("Deployment", "serving-runtime")
    names = {
        container["name"]
        for container in runtime["spec"]["template"]["spec"]["initContainers"]
    }

    assert core.load_certification().model_cache.verification_init_container in names


def test_the_readiness_budgets_are_the_charts_and_not_the_adapters() -> None:
    """The defect this test exists for, stated plainly.

    `runtime.startupBudgetMs` is how long the **adapter** waits for a runtime it
    started itself. The kubelet's startup probe budget is nearly twice that,
    because the chart's measurements do not fit inside the smaller number: a
    358,735 ms cold load was recorded, and a probe budgeted at 300,000 ms would
    have killed the container mid-load. A certification pinned to the adapter's
    figure reports a normal cold load as a failure.
    """
    budgets = core.load_certification().budgets
    runtime = CHART_VALUES["runtime"]
    api = CHART_VALUES["api"]

    assert budgets.runtime_startup_ms == runtime["probes"]["startup"]["budgetMs"]
    assert (
        budgets.runtime_rollout_ms
        == runtime["lifecycle"]["progressDeadlineSeconds"] * 1000
    )
    assert budgets.api_startup_ms == api["probes"]["startup"]["budgetMs"]
    assert budgets.api_rollout_ms == api["lifecycle"]["progressDeadlineSeconds"] * 1000
    assert budgets.runtime_startup_ms > load_runtime_package().startup_budget_ms


def test_a_measured_cold_load_fits_inside_the_runtime_budget() -> None:
    """The slowest load this repository has recorded, against the budget."""
    slowest_recorded_ms = 358_735

    assert core.load_certification().budgets.runtime_rollout_ms > slowest_recorded_ms


def test_the_request_budget_is_the_one_the_profile_publishes() -> None:
    assert (
        core.load_certification().request_timeout_ms
        == load_runtime_profile().request_budget_ms
    )


def test_the_procedure_the_descriptor_cites_exists() -> None:
    certification = core.load_certification()

    assert (REPO_ROOT / certification.procedure_ref).is_file()
    assert (REPO_ROOT / certification.certification_ref).is_file()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schemaVersion",), "inferops.io/v2"),
        (("certificationId",), "inferops-something-else"),
        (("certificationLevel",), "C3"),
        (("evidenceClass",), "production-experience"),
        (("evidenceLabel",), "production"),
        (("lane",), "default-checks"),
        (("chartRef",), "charts/other"),
        (("certificationRef",), "docs/testing/other.md"),
        (("procedureRef",), "docs/serving/other.md"),
    ],
)
def test_an_unsupported_identity_is_refused(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    with pytest.raises(core.CertificationError, match="identity is unsupported"):
        core.load_certification(_written(tmp_path, _mutated(path, value)))


@pytest.mark.parametrize(
    "member",
    [
        "requiresTerraformPrerequisites",
        "requiresTargetClusterAssertion",
        "requiresPinnedRuntimeImage",
        "requiresPinnedApiImage",
        "requiresVerifiedModelCache",
    ],
)
def test_a_waived_prerequisite_is_refused(tmp_path: Path, member: str) -> None:
    document = _mutated(("prerequisites", member), False)

    with pytest.raises(core.CertificationError, match="may not waive a prerequisite"):
        core.load_certification(_written(tmp_path, document))


@pytest.mark.parametrize(
    "member",
    [
        "requireUsageCounts",
        "requireNonEmptyContent",
        "requirePinnedModelRevision",
        "requireDigestPinnedImages",
        "requireEveryReplicaReady",
        "requireReleaseTest",
        "requirePinnedNodeImage",
    ],
)
def test_a_waived_real_assertion_is_refused(tmp_path: Path, member: str) -> None:
    document = _mutated(("assertions", member), False)

    with pytest.raises(core.CertificationError, match="may not waive a real assertion"):
        core.load_certification(_written(tmp_path, document))


@pytest.mark.parametrize(
    "member", ["requireReadOnlyMount", "requireArtifactHashCompared"]
)
def test_a_waived_model_cache_assertion_is_refused(tmp_path: Path, member: str) -> None:
    document = _mutated(("modelCache", member), False)

    with pytest.raises(core.CertificationError, match="model cache assertion"):
        core.load_certification(_written(tmp_path, document))


def test_a_namespace_outside_this_projects_prefix_is_refused(tmp_path: Path) -> None:
    """ADR 0001 (D5). The chart refuses it too; this refuses it before a
    kubeconfig is read, which is earlier and cheaper."""
    document = _mutated(("release", "namespace"), "default")

    with pytest.raises(core.CertificationError, match="inferops-"):
        core.load_certification(_written(tmp_path, document))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("release", "profile"), "mock"),
        (("assertions", "requiredAdapterKind"), "mock"),
    ],
)
def test_only_the_real_path_may_be_certified(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    with pytest.raises(core.CertificationError, match="only the real path"):
        core.load_certification(_written(tmp_path, _mutated(path, value)))


def test_an_empty_mock_marker_is_refused(tmp_path: Path) -> None:
    """The marker is what makes the mock refusal a refusal. An empty one would
    match nothing and the assertion would pass on every answer."""
    document = _mutated(("assertions", "prohibitedIdentitySubstring"), "")

    with pytest.raises(core.CertificationError, match="must be a string"):
        core.load_certification(_written(tmp_path, document))


def test_an_api_service_the_release_name_cannot_produce_is_refused(
    tmp_path: Path,
) -> None:
    document = _mutated(("release", "apiServiceName"), "somebody-elses-api")

    with pytest.raises(core.CertificationError, match="could produce"):
        core.load_certification(_written(tmp_path, document))


def test_a_node_image_named_by_tag_is_refused(tmp_path: Path) -> None:
    document = _mutated(("cluster", "nodeImageDigest"), "kindest/node:v1.34.8")

    with pytest.raises(core.CertificationError, match="named by digest"):
        core.load_certification(_written(tmp_path, document))


def test_a_startup_budget_below_the_adapters_is_refused(tmp_path: Path) -> None:
    """The chart's own rule: a kubelet that gives up first makes the adapter's
    budget unreachable."""
    document = _mutated(("readiness", "runtimeStartupBudgetMs"), 1_000)

    with pytest.raises(core.CertificationError, match="below the adapter's"):
        core.load_certification(_written(tmp_path, document))


@pytest.mark.parametrize("member", ["runtimeRolloutBudgetMs", "apiRolloutBudgetMs"])
def test_a_rollout_budget_below_its_startup_budget_is_refused(
    tmp_path: Path, member: str
) -> None:
    document = _mutated(("readiness", member), 1_000)

    with pytest.raises(core.CertificationError, match="below the startup budget"):
        core.load_certification(_written(tmp_path, document))


def test_a_request_budget_disagreeing_with_the_profile_is_refused(
    tmp_path: Path,
) -> None:
    document = _mutated(("request", "timeoutMs"), 1_000)

    with pytest.raises(core.CertificationError, match="budgets disagree"):
        core.load_certification(_written(tmp_path, document))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("request", "path"), "/v1/completions"),
        (("request", "modelsPath"), "/v1/model"),
        (("request", "readinessPath"), "/healthz"),
    ],
)
def test_a_request_path_that_is_not_a_served_route_is_refused(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    with pytest.raises(core.CertificationError, match="not a served route"):
        core.load_certification(_written(tmp_path, _mutated(path, value)))


def test_a_forward_off_loopback_is_refused_in_the_descriptor(tmp_path: Path) -> None:
    document = _mutated(("request", "host"), "0.0.0.0")

    with pytest.raises(core.CertificationError, match="stay on loopback"):
        core.load_certification(_written(tmp_path, document))


def test_a_multiline_prompt_is_refused(tmp_path: Path) -> None:
    document = _mutated(("request", "prompt"), "one\nturns into two")

    with pytest.raises(core.CertificationError, match="one line"):
        core.load_certification(_written(tmp_path, document))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("evidence", "directory"), "/tmp/inferops"),
        (("evidence", "factsFile"), "/etc/facts.json"),
        (("evidence", "retainGeneratedText"), True),
        (("evidence", "resultFile"), "../escape.json"),
        (("evidence", "diagnosticsFile"), "nested/diagnostics.json"),
    ],
)
def test_an_unsafe_evidence_location_is_refused(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    with pytest.raises(core.CertificationError, match="evidence location is unsafe"):
        core.load_certification(_written(tmp_path, _mutated(path, value)))


def test_a_run_that_keeps_its_release_is_refused(tmp_path: Path) -> None:
    document = _mutated(("cleanup", "uninstallsRelease"), False)

    with pytest.raises(core.CertificationError, match="must remove the release"):
        core.load_certification(_written(tmp_path, document))


@pytest.mark.parametrize("member", ["removesPrerequisites", "removesCluster"])
def test_a_run_that_would_remove_what_outlives_a_release_is_refused(
    tmp_path: Path, member: str
) -> None:
    """The namespace, the model cache claim, and the cluster are not this
    workflow's to remove -- and the claim holds weights that are re-downloaded
    over a transport this project does not authenticate."""
    document = _mutated(("cleanup", member), True)

    with pytest.raises(core.CertificationError, match="neither the prerequisites"):
        core.load_certification(_written(tmp_path, document))


def test_an_unknown_member_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(CERTIFICATION_DOCUMENT)
    document["evidence"]["uploadTo"] = "https://example.invalid"

    with pytest.raises(core.CertificationError, match="unsupported members"):
        core.load_certification(_written(tmp_path, document))


def test_an_unreadable_descriptor_is_refused(tmp_path: Path) -> None:
    with pytest.raises(core.CertificationError, match="unreadable"):
        core.load_certification(tmp_path / "missing.json")


# --------------------------------------------------------------------------
# The collected facts are held to the descriptor
# --------------------------------------------------------------------------


def test_well_formed_facts_are_accepted(tmp_path: Path) -> None:
    certification = core.load_certification()

    facts = core.load_cluster_facts(
        certification, repo_root=facts_root(tmp_path, facts_document())
    )

    assert facts.release_name == certification.release.name
    assert facts.release_revision == 1
    assert all(workload.fully_ready for workload in facts.workloads)


def test_a_helm_revision_reported_as_a_string_is_accepted(tmp_path: Path) -> None:
    """`helm list -o json` serialises a revision as `"1"`.

    Refusing it would fail a certification at the readiness stage for a reason
    that has nothing to do with readiness -- after the Terraform apply, the
    install, the model load, and the in-cluster test had all already happened.
    """
    facts = core.load_cluster_facts(
        core.load_certification(),
        repo_root=facts_root(tmp_path, facts_document(**{"release.revision": "3"})),
    )

    assert facts.release_revision == 3


@pytest.mark.parametrize("value", ["", "one", "1.5", 1.5, True, 0])
def test_a_revision_that_is_not_a_whole_number_is_refused(
    tmp_path: Path, value: object
) -> None:
    document = facts_document(**{"release.revision": value})

    with pytest.raises(core.CertificationFailed, match=re.escape("release.revision")):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_unreadable_facts_stop_the_run(tmp_path: Path) -> None:
    with pytest.raises(core.CertificationFailed, match="unreadable"):
        core.load_cluster_facts(core.load_certification(), repo_root=tmp_path)


def test_the_facts_are_read_from_where_the_descriptor_says(tmp_path: Path) -> None:
    """Not from wherever a caller points.

    The whole cluster half of the record is copied out of this file, so a path
    argument would make the base-URL guard decorative: a run could reach a real
    Service and describe an environment read from somewhere else entirely.
    """
    certification = core.load_certification()
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text(json.dumps(facts_document()), encoding="utf-8")

    assert certification.facts_path(tmp_path) == tmp_path / core.EXPECTED_FACTS_FILE
    with pytest.raises(core.CertificationFailed, match="unreadable"):
        core.load_cluster_facts(certification, repo_root=tmp_path)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("release.name", "somebody-elses-release"),
        ("release.namespace", "default"),
        ("release.profile", "mock"),
    ],
)
def test_facts_describing_another_release_stop_the_run(
    tmp_path: Path, path: str, value: str
) -> None:
    with pytest.raises(core.CertificationFailed) as raised:
        core.load_cluster_facts(
            core.load_certification(),
            repo_root=facts_root(tmp_path, facts_document(**{path: value})),
        )

    assert raised.value.stage == core.STAGE_RELEASE


@pytest.mark.parametrize(
    ("path", "value"),
    [("cluster.name", "somebody-elses-cluster"), ("cluster.context", "docker-desktop")],
)
def test_facts_describing_another_cluster_stop_the_run(
    tmp_path: Path, path: str, value: str
) -> None:
    with pytest.raises(core.CertificationFailed) as raised:
        core.load_cluster_facts(
            core.load_certification(),
            repo_root=facts_root(tmp_path, facts_document(**{path: value})),
        )

    assert raised.value.stage == core.STAGE_PREREQUISITES


def test_a_node_image_that_is_not_the_pinned_one_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"cluster.nodeImageDigest": "sha256:" + "ab" * 32})

    with pytest.raises(core.CertificationFailed, match="not the pinned one"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_a_release_that_is_not_deployed_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"release.status": "failed"})

    with pytest.raises(core.CertificationFailed, match="rather than deployed"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_a_release_missing_a_component_stops_the_run(tmp_path: Path) -> None:
    """A `mock` profile installs no runtime, and a run that certified one
    Deployment would be certifying the mock path with a real label."""
    document = facts_document()
    document["workloads"] = document["workloads"][:1]

    with pytest.raises(core.CertificationFailed, match="exactly the API and"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_a_relabelled_deployment_stops_the_run(tmp_path: Path) -> None:
    """The component label is queried from the cluster, so this check can fail.

    Were the label copied from the descriptor into the facts, the comparison
    would be the descriptor against itself and a chart that relabelled a
    Deployment would go on certifying under the old label.
    """
    document = facts_document()
    document["workloads"][0]["component"] = "api"

    with pytest.raises(core.CertificationFailed, match="component labels"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_a_replica_that_is_not_ready_stops_the_run(tmp_path: Path) -> None:
    document = facts_document()
    document["workloads"][1]["replicasReady"] = 0

    with pytest.raises(core.CertificationFailed) as raised:
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )

    assert raised.value.stage == core.STAGE_READINESS
    assert "0 of 1 replicas ready" in str(raised.value)


def test_a_replica_count_this_pr_does_not_describe_stops_the_run(
    tmp_path: Path,
) -> None:
    """Multi-replica certification is the next PR's boundary. A single-replica
    descriptor meeting a two-replica release must refuse rather than quietly
    report the stronger result."""
    document = facts_document()
    document["workloads"][1]["replicasDesired"] = 2
    document["workloads"][1]["replicasReady"] = 2

    with pytest.raises(core.CertificationFailed, match="this certification describes"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_an_image_that_is_not_digest_pinned_stops_the_run(tmp_path: Path) -> None:
    """A tag is a label that can be moved, and a C2 record naming one records
    nothing reproducible."""
    document = facts_document()
    document["workloads"][0]["images"] = ["localhost/inferops-api:latest"]

    with pytest.raises(core.CertificationFailed, match="not digest-pinned"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


# -- the model cache, which is what makes `requiresVerifiedModelCache` a check


def test_a_release_mounting_another_claim_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"modelCache.claimName": "somebody-elses-cache"})

    with pytest.raises(core.CertificationFailed, match="mounts claim"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


@pytest.mark.parametrize("member", ["volumeReadOnly", "mountReadOnly"])
def test_a_writable_model_cache_stops_the_run(tmp_path: Path, member: str) -> None:
    document = facts_document(**{f"modelCache.{member}": False})

    with pytest.raises(core.CertificationFailed, match="not mounted read-only"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_a_release_with_no_verification_init_container_stops_the_run(
    tmp_path: Path,
) -> None:
    document = facts_document(**{"modelCache.initContainers": ["something-else"]})

    with pytest.raises(core.CertificationFailed, match="init container"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_a_run_that_did_not_compare_the_artifact_hash_stops_the_run(
    tmp_path: Path,
) -> None:
    """The chart permits `verifyOnStart: size` and `none` under the real profile
    and the operator supplies the values file. Without this the record's
    provenance would name a SHA-256 that nothing in the run computed."""
    document = facts_document(**{"modelCache.artifactHashCompared": False})

    with pytest.raises(core.CertificationFailed, match="against its pinned"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_a_failed_in_cluster_connection_test_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"release.testPassed": False})

    with pytest.raises(core.CertificationFailed, match="connection test did not pass"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_an_unpinned_model_revision_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"configuration.modelRevision": "main"})

    with pytest.raises(core.CertificationFailed, match="not the pinned"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


@pytest.mark.parametrize(
    ("member", "value", "expected"),
    [
        ("timings.runtimeReadyMs", 1_000_000, "serving runtime took"),
        ("timings.apiReadyMs", 400_000, "platform API took"),
        ("timings.installMs", 1_000_000, "install took"),
        ("timings.releaseTestMs", 400_000, "connection test took"),
    ],
)
def test_a_measurement_over_budget_stops_the_run(
    tmp_path: Path, member: str, value: int, expected: str
) -> None:
    document = facts_document(**{member: value})

    with pytest.raises(core.CertificationFailed, match=expected):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_a_mock_marker_in_the_collected_facts_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"configuration.modelIdentifier": "mock-model"})

    with pytest.raises(core.CertificationFailed, match="mock identity metadata"):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_a_missing_measurement_stops_the_run(tmp_path: Path) -> None:
    """An absent field is not a zero: it is a question nobody answered, and a
    record built from one describes an environment nobody measured."""
    document = facts_document()
    del document["cluster"]["serverVersion"]

    with pytest.raises(
        core.CertificationFailed, match=re.escape("cluster.serverVersion")
    ):
        core.load_cluster_facts(
            core.load_certification(), repo_root=facts_root(tmp_path, document)
        )


def test_an_unset_service_version_is_recorded_rather_than_refused(
    tmp_path: Path,
) -> None:
    """`telemetry.serviceVersion` has an empty default and the committed real
    render carries it empty. Refusing it would make this certification
    unrunnable against the very values file it names."""
    facts = core.load_cluster_facts(
        core.load_certification(), repo_root=facts_root(tmp_path, facts_document())
    )

    assert facts.service_version == ""


# --------------------------------------------------------------------------
# The facts the script writes are the facts the reader accepts
# --------------------------------------------------------------------------


def embedded_facts_writer() -> str:
    """The JSON writer the operating script embeds, as source.

    Extracted rather than duplicated, because a copy of it here would test the
    copy. This is the one part of the workflow that turns real command output
    into the document everything downstream reads, and reading both halves did
    not catch that they disagreed.
    """
    marker = "<<'PYTHON'\n"
    start = SCRIPT_TEXT.index(marker) + len(marker)
    return SCRIPT_TEXT[start : SCRIPT_TEXT.index("\nPYTHON\n", start)]


def collected_environment(**overrides: str) -> dict[str, str]:
    """What the script's own queries would have put in the environment."""
    manifest = load_manifest()
    digest = manifest.sha256.removeprefix("sha256:")
    verification = (
        "set -eu\n"
        "artifact='/models/Qwen3-1.7B-Q8_0.gguf'\n"
        f'echo "{digest}  $artifact" | sha256sum -c -\n'
    )
    environment = {
        "CLUSTER_NAME": lib_constant("INFEROPS_CLUSTER_NAME"),
        "CONTEXT": kube_context(),
        "SERVER_VERSION": "v1.34.8",
        "NODE_DIGEST": lib_constant("INFEROPS_NODE_IMAGE_DIGEST"),
        "HELM": "v3.19.0+g3d8990f",
        "KUBECTL": "v1.36.1",
        "TERRAFORM": json.dumps(
            {"terraform_version": "1.15.8", "platform": "windows_386"}
        ),
        "RELEASE_NAME": "inferops",
        "NAMESPACE": "inferops-release",
        # The real shape: `helm list -o json` is an array and its revision is a
        # string.
        "RELEASE_JSON": json.dumps(
            [
                {
                    "name": "inferops",
                    "namespace": "inferops-release",
                    "revision": "1",
                    "updated": "2026-09-08 12:00:00.0 +0000 UTC",
                    "status": "deployed",
                    "chart": "inferops-llm-0.2.0",
                    "app_version": "0.1.0",
                }
            ]
        ),
        "PROFILE": "real",
        "SERVICE_VERSION": "",
        "MODEL_IDENTIFIER": MODEL_IDENTIFIER,
        "MODEL_REVISION": manifest.revision,
        "ENVIRONMENT": "dev",
        "API_NAME": "inferops-inferops-llm",
        "API_COMPONENT": "platform-api",
        # A jsonpath over an empty initContainers list yields a leading space.
        "API_IMAGES": f" {API_IMAGE}",
        "API_DESIRED": "1",
        "API_READY": "1",
        "RUNTIME_NAME": "inferops-inferops-llm-runtime",
        "RUNTIME_COMPONENT": "serving-runtime",
        "RUNTIME_IMAGES": f"{VERIFY_IMAGE} {RUNTIME_IMAGE}",
        "RUNTIME_DESIRED": "1",
        "RUNTIME_READY": "1",
        "CLAIM_NAME": "inferops-model-cache",
        "VOLUME_READ_ONLY": "true",
        "MOUNT_READ_ONLY": "true",
        "INIT_CONTAINERS": "verify-model",
        "INIT_COMMAND": verification,
        "MODEL_SHA256": manifest.sha256,
        "PREREQUISITES_MS": "4200",
        "INSTALL_MS": "1800",
        "API_READY_MS": "9500",
        "RUNTIME_READY_MS": "358735",
        "RELEASE_TEST_MS": "6000",
        "RELEASE_TEST_PASSED": "true",
    }
    environment.update(overrides)
    return {f"INFEROPS_FACT_{name}": value for name, value in environment.items()}


def run_facts_writer(tmp_path: Path, **overrides: str) -> Path:
    """Execute the script's embedded writer and return the repository root."""
    program = tmp_path / "facts_writer.py"
    program.write_text(embedded_facts_writer(), encoding="utf-8")
    target = tmp_path / core.EXPECTED_FACTS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    completed = subprocess.run(
        [sys.executable, str(program), str(target)],
        env={**os.environ, **collected_environment(**overrides)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    return tmp_path


def test_the_scripts_own_writer_produces_facts_the_reader_accepts(
    tmp_path: Path,
) -> None:
    """The round trip the two halves needed and did not have."""
    root = run_facts_writer(tmp_path)

    facts = core.load_cluster_facts(core.load_certification(), repo_root=root)

    assert facts.release_revision == 1
    assert facts.chart_version == "inferops-llm-0.2.0"
    assert facts.terraform_version == "1.15.8"
    assert facts.model_cache.artifact_hash_compared is True
    assert facts.model_cache.init_containers == ("verify-model",)
    assert [workload.images for workload in facts.workloads] == [
        (API_IMAGE,),
        (VERIFY_IMAGE, RUNTIME_IMAGE),
    ]
    assert facts.runtime_ready_ms == 358_735


def test_the_writer_reports_an_unverified_artifact_rather_than_assuming_one(
    tmp_path: Path,
) -> None:
    """`verifyOnStart: size` renders a command with no hash comparison in it."""
    root = run_facts_writer(
        tmp_path,
        INIT_COMMAND='set -eu\ntest "$(stat -c %s "$artifact")" = 1834426016\n',
    )

    with pytest.raises(core.CertificationFailed, match="against its pinned"):
        core.load_cluster_facts(core.load_certification(), repo_root=root)


def test_the_writer_reports_a_writable_mount_rather_than_assuming_one(
    tmp_path: Path,
) -> None:
    root = run_facts_writer(tmp_path, MOUNT_READ_ONLY="false")

    with pytest.raises(core.CertificationFailed, match="not mounted read-only"):
        core.load_cluster_facts(core.load_certification(), repo_root=root)


def test_the_writer_does_not_read_an_absent_mount_as_read_only(
    tmp_path: Path,
) -> None:
    """An empty jsonpath result means the mount was not found, which is not the
    same as finding it and seeing it read-only."""
    root = run_facts_writer(tmp_path, MOUNT_READ_ONLY="")

    with pytest.raises(core.CertificationFailed, match="not mounted read-only"):
        core.load_cluster_facts(core.load_certification(), repo_root=root)


# --------------------------------------------------------------------------
# The forward is the one the operating script opened
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "base_url",
    [
        "https://127.0.0.1:18090",
        "http://10.0.0.5:18090",
        "http://example.invalid:18090",
        "http://127.0.0.1",
        "http://127.0.0.1:18090/v1",
        "http://127.0.0.1:18090?redirect=1",
    ],
)
def test_a_base_url_that_is_not_the_loopback_forward_is_refused(base_url: str) -> None:
    with pytest.raises(core.PrerequisiteUnmet):
        core.require_forwarded_base_url(base_url, core.load_certification())


def test_the_loopback_forward_is_accepted_and_normalised() -> None:
    assert (
        core.require_forwarded_base_url(
            "http://127.0.0.1:18090/", core.load_certification()
        )
        == "http://127.0.0.1:18090"
    )


# --------------------------------------------------------------------------
# The assertions over what the release answered
# --------------------------------------------------------------------------


@pytest.fixture()
def certification() -> core.Certification:
    return core.load_certification()


@pytest.fixture()
def facts(tmp_path: Path, certification: core.Certification) -> core.ClusterFacts:
    return core.load_cluster_facts(
        certification, repo_root=facts_root(tmp_path, facts_document())
    )


def test_an_api_that_does_not_report_itself_ready_is_refused(
    certification: core.Certification,
) -> None:
    answers = Answers(ready_status=503)

    with pytest.raises(
        core.CertificationFailed, match="reporting itself ready"
    ) as raised:
        core.observe_readiness(
            certification, base_url="http://127.0.0.1:18090", get=answers.get
        )

    assert raised.value.stage == core.STAGE_READINESS


def test_a_real_identity_is_read_from_the_service(
    certification: core.Certification, facts: core.ClusterFacts
) -> None:
    answers = Answers()

    identity = core.observe_identity(
        certification, facts, base_url="http://127.0.0.1:18090", get=answers.get
    )

    assert identity.adapter_kind == "real"
    assert identity.runtime_name == RUNTIME_NAME
    assert identity.model_revision == load_manifest().revision
    assert identity.token_usage_declared is True
    assert answers.urls == ["http://127.0.0.1:18090/v1/models"]


@pytest.mark.parametrize(
    ("keywords", "expected"),
    [
        ({"adapter_kind": "mock"}, "required adapter kind"),
        ({"runtime_name": "a runtime nobody selected"}, "unselected runtime"),
        ({"model_identifier": "some-other-model"}, "was not configured with"),
        ({"model_revision": "main"}, "pinned model revision"),
        ({"token_usage": False}, "mock capability metadata"),
        ({"token_usage": None}, "mock capability metadata"),
        ({"entries": 2}, "exactly one model"),
    ],
)
def test_an_identity_that_is_not_the_real_one_is_refused(
    certification: core.Certification,
    facts: core.ClusterFacts,
    keywords: dict[str, Any],
    expected: str,
) -> None:
    answers = Answers(models=models_body(**keywords))

    with pytest.raises(core.CertificationFailed, match=expected) as raised:
        core.observe_identity(
            certification, facts, base_url="http://127.0.0.1:18090", get=answers.get
        )

    assert raised.value.stage == core.STAGE_IDENTITY


def test_a_model_list_that_does_not_answer_is_refused(
    certification: core.Certification, facts: core.ClusterFacts
) -> None:
    answers = Answers(models_status=503)

    with pytest.raises(core.CertificationFailed, match="did not answer"):
        core.observe_identity(
            certification, facts, base_url="http://127.0.0.1:18090", get=answers.get
        )


def test_one_real_completion_is_observed_and_its_text_is_not_kept(
    certification: core.Certification, facts: core.ClusterFacts
) -> None:
    answers = Answers()
    ticks = iter([10.0, 10.75])

    observation = core.observe_inference(
        certification,
        facts,
        base_url="http://127.0.0.1:18090",
        post=answers.post,
        clock=lambda: next(ticks),
    )

    assert observation.status == 200
    assert observation.elapsed_ms == 750
    assert observation.total_tokens == 20
    assert observation.request_id_echoed is True
    assert observation.correlation_id_echoed is True
    assert answers.bodies[0]["model"] == MODEL_IDENTIFIER
    assert not hasattr(observation, "content")


def test_the_certified_request_carries_the_correlation_headers(
    certification: core.Certification, facts: core.ClusterFacts
) -> None:
    recorded: dict[str, str] = {}

    def post(
        url: str,
        body: Mapping[str, object],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> core.ApiResponse:
        del url, body, timeout_seconds
        recorded.update(headers)
        return core.ApiResponse(200, completion_body(), dict(headers))

    core.observe_inference(
        certification, facts, base_url="http://127.0.0.1:18090", post=post
    )

    assert recorded[REQUEST_ID_HEADER] == certification.request_id
    assert recorded[CORRELATION_ID_HEADER] == certification.correlation_id


@pytest.mark.parametrize(
    ("keywords", "expected"),
    [
        ({"adapter_kind": "mock"}, "required adapter kind"),
        ({"model_identifier": "some-other-model"}, "unconfigured model"),
        ({"content": "   "}, "no completion content"),
        ({"prompt_tokens": 0}, "counts are absent or inconsistent"),
        ({"total_tokens": 3}, "counts are absent or inconsistent"),
    ],
)
def test_a_completion_that_is_not_a_real_one_is_refused(
    certification: core.Certification,
    facts: core.ClusterFacts,
    keywords: dict[str, Any],
    expected: str,
) -> None:
    answers = Answers(completion=completion_body(**keywords))

    with pytest.raises(core.CertificationFailed, match=expected) as raised:
        core.observe_inference(
            certification, facts, base_url="http://127.0.0.1:18090", post=answers.post
        )

    assert raised.value.stage == core.STAGE_INFERENCE


def test_a_request_that_does_not_complete_is_refused(
    certification: core.Certification, facts: core.ClusterFacts
) -> None:
    answers = Answers(completion_status=503)

    with pytest.raises(core.CertificationFailed, match="did not return a completion"):
        core.observe_inference(
            certification, facts, base_url="http://127.0.0.1:18090", post=answers.post
        )


# --------------------------------------------------------------------------
# The record, and what it is allowed to carry
# --------------------------------------------------------------------------


def test_an_unconfirmed_run_observes_nothing(tmp_path: Path) -> None:
    with pytest.raises(core.PrerequisiteUnmet, match="confirm-real-kubernetes"):
        core.certify(
            core.load_certification(),
            confirmed=False,
            base_url="http://127.0.0.1:18090",
            repo_root=facts_root(tmp_path, facts_document()),
        )


def test_a_confirmed_run_produces_a_labelled_record(tmp_path: Path) -> None:
    answers = Answers()

    result = core.certify(
        core.load_certification(),
        confirmed=True,
        base_url="http://127.0.0.1:18090",
        repo_root=facts_root(tmp_path, facts_document()),
        get=answers.get,
        post=answers.post,
    )
    document = core.result_document(result)

    assert document["outcome"] == "certified"
    assert document["evidenceLabel"] == "local real Kubernetes"
    assert document["evidenceClass"] == "local-real-cpu"
    inference = document["inference"]
    assert isinstance(inference, dict)
    assert inference["generatedTextRetained"] is False
    kubernetes = document["kubernetes"]
    assert isinstance(kubernetes, dict)
    assert kubernetes["timings"]["runtimeReadyMs"] == 358_735
    assert kubernetes["modelCache"]["artifactHashCompared"] is True


def test_the_record_carries_no_prompt_and_no_completion(tmp_path: Path) -> None:
    """A record is committed evidence. A prompt or a completion in one is
    content this project has no business retaining, and the telemetry catalog
    refuses the same thing for the same reason."""
    answers = Answers()
    result = core.certify(
        core.load_certification(),
        confirmed=True,
        base_url="http://127.0.0.1:18090",
        repo_root=facts_root(tmp_path, facts_document()),
        get=answers.get,
        post=answers.post,
    )
    serialised = json.dumps(core.result_document(result))

    assert core.load_certification().prompt not in serialised
    assert "Kubernetes orchestrates containers" not in serialised


def test_provenance_names_the_hash_only_alongside_what_compared_it(
    tmp_path: Path,
) -> None:
    """A C2 record must name the model hash 'computed and compared'. Naming it
    beside a flag the run established is the difference between a record and a
    copy of a committed value."""
    facts = core.load_cluster_facts(
        core.load_certification(), repo_root=facts_root(tmp_path, facts_document())
    )
    record = core.provenance(core.load_certification(), facts)

    assert record["runtimeImage"].startswith("ghcr.io/ggml-org/llama.cpp@sha256:")
    assert record["modelRevision"] == load_manifest().revision
    assert record["modelSha256"] == load_manifest().sha256
    assert record["modelHashComparedInCluster"] == "true"


def test_the_evidence_directory_refuses_a_linked_component(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    linked = tmp_path.resolve() / ".cache" / "inferops" / "certification"
    original = Path.is_symlink

    def is_linked(self: Path) -> bool:
        return self == linked or original(self)

    monkeypatch.setattr(Path, "is_symlink", is_linked)

    with pytest.raises(core.EvidenceUnwritable, match="evidence path is unsafe"):
        core.EvidenceDirectory(core.load_certification(), repo_root=tmp_path)


def test_an_unwritable_record_is_reported_at_the_evidence_stage() -> None:
    """A run whose inference succeeded and whose record could not be stored did
    not fail at `load`, which is where the base class default would put it."""
    assert core.EvidenceUnwritable("x").stage == core.STAGE_EVIDENCE
    assert core.STAGE_EVIDENCE in core.STAGES


def test_diagnostics_name_the_stage_a_run_stopped_in(tmp_path: Path) -> None:
    """The bounded-and-diagnostic criterion: a failure leaves something worth
    reading, in the vocabulary the procedure document publishes."""
    certification = core.load_certification()
    evidence = core.EvidenceDirectory(certification, repo_root=tmp_path)

    written = evidence.write(
        evidence.diagnostics_path,
        core.diagnostics_document(
            core.Diagnostics(
                stage=core.STAGE_READINESS,
                reason="the serving runtime took 1000000 ms to become ready",
            )
        ),
    )
    document = json.loads(written.read_text(encoding="utf-8"))

    assert written == (
        tmp_path.resolve()
        / ".cache/inferops/certification/k8s-real-inference-diagnostics.json"
    )
    assert document["outcome"] == "not-certified"
    assert document["stage"] == "readiness"
    assert document["stage"] in core.STAGES
    assert document["kubernetes"] is None


def test_the_result_and_diagnostics_records_are_separate_files() -> None:
    certification = core.load_certification()

    assert certification.result_file != certification.diagnostics_file


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_offline_check_contacts_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check"]) == 0

    printed = capsys.readouterr().out
    assert "C2; local-real-cpu" in printed
    assert "real-runtime; outside the default check lane" in printed
    assert "labelled local real Kubernetes" in printed
    assert "not started (offline certification validation only)" in printed


def test_the_command_refuses_an_unconfirmed_observation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["observe"]) == 3

    printed = capsys.readouterr().err
    assert "REFUSED Kubernetes certification at stage prerequisites" in printed
    assert "confirm-real-kubernetes" in printed
    assert "diagnostics   not written" in printed


def test_the_command_takes_no_path_to_the_collected_facts() -> None:
    """Their location is the descriptor's. A flag would make the base-URL guard
    decorative."""
    with pytest.raises(SystemExit):
        main(["observe", "--cluster-facts", "anywhere.json"])


def test_the_command_refuses_a_forward_it_did_not_recognise(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        ["observe", "--confirm-real-kubernetes", "--base-url", "http://10.1.2.3:8090"]
    )

    assert exit_code == 3
    assert "must name 127.0.0.1" in capsys.readouterr().err


# --------------------------------------------------------------------------
# The operating script is written the way a cluster-operating script must be
# --------------------------------------------------------------------------


def descriptor_reads() -> tuple[list[str], list[str], list[str]]:
    """The fields the script asks for, the variables it assigns, and its guard."""
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


def test_the_script_assigns_every_descriptor_field_to_the_variable_it_named() -> None:
    """A positional read is a silent corruption waiting for an edit.

    The script asks for N descriptor fields and assigns them to N variables in
    order. Adding a field to one list and not the other shifts every value after
    it -- a budget receives a Service name, a name receives a number -- and no
    linter sees it. This has already happened once while this file was written.
    """
    fields, variables, guard = descriptor_reads()

    assert len(fields) == len(variables), list(zip(fields, variables, strict=False))
    assert set(guard) == set(variables), set(guard).symmetric_difference(variables)


def test_the_script_holds_every_number_it_computes_with_to_being_a_number() -> None:
    """A descriptor field reaching shell arithmetic must be checked where it is
    used, not in another program that happens to run first."""
    start = SCRIPT_TEXT.index("for number in ")
    checked = set(
        SCRIPT_TEXT[start : SCRIPT_TEXT.index("; do", start)]
        .replace("for number in", "")
        .replace("\\", " ")
        .split()
    )

    arithmetic = set(re.findall(r"\$\(\((\w+) / 1000\)\)", SCRIPT_TEXT))
    arithmetic |= set(re.findall(r"\$\(\(SECONDS \+ (\w+) / 1000\)\)", SCRIPT_TEXT))

    assert arithmetic
    assert arithmetic <= checked, arithmetic - checked
    assert "descriptor_api_port" in checked


def test_the_script_reads_its_budgets_from_the_descriptor() -> None:
    """A threshold written into the script is a second copy of a decision, and
    the copy is the one that stops agreeing."""
    for member in (
        "readiness.installBudgetMs",
        "readiness.runtimeRolloutBudgetMs",
        "readiness.apiRolloutBudgetMs",
        "readiness.releaseTestBudgetMs",
        "readiness.forwardBudgetMs",
        "readiness.uninstallBudgetMs",
    ):
        assert member in SCRIPT_TEXT, member


def test_no_wait_in_the_script_carries_a_literal_duration() -> None:
    """Every bound comes from the descriptor, so none is written here."""
    offenders = [
        line.strip()
        for line in SCRIPT_TEXT.splitlines()
        if not line.lstrip().startswith("#")
        and re.search(r"--timeout[= ][0-9]+[ms]?\b", line)
    ]

    assert not offenders, offenders


def test_the_script_asks_kubectl_for_a_version_in_a_form_it_supports() -> None:
    """`kubectl version` accepts only yaml and json for --output.

    It refuses `jsonpath` outright, so the obvious-looking invocation exits 1 --
    which, in this workflow, happens after the Terraform apply, the install, the
    model load, and the in-cluster test have all already run.
    """
    versions = [
        line
        for line in SCRIPT_TEXT.splitlines()
        if "kubectl version" in line and not line.lstrip().startswith("#")
    ]

    assert versions
    for line in versions:
        assert "jsonpath" not in line, line


def test_the_script_validates_the_descriptor_before_it_reaches_a_cluster() -> None:
    validated = SCRIPT_TEXT.index("tools.kubernetes_certification check")
    installed = SCRIPT_TEXT.index("inferops::helm install")

    assert validated < installed


def test_the_script_requires_explicit_authorization_before_certifying() -> None:
    assert "--confirm-real-kubernetes" in SCRIPT_TEXT
    assert "certify needs --confirm-real-kubernetes" in SCRIPT_TEXT


def test_the_script_asserts_the_target_cluster_before_installing() -> None:
    asserted = SCRIPT_TEXT.index("inferops::assert_target_cluster")
    installed = SCRIPT_TEXT.index("inferops::helm install")

    assert asserted < installed


def test_the_script_applies_the_prerequisites_before_installing() -> None:
    applied = SCRIPT_TEXT.index('terraform-prerequisites.sh" apply')
    installed = SCRIPT_TEXT.index("inferops::helm install")

    assert applied < installed


def test_the_script_compares_the_descriptor_with_the_shared_target() -> None:
    """One cluster and one release named by two records, compared rather than
    assumed."""
    for comparison in (
        'descriptor_cluster}" = "${INFEROPS_CLUSTER_NAME}',
        'descriptor_context}" = "${INFEROPS_KUBE_CONTEXT}',
        'descriptor_release}" = "${INFEROPS_RELEASE_NAME}',
        'descriptor_namespace}" = "${INFEROPS_RELEASE_NAMESPACE}',
    ):
        assert comparison in SCRIPT_TEXT, comparison


def test_the_script_never_removes_the_prerequisites_or_the_cluster() -> None:
    """`terraform destroy`, `kind delete`, and a namespace deletion each remove
    something whose lifetime is longer than a release's."""
    forbidden = ("terraform destroy", "kind delete", "delete namespace")
    offenders = [
        line
        for line in SCRIPT_TEXT.splitlines()
        if not line.lstrip().startswith("#")
        and any(pattern in line for pattern in forbidden)
    ]

    assert not offenders, offenders


def test_the_script_counts_the_claims_on_both_sides_of_the_release() -> None:
    """The claim is the one object in this namespace that must survive, and
    counting is how that is asserted without knowing which claim a values file
    named. `helm-lifecycle.sh` already does this; the workflow that writes the
    C2 record may not be weaker than the one that does not."""
    before = SCRIPT_TEXT.index("claims_before=")
    installed = SCRIPT_TEXT.index("inferops::helm install")
    after = SCRIPT_TEXT.index("claims_after=")

    assert before < installed < after
    assert 'claims_after}" = "${claims_before}' in SCRIPT_TEXT


def test_the_residue_check_asks_about_claims_too() -> None:
    start = SCRIPT_TEXT.index("did uninstall remove the release")
    selector = SCRIPT_TEXT[start : start + 800]

    assert "pvc" in selector


def test_the_script_confirms_helm_forgot_the_release_as_well() -> None:
    assert "helm still reports a release named" in SCRIPT_TEXT


def test_the_script_leaves_a_failed_release_in_place() -> None:
    """A teardown that ran on failure would remove the evidence of it."""
    assert "left in place for inspection" in SCRIPT_TEXT
    assert "collect_diagnostics" in SCRIPT_TEXT


def test_the_script_asserts_the_namespace_survived_its_own_teardown() -> None:
    assert "must outlive the release" in SCRIPT_TEXT


def test_the_script_forwards_only_to_the_loopback_host_the_descriptor_names() -> None:
    assert '--address "${descriptor_host}"' in SCRIPT_TEXT
    assert 'base_url="http://${descriptor_host}:${forward_port}"' in SCRIPT_TEXT


def test_the_script_closes_the_forward_on_a_signal_as_well_as_on_exit() -> None:
    """A forward left open after the script is interrupted is a hole in a
    cluster somebody stopped paying attention to, and this workflow also leaves
    a real release behind."""
    assert "trap on_exit INT TERM EXIT" in SCRIPT_TEXT
    assert "close_forward" in SCRIPT_TEXT.split("on_exit()", 1)[1]


def test_the_script_writes_its_facts_through_a_json_writer() -> None:
    """A shell assembling JSON by hand produces a malformed document the first
    time a version banner contains a quote."""
    assert "json.dumps" in SCRIPT_TEXT
    assert "os.environ" in SCRIPT_TEXT


def test_the_script_refuses_an_unanswered_query() -> None:
    """An empty field is not a measurement, and a C2 record names the
    environment it ran in."""
    assert "is not a measurement" in SCRIPT_TEXT


def test_the_script_reads_the_component_labels_from_the_cluster() -> None:
    """A fact copied from the descriptor cannot disagree with it."""
    assert "app\\.kubernetes\\.io/component" in SCRIPT_TEXT
    assert "the API component label" in SCRIPT_TEXT
    assert "the runtime component label" in SCRIPT_TEXT


def test_the_procedure_document_publishes_every_stage() -> None:
    published = PROCEDURE_PATH.read_text(encoding="utf-8")

    for stage in core.STAGES:
        assert f"`{stage}`" in published, stage
