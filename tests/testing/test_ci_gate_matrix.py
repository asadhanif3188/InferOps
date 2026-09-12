"""The continuous-integration gate matrix, held to the workflows it describes.

A gate matrix is the document most likely to be written once and then quietly
outlive the workflow it describes. A job gets renamed, a step gets added, a scan
gets dropped, and the table still reads beautifully. So the matrix here is data,
the workflows are parsed rather than trusted, and the two are compared in both
directions: a job with no row and a row with no job each fail.

Three of the checks are not bookkeeping. The normal lane may not reach a
Kubernetes cluster, may not download the pinned model artifact, and may not name
a third-party action by a tag. Each is a property somebody could break with one
plausible line, and each is stated as a prohibition in the matrix data and
checked here rather than reviewed.

This reads committed files. It runs no workflow, contacts no service, and knows
nothing about whether any of these jobs has ever passed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.ci_gates.core import MINIMUM_CONTROLS

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTING_DIR = REPO_ROOT / "docs" / "testing"
MATRIX_PATH = TESTING_DIR / "ci-gate-matrix.v1alpha1.json"
STRATEGY_PATH = TESTING_DIR / "test-strategy.v1alpha1.json"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

MATRIX: dict[str, Any] = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
STRATEGY: dict[str, Any] = json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))

GATES: list[dict[str, Any]] = MATRIX["gates"]
WORKFLOWS: list[dict[str, Any]] = MATRIX["workflows"]
PROHIBITIONS: list[dict[str, Any]] = MATRIX["prohibitions"]
TOOL_PINS: list[dict[str, Any]] = MATRIX["toolPins"]

LANE_BY_ID = {lane["laneId"]: lane for lane in STRATEGY["lanes"]}
LAYER_BY_ID = {layer["layerId"]: layer for layer in STRATEGY["layers"]}
CLAIM_BY_ID = {claim["claimId"]: claim for claim in STRATEGY["claims"]}
CLASS_BY_ID = {row["classId"]: row for row in STRATEGY["evidenceClasses"]}
LEVEL_BY_ID = {row["levelId"]: row for row in STRATEGY["certificationLevels"]}

GATE_FIELDS = (
    "gateId",
    "workflowId",
    "jobId",
    "purpose",
    "commands",
    "layers",
    "claims",
    "evidenceClass",
    "maxCertification",
    "blocking",
    "defendsNoClaimBecause",
    "whatItDoesNotProve",
    "claimStatusNote",
)

WORKFLOW_FIELDS = (
    "workflowId",
    "path",
    "workflowName",
    "lane",
    "triggers",
    "optIn",
    "requiresModel",
    "requiresCluster",
    "requiresAuthorization",
    "permissions",
    "notes",
)

#: A reference to an action, as it is written in a workflow: ``owner/repo@ref``.
#: Local (``./``) and container (``docker://``) references are not used here and
#: would need their own rule if they ever were.
USES = re.compile(r"^(?P<action>[^@\s]+)@(?P<ref>\S+)$")
FORTY_HEX = re.compile(r"^[0-9a-f]{40}$")

#: What a cluster-free workflow may not invoke. Each of these is one line away
#: from turning the normal lane into something that can reach an operator's
#: cluster, which is the failure ADR 0011 and the Sprint 4 amendment both name.
CLUSTER_TOKENS = (
    "kubectl",
    "helm ",
    "terraform ",
    "kind ",
    "kind create",
    "INFEROPS_PROVIDER",
    "KUBECONFIG",
    "kubeconfig",
)

#: What a model-free workflow may not invoke.
MODEL_TOKENS = (
    "tools.model_acquisition",
    "tools.model_lifecycle",
    "--confirm-real-runtime",
    "huggingface.co",
)


def workflow_document(entry: dict[str, Any]) -> dict[str, Any]:
    """A committed workflow, parsed.

    ``on:`` is the YAML 1.1 boolean ``True`` once loaded, which is why the
    trigger check below looks the key up by both spellings rather than by the
    one a reader would expect.
    """
    loaded = yaml.safe_load((REPO_ROOT / entry["path"]).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), entry["path"]
    return loaded


def workflow_text(entry: dict[str, Any]) -> str:
    return (REPO_ROOT / entry["path"]).read_text(encoding="utf-8")


def committed_workflows() -> list[Path]:
    if not WORKFLOW_DIR.is_dir():
        return []
    return sorted(
        path
        for path in WORKFLOW_DIR.iterdir()
        if path.suffix in {".yml", ".yaml"} and path.is_file()
    )


# --------------------------------------------------------------------------
# The data is well formed, and it found something
# --------------------------------------------------------------------------


def test_the_matrix_describes_at_least_one_workflow_and_several_gates() -> None:
    """A glob that matched nothing produces an empty, passing matrix."""
    assert WORKFLOWS, "the gate matrix describes no workflow"
    assert len(GATES) >= 8, len(GATES)


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_every_gate_declares_every_required_field(gate: dict) -> None:
    assert set(gate) == set(GATE_FIELDS), {
        "missing": sorted(set(GATE_FIELDS) - set(gate)),
        "unexpected": sorted(set(gate) - set(GATE_FIELDS)),
    }


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_every_workflow_row_declares_every_required_field(entry: dict) -> None:
    assert set(entry) == set(WORKFLOW_FIELDS), {
        "missing": sorted(set(WORKFLOW_FIELDS) - set(entry)),
        "unexpected": sorted(set(entry) - set(WORKFLOW_FIELDS)),
    }


def test_every_gate_identifier_is_unique() -> None:
    identifiers = [gate["gateId"] for gate in GATES]
    assert len(identifiers) == len(set(identifiers)), identifiers


def test_the_data_points_back_at_the_documents_that_describe_it() -> None:
    for field in (
        "decisionRef",
        "documentRef",
        "strategyRef",
        "strategyDocumentRef",
        "matrixRef",
        "contributingRef",
    ):
        ref = MATRIX[field]
        assert (REPO_ROOT / ref).is_file(), f"{field} -> {ref}"


# --------------------------------------------------------------------------
# The matrix and the workflows, in both directions
# --------------------------------------------------------------------------


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_every_workflow_the_matrix_names_is_committed(entry: dict) -> None:
    assert (REPO_ROOT / entry["path"]).is_file(), entry["path"]


def test_every_committed_workflow_has_a_row() -> None:
    """A workflow file nobody put in the matrix is a gate nobody reviewed."""
    described = {entry["path"] for entry in WORKFLOWS}
    committed = {
        path.relative_to(REPO_ROOT).as_posix() for path in committed_workflows()
    }
    assert committed == described, {
        "committed but not in the matrix": sorted(committed - described),
        "in the matrix but not committed": sorted(described - committed),
    }


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_the_matrix_and_the_workflow_declare_the_same_jobs(entry: dict) -> None:
    document = workflow_document(entry)
    in_workflow = set(document["jobs"])
    in_matrix = {
        gate["jobId"] for gate in GATES if gate["workflowId"] == entry["workflowId"]
    }
    assert in_workflow == in_matrix, {
        "workflow": entry["path"],
        "jobs with no gate row": sorted(in_workflow - in_matrix),
        "gate rows with no job": sorted(in_matrix - in_workflow),
    }


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_every_gate_names_a_workflow_the_matrix_describes(gate: dict) -> None:
    assert gate["workflowId"] in {entry["workflowId"] for entry in WORKFLOWS}, gate[
        "workflowId"
    ]


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_the_workflow_publishes_the_name_the_matrix_records(entry: dict) -> None:
    assert workflow_document(entry)["name"] == entry["workflowName"], entry["path"]


# --------------------------------------------------------------------------
# The lane, and what a gate is allowed to certify
# --------------------------------------------------------------------------


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_every_workflow_runs_a_lane_the_strategy_declares(entry: dict) -> None:
    assert entry["lane"] in LANE_BY_ID, entry["lane"]


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_the_lane_a_workflow_runs_points_back_at_that_workflow(entry: dict) -> None:
    """The strategy's ``workflowRef`` and this matrix name the same file.

    Without this the strategy could record one workflow as automating a lane
    while the gate matrix described a different one, and both documents would
    pass their own suites.
    """
    lane = LANE_BY_ID[entry["lane"]]
    assert lane["automated"] is True, lane["laneId"]
    assert lane["workflowRef"] == entry["path"], {
        "lane": lane["laneId"],
        "strategy workflowRef": lane["workflowRef"],
        "gate matrix path": entry["path"],
    }


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_a_workflow_agrees_with_its_lane_about_model_cluster_and_opt_in(
    entry: dict,
) -> None:
    lane = LANE_BY_ID[entry["lane"]]
    assert entry["requiresCluster"] == lane["clusterRequired"], lane["laneId"]
    assert entry["requiresAuthorization"] == lane["authorizationRequired"], lane[
        "laneId"
    ]
    assert entry["optIn"] == lane["optIn"], lane["laneId"]
    assert entry["requiresModel"] == (lane["modelDownload"] != "none"), lane["laneId"]


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_every_gate_declares_an_evidence_class_the_strategy_defines(gate: dict) -> None:
    assert gate["evidenceClass"] in CLASS_BY_ID, gate["evidenceClass"]
    assert gate["maxCertification"] in LEVEL_BY_ID, gate["maxCertification"]


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_no_gate_certifies_above_the_ceiling_its_evidence_class_allows(
    gate: dict,
) -> None:
    """The ceiling is inherited, never restated. A mock stops at C1 here too."""
    ceiling = CLASS_BY_ID[gate["evidenceClass"]]["maxCertification"]
    assert ceiling is not None, gate["evidenceClass"]
    assert (
        LEVEL_BY_ID[gate["maxCertification"]]["rank"] <= LEVEL_BY_ID[ceiling]["rank"]
    ), {
        "gate": gate["gateId"],
        "claims up to": gate["maxCertification"],
        "class ceiling": ceiling,
    }


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_no_gate_in_a_cluster_free_lane_names_a_layer_that_needs_one(
    gate: dict,
) -> None:
    entry = next(row for row in WORKFLOWS if row["workflowId"] == gate["workflowId"])
    for layer_id in gate["layers"]:
        layer = LAYER_BY_ID[layer_id]
        if not entry["requiresCluster"]:
            assert not layer["requiresCluster"], (gate["gateId"], layer_id)
        if not entry["requiresModel"]:
            assert not layer["requiresModel"], (gate["gateId"], layer_id)


# --------------------------------------------------------------------------
# Every gate maps to a claim, or says why it maps to none
# --------------------------------------------------------------------------


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_every_layer_a_gate_names_is_a_layer_the_strategy_declares(gate: dict) -> None:
    for layer_id in gate["layers"]:
        assert layer_id in LAYER_BY_ID, (gate["gateId"], layer_id)


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_every_claim_a_gate_names_is_a_claim_the_strategy_declares(gate: dict) -> None:
    for claim_id in gate["claims"]:
        assert claim_id in CLAIM_BY_ID, (gate["gateId"], claim_id)


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_a_gate_maps_to_a_claim_or_records_why_it_maps_to_none(gate: dict) -> None:
    """There is no third option, which is what makes the mapping complete.

    The acceptance criterion is that the matrix maps every check to a V1 claim.
    A check that genuinely defends none - a formatter, a build - satisfies it by
    saying so in writing, and a row that is simply blank fails.
    """
    if gate["claims"]:
        assert gate["defendsNoClaimBecause"] is None, gate["gateId"]
    else:
        assert gate["defendsNoClaimBecause"], gate["gateId"]


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_a_gate_claims_only_what_the_layers_it_runs_could_support(gate: dict) -> None:
    """A claim is reachable from a gate only through a layer they share.

    Without this a scanning gate could be recorded as defending a serving claim,
    and the matrix would read as if continuous integration proved something it
    never touches.
    """
    reachable = set(gate["layers"])
    for claim_id in gate["claims"]:
        named = set(CLAIM_BY_ID[claim_id]["layers"])
        assert named & reachable, {
            "gate": gate["gateId"],
            "claim": claim_id,
            "claim rests on": sorted(named),
            "gate runs": sorted(reachable),
        }


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_every_gate_states_what_it_does_not_prove(gate: dict) -> None:
    assert gate["whatItDoesNotProve"], gate["gateId"]


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_a_gate_naming_a_planned_claim_says_the_claim_is_still_planned(
    gate: dict,
) -> None:
    """A workflow is a configuration, and a configuration is not a result.

    A gate may name a claim the strategy still records as planned - that is the
    mapping the matrix exists to publish. What it may not do is leave a reader
    to assume that committing the workflow certified it.
    """
    planned = [
        claim_id
        for claim_id in gate["claims"]
        if CLAIM_BY_ID[claim_id]["v1Status"] != "certified"
    ]
    if planned:
        assert gate["claimStatusNote"] or gate["evidenceClass"] == "mock", {
            "gate": gate["gateId"],
            "claims that are not certified": planned,
        }


# --------------------------------------------------------------------------
# The prohibitions, which are the reason this suite exists
# --------------------------------------------------------------------------


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_a_cluster_free_workflow_cannot_reach_a_cluster(entry: dict) -> None:
    """The Sprint 4 amendment as a check rather than a sentence.

    A normal lane that can discover an ambient cluster is a normal lane that can
    mutate somebody's cluster from a pull request. The tokens are read out of
    the file's text rather than out of its parsed steps, because a cluster can
    be reached from a script block, an action input, or an environment variable,
    and only the text sees all three.
    """
    if entry["requiresCluster"]:
        return
    text = workflow_text(entry)
    prose = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    found = [token for token in CLUSTER_TOKENS if token in prose]
    assert not found, {"workflow": entry["path"], "cluster tokens": found}


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_a_model_free_workflow_cannot_download_the_model(entry: dict) -> None:
    if entry["requiresModel"]:
        return
    prose = "\n".join(
        line
        for line in workflow_text(entry).splitlines()
        if not line.lstrip().startswith("#")
    )
    found = [token for token in MODEL_TOKENS if token in prose]
    assert not found, {"workflow": entry["path"], "model tokens": found}


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_every_action_a_workflow_uses_is_pinned_by_commit_sha(entry: dict) -> None:
    document = workflow_document(entry)
    unpinned: list[str] = []
    for job in document["jobs"].values():
        for step in job.get("steps", []):
            reference = step.get("uses")
            if reference is None:
                continue
            matched = USES.match(reference)
            assert matched, reference
            if not FORTY_HEX.match(matched.group("ref")):
                unpinned.append(reference)
    assert not unpinned, {"workflow": entry["path"], "not pinned by SHA": unpinned}


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_every_action_a_workflow_uses_is_recorded_in_the_tool_pins(entry: dict) -> None:
    pinned = {row["tool"]: row["pin"] for row in TOOL_PINS}
    document = workflow_document(entry)
    for job in document["jobs"].values():
        for step in job.get("steps", []):
            reference = step.get("uses")
            if reference is None:
                continue
            matched = USES.match(reference)
            assert matched, reference
            action, ref = matched.group("action"), matched.group("ref")
            assert action in pinned, f"{action} is used but has no toolPins row"
            assert pinned[action] == ref, {
                "action": action,
                "in the workflow": ref,
                "in the tool pins": pinned[action],
            }


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_every_workflow_declares_its_token_permissions(entry: dict) -> None:
    document = workflow_document(entry)
    assert "permissions" in document, entry["path"]
    assert document["permissions"] == {"contents": "read"}, document["permissions"]


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_every_job_declares_a_timeout_within_its_lane_budget(entry: dict) -> None:
    """An unbounded job is a six-hour job, which is the runner default."""
    budget = LANE_BY_ID[entry["lane"]]["timeoutMinutes"]
    for name, job in workflow_document(entry)["jobs"].items():
        assert "timeout-minutes" in job, f"{entry['path']}: {name} declares no timeout"
        assert job["timeout-minutes"] <= budget, {
            "job": name,
            "timeout": job["timeout-minutes"],
            "lane budget": budget,
        }


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_every_job_runs_on_a_pinned_runner_image(entry: dict) -> None:
    """``ubuntu-latest`` moves, and a lane whose runner moves cannot attribute
    a failure to the change that appeared to cause it."""
    declared = MATRIX["service"]["runner"]
    for name, job in workflow_document(entry)["jobs"].items():
        assert job["runs-on"] == declared, {
            "job": name,
            "runs-on": job["runs-on"],
            "declared runner": declared,
        }
        assert "latest" not in job["runs-on"], job["runs-on"]


@pytest.mark.parametrize(
    "prohibition", PROHIBITIONS, ids=lambda row: row["prohibitionId"]
)
def test_every_prohibition_names_the_module_that_enforces_it(
    prohibition: dict,
) -> None:
    ref = prohibition["enforcedBy"]
    assert (REPO_ROOT / ref).is_file(), ref


# --------------------------------------------------------------------------
# The document and the data
# --------------------------------------------------------------------------

FIRST_TABLE_COLUMN = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)


def matrix_document() -> str:
    return (REPO_ROOT / MATRIX["documentRef"]).read_text(encoding="utf-8")


def test_the_document_publishes_every_gate_and_only_gates() -> None:
    published = set(FIRST_TABLE_COLUMN.findall(matrix_document()))
    expected = {gate["gateId"] for gate in GATES}
    allowed = expected | {row["tool"] for row in TOOL_PINS} | set(MINIMUM_CONTROLS)
    assert not expected - published, sorted(expected - published)
    assert not published - allowed, sorted(published - allowed)


def test_the_document_publishes_every_expected_failure_control_group() -> None:
    """The four groups are read from the tool, not retyped beside it.

    A group added to the runner and not to the document would otherwise be a
    control nobody reviewing the matrix knows runs.
    """
    published = set(FIRST_TABLE_COLUMN.findall(matrix_document()))
    assert set(MINIMUM_CONTROLS) <= published, sorted(set(MINIMUM_CONTROLS) - published)


def test_the_document_publishes_the_gate_count_the_data_produces() -> None:
    """A count kept by hand is a count that outlives its data."""
    words = (
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
    )
    expected = f"{words[len(GATES)].capitalize()} gates run on every change."
    assert expected in " ".join(matrix_document().split()), expected
