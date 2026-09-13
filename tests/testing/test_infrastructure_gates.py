"""The infrastructure gates' own rules, put to the shapes they exist to refuse.

Three checkers arrived with V1-S4-001-PR2, and each one is a rule that passes
over the committed files - which is also what a rule that reads nothing does.
So every rule here is held to fixtures that must be refused for a recorded
reason, and to inputs that must be accepted:

* the lane rules for a workflow - the cluster-free rule the normal lane runs
  under, and the dispatch rules a lane that needs a cluster would run under if
  one were committed. None is: no runner is labelled capable;
* the ownership-overlap rule between a chart render and a Terraform
  configuration;
* the tool-control runner, which may not pass a negative control because a
  tool failed to start or refused for a reason nobody wrote down.

This module needs no Helm, no Terraform, and no network. The controls that run
those tools are exercised by the `helm-chart` and `terraform` gates; what is
checked here is the machinery that decides whether such a control passed.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.ci_gates import infrastructure, suites, workflow_boundary
from tools.ci_gates import ownership_overlap as overlap
from tools.ci_gates.core import MINIMUM_CONTROLS, controls, shortfalls

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]

WORKFLOW_FIXTURES = REPO_ROOT / "tests" / "testing" / "fixtures" / "workflow-boundary"
WORKFLOW_MANIFEST: dict[str, Any] = json.loads(
    (WORKFLOW_FIXTURES / "invalid" / "expected-rejections.json").read_text(
        encoding="utf-8"
    )
)
OWNERSHIP_FIXTURES = REPO_ROOT / "tests" / "testing" / "fixtures" / "ownership-overlap"
INVENTORY: dict[str, Any] = json.loads(
    (
        REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
    ).read_text(encoding="utf-8")
)
RENDERED = REPO_ROOT / "charts" / "inferops-llm" / "ci" / "rendered"
TERRAFORM_ROOT = REPO_ROOT / "infra" / "terraform"


def _rules(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    lane = workflow_boundary.lane_for(path, text)
    assert lane is not None, path.name
    return {problem.rule for problem in workflow_boundary.problems(text, lane)}


# --------------------------------------------------------------------------
# The workflow fixtures, and the manifest that says why each is refused
# --------------------------------------------------------------------------

INVALID_WORKFLOWS = sorted((WORKFLOW_FIXTURES / "invalid").glob("*.yaml"))
VALID_WORKFLOWS = sorted((WORKFLOW_FIXTURES / "valid").glob("*.yaml"))
RECORDED = {row["fixture"]: row for row in WORKFLOW_MANIFEST["fixtures"]}


def test_the_workflow_manifest_and_the_fixture_directory_agree() -> None:
    on_disk = {path.name for path in INVALID_WORKFLOWS}
    assert on_disk == set(RECORDED), {
        "fixtures with no manifest row": sorted(on_disk - set(RECORDED)),
        "manifest rows with no fixture": sorted(set(RECORDED) - on_disk),
    }


@pytest.mark.parametrize("path", INVALID_WORKFLOWS, ids=lambda path: path.name)
def test_each_broken_workflow_breaks_exactly_the_rules_it_records(path: Path) -> None:
    """Both directions: a fixture refused for a different rule is a failure."""
    row = RECORDED[path.name]
    text = path.read_text(encoding="utf-8")
    assert workflow_boundary.lane_for(path, text) == row["lane"], path.name
    assert _rules(path) == set(row["rules"]), {
        "fixture": path.name,
        "recorded": row["rules"],
        "produced": sorted(_rules(path)),
    }


@pytest.mark.parametrize("path", VALID_WORKFLOWS, ids=lambda path: path.name)
def test_each_valid_workflow_shape_breaks_no_rule(path: Path) -> None:
    assert _rules(path) == set(), path.name


def test_the_valid_shapes_cover_both_lanes_that_need_a_cluster() -> None:
    lanes = {
        workflow_boundary.lane_for(path, path.read_text(encoding="utf-8"))
        for path in VALID_WORKFLOWS
    }
    assert lanes == {"cluster-smoke", "real-runtime"}, lanes


RULE_IN_SOURCE = re.compile(r'Problem\(\s*"(?P<rule>[a-z0-9-]+)"')


def test_every_rule_the_checker_can_raise_is_exercised_by_a_fixture() -> None:
    """A rule no fixture breaks is a rule nobody has watched fire."""
    source = Path(workflow_boundary.__file__).read_text(encoding="utf-8")
    raisable = set(RULE_IN_SOURCE.findall(source))
    # Two guard against malformed input rather than a broken lane rule, and a
    # fixture for either would be a test of YAML rather than of the boundary.
    raisable -= {"lane-is-declared", "workflow-parses"}
    exercised = {rule for row in RECORDED.values() for rule in row["rules"]}
    assert raisable == exercised, {
        "raisable and never exercised": sorted(raisable - exercised),
        "recorded and not raisable": sorted(exercised - raisable),
    }


def test_the_committed_workflows_are_accepted_by_the_same_checker() -> None:
    committed = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
    assert committed, "no committed workflow; the check is vacuous"
    for path in committed:
        assert _rules(path) == set(), path.name


# --- The cluster-free rule, put to the shapes it has to see ------------------

REFUSED_IN_THE_DEFAULT_LANE = (
    "helm install inferops charts/inferops-llm",
    "helm upgrade --install inferops charts/inferops-llm",
    "helm test inferops",
    "helm uninstall inferops",
    "helm list --all",
    "helm repo add bitnami https://example.invalid",
    "helm dependency build charts/inferops-llm",
    "helm $SUBCOMMAND charts/inferops-llm",
    "terraform plan",
    "terraform apply -auto-approve",
    "terraform -chdir=infra/terraform/environments/local destroy",
    "terraform -chdir=infra/terraform/environments/local import x y",
    "terraform state list",
    "terraform init",
    "terraform -chdir=infra/terraform/environments/local init -input=false",
    "kubectl get nodes",
    "kind create cluster",
    "export KUBECONFIG=/tmp/config",
    "helm template x charts/inferops-llm --kube-context other",
    "INFEROPS_PROVIDER=kind make",
    "scripts/environment/cluster-up.sh",
    "bash scripts/environment/terraform-prerequisites.sh check",
    "echo ready && helm install x charts/inferops-llm",
    "cat render.yaml | helm upgrade x charts/inferops-llm",
)

ACCEPTED_IN_THE_DEFAULT_LANE = (
    "helm lint charts/inferops-llm --strict --values charts/inferops-llm/ci/real-values.yaml",
    "helm template inferops charts/inferops-llm --namespace inferops-platform",
    "helm version --short",
    "terraform fmt -check -recursive infra/terraform",
    "terraform -chdir=infra/terraform/environments/local init -backend=false -input=false",
    "terraform -chdir=infra/terraform/environments/local validate",
    "terraform version",
    "tar -xzf helm-v3.19.0-linux-amd64.tar.gz linux-amd64/helm",
    "sudo install -m 0755 linux-amd64/helm /usr/local/bin/helm",
    "sudo install -m 0755 terraform-bin/terraform /usr/local/bin/terraform",
    'archive="terraform_${TERRAFORM_VERSION}_linux_amd64.zip"',
    "tflint --recursive --chdir=infra/terraform --format=compact",
    "kubeconform -strict -summary -kubernetes-version 1.34.0 -",
)


@pytest.mark.parametrize("line", REFUSED_IN_THE_DEFAULT_LANE)
def test_the_cluster_free_rule_refuses_what_reaches_a_cluster(line: str) -> None:
    assert workflow_boundary.cluster_calls(line), line


@pytest.mark.parametrize("line", ACCEPTED_IN_THE_DEFAULT_LANE)
def test_the_cluster_free_rule_accepts_what_reads_files(line: str) -> None:
    """The other half: a rule that refuses everything is not a rule."""
    assert workflow_boundary.cluster_calls(line) == [], line


def test_a_program_name_on_the_next_line_is_not_read_as_a_subcommand() -> None:
    """`\\s` would read the first word of the following line as the subcommand."""
    text = "tar -xzf archive.tar.gz helm\ninstall -m 0755 x /usr/local/bin/x\n"
    assert workflow_boundary.cluster_calls(text) == []


def test_a_comment_is_not_read_as_a_command() -> None:
    text = "# never run helm install here\nrun: helm lint charts/inferops-llm\n"
    assert (
        workflow_boundary.cluster_calls(workflow_boundary.executable_text(text)) == []
    )


# --- The dispatch rules' two derived inputs ----------------------------------


def test_the_guarded_scripts_are_derived_from_the_provider_guard() -> None:
    guarded = workflow_boundary.guarded_scripts()
    assert "kubernetes-certification.sh" in guarded
    assert "helm-lifecycle.sh" in guarded
    assert "lib.sh" not in guarded
    assert not guarded & workflow_boundary.CLUSTER_LIFECYCLE_SCRIPTS


@pytest.mark.parametrize(
    "script", ("smoke.sh", "cluster-verify.sh", "preflight.sh", "verify-clean.sh")
)
def test_the_cluster_smoke_scripts_still_do_not_call_the_provider_guard(
    script: str,
) -> None:
    """A gap, measured and kept visible.

    These four scripts are the ones the cluster-smoke lane is built from, and
    none of them calls `inferops::resolve_target`: `smoke.sh` calls the older
    kind-only identity check and the other three call neither. So a dispatched
    cluster-smoke workflow could not use them under the rule above. When one of
    them is moved onto the guard this fails, and the gate matrix's limitation
    that names the gap has to be corrected in the same change.
    """
    assert script not in workflow_boundary.guarded_scripts(), script


def test_the_provider_choice_is_the_provider_contract() -> None:
    assert workflow_boundary.supported_providers() == ["kind", "docker-desktop"]


# --------------------------------------------------------------------------
# Ownership overlap
# --------------------------------------------------------------------------


def test_the_inventory_gives_each_writing_owner_the_kinds_it_is_known_to_own() -> None:
    owners = overlap.kinds_by_owner(INVENTORY)
    assert owners["terraform"] == {
        "Namespace",
        "PersistentVolumeClaim",
        "ResourceQuota",
    }
    assert {"Deployment", "Service", "ConfigMap", "Job", "NetworkPolicy"} <= owners[
        "helm"
    ]
    assert owners["kubernetes-control-plane"] == {
        "ReplicaSet",
        "Pod",
        "EndpointSlice",
        "PersistentVolume",
    }
    assert not owners["helm"] & owners["terraform"], "the inventory itself overlaps"


@pytest.mark.parametrize(
    ("resource_type", "kind"),
    (
        ("kubernetes_namespace_v1", "Namespace"),
        ("kubernetes_persistent_volume_claim_v1", "PersistentVolumeClaim"),
        ("kubernetes_deployment_v1", "Deployment"),
        ("kubernetes_config_map", "ConfigMap"),
        ("kubernetes_role_binding_v1", "RoleBinding"),
        ("helm_release", None),
        ("aws_s3_bucket", None),
    ),
)
def test_a_terraform_type_maps_to_the_kind_it_creates(
    resource_type: str, kind: str | None
) -> None:
    assert overlap.kind_of_terraform_type(resource_type) == kind


def _overlap(renders: list[Path], terraform: Path) -> list[str]:
    return overlap.problems(
        overlap.rendered_documents(renders),
        overlap.terraform_resource_types(terraform),
        INVENTORY,
    )


def test_the_committed_renders_and_configuration_do_not_overlap() -> None:
    renders = sorted(RENDERED.glob("*.expected.yaml"))
    assert len(renders) == 2
    assert _overlap(renders, TERRAFORM_ROOT) == []


def test_the_committed_configuration_is_read_and_not_its_working_state() -> None:
    assert sorted(overlap.terraform_resource_types(TERRAFORM_ROOT)) == [
        "kubernetes_namespace_v1",
        "kubernetes_persistent_volume_claim_v1",
    ]


OWNERSHIP_REFUSALS = {
    "release-renders-the-namespace.yaml": (
        "gives Namespace to Terraform",
        "Namespace is both rendered by the chart and declared by Terraform",
    ),
    "release-renders-the-model-cache-claim.yaml": (
        "gives PersistentVolumeClaim to Terraform",
        "PersistentVolumeClaim is both rendered",
    ),
    "release-renders-a-resource-quota.yaml": ("gives ResourceQuota to Terraform",),
    "release-renders-a-replica-set.yaml": (
        "gives ReplicaSet to the Kubernetes control plane",
    ),
}


@pytest.mark.parametrize("name", sorted(OWNERSHIP_REFUSALS))
def test_a_render_that_reaches_across_the_boundary_is_refused(name: str) -> None:
    found = _overlap([OWNERSHIP_FIXTURES / "release-renders" / name], TERRAFORM_ROOT)
    assert len(found) == len(OWNERSHIP_REFUSALS[name]), found
    for fragment in OWNERSHIP_REFUSALS[name]:
        assert any(fragment in line for line in found), (fragment, found)


def test_every_render_fixture_has_a_recorded_refusal() -> None:
    on_disk = {
        path.name for path in (OWNERSHIP_FIXTURES / "release-renders").glob("*.yaml")
    }
    assert on_disk == set(OWNERSHIP_REFUSALS)


@pytest.mark.parametrize(
    ("directory", "fragment"),
    (
        ("declares-a-deployment", "gives Deployment to Helm"),
        ("declares-a-helm-release", "not a Kubernetes resource this check can place"),
    ),
)
def test_a_configuration_that_reaches_across_the_boundary_is_refused(
    directory: str, fragment: str
) -> None:
    found = _overlap(
        [RENDERED / "real.expected.yaml"],
        OWNERSHIP_FIXTURES / "terraform-declares" / directory,
    )
    assert any(fragment in line for line in found), found


def test_the_indented_resource_block_in_a_fixture_is_seen() -> None:
    """The Terraform suite's first resource pattern could not see an indented
    block. The Deployment fixture indents its block to keep this one honest."""
    types = overlap.terraform_resource_types(
        OWNERSHIP_FIXTURES / "terraform-declares" / "declares-a-deployment"
    )
    assert "kubernetes_deployment_v1" in types


def test_a_helm_test_hook_pod_is_not_refused_as_a_derived_object() -> None:
    hook = {
        "kind": "Pod",
        "metadata": {"name": "t", "annotations": {"helm.sh/hook": "test"}},
    }
    plain = {"kind": "Pod", "metadata": {"name": "t"}}
    types = ["kubernetes_namespace_v1"]
    assert overlap.problems([hook], types, INVENTORY) == []
    assert overlap.problems([plain], types, INVENTORY)


# --------------------------------------------------------------------------
# The binary-free control groups
# --------------------------------------------------------------------------


def test_the_expected_failure_gate_finds_every_group_it_promises() -> None:
    found = controls()
    assert shortfalls(found) == []
    kinds = {control.controlId.split("/", 1)[0] for control in found}
    assert kinds == set(MINIMUM_CONTROLS)


#: The groups V1-S4-001-PR2 added to the binary-free gate. Their minimums are
#: the committed counts exactly, so a deleted fixture fails here. The four groups
#: that were already there keep the floors their own change chose.
PR2_BINARY_FREE_GROUPS = (
    "workflow-refused",
    "workflow-accepted",
    "ownership-refused",
    "ownership-accepted",
)


def test_the_added_groups_minimums_are_the_counts_committed() -> None:
    """A minimum well below the real count lets fixtures disappear unnoticed."""
    counted: dict[str, int] = {}
    for control in controls():
        kind = control.controlId.split("/", 1)[0]
        counted[kind] = counted.get(kind, 0) + 1
    for group in PR2_BINARY_FREE_GROUPS:
        assert counted[group] == MINIMUM_CONTROLS[group], (group, counted[group])


# --------------------------------------------------------------------------
# The tool controls: the manifest, the counts, and what counts as a pass
# --------------------------------------------------------------------------

TOOL_MANIFEST = infrastructure.manifest()


@pytest.mark.parametrize(
    ("group", "directory", "entries_are"),
    (
        ("values-refused", infrastructure.VALUES_FIXTURES, "files"),
        ("schema-refused", infrastructure.SCHEMA_FIXTURES, "files"),
        ("terraform-format-refused", infrastructure.TERRAFORM_FIXTURES, "dirs"),
    ),
)
def test_the_tool_manifest_names_only_fixtures_that_exist(
    group: str, directory: Path, entries_are: str
) -> None:
    for row in TOOL_MANIFEST[group]:
        target = directory / row["fixture"]
        assert target.is_file() if entries_are == "files" else target.is_dir(), target
        assert row["reason"], row["fixture"]


def test_every_values_fixture_is_in_exactly_one_group() -> None:
    named = [
        row["fixture"]
        for group in ("values-refused", "render-refused-by-policy")
        for row in TOOL_MANIFEST[group]
    ]
    on_disk = sorted(
        path.name for path in infrastructure.VALUES_FIXTURES.glob("*.yaml")
    )
    assert sorted(named) == on_disk


def test_every_schema_fixture_is_named() -> None:
    named = sorted(row["fixture"] for row in TOOL_MANIFEST["schema-refused"])
    on_disk = sorted(
        path.name for path in infrastructure.SCHEMA_FIXTURES.glob("*.yaml")
    )
    assert named == on_disk


def test_every_terraform_fixture_is_in_exactly_one_group() -> None:
    named = [
        row["fixture"]
        for group in (
            "terraform-format-refused",
            "terraform-validate-refused",
            "terraform-lint-refused",
        )
        for row in TOOL_MANIFEST[group]
    ]
    on_disk = sorted(
        p.name for p in infrastructure.TERRAFORM_FIXTURES.iterdir() if p.is_dir()
    )
    assert sorted(named) == on_disk


@pytest.mark.parametrize("family", infrastructure.FAMILIES)
def test_each_tool_family_finds_every_group_it_promises(family: str) -> None:
    found = infrastructure.controls(family)
    assert infrastructure.shortfalls(family, found) == []


def test_the_tool_minimum_counts_are_the_counts_committed() -> None:
    counted: dict[str, int] = {}
    for family in infrastructure.FAMILIES:
        for control in infrastructure.controls(family):
            kind = control.controlId.split("/", 1)[0]
            counted[kind] = counted.get(kind, 0) + 1
    assert counted == infrastructure.MINIMUM_TOOL_CONTROLS, counted


def test_every_negative_tool_control_names_the_reason_it_must_refuse_for() -> None:
    for family in infrastructure.FAMILIES:
        for control in infrastructure.controls(family):
            if control.fails_at is not None:
                assert control.reason, control.controlId


def test_the_lint_fixture_that_proves_the_configuration_was_read_needs_the_all_preset() -> (
    None
):
    """`terraform_documented_variables` is not in tflint's default preset."""
    config = infrastructure.TFLINT_CONFIG.read_text(encoding="utf-8")
    assert re.search(r'preset\s*=\s*"all"', config), config
    reasons = {
        row["fixture"]: row["reason"] for row in TOOL_MANIFEST["terraform-lint-refused"]
    }
    assert reasons["lint-undocumented-variable"] == "terraform_documented_variables"


def test_no_published_command_carries_a_host_path() -> None:
    for family in infrastructure.FAMILIES:
        for control in infrastructure.controls(family):
            command = control.published_command
            assert str(REPO_ROOT) not in command, command
            assert REPO_ROOT.as_posix() not in command, command


def _control(
    fails_at: int | None, reason: str | None = "expected text"
) -> infrastructure.ToolControl:
    stage = infrastructure.Stage(("helm", "template"))
    return infrastructure.ToolControl(
        controlId="values-refused/example.yaml",
        stages=(stage, stage),
        fails_at=fails_at,
        reason=reason,
    )


@pytest.mark.parametrize(
    ("fails_at", "exits", "output", "passed"),
    (
        (1, (0, 1), "... expected text ...", True),
        (1, (0, 1), "refused for another reason", False),
        (1, (1,), "expected text", False),
        (1, (0, 0), "expected text", False),
        (0, (127,), "expected text", True),
        (None, (0, 0), "", True),
        (None, (0,), "", False),
        (None, (0, 2), "", False),
    ),
)
def test_a_tool_control_passes_only_for_the_right_stage_and_the_right_reason(
    fails_at: int | None, exits: tuple[int, ...], output: str, passed: bool
) -> None:
    result = infrastructure.ToolResult(
        control=_control(fails_at), exits=exits, output=output
    )
    assert result.passed is passed


def test_a_missing_tool_stops_the_family_before_any_control_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    for family in infrastructure.FAMILIES:
        resolved, problems = infrastructure.tool_problems(family)
        assert resolved == {}
        assert len(problems) == len(infrastructure.TOOLS_BY_FAMILY[family])
        assert all("not on PATH" in problem for problem in problems)


def test_a_tool_at_another_version_stops_the_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(infrastructure, "_probe", lambda _tool, _path: "0.0.0")
    resolved, problems = infrastructure.tool_problems("terraform")
    assert resolved == {}
    assert len(problems) == 2
    assert all("this gate is pinned to" in problem for problem in problems)


# --------------------------------------------------------------------------
# The no-skip runner reads pytest's report, not its exit status
# --------------------------------------------------------------------------

JUNIT_WITH_A_SKIP = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="0" failures="0" skipped="1" tests="3">
<testcase classname="tests.architecture.test_helm_chart" name="test_a"/>
<testcase classname="tests.architecture.test_helm_chart" name="test_b"/>
<testcase classname="tests.architecture.test_helm_chart" name="test_drift">
<skipped message="helm is not on PATH"/></testcase>
</testsuite></testsuites>
"""


def test_a_skip_fails_the_no_skip_gate_even_when_pytest_exits_zero(
    tmp_path: Path,
) -> None:
    junit = tmp_path / "report.xml"
    junit.write_text(JUNIT_WITH_A_SKIP, encoding="utf-8")
    report = suites._report(junit, exit_status=0)
    assert report.tests == 3
    assert len(report.skipped) == 1
    assert "helm is not on PATH" in report.skipped[0]
    assert report.passed is False


def test_an_empty_run_fails_the_no_skip_gate(tmp_path: Path) -> None:
    junit = tmp_path / "report.xml"
    junit.write_text(
        '<testsuites><testsuite name="pytest" errors="0" failures="0" '
        'skipped="0" tests="0"></testsuite></testsuites>',
        encoding="utf-8",
    )
    assert suites._report(junit, exit_status=0).passed is False


def test_the_no_skip_gate_points_only_at_modules_that_exist() -> None:
    for module in suites.TOOL_BACKED_SUITES.values():
        assert (REPO_ROOT / module).is_file(), module


# --------------------------------------------------------------------------
# The fixtures are fixtures
# --------------------------------------------------------------------------


def test_no_workflow_fixture_lives_where_github_would_run_it() -> None:
    for path in [*INVALID_WORKFLOWS, *VALID_WORKFLOWS]:
        assert ".github" not in path.parts, path


@pytest.mark.parametrize(
    "path", [*INVALID_WORKFLOWS, *VALID_WORKFLOWS], ids=lambda p: p.name
)
def test_every_workflow_fixture_parses(path: Path) -> None:
    assert isinstance(yaml.safe_load(path.read_text(encoding="utf-8")), dict)
