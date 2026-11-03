"""Rule G3 of the V2-E02A record, and revision 3 of the V2-E02B record.

``V2-S7-003-PR2`` restores the target in the desired state and registers revision 3
of the V2-E02B record, revision 5 of the V2-E03 record, and revision 4 of the V2-E06
record in the same change. These tests read the committed records and the tree. They
hold what the change states about itself: which members of each record differ, that
the three restored files have the pins of the revisions before the G1 switch, that
the provenance of the switch is the classification's, and that the two sides of the
controlled comparison differ in nothing else.

**What this does not hold.** No test can show that the repository owner authorized
the merge, and no test reads a cluster. The observation of the restored release
after the merge is not in this change, because the merge is the switch.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.support.target_tree import target_files
from tools.experiment_freeze import (
    REGISTRY_PATH,
    changed_inputs,
    content_digest,
    load_registry,
)
from tools.gitops_desired_state import desired_state_release

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = "docs/proof/experiments"

E02A_R4 = f"{EXPERIMENTS}/v2-e02a/freeze-r4.v1alpha1.json"
E02B_R1 = f"{EXPERIMENTS}/v2-e02b/freeze-r1.v1alpha1.json"
E02B_R2 = f"{EXPERIMENTS}/v2-e02b/freeze-r2.v1alpha1.json"
E02B_R3 = f"{EXPERIMENTS}/v2-e02b/freeze-r3.v1alpha1.json"
E02C_R2 = f"{EXPERIMENTS}/v2-e02c/freeze-r2.v1alpha1.json"
E03_R4 = f"{EXPERIMENTS}/v2-e03/freeze-r4.v1alpha1.json"
E03_R5 = f"{EXPERIMENTS}/v2-e03/freeze-r5.v1alpha1.json"
E04_R3 = f"{EXPERIMENTS}/v2-e04/freeze-r3.v1alpha1.json"
E05_R2 = f"{EXPERIMENTS}/v2-e05/freeze-r2.v1alpha1.json"
E06_R3 = f"{EXPERIMENTS}/v2-e06/freeze-r3.v1alpha1.json"
E06_R4 = f"{EXPERIMENTS}/v2-e06/freeze-r4.v1alpha1.json"
Q1_R2 = f"{EXPERIMENTS}/v2-q1/freeze-r2.v1alpha1.json"
Q2_R3 = f"{EXPERIMENTS}/v2-q2/freeze-r3.v1alpha1.json"
Q3_R2 = f"{EXPERIMENTS}/v2-q3/freeze-r2.v1alpha1.json"
S5_R2 = f"{EXPERIMENTS}/v2-s5-integration/freeze-r2.v1alpha1.json"
CLASSIFICATION = f"{EXPERIMENTS}/v2-e02a/classification.v1alpha1.json"

KEY = "local-docker-desktop/support-assistant"
DIRECTORY = "gitops/environments/local-docker-desktop/workloads/support-assistant"
RELEASE_FILE = f"{DIRECTORY}/rendered-workload-release.yaml"
VALUES_FILE = f"{DIRECTORY}/values.generated.yaml"
DECLARATION = "tools/gitops_desired_state/core.py"
#: The three files of the delivery path that each switch moves.
SWITCHED = {RELEASE_FILE, VALUES_FILE, DECLARATION}
LEDGER_LIST = {"tools/evidence_index/__init__.py", "tools/evidence_index/core.py"}
BASELINE_TOOL = {
    "tools/baseline_profile/__init__.py",
    "tools/baseline_profile/__main__.py",
    "tools/baseline_profile/core.py",
}
EVIDENCE_TOOL = {
    "tools/experiment_evidence/__init__.py",
    "tools/experiment_evidence/__main__.py",
    "tools/experiment_evidence/core.py",
}
PREREGISTRATION_CORE = "tools/experiment_preregistration/core.py"
#: The pins of revision 2 of V2-E02B that revision 3 classifies.
MOVED_FROM_R2 = {*BASELINE_TOOL, *LEDGER_LIST, PREREGISTRATION_CORE}
COMPARISON_RECORD = (
    "tests/domain/fixtures/experiment-profiles/"
    "single-runtime-baseline.comparison.v1alpha1.json"
)

#: The members of revision 3 that differ from revision 2.
CHANGED_MEMBERS_E02B = {
    "metadata",
    "definition.gitTransitions",
    "definition.g3Provenance",
    "definition.limitations",
    "definition.history",
    "fields.experimentIdVersion",
    "fields.gitRevision",
    "pinnedInputs",
    "inputChanges",
}
#: The members that each rebinding record changes. V2-E03 also lists them.
CHANGED_MEMBERS_E03 = {
    "metadata",
    "definition.sources",
    "definition.history",
    "definition.changesFromSupersededRevision",
    "fields.experimentIdVersion",
    "fields.gitRevision",
    "pinnedInputs",
    "inputChanges",
}
CHANGED_MEMBERS_E06 = CHANGED_MEMBERS_E03 - {"definition.changesFromSupersededRevision"}
OWNER = (
    "Each switch is a commit to main that needs the explicit authorization of the "
    "repository owner."
)
#: The limitation of revision 2 that the runs of V2-E02A made false.
STALE_LIMITATION = (
    "The single-runtime baseline release has never been installed. Its install "
    "inputs are compared with those of the target by the committed comparison "
    "record, and no cluster has run it."
)


#: Two sentences of revision 2 that named every experiment. V2-E02A has a control.
DECLARATION_LIMITATION = (
    "No code holds a declaration of the analysis to "
    "definition.analysisDeclaration. The review of each run compares them."
)
LATEST_LIMITATION = (
    "No tool checks that a run executes the latest registered revision of its "
    "experiment. P1 states it, and the review of each run compares it."
)


def read(path: str) -> dict[str, Any]:
    document = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def pins(path: str) -> dict[str, str]:
    return {pin["path"]: pin["sha256"] for pin in read(path)["pinnedInputs"]}


def digest_of(path: str, root: Path = REPO_ROOT) -> str:
    return content_digest((root / path).read_bytes())


def members_that_differ(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    differing = set()
    for section in ("definition", "fields"):
        for key in set(before[section]) | set(after[section]):
            if before[section].get(key) != after[section].get(key):
                differing.add(f"{section}.{key}")
    for key in set(before) | set(after):
        if key not in ("definition", "fields") and before.get(key) != after.get(key):
            differing.add(key)
    return differing


def moved_paths(path: str) -> set[str]:
    return {change.path for change in changed_inputs(read(path), REPO_ROOT)}


# --------------------------------------------------------------------------
# The restored files
# --------------------------------------------------------------------------


def test_the_two_files_have_the_digests_that_the_topology_states() -> None:
    topology = read(E02B_R3)["fields"]["topology"][0]["value"]
    assert (topology["apiReplicas"], topology["runtimeReplicas"]) == (2, 2)
    assert topology["desiredStatePath"] == DIRECTORY
    stated = topology["release"]["desiredStateFiles"]
    assert stated == {
        "rendered-workload-release.yaml": digest_of(RELEASE_FILE),
        "values.generated.yaml": digest_of(VALUES_FILE),
    }
    assert topology["release"]["helmValuesSha256"] == digest_of(VALUES_FILE)
    for name, data in target_files().items():
        assert content_digest(data) == stated[name], name


@pytest.mark.parametrize("revision", [E02B_R1, E02B_R2, E02B_R3])
def test_each_revision_pins_the_three_restored_files_at_one_digest(
    revision: str,
) -> None:
    """Rule G3 restores the bytes of the target, and of the declaration, so no
    revision of V2-E02B saw another digest of the three files."""
    pinned = pins(revision)
    for path in SWITCHED:
        assert pinned[path] == digest_of(path), path


def test_the_declaration_names_the_two_replica_contract_of_the_target() -> None:
    contract = read(E02B_R3)["fields"]["topology"][0]["value"]["release"]["contract"]
    declared = desired_state_release(KEY)
    assert declared.contract == contract["path"]
    assert digest_of(contract["path"]) == contract["contentSha256"]


def test_the_comparison_record_is_the_one_that_both_sides_pin() -> None:
    assert (
        pins(E02A_R4)[COMPARISON_RECORD]
        == pins(E02B_R2)[COMPARISON_RECORD]
        == pins(E02B_R3)[COMPARISON_RECORD]
        == digest_of(COMPARISON_RECORD)
    )


def test_the_two_sides_differ_in_the_switch_and_the_list_of_ledgers_alone() -> None:
    """The controlled comparison read from the pins: every file that both records
    pin has one digest, but for the three switched files and the list of ledgers. A
    change to the chart, a contract, a script, or a tool between the last run of
    V2-E02A and revision 3 fails here."""
    baseline, target = pins(E02A_R4), pins(E02B_R3)
    assert not set(target) - set(baseline)
    differing = {path for path in target if baseline[path] != target[path]}
    assert differing == SWITCHED | LEDGER_LIST


# --------------------------------------------------------------------------
# Revision 3 of V2-E02B
# --------------------------------------------------------------------------


def test_revision_3_differs_from_revision_2_in_the_listed_members_alone() -> None:
    two, three = read(E02B_R2), read(E02B_R3)
    assert members_that_differ(two, three) == CHANGED_MEMBERS_E02B
    assert three["materialScope"] == two["materialScope"]
    assert three["exclusionReasons"] == two["exclusionReasons"]
    assert three["parts"] == two["parts"]
    assert three["fields"]["acceptanceCriteria"] == two["fields"]["acceptanceCriteria"]
    assert three["fields"]["topology"] == two["fields"]["topology"]
    assert three["definition"]["history"][:-1] == two["definition"]["history"]


def test_the_metadata_names_the_change_and_the_superseded_revision() -> None:
    metadata = read(E02B_R3)["metadata"]
    assert metadata["experiment"] == "V2-E02B"
    assert metadata["revision"] == 3
    assert metadata["registeredBy"] == "V2-S7-003-PR2"
    assert metadata["preregistrationRules"] == 2
    assert metadata["supersedes"] == {
        "path": E02B_R2,
        "contentSha256": load_registry()[E02B_R2],
    }
    fields = read(E02B_R3)["fields"]
    assert fields["experimentIdVersion"][0]["value"]["freezeRevision"] == 3


def test_revision_3_classifies_each_pin_that_moved_as_not_material() -> None:
    two, three = pins(E02B_R2), pins(E02B_R3)
    moved = {path for path in set(two) | set(three) if two.get(path) != three.get(path)}
    assert moved == MOVED_FROM_R2
    changes = read(E02B_R3)["inputChanges"]
    assert {change["path"] for change in changes} == moved
    for change in changes:
        assert change["from"] == two[change["path"]]
        assert change["to"] == three[change["path"]]
        assert change["material"] is False
        assert change["reason"]
    reasons = [change["reason"] for change in changes]
    assert len(set(reasons)) == len(reasons)


def test_revision_3_states_the_switch_that_registers_it() -> None:
    """Revision 2 states that no switch is executed by the change that registers it,
    and that held. Revision 3 is registered by the G3 switch, so it states that, and
    the owner-authorization sentence is word for word that of rule G4 of V2-E02A."""
    two = read(E02B_R2)["definition"]["gitTransitions"]
    three = read(E02B_R3)["definition"]["gitTransitions"]
    assert two[1] == "No switch is executed by the change that registers this record."
    assert three[1] == (
        "The change that registers this record executes the G3 switch, in the same "
        f"merge. {OWNER}"
    )
    assert not any("No switch is executed" in text for text in three)
    g4 = read(E02A_R4)["definition"]["gitTransitions"][3]
    assert g4.endswith(OWNER)


def test_the_provenance_is_the_handoff_of_the_classification() -> None:
    provenance = read(E02B_R3)["definition"]["g3Provenance"]
    classification = read(CLASSIFICATION)
    handoff = classification["handoff"]
    last = handoff["lastRun"]
    assert provenance["governingRecord"] == {
        "experiment": "V2-E02A",
        **classification["governingRecord"],
    }
    assert provenance["governingRecord"]["path"] == E02A_R4
    assert provenance["governingRecord"]["contentSha256"] == load_registry()[E02A_R4]
    assert provenance["lastRun"] == {
        name: last[name]
        for name in (
            "runId",
            "state",
            "executingRevision",
            "finishedAt",
            "manifestSha256",
            "rawEvidenceSha256",
        )
    }
    assert provenance["lastRun"]["runId"] == classification["attempts"][-1]["runId"]
    assert provenance["classification"] == {
        "path": CLASSIFICATION,
        "contentSha256": digest_of(CLASSIFICATION),
        "verdict": "eligible",
    }
    baseline = handoff["baselineDesiredState"]
    assert provenance["restoredFrom"] == {
        "releaseId": baseline["releaseId"],
        "apiReplicas": baseline["apiReplicas"],
        "runtimeReplicas": baseline["runtimeReplicas"],
        "desiredStateFiles": baseline["files"],
    }
    assert (
        provenance["restoredFrom"]["desiredStateFiles"]
        == read(E02A_R4)["fields"]["topology"][0]["value"]["release"][
            "desiredStateFiles"
        ]
    )


def test_the_target_of_the_handoff_is_the_restored_release() -> None:
    handoff = read(CLASSIFICATION)["handoff"]["targetDesiredState"]
    release = read(E02B_R3)["fields"]["topology"][0]["value"]["release"]
    assert handoff["releaseId"] == release["releaseId"]
    assert handoff["files"] == release["desiredStateFiles"]


def test_three_limitations_are_restated_and_five_are_added() -> None:
    two = read(E02B_R2)["definition"]["limitations"]
    three = read(E02B_R3)["definition"]["limitations"]
    restated = {item for item, kept in zip(two, three, strict=False) if item != kept}
    assert restated == {DECLARATION_LIMITATION, STALE_LIMITATION, LATEST_LIMITATION}
    assert "installed the single-runtime baseline release" in " ".join(three)
    assert sum("This experiment has no control" in item for item in three) == 2
    assert len(three) == len(two) + 5
    added = "\n".join(three[len(two) :])
    assert "no characterization of the single-runtime baseline release" in added
    assert "no tool checks that the controller delivered the target" in added
    assert "E02B-AC2" in added
    assert "B_failures is 2 and B_episode is 4,065 ms" in added


def test_the_history_states_the_runs_that_revision_3_was_written_after() -> None:
    entry = read(E02B_R3)["definition"]["history"][-1]
    for run in ("e02a-1", "e02a-2", "e02a-3"):
        assert run in entry
    assert "No run of V2-E02B, V2-E02C, V2-E04, or V2-E05 exists." in entry
    assert "changes no criterion" in entry


def test_revision_3_adds_no_driver() -> None:
    assert "No driver for this experiment exists." in " ".join(
        read(E02B_R3)["definition"]["limitations"]
    )
    assert not (REPO_ROOT / EXPERIMENTS / "v2-e02b" / "procedure").exists()
    assert not (REPO_ROOT / EXPERIMENTS / "v2-e02b" / "runs").exists()


# --------------------------------------------------------------------------
# The records that bind it
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("before", "after", "changed", "role"),
    [
        (E03_R4, E03_R5, CHANGED_MEMBERS_E03, "initial"),
        (E06_R3, E06_R4, CHANGED_MEMBERS_E06, "target"),
    ],
    ids=["e03", "e06"],
)
def test_each_analysis_record_binds_revision_3_and_nothing_else(
    before: str, after: str, changed: set[str], role: str
) -> None:
    old, new = read(before), read(after)
    assert members_that_differ(old, new) == changed
    assert new["materialScope"] == old["materialScope"]
    assert new["definition"]["history"][:-1] == old["definition"]["history"]
    assert new["metadata"]["supersedes"] == {
        "path": before,
        "contentSha256": load_registry()[before],
    }
    was, now = old["definition"]["sources"], new["definition"]["sources"]
    assert [b for b in now if b["experiment"] != "V2-E02B"] == [
        b for b in was if b["experiment"] != "V2-E02B"
    ]
    [binding] = [b for b in now if b["experiment"] == "V2-E02B"]
    assert binding == {
        "experiment": "V2-E02B",
        "role": role,
        "path": E02B_R3,
        "revision": 3,
        "contentSha256": load_registry()[E02B_R3],
        "preregistrationRules": 2,
    }


def test_v2_e06_pins_the_restored_files_as_its_revision_3_requires() -> None:
    """Revision 3 of V2-E06 states that a revision that binds the V2-E02B revision
    pins the restored files before any figure is computed."""
    three, four = pins(E06_R3), pins(E06_R4)
    changes = {change["path"]: change for change in read(E06_R4)["inputChanges"]}
    assert set(changes) == {E02B_R3, RELEASE_FILE, VALUES_FILE, *LEDGER_LIST}
    for path in (RELEASE_FILE, VALUES_FILE):
        assert four[path] == digest_of(path)
        assert three[path] != four[path]
        assert changes[path]["material"] is True
    assert changes[E02B_R3]["material"] is True
    assert changes[E02B_R3]["from"] is None


def test_v2_e03_lists_each_member_that_it_changes() -> None:
    listed = {
        item["member"]
        for item in read(E03_R5)["definition"]["changesFromSupersededRevision"]
    }
    assert listed == (
        CHANGED_MEMBERS_E03 - {"definition.changesFromSupersededRevision"}
    )


def test_the_three_records_are_registered_by_the_switch_alone() -> None:
    registry = json.loads((REPO_ROOT / REGISTRY_PATH).read_text(encoding="utf-8"))
    rows = [
        row["path"]
        for row in registry["records"]
        if row["registeredBy"] == "V2-S7-003-PR2"
    ]
    assert rows == [E02B_R3, E03_R5, E06_R4]


# --------------------------------------------------------------------------
# What the switch leaves stale, and what it clears
# --------------------------------------------------------------------------


@pytest.mark.parametrize("record", [Q1_R2, Q2_R3, Q3_R2], ids=lambda p: p[-24:])
def test_a_record_that_the_switch_restores_or_registers_lists_no_moved_file(
    record: str,
) -> None:
    assert changed_inputs(read(record), REPO_ROOT) == []


@pytest.mark.parametrize(
    ("record", "moved"),
    [
        (E02A_R4, SWITCHED | LEDGER_LIST),
        (E02B_R2, MOVED_FROM_R2),
        (E02C_R2, LEDGER_LIST | {PREREGISTRATION_CORE}),
        (E04_R3, LEDGER_LIST),
        (E05_R2, LEDGER_LIST | {PREREGISTRATION_CORE}),
        (S5_R2, LEDGER_LIST | EVIDENCE_TOOL),
        (E02B_R3, LEDGER_LIST),
        (E03_R5, LEDGER_LIST),
        (E06_R4, LEDGER_LIST),
    ],
    ids=[
        "e02a-r4",
        "e02b-r2",
        "e02c-r2",
        "e04-r3",
        "e05-r2",
        "s5-r2",
        "e02b-r3",
        "e03-r5",
        "e06-r4",
    ],
)
def test_a_record_that_owes_a_revision_lists_each_moved_file(
    record: str, moved: set[str]
) -> None:
    """A tripwire. P1 of each record states that a run refuses while a file is listed.
    Only V2-E02A has a control that applies P1. A file that moves later fails here."""
    assert moved_paths(record) == moved


# --------------------------------------------------------------------------
# A switch that is not whole, and drift after it
# --------------------------------------------------------------------------


@pytest.fixture
def pinned_tree(tmp_path: Path) -> Path:
    """A copy of the files that revision 3 pins."""
    for path in pins(E02B_R3):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / path, target)
    return tmp_path


def beyond_the_ledgers(tree: Path) -> list[Any]:
    """What moved against revision 3, past the two files that the ledgers move.

    Since V2-S7-004-PR1 those two differ from revision 3, and a test above holds that.
    """
    return [
        change
        for change in changed_inputs(read(E02B_R3), tree)
        if change.path not in LEDGER_LIST
    ]


def test_a_hand_edit_of_a_restored_file_is_listed_against_revision_3(
    pinned_tree: Path,
) -> None:
    path = pinned_tree / VALUES_FILE
    path.write_bytes(path.read_bytes().replace(b"replicaCount: 2", b"replicaCount: 1"))
    assert [(c.path, c.kind) for c in beyond_the_ledgers(pinned_tree)] == [
        (VALUES_FILE, "changed")
    ]


def test_the_files_of_the_baseline_at_the_path_are_listed_against_revision_3(
    pinned_tree: Path,
) -> None:
    """The desired state left at 2+1: a run under revision 3 refuses at P1."""
    profile = "tests/domain/fixtures/experiment-profiles/single-runtime-baseline"
    for name in target_files():
        shutil.copyfile(pinned_tree / profile / name, pinned_tree / DIRECTORY / name)
    changes = beyond_the_ledgers(pinned_tree)
    assert {change.path for change in changes} == {RELEASE_FILE, VALUES_FILE}


def test_a_declaration_left_at_the_baseline_is_listed_against_revision_3(
    pinned_tree: Path,
) -> None:
    path = pinned_tree / DECLARATION
    data = path.read_bytes()
    assert data.count(b"synchronous-llm-two-replicas.yaml") == 1
    path.write_bytes(
        data.replace(
            b"synchronous-llm-two-replicas.yaml", b"synchronous-llm-local.yaml"
        )
    )
    assert [c.path for c in beyond_the_ledgers(pinned_tree)] == [DECLARATION]
