"""The freeze records of the reliability experiments, held to their sources.

V2-S6-003-PR1 registered one freeze record for each of V2-E02A, V2-E02B, V2-E02C,
V2-E04, and V2-E05, before any run. V2-S6-007-PR1 registered revision 2 of the
records of V2-E02A, V2-E02B, V2-E02C, and V2-E05, under rule set 2 and its one
clock policy. V2-S6-005-PR1 registered revision 2 of the record of V2-E04, under
the same policy and the reversal timing as the repository owner amended it.
V2-S6-008-PR1 registered revision 3 of the record of V2-E04, under rule set 4, which
selects the span of its recovery criterion with no onset exclusion. Revision 1 of
each, and revision 2 of V2-E04, stay unchanged.
``tools.experiment_freeze`` checks that each record answers every freeze field.
``tools.experiment_preregistration`` reads the answers: the qualification, the
bound record, and the baseline comparison that each record names, the clock
policy of a record of rule set 2, the reversal timing of V2-E04, and the records
against each other.

The first part holds the committed records, with their identities written out so
that a change to one is visible in review. The second and the third part plant
each defect that the check refuses in a copy of the files it reads, and assert
the exact findings. The fourth part does the same for the clock rules, and the fifth for
the reversal-timing rules of V2-E04. Those parts read a copy of the records as they
were before revision 3 of V2-E04, so that rule set 3 is held to read exactly as it
did. The sixth part holds revision 3 and the selection rules of rule set 4 in a copy
of every committed record. No test runs an experiment or contacts a cluster.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tools import reliability_analysis as analysis
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

#: The latest revision of each experiment: revision 2.
E02A = "docs/proof/experiments/v2-e02a/freeze-r2.v1alpha1.json"
E02B = "docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json"
E02C = "docs/proof/experiments/v2-e02c/freeze-r2.v1alpha1.json"
E04 = "docs/proof/experiments/v2-e04/freeze-r2.v1alpha1.json"
E05 = "docs/proof/experiments/v2-e05/freeze-r2.v1alpha1.json"
#: Revision 1 of each experiment. Revision 2 supersedes it.
E02A_R1 = "docs/proof/experiments/v2-e02a/freeze-r1.v1alpha1.json"
E02B_R1 = "docs/proof/experiments/v2-e02b/freeze-r1.v1alpha1.json"
E02C_R1 = "docs/proof/experiments/v2-e02c/freeze-r1.v1alpha1.json"
E04_R1 = "docs/proof/experiments/v2-e04/freeze-r1.v1alpha1.json"
E05_R1 = "docs/proof/experiments/v2-e05/freeze-r1.v1alpha1.json"
REVISION_ONE = {
    "V2-E02A": E02A_R1,
    "V2-E02B": E02B_R1,
    "V2-E02C": E02C_R1,
    "V2-E04": E04_R1,
    "V2-E05": E05_R1,
}
#: The five revisions 2: four of rule set 2, and V2-E04, of rule set 3, which holds
#: every rule of rule set 2 and adds the reversal-timing rules.
REVISION_TWO = {
    "V2-E02A": E02A,
    "V2-E02B": E02B,
    "V2-E02C": E02C,
    "V2-E04": E04,
    "V2-E05": E05,
}
#: The four of them that V2-S6-007-PR1 registered, and the one of V2-S6-005-PR1.
CLOCK_REVISIONS = {k: v for k, v in REVISION_TWO.items() if k != "V2-E04"}
REGISTERED_BY = {
    **dict.fromkeys(CLOCK_REVISIONS, "V2-S6-007-PR1"),
    "V2-E04": "V2-S6-005-PR1",
}
RULE_SET_OF = {**dict.fromkeys(CLOCK_REVISIONS, 2), "V2-E04": 3}
#: Every record of the five experiments before V2-S6-008-PR1. The second to the
#: fifth part read a copy of these alone, in which revision 2 of V2-E04 is the latest.
ALL_RECORDS = sorted(set(REVISION_ONE.values()) | set(REVISION_TWO.values()))
#: The latest revision of each experiment in that copy.
RECORDS = {
    "V2-E02A": E02A,
    "V2-E02B": E02B,
    "V2-E02C": E02C,
    "V2-E04": E04,
    "V2-E05": E05,
}
#: Revision 3 of V2-E04, of rule set 4, registered by V2-S6-008-PR1. Its registered
#: pin is written out so that a change is visible.
E04_R3 = "docs/proof/experiments/v2-e04/freeze-r3.v1alpha1.json"
E04_R3_PIN = "41fa69cd4a84940f587577a3278083d86f9c2b970e7ba5179aded10a07fc1f05"
#: Revision 3 of V2-E02A, of rule set 2, registered by V2-S7-001-PR1. It pins the
#: driver of V2-E02A and the control that the driver starts. The copies of the later
#: parts leave it out, so that they read revision 2 as the latest V2-E02A record.
E02A_R3 = "docs/proof/experiments/v2-e02a/freeze-r3.v1alpha1.json"
E02A_R3_PIN = "2eb83a06ba4c1a6289f9f9ebeeb971298ae7f001d91475e8dc6c09696528d456"
DRIVER = "docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt"
#: Every committed record before V2-S7-001-PR1, every committed record, and the latest
#: committed revision of each experiment.
ALL_COMMITTED = sorted([*ALL_RECORDS, E04_R3])
EVERY_RECORD = sorted([*ALL_COMMITTED, E02A_R3])
LATEST_RECORDS = {**RECORDS, "V2-E04": E04_R3, "V2-E02A": E02A_R3}

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
        "PASSED: 5 experiment record(s) and 7 superseded revision(s), every rule held"
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


def test_the_latest_records_are_revision_two_and_v2_e04_and_v2_e02a_revision_three() -> (
    None
):
    assert {k: path for k, (path, _) in latest_records().items()} == LATEST_RECORDS
    e02a = load(E02A_R3)["metadata"]
    assert e02a == {
        "experiment": "V2-E02A",
        "title": load(E02A)["metadata"]["title"],
        "revision": 3,
        "registered": "2026-10-22",
        "registeredBy": "V2-S7-001-PR1",
        "supersedes": {"path": E02A, "contentSha256": FROZEN_RECORDS[E02A]},
        "preregistrationRules": 2,
    }
    assert FROZEN_RECORDS[E02A_R3] == E02A_R3_PIN
    assert content_digest((REPO_ROOT / E02A_R3).read_bytes()) == E02A_R3_PIN
    three = load(E04_R3)["metadata"]
    assert three == {
        "experiment": "V2-E04",
        "title": load(E04)["metadata"]["title"],
        "revision": 3,
        "registered": "2026-10-20",
        "registeredBy": "V2-S6-008-PR1",
        "supersedes": {"path": E04, "contentSha256": FROZEN_RECORDS[E04]},
        "preregistrationRules": 4,
    }
    assert FROZEN_RECORDS[E04_R3] == E04_R3_PIN
    assert content_digest((REPO_ROOT / E04_R3).read_bytes()) == E04_R3_PIN
    for experiment, path in REVISION_TWO.items():
        metadata = load(path)["metadata"]
        assert metadata["experiment"] == experiment
        assert metadata["revision"] == 2
        assert metadata["registeredBy"] == REGISTERED_BY[experiment]
        assert metadata["preregistrationRules"] == RULE_SET_OF[experiment]
        assert metadata["supersedes"] == {
            "path": REVISION_ONE[experiment],
            "contentSha256": FROZEN_RECORDS[REVISION_ONE[experiment]],
        }
        assert FROZEN_RECORDS[path] == content_digest((REPO_ROOT / path).read_bytes())


def test_no_field_is_pending_or_not_applicable() -> None:
    """No placeholder: every freeze field of every record is answered with a value."""
    for path in ALL_COMMITTED:
        for field, entries in load(path)["fields"].items():
            assert [e["status"] for e in entries] == ["value"], (path, field)


def test_each_record_names_the_q1_2_lineage_and_the_bound_record() -> None:
    for path in ALL_COMMITTED:
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
    for path in ALL_COMMITTED:
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


def test_no_run_exists_and_the_one_driver_is_that_of_v2_e02a() -> None:
    """The records come before any run. Since V2-S7-001-PR1 one driver is committed,
    that of V2-E02A, and revision 3 of its record pins it. Revisions 1 and 2 of
    V2-E02A list it as added. No other experiment has a driver."""
    for experiment in EXPERIMENTS:
        directory = REPO_ROOT / experiment.directory
        revisions = 3 if experiment.experiment_id in ("V2-E04", "V2-E02A") else 2
        names = [f"freeze-r{n}.v1alpha1.json" for n in range(1, revisions + 1)]
        if experiment.experiment_id == "V2-E02A":
            names.append("procedure")
            assert [p.name for p in (directory / "procedure").iterdir()] == [
                "e02a-driver.txt"
            ]
        assert sorted(p.name for p in directory.iterdir()) == names


def test_each_record_pins_exactly_its_material_scope_at_registration() -> None:
    """A tripwire: a file added to or removed from a scope moves this set. Such a
    change owes a later revision of the record before any run, and the
    ``--changes`` command of the freeze tool lists the file until then. Revision 1
    pins the same files as revision 2, with other digests of this check. Revision 3
    of V2-E04 also pins the outcome reference that its selection names. The driver
    of V2-E02A is in the scope of revisions 1 and 2 of V2-E02A, which do not pin it,
    and revision 3 pins it."""
    for path in EVERY_RECORD:
        document = load(path)
        pinned = {item["path"] for item in document["pinnedInputs"]}
        added = {DRIVER} if path in (E02A_R1, E02A) else set()
        assert material_files(document["materialScope"], REPO_ROOT) - pinned == added
        assert pinned <= material_files(document["materialScope"], REPO_ROOT), path
        assert "tools/experiment_preregistration/core.py" in pinned
        assert REGISTRY not in pinned
        assert path not in pinned


def test_every_rule_is_published() -> None:
    assert len(RULES) == 28
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
    "definition.criteriaWithoutClocks",
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
    """A tripwire: every other member keeps its revision-1 value byte for byte.
    V2-E04 changes more members, and the fifth part holds them."""
    for experiment, path in CLOCK_REVISIONS.items():
        one, two = load(REVISION_ONE[experiment]), load(path)
        expected = CHANGED_MEMBERS | (
            E05_CHANGED_MEMBERS if experiment == "V2-E05" else set()
        )
        assert differences(one, two) == expected, experiment
        limitations_1 = one["definition"]["limitations"]
        limitations_2 = two["definition"]["limitations"]
        index = limitations_1.index(R1_LIMITATION)
        assert limitations_2[:index] == limitations_1[:index]
        assert "tools/reliability_analysis" in limitations_2[index + 1]
        assert limitations_2[index + 2 : -1] == limitations_1[index + 1 :]
        assert len(limitations_2) == len(limitations_1) + 2
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


def test_the_moved_pins_of_each_record_are_this_check_alone() -> None:
    """A tripwire. Revision 2 classifies the moves since each revision 1. The
    reversal-timing rules of V2-S6-005-PR1 moved core.py once more, after the four
    revisions 2 of V2-S6-007-PR1 pinned it, and the selection rules of V2-S6-008-PR1
    moved it again. No revision classifies those moves: each of the four, and
    revision 2 of V2-E04, lists core.py as changed, and its P1 refuses a run, until
    a later revision of it classifies it. V2-E04 revision 3 pins the present file,
    and no other file of the check moved. Since V2-S7-001-PR1 revisions 1 and 2 of
    V2-E02A also list the driver as added, and revision 3 of V2-E02A pins the driver
    and classifies the move of core.py."""
    for path in REVISION_ONE.values():
        changes = changed_inputs(load(path), REPO_ROOT)
        added = [(DRIVER, "added")] if path == E02A_R1 else []
        assert sorted((c.path, c.kind) for c in changes) == sorted(
            [*added, *((file, "changed") for file in CHECK_FILES)]
        ), path
    for path in REVISION_TWO.values():
        changes = changed_inputs(load(path), REPO_ROOT)
        added = [(DRIVER, "added")] if path == E02A else []
        assert sorted((c.path, c.kind) for c in changes) == sorted(
            [*added, ("tools/experiment_preregistration/core.py", "changed")]
        ), path
    assert changed_inputs(load(E04_R3), REPO_ROOT) == []
    assert changed_inputs(load(E02A_R3), REPO_ROOT) == []


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
            ("definition.window.clocks", FIXED_ORDER),
        ], experiment


CONTRADICTION = "prereg-clock-contradiction"
CLOCK_RULES = "prereg-clock-rules"
MEASUREMENT = "prereg-clock-measurement"
INVENTORY = "prereg-clock-inventory"
REASONS = "prereg-clock-reasons"
NOT_MEASURED = "it states that the clock difference is not measured"
FIXED_ORDER = (
    "it states an ordering threshold that does not name the margin of rule set 2"
)


def _limitation(document: dict[str, Any]) -> None:
    limitations = document["definition"]["limitations"]
    limitations[2] = R1_LIMITATION


def _window(document: dict[str, Any]) -> None:
    document["definition"]["window"]["clocks"] = R1_WINDOW_CLOCKS


def test_a_limitation_that_says_the_difference_is_not_measured_is_refused(
    root: Path,
) -> None:
    """The limitation of revision 1."""
    edit_two(root, _limitation)
    assert found(root) == each(CONTRADICTION, "definition.limitations[2]", NOT_MEASURED)


def test_a_window_that_says_the_difference_is_not_measured_is_refused(
    root: Path,
) -> None:
    """The window text of revision 1: two contradictions."""
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
    edit_two(root, change)
    assert found(root) == each(MEASUREMENT, location, detail)


@pytest.mark.parametrize("reason", ["clock-reading-missing", "clock-bound-reached"])
def test_a_record_without_a_clock_reason_is_refused(root: Path, reason: str) -> None:

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
    """A fixed threshold of one second, as revision 1 stated it."""

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
    """The runner pod's clock, which revision 1 named as a clock of its own."""

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
    """stabilizedAt, on the node clock, against the observation limit, on the
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
    """A criterion cannot become same-clock by moving its source."""

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
            "it declares no clocks and is not listed in "
            "definition.criteriaWithoutClocks",
        ),
        (
            INVENTORY,
            E02C,
            "fields.acceptanceCriteria[0].value[9]",
            "it names a bound and declares no clocks of its interval",
        ),
    ]


def test_clock_policies_of_the_baseline_and_the_target_that_differ_are_refused(
    root: Path,
) -> None:

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
    """The formula without the time between the two host instants."""
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
    edit_two(root, change)
    assert found(root) == each(
        CONTRADICTION,
        location,
        "it names synchronization or a guarantee with no negation",
    )


END_READING = (
    "an unusable end reading does not leave the bound not computable, under "
    "clock-reading-missing, with the state that definition.clockPolicy.notJudged "
    "decides"
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
    """A FAILED state that the judged verdicts decide is never made an exclusion."""
    edit_two(root, change)
    # A rule that makes every run INCONCLUSIVE also states so in words.
    every_run = "every run" in str(policy_of(load(E02C, root))["notJudged"]["rule"])
    contradiction = each(
        CONTRADICTION,
        "definition.clockPolicy.notJudged.rule",
        "it states that every run is INCONCLUSIVE",
    )
    expected = each(CLOCK_RULES, "definition.clockPolicy.notJudged", NOT_JUDGED)
    assert found(root) == (expected + contradiction if every_run else expected)


def test_a_policy_without_the_offset_stability_assumption_is_refused(
    root: Path,
) -> None:
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
            END_READING,
            id="end-bound-computable",
        ),
        pytest.param(
            lambda d: policy_of(d)["missingReadings"]["end"].__setitem__(
                "resultState", "INCONCLUSIVE"
            ),
            "definition.clockPolicy.missingReadings.end",
            END_READING,
            id="end-fixed-state",
        ),
        pytest.param(
            lambda d: policy_of(d)["missingReadings"]["end"].__setitem__(
                "statement",
                "An unusable end reading makes the clock bound not computable, and the "
                "run is INCONCLUSIVE.",
            ),
            "definition.clockPolicy.missingReadings.end",
            END_READING,
            id="end-statement",
        ),
        pytest.param(
            lambda d: policy_of(d)["ordering"].__setitem__("sameClock", "Ordered."),
            "definition.clockPolicy.ordering",
            "it does not apply the margin of rule set 2 across the clocks, under "
            "clock-bound-reached",
            id="ordering-same-clock",
        ),
        pytest.param(
            lambda d: policy_of(d)["boundComparison"].__setitem__(
                "sameClock", "Compared."
            ),
            "definition.clockPolicy.boundComparison",
            "it does not apply the margin of rule set 2 across the clocks, under "
            "clock-bound-reached",
            id="comparison-same-clock",
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
            5,
            "the record states no rule set of 2 or later that this check knows",
            id="unknown-rule-set",
        ),
        pytest.param(
            E04,
            2,
            "a V2-E04 record after revision 1 states no rule set of 3 or later that "
            "this check knows",
            id="e04-revision-two-under-rule-set-two",
        ),
        pytest.param(
            E04,
            None,
            "a V2-E04 record after revision 1 states no rule set of 3 or later that "
            "this check knows",
            id="e04-revision-two-states-none",
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
            E04_R1,
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


SOURCES = (
    "the sources are not those of rule set 2, each once with its clock, its "
    "resolution, and a statement"
)
MARGIN = (
    "it does not apply the margin of rule set 2 across the clocks, under "
    "clock-bound-reached"
)
MEASURED = (
    "the measurement is not P8, with a start and an end reading of three instants, "
    "each with its time"
)
FORMULA = (
    "the bound is not the formula of revision 1 with the computation of rule set 2, "
    "in milliseconds, with the reason that it is conservative"
)


def _criterion(index: int) -> Callable[[dict[str, Any]], None]:
    return lambda d: value(d, "acceptanceCriteria")[index].__setitem__("id", ["x"])


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        pytest.param(
            lambda d: policy_of(d).__setitem__("sources", "x"),
            [(INVENTORY, "definition.clockPolicy.sources", SOURCES)],
            id="sources",
        ),
        pytest.param(
            lambda d: policy_of(d)["sources"][0].__setitem__("id", ["x"]),
            [(INVENTORY, "definition.clockPolicy.sources", SOURCES)],
            id="source-id-a-list",
        ),
        pytest.param(
            lambda d: policy_of(d).__setitem__("clocks", [1]),
            [
                (
                    INVENTORY,
                    "definition.clockPolicy.clocks",
                    "the inventory does not state the node clock and the host clock, "
                    "each with a statement",
                )
            ],
            id="clocks",
        ),
        pytest.param(
            lambda d: policy_of(d).__setitem__("measurement", []),
            [(MEASUREMENT, "definition.clockPolicy.measurement", MEASURED)],
            id="measurement",
        ),
        pytest.param(
            lambda d: policy_of(d)["bound"].__setitem__("formula", 1),
            [(MEASUREMENT, "definition.clockPolicy.bound", FORMULA)],
            id="formula",
        ),
        pytest.param(
            lambda d: policy_of(d).__setitem__("ordering", None),
            [(CLOCK_RULES, "definition.clockPolicy.ordering", MARGIN)],
            id="ordering",
        ),
        pytest.param(
            lambda d: d["definition"]["criterionClocks"].__setitem__(0, "x"),
            [
                (
                    INVENTORY,
                    "definition.criterionClocks[0]",
                    "the entry is not an object",
                )
            ],
            id="entry",
        ),
        pytest.param(
            lambda d: d["definition"]["criterionClocks"][0].__setitem__(
                "instants", [1, 2]
            ),
            [
                (
                    INVENTORY,
                    "definition.criterionClocks[0]",
                    "it does not state two instants, each with a source and a clock",
                )
            ],
            id="instants",
        ),
        pytest.param(
            lambda d: d["definition"]["criterionClocks"][0].__setitem__(
                "criterion", ["x"]
            ),
            [
                (
                    INVENTORY,
                    "definition.criterionClocks[0]",
                    "it names no criterion of the record",
                )
            ],
            id="entry-criterion-a-list",
        ),
        pytest.param(
            lambda d: d["definition"]["criterionClocks"][0].__setitem__(
                "comparison", ["order"]
            ),
            [
                (
                    INVENTORY,
                    "definition.criterionClocks[0]",
                    "it states no comparison, order or interval, and no statement",
                )
            ],
            id="comparison-a-list",
        ),
        pytest.param(
            lambda d: d["definition"]["criterionClocks"][13].__setitem__(
                "bound", ["x"]
            ),
            [
                (
                    INVENTORY,
                    "definition.criterionClocks[13]",
                    "it names a bound and is not an interval of one criterion",
                ),
                (
                    INVENTORY,
                    "fields.acceptanceCriteria[0].value[9]",
                    "it names a bound and declares no clocks of its interval",
                ),
            ],
            id="entry-bound-a-list",
        ),
        pytest.param(
            lambda d: d["definition"].__setitem__("criteriaWithoutClocks", [["x"]]),
            [
                (
                    INVENTORY,
                    "definition.criteriaWithoutClocks",
                    "it is not a list of criterion identifiers, each once",
                ),
                (
                    INVENTORY,
                    "fields.acceptanceCriteria[0].value[6]",
                    "it declares no clocks and is not listed in "
                    "definition.criteriaWithoutClocks",
                ),
            ],
            id="without-clocks-a-list",
        ),
        pytest.param(
            lambda d: d["exclusionReasons"]["reasons"][8].__setitem__("id", ["x"]),
            [
                (
                    "prereg-exclusion-reasons-unsupported",
                    "exclusionReasons",
                    "a reason has no identifier of its own",
                ),
                (
                    REASONS,
                    "exclusionReasons",
                    "clock-reading-missing is not registered for INCONCLUSIVE",
                ),
            ],
            id="reason-id-a-list",
        ),
        pytest.param(
            lambda d: d["exclusionReasons"]["reasons"][8].__setitem__(
                "resultState", ["INCONCLUSIVE"]
            ),
            [
                (
                    "prereg-exclusion-reasons-unsupported",
                    "exclusionReasons",
                    "a reason is registered for a result state that is counted",
                ),
                (
                    REASONS,
                    "exclusionReasons",
                    "clock-reading-missing is not registered for INCONCLUSIVE",
                ),
            ],
            id="reason-state-a-list",
        ),
    ],
)
def test_a_malformed_clock_policy_is_a_finding_and_not_an_error(
    root: Path,
    change: Callable[[dict[str, Any]], None],
    expected: list[tuple[str, str, str]],
) -> None:
    """Each member that the clock rules read is held to its type. A list where a
    string is read, such as an identifier, is a finding and never a TypeError."""

    before = json.dumps(policy_of(load(E02C, root)), sort_keys=True)
    edit(root, E02C, change)
    after = json.dumps(policy_of(load(E02C, root)), sort_keys=True)
    # A policy that differs from that of V2-E02B is also a shared difference.
    policy = [shared(E02C, "definition.clockPolicy")] if after != before else []
    assert found(root) == policy + [
        (rule, E02C, where, detail) for rule, where, detail in expected
    ]


def test_an_acceptance_criterion_identifier_that_is_a_list_is_a_finding(
    root: Path,
) -> None:
    edit(root, E02C, _criterion(9))
    findings = found(root)
    assert (
        INVENTORY,
        E02C,
        "fields.acceptanceCriteria[0].value[9]",
        "it states no identifier",
    ) in findings
    assert all(f[1] == E02C for f in findings)


def test_a_criterion_with_no_clocks_and_not_listed_is_refused(root: Path) -> None:
    """Each criterion either declares the clocks of its instants or is listed as a
    criterion without clocks."""

    def change(document: dict[str, Any]) -> None:
        clocks = document["definition"]["criterionClocks"]
        clocks[:] = [e for e in clocks if e["criterion"] != "E02C-AC9"]

    edit(root, E02C, change)
    assert found(root) == [
        (
            INVENTORY,
            E02C,
            "fields.acceptanceCriteria[0].value[8]",
            "it declares no clocks and is not listed in "
            "definition.criteriaWithoutClocks",
        )
    ]


@pytest.mark.parametrize(
    ("listed", "detail"),
    [
        pytest.param(
            "E02C-AC9",
            "E02C-AC9 is listed as without clocks and declares clocks",
            id="listed-and-declared",
        ),
        pytest.param(
            "E02C-AC99", "E02C-AC99 is not a criterion of the record", id="unknown"
        ),
    ],
)
def test_a_criterion_without_clocks_that_is_not_one_is_refused(
    root: Path, listed: str, detail: str
) -> None:
    edit(root, E02C, lambda d: d["definition"]["criteriaWithoutClocks"].append(listed))
    assert found(root) == [
        (INVENTORY, E02C, "definition.criteriaWithoutClocks", detail)
    ]


def test_validity_clocks_of_the_baseline_and_the_target_that_differ_are_refused(
    root: Path,
) -> None:
    """The two sides hold their validity criteria to the same instants."""

    def change(document: dict[str, Any]) -> None:
        document["definition"]["criterionClocks"][0]["statement"] += " Baseline."

    edit(root, E02A, change)
    assert found(root) == [shared(E02A, "definition.criterionClocks (validity)")]


@pytest.mark.parametrize(
    ("text", "detail"),
    [
        pytest.param(
            "The clock offset was never measured.", NOT_MEASURED, id="never-measured"
        ),
        pytest.param(
            "The clock difference has not been measured.",
            NOT_MEASURED,
            id="not-been-measured",
        ),
        pytest.param("Clock difference: not measured.", NOT_MEASURED, id="colon"),
        pytest.param(
            "There is no measurement of the clock offset.",
            NOT_MEASURED,
            id="no-measurement",
        ),
        pytest.param(
            "Instants are ordered when they are four seconds apart.",
            FIXED_ORDER,
            id="four-seconds",
        ),
        pytest.param(
            "Instants are ordered when they are one minute apart.",
            FIXED_ORDER,
            id="one-minute",
        ),
        pytest.param(
            "Instants are ordered by one second, not by the clock bound.",
            FIXED_ORDER,
            id="names-the-bound-only",
        ),
        pytest.param(
            "A precedes B when it is earlier by 2 s.", FIXED_ORDER, id="precedes"
        ),
        pytest.param(
            "No run exists\nThe clocks are synchronized",
            "it names synchronization or a guarantee with no negation",
            id="newline",
        ),
        pytest.param(
            "An unusable end reading makes every run INCONCLUSIVE.",
            "it states that every run is INCONCLUSIVE",
            id="every-run",
        ),
    ],
)
def test_a_paraphrase_that_the_scan_names_is_refused(text: str, detail: str) -> None:
    document = {"definition": {"limitations": [text]}}
    assert [
        (f.location, f.detail) for f in core._contradiction_findings("x", document)
    ] == [("definition.limitations[0]", detail)]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("The clocks are synchronized, and no run is lost.", id="negation"),
        pytest.param("The two clocks agree to the millisecond.", id="agree"),
        pytest.param("The clocks were never compared.", id="never-compared"),
        pytest.param("Instants count as simultaneous within 1 s.", id="simultaneous"),
    ],
)
def test_a_paraphrase_that_the_scan_does_not_name_is_not_refused(text: str) -> None:
    """Known limits: the scan reads the phrases that it names, not meaning. Each of
    these contradicts the policy and is not refused."""
    document = {"definition": {"limitations": [text]}}
    assert list(core._contradiction_findings("x", document)) == []


def test_one_text_states_each_contradiction_once() -> None:
    document = {
        "definition": {
            "limitations": ["The clocks are synchronized. The clocks are synchronized."]
        }
    }
    assert len(list(core._contradiction_findings("x", document))) == 1


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
    assert sorted(core.RULE_SETS) == [1, 2, 3, 4]
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


# --------------------------------------------------------------------------
# 5. The reversal timing of V2-E04
# --------------------------------------------------------------------------

E04_R1_PIN = "0dcc3b1c0cba1ee51acc962a083d78a82c42093a75fad72e41b193dde3124e5d"
INSTANTS_RULE = "prereg-reversal-instants"
INTERVALS_RULE = "prereg-reversal-intervals"
CRITERIA_RULE = "prereg-reversal-criteria"
TIMING_REASONS = "prereg-reversal-reasons"
TIMING = "definition.reversalTiming"
#: Where E04-AC8 and E04-AC12 are in the list of criteria.
AC8 = "fields.acceptanceCriteria[0].value[7]"
AC12 = "fields.acceptanceCriteria[0].value[11]"

#: The members in which V2-E04 revision 2 differs from its revision 1. A list is
#: one member, so a changed criterion or limitation moves its whole list.
E04_CHANGED_MEMBERS = {
    "metadata.revision",
    "metadata.registered",
    "metadata.registeredBy",
    "metadata.supersedes",
    "metadata.preregistrationRules",
    "definition.hypothesis",
    "definition.gitTransitions",
    "definition.detectionRule",
    "definition.reversalTiming.reversalStart",
    "definition.reversalTiming.recoveryEnd",
    "definition.reversalTiming.operatorDecisionMs",
    "definition.reversalTiming.split",
    "definition.reversalTiming.statement",
    "definition.reversalTiming.instants",
    "definition.reversalTiming.intervals",
    "definition.reversalTiming.operatorEvents",
    "definition.reversalTiming.events",
    "definition.limitations",
    "definition.history",
    "definition.preparation",
    "definition.window.clocks",
    "definition.clockPolicy",
    "definition.criterionClocks",
    "definition.criteriaWithoutClocks",
    "definition.measurements",
    "definition.outcomeRules",
    "exclusionReasons.reasons",
    "fields.experimentIdVersion",
    "fields.gitRevision",
    "fields.acceptanceCriteria",
    "pinnedInputs",
    "inputChanges",
}
#: The revision-1 sentence that put the discovery of the reversal commit in the
#: operator interval.
R1_DISCOVERY = (
    "The controller discovers a commit of main by its periodic reconciliation, so the "
    "time from reversal-accepted to reversalStart depends on its interval, and it is "
    "stated in the operator interval."
)


def timing_of(document: dict[str, Any]) -> dict[str, Any]:
    result = document["definition"]["reversalTiming"]
    assert isinstance(result, dict)
    return result


def criterion_of(document: dict[str, Any], identifier: str) -> dict[str, Any]:
    (result,) = [
        c for c in value(document, "acceptanceCriteria") if c["id"] == identifier
    ]
    assert isinstance(result, dict)
    return result


def test_revision_two_of_e04_names_each_instant_with_its_source_and_clock() -> None:
    timing = timing_of(load(E04))
    instants = timing["instants"]
    assert {k: (v["source"], v["clock"]) for k, v in instants.items()} == {
        "reversalStart": ("operator-event", "host"),
        "controllerObserved": ("collector-reading", "host"),
        "desiredStateRestored": ("collector-reading", "host"),
        "stabilizationOnset": ("caller-record", "node"),
        "stabilizedAt": ("caller-record", "node"),
    }
    start = instants["reversalStart"]
    assert (start["kind"], start["judgedAt"]) == ("git-visibility", "earlier")
    assert "not a controller observation" in start["definition"]
    assert "remote that the controller reads" in start["definition"]
    assert "reversal-created" in start["bracket"]["earlier"]["instant"]
    assert "immediately before the push" in start["bracket"]["earlier"]["instant"]
    assert "first read of main" in start["bracket"]["later"]["instant"]
    assert start["notEstablished"]["reason"] == "reversal-start-unconfirmed"
    onset = instants["stabilizationOnset"]
    assert onset["analysisMember"] == "stabilizedRecovery.span.first.finishedAt"
    assert onset["completedSpanOnly"] is True
    assert onset["after"] == "reversalStart"
    settled = instants["stabilizedAt"]
    assert settled["analysisMember"] == "stabilizedRecovery.stabilizedAt"
    assert settled["insideObservationLimit"] is True
    assert timing["recoveryEnd"] == "stabilizationOnset"
    assert "Synced" in instants["desiredStateRestored"]["definition"]


def test_revision_two_of_e04_names_each_interval_with_its_two_ends() -> None:
    timing = timing_of(load(E04))
    assert {
        name: (i["start"], i["end"], i["judged"], i["criterion"])
        for name, i in timing["intervals"].items()
    } == {
        "recoveryMs": ("reversalStart", "stabilizationOnset", True, "E04-AC12"),
        "gitopsDiscoveryMs": ("reversalStart", "controllerObserved", False, None),
        "operatorDecisionMs": ("detection-reviewed", "reversalStart", False, None),
    }
    assert timing["operatorEvents"] == [
        "detection-reviewed",
        "reversal-decided",
        "reversal-created",
        "reversal-accepted",
    ]
    operator = timing["intervals"]["operatorDecisionMs"]["statement"]
    assert "holds no discovery, reconciliation, or stabilization" in operator


def test_e04_ac12_judges_recovery_against_the_unchanged_q4_bound() -> None:
    document = load(E04)
    criterion = criterion_of(document, "E04-AC12")
    assert criterion["bound"] == "reversal_recovery_bound_ms"
    assert criterion["interval"] == "recoveryMs"
    assert criterion["boundValueMs"] == BOUND_VALUES["reversal_recovery_bound_ms"]
    assert criterion["boundFormula"] == "(2 * S) + 30000"
    assert criterion["boundRecord"] == {"path": BOUNDS, "contentSha256": BOUNDS_SHA256}
    (committed,) = [
        b for b in load(BOUNDS)["bounds"] if b["name"] == "reversal_recovery_bound_ms"
    ]
    assert (committed["formula"], committed["valueMs"]) == ("(2 * S) + 30000", 52_000)
    assert value(document, "derivedNumericBounds") == value(
        load(E04_R1), "derivedNumericBounds"
    )
    (entry,) = [
        e
        for e in document["definition"]["criterionClocks"]
        if e["criterion"] == "E04-AC12" and e["comparison"] == "interval"
    ]
    assert entry["bound"] == "reversal_recovery_bound_ms"
    assert [(i["source"], i["clock"]) for i in entry["instants"]] == [
        ("operator-event", "host"),
        ("caller-record", "node"),
    ]
    assert entry["crossClock"] is True


def test_the_q4_bound_record_is_the_only_one_and_unchanged() -> None:
    assert sorted(p.name for p in (REPO_ROOT / BOUNDS).parent.iterdir()) == [
        "bounds-r1.v1alpha1.json"
    ]
    assert content_digest((REPO_ROOT / BOUNDS).read_bytes()) == BOUNDS_SHA256


def test_e04_ac8_ends_its_window_at_desired_state_restoration() -> None:
    """Revision 1 ended the window at its reversalStart, the start of the last
    controller reading before the reversal commit was resolved. Revision 2 moves
    reversalStart earlier, to Git visibility, so the window ends later instead,
    when the desired state is restored."""
    one = criterion_of(load(E04_R1), "E04-AC8")
    two = criterion_of(load(E04), "E04-AC8")
    assert one["statement"].endswith(
        "from the fault-injection-started event to reversalStart."
    )
    assert two["window"] == {
        "from": "fault-injection-started",
        "to": "desiredStateRestored",
    }
    assert "to desiredStateRestored" in two["statement"]
    assert "reversalStart" not in two["statement"]
    assert two["statement"].startswith(one["statement"].split(" to reversalStart.")[0])


def test_revision_two_of_e04_differs_from_revision_one_only_in_the_listed_members() -> (
    None
):
    """A tripwire: every other member keeps its revision-1 value byte for byte."""
    one, two = load(E04_R1), load(E04)
    assert differences(one, two) == E04_CHANGED_MEMBERS
    criteria_1 = value(one, "acceptanceCriteria")
    criteria_2 = value(two, "acceptanceCriteria")
    assert [c["id"] for c in criteria_1] == [c["id"] for c in criteria_2]
    assert [
        c1["id"] for c1, c2 in zip(criteria_1, criteria_2, strict=True) if c1 != c2
    ] == ["E04-AC8", "E04-AC12"]
    definition_1, definition_2 = one["definition"], two["definition"]
    assert definition_2["detectionRule"]["rule"] == definition_1["detectionRule"]
    assert "22,000 ms" in definition_2["detectionRule"]["rule"]
    assert "22,000 ms" in definition_2["detectionRule"]["clocks"]
    transitions_1 = definition_1["gitTransitions"]
    transitions_2 = definition_2["gitTransitions"]
    assert (
        transitions_2[:2] + transitions_2[3:] == transitions_1[:2] + transitions_1[3:]
    )
    assert transitions_2[2].startswith("T3. ")
    assert definition_2["history"][:5] == definition_1["history"]
    assert len(definition_2["history"]) == 9
    limitations_1 = definition_1["limitations"]
    limitations_2 = definition_2["limitations"]
    assert limitations_1[2] == R1_LIMITATION
    assert limitations_1[-1] == R1_DISCOVERY
    assert limitations_2[:2] == limitations_1[:2]
    assert limitations_2[4:9] == limitations_1[3:8]
    assert R1_DISCOVERY not in limitations_2
    assert "inside recoveryMs" in limitations_2[9]
    assert len(limitations_2) == 15
    assert definition_2["measurements"][:-1] == definition_1["measurements"]
    rules_1 = definition_1["outcomeRules"]
    rules_2 = definition_2["outcomeRules"]
    assert rules_1[5] == R1_CLOCK_RULE
    assert rules_2[:5] + rules_2[7:] == rules_1[:5] + rules_1[6:]
    steps_1, steps_2 = definition_1["preparation"], definition_2["preparation"]
    assert steps_2[1:7] == steps_1[1:7]
    assert steps_2[0].startswith(steps_1[0])
    assert steps_2[0] == load(E02B)["definition"]["preparation"][0]
    assert "latest revision of its experiment" in steps_2[0]
    reasons_1 = {r["id"]: r for r in one["exclusionReasons"]["reasons"]}
    reasons_2 = {r["id"]: r for r in two["exclusionReasons"]["reasons"]}
    assert set(reasons_2) - set(reasons_1) == {
        "clock-reading-missing",
        "reversal-start-unconfirmed",
        "recovery-onset-not-after-reversal",
    }
    for reason, entry in reasons_1.items():
        if reason != "clock-bound-reached":
            assert reasons_2[reason] == entry
    assert len(reasons_2) == 12
    moved = {p["path"] for p in one["pinnedInputs"] if p not in two["pinnedInputs"]}
    assert sorted(moved) == CHECK_FILES
    assert [c["path"] for c in two["inputChanges"]] == CHECK_FILES
    assert [c["material"] for c in two["inputChanges"]] == [False, False, True]
    for field in ("fault", "topology", "repetitionCount", "abortConditions"):
        assert value(one, field) == value(two, field), field
    for member in ("setRules", "observation", "postRecoveryWindow"):
        assert definition_1[member] == definition_2[member], member


def test_no_text_of_revision_two_of_e04_puts_discovery_in_the_operator_interval() -> (
    None
):
    texts = [text for _, text in core._strings_in(load(E04), "")]
    assert not any("in the operator interval" in text for text in texts)
    assert "split" not in timing_of(load(E04))
    assert "split" in timing_of(load(E04_R1))


def test_the_history_of_e04_states_when_the_timing_was_chosen_and_amended() -> None:
    history = load(E04)["definition"]["history"]
    chosen, amended, consequence = history[6], history[7], history[8]
    assert "after the Q4 values were known" in chosen
    assert "no change control governed those choices" in chosen
    assert "change control on 2026-10-18" in amended
    assert "before any run of V2-E04" in amended
    assert "also after the Q4 values were known" in amended
    assert "stays 52,000 ms" in amended
    assert "Most runs are not expected to meet E04-AC12" in consequence


def test_revision_one_of_e04_is_kept_byte_for_byte() -> None:
    assert FROZEN_RECORDS[E04_R1] == E04_R1_PIN
    assert content_digest((REPO_ROOT / E04_R1).read_bytes()) == E04_R1_PIN
    rows = {row["path"]: row for row in load(REGISTRY)["records"]}
    assert rows[E04_R1] == {
        "path": E04_R1,
        "contentSha256": E04_R1_PIN,
        "registeredBy": "V2-S6-003-PR1",
    }
    assert rows[E04] == {
        "path": E04,
        "contentSha256": FROZEN_RECORDS[E04],
        "registeredBy": "V2-S6-005-PR1",
    }


def test_revision_one_of_e04_is_not_held_to_the_reversal_timing_rules(
    root: Path,
) -> None:
    """Rule set 1 reads no reversal timing, so a revision 1 without it still passes
    this check. The freeze check refuses the edit itself."""
    edit(root, E04_R1, lambda d: d["definition"].pop("reversalTiming"))
    assert found(root) == []


def _set(path: list[str], member: str, new: Any) -> Callable[[dict[str, Any]], None]:
    """A change that sets ``member`` of the object at ``path`` of the definition."""

    def change(document: dict[str, Any]) -> None:
        target: Any = document["definition"]
        for step in path:
            target = target[step]
        target[member] = new

    return change


def _drop(path: list[str], member: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        target: Any = document["definition"]
        for step in path:
            target = target[step]
        del target[member]

    return change


def _both(
    *changes: Callable[[dict[str, Any]], None],
) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        for one in changes:
            one(document)

    return change


def _criterion_member(
    identifier: str, member: str, new: Any
) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        criterion_of(document, identifier)[member] = new

    return change


def _ac12_clocks(
    change: Callable[[dict[str, Any]], None],
) -> Callable[[dict[str, Any]], None]:
    def wrapped(document: dict[str, Any]) -> None:
        (entry,) = [
            e
            for e in document["definition"]["criterionClocks"]
            if e["criterion"] == "E04-AC12" and e["comparison"] == "interval"
        ]
        change(entry)

    return wrapped


def _same_clock(entry: dict[str, Any]) -> None:
    """Both ends on the caller record, so the inventory reads it as same-clock."""
    entry["instants"][0].update(source="caller-record", clock="node")
    entry["crossClock"] = False


def _ac8_to_reversal_start(document: dict[str, Any]) -> None:
    criterion = criterion_of(document, "E04-AC8")
    criterion["window"] = {"from": "fault-injection-started", "to": "reversalStart"}
    criterion["statement"] = criterion_of(load(E04_R1), "E04-AC8")["statement"]


def _drop_reason(reason: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        reasons = document["exclusionReasons"]["reasons"]
        reasons[:] = [r for r in reasons if r["id"] != reason]

    return change


START = ["reversalTiming", "instants", "reversalStart"]
ONSET = ["reversalTiming", "instants", "stabilizationOnset"]
INTERVALS = ["reversalTiming", "intervals"]
START_AT = f"{TIMING}.instants.reversalStart"
ONSET_AT = f"{TIMING}.instants.stabilizationOnset"
AC12_CLOCKS = (
    "E04-AC12 does not declare one cross-clock interval of reversal_recovery_bound_ms, "
    "from reversalStart on the host clock to stabilizationOnset on the node clock"
)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        pytest.param(
            _both(
                _set(START, "kind", "controller-observation"),
                _set(START, "source", "collector-reading"),
            ),
            [
                (
                    INSTANTS_RULE,
                    START_AT,
                    "reversalStart is not stated with its definition, the source "
                    "operator-event, and the host clock",
                ),
                (
                    INSTANTS_RULE,
                    START_AT,
                    "reversalStart is not the Git-visibility instant: it is not stated "
                    "as git-visibility",
                ),
            ],
            id="reversal-start-is-a-controller-observation",
        ),
        pytest.param(
            _set(START, "judgedAt", "later"),
            [
                (
                    INSTANTS_RULE,
                    START_AT,
                    "reversalStart is not bracketed by two operator-event instants and "
                    "judged at the earlier end",
                )
            ],
            id="reversal-start-at-the-later-end",
        ),
        pytest.param(
            _set(["reversalTiming"], "recoveryEnd", "stabilizedAt"),
            [
                (
                    INSTANTS_RULE,
                    f"{TIMING}.recoveryEnd",
                    "recoveryEnd is not stabilizationOnset, the onset of the span",
                )
            ],
            id="recovery-end-is-stabilized-at",
        ),
        pytest.param(
            _set(ONSET, "completedSpanOnly", False),
            [
                (
                    INSTANTS_RULE,
                    ONSET_AT,
                    "stabilizationOnset is not held to a span that completed: an "
                    "interrupted span could establish a recovery",
                )
            ],
            id="recovery-end-from-a-span-that-did-not-complete",
        ),
        pytest.param(
            _set([*INTERVALS, "operatorDecisionMs"], "end", "controllerObserved"),
            [
                (
                    INTERVALS_RULE,
                    f"{TIMING}.intervals.operatorDecisionMs",
                    "operatorDecisionMs is not stated from detection-reviewed to "
                    "reversalStart, reported",
                )
            ],
            id="operator-interval-ends-at-controller-observed",
        ),
        pytest.param(
            _drop(INTERVALS, "gitopsDiscoveryMs"),
            [
                (
                    INTERVALS_RULE,
                    f"{TIMING}.intervals.gitopsDiscoveryMs",
                    "gitopsDiscoveryMs is not stated from reversalStart to "
                    "controllerObserved, reported",
                )
            ],
            id="gitops-discovery-removed",
        ),
        pytest.param(
            _drop(["reversalTiming", "instants"], "desiredStateRestored"),
            [
                (
                    INSTANTS_RULE,
                    f"{TIMING}.instants.desiredStateRestored",
                    "desiredStateRestored is not stated with its definition, the "
                    "source collector-reading, and the host clock",
                )
            ],
            id="desired-state-restored-removed",
        ),
        pytest.param(
            _criterion_member("E04-AC12", "boundValueMs", 60_000),
            [
                (
                    CRITERIA_RULE,
                    AC12,
                    "E04-AC12 states another value of reversal_recovery_bound_ms than "
                    "derivedNumericBounds",
                )
            ],
            id="bound-value",
        ),
        pytest.param(
            _criterion_member("E04-AC12", "boundFormula", "(2 * S) + 40000"),
            [
                (
                    CRITERIA_RULE,
                    AC12,
                    "E04-AC12 states another formula of reversal_recovery_bound_ms "
                    "than derivedNumericBounds",
                )
            ],
            id="bound-formula",
        ),
        pytest.param(
            _criterion_member(
                "E04-AC12", "boundRecord", {"path": BOUNDS, "contentSha256": "0" * 64}
            ),
            [
                (
                    CRITERIA_RULE,
                    AC12,
                    "E04-AC12 states another bound record of "
                    "reversal_recovery_bound_ms than derivedNumericBounds",
                )
            ],
            id="bound-record-digest",
        ),
        pytest.param(
            _ac12_clocks(lambda e: e.__setitem__("crossClock", False)),
            [
                (
                    INVENTORY,
                    "definition.criterionClocks[16]",
                    "it is declared same-clock, and its instants are on two clocks",
                ),
                (CRITERIA_RULE, "definition.criterionClocks", AC12_CLOCKS),
            ],
            id="declared-same-clock",
        ),
        pytest.param(
            _ac12_clocks(_same_clock),
            [(CRITERIA_RULE, "definition.criterionClocks", AC12_CLOCKS)],
            id="moved-to-one-clock",
        ),
        pytest.param(
            _ac8_to_reversal_start,
            [
                (
                    CRITERIA_RULE,
                    AC8,
                    "E04-AC8 does not end its window at desiredStateRestored",
                )
            ],
            id="containment-window-ends-at-reversal-start",
        ),
        pytest.param(
            _drop_reason("reversal-start-unconfirmed"),
            [
                (
                    TIMING_REASONS,
                    "exclusionReasons",
                    "reversal-start-unconfirmed is not registered for INCONCLUSIVE",
                )
            ],
            id="missing-confirmation-reason-removed",
        ),
        pytest.param(
            _drop(START, "notEstablished"),
            [
                (
                    INSTANTS_RULE,
                    f"{START_AT}.notEstablished",
                    "a reversalStart that is not established does not leave E04-AC12 "
                    "not judged, for reversal-start-unconfirmed",
                )
            ],
            id="missing-confirmation-rule-removed",
        ),
        pytest.param(
            _drop_reason("recovery-onset-not-after-reversal"),
            [
                (
                    TIMING_REASONS,
                    "exclusionReasons",
                    "recovery-onset-not-after-reversal is not registered for "
                    "INCONCLUSIVE",
                )
            ],
            id="onset-reason-removed",
        ),
        pytest.param(
            _set(ONSET, "analysisMember", "stabilizedRecovery.stabilizedAt"),
            [
                (
                    INSTANTS_RULE,
                    ONSET_AT,
                    "stabilizationOnset is not read from "
                    "stabilizedRecovery.span.first.finishedAt",
                )
            ],
            id="onset-read-from-stabilized-at",
        ),
        pytest.param(
            _drop(ONSET, "after"),
            [
                (
                    INSTANTS_RULE,
                    ONSET_AT,
                    "stabilizationOnset is not held to follow reversalStart, with "
                    "E04-AC12 not judged for recovery-onset-not-after-reversal "
                    "otherwise",
                )
            ],
            id="onset-not-held-after-reversal-start",
        ),
        pytest.param(
            _set(
                ["reversalTiming", "instants", "stabilizedAt"],
                "insideObservationLimit",
                False,
            ),
            [
                (
                    INSTANTS_RULE,
                    f"{TIMING}.instants.stabilizedAt",
                    "stabilizedAt is not read from stabilizedRecovery.stabilizedAt and "
                    "held inside the observation limit",
                )
            ],
            id="stabilized-at-outside-the-limit",
        ),
        pytest.param(
            _set([*INTERVALS, "recoveryMs"], "judged", False),
            [
                (
                    INTERVALS_RULE,
                    f"{TIMING}.intervals.recoveryMs",
                    "recoveryMs is not stated from reversalStart to stabilizationOnset, "
                    "judged by E04-AC12",
                )
            ],
            id="recovery-not-judged",
        ),
        pytest.param(
            _set(["reversalTiming"], "operatorEvents", ["detection-reviewed"]),
            [
                (
                    INTERVALS_RULE,
                    f"{TIMING}.operatorEvents",
                    "the four operator events of the reversal are not kept with their "
                    "own instants",
                )
            ],
            id="operator-events",
        ),
    ],
)
def test_each_reversal_timing_defect_is_refused(
    root: Path,
    change: Callable[[dict[str, Any]], None],
    expected: list[tuple[str, str, str]],
) -> None:
    edit(root, E04, change)
    assert found(root) == [
        (rule, E04, where, detail) for rule, where, detail in expected
    ]


def test_a_clock_policy_of_e04_that_differs_is_refused(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        policy_of(document)["statement"] += " E04 reads it differently."

    edit(root, E04, change)
    assert found(root) == [shared(E04, "definition.clockPolicy")]


def test_an_e04_of_rule_set_two_without_a_reversal_timing_is_refused(
    root: Path,
) -> None:
    edit(root, E04, lambda d: d["definition"].__setitem__("reversalTiming", "x"))
    assert found(root) == [
        ("prereg-record-shape", E04, "$", "definition states no reversal timing")
    ]


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(_set(["reversalTiming"], "instants", []), id="instants-a-list"),
        pytest.param(_set(["reversalTiming"], "intervals", "x"), id="intervals-text"),
        pytest.param(_set(START, "bracket", [1, 2]), id="bracket-a-list"),
        pytest.param(_set(START, "notEstablished", ["x"]), id="rule-a-list"),
        pytest.param(_set(START, "kind", ["git-visibility"]), id="kind-a-list"),
        pytest.param(_criterion_member("E04-AC12", "boundRecord", [1]), id="record"),
        pytest.param(_criterion_member("E04-AC12", "bound", ["x"]), id="bound"),
        pytest.param(_criterion_member("E04-AC8", "window", ["x"]), id="window"),
        pytest.param(_criterion_member("E04-AC8", "statement", ["x"]), id="statement"),
        pytest.param(
            _ac12_clocks(lambda e: e.__setitem__("instants", [1, 2])), id="ends"
        ),
    ],
)
def test_a_malformed_reversal_timing_is_a_finding_and_not_an_error(
    root: Path, change: Callable[[dict[str, Any]], None]
) -> None:
    edit(root, E04, change)
    findings = found(root)
    assert findings
    assert {f[1] for f in findings} == {E04}
    # Each finding is of a rule that reads the member, never another rule. A bound
    # that is not a string is refused by the shape rule before any rule reads it.
    assert {f[0] for f in findings} <= {
        "prereg-record-shape",
        INSTANTS_RULE,
        INTERVALS_RULE,
        CRITERIA_RULE,
        INVENTORY,
        "prereg-criterion-bound-unknown",
    }


# The analysis semantics that revision 2 names, on a synthetic run of
# tools/reliability_analysis: the committed zero-failure case of its suite.

ANALYSIS_CASE = (
    REPO_ROOT
    / "tests"
    / "domain"
    / "fixtures"
    / "reliability-analysis"
    / "zero-failure"
)


def _analysis_inputs() -> tuple[str, dict[str, str | None]]:
    declaration = (ANALYSIS_CASE / "declaration.json").read_text(encoding="utf-8")
    texts: dict[str, str | None] = {}
    for name in analysis.INPUTS:
        path = ANALYSIS_CASE / f"{name}.jsonl"
        texts[name] = path.read_text(encoding="utf-8") if path.is_file() else None
    return declaration, texts


def _at(document: Any, dotted: str) -> Any:
    """The member of a run analysis that a dotted path names, or None."""
    for step in dotted.split("."):
        if not isinstance(document, dict):
            return None
        document = document.get(step)
    return document


def _ms(instant: str) -> int:
    parsed = datetime.strptime(instant, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)


def test_the_onset_that_revision_two_names_is_the_start_of_a_completed_span() -> None:
    """stabilizationOnset is the completion of the first request of the span, and
    stabilizedAt that of the last. They differ by the length of the span, at least
    60 s, so the one cannot be read for the other."""
    instants = timing_of(load(E04))["instants"]
    onset_member = instants["stabilizationOnset"]["analysisMember"]
    settled_member = instants["stabilizedAt"]["analysisMember"]
    declaration, texts = _analysis_inputs()
    document = analysis.analyze(declaration, texts)
    recovery = document["stabilizedRecovery"]
    assert recovery["stabilized"] is True
    onset, settled = _at(document, onset_member), _at(document, settled_member)
    assert onset == recovery["span"]["first"]["finishedAt"]
    assert onset == "2026-10-12T08:00:51.000Z"
    assert settled == recovery["stabilizedAt"] == "2026-10-12T08:01:51.000Z"
    assert _ms(settled) - _ms(onset) == recovery["span"]["ms"] == 60_000
    assert recovery["span"]["successes"] >= 10


def test_an_interrupted_candidate_span_yields_no_recovery() -> None:
    """One failed completion inside the span of the committed case. The span that
    had started is interrupted, no later span completes inside the window, and the
    members that revision 2 names state no instant."""
    instants = timing_of(load(E04))["instants"]
    declaration, texts = _analysis_inputs()
    caller = texts["caller"]
    assert caller is not None
    lines = [json.loads(line) for line in caller.splitlines()]
    (failed,) = [
        line
        for line in lines
        if line.get("record") == "request"
        and line["finishedAt"] == "2026-10-12T08:01:30.000Z"
    ]
    failed.update(
        success=False,
        outcome="http-error",
        httpStatus=503,
        errorCode="adapter-unavailable",
        errorCondition="runtime-unreachable",
        finishReason=None,
        inputTokens=None,
        outputTokens=None,
    )
    (end,) = [line for line in lines if line.get("record") == "end"]
    end["outcomes"]["success"] -= 1
    end["outcomes"]["http-error"] += 1
    texts["caller"] = "".join(
        json.dumps(line, separators=(",", ":"), sort_keys=True) + "\n" for line in lines
    )
    document = analysis.analyze(declaration, texts)
    recovery = document["stabilizedRecovery"]
    assert (recovery["state"], recovery["stabilized"]) == ("computed", False)
    assert recovery["span"] is None
    assert recovery["stabilizedAt"] is None
    assert _at(document, instants["stabilizationOnset"]["analysisMember"]) is None
    assert _at(document, instants["stabilizedAt"]["analysisMember"]) is None


def test_rule_set_two_is_not_edited() -> None:
    """A tripwire: the four records of V2-S6-007-PR1 are read under rule set 2, so
    its statement and its rules stay as registered. Rule set 3 adds the reversal
    timing beside it."""
    assert core.RULE_SETS[2] == (
        "Rule set 1 and the clock rules: one clock policy for the node clock and the "
        "host clock, the clock of each instant that a criterion orders or measures, "
        "and no text that contradicts the policy."
    )
    for path in CLOCK_REVISIONS.values():
        document = load(path)
        assert document["metadata"]["preregistrationRules"] == 2
        # The rules would refuse each of them, and rule set 2 does not apply them.
        assert list(core._reversal_findings(path, document)) != []
    assert check_records({e: (p, load(p)) for e, p in RECORDS.items()}) == []


def test_a_record_of_another_experiment_under_rule_set_three_reads_as_rule_set_two(
    root: Path,
) -> None:
    """The reversal-timing rules read a V2-E04 record alone. The freeze check
    refuses the edit itself."""
    edit(root, E05, lambda d: d["metadata"].__setitem__("preregistrationRules", 3))
    assert found(root) == []


# The defects that the independent review of the first commit planted, and the
# clauses that its first suite left without a negative test.


def _duplicate(
    identifier: str, member: str, new: Any
) -> Callable[[dict[str, Any]], None]:
    """A defective criterion, with a conforming copy of it after it."""

    def change(document: dict[str, Any]) -> None:
        criteria = value(document, "acceptanceCriteria")
        conforming = copy.deepcopy(criterion_of(document, identifier))
        criterion_of(document, identifier)[member] = new
        criteria.append(conforming)

    return change


def _swap_bracket(document: dict[str, Any]) -> None:
    bracket = document["definition"]["reversalTiming"]["instants"]["reversalStart"][
        "bracket"
    ]
    earlier, later = bracket["earlier"]["instant"], bracket["later"]["instant"]
    bracket["earlier"]["instant"], bracket["later"]["instant"] = later, earlier


def _duplicate_ac12_clocks(document: dict[str, Any]) -> None:
    clocks = document["definition"]["criterionClocks"]
    (entry,) = [
        e
        for e in clocks
        if e["criterion"] == "E04-AC12" and e["comparison"] == "interval"
    ]
    clocks.append(copy.deepcopy(entry))


def _drop_ac12_clocks(document: dict[str, Any]) -> None:
    clocks = document["definition"]["criterionClocks"]
    clocks[:] = [
        e
        for e in clocks
        if not (e["criterion"] == "E04-AC12" and e["comparison"] == "interval")
    ]


def _outcome_without(reason: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        rules = document["definition"]["outcomeRules"]
        rules[:] = [r.replace(reason, "a reason") for r in rules]

    return change


CRITERIA = "fields.acceptanceCriteria"
PHRASES = "it does not hold the phrases "


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        pytest.param(
            _duplicate("E04-AC12", "boundValueMs", 1),
            [
                (CRITERIA_RULE, CRITERIA, "E04-AC12 is stated 2 times, and not once"),
                (
                    CRITERIA_RULE,
                    AC12,
                    "E04-AC12 states another value of reversal_recovery_bound_ms than "
                    "derivedNumericBounds",
                ),
            ],
            id="a-defective-recovery-criterion-before-a-conforming-copy",
        ),
        pytest.param(
            _duplicate("E04-AC8", "window", {"from": "x", "to": "reversalStart"}),
            [
                (CRITERIA_RULE, CRITERIA, "E04-AC8 is stated 2 times, and not once"),
                (
                    CRITERIA_RULE,
                    AC8,
                    "E04-AC8 does not end its window at desiredStateRestored",
                ),
            ],
            id="a-defective-containment-criterion-before-a-conforming-copy",
        ),
        pytest.param(
            _swap_bracket,
            [
                (
                    INSTANTS_RULE,
                    f"{START_AT}.bracket.earlier.instant",
                    PHRASES + "'reversal-created', 'immediately before the push'",
                ),
                (
                    INSTANTS_RULE,
                    f"{START_AT}.bracket.later.instant",
                    PHRASES + "'first read of main', 'reversal-accepted'",
                ),
            ],
            id="the-two-bracket-ends-swapped",
        ),
        pytest.param(
            _set(ONSET, "definition", "The stabilizedAt instant of the analysis."),
            [
                (
                    INSTANTS_RULE,
                    f"{ONSET_AT}.definition",
                    PHRASES + "'first request', 'starts after reversalStart', "
                    "'observed complete without interruption'",
                )
            ],
            id="an-onset-defined-as-stabilized-at",
        ),
        pytest.param(
            _set(
                START,
                "definition",
                "The first argo reading that resolves the reversal commit.",
            ),
            [
                (
                    INSTANTS_RULE,
                    f"{START_AT}.definition",
                    PHRASES + "'remote that the controller reads', "
                    "'not a controller observation'",
                )
            ],
            id="a-reversal-start-defined-as-a-controller-reading",
        ),
        pytest.param(
            _set(
                ["reversalTiming", "instants", "controllerObserved"],
                "source",
                "operator-event",
            ),
            [
                (
                    INSTANTS_RULE,
                    f"{TIMING}.instants.controllerObserved",
                    "controllerObserved is not stated with its definition, the source "
                    "collector-reading, and the host clock",
                )
            ],
            id="controller-observed-on-another-source",
        ),
        pytest.param(
            _set(["reversalTiming", "instants", "stabilizedAt"], "clock", "host"),
            [
                (
                    INSTANTS_RULE,
                    f"{TIMING}.instants.stabilizedAt",
                    "stabilizedAt is not stated with its definition, the source "
                    "caller-record, and the node clock",
                )
            ],
            id="stabilized-at-on-the-host-clock",
        ),
        pytest.param(
            _set([*ONSET, "notAfterReversalStart"], "reason", "clock-bound-reached"),
            [
                (
                    INSTANTS_RULE,
                    ONSET_AT,
                    "stabilizationOnset is not held to follow reversalStart, with "
                    "E04-AC12 not judged for recovery-onset-not-after-reversal "
                    "otherwise",
                )
            ],
            id="onset-rule-with-another-reason",
        ),
        pytest.param(
            _set(ONSET, "after", "controllerObserved"),
            [
                (
                    INSTANTS_RULE,
                    ONSET_AT,
                    "stabilizationOnset is not held to follow reversalStart, with "
                    "E04-AC12 not judged for recovery-onset-not-after-reversal "
                    "otherwise",
                )
            ],
            id="onset-after-another-instant",
        ),
        pytest.param(
            _criterion_member("E04-AC12", "interval", "gitopsDiscoveryMs"),
            [
                (
                    CRITERIA_RULE,
                    AC12,
                    "E04-AC12 does not judge recoveryMs against "
                    "reversal_recovery_bound_ms",
                )
            ],
            id="recovery-criterion-judges-another-interval",
        ),
        pytest.param(
            _criterion_member(
                "E04-AC8",
                "statement",
                "Every endpoints reading from the fault-injection-started event to "
                "reversalStart, and not to desiredStateRestored.",
            ),
            [
                (
                    CRITERIA_RULE,
                    AC8,
                    "E04-AC8 does not end its window at desiredStateRestored",
                )
            ],
            id="containment-statement-names-reversal-start",
        ),
        pytest.param(
            _outcome_without("reversal-start-unconfirmed"),
            [
                (
                    TIMING_REASONS,
                    "definition.outcomeRules",
                    "the outcome rules do not name reversal-start-unconfirmed",
                )
            ],
            id="outcome-rules-without-the-confirmation-reason",
        ),
        pytest.param(
            _duplicate_ac12_clocks,
            [(CRITERIA_RULE, "definition.criterionClocks", AC12_CLOCKS)],
            id="recovery-interval-declared-twice",
        ),
        pytest.param(
            _drop_ac12_clocks,
            [
                (
                    INVENTORY,
                    AC12,
                    "it names a bound and declares no clocks of its interval",
                ),
                (CRITERIA_RULE, "definition.criterionClocks", AC12_CLOCKS),
            ],
            id="recovery-interval-not-declared",
        ),
    ],
)
def test_each_reversal_timing_defect_of_the_review_is_refused(
    root: Path,
    change: Callable[[dict[str, Any]], None],
    expected: list[tuple[str, str, str]],
) -> None:
    edit(root, E04, change)
    assert found(root) == [
        (rule, E04, where, detail) for rule, where, detail in expected
    ]


def test_each_record_is_read_under_the_rule_set_it_was_registered_under() -> None:
    """A tripwire: rule set 3 changes the rule set of no registered record."""
    for path in REVISION_ONE.values():
        assert core._rule_set(path, load(path)) == 1, path
    for path in CLOCK_REVISIONS.values():
        assert core._rule_set(path, load(path)) == 2, path
    assert core._rule_set(E04, load(E04)) == 3
    assert core._rule_set(E04_R3, load(E04_R3)) == 4


# --------------------------------------------------------------------------
# 6. The selection of V2-E04 revision 3, and rule set 4
# --------------------------------------------------------------------------

SELECTION_RULE = "prereg-reversal-selection"
ONSET_RULE = "prereg-reversal-onset-exclusion"
UNMET_RULE = "prereg-reversal-unmet-recovery"
SELECTED_RULE = "prereg-reversal-selected-span"
REFERENCE_RULE = "prereg-reversal-outcome-reference"
CONTROLLER_RULE = "prereg-reversal-controller-discovery"
SELECTED_AT = f"{TIMING}.selection"
#: Where E04-AC5 is in the list of criteria.
AC5 = "fields.acceptanceCriteria[0].value[4]"
ONSET_REASON = "recovery-onset-not-after-reversal"
E04_R2_PIN = "fae41b8b244cda76e1325ff36e305705d620163bcfac8c1e7bffec2c61b1e619"

#: The members in which V2-E04 revision 3 differs from its revision 2. A list is
#: one member, so a changed criterion, criterion clock, or limitation moves its
#: whole list.
E04_R3_CHANGED_MEMBERS = {
    "metadata.revision",
    "metadata.registered",
    "metadata.registeredBy",
    "metadata.supersedes.path",
    "metadata.supersedes.contentSha256",
    "metadata.preregistrationRules",
    "definition.reversalTiming.statement",
    "definition.reversalTiming.selection",
    "definition.reversalTiming.controllerDiscovery",
    "definition.reversalTiming.instants.stabilizationOnset.analysisMember",
    "definition.reversalTiming.instants.stabilizationOnset.notAfterReversalStart",
    "definition.reversalTiming.instants.stabilizationOnset.selectedBy",
    "definition.reversalTiming.instants.stabilizationOnset.completion",
    "definition.reversalTiming.instants.stabilizedAt.analysisMember",
    "definition.reversalTiming.instants.stabilizedAt.selectedBy",
    "definition.reversalTiming.instants.stabilizedAt.definition",
    "definition.reversalTiming.instants.stabilizedAt.statement",
    "definition.observation",
    "definition.postRecoveryWindow",
    "definition.criterionClocks",
    "definition.outcomeRules",
    "definition.limitations",
    "definition.history",
    "exclusionReasons.reasons",
    "fields.experimentIdVersion",
    "fields.gitRevision",
    "fields.acceptanceCriteria",
    "materialScope.description",
    "materialScope.entryModules",
    "pinnedInputs",
    "inputChanges",
}


@pytest.fixture
def full_root(tmp_path: Path) -> Path:
    """A root that holds every file the check reads, with revision 3 of V2-E04."""
    for relative in (REGISTRY, QUALIFICATION, QUALIFICATION_1, BOUNDS, COMPARISON):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, target)
    for path in ALL_COMMITTED:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / path, target)
    return tmp_path


def selection_of(document: dict[str, Any]) -> dict[str, Any]:
    result = timing_of(document)["selection"]
    assert isinstance(result, dict)
    return result


def test_revision_three_holds_every_rule_of_rule_set_four(full_root: Path) -> None:
    assert found(full_root) == []
    document = load(E04_R3)
    assert core._rule_set(E04_R3, document) == core.SELECTION_RULE_SET == 4
    assert list(core._selection_findings(E04_R3, document)) == []
    assert list(core._clock_findings(E04_R3, document)) == []


def test_revision_three_differs_from_revision_two_only_in_the_listed_members() -> None:
    """A tripwire: every other member keeps its revision-2 value byte for byte."""
    two, three = load(E04), load(E04_R3)
    assert differences(two, three) == E04_R3_CHANGED_MEMBERS
    definition_2, definition_3 = two["definition"], three["definition"]
    assert definition_3["clockPolicy"] == definition_2["clockPolicy"]
    for member in (
        "hypothesis",
        "detectionRule",
        "gitTransitions",
        "preparation",
        "window",
        "measurements",
        "setRules",
        "executables",
        "analysisDeclaration",
        "repetitionRule",
    ):
        assert definition_3[member] == definition_2[member], member
    timing_2, timing_3 = timing_of(two), timing_of(three)
    for member in ("intervals", "operatorEvents", "events", "recoveryEnd"):
        assert timing_3[member] == timing_2[member], member
    for instant in ("reversalStart", "controllerObserved", "desiredStateRestored"):
        assert timing_3["instants"][instant] == timing_2["instants"][instant]
    criteria_2 = value(two, "acceptanceCriteria")
    criteria_3 = value(three, "acceptanceCriteria")
    assert [c["id"] for c in criteria_2] == [c["id"] for c in criteria_3]
    assert [
        c2["id"] for c2, c3 in zip(criteria_2, criteria_3, strict=True) if c2 != c3
    ] == ["E04-AC2", "E04-AC5", "E04-AC12"]
    # E04-AC2 loses its controller clause and gains the record of the accepted
    # reversal, by the change control of 2026-10-20, and nothing else.
    ac2_2, ac2_3 = criterion_of(two, "E04-AC2"), criterion_of(three, "E04-AC2")
    assert {k: v for k, v in ac2_3.items() if k != "statement"} == {
        k: v for k, v in ac2_2.items() if k != "statement"
    }
    clause = (
        ", and an argo reading reports the reversal commit as resolvedRevision "
        "inside the observation limit."
    )
    assert ac2_2["statement"].endswith(clause)
    assert ac2_3["statement"].startswith(ac2_2["statement"][: -len(clause)] + ". ")
    assert "argo" not in ac2_3["statement"]
    ac12_2, ac12_3 = criterion_of(two, "E04-AC12"), criterion_of(three, "E04-AC12")
    assert {k: v for k, v in ac12_3.items() if k != "statement"} == {
        k: v for k, v in ac12_2.items() if k != "statement"
    }
    assert criterion_of(three, "E04-AC5")["kind"] == "validity"
    assert criterion_of(three, "E04-AC8") == criterion_of(two, "E04-AC8")
    reasons_2 = two["exclusionReasons"]["reasons"]
    reasons_3 = three["exclusionReasons"]["reasons"]
    assert reasons_3 == [r for r in reasons_2 if r["id"] != ONSET_REASON]
    assert len(reasons_3) == 11
    rules_2, rules_3 = definition_2["outcomeRules"], definition_3["outcomeRules"]
    assert rules_3[:6] + rules_3[7:] == rules_2[:6] + rules_2[7:]
    clocks_2, clocks_3 = (
        definition_2["criterionClocks"],
        definition_3["criterionClocks"],
    )
    # Revision 3 drops the one criterion clock of E04-AC2 that read an argo reading.
    (removed,) = [
        e
        for e in clocks_2
        if e["criterion"] == "E04-AC2"
        and any(i["source"] != "operator-event" for i in e["instants"])
    ]
    assert clocks_2.index(removed) == 2
    clocks_2 = [e for e in clocks_2 if e is not removed]
    assert [
        i for i, (a, b) in enumerate(zip(clocks_2, clocks_3, strict=True)) if a != b
    ] == [6, 7, 15, 16, 17]
    limitations_2 = definition_2["limitations"]
    limitations_3 = definition_3["limitations"]
    (index,) = [i for i, text in enumerate(limitations_2) if ONSET_REASON in text]
    assert limitations_3[:index] == limitations_2[:index]
    assert limitations_3[index + 4 :] == limitations_2[index + 1 :]
    assert len(limitations_3) == len(limitations_2) + 3
    assert definition_3["history"][:9] == definition_2["history"]
    assert len(definition_3["history"]) == 13
    for field in (
        "fault",
        "topology",
        "repetitionCount",
        "abortConditions",
        "cleanupProcedure",
        "evidencePaths",
        "derivedNumericBounds",
        "environmentIdentity",
        "callerProfileRevision",
        "intendedEvidenceLevel",
    ):
        assert value(two, field) == value(three, field), field
    moved = [c["path"] for c in three["inputChanges"]]
    assert moved == [
        "tools/experiment_preregistration/core.py",
        "tools/reversal_outcome/__init__.py",
        "tools/reversal_outcome/core.py",
    ]
    assert [c["material"] for c in three["inputChanges"]] == [True, False, True]


def test_revision_two_is_kept_and_read_under_rule_set_three() -> None:
    """Revision 2 and its registry row are unchanged. It still registers the onset
    reason, and rule set 3 still requires it of revision 2."""
    assert FROZEN_RECORDS[E04] == E04_R2_PIN
    assert content_digest((REPO_ROOT / E04).read_bytes()) == E04_R2_PIN
    rows = {row["path"]: row for row in load(REGISTRY)["records"]}
    assert rows[E04] == {
        "path": E04,
        "contentSha256": E04_R2_PIN,
        "registeredBy": "V2-S6-005-PR1",
    }
    assert rows[E04_R3] == {
        "path": E04_R3,
        "contentSha256": E04_R3_PIN,
        "registeredBy": "V2-S6-008-PR1",
    }
    document = load(E04)
    assert core._rule_set(E04, document) == 3
    assert ONSET_REASON in {r["id"] for r in document["exclusionReasons"]["reasons"]}
    assert list(core._reversal_findings(E04, document)) == []
    without = copy.deepcopy(document)
    without["exclusionReasons"]["reasons"] = [
        r for r in without["exclusionReasons"]["reasons"] if r["id"] != ONSET_REASON
    ]
    assert [f.detail for f in core._reversal_findings(E04, without)] == [
        f"{ONSET_REASON} is not registered for INCONCLUSIVE"
    ]


def test_rule_set_four_does_not_read_revision_two_and_inherits_no_onset_rule() -> None:
    """Revision 2 fails every selection rule, so rule set 4 is not rule set 3 with
    rules added; and revision 3, which states no onset rule, passes rule set 4."""
    findings = {f.rule_id for f in core._selection_findings(E04, load(E04))}
    assert findings == {
        SELECTION_RULE,
        ONSET_RULE,
        UNMET_RULE,
        SELECTED_RULE,
        REFERENCE_RULE,
        CONTROLLER_RULE,
    }
    three = load(E04_R3)
    assert "notAfterReversalStart" not in json.dumps(three)
    assert list(core._selection_findings(E04_R3, three)) == []


def test_the_selection_of_revision_three_is_as_registered() -> None:
    selection = selection_of(load(E04_R3))
    assert selection["candidates"]["after"] == "reversalStart"
    assert selection["candidates"]["source"] == "caller-record"
    assert {k: v for k, v in selection["spanRule"].items() if k != "statement"} == {
        "tool": "tools/reliability_analysis",
        "function": "_find_span",
        "unchanged": True,
        "consecutiveSuccesses": analysis.STABILIZATION_SUCCESSES,
        "spanMs": analysis.STABILIZATION_SPAN_MS,
    }
    assert (selection["onset"]["instant"], selection["onset"]["request"]) == (
        "stabilizationOnset",
        "first",
    )
    assert (
        selection["stabilizedAt"]["instant"],
        selection["stabilizedAt"]["request"],
    ) == ("stabilizedAt", "last")
    assert selection["observationLimit"]["limitMs"] == 1_680_000
    assert selection["beforeReversalStart"]["selected"] is False
    assert selection["beforeReversalStart"]["reasonForVerdict"] is False
    assert [
        (o["id"], o["insideMargin"], o["resolutions"]) for o in selection["orders"]
    ] == [
        (
            "candidate-and-reversal-start",
            "both-ways",
            ["margin-as-after", "margin-as-before"],
        ),
        (
            "stabilized-at-and-observation-limit",
            "both-ways",
            ["margin-as-inside", "margin-as-outside"],
        ),
    ]
    assert selection["verdicts"]["differ"] == {
        "verdict": "not-judged",
        "reason": "clock-bound-reached",
        "stateDecidedBy": "definition.clockPolicy.notJudged",
    }
    assert selection["reported"]["resolution"] == "margin-as-before"
    assert selection["reported"]["otherwise"] == "margin-as-after"
    assert selection["endReading"]["noSpan"] == "not-met"
    assert selection["outcomeReference"]["module"] == "tools.reversal_outcome.core"
    assert (
        "never a reason to leave E04-AC12 not judged"
        in (selection["evidenceComputation"])
    )


def test_the_resolution_names_of_the_record_are_those_of_the_reference() -> None:
    """The record and tools/reversal_outcome name one set of resolutions."""
    from tools import reversal_outcome

    selection = selection_of(load(E04_R3))
    (candidates, limit) = selection["orders"]
    assert tuple(candidates["resolutions"]) == reversal_outcome.CANDIDATE_RESOLUTIONS
    assert tuple(limit["resolutions"]) == reversal_outcome.LIMIT_RESOLUTIONS
    assert selection["reported"]["resolution"] == reversal_outcome.REPORTED_RESOLUTION


def test_the_reasons_that_leave_e04_ac12_not_judged_are_exactly_three() -> None:
    document = load(E04_R3)
    leaving = {
        reason
        for _, reason in core._not_judged_members(
            {k: v for k, v in document.items() if k != "pinnedInputs"}, ""
        )
    }
    assert leaving == {"reversal-start-unconfirmed"}
    assert {
        "reversal-start-unconfirmed",
        "clock-bound-reached",
        "clock-reading-missing",
    } == core.RECOVERY_NOT_JUDGED_REASONS
    for location, text in core._outside_history(document):
        assert ONSET_REASON not in text, location
    history = " ".join(document["definition"]["history"])
    assert ONSET_REASON in history
    assert "found that the amended definition does not authorize it" in history


def test_the_check_does_not_import_the_outcome_reference() -> None:
    """So the pins of a record that does not name it do not gain it."""
    for path in ALL_RECORDS:
        pinned = {item["path"] for item in load(path)["pinnedInputs"]}
        assert not any(p.startswith("tools/reversal_outcome/") for p in pinned), path
    source = (REPO_ROOT / "tools/experiment_preregistration/core.py").read_text(
        encoding="utf-8"
    )
    assert "import tools.reversal_outcome" not in source
    assert "from tools.reversal_outcome" not in source


def _r3(*path: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def at(document: dict[str, Any]) -> dict[str, Any]:
        target: Any = document["definition"]
        for step in path:
            target = target[step]
        assert isinstance(target, dict)
        return target

    return at


def _plant(
    at: Callable[[dict[str, Any]], dict[str, Any]], member: str, new: Any
) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        at(document)[member] = new

    return change


def _remove(
    at: Callable[[dict[str, Any]], dict[str, Any]], member: str
) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        del at(document)[member]

    return change


def _register(reason: dict[str, str]) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document["exclusionReasons"]["reasons"].append(reason)

    return change


def _outcome_rule(text: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document["definition"]["outcomeRules"][6] += " " + text

    return change


def _statement(identifier: str, text: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        criterion_of(document, identifier)["statement"] = text

    return change


def _append_to_statement(
    identifier: str, text: str
) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        criterion_of(document, identifier)["statement"] += " " + text

    return change


def _clock_entry(
    index: int, change: Callable[[dict[str, Any]], None]
) -> Callable[[dict[str, Any]], None]:
    def wrapped(document: dict[str, Any]) -> None:
        change(document["definition"]["criterionClocks"][index])

    return wrapped


def _unpin_reference(document: dict[str, Any]) -> None:
    document["pinnedInputs"] = [
        p
        for p in document["pinnedInputs"]
        if not p["path"].startswith("tools/reversal_outcome/")
    ]


def _unscope_reference(document: dict[str, Any]) -> None:
    modules = document["materialScope"]["entryModules"]
    modules.remove("tools.reversal_outcome.core")


def _shorten_limit(document: dict[str, Any]) -> None:
    definition = document["definition"]
    definition["observation"] = definition["observation"].replace("1,680 s", "600 s")
    selection_of(document)["observationLimit"]["limitMs"] = 600_000


SELECTION = _r3("reversalTiming", "selection")
SELECTED_ONSET = _r3("reversalTiming", "instants", "stabilizationOnset")
SELECTED_STABILIZED = _r3("reversalTiming", "instants", "stabilizedAt")
START_R3 = _r3("reversalTiming", "instants", "reversalStart")
RECOVERY_R3 = _r3("reversalTiming", "intervals", "recoveryMs")
ONSET_SELECTION = (
    "stabilizationOnset does not name the selection of a completed span after "
    "reversalStart, or names a member of the run analysis"
)
ANOTHER_REASON = "it leaves E04-AC12 not judged for another reason"
NAMES_REASON = f"it names {ONSET_REASON}"
DOES_NOT_FOLLOW = "it states that the onset or a span does not follow reversalStart"


def _append_text(
    at: Callable[[dict[str, Any]], dict[str, Any]], member: str, text: str
) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        at(document)[member] += " " + text

    return change


def _duplicate_ac5(document: dict[str, Any]) -> None:
    criteria = value(document, "acceptanceCriteria")
    defective = copy.deepcopy(criterion_of(document, "E04-AC5"))
    defective["statement"] = criterion_of(load(E04), "E04-AC5")["statement"]
    criteria.append(defective)


# The defects that the independent review of the first commit planted: the
# exclusion in words that the first matcher did not name, in texts that it did not
# read, a reason of the timing that does not name E04-AC12, and a second E04-AC5.
REVIEW_DEFECTS = [
    pytest.param(
        _outcome_rule(
            "When the span starts before reversalStart, E04-AC12 is not judged."
        ),
        [(ONSET_RULE, "definition.outcomeRules[6]", DOES_NOT_FOLLOW)],
        id="a-span-before-reversal-start-not-judged",
    ),
    pytest.param(
        _outcome_rule(
            "When stabilizationOnset precedes reversalStart, the run is INCONCLUSIVE."
        ),
        [(ONSET_RULE, "definition.outcomeRules[6]", DOES_NOT_FOLLOW)],
        id="an-onset-that-precedes-reversal-start-inconclusive",
    ),
    pytest.param(
        _append_text(
            SELECTED_ONSET,
            "completion",
            "When stabilizationOnset precedes reversalStart, E04-AC12 is not judged.",
        ),
        [(ONSET_RULE, f"{ONSET_AT}.completion", DOES_NOT_FOLLOW)],
        id="the-exclusion-in-a-member-of-the-timing",
    ),
    pytest.param(
        lambda d: d["definition"].__setitem__(
            "observation",
            d["definition"]["observation"]
            + " A span that starts before reversalStart leaves E04-AC12 not judged.",
        ),
        [(ONSET_RULE, "definition.observation", DOES_NOT_FOLLOW)],
        id="the-exclusion-in-the-observation-limit",
    ),
    pytest.param(
        _register(
            {
                "id": "span-before-reversal",
                "resultState": "INCONCLUSIVE",
                "reason": "A span starts before reversalStart.",
            }
        ),
        [
            (
                ONSET_RULE,
                "exclusionReasons.reasons[11]",
                "span-before-reversal is a reason of the reversal timing beside "
                "reversal-start-unconfirmed",
            )
        ],
        id="a-reason-of-the-timing-that-does-not-name-e04-ac12",
    ),
    pytest.param(
        _duplicate_ac5,
        [
            (
                SELECTED_RULE,
                "fields.acceptanceCriteria",
                "E04-AC5 is stated 2 times, and not once",
            )
        ],
        id="a-defective-e04-ac5-beside-a-conforming-one",
    ),
]


@pytest.mark.parametrize(("change", "expected"), REVIEW_DEFECTS)
def test_each_selection_defect_of_the_review_is_refused(
    full_root: Path,
    change: Callable[[dict[str, Any]], None],
    expected: list[tuple[str, str, str]],
) -> None:
    edit(full_root, E04_R3, change)
    assert found(full_root) == [
        (rule, E04_R3, where, detail) for rule, where, detail in expected
    ]


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        pytest.param(
            _register(
                {
                    "id": ONSET_REASON,
                    "resultState": "INCONCLUSIVE",
                    "reason": "The span does not start after reversalStart.",
                }
            ),
            [
                (ONSET_RULE, "exclusionReasons", f"{ONSET_REASON} is registered"),
                (ONSET_RULE, "exclusionReasons.reasons[11].id", NAMES_REASON),
            ],
            id="the-onset-reason-registered",
        ),
        pytest.param(
            _outcome_rule(
                "When the span of the analysis is earlier, E04-AC12 is not judged, "
                f"for the reason {ONSET_REASON}."
            ),
            [
                (ONSET_RULE, "definition.outcomeRules[6]", NAMES_REASON),
                (ONSET_RULE, "definition.outcomeRules[6]", ANOTHER_REASON),
            ],
            id="the-onset-reason-in-an-outcome-rule",
        ),
        pytest.param(
            _append_to_statement(
                "E04-AC12", f"An earlier span is not judged, for {ONSET_REASON}."
            ),
            [(ONSET_RULE, f"{AC12}.statement", NAMES_REASON)],
            id="the-onset-reason-in-e04-ac12",
        ),
        pytest.param(
            _register(
                {
                    "id": "recovery-span-early",
                    "resultState": "INCONCLUSIVE",
                    "reason": "A span starts early, so E04-AC12 is not judged.",
                }
            ),
            [
                (
                    ONSET_RULE,
                    "exclusionReasons.reasons[11]",
                    "recovery-span-early leaves E04-AC12 not judged",
                )
            ],
            id="another-registered-reason-for-e04-ac12",
        ),
        pytest.param(
            _outcome_rule(
                "When a span starts early, E04-AC12 is not judged, for the reason "
                "recovery-span-early."
            ),
            [(ONSET_RULE, "definition.outcomeRules[6]", ANOTHER_REASON)],
            id="another-unregistered-reason-in-an-outcome-rule",
        ),
        pytest.param(
            _plant(
                SELECTION,
                "earlySpan",
                {
                    "criterion": "E04-AC12",
                    "verdict": "not-judged",
                    "reason": "recovery-span-early",
                },
            ),
            [(ONSET_RULE, f"{SELECTED_AT}.earlySpan", ANOTHER_REASON)],
            id="another-member-that-leaves-e04-ac12-not-judged",
        ),
        pytest.param(
            _plant(
                SELECTED_ONSET,
                "analysisMember",
                "stabilizedRecovery.span.first.finishedAt",
            ),
            [(SELECTION_RULE, ONSET_AT, ONSET_SELECTION)],
            id="the-onset-read-from-the-search-after-the-fault",
        ),
        pytest.param(
            _plant(
                _r3("reversalTiming", "selection", "candidates"),
                "after",
                "fault-injection-finished",
            ),
            [
                (
                    SELECTION_RULE,
                    f"{SELECTED_AT}.candidates",
                    "the candidates are not the caller completions after reversalStart",
                )
            ],
            id="candidates-from-the-fault",
        ),
        pytest.param(
            _plant(
                _r3("reversalTiming", "selection", "beforeReversalStart"),
                "selected",
                True,
            ),
            [
                (
                    SELECTION_RULE,
                    f"{SELECTED_AT}.beforeReversalStart",
                    "a span that starts before reversalStart is not held from the "
                    "selection and from every verdict",
                )
            ],
            id="a-span-before-reversal-start-admitted",
        ),
        pytest.param(
            lambda d: selection_of(d)["orders"].pop(),
            [
                (
                    SELECTION_RULE,
                    f"{SELECTED_AT}.orders",
                    "the order stabilized-at-and-observation-limit is not stated once "
                    "and resolved both ways inside the margin",
                ),
                (
                    SELECTION_RULE,
                    f"{SELECTED_AT}.orders",
                    "the orders are not exactly the two of the selection",
                ),
            ],
            id="the-two-way-rule-of-the-limit-removed",
        ),
        pytest.param(
            lambda d: selection_of(d)["orders"][0].__setitem__(
                "insideMargin", "not-judged"
            ),
            [
                (
                    SELECTION_RULE,
                    f"{SELECTED_AT}.orders",
                    "the order candidate-and-reversal-start is not stated once and "
                    "resolved both ways inside the margin",
                )
            ],
            id="always-not-judged-inside-the-margin",
        ),
        pytest.param(
            lambda d: selection_of(d)["reported"].__setitem__(
                "resolution", "margin-as-after"
            ),
            [
                (
                    SELECTION_RULE,
                    f"{SELECTED_AT}.reported",
                    "the reported span is not that of the resolution that counts only "
                    "the completions ordered after reversalStart",
                )
            ],
            id="the-reported-span-understates-recovery",
        ),
        pytest.param(
            _statement(
                "E04-AC12",
                "recoveryMs is at most reversal_recovery_bound_ms, 52,000 ms. When "
                "reversalStart is not established, the criterion is not judged, for "
                "the reason reversal-start-unconfirmed.",
            ),
            [
                (
                    UNMET_RULE,
                    AC12,
                    "E04-AC12 does not state that it is not met when no span that "
                    "starts after reversalStart completes inside the observation limit",
                )
            ],
            id="the-no-span-clause-of-e04-ac12-removed",
        ),
        pytest.param(
            _criterion_member("E04-AC12", "kind", "validity"),
            [(UNMET_RULE, AC12, "E04-AC12 is not a pass criterion")],
            id="e04-ac12-made-a-validity-criterion",
        ),
        pytest.param(
            lambda d: d["definition"]["outcomeRules"].__setitem__(
                6,
                "When reversalStart is not established, E04-AC12 is not judged, for "
                "the reason reversal-start-unconfirmed.",
            ),
            [
                (
                    UNMET_RULE,
                    "definition.outcomeRules",
                    "the outcome rules do not state that E04-AC12 is not met when no "
                    "span that starts after reversalStart completes inside the "
                    "observation limit",
                )
            ],
            id="the-no-span-outcome-rule-removed",
        ),
        pytest.param(
            _statement(
                "E04-AC5",
                "When the analysis states a stabilized recovery inside the "
                "observation limit, at least 10 successful requests complete after "
                "the stabilizedAt instant inside the window, and the last of them "
                "completes at least 60 s after it.",
            ),
            [
                (
                    SELECTED_RULE,
                    AC5,
                    "E04-AC5 is not a validity criterion of the selected span",
                )
            ],
            id="e04-ac5-on-the-span-of-the-analysis",
        ),
        pytest.param(
            _plant(
                SELECTED_STABILIZED, "analysisMember", "stabilizedRecovery.stabilizedAt"
            ),
            [
                (
                    SELECTED_RULE,
                    f"{TIMING}.instants.stabilizedAt",
                    "stabilizedAt does not name the selected span, or names a member of "
                    "the run analysis",
                )
            ],
            id="stabilized-at-from-the-analysis",
        ),
        pytest.param(
            lambda d: d["definition"].__setitem__(
                "postRecoveryWindow",
                load(E04)["definition"]["postRecoveryWindow"],
            ),
            [
                (
                    SELECTED_RULE,
                    "definition.postRecoveryWindow",
                    "it does not name the selected span, or names the stabilized "
                    "recovery that the analysis states",
                )
            ],
            id="the-post-recovery-window-of-revision-two",
        ),
        pytest.param(
            _shorten_limit,
            [
                (
                    SELECTION_RULE,
                    f"{SELECTED_AT}.observationLimit",
                    "the observation limit is not 1,680,000 ms after "
                    "fault-injection-finished, as definition.observation states it",
                )
            ],
            id="the-observation-limit-shortened",
        ),
        pytest.param(
            _ac8_to_reversal_start,
            [
                (
                    CRITERIA_RULE,
                    AC8,
                    "E04-AC8 does not end its window at desiredStateRestored",
                )
            ],
            id="the-containment-window-changed",
        ),
        pytest.param(
            _criterion_member("E04-AC12", "boundValueMs", 60_000),
            [
                (
                    CRITERIA_RULE,
                    AC12,
                    "E04-AC12 states another value of reversal_recovery_bound_ms than "
                    "derivedNumericBounds",
                )
            ],
            id="the-bound-value-changed",
        ),
        pytest.param(
            _criterion_member("E04-AC12", "boundFormula", "(2 * S) + 40000"),
            [
                (
                    CRITERIA_RULE,
                    AC12,
                    "E04-AC12 states another formula of reversal_recovery_bound_ms "
                    "than derivedNumericBounds",
                )
            ],
            id="the-bound-formula-changed",
        ),
        pytest.param(
            _criterion_member(
                "E04-AC12", "boundRecord", {"path": BOUNDS, "contentSha256": "0" * 64}
            ),
            [
                (
                    CRITERIA_RULE,
                    AC12,
                    "E04-AC12 states another bound record of "
                    "reversal_recovery_bound_ms than derivedNumericBounds",
                )
            ],
            id="the-bound-record-digest-changed",
        ),
        pytest.param(
            lambda d: policy_of(d).__setitem__(
                "statement", policy_of(d)["statement"] + " E04 reads it differently."
            ),
            [
                (
                    "prereg-shared-differs",
                    "definition.clockPolicy",
                    "it differs from V2-E02B",
                )
            ],
            id="a-clock-policy-that-differs",
        ),
        pytest.param(
            _unpin_reference,
            [(REFERENCE_RULE, "pinnedInputs", "the outcome reference is not pinned")],
            id="the-outcome-reference-not-pinned",
        ),
        pytest.param(
            _unscope_reference,
            [
                (
                    REFERENCE_RULE,
                    "materialScope.entryModules",
                    "the scope does not name the outcome reference",
                )
            ],
            id="the-outcome-reference-not-in-the-scope",
        ),
        pytest.param(
            lambda d: selection_of(d)["outcomeReference"].__setitem__(
                "function", "outcome"
            ),
            [
                (
                    REFERENCE_RULE,
                    f"{SELECTED_AT}.outcomeReference",
                    "the selection does not name reversal_outcome of "
                    "tools.reversal_outcome.core",
                )
            ],
            id="another-outcome-reference",
        ),
        pytest.param(
            _plant(START_R3, "kind", "controller-observation"),
            [
                (
                    INSTANTS_RULE,
                    f"{TIMING}.instants.reversalStart",
                    "reversalStart is not the Git-visibility instant: it is not stated "
                    "as git-visibility",
                )
            ],
            id="the-reversal-start-kind-changed",
        ),
        pytest.param(
            _swap_bracket,
            [
                (
                    INSTANTS_RULE,
                    f"{TIMING}.instants.reversalStart.bracket.earlier.instant",
                    PHRASES + "'reversal-created', 'immediately before the push'",
                ),
                (
                    INSTANTS_RULE,
                    f"{TIMING}.instants.reversalStart.bracket.later.instant",
                    PHRASES + "'first read of main', 'reversal-accepted'",
                ),
            ],
            id="the-reversal-start-bracket-swapped",
        ),
        pytest.param(
            _plant(START_R3, "judgedAt", "later"),
            [
                (
                    INSTANTS_RULE,
                    f"{TIMING}.instants.reversalStart",
                    "reversalStart is not bracketed by two operator-event instants and "
                    "judged at the earlier end",
                )
            ],
            id="the-reversal-start-judged-at-the-later-end",
        ),
        pytest.param(
            _plant(RECOVERY_R3, "end", "stabilizedAt"),
            [
                (
                    INTERVALS_RULE,
                    f"{TIMING}.intervals.recoveryMs",
                    "recoveryMs is not stated from reversalStart to stabilizationOnset, "
                    "judged by E04-AC12",
                )
            ],
            id="the-recovery-interval-changed",
        ),
        pytest.param(
            _append_to_statement(
                "E04-AC12",
                "When stabilizationOnset does not follow it, the criterion is not "
                "judged.",
            ),
            [(ONSET_RULE, AC12, DOES_NOT_FOLLOW)],
            id="the-ac12-clause-of-the-exclusion-without-its-reason",
        ),
        pytest.param(
            _clock_entry(
                16,
                lambda e: e.update(
                    instants=[
                        e["instants"][0],
                        {
                            "instant": "stabilizationOnset, the completion instant of "
                            "the first request of the selected span",
                            "source": "caller-record",
                            "clock": "node",
                        },
                    ],
                    statement="stabilizationOnset follows reversalStart, and inside "
                    "the margin the verdict is not judged.",
                ),
            ),
            [
                (
                    ONSET_RULE,
                    "definition.criterionClocks[16]",
                    "an order of E04-AC12 orders stabilizationOnset",
                ),
                (
                    ONSET_RULE,
                    "definition.criterionClocks[16]",
                    "an order of E04-AC12 is not resolved both ways",
                ),
            ],
            id="the-order-entry-of-the-exclusion",
        ),
        pytest.param(
            _outcome_rule(
                "When stabilizationOnset does not follow reversalStart, E04-AC12 is "
                "not judged, and definition.clockPolicy.notJudged decides the state."
            ),
            [(ONSET_RULE, "definition.outcomeRules[6]", DOES_NOT_FOLLOW)],
            id="the-outcome-rule-of-the-exclusion-without-its-reason",
        ),
        pytest.param(
            _plant(
                SELECTED_ONSET,
                "notAfterReversalStart",
                {
                    "reason": "clock-bound-reached",
                    "criterion": "E04-AC12",
                    "verdict": "not-judged",
                    "statement": "Not judged when the onset is earlier.",
                },
            ),
            [
                (
                    ONSET_RULE,
                    f"{ONSET_AT}.notAfterReversalStart",
                    "it is a notAfterReversalStart member",
                )
            ],
            id="the-onset-member-under-an-allowed-reason",
        ),
        pytest.param(
            _remove(SELECTION, "evidenceComputation"),
            [
                (
                    REFERENCE_RULE,
                    f"{SELECTED_AT}.evidenceComputation",
                    "it does not state that code which computes the selection from "
                    "evidence is pinned before the first result-bearing run",
                )
            ],
            id="the-evidence-computation-rule-removed",
        ),
        pytest.param(
            lambda d: d["metadata"].__setitem__("preregistrationRules", 3),
            [
                (
                    "prereg-rule-set-unknown",
                    "metadata.preregistrationRules",
                    "a V2-E04 record after revision 2 states no rule set of 4 or later "
                    "that this check knows",
                )
            ],
            id="revision-three-under-rule-set-three",
        ),
    ],
)
def test_each_selection_defect_of_revision_three_is_refused(
    full_root: Path,
    change: Callable[[dict[str, Any]], None],
    expected: list[tuple[str, str, str]],
) -> None:
    edit(full_root, E04_R3, change)
    assert found(full_root) == [
        (rule, E04_R3, where, detail) for rule, where, detail in expected
    ]


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(_plant(SELECTION, "orders", "x"), id="orders-text"),
        pytest.param(_plant(SELECTION, "orders", [1, [2]]), id="orders-unhashable"),
        pytest.param(_plant(SELECTION, "candidates", ["x"]), id="candidates-a-list"),
        pytest.param(_plant(SELECTION, "outcomeReference", 3), id="reference-a-number"),
        pytest.param(
            _plant(_r3("reversalTiming"), "selection", []), id="selection-a-list"
        ),
        pytest.param(_plant(SELECTED_ONSET, "definition", ["x"]), id="onset-a-list"),
        pytest.param(
            lambda d: d["definition"].__setitem__("observation", {"x": 1}),
            id="observation-an-object",
        ),
        pytest.param(
            lambda d: d["exclusionReasons"]["reasons"].append({"id": ["x"]}),
            id="reason-id-a-list",
        ),
        pytest.param(
            lambda d: d["materialScope"].__setitem__("entryModules", "x"),
            id="modules-text",
        ),
        pytest.param(_criterion_member("E04-AC5", "statement", 5), id="ac5-a-number"),
        pytest.param(
            lambda d: timing_of(d)["instants"]["reversalStart"][
                "notEstablished"
            ].__setitem__("reason", []),
            id="not-established-reason-a-list",
        ),
        pytest.param(
            lambda d: timing_of(d)["instants"]["reversalStart"][
                "notEstablished"
            ].__setitem__("reason", {"x": 1}),
            id="not-established-reason-an-object",
        ),
    ],
)
def test_a_malformed_selection_is_a_finding_and_not_an_error(
    full_root: Path, change: Callable[[dict[str, Any]], None]
) -> None:
    edit(full_root, E04_R3, change)
    findings = found(full_root)
    assert findings
    assert {f[1] for f in findings} == {E04_R3}


# --------------------------------------------------------------------------
# 7. The controller's discovery of the reversal is no condition of validity
# --------------------------------------------------------------------------

AC2_AT = "fields.acceptanceCriteria[0].value[1]"
VALIDITY_DETAIL = (
    "it makes the controller's discovery of the reversal a condition of validity"
)
EXCLUDING_DETAIL = (
    "it leaves a verdict not judged, or a run INCONCLUSIVE or aborted, on the "
    "controller's discovery of the reversal"
)
DISCOVERY_AT = "definition.reversalTiming.controllerDiscovery"
DISCOVERY_DETAIL = (
    "the controller's discovery of the reversal is not stated as part of "
    "recoveryMs, judged by E04-AC12 and by no validity criterion"
)
EVENTS_DETAIL = (
    "E04-AC2 is not the validity criterion of the operator events of the reversal "
    "and the reversal commit"
)


def _restore_ac2(document: dict[str, Any]) -> None:
    """E04-AC2 as revision 2 states it, with the controller clause."""
    criterion_of(document, "E04-AC2")["statement"] = criterion_of(load(E04), "E04-AC2")[
        "statement"
    ]


def _restore_ac2_clock(document: dict[str, Any]) -> None:
    """The criterion clock of E04-AC2 that revision 2 states for its argo reading."""
    entry = load(E04)["definition"]["criterionClocks"][2]
    assert entry["criterion"] == "E04-AC2"
    document["definition"]["criterionClocks"].insert(2, entry)


def _add_to(identifier: str, text: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        criterion_of(document, identifier)["statement"] += " " + text

    return change


def _abort(text: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        value(document, "abortConditions").append(text)

    return change


def _rule(text: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document["definition"]["outcomeRules"].append(text)

    return change


def _discovery(member: str, new: Any) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        timing_of(document)["controllerDiscovery"][member] = new

    return change


def _restored(document: dict[str, Any]) -> None:
    instants = timing_of(document)["instants"]
    instants["desiredStateRestored"]["notEstablished"] += (
        " When desiredStateRestored is not established, the run is INCONCLUSIVE."
    )


def _r3_append_clock_policy(text: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document["definition"]["clockPolicy"]["notJudged"]["rule"] += " " + text

    return change


CONTROLLER_DEFECTS = [
    pytest.param(
        _restore_ac2,
        [(CONTROLLER_RULE, f"{AC2_AT}.statement", VALIDITY_DETAIL)],
        id="the-clause-of-revision-two-restored-to-e04-ac2",
    ),
    pytest.param(
        _restore_ac2_clock,
        [
            (
                CONTROLLER_RULE,
                "definition.criterionClocks[2]",
                "an order of E04-AC2 reads a source other than the operator events",
            ),
            (
                CONTROLLER_RULE,
                "definition.criterionClocks[2].statement",
                VALIDITY_DETAIL,
            ),
        ],
        id="the-argo-clock-of-revision-two-restored-to-e04-ac2",
    ),
    pytest.param(
        _add_to(
            "E04-AC2",
            "The controller resolves the reversal commit inside the observation limit.",
        ),
        [(CONTROLLER_RULE, f"{AC2_AT}.statement", VALIDITY_DETAIL)],
        id="the-clause-in-other-words",
    ),
    pytest.param(
        _add_to(
            "E04-AC3",
            "The argo stream reports the commit of the revert as resolvedRevision.",
        ),
        [
            (
                CONTROLLER_RULE,
                "fields.acceptanceCriteria[0].value[2].statement",
                VALIDITY_DETAIL,
            )
        ],
        id="the-clause-moved-to-another-validity-criterion",
    ),
    pytest.param(
        _add_to("E04-AC4", "Argo CD discovers the known-good revision."),
        [
            (
                CONTROLLER_RULE,
                "fields.acceptanceCriteria[0].value[3].statement",
                VALIDITY_DETAIL,
            )
        ],
        id="the-known-good-revision-in-a-validity-criterion",
    ),
    pytest.param(
        _register(
            {
                "id": "reversal-not-discovered",
                "resultState": "INCONCLUSIVE",
                "reason": "The controller never resolves the reversal commit inside "
                "the observation limit.",
            }
        ),
        [(CONTROLLER_RULE, "exclusionReasons.reasons[11].reason", VALIDITY_DETAIL)],
        id="an-exclusion-reason-for-a-controller-that-does-not-discover",
    ),
    pytest.param(
        _abort("The controller does not resolve the reversal commit in 600 s."),
        [(CONTROLLER_RULE, "fields.abortConditions[0].value[11]", VALIDITY_DETAIL)],
        id="an-abort-condition-for-a-controller-that-does-not-discover",
    ),
    pytest.param(
        _rule(
            "When the controller never resolves the commit, the run is INCONCLUSIVE."
        ),
        [(CONTROLLER_RULE, "definition.outcomeRules[8]", EXCLUDING_DETAIL)],
        id="an-outcome-rule-that-leaves-the-run-inconclusive",
    ),
    pytest.param(
        _add_to(
            "E04-AC12",
            "When controllerObserved is not stated, the criterion is not judged.",
        ),
        [(CONTROLLER_RULE, f"{AC12}.statement", EXCLUDING_DETAIL)],
        id="e04-ac12-not-judged-without-the-controller",
    ),
    pytest.param(
        _restored,
        [
            (
                CONTROLLER_RULE,
                "definition.reversalTiming.instants.desiredStateRestored.notEstablished",
                EXCLUDING_DETAIL,
            )
        ],
        id="a-restored-state-that-is-not-established-leaves-the-run-inconclusive",
    ),
    pytest.param(
        _remove(_r3("reversalTiming"), "controllerDiscovery"),
        [(CONTROLLER_RULE, DISCOVERY_AT, DISCOVERY_DETAIL)],
        id="the-discovery-member-removed",
    ),
    pytest.param(
        _discovery("validity", True),
        [(CONTROLLER_RULE, DISCOVERY_AT, DISCOVERY_DETAIL)],
        id="the-discovery-a-condition-of-validity",
    ),
    pytest.param(
        _discovery("judgedBy", "E04-AC2"),
        [(CONTROLLER_RULE, DISCOVERY_AT, DISCOVERY_DETAIL)],
        id="the-discovery-judged-by-e04-ac2",
    ),
    pytest.param(
        _discovery("notDiscovered", "not-judged"),
        [(CONTROLLER_RULE, DISCOVERY_AT, DISCOVERY_DETAIL)],
        id="a-controller-that-does-not-discover-leaves-e04-ac12-not-judged",
    ),
    pytest.param(
        _criterion_member("E04-AC2", "kind", "pass"),
        [(CONTROLLER_RULE, AC2_AT, EVENTS_DETAIL)],
        id="e04-ac2-made-a-pass-criterion",
    ),
    pytest.param(
        _criterion_member(
            "E04-AC2",
            "statement",
            "The operator events detection-reviewed, reversal-decided, and "
            "reversal-created are recorded in that order, with the reversal commit.",
        ),
        [(CONTROLLER_RULE, AC2_AT, EVENTS_DETAIL)],
        id="e04-ac2-without-reversal-accepted",
    ),
    # The defects that the independent review of the third commit planted: a modal or
    # a passive paraphrase, a state that only the controller sets, a verdict after a
    # semicolon, and a controller condition in the clock policy.
    pytest.param(
        _add_to("E04-AC2", "Argo CD must sync the reversal commit."),
        [(CONTROLLER_RULE, f"{AC2_AT}.statement", VALIDITY_DETAIL)],
        id="a-modal-paraphrase-in-e04-ac2",
    ),
    pytest.param(
        _add_to("E04-AC3", "Argo CD detects the reversal."),
        [
            (
                CONTROLLER_RULE,
                "fields.acceptanceCriteria[0].value[2].statement",
                VALIDITY_DETAIL,
            )
        ],
        id="a-detection-of-the-reversal-in-a-validity-criterion",
    ),
    pytest.param(
        _add_to("E04-AC4", "The Application reports Synced at the end of the window."),
        [
            (
                CONTROLLER_RULE,
                "fields.acceptanceCriteria[0].value[3].statement",
                VALIDITY_DETAIL,
            )
        ],
        id="a-sync-state-in-a-validity-criterion-without-the-reversal",
    ),
    pytest.param(
        _rule("Argo CD must discover the reversal; otherwise the run is INCONCLUSIVE."),
        [(CONTROLLER_RULE, "definition.outcomeRules[8]", EXCLUDING_DETAIL)],
        id="a-verdict-after-a-semicolon",
    ),
    pytest.param(
        _rule("If the reversal is not discovered, the run is inconclusive."),
        [(CONTROLLER_RULE, "definition.outcomeRules[8]", EXCLUDING_DETAIL)],
        id="a-passive-paraphrase-in-lower-case",
    ),
]


@pytest.mark.parametrize(("change", "expected"), CONTROLLER_DEFECTS)
def test_each_controller_discovery_defect_is_refused(
    full_root: Path,
    change: Callable[[dict[str, Any]], None],
    expected: list[tuple[str, str, str]],
) -> None:
    edit(full_root, E04_R3, change)
    assert found(full_root) == [
        (rule, E04_R3, where, detail) for rule, where, detail in expected
    ]


def test_a_controller_condition_in_the_clock_policy_is_refused(
    full_root: Path,
) -> None:
    """The clock policy is shared, so the shared and the clock rules refuse the edit
    too; the controller rule refuses it on its own text."""
    edit(
        full_root,
        E04_R3,
        _r3_append_clock_policy(
            "When the controller never resolves the reversal commit, the run is "
            "INCONCLUSIVE."
        ),
    )
    assert (
        CONTROLLER_RULE,
        E04_R3,
        "definition.clockPolicy.notJudged.rule",
        EXCLUDING_DETAIL,
    ) in found(full_root)


def test_revision_three_states_the_controller_discovery_as_recovery() -> None:
    document = load(E04_R3)
    discovery = timing_of(document)["controllerDiscovery"]
    assert {k: v for k, v in discovery.items() if k != "statement"} == dict(
        core.CONTROLLER_DISCOVERY_MEMBERS
    )
    assert "FAILED" in discovery["statement"]
    ac2 = criterion_of(document, "E04-AC2")
    assert ac2["kind"] == "validity"
    clocks = [
        e
        for e in document["definition"]["criterionClocks"]
        if e["criterion"] == "E04-AC2"
    ]
    assert len(clocks) == 1
    assert {i["source"] for i in clocks[0]["instants"]} == {"operator-event"}
    reasons = {r["id"] for r in document["exclusionReasons"]["reasons"]}
    assert reasons == {r["id"] for r in load(E04)["exclusionReasons"]["reasons"]} - {
        ONSET_REASON
    }


def test_the_controller_rule_does_not_read_revision_two_or_another_experiment(
    root: Path,
) -> None:
    """Revision 2 keeps the clause and reads under rule set 3 as before, and the rule
    reads no record of another experiment."""
    findings = {f.rule_id for f in core._selection_findings(E04, load(E04))}
    assert CONTROLLER_RULE in findings
    assert found(root) == []


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            _criterion_member("E04-AC3", "id", ["x"]), id="a-criterion-id-a-list"
        ),
        pytest.param(
            lambda d: d["definition"]["criterionClocks"][0].__setitem__(
                "criterion", ["x"]
            ),
            id="a-clock-criterion-a-list",
        ),
        pytest.param(_discovery("statement", ["x"]), id="a-discovery-statement-a-list"),
        pytest.param(
            lambda d: timing_of(d).__setitem__("controllerDiscovery", "x"),
            id="the-discovery-a-text",
        ),
    ],
)
def test_a_malformed_controller_member_is_a_finding_and_not_an_error(
    full_root: Path, change: Callable[[dict[str, Any]], None]
) -> None:
    edit(full_root, E04_R3, change)
    findings = found(full_root)
    assert findings
    assert {f[1] for f in findings} == {E04_R3}
