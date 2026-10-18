"""The freeze records of the reliability experiments, held to their sources.

V2-S6-003-PR1 registered one freeze record for each of V2-E02A, V2-E02B, V2-E02C,
V2-E04, and V2-E05, before any run. V2-S6-007-PR1 registered revision 2 of the
records of V2-E02A, V2-E02B, V2-E02C, and V2-E05, under rule set 2 and its one
clock policy. Revision 1 of each stays unchanged, and V2-E04 stays at revision 1.
``tools.experiment_freeze`` checks that each record answers every freeze field.
``tools.experiment_preregistration`` reads the answers: the qualification, the
bound record, and the baseline comparison that each record names, the clock
policy of a record of rule set 2, and the records against each other.

The first part holds the committed records, with their identities written out so
that a change to one is visible in review. The second and the third part plant
each defect that the check refuses in a copy of the files it reads, and assert
the exact findings. The fourth part does the same for the clock rules. No test
runs an experiment or contacts a cluster.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tools.experiment_freeze.core import (
    FROZEN_RECORDS,
    changed_inputs,
    content_digest,
    material_files,
)
from tools.experiment_freeze.core import (
    check_repository as check_freezes,
)
from tools.experiment_preregistration import (
    BASELINE,
    EXPERIMENTS,
    PERMITTED_TOPOLOGY,
    RULES,
    TARGET,
    check_records,
    check_repository,
    core,
    latest_records,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "docs" / "proof" / "experiments" / "README.md"

#: The latest revision of each experiment: revision 2, except for V2-E04.
E02A = "docs/proof/experiments/v2-e02a/freeze-r2.v1alpha1.json"
E02B = "docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json"
E02C = "docs/proof/experiments/v2-e02c/freeze-r2.v1alpha1.json"
E04 = "docs/proof/experiments/v2-e04/freeze-r1.v1alpha1.json"
E05 = "docs/proof/experiments/v2-e05/freeze-r2.v1alpha1.json"
#: Revision 1 of each experiment. Revision 2 supersedes it, except for V2-E04.
E02A_R1 = "docs/proof/experiments/v2-e02a/freeze-r1.v1alpha1.json"
E02B_R1 = "docs/proof/experiments/v2-e02b/freeze-r1.v1alpha1.json"
E02C_R1 = "docs/proof/experiments/v2-e02c/freeze-r1.v1alpha1.json"
E05_R1 = "docs/proof/experiments/v2-e05/freeze-r1.v1alpha1.json"
REVISION_ONE = {
    "V2-E02A": E02A_R1,
    "V2-E02B": E02B_R1,
    "V2-E02C": E02C_R1,
    "V2-E04": E04,
    "V2-E05": E05_R1,
}
#: The four records of rule set 2.
REVISION_TWO = {"V2-E02A": E02A, "V2-E02B": E02B, "V2-E02C": E02C, "V2-E05": E05}
#: Every committed record of the five experiments.
ALL_RECORDS = sorted(set(REVISION_ONE.values()) | set(REVISION_TWO.values()))
RECORDS = {
    "V2-E02A": E02A,
    "V2-E02B": E02B,
    "V2-E02C": E02C,
    "V2-E04": E04,
    "V2-E05": E05,
}

QUALIFICATION = "docs/proof/experiments/v2-q1/runs/q1-2/record.v1alpha1.json"
QUALIFICATION_1 = "docs/proof/experiments/v2-q1/runs/q1-1/record.v1alpha1.json"
BOUNDS = "docs/proof/experiments/v2-q4/bounds-r1.v1alpha1.json"
COMPARISON = (
    "tests/domain/fixtures/experiment-profiles/"
    "single-runtime-baseline.comparison.v1alpha1.json"
)
REGISTRY = "docs/proof/experiments/registry.v1alpha1.json"

#: The identities the five records name, written out so that a change is visible.
ENVIRONMENT_SHA256 = (
    "sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c"
)
QUALIFICATION_SHA256 = (
    "1141cbd1c0acd7eff839395a89eba3fe116a060dafb3941128bf23c440ec1b3d"
)
BOUNDS_SHA256 = "542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116"
TARGET_RELEASE = "b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db"
BASELINE_RELEASE = "ecc4b9cf2d8c2e137e743dcf9e99dcdad12ec297821bc0115694dc703f88a465"
BOUND_VALUES = {
    "runtime_start_bound_ms": 11_000,
    "caller_gap_reference_ms": 10_113,
    "reversal_recovery_bound_ms": 52_000,
    "caller_total_unavailability_bound_ms": 20_226,
}


def load(path: str, root: Path = REPO_ROOT) -> dict[str, Any]:
    document = json.loads((root / path).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def value(document: dict[str, Any], field: str) -> Any:
    (entry,) = document["fields"][field]
    assert entry["status"] == "value"
    return entry["value"]


# --------------------------------------------------------------------------
# 1. The committed records
# --------------------------------------------------------------------------


def test_the_committed_records_hold_every_rule() -> None:
    assert check_repository() == []


def test_the_command_passes_over_the_committed_records() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.experiment_preregistration", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == (
        "PASSED: 5 experiment record(s) and 4 superseded revision(s), every rule held"
    )


def test_each_revision_one_record_is_registered_by_v2_s6_003_and_unchanged() -> None:
    for experiment, path in REVISION_ONE.items():
        document = load(path)
        assert document["metadata"]["experiment"] == experiment
        assert document["metadata"]["revision"] == 1
        assert document["metadata"]["supersedes"] is None
        assert document["metadata"]["registeredBy"] == "V2-S6-003-PR1"
        assert "preregistrationRules" not in document["metadata"]
        assert FROZEN_RECORDS[path] == content_digest((REPO_ROOT / path).read_bytes())
    assert check_freezes() == []


def test_the_latest_records_are_revision_two_and_e04_revision_one() -> None:
    assert {k: path for k, (path, _) in latest_records().items()} == RECORDS
    for experiment, path in REVISION_TWO.items():
        metadata = load(path)["metadata"]
        assert metadata["experiment"] == experiment
        assert metadata["revision"] == 2
        assert metadata["registeredBy"] == "V2-S6-007-PR1"
        assert metadata["preregistrationRules"] == 2
        assert metadata["supersedes"] == {
            "path": REVISION_ONE[experiment],
            "contentSha256": FROZEN_RECORDS[REVISION_ONE[experiment]],
        }
        assert FROZEN_RECORDS[path] == content_digest((REPO_ROOT / path).read_bytes())


def test_no_field_is_pending_or_not_applicable() -> None:
    """No placeholder: every freeze field of every record is answered with a value."""
    for path in ALL_RECORDS:
        for field, entries in load(path)["fields"].items():
            assert [e["status"] for e in entries] == ["value"], (path, field)


def test_each_record_names_the_q1_2_lineage_and_the_bound_record() -> None:
    for path in ALL_RECORDS:
        document = load(path)
        environment = value(document, "environmentIdentity")
        assert environment["environmentSha256"] == ENVIRONMENT_SHA256
        assert environment["qualification"] == {
            "qualificationId": "q1-2",
            "path": QUALIFICATION,
            "contentSha256": QUALIFICATION_SHA256,
            "result": "QUALIFIED",
        }
        assert environment["qualifiedRelease"] == TARGET_RELEASE
        bounds = value(document, "derivedNumericBounds")
        assert bounds["boundRecord"] == {"path": BOUNDS, "contentSha256": BOUNDS_SHA256}
        assert {b["name"]: b["valueMs"] for b in bounds["bounds"]} == BOUND_VALUES
        assert bounds["sourceRelease"] == TARGET_RELEASE
        assert "not bounds of another release" in bounds["role"]
    assert content_digest((REPO_ROOT / QUALIFICATION).read_bytes()) == (
        QUALIFICATION_SHA256
    )
    assert content_digest((REPO_ROOT / BOUNDS).read_bytes()) == BOUNDS_SHA256


def test_the_q3_1_refusal_is_kept_and_named_as_history() -> None:
    record = load("docs/proof/experiments/v2-q3/runs/q3-1/record.v1alpha1.json")
    assert record["result"] == "REFUSED"
    for path in ALL_RECORDS:
        assert any(
            "q3-1 REFUSED" in line for line in load(path)["definition"]["history"]
        )


def test_each_record_states_its_repetitions_and_level() -> None:
    counts = {"V2-E02A": 3, "V2-E02B": 3, "V2-E02C": 3, "V2-E04": 2, "V2-E05": 2}
    for experiment, path in RECORDS.items():
        document = load(path)
        assert value(document, "repetitionCount").startswith(
            f"{counts[experiment]} counted result-bearing runs"
        )
        assert value(document, "intendedEvidenceLevel") == "C2"
        assert document["exclusionReasons"]["experimentId"] == experiment


def test_the_baseline_and_the_target_differ_in_the_runtime_topology_alone() -> None:
    baseline = value(load(E02A), "topology")
    target = value(load(E02B), "topology")
    differing = {k for k in baseline if baseline[k] != target.get(k)}
    assert differing == PERMITTED_TOPOLOGY
    assert (baseline["apiReplicas"], baseline["runtimeReplicas"]) == (2, 1)
    assert (target["apiReplicas"], target["runtimeReplicas"]) == (2, 2)
    assert baseline["release"]["releaseId"] == BASELINE_RELEASE
    assert target["release"]["releaseId"] == TARGET_RELEASE
    assert baseline["delivery"] == target["delivery"]
    assert baseline["desiredStatePath"] == target["desiredStatePath"]


def test_the_other_three_run_the_target_topology() -> None:
    target = value(load(E02B), "topology")
    for path in (E02C, E04, E05):
        assert value(load(path), "topology") == target


def test_the_bounds_that_criteria_use_are_stated_with_their_values() -> None:
    used = {
        path: sorted(
            c["bound"] for c in value(load(path), "acceptanceCriteria") if "bound" in c
        )
        for path in RECORDS.values()
    }
    assert used == {
        E02A: [],
        E02B: [],
        E02C: ["caller_total_unavailability_bound_ms"],
        E04: ["caller_total_unavailability_bound_ms", "reversal_recovery_bound_ms"],
        E05: ["reconciliation_bound_ms"],
    }


def test_the_reconciliation_bound_of_e05_is_210000_ms_and_not_a_guarantee() -> None:
    bound = value(load(E05), "derivedNumericBounds")["reconciliationBound"]
    assert bound["valueMs"] == 210_000
    assert bound["components"] == {
        "reconciliationTimeoutMs": 120_000,
        "reconciliationJitterMaximumMs": 60_000,
        "allowanceMs": 30_000,
    }
    assert bound["derivedFromQualification"] is False
    assert "does not guarantee" in bound["notAGuarantee"]
    assert "2 to 4 s" in bound["priorObservation"]
    for path in (E02A, E02B, E02C, E04):
        assert "reconciliationBound" not in value(load(path), "derivedNumericBounds")


def test_no_run_and_no_driver_exists_for_any_experiment() -> None:
    """The records come before any run. No driver is committed: the change that adds
    one registers a later revision, and its file is listed as added until then."""
    for experiment in EXPERIMENTS:
        directory = REPO_ROOT / experiment.directory
        assert sorted(p.name for p in directory.iterdir()) == (
            ["freeze-r1.v1alpha1.json"]
            if experiment.experiment_id == "V2-E04"
            else ["freeze-r1.v1alpha1.json", "freeze-r2.v1alpha1.json"]
        )


def test_each_record_pins_exactly_its_material_scope_at_registration() -> None:
    """A tripwire: a file added to or removed from a scope moves this set. Such a
    change owes a later revision of the record before any run, and the
    ``--changes`` command of the freeze tool lists the file until then. Revision 1
    pins the same files as revision 2, with other digests of this check."""
    for path in ALL_RECORDS:
        document = load(path)
        pinned = {item["path"] for item in document["pinnedInputs"]}
        assert material_files(document["materialScope"], REPO_ROOT) == pinned, path
        assert "tools/experiment_preregistration/core.py" in pinned
        assert REGISTRY not in pinned
        assert path not in pinned


def test_every_rule_is_published() -> None:
    assert len(RULES) == 18
    text = README.read_text(encoding="utf-8")
    for rule, statement in RULES.items():
        assert f"| `{rule}` | {statement} |" in text, rule


# --------------------------------------------------------------------------
# 2. Each defect the check refuses
# --------------------------------------------------------------------------


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A root that holds every file the check reads, as committed."""
    for relative in (REGISTRY, QUALIFICATION, QUALIFICATION_1, BOUNDS, COMPARISON):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, target)
    for path in ALL_RECORDS:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / path, target)
    return tmp_path


def edit(root: Path, path: str, change: Callable[[dict[str, Any]], None]) -> None:
    document = load(path, root)
    change(document)
    (root / path).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def found(root: Path) -> list[tuple[str, str, str, str]]:
    return [(f.rule_id, f.record, f.location, f.detail) for f in check_repository(root)]


def topology_of(document: dict[str, Any]) -> dict[str, Any]:
    result = value(document, "topology")
    assert isinstance(result, dict)
    return result


def test_the_copy_holds_every_rule(root: Path) -> None:
    assert found(root) == []


def test_an_unpermitted_baseline_difference_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        topology_of(document)["chart"]["version"] = "0.7.0"

    edit(root, E02A, change)
    assert found(root) == [
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.chart",
            "it is not a permitted difference",
        )
    ]


def test_a_permitted_difference_alone_is_not_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        topology_of(document)["statement"] = "Another statement of the baseline."

    edit(root, E02A, change)
    assert found(root) == []


def test_a_baseline_release_other_than_the_comparison_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        topology_of(document)["release"]["releaseId"] = "0" * 64

    edit(root, E02A, change)
    assert found(root) == [
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.release (baseline)",
            "releaseId is not the one of the comparison",
        )
    ]


def test_a_desired_state_file_that_is_not_pinned_with_its_digest_is_refused(
    root: Path,
) -> None:
    def change(document: dict[str, Any]) -> None:
        files = topology_of(document)["release"]["desiredStateFiles"]
        files["rendered-workload-release.yaml"] = "1" * 64

    edit(root, E02A, change)
    assert found(root) == [
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.release (baseline)",
            "rendered-workload-release.yaml is not pinned with the stated digest",
        )
    ]


def test_a_comparison_that_is_not_comparable_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["result"] = "REFUSED"

    edit(root, COMPARISON, change)
    assert found(root) == [
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.comparison",
            "the comparison has another digest",
        ),
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.comparison",
            "the comparison is not COMPARABLE",
        ),
    ]


def test_a_target_topology_that_differs_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        topology_of(document)["runtimeReplicas"] = 3

    edit(root, E05, change)
    assert found(root) == [
        (
            "prereg-target-topology-differs",
            E05,
            "fields.topology",
            f"it differs from {TARGET}",
        )
    ]


def test_a_missing_executable_pin_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["pinnedInputs"] = [
            item
            for item in document["pinnedInputs"]
            if item["path"] != "scripts/environment/reliability-runner.sh"
        ]

    edit(root, E02C, change)
    assert found(root) == [
        (
            "prereg-executable-unpinned",
            E02C,
            "definition.executables",
            "scripts/environment/reliability-runner.sh is not pinned",
        )
    ]


def test_a_scope_without_the_procedure_directory_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["materialScope"]["paths"].remove(
            "docs/proof/experiments/v2-e04/procedure/*"
        )

    edit(root, E04, change)
    assert found(root) == [
        (
            "prereg-executable-unpinned",
            E04,
            "materialScope.paths",
            "the scope does not name docs/proof/experiments/v2-e04/procedure/*",
        )
    ]


def test_a_stale_bound_value_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        bounds = value(document, "derivedNumericBounds")["bounds"]
        bounds[3]["valueMs"] = 20_000

    edit(root, E02C, change)
    assert found(root) == [
        (
            "prereg-bounds-stale",
            E02C,
            "fields.derivedNumericBounds",
            "the bounds differ from those of the bound record",
        ),
        (
            "prereg-criterion-bound-unknown",
            E02C,
            "fields.acceptanceCriteria[0].value[9]",
            "its statement does not state 20,000 ms",
        ),
        (
            "prereg-shared-differs",
            E02C,
            "fields.derivedNumericBounds",
            f"it differs from {TARGET}",
        ),
    ]


def test_a_later_bound_record_makes_every_record_stale(root: Path) -> None:
    shutil.copyfile(
        root / BOUNDS, root / "docs/proof/experiments/v2-q4/bounds-r2.v1alpha1.json"
    )
    assert found(root) == [
        (
            "prereg-bounds-stale",
            path,
            "fields.derivedNumericBounds",
            "the bound record is not the latest committed",
        )
        for path in sorted(RECORDS.values())
    ]


def test_an_edited_bound_record_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["bounds"][1]["valueMs"] = 9_000

    edit(root, BOUNDS, change)
    findings = found(root)
    assert {f[0] for f in findings} == {"prereg-bounds-stale"}
    # A superseded revision is held to the digest of the bound record it names.
    assert sorted({f[1] for f in findings}) == ALL_RECORDS
    assert {f[3] for f in findings} == {
        "the bound record has another digest",
        "the bounds differ from those of the bound record",
    }


def test_an_incompatible_environment_identity_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        value(document, "environmentIdentity")["environmentSha256"] = (
            "sha256:" + "2" * 64
        )

    edit(root, E04, change)
    assert found(root) == [
        (
            "prereg-qualification-incompatible",
            E04,
            "fields.environmentIdentity",
            "environmentSha256 differs from the qualification",
        ),
        (
            "prereg-bounds-incompatible",
            E04,
            "fields.derivedNumericBounds",
            "environmentSha256 differs",
        ),
        (
            "prereg-shared-differs",
            E04,
            "fields.environmentIdentity",
            f"it differs from {TARGET}",
        ),
    ]


def test_a_qualification_of_another_lineage_is_refused(root: Path) -> None:
    """q1-1 qualified the exact identity, which a boot changed: it is not the lineage."""

    def change(document: dict[str, Any]) -> None:
        qualification = value(document, "environmentIdentity")["qualification"]
        qualification["path"] = QUALIFICATION_1
        qualification["contentSha256"] = content_digest(
            (root / QUALIFICATION_1).read_bytes()
        )

    edit(root, E02B, change)
    findings = found(root)
    assert (
        "prereg-qualification-incompatible",
        E02B,
        "fields.environmentIdentity",
        "environmentSha256 differs from the qualification",
    ) in findings
    assert (
        "prereg-bounds-incompatible",
        E02B,
        "fields.derivedNumericBounds",
        "the qualification differs",
    ) in findings
    # The scope of the record names q1-2, so it does not name the other one either.
    assert (
        "prereg-executable-unpinned",
        E02B,
        "materialScope.paths",
        f"the scope does not name {QUALIFICATION_1}",
    ) in findings
    assert {f[0] for f in findings} == {
        "prereg-qualification-incompatible",
        "prereg-bounds-incompatible",
        "prereg-executable-unpinned",
        "prereg-shared-differs",
    }


def test_a_qualification_that_is_not_qualified_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["result"] = "REFUSED"

    edit(root, QUALIFICATION, change)
    findings = found(root)
    for path in RECORDS.values():
        assert (
            "prereg-qualification-incompatible",
            path,
            "fields.environmentIdentity",
            "result differs from the qualification",
        ) in findings
        assert (
            "prereg-qualification-incompatible",
            path,
            "fields.environmentIdentity",
            "the qualification has another digest",
        ) in findings


def test_a_reconciliation_bound_that_is_not_the_registered_sum_is_refused(
    root: Path,
) -> None:
    def change(document: dict[str, Any]) -> None:
        value(document, "derivedNumericBounds")["reconciliationBound"]["valueMs"] = (
            200_000
        )

    edit(root, E05, change)
    assert found(root) == [
        (
            "prereg-criterion-bound-unknown",
            E05,
            "fields.acceptanceCriteria[0].value[8]",
            "its statement does not state 200,000 ms",
        ),
        (
            "prereg-reconciliation-bound-differs",
            E05,
            "fields.derivedNumericBounds.reconciliationBound",
            "the bound is not the sum of its registered components",
        ),
    ]


def test_a_shared_definition_that_differs_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["definition"]["callerRun"]["durationSeconds"] = 1200

    edit(root, E02B, change)
    assert found(root) == [
        (
            "prereg-shared-differs",
            E02A,
            "definition.callerRun",
            f"it differs from {TARGET}",
        )
    ]


def test_a_validity_criterion_that_differs_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        value(document, "acceptanceCriteria")[1]["statement"] += " Another clause."

    edit(root, E02A, change)
    assert found(root) == [
        (
            "prereg-shared-differs",
            E02A,
            "fields.acceptanceCriteria (validity)",
            f"it differs from {TARGET}",
        )
    ]


def test_exclusion_reasons_of_another_experiment_are_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["exclusionReasons"]["experimentId"] = "V2-E02B"

    edit(root, E02C, change)
    assert found(root) == [
        (
            "prereg-exclusion-reasons-unsupported",
            E02C,
            "exclusionReasons",
            "the reasons name another experiment",
        )
    ]


def test_a_missing_record_is_refused(root: Path) -> None:
    shutil.rmtree(root / "docs/proof/experiments/v2-e05")
    assert found(root) == [
        (
            "prereg-record-missing",
            "docs/proof/experiments/v2-e05",
            "$",
            "no freeze record is committed",
        )
    ]


def test_a_record_without_its_release_shape_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        del topology_of(document)["release"]["releaseId"]

    edit(root, E02C, change)
    assert found(root) == [
        (
            "prereg-record-shape",
            E02C,
            "$",
            "topology states no release in the form read here",
        )
    ]


def test_the_command_exits_1_on_a_planted_defect(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        topology_of(document)["runtimeReplicas"] = 3

    edit(root, E04, change)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.experiment_preregistration",
            "--check",
            "--root",
            str(root),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "REFUSED  " + E04 + "  prereg-target-topology-differs" in result.stdout
    assert result.stdout.strip().endswith("FAILED: 1 finding(s) across 5 experiment(s)")


def test_baseline_and_target_are_the_two_sides() -> None:
    assert (BASELINE, TARGET) == ("V2-E02A", "V2-E02B")


# --------------------------------------------------------------------------
# 3. Defects that the independent review of the first commit planted
# --------------------------------------------------------------------------

ENV = "fields.environmentIdentity"
BOUND = "fields.derivedNumericBounds"


def shared(path: str, location: str) -> tuple[str, str, str, str]:
    return ("prereg-shared-differs", path, location, f"it differs from {TARGET}")


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        pytest.param(
            lambda d: d.__setitem__("fields", []),
            "the record states no fields object and no metadata object",
            id="fields-a-list",
        ),
        pytest.param(
            lambda d: d["definition"].__setitem__("executables", []),
            "definition lists no executables",
            id="no-executables",
        ),
        pytest.param(
            lambda d: d["definition"].__setitem__("executables", [["tools"]]),
            "definition lists no executables",
            id="executable-not-a-path",
        ),
        pytest.param(
            lambda d: value(d, "acceptanceCriteria")[9].__setitem__("bound", ["x"]),
            "acceptanceCriteria is not a list of criteria",
            id="bound-a-list",
        ),
        pytest.param(
            lambda d: value(d, "environmentIdentity").__setitem__("nodeCount", None),
            "environmentIdentity states no environment in the form read here",
            id="node-count-null",
        ),
        pytest.param(
            lambda d: value(d, "derivedNumericBounds")["bounds"].pop(),
            "derivedNumericBounds names no bound record and no four bounds",
            id="three-bounds",
        ),
        pytest.param(
            lambda d: d.__setitem__("exclusionReasons", "none"),
            "the record registers no exclusion reasons",
            id="reasons-a-string",
        ),
        pytest.param(
            lambda d: topology_of(d).__setitem__("runtimeDisruptionBudget", "none"),
            "topology states no replica counts and disruption budgets in the form "
            "read here",
            id="budget-a-string",
        ),
    ],
)
def test_a_malformed_record_is_a_finding_and_not_an_error(
    root: Path, change: Callable[[dict[str, Any]], None], problem: str
) -> None:
    edit(root, E02C, change)
    assert found(root) == [("prereg-record-shape", E02C, "$", problem)]


def test_a_record_of_another_experiment_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["metadata"]["experiment"] = "V2-E99"

    edit(root, E04, change)
    assert found(root) == [
        (
            "prereg-record-missing",
            E04,
            "metadata.experiment",
            "the record does not name V2-E04",
        )
    ]


def test_an_executable_without_its_entry_module_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["materialScope"]["entryModules"].remove(
            "tools.experiment_events.__main__"
        )

    edit(root, E02C, change)
    assert found(root) == [
        (
            "prereg-executable-unpinned",
            E02C,
            "materialScope.entryModules",
            "the scope names no entry module for tools/experiment_events/__main__.py",
        )
    ]


def test_a_missing_pin_of_the_baseline_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["pinnedInputs"] = [
            item
            for item in document["pinnedInputs"]
            if item["path"] != "tools/baseline_profile/__main__.py"
        ]

    edit(root, E02A, change)
    assert found(root) == [
        (
            "prereg-executable-unpinned",
            E02A,
            "definition.executables",
            "tools/baseline_profile/__main__.py is not pinned",
        )
    ]


def test_a_baseline_budget_that_the_chart_does_not_render_is_refused(
    root: Path,
) -> None:
    def change(document: dict[str, Any]) -> None:
        topology_of(document)["runtimeDisruptionBudget"] = {
            "rendered": True,
            "minAvailable": 1,
            "statement": "A budget.",
        }

    edit(root, E02A, change)
    assert found(root) == [
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.runtimeDisruptionBudget",
            "it is not the budget that the chart renders for the replica count",
        )
    ]


def test_a_baseline_replica_count_other_than_the_comparison_is_refused(
    root: Path,
) -> None:
    def change(document: dict[str, Any]) -> None:
        topology_of(document)["runtimeReplicas"] = 3

    edit(root, E02A, change)
    assert found(root) == [
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.release (baseline)",
            "runtimeReplicas is not the one of the comparison",
        ),
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.runtimeDisruptionBudget",
            "it is not the budget that the chart renders for the replica count",
        ),
    ]


def test_a_target_release_other_than_the_comparison_is_refused_on_the_target(
    root: Path,
) -> None:
    def change(document: dict[str, Any]) -> None:
        topology_of(document)["release"]["workloadVersion"] = "0.9.0"

    edit(root, E02B, change)
    assert found(root) == [
        (
            "prereg-baseline-difference-unpermitted",
            E02B,
            "fields.topology.release (target)",
            "workloadVersion is not the one of the comparison",
        ),
        *[
            (
                "prereg-target-topology-differs",
                path,
                "fields.topology",
                f"it differs from {TARGET}",
            )
            for path in sorted((E02C, E04, E05))
        ],
    ]


def test_permitted_differences_that_drift_from_the_comparison_are_refused(
    root: Path,
) -> None:
    def change(document: dict[str, Any]) -> None:
        topology_of(document)["comparison"]["permittedDifferences"]["values"] = {}

    edit(root, E02A, change)
    assert found(root) == [
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.comparison",
            "it is not a permitted difference",
        ),
        (
            "prereg-baseline-difference-unpermitted",
            E02A,
            "fields.topology.comparison",
            "the permitted differences are not those of the comparison",
        ),
    ]


@pytest.mark.parametrize(
    ("member", "changed", "bounds"),
    [
        pytest.param("provider", "kind", ["provider differs"], id="provider"),
        pytest.param("identityRevision", 1, [], id="identity-revision"),
        pytest.param("kubernetesServerVersion", "v1.35.0", [], id="server-version"),
        pytest.param("nodeCount", 2, [], id="node-count"),
    ],
)
def test_each_identity_member_is_compared_with_the_qualification(
    root: Path, member: str, changed: object, bounds: list[str]
) -> None:
    def change(document: dict[str, Any]) -> None:
        value(document, "environmentIdentity")[member] = changed

    edit(root, E04, change)
    assert found(root) == [
        (
            "prereg-qualification-incompatible",
            E04,
            ENV,
            f"{member} differs from the qualification",
        ),
        *[("prereg-bounds-incompatible", E04, BOUND, detail) for detail in bounds],
        shared(E04, ENV),
    ]


def test_a_qualification_freeze_record_that_is_not_registered_is_refused(
    root: Path,
) -> None:
    def change(document: dict[str, Any]) -> None:
        freeze = value(document, "environmentIdentity")["qualificationFreezeRecord"]
        freeze["contentSha256"] = "3" * 64

    edit(root, E02C, change)
    assert found(root) == [
        (
            "prereg-qualification-incompatible",
            E02C,
            ENV,
            "the freeze record differs from the qualification",
        ),
        (
            "prereg-qualification-incompatible",
            E02C,
            ENV,
            "the qualification freeze record is not registered",
        ),
        shared(E02C, ENV),
    ]


def test_a_qualified_release_other_than_the_target_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        value(document, "environmentIdentity")["qualifiedRelease"] = "4" * 64

    edit(root, E02C, change)
    assert found(root) == [
        (
            "prereg-qualification-incompatible",
            E02C,
            ENV,
            "the qualified release differs from the qualification",
        ),
        (
            "prereg-qualification-incompatible",
            E02C,
            ENV,
            "the qualified release is not the target release",
        ),
        ("prereg-bounds-incompatible", E02C, BOUND, "the release differs"),
        ("prereg-bounds-incompatible", E02C, BOUND, "the source release differs"),
        shared(E02C, ENV),
    ]


def test_a_stated_result_other_than_qualified_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        value(document, "environmentIdentity")["qualification"]["result"] = "REFUSED"

    edit(root, E04, change)
    assert found(root) == [
        (
            "prereg-qualification-incompatible",
            E04,
            ENV,
            "the stated result differs from the qualification",
        ),
        shared(E04, ENV),
    ]


def test_a_qualification_that_is_not_committed_is_refused(root: Path) -> None:
    absent = "docs/proof/experiments/v2-q1/runs/q1-9/record.v1alpha1.json"

    def change(document: dict[str, Any]) -> None:
        value(document, "environmentIdentity")["qualification"]["path"] = absent

    edit(root, E05, change)
    assert found(root) == [
        (
            "prereg-qualification-incompatible",
            E05,
            ENV,
            "the qualification is not committed",
        ),
        ("prereg-bounds-incompatible", E05, BOUND, "the qualification differs"),
        shared(E05, ENV),
        (
            "prereg-executable-unpinned",
            E05,
            "materialScope.paths",
            f"the scope does not name {absent}",
        ),
    ]


def test_a_qualification_path_outside_the_root_is_not_read(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        value(document, "environmentIdentity")["qualification"]["path"] = (
            "../" + QUALIFICATION
        )

    edit(root, E05, change)
    assert (
        "prereg-qualification-incompatible",
        E05,
        ENV,
        "the qualification is not committed",
    ) in found(root)


def test_the_check_does_not_change_when_every_qualification_is_refused(
    root: Path,
) -> None:
    """The exact findings when the qualification record says REFUSED. A superseded
    revision is held to the qualification that it names, as the latest one is."""

    def change(document: dict[str, Any]) -> None:
        document["result"] = "REFUSED"

    edit(root, QUALIFICATION, change)
    assert found(root) == [
        finding
        for path in ALL_RECORDS
        for finding in (
            (
                "prereg-qualification-incompatible",
                path,
                ENV,
                "the qualification has another digest",
            ),
            (
                "prereg-qualification-incompatible",
                path,
                ENV,
                "result differs from the qualification",
            ),
        )
    ]


def test_a_reconciliation_bound_outside_v2_e05_is_refused(root: Path) -> None:
    reconciliation = value(load(E05, root), "derivedNumericBounds")[
        "reconciliationBound"
    ]

    def change(document: dict[str, Any]) -> None:
        value(document, "derivedNumericBounds")["reconciliationBound"] = reconciliation

    edit(root, E04, change)
    assert found(root) == [
        (
            "prereg-reconciliation-bound-differs",
            E04,
            "fields.derivedNumericBounds.reconciliationBound",
            "only V2-E05 states a reconciliation bound",
        )
    ]


def test_v2_e05_without_its_reconciliation_bound_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        del value(document, "derivedNumericBounds")["reconciliationBound"]

    edit(root, E05, change)
    assert found(root) == [
        (
            "prereg-criterion-bound-unknown",
            E05,
            "fields.acceptanceCriteria[0].value[8]",
            "it names no bound of the record",
        ),
        (
            "prereg-reconciliation-bound-differs",
            E05,
            "fields.derivedNumericBounds.reconciliationBound",
            "V2-E05 states no reconciliation bound",
        ),
    ]


def test_a_criterion_that_names_an_unknown_bound_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        value(document, "acceptanceCriteria")[9]["bound"] = "no_such_bound_ms"

    edit(root, E02C, change)
    assert found(root) == [
        (
            "prereg-criterion-bound-unknown",
            E02C,
            "fields.acceptanceCriteria[0].value[9]",
            "it names no bound of the record",
        ),
        (
            "prereg-clock-inventory",
            E02C,
            "fields.acceptanceCriteria[0].value[9]",
            "it names a bound and declares no clocks of its interval",
        ),
    ]


def test_a_bound_figure_inside_a_larger_one_is_not_its_statement() -> None:
    assert core._states("at most 20,000 ms.", 20_000)
    assert not core._states("at most 120,000 ms.", 20_000)
    assert not core._states("at most 1,20,000 ms.", 20_000)
    assert not core._states("at most 20,0000 ms.", 20_000)


def test_the_comparison_reads_identifiers_only_as_whole_tokens() -> None:
    (baseline,) = [e for e in EXPERIMENTS if e.experiment_id == BASELINE]
    assert core._normalised(
        {"a": "run e02a-1 of V2-E02A in docs/proof/experiments/v2-e02a/runs"}, baseline
    ) == {"a": "run <run>-1 of <experiment> in <directory>/runs"}
    assert core._normalised({"a": "xe02a-1 V2-E02AB"}, baseline) == {
        "a": "xe02a-1 V2-E02AB"
    }


# --------------------------------------------------------------------------
# 4. The clock policy of rule set 2
# --------------------------------------------------------------------------

#: The text of revision 1 that the first Sprint 6 review found to contradict P8.
R1_LIMITATION = (
    "The caller instants, the readings, and the events are on three clocks whose "
    "differences are not measured."
)
R1_WINDOW_CLOCKS = (
    "A caller instant is on the clock of the runner pod. A reading is on the clock "
    "of the collecting host, and an event on the clock of the recording host. The "
    "difference between the clocks is not measured, and no order of two instants of "
    "two clocks that are less than one second apart is stated."
)
R1_CLOCK_RULE = (
    "A criterion that compares an interval between instants of two clocks with a "
    "bound is not held and not failed when the interval lies within the clock bound "
    "of P8 of that bound. The run is then INCONCLUSIVE for the reason "
    "clock-bound-reached."
)

#: The members in which a revision 2 differs from its revision 1, and nothing else.
CHANGED_MEMBERS = {
    "metadata.revision",
    "metadata.registeredBy",
    "metadata.supersedes",
    "metadata.preregistrationRules",
    "definition.limitations",
    "definition.history",
    "definition.preparation",
    "definition.window.clocks",
    "definition.clockPolicy",
    "definition.criterionClocks",
    "definition.outcomeRules",
    "exclusionReasons.reasons",
    "fields.experimentIdVersion",
    "fields.gitRevision",
    "pinnedInputs",
    "inputChanges",
}
E05_CHANGED_MEMBERS = {
    "definition.reconciliationTiming.start",
    "definition.reconciliationTiming.end",
    "definition.reconciliationTiming.clocks",
}
#: The three files of this check, which every record pins. An edit to one moves the
#: pins of every record, and of revision 1 too.
CHECK_FILES = [
    "tools/experiment_preregistration/__init__.py",
    "tools/experiment_preregistration/__main__.py",
    "tools/experiment_preregistration/core.py",
]


def policy_of(document: dict[str, Any]) -> dict[str, Any]:
    result = document["definition"]["clockPolicy"]
    assert isinstance(result, dict)
    return result


def edit_two(root: Path, change: Callable[[dict[str, Any]], None]) -> None:
    """Plant one change in each record of rule set 2, so that they stay alike."""
    for path in REVISION_TWO.values():
        edit(root, path, change)


def each(rule: str, location: str, detail: str) -> list[tuple[str, str, str, str]]:
    return [(rule, path, location, detail) for path in sorted(REVISION_TWO.values())]


def differences(left: Any, right: Any, prefix: str = "") -> set[str]:
    """The paths of the members in which two values differ. A list is one member."""
    if isinstance(left, dict) and isinstance(right, dict):
        found: set[str] = set()
        for key in set(left) | set(right):
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                found.add(path)
            else:
                found |= differences(left[key], right[key], path)
        return found
    return set() if left == right else {prefix}


def test_every_record_of_rule_set_two_states_one_clock_policy() -> None:
    policies = {path: policy_of(load(path)) for path in REVISION_TWO.values()}
    assert policy_of(load(E02A)) == policy_of(load(E02B))
    assert len({json.dumps(p, sort_keys=True) for p in policies.values()}) == 1
    policy = policies[E02B]
    assert [c["id"] for c in policy["clocks"]] == ["node", "host"]
    assert {s["id"]: (s["clock"], s["resolutionMs"]) for s in policy["sources"]} == {
        "caller-record": ("node", 1),
        "kubernetes-timestamp": ("node", 1000),
        "collector-reading": ("host", 1),
        "operator-event": ("host", 1),
        "clock-reading-host": ("host", 1),
        "clock-reading-node": ("node", 1),
    }
    assert policy["measurement"]["readings"] == ["start", "end"]
    assert policy["missingReadings"]["end"]["reason"] == "clock-reading-missing"
    assert policy["notJudged"]["decidedStateStands"] is True
    assert "the clock bound" in policy["ordering"]["margin"]
    assert policy["ordering"]["margin"] == policy["boundComparison"]["margin"]


def test_the_bound_is_the_formula_of_revision_one_word_for_word() -> None:
    for experiment, path in REVISION_TWO.items():
        (step_1,) = [
            s
            for s in load(REVISION_ONE[experiment])["definition"]["preparation"]
            if s.startswith("P8. ")
        ]
        (step_2,) = [
            s for s in load(path)["definition"]["preparation"] if s.startswith("P8. ")
        ]
        assert core.CLOCK_BOUND_FORMULA in step_1
        assert core.CLOCK_BOUND_FORMULA in step_2
        assert step_2.startswith(step_1)
        assert policy_of(load(path))["bound"]["formula"] == core.CLOCK_BOUND_FORMULA


def test_revision_two_differs_from_revision_one_only_in_the_listed_members() -> None:
    """A tripwire: every other member keeps its revision-1 value byte for byte."""
    for experiment, path in REVISION_TWO.items():
        one, two = load(REVISION_ONE[experiment]), load(path)
        expected = CHANGED_MEMBERS | (
            E05_CHANGED_MEMBERS if experiment == "V2-E05" else set()
        )
        assert differences(one, two) == expected, experiment
        limitations_1 = one["definition"]["limitations"]
        limitations_2 = two["definition"]["limitations"]
        index = limitations_1.index(R1_LIMITATION)
        assert limitations_2[:index] == limitations_1[:index]
        assert limitations_2[index + 1 : -1] == limitations_1[index + 1 :]
        assert len(limitations_2) == len(limitations_1) + 1
        assert two["definition"]["history"][:-1] == one["definition"]["history"]
        steps_1 = one["definition"]["preparation"]
        steps_2 = two["definition"]["preparation"]
        assert steps_2[1:7] == steps_1[1:7]
        assert steps_2[0].startswith(steps_1[0])
        assert "latest revision of its experiment" in steps_2[0]
        rules_1 = one["definition"]["outcomeRules"]
        rules_2 = two["definition"]["outcomeRules"]
        assert rules_1[5] == R1_CLOCK_RULE
        assert rules_2[:5] + rules_2[6:] == rules_1[:5] + rules_1[6:]
        reasons_1 = {r["id"]: r for r in one["exclusionReasons"]["reasons"]}
        reasons_2 = {r["id"]: r for r in two["exclusionReasons"]["reasons"]}
        assert set(reasons_2) - set(reasons_1) == {"clock-reading-missing"}
        for reason, entry in reasons_1.items():
            if reason != "clock-bound-reached":
                assert reasons_2[reason] == entry
        assert len(reasons_2) == 10
        moved = {p["path"] for p in one["pinnedInputs"] if p not in two["pinnedInputs"]}
        assert sorted(moved) == CHECK_FILES
        assert [c["path"] for c in two["inputChanges"]] == CHECK_FILES
        assert [c["material"] for c in two["inputChanges"]] == [False, False, True]


def test_each_revision_one_record_still_passes_under_its_own_rules() -> None:
    """The full rule set 1, with the cross-record rules, over the five revision-1
    records, as V2-S6-003-PR1 checked them."""
    records = {
        experiment: (path, load(path)) for experiment, path in REVISION_ONE.items()
    }
    assert check_records(records) == []


def test_the_moved_pins_of_each_revision_one_record_are_this_check_alone() -> None:
    """Revision 2 classifies them. V2-E04 has no revision 2 yet, so its revision 1
    lists them as changed until a later revision of it supersedes it."""
    for path in REVISION_ONE.values():
        changes = changed_inputs(load(path), REPO_ROOT)
        assert [(c.path, c.kind) for c in changes] == [
            (file, "changed") for file in CHECK_FILES
        ], path
    for path in REVISION_TWO.values():
        assert changed_inputs(load(path), REPO_ROOT) == [], path


def test_the_reconciliation_bound_of_e05_is_on_the_host_clock_alone() -> None:
    document = load(E05)
    (entry,) = [
        e
        for e in document["definition"]["criterionClocks"]
        if e["criterion"] == "E05-AC9"
    ]
    assert entry["bound"] == "reconciliation_bound_ms"
    assert [i["clock"] for i in entry["instants"]] == ["host", "host"]
    assert entry["crossClock"] is False
    assert "host clock" in document["definition"]["reconciliationTiming"]["clocks"]


def test_the_caller_bound_of_e02c_is_on_the_node_clock_alone() -> None:
    (entry,) = [
        e
        for e in load(E02C)["definition"]["criterionClocks"]
        if e["criterion"] == "E02C-AC10"
    ]
    assert entry["bound"] == "caller_total_unavailability_bound_ms"
    assert [i["source"] for i in entry["instants"]] == ["caller-record"] * 2
    assert entry["crossClock"] is False


def test_each_criterion_clock_entry_is_cross_clock_exactly_when_its_clocks_differ() -> (
    None
):
    for path in REVISION_TWO.values():
        for entry in load(path)["definition"]["criterionClocks"]:
            clocks = [core.CLOCK_SOURCES[i["source"]][0] for i in entry["instants"]]
            assert [i["clock"] for i in entry["instants"]] == clocks
            assert entry["crossClock"] is (clocks[0] != clocks[1])


def test_no_text_of_a_record_of_rule_set_two_contradicts_the_policy() -> None:
    for path in REVISION_TWO.values():
        assert list(core._contradiction_findings(path, load(path))) == []


def test_revision_one_text_is_what_the_clock_rules_refuse() -> None:
    """The scan finds the contradictions that the review named in revision 1, and
    nothing else."""
    for experiment, path in REVISION_ONE.items():
        assert [
            (f.location, f.detail)
            for f in core._contradiction_findings(path, load(path))
        ] == [
            (
                "definition.limitations[2]",
                "it states that the clock difference is not measured",
            ),
            (
                "definition.window.clocks",
                "it states that the clock difference is not measured",
            ),
            (
                "definition.window.clocks",
                "it states an ordering threshold that does not name the clock bound",
            ),
        ], experiment


def test_a_negation_hides_a_claim_from_the_scan() -> None:
    """A known limit: the scan reads words, not meaning. A sentence that claims
    synchronization and holds a negation elsewhere is not refused."""
    document = {
        "definition": {"limitations": ["The clocks are synchronized, not drifting."]}
    }
    assert list(core._contradiction_findings("x", document)) == []
    document = {"definition": {"limitations": ["The clocks are synchronized."]}}
    assert [f.detail for f in core._contradiction_findings("x", document)] == [
        "it names synchronization or a guarantee with no negation"
    ]


CONTRADICTION = "prereg-clock-contradiction"
CLOCK_RULES = "prereg-clock-rules"
MEASUREMENT = "prereg-clock-measurement"
INVENTORY = "prereg-clock-inventory"
REASONS = "prereg-clock-reasons"
NOT_MEASURED = "it states that the clock difference is not measured"
FIXED_ORDER = "it states an ordering threshold that does not name the clock bound"


def _limitation(document: dict[str, Any]) -> None:
    limitations = document["definition"]["limitations"]
    limitations[2] = R1_LIMITATION


def _window(document: dict[str, Any]) -> None:
    document["definition"]["window"]["clocks"] = R1_WINDOW_CLOCKS


def test_a_limitation_that_says_the_difference_is_not_measured_is_refused(
    root: Path,
) -> None:
    """(a) The limitation of revision 1."""
    edit_two(root, _limitation)
    assert found(root) == each(CONTRADICTION, "definition.limitations[2]", NOT_MEASURED)


def test_a_window_that_says_the_difference_is_not_measured_is_refused(
    root: Path,
) -> None:
    """(a) and (e) The window text of revision 1: two contradictions."""
    edit_two(root, _window)
    assert found(root) == [
        finding
        for path in sorted(REVISION_TWO.values())
        for finding in (
            (CONTRADICTION, path, "definition.window.clocks", NOT_MEASURED),
            (CONTRADICTION, path, "definition.window.clocks", FIXED_ORDER),
        )
    ]


def test_a_record_without_p8_is_refused(root: Path) -> None:
    """(b) P8 removed."""

    def change(document: dict[str, Any]) -> None:
        steps = document["definition"]["preparation"]
        steps[:] = [s for s in steps if not s.startswith("P8. ")]

    edit_two(root, change)
    assert found(root) == each(
        MEASUREMENT, "definition.preparation", "the preparation has no one step P8"
    )


@pytest.mark.parametrize(
    ("change", "location", "detail"),
    [
        pytest.param(
            lambda d: d["definition"]["preparation"].__setitem__(
                7,
                d["definition"]["preparation"][7].replace(
                    " and again after the window ends", ""
                ),
            ),
            "definition.preparation",
            "P8 does not read the clocks before the runner starts and after the "
            "window ends",
            id="p8-text",
        ),
        pytest.param(
            lambda d: policy_of(d)["measurement"].__setitem__("readings", ["start"]),
            "definition.clockPolicy.measurement",
            "the measurement is not P8, with a start and an end reading of three "
            "instants, each with its time",
            id="policy-readings",
        ),
    ],
)
def test_a_measurement_without_its_end_reading_is_refused(
    root: Path, change: Callable[[dict[str, Any]], None], location: str, detail: str
) -> None:
    """(b) One of the two readings removed."""
    edit_two(root, change)
    assert found(root) == each(MEASUREMENT, location, detail)


@pytest.mark.parametrize("reason", ["clock-reading-missing", "clock-bound-reached"])
def test_a_record_without_a_clock_reason_is_refused(root: Path, reason: str) -> None:
    """(c) and (d) One clock reason removed."""

    def change(document: dict[str, Any]) -> None:
        reasons = document["exclusionReasons"]["reasons"]
        reasons[:] = [r for r in reasons if r["id"] != reason]

    edit_two(root, change)
    assert found(root) == each(
        REASONS, "exclusionReasons", f"{reason} is not registered for INCONCLUSIVE"
    )


def test_outcome_rules_that_name_one_clock_reason_are_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["definition"]["outcomeRules"][5] = R1_CLOCK_RULE

    edit_two(root, change)
    assert found(root) == each(
        REASONS,
        "definition.outcomeRules",
        "the outcome rules do not name clock-reading-missing",
    )


def test_an_ordering_threshold_that_does_not_use_the_bound_is_refused(
    root: Path,
) -> None:
    """(e) A fixed threshold of one second, as revision 1 stated it."""

    def change(document: dict[str, Any]) -> None:
        ordering = policy_of(document)["ordering"]
        ordering["crossClock"] = (
            "No order is stated between two instants of two clocks that are less "
            "than one second apart."
        )
        ordering["margin"] = "1,000 ms"

    edit_two(root, change)
    assert found(root) == each(
        CLOCK_RULES,
        "definition.clockPolicy.ordering",
        "it does not apply the margin of rule set 2 across the clocks, under "
        "clock-bound-reached",
    ) + each(CONTRADICTION, "definition.clockPolicy.ordering.crossClock", FIXED_ORDER)


def test_a_criterion_clock_that_the_inventory_does_not_hold_is_refused(
    root: Path,
) -> None:
    """(f) The runner pod's clock, which revision 1 named as a clock of its own."""

    def change(document: dict[str, Any]) -> None:
        document["definition"]["criterionClocks"][13]["instants"][0]["clock"] = (
            "runner-pod"
        )

    edit(root, E02C, change)
    where = "definition.criterionClocks[13]"
    assert found(root) == [
        (
            INVENTORY,
            E02C,
            where,
            "it names the clock runner-pod, which the inventory does not hold",
        ),
    ]


def test_a_cross_clock_criterion_declared_same_clock_is_refused(root: Path) -> None:
    """(g) stabilizedAt, on the node clock, against the observation limit, on the
    host clock."""

    def change(document: dict[str, Any]) -> None:
        entry = document["definition"]["criterionClocks"][7]
        assert [i["clock"] for i in entry["instants"]] == ["node", "host"]
        entry["crossClock"] = False

    edit(root, E02C, change)
    assert found(root) == [
        (
            INVENTORY,
            E02C,
            "definition.criterionClocks[7]",
            "it is declared same-clock, and its instants are on two clocks",
        )
    ]


def test_a_same_clock_criterion_declared_cross_clock_is_refused(root: Path) -> None:
    """callerFailureEpisodeMs: two caller completions, on the node clock."""

    def change(document: dict[str, Any]) -> None:
        document["definition"]["criterionClocks"][13]["crossClock"] = True

    edit(root, E02C, change)
    assert found(root) == [
        (
            INVENTORY,
            E02C,
            "definition.criterionClocks[13]",
            "it is declared cross-clock, and its instants are on one clock",
        )
    ]


def test_a_source_moved_to_the_other_clock_is_refused(root: Path) -> None:
    """(g) A criterion cannot become same-clock by moving its source."""

    def change(document: dict[str, Any]) -> None:
        entry = document["definition"]["criterionClocks"][7]
        entry["instants"][0]["clock"] = "host"

    edit(root, E02C, change)
    where = "definition.criterionClocks[7]"
    assert found(root) == [
        (
            INVENTORY,
            E02C,
            where,
            "it puts the source caller-record on the host clock, and the inventory "
            "puts it on the node clock",
        )
    ]


def test_an_inventory_that_moves_the_caller_to_the_host_clock_is_refused(
    root: Path,
) -> None:
    def change(document: dict[str, Any]) -> None:
        policy_of(document)["sources"][0]["clock"] = "host"

    edit_two(root, change)
    assert found(root) == each(
        INVENTORY,
        "definition.clockPolicy.sources",
        "the sources are not those of rule set 2, each once with its clock, its "
        "resolution, and a statement",
    )


def test_a_bound_criterion_without_its_clocks_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        del document["definition"]["criterionClocks"][13]

    edit(root, E02C, change)
    assert found(root) == [
        (
            INVENTORY,
            E02C,
            "fields.acceptanceCriteria[0].value[9]",
            "it names a bound and declares no clocks of its interval",
        )
    ]


def test_clock_policies_of_the_baseline_and_the_target_that_differ_are_refused(
    root: Path,
) -> None:
    """(h)"""

    def change(document: dict[str, Any]) -> None:
        policy_of(document)["statement"] += " The baseline reads it differently."

    edit(root, E02A, change)
    assert found(root) == [shared(E02A, "definition.clockPolicy")]


def test_a_clock_policy_of_e05_that_differs_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        policy_of(document)["clocks"][1]["statement"] += " Another host."

    edit(root, E05, change)
    assert found(root) == [shared(E05, "definition.clockPolicy")]


@pytest.mark.parametrize(
    ("change", "location", "detail"),
    [
        pytest.param(
            lambda d: policy_of(d)["bound"].__setitem__(
                "formula", core.CLOCK_BOUND_FORMULA.split(", plus")[0]
            ),
            "definition.clockPolicy.bound",
            "the bound is not the formula of revision 1 with the computation of rule "
            "set 2, in milliseconds, with the reason that it is conservative",
            id="policy-formula",
        ),
        pytest.param(
            lambda d: policy_of(d)["bound"].__setitem__(
                "computation",
                core.CLOCK_BOUND_COMPUTATION.replace(
                    " plus the larger w of the two readings", ""
                ),
            ),
            "definition.clockPolicy.bound",
            "the bound is not the formula of revision 1 with the computation of rule "
            "set 2, in milliseconds, with the reason that it is conservative",
            id="policy-computation",
        ),
        pytest.param(
            lambda d: d["definition"]["preparation"].__setitem__(
                7,
                d["definition"]["preparation"][7].replace(
                    ", plus the time between the two host instants", ""
                ),
            ),
            "definition.preparation",
            "P8 does not state the bound formula of revision 1",
            id="p8-formula",
        ),
    ],
)
def test_a_bound_formula_other_than_that_of_revision_one_is_refused(
    root: Path, change: Callable[[dict[str, Any]], None], location: str, detail: str
) -> None:
    """(i) The formula without the time between the two host instants."""
    edit_two(root, change)
    assert found(root) == each(MEASUREMENT, location, detail)


@pytest.mark.parametrize(
    ("change", "location"),
    [
        pytest.param(
            lambda d: policy_of(d)["uncertainty"].__setitem__(
                "notClaimed", "The host synchronizes the clocks, so the bound holds."
            ),
            "definition.clockPolicy.uncertainty.notClaimed",
            id="synchronized",
        ),
        pytest.param(
            lambda d: d["definition"]["window"].__setitem__(
                "clocks",
                d["definition"]["window"]["clocks"]
                + " The clock bound is guaranteed between the two readings.",
            ),
            "definition.window.clocks",
            id="guaranteed",
        ),
    ],
)
def test_wording_that_claims_synchronization_or_a_guarantee_is_refused(
    root: Path, change: Callable[[dict[str, Any]], None], location: str
) -> None:
    """(j)"""
    edit_two(root, change)
    assert found(root) == each(
        CONTRADICTION,
        location,
        "it names synchronization or a guarantee with no negation",
    )


NOT_JUDGED = (
    "a verdict that is not judged does not follow the rule of rule set 2, in which "
    "a state that the judged verdicts decide stands"
)


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda d: policy_of(d)["notJudged"].__setitem__(
                "rule",
                "An unusable end reading makes every run INCONCLUSIVE for the reason "
                "clock-reading-missing.",
            ),
            id="every-run-inconclusive",
        ),
        pytest.param(
            lambda d: policy_of(d)["notJudged"].__setitem__(
                "decidedStateStands", False
            ),
            id="decided-state-does-not-stand",
        ),
    ],
)
def test_an_end_reading_rule_that_excludes_every_run_is_refused(
    root: Path, change: Callable[[dict[str, Any]], None]
) -> None:
    """(k) A clear FAILED is never turned into an exclusion."""
    edit_two(root, change)
    assert found(root) == each(
        CLOCK_RULES, "definition.clockPolicy.notJudged", NOT_JUDGED
    )


def test_a_policy_without_the_offset_stability_assumption_is_refused(
    root: Path,
) -> None:
    """(l)"""
    edit_two(root, lambda d: policy_of(d)["uncertainty"].pop("offsetStability"))
    assert found(root) == each(
        CLOCK_RULES,
        "definition.clockPolicy.uncertainty",
        "it does not state the offset-stability assumption of rule set 2",
    )


@pytest.mark.parametrize(
    ("change", "location", "detail"),
    [
        pytest.param(
            lambda d: policy_of(d)["missingReadings"]["start"].__setitem__(
                "resultState", "INCONCLUSIVE"
            ),
            "definition.clockPolicy.missingReadings.start",
            "an unusable start reading does not refuse the run before the fault",
            id="start-inconclusive",
        ),
        pytest.param(
            lambda d: policy_of(d)["missingReadings"]["start"].__setitem__(
                "faultInjected", True
            ),
            "definition.clockPolicy.missingReadings.start",
            "an unusable start reading does not refuse the run before the fault",
            id="start-fault-injected",
        ),
        pytest.param(
            lambda d: policy_of(d)["missingReadings"]["end"].__setitem__(
                "boundComputable", True
            ),
            "definition.clockPolicy.missingReadings.end",
            "an unusable end reading does not leave the bound not computable, under "
            "clock-reading-missing",
            id="end-bound-computable",
        ),
    ],
)
def test_a_missing_reading_rule_other_than_that_of_rule_set_two_is_refused(
    root: Path, change: Callable[[dict[str, Any]], None], location: str, detail: str
) -> None:
    edit_two(root, change)
    assert found(root) == each(CLOCK_RULES, location, detail)


@pytest.mark.parametrize(
    ("path", "stated", "detail"),
    [
        pytest.param(
            E05,
            None,
            "the record states no rule set of 2 or later that this check knows",
            id="revision-two-states-none",
        ),
        pytest.param(
            E05,
            3,
            "the record states no rule set of 2 or later that this check knows",
            id="unknown-rule-set",
        ),
        pytest.param(
            E05,
            1,
            "the record states no rule set of 2 or later that this check knows",
            id="later-revision-under-rule-set-one",
        ),
        pytest.param(
            E05,
            True,
            "the record states no rule set of 2 or later that this check knows",
            id="rule-set-a-boolean",
        ),
        pytest.param(
            E04,
            2,
            "a revision-1 record of rule set 1 states no rule set",
            id="revision-one-states-one",
        ),
    ],
)
def test_a_record_with_no_known_rule_set_is_refused(
    root: Path, path: str, stated: Any, detail: str
) -> None:
    """A revision cannot leave the clock rules by stating no rule set."""

    def change(document: dict[str, Any]) -> None:
        if stated is None:
            del document["metadata"]["preregistrationRules"]
        else:
            document["metadata"]["preregistrationRules"] = stated

    edit(root, path, change)
    assert found(root) == [
        ("prereg-rule-set-unknown", path, "metadata.preregistrationRules", detail)
    ]


def test_a_superseded_revision_with_a_rule_set_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["metadata"]["preregistrationRules"] = 2

    edit(root, E02C_R1, change)
    assert found(root) == [
        (
            "prereg-rule-set-unknown",
            E02C_R1,
            "metadata.preregistrationRules",
            "a revision-1 record of rule set 1 states no rule set",
        )
    ]


def test_a_record_of_rule_set_two_without_a_clock_policy_is_refused(
    root: Path,
) -> None:
    edit(root, E02C, lambda d: d["definition"].pop("clockPolicy"))
    assert found(root) == [
        (
            "prereg-record-shape",
            E02C,
            "$",
            "definition states no clock policy and no criterion clocks",
        )
    ]


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda d: policy_of(d).__setitem__("sources", "x"), id="sources"),
        pytest.param(lambda d: policy_of(d).__setitem__("clocks", [1]), id="clocks"),
        pytest.param(
            lambda d: policy_of(d).__setitem__("measurement", []), id="measurement"
        ),
        pytest.param(
            lambda d: policy_of(d)["bound"].__setitem__("formula", 1), id="formula"
        ),
        pytest.param(
            lambda d: policy_of(d).__setitem__("ordering", None), id="ordering"
        ),
        pytest.param(
            lambda d: d["definition"]["criterionClocks"].__setitem__(0, "x"),
            id="entry",
        ),
        pytest.param(
            lambda d: d["definition"]["criterionClocks"][0].__setitem__(
                "instants", [1, 2]
            ),
            id="instants",
        ),
        pytest.param(
            lambda d: d["exclusionReasons"]["reasons"].__setitem__(0, "x"),
            id="reason",
        ),
    ],
)
def test_a_malformed_clock_policy_is_a_finding_and_not_an_error(
    root: Path, change: Callable[[dict[str, Any]], None]
) -> None:
    edit(root, E02C, change)
    findings = found(root)
    assert findings
    assert all(f[1] == E02C for f in findings)


def test_a_superseded_revision_is_checked_against_its_own_sources(
    root: Path,
) -> None:
    """History is checked alone: its rules that read one record still apply."""

    def change(document: dict[str, Any]) -> None:
        value(document, "derivedNumericBounds")["bounds"][3]["valueMs"] = 20_000

    edit(root, E02C_R1, change)
    assert found(root) == [
        (
            "prereg-bounds-stale",
            E02C_R1,
            "fields.derivedNumericBounds",
            "the bounds differ from those of the bound record",
        ),
        (
            "prereg-criterion-bound-unknown",
            E02C_R1,
            "fields.acceptanceCriteria[0].value[9]",
            "its statement does not state 20,000 ms",
        ),
    ]


def test_a_later_bound_record_leaves_the_superseded_revisions_alone(
    root: Path,
) -> None:
    """A superseded revision is not run, so it is not held to the latest bounds."""
    shutil.copyfile(
        root / BOUNDS, root / "docs/proof/experiments/v2-q4/bounds-r2.v1alpha1.json"
    )
    assert {f[1] for f in found(root)} == set(RECORDS.values())


def test_the_rule_sets_are_published() -> None:
    assert sorted(core.RULE_SETS) == [1, 2]
    assert frozenset(REVISION_ONE.values()) == core.REVISION_ONE_RECORDS
    text = README.read_text(encoding="utf-8")
    for constant in (
        core.CLOCK_BOUND_FORMULA,
        core.CLOCK_BOUND_COMPUTATION,
        core.CLOCK_MARGIN,
        core.OFFSET_STABILITY,
        core.NOT_JUDGED_RULE,
    ):
        assert constant in " ".join(text.split()), constant[:40]
