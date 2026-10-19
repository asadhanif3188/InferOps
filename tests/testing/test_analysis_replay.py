"""The analysis of an experiment run, bound to its evidence and computed again.

``tools.analysis_replay`` reads a run directory, computes the reliability
analysis from the manifest and the raw evidence files, and states the digest of
each input and the code that computed the document. A replay computes a stored
document again and compares the two byte for byte.

**No run executed, and no run was analysed.** Each run directory here is built
by the suite. The evidence files are the six synthetic cases that
``tests/domain/test_reliability_analysis.py`` commits. The manifest is a
committed ExperimentRun fixture with other identifiers, and the freeze record
is one line that freezes no experiment. One run directory of this kind is
committed, under ``tests/testing/fixtures/analysis-replay``, as an example of a
replay. To write it again, run this module as a script.

The suite holds the tool to these properties.

*A stored document is not authoritative.* A figure, a statement, a declared
value, a member, or the form of a stored run analysis that was changed by hand
is refused, with the digest in the manifest changed to match. One edited figure
is also refused with the manifest left as it was.

*Evidence that changed or is absent refuses the replay.* The layout check
refuses a run directory first. A file and its digest in the manifest, replaced
together, are refused by the digest that the document states.

*The code has two identities.* The source digest follows each source file, a
document that another code wrote replays with that stated, and a commit is held
to Git only when the clone holds it.

*An aggregate leaves no run out.* The result state of each run is the one of
its manifest, a run of the experiment that was not given is a refusal under
each spelling of an argument, a directory beside the runs that does not conform
is a refusal, and a counted run with no value leaves the aggregate with no
median.

*A result state alone leaves no run out.* A run in the state INCONCLUSIVE,
REFUSED, or ABORTED is not counted only for a reason that the freeze record of
its manifest registers for the experiment, the state, and the run, in a record
that the freeze registry of the tree pins. The aggregate states that reason
and that record. A reason that is changed, or that no record registers,
refuses the aggregate. So does a reason that only an earlier revision
registers, and a reason that was added to a record while the registry pins the
earlier content. A run that is not counted does not choose its record: each
run of the aggregate must name the same one. Each freeze record and each
registry here is built by the suite, and it freezes no experiment.

*The record is read at the executing revision.* A test that leaves a run out
makes a clone in its temporary tree and commits the record and the registry.
The run states that commit. A reason that is registered afterwards, with the
tree made to agree with itself, refuses the aggregate, and so does a commit
that the clone does not hold. A manifest that restates its executing revision
to a later commit is accepted, and the suite measures that.

*Nothing is promoted.* A document that replays holds no claim status, no
evidence level, and no result state, the evidence index refuses a run whose
analysis does not replay, and it states nothing about one that does.

These tests show what the tool computes from files. No test here is evidence of
a run, of a failure, or of a recovery.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
#: The run directories of the Sprint 5 integration validation, one for each
#: attempt, added by V2-S5-006-PR1. Each is of the published layout. An attempt
#: added later is a visible change of this tuple.
INTEGRATION_RUNS = ("integration-1", "integration-2")
INTEGRATION_DIRECTORY = "docs/proof/experiments/v2-s5-integration/runs"
if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT))

from tools import evidence_index  # noqa: E402
from tools import reliability_analysis as analysis  # noqa: E402
from tools.analysis_replay import __main__ as command  # noqa: E402
from tools.analysis_replay import core  # noqa: E402
from tools.evidence_index import core as index_core  # noqa: E402
from tools.evidence_model import load_register  # noqa: E402
from tools.experiment_evidence import ROLES, check_run, file_digest  # noqa: E402
from tools.experiment_freeze import REGISTRY_PATH, load_registry  # noqa: E402
from tools.experiment_run import core as run_core  # noqa: E402

pytestmark = pytest.mark.docs

PAGE = REPO_ROOT / "docs" / "testing" / "analysis-replay.md"
CASES = REPO_ROOT / "tests" / "domain" / "fixtures" / "reliability-analysis"
EXAMPLE_ROOT = REPO_ROOT / "tests" / "testing" / "fixtures" / "analysis-replay"
BASE: dict[str, Any] = json.loads(
    (
        REPO_ROOT
        / "contracts"
        / "experiment"
        / "examples"
        / "valid"
        / "fault-injected-passed.json"
    ).read_text(encoding="utf-8")
)

EXPERIMENT = "example-experiment"
EXPERIMENT_REF = "docs/proof/experiments/example-replay"
FREEZE_REF = f"{EXPERIMENT_REF}/freeze-r1.v1alpha1.json"
FREEZE_TEXT = (
    '{"metadata": {"revision": 1}, "synthetic": "A fixture. It freezes no '
    'experiment."}\n'
)
#: A placeholder. A commit cannot name itself, so no built document states the
#: commit that holds the code that wrote it.
REVISION = "c" * 40
CASE_NAMES = (
    "abort",
    "clock-ties",
    "concurrency",
    "missing-signal",
    "open-episode",
    "zero-failure",
)
EXAMPLE_CASE = "concurrency"
ANALYSIS_FILE = "analysis.json"
REASON = "The run decides no criterion. This document is a fixture."
OTHER_REASON = "An abort condition stopped the run. This document is a fixture."
#: The reason of the probe that showed the defect. No record registers it.
POST_HOC_REASON = "Excluded after inspection. No preregistered reason exists."


#: The commit of each temporary clone that :func:`_commit` wrote last. A run
#: that is built in such a tree states that commit as its executing revision.
HEADS: dict[Path, str] = {}


def _git(root: Path, *arguments: str) -> str:
    done = subprocess.run(
        [
            "git",
            "-c",
            "user.name=suite",
            "-c",
            "user.email=suite@example.invalid",
            "-c",
            "core.autocrlf=false",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "tag.gpgsign=false",
            *arguments,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return done.stdout.strip()


def _commit(root: Path) -> str:
    """Commit each file of a temporary tree to its own clone, and give the commit.

    The clone is made in the tree when it has none. The checkout of this suite
    is not read and not written.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    if not (root / ".git").exists():
        _git(root, "init", "--quiet")
    _git(root, "add", "--all")
    _git(root, "commit", "--quiet", "--allow-empty", "-m", "a tree of the suite")
    HEADS[root] = _git(root, "rev-parse", "HEAD")
    return HEADS[root]


def _run_id(case: str) -> str:
    return f"{case}-1"


def _run_ref(case: str) -> str:
    return f"{EXPERIMENT_REF}/runs/{_run_id(case)}"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _write_json(path: Path, document: Any) -> None:
    _write(path, json.dumps(document, indent=2) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def _declaration(case: str) -> str:
    return (CASES / case / "declaration.json").read_text(encoding="utf-8")


def _manifest(
    root: Path,
    run_id: str,
    entries: list[dict[str, str]],
    state: str,
    experiment: str = EXPERIMENT,
) -> dict[str, Any]:
    """A manifest of the published schema for one synthetic run directory."""
    manifest = copy.deepcopy(BASE)
    if root in HEADS:
        manifest["metadata"]["executingRevision"] = HEADS[root]
    manifest["metadata"].update(
        experimentId=experiment,
        runId=run_id,
        startedAt="2026-10-12T07:59:00Z",
        finishedAt="2026-10-12T08:05:00Z",
        spec={
            "freezeRecord": FREEZE_REF,
            "freezeRevision": 1,
            "freezeContentSha256": run_core.content_digest(
                (root / FREEZE_REF).read_bytes()
            ),
        },
    )
    manifest["fault"]["injectedAt"] = "2026-10-12T08:00:30.000Z"
    if state == "REFUSED":
        # A REFUSED run did not start its procedure, so its manifest states no
        # injected fault. The evidence files of the case are left as they are.
        manifest["fault"] = {
            "registered": True,
            "type": manifest["fault"]["type"],
            "injected": False,
            "reason": "The run was refused before its procedure started.",
        }
    manifest["result"] = (
        {"state": state}
        if state in run_core.DECIDED_STATES
        else {"state": state, "reason": REASON}
    )
    manifest["evidence"]["files"] = entries
    return manifest


def _raw_run(root: Path, case: str, state: str = "FAILED") -> Path:
    """A run directory that holds the evidence files of one case and no analysis.

    The freeze record is the one line that registers nothing, unless the tree
    holds a record already.
    """
    if not (root / FREEZE_REF).exists():
        _write(root / FREEZE_REF, FREEZE_TEXT)
    run_dir = root / _run_ref(case)
    entries = []
    for source in sorted((CASES / case).glob("*.jsonl")):
        _write(run_dir / source.name, source.read_bytes().decode("utf-8"))
        entries.append(
            {
                "role": source.stem,
                "path": source.name,
                "sha256": file_digest(run_dir / source.name),
            }
        )
    _write_json(
        run_dir / run_core.MANIFEST_NAME,
        _manifest(root, _run_id(case), entries, state),
    )
    return run_dir


def _store(run_dir: Path, text: str, name: str = ANALYSIS_FILE) -> None:
    """Write a file with the role analysis, and name it in the manifest."""
    _write(run_dir / name, text)
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    files = [entry for entry in manifest["evidence"]["files"] if entry["path"] != name]
    files.append(
        {"role": "analysis", "path": name, "sha256": file_digest(run_dir / name)}
    )
    manifest["evidence"]["files"] = files
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)


def _bound_run(root: Path, case: str, state: str = "FAILED") -> Path:
    """A run directory with its run analysis, as a person would commit it."""
    run_dir = _raw_run(root, case, state)
    document = core.bind_run(run_dir, _declaration(case), REVISION, root)
    _store(run_dir, core.record_text(document))
    return run_dir


def _stored(run_dir: Path) -> dict[str, Any]:
    return _read_json(run_dir / ANALYSIS_FILE)


def _rewrite(run_dir: Path, change: Callable[[dict[str, Any]], None]) -> None:
    """Change the stored run analysis by hand, and make the manifest match it."""
    document = _stored(run_dir)
    change(document)
    _store(run_dir, core.record_text(document))


def _rules(report: core.RunReplay) -> list[str]:
    return sorted({finding.rule for finding in report.findings})


def _messages(report: core.RunReplay) -> str:
    return " ".join(finding.message for finding in report.findings)


# --------------------------------------------------------------------------
# The control, and the document
# --------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASE_NAMES)
def test_a_run_analysis_holds_the_analysis_of_the_evidence_files(
    tmp_path: Path, case: str
) -> None:
    """The control. The figures are those of the committed case, byte for byte."""
    run_dir = _raw_run(tmp_path, case)
    document = core.bind_run(run_dir, _declaration(case), REVISION, tmp_path)
    committed = (CASES / case / "analysis.json").read_bytes().decode("utf-8")
    assert analysis.analysis_text(document["analysis"]) == committed
    assert document["schema"] == core.SCHEMA
    assert (document["experimentId"], document["runId"]) == (EXPERIMENT, _run_id(case))
    assert document["runDirectory"] == _run_ref(case)


@pytest.mark.parametrize("case", CASE_NAMES)
def test_a_stored_run_analysis_replays(tmp_path: Path, case: str) -> None:
    report = core.replay_run(_bound_run(tmp_path, case), tmp_path)
    assert report.findings == ()
    assert report.status == core.REPLAYED
    assert report.path == _run_ref(case)
    (replayed,) = report.analyses
    assert (replayed.path, replayed.code, replayed.changed_sources) == (
        ANALYSIS_FILE,
        core.CODE_SAME,
        (),
    )


def test_a_run_analysis_states_each_input_as_the_manifest_does(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, "missing-signal")
    document = _stored(run_dir)
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    named = {
        entry["role"]: entry
        for entry in manifest["evidence"]["files"]
        if entry["role"] != "analysis"
    }
    assert [entry["name"] for entry in document["inputs"]] == [
        name for name in analysis.INPUTS if name in named
    ]
    for entry in document["inputs"]:
        assert entry["path"] == named[entry["name"]]["path"]
        assert entry["sha256"] == named[entry["name"]]["sha256"]
        assert entry["sha256"] == file_digest(run_dir / entry["path"])
    # The case does not give the argo stream and the pods stream.
    assert document["notGiven"] == ["pods", "argo"]
    assert document["analysis"]["inputs"]["argo"] == "not-given"


def test_the_raw_evidence_digest_is_the_one_of_the_layout_check(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    report = check_run(run_dir, tmp_path)
    assert report.digests is not None
    document = _stored(run_dir)
    assert document["rawEvidence"] == {
        "sha256": report.digests.raw,
        "files": report.raw_files,
    }
    # The run analysis is a derived file, so adding it did not move the digest.
    assert report.files == report.raw_files + 1


def test_a_run_analysis_is_stored_with_sorted_members_and_line_feeds(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    data = (run_dir / ANALYSIS_FILE).read_bytes()
    assert b"\r" not in data and data.endswith(b"}\n")
    document = json.loads(data)
    assert data.decode("utf-8") == json.dumps(document, indent=2, sort_keys=True) + "\n"
    assert set(document) == {
        "schema",
        "experimentId",
        "runId",
        "runDirectory",
        "rawEvidence",
        "inputs",
        "notGiven",
        "declaration",
        "analysisCode",
        "analysis",
        "authority",
        "limitations",
        "doesNotEstablish",
    }
    assert document["authority"] == core.AUTHORITY
    assert document["limitations"] == list(core.LIMITATIONS)
    assert document["doesNotEstablish"] == list(core.DOES_NOT_ESTABLISH)


def test_a_checkout_with_carriage_returns_replays(tmp_path: Path) -> None:
    """A Windows checkout can hold each text file with CRLF. The digests do not move."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    for path in sorted(tmp_path.rglob("*")):
        if path.is_file():
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert b"\r\n" in (run_dir / "caller.jsonl").read_bytes()
    assert core.replay_run(run_dir, tmp_path).status == core.REPLAYED


def test_the_declaration_of_a_document_is_the_one_that_was_given(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    assert _stored(run_dir)["declaration"] == json.loads(_declaration(EXAMPLE_CASE))


# --------------------------------------------------------------------------
# A stored document is not authoritative
# --------------------------------------------------------------------------


def _set_figure(document: dict[str, Any]) -> None:
    """Lower the episode figure, or give an open episode a duration."""
    episodes = document["analysis"]["caller"]["failureEpisodes"]
    if episodes["callerFailureEpisodeMs"] is None:
        episodes["callerFailureEpisodeMs"] = 60_000
    else:
        episodes["callerFailureEpisodeMs"] -= 1


def _drop_limitation(document: dict[str, Any]) -> None:
    document["limitations"].pop()


def _add_member(document: dict[str, Any]) -> None:
    document["reviewedBy"] = "a person"


def _drop_without_value(document: dict[str, Any]) -> None:
    assert document["analysis"]["withoutValue"]
    document["analysis"]["withoutValue"] = []


def _widen_window(document: dict[str, Any]) -> None:
    document["declaration"]["window"]["to"] = "2026-10-12T08:02:00.000Z"


def _lower_threshold(document: dict[str, Any]) -> None:
    document["declaration"]["signals"][0]["problemBelow"] = 1


HAND_EDITS = {
    "a figure": _set_figure,
    "a limitation": _drop_limitation,
    "a new member": _add_member,
    "the list of metrics with no value": _drop_without_value,
    "the declared window": _widen_window,
    "a declared threshold": _lower_threshold,
}


@pytest.mark.parametrize("edit", sorted(HAND_EDITS))
def test_a_hand_edit_with_a_matching_manifest_is_refused(
    tmp_path: Path, edit: str
) -> None:
    """The manifest states the digest of the edited file, so the layout check passes."""
    run_dir = _bound_run(tmp_path, "open-episode")
    _rewrite(run_dir, HAND_EDITS[edit])
    assert check_run(run_dir, tmp_path).status == run_core.CONFORMING
    report = core.replay_run(run_dir, tmp_path)
    assert report.status == core.REFUSED
    assert _rules(report) == [core.RULE_DOCUMENT]


def test_a_hand_edit_with_the_manifest_left_as_it_was_is_refused(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    document = _stored(run_dir)
    _set_figure(document)
    _write(run_dir / ANALYSIS_FILE, core.record_text(document))
    report = core.replay_run(run_dir, tmp_path)
    assert _rules(report) == [core.RULE_RUN]
    assert "evidence-file-digest-differs" in _messages(report)


def test_a_document_in_another_form_is_refused(tmp_path: Path) -> None:
    """The same members with other white space are not the stored text."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    _store(run_dir, json.dumps(_stored(run_dir), sort_keys=True) + "\n")
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_DOCUMENT]


def test_a_refusal_repeats_no_figure_of_the_document(tmp_path: Path) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    document = _stored(run_dir)
    document["analysis"]["caller"]["failureEpisodes"]["callerFailureEpisodeMs"] = 987654
    _store(run_dir, core.record_text(document))
    assert "987654" not in _messages(core.replay_run(run_dir, tmp_path))


def test_a_refusal_repeats_no_text_of_the_stored_declaration(tmp_path: Path) -> None:
    """The first commit repeated the message of the analysis, which quotes a value."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)

    def rename(document: dict[str, Any]) -> None:
        signal = document["declaration"]["signals"][0]
        signal["id"], signal["source"] = "p99-latency-987654-ms", "no-such-source"

    _rewrite(run_dir, rename)
    report = core.replay_run(run_dir, tmp_path)
    assert _rules(report) == [core.RULE_ANALYSIS]
    assert "987654" not in _messages(report)
    assert "analysis-signal-unsupported" in _messages(report)
    (problem,) = core.gate_problems(run_dir, tmp_path)
    assert "987654" not in problem


def test_a_run_directory_outside_the_root_is_shown_by_its_name(tmp_path: Path) -> None:
    """A refusal holds no path of a host."""
    run_dir = _bound_run(tmp_path / "tree", EXAMPLE_CASE)
    other = tmp_path / "elsewhere"
    other.mkdir()
    report = core.replay_run(run_dir, other)
    assert report.status == core.REFUSED
    assert report.path == run_dir.name
    assert [finding.path for finding in report.findings] == [run_dir.name]
    assert str(tmp_path) not in _messages(report)
    assert tmp_path.as_posix() not in _messages(report)


def test_an_evidence_file_that_the_analysis_no_longer_reads_refuses_the_replay(
    tmp_path: Path,
) -> None:
    """A changed file with a matching manifest can be refused by the analysis first."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    _write(run_dir / "pods.jsonl", "not a stream\n")
    _restate(run_dir, "pods.jsonl")
    assert check_run(run_dir, tmp_path).status == run_core.CONFORMING
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_ANALYSIS]


def test_a_raw_file_that_the_analysis_does_not_read_moves_the_raw_digest(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    _write(run_dir / "transcript.txt", "exit status 0\n")
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    manifest["evidence"]["files"].append(
        {
            "role": "transcript",
            "path": "transcript.txt",
            "sha256": file_digest(run_dir / "transcript.txt"),
        }
    )
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)
    assert check_run(run_dir, tmp_path).status == run_core.CONFORMING
    report = core.replay_run(run_dir, tmp_path)
    assert _rules(report) == [core.RULE_EVIDENCE]
    assert "rawEvidence" in _messages(report)


def test_a_changed_reason_of_a_metric_with_no_value_is_refused(tmp_path: Path) -> None:
    run_dir = _bound_run(tmp_path, "open-episode")

    def change(document: dict[str, Any]) -> None:
        episodes = document["analysis"]["caller"]["failureEpisodes"]
        assert episodes["reason"] == "episode-open"
        episodes["reason"] = "no-completion-in-window"

    _rewrite(run_dir, change)
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_DOCUMENT]


def test_a_changed_declaration_that_is_computed_again_replays(tmp_path: Path) -> None:
    """A measured limit: the declaration is held to no frozen record."""
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    declaration = json.loads(_declaration(EXAMPLE_CASE))
    declaration["signals"][0]["problemBelow"] = 1
    document = core.bind_run(run_dir, json.dumps(declaration), REVISION, tmp_path)
    _store(run_dir, core.record_text(document))
    assert core.replay_run(run_dir, tmp_path).status == core.REPLAYED


# --------------------------------------------------------------------------
# Evidence that changed or is absent
# --------------------------------------------------------------------------


def _touch_caller(run_dir: Path) -> None:
    """Change one value of the caller record that no figure reads."""
    path = run_dir / "caller.jsonl"
    text = path.read_bytes().decode("utf-8")
    assert '"outputTokens":40' in text
    _write(path, text.replace('"outputTokens":40', '"outputTokens":41', 1))


def _restate(run_dir: Path, name: str) -> None:
    """Give the manifest the present digest of one file that it names."""
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    for entry in manifest["evidence"]["files"]:
        if entry["path"] == name:
            entry["sha256"] = file_digest(run_dir / name)
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)


def test_an_evidence_file_that_changed_refuses_the_replay(tmp_path: Path) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    _touch_caller(run_dir)
    report = core.replay_run(run_dir, tmp_path)
    assert report.status == core.REFUSED
    assert _rules(report) == [core.RULE_RUN]
    assert "evidence-file-digest-differs" in _messages(report)


def test_an_evidence_file_that_is_absent_refuses_the_replay(tmp_path: Path) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    (run_dir / "endpoints.jsonl").unlink()
    report = core.replay_run(run_dir, tmp_path)
    assert _rules(report) == [core.RULE_RUN]
    assert "evidence-file-missing" in _messages(report)


def test_a_file_and_its_manifest_digest_replaced_together_are_refused(
    tmp_path: Path,
) -> None:
    """The layout check accepts the pair. The document states the earlier digest."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    _touch_caller(run_dir)
    _restate(run_dir, "caller.jsonl")
    assert check_run(run_dir, tmp_path).status == run_core.CONFORMING
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_EVIDENCE]


def test_a_file_that_is_removed_from_the_run_and_the_manifest_is_refused(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    (run_dir / "argo.jsonl").unlink()
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    manifest["evidence"]["files"] = [
        entry for entry in manifest["evidence"]["files"] if entry["role"] != "argo"
    ]
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)
    assert check_run(run_dir, tmp_path).status == run_core.CONFORMING
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_EVIDENCE]


def test_stated_digests_that_were_patched_by_hand_leave_the_figures_refused(
    tmp_path: Path,
) -> None:
    """The digests of the document agree with the run again. Its figures do not."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    (run_dir / "argo.jsonl").unlink()
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    manifest["evidence"]["files"] = [
        entry for entry in manifest["evidence"]["files"] if entry["role"] != "argo"
    ]
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)
    again = core.bind_run(run_dir, _declaration(EXAMPLE_CASE), REVISION, tmp_path)

    def patch(document: dict[str, Any]) -> None:
        for name in ("rawEvidence", "inputs", "notGiven"):
            document[name] = again[name]

    _rewrite(run_dir, patch)
    report = core.replay_run(run_dir, tmp_path)
    assert _rules(report) == [core.RULE_DOCUMENT]


def test_everything_replaced_together_replays(tmp_path: Path) -> None:
    """A measured limit. The replay reads one tree and not Git."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    before = _stored(run_dir)
    _touch_caller(run_dir)
    _restate(run_dir, "caller.jsonl")
    again = core.bind_run(run_dir, _declaration(EXAMPLE_CASE), REVISION, tmp_path)
    _store(run_dir, core.record_text(again))
    assert core.replay_run(run_dir, tmp_path).status == core.REPLAYED
    assert again["rawEvidence"] != before["rawEvidence"]


@pytest.mark.parametrize(
    "member, value",
    [
        ("experimentId", "another-experiment"),
        ("runId", "another-run"),
        ("runDirectory", f"{EXPERIMENT_REF}/runs/another-run"),
        ("notGiven", ["pods"]),
    ],
)
def test_a_document_that_names_another_run_is_refused(
    tmp_path: Path, member: str, value: object
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    _rewrite(run_dir, lambda document: document.__setitem__(member, value))
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_EVIDENCE]


def test_a_run_directory_with_no_analysis_states_that(tmp_path: Path) -> None:
    report = core.replay_run(_raw_run(tmp_path, EXAMPLE_CASE), tmp_path)
    assert (report.status, report.analyses, report.findings) == (
        core.NO_ANALYSIS,
        (),
        (),
    )


# --------------------------------------------------------------------------
# What the tool does not bind
# --------------------------------------------------------------------------


def test_a_declaration_of_another_run_is_refused(tmp_path: Path) -> None:
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    with pytest.raises(core.ReplayRefused) as refused:
        core.bind_run(run_dir, _declaration("abort"), REVISION, tmp_path)
    assert refused.value.rule == core.RULE_DECLARATION_IDENTITY


def test_a_declaration_that_the_analysis_refuses_is_refused(tmp_path: Path) -> None:
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    with pytest.raises(core.ReplayRefused) as refused:
        core.bind_run(run_dir, "{}", REVISION, tmp_path)
    assert refused.value.rule == core.RULE_ANALYSIS
    assert "analysis-declaration-unsupported" in refused.value.message


def test_two_files_with_one_role_that_the_analysis_reads_are_refused(
    tmp_path: Path,
) -> None:
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    _write(run_dir / "pods-2.jsonl", (run_dir / "pods.jsonl").read_text("utf-8"))
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    manifest["evidence"]["files"].append(
        {
            "role": "pods",
            "path": "pods-2.jsonl",
            "sha256": file_digest(run_dir / "pods-2.jsonl"),
        }
    )
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)
    with pytest.raises(core.ReplayRefused) as refused:
        core.bind_run(run_dir, _declaration(EXAMPLE_CASE), REVISION, tmp_path)
    assert refused.value.rule == core.RULE_INPUT_AMBIGUOUS


def test_a_run_with_no_caller_record_has_no_run_analysis(tmp_path: Path) -> None:
    """The analysis requires the caller record. No figure is invented without it."""
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE, "INCONCLUSIVE")
    (run_dir / "caller.jsonl").unlink()
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    manifest["evidence"]["files"] = [
        entry for entry in manifest["evidence"]["files"] if entry["role"] != "caller"
    ]
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)
    assert check_run(run_dir, tmp_path).status == run_core.CONFORMING
    with pytest.raises(core.ReplayRefused) as refused:
        core.bind_run(run_dir, _declaration(EXAMPLE_CASE), REVISION, tmp_path)
    assert refused.value.rule == core.RULE_ANALYSIS
    assert "analysis-input-refused" in refused.value.message


def test_a_run_directory_that_the_layout_refuses_is_not_bound(tmp_path: Path) -> None:
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    _write(run_dir / "notes.txt", "A file that the manifest does not name.\n")
    with pytest.raises(core.ReplayRefused) as refused:
        core.bind_run(run_dir, _declaration(EXAMPLE_CASE), REVISION, tmp_path)
    assert refused.value.rule == core.RULE_RUN
    assert "evidence-file-unlisted" in refused.value.message


@pytest.mark.parametrize(
    "text",
    [
        "not JSON\n",
        "[]\n",
        '{"schema": "inferops.io/run-analysis/v1alpha1", "schema": "x"}\n',
        '{"schema": "inferops.io/reliability-analysis/v1alpha1"}\n',
    ],
)
def test_a_file_with_the_role_analysis_that_is_no_run_analysis_is_refused(
    tmp_path: Path, text: str
) -> None:
    """The last text has the schema name of a document that states no digest."""
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    _store(run_dir, text)
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_RECORD_UNREADABLE]


def test_a_bare_analysis_document_under_the_role_analysis_is_refused(
    tmp_path: Path,
) -> None:
    """The committed analysis of a case is correct, and it is bound to nothing."""
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    _store(run_dir, (CASES / EXAMPLE_CASE / "analysis.json").read_text("utf-8"))
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_RECORD_UNREADABLE]


def test_each_run_analysis_of_a_run_is_replayed(tmp_path: Path) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    text = (run_dir / ANALYSIS_FILE).read_text("utf-8")
    _store(run_dir, text, "analysis-2.json")
    assert len(core.replay_run(run_dir, tmp_path).analyses) == 2
    document = json.loads(text)
    _set_figure(document)
    _store(run_dir, core.record_text(document), "analysis-2.json")
    report = core.replay_run(run_dir, tmp_path)
    assert [finding.path for finding in report.findings] == [
        f"{_run_ref(EXAMPLE_CASE)}/analysis-2.json"
    ]


# --------------------------------------------------------------------------
# The analysis code
# --------------------------------------------------------------------------


def test_the_source_rows_are_the_python_files_of_the_registered_packages() -> None:
    rows = core.analysis_sources()
    paths = [row["path"] for row in rows]
    assert paths == sorted(paths)
    expected = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for package in core.SOURCE_PACKAGES
        for path in (REPO_ROOT / "tools" / package).rglob("*.py")
    )
    assert paths == expected
    assert "tools/analysis_replay/core.py" in paths
    assert "tools/reliability_analysis/core.py" in paths
    for row in rows:
        data = (REPO_ROOT / row["path"]).read_bytes()
        assert row["sha256"] == run_core.content_digest(data)


def test_the_source_digest_does_not_move_with_the_line_endings(tmp_path: Path) -> None:
    for name, newline in (("lf", b"\n"), ("crlf", b"\r\n")):
        for package in core.SOURCE_PACKAGES:
            target = tmp_path / name / "tools" / package / "core.py"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"VALUE = 1" + newline)
    assert core.analysis_sources(tmp_path / "lf") == core.analysis_sources(
        tmp_path / "crlf"
    )


def test_the_analysis_code_states_a_commit_and_the_digest_of_its_rows() -> None:
    code = core.analysis_code(REVISION)
    assert set(code) == {"revision", "sourceSha256", "sources"}
    assert code["revision"] == REVISION
    assert code["sourceSha256"] == index_core.evidence_set_sha256(code["sources"])
    for revision in ("main", "c" * 39, "C" * 40, ""):
        with pytest.raises(core.ReplayRefused) as refused:
            core.analysis_code(revision)
        assert refused.value.rule == core.RULE_UNCOMMITTED


def _tools_imports(path: Path) -> set[str]:
    """Each package under ``tools`` that a module imports by an absolute name."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            # ``from tools import x`` names the package in the imported name.
            modules = (
                [f"tools.{alias.name}" for alias in node.names]
                if module == "tools"
                else [module]
            )
        else:
            continue
        names.update(m.split(".")[1] for m in modules if m.startswith("tools."))
    return names


def test_the_source_packages_hold_the_analysis_and_each_reader_of_an_input() -> None:
    """Each package that a source file imports and the digest does not cover.

    The imports of each Python file of each source package are read. A package
    that those name and that is not a source package is outside the digest.
    The imports of those packages in turn are not read here.
    """
    imported = _tools_imports(REPO_ROOT / "tools" / "reliability_analysis" / "core.py")
    assert imported & set(core.SOURCE_PACKAGES) == {
        "experiment_events",
        "experiment_timeline",
        "reliability_runner",
        "service_endpoint_state",
    }
    # The reader of a caller record holds a header to the caller profile.
    runner = _tools_imports(REPO_ROOT / "tools" / "reliability_runner" / "core.py")
    assert "reliability_profile" in runner
    assert "reliability_profile" in core.SOURCE_PACKAGES
    outside: set[str] = set()
    for row in core.analysis_sources():
        outside |= _tools_imports(REPO_ROOT / row["path"])
    assert outside - set(core.SOURCE_PACKAGES) == {
        "evidence_index",
        "experiment_evidence",
        "experiment_freeze",
        "experiment_run",
        "llm_load",
        "model_acquisition",
        "runtime_configuration",
        "runtime_packaging",
    }
    text = PAGE.read_text(encoding="utf-8")
    for package in outside - set(core.SOURCE_PACKAGES):
        assert f"`tools/{package}`" in text, package


def test_a_source_file_is_a_file_whose_name_ends_with_py_in_lower_case(
    tmp_path: Path,
) -> None:
    package = tmp_path / "tools" / core.SOURCE_PACKAGES[0]
    package.mkdir(parents=True)
    (package / "core.py").write_bytes(b"VALUE = 1\n")
    (package / "Shadow.PY").write_bytes(b"VALUE = 2\n")
    (package / "notes.txt").write_bytes(b"not code\n")
    assert [row["path"] for row in core.analysis_sources(tmp_path)] == [
        f"tools/{core.SOURCE_PACKAGES[0]}/core.py"
    ]


def test_a_source_file_with_a_path_that_no_document_can_state_gives_no_code(
    tmp_path: Path,
) -> None:
    """The form of a source row has no hyphen. A replay would refuse the document."""
    package = tmp_path / "tools" / core.SOURCE_PACKAGES[0]
    package.mkdir(parents=True)
    (package / "core.py").write_bytes(b"VALUE = 1\n")
    assert core._code_problem(core.analysis_code(REVISION, tmp_path)) is None
    (package / "my-notes.py").write_bytes(b"VALUE = 2\n")
    with pytest.raises(core.ReplayRefused) as refused:
        core.analysis_code(REVISION, tmp_path)
    assert refused.value.rule == core.RULE_UNCOMMITTED


def _restate_code(document: dict[str, Any], rows: list[dict[str, str]]) -> None:
    document["analysisCode"]["sources"] = rows
    document["analysisCode"]["sourceSha256"] = index_core.evidence_set_sha256(rows)


def test_a_document_of_another_code_replays_and_states_the_difference(
    tmp_path: Path,
) -> None:
    """The figures are those that the present code gives. The source digest is not."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)

    def other_code(document: dict[str, Any]) -> None:
        rows = copy.deepcopy(document["analysisCode"]["sources"])
        rows[0]["sha256"] = "0" * 64
        _restate_code(document, rows)

    _rewrite(run_dir, other_code)
    report = core.replay_run(run_dir, tmp_path)
    assert report.status == core.REPLAYED
    (replayed,) = report.analyses
    assert replayed.code == core.CODE_DIFFERS
    assert replayed.changed_sources == ("tools/analysis_replay/__init__.py",)


def test_a_source_file_that_the_document_does_not_state_is_a_difference(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)

    def fewer(document: dict[str, Any]) -> None:
        _restate_code(document, document["analysisCode"]["sources"][1:])

    _rewrite(run_dir, fewer)
    (replayed,) = core.replay_run(run_dir, tmp_path).analyses
    assert replayed.changed_sources == ("tools/analysis_replay/__init__.py",)


def test_an_edited_figure_under_another_code_is_refused_and_says_so(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)

    def edit(document: dict[str, Any]) -> None:
        rows = copy.deepcopy(document["analysisCode"]["sources"])
        rows[0]["sha256"] = "0" * 64
        _restate_code(document, rows)
        _set_figure(document)

    _rewrite(run_dir, edit)
    report = core.replay_run(run_dir, tmp_path)
    assert _rules(report) == [core.RULE_DOCUMENT]
    assert "1 source file(s) differ" in _messages(report)


def _code_edits() -> dict[str, Callable[[dict[str, Any]], None]]:
    def extra(code: dict[str, Any]) -> None:
        code["builtBy"] = "a person"

    def short(code: dict[str, Any]) -> None:
        code["revision"] = "c" * 39

    def digest(code: dict[str, Any]) -> None:
        code["sourceSha256"] = "0" * 64

    def unordered(code: dict[str, Any]) -> None:
        code["sources"] = code["sources"][::-1]

    def repeated(code: dict[str, Any]) -> None:
        code["sources"] = [code["sources"][0], *code["sources"]]

    def outside(code: dict[str, Any]) -> None:
        code["sources"][0]["path"] = "src/module.py"

    def parent(code: dict[str, Any]) -> None:
        code["sources"][0]["path"] = "tools/../secret.py"

    def no_rows(code: dict[str, Any]) -> None:
        code["sources"] = []

    def row_member(code: dict[str, Any]) -> None:
        code["sources"][0]["note"] = "x"

    return {
        "another member": extra,
        "a short commit": short,
        "a digest that is not the rows'": digest,
        "rows out of order": unordered,
        "a path stated twice": repeated,
        "a path outside tools": outside,
        "a parent segment": parent,
        "no row": no_rows,
        "a row with another member": row_member,
    }


@pytest.mark.parametrize("name", sorted(_code_edits()))
def test_an_analysis_code_in_another_form_is_refused(tmp_path: Path, name: str) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    _rewrite(run_dir, lambda document: _code_edits()[name](document["analysisCode"]))
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_RECORD_FORM]


@pytest.mark.parametrize("value", [None, [], "window", 3])
def test_a_document_with_no_declaration_object_is_refused(
    tmp_path: Path, value: object
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    _rewrite(run_dir, lambda document: document.__setitem__("declaration", value))
    assert _rules(core.replay_run(run_dir, tmp_path)) == [core.RULE_RECORD_FORM]


def test_the_stated_commit_is_held_to_what_git_gives() -> None:
    rows = [
        {"path": "tools/a/core.py", "sha256": run_core.content_digest(b"A = 1\n")},
        {"path": "tools/b/core.py", "sha256": run_core.content_digest(b"B = 2\n")},
    ]
    code = {"revision": REVISION, "sourceSha256": "", "sources": rows}
    blobs: dict[str, bytes | None] = {
        "tools/a/core.py": b"A = 1\r\n",
        "tools/b/core.py": b"B = 2\n",
    }
    asked: list[str] = []

    def blob(revision: str, path: str) -> bytes | None:
        asked.append(revision)
        return blobs[path]

    held: dict[str, list[str] | None] = {
        "tools/a": ["tools/a/core.py", "tools/a/notes.txt"],
        "tools/b": ["tools/b/core.py"],
    }

    def tracked(revision: str, package: str) -> list[str] | None:
        asked.append(revision)
        return held[package]

    def state(present: bool = True) -> tuple[str, tuple[str, ...]]:
        return core.revision_state(code, lambda _: present, blob, tracked)

    assert state() == (core.REVISION_HELD, ())
    assert set(asked) == {REVISION}
    # A clone that does not hold the commit compares nothing.
    assert state(present=False) == (core.REVISION_NOT_CHECKED, ())
    # The commit holds a Python file of a stated package that no row states.
    held["tools/a"] = ["tools/a/core.py", "tools/a/extra.py"]
    assert state() == (core.CODE_DIFFERS, ("tools/a/extra.py",))
    # A directory that cannot be listed is not read as held.
    held["tools/a"] = None
    assert state() == (core.CODE_DIFFERS, ("tools/a",))
    held["tools/a"] = ["tools/a/core.py"]
    blobs["tools/a/core.py"] = b"A = 2\n"
    blobs["tools/b/core.py"] = None
    assert state() == (core.CODE_DIFFERS, ("tools/a/core.py", "tools/b/core.py"))


# --------------------------------------------------------------------------
# The aggregate of the runs of one experiment
# --------------------------------------------------------------------------

METRIC = "caller-failure-episode-ms"


def _runs(root: Path, states: dict[str, str]) -> list[Path]:
    return [_bound_run(root, case, state) for case, state in states.items()]


def _figure(case: str) -> int | None:
    document = _read_json(CASES / case / "analysis.json")
    value = document["caller"]["failureEpisodes"]["callerFailureEpisodeMs"]
    assert value is None or type(value) is int
    return value


THREE = {"zero-failure": "PASSED", "concurrency": "FAILED", "missing-signal": "FAILED"}


def test_the_aggregate_is_the_median_of_three_counted_runs(tmp_path: Path) -> None:
    _preregister(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    document = _aggregate(runs, tmp_path)
    values = sorted(_figure(case) or 0 for case in THREE)
    assert all(_figure(case) is not None for case in THREE)
    figures = document["aggregate"]
    assert (figures["rule"], figures["countedRuns"], figures["median"]) == (
        "median-of-three",
        3,
        values[1],
    )
    listed = {row["runId"]: row for row in figures["runs"]}
    assert len(listed) == 4
    # The state of each run is the one of its manifest.
    assert {run: row["resultState"] for run, row in listed.items()} == {
        "zero-failure-1": "PASSED",
        "concurrency-1": "FAILED",
        "missing-signal-1": "FAILED",
        "abort-1": "ABORTED",
    }
    assert listed["abort-1"]["counted"] is False
    assert listed["abort-1"]["exclusion"] == {
        "reasonId": "fixture-aborted",
        "reason": REASON,
        "preregistration": _read_at(tmp_path),
    }
    assert document["schema"] == core.AGGREGATE_SCHEMA
    assert document["runsDirectory"] == f"{EXPERIMENT_REF}/runs"
    assert document["rules"] == list(core.AGGREGATE_RULES)
    assert document["analysisCode"] == core.analysis_code(REVISION)


def test_an_aggregate_states_the_digests_of_each_run(tmp_path: Path) -> None:
    runs = _runs(tmp_path, THREE)
    document = _aggregate(runs, tmp_path)
    assert [row["runId"] for row in document["runs"]] == sorted(
        _run_id(case) for case in THREE
    )
    for row in document["runs"]:
        run_dir = tmp_path / row["runDirectory"]
        assert row["manifestSha256"] == file_digest(run_dir / run_core.MANIFEST_NAME)
        code = _stored(run_dir)["analysisCode"]
        assert row["runAnalysis"] == {
            "path": ANALYSIS_FILE,
            "sha256": file_digest(run_dir / ANALYSIS_FILE),
            "revision": code["revision"],
            "sourceSha256": code["sourceSha256"],
            "code": core.CODE_SAME,
        }
        assert row["rawEvidenceSha256"] == _stored(run_dir)["rawEvidence"]["sha256"]


def test_the_run_with_the_worst_figure_is_counted(tmp_path: Path) -> None:
    """A FAILED run with the largest figure is a counted run, with its value."""
    states = {"zero-failure": "PASSED", "clock-ties": "FAILED", "concurrency": "FAILED"}
    figures = _aggregate(_runs(tmp_path, states), tmp_path)["aggregate"]
    listed = {row["runId"]: row for row in figures["runs"]}
    assert [listed[_run_id(case)]["value"] for case in states] == [0, 3000, 20900]
    assert all(row["counted"] for row in listed.values())
    assert (figures["countedRuns"], figures["median"]) == (3, 3000)


def test_a_run_of_the_experiment_that_is_not_given_is_a_refusal(tmp_path: Path) -> None:
    runs = _runs(tmp_path, THREE | {"open-episode": "FAILED"})
    with pytest.raises(core.ReplayRefused) as refused:
        _aggregate(runs[:3], tmp_path)
    assert refused.value.rule == core.RULE_AGGREGATE_OMITTED
    assert "open-episode-1" in refused.value.message


def test_a_counted_run_with_no_value_leaves_no_median(tmp_path: Path) -> None:
    """An open episode has no duration. The run is counted, and it is not dropped."""
    assert _figure("open-episode") is None
    states = {
        "zero-failure": "PASSED",
        "concurrency": "FAILED",
        "open-episode": "FAILED",
    }
    figures = _aggregate(_runs(tmp_path, states), tmp_path)["aggregate"]
    assert (figures["countedRuns"], figures["median"], figures["reason"]) == (
        3,
        None,
        "counted-run-without-value",
    )


def test_a_counted_run_with_no_run_analysis_leaves_no_median(tmp_path: Path) -> None:
    runs = _runs(tmp_path, {"zero-failure": "PASSED", "concurrency": "FAILED"})
    runs.append(_raw_run(tmp_path, "missing-signal", "FAILED"))
    document = _aggregate(runs, tmp_path)
    assert document["aggregate"]["reason"] == "counted-run-without-value"
    assert document["aggregate"]["median"] is None
    bare = next(r for r in document["runs"] if r["runId"] == "missing-signal-1")
    assert bare["runAnalysis"] is None


def test_two_counted_runs_have_no_median(tmp_path: Path) -> None:
    _preregister(tmp_path)
    states = {"zero-failure": "PASSED", "concurrency": "FAILED", "abort": "ABORTED"}
    figures = _aggregate(_runs(tmp_path, states), tmp_path)["aggregate"]
    assert (figures["countedRuns"], figures["median"], figures["reason"]) == (
        2,
        None,
        "not-three-counted-runs",
    )


def test_a_run_whose_analysis_does_not_replay_refuses_the_aggregate(
    tmp_path: Path,
) -> None:
    runs = _runs(tmp_path, THREE)
    _rewrite(runs[1], _set_figure)
    with pytest.raises(core.ReplayRefused) as refused:
        _aggregate(runs, tmp_path)
    assert refused.value.rule == core.RULE_AGGREGATE_RUN
    assert core.RULE_DOCUMENT in refused.value.message


def test_a_directory_beside_the_runs_with_no_valid_manifest_is_a_refusal(
    tmp_path: Path,
) -> None:
    runs = _runs(tmp_path, THREE)
    (runs[0].parent / "scratch").mkdir()
    with pytest.raises(core.ReplayRefused) as refused:
        _aggregate(runs, tmp_path)
    assert refused.value.rule == core.RULE_AGGREGATE_OMITTED


def test_a_run_is_not_left_out_by_another_spelling_of_an_argument(
    tmp_path: Path,
) -> None:
    """The runs directory is read at its place, and not beside the last argument.

    The first commit listed the parent of the last path as it was written. A
    path through a directory of the run then listed that run, and a fourth run
    of the experiment was left out with no refusal.
    """
    runs = _runs(tmp_path, THREE | {"open-episode": "FAILED"})
    (runs[2] / "logs").mkdir()
    assert check_run(runs[2], tmp_path).status == run_core.CONFORMING
    spelled = runs[2] / "logs" / ".."
    with pytest.raises(core.ReplayRefused) as refused:
        _aggregate([runs[0], runs[1], spelled], tmp_path)
    assert refused.value.rule == core.RULE_AGGREGATE_OMITTED
    assert "open-episode-1" in refused.value.message
    # With each run given, the other spelling gives the document of the plain one.
    plain = _aggregate(runs, tmp_path)
    assert _aggregate([*runs[:2], spelled, runs[3]], tmp_path) == plain
    for missing in (runs[2] / "caller.jsonl" / "..", runs[2] / "absent" / ".."):
        with pytest.raises(core.ReplayRefused):
            _aggregate([runs[0], runs[1], missing], tmp_path)


def test_a_run_is_not_left_out_by_another_experiment_in_its_manifest_alone(
    tmp_path: Path,
) -> None:
    """The first commit read the experiment of a run that was not given from a
    manifest that validates. The manifest of the worst run, with another
    experiment and no other change, was then passed as a run of that experiment.
    The layout check refuses it: its caller record names the first experiment.
    """
    runs = _runs(tmp_path, THREE | {"open-episode": "FAILED"})
    manifest = _read_json(runs[3] / run_core.MANIFEST_NAME)
    manifest["metadata"]["experimentId"] = "another-experiment"
    _write_json(runs[3] / run_core.MANIFEST_NAME, manifest)
    assert not run_core.validate(manifest)
    assert check_run(runs[3], tmp_path).status == core.REFUSED
    with pytest.raises(core.ReplayRefused) as refused:
        _aggregate(runs[:3], tmp_path)
    assert refused.value.rule == core.RULE_AGGREGATE_OMITTED
    assert "does not conform" in refused.value.message


def test_an_aggregate_states_the_code_of_each_run_analysis(tmp_path: Path) -> None:
    """The aggregate compares no commit with Git. It states what each run states."""
    runs = _runs(tmp_path, THREE)

    def other_code(document: dict[str, Any]) -> None:
        rows = copy.deepcopy(document["analysisCode"]["sources"])
        rows[0]["sha256"] = "0" * 64
        _restate_code(document, rows)
        document["analysisCode"]["revision"] = "d" * 40

    _rewrite(runs[0], other_code)
    document = _aggregate(runs, tmp_path)
    listed = {row["runId"]: row["runAnalysis"] for row in document["runs"]}
    changed = listed[runs[0].name]
    assert (changed["code"], changed["revision"]) == (core.CODE_DIFFERS, "d" * 40)
    assert changed["sourceSha256"] != document["analysisCode"]["sourceSha256"]
    assert {listed[run.name]["code"] for run in runs[1:]} == {core.CODE_SAME}
    assert document["analysisCode"]["revision"] == REVISION


def test_a_run_of_another_experiment_beside_the_runs_is_not_required(
    tmp_path: Path,
) -> None:
    runs = _runs(tmp_path, THREE)
    other = runs[0].parent / "other-1"
    other.mkdir()
    _write_json(
        other / run_core.MANIFEST_NAME,
        _manifest(tmp_path, "other-1", [], "INCONCLUSIVE", "another-experiment"),
    )
    assert check_run(other, tmp_path).status == run_core.CONFORMING
    document = _aggregate(runs, tmp_path)
    assert len(document["runs"]) == 3
    with pytest.raises(core.ReplayRefused) as refused:
        _aggregate([*runs, other], tmp_path)
    assert refused.value.rule == core.RULE_AGGREGATE


def test_an_aggregate_refuses_what_it_cannot_read(tmp_path: Path) -> None:
    runs = _runs(tmp_path, THREE)
    for metric, given in (
        ("availability-percent", runs),
        (METRIC, []),
        (METRIC, [*runs, runs[0]]),
    ):
        with pytest.raises(core.ReplayRefused) as refused:
            core.aggregate_runs(metric, given, REVISION, tmp_path)
        assert refused.value.rule == core.RULE_AGGREGATE
    _store(runs[2], (runs[2] / ANALYSIS_FILE).read_text("utf-8"), "analysis-2.json")
    with pytest.raises(core.ReplayRefused) as refused:
        _aggregate(runs, tmp_path)
    assert refused.value.rule == core.RULE_AGGREGATE


# --------------------------------------------------------------------------
# A run that is not counted, and the reason that a freeze record registers
# --------------------------------------------------------------------------


def _reasons(experiment: str = EXPERIMENT) -> dict[str, Any]:
    """Synthetic exclusion reasons. They are the reasons of no experiment."""
    return {
        "experimentId": experiment,
        "reasons": [
            {
                "id": "fixture-inconclusive",
                "resultState": "INCONCLUSIVE",
                "reason": REASON,
            },
            {"id": "fixture-refused", "resultState": "REFUSED", "reason": REASON},
            {"id": "fixture-aborted", "resultState": "ABORTED", "reason": REASON},
            {"id": "fixture-abort-2", "resultState": "ABORTED", "reason": OTHER_REASON},
        ],
    }


def _freeze(reasons: dict[str, Any] | None, revision: int = 1) -> str:
    record: dict[str, Any] = {
        "metadata": {"revision": revision},
        "synthetic": "A fixture. It freezes no experiment.",
    }
    if reasons is not None:
        record[core.EXCLUSION_REASONS_MEMBER] = reasons
    return json.dumps(record, indent=2) + "\n"


def _pin(root: Path, *refs: str) -> None:
    """Write a freeze registry that pins each given record as it is now."""
    _write_json(
        root / REGISTRY_PATH,
        {
            "apiVersion": "inferops.io/v1alpha1",
            "kind": "ExperimentFreezeRegistry",
            "records": [
                {
                    "path": ref,
                    "contentSha256": run_core.content_digest((root / ref).read_bytes()),
                }
                for ref in refs
            ],
        },
    )
    assert set(load_registry(root)) == set(refs)


def _preregister(root: Path, reasons: dict[str, Any] | None = None) -> str:
    """Before a run is built: a freeze record with exclusion reasons, and its pin.

    The two files are committed to a clone of the tree. Each run that is then
    built states that commit as its executing revision.
    """
    assert not (root / EXPERIMENT_REF / "runs").exists()
    _write(root / FREEZE_REF, _freeze(_reasons() if reasons is None else reasons))
    _pin(root, FREEZE_REF)
    return _commit(root)


def _spec(root: Path, ref: str = FREEZE_REF, revision: int = 1) -> dict[str, Any]:
    return {
        "freezeRecord": ref,
        "freezeRevision": revision,
        "freezeContentSha256": run_core.content_digest((root / ref).read_bytes()),
    }


def _read_at(root: Path, ref: str = FREEZE_REF, revision: int = 1) -> dict[str, Any]:
    """How a row names the record of a run that is not counted."""
    return _spec(root, ref, revision) | {"executingRevision": HEADS[root]}


def _restate_manifest(run_dir: Path, change: Callable[[dict[str, Any]], None]) -> None:
    """Change the manifest of a run by hand, and no other file."""
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    change(manifest)
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)


def _executed(run_dir: Path, revision: str) -> None:
    """Restate the executing revision of one manifest, and no other member."""
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    manifest["metadata"]["executingRevision"] = revision
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)


def _set_result(run_dir: Path, state: str, reason: str | None = None) -> None:
    result = {"state": state} if reason is None else {"state": state, "reason": reason}
    _restate_manifest(run_dir, lambda manifest: manifest.update(result=result))


def _other_files(run_dir: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(run_dir.iterdir())
        if path.name != run_core.MANIFEST_NAME
    }


def _aggregate(runs: list[Path], root: Path) -> dict[str, Any]:
    """The aggregate, with the reader of commits that the command gives it."""
    return core.aggregate_runs(METRIC, runs, REVISION, root, command.history(root))


def _refusal(runs: list[Path], root: Path) -> core.ReplayRefused:
    with pytest.raises(core.ReplayRefused) as refused:
        _aggregate(runs, root)
    return refused.value


FOUR = THREE | {"open-episode": "FAILED"}


@pytest.mark.parametrize("preregistered", [False, True])
def test_a_run_is_not_left_out_for_a_reason_that_no_record_registers(
    tmp_path: Path, preregistered: bool
) -> None:
    """The probe that showed the defect, step for step.

    Three runs have a figure, and a fourth, FAILED, has an open episode. The
    aggregate counts four runs and states no median. Then the manifest of the
    fourth run alone is changed to INCONCLUSIVE, with a reason that was written
    after the run. No other byte changes, and the run still replays.

    Before this change the aggregate then counted three runs and stated a
    median of 20,900 ms, and the reason was nowhere in the document. Now the
    aggregate is refused: with no registry, and with a registered record that
    does not hold the reason.
    """
    if preregistered:
        _preregister(tmp_path)
    runs = _runs(tmp_path, FOUR)
    before = _aggregate(runs, tmp_path)["aggregate"]
    assert (before["countedRuns"], before["state"], before["median"]) == (
        4,
        analysis.NOT_COMPUTABLE,
        None,
    )
    changed = runs[-1]
    others = _other_files(changed)
    _set_result(changed, "INCONCLUSIVE", POST_HOC_REASON)
    assert _other_files(changed) == others
    assert core.replay_run(changed, tmp_path).status == core.REPLAYED
    refused = _refusal(runs, tmp_path)
    if preregistered:
        assert refused.rule == core.RULE_EXCLUSION
        assert "analysis-exclusion-unregistered" in refused.message
    else:
        assert refused.rule == core.RULE_EXCLUSION_RECORD
    assert "open-episode-1" in refused.message
    assert POST_HOC_REASON not in str(refused)
    # The three finite runs alone have the median that the probe obtained. No
    # document states it while the fourth run is in the runs directory.
    assert sorted(_figure(case) or 0 for case in THREE)[1] == 20_900


@pytest.mark.parametrize("state", list(analysis.EXCLUDED_STATES))
def test_a_registered_reason_leaves_a_run_out_and_is_stated(
    tmp_path: Path, state: str
) -> None:
    _preregister(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": state})
    document = _aggregate(runs, tmp_path)
    figures = document["aggregate"]
    assert (figures["countedRuns"], figures["state"], figures["median"]) == (
        3,
        analysis.COMPUTED,
        sorted(_figure(case) or 0 for case in THREE)[1],
    )
    row = next(r for r in figures["runs"] if r["runId"] == "abort-1")
    assert row == {
        "runId": "abort-1",
        "resultState": state,
        "counted": False,
        "exclusion": {
            "reasonId": f"fixture-{state.lower()}",
            "reason": REASON,
            "preregistration": _read_at(tmp_path),
        },
        "value": _figure("abort"),
    }
    # Each run states the freeze record that its manifest names, and the
    # commit that its manifest states as its executing revision.
    assert [r["preregistration"] for r in document["runs"]] == [_spec(tmp_path)] * 4
    assert {r["executingRevision"] for r in document["runs"]} == {HEADS[tmp_path]}
    assert document["schema"] == "inferops.io/run-aggregate/v1alpha2"


def test_an_excluded_run_needs_a_registry_that_pins_its_freeze_record(
    tmp_path: Path,
) -> None:
    """A file that a manifest names is a frozen record only when it is pinned.

    The executing revision holds the record and no registry. A registry that
    is written afterwards pins the record in the tree, and not at that commit.
    """
    _write(tmp_path / FREEZE_REF, _freeze(_reasons()))
    _commit(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_RECORD
    _write(tmp_path / REGISTRY_PATH, "not a registry\n")
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_RECORD
    _pin(tmp_path)
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_RECORD
    _pin(tmp_path, FREEZE_REF)
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_HISTORY
    assert "freeze registry of its executing revision" in refused.message
    # A registry is not read for runs that are all counted.
    (tmp_path / REGISTRY_PATH).unlink()
    _set_result(runs[-1], "FAILED")
    assert _aggregate(runs, tmp_path)["aggregate"]["countedRuns"] == 4


@pytest.mark.parametrize(
    "reasons",
    [
        None,
        {"experimentId": EXPERIMENT, "reasons": []},
        {
            "experimentId": EXPERIMENT,
            "reasons": [
                {"id": "another", "resultState": "ABORTED", "reason": OTHER_REASON}
            ],
        },
    ],
)
def test_a_record_that_does_not_register_the_reason_refuses_the_aggregate(
    tmp_path: Path, reasons: dict[str, Any] | None
) -> None:
    _write(tmp_path / FREEZE_REF, _freeze(reasons))
    _pin(tmp_path, FREEZE_REF)
    _commit(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION
    assert "analysis-exclusion-unregistered" in refused.message


@pytest.mark.parametrize(
    "reason", [REASON + " ", REASON.lower(), REASON[:-1], REASON + " And more."]
)
def test_a_reason_that_differs_by_a_character_refuses_the_aggregate(
    tmp_path: Path, reason: str
) -> None:
    _preregister(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    _set_result(runs[-1], "ABORTED", reason)
    assert check_run(runs[-1], tmp_path).status == run_core.CONFORMING
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION
    assert "analysis-exclusion-unregistered" in refused.message


def test_a_run_that_is_not_counted_and_states_no_reason_does_not_conform(
    tmp_path: Path,
) -> None:
    """The manifest schema requires the reason, so the layout check refuses first."""
    _preregister(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    _set_result(runs[-1], "ABORTED")
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_AGGREGATE_RUN


def test_a_reason_of_another_result_state_refuses_the_aggregate(tmp_path: Path) -> None:
    _preregister(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    _set_result(runs[-1], "INCONCLUSIVE", OTHER_REASON)
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION
    assert "another result state" in refused.message


def test_a_reason_of_another_experiment_refuses_the_aggregate(tmp_path: Path) -> None:
    """A freeze record of another experiment, put beside the runs and pinned."""
    _preregister(tmp_path, _reasons("another-experiment"))
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION
    assert "another experiment" in refused.message


def test_a_reason_of_another_run_refuses_the_aggregate(tmp_path: Path) -> None:
    reasons = _reasons()
    reasons["reasons"][2]["runIds"] = ["clock-ties-1"]
    _preregister(tmp_path, reasons)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION
    assert "other runs" in refused.message


def test_a_reason_of_a_named_run_leaves_that_run_out(tmp_path: Path) -> None:
    reasons = _reasons()
    reasons["reasons"][2]["runIds"] = ["abort-1"]
    _preregister(tmp_path, reasons)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    figures = _aggregate(runs, tmp_path)["aggregate"]
    assert figures["countedRuns"] == 3


def _answer(root: Path, runs: list[Path], ref: str, revision: int) -> None:
    """Restate the freeze record that each given manifest names."""
    for run in runs:
        _restate_manifest(
            run,
            lambda manifest: manifest["metadata"].update(
                spec=_spec(root, ref, revision)
            ),
        )
        assert check_run(run, root).status == run_core.CONFORMING


SECOND_REF = f"{EXPERIMENT_REF}/freeze-r2.v1alpha1.json"


def _two_revisions(root: Path) -> list[Path]:
    """Revision 1 registers both reasons, and revision 2 does not register REASON."""
    _write(root / FREEZE_REF, _freeze(_reasons()))
    narrowed = _reasons()
    narrowed["reasons"] = [r for r in narrowed["reasons"] if r["reason"] != REASON]
    _write(root / SECOND_REF, _freeze(narrowed, revision=2))
    _pin(root, FREEZE_REF, SECOND_REF)
    _commit(root)
    return _runs(root, THREE | {"abort": "ABORTED"})


def test_a_reason_that_only_an_earlier_revision_registers_is_refused(
    tmp_path: Path,
) -> None:
    """Each run answers revision 2, which does not register the reason.

    The reason of revision 1 is stale for a run that answers revision 2.
    """
    runs = _two_revisions(tmp_path)
    # Under revision 1 the reason is registered.
    assert _aggregate(runs, tmp_path)["aggregate"]["median"]
    _answer(tmp_path, runs, SECOND_REF, 2)
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION
    assert "analysis-exclusion-unregistered" in refused.message
    # The other reason is registered by revision 2, and the row names revision 2.
    _set_result(runs[-1], "ABORTED", OTHER_REASON)
    figures = _aggregate(runs, tmp_path)["aggregate"]
    row = next(r for r in figures["runs"] if r["runId"] == "abort-1")
    assert row["exclusion"]["preregistration"] == _read_at(tmp_path, SECOND_REF, 2)
    assert row["exclusion"]["reasonId"] == "fixture-abort-2"


def test_a_run_does_not_go_back_to_an_earlier_revision_for_its_reason(
    tmp_path: Path,
) -> None:
    """One manifest alone is restated to revision 1, which registers the reason.

    The first commit held each run to the record of its own manifest. So this
    one edit gave a median again. Each run of an aggregate that leaves a run
    out must now name one record.
    """
    runs = _two_revisions(tmp_path)
    _answer(tmp_path, runs, SECOND_REF, 2)
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION
    _answer(tmp_path, runs[-1:], FREEZE_REF, 1)
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_RECORDS
    # Runs of two revisions that are all counted are aggregated as before.
    _set_result(runs[-1], "FAILED")
    assert _aggregate(runs, tmp_path)["aggregate"]["countedRuns"] == 4


def test_a_record_that_is_written_after_the_runs_gives_one_run_no_reason(
    tmp_path: Path,
) -> None:
    """A new record with the reason of the probe, added to the registry.

    No pin of the registry is changed, and one manifest alone names the new
    record. The first commit gave a median of 20,900 ms for this.
    """
    _preregister(tmp_path)
    runs = _runs(tmp_path, FOUR)
    reasons = _reasons()
    reasons["reasons"] = [
        {"id": "added-later", "resultState": "INCONCLUSIVE", "reason": POST_HOC_REASON}
    ]
    _write(tmp_path / SECOND_REF, _freeze(reasons, revision=2))
    _pin(tmp_path, FREEZE_REF, SECOND_REF)
    _set_result(runs[-1], "INCONCLUSIVE", POST_HOC_REASON)
    _answer(tmp_path, runs[-1:], SECOND_REF, 2)
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_RECORDS
    assert POST_HOC_REASON not in str(refused)


@pytest.mark.parametrize(
    ("name", "revision"),
    [
        ("notes.json", 7),
        ("freeze-r1-exclusions.json", 1),
        ("freeze-r2.v1alpha1.json", 1),
    ],
)
def test_a_file_without_the_name_of_its_revision_registers_no_reason(
    tmp_path: Path, name: str, revision: int
) -> None:
    """Each manifest names the file, and the registry pins it."""
    ref = f"{EXPERIMENT_REF}/{name}"
    _write(tmp_path / FREEZE_REF, FREEZE_TEXT)
    _write(tmp_path / ref, _freeze(_reasons(), revision=revision))
    _pin(tmp_path, FREEZE_REF, ref)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    _answer(tmp_path, runs, ref, revision)
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_RECORDS
    assert "name of its revision" in refused.message


_PIN = '"records": [{{"path": "{path}", "contentSha256": "{digest}"}}]'
_HEAD = '"apiVersion": "inferops.io/v1alpha1"'
REGISTRIES = {
    "records twice": (
        f'{{{{{_HEAD}, "kind": "ExperimentFreezeRegistry", "records": [], {_PIN}}}}}'
    ),
    "kind twice": (
        f'{{{{{_HEAD}, "kind": "Another", "kind": "ExperimentFreezeRegistry", {_PIN}}}}}'
    ),
    "path twice": (
        f'{{{{{_HEAD}, "kind": "ExperimentFreezeRegistry", "records": '
        '[{{"path": "another", "path": "{path}", "contentSha256": "{digest}"}}]}}'
    ),
    "nested arrays": "[" * 100_000,
    "nested objects": '{{"a":' * 100_000,
}


@pytest.mark.parametrize("name", sorted(REGISTRIES))
def test_a_registry_that_two_readers_could_read_in_two_ways_is_refused(
    tmp_path: Path, name: str
) -> None:
    """A member stated twice, and a nesting that no reader finishes.

    The reader of the registry keeps the last of two members. The first commit
    accepted each registry with a member twice, and the two nestings left the
    tool with an error that is no refusal.
    """
    _preregister(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    assert _aggregate(runs, tmp_path)["aggregate"]["median"]
    spec = _spec(tmp_path)
    registry = REGISTRIES[name].format(
        path=spec["freezeRecord"], digest=spec["freezeContentSha256"]
    )
    if "twice" in name:
        # The reader of the registry accepts it, and gives the pin.
        _write(tmp_path / REGISTRY_PATH, registry)
        assert load_registry(tmp_path) == {
            spec["freezeRecord"]: spec["freezeContentSha256"]
        }
    _write(tmp_path / REGISTRY_PATH, registry)
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_RECORD


def _add_post_hoc_reason(root: Path) -> None:
    reasons = _reasons()
    reasons["reasons"].append(
        {"id": "added-later", "resultState": "INCONCLUSIVE", "reason": POST_HOC_REASON}
    )
    _write(root / FREEZE_REF, _freeze(reasons))


def _restate_freeze_digest(root: Path, runs: list[Path]) -> None:
    for run in runs:
        _restate_manifest(
            run, lambda manifest: manifest["metadata"].update(spec=_spec(root))
        )


def test_a_reason_that_is_added_to_the_record_is_refused_while_its_pin_is_kept(
    tmp_path: Path,
) -> None:
    """The probe, with the reason written into the freeze record afterwards.

    The record alone: the layout check refuses each run, because the record no
    longer has the digest that the manifests state. The record with each
    manifest restated: the registry does not pin the new content. The record,
    each manifest, and the registry, replaced together, agree in the tree. The
    second commit of this change accepted them, and stated a median of
    20,900 ms. They are now refused: the executing revision of the run holds
    the record with its earlier content.
    """
    _preregister(tmp_path)
    runs = _runs(tmp_path, FOUR)
    _set_result(runs[-1], "INCONCLUSIVE", POST_HOC_REASON)
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION

    _add_post_hoc_reason(tmp_path)
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_AGGREGATE_RUN
    assert {
        finding.rule for run in runs for finding in check_run(run, tmp_path).findings
    } == {"evidence-freeze-record-differs"}

    _restate_freeze_digest(tmp_path, runs)
    assert all(check_run(run, tmp_path).status == run_core.CONFORMING for run in runs)
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_RECORD
    assert "does not pin" in refused.message

    _pin(tmp_path, FREEZE_REF)
    assert all(check_run(run, tmp_path).status == run_core.CONFORMING for run in runs)
    assert load_registry(tmp_path) == {
        FREEZE_REF: _spec(tmp_path)["freezeContentSha256"]
    }
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_HISTORY
    assert "does not hold its freeze record" in refused.message
    assert POST_HOC_REASON not in str(refused)


def test_a_failed_run_with_a_registered_reason_is_counted(tmp_path: Path) -> None:
    """A reason beside a counted state leaves no run out.

    The worst run states FAILED and a reason that the record registers. It is
    counted with its value, and no record is read for it.
    """
    _preregister(tmp_path)
    states = {"zero-failure": "PASSED", "clock-ties": "FAILED", "concurrency": "FAILED"}
    runs = _runs(tmp_path, states)
    _set_result(runs[-1], "FAILED", REASON)
    (tmp_path / REGISTRY_PATH).unlink()
    figures = _aggregate(runs, tmp_path)["aggregate"]
    row = next(r for r in figures["runs"] if r["runId"] == "concurrency-1")
    assert (row["counted"], row["exclusion"], row["value"]) == (True, None, 20_900)
    assert (figures["countedRuns"], figures["median"]) == (3, 3000)


def test_a_counted_run_with_no_value_is_not_hidden_by_an_exclusion(
    tmp_path: Path,
) -> None:
    _preregister(tmp_path)
    states = {
        "zero-failure": "PASSED",
        "concurrency": "FAILED",
        "open-episode": "FAILED",
        "abort": "ABORTED",
    }
    figures = _aggregate(_runs(tmp_path, states), tmp_path)["aggregate"]
    assert (figures["countedRuns"], figures["median"], figures["reason"]) == (
        3,
        None,
        "counted-run-without-value",
    )


def test_a_substituted_reason_does_not_give_the_earlier_aggregate(
    tmp_path: Path,
) -> None:
    """One registered reason, replaced by another registered reason.

    The aggregate is accepted, because the record registers both. The document
    is not the earlier one: it states the other reason, its identifier, and
    another manifest digest. So a stored copy that is compared with the
    command's output shows the substitution.
    """
    _preregister(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    earlier = _aggregate(runs, tmp_path)
    stored = core.record_text(earlier)
    _set_result(runs[-1], "ABORTED", OTHER_REASON)
    later = _aggregate(runs, tmp_path)
    assert core.record_text(later) != stored
    was = next(r for r in earlier["aggregate"]["runs"] if not r["counted"])
    now = next(r for r in later["aggregate"]["runs"] if not r["counted"])
    assert (was["exclusion"]["reasonId"], now["exclusion"]["reasonId"]) == (
        "fixture-aborted",
        "fixture-abort-2",
    )
    assert now["exclusion"]["reason"] == OTHER_REASON
    digests = [
        {row["runId"]: row["manifestSha256"] for row in document["runs"]}
        for document in (earlier, later)
    ]
    assert digests[0]["abort-1"] != digests[1]["abort-1"]
    assert {k: v for k, v in digests[0].items() if k != "abort-1"} == {
        k: v for k, v in digests[1].items() if k != "abort-1"
    }
    # A stored copy whose reason was edited by hand is not the output either.
    edited = json.loads(stored)
    row = next(r for r in edited["aggregate"]["runs"] if not r["counted"])
    row["exclusion"]["reason"] = OTHER_REASON
    assert core.record_text(edited) not in (stored, core.record_text(later))


@pytest.mark.parametrize(
    "change",
    [
        lambda reasons: reasons.update(note="another member"),
        lambda reasons: reasons["reasons"][0].update(resultState="FAILED"),
        lambda reasons: reasons["reasons"].append(dict(reasons["reasons"][0])),
        lambda reasons: reasons.update(reasons="text"),
    ],
)
def test_exclusion_reasons_in_another_form_refuse_the_aggregate(
    tmp_path: Path, change: Callable[[dict[str, Any]], None]
) -> None:
    reasons = _reasons()
    change(reasons)
    _preregister(tmp_path, reasons)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION
    assert "analysis-exclusion-reasons-unsupported" in refused.message


def test_a_refusal_of_an_exclusion_repeats_no_text_of_a_file(tmp_path: Path) -> None:
    marker = "MARKER-51c9"
    reasons = _reasons()
    reasons["reasons"][3]["reason"] = f"A registered reason with {marker}."
    _preregister(tmp_path, reasons)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    # A stated reason that is not registered.
    _set_result(runs[-1], "ABORTED", f"A stated reason with {marker}.")
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION and marker not in str(refused)
    # A registered reason, stated under another result state.
    _set_result(runs[-1], "INCONCLUSIVE", f"A registered reason with {marker}.")
    refused = _refusal(runs, tmp_path)
    assert "another result state" in refused.message and marker not in str(refused)
    (tmp_path / REGISTRY_PATH).unlink()
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_RECORD and marker not in str(refused)


def test_a_run_that_was_left_out_is_stated_before_a_reason_is(tmp_path: Path) -> None:
    """The all-run rule is held first, so no reason hides a run that is not given."""
    runs = _runs(tmp_path, FOUR)
    _set_result(runs[0], "INCONCLUSIVE", POST_HOC_REASON)
    assert _refusal(runs[:3], tmp_path).rule == core.RULE_AGGREGATE_OMITTED


def test_the_aggregate_command_refuses_an_unregistered_exclusion(
    tmp_path: Path, no_git: None, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    _preregister(tmp_path)
    runs = _runs(tmp_path, FOUR)
    arguments = ["aggregate", "--metric", METRIC, "--root", str(tmp_path)]
    arguments += [str(run) for run in runs]
    assert command.main(arguments) == 0
    capfdbinary.readouterr()
    _set_result(runs[-1], "INCONCLUSIVE", POST_HOC_REASON)
    assert command.main(arguments) == 3
    captured = capfdbinary.readouterr()
    assert captured.out == b""
    assert captured.err.startswith(f"REFUSED  {core.RULE_EXCLUSION}: ".encode())
    assert POST_HOC_REASON.encode() not in captured.err


# --------------------------------------------------------------------------
# The freeze record at the executing revision of a run
# --------------------------------------------------------------------------
# Each test here makes a clone in its temporary tree, and each commit is a real
# commit of that clone. The reader of commits is the one of the command.


def _register_post_hoc(root: Path, runs: list[Path], *, in_place: bool) -> None:
    """After the runs: register the reason of the probe, and make the tree agree.

    In place, the reason is written into the record that each manifest names.
    Otherwise it is written into a new record of revision 2. Each manifest is
    restated to the record, and the registry is written again. No manifest is
    given another executing revision.
    """
    if in_place:
        _add_post_hoc_reason(root)
        _restate_freeze_digest(root, runs)
        _pin(root, FREEZE_REF)
    else:
        reasons = _reasons()
        reasons["reasons"].append(
            {
                "id": "added-later",
                "resultState": "INCONCLUSIVE",
                "reason": POST_HOC_REASON,
            }
        )
        _write(root / SECOND_REF, _freeze(reasons, revision=2))
        _pin(root, FREEZE_REF, SECOND_REF)
        _answer(root, runs, SECOND_REF, 2)
    assert all(check_run(run, root).status == run_core.CONFORMING for run in runs)
    specs = [
        _read_json(run / run_core.MANIFEST_NAME)["metadata"]["spec"] for run in runs
    ]
    assert all(spec == specs[0] for spec in specs)


def test_a_reason_that_the_executing_revision_registers_leaves_the_run_out(
    tmp_path: Path,
) -> None:
    """Commit A holds the record with the reason, and a registry that pins it.

    A run that states A as its executing revision, and that reason, is not
    counted. The row states the reason, its identifier, the record, and A. A
    later commit of the clone changes nothing.
    """
    first = _preregister(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    reader = command.history(tmp_path)
    assert reader.commit_present(first)
    held = reader.blob(first, FREEZE_REF)
    assert held is not None
    assert run_core.content_digest(held) == _spec(tmp_path)["freezeContentSha256"]
    assert json.loads(held)[core.EXCLUSION_REASONS_MEMBER] == _reasons()
    pinned = reader.blob(first, REGISTRY_PATH)
    assert pinned is not None
    assert core._registry_pins(pinned) == {FREEZE_REF: run_core.content_digest(held)}
    document = _aggregate(runs, tmp_path)
    figures = document["aggregate"]
    assert (figures["countedRuns"], figures["median"]) == (3, 20_900)
    row = next(r for r in figures["runs"] if not r["counted"])
    assert row["exclusion"] == {
        "reasonId": "fixture-aborted",
        "reason": REASON,
        "preregistration": {
            "freezeRecord": FREEZE_REF,
            "freezeRevision": 1,
            "freezeContentSha256": run_core.content_digest(held),
            "executingRevision": first,
        },
    }
    stored = core.record_text(document)
    # The runs are committed afterwards. The executing revision is still A.
    assert _commit(tmp_path) != first
    assert core.record_text(_aggregate(runs, tmp_path)) == stored


@pytest.mark.parametrize("in_place", [True, False])
@pytest.mark.parametrize("committed", [False, True])
def test_a_reason_that_is_registered_after_the_executing_revision_is_refused(
    tmp_path: Path, in_place: bool, committed: bool
) -> None:
    """The record, the registry, and each manifest are changed after the run.

    Commit A holds a record that does not register the reason of the probe,
    and a registry that pins that record. Four runs state A. Then the reason
    is registered, in the record or in a new record, the registry pins the
    result, and each manifest names it. The tree agrees with itself, and it is
    committed or not. The second commit of this change gave a median of
    20,900 ms for the tree. The authority is A, so the aggregate is refused.
    """
    first = _preregister(tmp_path)
    runs = _runs(tmp_path, FOUR)
    assert _aggregate(runs, tmp_path)["aggregate"]["countedRuns"] == 4
    _set_result(runs[-1], "INCONCLUSIVE", POST_HOC_REASON)
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION

    _register_post_hoc(tmp_path, runs, in_place=in_place)
    spec = _read_json(runs[-1] / run_core.MANIFEST_NAME)["metadata"]["spec"]
    assert load_registry(tmp_path)[spec["freezeRecord"]] == spec["freezeContentSha256"]
    registered = _read_json(tmp_path / spec["freezeRecord"])
    assert POST_HOC_REASON in json.dumps(registered[core.EXCLUSION_REASONS_MEMBER])
    if committed:
        assert _commit(tmp_path) != first
    for run in runs:
        manifest = _read_json(run / run_core.MANIFEST_NAME)
        assert manifest["metadata"]["executingRevision"] == first
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_HISTORY
    assert "does not hold its freeze record" in refused.message
    assert "open-episode-1" in refused.message
    assert POST_HOC_REASON not in str(refused)
    # What A holds: the path of a new record is absent, and the record that
    # was changed in place has its earlier content.
    at_first = command.history(tmp_path).blob(first, spec["freezeRecord"])
    if in_place:
        assert at_first is not None
        assert run_core.content_digest(at_first) != spec["freezeContentSha256"]
        assert POST_HOC_REASON.encode() not in at_first
    else:
        assert at_first is None


def test_a_manifest_that_restates_its_executing_revision_is_accepted(
    tmp_path: Path,
) -> None:
    """A measured limit. The manifest is the authority for the executing revision.

    The tree of the test above, committed as B. While the manifest of the run
    states A, the aggregate is refused. With that manifest restated to B, the
    aggregate reads the record at B and is accepted, and the row states B.
    The aggregate does not decide which commit a run executed.
    """
    first = _preregister(tmp_path)
    runs = _runs(tmp_path, FOUR)
    _set_result(runs[-1], "INCONCLUSIVE", POST_HOC_REASON)
    _register_post_hoc(tmp_path, runs, in_place=True)
    second = _commit(tmp_path)
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_HISTORY
    _executed(runs[-1], second)
    document = _aggregate(runs, tmp_path)
    row = next(r for r in document["aggregate"]["runs"] if not r["counted"])
    assert row["exclusion"]["reason"] == POST_HOC_REASON
    assert row["exclusion"]["preregistration"]["executingRevision"] == second
    assert sorted(r["executingRevision"] for r in document["runs"]) == sorted(
        [first] * 3 + [second]
    )


def _registry_text(records: str, kind: str = "ExperimentFreezeRegistry") -> str:
    return f'{{{_HEAD}, "kind": "{kind}", "records": {records}}}'


def _rows(*pins: tuple[str, str]) -> str:
    return json.dumps(
        [{"path": path, "contentSha256": digest} for path, digest in pins]
    )


#: A registry of a commit, by the path and the digest of the record. None is
#: no registry.
REGISTRIES_AT_REVISION: dict[str, Callable[[str, str], str | bytes | None]] = {
    "absent": lambda path, digest: None,
    "no pin": lambda path, digest: _registry_text("[]"),
    "another digest": lambda path, digest: _registry_text(_rows((path, "0" * 64))),
    "another path": lambda path, digest: _registry_text(
        _rows((path + ".other", digest))
    ),
    "another kind": lambda path, digest: _registry_text(
        _rows((path, digest)), kind="Another"
    ),
    "records twice": lambda path, digest: (
        f'{{{_HEAD}, "kind": "ExperimentFreezeRegistry", "records": [], '
        f'"records": {_rows((path, digest))}}}'
    ),
    "path twice in one record": lambda path, digest: _registry_text(
        f'[{{"path": "another", "path": "{path}", "contentSha256": "{digest}"}}]'
    ),
    "record twice": lambda path, digest: _registry_text(
        _rows((path, digest), (path, digest))
    ),
    "not text": lambda path, digest: b"\xff\xfe\x00",
    "nested arrays": lambda path, digest: "[" * 100_000,
}


@pytest.mark.parametrize("name", sorted(REGISTRIES_AT_REVISION))
def test_a_registry_that_does_not_pin_the_record_at_the_revision_is_a_refusal(
    tmp_path: Path, name: str
) -> None:
    """The registry of commit A is absent, or it does not pin the record.

    The registry of the tree is then written to pin the record, so each check
    of the tree is held, and the reason is the one that the record registers.
    """
    _write(tmp_path / FREEZE_REF, _freeze(_reasons()))
    digest = run_core.content_digest((tmp_path / FREEZE_REF).read_bytes())
    registry = REGISTRIES_AT_REVISION[name](FREEZE_REF, digest)
    if isinstance(registry, bytes):
        (tmp_path / REGISTRY_PATH).write_bytes(registry)
    elif registry is not None:
        _write(tmp_path / REGISTRY_PATH, registry)
    _commit(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    _pin(tmp_path, FREEZE_REF)
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_HISTORY
    assert "freeze registry of its executing revision" in refused.message
    # The same tree, committed, with the run restated to that commit, is accepted.
    second = _commit(tmp_path)
    _executed(runs[-1], second)
    assert _aggregate(runs, tmp_path)["aggregate"]["median"] == 20_900


def _consistent_tree(root: Path) -> list[Path]:
    """A tree whose record registers the reason of each run, with its commit."""
    _preregister(root)
    return _runs(root, THREE | {"abort": "ABORTED"})


def test_an_executing_revision_that_the_clone_does_not_hold_is_a_refusal(
    tmp_path: Path,
) -> None:
    """No file of the tree is read in the place of a commit that is absent.

    The tree registers the reason, and its registry pins the record. The
    aggregate is refused for a commit that the clone does not hold, for the
    identifier of a tag object, and for the identifier of a tree object.
    """
    runs = _consistent_tree(tmp_path)
    first = HEADS[tmp_path]
    assert _aggregate(runs, tmp_path)["aggregate"]["median"] == 20_900
    _git(tmp_path, "tag", "-a", "v0", "-m", "an annotated tag")
    for revision in (
        "d" * 40,
        _git(tmp_path, "rev-parse", "v0"),
        _git(tmp_path, "rev-parse", first + "^{tree}"),
    ):
        assert revision != first and len(revision) == 40
        _executed(runs[-1], revision)
        assert check_run(runs[-1], tmp_path).status == run_core.CONFORMING
        refused = _refusal(runs, tmp_path)
        assert refused.rule == core.RULE_EXCLUSION_REVISION
        assert "abort-1" in refused.message
        assert tmp_path.name not in str(refused)


def _writable(function: Callable[..., Any], name: str, _: Any) -> None:
    """Git writes its objects read-only, and Windows does not remove such a file."""
    os.chmod(name, stat.S_IWRITE)
    function(name)


def test_an_aggregate_with_no_reader_of_commits_leaves_no_run_out(
    tmp_path: Path,
) -> None:
    """The function is given no reader, or the tree is in no clone."""
    runs = _consistent_tree(tmp_path)
    assert _aggregate(runs, tmp_path)["aggregate"]["median"] == 20_900
    with pytest.raises(core.ReplayRefused) as refused:
        core.aggregate_runs(METRIC, runs, REVISION, tmp_path)
    assert refused.value.rule == core.RULE_EXCLUSION_REVISION
    shutil.rmtree(tmp_path / ".git", onerror=_writable)
    if command._git(tmp_path, "rev-parse", "--git-dir") is not None:
        pytest.skip("the temporary directory is inside a Git checkout")
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_REVISION


def test_no_commit_is_read_for_runs_that_are_all_counted(tmp_path: Path) -> None:
    """PASSED and FAILED runs are counted whatever their executing revision is.

    The reader of commits fails when it is called, the manifests state a
    commit that no clone holds, and one FAILED run states a reason.
    """

    def fail(*_: str) -> Any:
        raise AssertionError("a commit was read")

    runs = _runs(tmp_path, FOUR)
    _set_result(runs[1], "FAILED", REASON)
    figures = core.aggregate_runs(
        METRIC, runs, REVISION, tmp_path, core.History(fail, fail)
    )["aggregate"]
    assert (figures["countedRuns"], figures["median"]) == (4, None)
    assert all(row["counted"] and row["exclusion"] is None for row in figures["runs"])


def test_a_replacement_object_does_not_stand_for_the_executing_revision(
    tmp_path: Path,
) -> None:
    """Git can be told to read one commit in the place of another.

    Commit B registers the reason of the probe, and the clone is told to read
    B where A is named. A plain read of A then gives the record of B. The
    reader of the aggregate reads no replacement, so it gives the record of A.
    """
    first = _preregister(tmp_path)
    runs = _runs(tmp_path, FOUR)
    _set_result(runs[-1], "INCONCLUSIVE", POST_HOC_REASON)
    _register_post_hoc(tmp_path, runs, in_place=True)
    second = _commit(tmp_path)
    _git(tmp_path, "replace", first, second)
    plain = command._blob(tmp_path, first, FREEZE_REF)
    assert plain is not None and POST_HOC_REASON.encode() in plain
    held = command.history(tmp_path).blob(first, FREEZE_REF)
    assert held is not None and POST_HOC_REASON.encode() not in held
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_HISTORY


def test_a_file_of_a_commit_that_is_too_long_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = _consistent_tree(tmp_path)
    first = HEADS[tmp_path]
    assert _aggregate(runs, tmp_path)["aggregate"]["median"] == 20_900
    size = len((tmp_path / FREEZE_REF).read_bytes())
    monkeypatch.setattr(command, "MAX_HISTORY_BYTES", size)
    assert command.history(tmp_path).blob(first, FREEZE_REF) is not None
    monkeypatch.setattr(command, "MAX_HISTORY_BYTES", size - 1)
    assert command.history(tmp_path).blob(first, FREEZE_REF) is None
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_HISTORY


def test_the_reader_of_commits_reads_a_file_of_the_commit_and_nothing_else(
    tmp_path: Path,
) -> None:
    """A directory, a file of the tree alone, and a path that the commit lacks."""
    first = _preregister(tmp_path)
    reader = command.history(tmp_path)
    _write(tmp_path / "untracked.json", "{}\n")
    (tmp_path / FREEZE_REF).write_bytes(b"changed in the tree\n")
    for name in (EXPERIMENT_REF, "untracked.json", "absent.json"):
        assert reader.blob(first, name) is None, name
    held = reader.blob(first, FREEZE_REF)
    assert held is not None and json.loads(held)["metadata"] == {"revision": 1}
    assert not reader.commit_present("d" * 40)
    assert not reader.commit_present("")


def test_a_record_of_the_revision_in_another_form_is_a_refusal(tmp_path: Path) -> None:
    """The record at the commit states a member twice. Its digest is the stated one.

    The layout check refuses such a record in the tree, so no run directory
    with it is built, and no aggregate reaches the commit. The function that
    reads the commit is held by itself here, with the members of a manifest
    that it reads.
    """
    record = (
        '{"metadata": {"revision": 1}, "exclusionReasons": null, '
        f'"exclusionReasons": {json.dumps(_reasons())}}}\n'
    )
    _write(tmp_path / FREEZE_REF, record)
    _pin(tmp_path, FREEZE_REF)
    first = _commit(tmp_path)
    manifest = {
        "metadata": {
            "runId": "abort-1",
            "executingRevision": first,
            "spec": _spec(tmp_path),
        }
    }
    run = core._Run(_run_ref("abort"), tmp_path, manifest, "0" * 64)
    with pytest.raises(core.ReplayRefused) as refused:
        core._frozen_reasons(run, command.history(tmp_path))
    assert refused.value.rule == core.RULE_EXCLUSION_HISTORY
    assert "one JSON object" in refused.value.message
    # The same members with a record of one object give the reasons.
    _write(tmp_path / FREEZE_REF, _freeze(_reasons()))
    _pin(tmp_path, FREEZE_REF)
    manifest["metadata"].update(
        executingRevision=_commit(tmp_path), spec=_spec(tmp_path)
    )
    assert core._frozen_reasons(run, command.history(tmp_path)) == _reasons()


def _object_file(root: Path, name: str) -> Path:
    """The loose file of the object store that holds one object of a clone."""
    identifier = _git(root, "rev-parse", name)
    return root / ".git" / "objects" / identifier[:2] / identifier[2:]


def test_a_replaced_file_of_the_object_store_does_not_give_another_record(
    tmp_path: Path,
) -> None:
    """The two objects of commit A are overwritten with the files of the tree.

    The tree registers the reason of the probe and agrees with itself. A plain
    read of A then gives the record of the tree, because Git does not compute
    the identifier of an object that it reads. The reader of the aggregate
    computes it, so the aggregate is refused. A review of this commit obtained
    a median of 20,900 ms this way before the reader held each object to its
    identifier.
    """
    first = _preregister(tmp_path)
    runs = _runs(tmp_path, FOUR)
    _set_result(runs[-1], "INCONCLUSIVE", POST_HOC_REASON)
    _register_post_hoc(tmp_path, runs, in_place=True)
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_HISTORY
    for ref in (FREEZE_REF, REGISTRY_PATH):
        data = (tmp_path / ref).read_bytes()
        stored = _object_file(tmp_path, f"{first}:{ref}")
        os.chmod(stored, stat.S_IWRITE | stat.S_IREAD)
        stored.write_bytes(zlib.compress(b"blob %d\0" % len(data) + data))
    plain = command._blob(tmp_path, first, FREEZE_REF)
    assert plain is not None and POST_HOC_REASON.encode() in plain
    assert command.history(tmp_path).blob(first, FREEZE_REF) is None
    refused = _refusal(runs, tmp_path)
    assert refused.rule == core.RULE_EXCLUSION_HISTORY
    assert POST_HOC_REASON not in str(refused)


def test_a_record_that_the_commit_holds_as_a_link_is_not_read(tmp_path: Path) -> None:
    """The commit names the bytes of the record under the mode of a symbolic link.

    The bytes have the content digest that each manifest states, and a plain
    read of the path gives them. A path that is no regular file of the commit
    is no freeze record of it.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    _write(tmp_path / FREEZE_REF, _freeze(_reasons()))
    _pin(tmp_path, FREEZE_REF)
    _git(tmp_path, "init", "--quiet")
    _git(tmp_path, "add", "--", REGISTRY_PATH)
    identifier = _git(tmp_path, "hash-object", "-w", "--", FREEZE_REF)
    _git(
        tmp_path,
        "update-index",
        "--add",
        "--cacheinfo",
        f"120000,{identifier},{FREEZE_REF}",
    )
    _git(tmp_path, "commit", "--quiet", "-m", "a record under the mode of a link")
    first = HEADS[tmp_path] = _git(tmp_path, "rev-parse", "HEAD")
    assert _git(tmp_path, "ls-tree", first, "--", FREEZE_REF).startswith("120000 blob")
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    plain = command._blob(tmp_path, first, FREEZE_REF)
    assert plain is not None
    assert run_core.content_digest(plain) == _spec(tmp_path)["freezeContentSha256"]
    assert command.history(tmp_path).blob(first, FREEZE_REF) is None
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_HISTORY


def test_a_clone_that_fetches_the_objects_that_it_lacks_gives_no_commit(
    tmp_path: Path,
) -> None:
    """A partial clone. Its commit A is present, and the two files of A are not.

    A plain read of a file of A makes Git fetch it from the remote of the
    clone. The reader of the aggregate fetches nothing, and it gives no commit
    for a clone that is set to fetch. The objects are still absent afterwards.
    A review of this commit obtained an accepted aggregate from such a clone.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    first = _preregister(origin)
    _git(origin, "config", "uploadpack.allowfilter", "true")
    clone = tmp_path / "clone"
    _git(
        tmp_path,
        "clone",
        "--quiet",
        "--filter=blob:none",
        "--no-checkout",
        origin.as_uri(),
        "clone",
    )

    def missing() -> list[str]:
        listed = _git(clone, "rev-list", "--objects", "--missing=print", first)
        return [line for line in listed.splitlines() if line.startswith("?")]

    assert len(missing()) == 2
    for ref in (FREEZE_REF, REGISTRY_PATH):
        _write(clone / ref, (origin / ref).read_bytes().decode("utf-8"))
    HEADS[clone] = first
    runs = _runs(clone, THREE | {"abort": "ABORTED"})
    reader = command.history(clone)
    assert not reader.commit_present(first)
    assert reader.blob(first, FREEZE_REF) is None
    assert _refusal(runs, clone).rule == core.RULE_EXCLUSION_REVISION
    assert len(missing()) == 2
    # The same files in the clone that holds each object are accepted.
    HEADS[origin] = first
    assert _aggregate(_runs(origin, THREE | {"abort": "ABORTED"}), origin)["aggregate"][
        "median"
    ]


def test_the_environment_does_not_name_the_clone_of_the_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tree in no clone, with a variable that names the clone of another tree."""
    other = tmp_path / "other"
    other.mkdir()
    first = _preregister(other)
    plain = tmp_path / "plain"
    plain.mkdir()
    if command._git(plain, "rev-parse", "--git-dir") is not None:
        pytest.skip("the temporary directory is inside a Git checkout")
    for ref in (FREEZE_REF, REGISTRY_PATH):
        _write(plain / ref, (other / ref).read_bytes().decode("utf-8"))
    HEADS[plain] = first
    runs = _runs(plain, THREE | {"abort": "ABORTED"})
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    assert command._commit_present(plain, first)
    assert not command.history(plain).commit_present(first)
    assert _refusal(runs, plain).rule == core.RULE_EXCLUSION_REVISION
    monkeypatch.delenv("GIT_DIR")
    monkeypatch.setenv(
        "GIT_ALTERNATE_OBJECT_DIRECTORIES", str(other / ".git" / "objects")
    )
    assert _refusal(runs, plain).rule == core.RULE_EXCLUSION_REVISION


def test_a_host_with_no_git_leaves_no_run_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = _consistent_tree(tmp_path)
    assert _aggregate(runs, tmp_path)["aggregate"]["median"] == 20_900

    def absent(*_: Any, **__: Any) -> Any:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", absent)
    assert _refusal(runs, tmp_path).rule == core.RULE_EXCLUSION_REVISION


def test_a_root_below_the_top_of_a_clone_reads_its_own_paths(tmp_path: Path) -> None:
    """The root is a directory of a clone. A path above it is not read."""
    root = tmp_path / "sub"
    _write(root / "inside.json", '{"inside": true}\n')
    _write(tmp_path / "outside.json", "{}\n")
    first = _commit(tmp_path)
    reader = command.history(root)
    assert reader.commit_present(first)
    assert reader.blob(first, "inside.json") == b'{"inside": true}\n'
    for name in (
        "../outside.json",
        "./inside.json",
        "inside.json/",
        "/inside.json",
        "",
    ):
        assert reader.blob(first, name) is None, name
    assert command.history(tmp_path).blob(first, "sub/inside.json") is not None
    # A path with a character that no file name of a record holds gives no content.
    for name in ("a\0b", "a\nb", "sub\\inside.json"):
        assert command.history(tmp_path).blob(first, name) is None


def test_a_file_is_the_one_that_the_commit_identifier_names() -> None:
    """The reader follows a path through objects that it is given, by their hashes."""

    def held(kind: str, content: bytes) -> tuple[str, str, bytes]:
        header = f"{kind} {len(content)}".encode() + b"\0"
        return hashlib.sha1(header + content).hexdigest(), kind, content

    def tree(mode: bytes, name: bytes, identifier: str) -> tuple[str, str, bytes]:
        return held("tree", mode + b" " + name + b"\0" + bytes.fromhex(identifier))

    blob = held("blob", b"content\n")
    inner = tree(b"100644", b"record.json", blob[0])
    outer = tree(b"40000", b"docs", inner[0])
    commit = held("commit", f"tree {outer[0]}\nauthor a\n\nmessage\n".encode())
    parts = ["docs", "record.json"]
    chain = [commit, outer, inner, blob]
    assert command.verified_file(commit[0], parts, chain) == b"content\n"
    other = held("blob", b"another\n")
    link = tree(b"120000", b"record.json", blob[0])
    refused = {
        "another commit identifier": ("0" * 40, parts, chain),
        "a blob that the tree does not name": (commit[0], parts, [*chain[:3], other]),
        "content under another identifier": (
            commit[0],
            parts,
            [*chain[:3], (blob[0], "blob", b"another\n")],
        ),
        "a tree that the commit does not name": (
            commit[0],
            ["record.json"],
            [commit, inner, blob],
        ),
        "another name": (commit[0], ["docs", "record.JSON"], chain),
        "a link": (
            commit[0],
            parts,
            [
                held(
                    "commit", f"tree {tree(b'40000', b'docs', link[0])[0]}\n".encode()
                ),
                tree(b"40000", b"docs", link[0]),
                link,
                blob,
            ],
        ),
        "an object too few": (commit[0], parts, chain[:3]),
        "a tree in the place of the file": (
            commit[0],
            ["docs"],
            [commit, outer, inner],
        ),
    }
    for name, (revision, path, objects) in refused.items():
        assert command.verified_file(revision, path, objects) is None, name
    # The link case has each hash and each name in order. Its mode alone refuses it.
    revision, path, objects = refused["a link"]
    assert revision != objects[0][0]
    assert command.verified_file(objects[0][0], path, objects) is None
    regular = [
        held("commit", f"tree {outer[0]}\n".encode()),
        outer,
        inner,
        blob,
    ]
    assert command.verified_file(regular[0][0], path, regular) == b"content\n"


def test_the_aggregate_command_reads_the_executing_revision(
    tmp_path: Path, no_git: None, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    """The command, on a clone: an accepted exclusion, then the post-hoc tree."""
    first = _preregister(tmp_path)
    runs = _runs(tmp_path, THREE | {"abort": "ABORTED"})
    arguments = ["aggregate", "--metric", METRIC, "--root", str(tmp_path)]
    arguments += [str(run) for run in runs]
    assert command.main(arguments) == 0
    printed = json.loads(capfdbinary.readouterr().out)
    row = next(r for r in printed["aggregate"]["runs"] if not r["counted"])
    assert row["exclusion"]["preregistration"]["executingRevision"] == first
    assert row["exclusion"]["reason"] == REASON
    _set_result(runs[-1], "ABORTED", POST_HOC_REASON)
    reasons = _reasons()
    reasons["reasons"].append(
        {"id": "added-later", "resultState": "ABORTED", "reason": POST_HOC_REASON}
    )
    _write(tmp_path / FREEZE_REF, _freeze(reasons))
    _restate_freeze_digest(tmp_path, runs)
    _pin(tmp_path, FREEZE_REF)
    assert command.main(arguments) == 3
    captured = capfdbinary.readouterr()
    assert captured.out == b""
    assert captured.err.startswith(f"REFUSED  {core.RULE_EXCLUSION_HISTORY}: ".encode())
    assert POST_HOC_REASON.encode() not in captured.err
    assert tmp_path.name.encode() not in captured.err


def test_only_the_reliability_experiment_records_register_exclusion_reasons() -> None:
    """Three committed records are of E01, and E01 has no numerical aggregate. Two
    are the Sprint 5 integration validation, which computes no aggregate. One is the
    Q1 environment qualification, added by V2-S6-001-PR1, which computes none either.
    Two are the Q2 runtime startup characterization, revisions 1 and 2, added by
    V2-S6-002-PR1, which states a maximum and computes no aggregate. One is the Q3
    stable caller characterization, added by V2-S6-002-PR2, which states one
    percentile of one run and computes no aggregate over runs. Three more are Q1
    revision 2, Q2 revision 3, and Q3 revision 2, added by V2-S6-004-PR1, which
    change the environment identity and compute no aggregate either. None of
    these twelve registers an exclusion reason.

    The five records added by V2-S6-003-PR1, of V2-E02A, V2-E02B, V2-E02C,
    V2-E04, and V2-E05, each register the reasons of their own experiment before
    any run, in the form that the aggregate reads. The four records added by
    V2-S6-007-PR1, revision 2 of V2-E02A, V2-E02B, V2-E02C, and V2-E05, register
    them again, with the reason clock-reading-missing added. The record added by
    V2-S6-005-PR1, revision 2 of V2-E04, registers them again, with that reason and
    the two reasons of its reversal timing added. The freeze check does not read the
    member. The member is read when an aggregate reads it.
    """
    records = sorted((REPO_ROOT / "docs" / "proof" / "experiments").rglob("freeze-r*"))
    assert len(records) == 22
    reliability = {"v2-e02a", "v2-e02b", "v2-e02c", "v2-e04", "v2-e05"}
    registering = []
    for record in records:
        document = _read_json(record)
        if record.parent.name in reliability:
            policy = document[core.EXCLUSION_REASONS_MEMBER]
            assert analysis.core._reasons_problem(policy) is None
            assert policy["experimentId"] == document["metadata"]["experiment"]
            registering.append(record.parent.name)
        else:
            assert core.EXCLUSION_REASONS_MEMBER not in document
    assert sorted(registering) == sorted([*reliability, *reliability])
    example = _read_json(EXAMPLE_ROOT / FREEZE_REF)
    assert core.EXCLUSION_REASONS_MEMBER not in example


# --------------------------------------------------------------------------
# Nothing is promoted
# --------------------------------------------------------------------------


def _member_names(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {n for item in value.values() for n in _member_names(item)}
    if isinstance(value, list):
        return {n for item in value for n in _member_names(item)}
    return set()


def test_a_run_analysis_has_no_member_for_a_claim_a_level_or_a_result(
    tmp_path: Path,
) -> None:
    names = _member_names(_stored(_bound_run(tmp_path, EXAMPLE_CASE)))
    for name in names:
        lowered = name.lower()
        assert "claim" not in lowered and "certif" not in lowered
        assert "level" not in lowered and "verdict" not in lowered
        assert lowered not in ("resultstate", "result", "state_of_run", "passed")


def test_the_tool_writes_no_file_and_imports_no_claim_register() -> None:
    for name in ("core.py", "__main__.py", "__init__.py"):
        path = REPO_ROOT / "tools" / "analysis_replay" / name
        text = path.read_text(encoding="utf-8")
        for call in ("write_text", "write_bytes", ".open(", "open(", "unlink", "mkdir"):
            assert call not in text, (name, call)
        assert "evidence_model" not in _tools_imports(path)
    # The module that computes imports no process module. The command does, for Git.
    tree = ast.parse(
        (REPO_ROOT / "tools" / "analysis_replay" / "core.py").read_text("utf-8")
    )
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not imported & {"subprocess", "socket", "urllib", "http", "shutil"}


def test_the_gate_holds_no_run_that_names_no_analysis(tmp_path: Path) -> None:
    assert core.gate_problems(_raw_run(tmp_path, EXAMPLE_CASE), tmp_path) == []
    assert core.gate_problems(tmp_path / "no-such-run", tmp_path) == []
    # The three committed runs were written before the schema, and name no role.
    for run in sorted((REPO_ROOT / "docs/proof/experiments/v2-e01/runs").iterdir()):
        assert core.gate_problems(run, REPO_ROOT) == []


def test_the_gate_holds_a_run_that_names_an_analysis(tmp_path: Path) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    assert core.gate_problems(run_dir, tmp_path) == []
    _rewrite(run_dir, _set_figure)
    (problem,) = core.gate_problems(run_dir, tmp_path)
    assert problem.startswith(core.RULE_DOCUMENT)


def test_the_gate_refuses_a_manifest_that_it_cannot_read(tmp_path: Path) -> None:
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    _write(run_dir / run_core.MANIFEST_NAME, "not JSON\n")
    assert core.gate_problems(run_dir, tmp_path) == [
        "the run manifest is not readable as one JSON object"
    ]


def test_the_gate_reads_a_manifest_of_another_shape_for_the_role(
    tmp_path: Path,
) -> None:
    """A manifest that the schema refuses and that names an analysis is not passed."""
    run_dir = tmp_path / _run_ref(EXAMPLE_CASE)
    _write_json(
        run_dir / run_core.MANIFEST_NAME,
        {"evidence": {"files": [{"role": "analysis", "path": ANALYSIS_FILE}]}},
    )
    (problem,) = core.gate_problems(run_dir, tmp_path)
    assert problem.startswith(core.RULE_RUN)
    assert "evidence-manifest-refused" in problem


@pytest.mark.parametrize("role", ["Analysis", "analysis ", " ANALYSIS"])
def test_the_gate_reads_a_role_in_another_spelling(tmp_path: Path, role: str) -> None:
    """The first commit compared the role as text, and passed each of these."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    manifest["evidence"]["files"][-1]["role"] = role
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)
    assert core.gate_problems(run_dir, tmp_path)


@pytest.mark.parametrize(
    "evidence",
    [[], "files", {"files": {}}, {"files": ["analysis"]}, {"files": [{"role": 7}]}, {}],
)
def test_the_gate_refuses_evidence_that_states_no_role_for_each_file(
    tmp_path: Path, evidence: object
) -> None:
    run_dir = tmp_path / _run_ref(EXAMPLE_CASE)
    _write_json(run_dir / run_core.MANIFEST_NAME, {"evidence": evidence})
    assert core.gate_problems(run_dir, tmp_path) == [
        "the run manifest does not state its evidence files with a role each"
    ]


def test_the_gate_refuses_a_manifest_that_is_a_directory(tmp_path: Path) -> None:
    run_dir = tmp_path / _run_ref(EXAMPLE_CASE)
    (run_dir / run_core.MANIFEST_NAME).mkdir(parents=True)
    assert core.gate_problems(run_dir, tmp_path) == [
        "the run manifest is not readable as one JSON object"
    ]


def test_the_gate_does_not_read_a_run_analysis_under_another_role(
    tmp_path: Path,
) -> None:
    """A measured limit. The gate reads the role of a file and not its content."""
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    _rewrite(run_dir, _set_figure)
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    manifest["evidence"]["files"][-1]["role"] = "result"
    _write_json(run_dir / run_core.MANIFEST_NAME, manifest)
    assert check_run(run_dir, tmp_path).status == run_core.CONFORMING
    assert core.gate_problems(run_dir, tmp_path) == []


def test_the_command_of_the_index_reports_a_run_that_does_not_replay(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools.evidence_index import __main__ as index_command

    def refuse(*_: object, **__: object) -> list[str]:
        raise ValueError("the analysis of a run does not replay")

    monkeypatch.setattr(index_core, "analysis_gate", refuse)
    for mode in ([], ["--print"], ["--check"]):
        assert index_command.main(mode) == 1
        assert capsys.readouterr().out.startswith("MISMATCH the analysis of a run")


def _ledger(run_ref: str) -> dict[str, Any]:
    return {
        "registerChanges": [
            {
                "changeId": "C-1",
                "operation": "add-record",
                "record": {"files": [f"{run_ref}/{ANALYSIS_FILE}"]},
            }
        ]
    }


def test_the_evidence_index_refuses_a_run_whose_analysis_does_not_replay(
    tmp_path: Path,
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    ledgers = [_ledger(_run_ref(EXAMPLE_CASE))]
    assert index_core.analysis_gate({}, ledgers, tmp_path) == [_run_ref(EXAMPLE_CASE)]
    _rewrite(run_dir, _set_figure)
    with pytest.raises(ValueError, match="does not replay") as refused:
        index_core.analysis_gate({}, ledgers, tmp_path)
    assert core.RULE_DOCUMENT in str(refused.value)
    assert _run_ref(EXAMPLE_CASE) in str(refused.value)


def test_the_evidence_index_is_built_through_the_gate_and_states_nothing_of_it() -> (
    None
):
    """The committed index is what the register and the ledgers produce."""
    assert evidence_index.analysis_gate is index_core.analysis_gate
    register = load_register()
    runs = index_core.analysis_gate(register, evidence_index.load_ledgers())
    assert runs == sorted(
        f"docs/proof/experiments/v2-e01/runs/{name}"
        for name in ("20261002-e01-abc-1", "20261003-e01-abc-1", "20261006-e01-d-1")
    )
    index = index_core.build_index()
    assert index_core.render_index(index) == index_core.INDEX_PATH.read_text("utf-8")
    assert "analysis_replay" not in json.dumps(index)
    assert "run-analysis" not in json.dumps(index)


def test_building_the_index_calls_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: object, **__: object) -> list[str]:
        raise ValueError("the analysis of a run does not replay")

    monkeypatch.setattr(index_core, "analysis_gate", refuse)
    with pytest.raises(ValueError, match="does not replay"):
        index_core.build_index()


def test_the_role_of_a_run_analysis_is_a_derived_role_of_the_layout() -> None:
    assert ROLES[core.ANALYSIS_ROLE].kind == "derived"
    assert set(analysis.INPUTS) <= {n for n, r in ROLES.items() if r.kind == "raw"}


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


@pytest.fixture
def no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """A command that reads no commit of the analysis code.

    The commit of the checkout is given, and no clone holds the commit that a
    run analysis states. The reader of an executing revision is not replaced.
    """
    monkeypatch.setattr(command, "checkout_revision", lambda: REVISION)
    monkeypatch.setattr(command, "_commit_present", lambda *_: False)


def test_bind_prints_the_document_that_the_function_gives(
    tmp_path: Path, no_git: None, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    declaration = CASES / EXAMPLE_CASE / "declaration.json"
    status = command.main(
        [
            "bind",
            str(run_dir),
            "--declaration",
            str(declaration),
            "--root",
            str(tmp_path),
        ]
    )
    printed = capfdbinary.readouterr().out
    assert status == 0 and b"\r" not in printed
    expected = core.bind_run(run_dir, _declaration(EXAMPLE_CASE), REVISION, tmp_path)
    assert printed.decode("utf-8") == core.record_text(expected)
    assert sorted(p.name for p in run_dir.iterdir()) == sorted(
        [
            run_core.MANIFEST_NAME,
            *(p.name for p in (CASES / EXAMPLE_CASE).glob("*.jsonl")),
        ]
    )


def test_bind_refuses_with_one_line_and_exit_status_3(
    tmp_path: Path, no_git: None, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = _raw_run(tmp_path, EXAMPLE_CASE)
    arguments = ["bind", str(run_dir), "--root", str(tmp_path), "--declaration"]
    assert command.main([*arguments, str(CASES / "abort" / "declaration.json")]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"REFUSED  {core.RULE_DECLARATION_IDENTITY}: ")
    assert command.main([*arguments, str(tmp_path / "absent.json")]) == 3
    assert capsys.readouterr().err.startswith(f"REFUSED  {core.RULE_ANALYSIS}: ")


def test_verify_reports_a_replay_and_what_it_did_not_compare(
    tmp_path: Path, no_git: None, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    assert command.main(["verify", str(run_dir), "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith(
        f"replayed    {_run_ref(EXAMPLE_CASE)}/{ANALYSIS_FILE}  (6 input file(s), "
        "code same)\n"
    )
    assert "revision  not-checked" in out


def test_verify_refuses_an_edit_and_a_run_with_no_analysis(
    tmp_path: Path, no_git: None, capsys: pytest.CaptureFixture[str]
) -> None:
    edited = _bound_run(tmp_path, EXAMPLE_CASE)
    _rewrite(edited, _set_figure)
    bare = _raw_run(tmp_path, "abort")
    arguments = ["verify", "--root", str(tmp_path)]
    assert command.main([*arguments, str(edited)]) == 3
    assert core.RULE_DOCUMENT in capsys.readouterr().out
    assert command.main([*arguments, str(bare)]) == 3
    out = capsys.readouterr().out
    assert out.startswith("REFUSED") and core.RULE_MISSING in out


def test_verify_refuses_a_commit_whose_files_are_not_the_stated_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = _bound_run(tmp_path, EXAMPLE_CASE)
    monkeypatch.setattr(command, "_commit_present", lambda *_: True)
    monkeypatch.setattr(
        command, "_blob", lambda root, revision, path: (root / path).read_bytes()
    )
    monkeypatch.setattr(
        command,
        "_tracked",
        lambda root, revision, package: [
            path.relative_to(root).as_posix() for path in (root / package).rglob("*.py")
        ],
    )
    assert command.main(["verify", str(run_dir), "--root", str(tmp_path)]) == 0
    assert "revision  held" in capsys.readouterr().out
    monkeypatch.setattr(command, "_blob", lambda *_: b"other\n")
    assert command.main(["verify", str(run_dir), "--root", str(tmp_path)]) == 3
    assert core.RULE_REVISION in capsys.readouterr().out


def test_aggregate_prints_the_document_that_the_function_gives(
    tmp_path: Path, no_git: None, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    runs = _runs(tmp_path, THREE)
    arguments = ["aggregate", "--metric", METRIC, "--root", str(tmp_path)]
    assert command.main([*arguments, *(str(run) for run in runs)]) == 0
    printed = capfdbinary.readouterr().out.decode("utf-8")
    assert printed == core.record_text(
        core.aggregate_runs(METRIC, runs, REVISION, tmp_path)
    )
    assert command.main([*arguments, str(runs[0])]) == 3
    assert capfdbinary.readouterr().err.startswith(
        f"REFUSED  {core.RULE_AGGREGATE_OMITTED}: ".encode()
    )


def test_the_commands_take_no_revision_and_no_result_state() -> None:
    """The commit is read from Git and each state from a manifest."""
    for arguments in (
        ["bind", "x", "--declaration", "y", "--revision", REVISION],
        ["aggregate", "--metric", METRIC, "x=PASSED", "--state", "PASSED"],
        ["verify", "x", "--force"],
    ):
        with pytest.raises(SystemExit) as stopped:
            command.main(arguments)
        assert stopped.value.code == 2


def test_sources_prints_one_line_for_each_source_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert command.main(["sources"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"{row['sha256']}  {row['path']}" for row in core.analysis_sources()
    ]


def test_the_repository_command_replays_the_committed_attempts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Three committed run directories were written before the schema. Since
    V2-S5-006-PR1 each attempt of the Sprint 5 integration validation is replayed:
    its analysis is computed again with the same bytes.

    Where the clone holds the commit that an attempt states, the command states
    that the revision held; otherwise it states that it did not check it. The
    checkout of the hosted default lane holds one commit, so it holds neither
    stated commit. Which commits the clone holds is read here with Git itself, not
    with the function of the command. This test does not require that any clone
    holds them."""
    stated = [
        json.loads(
            (REPO_ROOT / INTEGRATION_DIRECTORY / run / "analysis.json").read_text(
                encoding="utf-8"
            )
        )["analysisCode"]["revision"]
        for run in INTEGRATION_RUNS
    ]
    present = sum(
        subprocess.run(
            ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
        for revision in stated
    )
    assert command.main(["repository"]) == 0
    lines = capsys.readouterr().out.splitlines()
    # The first attempt was bound before the same change gave the runner its
    # network policy, so its stated runner sources differ from the present ones.
    # The replay still holds: the present code gives the stored bytes.
    differs = [line.split()[-1] for line in lines if line.split()[0] == "source"]
    assert all(path.startswith("tools/reliability_runner/") for path in differs)
    assert [line.split()[0] for line in lines if line.split()[0] != "source"] == [
        "pre-schema"
    ] * 3 + ["replayed", "revision"] * len(INTEGRATION_RUNS) + ["runs"]
    assert sum(line.endswith("revision  held") for line in lines) == present
    unchecked = len(INTEGRATION_RUNS) - present
    assert sum("revision  not-checked" in line for line in lines) == unchecked
    total = 3 + len(INTEGRATION_RUNS)
    assert lines[-1].endswith(
        f"{total}: 3 pre-schema and not replayed, 0 with no analysis, "
        f"{len(INTEGRATION_RUNS)} replayed, 0 refused"
    )


def test_the_repository_command_lists_each_state_of_a_tree(
    tmp_path: Path, no_git: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tree that the suite builds: one run of each state that is not pre-schema."""
    _write_json(
        tmp_path / run_core.PRE_SCHEMA_REGISTER_REF,
        {
            "schemaVersion": run_core.SUPPORTED_API_VERSION,
            "kind": run_core.PRE_SCHEMA_REGISTER_KIND,
            "records": [],
        },
    )
    _bound_run(tmp_path, "zero-failure")
    _raw_run(tmp_path, "abort")
    assert command.main(["repository", "--root", str(tmp_path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines] == [
        "no-analysis",
        "replayed",
        "revision",
        "runs",
    ]
    assert lines[-1].endswith(
        "2: 0 pre-schema and not replayed, 1 with no analysis, 1 replayed, 0 refused"
    )
    _rewrite(tmp_path / _run_ref("zero-failure"), _set_figure)
    assert command.main(["repository", "--root", str(tmp_path)]) == 3
    out = capsys.readouterr().out
    assert core.RULE_DOCUMENT in out
    assert out.splitlines()[-1].endswith("0 replayed, 1 refused")


def test_a_name_in_another_script_does_not_stop_the_output(
    tmp_path: Path, no_git: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """The first commit printed the name as it was, and a console could refuse it."""
    name = "nope-\u2192-\u03bb"
    assert command.main(["verify", str(tmp_path / name), "--root", str(tmp_path)]) == 3
    out = capsys.readouterr().out
    assert out.isascii() and "\\u2192" in out


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
def test_the_commit_is_read_from_git_and_refused_while_a_source_differs(
    tmp_path: Path,
) -> None:
    """A temporary repository. The checkout of this suite is not read."""
    source = tmp_path / "tools" / core.SOURCE_PACKAGES[0] / "core.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"VALUE = 1\n")
    (tmp_path / ".gitignore").write_bytes(b"local_*.py\n")
    _git(tmp_path, "init", "--quiet")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "--quiet", "-m", "one source file")
    head = _git(tmp_path, "rev-parse", "HEAD")
    assert command.checkout_revision(tmp_path) == head

    rows = core.analysis_sources(tmp_path)
    code = {"revision": head, "sourceSha256": "", "sources": rows}

    def state(stated: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
        return core.revision_state(
            stated,
            lambda revision: command._commit_present(tmp_path, revision),
            lambda revision, path: command._blob(tmp_path, revision, path),
            lambda revision, package: command._tracked(tmp_path, revision, package),
        )

    assert state(code) == (core.REVISION_HELD, ())
    assert state(code | {"revision": "d" * 40}) == (core.REVISION_NOT_CHECKED, ())

    source.write_bytes(b"VALUE = 2\n")
    with pytest.raises(core.ReplayRefused) as refused:
        command.checkout_revision(tmp_path)
    assert refused.value.rule == core.RULE_UNCOMMITTED
    # The commit still holds the earlier file, so the present rows are not its rows.
    assert state(code | {"sources": core.analysis_sources(tmp_path)}) == (
        core.CODE_DIFFERS,
        (rows[0]["path"],),
    )
    source.write_bytes(b"VALUE = 1\n")
    assert command.checkout_revision(tmp_path) == head
    added = source.parent / "added.py"
    added.write_bytes(b"VALUE = 3\n")
    with pytest.raises(core.ReplayRefused):
        command.checkout_revision(tmp_path)
    added.unlink()

    # A file that Git ignores is a source file, and the status of Git is empty.
    ignored = source.parent / "local_settings.py"
    ignored.write_bytes(b"VALUE = 4\n")
    assert _git(tmp_path, "status", "--porcelain") == ""
    with pytest.raises(core.ReplayRefused) as refused:
        command.checkout_revision(tmp_path)
    assert refused.value.rule == core.RULE_UNCOMMITTED
    ignored.unlink()

    # A changed file that Git is told to leave out of its status is compared.
    _git(tmp_path, "update-index", "--assume-unchanged", rows[0]["path"])
    source.write_bytes(b"VALUE = 5\n")
    assert _git(tmp_path, "status", "--porcelain") == ""
    with pytest.raises(core.ReplayRefused):
        command.checkout_revision(tmp_path)
    _git(tmp_path, "update-index", "--no-assume-unchanged", rows[0]["path"])
    source.write_bytes(b"VALUE = 1\n")

    # A tag object is not a commit, and a document that states it is not checked.
    _git(tmp_path, "tag", "-a", "v0", "-m", "an annotated tag")
    tag = _git(tmp_path, "rev-parse", "v0")
    assert tag != head and len(tag) == 40
    assert state(code | {"revision": tag}) == (core.REVISION_NOT_CHECKED, ())

    # A second file in the commit that the rows do not state is a difference.
    added.write_bytes(b"VALUE = 3\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "--quiet", "-m", "a second source file")
    second = _git(tmp_path, "rev-parse", "HEAD")
    assert state(code | {"revision": second}) == (
        core.CODE_DIFFERS,
        (f"tools/{core.SOURCE_PACKAGES[0]}/added.py",),
    )


def test_a_directory_that_is_no_git_checkout_gives_no_commit(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()
    if command._git(outside, "rev-parse", "--verify", "HEAD^{commit}") is not None:
        pytest.skip("the temporary directory is inside a Git checkout")
    with pytest.raises(core.ReplayRefused) as refused:
        command.checkout_revision(outside)
    assert refused.value.rule == core.RULE_UNCOMMITTED


# --------------------------------------------------------------------------
# The committed example
# --------------------------------------------------------------------------


def test_the_committed_example_replays() -> None:
    """One synthetic run directory with its run analysis, as a replay example."""
    run_dir = EXAMPLE_ROOT / _run_ref(EXAMPLE_CASE)
    report = core.replay_run(run_dir, EXAMPLE_ROOT)
    assert report.findings == ()
    assert report.status == core.REPLAYED
    (replayed,) = report.analyses
    document = replayed.document
    committed = (CASES / EXAMPLE_CASE / "analysis.json").read_bytes().decode("utf-8")
    assert analysis.analysis_text(document["analysis"]) == committed
    # A placeholder: the example names no commit of this repository.
    assert document["analysisCode"]["revision"] == REVISION


def test_the_evidence_files_of_the_example_are_those_of_the_committed_case() -> None:
    run_dir = EXAMPLE_ROOT / _run_ref(EXAMPLE_CASE)
    sources = sorted((CASES / EXAMPLE_CASE).glob("*.jsonl"))
    assert len(sources) == 6
    for source in sources:
        assert file_digest(run_dir / source.name) == file_digest(source)
    assert sorted(path.name for path in run_dir.iterdir()) == sorted(
        [ANALYSIS_FILE, run_core.MANIFEST_NAME, *(s.name for s in sources)]
    )
    manifest = _read_json(run_dir / run_core.MANIFEST_NAME)
    assert manifest["limitations"][0].startswith("Fixture. No run executed.")


def test_the_example_is_what_the_suite_builds_but_for_its_code(tmp_path: Path) -> None:
    """The example states the sources of the commit that wrote it.

    A later change to a source file does not change the example. So the two
    documents are compared without the analysis code, and the replay above holds
    the example to the present code.
    """
    built = _stored(_bound_run(tmp_path, EXAMPLE_CASE))
    committed = _stored(EXAMPLE_ROOT / _run_ref(EXAMPLE_CASE))
    assert core._code_problem(committed["analysisCode"]) is None
    built.pop("analysisCode")
    committed.pop("analysisCode")
    assert built == committed


def test_the_example_is_outside_the_proof_tree() -> None:
    """The example is not in ``docs/proof/experiments``. Since V2-S5-006-PR1 the
    run directories of the layout there are the attempts of the Sprint 5
    integration validation, and no other."""
    assert not (REPO_ROOT / EXPERIMENT_REF).exists()
    listing = run_core.repository_report(REPO_ROOT)
    assert [entry.status for entry in listing.manifests] == [
        run_core.PRE_SCHEMA
    ] * 3 + [run_core.CONFORMING] * len(INTEGRATION_RUNS)


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_the_page_states_each_rule_as_the_module_does() -> None:
    rows = dict(re.findall(r"(?m)^\| `(replay-[a-z-]+)` \| (.+?) \|$", _page()))
    assert rows == dict(core.RULES)
    assert len(core.RULES) == 19


def test_the_page_states_each_limit_boundary_and_aggregate_rule() -> None:
    flat = _flat(_page())
    for statement in (
        core.AUTHORITY,
        *core.LIMITATIONS,
        *core.DOES_NOT_ESTABLISH,
        *core.AGGREGATE_RULES,
    ):
        assert statement in flat, statement
    assert len(core.LIMITATIONS) == 7
    assert len(core.DOES_NOT_ESTABLISH) == 5
    assert len(core.AGGREGATE_RULES) == 10


def test_the_page_names_each_source_package_and_both_schema_names() -> None:
    text = _page()
    for package in core.SOURCE_PACKAGES:
        assert f"`tools/{package}`" in text
    assert len(core.SOURCE_PACKAGES) == 7
    assert f"`{core.SCHEMA}`" in text
    assert f"`{core.AGGREGATE_SCHEMA}`" in text
    for metric in analysis.AGGREGATE_METRICS:
        assert f"`{metric}`" in text


def test_the_page_states_the_commands_of_the_tool() -> None:
    text = _page()
    for name in ("bind", "verify", "repository", "aggregate", "sources"):
        assert f"python -m tools.analysis_replay {name}" in text


def _write_example() -> None:
    """Write the committed example again, with the sources that are present."""
    run_dir = EXAMPLE_ROOT / _run_ref(EXAMPLE_CASE)
    if run_dir.exists():
        shutil.rmtree(run_dir)
    manifest = _read_json(
        _bound_run(EXAMPLE_ROOT, EXAMPLE_CASE) / run_core.MANIFEST_NAME
    )
    assert manifest["metadata"]["runId"] == _run_id(EXAMPLE_CASE)
    print(f"wrote {run_dir.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    _write_example()
