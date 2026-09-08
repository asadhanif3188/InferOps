"""The Kubernetes certification descriptor, its guards, and its operating script.

Every check here reads committed files or drives the workflow through injected
HTTP and clock seams. No cluster is contacted, no release is installed, no
forward is opened, no model byte is read, and nothing in `scripts/environment/`
is executed: the script is read as text. These results are `local-static` and
synthetic. They establish that the certification mechanism refuses what it must,
records what it observes, and is written the way the accepted safety decisions
say a cluster-operating script must be written.

They establish nothing about Kubernetes. Whether a release installs, whether a
model loads, whether a completion returns through a Service, and whether a
teardown leaves no residue are runtime questions, and only an authorized run of
`scripts/environment/kubernetes-certification.sh certify --confirm-real-kubernetes`
answers them. A static reading of a workflow is not a substitute for running it.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.api.surface import CORRELATION_ID_HEADER, REQUEST_ID_HEADER
from tools.kubernetes_certification import core
from tools.kubernetes_certification.__main__ import main
from tools.local_composition import load_composition
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

CERTIFICATION_DOCUMENT: dict[str, Any] = json.loads(
    core.CERTIFICATION_PATH.read_text(encoding="utf-8")
)

SCRIPT_TEXT = SCRIPT_PATH.read_text(encoding="utf-8")
LIB_TEXT = LIB_PATH.read_text(encoding="utf-8")

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


def lib_constant(name: str) -> str:
    match = re.search(
        rf'^readonly {re.escape(name)}="([^"]*)"', LIB_TEXT, flags=re.MULTILINE
    )
    assert match is not None, f"lib.sh does not define {name}"
    return match.group(1)


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
    """One well-formed collection, in the shape the operating script writes."""
    document: dict[str, Any] = {
        "cluster": {
            "name": "inferops-dev",
            "context": "kind-inferops-dev",
            "serverVersion": "v1.34.8",
            "nodeImageDigest": "sha256:" + "02" * 32,
        },
        "tooling": {
            "helm": "v3.19.0+g3d8990f",
            "kubectl": "v1.36.1",
            "terraform": "1.15.8",
        },
        "release": {
            "name": "inferops",
            "namespace": "inferops-release",
            "revision": 1,
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
                "images": [RUNTIME_IMAGE],
                "replicasDesired": 1,
                "replicasReady": 1,
            },
        ],
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
            "runtimeReadyMs": 140_000,
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


def written_facts(tmp_path: Path, document: Mapping[str, Any]) -> Path:
    candidate = tmp_path / "cluster-facts.json"
    candidate.write_text(json.dumps(document), encoding="utf-8")
    return candidate


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
    """A recorded GET and POST pair standing in for the forwarded Service."""

    def __init__(
        self,
        *,
        models: Mapping[str, Any] | None = None,
        completion: Mapping[str, Any] | None = None,
        models_status: int = 200,
        completion_status: int = 200,
        echo_headers: bool = True,
    ) -> None:
        self.models = models_body() if models is None else models
        self.completion = completion_body() if completion is None else completion
        self.models_status = models_status
        self.completion_status = completion_status
        self.echo_headers = echo_headers
        self.urls: list[str] = []
        self.bodies: list[Mapping[str, object]] = []

    def get(self, url: str, timeout_seconds: float) -> core.ApiResponse:
        del timeout_seconds
        self.urls.append(url)
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


def test_the_evidence_label_names_kubernetes_and_the_class_stays_a_published_one() -> (
    None
):
    """A new label is not a new evidence class, and only one of the two is free.

    `docs/testing/certification.md` fixes the evidence classes and the ceiling
    each one carries. This workflow runs the real component on a contributor's
    own machine on CPU, which is `local-real-cpu` exactly as the composed C2 run
    is; what differs is that it ran through Kubernetes, and that is what the
    label says. Inventing a class here would have raised a ceiling by writing a
    string.
    """
    certification = core.load_certification()
    published = json.loads(
        (REPO_ROOT / "docs/testing/test-strategy.v1alpha1.json").read_text(
            encoding="utf-8"
        )
    )
    classes = {entry["classId"] for entry in published["evidenceClasses"]}

    assert certification.evidence_class in classes
    assert "kubernetes" in certification.evidence_label.casefold()


def test_the_descriptor_names_the_release_these_scripts_operate() -> None:
    """Two records name one release, and a run where they disagree certifies
    something other than what it installed."""
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
        == certification.release.api_service_name
    )
    runtime_deployments = [
        document
        for document in rendered_objects()
        if document["kind"] == "Deployment"
        and document["metadata"]["name"] == certification.release.runtime_service_name
    ]
    assert len(runtime_deployments) == 1


def test_the_descriptor_names_the_port_the_chart_publishes() -> None:
    values = yaml.safe_load(CHART_VALUES_PATH.read_text(encoding="utf-8"))

    assert (
        core.load_certification().release.api_service_port
        == values["api"]["service"]["port"]
    )


def test_the_descriptor_names_the_components_the_chart_labels() -> None:
    certification = core.load_certification()
    labelled = {
        document["metadata"]["labels"].get("app.kubernetes.io/component")
        for document in rendered_objects()
        if document["kind"] == "Deployment"
    }

    assert {
        certification.release.api_component,
        certification.release.runtime_component,
    } == labelled


def test_the_descriptor_describes_the_profile_the_values_fixture_selects() -> None:
    values = yaml.safe_load(REAL_VALUES_PATH.read_text(encoding="utf-8"))

    assert core.load_certification().release.profile == values["profile"]


def test_the_budgets_are_the_ones_the_accepted_records_already_publish() -> None:
    certification = core.load_certification()

    assert certification.runtime_budget_ms == load_runtime_package().startup_budget_ms
    assert certification.api_budget_ms == load_composition().response_budget_ms
    assert certification.request_timeout_ms == load_runtime_profile().request_budget_ms


def test_the_procedure_the_descriptor_cites_exists() -> None:
    assert (REPO_ROOT / core.load_certification().procedure_ref).is_file()
    assert (REPO_ROOT / core.load_certification().certification_ref).is_file()


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
    ],
)
def test_a_waived_real_assertion_is_refused(tmp_path: Path, member: str) -> None:
    document = _mutated(("assertions", member), False)

    with pytest.raises(core.CertificationError, match="may not waive a real assertion"):
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


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("readiness", "runtimeBudgetMs"), 1_000),
        (("readiness", "apiBudgetMs"), 1_000),
        (("request", "timeoutMs"), 1_000),
    ],
)
def test_a_budget_disagreeing_with_the_profile_is_refused(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    with pytest.raises(core.CertificationError, match="budgets disagree"):
        core.load_certification(_written(tmp_path, _mutated(path, value)))


def test_an_install_budget_under_the_model_load_budget_is_refused(
    tmp_path: Path,
) -> None:
    """A timeout that fires during a normal load reports a slow load as a
    failure, and a certification that does that is worse than none."""
    document = _mutated(("readiness", "installBudgetMs"), 1_000)

    with pytest.raises(core.CertificationError, match="below the model load budget"):
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
    candidate = tmp_path / "missing.json"

    with pytest.raises(core.CertificationError, match="unreadable"):
        core.load_certification(candidate)


# --------------------------------------------------------------------------
# The collected facts are held to the descriptor
# --------------------------------------------------------------------------


def test_well_formed_facts_are_accepted(tmp_path: Path) -> None:
    certification = core.load_certification()

    facts = core.load_cluster_facts(
        written_facts(tmp_path, facts_document()), certification
    )

    assert facts.release_name == certification.release.name
    assert facts.release_status == "deployed"
    assert {workload.component for workload in facts.workloads} == {
        certification.release.api_component,
        certification.release.runtime_component,
    }
    assert all(workload.fully_ready for workload in facts.workloads)


def test_unreadable_facts_stop_the_run(tmp_path: Path) -> None:
    with pytest.raises(core.CertificationFailed, match="unreadable"):
        core.load_cluster_facts(tmp_path / "absent.json", core.load_certification())


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
    document = facts_document(**{path: value})

    with pytest.raises(core.CertificationFailed) as raised:
        core.load_cluster_facts(
            written_facts(tmp_path, document), core.load_certification()
        )

    assert raised.value.stage == core.STAGE_RELEASE


def test_a_release_that_is_not_deployed_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"release.status": "failed"})

    with pytest.raises(core.CertificationFailed, match="rather than deployed"):
        core.load_cluster_facts(
            written_facts(tmp_path, document), core.load_certification()
        )


def test_a_release_missing_a_component_stops_the_run(tmp_path: Path) -> None:
    """A `mock` profile installs no runtime, and a run that certified one
    Deployment would be certifying the mock path with a real label."""
    document = facts_document()
    document["workloads"] = document["workloads"][:1]

    with pytest.raises(core.CertificationFailed, match="exactly the API and"):
        core.load_cluster_facts(
            written_facts(tmp_path, document), core.load_certification()
        )


def test_a_replica_that_is_not_ready_stops_the_run(tmp_path: Path) -> None:
    document = facts_document()
    document["workloads"][1]["replicasReady"] = 0

    with pytest.raises(core.CertificationFailed) as raised:
        core.load_cluster_facts(
            written_facts(tmp_path, document), core.load_certification()
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
            written_facts(tmp_path, document), core.load_certification()
        )


def test_an_image_that_is_not_digest_pinned_stops_the_run(tmp_path: Path) -> None:
    """A tag is a label that can be moved, and a C2 record naming one records
    nothing reproducible."""
    document = facts_document()
    document["workloads"][0]["images"] = ["localhost/inferops-api:latest"]

    with pytest.raises(core.CertificationFailed, match="not digest-pinned"):
        core.load_cluster_facts(
            written_facts(tmp_path, document), core.load_certification()
        )


def test_a_failed_in_cluster_connection_test_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"release.testPassed": False})

    with pytest.raises(core.CertificationFailed, match="connection test did not pass"):
        core.load_cluster_facts(
            written_facts(tmp_path, document), core.load_certification()
        )


def test_an_unpinned_model_revision_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"configuration.modelRevision": "main"})

    with pytest.raises(core.CertificationFailed, match="not the pinned one"):
        core.load_cluster_facts(
            written_facts(tmp_path, document), core.load_certification()
        )


@pytest.mark.parametrize(
    ("member", "value", "expected"),
    [
        ("timings.runtimeReadyMs", 400_000, "serving runtime took"),
        ("timings.apiReadyMs", 200_000, "platform API took"),
        ("timings.installMs", 1_000_000, "install took"),
    ],
)
def test_a_measurement_over_budget_stops_the_run(
    tmp_path: Path, member: str, value: int, expected: str
) -> None:
    document = facts_document(**{member: value})

    with pytest.raises(core.CertificationFailed, match=expected):
        core.load_cluster_facts(
            written_facts(tmp_path, document), core.load_certification()
        )


def test_a_mock_marker_in_the_collected_facts_stops_the_run(tmp_path: Path) -> None:
    document = facts_document(**{"configuration.modelIdentifier": "mock-model"})

    with pytest.raises(core.CertificationFailed, match="mock identity metadata"):
        core.load_cluster_facts(
            written_facts(tmp_path, document), core.load_certification()
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
            written_facts(tmp_path, document), core.load_certification()
        )


def test_an_unset_service_version_is_recorded_rather_than_refused(
    tmp_path: Path,
) -> None:
    """`telemetry.serviceVersion` has an empty default and the committed real
    render carries it empty. Refusing it would make this certification
    unrunnable against the very values file it names."""
    facts = core.load_cluster_facts(
        written_facts(tmp_path, facts_document()), core.load_certification()
    )

    assert facts.service_version == ""


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
def test_a_base_url_that_is_not_the_loopback_forward_is_refused(
    base_url: str,
) -> None:
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
        written_facts(tmp_path, facts_document()), certification
    )


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
            facts_path=written_facts(tmp_path, facts_document()),
        )


def test_a_confirmed_run_produces_a_labelled_record(tmp_path: Path) -> None:
    answers = Answers()
    certification = core.load_certification()

    result = core.certify(
        certification,
        confirmed=True,
        base_url="http://127.0.0.1:18090",
        facts_path=written_facts(tmp_path, facts_document()),
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
    assert kubernetes["timings"]["runtimeReadyMs"] == 140_000
    assert kubernetes["release"]["revision"] == 1


def test_the_record_carries_no_prompt_and_no_completion(tmp_path: Path) -> None:
    """A record is committed evidence. A prompt or a completion in one is
    content this project has no business retaining, and the telemetry catalog
    refuses the same thing for the same reason."""
    answers = Answers()
    result = core.certify(
        core.load_certification(),
        confirmed=True,
        base_url="http://127.0.0.1:18090",
        facts_path=written_facts(tmp_path, facts_document()),
        get=answers.get,
        post=answers.post,
    )
    serialised = json.dumps(core.result_document(result))

    assert core.load_certification().prompt not in serialised
    assert "Kubernetes orchestrates containers" not in serialised


def test_provenance_names_the_immutable_inputs_a_c2_record_must_carry() -> None:
    record = core.provenance(core.load_certification())

    assert record["runtimeImage"].startswith("ghcr.io/ggml-org/llama.cpp@sha256:")
    assert record["modelRevision"] == load_manifest().revision
    assert record["modelSha256"].startswith("sha256:")
    assert record["chartRef"] == "charts/inferops-llm"


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
                reason="the serving runtime took 400000 ms to become ready",
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


def test_an_unconfirmed_refusal_writes_no_diagnostics_record(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A diagnostics file for a lane nobody entered is noise, not evidence."""
    assert main(["observe", "--base-url", "http://127.0.0.1:18090"]) == 3

    assert "not written" in capsys.readouterr().err


def test_the_command_refuses_a_forward_it_did_not_recognise(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = main(
        [
            "observe",
            "--confirm-real-kubernetes",
            "--base-url",
            "http://10.1.2.3:8090",
            "--cluster-facts",
            str(written_facts(tmp_path, facts_document())),
        ]
    )

    assert exit_code == 3
    assert "must name 127.0.0.1" in capsys.readouterr().err


# --------------------------------------------------------------------------
# The operating script is written the way a cluster-operating script must be
# --------------------------------------------------------------------------


def test_the_script_reads_its_budgets_from_the_descriptor() -> None:
    """A threshold written into the script is a second copy of a decision, and
    the copy is the one that stops agreeing."""
    for member in (
        "readiness.installBudgetMs",
        "readiness.runtimeBudgetMs",
        "readiness.apiBudgetMs",
        "readiness.releaseTestBudgetMs",
    ):
        assert member in SCRIPT_TEXT, member


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


def test_the_script_compares_the_descriptor_with_the_shared_target() -> None:
    """One release named by two records, compared rather than assumed."""
    assert 'descriptor_release}" = "${INFEROPS_RELEASE_NAME}' in SCRIPT_TEXT
    assert 'descriptor_namespace}" = "${INFEROPS_RELEASE_NAMESPACE}' in SCRIPT_TEXT


def test_every_wait_in_the_script_is_bounded() -> None:
    """A hung rollout must fail the workflow, not the contributor's evening."""
    waits = [
        line
        for line in SCRIPT_TEXT.splitlines()
        if "rollout status" in line or "helm test" in line or "helm install" in line
    ]
    assert waits
    joined = "\n".join(SCRIPT_TEXT.splitlines())
    for wait in waits:
        if wait.lstrip().startswith("#"):
            continue
        following = joined[joined.index(wait) : joined.index(wait) + 400]
        assert "--timeout" in following, wait


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


def test_the_script_leaves_a_failed_release_in_place() -> None:
    """A teardown that ran on failure would remove the evidence of it."""
    assert "left in place for inspection" in SCRIPT_TEXT
    assert "collect_diagnostics" in SCRIPT_TEXT


def test_the_script_asserts_the_namespace_survived_its_own_teardown() -> None:
    assert "must outlive the release" in SCRIPT_TEXT


def test_the_script_forwards_only_to_loopback() -> None:
    assert "--address 127.0.0.1" in SCRIPT_TEXT


def test_the_script_closes_the_forward_on_every_path() -> None:
    """A forward left open after the script exits is a hole in a cluster
    somebody stopped paying attention to."""
    assert "trap on_exit EXIT" in SCRIPT_TEXT
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


def test_the_procedure_document_publishes_every_stage() -> None:
    published = PROCEDURE_PATH.read_text(encoding="utf-8")

    for stage in core.STAGES:
        assert f"`{stage}`" in published, stage
