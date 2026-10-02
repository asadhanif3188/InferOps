"""Experiment freeze records: every field answered, and no edit after merge.

A freeze record fixes an experiment family before its first result-bearing run.
``tools/experiment_freeze`` checks every committed record. This suite runs that check
over the committed records and plants each defect it refuses in a copy:

- a freeze field that is missing, empty, a placeholder, ``not-applicable`` without a
  reason, or ``pending`` anywhere but the one place an allowance names, with its owner;
- entries of one field that leave a part uncovered, cover one twice, or name an
  unknown part;
- a committed record whose content differs from its pin, one nobody pinned, a pin
  with no record, and revisions that skip a number, name the wrong predecessor, or
  leave a moved input unclassified.

It also holds the E01 family freeze to what its registration requires: E01-A, E01-B,
and E01-C frozen as C0 work, E01-D's procedure and criteria frozen as C2 work, E01-D's
environment identity pending with the owner the allowance names, and every input a
part names pinned by content digest.

**Nothing here runs E01.** No part's procedure executes, and no test compares the
record's expected refusals with the code: that comparison is a result-bearing run,
which may happen only after the record merges. Nor does any test compare the pins
with today's files; a change to a pinned input may merge, and the run refuses to
start until a merged revision classifies it.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tools.experiment_freeze import (
    FREEZE_FIELDS,
    FROZEN_RECORDS,
    PENDING_ALLOWED,
    RULES,
    changed_inputs,
    check_record,
    check_repository,
    content_digest,
    record_paths,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
E01 = "docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json"
README = REPO_ROOT / "docs" / "proof" / "experiments" / "README.md"


def load(path: str = E01, root: Path = REPO_ROOT) -> dict[str, Any]:
    document = json.loads((root / path).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def rules(findings: list[Any]) -> set[tuple[str, str]]:
    return {(finding.rule_id, finding.location) for finding in findings}


def entry(document: dict[str, Any], field: str, part: str) -> dict[str, Any]:
    return next(e for e in document["fields"][field] if part in e["parts"])


# --------------------------------------------------------------------------
# 1. The committed records hold every rule
# --------------------------------------------------------------------------


def test_every_committed_record_holds_every_rule() -> None:
    assert check_repository() == []


def test_the_committed_records_are_the_pinned_ones() -> None:
    assert record_paths() == sorted(FROZEN_RECORDS) == [E01]


def test_the_command_passes_over_the_committed_records() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.experiment_freeze", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASSED: 1 freeze record(s)" in result.stdout


def test_every_rule_is_published_once_and_every_field_once() -> None:
    assert len({rule.rule_id for rule in RULES}) == len(RULES) == 17
    assert len({field.key for field in FREEZE_FIELDS}) == len(FREEZE_FIELDS) == 13
    text = README.read_text(encoding="utf-8")
    for rule in RULES:
        assert f"`{rule.rule_id}`" in text, rule.rule_id
    for field in FREEZE_FIELDS:
        assert f"`{field.key}`" in text, field.key


# --------------------------------------------------------------------------
# 2. Every freeze field is answered
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key", [field.key for field in FREEZE_FIELDS])
def test_a_missing_field_is_refused(key: str) -> None:
    document = load()
    del document["fields"][key]
    assert ("freeze-field-missing", f"fields.{key}") in rules(check_record(document))


def _set_value(value: Any) -> Callable[[dict[str, Any]], None]:
    return lambda d: entry(d, "topology", "E01-D").__setitem__("value", value)


FIELD_DEFECTS: dict[str, tuple[Callable[[dict[str, Any]], None], str, str]] = {
    "an unknown field": (
        lambda d: d["fields"].__setitem__("faults", d["fields"]["fault"]),
        "freeze-field-unknown",
        "fields.faults",
    ),
    "a field with no entries": (
        lambda d: d["fields"].__setitem__("fault", []),
        "freeze-field-empty",
        "fields.fault",
    ),
    "an empty string": (
        _set_value(""),
        "freeze-field-empty",
        "fields.topology[1].value",
    ),
    "a blank string": (
        _set_value("   "),
        "freeze-field-empty",
        "fields.topology[1].value",
    ),
    "null": (_set_value(None), "freeze-field-empty", "fields.topology[1].value"),
    "an empty list": (_set_value([]), "freeze-field-empty", "fields.topology[1].value"),
    "an empty object": (
        _set_value({}),
        "freeze-field-empty",
        "fields.topology[1].value",
    ),
    "TBD": (_set_value("TBD"), "freeze-field-empty", "fields.topology[1].value"),
    "a placeholder": (
        _set_value("<topology>"),
        "freeze-field-empty",
        "fields.topology[1].value",
    ),
    "n/a written as a value": (
        _set_value("N/A"),
        "freeze-field-empty",
        "fields.topology[1].value",
    ),
    "an empty member": (
        _set_value({"runtimeReplicas": "1", "apiReplicas": ""}),
        "freeze-field-empty",
        "fields.topology[1].value",
    ),
    "a not-applicable without a reason": (
        lambda d: entry(d, "fault", "E01-A").pop("reason"),
        "freeze-field-reason-missing",
        "fields.fault[0].reason",
    ),
    "a not-applicable with a blank reason": (
        lambda d: entry(d, "fault", "E01-A").__setitem__("reason", " "),
        "freeze-field-reason-missing",
        "fields.fault[0].reason",
    ),
    "an unknown status": (
        lambda d: entry(d, "fault", "E01-A").__setitem__("status", "skipped"),
        "freeze-field-status-unknown",
        "fields.fault[0].status",
    ),
    "an empty note": (
        lambda d: entry(d, "intendedEvidenceLevel", "E01-D").__setitem__("note", ""),
        "freeze-field-empty",
        "fields.intendedEvidenceLevel[1].note",
    ),
    "an unknown evidence level": (
        lambda d: entry(d, "intendedEvidenceLevel", "E01-D").__setitem__("value", "C5"),
        "freeze-evidence-level-unknown",
        "fields.intendedEvidenceLevel[1].value",
    ),
    "a part left uncovered": (
        lambda d: entry(d, "fault", "E01-A")["parts"].remove("E01-D"),
        "freeze-field-parts",
        "fields.fault",
    ),
    "a part covered twice": (
        lambda d: entry(d, "topology", "E01-A")["parts"].append("E01-D"),
        "freeze-field-parts",
        "fields.topology",
    ),
    "an unknown part": (
        lambda d: entry(d, "fault", "E01-A")["parts"].append("E01-E"),
        "freeze-field-parts",
        "fields.fault",
    ),
}


@pytest.mark.parametrize("name", sorted(FIELD_DEFECTS))
def test_a_field_that_answers_nothing_is_refused(name: str) -> None:
    mutate, rule_id, location = FIELD_DEFECTS[name]
    document = load()
    mutate(document)
    assert (rule_id, location) in rules(check_record(document))


def _pending(field: str, part: str) -> Callable[[dict[str, Any]], None]:
    def mutate(document: dict[str, Any]) -> None:
        target = entry(document, field, part)
        target.clear()
        target.update(
            {
                "parts": [part],
                "status": "pending",
                "owner": "V2-S3-004-PR1",
                "reason": "named later",
            }
        )
        others = [e for e in document["fields"][field] if e is not target]
        for other in others:
            if part in other["parts"]:
                other["parts"].remove(part)

    return mutate


def _pending_two_parts(document: dict[str, Any]) -> None:
    entry(document, "environmentIdentity", "E01-A")["parts"].remove("E01-C")
    entry(document, "environmentIdentity", "E01-D")["parts"].insert(0, "E01-C")


PENDING_DEFECTS: dict[str, tuple[Callable[[dict[str, Any]], None], str]] = {
    "another field": (_pending("topology", "E01-D"), "fields.topology[1]"),
    "another part": (
        _pending("environmentIdentity", "E01-A"),
        "fields.environmentIdentity",
    ),
    "the wrong owner": (
        lambda d: entry(d, "environmentIdentity", "E01-D").__setitem__(
            "owner", "another-owner"
        ),
        "fields.environmentIdentity[1].owner",
    ),
    "no owner": (
        lambda d: entry(d, "environmentIdentity", "E01-D").pop("owner"),
        "fields.environmentIdentity[1].owner",
    ),
    "two parts at once": (_pending_two_parts, "fields.environmentIdentity[1]"),
    "another experiment": (
        lambda d: d["metadata"].__setitem__("experiment", "V2-E02"),
        "fields.environmentIdentity[1]",
    ),
}


@pytest.mark.parametrize("name", sorted(PENDING_DEFECTS))
def test_pending_is_refused_anywhere_the_allowance_does_not_name(name: str) -> None:
    mutate, location = PENDING_DEFECTS[name]
    document = load()
    mutate(document)
    found = [
        f
        for f in check_record(document)
        if f.rule_id == "freeze-field-pending-not-allowed"
    ]
    assert any(f.location.startswith(location) for f in found), check_record(document)


def test_a_pending_entry_without_a_reason_is_refused() -> None:
    document = load()
    entry(document, "environmentIdentity", "E01-D").pop("reason")
    assert (
        "freeze-field-reason-missing",
        "fields.environmentIdentity[1].reason",
    ) in rules(check_record(document))


def test_the_one_allowance_is_e01_ds_environment_identity() -> None:
    assert [(a.experiment, a.field, a.part, a.owner) for a in PENDING_ALLOWED] == [
        ("V2-E01", "environmentIdentity", "E01-D", "V2-S3-004-PR1")
    ]


SHAPE_DEFECTS: dict[str, Callable[[dict[str, Any]], None]] = {
    "another kind": lambda d: d.__setitem__("kind", "ExperimentRun"),
    "another version": lambda d: d.__setitem__("apiVersion", "inferops.io/v1"),
    "a revision as text": lambda d: d["metadata"].__setitem__("revision", "1"),
    "a revision as a boolean": lambda d: d["metadata"].__setitem__("revision", True),
    "no parts": lambda d: d.__setitem__("parts", []),
    "a part twice": lambda d: d["parts"].append(copy.deepcopy(d["parts"][0])),
}


@pytest.mark.parametrize("name", sorted(SHAPE_DEFECTS))
def test_a_record_of_the_wrong_shape_is_refused_before_its_fields_are_read(
    name: str,
) -> None:
    document = load()
    SHAPE_DEFECTS[name](document)
    assert [f.rule_id for f in check_record(document)] == ["freeze-record-shape"]


def test_a_record_that_is_not_an_object_is_unreadable() -> None:
    assert [f.rule_id for f in check_record(["not", "a", "record"])] == [
        "freeze-record-unreadable"
    ]


PIN_DEFECTS: dict[str, Callable[[dict[str, Any]], None]] = {
    "an absolute path": lambda d: d["pinnedInputs"][0].__setitem__(
        "path", "/etc/passwd"
    ),
    "a parent path": lambda d: d["pinnedInputs"][0].__setitem__(
        "path", "../outside.yaml"
    ),
    "a Windows path": lambda d: d["pinnedInputs"][0].__setitem__(
        "path", "charts\\x.yaml"
    ),
    "a path pinned twice": lambda d: d["pinnedInputs"].append(
        copy.deepcopy(d["pinnedInputs"][0])
    ),
    "a short digest": lambda d: d["pinnedInputs"][0].__setitem__("sha256", "abc"),
    "an uppercase digest": lambda d: d["pinnedInputs"][0].__setitem__(
        "sha256", d["pinnedInputs"][0]["sha256"].upper()
    ),
    "no role": lambda d: d["pinnedInputs"][0].pop("role"),
    "no pins": lambda d: d.__setitem__("pinnedInputs", []),
}


@pytest.mark.parametrize("name", sorted(PIN_DEFECTS))
def test_a_malformed_pin_is_refused(name: str) -> None:
    document = load()
    PIN_DEFECTS[name](document)
    assert "freeze-pinned-input-malformed" in {
        f.rule_id for f in check_record(document)
    }


# --------------------------------------------------------------------------
# 3. A merged record is never edited; a change is a new revision
# --------------------------------------------------------------------------


@pytest.fixture
def copy_root(tmp_path: Path) -> Path:
    """A copy of the records directory, under a root of its own."""
    shutil.copytree(
        REPO_ROOT / "docs" / "proof" / "experiments",
        tmp_path / "docs" / "proof" / "experiments",
    )
    return tmp_path


def _write(root: Path, path: str, document: Any) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def test_the_copy_holds_every_rule(copy_root: Path) -> None:
    assert check_repository(copy_root) == []


def test_an_edited_record_is_refused(copy_root: Path) -> None:
    document = load(root=copy_root)
    document["fields"]["fault"][0]["reason"] += " Edited after merge."
    _write(copy_root, E01, document)
    assert {f.rule_id for f in check_repository(copy_root)} == {"freeze-record-edited"}


def test_a_crlf_checkout_of_a_record_is_not_an_edit(copy_root: Path) -> None:
    target = copy_root / E01
    target.write_bytes(
        target.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    )
    assert check_repository(copy_root) == []


def test_a_record_nobody_pinned_is_refused(copy_root: Path) -> None:
    document = load(root=copy_root)
    document["metadata"]["experiment"] = "V2-E09"
    _write(copy_root, "docs/proof/experiments/v2-e09/freeze-r1.v1alpha1.json", document)
    assert ("freeze-record-unregistered", "$") in rules(check_repository(copy_root))


def test_a_pinned_record_that_is_absent_is_refused(copy_root: Path) -> None:
    (copy_root / E01).unlink()
    assert [f.rule_id for f in check_repository(copy_root)] == ["freeze-record-missing"]


def test_a_misnamed_record_and_a_wrong_revision_are_refused(copy_root: Path) -> None:
    document = load(root=copy_root)
    _write(copy_root, "docs/proof/experiments/v2-e09/freeze-r1.json", document)
    document["metadata"]["revision"] = 2
    _write(copy_root, "docs/proof/experiments/v2-e08/freeze-r1.v1alpha1.json", document)
    found = rules(check_repository(copy_root))
    assert ("freeze-revision-sequence", "$") in found
    assert ("freeze-revision-sequence", "metadata.revision") in found


R2 = "docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json"


def _revision_two(root: Path) -> dict[str, Any]:
    """A second revision that supersedes the first correctly and moves no input."""
    document = load(root=root)
    document["metadata"]["revision"] = 2
    document["metadata"]["supersedes"] = {
        "path": E01,
        "contentSha256": content_digest((root / E01).read_bytes()),
    }
    return document


def _revision_findings(root: Path) -> set[str]:
    return {
        f.rule_id
        for f in check_repository(root)
        if f.rule_id != "freeze-record-unregistered"
    }


def test_a_revision_that_follows_the_one_before_it_holds_the_revision_rules(
    copy_root: Path,
) -> None:
    _write(copy_root, R2, _revision_two(copy_root))
    assert _revision_findings(copy_root) == set()


def test_a_revision_that_names_the_wrong_predecessor_is_refused(
    copy_root: Path,
) -> None:
    document = _revision_two(copy_root)
    document["metadata"]["supersedes"]["contentSha256"] = "0" * 64
    _write(copy_root, R2, document)
    assert _revision_findings(copy_root) == {"freeze-revision-supersedes"}


def test_a_first_revision_that_supersedes_something_is_refused(copy_root: Path) -> None:
    document = load(root=copy_root)
    document["metadata"]["supersedes"] = {"path": E01, "contentSha256": "0" * 64}
    _write(copy_root, E01, document)
    assert "freeze-revision-supersedes" in {
        f.rule_id for f in check_repository(copy_root)
    }


def test_a_skipped_revision_is_refused(copy_root: Path) -> None:
    document = _revision_two(copy_root)
    document["metadata"]["revision"] = 3
    _write(copy_root, "docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json", document)
    assert "freeze-revision-sequence" in _revision_findings(copy_root)


def test_a_revision_must_classify_every_input_that_moved(copy_root: Path) -> None:
    document = _revision_two(copy_root)
    moved = document["pinnedInputs"][0]
    moved["sha256"] = "f" * 64
    _write(copy_root, R2, document)
    assert _revision_findings(copy_root) == {"freeze-input-change-unclassified"}

    document["inputChanges"] = [
        {"path": moved["path"], "material": "no", "reason": "x"}
    ]
    _write(copy_root, R2, document)
    assert _revision_findings(copy_root) == {"freeze-input-change-unclassified"}

    document["inputChanges"] = [
        {"path": moved["path"], "material": False, "reason": "A comment changed."}
    ]
    _write(copy_root, R2, document)
    assert _revision_findings(copy_root) == set()


# --------------------------------------------------------------------------
# 4. Listing the pinned inputs that moved
# --------------------------------------------------------------------------


@pytest.fixture
def pinned_root(tmp_path: Path) -> Path:
    """A root holding the E01 record and a copy of every input it pins."""
    document = load()
    for item in document["pinnedInputs"]:
        target = tmp_path / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / item["path"], target)
    shutil.copytree(
        REPO_ROOT / "docs" / "proof" / "experiments",
        tmp_path / "docs" / "proof" / "experiments",
        dirs_exist_ok=True,
    )
    return tmp_path


def test_a_copy_of_the_pinned_inputs_moved_nothing(pinned_root: Path) -> None:
    assert changed_inputs(load(), pinned_root) == []


def test_a_changed_and_an_absent_input_are_listed_and_a_crlf_one_is_not(
    pinned_root: Path,
) -> None:
    document = load()
    contract = "contracts/workload/examples/valid/synchronous-llm-local.yaml"
    renderer = "src/inferops/domain/render/helm_values.py"
    chart = "charts/inferops-llm/Chart.yaml"
    (pinned_root / contract).write_bytes(
        (pinned_root / contract).read_bytes() + b"# x\n"
    )
    (pinned_root / renderer).unlink()
    data = (pinned_root / chart).read_bytes().replace(b"\r\n", b"\n")
    (pinned_root / chart).write_bytes(data.replace(b"\n", b"\r\n"))
    changes = {
        change.path: change.actual for change in changed_inputs(document, pinned_root)
    }
    assert set(changes) == {contract, renderer}
    assert changes[renderer] is None


def _command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.experiment_freeze", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_command_reports_moved_inputs_and_an_edited_record(
    pinned_root: Path,
) -> None:
    unchanged = _command("--root", str(pinned_root), "--changes", E01)
    assert unchanged.returncode == 0, unchanged.stdout
    target = pinned_root / "uv.lock"
    target.write_bytes(target.read_bytes() + b"\n# moved\n")
    moved = _command("--root", str(pinned_root), "--changes", E01)
    assert moved.returncode == 1
    assert "CHANGED  uv.lock" in moved.stdout

    record = pinned_root / E01
    record.write_bytes(record.read_bytes() + b"\n")
    edited = _command("--root", str(pinned_root), "--check")
    assert edited.returncode == 1
    assert "freeze-record-edited" in edited.stdout

    unreadable = _command("--root", str(pinned_root), "--changes", "docs/absent.json")
    assert unreadable.returncode == 2


# --------------------------------------------------------------------------
# 5. The E01 family freeze is what its registration requires
# --------------------------------------------------------------------------


def test_e01_freezes_four_parts_a_b_and_c_at_c0_and_d_at_c2() -> None:
    document = load()
    assert [part["id"] for part in document["parts"]] == [
        "E01-A",
        "E01-B",
        "E01-C",
        "E01-D",
    ]
    levels = {
        part: entry(document, "intendedEvidenceLevel", part)["value"]
        for part in ("E01-A", "E01-B", "E01-C", "E01-D")
    }
    assert levels == {"E01-A": "C0", "E01-B": "C0", "E01-C": "C0", "E01-D": "C2"}
    assert document["metadata"]["revision"] == 1
    assert document["metadata"]["supersedes"] is None


def test_e01_ds_environment_identity_is_pending_on_its_owner_and_nothing_else_is() -> (
    None
):
    document = load()
    pending = [
        (key, e["parts"], e.get("owner"))
        for key, entries in document["fields"].items()
        for e in entries
        if e["status"] == "pending"
    ]
    assert pending == [("environmentIdentity", ["E01-D"], "V2-S3-004-PR1")]
    assert entry(document, "environmentIdentity", "E01-A")["status"] == "value"


def test_e01_states_why_a_fault_and_derived_bounds_do_not_apply() -> None:
    document = load()
    for key in ("fault", "derivedNumericBounds"):
        entries = document["fields"][key]
        assert [e["status"] for e in entries] == ["not-applicable"], key
        assert entries[0]["parts"] == ["E01-A", "E01-B", "E01-C", "E01-D"]


def test_e01_c_runs_at_least_the_four_required_kinds_of_negative_case() -> None:
    cases = next(p for p in load()["parts"] if p["id"] == "E01-C")["cases"]
    assert len({case["id"] for case in cases}) == len(cases) == 6
    assert {
        "schema-invalid",
        "semantic-invalid",
        "ownership-conflict",
        "unsupported-profile",
    } <= {case["kind"] for case in cases}
    for case in cases:
        expected = case["expected"]
        findings = expected.get("findings")
        if findings is None:
            assert expected["code"] and expected["field"], case["id"]
        else:
            assert findings, case["id"]
            for finding in findings:
                assert set(finding) == {"rule", "category", "code", "field"}, case["id"]


def test_e01_numbers_its_criteria_in_order_and_gives_every_part_one() -> None:
    document = load()
    ids = [
        criterion["id"]
        for e in document["fields"]["acceptanceCriteria"]
        for criterion in e["value"]
    ]
    assert ids == [f"E01-AC{n}" for n in range(1, 11)]
    for part in ("E01-A", "E01-B", "E01-C", "E01-D"):
        assert entry(document, "acceptanceCriteria", part)["value"], part


_REPO_PATH = re.compile(r"^[a-z][a-z0-9_.-]*(/[A-Za-z0-9_.-]+)+\.(ya?ml|json|py)$")


def _named_paths(node: Any) -> set[str]:
    if isinstance(node, str):
        return {node} if _REPO_PATH.match(node) else set()
    if isinstance(node, dict):
        return set().union(*(_named_paths(v) for v in node.values()), set())
    if isinstance(node, list):
        return set().union(*(_named_paths(v) for v in node), set())
    return set()


def test_every_input_a_part_names_is_pinned_and_so_are_the_four_the_brief_names() -> (
    None
):
    document = load()
    pinned = {item["path"]: item["role"] for item in document["pinnedInputs"]}
    named = _named_paths(document["parts"])
    assert named, "the parts name their input files"
    assert named <= set(pinned), sorted(named - set(pinned))
    roles = set(pinned.values())
    for role in ("workload-contract", "environment-binding", "renderer"):
        assert role in roles, role
    assert pinned["charts/inferops-llm/values.yaml"].startswith("platform-defaults")


def test_every_pinned_input_is_a_committed_file() -> None:
    for item in load()["pinnedInputs"]:
        assert (REPO_ROOT / item["path"]).is_file(), item["path"]


def test_e01_names_its_preparation_revision_and_no_commit_that_merges_it() -> None:
    value = load()["fields"]["gitRevision"][0]["value"]
    assert re.fullmatch(r"[0-9a-f]{40}", value["preparedFrom"])
    assert "pinnedInputs" in value["pinnedInputs"]


def test_the_record_names_only_its_own_story_and_the_pending_owner() -> None:
    text = (REPO_ROOT / E01).read_text(encoding="utf-8")
    assert set(re.findall(r"V2-S\d+-\d+-PR\d+", text)) == {
        "V2-S2-003-PR1",
        "V2-S3-004-PR1",
    }
    assert not re.search(r"[A-Za-z]:\\|/Users/|/home/", text)
