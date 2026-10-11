"""The directory of an experiment run: its layout and its integrity check.

Every check here reads files from this repository, or files it writes under a
temporary directory, and nothing else. No network, no cluster, no clock, no
randomness. **No run executed.** Each run directory that a test checks is built by
the test: a manifest from a committed ExperimentRun fixture, a freeze record that
states one revision, a caller record that the runner's own loop writes against a
scripted answer, and a few lines of text for each other file. Two tests read a
committed run directory, the E01-D one, and each holds that it is refused at its
manifest.

Six things are asserted that a plain "the files have their digests" suite would not
catch:

1. **One file has one digest in each tool.** The layout's digest is the evidence
   index's digest of a text file, a CRLF checkout does not move it, and the result
   review gate reads a run of this layout.
2. **A directory is closed in both directions.** A named file that is absent is
   refused, and so is a file that is present and not named.
3. **A generated summary is downstream of raw evidence.** A derived file with no
   raw file is refused, and a corrected summary moves the set digest and not the
   raw digest.
4. **A correction is additive.** It is a file beside the ``runs`` directory, it
   moves no digest of the run, and a correction of a file that was edited is
   refused.
5. **The layout requires no file that holds a secret, a prompt, or a path of a
   host.** A run with no evidence file conforms, and the two text rules refuse what
   they are stated to refuse.
6. **The gaps are measured.** What the rules still accept is asserted, so closing
   a gap is a visible change.
"""

from __future__ import annotations

import copy
import io
import json
import os
import re
import shutil
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tools import evidence_index, experiment_evidence
from tools.evidence_index import core as index_core
from tools.experiment_evidence import __main__ as command
from tools.experiment_evidence import core
from tools.experiment_run import core as run_core
from tools.reliability_runner import core as runner_core
from tools.reliability_runner import incluster

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYOUT_DOC = REPO_ROOT / "docs" / "testing" / "experiment-evidence-layout.md"
FIXTURES = REPO_ROOT / "contracts" / "experiment" / "examples" / "valid"
REHEARSAL_RECORD = (
    REPO_ROOT / "docs" / "proof" / "serving" / "v2-s5-001-pr2-rehearsal-caller.jsonl"
)

BASE: dict[str, Any] = json.loads(
    (FIXTURES / "fault-injected-passed.json").read_text(encoding="utf-8")
)
EXPERIMENT_ID: str = BASE["metadata"]["experimentId"]
RUN_ID: str = BASE["metadata"]["runId"]
RELEASE_ID: str = BASE["release"]["releaseId"]
EXPERIMENT_REF = "docs/proof/experiments/example-e1"
FREEZE_REF = f"{EXPERIMENT_REF}/freeze-r1.v1alpha1.json"
RUN_REF = f"{EXPERIMENT_REF}/runs/{RUN_ID}"
CORRECTIONS_REF = f"{EXPERIMENT_REF}/corrections/{RUN_ID}"

# Each value below is joined when the suite runs. The committed text of this module
# holds no credential-shaped word and no path under a user directory.
PREFIXED_WORD = "sk-" + "example-not-a-credential"
AWS_EXAMPLE_WORD = "AKIA" + "IOSFODNN7EXAMPLE"
POSIX_HOME = "/" + "home" + "/" + "operator" + "/" + "run.log"
MAC_HOME = "/" + "Users" + "/" + "operator" + "/" + "run.log"
DRIVE_HOME = "C:" + "\\" + "Users" + "\\" + "operator" + "\\" + "run.log"

RULE_IDS = tuple(core.RULES)


def _caller_record(
    *,
    experiment_id: str = EXPERIMENT_ID,
    run_id: str = RUN_ID,
    release_id: str | None = RELEASE_ID,
) -> str:
    """A caller record that the runner's own loop writes against one scripted answer.

    No request is sent. The clock is a fixed instant, and one millisecond more for
    each reading. So the record is synthetic and two calls give the same bytes.
    """
    plan = runner_core.build_plan(
        experiment_id=experiment_id,
        run_id=run_id,
        duration_seconds=60,
        request_ceiling=4,
        release_id=release_id,
    )
    _, status, answer = runner_core.scripted_answers(plan)[0]
    base = datetime(2026, 1, 1, 10, 1, tzinfo=UTC)
    ticks = [0]

    def wall() -> datetime:
        ticks[0] += 1
        return base + timedelta(milliseconds=ticks[0])

    out = io.StringIO()
    incluster.Run(
        plan,
        out=out,
        runner_sha256=runner_core.runner_digest(),
        plan_sha256=runner_core.plan_digest(runner_core.plan_text(plan)),
        transport=lambda *_: (status, answer),
        wall=wall,
        sleep=lambda _: None,
    ).execute()
    return out.getvalue()


CALLER_TEXT = _caller_record()
PODS_TEXT = '{"readAt":"2026-01-01T10:02:00Z","pods":[]}\n'
RESULT_TEXT = "# Result\n\nSynthetic. No run executed.\n"
FILES: dict[str, tuple[str, str]] = {
    "caller.jsonl": ("caller", CALLER_TEXT),
    "pods.jsonl": ("pods", PODS_TEXT),
    "result.md": ("result", RESULT_TEXT),
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _write_json(path: Path, document: Any) -> None:
    _write(path, json.dumps(document, indent=2) + "\n")


def _build(
    root: Path,
    *,
    files: dict[str, tuple[str, str]] | None = None,
    mutate: Callable[[dict[str, Any]], None] | None = None,
    freeze_ref: str = FREEZE_REF,
    run_ref: str = RUN_REF,
) -> Path:
    """Write a tree with one run directory, and return the run directory."""
    _write_json(
        root / run_core.PRE_SCHEMA_REGISTER_REF,
        {
            "schemaVersion": run_core.SUPPORTED_API_VERSION,
            "kind": run_core.PRE_SCHEMA_REGISTER_KIND,
            "records": [],
        },
    )
    _write_json(root / freeze_ref, {"metadata": {"revision": 1}})
    run_dir = root / run_ref
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = copy.deepcopy(BASE)
    manifest["metadata"]["spec"] = {
        "freezeRecord": freeze_ref,
        "freezeRevision": 1,
        "freezeContentSha256": run_core.content_digest(
            (root / freeze_ref).read_bytes()
        ),
    }
    entries = []
    for relative, (role, text) in (FILES if files is None else files).items():
        _write(run_dir / relative, text)
        entries.append(
            {
                "role": role,
                "path": relative,
                "sha256": core.file_digest(run_dir / relative),
            }
        )
    manifest["evidence"]["files"] = entries
    if mutate is not None:
        mutate(manifest)
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)
    return run_dir


def _rules(report: core.RunReport) -> list[str]:
    return sorted({finding.rule for finding in report.findings})


def _manifest(run_dir: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (run_dir / run_core.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    return document


def _undecided(manifest: dict[str, Any]) -> None:
    """A state that the ExperimentRun rules do not bind to a caller record."""
    manifest["result"] = {
        "state": "INCONCLUSIVE",
        "reason": "The evidence decides no criterion. This document is a fixture.",
    }


# --------------------------------------------------------------------------
# The control, and the agreement with the document
# --------------------------------------------------------------------------


def test_a_run_directory_that_holds_what_its_manifest_names_conforms(
    tmp_path: Path,
) -> None:
    """The control for every refusal below."""
    report = core.check_run(_build(tmp_path), tmp_path)
    assert report.findings == ()
    assert report.status == run_core.CONFORMING
    assert (report.path, report.files, report.raw_files) == (RUN_REF, 3, 2)
    assert report.corrections == 0
    assert report.digests is not None and report.digests.raw is not None


def test_the_document_states_each_rule_as_the_module_does() -> None:
    text = LAYOUT_DOC.read_text(encoding="utf-8")
    rows = dict(re.findall(r"(?m)^\| `(evidence-[a-z-]+)` \| (.+?) \|$", text))
    assert rows == dict(core.RULES)
    assert len(core.RULES) == 21


def test_the_document_states_each_role_as_the_module_does() -> None:
    text = LAYOUT_DOC.read_text(encoding="utf-8")
    rows = re.findall(r"(?m)^\| `([a-z-]+)` \| (raw|derived) \| (.+?) \|$", text)
    assert [(name, kind, holds) for name, kind, holds in rows] == [
        (name, role.kind, role.holds) for name, role in core.ROLES.items()
    ]
    assert sum(1 for role in core.ROLES.values() if role.kind == core.RAW) == 11
    assert sorted(n for n, r in core.ROLES.items() if r.kind == core.DERIVED) == [
        "analysis",
        "result",
    ]


def test_the_package_exports_what_the_module_defines() -> None:
    assert experiment_evidence.RULES is core.RULES
    assert experiment_evidence.ROLES is core.ROLES
    assert experiment_evidence.CALLER_ROLE == run_core.CALLER_ROLE
    assert experiment_evidence.REFUSED == run_core.REFUSED


# --------------------------------------------------------------------------
# One file has one digest in each tool
# --------------------------------------------------------------------------


def test_the_digest_and_the_text_suffixes_are_the_evidence_indexes(
    tmp_path: Path,
) -> None:
    assert core.EVIDENCE_SUFFIXES is evidence_index.TEXT_SUFFIXES
    assert core.file_digest(REHEARSAL_RECORD) == evidence_index.content_sha256(
        REHEARSAL_RECORD
    )
    run_dir = _build(tmp_path)
    for entry in _manifest(run_dir)["evidence"]["files"]:
        path = run_dir / entry["path"]
        assert entry["sha256"] == evidence_index.content_sha256(path)
        assert path.suffix in evidence_index.TEXT_SUFFIXES


def test_a_crlf_checkout_of_a_run_directory_conforms(tmp_path: Path) -> None:
    """A Windows checkout can hold each committed text file with CRLF."""
    run_dir = _build(tmp_path)
    before = core.check_run(run_dir, tmp_path)
    for path in [*run_dir.iterdir(), tmp_path / FREEZE_REF]:
        data = path.read_bytes()
        assert b"\r\n" not in data
        path.write_bytes(data.replace(b"\n", b"\r\n"))
    after = core.check_run(run_dir, tmp_path)
    assert after.findings == ()
    assert after.digests == before.digests


def test_the_run_digests_are_the_evidence_indexes_set_digest(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    report = core.check_run(run_dir, tmp_path)
    rows = [
        {"path": f"{RUN_REF}/{name}", "sha256": evidence_index.content_sha256(path)}
        for name, path in ((p.name, p) for p in sorted(run_dir.iterdir()))
    ]
    raw = [row for row in rows if row["path"].endswith(".jsonl")]
    assert report.digests == core.RunDigests(
        raw=evidence_index.evidence_set_sha256(raw),
        evidence_set=evidence_index.evidence_set_sha256(rows),
    )


def test_a_rewritten_summary_moves_the_set_digest_and_not_the_raw_digest(
    tmp_path: Path,
) -> None:
    first = core.check_run(_build(tmp_path / "a"), tmp_path / "a").digests
    files = {**FILES, "result.md": ("result", RESULT_TEXT + "\nAnother sentence.\n")}
    second = core.check_run(_build(tmp_path / "b", files=files), tmp_path / "b").digests
    assert first is not None and second is not None
    assert first.raw == second.raw
    assert first.evidence_set != second.evidence_set


def test_a_run_with_no_raw_file_has_no_raw_digest(tmp_path: Path) -> None:
    def refused(manifest: dict[str, Any]) -> None:
        refused_fixture = json.loads(
            (FIXTURES / "refused-before-the-procedure.json").read_text(encoding="utf-8")
        )
        for member in ("fault", "result", "cleanup"):
            manifest[member] = refused_fixture[member]

    report = core.check_run(_build(tmp_path, files={}, mutate=refused), tmp_path)
    assert report.findings == ()
    assert report.digests is not None and report.digests.raw is None


def _review(root: Path) -> dict[str, str]:
    """Write a review artifact of the run, and return its ledger row."""
    run_dir = root / RUN_REF
    review_ref = f"{EXPERIMENT_REF}/reviews/{RUN_ID}-review-1.v1alpha1.json"
    _write_json(
        root / review_ref,
        {
            "kind": index_core.RESULT_REVIEW_KIND,
            "subject": {
                "runId": RUN_ID,
                "runPath": RUN_REF,
                "freeze": {
                    "path": FREEZE_REF,
                    "contentSha256": evidence_index.content_sha256(root / FREEZE_REF),
                },
                "files": {
                    path.name: evidence_index.content_sha256(path)
                    for path in run_dir.iterdir()
                },
            },
        },
    )
    return {
        "runPath": RUN_REF,
        "reviewRef": review_ref,
        "reviewSha256": evidence_index.content_sha256(root / review_ref),
    }


def test_the_result_review_gate_reads_a_run_of_this_layout(tmp_path: Path) -> None:
    """The gate names the freeze record through the manifest. A manifest of the
    published schema states it in another member than the three earlier ones do."""
    _build(tmp_path)
    row = _review(tmp_path)
    checked = index_core._checked_review("a-ledger", row, tmp_path)
    assert checked["runPath"] == RUN_REF
    assert index_core._named_freeze_record(_manifest(tmp_path / RUN_REF)) == FREEZE_REF
    earlier = {"metadata": {"freezeRecord": "a/freeze.json"}}
    assert index_core._named_freeze_record(earlier) == "a/freeze.json"
    _write_json(tmp_path / RUN_REF / run_core.MANIFEST_NAME, {"metadata": "text"})
    with pytest.raises(ValueError):
        index_core._checked_review("a-ledger", _review(tmp_path), tmp_path)


def test_the_gate_still_refuses_a_review_of_another_freeze_record(
    tmp_path: Path,
) -> None:
    _build(tmp_path)
    row = _review(tmp_path)
    manifest = _manifest(tmp_path / RUN_REF)
    manifest["metadata"]["spec"]["freezeRecord"] = f"{EXPERIMENT_REF}/freeze-r2.json"
    _write_json(tmp_path / RUN_REF / run_core.MANIFEST_NAME, manifest)
    with pytest.raises(ValueError):
        index_core._checked_review("a-ledger", row, tmp_path)


def test_a_correction_does_not_end_a_review_of_the_run(tmp_path: Path) -> None:
    """A review states the digest of each file of the run directory. A correction is
    outside that directory, so the review still describes the run."""
    _build(tmp_path)
    row = _review(tmp_path)
    _correct(tmp_path, 1)
    assert core.check_run(tmp_path / RUN_REF, tmp_path).corrections == 1
    assert index_core._checked_review("a-ledger", row, tmp_path)["reviewRef"]


# --------------------------------------------------------------------------
# The place of a run directory, and its freeze record
# --------------------------------------------------------------------------


def test_a_run_directory_under_another_name_is_refused(tmp_path: Path) -> None:
    run_dir = _build(tmp_path, run_ref=f"{EXPERIMENT_REF}/runs/another-run")
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_MISPLACED]


def test_a_run_directory_beside_another_freeze_record_is_refused(
    tmp_path: Path,
) -> None:
    run_dir = _build(
        tmp_path, freeze_ref="docs/proof/experiments/example-e2/freeze-r1.v1alpha1.json"
    )
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_MISPLACED]


@pytest.mark.parametrize(
    "freeze_ref",
    [
        "docs/proof/experiments/freeze-r1.v1alpha1.json",
        "docs/proof/experiments/example-e1/records/freeze-r1.v1alpha1.json",
        "docs/proof/serving/example-e1/freeze-r1.v1alpha1.json",
    ],
)
def test_a_freeze_record_outside_one_experiment_directory_gives_no_place(
    tmp_path: Path, freeze_ref: str
) -> None:
    run_dir = _build(tmp_path, freeze_ref=freeze_ref)
    assert core.expected_run_ref(_manifest(run_dir)) is None
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_MISPLACED]


def test_a_run_directory_outside_the_tree_is_refused(tmp_path: Path) -> None:
    run_dir = _build(tmp_path / "tree")
    report = core.check_run(run_dir, tmp_path / "elsewhere")
    assert core.RULE_MISPLACED in _rules(report)


def _edited(root: Path) -> None:
    _write_json(root / FREEZE_REF, {"metadata": {"revision": 1}, "added": True})


def _absent(root: Path) -> None:
    (root / FREEZE_REF).unlink()


def _not_json(root: Path) -> None:
    _write(root / FREEZE_REF, "not a JSON document\n")


@pytest.mark.parametrize("change", [_edited, _absent, _not_json])
def test_a_freeze_record_that_is_not_the_stated_one_is_refused(
    tmp_path: Path, change: Callable[[Path], None]
) -> None:
    run_dir = _build(tmp_path)
    change(tmp_path)
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FREEZE]


@pytest.mark.parametrize("revision", [2, True, "1", None])
def test_a_freeze_record_of_another_revision_is_refused(
    tmp_path: Path, revision: object
) -> None:
    def another(manifest: dict[str, Any]) -> None:
        _write_json(tmp_path / FREEZE_REF, {"metadata": {"revision": revision}})
        manifest["metadata"]["spec"]["freezeContentSha256"] = run_core.content_digest(
            (tmp_path / FREEZE_REF).read_bytes()
        )

    run_dir = _build(tmp_path, mutate=another)
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FREEZE]


def test_a_freeze_record_under_another_letter_case_is_refused(tmp_path: Path) -> None:
    """A file system that ignores letter case opens the file. The check compares
    each name as text, so one tree has one verdict on each host."""
    run_dir = _build(tmp_path)
    stated = tmp_path / FREEZE_REF
    stated.rename(stated.with_name("Freeze-r1.v1alpha1.json"))
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FREEZE]


# --------------------------------------------------------------------------
# The manifest
# --------------------------------------------------------------------------


def test_a_directory_with_no_manifest_is_refused(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    (run_dir / run_core.MANIFEST_NAME).unlink()
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_MANIFEST_MISSING]
    assert _rules(core.check_run(tmp_path / "absent", tmp_path)) == [
        core.RULE_MANIFEST_MISSING
    ]


def test_a_manifest_that_the_validator_refuses_is_refused_and_nothing_else_is_read(
    tmp_path: Path,
) -> None:
    run_dir = _build(tmp_path, mutate=lambda manifest: manifest.pop("limitations"))
    (run_dir / "pods.jsonl").unlink()
    report = core.check_run(run_dir, tmp_path)
    assert _rules(report) == [core.RULE_MANIFEST_REFUSED]
    assert report.digests is None
    _write(run_dir / run_core.MANIFEST_NAME, "{")
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_MANIFEST_REFUSED]


# --------------------------------------------------------------------------
# A directory is closed in both directions
# --------------------------------------------------------------------------


def test_a_named_file_that_is_absent_is_refused(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    (run_dir / "pods.jsonl").unlink()
    report = core.check_run(run_dir, tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_FILE_MISSING, f"{RUN_REF}/pods.jsonl")
    ]


@pytest.mark.parametrize("extra", ["notes.txt", "raw/extra.json", ".DS_Store"])
def test_a_file_that_the_manifest_does_not_name_is_refused(
    tmp_path: Path, extra: str
) -> None:
    run_dir = _build(tmp_path)
    _write(run_dir / extra, "A file that no manifest names.\n")
    report = core.check_run(run_dir, tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_FILE_UNLISTED, f"{RUN_REF}/{extra}")
    ]


def test_an_edited_file_is_refused(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    _write(run_dir / "result.md", RESULT_TEXT + "One more sentence.\n")
    report = core.check_run(run_dir, tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_FILE_DIGEST, f"{RUN_REF}/result.md")
    ]


def test_a_file_under_another_letter_case_is_absent_and_not_named(
    tmp_path: Path,
) -> None:
    run_dir = _build(tmp_path)
    (run_dir / "result.md").rename(run_dir / "Result.md")
    assert _rules(core.check_run(run_dir, tmp_path)) == [
        core.RULE_FILE_MISSING,
        core.RULE_FILE_UNLISTED,
    ]


def test_two_paths_that_one_directory_cannot_hold_are_refused(tmp_path: Path) -> None:
    """The ExperimentRun rules accept ``pods`` beside ``pods/a.json``. A directory
    cannot hold both as files, so the check of a directory refuses the manifest."""

    def both(manifest: dict[str, Any]) -> None:
        manifest["evidence"]["files"].append(
            {"role": "pods", "path": "pods.jsonl/a.json", "sha256": "0" * 64}
        )

    run_dir = _build(tmp_path, mutate=both)
    assert run_core.validate(_manifest(run_dir)) == []
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FILE_MISSING]


def test_a_link_is_refused(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    target = tmp_path / "outside.txt"
    _write(target, "A file outside the run directory.\n")
    try:
        (run_dir / "linked.txt").symlink_to(target)
    except OSError:
        pytest.skip("this host does not let the suite create a symbolic link")
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FILE_NOT_REGULAR]


def test_an_entry_that_the_host_reports_as_a_link_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rule on a host that cannot create a link: the host's answer is replaced
    for one file name. The test above creates a real link where the host lets it."""
    run_dir = _build(tmp_path)
    _write(
        run_dir / "linked.txt", "A regular file that is reported as a link." + chr(10)
    )
    original = Path.is_symlink

    def linked(path: Path) -> bool:
        return path.name == "linked.txt" or original(path)

    monkeypatch.setattr(Path, "is_symlink", linked)
    report = core.check_run(run_dir, tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_FILE_NOT_REGULAR, f"{RUN_REF}/linked.txt")
    ]
    lines, findings = core.digest_lines(run_dir)
    assert len(lines) == 3
    assert [f.rule for f in findings] == [core.RULE_FILE_NOT_REGULAR]
    with pytest.raises(core.LayoutError) as refusal:
        core.describe_file(run_dir, "linked.txt", "transcript")
    assert refusal.value.rule == core.RULE_FILE_MISSING


# --------------------------------------------------------------------------
# The form of a file
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("pods.bin", b"text under a suffix the index hashes byte for byte\n"),
        ("pods.log", b"text under a suffix the index hashes byte for byte\n"),
        ("pods", b"text with no suffix\n"),
        ("pods.json", b'{"name": "\xff\xfe"}\n'),
        ("pods.json", b'{"name": "a\x00b"}\n'),
    ],
)
def test_a_file_that_is_not_text_of_a_known_suffix_is_refused(
    tmp_path: Path, name: str, data: bytes
) -> None:
    def named(manifest: dict[str, Any]) -> None:
        manifest["evidence"]["files"].append(
            {"role": "pods", "path": name, "sha256": "0" * 64}
        )

    run_dir = _build(tmp_path, mutate=named)
    (run_dir / name).write_bytes(data)
    report = core.check_run(run_dir, tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_FILE_FORM, f"{RUN_REF}/{name}")
    ]


def test_each_suffix_the_index_hashes_as_text_is_an_evidence_suffix(
    tmp_path: Path,
) -> None:
    files = {
        f"transcript{suffix}": ("transcript", "One line.\n")
        for suffix in sorted(evidence_index.TEXT_SUFFIXES)
    }
    report = core.check_run(_build(tmp_path, files=files, mutate=_undecided), tmp_path)
    assert report.findings == ()
    assert report.files == len(evidence_index.TEXT_SUFFIXES) == 7


# --------------------------------------------------------------------------
# Roles: raw and derived
# --------------------------------------------------------------------------


def test_a_file_with_a_role_that_is_not_registered_is_refused(tmp_path: Path) -> None:
    files = {**FILES, "completion.json": ("completion", "{}\n")}
    report = core.check_run(_build(tmp_path, files=files), tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_ROLE, f"{RUN_REF}/completion.json")
    ]


def test_one_role_of_the_committed_fixtures_is_not_a_registered_role() -> None:
    """Measured. The schema holds no role vocabulary, so a fixture of the schema can
    name a role that the layout does not register. No fixture is a run directory."""
    named = {
        entry["role"]
        for path in sorted(FIXTURES.glob("*.json"))
        for entry in json.loads(path.read_text(encoding="utf-8"))["evidence"]["files"]
    }
    assert named - set(core.ROLES) == {"completion"}


@pytest.mark.parametrize("role", ["result", "analysis"])
def test_a_derived_file_with_no_raw_file_is_refused(tmp_path: Path, role: str) -> None:
    files = {"summary.md": (role, RESULT_TEXT)}
    report = core.check_run(_build(tmp_path, files=files, mutate=_undecided), tmp_path)
    assert _rules(report) == [core.RULE_SUMMARY]


@pytest.mark.parametrize(
    "role",
    sorted(n for n, r in core.ROLES.items() if r.kind == core.RAW and n != "caller"),
)
def test_a_derived_file_beside_one_raw_file_of_any_role_conforms(
    tmp_path: Path, role: str
) -> None:
    files = {"raw.json": (role, "{}\n"), "result.md": ("result", RESULT_TEXT)}
    report = core.check_run(_build(tmp_path, files=files, mutate=_undecided), tmp_path)
    assert report.findings == ()
    assert (report.files, report.raw_files) == (2, 1)
    assert core.is_raw(role) and not core.is_raw("result")
    assert not core.is_raw("completion")


# --------------------------------------------------------------------------
# The caller record
# --------------------------------------------------------------------------


def test_a_caller_file_that_is_not_a_caller_record_is_refused(tmp_path: Path) -> None:
    files = {**FILES, "caller.jsonl": ("caller", '{"record":"header"}\n')}
    report = core.check_run(_build(tmp_path, files=files), tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_CALLER_RECORD, f"{RUN_REF}/caller.jsonl")
    ]
    assert report.findings[0].message.endswith(runner_core.RULE_MEMBERS)


def test_a_caller_record_without_its_end_line_is_refused(tmp_path: Path) -> None:
    cut = "".join(CALLER_TEXT.splitlines(keepends=True)[:-1])
    files = {**FILES, "caller.jsonl": ("caller", cut)}
    report = core.check_run(_build(tmp_path, files=files), tmp_path)
    assert _rules(report) == [core.RULE_CALLER_RECORD]


@pytest.mark.parametrize(
    "record",
    [
        _caller_record(run_id="another-run"),
        _caller_record(experiment_id="ANOTHER-E1"),
        _caller_record(release_id="5" * 64),
        REHEARSAL_RECORD.read_text(encoding="utf-8"),
    ],
    ids=["another-run", "another-experiment", "another-release", "a-rehearsal"],
)
def test_a_caller_record_of_another_run_or_of_a_rehearsal_is_refused(
    tmp_path: Path, record: str
) -> None:
    files = {**FILES, "caller.jsonl": ("caller", record)}
    report = core.check_run(_build(tmp_path, files=files), tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_CALLER_IDENTITY, f"{RUN_REF}/caller.jsonl")
    ]


def test_the_committed_rehearsal_record_names_its_own_run_and_is_still_refused(
    tmp_path: Path,
) -> None:
    """A rehearsal sends no request, so it is not the caller record of a run."""

    def rehearsal(manifest: dict[str, Any]) -> None:
        manifest["metadata"]["experimentId"] = "rehearsal"
        manifest["metadata"]["runId"] = "rehearsal-1"

    files = {
        **FILES,
        "caller.jsonl": ("caller", REHEARSAL_RECORD.read_text(encoding="utf-8")),
    }
    run_dir = _build(
        tmp_path,
        files=files,
        mutate=rehearsal,
        run_ref=f"{EXPERIMENT_REF}/runs/rehearsal-1",
    )
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CALLER_IDENTITY]


def test_a_caller_record_under_a_manifest_with_no_caller_profile_is_refused(
    tmp_path: Path,
) -> None:
    def no_profile(manifest: dict[str, Any]) -> None:
        manifest["callerProfile"] = {
            "applies": False,
            "reason": "The frozen record registers no caller. This is a fixture.",
        }

    report = core.check_run(_build(tmp_path, mutate=no_profile), tmp_path)
    assert _rules(report) == [core.RULE_CALLER_IDENTITY]


def test_a_caller_record_that_declares_no_release_conforms(tmp_path: Path) -> None:
    """Measured. A record whose plan declared no release names none to compare."""
    files = {**FILES, "caller.jsonl": ("caller", _caller_record(release_id=None))}
    assert core.check_run(_build(tmp_path, files=files), tmp_path).findings == ()


# --------------------------------------------------------------------------
# Public safety
# --------------------------------------------------------------------------


def test_a_refused_run_with_no_evidence_file_conforms(tmp_path: Path) -> None:
    """The layout requires no file. So it requires no file that holds a secret, a
    prompt, or a path of a host."""

    def refused(manifest: dict[str, Any]) -> None:
        refused_fixture = json.loads(
            (FIXTURES / "refused-before-the-procedure.json").read_text(encoding="utf-8")
        )
        for member in ("fault", "result", "cleanup"):
            manifest[member] = refused_fixture[member]

    run_dir = _build(tmp_path, files={}, mutate=refused)
    report = core.check_run(run_dir, tmp_path)
    assert (report.status, report.files) == (run_core.CONFORMING, 0)
    assert [path.name for path in run_dir.iterdir()] == [run_core.MANIFEST_NAME]


def test_no_role_description_names_content_or_a_credential() -> None:
    """The descriptions of the roles are read, and no file is. The test does
    not show what a file with a role holds."""
    words = " ".join(role.holds.lower() for role in core.ROLES.values())
    for word in ("prompt", "completion", "response", "secret", "credential", "token"):
        assert word not in words


@pytest.mark.parametrize(
    "text",
    [
        f"Authorization: Bearer {PREFIXED_WORD}\n",
        f'{{"key":"{AWS_EXAMPLE_WORD}"}}\n',
        f"export KEY={PREFIXED_WORD}\n",
        f"key: '{AWS_EXAMPLE_WORD}'\n",
    ],
)
def test_a_word_with_a_published_credential_prefix_is_refused(
    tmp_path: Path, text: str
) -> None:
    files = {**FILES, "transcript.txt": ("transcript", text)}
    report = core.check_run(_build(tmp_path, files=files), tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_FILE_CREDENTIAL, f"{RUN_REF}/transcript.txt")
    ]
    assert PREFIXED_WORD not in report.findings[0].message
    assert AWS_EXAMPLE_WORD not in report.findings[0].message


@pytest.mark.parametrize(
    "path",
    [
        POSIX_HOME,
        MAC_HOME,
        DRIVE_HOME,
        DRIVE_HOME.replace("\\", "/"),
        json.dumps(DRIVE_HOME),
        "/mnt/c" + MAC_HOME,
    ],
)
def test_a_path_under_a_user_directory_is_refused(tmp_path: Path, path: str) -> None:
    files = {**FILES, "transcript.txt": ("transcript", f"wrote {path}\n")}
    report = core.check_run(_build(tmp_path, files=files), tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_FILE_PERSONAL_PATH, f"{RUN_REF}/transcript.txt")
    ]
    assert "operator" not in report.findings[0].message


@pytest.mark.parametrize(
    "text",
    [
        # A lowercase secret with no published prefix.
        "token q7f3k9x2m4p8w6z1\n",
        # The opaque shape that the ExperimentRun rules refuse in a statement. Raw
        # evidence holds identifiers of this shape, so the layout does not read it.
        "uid " + "Zx4Kq9TbLm2Rd7" + "Wf1Hs3Nv8Yc6Ej0Pa\n",
        # A published prefix directly after a letter, inside a longer word.
        "value" + PREFIXED_WORD + "\n",
        # A host path that is not under a user directory.
        "wrote /var/lib/kubelet/pods/a.log and /root/a.log\n",
        # A drive path that is not under a user directory.
        "wrote D:" + "\\" + "work" + "\\" + "run.log\n",
        # A request text. No rule reads a file for a prompt or a response.
        '{"messages":[{"role":"user","content":"Reply with one word."}]}\n',
        # A user directory with no name after it.
        "the directory /" + "home" + "/ holds accounts\n",
    ],
)
def test_what_the_two_text_rules_still_accept(tmp_path: Path, text: str) -> None:
    """Measured. Each of these is in a file and no rule refuses it."""
    files = {**FILES, "transcript.txt": ("transcript", text)}
    assert core.check_run(_build(tmp_path, files=files), tmp_path).findings == ()
    assert core.text_problems(text) == []


def test_a_container_path_under_a_home_directory_is_refused_too() -> None:
    """Measured. The rule cannot tell a path in a container from a path of a host.
    The security baseline suite refuses the same text in each committed file."""
    text = '{"mountPath":"' + "/" + "home" + "/nonroot/cache" + '/"}\n'
    assert [rule for rule, _ in core.text_problems(text)] == [
        core.RULE_FILE_PERSONAL_PATH
    ]


# --------------------------------------------------------------------------
# Corrections
# --------------------------------------------------------------------------


def _correct(
    root: Path,
    number: int,
    *,
    corrects: list[dict[str, str]] | None = None,
    files: dict[str, tuple[str, str]] | None = None,
    mutate: Callable[[dict[str, Any]], None] | None = None,
    name: str | None = None,
) -> Path:
    """Write one correction of the run, with the digests the tree has now."""
    run_dir = root / RUN_REF
    directory = root / CORRECTIONS_REF
    previous = directory / f"correction-{number - 1}.v1alpha1.json"
    added = []
    for relative, (role, text) in (files or {}).items():
        path = directory / f"correction-{number}" / relative
        _write(path, text)
        added.append({"role": role, "path": relative, "sha256": core.file_digest(path)})
    document: dict[str, Any] = {
        "schemaVersion": run_core.SUPPORTED_API_VERSION,
        "kind": core.CORRECTION_KIND,
        "experimentId": EXPERIMENT_ID,
        "runId": RUN_ID,
        "number": number,
        "recordedAt": "2026-01-02T09:00:00Z",
        "manifestSha256": core.file_digest(run_dir / run_core.MANIFEST_NAME),
        "previousCorrectionSha256": (
            core.file_digest(previous) if previous.is_file() else None
        ),
        "corrects": corrects
        if corrects is not None
        else [
            {
                "path": "result.md",
                "sha256": core.file_digest(run_dir / "result.md"),
            }
        ],
        "statements": ["The result page states one figure wrongly. This is a fixture."],
        "files": added,
    }
    if mutate is not None:
        mutate(document)
    path = directory / (name or f"correction-{number}.v1alpha1.json")
    _write_json(path, document)
    return path


def test_a_correction_beside_the_runs_directory_conforms_and_moves_no_digest(
    tmp_path: Path,
) -> None:
    run_dir = _build(tmp_path)
    before = core.check_run(run_dir, tmp_path)
    _correct(tmp_path, 1, files={"result.md": ("result", RESULT_TEXT + "Corrected.\n")})
    after = core.check_run(run_dir, tmp_path)
    assert after.findings == ()
    assert (before.corrections, after.corrections) == (0, 1)
    assert after.digests == before.digests
    assert not (run_dir / "corrections").exists()


def test_a_second_correction_states_the_digest_of_the_first(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    first = _correct(tmp_path, 1)
    _correct(
        tmp_path,
        2,
        corrects=[
            {"path": first.name, "sha256": core.file_digest(first)},
            {
                "path": run_core.MANIFEST_NAME,
                "sha256": core.file_digest(run_dir / run_core.MANIFEST_NAME),
            },
        ],
    )
    report = core.check_run(run_dir, tmp_path)
    assert report.findings == ()
    assert report.corrections == 2


def test_an_edited_file_under_a_correction_is_refused_by_two_rules(
    tmp_path: Path,
) -> None:
    """A correction states the digest of the file it corrects. So an edit of that
    file after the correction is refused for the file and for the correction."""
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1)
    _write(run_dir / "result.md", RESULT_TEXT + "Rewritten in place.\n")
    assert _rules(core.check_run(run_dir, tmp_path)) == [
        core.RULE_CORRECTION_TARGET,
        core.RULE_FILE_DIGEST,
    ]


def _rewrite_file_and_manifest(root: Path) -> None:
    run_dir = root / RUN_REF
    _write(run_dir / "result.md", RESULT_TEXT + "Rewritten with its digest.\n")
    manifest = _manifest(run_dir)
    for entry in manifest["evidence"]["files"]:
        entry["sha256"] = core.file_digest(run_dir / entry["path"])
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)


def test_a_file_and_its_manifest_digest_rewritten_together_pass_with_no_correction(
    tmp_path: Path,
) -> None:
    """Measured. The check reads one tree and not Git. A file that is replaced with
    its digest in the manifest is a run directory that conforms."""
    run_dir = _build(tmp_path)
    _rewrite_file_and_manifest(tmp_path)
    assert core.check_run(run_dir, tmp_path).findings == ()


def test_a_file_and_its_manifest_digest_rewritten_together_are_refused_once_corrected(
    tmp_path: Path,
) -> None:
    """A correction states the digest of the manifest. So the first correction of a
    run pins the manifest, and through it each file."""
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1, corrects=[{"path": "pods.jsonl", "sha256": "0" * 64}])
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CORRECTION_TARGET]
    shutil.rmtree(tmp_path / CORRECTIONS_REF)
    _correct(
        tmp_path,
        1,
        corrects=[
            {"path": "pods.jsonl", "sha256": core.file_digest(run_dir / "pods.jsonl")}
        ],
    )
    assert core.check_run(run_dir, tmp_path).findings == ()
    _rewrite_file_and_manifest(tmp_path)
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CORRECTION_IDENTITY]


def _as(member: str, value: object) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document[member] = value

    return change


def _without(member: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        del document[member]

    return change


@pytest.mark.parametrize(
    "mutate",
    [
        _without("statements"),
        _as("note", "A member that is not registered."),
        _as("schemaVersion", "inferops.io/v1"),
        _as("kind", "ExperimentRun"),
        _as("number", "1"),
        _as("number", True),
        _as("number", 0),
        _as("number", 10000),
        _as("statements", ["   "]),
        _as("corrects", [{"path": "result.md", "sha256": "0" * 64}] * 2),
        _as("runId", 7),
        _as("recordedAt", "2026-01-02T09:00:00+01:00"),
        _as("recordedAt", "2026-02-30T09:00:00Z"),
        _as("manifestSha256", "sha256:" + "0" * 64),
        _as("previousCorrectionSha256", "none"),
        _as("corrects", []),
        _as("corrects", [{"path": "result.md"}]),
        _as("corrects", [{"path": "result.md", "sha256": "A" * 64}]),
        _as("statements", []),
        _as("statements", [""]),
        _as("statements", ["a" * 2001]),
        _as("statements", "One statement that is not in a list."),
        _as("files", None),
        _as("files", [{"role": "result", "path": "../result.md", "sha256": "0" * 64}]),
        _as(
            "files",
            [{"role": "result", "path": "a.md", "sha256": "0" * 64}] * 2,
        ),
    ],
)
def test_a_correction_that_does_not_have_its_form_is_refused(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], None]
) -> None:
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1, mutate=mutate)
    assert _rules(core.check_run(run_dir, tmp_path)) == [
        core.RULE_CORRECTION_UNREADABLE
    ]


def test_a_correction_that_is_not_one_json_object_is_refused(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    _write(_correct(tmp_path, 1), "[]\n")
    assert _rules(core.check_run(run_dir, tmp_path)) == [
        core.RULE_CORRECTION_UNREADABLE
    ]
    _write(_correct(tmp_path, 1), '{"number": 1, "number": 2}\n')
    assert _rules(core.check_run(run_dir, tmp_path)) == [
        core.RULE_CORRECTION_UNREADABLE
    ]


@pytest.mark.parametrize(
    ("mutate", "rule"),
    [
        (_as("runId", "another-run"), core.RULE_CORRECTION_IDENTITY),
        (_as("experimentId", "ANOTHER-E1"), core.RULE_CORRECTION_IDENTITY),
        (_as("manifestSha256", "0" * 64), core.RULE_CORRECTION_IDENTITY),
        (_as("previousCorrectionSha256", "0" * 64), core.RULE_CORRECTION_CHAIN),
        (_as("number", 2), core.RULE_CORRECTION_NUMBER),
        (
            _as("corrects", [{"path": "result.md", "sha256": "0" * 64}]),
            core.RULE_CORRECTION_TARGET,
        ),
        (
            _as("corrects", [{"path": "absent.md", "sha256": "0" * 64}]),
            core.RULE_CORRECTION_TARGET,
        ),
        (
            _as(
                "corrects",
                [{"path": "correction-1.v1alpha1.json", "sha256": "0" * 64}],
            ),
            core.RULE_CORRECTION_TARGET,
        ),
        (
            _as("files", [{"role": "result", "path": "a.md", "sha256": "0" * 64}]),
            core.RULE_FILE_MISSING,
        ),
        (
            _as("statements", [f"The key was {PREFIXED_WORD} in the first reading."]),
            core.RULE_FILE_CREDENTIAL,
        ),
        (
            _as("statements", [f"The file was written to {POSIX_HOME} first."]),
            core.RULE_FILE_PERSONAL_PATH,
        ),
    ],
)
def test_a_correction_that_does_not_agree_with_its_run_is_refused(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], None], rule: str
) -> None:
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1, mutate=mutate)
    assert _rules(core.check_run(run_dir, tmp_path)) == [rule]


def test_corrections_that_are_not_numbered_from_one_are_refused(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    _correct(tmp_path, 2)
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CORRECTION_NUMBER]
    _correct(tmp_path, 3)
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CORRECTION_NUMBER]


def test_a_later_correction_with_the_digest_of_another_file_is_refused(
    tmp_path: Path,
) -> None:
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1)
    _correct(tmp_path, 2, mutate=_as("previousCorrectionSha256", "0" * 64))
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CORRECTION_CHAIN]


def test_an_edited_first_correction_breaks_the_second(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    first = _correct(tmp_path, 1)
    _correct(tmp_path, 2)
    document = json.loads(first.read_text(encoding="utf-8"))
    document["statements"].append("A sentence that was added later.")
    _write_json(first, document)
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CORRECTION_CHAIN]


@pytest.mark.parametrize(
    ("change", "rule"),
    [
        ("edit", core.RULE_FILE_DIGEST),
        ("remove", core.RULE_FILE_MISSING),
        ("extra", core.RULE_FILE_UNLISTED),
        ("stray", core.RULE_FILE_UNLISTED),
        ("role", core.RULE_ROLE),
    ],
)
def test_the_files_of_a_correction_are_held_as_the_files_of_a_run_are(
    tmp_path: Path, change: str, rule: str
) -> None:
    run_dir = _build(tmp_path)
    role = "completion" if change == "role" else "result"
    _correct(tmp_path, 1, files={"result.md": (role, RESULT_TEXT + "Corrected.\n")})
    added = tmp_path / CORRECTIONS_REF / "correction-1" / "result.md"
    if change == "edit":
        _write(added, "Another text.\n")
    elif change == "remove":
        added.unlink()
    elif change == "extra":
        _write(added.with_name("notes.md"), "A file that no correction names.\n")
    elif change == "stray":
        _write(tmp_path / CORRECTIONS_REF / "readme.md", "Not a correction.\n")
    assert _rules(core.check_run(run_dir, tmp_path)) == [rule]


def test_a_correction_under_a_name_that_states_no_number_is_not_a_correction(
    tmp_path: Path,
) -> None:
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1, name="correction-01.v1alpha1.json")
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FILE_UNLISTED]


def test_the_form_of_a_correction_is_checked_alone() -> None:
    assert core.correction_problem([]) is not None
    assert len(core.CORRECTION_MEMBERS) == 11


# --------------------------------------------------------------------------
# The repository listing
# --------------------------------------------------------------------------


def test_the_repository_holds_three_earlier_run_directories_and_checks_none() -> None:
    """No run directory of this layout is committed. The three that are committed
    were written before the ExperimentRun schema, and the listing does not check
    them: it says so for each."""
    report = core.repository_report()
    assert [(run.path, run.status) for run in report.runs] == [
        (f"docs/proof/experiments/v2-e01/runs/{run_id}", run_core.PRE_SCHEMA)
        for run_id in (
            "20261002-e01-abc-1",
            "20261003-e01-abc-1",
            "20261006-e01-d-1",
        )
    ]
    assert report.findings == () and not report.refused
    assert all(run.digests is None for run in report.runs)


def test_the_earlier_run_directories_would_not_conform(tmp_path: Path) -> None:
    """Measured. The listing skips them because the register names them, and not
    because they hold what the layout asks."""
    source = REPO_ROOT / "docs/proof/experiments/v2-e01/runs/20261006-e01-d-1"
    copied = tmp_path / "docs/proof/experiments/v2-e01/runs/20261006-e01-d-1"
    shutil.copytree(source, copied)
    assert _rules(core.check_run(copied, tmp_path)) == [core.RULE_MANIFEST_REFUSED]


def test_the_listing_checks_each_run_directory_of_a_tree(tmp_path: Path) -> None:
    _build(tmp_path)
    report = core.repository_report(tmp_path)
    assert [(run.path, run.status) for run in report.runs] == [
        (RUN_REF, run_core.CONFORMING)
    ]
    assert not report.refused
    _write(tmp_path / RUN_REF / "notes.txt", "A file that no manifest names.\n")
    _write(tmp_path / EXPERIMENT_REF / "runs" / "empty-run" / "a.txt", "One line.\n")
    report = core.repository_report(tmp_path)
    assert [(run.path, _rules(run)) for run in report.runs] == [
        (RUN_REF, [core.RULE_FILE_UNLISTED]),
        (f"{EXPERIMENT_REF}/runs/empty-run", [core.RULE_MANIFEST_MISSING]),
    ]
    assert report.refused


def test_a_corrections_directory_with_no_run_of_this_layout_is_refused(
    tmp_path: Path,
) -> None:
    _build(tmp_path)
    _correct(tmp_path, 1)
    shutil.move(
        str(tmp_path / CORRECTIONS_REF),
        str(tmp_path / EXPERIMENT_REF / "corrections" / "another-run"),
    )
    report = core.repository_report(tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_CORRECTION_RUN, f"{EXPERIMENT_REF}/corrections/another-run")
    ]
    assert report.refused


def test_a_correction_of_an_earlier_run_directory_is_refused(tmp_path: Path) -> None:
    """A run directory that the pre-schema register names is not of this layout, so
    this layout gives it no correction."""
    _build(tmp_path)
    earlier = f"{EXPERIMENT_REF}/runs/earlier-run/{run_core.MANIFEST_NAME}"
    _write_json(tmp_path / earlier, {"kind": "ExperimentRun"})
    _write_json(
        tmp_path / run_core.PRE_SCHEMA_REGISTER_REF,
        {
            "schemaVersion": run_core.SUPPORTED_API_VERSION,
            "kind": run_core.PRE_SCHEMA_REGISTER_KIND,
            "records": [
                {
                    "path": earlier,
                    "contentSha256": run_core.content_digest(
                        (tmp_path / earlier).read_bytes()
                    ),
                }
            ],
        },
    )
    _write(tmp_path / EXPERIMENT_REF / "corrections" / "earlier-run" / "a.json", "{}\n")
    report = core.repository_report(tmp_path)
    assert [run.status for run in report.runs] == [
        run_core.CONFORMING,
        run_core.PRE_SCHEMA,
    ]
    assert [f.rule for f in report.findings] == [core.RULE_CORRECTION_RUN]


def test_a_register_with_a_defect_is_a_finding_of_the_listing(tmp_path: Path) -> None:
    _build(tmp_path)
    _write(tmp_path / run_core.PRE_SCHEMA_REGISTER_REF, "{}\n")
    report = core.repository_report(tmp_path)
    assert [f.rule for f in report.findings] == [core.RULE_MANIFEST_REFUSED]
    assert report.refused


# --------------------------------------------------------------------------
# The helpers of a writer
# --------------------------------------------------------------------------


def test_a_writer_gets_each_entry_of_a_manifest_from_the_layout(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    entries = [
        core.describe_file(run_dir, name, role) for name, (role, _) in FILES.items()
    ]
    assert entries == _manifest(run_dir)["evidence"]["files"]


@pytest.mark.parametrize(
    ("relative", "role", "text", "rule"),
    [
        ("pods.jsonl", "completion", "{}\n", core.RULE_ROLE),
        ("absent.json", "pods", None, core.RULE_FILE_MISSING),
        ("../pods.json", "pods", None, core.RULE_FILE_FORM),
        ("Pods.json", "pods", "{}\n", core.RULE_FILE_FORM),
        (run_core.MANIFEST_NAME, "pods", "{}\n", core.RULE_FILE_FORM),
        ("pods.bin", "pods", "{}\n", core.RULE_FILE_FORM),
        ("t.txt", "transcript", f"key {PREFIXED_WORD}\n", core.RULE_FILE_CREDENTIAL),
        ("t.txt", "transcript", f"at {MAC_HOME}\n", core.RULE_FILE_PERSONAL_PATH),
    ],
)
def test_a_writer_is_refused_an_entry_that_the_check_would_refuse(
    tmp_path: Path, relative: str, role: str, text: str | None, rule: str
) -> None:
    if text is not None and ".." not in relative:
        _write(tmp_path / relative, text)
    with pytest.raises(core.LayoutError) as refusal:
        core.describe_file(tmp_path, relative, role)
    assert refusal.value.rule == rule
    assert PREFIXED_WORD not in str(refusal.value)


def test_the_digest_lines_are_those_of_the_manifest_in_path_order(
    tmp_path: Path,
) -> None:
    run_dir = _build(tmp_path)
    lines, findings = core.digest_lines(run_dir)
    assert findings == []
    assert lines == [
        f"{entry['sha256']}  {entry['path']}"
        for entry in sorted(
            _manifest(run_dir)["evidence"]["files"], key=lambda e: e["path"]
        )
    ]
    (run_dir / "image.png").write_bytes(b"\x89PNG")
    lines, findings = core.digest_lines(run_dir)
    assert len(lines) == 3
    assert [(f.rule, f.path) for f in findings] == [(core.RULE_FILE_FORM, "image.png")]


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_passes_the_repository_and_names_what_it_did_not_check(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert command.main(["repository"]) == command.EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == (
        "runs       3: 3 pre-schema and not checked, 0 conforming, 0 refused"
    )
    assert sum(1 for line in out if line.endswith("(not checked)")) == 3


def test_the_command_checks_a_run_directory_and_prints_its_two_digests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = _build(tmp_path)
    arguments = ["check", str(run_dir), "--root", str(tmp_path)]
    assert command.main(arguments) == command.EXIT_OK
    digests = core.check_run(run_dir, tmp_path).digests
    assert digests is not None
    assert capsys.readouterr().out.splitlines() == [
        f"ok         {RUN_REF}  (3 evidence file(s), 2 raw, 0 correction(s))",
        f"           raw evidence  {digests.raw}",
        f"           evidence set  {digests.evidence_set}",
    ]
    (run_dir / "pods.jsonl").unlink()
    assert command.main(arguments) == command.EXIT_REFUSED
    out = capsys.readouterr().out
    assert out.startswith(f"REFUSED    {RUN_REF}  (1 finding(s))\n")
    assert core.RULE_FILE_MISSING in out


def test_the_command_prints_the_digest_lines_of_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = _build(tmp_path)
    assert command.main(["digests", str(run_dir)]) == command.EXIT_OK
    assert capsys.readouterr().out.splitlines() == core.digest_lines(run_dir)[0]
    (run_dir / "image.png").write_bytes(b"\x89PNG")
    assert command.main(["digests", str(run_dir)]) == command.EXIT_REFUSED


def test_the_command_exits_2_for_arguments_and_4_for_a_failure_no_rule_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        command.main(["check"])
    assert stopped.value.code == 2

    def fail(_: Path) -> core.RepositoryReport:
        raise RuntimeError("a failure with a value: " + PREFIXED_WORD)

    monkeypatch.setattr(command, "repository_report", fail)
    assert command.main(["repository"]) == command.EXIT_FAILED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert PREFIXED_WORD not in captured.err


def test_a_character_that_is_not_printable_is_replaced_in_a_name() -> None:
    name = "a" + chr(10) + "REFUSED" + chr(9) + "b" + chr(27) + ".txt"
    assert core.printable(name) == "a?REFUSED?b?.txt"
    assert core.printable("runs/20260101-example-e1-1") == "runs/20260101-example-e1-1"


def test_a_name_with_a_line_break_cannot_start_an_output_line(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("this host's file system holds no line break in a file name")
    run_dir = _build(tmp_path)
    _write(run_dir / "a\nREFUSED.txt", "One line.\n")
    report = core.check_run(run_dir, tmp_path)
    assert [f.path for f in report.findings] == [f"{RUN_REF}/a?REFUSED.txt"]


# --------------------------------------------------------------------------
# What the independent reviews of the first commit found
# --------------------------------------------------------------------------

BACKSLASH = chr(92)


@pytest.mark.parametrize(
    "text",
    [
        # A line break inside a JSON string is a backslash and a letter.
        json.dumps({"stdout": "Token:\n" + PREFIXED_WORD}),
        json.dumps({"stdout": "a\tb\r\n" + AWS_EXAMPLE_WORD}),
        # A character of the prefix written as a JSON escape.
        '{"key":"' + BACKSLASH + "u0073k-example-not-a-credential" + '"}',
        # The forms of a URL and of a command line.
        "origin https://" + PREFIXED_WORD + "@example.invalid/o/r.git (fetch)",
        "GET https://example.invalid/" + PREFIXED_WORD,
        "?a=1&" + PREFIXED_WORD,
        "echo $" + PREFIXED_WORD,
        "s3://bucket/" + AWS_EXAMPLE_WORD + "/x",
        # A byte order mark before the first word.
        chr(0xFEFF) + PREFIXED_WORD,
        "value*" + PREFIXED_WORD,
    ],
)
def test_a_credential_prefix_after_any_character_but_a_letter_or_digit_is_refused(
    text: str,
) -> None:
    """The first commit read the start of a word, and a word ended only at white
    space and at some punctuation. Each of these passed it."""
    assert [rule for rule, _ in core.text_problems(text + "\n")] == [
        core.RULE_FILE_CREDENTIAL
    ]


@pytest.mark.parametrize(
    "text",
    [
        # An ordinary name that starts with the letters of a published prefix.
        "mounted /" + "hf_" + "cache as the model cache\n",
        "the task " + "sk-" + "ipped one step\n",
    ],
)
def test_an_ordinary_name_that_starts_with_a_published_prefix_is_refused_too(
    text: str,
) -> None:
    """Measured. The rule reads a prefix and no more of the word. A writer of such
    a file must rename the thing, or the file is not evidence of this layout."""
    assert [rule for rule, _ in core.text_problems(text)] == [core.RULE_FILE_CREDENTIAL]


@pytest.mark.parametrize(
    "text",
    [
        "HOME=" + "/" + "home" + "/" + "operator\n",
        '{"cwd":"' + "/" + "home" + "/" + "operator" + '"}\n',
        "/" + "Users" + "/" + "An Operator/work/x.log\n",
        "c:" + BACKSLASH + "users" + BACKSLASH + "operator" + BACKSLASH + "x\n",
        "/" + "users" + "/" + "operator/a\n",
        "/" + "home" + "/" + chr(0xE1) + "sad/x\n",
        # Measured: a URL whose host is one of the two names is refused as well.
        "GET http://" + "home" + "/status\n",
    ],
)
def test_a_user_directory_in_more_forms_is_refused(text: str) -> None:
    """The first commit asked for a separator after the account name and for the
    two names in one letter case. Each of these but the last passed it."""
    assert [rule for rule, _ in core.text_problems(text)] == [
        core.RULE_FILE_PERSONAL_PATH
    ]


@pytest.mark.parametrize(
    "text",
    [
        "wrote ~/run.log\n",
        "wrote ~operator/run.log\n",
        "wrote %USERPROFILE%" + BACKSLASH + "a.log\n",
        "wrote " + "home" + "/operator/run.log\n",
        "wrote C%3A%5C" + "Users" + "%5Coperator\n",
        "C:" + BACKSLASH * 4 + "Users" + BACKSLASH * 4 + "operator\n",
        # A prefix after a percent escape stands after a digit.
        "Bearer%20" + PREFIXED_WORD + "\n",
        # A prefix directly after a letter is inside a longer word.
        "value" + PREFIXED_WORD + "\n",
    ],
)
def test_forms_of_a_user_directory_and_of_a_prefix_that_still_pass(text: str) -> None:
    """Measured. No rule refuses these."""
    assert core.text_problems(text) == []


def test_the_text_rules_measured_on_every_committed_proof_file() -> None:
    """The corpus of both rules: each committed text file of ``docs/proof`` that is
    not a Markdown page. One file holds a published prefix: a ledger that names the
    prefix in a sentence. None holds a path under a user directory."""
    hits: dict[str, list[str]] = {}
    files = 0
    for path in sorted((REPO_ROOT / "docs" / "proof").rglob("*")):
        if not path.is_file() or path.suffix not in core.EVIDENCE_SUFFIXES - {".md"}:
            continue
        files += 1
        rules = [
            rule for rule, _ in core.text_problems(path.read_bytes().decode("utf-8"))
        ]
        if rules:
            hits[path.relative_to(REPO_ROOT).as_posix()] = rules
    assert files > 100
    assert hits == {
        "docs/proof/testing/v1-s5-012-pr2-migration.v1alpha1.json": [
            core.RULE_FILE_CREDENTIAL
        ]
    }


def _freeze_with(root: Path, data: bytes) -> Callable[[dict[str, Any]], None]:
    def change(manifest: dict[str, Any]) -> None:
        (root / FREEZE_REF).write_bytes(data)
        manifest["metadata"]["spec"]["freezeContentSha256"] = run_core.content_digest(
            data
        )

    return change


@pytest.mark.parametrize(
    "data",
    [
        b'{"metadata": {"revision": 1.0}}',
        b'{"metadata": {"revision": 1e0}}',
        b'{"metadata": {"revision": 7, "revision": 1}}',
        b'{"metadata": {"revision": 7}, "metadata": {"revision": 1}}',
        b'{"metadata": {"revision": 1}, "other": NaN}',
        b"[" * 100000 + b"]" * 100000,
    ],
    ids=["float", "exponent", "member-twice", "object-twice", "not-json", "nested"],
)
def test_a_freeze_record_read_more_loosely_than_a_manifest_is_refused(
    tmp_path: Path, data: bytes
) -> None:
    """The first commit read the record with the plain JSON reader. It accepted a
    revision of 1.0 and a member stated twice, and a deeply nested file raised an
    error that no rule names."""
    run_dir = _build(tmp_path, mutate=_freeze_with(tmp_path, data))
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FREEZE]
    assert core.repository_report(tmp_path).refused


def test_an_evidence_file_cannot_have_the_name_of_a_run_manifest(
    tmp_path: Path,
) -> None:
    """The manifest listing reads each file of that name as the manifest of a run.
    The first commit accepted one as an evidence file, and the listing then showed
    a second run."""

    def nested(manifest: dict[str, Any]) -> None:
        manifest["evidence"]["files"].append(
            {
                "role": "release",
                "path": f"sub/{run_core.MANIFEST_NAME}",
                "sha256": "0" * 64,
            }
        )

    run_dir = _build(tmp_path, mutate=nested)
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FILE_FORM]
    _write(run_dir / "sub" / run_core.MANIFEST_NAME, "{}\n")
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FILE_FORM]


def test_a_correction_cannot_add_a_file_with_the_name_of_a_run_manifest(
    tmp_path: Path,
) -> None:
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1, files={run_core.MANIFEST_NAME: ("release", "{}\n")})
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_FILE_FORM]
    assert core.repository_report(tmp_path).refused


def test_a_caller_file_that_a_correction_adds_is_read_as_a_caller_record(
    tmp_path: Path,
) -> None:
    """The first commit read a caller file only when the manifest named it."""
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1, files={"caller.jsonl": ("caller", '{"record":"header"}\n')})
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CALLER_RECORD]
    shutil.rmtree(tmp_path / CORRECTIONS_REF)
    _correct(
        tmp_path,
        1,
        files={"caller.jsonl": ("caller", _caller_record(run_id="another-run"))},
    )
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CALLER_IDENTITY]
    shutil.rmtree(tmp_path / CORRECTIONS_REF)
    _correct(tmp_path, 1, files={"caller.jsonl": ("caller", CALLER_TEXT)})
    assert core.check_run(run_dir, tmp_path).findings == ()


def test_an_entry_of_a_runs_or_corrections_directory_that_is_no_directory_is_refused(
    tmp_path: Path,
) -> None:
    """The first commit read the directories of each and did not see a file."""
    _build(tmp_path)
    _write(tmp_path / EXPERIMENT_REF / "runs" / "stray.txt", "One line.\n")
    _write(tmp_path / EXPERIMENT_REF / "corrections" / "note.md", "One line.\n")
    report = core.repository_report(tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_FILE_UNLISTED, f"{EXPERIMENT_REF}/corrections/note.md"),
        (core.RULE_FILE_UNLISTED, f"{EXPERIMENT_REF}/runs/stray.txt"),
    ]
    assert report.refused


def test_the_corrections_of_a_refused_run_get_no_finding_of_their_own(
    tmp_path: Path,
) -> None:
    """Measured. The corrections of a run are read when the run directory is in
    its place and its manifest validates."""
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1, mutate=_as("runId", "another-run"))
    (run_dir / run_core.MANIFEST_NAME).unlink()
    report = core.repository_report(tmp_path)
    assert [(run.path, _rules(run)) for run in report.runs] == [
        (RUN_REF, [core.RULE_MANIFEST_MISSING])
    ]
    assert report.findings == ()


def test_a_corrections_directory_of_a_run_that_is_a_file_is_refused(
    tmp_path: Path,
) -> None:
    run_dir = _build(tmp_path)
    _write(tmp_path / CORRECTIONS_REF, "A file where a directory is expected.\n")
    report = core.check_run(run_dir, tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_CORRECTION_RUN, CORRECTIONS_REF)
    ]
    assert core.repository_report(tmp_path).refused


def test_a_directory_junction_is_a_link_to_the_check(tmp_path: Path) -> None:
    """A real link on a host that lets the suite create no symbolic link."""
    if os.name != "nt":
        pytest.skip("a directory junction is of one host's file system")
    import _winapi

    run_dir = _build(tmp_path)
    outside = tmp_path / "outside"
    _write(outside / "a.json", "{}\n")
    _winapi.CreateJunction(str(outside), str(run_dir / "linked"))
    report = core.check_run(run_dir, tmp_path)
    assert [(f.rule, f.path) for f in report.findings] == [
        (core.RULE_FILE_NOT_REGULAR, f"{RUN_REF}/linked")
    ]
    with pytest.raises(core.LayoutError):
        core.describe_file(run_dir, "linked/a.json", "pods")
    (run_dir / "linked").rmdir()
    _winapi.CreateJunction(
        str(run_dir), str(tmp_path / EXPERIMENT_REF / "runs" / "alias")
    )
    listing = core.repository_report(tmp_path)
    assert [(f.rule, f.path) for f in listing.findings] == [
        (core.RULE_FILE_NOT_REGULAR, f"{EXPERIMENT_REF}/runs/alias")
    ]
    assert [run.path for run in listing.runs] == [RUN_REF]


def test_a_correction_can_correct_a_file_that_an_earlier_correction_adds(
    tmp_path: Path,
) -> None:
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1, files={"result.md": ("result", RESULT_TEXT + "Corrected.\n")})
    added = tmp_path / CORRECTIONS_REF / "correction-1" / "result.md"
    target = {"path": "correction-1/result.md", "sha256": core.file_digest(added)}
    _correct(tmp_path, 2, corrects=[target])
    assert core.check_run(run_dir, tmp_path).corrections == 2
    _write(added, "Another text.\n")
    assert _rules(core.check_run(run_dir, tmp_path)) == [
        core.RULE_CORRECTION_TARGET,
        core.RULE_FILE_DIGEST,
    ]


def test_a_correction_cannot_correct_a_file_that_it_adds_itself(tmp_path: Path) -> None:
    run_dir = _build(tmp_path)
    _correct(
        tmp_path,
        1,
        files={"result.md": ("result", RESULT_TEXT + "Corrected.\n")},
        mutate=lambda document: document["corrects"].append(
            {"path": "correction-1/result.md", "sha256": document["files"][0]["sha256"]}
        ),
    )
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CORRECTION_TARGET]


def _rewrite_correction(root: Path, number: int) -> None:
    """State in a correction the digests that the tree has now."""
    directory = root / CORRECTIONS_REF
    path = directory / f"correction-{number}.v1alpha1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    run_dir = root / RUN_REF
    document["manifestSha256"] = core.file_digest(run_dir / run_core.MANIFEST_NAME)
    previous = directory / f"correction-{number - 1}.v1alpha1.json"
    if previous.is_file():
        document["previousCorrectionSha256"] = core.file_digest(previous)
    for target in document["corrects"]:
        if (run_dir / target["path"]).is_file():
            target["sha256"] = core.file_digest(run_dir / target["path"])
    _write_json(path, document)


def test_a_run_and_its_corrections_rewritten_together_conform(tmp_path: Path) -> None:
    """Measured. A correction pins the manifest only while the correction is
    unchanged. A file, the manifest, and each correction, replaced together, are a
    run directory that conforms, and the raw digest has moved."""
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1, corrects=[_target(run_dir, "pods.jsonl")])
    _correct(tmp_path, 2)
    before = core.check_run(run_dir, tmp_path)
    _write(run_dir / "pods.jsonl", PODS_TEXT + PODS_TEXT)
    manifest = _manifest(run_dir)
    for entry in manifest["evidence"]["files"]:
        entry["sha256"] = core.file_digest(run_dir / entry["path"])
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)
    assert core.RULE_CORRECTION_IDENTITY in _rules(core.check_run(run_dir, tmp_path))
    _rewrite_correction(tmp_path, 1)
    _rewrite_correction(tmp_path, 2)
    after = core.check_run(run_dir, tmp_path)
    assert after.findings == () and after.corrections == 2
    assert before.digests is not None and after.digests is not None
    assert before.digests.raw != after.digests.raw


def _target(run_dir: Path, name: str) -> dict[str, str]:
    return {"path": name, "sha256": core.file_digest(run_dir / name)}


def test_an_edited_correction_with_the_next_one_rewritten_conforms(
    tmp_path: Path,
) -> None:
    """Measured. The chain refuses an edit of an earlier correction only while the
    later one is unchanged."""
    run_dir = _build(tmp_path)
    first = _correct(tmp_path, 1)
    _correct(tmp_path, 2)
    document = json.loads(first.read_text(encoding="utf-8"))
    document["statements"] = ["Another statement. This is a fixture."]
    _write_json(first, document)
    assert _rules(core.check_run(run_dir, tmp_path)) == [core.RULE_CORRECTION_CHAIN]
    _rewrite_correction(tmp_path, 2)
    assert core.check_run(run_dir, tmp_path).findings == ()


def test_removed_corrections_leave_a_run_directory_that_conforms(
    tmp_path: Path,
) -> None:
    """Measured. Nothing in the tree states how many corrections a run has."""
    run_dir = _build(tmp_path)
    _correct(tmp_path, 1)
    _correct(tmp_path, 2)
    (tmp_path / CORRECTIONS_REF / "correction-2.v1alpha1.json").unlink()
    assert core.check_run(run_dir, tmp_path).corrections == 1
    shutil.rmtree(tmp_path / CORRECTIONS_REF)
    report = core.check_run(run_dir, tmp_path)
    assert report.findings == () and report.corrections == 0


def test_a_corrections_directory_under_another_letter_case_is_not_read(
    tmp_path: Path,
) -> None:
    """Measured. The names ``corrections`` and the run identifier are compared as
    text. A directory under another letter case is not the corrections directory of
    the run on any host, and no rule refuses it."""
    run_dir = _build(tmp_path)
    _correct(tmp_path, 2)
    (tmp_path / EXPERIMENT_REF / "corrections").rename(
        tmp_path / EXPERIMENT_REF / "Corrections"
    )
    report = core.check_run(run_dir, tmp_path)
    assert report.findings == () and report.corrections == 0
    assert not core.repository_report(tmp_path).refused


def test_what_the_form_of_a_correction_still_accepts(tmp_path: Path) -> None:
    """Measured. The recorded time is compared with no other time. The shape
    heuristic of the ExperimentRun rules is not applied to a statement."""
    shaped = (
        "The identifier was " + "Zx4Kq9TbLm2Rd7" + "Wf1Hs3Nv8Yc6Ej0Pa in the reading."
    )
    assert run_core.credential_shaped(shaped)
    run_dir = _build(tmp_path)
    _correct(
        tmp_path,
        1,
        mutate=lambda document: document.update(
            recordedAt="1999-01-01T00:00:00Z", statements=[shaped]
        ),
    )
    assert core.check_run(run_dir, tmp_path).findings == ()


def test_what_a_run_directory_still_accepts(tmp_path: Path) -> None:
    """Measured. An empty directory, an empty file, a byte order mark, and a lone
    carriage return are each in a run directory that conforms."""
    files = {
        **FILES,
        "empty.txt": ("transcript", ""),
        "marked.txt": ("transcript", chr(0xFEFF) + "One line.\n"),
        "returns.txt": ("transcript", "one\rtwo\r"),
    }
    run_dir = _build(tmp_path, files=files)
    (run_dir / "an-empty-directory").mkdir()
    assert core.check_run(run_dir, tmp_path).findings == ()


def test_the_review_gate_refuses_a_manifest_that_names_the_freeze_record_twice() -> (
    None
):
    """A manifest with the member of each shape could let a review name one record
    and a reader see the other."""
    both = {"metadata": {"spec": {"freezeRecord": "b"}, "freezeRecord": "a"}}
    with pytest.raises(ValueError):
        index_core._named_freeze_record(both)
    shapes: tuple[Any, ...] = (
        {"spec": None},
        {"spec": {}},
        {"spec": "text"},
        [],
        "text",
    )
    for metadata in shapes:
        with pytest.raises((KeyError, TypeError, AttributeError)):
            index_core._named_freeze_record({"metadata": metadata})


def test_a_writer_is_refused_a_role_that_is_no_text_and_a_name_in_another_case(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "Extra.json", "{}\n")
    with pytest.raises(core.LayoutError) as refusal:
        core.describe_file(tmp_path, "extra.json", "pods")
    assert refusal.value.rule == core.RULE_FILE_MISSING
    with pytest.raises(core.LayoutError) as refusal:
        core.describe_file(tmp_path, "extra.json", ["pods"])  # type: ignore[arg-type]
    assert refusal.value.rule == core.RULE_ROLE


def test_a_writer_gets_an_entry_that_the_check_of_the_directory_refuses(
    tmp_path: Path,
) -> None:
    """Measured. The helper reads one file and knows no manifest, so it returns an
    entry for a caller file that is no caller record."""
    _write(tmp_path / "caller.jsonl", '{"record":"header"}\n')
    assert core.describe_file(tmp_path, "caller.jsonl", "caller")["role"] == "caller"


def test_the_digest_lines_are_in_the_order_of_the_paths_as_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("a/b.txt", "a-b.txt", "a.txt", "b.txt"):
        _write(tmp_path / "d" / name, "One line.\n")
    _write(tmp_path / "d" / "t.txt", f"key {PREFIXED_WORD}\n")
    lines, findings = core.digest_lines(tmp_path / "d")
    assert [line.split("  ")[1] for line in lines] == [
        "a-b.txt",
        "a.txt",
        "a/b.txt",
        "b.txt",
    ]
    assert [(f.rule, f.path) for f in findings] == [
        (core.RULE_FILE_CREDENTIAL, "t.txt")
    ]
    lines, findings = core.digest_lines(tmp_path / "absent")
    assert lines == [] and [f.rule for f in findings] == [core.RULE_FILE_MISSING]
    assert command.main(["digests", str(tmp_path / "absent")]) == command.EXIT_REFUSED
    assert command.main(["digests", str(tmp_path / "d" / "a.txt")]) == (
        command.EXIT_REFUSED
    )
    capsys.readouterr()


def test_the_check_command_refuses_an_earlier_run_directory_at_its_manifest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The ``repository`` command lists an earlier run directory and does not check
    it. The ``check`` command, given one, checks it."""
    earlier = "docs/proof/experiments/v2-e01/runs/20261006-e01-d-1"
    assert command.main(["check", str(REPO_ROOT / earlier)]) == command.EXIT_REFUSED
    out = capsys.readouterr().out
    assert out.startswith(f"REFUSED    {earlier}  (1 finding(s))\n")
    assert core.RULE_MANIFEST_REFUSED in out


# --------------------------------------------------------------------------
# What no rule holds
# --------------------------------------------------------------------------


def test_a_derived_file_that_was_not_computed_from_the_raw_files_conforms(
    tmp_path: Path,
) -> None:
    """Measured. The rule asks for a raw file beside a derived file. No rule reads
    the derived file, so no rule shows that it follows from the raw files."""
    files = {**FILES, "result.md": ("result", "Every criterion held.\n")}
    assert core.check_run(_build(tmp_path, files=files), tmp_path).findings == ()


def test_a_raw_file_other_than_a_caller_record_is_not_read_for_its_meaning(
    tmp_path: Path,
) -> None:
    """Measured. A file with the role pods that holds no reading of a pod conforms."""
    files = {**FILES, "pods.jsonl": ("pods", "not a reading of a pod\n")}
    assert core.check_run(_build(tmp_path, files=files), tmp_path).findings == ()


def test_every_rule_identifier_is_named_in_this_suite() -> None:
    """Each rule identifier is named in this module. The test reads the
    source for the name. It does not show that an assertion provokes the
    rule."""
    source = Path(__file__).read_text(encoding="utf-8")
    names = {
        name: value
        for name, value in vars(core).items()
        if name.startswith("RULE_") and isinstance(value, str)
    }
    assert sorted(names.values()) == sorted(RULE_IDS)
    for name in names:
        assert f"core.{name}" in source, name
