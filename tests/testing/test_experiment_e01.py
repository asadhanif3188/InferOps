"""The V2-E01 static run: the runner, the judge, and the committed run.

``tools/experiment_e01`` runs E01-A, E01-B, and E01-C as the E01 family freeze record
registers them, and judges a run from its raw evidence. This suite:

- checks every committed run against its own evidence: each file has the digest the
  manifest records, and the verdicts, outcomes, and result page computed again from
  the files are the ones the run recorded;
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
from tools.experiment_freeze import REGISTRY_PATH

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS = committed_runs(REPO_ROOT)
#: The freeze revision the committed run was registered under.
R1 = FREEZE_RECORDS[1]


def _manifest(run: Path) -> dict[str, Any]:
    document = json.loads((run / MANIFEST).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


# --------------------------------------------------------------------------
# 1. The committed run agrees with its own evidence
# --------------------------------------------------------------------------


def test_there_is_one_committed_run_of_the_static_parts() -> None:
    assert [run.name for run in RUNS] == ["20261002-e01-abc-1"]


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
    freeze = load_freeze(REPO_ROOT)
    for relative in [*GOVERNANCE, *(pin["path"] for pin in freeze["pinnedInputs"])]:
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, root / relative)
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
    # temporary checkout, as it does from a real one.
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
