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
part names pinned by content digest. Revision 1 is history and is held to what it
was; revision 2 restores the governing no-duplication criterion, declares its
material scope, pins the runner and analysis, and classifies every change since
revision 1, added files included.

The material scope is checked on copies: an added file, a deleted one, a changed one,
a new local helper the runner imports, and a pinned file the scope no longer names are
each listed, and the import closure follows relative and absolute imports and nothing
outside its package roots.

**Nothing here runs E01.** No part's procedure executes. No test compares the pins
with today's files; a change to a material file may merge, and the run refuses to
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
    ALWAYS_ANSWERED,
    FREEZE_FIELDS,
    FROZEN_RECORDS,
    PENDING_ALLOWED,
    REGISTRY_PATH,
    RULES,
    UNSCOPED_RECORDS,
    changed_inputs,
    check_record,
    check_repository,
    content_digest,
    import_closure,
    load_registry,
    material_files,
    record_paths,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
R1 = "docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json"
R2 = "docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json"
R3 = "docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json"
#: Revision 2's registered pin, written out so that a change to it is visible.
R2_PIN = "198f60b5133338e445b1c0fef9f9171ad3e58fe3bde66ac1e7a8d1d674730ac8"
#: Revision 3's registered pin, written out for the same reason.
R3_PIN = "798309f8068d65978ce8f2ca8924e42f85c7727c10dd865bb916a5b3482745c9"
#: The next revision: a planted record that follows the latest one.
R4 = "docs/proof/experiments/v2-e01/freeze-r4.v1alpha1.json"
#: The revision every content defect below is planted in. Revision 3 follows it, so
#: a test that needs the chain to hold after an edit plants the edit in LATEST.
E01 = R2
#: The latest revision: the one a planted next revision supersedes.
LATEST = R3
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
    assert record_paths() == sorted(FROZEN_RECORDS) == [R1, R2, R3]
    assert load_registry() == dict(FROZEN_RECORDS)


def test_the_first_record_keeps_the_pin_it_was_registered_with() -> None:
    """Revision 1 is history: its pin is the one V2-S2-003-PR1 registered."""
    assert FROZEN_RECORDS[R1] == (
        "fcb19502d1d8350395b88293f4e3e2bf92076591e3fa8ecfc814defa46267fa9"
    )
    assert content_digest((REPO_ROOT / R1).read_bytes()) == FROZEN_RECORDS[R1]
    assert frozenset({R1}) == UNSCOPED_RECORDS


def test_the_command_passes_over_the_committed_records() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.experiment_freeze", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASSED: 3 freeze record(s)" in result.stdout


def test_every_rule_is_published_once_and_every_field_once() -> None:
    assert len({rule.rule_id for rule in RULES}) == len(RULES) == 22
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
        lambda d: d["metadata"].__setitem__("experiment", "EXP-OTHER"),
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


@pytest.mark.parametrize("key", sorted(ALWAYS_ANSWERED))
def test_a_field_every_run_has_is_never_not_applicable(key: str) -> None:
    document = load()
    document["fields"][key] = [
        {
            "parts": ["E01-A", "E01-B", "E01-C", "E01-D"],
            "status": "not-applicable",
            "reason": "said not to apply",
        }
    ]
    assert ("freeze-field-always-answered", f"fields.{key}[0].status") in rules(
        check_record(document)
    )


def test_the_fields_that_may_not_apply_are_the_five_a_part_can_lack() -> None:
    assert {field.key for field in FREEZE_FIELDS} - ALWAYS_ANSWERED == {
        "environmentIdentity",
        "callerProfileRevision",
        "topology",
        "fault",
        "derivedNumericBounds",
    }


def _criteria(document: dict[str, Any]) -> list[Any]:
    return entry(document, "acceptanceCriteria", "E01-A")["value"]


CRITERIA_DEFECTS: dict[str, Callable[[dict[str, Any]], None]] = {
    "no identifier": lambda d: _criteria(d)[0].pop("id"),
    "a blank statement": lambda d: _criteria(d)[0].__setitem__("statement", "."),
    "an identifier used twice": lambda d: _criteria(d)[1].__setitem__(
        "id", _criteria(d)[0]["id"]
    ),
    "an identifier used in another part": lambda d: entry(
        d, "acceptanceCriteria", "E01-D"
    )["value"][0].__setitem__("id", "E01-AC1"),
    "a criterion that is not an object": lambda d: _criteria(d).append("must pass"),
}


@pytest.mark.parametrize("name", sorted(CRITERIA_DEFECTS))
def test_a_malformed_criterion_is_refused(name: str) -> None:
    document = load()
    CRITERIA_DEFECTS[name](document)
    assert "freeze-criteria-malformed" in {f.rule_id for f in check_record(document)}


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
    document = load(LATEST, root=copy_root)
    document["fields"]["fault"][0]["reason"] += " Edited after merge."
    _write(copy_root, LATEST, document)
    assert {f.rule_id for f in check_repository(copy_root)} == {"freeze-record-edited"}


def test_an_edit_to_a_superseded_record_also_breaks_the_revision_after_it(
    copy_root: Path,
) -> None:
    """Revision 3 names revision 2's content digest, so an edit to revision 2 is
    reported twice: against its pin, and against the record that supersedes it."""
    document = load(R2, root=copy_root)
    document["fields"]["fault"][0]["reason"] += " Edited after merge."
    _write(copy_root, R2, document)
    assert {(f.rule_id, f.record) for f in check_repository(copy_root)} == {
        ("freeze-record-edited", R2),
        ("freeze-revision-supersedes", R3),
    }


def test_a_crlf_checkout_of_a_record_is_not_an_edit(copy_root: Path) -> None:
    target = copy_root / E01
    target.write_bytes(
        target.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    )
    assert check_repository(copy_root) == []


def test_a_record_nobody_pinned_is_refused(copy_root: Path) -> None:
    document = load(root=copy_root)
    document["metadata"]["experiment"] = "EXP-OTHER"
    _write(
        copy_root, "docs/proof/experiments/exp-other/freeze-r1.v1alpha1.json", document
    )
    assert ("freeze-record-unregistered", "$") in rules(check_repository(copy_root))


def test_a_pinned_record_that_is_absent_is_refused(copy_root: Path) -> None:
    (copy_root / LATEST).unlink()
    assert [f.rule_id for f in check_repository(copy_root)] == ["freeze-record-missing"]


def test_a_misnamed_record_and_a_wrong_revision_are_refused(copy_root: Path) -> None:
    document = load(root=copy_root)
    _write(copy_root, "docs/proof/experiments/exp-a/freeze-r1.json", document)
    document["metadata"]["revision"] = 2
    _write(copy_root, "docs/proof/experiments/exp-b/freeze-r1.v1alpha1.json", document)
    found = rules(check_repository(copy_root))
    assert ("freeze-revision-sequence", "$") in found
    assert ("freeze-revision-sequence", "metadata.revision") in found


def _next_revision(root: Path) -> dict[str, Any]:
    """A next revision that supersedes the latest correctly and moves no input."""
    document = load(LATEST, root=root)
    document["metadata"]["revision"] = 4
    document["metadata"]["supersedes"] = {
        "path": LATEST,
        "contentSha256": content_digest((root / LATEST).read_bytes()),
    }
    document["inputChanges"] = []
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
    _write(copy_root, R4, _next_revision(copy_root))
    assert _revision_findings(copy_root) == set()


def test_a_revision_that_names_the_wrong_predecessor_is_refused(
    copy_root: Path,
) -> None:
    document = _next_revision(copy_root)
    document["metadata"]["supersedes"]["contentSha256"] = "0" * 64
    _write(copy_root, R4, document)
    assert _revision_findings(copy_root) == {"freeze-revision-supersedes"}


def test_a_first_revision_that_supersedes_something_is_refused(copy_root: Path) -> None:
    document = load(R1, root=copy_root)
    document["metadata"]["supersedes"] = {"path": R1, "contentSha256": "0" * 64}
    _write(copy_root, R1, document)
    assert "freeze-revision-supersedes" in {
        f.rule_id for f in check_repository(copy_root)
    }


def test_a_skipped_revision_is_refused(copy_root: Path) -> None:
    document = _next_revision(copy_root)
    document["metadata"]["revision"] = 5
    _write(copy_root, "docs/proof/experiments/v2-e01/freeze-r5.v1alpha1.json", document)
    assert "freeze-revision-sequence" in _revision_findings(copy_root)


def test_a_revision_must_classify_every_input_that_moved(copy_root: Path) -> None:
    document = _next_revision(copy_root)
    moved = document["pinnedInputs"][0]
    moved["sha256"] = "f" * 64
    _write(copy_root, R4, document)
    assert _revision_findings(copy_root) == {"freeze-input-change-unclassified"}

    document["inputChanges"] = [
        {"path": moved["path"], "material": "no", "reason": "x"}
    ]
    _write(copy_root, R4, document)
    assert _revision_findings(copy_root) == {"freeze-input-change-unclassified"}

    document["inputChanges"] = [
        {"path": moved["path"], "material": False, "reason": "A comment changed."}
    ]
    _write(copy_root, R4, document)
    assert _revision_findings(copy_root) == set()


def test_a_revision_must_classify_an_input_it_pins_for_the_first_time(
    copy_root: Path,
) -> None:
    """An added file is a change, as revision 2 classified the runner it added."""
    document = _next_revision(copy_root)
    document["pinnedInputs"].append(
        {
            "path": "tools/new_helper.py",
            "role": "runner-and-analysis",
            "sha256": "e" * 64,
        }
    )
    _write(copy_root, R4, document)
    assert _revision_findings(copy_root) == {"freeze-input-change-unclassified"}


def test_revision_two_classifies_every_input_that_moved_since_revision_one() -> None:
    before = {i["path"]: i["sha256"] for i in load(R1)["pinnedInputs"]}
    after = {i["path"]: i["sha256"] for i in load(R2)["pinnedInputs"]}
    moved = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
    classified = {c["path"]: c for c in load(R2)["inputChanges"]}
    assert set(classified) == moved
    added = {p for p in moved if p not in before}
    assert added == {
        "tools/__init__.py",
        "tools/experiment_e01/__init__.py",
        "tools/experiment_e01/__main__.py",
        "tools/experiment_e01/core.py",
        "tools/experiment_freeze/__init__.py",
        "tools/experiment_freeze/core.py",
        "tools/generated_release/__init__.py",
    }
    for path in added:
        assert classified[path]["change"] == "added"
        assert classified[path]["material"] is True


# --------------------------------------------------------------------------
# 3a. The registry and the material scope
# --------------------------------------------------------------------------


def test_an_unreadable_registry_is_refused(copy_root: Path) -> None:
    (copy_root / REGISTRY_PATH).write_text("[]\n", encoding="utf-8")
    found = {f.rule_id for f in check_repository(copy_root)}
    assert "freeze-registry-unreadable" in found
    assert "freeze-record-unregistered" in found


def test_a_registry_that_pins_a_record_twice_is_refused(copy_root: Path) -> None:
    registry = json.loads((copy_root / REGISTRY_PATH).read_text(encoding="utf-8"))
    registry["records"].append(dict(registry["records"][0]))
    _write(copy_root, REGISTRY_PATH, registry)
    with pytest.raises(ValueError):
        load_registry(copy_root)


def test_a_record_without_a_scope_is_refused_unless_registered_before_scopes() -> None:
    document = load()
    del document["materialScope"]
    assert ("freeze-scope-missing", "materialScope") in rules(
        check_record(document, E01)
    )
    assert check_record(load(R1), R1) == []


@pytest.mark.parametrize(
    "defect",
    [
        lambda scope: scope.__setitem__("entryModules", []),
        lambda scope: scope.__setitem__("entryModules", ["elsewhere.module"]),
        lambda scope: scope.__setitem__("packageRoots", {"tools": "/abs"}),
        lambda scope: scope.__setitem__("paths", ["../outside.yaml"]),
        lambda scope: scope.__setitem__("paths", ["C:/outside.yaml"]),
        lambda scope: scope.__setitem__("packageRoots", {"tools": "C:tools"}),
        lambda scope: scope.__setitem__("exclusions", [{"path": "uv.lock"}]),
    ],
)
def test_a_malformed_scope_is_refused(defect: Callable[[dict[str, Any]], None]) -> None:
    document = load()
    defect(document["materialScope"])
    assert "freeze-scope-malformed" in {f.rule_id for f in check_record(document, E01)}


def test_revision_two_pins_exactly_its_material_scope(pinned_root: Path) -> None:
    """At registration, the pins and the scope are the same set of files. The scope is
    computed over a tree that holds each pinned file as it was pinned, so this does
    not compare the pins with today's files."""
    document = load()
    pinned = {item["path"] for item in document["pinnedInputs"]}
    assert material_files(document["materialScope"], pinned_root) == pinned
    assert len(pinned) == 74
    assert "tools/experiment_e01/core.py" in pinned
    assert "tools/experiment_freeze/core.py" in pinned
    assert REGISTRY_PATH not in pinned
    assert R2 not in pinned


def test_every_registered_record_keeps_the_pin_it_was_registered_with() -> None:
    """The registry is a file a change can edit, together with the record. These
    literal pins are what a reviewer sees move if one does; nothing else stops it."""
    assert FROZEN_RECORDS == {
        R1: "fcb19502d1d8350395b88293f4e3e2bf92076591e3fa8ecfc814defa46267fa9",
        R2: R2_PIN,
        R3: R3_PIN,
    }


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tmp_path


def test_the_import_closure_follows_local_imports_and_nothing_else(
    tmp_path: Path,
) -> None:
    root = _tree(
        tmp_path,
        {
            "tools/__init__.py": "",
            "tools/run/__init__.py": "from .core import go\n",
            "tools/run/__main__.py": "from . import go\n",
            "tools/run/core.py": (
                "import json\nimport yaml\nfrom pkg.a import b\n"
                "def go():\n    from tools.helper import x\n"
            ),
            "tools/helper.py": "x = 1\n",
            "tools/unused.py": "y = 2\n",
            "src/pkg/__init__.py": "",
            "src/pkg/a/__init__.py": "from .b import c\n",
            "src/pkg/a/b.py": "c = 3\n",
            "src/pkg/z.py": "",
        },
    )
    closure = import_closure(["tools.run.__main__"], {"tools": ".", "pkg": "src"}, root)
    assert closure == {
        "tools/__init__.py",
        "tools/run/__init__.py",
        "tools/run/__main__.py",
        "tools/run/core.py",
        "tools/helper.py",
        "src/pkg/__init__.py",
        "src/pkg/a/__init__.py",
        "src/pkg/a/b.py",
    }


def test_an_import_in_the_wrong_case_resolves_to_nothing_on_every_host(
    tmp_path: Path,
) -> None:
    """Windows would open tools/Helper.py for ``tools.helper``; Linux would not. The
    closure follows the directory listing, so both give the same scope."""
    root = _tree(
        tmp_path,
        {
            "tools/__init__.py": "",
            "tools/run.py": "from tools.helper import x\n",
            "tools/Helper.py": "x = 1\n",
        },
    )
    assert import_closure(["tools.run"], {"tools": "."}, root) == {
        "tools/__init__.py",
        "tools/run.py",
    }


def test_material_files_add_paths_and_patterns_and_drop_exclusions(
    tmp_path: Path,
) -> None:
    root = _tree(
        tmp_path,
        {
            "tools/__init__.py": "",
            "tools/run.py": "",
            "charts/c/templates/a.yaml": "",
            "charts/c/templates/sub/b.yaml": "",
            "charts/c/README.md": "",
            "uv.lock": "",
            "tools/__pycache__/run.cpython-312.pyc": "",
        },
    )
    scope = {
        "entryModules": ["tools.run"],
        "packageRoots": {"tools": "."},
        "paths": ["charts/c/templates/**/*", "uv.lock"],
        "exclusions": [{"path": "uv.lock", "reason": "a planted exclusion"}],
    }
    assert material_files(scope, root) == {
        "tools/__init__.py",
        "tools/run.py",
        "charts/c/templates/a.yaml",
        "charts/c/templates/sub/b.yaml",
    }


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
    defaults = "charts/inferops-llm/values.schema.json"
    chart = "charts/inferops-llm/Chart.yaml"
    (pinned_root / contract).write_bytes(
        (pinned_root / contract).read_bytes() + b"# x\n"
    )
    (pinned_root / defaults).unlink()
    data = (pinned_root / chart).read_bytes().replace(b"\r\n", b"\n")
    (pinned_root / chart).write_bytes(data.replace(b"\n", b"\r\n"))
    changes = {
        change.path: (change.kind, change.actual)
        for change in changed_inputs(document, pinned_root)
    }
    assert set(changes) == {contract, defaults}
    assert changes[defaults] == ("absent", None)
    assert changes[contract][0] == "changed"


def test_an_added_material_file_is_listed(pinned_root: Path) -> None:
    """The F2 gap: a file the record never listed is a change, not invisible."""
    added = "charts/inferops-llm/templates/extra.yaml"
    (pinned_root / added).write_text("kind: ConfigMap\n", encoding="utf-8")
    changes = [(c.path, c.kind, c.pinned) for c in changed_inputs(load(), pinned_root)]
    assert changes == [(added, "added", None)]


def test_a_new_local_helper_the_runner_imports_is_listed(pinned_root: Path) -> None:
    runner = pinned_root / "tools" / "experiment_e01" / "core.py"
    runner.write_text(
        runner.read_text(encoding="utf-8") + "\nfrom . import helper  # noqa\n",
        encoding="utf-8",
    )
    (runner.parent / "helper.py").write_text("x = 1\n", encoding="utf-8")
    changes = {c.path: c.kind for c in changed_inputs(load(), pinned_root)}
    assert changes == {
        "tools/experiment_e01/core.py": "changed",
        "tools/experiment_e01/helper.py": "added",
    }


def test_a_pinned_file_the_scope_no_longer_names_is_listed(pinned_root: Path) -> None:
    runner = pinned_root / "tools" / "experiment_e01" / "core.py"
    text = runner.read_text(encoding="utf-8")
    line = "from tools.generated_release.core import _chart_api_defaults\n"
    assert line in text
    runner.write_text(text.replace(line, ""), encoding="utf-8")
    changes = {c.path: c.kind for c in changed_inputs(load(), pinned_root)}
    assert changes["tools/experiment_e01/core.py"] == "changed"
    assert changes["tools/generated_release/core.py"] == "unscoped"
    assert changes["tools/generated_release/__init__.py"] == "unscoped"


def test_revision_one_still_lists_only_its_own_pins(pinned_root: Path) -> None:
    """A record registered before scopes is checked as it was: an added file it never
    listed is invisible to it. That is the gap revision 2 closes."""
    (pinned_root / "charts/inferops-llm/templates/extra.yaml").write_text(
        "x: 1\n", encoding="utf-8"
    )
    paths = {c.path for c in changed_inputs(load(R1), pinned_root)}
    assert "charts/inferops-llm/templates/extra.yaml" not in paths


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


@pytest.mark.parametrize("path", [R1, R2])
def test_e01_freezes_four_parts_a_b_and_c_at_c0_and_d_at_c2(path: str) -> None:
    document = load(path)
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
    if path == R1:
        assert document["metadata"]["revision"] == 1
        assert document["metadata"]["supersedes"] is None
    else:
        assert document["metadata"]["revision"] == 2
        assert document["metadata"]["supersedes"] == {
            "path": R1,
            "contentSha256": FROZEN_RECORDS[R1],
        }


@pytest.mark.parametrize("path", [R1, R2])
def test_e01_ds_environment_identity_is_pending_on_its_owner_and_nothing_else_is(
    path: str,
) -> None:
    document = load(path)
    pending = [
        (key, e["parts"], e.get("owner"))
        for key, entries in document["fields"].items()
        for e in entries
        if e["status"] == "pending"
    ]
    assert pending == [("environmentIdentity", ["E01-D"], "V2-S3-004-PR1")]
    assert entry(document, "environmentIdentity", "E01-A")["status"] == "value"


@pytest.mark.parametrize("path", [R1, R2, R3])
def test_e01_states_why_a_fault_and_derived_bounds_do_not_apply(path: str) -> None:
    document = load(path)
    for key in ("fault", "derivedNumericBounds"):
        entries = document["fields"][key]
        assert [e["status"] for e in entries] == ["not-applicable"], key
        assert entries[0]["parts"] == ["E01-A", "E01-B", "E01-C", "E01-D"]


@pytest.mark.parametrize(("path", "count"), [(R1, 6), (R2, 7), (R3, 7)])
def test_e01_c_runs_at_least_the_four_required_kinds_of_negative_case(
    path: str, count: int
) -> None:
    cases = next(p for p in load(path)["parts"] if p["id"] == "E01-C")["cases"]
    assert len({case["id"] for case in cases}) == len(cases) == count
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


@pytest.mark.parametrize("path", [R1, R2, R3])
def test_e01_numbers_its_criteria_in_order_and_gives_every_part_one(path: str) -> None:
    document = load(path)
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


@pytest.mark.parametrize(
    ("path", "roles"),
    [
        (R1, ("workload-contract", "environment-binding", "renderer")),
        (
            R2,
            (
                "workload-contract",
                "environment-binding",
                "product-code",
                "runner-and-analysis",
                "freeze-checker",
            ),
        ),
        (
            R3,
            (
                "workload-contract",
                "environment-binding",
                "product-code",
                "runner-and-analysis",
                "freeze-checker",
                "desired-state-release",
                "argocd-manifest",
                "environment-procedure",
            ),
        ),
    ],
)
def test_every_input_a_part_names_is_pinned_and_so_are_the_ones_the_brief_names(
    path: str, roles: tuple[str, ...]
) -> None:
    document = load(path)
    pinned = {item["path"]: item["role"] for item in document["pinnedInputs"]}
    named = _named_paths(document["parts"])
    assert named, "the parts name their input files"
    assert named <= set(pinned), sorted(named - set(pinned))
    for role in roles:
        assert role in set(pinned.values()), role
    assert pinned["charts/inferops-llm/values.yaml"].startswith("platform-defaults")


@pytest.mark.parametrize("path", [R1, R2, R3])
def test_every_pinned_input_is_a_committed_file(path: str) -> None:
    for item in load(path)["pinnedInputs"]:
        assert (REPO_ROOT / item["path"]).is_file(), item["path"]


@pytest.mark.parametrize("path", [R1, R2, R3])
def test_e01_names_its_preparation_revision_and_no_commit_that_merges_it(
    path: str,
) -> None:
    value = load(path)["fields"]["gitRevision"][0]["value"]
    assert re.fullmatch(r"[0-9a-f]{40}", value["preparedFrom"])
    assert "pinnedInputs" in value["pinnedInputs"]


@pytest.mark.parametrize(
    ("path", "stories"),
    [
        (R1, {"V2-S2-003-PR1", "V2-S3-004-PR1"}),
        (R2, {"V2-S2-004-PR1", "V2-S3-004-PR1"}),
        (R3, {"V2-S3-004-PR1"}),
    ],
)
def test_the_record_names_only_its_own_story_and_the_pending_owner(
    path: str, stories: set[str]
) -> None:
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    assert set(re.findall(r"V2-S\d+-\d+-PR\d+", text)) == stories
    assert not re.search(r"[A-Za-z]:\\|/Users/|/home/", text)


def test_revision_one_states_the_exception_revision_two_removes() -> None:
    """History is kept: revision 1 still carries the exception the review rejected."""
    assert "except the model's download URL" in load(R1)["definition"]["hypothesis"]


def test_revision_two_restores_the_governing_no_duplication_criterion() -> None:
    document = load(R2)
    assert document["definition"]["hypothesis"].endswith(
        "and no claim-relevant workload intent is written again by hand after "
        "rendering."
    )
    statements = {
        criterion["id"]: criterion["statement"]
        for e in document["fields"]["acceptanceCriteria"]
        for criterion in e["value"]
    }
    for criterion in ("E01-AC5", "E01-AC10"):
        assert "except the model" not in statements[criterion], criterion
        assert "eight characters" in statements[criterion], criterion
    text = json.dumps(document)
    assert "sourceUrl and model.license.reference strings" not in text


def test_revision_two_records_the_first_runs_audit_and_the_preview_evidence() -> None:
    history = load(R2)["history"]
    assert [run["runId"] for run in history["priorRuns"]] == ["20261002-e01-abc-1"]
    assert "not available" in history["previewEvidence"]
    assert "not preregistered" not in history["previewEvidence"]
    assert "None was preregistered" in history["previewEvidence"]


def test_revision_two_defines_its_non_result_executions_before_any_run() -> None:
    definition = load(R2)["definition"]
    classes = [item["class"] for item in definition["nonResultExecutions"]]
    assert classes == [
        "test-suite",
        "committed-run-check",
        "freeze-check",
        "registration-calibration",
    ]
    assert "not permitted" in definition["previewRule"]
    assert "procedure" in definition["previewRule"]


# --------------------------------------------------------------------------
# 6. Revision 3 names the E01-D environment and changes one clause
# --------------------------------------------------------------------------

STATIC_PARTS = ("E01-A", "E01-B", "E01-C")


def _statements(document: dict[str, Any]) -> dict[str, str]:
    return {
        criterion["id"]: criterion["statement"]
        for e in document["fields"]["acceptanceCriteria"]
        for criterion in e["value"]
    }


def _part(document: dict[str, Any], part: str) -> dict[str, Any]:
    found = next(p for p in document["parts"] if p["id"] == part)
    assert isinstance(found, dict)
    return found


def test_revision_three_supersedes_revision_two_and_freezes_the_same_four_parts() -> (
    None
):
    document = load(R3)
    assert document["metadata"]["revision"] == 3
    assert document["metadata"]["registeredBy"] == "V2-S3-004-PR1"
    assert document["metadata"]["supersedes"] == {"path": R2, "contentSha256": R2_PIN}
    assert [part["id"] for part in document["parts"]] == [*STATIC_PARTS, "E01-D"]
    levels = {
        part: entry(document, "intendedEvidenceLevel", part)["value"]
        for part in (*STATIC_PARTS, "E01-D")
    }
    assert levels == {"E01-A": "C0", "E01-B": "C0", "E01-C": "C0", "E01-D": "C2"}


def test_revision_three_leaves_nothing_pending_and_names_the_environment() -> None:
    """The one allowance was for the field this revision answers. The checker still
    holds the allowance, so this test is what says the latest record does not use it."""
    document = load(R3)
    statuses = {e["status"] for entries in document["fields"].values() for e in entries}
    assert "pending" not in statuses
    environment = entry(document, "environmentIdentity", "E01-D")
    assert environment["status"] == "value"
    identity = environment["value"]["identity"]
    assert set(identity) >= {
        "provider",
        "cluster",
        "nodes",
        "storage",
        "gitopsController",
        "desiredState",
        "application",
        "contract",
        "environmentBinding",
        "runtime",
        "model",
        "apiImage",
    }
    assert identity["provider"]["providerId"] == "docker-desktop"
    assert identity["provider"]["paid"] is False
    assert identity["nodes"]["count"] == len(identity["nodes"]["names"]) == 1
    version = identity["cluster"]["kubernetesServerVersion"]
    assert re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", version)
    assert re.fullmatch(r".+@sha256:[0-9a-f]{64}", identity["runtime"]["image"])
    assert re.fullmatch(r"[0-9a-f]{40}", identity["model"]["revision"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", identity["model"]["sha256"])


def test_revision_three_keeps_the_static_parts_as_revision_two_froze_them() -> None:
    before, after = load(R2), load(R3)
    for key in ("hypothesis", "scope", "outcomeStates", "repetitionRule"):
        assert after["definition"][key] == before["definition"][key], key
    for part in STATIC_PARTS:
        assert _part(after, part) == _part(before, part), part
    for key in (
        "environmentIdentity",
        "callerProfileRevision",
        "topology",
        "repetitionCount",
        "acceptanceCriteria",
        "evidencePaths",
        "abortConditions",
        "cleanupProcedure",
        "intendedEvidenceLevel",
    ):
        for part in STATIC_PARTS:
            assert entry(after, key, part) == entry(before, key, part), (key, part)
    assert entry(after, "repetitionCount", "E01-D") == entry(
        before, "repetitionCount", "E01-D"
    )


def test_revision_three_changes_one_clause_of_one_criterion_and_records_it() -> None:
    before, after = _statements(load(R2)), _statements(load(R3))
    assert list(after) == list(before)
    changed = [key for key in before if before[key] != after[key]]
    assert changed == ["E01-AC10"]
    (change,) = load(R3)["criteriaChanges"]
    assert change["id"] == "E01-AC10"
    assert change["previousStatement"] == before["E01-AC10"]
    assert change["statement"] == after["E01-AC10"]
    assert "with no parameter override" in change["previousStatement"]
    statement = after["E01-AC10"]
    assert statement.startswith(
        "No claim-relevant workload intent is written by hand after rendering: no "
        "hand-written value and no operator-supplied parameter of the release "
        "restates or overrides claim-relevant workload intent;"
    )
    assert "api.image.digest" in statement
    assert "from no other source" in statement
    assert "eight characters" in statement
    assert "except the model" not in statement
    for key in ("why", "whyTheParameterIsPermitted", "approvedBy", "whatDidNotChange"):
        assert change[key].strip(), key
    assert "No E01-D run had executed" in change["resultsObservedBefore"]


def test_revision_three_keeps_every_pin_of_revision_two_and_only_adds() -> None:
    before = {i["path"]: i["sha256"] for i in load(R2)["pinnedInputs"]}
    document = load(R3)
    after = {i["path"]: i["sha256"] for i in document["pinnedInputs"]}
    assert {path: after.get(path) for path in before} == before
    added = set(after) - set(before)
    classified = {c["path"]: c for c in document["inputChanges"]}
    assert set(classified) == added
    assert len(after) == 158
    assert len(added) == 84
    for path, change in classified.items():
        assert change["change"] == "added", path
        assert change["material"] is True, path
        assert change["materialTo"] == ["E01-D"], path
        assert change["materialToStaticResult"] is False, path
        assert change["sinceRevision2Merged"] in ("unchanged", "added", "changed")


def test_revision_three_pins_exactly_its_material_scope(tmp_path: Path) -> None:
    """As for revision 2: the scope is computed over a tree that holds each pinned
    file, so this does not compare the pins with today's content."""
    document = load(R3)
    pinned = {item["path"] for item in document["pinnedInputs"]}
    for path in pinned:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / path, target)
    assert material_files(document["materialScope"], tmp_path) == pinned
    assert REGISTRY_PATH not in pinned
    assert not {R1, R2, R3} & pinned
    release = "gitops/environments/local-docker-desktop/workloads/support-assistant"
    for path in (
        f"{release}/values.generated.yaml",
        f"{release}/rendered-workload-release.yaml",
        "infra/argocd/local-docker-desktop-support-assistant.yaml",
        "infra/argocd/workloads-project.yaml",
        "scripts/environment/argocd-application.sh",
        "scripts/environment/argocd-bootstrap.sh",
        "scripts/environment/lib.sh",
        "contracts/environment/examples/valid/local-docker-desktop.yaml",
        "tools/gitops_desired_state/core.py",
        "tools/desired_state_provenance/core.py",
        "tools/reconciliation_evidence/core.py",
        "src/inferops/api/__init__.py",
    ):
        assert path in pinned, path


def test_revision_three_accounts_for_every_file_changed_since_revision_two() -> None:
    document = load(R3)
    changes = document["changesSinceSupersededRevision"]
    rows = changes["files"]
    paths = [row["path"] for row in rows]
    assert paths == sorted(set(paths))
    assert re.fullmatch(r"[0-9a-f]{40}", changes["from"])
    prepared = document["fields"]["gitRevision"][0]["value"]["preparedFrom"]
    assert changes["to"] == prepared
    pinned = {item["path"] for item in document["pinnedInputs"]}
    in_scope = [row for row in rows if row["inScope"]]
    assert changes["counts"] == {
        "files": len(rows),
        "added": sum(1 for row in rows if row["change"] == "added"),
        "changed": sum(1 for row in rows if row["change"] == "changed"),
        "deleted": 0,
        "inScope": len(in_scope),
        "outsideScope": len(rows) - len(in_scope),
    }
    revision_two = {item["path"] for item in load(R2)["pinnedInputs"]}
    for row in rows:
        assert isinstance(row["material"], bool), row["path"]
        assert row["reason"].strip(), row["path"]
        assert row["inScope"] == (row["path"] in pinned), row["path"]
        assert row["material"] == row["inScope"], row["path"]
        assert row["path"] not in revision_two, row["path"]
        if not row["inScope"]:
            assert row["category"].strip(), row["path"]


def test_revision_three_registers_the_e01_d_path_steps_and_rules() -> None:
    document = load(R3)
    part = _part(document, "E01-D")
    inputs = part["inputs"]
    assert inputs["bindingName"] == "local-docker-desktop"
    release = inputs["desiredStateRelease"]
    assert release["directory"] == (
        "gitops/environments/local-docker-desktop/workloads/support-assistant"
    )
    for key in ("releaseId", "helmValuesSha256", "contractSha256"):
        assert re.fullmatch(r"[0-9a-f]{64}", release[key]), key
    application = inputs["application"]
    assert application["name"] == "local-docker-desktop-support-assistant"
    assert application["targetRevision"] == "main"
    assert application["valueFiles"] == [
        f"/{release['directory']}/values.generated.yaml"
    ]
    assert inputs["operatorParameter"]["name"] == "api.image.digest"
    request = inputs["request"]
    assert (request["method"], request["path"]) == ("POST", "/v1/chat/completions")
    assert request["count"] == 1
    assert request["body"]["stream"] is False
    assert [step["step"] for step in part["preparation"]] == [
        f"P{n}" for n in range(1, 8)
    ]
    assert [step["step"] for step in part["procedure"]] == [
        f"D{n}" for n in range(1, 7)
    ]
    frozen = _part(load(R2), "E01-D")["procedure"]
    for index in (3, 4, 5):
        assert part["procedure"][index]["frozenStep"] == frozen[index], index
    commands = [c for step in part["procedure"] for c in step["commands"]]
    applies = [c for c in commands if "argocd-application.sh apply" in c]
    assert applies == [
        "bash scripts/environment/argocd-application.sh apply "
        "--api-image-digest <api-image-digest>"
    ]
    assert not any("--set" in c or c.startswith("helm ") for c in commands)
    for criterion in ("E01-AC8", "E01-AC9", "E01-AC10"):
        assert part["verification"][criterion], criterion
    replaced = document["procedureChanges"]["changes"]
    assert len(replaced) == 3
    for change in replaced:
        assert change["revision2"].strip() and change["why"].strip()
    assert "with no parameter override" in replaced[0]["revision2"]


def test_revision_three_keeps_the_history_and_discloses_the_earlier_cluster_runs() -> (
    None
):
    before, after = load(R2), load(R3)
    history = after["history"]
    earlier = history["earlierHistory"]
    assert earlier["priorRuns"] == before["history"]["priorRuns"]
    assert earlier["previewEvidence"] == before["history"]["previewEvidence"]
    assert [run["runId"] for run in history["priorRuns"]] == [
        "20261002-e01-abc-1",
        "20261003-e01-abc-1",
    ]
    assert history["priorRuns"][0] == before["history"]["priorRuns"][0]
    runs = history["environmentRunsBeforeRegistration"]["runs"]
    assert len(runs) == 3
    for run in runs:
        assert (REPO_ROOT / run["record"]).is_file(), run["record"]
    assert "one returned no response" in runs[1]["what"]
    classes = [c["class"] for c in after["definition"]["nonResultExecutions"]]
    assert classes == [
        "test-suite",
        "committed-run-check",
        "freeze-check",
        "registration-calibration",
        "environment-identity-read",
        "environment-procedure-runs-before-registration",
        "procedure-stub-tests",
    ]
    consumed = after["definition"]["staticResultConsumed"]
    assert consumed["runId"] == "20261003-e01-abc-1"
    assert consumed["freezeRevision"] == 2
    assert (REPO_ROOT / consumed["run"]).is_file()
    gate = after["definition"]["reviewGate"]
    assert (REPO_ROOT / gate["notReused"].split(" ")[0]).is_file()


def test_revision_three_says_that_no_runner_exists_for_e01_d() -> None:
    definition = load(R3)["definition"]
    limitations = " ".join(definition["limitations"])
    assert "No runner and no coded analysis exist for E01-D" in limitations
    assert "CURRENT_REVISION is 2" in limitations
    assert "The API image digest is not in Git" in limitations
    for item in load(R2)["definition"]["limitations"]:
        assert item in definition["limitations"]
