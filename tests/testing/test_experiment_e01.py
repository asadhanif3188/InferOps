"""The V2-E01 static run: the runner, the judge, and the committed run.

``tools/experiment_e01`` runs E01-A, E01-B, and E01-C as the E01 family freeze record
registers them, and judges a run from its raw evidence. This suite:

- checks every committed run against its own evidence: each file has the digest the
  manifest records, and the verdicts, outcomes, and result page computed again from
  the files are the ones the run recorded;
- holds the second committed run to the execution identity freeze revision 2
  requires: the record's registered digest, the runner and the package imported from
  the checkout, and every loaded module file a pinned input with its pinned content;
- plants each kind of defect in a copy of the committed run - a changed render, a
  changed refusal, an edited outcome, an edited page, a missing or extra file - and
  requires the check to find it;
- holds the judge to each outcome state: a failed precondition is REFUSED, a met
  abort condition is ABORTED, missing evidence is INCONCLUSIVE, and a criterion that
  does not hold is FAILED;
- judges every committed run by the analysis of the freeze revision it names, so the
  first run is still judged by revision 1, byte for byte;
- executes the runner end to end in a temporary Git repository built from the pinned
  inputs, and requires a precondition that fails to refuse the run: among them, from
  revision 2, a runner or package imported from outside the checkout, an unregistered
  record, and an added material file; and requires a loaded module that is not a pinned
  input to abort it;
- runs the command itself from a temporary merged checkout, importing the runner and
  the package from that checkout, and requires every execution-identity precondition
  to hold and every loaded module to be a pinned input.

**What this does not assert.** No test requires a fresh execution to PASS. The
end-to-end tests run the parts, which the freeze record says is not result evidence,
and they assert only that the runner records what it observed and that the judge
agrees with it. Comparing today's code with the frozen expectations would be a run,
and a run is recorded under docs/proof/experiments/v2-e01/runs/, not asserted here.
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.support.e01_pinned_runner import (
    RUNNER,
    copy_pinned_input,
    pinned_runner_bytes,
)
from tests.support.e01_repinned_record import repin_record
from tools.experiment_e01 import (
    CRITERIA,
    CURRENT_REVISION,
    FREEZE_PATH,
    FREEZE_RECORDS,
    OUTCOME_STATES,
    PARTS,
    RUNS_DIR,
    PatchError,
    apply_patch,
    check_run,
    committed_runs,
    deep_merge,
    execute_run,
    judge,
    leaves,
    load_freeze,
    precondition_findings,
    result_page,
    run_id_problem,
)
from tools.experiment_e01 import core as e01_core
from tools.experiment_e01.__main__ import _shown
from tools.experiment_e01.core import MANIFEST, REFUSALS, RESULT
from tools.experiment_freeze import REGISTRY_PATH, changed_inputs, content_digest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS = committed_runs(REPO_ROOT)
#: The one committed run of part E01-D. The runner's listing leaves it out.
E01_D_RUN = "20261006-e01-d-1"
#: The freeze revision the committed run was registered under.
R1 = FREEZE_RECORDS[1]


def _manifest(run: Path) -> dict[str, Any]:
    document = json.loads((run / MANIFEST).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


# --------------------------------------------------------------------------
# 1. The committed run agrees with its own evidence
# --------------------------------------------------------------------------


def test_there_are_two_committed_runs_of_the_static_parts() -> None:
    """Every run stays recorded under its own identifier. The first ran under
    revision 1 and the second under revision 2; neither replaces the other."""
    assert [run.name for run in RUNS] == [
        "20261002-e01-abc-1",
        "20261003-e01-abc-1",
    ]
    assert [_manifest(run)["metadata"]["freezeRevision"] for run in RUNS] == [1, 2]


def test_the_run_of_the_real_deployment_is_not_listed_as_a_static_run() -> None:
    """The runs directory holds one run of part E01-D. The listing leaves it out,
    because this runner holds no analysis of that part."""
    held = {path.name for path in (REPO_ROOT / RUNS_DIR).iterdir()}
    assert held == {*(run.name for run in RUNS), E01_D_RUN}
    assert E01_D_RUN not in {run.name for run in RUNS}


def test_only_a_real_deployment_run_is_left_out(tmp_path: Path) -> None:
    """A directory is left out only when its name is an E01-D identifier and its own
    manifest names that part and no other. Every other directory is listed, so a
    misnamed static run, and a static run under an E01-D name, are checked."""
    real = json.dumps({"metadata": {"parts": ["E01-D"]}})
    static = json.dumps({"metadata": {"parts": ["E01-A", "E01-B", "E01-C"]}})
    #: Each directory name, its manifest text or None for no manifest, and
    #: whether the listing returns it.
    cases: list[tuple[str, str | None, bool]] = [
        ("20261006-e01-abc-1", static, True),
        ("20261006-e01-d-1", real, False),
        ("20261006-e01-d-12", real, False),
        ("20261006-e01-d-2", static, True),
        ("20261006-e01-d-3", None, True),
        ("20261006-e01-d-4", "not json", True),
        (
            "20261006-e01-d-5",
            json.dumps({"metadata": {"parts": ["E01-D", "E01-A"]}}),
            True,
        ),
        ("20261006-e01-d-6", json.dumps(["E01-D"]), True),
        ("20261006-e01-d-0", real, True),
        ("20261006-e01-d", real, True),
        ("20261006-E01-D-8", real, True),
        ("x20261006-e01-d-1", real, True),
        ("20261006-e01-d-1-copy", real, True),
    ]
    for name, manifest, _ in cases:
        (tmp_path / RUNS_DIR / name).mkdir(parents=True)
        if manifest is not None:
            (tmp_path / RUNS_DIR / name / MANIFEST).write_text(
                manifest, encoding="utf-8"
            )
    (tmp_path / RUNS_DIR / "20261006-e01-d-7").write_text("", encoding="utf-8")
    listed = {path.name for path in committed_runs(tmp_path)}
    assert listed == {name for name, _, returned in cases if returned}


def test_a_static_run_under_a_real_deployment_name_is_checked_and_fails(
    tmp_path: Path,
) -> None:
    """The name alone hides nothing: a copy of the second static run in a directory
    named as an E01-D run is listed, and the check finds that its name is wrong."""
    target = tmp_path / RUNS_DIR / "20261006-e01-d-9"
    shutil.copytree(RUNS[-1], target)
    for relative in (REGISTRY_PATH, *FREEZE_RECORDS.values()):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, tmp_path / relative)
    assert committed_runs(tmp_path) == [target]
    assert check_run(target, tmp_path) != []


def test_the_runner_differs_from_its_pin_by_the_committed_run_listing_only() -> None:
    """The listing changed after the E01-D run. The runner without that change has
    the digest that revisions 2 and 3 pin: the support module requires it and fails
    otherwise. So the change is the only difference, and both records report the
    runner as changed. This does not test that a run is refused; the tests of the
    preconditions do, on a moved input in a temporary repository."""
    pinned_runner_bytes(REPO_ROOT)
    for revision in (2, 3):
        path = f"docs/proof/experiments/v2-e01/freeze-r{revision}.v1alpha1.json"
        record = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
        moved = {c.path: c.kind for c in changed_inputs(record, REPO_ROOT)}
        assert moved.get(RUNNER) == "changed", revision


@pytest.mark.parametrize("run", RUNS, ids=lambda run: run.name)
def test_every_committed_run_agrees_with_its_evidence(run: Path) -> None:
    assert check_run(run, REPO_ROOT) == []


def test_the_command_passes_over_the_committed_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.experiment_e01", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"PASSED: {len(RUNS)} run(s)" in result.stdout


@pytest.mark.parametrize("run", RUNS, ids=lambda run: run.name)
def test_a_committed_run_names_the_freeze_and_every_part(run: Path) -> None:
    manifest = _manifest(run)
    revision = manifest["metadata"]["freezeRevision"]
    assert manifest["metadata"]["freezeRecord"] == FREEZE_RECORDS[revision]
    assert manifest["metadata"]["parts"] == list(PARTS)
    assert set(manifest["outcomes"]) == set(PARTS)
    assert set(manifest["outcomes"].values()) <= set(OUTCOME_STATES)
    assert len(manifest["executingRevision"]) == 40


@pytest.mark.parametrize("run", RUNS, ids=lambda run: run.name)
def test_a_committed_run_records_no_local_path(run: Path) -> None:
    """The evidence names files by repository path, never by a host's own path, and
    names no address."""
    for path in run.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not re.search(
                r"(?i)(?<![a-z])[a-z]:[\\/]|/users/|/home/|scratchpad|planning[\\/]|/tmp/",
                text,
            ), path.name
            assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), path.name


def test_the_second_run_records_the_execution_identity_revision_two_requires() -> None:
    """Read from the committed manifest and from freeze revision 2, which never
    changes: the run named that record by its registered digest, imported the runner
    and the package from its checkout in both processes, and loaded no repository
    module file that is not a pinned input with its pinned content."""
    manifest = _manifest(RUNS[1])
    r2 = load_freeze(REPO_ROOT, 2)
    registry = json.loads((REPO_ROOT / REGISTRY_PATH).read_text(encoding="utf-8"))
    (registered,) = [
        row["contentSha256"]
        for row in registry["records"]
        if row["path"] == FREEZE_RECORDS[2]
    ]
    assert manifest["metadata"]["freezeRecord"] == FREEZE_RECORDS[2]
    assert manifest["metadata"]["freezeContentSha256"] == registered
    seen = manifest["preconditions"]
    assert seen["findings"] == []
    assert seen["statusBefore"] == []
    assert seen["inventoryChanges"] == []
    assert seen["executingRevisionMerged"] is True
    assert seen["mergedRefRevision"] == manifest["executingRevision"]
    assert seen["runnerInCheckout"] is True
    assert seen["freezeRecordRegistered"] is True
    identity = manifest["executionIdentity"]
    assert identity["runnerFile"] == "tools/experiment_e01/core.py"
    assert identity["inferopsPackage"] == "src/inferops"
    assert identity["loadedOutsideFrozenInputs"] == []
    assert manifest["runner"]["package"] == "tools.experiment_e01"
    pinned = {pin["path"]: pin["sha256"] for pin in r2["pinnedInputs"]}
    for process in ("loadedModules", "loadedModulesSecondProcess"):
        loaded = identity[process]
        assert "tools/experiment_e01/core.py" in loaded, process
        assert "src/inferops/domain/render/helm_values.py" in loaded, process
        assert {path: pinned.get(path) for path in loaded} == loaded, process
    for name, digest in manifest["runner"]["files"].items():
        assert pinned[f"tools/experiment_e01/{name}"] == digest, name
    second = manifest["observations"]["E01-A"]["renderB"]["reported"]
    assert second["runnerInCheckout"] is True
    assert second["inferopsPackage"] == "src/inferops"
    assert manifest["abortChecks"]["conditions"] == []
    assert manifest["error"] is None


def test_an_edited_identity_in_a_copy_of_the_second_run_is_found(
    tmp_path: Path,
) -> None:
    """The committed second run, copied beside its freeze record: clean as copied,
    and refused once a loaded module's digest is not its pin."""
    for relative in (FREEZE_RECORDS[2],):
        (tmp_path / relative).parent.mkdir(parents=True)
        shutil.copyfile(REPO_ROOT / relative, tmp_path / relative)
    target = tmp_path / RUNS_DIR / RUNS[1].name
    shutil.copytree(RUNS[1], target)
    assert check_run(target, tmp_path) == []
    manifest = _manifest(target)
    manifest["executionIdentity"]["loadedModules"]["tools/experiment_e01/core.py"] = (
        "0" * 64
    )
    (target / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    assert check_run(target, tmp_path) != []


# --------------------------------------------------------------------------
# 2. The check finds a planted defect
# --------------------------------------------------------------------------


def test_the_first_run_is_judged_by_revision_one_and_a_new_run_by_the_latest() -> None:
    assert _manifest(RUNS[0])["metadata"]["freezeRecord"] == R1
    assert FREEZE_PATH == FREEZE_RECORDS[CURRENT_REVISION] != R1
    assert load_freeze(REPO_ROOT)["metadata"]["revision"] == CURRENT_REVISION == 2


@pytest.fixture
def copied(tmp_path: Path) -> Path:
    """A repository root holding the first run's freeze record and a copy of the run."""
    if not RUNS:
        pytest.skip("no committed run")
    (tmp_path / R1).parent.mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / R1, tmp_path / R1)
    target = tmp_path / RUNS_DIR / RUNS[0].name
    shutil.copytree(RUNS[0], target)
    return target


def _rewrite_digest(run: Path, relative: str) -> None:
    """Keep the manifest's digest of ``relative`` current, so only the judge can tell."""
    import hashlib

    manifest = _manifest(run)
    manifest["files"][relative] = hashlib.sha256(
        (run / relative).read_bytes()
    ).hexdigest()
    (run / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _locations(run: Path, root: Path) -> set[str]:
    return {finding.location for finding in check_run(run, root)}


def test_the_copy_is_clean_before_a_defect_is_planted(copied: Path) -> None:
    assert check_run(copied, copied.parents[5]) == []


def test_a_changed_second_render_is_found_by_the_judge(copied: Path) -> None:
    values = copied / "render-b" / "values.generated.yaml"
    values.write_bytes(
        values.read_bytes().replace(b"replicaCount: 1", b"replicaCount: 3", 1)
    )
    _rewrite_digest(copied, "render-b/values.generated.yaml")
    found = _locations(copied, copied.parents[5])
    assert {"criteria[E01-AC1]", "outcomes", RESULT} <= found


def test_a_changed_refusal_is_found_by_the_judge(copied: Path) -> None:
    refusals = json.loads((copied / REFUSALS).read_text(encoding="utf-8"))
    refusals[0]["attempts"][1]["refusal"]["findings"][0]["code"] = "version-unsupported"
    (copied / REFUSALS).write_text(
        json.dumps(refusals, indent=2) + "\n", encoding="utf-8"
    )
    _rewrite_digest(copied, REFUSALS)
    assert {"criteria[E01-AC7]", "outcomes"} <= _locations(copied, copied.parents[5])


def test_a_changed_mutation_is_found_by_the_judge(copied: Path) -> None:
    values = copied / "mutation" / "values.generated.yaml"
    values.write_bytes(
        values.read_bytes().replace(b"maxOutputTokens: 128", b"maxOutputTokens: 64")
    )
    _rewrite_digest(copied, "mutation/values.generated.yaml")
    assert "criteria[E01-AC6]" in _locations(copied, copied.parents[5])


def test_a_file_without_its_recorded_digest_is_found(copied: Path) -> None:
    path = copied / "render-a" / "rendered-workload-release.yaml"
    path.write_bytes(path.read_bytes() + b"# appended\n")
    assert "render-a/rendered-workload-release.yaml" in _locations(
        copied, copied.parents[5]
    )


def test_a_file_the_manifest_does_not_name_is_found(copied: Path) -> None:
    (copied / "notes.txt").write_text("added after the run\n", encoding="utf-8")
    assert "notes.txt" in _locations(copied, copied.parents[5])


def test_an_absent_file_is_found(copied: Path) -> None:
    (copied / "commands.txt").unlink()
    assert "commands.txt" in _locations(copied, copied.parents[5])


def test_an_edited_outcome_is_found(copied: Path) -> None:
    manifest = _manifest(copied)
    manifest["outcomes"]["E01-B"] = "INCONCLUSIVE"
    (copied / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    assert "outcomes" in _locations(copied, copied.parents[5])


def test_an_edited_criterion_is_found(copied: Path) -> None:
    manifest = _manifest(copied)
    manifest["criteria"][0]["holds"] = not manifest["criteria"][0]["holds"]
    (copied / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    assert "criteria[E01-AC1]" in _locations(copied, copied.parents[5])


def test_an_edited_result_page_is_found(copied: Path) -> None:
    page = copied / RESULT
    page.write_text(
        page.read_text(encoding="utf-8").replace("held", "holds", 1), encoding="utf-8"
    )
    assert RESULT in _locations(copied, copied.parents[5])


def test_a_run_judged_against_another_freeze_record_is_found(copied: Path) -> None:
    root = copied.parents[5]
    freeze = root / R1
    freeze.write_bytes(freeze.read_bytes() + b"\n")
    assert "metadata.freezeContentSha256" in _locations(copied, root)


def test_a_run_that_names_an_unknown_freeze_record_is_found(copied: Path) -> None:
    manifest = _manifest(copied)
    manifest["metadata"]["freezeRecord"] = "docs/proof/experiments/v2-e01/other.json"
    (copied / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    assert _locations(copied, copied.parents[5]) == {"metadata.freezeRecord"}


def test_the_first_run_judged_by_revision_two_would_not_be_its_own_page(
    copied: Path,
) -> None:
    """Versioned analysis is not decorative: revision 2's page differs from the one
    the first run recorded, so judging it by revision 2 would reinterpret it."""
    manifest = _manifest(copied)
    r2 = load_freeze(REPO_ROOT, 2)
    page = result_page(manifest, r2, judge(copied, r2, manifest))
    assert page != (copied / RESULT).read_text(encoding="utf-8")


def test_a_renamed_run_is_found(copied: Path) -> None:
    renamed = copied.with_name("20261002-e01-abc-9")
    copied.rename(renamed)
    assert "metadata.runId" in _locations(renamed, renamed.parents[5])


def test_the_command_fails_on_a_planted_defect(copied: Path) -> None:
    manifest = _manifest(copied)
    manifest["outcomes"]["E01-A"] = "FAILED"
    (copied / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.experiment_e01",
            "--check",
            "--root",
            str(copied.parents[5]),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "MISMATCH" in result.stdout


# --------------------------------------------------------------------------
# 3. The judge gives each outcome state
# --------------------------------------------------------------------------


def _judged(run: Path, change: Callable[[dict[str, Any]], None]) -> dict[str, str]:
    manifest = _manifest(run)
    change(manifest)
    return dict(judge(run, load_freeze(run.parents[5], 1), manifest).outcomes)


def test_revision_two_fails_e01_a_when_a_hand_written_string_restates_a_pin(
    copied: Path,
) -> None:
    """The restored criterion: under revision 2, a restated pin fails E01-AC5."""
    manifest = _manifest(copied)
    r2 = load_freeze(REPO_ROOT, 2)
    manifest["observations"]["E01-A"]["restatedPins"] = []
    assert judge(copied, r2, manifest).verdicts["E01-AC5"] is True
    manifest["observations"]["E01-A"]["restatedPins"] = [
        {"path": "model.artifact.sourceUrl", "restates": ["model.revision"]}
    ]
    assert judge(copied, r2, manifest).verdicts["E01-AC5"] is False
    del manifest["observations"]["E01-A"]["restatedPins"]
    assert judge(copied, r2, manifest).verdicts["E01-AC5"] is None


def test_a_failed_precondition_refuses_every_part(copied: Path) -> None:
    def refuse(manifest: dict[str, Any]) -> None:
        manifest["preconditions"]["findings"] = ["the working tree is not clean"]

    assert _judged(copied, refuse) == dict.fromkeys(PARTS, "REFUSED")


def test_a_met_abort_condition_aborts_every_part(copied: Path) -> None:
    def abort(manifest: dict[str, Any]) -> None:
        manifest["abortChecks"]["conditions"] = ["the checked-out commit changed"]

    assert _judged(copied, abort) == dict.fromkeys(PARTS, "ABORTED")


def test_missing_evidence_is_inconclusive_and_only_for_its_part(copied: Path) -> None:
    shutil.rmtree(copied / "render-b")
    outcomes = _judged(copied, lambda manifest: None)
    assert outcomes["E01-A"] == "INCONCLUSIVE"
    assert outcomes["E01-B"] == _manifest(copied)["outcomes"]["E01-B"]


def test_a_second_render_from_the_same_seed_does_not_answer_e01_ac1(
    copied: Path,
) -> None:
    def same_seed(manifest: dict[str, Any]) -> None:
        manifest["observations"]["E01-A"]["renderB"]["reported"]["pythonHashSeed"] = "1"

    assert _judged(copied, same_seed)["E01-A"] == "INCONCLUSIVE"


def test_a_failed_criterion_is_failed_even_beside_an_unanswered_one(
    copied: Path,
) -> None:
    """FAILED is not repeatable and INCONCLUSIVE is, so FAILED must win."""

    def mixed(manifest: dict[str, Any]) -> None:
        manifest["observations"]["E01-A"]["contractDigest"] = "0" * 64
        manifest["observations"]["E01-A"]["renderB"]["reported"] = None

    assert _judged(copied, mixed)["E01-A"] == "FAILED"


def test_renders_that_differ_fail_even_without_the_seed_report(copied: Path) -> None:
    values = copied / "render-b" / "values.generated.yaml"
    values.write_bytes(values.read_bytes() + b"# differs\n")

    def unreported(manifest: dict[str, Any]) -> None:
        manifest["observations"]["E01-A"]["renderB"]["reported"] = None

    assert _judged(copied, unreported)["E01-A"] == "FAILED"


def test_an_unreadable_render_leaves_its_part_unanswered(copied: Path) -> None:
    (copied / "render-a" / "rendered-workload-release.yaml").write_bytes(b": [\n")
    assert _judged(copied, lambda manifest: None)["E01-A"] == "INCONCLUSIVE"


def test_a_run_against_another_reference_is_found(copied: Path) -> None:
    manifest = _manifest(copied)
    manifest["preconditions"]["mergedRef"] = "HEAD"
    (copied / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    assert "preconditions.mergedRef" in _locations(copied, copied.parents[5])


def test_recorded_findings_the_observations_do_not_give_are_found(copied: Path) -> None:
    manifest = _manifest(copied)
    manifest["preconditions"]["executingRevisionMerged"] = False
    (copied / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    assert "preconditions.findings" in _locations(copied, copied.parents[5])


def test_a_malformed_manifest_is_a_finding_not_a_traceback(copied: Path) -> None:
    manifest = _manifest(copied)
    del manifest["preconditions"]
    (copied / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    assert _locations(copied, copied.parents[5]) == {MANIFEST}


def test_an_unadmitted_hand_written_file_fails_e01_a(copied: Path) -> None:
    def refused(manifest: dict[str, Any]) -> None:
        manifest["observations"]["E01-A"]["admission"] = {
            "admitted": False,
            "refusal": {},
        }

    assert _judged(copied, refused)["E01-A"] == "FAILED"


def test_a_second_merged_difference_fails_e01_a(copied: Path) -> None:
    def another(manifest: dict[str, Any]) -> None:
        manifest["observations"]["E01-A"]["mergedDifferences"].append(
            {
                "path": "api.replicaCount",
                "v2": {"present": True, "value": 2},
                "v1": {"present": True, "value": 1},
            }
        )

    assert _judged(copied, another)["E01-A"] == "FAILED"


def test_a_contract_digest_that_disagrees_fails_e01_b(copied: Path) -> None:
    def other(manifest: dict[str, Any]) -> None:
        manifest["observations"]["E01-B"]["mutatedContractDigest"] = "0" * 64

    assert _judged(copied, other)["E01-B"] == "FAILED"


def test_a_case_written_to_its_output_directory_fails_e01_c(copied: Path) -> None:
    refusals = json.loads((copied / REFUSALS).read_text(encoding="utf-8"))
    refusals[2]["attempts"][0]["outputDirectoryExists"] = True
    (copied / REFUSALS).write_text(json.dumps(refusals), encoding="utf-8")
    assert _judged(copied, lambda manifest: None)["E01-C"] == "FAILED"


def test_a_case_recorded_once_leaves_e01_c_unanswered(copied: Path) -> None:
    refusals = json.loads((copied / REFUSALS).read_text(encoding="utf-8"))
    refusals[0]["attempts"].pop()
    (copied / REFUSALS).write_text(json.dumps(refusals), encoding="utf-8")
    assert _judged(copied, lambda manifest: None)["E01-C"] == "INCONCLUSIVE"


def test_the_page_lists_limitations_before_criteria(copied: Path) -> None:
    manifest = _manifest(copied)
    freeze = load_freeze(copied.parents[5], 1)
    page = result_page(manifest, freeze, judge(copied, freeze, manifest))
    assert page.index("## Limitations") < page.index("## Criteria")
    for criterion in CRITERIA:
        assert f"### {criterion.criterion_id} ({criterion.part})" in page


# --------------------------------------------------------------------------
# 4. Documents, identifiers, and preconditions
# --------------------------------------------------------------------------


def test_a_patch_applies_add_remove_and_replace_to_a_copy() -> None:
    document = {"spec": {"a": 1, "b": {"c": 2}}}
    patched = apply_patch(
        document,
        [
            {"op": "replace", "path": "/spec/a", "value": 5},
            {"op": "remove", "path": "/spec/b/c"},
            {"op": "add", "path": "/spec/d~1e", "value": {"f": 1}},
        ],
    )
    assert patched == {"spec": {"a": 5, "b": {}, "d/e": {"f": 1}}}
    assert document == {"spec": {"a": 1, "b": {"c": 2}}}


@pytest.mark.parametrize(
    "operation",
    [
        {"op": "add", "path": "/spec/b"},
        {"op": "replace", "path": "/spec/a"},
        {"op": "move", "path": "/spec/a"},
        {"op": "remove", "path": "/spec/absent"},
        {"op": "replace", "path": "/spec/absent", "value": 1},
        {"op": "add", "path": "/absent/a", "value": 1},
        {"op": "add", "path": "spec/a", "value": 1},
        {"op": "add", "path": "/spec/a/b", "value": 1},
    ],
)
def test_a_patch_that_cannot_apply_is_refused(operation: dict[str, Any]) -> None:
    with pytest.raises(PatchError):
        apply_patch({"spec": {"a": 1}}, [operation])


def test_every_registered_edit_applies_to_its_pinned_file() -> None:
    freeze = load_freeze(REPO_ROOT)
    import yaml

    for part in freeze["parts"]:
        if part["id"] == "E01-B":
            contract = yaml.safe_load(
                (REPO_ROOT / part["inputs"]["workloadContract"]).read_text(
                    encoding="utf-8"
                )
            )
            apply_patch(contract, part["inputs"]["mutation"])
        for case in part.get("cases", []):
            for spec in case["inputs"].values():
                if isinstance(spec, dict) and "file" in spec:
                    document = yaml.safe_load(
                        (REPO_ROOT / spec["file"]).read_text(encoding="utf-8")
                    )
                    apply_patch(document, spec["edits"])


def test_leaves_and_the_merge_follow_helm() -> None:
    merged = deep_merge({"a": {"b": 1, "c": [1]}, "d": 1}, {"a": {"c": [2]}}, {"d": {}})
    assert merged == {"a": {"b": 1, "c": [2]}, "d": {}}
    assert dict(leaves(merged)) == {"a.b": 1, "a.c": [2], "d": {}}


def test_a_run_identifier_carries_the_utc_date_and_a_sequence() -> None:
    started = datetime.datetime(2026, 10, 2, 23, 30, tzinfo=datetime.UTC)
    assert run_id_problem("20261002-e01-abc-1", started) is None
    assert run_id_problem("20261003-e01-abc-1", started) is not None
    assert run_id_problem("20261002-e01-abc-0", started) is not None
    assert run_id_problem("20261002-e01-abcd-1", started) is not None


CLEAN: dict[str, Any] = {
    "head": "a" * 40,
    "merged": True,
    "freeze_at_head": True,
    "status": [],
    "moved_inputs": [],
    "parts": PARTS,
    "revision": 1,
}


def test_the_preconditions_hold_for_a_clean_merged_commit() -> None:
    assert precondition_findings(**CLEAN) == []
    assert precondition_findings(**{**CLEAN, "revision": 2}) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"head": "abc"}, "not a full Git revision"),
        ({"merged": False}, "not merged"),
        ({"freeze_at_head": False}, "holds no"),
        ({"status": [" M README.md"]}, "not clean"),
        ({"moved_inputs": ["uv.lock"]}, "1 pinned input(s) differ"),
        ({"parts": (*PARTS, "E01-D")}, "E01-D is refused"),
        ({"package_in_checkout": False}, "inferops package"),
        ({"revision": 2, "moved_inputs": ["x"]}, "1 material file(s) differ"),
        ({"revision": 2, "runner_in_checkout": False}, "the runner imported"),
        ({"revision": 2, "record_registered": False}, "is not registered"),
    ],
)
def test_each_failed_precondition_is_named(
    change: dict[str, Any], expected: str
) -> None:
    findings = precondition_findings(**{**CLEAN, **change})
    assert len(findings) == 1 and expected in findings[0]


def test_revision_one_ignores_the_checks_it_did_not_have() -> None:
    """The first run's recorded findings stay the ones revision 1 gives."""
    assert (
        precondition_findings(
            **CLEAN, runner_in_checkout=False, record_registered=False
        )
        == []
    )


# --------------------------------------------------------------------------
# 5. The runner, end to end, in a temporary repository
# --------------------------------------------------------------------------


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=e01",
            "-c",
            "user.email=e01@example.invalid",
            *arguments,
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _merge(root: Path) -> None:
    """Point the repository's origin/main at its HEAD, as a merge and a fetch would."""
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")


def _run(root: Path, **options: Any) -> tuple[Path, Any]:
    """A run in a temporary repository. The package and the runner imported are this
    checkout's, so the run is told to expect them there rather than under the
    temporary root."""
    return execute_run(
        root, f"{_today()}-e01-abc-1", **{"source_root": REPO_ROOT, **options}
    )


#: Every file a temporary repository needs besides the record's pinned inputs: the
#: registry and every revision, so the record is registered and its chain checks.
GOVERNANCE = (REGISTRY_PATH, *FREEZE_RECORDS.values())


def _populate(root: Path) -> None:
    """Copy the governance files and every pinned input. The runner is written in
    the content the record pins: the runner in the tree differs from its pin by the
    committed-run listing, and a run refuses a tree that holds a moved input.

    Other pinned inputs have changed in the tree since the record was registered,
    so the copy of the record is then re-pinned to the copied files. The run in
    this repository is a test of the runner on a tree that agrees with its record.
    It does not show that the tree holds what the committed record pinned."""
    freeze = load_freeze(REPO_ROOT)
    for relative in [*GOVERNANCE, *(pin["path"] for pin in freeze["pinnedInputs"])]:
        copy_pinned_input(REPO_ROOT, relative, root / relative)
    repin_record(root, FREEZE_PATH)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "inputs")
    _merge(root)


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A Git repository holding the freeze records and every input the latest pins,
    merged. The run imports this checkout's code, as a test does; the modules a test
    session has loaded are not the run's, so the loaded-module record is left empty
    here and tested on its own."""
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    _populate(tmp_path)
    monkeypatch.setattr(e01_core, "loaded_modules", lambda root, packages: {})
    # The second render's process imports the runner and the package from the
    # temporary checkout, as it does from a real one. That runner is the pinned
    # content, not the runner in the tree: the first process runs the tree's.
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join([str(tmp_path), str(tmp_path / "src")])
    )
    monkeypatch.setenv("PYTHONHASHSEED", "1")
    # The second render runs the copied runner from the temporary root, which has no
    # .gitignore: a bytecode cache written there would read as a changed file.
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    return tmp_path


def _today() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y%m%d")


def test_a_run_writes_evidence_the_judge_agrees_with(repository: Path) -> None:
    evidence, judgement = _run(repository)
    assert check_run(evidence, repository) == []
    manifest = _manifest(evidence)
    assert manifest["preconditions"]["mergedRef"] == "origin/main"
    assert manifest["preconditions"]["findings"] == []
    assert manifest["abortChecks"]["conditions"] == []
    assert manifest["abortChecks"]["temporaryDirectoryRemoved"] is True
    assert manifest["error"] is None
    assert set(judgement.outcomes) == set(PARTS)
    refusals = json.loads((evidence / REFUSALS).read_text(encoding="utf-8"))
    assert [len(case["attempts"]) for case in refusals] == [2] * 7
    assert manifest["metadata"]["freezeRecord"] == FREEZE_PATH
    assert manifest["preconditions"]["runnerInCheckout"] is True
    assert manifest["preconditions"]["freezeRecordRegistered"] is True
    assert manifest["preconditions"]["inventoryChanges"] == []
    assert "restatedPins" in manifest["observations"]["E01-A"]
    for name in ("render-a", "render-b", "mutation"):
        assert sorted(p.name for p in (evidence / name).iterdir()) == [
            "rendered-workload-release.yaml",
            "values.generated.yaml",
        ]
    second = manifest["observations"]["E01-A"]["renderB"]
    assert second["exitStatus"] == 0
    assert second["reported"]["pythonHashSeed"] == "2"


def test_a_run_into_an_existing_directory_writes_nothing(repository: Path) -> None:
    run_id = f"{_today()}-e01-abc-1"
    (repository / RUNS_DIR / run_id).mkdir(parents=True)
    with pytest.raises(FileExistsError):
        execute_run(repository, run_id, source_root=REPO_ROOT)
    assert list((repository / RUNS_DIR / run_id).iterdir()) == []


def test_a_run_identifier_for_another_day_writes_nothing(repository: Path) -> None:
    with pytest.raises(ValueError):
        execute_run(repository, "20000101-e01-abc-1", source_root=REPO_ROOT)
    assert not (repository / RUNS_DIR).exists()


def _refused(repository: Path, **options: Any) -> dict[str, Any]:
    evidence, judgement = _run(repository, **options)
    assert dict(judgement.outcomes) == dict.fromkeys(PARTS, "REFUSED")
    assert not (evidence / REFUSALS).exists()
    assert check_run(evidence, repository) == []
    return _manifest(evidence)


def test_a_dirty_tree_refuses_the_run(repository: Path) -> None:
    (repository / "stray.txt").write_text("x\n", encoding="utf-8")
    manifest = _refused(repository)
    assert manifest["preconditions"]["statusBefore"] == ["?? stray.txt"]


def test_a_moved_pinned_input_refuses_the_run(repository: Path) -> None:
    contract = (
        repository / "contracts/workload/examples/valid/synchronous-llm-local.yaml"
    )
    contract.write_text(
        contract.read_text(encoding="utf-8") + "# moved\n", encoding="utf-8"
    )
    _git(repository, "commit", "-q", "-am", "move an input")
    _merge(repository)
    manifest = _refused(repository)
    assert manifest["preconditions"]["movedPinnedInputs"] == [
        "contracts/workload/examples/valid/synchronous-llm-local.yaml"
    ]


def test_an_added_material_file_refuses_the_run(repository: Path) -> None:
    """The F2 gap, closed: a file the record never listed now refuses the run."""
    added = repository / "charts/inferops-llm/templates/extra.yaml"
    added.write_text("kind: ConfigMap\n", encoding="utf-8")
    _git(repository, "add", "-A")
    _git(repository, "commit", "-q", "-m", "add a material file")
    _merge(repository)
    manifest = _refused(repository)
    assert manifest["preconditions"]["inventoryChanges"] == [
        {"path": "charts/inferops-llm/templates/extra.yaml", "kind": "added"}
    ]


def test_an_unregistered_record_refuses_the_run(repository: Path) -> None:
    registry = repository / REGISTRY_PATH
    document = json.loads(registry.read_text(encoding="utf-8"))
    document["records"] = [r for r in document["records"] if r["path"] != FREEZE_PATH]
    registry.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    _git(repository, "commit", "-q", "-am", "unregister")
    _merge(repository)
    manifest = _refused(repository)
    assert manifest["preconditions"]["freezeRecordRegistered"] is False


def test_a_loaded_module_that_is_not_pinned_aborts_the_run(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        e01_core, "loaded_modules", lambda root, packages: {"tools/stray.py": "0" * 64}
    )
    evidence, judgement = _run(repository)
    assert dict(judgement.outcomes) == dict.fromkeys(PARTS, "ABORTED")
    manifest = _manifest(evidence)
    assert manifest["executionIdentity"]["loadedOutsideFrozenInputs"] == [
        "tools/stray.py"
    ]
    assert manifest["abortChecks"]["conditions"] == [e01_core.LOADED_OUTSIDE]
    assert check_run(evidence, repository) == []


def test_a_second_process_from_another_checkout_aborts_the_run(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second render imports the package from this checkout, not the temporary
    one: the first process's checks alone would not see it."""
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    evidence, judgement = _run(repository)
    assert dict(judgement.outcomes) == dict.fromkeys(PARTS, "ABORTED")
    assert e01_core.SECOND_OUTSIDE in _manifest(evidence)["abortChecks"]["conditions"]
    assert check_run(evidence, repository) == []


def _edited_manifest(evidence: Path, change: Callable[[dict[str, Any]], None]) -> None:
    manifest = _manifest(evidence)
    change(manifest)
    (evidence / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("change", "location"),
    [
        (
            lambda m: m["executionIdentity"]["loadedModules"].__setitem__(
                "tools/stray.py", "0" * 64
            ),
            "executionIdentity.loadedOutsideFrozenInputs",
        ),
        (
            lambda m: m["abortChecks"]["conditions"].append(e01_core.LOADED_OUTSIDE),
            "abortChecks.conditions",
        ),
        (
            lambda m: m["observations"]["E01-A"]["renderB"]["reported"].__setitem__(
                "inferopsPackage", "outside the checked-out tree"
            ),
            "abortChecks.conditions",
        ),
        (lambda m: m["preconditions"].pop("runnerInCheckout"), MANIFEST),
        (lambda m: m.pop("executionIdentity"), MANIFEST),
    ],
)
def test_check_finds_an_execution_identity_the_record_does_not_support(
    repository: Path, change: Callable[[dict[str, Any]], None], location: str
) -> None:
    """``--check`` recomputes the identity conditions of a revision-2 run from what
    it recorded, and refuses a manifest that drops the identity records."""
    evidence, _ = _run(repository)
    assert check_run(evidence, repository) == []
    _edited_manifest(evidence, change)
    assert location in {f.location for f in check_run(evidence, repository)}


def test_loaded_modules_count_only_the_package_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A virtual environment inside the checkout is not the experiment's code: uv
    puts .venv there, and counting it would abort every documented run."""
    import types

    files = {
        "venv_mod": tmp_path / ".venv" / "Lib" / "site-packages" / "venv_mod.py",
        "tool_mod": tmp_path / "tools" / "tool_mod.py",
        "src_mod": tmp_path / "src" / "inferops" / "src_mod.py",
        "test_mod": tmp_path / "tests" / "test_mod.py",
    }
    for name, path in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n", encoding="utf-8")
        module = types.ModuleType(f"_e01_probe_{name}")
        module.__file__ = str(path)
        monkeypatch.setitem(sys.modules, module.__name__, module)
    packages = e01_core.package_directories(load_freeze(REPO_ROOT))
    assert packages == ("src/inferops/", "tools/")
    assert set(e01_core.loaded_modules(tmp_path, packages)) == {
        "src/inferops/src_mod.py",
        "tools/tool_mod.py",
    }


def test_an_unmerged_commit_refuses_the_run(repository: Path) -> None:
    _git(repository, "commit", "-q", "--allow-empty", "-m", "not merged")
    manifest = _refused(repository)
    assert manifest["preconditions"]["executingRevisionMerged"] is False


def test_a_package_and_runner_from_another_checkout_refuse_the_run(
    repository: Path,
) -> None:
    """The run imports this checkout's package and runner, which are not under the
    temporary root: the first run's boundary defect, now a refusal."""
    manifest = _refused(repository, source_root=None)
    assert manifest["preconditions"]["inferopsPackage"] == (
        "outside the checked-out tree"
    )
    assert manifest["preconditions"]["runnerInCheckout"] is False
    findings = manifest["preconditions"]["findings"]
    assert any("inferops package" in f for f in findings)
    assert any("the runner imported" in f for f in findings)
    assert manifest["executionIdentity"]["runnerFile"] == "outside the checked-out tree"


def test_a_step_that_raises_is_recorded_and_answers_nothing(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*arguments: Any) -> None:
        raise RuntimeError("a step failed")

    monkeypatch.setattr(e01_core, "_run_parts", broken)
    evidence, judgement = _run(repository)
    manifest = _manifest(evidence)
    assert manifest["error"] == {
        "exception": "RuntimeError",
        "message": "a step failed",
    }
    assert dict(judgement.outcomes) == dict.fromkeys(PARTS, "INCONCLUSIVE")
    assert check_run(evidence, repository) == []


def test_a_tracked_file_changed_during_the_run_aborts_it(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def tamper(root: Path, *arguments: Any) -> None:
        (root / "uv.lock").write_text("changed\n", encoding="utf-8")

    monkeypatch.setattr(e01_core, "_run_parts", tamper)
    evidence, judgement = _run(repository)
    assert dict(judgement.outcomes) == dict.fromkeys(PARTS, "ABORTED")
    assert _manifest(evidence)["abortChecks"]["conditions"] == [
        "a file outside the run's evidence directory changed"
    ]


def test_the_command_refuses_to_start_without_the_first_seed(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHONHASHSEED")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.experiment_e01",
            "--run",
            f"{_today()}-e01-abc-1",
            "--root",
            str(repository),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "NOT STARTED" in result.stdout
    assert not (repository / RUNS_DIR).exists()


def test_the_manifest_is_a_copy_safe_document(copied: Path) -> None:
    """The judge reads a manifest without changing it."""
    manifest = _manifest(copied)
    before = copy.deepcopy(manifest)
    judge(copied, load_freeze(copied.parents[5], 1), manifest)
    assert manifest == before


def test_the_command_run_from_a_merged_checkout_imports_only_pinned_code(
    tmp_path: Path,
) -> None:
    """End to end, as a contributor runs it: the command, from a temporary merged
    checkout, with that checkout's runner and package first on the import path.
    Since the committed-run listing changed, that checkout's runner is the pinned
    content, rebuilt by the support module. It is not the runner in the tree.

    This is a test-suite execution, which the freeze record lists as not result
    evidence; it asserts the execution identity, never an outcome.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    _populate(tmp_path)
    environment = {
        **{k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        "PYTHONHASHSEED": "1",
        "PYTHONPATH": os.pathsep.join([str(tmp_path), str(tmp_path / "src")]),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    run_id = f"{_today()}-e01-abc-1"
    result = subprocess.run(
        [sys.executable, "-m", "tools.experiment_e01", "--run", run_id],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    evidence = tmp_path / RUNS_DIR / run_id
    assert evidence.is_dir(), result.stdout + result.stderr
    manifest = _manifest(evidence)
    assert manifest["preconditions"]["findings"] == []
    assert manifest["abortChecks"]["conditions"] == []
    identity = manifest["executionIdentity"]
    assert identity["runnerFile"] == "tools/experiment_e01/core.py"
    assert identity["inferopsPackage"] == "src/inferops"
    assert identity["loadedOutsideFrozenInputs"] == []
    pinned = {pin["path"] for pin in load_freeze(REPO_ROOT)["pinnedInputs"]}
    loaded = set(identity["loadedModules"]) | set(
        identity["loadedModulesSecondProcess"]
    )
    assert "tools/experiment_e01/core.py" in loaded
    assert "src/inferops/domain/render/helm_values.py" in loaded
    assert loaded <= pinned


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--run", "x", "--root", "."], "--run x --root ."),
        (
            ["--run", "x", "--prelude", "C:/host/prelude.txt"],
            "--run x --prelude <preparation commands file>",
        ),
        (["--root=/srv/checkout/repo"], "--root=<repository root>"),
        (
            ["--root", "/srv/repo", "--run", "x"],
            "--root <repository root> --run x",
        ),
    ],
)
def test_the_recorded_command_line_withholds_host_paths(
    argv: list[str], expected: str
) -> None:
    assert _shown(argv) == expected


# --------------------------------------------------------------------------
# The committed run of part E01-D
# --------------------------------------------------------------------------
#
# No runner executed this run, and a person applied its verdicts. These tests hold
# the run's manifest to the files beside it and to the freeze record it names, and
# they derive each rule's verdict again from those committed files. They do not show
# that the cluster returned those files, and they execute no step of the part.

E01_D_DIR = REPO_ROOT / RUNS_DIR / E01_D_RUN
E01_D_FREEZE = "docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json"
E01_D_APPLICATION = "infra/argocd/local-docker-desktop-support-assistant.yaml"
#: The files that revision 3 registers for an E01-D run.
E01_D_FILES = {
    "run.v1alpha1.json",
    "commands.txt",
    "driver.txt",
    "transcript.txt",
    "environment.json",
    "release.json",
    "argo.json",
    "pods.json",
    "reconciliation.record.json",
    "provenance.json",
    "completion.json",
    "result.md",
}


def _e01_d_record() -> dict[str, Any]:
    record = json.loads((REPO_ROOT / E01_D_FREEZE).read_text(encoding="utf-8"))
    assert isinstance(record, dict)
    return record


def _e01_d_part() -> dict[str, Any]:
    part = next(item for item in _e01_d_record()["parts"] if item["id"] == "E01-D")
    assert isinstance(part, dict)
    return part


def _container(pod: dict[str, Any], group: str, name: str) -> dict[str, Any]:
    found = next(item for item in pod[group] if item["name"] == name)
    assert isinstance(found, dict)
    return found


def _derived_rules(directory: Path) -> dict[str, list[bool]]:
    """Each verification rule of revision 3, applied to the files of ``directory``.

    The order is the record's. The generated identities are read from the release in
    the tree, which revision 3 pins. Two rules have no structured file: the admission
    rule is read from the pytest summary in the transcript, and the eight-character
    rule from the consumed static run that the record names.
    """

    def load(name: str) -> Any:
        return json.loads((directory / name).read_text(encoding="utf-8"))

    record, part = _e01_d_record(), _e01_d_part()
    frozen = part["inputs"]["desiredStateRelease"]
    generated = yaml.safe_load(
        (REPO_ROOT / frozen["files"][0]).read_text(encoding="utf-8")
    )
    manifest = load(MANIFEST)
    commit = manifest["executingRevision"]
    argo, completion, release = (
        load("argo.json"),
        load("completion.json"),
        load("release.json"),
    )
    (provenance,) = load("provenance.json")
    runtime = next(
        pod
        for pod in load("pods.json")["items"]
        if pod["metadata"]["labels"]["app.kubernetes.io/component"] == "serving-runtime"
    )
    image = _container(runtime["status"], "containerStatuses", "runtime")["imageID"]
    verified = _container(runtime["status"], "initContainerStatuses", "verify-model")
    mounts = _container(runtime["spec"], "containers", "runtime")["volumeMounts"]
    sub_paths = [mount["subPath"] for mount in mounts if mount.get("subPath")]
    status, helm = argo["status"], argo["spec"]["source"]["helm"]
    committed = yaml.safe_load(
        (REPO_ROOT / E01_D_APPLICATION).read_text(encoding="utf-8")
    )
    digests = {item["path"]: item["sha256"] for item in release["files"]}
    response = completion["response"]
    ac9 = [
        status["sync"]["status"] == "Synced"
        and status["sync"]["revision"] == commit
        and status["operationState"]["phase"] == "Succeeded"
        and status["operationState"]["syncResult"]["revision"] == commit,
        provenance["git"]["revision"] == commit
        and provenance["release"]["releaseId"] == frozen["releaseId"]
        and provenance["release"]["valuesSha256"] == frozen["helmValuesSha256"],
        release["desiredStateCheckExitStatus"] == 0
        and digests[frozen["files"][0]] == frozen["helmValuesSha256"],
        image.endswith(generated["runtime"]["image"]["digest"]),
        len(sub_paths) == 1
        and sub_paths[0].endswith(generated["model"]["revision"])
        and verified["state"].get("terminated", {}).get("exitCode") == 0,
        response.get("model") == generated["model"]["identifier"],
    ]
    consumed = record["definition"]["staticResultConsumed"]
    static = json.loads((REPO_ROOT / consumed["run"]).read_text(encoding="utf-8"))
    transcript = (directory / "transcript.txt").read_text(encoding="utf-8")
    return {
        "E01-AC8": [
            completion["httpStatus"] == "200" and completion["requestsSent"] == 1,
            (response.get("choiceCount") or 0) >= 1
            and (response["firstChoice"]["assistantMessageLength"] or 0) > 0,
            all(ac9),
        ],
        "E01-AC9": ac9,
        "E01-AC10": [
            helm["valueFiles"] == part["inputs"]["application"]["valueFiles"]
            and helm["valuesObject"]
            == committed["spec"]["source"]["helm"]["valuesObject"]
            and helm["parameters"]
            == [
                {
                    "name": "api.image.digest",
                    "value": manifest["executionIdentity"]["apiImage"]["digest"],
                }
            ]
            and sorted(helm)
            == ["parameters", "releaseName", "valueFiles", "valuesObject"],
            "collected 36 items / 33 deselected / 3 selected" in transcript
            and "3 passed, 33 deselected" in transcript,
            content_digest((REPO_ROOT / consumed["run"]).read_bytes())
            == consumed["runContentSha256"]
            and any(c["id"] == "E01-AC5" and c["holds"] for c in static["criteria"]),
        ],
    }


def e01_d_findings(directory: Path) -> list[str]:
    """Every way an E01-D run directory disagrees with its manifest and revision 3."""
    findings: list[str] = []
    held = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    }
    if held != E01_D_FILES:
        return [f"files: {sorted(held ^ E01_D_FILES)}"]
    manifest = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
    if set(manifest["files"]) != E01_D_FILES - {MANIFEST, RESULT}:
        findings.append("files: the manifest does not list every other file")
    for name, digest in manifest["files"].items():
        data = (directory / name).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != digest:
            findings.append(f"{name}: does not have the recorded SHA-256")
    metadata = manifest["metadata"]
    registry = json.loads((REPO_ROOT / REGISTRY_PATH).read_text(encoding="utf-8"))
    pins = {row["path"]: row["contentSha256"] for row in registry["records"]}
    if (
        metadata["runId"] != directory.name
        or metadata["parts"] != ["E01-D"]
        or metadata["freezeRecord"] != E01_D_FREEZE
        or metadata["freezeRevision"] != 3
        or metadata["freezeContentSha256"] != pins[E01_D_FREEZE]
        or metadata["freezeContentSha256"]
        != content_digest((REPO_ROOT / E01_D_FREEZE).read_bytes())
    ):
        findings.append("metadata: is not this run under revision 3 as registered")
    if (
        re.fullmatch(r"[0-9a-f]{40}", manifest["executingRevision"]) is None
        or manifest["preconditions"]["remoteMain"] != manifest["executingRevision"]
        or manifest["preconditions"]["findings"] != []
    ):
        findings.append("preconditions: do not state a merged commit with no finding")
    statements = {
        criterion["id"]: criterion["statement"]
        for entry in _e01_d_record()["fields"]["acceptanceCriteria"]
        if entry["parts"] == ["E01-D"]
        for criterion in entry["value"]
    }
    rules = _e01_d_part()["verification"]
    derived = _derived_rules(directory)
    if [c["id"] for c in manifest["criteria"]] != list(statements):
        return [*findings, "criteria: are not the three of E01-D in order"]
    for criterion in manifest["criteria"]:
        name = criterion["id"]
        if criterion["statement"] != statements[name]:
            findings.append(f"{name}: the statement is not revision 3's")
        if [rule["rule"] for rule in criterion["rules"]] != rules[name]:
            findings.append(f"{name}: the rules are not revision 3's")
        elif [rule["holds"] for rule in criterion["rules"]] != derived[name]:
            findings.append(f"{name}: a rule verdict is not the one the files give")
        if criterion["holds"] is not all(rule["holds"] for rule in criterion["rules"]):
            findings.append(f"{name}: the verdict does not follow from its rules")
    every = all(criterion["holds"] for criterion in manifest["criteria"])
    if manifest["outcomes"] != {"E01-D": "PASSED" if every else "FAILED"}:
        findings.append("outcomes: do not follow from the criteria")
    if manifest["abortChecks"]["conditions"] != []:
        findings.append("abortChecks: a condition is recorded")
    completion = json.loads((directory / "completion.json").read_text("utf-8"))
    if completion["request"]["body"] != _e01_d_part()["inputs"]["request"]["body"]:
        findings.append("completion.json: the request is not the registered one")
    environment = json.loads((directory / "environment.json").read_text("utf-8"))
    if environment["everyAttributeEqual"] is not True or not all(
        item["equal"] and item["frozen"] == item["read"]
        for item in environment["identityStepP3"]
    ):
        findings.append("environment.json: an attribute is not equal")
    page = (directory / RESULT).read_text(encoding="utf-8")
    if f"**Outcome: {manifest['outcomes']['E01-D']}.**" not in page:
        findings.append("result.md: does not state the manifest's outcome")
    for criterion in manifest["criteria"]:
        verdict = "holds" if criterion["holds"] else "does not hold"
        if f"### {criterion['id']}: {verdict}" not in page:
            findings.append(
                f"result.md: does not state the verdict of {criterion['id']}"
            )
    return findings


def test_the_real_deployment_run_agrees_with_its_files_and_revision_three() -> None:
    """The committed run holds the twelve registered files, each with the digest the
    manifest records. It names revision 3 by its registered digest. Each rule's
    recorded verdict is the one the committed files give, and the outcome follows."""
    assert e01_d_findings(E01_D_DIR) == []
    manifest = json.loads((E01_D_DIR / MANIFEST).read_text(encoding="utf-8"))
    assert manifest["outcomes"] == {"E01-D": "PASSED"}
    assert manifest["evidenceLevel"]["level"] == "C2"
    registered = next(
        entry["value"]["files"]
        for entry in _e01_d_record()["fields"]["evidencePaths"]
        if entry["parts"] == ["E01-D"]
    )
    assert set(registered) == E01_D_FILES


def _rewrite(path: Path, change: Callable[[Any], None]) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def _redigest(directory: Path, name: str) -> None:
    """Record the new digest of an edited file, so only the edit's meaning is found."""
    digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    _rewrite(directory / MANIFEST, lambda m: m["files"].__setitem__(name, digest))


def _runtime(pods: dict[str, Any]) -> dict[str, Any]:
    pod = next(
        item
        for item in pods["items"]
        if item["metadata"]["labels"]["app.kubernetes.io/component"]
        == "serving-runtime"
    )
    assert isinstance(pod, dict)
    return pod


#: One planted defect each: the file it edits, the edit, and where it is found.
E01_D_DEFECTS: dict[str, tuple[str, Callable[[Any], None], str]] = {
    "a rule verdict flipped in the manifest": (
        MANIFEST,
        lambda m: m["criteria"][1]["rules"][3].__setitem__("holds", False),
        "E01-AC9: a rule verdict is not the one the files give",
    ),
    "an outcome the criteria do not give": (
        MANIFEST,
        lambda m: m.__setitem__("outcomes", {"E01-D": "FAILED"}),
        "outcomes: do not follow from the criteria",
    ),
    "a rule in other words": (
        MANIFEST,
        lambda m: m["criteria"][0]["rules"][0].__setitem__("rule", "HTTP 200."),
        "E01-AC8: the rules are not revision 3's",
    ),
    "another freeze digest": (
        MANIFEST,
        lambda m: m["metadata"].__setitem__("freezeContentSha256", "0" * 64),
        "metadata: is not this run under revision 3 as registered",
    ),
    "another runtime image in the pod status": (
        "pods.json",
        lambda d: _container(
            _runtime(d)["status"], "containerStatuses", "runtime"
        ).__setitem__("imageID", "ghcr.io/ggml-org/llama.cpp@sha256:" + "0" * 64),
        "E01-AC9: a rule verdict is not the one the files give",
    ),
    "a failed model verification": (
        "pods.json",
        lambda d: _container(
            _runtime(d)["status"], "initContainerStatuses", "verify-model"
        )["state"]["terminated"].__setitem__("exitCode", 1),
        "E01-AC9: a rule verdict is not the one the files give",
    ),
    "another commit synced": (
        "argo.json",
        lambda d: d["status"]["sync"].__setitem__("revision", "0" * 40),
        "E01-AC9: a rule verdict is not the one the files give",
    ),
    "a second Helm parameter": (
        "argo.json",
        lambda d: d["spec"]["source"]["helm"]["parameters"].append(
            {"name": "runtime.replicaCount", "value": "2"}
        ),
        "E01-AC10: a rule verdict is not the one the files give",
    ),
    "a hand-written value that the manifest does not hold": (
        "argo.json",
        lambda d: d["spec"]["source"]["helm"]["valuesObject"].__setitem__("x", 1),
        "E01-AC10: a rule verdict is not the one the files give",
    ),
    "a completion that was not answered": (
        "completion.json",
        lambda d: d.__setitem__("httpStatus", "504"),
        "E01-AC8: a rule verdict is not the one the files give",
    ),
    "an empty assistant message": (
        "completion.json",
        lambda d: d["response"]["firstChoice"].__setitem__("assistantMessageLength", 0),
        "E01-AC8: a rule verdict is not the one the files give",
    ),
    "another model identifier": (
        "completion.json",
        lambda d: d["response"].__setitem__("model", "another"),
        "E01-AC9: a rule verdict is not the one the files give",
    ),
    "another release identifier": (
        "provenance.json",
        lambda d: d[0]["release"].__setitem__("releaseId", "0" * 64),
        "E01-AC9: a rule verdict is not the one the files give",
    ),
    "an environment attribute that differs": (
        "environment.json",
        lambda d: d["identityStepP3"][2].__setitem__("read", "v1.35.0"),
        "environment.json: an attribute is not equal",
    ),
}


@pytest.fixture
def copied_real_deployment(tmp_path: Path) -> Path:
    target = tmp_path / E01_D_RUN
    shutil.copytree(E01_D_DIR, target)
    assert e01_d_findings(target) == []
    return target


@pytest.mark.parametrize("defect", sorted(E01_D_DEFECTS))
def test_a_planted_defect_in_a_copy_of_the_real_deployment_run_is_found(
    copied_real_deployment: Path, defect: str
) -> None:
    """Each defect is planted with the manifest's digest of the edited file corrected,
    so the finding comes from what the file says and not from its digest."""
    name, change, expected = E01_D_DEFECTS[defect]
    _rewrite(copied_real_deployment / name, change)
    if name != MANIFEST:
        _redigest(copied_real_deployment, name)
    assert expected in e01_d_findings(copied_real_deployment)


def test_a_changed_added_or_absent_file_of_the_real_deployment_run_is_found(
    copied_real_deployment: Path,
) -> None:
    transcript = copied_real_deployment / "transcript.txt"
    transcript.write_bytes(transcript.read_bytes() + b"x\n")
    assert "transcript.txt: does not have the recorded SHA-256" in e01_d_findings(
        copied_real_deployment
    )
    (copied_real_deployment / "extra.json").write_text("{}", encoding="utf-8")
    assert e01_d_findings(copied_real_deployment) == ["files: ['extra.json']"]
    (copied_real_deployment / "extra.json").unlink()
    (copied_real_deployment / "pods.json").unlink()
    assert e01_d_findings(copied_real_deployment) == ["files: ['pods.json']"]


#: A path on a host, in the forms a Windows host and its POSIX shell print: a drive
#: with single or doubled backslashes, a drive with a slash, a drive as a POSIX
#: directory, and a home directory.
_HOST_PATH = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:\\{1,2}[A-Za-z0-9._ -]{2,}\\"
    r"|(?<![A-Za-z0-9])[A-Za-z]:/(?!/)[A-Za-z0-9._ -]+/"
    r"|(?<![A-Za-z0-9._/-])/[a-z]/[A-Za-z0-9._ -]+/"
    r"|/(?:home|Users)/"
)


@pytest.mark.parametrize(
    "text",
    [
        "at D:\\work\\repo\\file",
        'at "D:\\\\work\\\\repo\\\\file"',
        "at D:/work/repo/file",
        "at /d/work/repo/file",
        "at /" + "home" + "/someone/repo",
        "at /c/" + "Users" + "/someone",
    ],
)
def test_the_host_path_pattern_finds_each_form(text: str) -> None:
    assert _HOST_PATH.search(text) is not None


def test_the_real_deployment_files_hold_no_host_path_and_no_message_text() -> None:
    """No file names a path on the host or the checkout's own location, and none
    holds a terminal escape. completion.json summarises the response: it has no
    choices and no message content. This reads the committed files only; it does not
    show what the uncommitted response held."""
    completion = json.loads((E01_D_DIR / "completion.json").read_text("utf-8"))
    assert completion["generatedTextKept"] is False
    assert "choices" not in completion["response"]
    assert "content" not in json.dumps(completion["response"])
    root = REPO_ROOT.as_posix()
    own = {root, root.replace("/", "\\"), root.replace("/", "\\\\")}
    if re.match(r"[A-Za-z]:/", root):
        own.add("/" + root[0].lower() + root[2:])
    for name in sorted(E01_D_FILES):
        text = (E01_D_DIR / name).read_text(encoding="utf-8")
        assert "\x1b" not in text, name
        assert _HOST_PATH.search(text) is None, name
        for form in own:
            assert form not in text, name


def test_the_real_deployment_result_page_states_limitations_before_criteria() -> None:
    manifest = json.loads((E01_D_DIR / MANIFEST).read_text(encoding="utf-8"))
    page = (E01_D_DIR / RESULT).read_text(encoding="utf-8")
    assert page.index("## Limitations") < page.index("## Criteria")
    for item in manifest["limitations"]:
        assert item in page


# --------------------------------------------------------------------------
# The independent review record of the E01-D run
# --------------------------------------------------------------------------

E01_D_REVIEW = (
    REPO_ROOT
    / "docs/proof/experiments/v2-e01/reviews"
    / f"{E01_D_RUN}-review-1.v1alpha1.json"
)


def test_the_review_record_describes_the_real_deployment_run_as_it_is() -> None:
    """The review record names this run, revision 3 by its digest, and every file of
    the run directory with the content digest the file has now. These are the checks
    the review gate makes when a ledger references the record. Since `V2-S3-005-PR1`
    one ledger does, and the tests below hold it.
    The test does not show that a review took place or what it read."""
    review = json.loads(E01_D_REVIEW.read_text(encoding="utf-8"))
    subject = review["subject"]
    assert review["kind"] == "ExperimentResultReview"
    assert subject["runId"] == E01_D_RUN
    assert subject["runPath"] == f"{RUNS_DIR}/{E01_D_RUN}"
    assert subject["parts"] == ["E01-D"]
    assert subject["files"] == {
        path.relative_to(E01_D_DIR).as_posix(): content_digest(path.read_bytes())
        for path in sorted(E01_D_DIR.rglob("*"))
        if path.is_file()
    }
    manifest = json.loads((E01_D_DIR / MANIFEST).read_text(encoding="utf-8"))
    assert subject["freeze"] == {
        "path": manifest["metadata"]["freezeRecord"],
        "revision": 3,
        "contentSha256": manifest["metadata"]["freezeContentSha256"],
    }
    assert subject["registry"]["contentSha256"] == content_digest(
        (REPO_ROOT / REGISTRY_PATH).read_bytes()
    )
    assert subject["executingRevision"] == manifest["executingRevision"]
    assert subject["outcomes"] == manifest["outcomes"]
    assert review["review"]["reviewedRevision"] != subject["executingRevision"]
    assert review["review"]["access"] == "read-only"
    assert review["review"]["reviewer"]["independenceLimits"]
    assert review["notVerified"] and review["doesNotEstablish"]
    severities = {finding["severity"] for finding in review["findings"]}
    assert severities <= {"claim-material", "non-material", "observation"}
    page = E01_D_REVIEW.with_name(f"{E01_D_RUN}-review-1.md").read_text(
        encoding="utf-8"
    )
    for name, digest in subject["files"].items():
        assert f"| `{name}` | `{digest}` |" in page
    for finding in review["findings"]:
        assert f"| {finding['id']} | {finding['severity']} |" in page


# --------------------------------------------------------------------------
# The register claim of the E01-D run
# --------------------------------------------------------------------------
#
# `V2-S3-004-PR2` ran E01-D and registered no claim, and this module then required
# that absence. `V2-S3-005-PR1` added the claim, through a ledger of its own. The tests
# below replace the absence check. They bind the claim to the run, to revision 3, and
# to the review record, and they hold the boundary the claim travels with. They read
# committed files. They do not show that the claim's wording is complete.

E01_D_CLAIM_ID = (
    "the-e01-real-deployment-run-served-one-completion-from-the-release-"
    "reconciled-from-git"
)
E01_D_LEDGER = "docs/proof/testing/v2-s3-005-pr1-e01-d-registration.v1alpha1.json"
E01_D_RUN_PATH = f"{RUNS_DIR}/{E01_D_RUN}"


def _register_claims() -> list[dict[str, Any]]:
    register = json.loads(
        (REPO_ROOT / "docs/testing/claim-evidence-matrix.v1alpha2.json").read_text(
            encoding="utf-8"
        )
    )
    claims: list[dict[str, Any]] = register["claims"]
    return claims


def _real_deployment_claim() -> dict[str, Any]:
    (claim,) = [row for row in _register_claims() if row["claimId"] == E01_D_CLAIM_ID]
    return claim


def test_one_register_claim_holds_the_real_deployment_run_at_c2() -> None:
    """Exactly one claim cites a file of the run. It is certified on one record at
    C2, which is the level and the outcome the run's own manifest records."""
    manifest = json.loads((E01_D_DIR / MANIFEST).read_text(encoding="utf-8"))
    citing = [
        row["claimId"]
        for row in _register_claims()
        if any(
            ref.startswith(f"{E01_D_RUN_PATH}/")
            for record in row["evidenceRecords"]
            for ref in record["evidenceRefs"]
        )
    ]
    assert citing == [E01_D_CLAIM_ID]
    claim = _real_deployment_claim()
    assert claim["status"] == "certified"
    assert claim["assertsRealBehaviour"] is True
    (record,) = claim["evidenceRecords"]
    assert record["evidenceLevel"] == manifest["evidenceLevel"]["level"] == "C2"
    assert manifest["outcomes"] == {"E01-D": "PASSED"}
    assert record["execution"]["targetBehaviourExecuted"] is True
    assert record["execution"]["substitutions"] == []
    executed = {row["componentId"] for row in record["execution"]["executedComponents"]}
    assert set(claim["claimMaterialComponents"]) <= executed


def test_the_register_record_names_the_identities_the_run_recorded() -> None:
    """The run, the commit, revision 3, the review record, the environment, the
    runtime image, the model revision, the release, and the one request."""
    manifest = json.loads((E01_D_DIR / MANIFEST).read_text(encoding="utf-8"))
    review = json.loads(E01_D_REVIEW.read_text(encoding="utf-8"))
    (record,) = _real_deployment_claim()["evidenceRecords"]
    refs = record["evidenceRefs"]
    for name in E01_D_FILES:
        assert f"{E01_D_RUN_PATH}/{name}" in refs, name
    assert manifest["metadata"]["freezeRecord"] == E01_D_FREEZE
    assert E01_D_FREEZE in refs
    assert E01_D_REVIEW.relative_to(REPO_ROOT).as_posix() in refs
    assert review["metadata"]["page"] in refs
    assert record["versionsRecordedIn"] == f"{E01_D_RUN_PATH}/{MANIFEST}"
    values = {row["value"] for row in record["versions"]}
    criteria = {row["id"]: row for row in manifest["criteria"]}
    observed: dict[str, Any] = {}
    for rule in criteria["E01-AC9"]["rules"]:
        observed.update(rule["observed"])
    for value in (
        manifest["executingRevision"],
        manifest["metadata"]["freezeContentSha256"],
        observed["releaseId"],
        observed["valuesSha256"],
        observed["runtimeContainerImageID"],
        observed["generatedModelRevision"],
        f"{manifest['executionIdentity']['apiImage']['reference']}"
        f"@{manifest['executionIdentity']['apiImage']['digest']}",
    ):
        assert value in values, value
    environment = json.loads((E01_D_DIR / "environment.json").read_text("utf-8"))
    frozen = {row["attribute"]: row["frozen"] for row in environment["identityStepP3"]}
    assert record["environment"]["environmentId"] == "local-kubernetes"
    assert record["environment"]["provider"] == frozen["provider.providerId"]
    assert frozen["cluster.kubernetesServerVersion"] in record["environment"]["note"]
    assert frozen["nodes.count"] == 1
    assert "one node" in record["environment"]["note"]
    assert record["workload"]["source"] == "operator-issued"
    assert (
        record["workload"]["shape"]["requestCount"]
        == (manifest["steps"]["D5"]["requestsSent"])
    )
    period = record["measurement"]["observationPeriod"]
    assert period["start"] == manifest["metadata"]["startedAt"]
    assert period["end"] == manifest["metadata"]["finishedAt"]


def test_the_register_record_states_the_frozen_criteria_and_their_outcomes() -> None:
    """Each criterion is quoted from the run's manifest, which quotes revision 3, and
    each outcome is the verdict the manifest records."""
    manifest = json.loads((E01_D_DIR / MANIFEST).read_text(encoding="utf-8"))
    (record,) = _real_deployment_claim()["evidenceRecords"]
    assert [
        (row["criterionId"], row["statement"], row["declaredBefore"], row["outcome"])
        for row in record["acceptanceCriteria"]
    ] == [
        (
            row["id"].lower(),
            row["statement"],
            True,
            "met" if row["holds"] else "not-met",
        )
        for row in manifest["criteria"]
    ]
    assert [row["id"] for row in manifest["criteria"]] == [
        "E01-AC8",
        "E01-AC9",
        "E01-AC10",
    ]
    assert {row["criterionId"] for row in record["results"]} == {
        row["criterionId"] for row in record["acceptanceCriteria"]
    }


def test_the_ledger_that_registers_the_run_references_its_review_record() -> None:
    """The ledger names the review record of this run by its content digest. The
    review gate in tools/evidence_index makes the binding checks, and
    tests/testing/test_result_review_gate.py plants each refusal."""
    ledger = json.loads((REPO_ROOT / E01_D_LEDGER).read_text(encoding="utf-8"))
    rows = {row["runPath"]: row for row in ledger["resultReviews"]}
    row = rows[E01_D_RUN_PATH]
    assert row["reviewRef"] == E01_D_REVIEW.relative_to(REPO_ROOT).as_posix()
    assert row["reviewSha256"] == content_digest(E01_D_REVIEW.read_bytes())
    (added,) = [
        change
        for change in ledger["registerChanges"]
        if change["operation"] == "add-claim"
    ]
    assert added["claim"] == _real_deployment_claim()
    assert [
        change["operation"]
        for change in ledger["registerChanges"]
        if change["operation"] != "add-claim"
    ] == ["set-claim-field"] * 3 + ["set-register-field"]
    assert not [
        change
        for change in ledger["registerChanges"]
        if change.get("field") == "status"
    ]


def test_the_claim_is_bounded_to_the_one_run_and_says_what_it_does_not_establish() -> (
    None
):
    """The claim names one run, one provider, one node, and one request, and it names
    each thing a reader might take it for. A claim edited to drop one fails here."""
    claim = _real_deployment_claim()
    (record,) = claim["evidenceRecords"]
    statement = claim["statement"]
    for phrase in (
        "In one run on 2026-10-06",
        "on the docker-desktop provider",
        "on one cluster with one node",
        "one completion request",
        "freeze revision 3",
    ):
        assert phrase in statement, phrase
    for word in (
        "every",
        "always",
        "any ",
        "all ",
        "guarantee",
        "reliabl",
        "robust",
        "stable",
        "production",
    ):
        assert word not in statement.lower(), word
    limitation = claim["limitation"]
    for phrase in (
        "Runtime, C2, about one run, 20261006-e01-d-1",
        "one API replica, one runtime replica, and one completion request",
        "warm start",
        "no person and no outside party reviewed the result",
        "is not computed over the live Application",
        "Registration, 2026-10-07: the run executed and was reviewed on 2026-10-06 "
        "in V2-S3-004, and that change registered no claim.",
        "no part of E01 ran again",
    ):
        assert phrase in limitation, phrase
    boundary = claim["doesNotEstablish"]
    for phrase in (
        "That a second request is answered",
        "another provider",
        "a sync state, a health state, pod readiness, or a replica count",
        "latency, throughput, capacity, availability, or behaviour under overload",
        "high availability",
        "a node, a zone, or a region",
        "service-level objective",
        "representative evidence, C3, or operational evidence, C4",
        "a cost, a saving, a return on investment, or a business effect",
        "production readiness",
    ):
        assert phrase in boundary, phrase
    for phrase in (
        "A script that is not committed compared the values.",
        "does not establish that this record or its claim is correct",
        "One session wrote every file of the run.",
        "no file proves it",
        "does not check that the port-forward process is alive",
    ):
        assert any(phrase in item for item in record["limitations"]), phrase
    manifest = json.loads((E01_D_DIR / MANIFEST).read_text(encoding="utf-8"))
    assert len(record["doesNotEstablish"]) >= len(manifest["doesNotEstablish"])
    assert any("registered no claim" in item for item in record["limitations"])


def test_the_two_planned_claims_stay_planned_beside_the_real_deployment_claim() -> None:
    """One run does not establish the general statements. Each planned claim keeps its
    status, cites no record, and carries a dated note that names the run."""
    claims = {row["claimId"]: row for row in _register_claims()}
    for claim_id in (
        "the-platform-serves-a-workload-the-contract-describes",
        "deployment-values-derive-only-from-a-validated-document",
    ):
        claim = claims[claim_id]
        assert claim["status"] == "planned", claim_id
        assert claim["evidenceRecords"] == [], claim_id
        assert "Update, 2026-10-07: " in claim["limitation"], claim_id
        assert E01_D_RUN in claim["limitation"], claim_id
        assert "This claim stays planned." in claim["limitation"], claim_id
