"""The control of V2-E02A, tested offline: no cluster, no fault, and no run.

``tools.experiment_e02a`` runs the procedure of revision 3 of the V2-E02A freeze
record. The tests below hold what it takes from the record, each decision of the
procedure, and the order of the steps. The procedure tests drive the control with
:class:`~tools.experiment_e02a.ports.ScenarioPort`, which answers each read from a
scenario built in memory and executes nothing, on a virtual clock. Where a test
needs a fault, it passes a double that records the pod it was asked to delete and
deletes nothing. The driver tests execute the driver file with bash against a stub
``kubectl`` that records its arguments.

No test contacts a cluster, and no run of V2-E02A exists. The analysis test builds
a synthetic 2+1 run with the builders of the reliability-analysis suite and replays
it with ``tools.analysis_replay``.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import tests.domain.test_reliability_analysis as analysis_suite
from tools.analysis_replay import core as replay
from tools.experiment_e02a import __main__ as cli
from tools.experiment_e02a import control as control_module
from tools.experiment_e02a import core, ports
from tools.experiment_e02a.control import (
    ABORTED,
    OBSERVED,
    P1_CHECKS,
    REFUSED,
    Control,
)
from tools.experiment_e02a.ports import SCENARIO_SCHEMA, ScenarioPort
from tools.experiment_events import core as events
from tools.experiment_freeze import core as freeze
from tools.experiment_run import core as run_core
from tools.reliability_analysis import core as analysis

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
R2 = "docs/proof/experiments/v2-e02a/freeze-r2.v1alpha1.json"
R3 = "docs/proof/experiments/v2-e02a/freeze-r3.v1alpha1.json"
DRIVER = REPO_ROOT / "docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt"
PACKAGE = REPO_ROOT / "tools" / "experiment_e02a"
Q1_2_CAPACITY = "docs/proof/experiments/v2-q1/runs/q1-2/capacity/record.v1alpha1.json"
E02B_R2 = "docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json"
CONTROLLER = "delivery-controller"
HEAD = "a" * 40
DESIRED = "b" * 40
API_IMAGE = "sha256:" + "c" * 64

PLAN = core.load_plan(REPO_ROOT)


def _read(path: str) -> dict[str, Any]:
    return json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Objects of a synthetic cluster
# --------------------------------------------------------------------------


def _labels(tier: str) -> dict[str, str]:
    return {core.INSTANCE_LABEL: core.HELM_RELEASE, core.COMPONENT_LABEL: tier}


def _deployments(api: int | None = 2, runtime: int | None = 1) -> dict[str, Any]:
    items = []
    for tier, ready in ((core.API_TIER, api), (core.RUNTIME_TIER, runtime)):
        status = {} if ready is None else {"readyReplicas": ready}
        items.append(
            {
                "metadata": {"labels": _labels(tier)},
                "spec": {"replicas": {core.API_TIER: 2, core.RUNTIME_TIER: 1}[tier]},
                "status": status,
            }
        )
    return {"items": items}


def _slices(api: int = 2, runtime: int = 1) -> dict[str, Any]:
    items = []
    for tier, ready in ((core.API_TIER, api), (core.RUNTIME_TIER, runtime)):
        items.append(
            {
                "metadata": {"labels": {core.SERVICE_NAME_LABEL: core.SERVICES[tier]}},
                "endpoints": [{"conditions": {"ready": True}}] * ready
                + [{"conditions": {"ready": False}}],
            }
        )
    return {"items": items}


def _application(revision: str = DESIRED, sync: str = "Synced") -> dict[str, Any]:
    return {
        "status": {
            "sync": {"revision": revision, "status": sync},
            "health": {"status": "Healthy"},
        }
    }


def _pod(
    name: str,
    tier: str,
    uid: str,
    *,
    ready: bool = True,
    deleting: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"name": name, "uid": uid, "labels": _labels(tier)}
    if deleting:
        metadata["deletionTimestamp"] = "2026-10-22T10:00:00Z"
    pod: dict[str, Any] = {
        "metadata": metadata,
        "status": {
            "conditions": [{"type": "Ready", "status": "True" if ready else "False"}]
        },
    }
    if model is not None:
        pod["spec"] = {
            "initContainers": [
                {
                    "name": core.VERIFY_CONTAINER,
                    "command": ["/bin/sh", "-c", f"echo '{model}  /models/m.gguf'"],
                }
            ]
        }
    return pod


RUNTIME_POD = "inferops-inferops-llm-runtime-6c9f-x2k4p"


def _release_pods() -> dict[str, Any]:
    return {
        "items": [
            _pod("inferops-inferops-llm-7d8b-a1", core.API_TIER, "u-api-1"),
            _pod("inferops-inferops-llm-7d8b-b2", core.API_TIER, "u-api-2"),
            _pod(RUNTIME_POD, core.RUNTIME_TIER, "u-rt-1", model=PLAN.model_sha256),
        ]
    }


def _names(*names: str) -> str:
    return "".join(f"{name}\n" for name in names)


BASE_NAMESPACES = ("namespace/default", "namespace/kube-system")
BASE_CRDS = ("customresourcedefinition.apiextensions.k8s.io/other.example.io",)


def scenario(**changes: Any) -> dict[str, Any]:
    """A scenario in which every step holds, the stable window holds at its first
    check, and the run reaches the end of its window."""
    prepared = (*BASE_NAMESPACES, f"namespace/{PLAN.namespace}")
    document: dict[str, Any] = {
        "schema": SCENARIO_SCHEMA,
        "start": "2026-10-22T10:00:00.000Z",
        "controllerNamespace": CONTROLLER,
        "taken": [],
        "runsUnderRevision": 0,
        "repository": {
            "head": HEAD,
            "clean": True,
            "checks": {module: 0 for module in P1_CHECKS},
            "changes": 0,
            "desiredRevision": DESIRED,
            "deliveryPathsEqual": True,
            "desiredStateFiles": dict(PLAN.desired_state_files),
        },
        "reads": {
            "target": {"exit": 0},
            "namespaces": [
                {"text": _names(*BASE_NAMESPACES)},
                {"after": "prerequisites", "text": _names(*prepared)},
                {
                    "after": "controller",
                    "text": _names(*prepared, f"namespace/{CONTROLLER}"),
                },
                {"after": "release-remove", "text": _names(*BASE_NAMESPACES)},
            ],
            "crds": [
                {"text": _names(*BASE_CRDS)},
                {"after": "controller", "text": _names(*BASE_CRDS, "crd/app")},
                {"after": "release-remove", "text": _names(*BASE_CRDS)},
            ],
            "capacity": {"exit": 0},
            "capacity-record": {"json": _read(Q1_2_CAPACITY)},
            "api-image-digest": {"text": API_IMAGE + "\n"},
            "deployments": {"json": _deployments()},
            "endpoints": {"json": _slices()},
            "application": {"json": _application()},
            "application-verify": {"exit": 0},
            "provenance": {
                "json": [
                    {
                        "desiredState": {"key": PLAN.release_key},
                        "release": {"releaseId": PLAN.release_id},
                    }
                ]
            },
            "runtime-pods": {
                "json": {"items": [_release_pods()["items"][2]]},
            },
            "verify-log": {"text": f"/models/m.gguf: OK\n{core.MODEL_VERIFIED_LINE}\n"},
            "clock": {
                "text": "2026-10-22T10:00:00.000Z\n"
                "2026-10-22T10:00:00.010Z\n"
                "2026-10-22T10:00:00.020Z\n"
            },
            "release-pods": {"json": _release_pods()},
            "nodes": {
                "json": {
                    "items": [
                        {
                            "status": {
                                "conditions": [{"type": "Ready", "status": "True"}]
                            }
                        }
                    ]
                }
            },
            "claims": {"json": {"items": [{"metadata": {"name": "model-cache"}}]}},
            "runner-job": [
                {"json": {"status": {"active": 1}}},
                {
                    "after": "runner-start",
                    "from": 1510,
                    "json": {"status": {"succeeded": 1}},
                },
            ],
            "run-objects": {"text": ""},
        },
        "acts": {},
        "caller": {"podStartsAfterSeconds": 5, "everyMs": 2000, "failing": []},
    }
    for key, value in changes.items():
        document[key] = value
    return document


def _with_read(document: dict[str, Any], name: str, answer: Any) -> dict[str, Any]:
    document = copy.deepcopy(document)
    document["reads"][name] = answer
    return document


class RecordingFault:
    """A fault that records the pod it was asked to delete and deletes nothing."""

    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, pod: str) -> int:
        self.deleted.append(pod)
        return 0


def _control(
    tmp_path: Path,
    document: dict[str, Any],
    *,
    fault: RecordingFault | None = None,
    run_id: str | None = None,
) -> tuple[Control, ScenarioPort]:
    port = ScenarioPort(document, None)
    identifier = run_id or ("e02a-1" if fault is not None else "dry-run-1")
    control = Control(
        PLAN,
        port,
        run_id=identifier,
        work_root=tmp_path,
        controller_namespace=CONTROLLER,
        fault=fault,
    )
    return control, port


def _journal(outcome: control_module.Outcome) -> dict[str, Any]:
    return json.loads((outcome.work / "control.json").read_text(encoding="utf-8"))


def _steps(outcome: control_module.Outcome) -> list[str]:
    return [step["step"] for step in _journal(outcome)["steps"]]


def _cluster_entries(port: ScenarioPort) -> list[str]:
    """The entries of the port log that read or act on the cluster."""
    return [
        entry
        for entry in port.log
        if entry.split(" ")[0] in {"read", "status", "act", "start"}
    ]


# --------------------------------------------------------------------------
# The record is the source
# --------------------------------------------------------------------------


def test_the_plan_is_revision_3_with_its_registry_pin() -> None:
    registry = freeze.load_registry(REPO_ROOT)
    assert PLAN.record_path == R3
    assert PLAN.revision == 3
    assert PLAN.record_sha256 == registry[R3]
    assert freeze.content_digest((REPO_ROOT / R3).read_bytes()) == registry[R3]


def test_the_plan_takes_the_baseline_topology_and_release_from_the_record() -> None:
    topology = _read(R3)["fields"]["topology"][0]["value"]
    assert (PLAN.api_replicas, PLAN.runtime_replicas) == (2, 1)
    assert PLAN.replicas == {"platform-api": 2, "serving-runtime": 1}
    assert dict(PLAN.desired_state_files) == topology["release"]["desiredStateFiles"]
    assert PLAN.release_id == topology["release"]["releaseId"]
    assert PLAN.model_sha256 == topology["model"]["sha256"].removeprefix("sha256:")
    assert PLAN.namespace == "inferops-release"
    assert PLAN.duration_seconds == 1500
    assert PLAN.request_ceiling == 10000


def test_each_bound_phrase_is_in_revision_3_and_no_finding_is_raised() -> None:
    document = _read(R3)
    assert core.binding_findings(document) == []
    for pointer, phrase in core.BOUND_PHRASES:
        assert phrase in core._pointer(document, pointer), pointer


def test_the_figures_of_the_control_are_the_figures_of_the_phrases() -> None:
    assert core.check_offsets() == tuple(range(150, 601, 30))
    assert len(core.check_offsets()) == 16
    assert (core.STABLE_MINIMUM_SUCCESSES, core.STABLE_LOOKBACK_SECONDS) == (10, 60)
    assert (core.WINDOW_BEFORE_MS, core.WINDOW_AFTER_MS) == (60_000, 720_000)
    assert core.OBSERVATION_LIMIT_SECONDS == 600
    assert (core.TIMELINE_SAMPLES, core.TIMELINE_INTERVAL_SECONDS) == (900, 2)
    assert (core.TELEMETRY_SAMPLES, core.TELEMETRY_INTERVAL_SECONDS) == (120, 15)
    assert core.COLLECTOR_LEAD_SECONDS == 30
    assert core.TOPOLOGY_WAIT_SECONDS == 1800
    assert core.MAXIMUM_RUNS == 6


def _tree_with(tmp_path: Path, change: Any = None, *, register: bool = True) -> Path:
    """A tree that holds the registry and the V2-E02A records, with revision 3
    changed by ``change`` and registered again when ``register`` is set."""
    for path in (R2, R3, freeze.REGISTRY_PATH):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / path, target)
    if change is not None:
        document = _read(R3)
        change(document)
        data = (json.dumps(document, indent=2) + "\n").encode("utf-8")
        (tmp_path / R3).write_bytes(data)
        if register:
            registry = json.loads((tmp_path / freeze.REGISTRY_PATH).read_text("utf-8"))
            for row in registry["records"]:
                if row["path"] == R3:
                    row["contentSha256"] = freeze.content_digest(data)
            (tmp_path / freeze.REGISTRY_PATH).write_text(json.dumps(registry), "utf-8")
    return tmp_path


def test_a_record_that_differs_from_its_pin_is_refused(tmp_path: Path) -> None:
    root = _tree_with(
        tmp_path, lambda d: d["definition"]["history"].append("x"), register=False
    )
    with pytest.raises(core.PlanRefused, match="differs from its registry pin"):
        core.load_plan(root)


def test_a_registry_whose_latest_record_is_revision_2_is_refused(
    tmp_path: Path,
) -> None:
    root = _tree_with(tmp_path)
    registry = json.loads((root / freeze.REGISTRY_PATH).read_text("utf-8"))
    registry["records"] = [r for r in registry["records"] if r["path"] != R3]
    (root / freeze.REGISTRY_PATH).write_text(json.dumps(registry), "utf-8")
    with pytest.raises(core.PlanRefused, match="revision 2, which freezes no driver"):
        core.load_plan(root)


def _set_check_offset(document: dict[str, Any]) -> None:
    window = document["definition"]["stablePreFaultWindow"]
    document["definition"]["stablePreFaultWindow"] = window.replace(
        "at 150 s after", "at 120 s after"
    )


def _drop_abort(document: dict[str, Any]) -> None:
    document["fields"]["abortConditions"][0]["value"].pop()


def _set_samples(document: dict[str, Any]) -> None:
    timeline = document["definition"]["collection"]["timeline"]
    document["definition"]["collection"]["timeline"] = timeline.replace(
        "--samples 900", "--samples 600"
    )


@pytest.mark.parametrize("change", [_set_check_offset, _drop_abort, _set_samples])
def test_a_later_figure_in_the_record_refuses_this_control(
    tmp_path: Path, change: Any
) -> None:
    root = _tree_with(tmp_path, change)
    with pytest.raises(core.PlanRefused):
        core.load_plan(root)


def test_revision_3_pins_the_driver_and_every_module_of_the_control() -> None:
    pinned = {pin["path"] for pin in _read(R3)["pinnedInputs"]}
    assert "docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt" in pinned
    modules = {path.relative_to(REPO_ROOT).as_posix() for path in PACKAGE.glob("*.py")}
    assert modules == {
        f"tools/experiment_e02a/{name}"
        for name in ("__init__.py", "__main__.py", "control.py", "core.py", "ports.py")
    }
    assert modules <= pinned
    assert (
        "tools.experiment_e02a.__main__" in _read(R3)["materialScope"]["entryModules"]
    )


def test_no_material_input_of_revision_3_has_moved() -> None:
    document = _read(R3)
    files = freeze.material_files(document["materialScope"], REPO_ROOT)
    pinned = {pin["path"]: pin["sha256"] for pin in document["pinnedInputs"]}
    assert set(files) == set(pinned)
    for path in files:
        assert freeze.content_digest((REPO_ROOT / path).read_bytes()) == pinned[path], (
            path
        )


def test_revision_3_classifies_each_pin_that_moved_from_revision_2() -> None:
    two = {pin["path"]: pin["sha256"] for pin in _read(R2)["pinnedInputs"]}
    three = {pin["path"]: pin["sha256"] for pin in _read(R3)["pinnedInputs"]}
    moved = {path for path in set(two) | set(three) if two.get(path) != three.get(path)}
    changes = _read(R3)["inputChanges"]
    assert {change["path"] for change in changes} == moved
    for change in changes:
        assert change["from"] == two.get(change["path"])
        assert change["to"] == three.get(change["path"])
        assert isinstance(change["material"], bool) and change["reason"]
    preregistration = [
        c for c in changes if c["path"] == "tools/experiment_preregistration/core.py"
    ]
    assert [c["material"] for c in preregistration] == [False]


#: The members of revision 3 that differ from revision 2.
CHANGED_MEMBERS = {
    "metadata",
    "definition.gitTransitions",
    "definition.limitations",
    "definition.history",
    "fields.experimentIdVersion",
    "fields.gitRevision",
    "materialScope",
    "pinnedInputs",
    "inputChanges",
}


def test_revision_3_differs_from_revision_2_in_the_listed_members_alone() -> None:
    two, three = _read(R2), _read(R3)
    differing = set()
    for section in ("definition", "fields"):
        for key in set(two[section]) | set(three[section]):
            if two[section].get(key) != three[section].get(key):
                differing.add(f"{section}.{key}")
    for key in set(two) | set(three):
        if key not in ("definition", "fields") and two.get(key) != three.get(key):
            differing.add(key)
    assert differing == CHANGED_MEMBERS


def test_g1_names_revision_4_and_g4_keeps_the_owner_authorization_word_for_word() -> (
    None
):
    two = _read(R2)["definition"]["gitTransitions"]
    three = _read(R3)["definition"]["gitTransitions"]
    assert "That change registers revision 4 of this record" in three[0]
    assert "revision 4 merges before the first run" in three[0]
    assert "revision 2" not in three[0]
    assert three[0] == two[0].replace("revision 2", "revision 4")
    assert three[1:] == two[1:]
    assert (
        "Each switch is a commit to main that needs the explicit authorization of the "
        "repository owner." in three[3]
    )


def test_the_procedure_members_shared_with_e02b_are_unchanged() -> None:
    from tools.experiment_preregistration import core as preregistration

    two, three, target = _read(R2), _read(R3), _read(E02B_R2)
    for member in preregistration.SHARED_DEFINITION:
        assert three["definition"][member] == two["definition"][member], member
    assert three["definition"]["executables"] == target["definition"]["executables"]


def test_the_desired_state_on_main_still_derives_two_plus_two() -> None:
    """The control refuses the active desired state of this tree at P2: its two
    files have the digests of the 2+2 target, not those of the baseline."""
    repository = ports.LocalRepository(REPO_ROOT, PLAN)
    head = repository.head()
    if head is None:
        pytest.skip("git is not usable here")
    digests = repository.desired_state_digests(head, PLAN.desired_state_path)
    target = _read(E02B_R2)["fields"]["topology"][0]["value"]["release"]
    assert digests == target["desiredStateFiles"]
    findings = core.desired_state_findings(
        PLAN, desired=head, paths_equal=True, digests=digests
    )
    assert len(findings) == 2
    assert all("and the record states" in finding for finding in findings)


# --------------------------------------------------------------------------
# The identifier
# --------------------------------------------------------------------------


def test_a_dry_run_takes_a_dry_run_identifier_and_never_a_run_identifier() -> None:
    assert (
        core.identifier_findings(
            "dry-run-1", dry_run=True, taken=[], runs_under_revision=0
        )
        == []
    )
    assert core.identifier_findings(
        "e02a-1", dry_run=True, taken=[], runs_under_revision=0
    )
    assert core.identifier_findings(
        "dry-run-1", dry_run=False, taken=[], runs_under_revision=0
    )


def test_a_run_takes_the_next_identifier_and_at_most_six_start_under_a_revision() -> (
    None
):
    assert (
        core.identifier_findings(
            "e02a-1", dry_run=False, taken=[], runs_under_revision=0
        )
        == []
    )
    assert (
        core.identifier_findings(
            "e02a-3", dry_run=False, taken=["e02a-1", "e02a-2"], runs_under_revision=2
        )
        == []
    )
    assert core.identifier_findings(
        "e02a-2", dry_run=False, taken=["e02a-1", "e02a-2"], runs_under_revision=2
    )
    assert core.identifier_findings(
        "e02a-4", dry_run=False, taken=["e02a-1", "e02a-2"], runs_under_revision=2
    )
    assert core.identifier_findings(
        "e02a-7",
        dry_run=False,
        taken=[f"e02a-{n}" for n in range(1, 7)],
        runs_under_revision=6,
    )


def test_an_identifier_that_cannot_be_used_writes_nothing(tmp_path: Path) -> None:
    control, port = _control(
        tmp_path, scenario(taken=["e02a-1"]), fault=RecordingFault()
    )
    with pytest.raises(ValueError, match="the next run identifier is e02a-2"):
        control.run()
    assert list(tmp_path.iterdir()) == []
    assert _cluster_entries(port) == []


# --------------------------------------------------------------------------
# P1 to P4: the repository, the desired state, the target, and the capacity
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("clean", False),
        ("head", None),
        ("changes", 1),
        (
            "checks",
            {**{module: 0 for module in P1_CHECKS}, "tools.experiment_bounds": 1},
        ),
    ],
)
def test_p1_refuses_before_any_cluster_read(
    tmp_path: Path, member: str, value: Any
) -> None:
    document = scenario()
    document["repository"][member] = value
    control, port = _control(tmp_path, document)
    outcome = control.run()
    assert (outcome.state, outcome.reason, outcome.step) == (
        REFUSED,
        "precondition-not-held",
        "P1",
    )
    assert _cluster_entries(port) == []


def test_p2_refuses_the_two_plus_two_desired_state(tmp_path: Path) -> None:
    target = _read(E02B_R2)["fields"]["topology"][0]["value"]["release"]
    document = scenario()
    document["repository"]["desiredStateFiles"] = target["desiredStateFiles"]
    control, port = _control(tmp_path, document)
    outcome = control.run()
    assert (outcome.state, outcome.step) == (REFUSED, "P2")
    assert _cluster_entries(port) == []


@pytest.mark.parametrize(
    "digests",
    [
        {"rendered-workload-release.yaml": "0" * 64},
        {},
    ],
)
def test_p2_refuses_a_missing_or_other_file(digests: dict[str, str]) -> None:
    findings = core.desired_state_findings(
        PLAN, desired=DESIRED, paths_equal=True, digests=digests
    )
    assert findings


def test_p2_refuses_an_extra_file_and_differing_delivery_paths() -> None:
    files = {**PLAN.desired_state_files, "extra.yaml": "1" * 64}
    assert core.desired_state_findings(
        PLAN, desired=DESIRED, paths_equal=True, digests=files
    )
    assert core.desired_state_findings(
        PLAN, desired=DESIRED, paths_equal=False, digests=dict(PLAN.desired_state_files)
    )
    assert (
        core.desired_state_findings(
            PLAN,
            desired=DESIRED,
            paths_equal=True,
            digests=dict(PLAN.desired_state_files),
        )
        == []
    )


@pytest.mark.parametrize(
    ("target", "namespaces"),
    [
        (1, _names(*BASE_NAMESPACES)),
        (0, _names(*BASE_NAMESPACES, "namespace/inferops-release")),
        (0, _names(*BASE_NAMESPACES, f"namespace/{CONTROLLER}")),
    ],
)
def test_p3_refuses_another_target_or_a_cluster_that_holds_the_release(
    tmp_path: Path, target: int, namespaces: str
) -> None:
    document = _with_read(scenario(), "target", {"exit": target})
    document["reads"]["namespaces"] = {"text": namespaces}
    control, port = _control(tmp_path, document)
    outcome = control.run()
    assert (outcome.state, outcome.step) == (REFUSED, "P3")
    assert not any(entry.startswith("act") for entry in port.log)


def test_p4_takes_the_identity_of_the_qualification_from_the_capacity_record() -> None:
    record = _read(Q1_2_CAPACITY)
    assert core.capacity_findings(PLAN, exit_status=0, record=record) == []
    assert core.capacity_findings(PLAN, exit_status=5, record=record)
    other = copy.deepcopy(record)
    other["environment"]["containerEngine"]["cpus"] += 1
    assert (
        "stable environment identity is"
        in core.capacity_findings(PLAN, exit_status=0, record=other)[0]
    )


# --------------------------------------------------------------------------
# P6 to P8: the topology, the release, and the clocks
# --------------------------------------------------------------------------


def test_p6_holds_two_api_and_one_runtime_replica_at_the_desired_revision() -> None:
    held = core.topology_findings(
        PLAN,
        deployments=_deployments(),
        slices=_slices(),
        application=_application(),
        desired=DESIRED,
    )
    assert held == []


@pytest.mark.parametrize(
    ("deployments", "slices", "application"),
    [
        (_deployments(runtime=2), _slices(), _application()),
        (_deployments(runtime=None), _slices(), _application()),
        (_deployments(), _slices(runtime=2), _application()),
        (_deployments(), _slices(), _application(revision=HEAD)),
        (_deployments(), _slices(), _application(sync="OutOfSync")),
    ],
)
def test_p6_refuses_another_topology_or_state(
    deployments: Any, slices: Any, application: Any
) -> None:
    assert core.topology_findings(
        PLAN,
        deployments=deployments,
        slices=slices,
        application=application,
        desired=DESIRED,
    )


def test_p6_waits_at_most_1800_seconds_and_then_refuses_and_cleans_up(
    tmp_path: Path,
) -> None:
    document = _with_read(scenario(), "deployments", {"json": _deployments(runtime=2)})
    control, port = _control(tmp_path, document)
    outcome = control.run()
    assert (outcome.state, outcome.step) == (REFUSED, "P6")
    journal = _journal(outcome)
    started = core.parse_instant(journal["startedAt"])
    p6 = next(s for s in journal["steps"] if s["step"] == "P6")
    refused_at = core.parse_instant(p6["at"])
    assert started is not None and refused_at is not None
    assert refused_at - started >= timedelta(seconds=1800)
    assert "act release-remove: not executed in a dry run" in port.log
    assert _steps(outcome)[-1] == "C4"


def test_p7_refuses_another_release_or_an_unverified_model() -> None:
    pods = {
        "items": [_pod(RUNTIME_POD, core.RUNTIME_TIER, "u", model=PLAN.model_sha256)]
    }
    good_log = {RUNTIME_POD: core.MODEL_VERIFIED_LINE}
    assert core.model_findings(PLAN, pods, good_log) == []
    assert core.model_findings(PLAN, pods, {RUNTIME_POD: None})
    other = {"items": [_pod(RUNTIME_POD, core.RUNTIME_TIER, "u", model="0" * 64)]}
    assert core.model_findings(PLAN, other, good_log)
    assert (
        core.provenance_findings(
            PLAN,
            [
                {
                    "desiredState": {"key": PLAN.release_key},
                    "release": {"releaseId": PLAN.release_id},
                }
            ],
        )
        == []
    )
    assert core.provenance_findings(
        PLAN,
        [
            {
                "desiredState": {"key": PLAN.release_key},
                "release": {"releaseId": "0" * 64},
            }
        ],
    )


def test_p8_computes_the_bound_from_both_readings() -> None:
    start = core.clock_reading(
        "2026-10-22T10:00:00.000Z\n2026-10-22T10:00:00.130Z\n2026-10-22T10:00:00.100Z\n"
    )
    end = core.clock_reading(
        "2026-10-22T10:30:00.000Z\n2026-10-22T09:59:59.990Z\n2026-10-22T10:30:00.040Z\n"
    )
    assert start is not None and end is not None
    assert (start.difference_ms, start.width_ms) == (30, 100)
    assert (end.difference_ms, end.width_ms) == (1_800_010, 40)
    assert core.clock_bound_ms(start, end) == 1_800_010 + 100
    assert core.clock_bound_ms(start, None) is None


@pytest.mark.parametrize(
    "text",
    [
        None,
        "2026-10-22T10:00:00.000Z\n2026-10-22T10:00:00.010Z\n",
        "2026-10-22T10:00:00.000Z\nnot an instant\n2026-10-22T10:00:00.020Z\n",
        "2026-10-22T10:00:00.020Z\n2026-10-22T10:00:00.010Z\n2026-10-22T10:00:00.000Z\n",
    ],
)
def test_an_unusable_reading_is_none(text: str | None) -> None:
    assert core.clock_reading(text) is None


def test_an_unusable_start_reading_refuses_the_run_before_the_collection(
    tmp_path: Path,
) -> None:
    document = _with_read(scenario(), "clock", {"text": "unread\n"})
    control, port = _control(tmp_path, document)
    outcome = control.run()
    assert (outcome.state, outcome.reason, outcome.step) == (
        REFUSED,
        "precondition-not-held",
        "P8",
    )
    assert not any(entry.startswith("start") for entry in port.log)
    assert "act release-remove: not executed in a dry run" in port.log


# --------------------------------------------------------------------------
# The stable pre-fault window
# --------------------------------------------------------------------------


def _requests(*items: tuple[int, bool]) -> list[core.Request]:
    base = core.parse_instant("2026-10-22T10:00:00.000Z")
    assert base is not None
    return [core.Request(base + timedelta(seconds=s), ok) for s, ok in items]


CHECK = core.parse_instant("2026-10-22T10:02:30.000Z")


def test_the_window_holds_with_ten_successes_in_sixty_seconds_and_the_replicas() -> (
    None
):
    assert CHECK is not None
    requests = _requests(*[(100 + 5 * n, True) for n in range(10)])
    held, _ = core.stable_window(
        PLAN,
        requests,
        check_at=CHECK,
        replicas={"platform-api": 2, "serving-runtime": 1},
    )
    assert held


@pytest.mark.parametrize(
    ("requests", "replicas"),
    [
        (
            _requests(*[(100 + 5 * n, True) for n in range(9)]),
            {"platform-api": 2, "serving-runtime": 1},
        ),
        (
            _requests(*[(100 + 5 * n, True) for n in range(10)], (148, False)),
            {"platform-api": 2, "serving-runtime": 1},
        ),
        (
            _requests(*[(80 + 5 * n, True) for n in range(10)]),
            {"platform-api": 2, "serving-runtime": 1},
        ),
        (
            _requests(*[(100 + 5 * n, True) for n in range(10)]),
            {"platform-api": 2, "serving-runtime": None},
        ),
        (
            _requests(*[(100 + 5 * n, True) for n in range(10)]),
            {"platform-api": 1, "serving-runtime": 1},
        ),
    ],
)
def test_the_window_does_not_hold(
    requests: list[core.Request], replicas: dict[str, int | None]
) -> None:
    assert CHECK is not None
    held, why = core.stable_window(PLAN, requests, check_at=CHECK, replicas=replicas)
    assert not held and why


def test_a_request_that_completes_after_the_check_is_not_read() -> None:
    assert CHECK is not None
    requests = _requests(*[(100 + 5 * n, True) for n in range(10)], (151, False))
    held, _ = core.stable_window(
        PLAN,
        requests,
        check_at=CHECK,
        replicas={"platform-api": 2, "serving-runtime": 1},
    )
    assert held


def test_the_caller_log_skips_a_cut_line_another_run_and_text() -> None:
    lines = [
        json.dumps({"record": "header", "runId": "e02a-1"}),
        json.dumps(
            {
                "record": "request",
                "runId": "e02a-1",
                "finishedAt": "2026-10-22T10:00:01.000Z",
                "success": True,
            }
        ),
        "a line of another stream",
        json.dumps(
            {
                "record": "request",
                "runId": "e02a-9",
                "finishedAt": "2026-10-22T10:00:02.000Z",
                "success": True,
            }
        ),
        json.dumps(
            {
                "record": "request",
                "runId": "e02a-1",
                "finishedAt": "2026-10-22T10:00:03.000Z",
                "success": False,
            }
        ),
    ]
    cut = (
        "\n".join(lines)
        + '\n{"record": "request", "runId": "e02a-1", "finishedAt": "2026-10'
    )
    requests = core.caller_requests(cut, "e02a-1")
    assert [request.success for request in requests] == [True, False]


def test_a_run_whose_window_never_holds_is_refused_with_its_reason(
    tmp_path: Path,
) -> None:
    document = scenario()
    document["caller"]["failing"] = [[0, 10_000]]
    control, port = _control(tmp_path, document)
    outcome = control.run()
    assert (outcome.state, outcome.reason) == (REFUSED, "stable-window-not-reached")
    journal = _journal(outcome)
    assert [check["offsetSeconds"] for check in journal["stableWindowChecks"]] == list(
        core.check_offsets()
    )
    assert "act runner-collect dry-run-1: not executed in a dry run" in port.log
    assert "act runner-cleanup dry-run-1: not executed in a dry run" in port.log
    assert port.log[-3:-1] == [
        "act release-remove: not executed in a dry run",
        "read namespaces",
    ]
    assert not (outcome.work / "declaration.json").exists()


def test_the_window_holds_at_the_first_check_at_which_it_holds(tmp_path: Path) -> None:
    document = scenario()
    document["caller"]["failing"] = [[0, 200]]
    control, _ = _control(tmp_path, document)
    outcome = control.run()
    checks = _journal(outcome)["stableWindowChecks"]
    assert [check["holds"] for check in checks] == [False, False, False, True]
    assert checks[-1]["offsetSeconds"] == 240


# --------------------------------------------------------------------------
# F1 to F4: the target and the fault
# --------------------------------------------------------------------------


def test_the_target_is_the_first_ready_runtime_pod_by_name() -> None:
    pods = {
        "items": [
            _pod("inferops-inferops-llm-a", core.API_TIER, "u0"),
            _pod("runtime-c", core.RUNTIME_TIER, "u3"),
            _pod("runtime-a", core.RUNTIME_TIER, "u1", ready=False),
            _pod("runtime-b", core.RUNTIME_TIER, "u2", deleting=True),
            _pod("runtime-d", core.RUNTIME_TIER, "u4"),
        ]
    }
    target = core.fault_target(pods)
    assert target is not None
    assert (target.name, target.uid) == ("runtime-c", "u3")
    assert [name for name, _, _ in target.pods] == sorted(
        p["metadata"]["name"] for p in pods["items"]
    )
    assert core.fault_argv_tail(PLAN, target) == [
        "delete",
        "pod",
        "runtime-c",
        "--namespace",
        "inferops-release",
        "--wait=false",
    ]


def test_no_ready_runtime_pod_is_no_target() -> None:
    pods = {
        "items": [
            _pod("api", core.API_TIER, "u0"),
            _pod("rt", core.RUNTIME_TIER, "u1", ready=False),
        ]
    }
    assert core.fault_target(pods) is None


def test_a_run_deletes_the_target_once_between_the_two_fault_events(
    tmp_path: Path,
) -> None:
    fault = RecordingFault()
    control, _ = _control(tmp_path, scenario(), fault=fault)
    outcome = control.run()
    assert (outcome.state, outcome.reason) == (OBSERVED, None)
    assert fault.deleted == [RUNTIME_POD]
    log = events.read_log((outcome.work / "operator-events.jsonl").read_text("utf-8"))
    kinds = [(e["kind"], e.get("code"), e.get("subject")) for e in log.events]
    assert kinds == [
        (
            "fault-injection-started",
            core.FAULT_CODE,
            {"kind": "pod", "name": RUNTIME_POD},
        ),
        (
            "fault-injection-finished",
            core.FAULT_CODE,
            {"kind": "pod", "name": RUNTIME_POD},
        ),
    ]
    started, finished = (core.parse_instant(e["recordedAt"]) for e in log.events)
    assert started is not None and finished is not None and started <= finished


def test_a_second_fault_is_refused_as_an_abort(tmp_path: Path) -> None:
    """The guard of the control itself. The procedure calls the fault step once, so
    this sets the flag by hand. The marker of the driver is the guard that a run
    reaches, and the driver tests hold it."""
    fault = RecordingFault()
    control, _ = _control(tmp_path, scenario(), fault=fault)
    control.fault_issued = True
    with pytest.raises(control_module._Stop) as stop:
        control._fault(core.Target(RUNTIME_POD, "u", ()))
    assert (stop.value.state, stop.value.reason) == (ABORTED, "abort-fault-differs")
    assert fault.deleted == []


def test_a_dry_run_issues_no_fault_and_records_no_fault_event(tmp_path: Path) -> None:
    control, _ = _control(tmp_path, scenario())
    outcome = control.run()
    assert (outcome.state, outcome.reason) == (OBSERVED, None)
    log = events.read_log((outcome.work / "operator-events.jsonl").read_text("utf-8"))
    assert log.events == ()
    f2 = next(s for s in _journal(outcome)["steps"] if s["step"] == "F2-F4")
    assert f2["dryRun"] is True
    assert f2["command"] == [
        "kubectl",
        "--context",
        "docker-desktop",
        "delete",
        "pod",
        RUNTIME_POD,
        "--namespace",
        "inferops-release",
        "--wait=false",
    ]
    assert f2["held"] is True


def test_the_dry_run_command_constructs_no_fault_and_runs_no_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise AssertionError("a dry run started a process or constructed a fault")

    monkeypatch.setattr(ports, "LiveFault", refuse)
    monkeypatch.setattr(cli, "LiveFault", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "load_plan", lambda _root: PLAN)
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(scenario()), "utf-8")
    assert cli.main(["dry-run", "--run-id", "dry-run-1", "--scenario", str(path)]) == 0
    work = tmp_path / ".artifacts" / "v2-e02a" / "dry-runs" / "dry-run-1"
    assert (
        json.loads((work / "control.json").read_text("utf-8"))["outcome"]["state"]
        == OBSERVED
    )


def test_the_dry_run_command_refuses_a_run_identifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "load_plan", lambda _root: PLAN)
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(scenario()), "utf-8")
    assert (
        cli.main(["dry-run", "--run-id", "e02a-1", "--scenario", str(path)])
        == cli.REFUSED_EXIT
    )
    assert not (tmp_path / ".artifacts").exists()


def test_the_run_command_refuses_without_the_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INFEROPS_E02A_DRIVER", raising=False)
    assert (
        cli.main(["run", "--run-id", "e02a-1", "--controller-namespace", CONTROLLER])
        == cli.REFUSED_EXIT
    )


def test_a_live_fault_is_constructed_for_a_run_identifier_alone(tmp_path: Path) -> None:
    port = ports.LivePort(tmp_path, PLAN, DRIVER, "bash", tmp_path / "w")
    with pytest.raises(ValueError, match="run identifier"):
        ports.LiveFault(tmp_path, DRIVER, "bash", "dry-run-1", port)
    ports.LiveFault(tmp_path, DRIVER, "bash", "e02a-1", port)


# --------------------------------------------------------------------------
# The declaration and the window
# --------------------------------------------------------------------------


def test_the_declaration_is_the_rule_with_each_topology_member_replaced(
    tmp_path: Path,
) -> None:
    fault = RecordingFault()
    control, _ = _control(tmp_path, scenario(), fault=fault)
    outcome = control.run()
    stored = json.loads((outcome.work / "declaration.json").read_text("utf-8"))
    log = events.read_log((outcome.work / "operator-events.jsonl").read_text("utf-8"))
    started, finished = (core.parse_instant(e["recordedAt"]) for e in log.events)
    assert started is not None and finished is not None
    assert stored["window"] == {
        "from": core.format_instant(started - timedelta(milliseconds=60_000)),
        "to": core.format_instant(finished + timedelta(milliseconds=720_000)),
    }
    assert stored["expected"] == {
        "desiredRevision": DESIRED,
        "readyReplicas": {"platform-api": 2, "serving-runtime": 1},
        "runtimeReadyEndpoints": 1,
    }
    rule = _read(R3)["definition"]["analysisDeclaration"]
    assert [s["id"] for s in stored["signals"]] == [s["id"] for s in rule["signals"]]
    thresholds = {s["id"]: s.get("problemBelow") for s in stored["signals"]}
    assert thresholds["runtime-ready-endpoints"] == 1
    assert thresholds["api-ready-pods"] == 2
    assert "topology." not in json.dumps(stored)
    assert (stored["experimentId"], stored["runId"], stored["schema"]) == (
        "V2-E02A",
        "e02a-1",
        rule["schema"],
    )


# --------------------------------------------------------------------------
# Abort conditions
# --------------------------------------------------------------------------


def _observation(**changes: Any) -> core.Observation:
    base = core.parse_instant("2026-10-22T10:10:00.000Z")
    assert base is not None
    values: dict[str, Any] = {
        "at": base,
        "head": HEAD,
        "clean": True,
        "namespaces": BASE_NAMESPACES,
        "crds": BASE_CRDS,
        "node_ready": True,
        "runner_pod": {
            "items": [
                {
                    "status": {
                        "phase": "Running",
                        "containerStatuses": [{"restartCount": 0}],
                    }
                }
            ]
        },
        "runner_job": {"status": {"active": 1}},
        "application": _application(),
        "claims": {"items": [{}]},
        "window_ended": False,
    }
    values.update(changes)
    return core.Observation(**values)


def _abort(observation: core.Observation, since: Any = None) -> str | None:
    return core.abort_code(
        PLAN,
        observation,
        head=HEAD,
        namespaces=BASE_NAMESPACES,
        crds=BASE_CRDS,
        desired=DESIRED,
        unanswered_since=since,
    )


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({}, None),
        ({"head": DESIRED}, "abort-checkout-changed"),
        ({"clean": False}, "abort-checkout-changed"),
        ({"namespaces": (*BASE_NAMESPACES, "namespace/new")}, "abort-unrelated-change"),
        ({"crds": ()}, "abort-unrelated-change"),
        ({"runner_pod": {"items": []}}, "abort-caller-lost"),
        (
            {
                "runner_pod": {
                    "items": [
                        {
                            "status": {
                                "phase": "Running",
                                "containerStatuses": [{"restartCount": 1}],
                            }
                        }
                    ]
                }
            },
            "abort-caller-lost",
        ),
        (
            {
                "runner_pod": {
                    "items": [{"status": {"phase": "Failed", "reason": "Evicted"}}]
                }
            },
            "abort-caller-lost",
        ),
        ({"runner_job": {"status": {"failed": 1}}}, "abort-caller-lost"),
        ({"runner_pod": {"items": []}, "window_ended": True}, None),
        ({"application": _application(revision=HEAD)}, "abort-revision-unknown"),
        ({"claims": {"items": []}}, "abort-model-risk"),
    ],
)
def test_each_abort_condition_that_the_control_reads(
    changes: dict[str, Any], code: str | None
) -> None:
    assert _abort(_observation(**changes)) == code


def test_a_node_that_is_not_ready_for_more_than_sixty_seconds_aborts() -> None:
    observation = _observation(node_ready=None)
    assert _abort(observation, observation.at - timedelta(seconds=60)) is None
    assert (
        _abort(observation, observation.at - timedelta(seconds=61))
        == "abort-cluster-incident"
    )


def test_an_abort_after_the_fault_records_its_event_and_cleans_up(
    tmp_path: Path,
) -> None:
    document = scenario()
    document["reads"]["runner-pod"] = [
        {
            "after": "runner-start",
            "from": 5,
            "json": {
                "items": [
                    {
                        "status": {
                            "phase": "Running",
                            "startTime": "2026-10-22T10:00:05Z",
                            "containerStatuses": [{"restartCount": 0}],
                        }
                    }
                ]
            },
        },
    ]
    fault = RecordingFault()
    port = ScenarioPort(document, None)
    control = Control(
        PLAN,
        port,
        run_id="e02a-1",
        work_root=tmp_path,
        controller_namespace=CONTROLLER,
        fault=fault,
    )
    original = port.read

    def read(name: str, *arguments: str) -> str | None:
        if name == "runner-pod" and control.fault_issued:
            return json.dumps({"items": []})
        return original(name, *arguments)

    port.read = read  # type: ignore[method-assign]
    outcome = control.run()
    assert (outcome.state, outcome.reason) == (ABORTED, "abort-caller-lost")
    assert fault.deleted == [RUNTIME_POD]
    log = events.read_log((outcome.work / "operator-events.jsonl").read_text("utf-8"))
    assert [e["kind"] for e in log.events] == [
        "fault-injection-started",
        "fault-injection-finished",
        "run-aborted",
    ]
    assert log.events[-1]["code"] == "abort-caller-lost"
    assert "act runner-collect e02a-1: not executed in a dry run" in port.log
    assert _steps(outcome)[-2:] == ["cleanup", "C4"]


# --------------------------------------------------------------------------
# The cleanup
# --------------------------------------------------------------------------


def test_an_observed_run_ends_with_c1_to_c4_in_order(tmp_path: Path) -> None:
    control, port = _control(tmp_path, scenario(), fault=RecordingFault())
    outcome = control.run()
    assert _steps(outcome) == [
        "P1",
        "P2",
        "P3",
        "P4 before-install",
        "P4 before-apply",
        "P5",
        "P6",
        "P7",
        "collection",
        "F1",
        "F2-F4",
        "observation",
        "C1",
        "C2",
        "C3",
        "C4",
    ]
    journal = _journal(outcome)
    assert all(step["held"] for step in journal["steps"])
    assert journal["outcome"]["state"] == OBSERVED
    assert journal["clockReadings"]["boundMs"] == 30
    acts = [entry for entry in port.log if entry.startswith("act")]
    assert acts[-1] == "act release-remove: not executed in a dry run"
    assert acts.index(
        "act runner-collect e02a-1: not executed in a dry run"
    ) < acts.index("act runner-cleanup e02a-1: not executed in a dry run")
    log = events.read_log((outcome.work / "operator-events.jsonl").read_text("utf-8"))
    assert log.end is not None


def test_c4_states_a_namespace_that_the_removal_left(tmp_path: Path) -> None:
    document = scenario()
    document["reads"]["namespaces"][-1]["text"] = _names(
        *BASE_NAMESPACES, "namespace/left"
    )
    control, _ = _control(tmp_path, document)
    outcome = control.run()
    c4 = next(s for s in _journal(outcome)["steps"] if s["step"] == "C4")
    assert c4["findings"] == ["the namespaces differ from those read before P5"]


def test_a_refusal_before_p5_leaves_the_cluster_unchanged(tmp_path: Path) -> None:
    document = _with_read(scenario(), "capacity", {"exit": 5})
    control, port = _control(tmp_path, document)
    outcome = control.run()
    assert (outcome.state, outcome.step) == (REFUSED, "P4 before-install")
    assert not any(entry.startswith("act") for entry in port.log)


# --------------------------------------------------------------------------
# The analysis and its replay, on a synthetic 2+1 run
# --------------------------------------------------------------------------


def test_the_declaration_of_the_control_is_analyzed_and_replayed(
    tmp_path: Path,
) -> None:
    run_id = "e02a-1"
    t0 = analysis_suite.T0
    started_ms, finished_ms, end_ms = 100_000, 100_400, 900_000
    declaration = core.declaration(
        PLAN,
        run_id=run_id,
        desired=analysis_suite.COMMIT,
        started=t0 + timedelta(milliseconds=started_ms),
        finished=t0 + timedelta(milliseconds=finished_ms),
    )
    text = json.dumps(declaration, indent=2, sort_keys=True) + "\n"
    requests = analysis_suite.closed_loop(
        end_ms, lambda worker, start: 101_000 <= start < 120_000
    )
    samples = [
        analysis_suite.sample(api=2, runtime=0 if 10 <= k <= 11 else 1)
        for k in range(91)
    ]
    texts: dict[str, str] = {
        "caller": analysis_suite.caller_text(
            run_id, requests, started=0, finished=end_ms, experiment_id="V2-E02A"
        ),
        **analysis_suite.streams(tmp_path, run_id, samples, experiment_id="V2-E02A"),
        analysis.EVENTS: analysis_suite.events_text(
            tmp_path,
            run_id,
            analysis_suite.fault_events(started_ms, finished_ms),
            closed=end_ms,
            experiment_id="V2-E02A",
        ),
    }
    document = analysis.analyze(text, texts)
    episodes = document["caller"]["failureEpisodes"]["episodes"]
    assert episodes and all(
        analysis_suite.at(started_ms) <= e["start"]["finishedAt"] for e in episodes
    )
    runtime = document["zeroReadyEndpoints"]["tiers"]["serving-runtime"]
    assert runtime["intervals"], runtime

    root = tmp_path / "tree"
    record = root / R3
    record.parent.mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / R3, record)
    run_dir = root / core.DIRECTORY / "runs" / run_id
    run_dir.mkdir(parents=True)
    entries = []
    for role, content in texts.items():
        name = f"{role}.jsonl"
        (run_dir / name).write_bytes(content.encode("utf-8"))
        entries.append(
            {
                "role": role,
                "path": name,
                "sha256": freeze.content_digest(content.encode("utf-8")),
            }
        )
    manifest = json.loads(
        (
            REPO_ROOT / "contracts/experiment/examples/valid/fault-injected-passed.json"
        ).read_text("utf-8")
    )
    manifest["metadata"].update(
        experimentId="V2-E02A",
        runId=run_id,
        executingRevision=analysis_suite.COMMIT,
        startedAt="2026-10-12T07:59:00Z",
        finishedAt="2026-10-12T08:20:00Z",
        spec={
            "freezeRecord": R3,
            "freezeRevision": 3,
            "freezeContentSha256": PLAN.record_sha256,
        },
    )
    manifest["fault"]["injectedAt"] = analysis_suite.at(started_ms)
    manifest["result"] = {
        "state": "INCONCLUSIVE",
        "reason": "A synthetic run. It decides no criterion.",
    }
    manifest["evidence"]["files"] = entries
    (run_dir / run_core.MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", "utf-8"
    )
    bound = replay.bind_run(run_dir, text, "c" * 40, root)
    assert bound["declaration"] == declaration
    (run_dir / "analysis.json").write_text(replay.record_text(bound), "utf-8")
    manifest["evidence"]["files"].append(
        {
            "role": "analysis",
            "path": "analysis.json",
            "sha256": freeze.content_digest((run_dir / "analysis.json").read_bytes()),
        }
    )
    (run_dir / run_core.MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", "utf-8"
    )
    report = replay.replay_run(run_dir, root)
    assert report.status == "replayed", report.findings


# --------------------------------------------------------------------------
# The driver
# --------------------------------------------------------------------------


def _bash() -> str:
    bash = ports.find_bash()
    if bash is None:
        pytest.skip("bash is not on PATH")
    probe = subprocess.run(
        [bash, "-c", 'printf %s "$BASH_VERSION"'],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0 or not probe.stdout:
        pytest.skip("the bash on PATH is not GNU bash")
    return bash


def _stub_kubectl(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / "kubectl.log"
    stub = directory / "kubectl"
    stub.write_text(
        f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "{log.as_posix()}"\n',
        "utf-8",
        newline="\n",
    )
    stub.chmod(0o755)
    return log


def _driver(
    bash: str, root: Path, bin_dir: Path, *arguments: str, live: bool
) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("INFEROPS_E02A")
    }
    environment["PATH"] = f"{bin_dir}{os.pathsep}{environment.get('PATH', '')}"
    if live:
        environment["INFEROPS_E02A_MODE"] = "live"
    return subprocess.run(
        [bash, str(DRIVER), *arguments],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_the_driver_refuses_a_verb_or_a_fault_outside_a_run(tmp_path: Path) -> None:
    bash = _bash()
    log = _stub_kubectl(tmp_path / "bin")
    for arguments in (("verb", "namespaces"), ("fault", "e02a-1", "pod-a")):
        done = _driver(bash, tmp_path, tmp_path / "bin", *arguments, live=False)
        assert done.returncode == 2, done.stderr
        assert "REFUSED" in done.stderr
    assert not log.exists()


def test_the_driver_deletes_one_pod_once_per_run(tmp_path: Path) -> None:
    bash = _bash()
    log = _stub_kubectl(tmp_path / "bin")
    (tmp_path / ".artifacts" / "v2-e02a" / "runs" / "e02a-1").mkdir(parents=True)
    first = _driver(
        bash, tmp_path, tmp_path / "bin", "fault", "e02a-1", "pod-a", live=True
    )
    assert first.returncode == 0, first.stderr
    second = _driver(
        bash, tmp_path, tmp_path / "bin", "fault", "e02a-1", "pod-b", live=True
    )
    assert second.returncode == 2 and "has issued its fault" in second.stderr
    assert log.read_text("utf-8").splitlines() == [
        "--context docker-desktop delete pod pod-a --namespace inferops-release --wait=false"
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        ("fault", "dry-run-1", "pod-a"),
        ("fault", "e02a-2", "pod-a"),
        ("fault", "e02a-1", "Pod_A"),
    ],
)
def test_the_driver_refuses_a_fault_of_another_identifier_run_or_name(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    bash = _bash()
    log = _stub_kubectl(tmp_path / "bin")
    (tmp_path / ".artifacts" / "v2-e02a" / "runs" / "e02a-1").mkdir(parents=True)
    done = _driver(bash, tmp_path, tmp_path / "bin", *arguments, live=True)
    assert done.returncode == 2, done.stderr
    assert not log.exists()


def test_the_driver_holds_one_delete_and_the_package_names_no_cluster_command() -> None:
    text = DRIVER.read_text(encoding="utf-8")
    deletes = [
        line
        for line in text.splitlines()
        if " delete " in line and not line.lstrip().startswith("#")
    ]
    assert deletes == [
        '  k delete pod "${pod}" --namespace "${NAMESPACE}" --wait=false'
    ]
    for path in PACKAGE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "kubectl --context" not in source, path.name
        assert "docker exec" not in source, path.name


def test_each_verb_that_the_control_calls_is_a_verb_of_the_driver(
    tmp_path: Path,
) -> None:
    text = DRIVER.read_text(encoding="utf-8")
    control, port = _control(tmp_path, scenario(), fault=RecordingFault())
    control.run()
    called = {
        entry.split(":")[0].split(" ")[1]
        for entry in port.log
        if entry.split(" ")[0] in {"read", "status", "act", "start"}
    }
    for verb in called:
        assert f"\n    {verb})" in text, verb


# --------------------------------------------------------------------------
# Added after the independent review of the first commit
# --------------------------------------------------------------------------


class FailingFault(RecordingFault):
    """A fault whose command fails, as a kubectl that answers NotFound does."""

    def delete(self, pod: str) -> int:
        self.deleted.append(pod)
        return 1


def test_a_failed_fault_command_is_a_finding_and_the_run_is_observed(
    tmp_path: Path,
) -> None:
    fault = FailingFault()
    control, _ = _control(tmp_path, scenario(), fault=fault)
    outcome = control.run()
    assert outcome.state == OBSERVED
    step = next(s for s in _journal(outcome)["steps"] if s["step"] == "F2-F4")
    assert (step["held"], step["exitStatus"]) == (False, 1)
    assert step["findings"] == ["the fault command exited 1"]
    assert _steps(outcome)[-1] == "C4"


def test_p7_refuses_when_the_namespaces_after_the_preparation_are_not_read(
    tmp_path: Path,
) -> None:
    document = scenario()
    document["reads"]["namespaces"].insert(3, {"after": "application-apply", "exit": 1})
    control, port = _control(tmp_path, document)
    outcome = control.run()
    assert (outcome.state, outcome.step) == (REFUSED, "P7")
    p7 = next(s for s in _journal(outcome)["steps"] if s["step"] == "P7")
    assert p7["findings"] == [
        "the namespaces or the custom resource definitions were not read"
    ]
    assert "act release-remove: not executed in a dry run" in port.log


class _Failed:
    """A collector that samples and then exits 3."""

    def alive(self) -> bool:
        return True

    def output(self) -> str:
        return "samples: test\n"

    def wait(self, seconds: float) -> int | None:
        return 3

    def stop(self) -> None:
        return None


def test_c2_states_a_collector_that_failed(tmp_path: Path) -> None:
    control, port = _control(tmp_path, scenario(), fault=RecordingFault())
    port.start = lambda name, *arguments: _Failed()  # type: ignore[method-assign, assignment]
    outcome = control.run()
    c2 = next(s for s in _journal(outcome)["steps"] if s["step"] == "C2")
    assert c2["held"] is False
    assert c2["findings"] == [
        "the timeline collector exited 3",
        "the telemetry collector exited 3",
    ]


def test_c3_reads_spec_replicas_and_the_last_60_s_of_the_caller(
    tmp_path: Path,
) -> None:
    document = scenario()
    drifted = _deployments()
    drifted["items"][1]["spec"]["replicas"] = 2
    document["reads"]["deployments"] = [
        {"json": _deployments()},
        {"after": "runner-collect", "json": drifted},
    ]
    document["reads"]["caller-record"] = {"exit": 1}
    control, _ = _control(tmp_path, document, fault=RecordingFault())
    outcome = control.run()
    c3 = next(s for s in _journal(outcome)["steps"] if s["step"] == "C3")
    assert c3["findings"] == [
        "serving-runtime spec.replicas is 2",
        "the caller record holds no successful completion in the last 60 s of "
        "the window",
    ]


def test_c3_holds_when_the_caller_succeeds_at_the_end_of_the_window(
    tmp_path: Path,
) -> None:
    control, _ = _control(tmp_path, scenario(), fault=RecordingFault())
    outcome = control.run()
    c3 = next(s for s in _journal(outcome)["steps"] if s["step"] == "C3")
    assert c3["findings"] == []


def test_an_error_after_p5_stops_the_control_and_runs_the_cleanup(
    tmp_path: Path,
) -> None:
    control, port = _control(tmp_path, scenario())
    original = port.act

    def act(name: str, *arguments: str) -> int:
        if name == "controller":
            raise OSError("a file that cannot be written")
        return original(name, *arguments)

    port.act = act  # type: ignore[method-assign]
    outcome = control.run()
    assert (outcome.state, outcome.reason, outcome.step) == (
        control_module.STOPPED,
        "control-error: OSError",
        "P4 before-install",
    )
    journal = _journal(outcome)
    assert journal["outcome"]["state"] == control_module.STOPPED
    assert "act release-remove: not executed in a dry run" in port.log
    assert _steps(outcome)[-1] == "C4"


def test_an_interrupt_runs_the_cleanup_and_is_raised_again(tmp_path: Path) -> None:
    control, port = _control(tmp_path, scenario())
    original = port.act

    def act(name: str, *arguments: str) -> int:
        if name == "application-apply":
            raise KeyboardInterrupt
        return original(name, *arguments)

    port.act = act  # type: ignore[method-assign]
    with pytest.raises(KeyboardInterrupt):
        control.run()
    journal = json.loads((control.work / "control.json").read_text("utf-8"))
    assert journal["outcome"]["state"] == control_module.STOPPED
    assert "act release-remove: not executed in a dry run" in port.log


def test_a_dry_run_identifier_that_has_a_work_directory_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "load_plan", lambda _root: PLAN)
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(scenario()), "utf-8")
    arguments = ["dry-run", "--run-id", "dry-run-1", "--scenario", str(path)]
    assert cli.main(arguments) == 0
    assert cli.main(arguments) == cli.REFUSED_EXIT


@pytest.mark.parametrize(
    "caller",
    [
        {"everyMs": 0},
        {"everyMs": "2000"},
        {"podStartsAfterSeconds": -1},
        {"podStartsAfterSeconds": 1.5},
    ],
)
def test_a_scenario_with_an_unusable_caller_is_refused(caller: dict[str, Any]) -> None:
    with pytest.raises(ports.ScenarioRefused):
        ScenarioPort(scenario(caller=caller), None)


def test_the_driver_and_the_control_name_one_namespace_and_one_context() -> None:
    text = DRIVER.read_text(encoding="utf-8")
    assert f'\nNAMESPACE="{PLAN.namespace}"\n' in text
    assert f'k() {{ kubectl --context {core.KUBE_CONTEXT} "$@"; }}' in text


def test_the_driver_hands_the_control_paths_that_it_can_read(tmp_path: Path) -> None:
    """The phase run starts the control with the paths of the driver and of its
    bash in the form that the control reads, and with the controller namespace."""
    bash = _bash()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    seen = tmp_path / "seen.txt"
    stub = bin_dir / "uv"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$INFEROPS_E02A_DRIVER" "$INFEROPS_E02A_BASH" '
        f'"$INFEROPS_E02A_MODE" "$*" > "{seen.as_posix()}"\n',
        "utf-8",
        newline="\n",
    )
    stub.chmod(0o755)
    done = _driver(bash, tmp_path, bin_dir, "run", "e02a-1", live=False)
    assert done.returncode == 0, done.stderr
    driver, bash_path, mode, arguments = seen.read_text("utf-8").splitlines()
    assert Path(driver).resolve() == DRIVER.resolve()
    assert Path(bash_path).is_file()
    assert mode == "live"
    assert arguments.endswith(
        "python -m tools.experiment_e02a run --run-id e02a-1 "
        "--controller-namespace argocd"
    )


def _stub_driver(directory: Path, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stub = directory / "driver.txt"
    stub.write_text("#!/usr/bin/env bash\n" + body, "utf-8", newline="\n")
    return stub


def test_the_live_port_runs_each_verb_through_the_driver_and_keeps_it(
    tmp_path: Path,
) -> None:
    bash = _bash()
    # `pwd -W` prints the Windows form under Git Bash, and Linux bash has no such
    # option. Each host prints the form of the checkout path that its tools print.
    driver = _stub_driver(
        tmp_path / "bin",
        'case "$2" in\n'
        '  namespaces) printf "namespace/a\\n" ;;\n'
        '  runner-start) printf "from %s\\n" "$(pwd -W 2>/dev/null || pwd)"; exit 4 ;;\n'
        "  *) exit 1 ;;\n"
        "esac\n",
    )
    work = tmp_path / "work"
    work.mkdir()
    port = ports.LivePort(tmp_path, PLAN, driver, bash, work)
    assert port.read("namespaces") == "namespace/a\n"
    assert port.read("crds") is None
    assert port.act("runner-start", "e02a-1") == 4
    commands = (work / "commands.txt").read_text("utf-8").splitlines()
    assert commands[0].endswith("verb namespaces")
    assert all(str(tmp_path) not in line for line in commands)
    transcript = (work / "transcript.txt").read_text("utf-8")
    assert "[exit 4]" in transcript
    assert "from <repository>" in transcript


def test_a_live_fault_returns_the_status_of_the_fault_phase(tmp_path: Path) -> None:
    bash = _bash()
    driver = _stub_driver(
        tmp_path / "bin", '[ "$1" = fault ] && [ "$2" = e02a-1 ] && exit 3\nexit 9\n'
    )
    work = tmp_path / "work"
    work.mkdir()
    port = ports.LivePort(tmp_path, PLAN, driver, bash, work)
    fault = ports.LiveFault(tmp_path, driver, bash, "e02a-1", port)
    assert fault.delete("pod-a") == 3
    assert (
        (work / "commands.txt")
        .read_text("utf-8")
        .strip()
        .endswith("fault e02a-1 pod-a")
    )


@pytest.mark.skipif(
    sys.platform != "win32", reason="a drive-letter path is a path of Windows alone"
)
def test_the_transcript_replaces_each_form_of_the_checkout_path() -> None:
    port = ports.LivePort(Path("D:/work/InferOps"), PLAN, DRIVER, "bash", Path("w"))
    text = r"D:\work\InferOps\a D:/work/InferOps/b /d/work/InferOps/c /d/work/other"
    assert port._clean_text(text) == (
        r"<repository>\a <repository>/b <repository>/c /d/work/other"
    )
