"""The V2 capacity gate: what it reads, what it requires, and each refusal.

``tools.capacity_preflight`` reads one directory of cluster reads and returns one
record, whose result is ``ACCEPTED`` or ``REFUSED``. This suite builds each
directory from documents that no cluster produced. It contacts no cluster.

*The footprint.* The tool restates the pods of the chart from committed values.
One test renders the chart with the same values and compares each pod of the
render with the footprint. That test needs ``helm`` and skips without it.

*The arithmetic.* Each sufficiency rule is given the figure at which it holds
and the next smaller figure, at which it does not.

*The refusals.* Each ambiguous cluster and each absent read refuses. An absent
read is never read as an empty list.

*Continuity with V1.* The reserve is the V1 descriptor's headroom, the refusal
exit status is the V1 preflight's, and on a document that both read, this tool
and the V1 preflight program give the same four sums.

The evidence level of this suite is C0. It reads committed files and synthetic
documents. It does not establish that a pod is scheduled or starts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import capacity_preflight as gate
from tools.capacity_preflight import core
from tools.capacity_preflight.__main__ import main
from tools.gitops_desired_state import DESIRED_STATE_RELEASES, release_key
from tools.kubernetes_certification import multi_replica_cli

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_PATH = REPO_ROOT / "docs" / "environment" / "capacity-preflight.md"
KEY = "local-docker-desktop/support-assistant"
NAMESPACE = "inferops-release"
CLAIM = "inferops-model-cache"
NODE = "node-a"
V1_DESCRIPTOR = (
    REPO_ROOT / "deploy/serving/certification/k8s-multi-replica-inference.v1.json"
)
V1_SCRIPT = REPO_ROOT / "scripts/environment/kubernetes-multi-replica-certification.sh"
CASES = REPO_ROOT / "tests/domain/fixtures/capacity-preflight"

MI = 2**20
GI = 2**30

# Restated on purpose. A figure that this suite computed with the tool's own
# arithmetic would agree with the tool by construction.
STEADY = {"pods": 5, "cpu": 2300, "requests": 4480 * MI, "limits": 7680 * MI}
HEADROOM = {"pods": 2, "cpu": 200, "requests": 256 * MI, "limits": 1024 * MI}
TRANSIENT = {"pods": 2, "cpu": 110, "requests": 48 * MI, "limits": 192 * MI}
RESERVE = {"cpu": 500, "memory": 512 * MI}
REQUIRED = {
    "pods": 9,
    "cpu": 2300 + 200 + 110 + 500,
    "requests": (4480 + 256 + 48 + 512) * MI,
    "limits": (7680 + 1024 + 192 + 512) * MI,
}


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


def node(
    name: str = NODE,
    *,
    cpu: object = "12",
    memory: object = "16Gi",
    pods: object = "110",
    ready: str = "True",
    unschedulable: bool = False,
    taints: list[dict[str, str]] | None = None,
    pressure: dict[str, str] | None = None,
) -> dict[str, Any]:
    conditions = [
        {"type": kind, "status": (pressure or {}).get(kind, "False")}
        for kind in ("MemoryPressure", "DiskPressure", "PIDPressure")
    ]
    conditions.append({"type": "Ready", "status": ready})
    figures = {
        "cpu": cpu,
        "memory": memory,
        "pods": pods,
        "ephemeral-storage": "100Gi",
    }
    spec: dict[str, Any] = {}
    if unschedulable:
        spec["unschedulable"] = True
    if taints:
        spec["taints"] = taints
    return {
        "kind": "Node",
        "metadata": {"name": name},
        "spec": spec,
        "status": {
            "capacity": dict(figures),
            "allocatable": dict(figures),
            "conditions": conditions,
            "nodeInfo": {"kubeletVersion": "v1.36.1"},
        },
    }


def container(cpu: object = None, memory: object = None, **more: Any) -> dict[str, Any]:
    requests = {}
    if cpu is not None:
        requests["cpu"] = cpu
    if memory is not None:
        requests["memory"] = memory
    return {"name": "c", "resources": {"requests": requests}, **more}


def pod(
    name: str,
    *containers: dict[str, Any],
    namespace: str = "kube-system",
    on: str | None = NODE,
    phase: str = "Running",
    init: list[dict[str, Any]] | None = None,
    labels: dict[str, str] | None = None,
    **spec: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {"containers": list(containers), **spec}
    if on is not None:
        body["nodeName"] = on
    if init is not None:
        body["initContainers"] = init
    return {
        "kind": "Pod",
        "metadata": {"name": name, "namespace": namespace, "labels": labels or {}},
        "spec": body,
        "status": {"phase": phase},
    }


def system_pods() -> list[dict[str, Any]]:
    """Nine pods that request 950 millicores and 290 MiB together.

    Two state no processor request, and five state no memory request.
    """
    return [
        pod("dns-1", container("100m", "70Mi")),
        pod("dns-2", container("100m", "70Mi")),
        pod("etcd", container("100m", "100Mi")),
        pod("network", container("100m", "50Mi")),
        pod("api-server", container("250m")),
        pod("controller", container("200m")),
        pod("proxy", container()),
        pod("scheduler", container("100m")),
        pod("provisioner", container(), namespace="local-path-storage"),
    ]


def claim(
    *,
    name: str = CLAIM,
    capacity: object = "4Gi",
    request: object = "4Gi",
    namespace: str = NAMESPACE,
) -> dict[str, Any]:
    status: dict[str, Any] = {"phase": "Bound"}
    if capacity is not None:
        status["capacity"] = {"storage": capacity}
    return {
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "storageClassName": "standard",
            "resources": {"requests": {"storage": request}},
        },
        "status": status,
    }


def listed(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"apiVersion": "v1", "kind": "List", "items": items}


def header(**over: str) -> dict[str, str]:
    return {
        "schema": gate.COLLECTION_SCHEMA,
        "provider": "synthetic",
        "context": "synthetic",
        "releaseKey": KEY,
        "namespace": NAMESPACE,
        "executingCommit": "0" * 40,
        "collectedAt": "2026-01-01T00:00:00Z",
        **over,
    }


ABSENT = object()


def collection(
    directory: Path,
    *,
    nodes: Any = None,
    pods: Any = None,
    limits: Any = None,
    claims: Any = None,
    run: Any = None,
    footprint: Any = None,
    engine: Any = ABSENT,
    version: Any = ABSENT,
) -> Path:
    """Write one collection. ``ABSENT`` leaves a file out, and bytes are written as given."""
    directory.mkdir(parents=True, exist_ok=True)
    documents = {
        "run.json": header() if run is None else run,
        "footprint.json": gate.declared_footprint() if footprint is None else footprint,
        "nodes.json": listed([node()]) if nodes is None else nodes,
        "pods.json": listed(system_pods()) if pods is None else pods,
        "namespace-limits.json": listed([]) if limits is None else limits,
        "claims.json": listed([]) if claims is None else claims,
        "engine.json": engine,
        "version.json": version,
    }
    for name, document in documents.items():
        if document is ABSENT:
            continue
        if isinstance(document, bytes):
            (directory / name).write_bytes(document)
        else:
            (directory / name).write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    return directory


def finding(record: dict[str, Any], rule_id: str) -> dict[str, Any]:
    [found] = [f for f in record["findings"] if f["ruleId"] == rule_id]
    return found


def states(record: dict[str, Any]) -> dict[str, str]:
    return {f["ruleId"]: f["state"] for f in record["findings"]}


def refused_only_by(record: dict[str, Any], rule_id: str, category: str) -> None:
    assert record["result"] == gate.REFUSED
    assert record["refusal"] == {"categories": [category], "rules": [rule_id]}


# --------------------------------------------------------------------------
# Quantities
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("100m", Fraction(1, 10)),
        ("1500m", Fraction(3, 2)),
        ("1", Fraction(1)),
        ("12", Fraction(12)),
        ("0.5", Fraction(1, 2)),
        (".5", Fraction(1, 2)),
        ("2Gi", Fraction(2 * GI)),
        ("70Mi", Fraction(70 * MI)),
        ("10186204Ki", Fraction(10186204 * 1024)),
        ("1.5Gi", Fraction(3 * GI, 2)),
        ("129e6", Fraction(129_000_000)),
        ("1E3", Fraction(1000)),
        ("1e-3", Fraction(1, 1000)),
        ("1E", Fraction(10**18)),
        ("1M", Fraction(10**6)),
        ("1k", Fraction(1000)),
        ("250u", Fraction(250, 10**6)),
        ("5n", Fraction(5, 10**9)),
        ("128974848", Fraction(128974848)),
        (2, Fraction(2)),
        (0.5, Fraction(1, 2)),
    ],
)
def test_a_quantity_is_read_exactly(text: object, value: Fraction) -> None:
    assert gate.parse_quantity(text) == value


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        " 1",
        "1 ",
        "-1",
        "+1",
        "1 Gi",
        "1gi",
        "1GI",
        "1Kib",
        "1K",
        "Gi",
        "m",
        "1e",
        "1.2.3",
        "1,5",
        "0x10",
        chr(0xFF11) + chr(0xFF10) + chr(0xFF10) + "m",  # fullwidth digits
        chr(0x661) + chr(0x660) + chr(0x660) + "m",  # Arabic-Indic digits
        "1Ki\n",
        "nan",
        "inf",
        None,
        True,
        False,
        ["1"],
        {"cpu": "1"},
        float("inf"),
    ],
)
def test_a_value_that_is_not_a_quantity_is_refused(text: object) -> None:
    """A sign, a blank, another case, and a digit that is not ASCII are not read."""
    with pytest.raises(gate.QuantityRefused):
        gate.parse_quantity(text)


def test_a_fraction_of_a_unit_is_rounded_against_the_cluster() -> None:
    """A request is rounded up, and an allocatable figure is rounded down."""
    assert core._up(gate.parse_quantity("1n") * 1000) == 1
    assert core._down(gate.parse_quantity("11999999u") * 1000) == 11999
    assert core._up(Fraction(5)) == 5 == core._down(Fraction(5))


# --------------------------------------------------------------------------
# The request of one pod
# --------------------------------------------------------------------------


def test_a_pod_requests_the_sum_of_its_containers() -> None:
    spec = pod("p", container("100m", "64Mi"), container("250m", "1Gi"))["spec"]
    assert gate.pod_request(spec, "cpu") == (Fraction(350, 1000), True)
    assert gate.pod_request(spec, "memory") == (Fraction(64 * MI + GI), True)


def test_a_pod_requests_its_largest_init_container_when_that_is_larger() -> None:
    spec = pod(
        "p",
        container("100m", "70Mi"),
        container("250m"),
        init=[container("500m", "1Gi"), container("400m", "2Gi")],
    )["spec"]
    assert gate.pod_request(spec, "cpu") == (Fraction(1, 2), True)
    # The second container states no memory request.
    assert gate.pod_request(spec, "memory") == (Fraction(2 * GI), False)


def test_a_restartable_init_container_is_added_and_not_compared() -> None:
    """A sidecar runs beside the containers, and beside each later init container."""
    sidecar = container("200m", "100Mi", restartPolicy="Always")
    spec = pod(
        "p",
        container("300m", "50Mi"),
        init=[container("100m", "10Mi"), sidecar, container("600m", "20Mi")],
    )["spec"]
    # Containers and sidecar: 500m. The later init container beside the sidecar: 800m.
    assert gate.pod_request(spec, "cpu")[0] == Fraction(800, 1000)
    # Containers and sidecar: 150Mi. No init container beside the sidecar is larger.
    assert gate.pod_request(spec, "memory")[0] == Fraction(150 * MI)


def test_the_overhead_of_a_pod_is_added() -> None:
    spec = pod(
        "p", container("100m", "64Mi"), overhead={"cpu": "250m", "memory": "8Mi"}
    )["spec"]
    assert gate.pod_request(spec, "cpu")[0] == Fraction(350, 1000)
    assert gate.pod_request(spec, "memory")[0] == Fraction(72 * MI)


def test_a_request_that_a_pod_states_for_itself_is_its_request() -> None:
    spec = pod(
        "p",
        container(),
        container("100m"),
        resources={"requests": {"cpu": "2", "memory": "1Gi"}},
        overhead={"cpu": "100m"},
    )["spec"]
    assert gate.pod_request(spec, "cpu") == (Fraction(21, 10), True)
    assert gate.pod_request(spec, "memory") == (Fraction(GI), True)


def test_a_container_without_a_request_is_zero_and_is_reported() -> None:
    spec = pod("p", container("100m"), container())["spec"]
    assert gate.pod_request(spec, "cpu") == (Fraction(1, 10), False)
    assert gate.pod_request(spec, "memory") == (Fraction(0), False)


def test_an_unreadable_request_is_refused_and_is_not_zero() -> None:
    spec = pod("p", container("100 m", "64Mi"))["spec"]
    with pytest.raises(gate.QuantityRefused):
        gate.pod_request(spec, "cpu")


# --------------------------------------------------------------------------
# The declared footprint
# --------------------------------------------------------------------------


def test_the_footprint_states_the_two_replica_topology_and_its_headroom() -> None:
    """Two API pods, two runtime pods, one collector, two surge pods, two hook pods."""
    footprint = gate.declared_footprint()
    assert footprint["schema"] == gate.FOOTPRINT_SCHEMA
    assert footprint["release"] == {
        "key": KEY,
        "name": "inferops",
        "namespace": NAMESPACE,
    }
    assert footprint["topology"] == {"apiReplicas": 2, "runtimeReplicas": 2}
    assert footprint["placementConstraints"] == []
    assert footprint["model"] == {
        "identifier": "qwen3-1-7b-q8-0",
        "artifactBytes": 1834426016,
        "cacheClaimName": CLAIM,
    }
    shape = [
        (c["component"], c["kind"], c["class"], c["replicas"], c["surgePods"])
        for c in footprint["components"]
    ]
    assert shape == [
        ("platform-api", "Deployment", "steady", 2, 1),
        ("serving-runtime", "Deployment", "steady", 2, 0),
        ("telemetry-collector", "Deployment", "steady", 1, 1),
        ("model-acquisition", "Job", "transient", 1, 0),
        ("connection-test", "Pod", "transient", 1, 0),
    ]
    totals = footprint["totals"]
    for name, expected in (
        ("steady", STEADY),
        ("rolloutHeadroom", HEADROOM),
        ("transient", TRANSIENT),
    ):
        assert totals[name] == {
            "pods": expected["pods"],
            "cpuRequestMillis": expected["cpu"],
            "memoryRequestBytes": expected["requests"],
            "memoryLimitBytes": expected["limits"],
        }, name
    assert totals["reserve"] == {
        "cpuMillis": RESERVE["cpu"],
        "memoryBytes": RESERVE["memory"],
    }
    assert totals["required"] == {
        "pods": REQUIRED["pods"],
        "cpuRequestMillis": REQUIRED["cpu"],
        "memoryRequestBytes": REQUIRED["requests"],
        "memoryLimitBytes": REQUIRED["limits"],
    }


def test_the_runtime_surge_is_zero_so_no_third_runtime_is_required() -> None:
    """The headroom is one API pod and one collector pod. It holds no model."""
    footprint = gate.declared_footprint()
    by_name = {c["component"]: c for c in footprint["components"]}
    assert by_name["serving-runtime"]["surgePods"] == 0
    assert by_name["serving-runtime"]["surgeSource"] == "runtime.rollout.maxSurge"
    assert by_name["platform-api"]["surgeSource"] == "api.rollout.maxSurge"
    runtime_limit = by_name["serving-runtime"]["pod"]["memoryLimitBytes"]
    assert runtime_limit == 3 * GI
    assert footprint["totals"]["rolloutHeadroom"]["memoryLimitBytes"] < runtime_limit


def test_the_footprint_names_the_bytes_of_each_file_it_was_read_from() -> None:
    sources = gate.declared_footprint()["sources"]
    for name in ("chartDefaults", "generatedValues", "application"):
        data = (REPO_ROOT / sources[name]["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert sources[name]["sha256"] == "sha256:" + hashlib.sha256(data).hexdigest()
    chart = yaml.safe_load((REPO_ROOT / "charts/inferops-llm/Chart.yaml").read_text())
    assert sources["chart"] == {
        "path": "charts/inferops-llm",
        "name": chart["name"],
        "version": chart["version"],
    }


def test_each_declared_application_reads_a_declared_desired_state_release() -> None:
    """The tool reads no release declaration. This compares its table with one.

    The tool takes the chart and the values file from the Application. For each
    desired-state release, those are the release's own generated values and the
    platform defaults that the release was derived from.
    """
    declared = {release_key(release): release for release in DESIRED_STATE_RELEASES}
    assert set(gate.APPLICATIONS) == set(declared)
    for key, release in declared.items():
        sources = gate.declared_footprint(key)["sources"]
        assert sources["application"]["path"] == gate.APPLICATIONS[key]
        assert sources["generatedValues"]["path"] == (
            f"{release.directory}/values.generated.yaml"
        )
        assert sources["chartDefaults"]["path"] == release.platform_defaults


def _values_object() -> dict[str, Any]:
    application = yaml.safe_load(
        (REPO_ROOT / gate.APPLICATIONS[KEY]).read_text(encoding="utf-8")
    )
    return application["spec"]["source"]["helm"]["valuesObject"]


def test_each_pod_of_the_render_is_a_component_of_the_footprint(tmp_path: Path) -> None:
    """The footprint is the chart's render, for the values the Application gives.

    The tool restates which pods the chart renders. This renders the chart with
    the generated values and the Application's values, and holds each pod
    template of the render to one component: its replicas, its surge, and the
    name, the requests, and the memory limit of each container. A pod that the
    chart renders and the footprint does not state fails here.

    The API image digest is the one value that the Application leaves to its
    procedure. The chart requires it, so this gives a placeholder. It changes no
    resource figure.

    This reads a render. It does not establish what a cluster schedules.
    """
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is not on PATH; see CONTRIBUTING.md for the commands")
    footprint = gate.declared_footprint()
    overlay = tmp_path / "application-values.yaml"
    overlay.write_text(yaml.safe_dump(_values_object()), encoding="utf-8")
    rendered = subprocess.run(
        [
            helm,
            "template",
            footprint["release"]["name"],
            str(REPO_ROOT / footprint["sources"]["chart"]["path"]),
            "--namespace",
            footprint["release"]["namespace"],
            "--values",
            str(REPO_ROOT / footprint["sources"]["generatedValues"]["path"]),
            "--values",
            str(overlay),
            "--set",
            "api.image.digest=sha256:" + "a" * 64,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    documents = [d for d in yaml.safe_load_all(rendered.stdout) if isinstance(d, dict)]

    found = []
    for document in documents:
        kind = document["kind"]
        if kind == "Pod":
            spec, replicas, surge = document["spec"], 1, 0
        elif kind in ("Deployment", "Job"):
            spec = document["spec"]["template"]["spec"]
            replicas = document["spec"].get("replicas", 1)
            strategy = document["spec"].get("strategy")
            if kind == "Job":
                surge = 0
            elif strategy is None:
                # The Kubernetes default: 25 percent of the replicas, rounded up.
                surge = -(-replicas * 25 // 100)
            else:
                assert strategy["type"] == "RollingUpdate"
                surge = strategy["rollingUpdate"]["maxSurge"]
        else:
            assert "template" not in document.get("spec", {}), kind
            continue
        for member in ("nodeSelector", "tolerations", "affinity", "overhead"):
            assert not spec.get(member), (kind, member)
        assert "resources" not in spec, kind
        assert not [c for c in spec.get("initContainers") or [] if "restartPolicy" in c]

        def stated(containers: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "name": c["name"],
                    "requests": {
                        "cpu": str(c["resources"]["requests"]["cpu"]),
                        "memory": str(c["resources"]["requests"]["memory"]),
                    },
                    "limits": {"memory": str(c["resources"]["limits"]["memory"])},
                }
                for c in containers
            ]

        found.append(
            {
                "kind": kind,
                "replicas": replicas,
                "surgePods": surge,
                "containers": stated(spec["containers"]),
                "initContainers": stated(spec.get("initContainers") or []),
            }
        )

    def reduced(component: dict[str, Any]) -> dict[str, Any]:
        return {
            "kind": component["kind"],
            "replicas": component["replicas"],
            "surgePods": component["surgePods"],
            "containers": [
                {k: v for k, v in c.items() if k != "source"}
                for c in component["containers"]
            ],
            "initContainers": [
                {k: v for k, v in c.items() if k != "source"}
                for c in component["initContainers"]
            ],
        }

    declared = [reduced(component) for component in footprint["components"]]

    def order(entry: dict[str, Any]) -> str:
        return entry["containers"][0]["name"]

    assert sorted(found, key=order) == sorted(declared, key=order)
    # The collector is the one Deployment whose surge is the Kubernetes default.
    strategies = {
        d["metadata"]["labels"]["app.kubernetes.io/component"]: d["spec"].get(
            "strategy"
        )
        for d in documents
        if d["kind"] == "Deployment"
    }
    assert [name for name, strategy in strategies.items() if strategy is None] == [
        "telemetry-collector"
    ]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A copy of the committed files that a footprint is read from."""
    footprint = gate.declared_footprint()
    paths = [
        footprint["sources"][name]["path"]
        for name in ("chartDefaults", "generatedValues", "application")
    ]
    paths.append(footprint["sources"]["chart"]["path"] + "/Chart.yaml")
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / path, target)
    return tmp_path


def _edit(root: Path, path: str, change: Any) -> None:
    target = root / path
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    change(document)
    target.write_text(yaml.safe_dump(document), encoding="utf-8")


APPLICATION = "infra/argocd/local-docker-desktop-support-assistant.yaml"
GENERATED = (
    "gitops/environments/local-docker-desktop/workloads/support-assistant/"
    "values.generated.yaml"
)
DEFAULTS = "charts/inferops-llm/values.yaml"


def test_the_copied_tree_gives_the_committed_footprint(tree: Path) -> None:
    assert gate.declared_footprint(root=tree) == gate.declared_footprint()


def test_the_footprint_follows_the_replica_counts_of_the_values(tree: Path) -> None:
    def change(values: dict[str, Any]) -> None:
        values["runtime"]["replicaCount"] = 3
        values["api"]["replicaCount"] = 4

    _edit(tree, GENERATED, change)
    footprint = gate.declared_footprint(root=tree)
    assert footprint["topology"] == {"apiReplicas": 4, "runtimeReplicas": 3}
    assert footprint["totals"]["steady"]["pods"] == 8
    assert footprint["totals"]["steady"]["cpuRequestMillis"] == 400 + 3000 + 100
    assert footprint["totals"]["steady"]["memoryLimitBytes"] == (
        4 * 512 * MI + 3 * 3 * GI + 512 * MI
    )


def test_the_application_values_are_merged_over_the_generated_values(
    tree: Path,
) -> None:
    """The collector is in the footprint because the Application deploys it."""

    def change(application: dict[str, Any]) -> None:
        values = application["spec"]["source"]["helm"]["valuesObject"]
        values["telemetry"]["collection"]["collector"]["deploy"] = False
        values["runtime"]["resources"] = {"requests": {"memory": "2500Mi"}}

    _edit(tree, APPLICATION, change)
    footprint = gate.declared_footprint(root=tree)
    names = [c["component"] for c in footprint["components"]]
    assert "telemetry-collector" not in names
    runtime = footprint["components"][names.index("serving-runtime")]
    # The one member is replaced. The other members of the block stay.
    assert runtime["containers"][0]["requests"] == {"cpu": "1", "memory": "2500Mi"}
    assert runtime["containers"][0]["limits"] == {"memory": "3Gi"}
    assert runtime["pod"]["memoryRequestBytes"] == 2500 * MI


def test_a_surge_of_the_runtime_adds_one_whole_runtime_to_the_headroom(
    tree: Path,
) -> None:
    def change(values: dict[str, Any]) -> None:
        values["runtime"]["rollout"] = {"maxSurge": 1, "maxUnavailable": 0}

    _edit(tree, GENERATED, change)
    headroom = gate.declared_footprint(root=tree)["totals"]["rolloutHeadroom"]
    assert headroom["pods"] == HEADROOM["pods"] + 1
    assert headroom["memoryLimitBytes"] == HEADROOM["limits"] + 3 * GI
    assert headroom["cpuRequestMillis"] == HEADROOM["cpu"] + 1000


def test_a_placement_constraint_is_stated_in_the_footprint(tree: Path) -> None:
    def change(application: dict[str, Any]) -> None:
        values = application["spec"]["source"]["helm"]["valuesObject"]
        values["runtime"]["nodeSelector"] = {"pool": "runtime"}
        values["api"]["tolerations"] = [{"operator": "Exists"}]

    _edit(tree, APPLICATION, change)
    assert gate.declared_footprint(root=tree)["placementConstraints"] == [
        "api.tolerations",
        "runtime.nodeSelector",
    ]


def _drop_runtime_limit(values: dict[str, Any]) -> None:
    del values["runtime"]["resources"]["limits"]["memory"]


def _other_values_file(application: dict[str, Any]) -> None:
    application["spec"]["source"]["helm"]["valueFiles"].append("/other.yaml")


def _other_chart(application: dict[str, Any]) -> None:
    application["spec"]["source"]["path"] = "charts/other"


def _chart_outside(application: dict[str, Any]) -> None:
    application["spec"]["source"]["path"] = "../charts/inferops-llm"


def _values_file_outside(application: dict[str, Any]) -> None:
    application["spec"]["source"]["helm"]["valueFiles"] = ["/../outside.yaml"]


def _values_file_beside_the_chart(application: dict[str, Any]) -> None:
    application["spec"]["source"]["helm"]["valueFiles"] = ["values.other.yaml"]


def _no_values_file(application: dict[str, Any]) -> None:
    application["spec"]["source"]["helm"]["valueFiles"] = []


def _inline_values(application: dict[str, Any]) -> None:
    application["spec"]["source"]["helm"]["values"] = "runtime:\n  replicaCount: 1\n"


def _parameters(application: dict[str, Any]) -> None:
    application["spec"]["source"]["helm"]["parameters"] = [
        {"name": "runtime.replicaCount", "value": "1"}
    ]


def _mock_profile(values: dict[str, Any]) -> None:
    values["profile"] = "mock"


def _unreadable_request(values: dict[str, Any]) -> None:
    values["api"]["resources"]["requests"]["cpu"] = "100 m"


def _replicas_as_text(values: dict[str, Any]) -> None:
    values["runtime"]["replicaCount"] = "2"


def _limit_below_request(values: dict[str, Any]) -> None:
    values["api"]["resources"]["limits"]["memory"] = "64Mi"


def _limit_removed_by_a_null(application: dict[str, Any]) -> None:
    values = application["spec"]["source"]["helm"]["valuesObject"]
    values["runtime"]["resources"] = {"limits": {"memory": None}}


@pytest.mark.parametrize(
    ("path", "change", "message"),
    [
        (GENERATED, _drop_runtime_limit, "runtime.resources.limits.memory is absent"),
        (APPLICATION, _other_values_file, "does not read one values file"),
        (APPLICATION, _no_values_file, "does not read one values file"),
        (APPLICATION, _values_file_beside_the_chart, "does not read one values file"),
        (APPLICATION, _values_file_outside, "not a path inside the repository"),
        (APPLICATION, _chart_outside, "not a path inside the repository"),
        (APPLICATION, _other_chart, "was not read"),
        (APPLICATION, _inline_values, "does not merge"),
        (APPLICATION, _parameters, "does not merge"),
        (GENERATED, _mock_profile, "not the real profile"),
        (DEFAULTS, _unreadable_request, "not readable"),
        (DEFAULTS, _limit_below_request, "is below its memory request"),
        (
            APPLICATION,
            _limit_removed_by_a_null,
            "runtime.resources.limits.memory is absent",
        ),
        (GENERATED, _replicas_as_text, "runtime.replicaCount is not a whole number"),
    ],
)
def test_committed_files_that_give_no_one_footprint_are_refused(
    tree: Path, path: str, change: Any, message: str
) -> None:
    """A value that the gate cannot bound, or cannot attribute, gives no footprint."""
    if change is _drop_runtime_limit:
        # The limit is the generated file's own member, over the chart's default.
        _edit(tree, DEFAULTS, _drop_runtime_limit)
    _edit(tree, path, change)
    with pytest.raises(gate.FootprintRefused) as raised:
        gate.declared_footprint(root=tree)
    assert message in str(raised.value)


def test_an_absent_committed_file_gives_no_footprint(tree: Path) -> None:
    (tree / APPLICATION).unlink()
    with pytest.raises(gate.FootprintRefused, match="was not read"):
        gate.declared_footprint(root=tree)


def test_an_undeclared_release_gives_no_footprint() -> None:
    with pytest.raises(gate.FootprintRefused, match="no Application is declared"):
        gate.declared_footprint("local-kind/support-assistant")


# --------------------------------------------------------------------------
# An accepted cluster
# --------------------------------------------------------------------------


def test_a_cluster_with_room_is_accepted_and_the_record_states_each_input(
    tmp_path: Path,
) -> None:
    record = gate.build_record(
        collection(
            tmp_path,
            claims=listed([claim()]),
            engine={"cpus": 12, "memoryBytes": 16 * GI},
            version={"serverVersion": {"gitVersion": "v1.36.1"}},
        )
    )
    assert record["schema"] == gate.RECORD_SCHEMA
    assert record["result"] == gate.ACCEPTED
    assert record["refusal"] == {"categories": [], "rules": []}
    assert set(states(record).values()) == {gate.HELD}
    assert [f["ruleId"] for f in record["findings"]] == [r.rule_id for r in gate.RULES]

    [stated] = record["nodes"]
    assert stated["name"] == NODE
    assert stated["allocatable"] == {
        "cpuMillis": 12000,
        "memoryBytes": 16 * GI,
        "pods": 110,
        "ephemeralStorageBytes": 100 * GI,
    }
    assert stated["capacity"] == stated["allocatable"]
    reservations = record["reservations"]
    assert reservations["unfinishedPods"] == 9
    assert reservations["cpuRequestMillis"] == 950
    assert reservations["memoryRequestBytes"] == 290 * MI
    assert reservations["podsWithAContainerThatStatesNoCpuRequest"] == 2
    assert reservations["podsWithAContainerThatStatesNoMemoryRequest"] == 5
    assert reservations["byNamespace"] == [
        {
            "namespace": "kube-system",
            "pods": 8,
            "cpuRequestMillis": 950,
            "memoryRequestBytes": 290 * MI,
        },
        {
            "namespace": "local-path-storage",
            "pods": 1,
            "cpuRequestMillis": 0,
            "memoryRequestBytes": 0,
        },
    ]
    assert record["footprint"] == gate.declared_footprint()
    assert record["footprintSha256"] == gate.footprint_digest(record["footprint"])
    assert record["environment"] == {
        "provider": "synthetic",
        "kubernetesServerVersion": "v1.36.1",
        "containerEngine": {"cpus": 12, "memoryBytes": 16 * GI},
    }
    assert record["modelCache"]["claim"] == {
        "name": CLAIM,
        "phase": "Bound",
        "accessModes": ["ReadWriteOnce"],
        "storageClassName": "standard",
        "requestedStorageBytes": 4 * GI,
        "capacityStorageBytes": 4 * GI,
    }
    assert record["units"] == dict(gate.UNITS)
    assert record["doesNotEstablish"] == list(gate.DOES_NOT_ESTABLISH)

    assert finding(record, "cpu-requests-fit")["measure"] == {
        "required": REQUIRED["cpu"],
        "allocatable": 12000,
        "requestedByUnfinishedPods": 950,
        "available": 11050,
        "shortfall": 0,
        "unit": "millicores",
    }
    assert finding(record, "memory-limits-fit")["measure"] == {
        "required": REQUIRED["limits"],
        "allocatable": 16 * GI,
        "requestedByUnfinishedPods": 290 * MI,
        "available": 16 * GI - 290 * MI,
        "shortfall": 0,
        "unit": "bytes",
    }
    assert finding(record, "pod-count-fits")["measure"] == {
        "required": 9,
        "allocatable": 110,
        "requestedByUnfinishedPods": 9,
        "available": 101,
        "shortfall": 0,
        "unit": "pods",
    }


def test_the_same_collection_gives_the_same_record_bytes(tmp_path: Path) -> None:
    directory = collection(tmp_path)
    first = gate.record_text(gate.build_record(directory))
    assert gate.record_text(gate.build_record(directory)) == first
    assert first.endswith("\n") and "\r" not in first
    assert json.loads(first) == gate.build_record(directory)


def test_the_engine_and_the_server_version_are_stated_and_decide_nothing(
    tmp_path: Path,
) -> None:
    """No rule reads the engine. A node allocates what the scheduler places against."""
    small = gate.build_record(
        collection(tmp_path / "a", engine={"cpus": 1, "memoryBytes": 1})
    )
    assert small["result"] == gate.ACCEPTED
    assert small["environment"]["containerEngine"] == {"cpus": 1, "memoryBytes": 1}
    cases: tuple[Any, ...] = (
        {"cpus": "12", "memoryBytes": 1},
        {"cpus": True},
        [],
        b"{",
    )
    for unusable in cases:
        record = gate.build_record(collection(tmp_path / "b", engine=unusable))
        assert record["environment"]["containerEngine"] is None
        assert record["environment"]["kubernetesServerVersion"] is None
        assert record["result"] == gate.ACCEPTED


# --------------------------------------------------------------------------
# An insufficient cluster
# --------------------------------------------------------------------------

EXISTING_CPU = 950
EXISTING_MEMORY = 290 * MI


@pytest.mark.parametrize(
    ("rule_id", "figures", "shortfall", "unit"),
    [
        ("cpu-requests-fit", {"cpu": f"{REQUIRED['cpu'] + EXISTING_CPU}m"}, 0, None),
        (
            "cpu-requests-fit",
            {"cpu": f"{REQUIRED['cpu'] + EXISTING_CPU - 1}m"},
            1,
            "millicores",
        ),
        (
            "memory-limits-fit",
            {"memory": REQUIRED["limits"] + EXISTING_MEMORY},
            0,
            None,
        ),
        (
            "memory-limits-fit",
            {"memory": REQUIRED["limits"] + EXISTING_MEMORY - 1},
            1,
            "bytes",
        ),
        ("pod-count-fits", {"pods": "18"}, 0, None),
        ("pod-count-fits", {"pods": "17"}, 1, "pods"),
    ],
)
def test_each_figure_is_held_at_the_requirement_and_refused_one_unit_below(
    tmp_path: Path,
    rule_id: str,
    figures: dict[str, Any],
    shortfall: int,
    unit: str | None,
) -> None:
    record = gate.build_record(collection(tmp_path, nodes=listed([node(**figures)])))
    measure = finding(record, rule_id)["measure"]
    assert measure["shortfall"] == shortfall
    assert measure["required"] - measure["available"] == shortfall
    if shortfall == 0:
        assert record["result"] == gate.ACCEPTED
        return
    refused_only_by(record, rule_id, gate.INSUFFICIENT)
    assert finding(record, rule_id)["state"] == gate.NOT_HELD
    assert measure["unit"] == unit
    assert f"{shortfall} {unit} short" in finding(record, rule_id)["detail"]


def test_every_shortfall_is_stated_at_once(tmp_path: Path) -> None:
    """One reading names each figure that is short, and not the first one only."""
    record = gate.build_record(
        collection(tmp_path, nodes=listed([node(cpu="2", memory="4Gi", pods="10")]))
    )
    assert record["result"] == gate.REFUSED
    assert record["refusal"] == {
        "categories": [gate.INSUFFICIENT],
        "rules": ["pod-count-fits", "cpu-requests-fit", "memory-limits-fit"],
    }


def test_memory_is_refused_on_the_limits_where_the_requests_would_fit(
    tmp_path: Path,
) -> None:
    """The gate holds the memory limits to the node. The requests are smaller."""
    memory = REQUIRED["requests"] + EXISTING_MEMORY
    record = gate.build_record(
        collection(tmp_path, nodes=listed([node(memory=memory)]))
    )
    refused_only_by(record, "memory-limits-fit", gate.INSUFFICIENT)
    assert finding(record, "memory-limits-fit")["measure"]["shortfall"] == (
        REQUIRED["limits"] - REQUIRED["requests"]
    )


def test_a_pod_that_the_node_already_holds_lowers_what_is_available(
    tmp_path: Path,
) -> None:
    memory = REQUIRED["limits"] + EXISTING_MEMORY
    other = pod("other", container("100m", "1Gi"), namespace="another-team")
    record = gate.build_record(
        collection(
            tmp_path,
            nodes=listed([node(memory=memory)]),
            pods=listed([*system_pods(), other]),
        )
    )
    refused_only_by(record, "memory-limits-fit", gate.INSUFFICIENT)
    assert finding(record, "memory-limits-fit")["measure"]["shortfall"] == GI
    assert {
        "namespace": "another-team",
        "pods": 1,
        "cpuRequestMillis": 100,
        "memoryRequestBytes": GI,
    } in record["reservations"]["byNamespace"]


def test_which_pods_are_counted_against_the_node(tmp_path: Path) -> None:
    """A finished pod and a pod on another node hold nothing on this node.

    A pod that no node holds yet is counted, because it can be placed here.
    """
    pods = [
        pod("running", container("100m", "100Mi")),
        pod("pending-placed", container("100m", "100Mi"), phase="Pending"),
        pod("unscheduled", container("300m", "300Mi"), on=None, phase="Pending"),
        pod("done", container("4", "8Gi"), phase="Succeeded"),
        pod("crashed", container("4", "8Gi"), phase="Failed"),
        pod("elsewhere", container("4", "8Gi"), on="node-cordoned"),
        pod(
            "init-heavy",
            container("100m", "10Mi"),
            init=[container("900m", "1Gi")],
        ),
    ]
    record = gate.build_record(
        collection(
            tmp_path,
            nodes=listed([node(), node("node-cordoned", unschedulable=True)]),
            pods=listed(pods),
        )
    )
    reservations = record["reservations"]
    assert reservations["unfinishedPods"] == 4
    assert reservations["finishedPodsNotCounted"] == 2
    assert reservations["podsOnAnotherNodeNotCounted"] == 1
    assert reservations["unscheduledPodsCounted"] == 1
    assert reservations["cpuRequestMillis"] == 100 + 100 + 300 + 900
    assert reservations["memoryRequestBytes"] == 500 * MI + GI
    assert record["result"] == gate.ACCEPTED
    assert finding(record, "one-schedulable-node")["state"] == gate.HELD


# --------------------------------------------------------------------------
# An ambiguous cluster
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "file", ["nodes.json", "pods.json", "namespace-limits.json", "claims.json"]
)
@pytest.mark.parametrize(
    "content",
    [
        ABSENT,
        b"",
        b"{",
        b"[]",
        b"null",
        b'{"items": null}',
        b'{"items": {}}',
        b'{"items": ["node"]}',
        b"\xff\xfe",
    ],
)
def test_a_read_that_was_not_made_is_not_an_empty_list(
    tmp_path: Path, file: str, content: Any
) -> None:
    """An absent file, a file that is not JSON, and a file that is not a list refuse."""
    argument = {
        "nodes.json": "nodes",
        "pods.json": "pods",
        "namespace-limits.json": "limits",
        "claims.json": "claims",
    }[file]
    record = gate.build_record(collection(tmp_path, **{argument: content}))
    assert record["result"] == gate.REFUSED
    assert record["refusal"]["categories"] == [gate.AMBIGUOUS]
    complete = finding(record, "cluster-reads-complete")
    assert complete["state"] == gate.NOT_OBSERVED
    assert file in complete["detail"]
    assert gate.HELD not in {
        states(record)[rule_id]
        for rule_id in {
            "nodes.json": (
                "one-schedulable-node",
                "node-ready-without-pressure",
                "node-states-no-blocking-taint",
                "quantities-readable",
                "pod-count-fits",
                "cpu-requests-fit",
                "memory-limits-fit",
            ),
            "pods.json": (
                "release-is-not-installed",
                "quantities-readable",
                "pod-count-fits",
                "cpu-requests-fit",
                "memory-limits-fit",
            ),
            "namespace-limits.json": ("namespace-states-no-quota-or-limit-range",),
            "claims.json": ("model-cache-claim-holds-artifact",),
        }[file]
    }


def test_an_empty_cluster_is_refused_and_not_read_as_room(tmp_path: Path) -> None:
    record = gate.build_record(collection(tmp_path, nodes=listed([]), pods=listed([])))
    assert record["result"] == gate.REFUSED
    assert states(record)["one-schedulable-node"] == gate.NOT_HELD
    assert (
        "0 schedulable node(s) of 0 node(s)"
        in finding(record, "one-schedulable-node")["detail"]
    )
    for rule_id in ("pod-count-fits", "cpu-requests-fit", "memory-limits-fit"):
        assert states(record)[rule_id] == gate.NOT_OBSERVED


def test_two_schedulable_nodes_are_refused_however_large_they_are(
    tmp_path: Path,
) -> None:
    """The gate adds figures for one node. It places no pod among nodes."""
    record = gate.build_record(
        collection(
            tmp_path,
            nodes=listed(
                [
                    node(cpu="64", memory="256Gi"),
                    node("node-b", cpu="64", memory="256Gi"),
                ]
            ),
        )
    )
    assert record["result"] == gate.REFUSED
    assert record["refusal"]["categories"] == [gate.AMBIGUOUS]
    assert record["refusal"]["rules"][0] == "one-schedulable-node"
    assert states(record)["one-schedulable-node"] == gate.NOT_HELD
    for rule_id in (
        "node-ready-without-pressure",
        "node-states-no-blocking-taint",
        "pod-count-fits",
        "cpu-requests-fit",
        "memory-limits-fit",
    ):
        assert states(record)[rule_id] == gate.NOT_OBSERVED


def test_a_cordoned_node_alone_is_no_schedulable_node(tmp_path: Path) -> None:
    record = gate.build_record(
        collection(tmp_path, nodes=listed([node(unschedulable=True)]))
    )
    assert states(record)["one-schedulable-node"] == gate.NOT_HELD
    assert record["result"] == gate.REFUSED


@pytest.mark.parametrize(
    ("change", "rule_id"),
    [
        ({"ready": "False"}, "node-ready-without-pressure"),
        ({"ready": "Unknown"}, "node-ready-without-pressure"),
        ({"pressure": {"MemoryPressure": "True"}}, "node-ready-without-pressure"),
        ({"pressure": {"DiskPressure": "True"}}, "node-ready-without-pressure"),
        ({"pressure": {"PIDPressure": "Unknown"}}, "node-ready-without-pressure"),
        (
            {"taints": [{"key": "dedicated", "effect": "NoSchedule"}]},
            "node-states-no-blocking-taint",
        ),
        (
            {
                "taints": [
                    {"key": "node.kubernetes.io/unreachable", "effect": "NoExecute"}
                ]
            },
            "node-states-no-blocking-taint",
        ),
    ],
)
def test_a_node_that_does_not_accept_the_release_is_refused(
    tmp_path: Path, change: dict[str, Any], rule_id: str
) -> None:
    record = gate.build_record(collection(tmp_path, nodes=listed([node(**change)])))
    refused_only_by(record, rule_id, gate.AMBIGUOUS)


def test_a_node_without_a_ready_condition_is_refused(tmp_path: Path) -> None:
    bare = node()
    bare["status"]["conditions"] = []
    record = gate.build_record(collection(tmp_path, nodes=listed([bare])))
    refused_only_by(record, "node-ready-without-pressure", gate.AMBIGUOUS)


def test_a_taint_that_only_prefers_is_not_a_refusal(tmp_path: Path) -> None:
    preferring = node(taints=[{"key": "spot", "effect": "PreferNoSchedule"}])
    record = gate.build_record(collection(tmp_path, nodes=listed([preferring])))
    assert record["result"] == gate.ACCEPTED


@pytest.mark.parametrize(
    "nodes",
    [
        [node(cpu="twelve")],
        [node(memory="16 Gi")],
        [node(memory="-16Gi")],
        [node(pods="110 pods")],
    ],
)
def test_an_unreadable_figure_of_the_node_is_refused(
    tmp_path: Path, nodes: list[dict[str, Any]]
) -> None:
    record = gate.build_record(collection(tmp_path, nodes=listed(nodes)))
    assert record["result"] == gate.REFUSED
    assert record["refusal"]["categories"] == [gate.AMBIGUOUS]
    assert states(record)["quantities-readable"] == gate.NOT_HELD
    for rule_id in ("pod-count-fits", "cpu-requests-fit", "memory-limits-fit"):
        assert states(record)[rule_id] == gate.NOT_OBSERVED


def test_a_node_that_states_no_allocatable_figure_is_refused(tmp_path: Path) -> None:
    silent = node()
    del silent["status"]["allocatable"]["memory"]
    record = gate.build_record(collection(tmp_path, nodes=listed([silent])))
    assert record["result"] == gate.REFUSED
    assert record["refusal"]["categories"] == [gate.AMBIGUOUS]
    assert states(record)["memory-limits-fit"] == gate.NOT_OBSERVED
    assert record["nodes"][0]["allocatable"]["memoryBytes"] is None


def test_an_unreadable_request_of_a_pod_is_refused_and_not_counted_as_zero(
    tmp_path: Path,
) -> None:
    pods = [*system_pods(), pod("odd", container("100m", "1Gib"))]
    record = gate.build_record(collection(tmp_path, pods=listed(pods)))
    assert record["result"] == gate.REFUSED
    assert record["refusal"]["categories"] == [gate.AMBIGUOUS]
    readable = finding(record, "quantities-readable")
    assert readable["state"] == gate.NOT_HELD
    assert "kube-system/odd" in readable["detail"]
    assert states(record)["memory-limits-fit"] == gate.NOT_OBSERVED


def test_an_unreadable_request_of_a_finished_pod_decides_nothing(
    tmp_path: Path,
) -> None:
    pods = [*system_pods(), pod("odd", container("x", "y"), phase="Succeeded")]
    assert (
        gate.build_record(collection(tmp_path, pods=listed(pods)))["result"]
        == gate.ACCEPTED
    )


@pytest.mark.parametrize("kind", ["ResourceQuota", "LimitRange"])
def test_a_quota_or_a_limit_range_in_the_namespace_is_refused(
    tmp_path: Path, kind: str
) -> None:
    """Either object can refuse a pod, or change what a pod requests."""
    item = {"kind": kind, "metadata": {"name": "bounds", "namespace": NAMESPACE}}
    record = gate.build_record(collection(tmp_path, limits=listed([item])))
    refused_only_by(record, "namespace-states-no-quota-or-limit-range", gate.AMBIGUOUS)
    assert (
        f"{kind}/bounds"
        in finding(record, "namespace-states-no-quota-or-limit-range")["detail"]
    )


def test_a_release_that_is_already_installed_is_refused(tmp_path: Path) -> None:
    """Its pods are in the node's figures. The gate would count the release twice."""
    installed = pod(
        "inferops-inferops-llm-runtime-1",
        container("1", "2Gi"),
        namespace=NAMESPACE,
        labels={"app.kubernetes.io/instance": "inferops"},
    )
    record = gate.build_record(
        collection(tmp_path, pods=listed([*system_pods(), installed]))
    )
    refused_only_by(record, "release-is-not-installed", gate.AMBIGUOUS)
    assert record["reservations"]["releasePods"] == [
        f"{NAMESPACE}/inferops-inferops-llm-runtime-1"
    ]


@pytest.mark.parametrize(
    "other",
    [
        {
            "namespace": "another-team",
            "labels": {"app.kubernetes.io/instance": "inferops"},
        },
        {"namespace": NAMESPACE, "labels": {"app.kubernetes.io/instance": "other"}},
        {
            "namespace": NAMESPACE,
            "labels": {"app.kubernetes.io/instance": "inferops"},
            "phase": "Succeeded",
        },
    ],
)
def test_a_pod_that_is_not_an_unfinished_pod_of_the_release_is_not_the_release(
    tmp_path: Path, other: dict[str, Any]
) -> None:
    extra = pod("p", container("10m", "10Mi"), **other)
    record = gate.build_record(
        collection(tmp_path, pods=listed([*system_pods(), extra]))
    )
    assert record["result"] == gate.ACCEPTED
    assert record["reservations"]["releasePods"] == []


def test_a_placement_constraint_of_the_release_is_refused(tmp_path: Path) -> None:
    footprint = gate.declared_footprint()
    footprint["placementConstraints"] = ["runtime.nodeSelector"]
    record = gate.build_record(collection(tmp_path, footprint=footprint))
    refused_only_by(record, "release-states-no-placement-constraint", gate.AMBIGUOUS)


def test_an_insufficient_and_an_ambiguous_cluster_names_both_categories(
    tmp_path: Path,
) -> None:
    item = {"kind": "LimitRange", "metadata": {"name": "l", "namespace": NAMESPACE}}
    record = gate.build_record(
        collection(tmp_path, nodes=listed([node(cpu="1")]), limits=listed([item]))
    )
    assert record["refusal"] == {
        "categories": [gate.AMBIGUOUS, gate.INSUFFICIENT],
        "rules": ["namespace-states-no-quota-or-limit-range", "cpu-requests-fit"],
    }


# --------------------------------------------------------------------------
# The model cache claim
# --------------------------------------------------------------------------

ARTIFACT = 1834426016


def test_an_absent_claim_is_not_observed_and_does_not_refuse(tmp_path: Path) -> None:
    """The prerequisites create the claim. The gate can run before them."""
    record = gate.build_record(collection(tmp_path, claims=listed([])))
    rule = finding(record, "model-cache-claim-holds-artifact")
    assert rule["state"] == gate.NOT_OBSERVED
    assert rule["required"] is False
    assert "measure" not in rule
    assert record["modelCache"]["claim"] is None
    assert record["result"] == gate.ACCEPTED


def test_a_claim_of_another_name_is_not_the_model_cache(tmp_path: Path) -> None:
    record = gate.build_record(
        collection(tmp_path, claims=listed([claim(name="other", capacity="1Mi")]))
    )
    assert states(record)["model-cache-claim-holds-artifact"] == gate.NOT_OBSERVED
    assert record["result"] == gate.ACCEPTED


@pytest.mark.parametrize(
    ("capacity", "requested", "state", "basis"),
    [
        (ARTIFACT, "1Mi", gate.HELD, "capacity"),
        (ARTIFACT - 1, "8Gi", gate.NOT_HELD, "capacity"),
        (None, ARTIFACT, gate.HELD, "request"),
        (None, ARTIFACT - 1, gate.NOT_HELD, "request"),
    ],
)
def test_a_claim_is_held_to_the_byte_count_of_the_artifact(
    tmp_path: Path, capacity: object, requested: object, state: str, basis: str
) -> None:
    """The capacity of a bound claim is compared. An unbound claim states a request."""
    record = gate.build_record(
        collection(
            tmp_path, claims=listed([claim(capacity=capacity, request=requested)])
        )
    )
    rule = finding(record, "model-cache-claim-holds-artifact")
    assert rule["state"] == state
    assert f"the claim's {basis} is" in rule["detail"]
    assert rule["measure"]["required"] == ARTIFACT
    if state == gate.NOT_HELD:
        refused_only_by(record, "model-cache-claim-holds-artifact", gate.INSUFFICIENT)
        assert rule["measure"]["shortfall"] == 1
    else:
        assert record["result"] == gate.ACCEPTED


def test_a_claim_with_an_unreadable_size_is_refused(tmp_path: Path) -> None:
    record = gate.build_record(
        collection(tmp_path, claims=listed([claim(capacity="4 Gi")]))
    )
    assert record["result"] == gate.REFUSED
    assert states(record)["quantities-readable"] == gate.NOT_HELD


# --------------------------------------------------------------------------
# What is not a collection
# --------------------------------------------------------------------------


def _without(document: dict[str, Any], member: str) -> dict[str, Any]:
    return {name: value for name, value in document.items() if name != member}


@pytest.mark.parametrize(
    ("run", "message"),
    [
        (ABSENT, "no readable run.json"),
        (b"{", "no readable run.json"),
        ([], "no readable run.json"),
        (header(schema="inferops.io/other/v1"), "does not state"),
        (_without(header(), "provider"), "states no provider"),
        (_without(header(), "collectedAt"), "states no collectedAt"),
        (header(context=" "), "states no context"),
        (header(executingCommit="abc1234"), "no full executing commit"),
        (header(executingCommit="G" * 40), "no full executing commit"),
        (header(releaseKey="local-kind/support-assistant"), "names the release"),
        (header(namespace="default"), "names the namespace"),
    ],
)
def test_a_directory_without_a_usable_header_is_not_a_collection(
    tmp_path: Path, run: Any, message: str
) -> None:
    with pytest.raises(gate.CollectionRefused) as raised:
        gate.build_record(collection(tmp_path, run=run))
    assert message in str(raised.value)


def _lowered_reserve(footprint: dict[str, Any]) -> None:
    footprint["totals"]["reserve"] = {"cpuMillis": 0, "memoryBytes": 0}


def _lowered_requirement(footprint: dict[str, Any]) -> None:
    footprint["totals"]["required"]["memoryLimitBytes"] -= 1


def _lowered_pod(footprint: dict[str, Any]) -> None:
    footprint["components"][1]["pod"]["memoryLimitBytes"] = GI


def _lowered_headroom(footprint: dict[str, Any]) -> None:
    footprint["totals"]["rolloutHeadroom"] = dict.fromkeys(
        footprint["totals"]["rolloutHeadroom"], 0
    )


def _no_components(footprint: dict[str, Any]) -> None:
    footprint["components"] = []
    footprint.update(core._derived(footprint))


def _negative_replicas(footprint: dict[str, Any]) -> None:
    footprint["components"][1]["replicas"] = -2
    footprint.update(core._derived(footprint))


def _text_replicas(footprint: dict[str, Any]) -> None:
    footprint["components"][1]["replicas"] = "2"


def _unreadable_limit(footprint: dict[str, Any]) -> None:
    footprint["components"][1]["containers"][0]["limits"]["memory"] = "3 Gi"


def _no_model(footprint: dict[str, Any]) -> None:
    del footprint["model"]


def _other_schema(footprint: dict[str, Any]) -> None:
    footprint["schema"] = "inferops.io/other/v1"


def _components_as_text(footprint: dict[str, Any]) -> None:
    footprint["components"] = "none"


@pytest.mark.parametrize(
    "change",
    [
        _lowered_reserve,
        _lowered_requirement,
        _lowered_pod,
        _lowered_headroom,
        _no_components,
        _negative_replicas,
        _text_replicas,
        _unreadable_limit,
        _no_model,
        _other_schema,
        _components_as_text,
    ],
)
def test_a_footprint_with_a_lowered_or_an_unusable_figure_is_not_a_collection(
    tmp_path: Path, change: Any
) -> None:
    """A derived figure is computed again. A stored figure is not trusted.

    Each of the first four changes would turn a refusal into an acceptance on a
    node that is short. None of them gives a record.
    """
    footprint = gate.declared_footprint()
    change(footprint)
    short = node(memory=REQUIRED["limits"] + EXISTING_MEMORY - 1)
    with pytest.raises(gate.CollectionRefused):
        gate.build_record(
            collection(tmp_path, footprint=footprint, nodes=listed([short]))
        )


@pytest.mark.parametrize("footprint", [ABSENT, b"{", [], "footprint"])
def test_a_directory_without_a_footprint_is_not_a_collection(
    tmp_path: Path, footprint: Any
) -> None:
    with pytest.raises(gate.CollectionRefused, match=r"no readable footprint\.json"):
        gate.build_record(collection(tmp_path, footprint=footprint))


@pytest.mark.parametrize("argument", ["limits", "claims"])
def test_a_namespaced_read_of_another_namespace_is_not_a_collection(
    tmp_path: Path, argument: str
) -> None:
    """A read of another namespace says nothing about the release namespace."""
    item = {"kind": "LimitRange", "metadata": {"name": "l", "namespace": "default"}}
    stranger = claim(namespace="default") if argument == "claims" else item
    with pytest.raises(gate.CollectionRefused, match="another namespace: default"):
        gate.build_record(collection(tmp_path, **{argument: listed([stranger])}))


def test_a_self_consistent_footprint_of_fewer_replicas_gives_a_record_but_is_stale(
    tmp_path: Path,
) -> None:
    """What ``build_record`` cannot see, and what ``stale_footprint`` sees.

    A footprint that states one runtime replica, with each derived figure
    computed again, is a usable footprint. Its record accepts a node that the
    declared release does not fit. The comparison with the committed files is
    what refuses it, and the command makes that comparison first.
    """
    smaller = copy.deepcopy(gate.declared_footprint())
    smaller["components"][1]["replicas"] = 1
    smaller["topology"]["runtimeReplicas"] = 1
    smaller = core._derived(smaller)
    short = node(memory=REQUIRED["limits"] + EXISTING_MEMORY - 1)
    directory = collection(tmp_path, footprint=smaller, nodes=listed([short]))

    assert gate.build_record(directory)["result"] == gate.ACCEPTED
    stale = gate.stale_footprint(directory)
    assert stale is not None and "is not the footprint" in stale
    assert gate.stale_footprint(collection(tmp_path / "current")) is None


# --------------------------------------------------------------------------
# The record's vocabulary
# --------------------------------------------------------------------------


def test_the_rules_are_distinct_and_each_has_one_of_two_categories() -> None:
    identifiers = [rule.rule_id for rule in gate.RULES]
    assert len(identifiers) == len(set(identifiers)) == 12
    assert {rule.category for rule in gate.RULES} == {gate.AMBIGUOUS, gate.INSUFFICIENT}
    assert [rule.rule_id for rule in gate.RULES if not rule.required] == [
        "model-cache-claim-holds-artifact"
    ]
    for rule in gate.RULES:
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", rule.rule_id), rule.rule_id
        assert rule.statement.endswith("."), rule.rule_id
    assert gate.RESULT_STATES == (gate.ACCEPTED, gate.REFUSED)


EVALUATIVE = (
    "production-ready",
    "reliable",
    "highly available",
    "secure",
    "robust",
    "proven",
    "guarantee",
    "zero downtime",
)


def test_the_record_uses_no_evaluative_word(tmp_path: Path) -> None:
    text = gate.record_text(gate.build_record(collection(tmp_path))).lower()
    for word in EVALUATIVE:
        assert word not in text, word
    for sentence in gate.DOES_NOT_ESTABLISH:
        assert sentence.startswith("A record does not establish "), sentence


def test_the_page_states_each_rule_each_limit_and_each_figure() -> None:
    """The page restates the tool's tables. This holds each row to the tool."""
    text = " ".join(DOCUMENT_PATH.read_text(encoding="utf-8").split())
    for rule in gate.RULES:
        marker = "" if rule.required else " (not required)"
        assert f"| `{rule.rule_id}`{marker} | {rule.category} | {rule.statement} |" in (
            text
        ), rule.rule_id
    required = sum(rule.required for rule in gate.RULES)
    assert f"{len(gate.RULES)} rules. {required} are required." in text
    for sentence in gate.DOES_NOT_ESTABLISH:
        assert f"- {sentence}" in text, sentence
    for schema in (gate.RECORD_SCHEMA, gate.FOOTPRINT_SCHEMA, gate.COLLECTION_SCHEMA):
        assert f"`{schema}`" in text, schema

    footprint = gate.declared_footprint()
    assert f"At chart version `{footprint['sources']['chart']['version']}`" in text
    for component in footprint["components"]:
        pod = component["pod"]
        assert (
            f"| `{component['component']}` | {component['kind']} | "
            f"{component['class']} | {component['replicas']} | "
            f"{component['surgePods']} | {pod['cpuRequestMillis']:,} | "
            f"{pod['memoryRequestBytes']:,} | {pod['memoryLimitBytes']:,} |"
        ) in text, component["component"]
    totals = footprint["totals"]
    for name in ("steady", "rolloutHeadroom", "transient"):
        part = totals[name]
        assert (
            f"| {part['pods']} | {part['cpuRequestMillis']:,} | "
            f"{part['memoryRequestBytes']:,} | {part['memoryLimitBytes']:,} |"
        ) in text, name
    need = totals["required"]
    assert (
        f"| **Required** | **{need['pods']}** | **{need['cpuRequestMillis']:,}** | "
        f"**{need['memoryRequestBytes']:,}** | **{need['memoryLimitBytes']:,}** |"
    ) in text
    assert f"a model of {footprint['model']['artifactBytes']:,} bytes" in text
    for name in EXPECTED_CASES:
        assert f"| `{name}` | `{EXPECTED_CASES[name][0]}`" in text, name
    assert f"holds {NUMBER_WORDS[len(EXPECTED_CASES)]} collections" in text
    # The figures of the comparison with the V1 preflight.
    capacity = json.loads(V1_DESCRIPTOR.read_text(encoding="utf-8"))["capacity"]
    assert f"{capacity['minimumEngineMemoryBytes']:,} bytes of memory" in text
    assert f"fewer than {capacity['minimumEngineCpus']} processors" in text
    assert f"at least {need['memoryLimitBytes']:,} bytes" in text
    assert need["memoryLimitBytes"] > capacity["minimumEngineMemoryBytes"]
    assert need["cpuRequestMillis"] < capacity["minimumEngineCpus"] * 1000
    assert f"requires {need['cpuRequestMillis']:,} millicores" in text


NUMBER_WORDS = {5: "five", 6: "six", 7: "seven", 8: "eight"}


# --------------------------------------------------------------------------
# Continuity with the V1 preflight
# --------------------------------------------------------------------------


def test_the_reserve_and_the_exit_status_are_the_v1_preflights() -> None:
    """No figure of the V1 gate is lowered here."""
    capacity = json.loads(V1_DESCRIPTOR.read_text(encoding="utf-8"))["capacity"]
    assert {
        "cpuMillis": capacity["headroomCpuMillis"],
        "memoryBytes": capacity["headroomMemoryBytes"],
    } == gate.RESERVE
    assert gate.REFUSED_EXIT == multi_replica_cli.EXIT_CAPACITY == 5


def test_the_requirement_is_not_below_what_the_v1_preflight_requires() -> None:
    """The V1 gate requires requests and limits of the Deployments and one driver.

    This gate requires the same Deployments, and it adds the surge pods and the
    hook pods. So each of its two figures is larger than the V1 figure.
    """
    capacity = json.loads(V1_DESCRIPTOR.read_text(encoding="utf-8"))["capacity"]
    v1_cpu = capacity["requestedCpuMillis"] + capacity["headroomCpuMillis"]
    v1_memory = capacity["peakMemoryBytes"] + capacity["headroomMemoryBytes"]
    required = gate.declared_footprint()["totals"]["required"]
    assert required["cpuRequestMillis"] - v1_cpu == 300
    assert required["memoryLimitBytes"] - v1_memory == 1152 * MI


def _v1_program() -> str:
    text = V1_SCRIPT.read_text(encoding="utf-8")
    start = text.index("<<'CAPACITY_PYTHON'\n") + len("<<'CAPACITY_PYTHON'\n")
    return text[start : text.index("\nCAPACITY_PYTHON\n", start)]


def test_this_tool_and_the_v1_program_give_the_same_sums_for_one_document(
    tmp_path: Path,
) -> None:
    """The four sums of the V1 preflight, from the program the V1 script holds.

    The document has one schedulable node, one cordoned node that holds no pod,
    finished pods, a pod without a request, and a pod whose init container is the
    larger. Both readers give the same allocatable figures and the same requests.

    The two readers differ on purpose where the V1 program is not exact: it
    counts a restartable init container as an init container, it adds no pod
    overhead, it reads a pod on another node as a pod of the cluster, and it
    reads an unreadable quantity as an error of the whole program.
    """
    nodes = listed([node(memory="10186204Ki"), node("cordoned", unschedulable=True)])
    pods = listed(
        [
            *system_pods(),
            pod("done", container("2", "4Gi"), phase="Succeeded"),
            pod("init", container("100m", "70Mi"), init=[container("500m", "1Gi")]),
        ]
    )
    target = tmp_path / "v1-facts.json"
    completed = subprocess.run(
        [sys.executable, "-c", _v1_program(), str(target)],
        env={
            **os.environ,
            "INFEROPS_CAPACITY_ENGINE_CPUS": "12",
            "INFEROPS_CAPACITY_ENGINE_MEMORY": str(16 * GI),
            "INFEROPS_CAPACITY_NODES": json.dumps(nodes),
            "INFEROPS_CAPACITY_PODS": json.dumps(pods),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    v1 = json.loads(target.read_text(encoding="utf-8"))["cluster"]

    record = gate.build_record(collection(tmp_path / "c", nodes=nodes, pods=pods))
    [schedulable] = [n for n in record["nodes"] if n["schedulable"]]
    assert v1 == {
        "schedulableNodes": 1,
        "allocatableCpuMillis": schedulable["allocatable"]["cpuMillis"],
        "allocatableMemoryBytes": schedulable["allocatable"]["memoryBytes"],
        "committedCpuMillis": record["reservations"]["cpuRequestMillis"],
        "committedMemoryBytes": record["reservations"]["memoryRequestBytes"],
    }
    assert v1["committedCpuMillis"] == 950 + 500
    assert v1["committedMemoryBytes"] == 290 * MI + GI


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_exits_0_for_an_accepted_cluster_and_prints_the_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = collection(tmp_path)
    assert main([str(directory)]) == 0
    printed = capsys.readouterr()
    assert json.loads(printed.out) == gate.build_record(directory)
    assert printed.err == ""


def test_the_command_exits_5_for_a_refused_cluster_and_prints_the_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = collection(tmp_path, nodes=listed([node(memory="8Gi")]))
    assert main([str(directory)]) == gate.REFUSED_EXIT == 5
    record = json.loads(capsys.readouterr().out)
    assert record["result"] == gate.REFUSED
    assert record["refusal"]["rules"] == ["memory-limits-fit"]


def test_the_command_exits_1_and_prints_no_record_for_what_is_not_a_collection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(collection(tmp_path, run=ABSENT))]) == 1
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("REFUSED  not-a-collection: ")
    assert main([str(tmp_path / "absent")]) == 1
    assert capsys.readouterr().out == ""


def test_the_command_refuses_a_footprint_that_the_committed_files_do_not_give(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A collection for fewer replicas is not a gate for the declared release."""
    smaller = copy.deepcopy(gate.declared_footprint())
    smaller["components"][1]["replicas"] = 1
    smaller["topology"]["runtimeReplicas"] = 1
    directory = collection(tmp_path, footprint=core._derived(smaller))

    assert main([str(directory)]) == 1
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("REFUSED  footprint-not-current: ")

    assert main([str(directory), "--as-collected"]) == 0
    assert json.loads(capsys.readouterr().out)["footprint"]["topology"] == {
        "apiReplicas": 2,
        "runtimeReplicas": 1,
    }


def test_the_command_prints_the_declared_footprint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--footprint"]) == 0
    first = capsys.readouterr().out
    assert json.loads(first) == gate.declared_footprint()
    assert main(["--footprint", "--key", KEY]) == 0
    assert capsys.readouterr().out == first
    assert first == gate.footprint_text(gate.declared_footprint())

    assert main(["--footprint", "--key", "local-kind/support-assistant"]) == 1
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("REFUSED  no-footprint: ")


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--check", "--footprint"],
        ["directory", "--check"],
        ["directory", "--footprint"],
        ["--key", KEY],
        ["directory", "--key", KEY],
        ["--as-collected"],
        ["--check", "--as-collected"],
        ["--unknown"],
        ["one", "two"],
    ],
)
def test_the_command_exits_2_for_arguments_that_are_not_usable(
    arguments: list[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(arguments)
    assert raised.value.code == 2


def test_the_command_runs_as_a_module() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.capacity_preflight", "--footprint"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == gate.declared_footprint()


# --------------------------------------------------------------------------
# The committed cases
# --------------------------------------------------------------------------

EXPECTED_CASES = {
    "accepted-one-node": (gate.ACCEPTED, [], []),
    "refused-insufficient-memory": (
        gate.REFUSED,
        [gate.INSUFFICIENT],
        ["memory-limits-fit"],
    ),
    "refused-insufficient-processor-and-pods": (
        gate.REFUSED,
        [gate.INSUFFICIENT],
        ["pod-count-fits", "cpu-requests-fit"],
    ),
    "refused-ambiguous-two-nodes": (
        gate.REFUSED,
        [gate.AMBIGUOUS],
        [
            "one-schedulable-node",
            "node-ready-without-pressure",
            "node-states-no-blocking-taint",
            "pod-count-fits",
            "cpu-requests-fit",
            "memory-limits-fit",
        ],
    ),
    "refused-ambiguous-read-not-made": (
        gate.REFUSED,
        [gate.AMBIGUOUS],
        [
            "cluster-reads-complete",
            "quantities-readable",
            "release-is-not-installed",
            "pod-count-fits",
            "cpu-requests-fit",
            "memory-limits-fit",
        ],
    ),
    "refused-ambiguous-release-installed": (
        gate.REFUSED,
        [gate.AMBIGUOUS],
        ["release-is-not-installed"],
    ),
}


def test_the_committed_cases_are_the_expected_ones() -> None:
    assert sorted(p.name for p in CASES.iterdir() if p.is_dir()) == sorted(
        EXPECTED_CASES
    )
    assert gate.committed_collections() == sorted(
        [f"tests/domain/fixtures/capacity-preflight/{name}" for name in EXPECTED_CASES]
        + [
            p.relative_to(REPO_ROOT).as_posix()
            for p in REPO_ROOT.glob(gate.RUNS_PATTERN)
            if p.is_dir()
        ]
    )


@pytest.mark.parametrize("name", sorted(EXPECTED_CASES))
def test_each_committed_case_gives_its_committed_record(name: str) -> None:
    """The same documents give the same record, with the result the name states."""
    result, categories, rules = EXPECTED_CASES[name]
    directory = CASES / name
    record = gate.build_record(directory)
    assert record["result"] == result
    assert record["refusal"] == {"categories": categories, "rules": rules}
    committed = (directory / gate.RECORD_FILE).read_bytes().replace(b"\r\n", b"\n")
    assert gate.record_text(record).encode("utf-8") == committed
    # Each case is about the two-replica topology, and no cluster produced it.
    assert record["footprint"]["topology"] == {"apiReplicas": 2, "runtimeReplicas": 2}
    assert record["collection"]["provider"] == "synthetic"
    assert record["collection"]["executingCommit"] == "0" * 40


def test_the_check_passes_on_the_committed_collections(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert gate.check_committed() == []
    assert main(["--check"]) == 0
    assert capsys.readouterr().out.startswith(
        f"PASSED: {len(gate.committed_collections())} committed collection(s)"
    )


def _case_root(tmp_path: Path, name: str = "accepted-one-node") -> Path:
    target = tmp_path / "tests/domain/fixtures/capacity-preflight" / name
    shutil.copytree(CASES / name, target)
    return target


def test_the_check_names_a_record_that_its_collection_does_not_give(
    tmp_path: Path,
) -> None:
    directory = _case_root(tmp_path)
    assert gate.check_committed(tmp_path) == []

    record = json.loads((directory / gate.RECORD_FILE).read_text(encoding="utf-8"))
    record["result"] = gate.REFUSED
    (directory / gate.RECORD_FILE).write_text(
        gate.record_text(record), encoding="utf-8"
    )
    [named] = gate.check_committed(tmp_path)
    assert "is not what the collection gives" in named

    (directory / gate.RECORD_FILE).unlink()
    [named] = gate.check_committed(tmp_path)
    assert f"holds no {gate.RECORD_FILE}" in named

    (directory / "run.json").unlink()
    (directory / gate.RECORD_FILE).write_text("{}\n", encoding="utf-8")
    [named] = gate.check_committed(tmp_path)
    assert "no readable run.json" in named


def test_the_check_reads_a_collection_that_a_run_committed(tmp_path: Path) -> None:
    """A run is found by the name of its directory. No list names it."""
    run = tmp_path / "docs/proof/environment/example-capacity-preflight-run-1"
    collection(run)
    (run / gate.RECORD_FILE).write_text(
        gate.record_text(gate.build_record(run)), encoding="utf-8", newline="\n"
    )
    assert gate.committed_collections(tmp_path) == [
        "docs/proof/environment/example-capacity-preflight-run-1"
    ]
    assert gate.check_committed(tmp_path) == []
    (run / "nodes.json").write_text(
        json.dumps(listed([node(memory="1Gi")])), encoding="utf-8"
    )
    assert len(gate.check_committed(tmp_path)) == 1
