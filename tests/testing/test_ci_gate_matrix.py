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
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.ci_gates import workflow_boundary
from tools.ci_gates.core import MINIMUM_CONTROLS
from tools.ci_gates.infrastructure import (
    KUBECONFORM_SCHEMA_LOCATION,
    MINIMUM_TOOL_CONTROLS,
    PINNED_VERSIONS,
)

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

#: What a model-free workflow may not invoke. The authoritative list lives with
#: the rest of the lane rules and is imported rather than copied, so the gate and
#: this suite cannot disagree about what a download looks like.
MODEL_TOKENS = workflow_boundary.MODEL_TOKENS


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
def test_every_workflow_satisfies_the_rules_of_its_lane(entry: dict) -> None:
    """The Sprint 4 amendment as a check rather than a sentence.

    A normal lane that can discover an ambient cluster is a normal lane that can
    mutate somebody's cluster from a pull request. Until V1-S4-001-PR2 this read
    the workflow's text for `helm ` and `terraform ` and refused both outright.
    That was right while neither tool had a job here, and it could not survive
    the change that gave them one: `helm template` and `terraform validate` read
    files, and a rule that refused them would have kept the chart and the
    configuration out of the lane that exists to check them.

    The rule now refuses what reaches a cluster rather than the program names:
    any Helm or Terraform subcommand outside the offline set, `init` without
    `-backend=false`, kubectl, kind, a kubeconfig, a provider selection, and any
    environment script. It still reads text, because a cluster can be reached
    from a script block, an action input, or an environment variable, and only
    the text sees all three. A lane that needs a cluster is held to the dispatch
    rules instead, by the same function.
    """
    found = workflow_boundary.problems(workflow_text(entry), entry["lane"])
    assert not found, {
        "workflow": entry["path"],
        "lane": entry["lane"],
        "problems": [str(problem) for problem in found],
    }


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


BOUNDARY_RULE = re.compile(r'Problem\(\s*"(?P<rule>[a-z0-9-]+)"')

#: Rules that guard against malformed input rather than a lane's boundary.
INPUT_RULES = frozenset({"lane-is-declared", "workflow-parses"})


def boundary_rules() -> set[str]:
    """Every lane rule the workflow checker can raise, read from its source."""
    source = Path(workflow_boundary.__file__).read_text(encoding="utf-8")
    return set(BOUNDARY_RULE.findall(source)) - INPUT_RULES


def test_the_document_publishes_every_lane_rule_the_checker_raises() -> None:
    """A rule the checker enforces and the matrix does not name is a rule a
    reviewer of the first cluster workflow cannot find."""
    document = matrix_document()
    missing = sorted(rule for rule in boundary_rules() if f"`{rule}`" not in document)
    assert not missing, missing


def test_the_document_publishes_every_gate_and_only_gates() -> None:
    published = set(FIRST_TABLE_COLUMN.findall(matrix_document()))
    expected = {gate["gateId"] for gate in GATES}
    allowed = (
        expected
        | {row["tool"] for row in TOOL_PINS}
        | set(MINIMUM_CONTROLS)
        | set(MINIMUM_TOOL_CONTROLS)
        | boundary_rules()
    )
    assert not expected - published, sorted(expected - published)
    assert not published - allowed, sorted(published - allowed)


def test_the_document_publishes_every_expected_failure_control_group() -> None:
    """The groups are read from the runners, not retyped beside them.

    A group added to a runner and not to the document would otherwise be a
    control nobody reviewing the matrix knows runs.
    """
    published = set(FIRST_TABLE_COLUMN.findall(matrix_document()))
    groups = set(MINIMUM_CONTROLS) | set(MINIMUM_TOOL_CONTROLS)
    assert groups <= published, sorted(groups - published)


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


def _number_word(value: int) -> str:
    ones = [
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
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
    ]
    tens = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy"}
    if value < 20:
        return ones[value]
    ten, one = divmod(value, 10)
    return tens[ten] if one == 0 else f"{tens[ten]}-{ones[one]}"


def test_the_document_publishes_the_control_counts_the_runners_produce() -> None:
    """Three counts, each read from the runner that produces it."""
    from tools.ci_gates import core, infrastructure

    document = " ".join(matrix_document().split())
    counts = {
        "expected-failures": (len(core.controls()), len(MINIMUM_CONTROLS)),
        **{
            family: (
                len(infrastructure.controls(family)),
                len(infrastructure.GROUPS_BY_FAMILY[family]),
            )
            for family in infrastructure.FAMILIES
        },
    }
    for runner, (controls, groups) in counts.items():
        sentence = (
            f"{_number_word(controls).capitalize()} controls run, in "
            f"{_number_word(groups)} groups."
        )
        assert sentence in document, (runner, sentence)


# --- The commands a gate documents are commands its job actually runs -------

#: Shell words that introduce a command without being one.
_NOT_A_PROGRAM = frozenset({"", "sudo", "then", "do", "if", "!"})


def programs_in(command: str) -> list[str]:
    """Every program a command line invokes: the first word of each pipe stage.

    Deliberately coarse. It is not trying to parse a shell; it is trying to
    catch a matrix row that names a tool its job does not run, which is what
    happened once already - the wheel inspection was documented as ``unzip``
    while the job used Python's ``zipfile``.
    """
    found: list[str] = []
    for stage in command.split("|"):
        words = stage.strip().split()
        while words and words[0] in _NOT_A_PROGRAM:
            words = words[1:]
        if words:
            found.append(words[0])
    return found


@pytest.mark.parametrize("gate", GATES, ids=lambda gate: gate["gateId"])
def test_every_program_a_gate_documents_is_run_by_its_job(gate: dict) -> None:
    """A documented command is a command the job runs.

    The check is one-directional on purpose: a program the job runs and the
    matrix does not document - a setup step's curl - is not reported, because
    listing every one of those would make the matrix a transcript rather than a
    map. The direction that matters is the one that goes stale.
    """
    entry = next(row for row in WORKFLOWS if row["workflowId"] == gate["workflowId"])
    job = workflow_document(entry)["jobs"][gate["jobId"]]
    ran = "\n".join(
        str(step[key])
        for step in job.get("steps", [])
        for key in ("run", "uses")
        if key in step
    )
    missing = [
        program
        for command in gate["commands"]
        for program in programs_in(command)
        if program not in ran
    ]
    assert not missing, {
        "gate": gate["gateId"],
        "documented but never invoked by the job": missing,
    }


# --- A script a job runs by path is a script the runner may execute ---------

#: A ``run:`` line whose first word is a repository script, run by path rather
#: than through an interpreter, with or without a leading ``./``. A script handed
#: to ``bash`` or ``source`` is deliberately not matched: neither asks for the
#: executable bit, so neither can fail the way this check exists to prevent.
SCRIPT_BY_PATH = re.compile(r"^\s*(?:\./)?(?P<path>scripts/\S+\.sh)\b", re.MULTILINE)


def index_modes() -> dict[str, str]:
    """Every tracked path's mode, as git stores it and as a checkout applies it.

    Asked of git rather than of the filesystem, because on Windows the
    filesystem has no executable bit to report and every file looks runnable.
    That is how three scripts reached the workflow stored as ``100644``: every
    local run went through Git Bash, which does not ask, and the first hosted
    run refused all three with ``Permission denied``.
    """
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not on PATH; the stored file mode cannot be read")
    # A fixed argument vector with no shell: `git` is resolved from PATH by
    # `shutil.which` and every other member is a constant.
    result = subprocess.run(
        [git, "ls-files", "--stage", "--", "scripts"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"not a git work tree: {result.stderr.strip()}")
    modes: dict[str, str] = {}
    for line in result.stdout.splitlines():
        metadata, _, path = line.partition("\t")
        modes[path] = metadata.split()[0]
    return modes


@pytest.mark.parametrize("entry", WORKFLOWS, ids=lambda entry: entry["workflowId"])
def test_every_script_a_job_runs_by_path_is_stored_executable(entry: dict) -> None:
    modes = index_modes()
    invoked = {
        matched.group("path")
        for job in workflow_document(entry)["jobs"].values()
        for step in job.get("steps", [])
        for matched in SCRIPT_BY_PATH.finditer(str(step.get("run", "")))
    }
    assert invoked, f"{entry['path']} runs no script by path; the check is vacuous"
    not_executable = {
        path: modes.get(path, "untracked")
        for path in sorted(invoked)
        if modes.get(path) != "100755"
    }
    assert not not_executable, {
        "workflow": entry["path"],
        "run by path but not stored executable": not_executable,
    }


# --- A downloaded binary is a pinned binary ---------------------------------

#: A job environment variable holding a tool's release version or archive digest.
PIN_VARIABLE = re.compile(r"^(?P<tool>[A-Z]+)_(?P<kind>VERSION|SHA256)$")


def pinned_environment() -> dict[str, dict[str, str]]:
    """Every ``<TOOL>_VERSION`` and ``<TOOL>_SHA256`` a job declares, by tool."""
    found: dict[str, dict[str, str]] = {}
    for entry in WORKFLOWS:
        for job in workflow_document(entry)["jobs"].values():
            for name, value in (job.get("env") or {}).items():
                matched = PIN_VARIABLE.match(name)
                if matched is None:
                    continue
                tool = matched.group("tool").lower()
                kind = matched.group("kind")
                previous = found.setdefault(tool, {}).get(kind)
                assert previous in (None, str(value)), {
                    "tool": tool,
                    "pinned twice, differently": (previous, value),
                }
                found[tool][kind] = str(value)
    return found


def test_every_downloaded_tool_is_recorded_in_the_tool_pins() -> None:
    """A digest in the workflow and a digest in the matrix are the same digest."""
    pins = {row["tool"]: row for row in TOOL_PINS}
    environment = pinned_environment()
    assert environment, "no job pins a downloaded tool; the check is vacuous"
    for tool, declared in environment.items():
        assert tool in pins, f"{tool} is downloaded but has no toolPins row"
        assert declared.get("SHA256") == pins[tool]["pin"], {
            "tool": tool,
            "workflow digest": declared.get("SHA256"),
            "matrix pin": pins[tool]["pin"],
        }
        human = pins[tool]["humanVersion"].lstrip("v")
        assert declared.get("VERSION", "").lstrip("v") == human, (
            tool,
            declared.get("VERSION"),
            pins[tool]["humanVersion"],
        )


def test_the_installed_versions_are_the_versions_the_controls_require() -> None:
    """The runner refuses a tool at any other version, so the two must agree.

    Without this a bump to the workflow's download would install a binary the
    control runner then refuses - loudly, but on the service rather than here.
    """
    environment = pinned_environment()
    for tool, version in PINNED_VERSIONS.items():
        assert tool in environment, f"{tool} is required and never installed"
        installed = environment[tool]["VERSION"].lstrip("v")
        assert installed == version.lstrip("v"), (tool, installed, version)


def test_the_schema_source_the_job_reads_is_the_pinned_commit() -> None:
    declared = {
        job.get("env", {}).get("KUBECONFORM_SCHEMA_LOCATION")
        for entry in WORKFLOWS
        for job in workflow_document(entry)["jobs"].values()
    } - {None}
    assert declared == {KUBECONFORM_SCHEMA_LOCATION}, declared
    pins = {row["tool"]: row["pin"] for row in TOOL_PINS}
    assert pins["kubernetes-json-schema"] in KUBECONFORM_SCHEMA_LOCATION


KUBECONFORM_CALL = re.compile(r"(?:^|\|)\s*kubeconform\s+-")


def test_every_kubeconform_call_reads_the_pinned_schema_source() -> None:
    """kubeconform's default is a moving branch, and a call that forgets the
    flag reads it without saying so."""
    calls = 0
    for entry in WORKFLOWS:
        for name, job in workflow_document(entry)["jobs"].items():
            for step in job.get("steps", []):
                for line in str(step.get("run", "")).splitlines():
                    # `kubeconform -v` prints a version and validates nothing.
                    if (
                        KUBECONFORM_CALL.search(line)
                        and line.strip() != "kubeconform -v"
                    ):
                        calls += 1
                        assert "-schema-location" in line, (name, line)
    assert calls >= 2, calls


def test_every_download_is_checked_against_a_committed_digest() -> None:
    """A `curl` with no `sha256sum --check` after it is a binary nobody pinned."""
    checked = 0
    for entry in WORKFLOWS:
        for name, job in workflow_document(entry)["jobs"].items():
            for step in job.get("steps", []):
                script = str(step.get("run", ""))
                if "curl " not in script:
                    continue
                assert "sha256sum --check --strict" in script, (name, step.get("name"))
                assert script.index("curl ") < script.index("sha256sum --check"), name
                checked += 1
    assert checked >= 5, checked


# --- The local equivalents are the commands the jobs run --------------------


def _job_runs(job_id: str) -> str:
    entry = next(row for row in WORKFLOWS if row["workflowId"] == "checks")
    job = workflow_document(entry)["jobs"][job_id]
    return "\n".join(str(step.get("run", "")) for step in job["steps"])


def test_the_terraform_job_runs_what_the_wrapper_check_action_runs() -> None:
    """CONTRIBUTING publishes the wrapper's `check` action as a local equivalent.

    The job cannot call the wrapper - it is an environment script, and the lane
    refuses every one of those - so it types the same three commands, and this
    keeps the two from drifting apart.
    """
    wrapper = (
        REPO_ROOT / "scripts" / "environment" / "terraform-prerequisites.sh"
    ).read_text(encoding="utf-8")
    check_block = wrapper[wrapper.index('if [ "${action}" = "check" ]') :]
    check_block = check_block[: check_block.index("\nfi\n")]
    runs = _job_runs("terraform")
    for fragment in (
        "fmt -check -recursive",
        "init -backend=false -input=false",
        "validate",
    ):
        assert fragment in check_block, fragment
        assert fragment in runs, fragment


def test_the_helm_job_runs_the_lint_commands_contributing_publishes() -> None:
    contributing = (REPO_ROOT / MATRIX["contributingRef"]).read_text(encoding="utf-8")
    runs = _job_runs("helm-chart")
    for profile in ("real", "mock"):
        command = (
            "helm lint charts/inferops-llm --strict --namespace inferops-platform "
            f"--values charts/inferops-llm/ci/{profile}-values.yaml"
        )
        assert command in " ".join(contributing.split()), command
        assert command in runs, command
