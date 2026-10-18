"""The freeze records of the reliability experiments, held to their sources.

V2-S6-003-PR1 registers one freeze record for each of V2-E02A, V2-E02B, V2-E02C,
V2-E04, and V2-E05, before any run. ``tools.experiment_freeze`` checks that each
answers every freeze field. ``tools.experiment_preregistration`` reads the
answers: the qualification, the bound record, and the baseline comparison that
each record names, and the records against each other.

The first part holds the committed records, with their identities written out so
that a change to one is visible in review. The second part plants each defect
that the check refuses in a copy of the files it reads, and asserts the exact
findings. No test runs an experiment or contacts a cluster.
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
    check_repository,
    latest_records,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "docs" / "proof" / "experiments" / "README.md"

E02A = "docs/proof/experiments/v2-e02a/freeze-r1.v1alpha1.json"
E02B = "docs/proof/experiments/v2-e02b/freeze-r1.v1alpha1.json"
E02C = "docs/proof/experiments/v2-e02c/freeze-r1.v1alpha1.json"
E04 = "docs/proof/experiments/v2-e04/freeze-r1.v1alpha1.json"
E05 = "docs/proof/experiments/v2-e05/freeze-r1.v1alpha1.json"
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
    assert result.stdout.strip() == "PASSED: 5 experiment record(s), every rule held"


def test_each_record_is_revision_one_registered_by_this_change() -> None:
    assert {k: path for k, (path, _) in latest_records().items()} == RECORDS
    for experiment, path in RECORDS.items():
        document = load(path)
        assert document["metadata"]["experiment"] == experiment
        assert document["metadata"]["revision"] == 1
        assert document["metadata"]["supersedes"] is None
        assert document["metadata"]["registeredBy"] == "V2-S6-003-PR1"
        assert FROZEN_RECORDS[path] == content_digest((REPO_ROOT / path).read_bytes())
    assert check_freezes() == []


def test_no_field_is_pending_or_not_applicable() -> None:
    """No placeholder: every freeze field of every record is answered with a value."""
    for path in RECORDS.values():
        for field, entries in load(path)["fields"].items():
            assert [e["status"] for e in entries] == ["value"], (path, field)


def test_each_record_names_the_q1_2_lineage_and_the_bound_record() -> None:
    for path in RECORDS.values():
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
    for path in RECORDS.values():
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
        assert sorted(p.name for p in directory.iterdir()) == [
            "freeze-r1.v1alpha1.json"
        ]


def test_each_record_pins_exactly_its_material_scope_at_registration() -> None:
    """A tripwire: a file added to or removed from a scope moves this set. Such a
    change owes a later revision of the record before any run, and the
    ``--changes`` command of the freeze tool lists the file until then."""
    for path in RECORDS.values():
        document = load(path)
        pinned = {item["path"] for item in document["pinnedInputs"]}
        assert material_files(document["materialScope"], REPO_ROOT) == pinned, path
        assert "tools/experiment_preregistration/core.py" in pinned
        assert REGISTRY not in pinned
        assert path not in pinned


def test_every_rule_is_published() -> None:
    assert len(RULES) == 12
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
    for path in RECORDS.values():
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
            "fields.acceptanceCriteria[0].value[8]",
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
    assert sorted({f[1] for f in findings}) == sorted(RECORDS.values())
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
            "fields.acceptanceCriteria[0].value[5]",
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
