"""The V1 evidence pack's completeness and freeze decision, held to what it rests on.

`V1-S5-006-PR2` is the gate before the V1 evidence is frozen. It gave every finding the
normalization answered one final state, read how every executed record identifies the
repository code that ran, closed what committed evidence could close, and named what it
could not as release blockers. The failures this module exists to prevent are the ones
that make a freeze look finished when it is not: a finding that disappears, a blocker
that does not stop the gate, a code identity asserted rather than derived, a content
pin that does not match the repository's history, a hash that no longer names the file,
a current page that describes the freeze as undecided, and a superseded level meaning
coming back in data rather than prose.

What it does not establish is that any judgement in the completeness ledger is right --
that a chart version is a label rather than a pin, or that five claims are the right
five. Those are readings, and the ledger records each with its reason; this module
checks that they are recorded, consistent, derived where they can be, and carried to
every surface that publishes the claims.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_index import (
    CODE_IDENTITIES,
    COMPLETENESS_PATH,
    FINAL_STATES,
    INDEX_PATH,
    evidence_set_sha256,
    git_blob_id,
    load_index,
    load_ledger,
    release_gate,
)
from tools.evidence_index.__main__ import main as index_main
from tools.evidence_model import REGISTER_PATH, load_register

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = load_register()
NORMALIZATION = load_ledger()
COMPLETENESS = load_ledger(COMPLETENESS_PATH)
INDEX = load_index()
REPORT_PATH = (
    REPO_ROOT / "docs" / "proof" / "testing" / "v1-s5-006-pr2-evidence-completeness.md"
)
RUN_RECORD = "docs/proof/testing/v1-s5-006-pr2-pinned-suite-run.md"

CLAIMS = {claim["claimId"]: claim for claim in REGISTER["claims"]}
RECORDS = {
    record["recordId"]: (claim, record)
    for claim in REGISTER["claims"]
    for record in claim["evidenceRecords"]
}
EXECUTED = {
    record_id: pair
    for record_id, pair in RECORDS.items()
    if pair[1]["execution"]["targetBehaviourExecuted"]
}
IDENTITY = {row["recordId"]: row for row in COMPLETENESS["codeIdentity"]}
BLOCKED_CLAIMS = {blocker["claimId"] for blocker in COMPLETENESS["blockers"]}
BLOCKER_SENTENCE = "Release blocker since V1-S5-006-PR2"


def normalised(text: str) -> str:
    return " ".join(text.split())


def read(path: str | Path) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


@functools.cache
def _git(*arguments: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_bytes(*arguments: str) -> bytes | None:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=REPO_ROOT, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def tracked(pattern: str = "") -> list[str]:
    listed = _git("ls-files", "-z", *([pattern] if pattern else []))
    if listed is None:
        pytest.skip("git is not available to list tracked files")
    return [path for path in listed.split("\0") if path]


# ------------------------------------------------------------ final states


def test_the_ledger_publishes_the_final_states_and_identities_the_tool_knows() -> None:
    assert [row["stateId"] for row in COMPLETENESS["finalStates"]] == list(FINAL_STATES)
    assert [row["identity"] for row in COMPLETENESS["codeIdentityKinds"]] == list(
        CODE_IDENTITIES
    )


def test_every_normalization_finding_has_exactly_one_final_state() -> None:
    """No finding the normalization answered may silently disappear."""
    answered = [finding["findingId"] for finding in NORMALIZATION["findings"]]
    stated = [row["findingId"] for row in COMPLETENESS["findingStates"]]
    assert stated == answered
    by_id = {finding["findingId"]: finding for finding in NORMALIZATION["findings"]}
    for row in COMPLETENESS["findingStates"]:
        assert row["finalState"] in FINAL_STATES, row["findingId"]
        assert row["normalizationDisposition"] == by_id[row["findingId"]]["disposition"]
        assert len(row["verification"]) > 60, row["findingId"]


def test_every_finding_this_verification_made_has_one_final_state() -> None:
    earlier = {finding["findingId"] for finding in NORMALIZATION["findings"]}
    for finding in COMPLETENESS["findings"]:
        assert finding["source"] == "this-verification"
        assert finding["findingId"] not in earlier
        assert finding["finalState"] in FINAL_STATES, finding["findingId"]
        assert len(finding["observation"]) > 60 and len(finding["resolution"]) > 40
        for record_id in finding["recordIds"]:
            assert record_id in RECORDS, record_id
        assert set(finding["claimIds"]) <= set(CLAIMS)


def test_the_migration_audits_findings_are_all_in_exactly_one_category() -> None:
    """Every open item of the migration audit is accounted for, once."""
    audit = {
        finding["findingId"]
        for finding in NORMALIZATION["findings"]
        if finding["source"] == "v1-s5-012-pr2-audit"
    }
    categorised = [
        finding_id
        for category in COMPLETENESS["auditCategories"]
        for finding_id in category["findingIds"]
    ]
    assert Counter(categorised) == Counter(audit)
    for category in COMPLETENESS["auditCategories"]:
        assert category["findingIds"], category["categoryId"]


def test_only_findings_in_the_blocker_state_are_carried_by_a_blocker() -> None:
    states = {
        **{
            row["findingId"]: row["finalState"] for row in COMPLETENESS["findingStates"]
        },
        **{row["findingId"]: row["finalState"] for row in COMPLETENESS["findings"]},
    }
    blocking = {
        finding_id for finding_id, state in states.items() if state == "BLOCKER"
    }
    carried = {
        finding_id
        for blocker in COMPLETENESS["blockers"]
        for finding_id in blocker["findingIds"]
    }
    assert blocking <= carried
    for blocker in COMPLETENESS["blockers"]:
        assert set(blocker["findingIds"]) <= set(states), blocker["blockerId"]
        assert any(states[f] == "BLOCKER" for f in blocker["findingIds"]), blocker


# ------------------------------------------------------------ release gate


def test_the_stated_gate_is_the_one_the_blockers_decide() -> None:
    assert COMPLETENESS["releaseGate"]["decision"] == release_gate(COMPLETENESS)
    assert INDEX["summary"]["releaseGate"] == release_gate(COMPLETENESS)
    assert INDEX["summary"]["releaseBlockers"] == len(COMPLETENESS["blockers"])


def test_any_blocker_fails_the_gate_and_none_passes_it() -> None:
    """The rule, independent of today's blockers."""
    cleared = copy.deepcopy(COMPLETENESS)
    cleared["blockers"] = []
    assert release_gate(cleared) == "complete"
    one = copy.deepcopy(cleared)
    one["blockers"] = (
        [COMPLETENESS["blockers"][0]] if COMPLETENESS["blockers"] else [{}]
    )
    assert release_gate(one) == "incomplete"


def test_the_gate_command_exits_non_zero_while_a_blocker_stands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = index_main(["--gate"])
    printed = capsys.readouterr().out
    if COMPLETENESS["blockers"]:
        assert code == 1
        assert printed.startswith("INCOMPLETE V1-S5-006")
        for blocker in COMPLETENESS["blockers"]:
            assert blocker["blockerId"] in printed
    else:
        assert code == 0


def test_an_incomplete_gate_keeps_its_consumers_blocked() -> None:
    gate = COMPLETENESS["releaseGate"]
    assert gate["storyId"] == "V1-S5-006"
    if gate["decision"] == "incomplete":
        assert gate["consumersBlocked"]
        assert len(gate["reason"]) > 60


@pytest.mark.parametrize(
    "blocker", COMPLETENESS["blockers"], ids=lambda blocker: blocker["blockerId"]
)
def test_every_blocker_names_a_certified_claim_the_run_and_the_alternative(
    blocker: dict[str, Any],
) -> None:
    claim = CLAIMS[blocker["claimId"]]
    assert claim["status"] == "certified"
    held = {record["recordId"] for record in claim["evidenceRecords"]}
    assert set(blocker["recordIds"]) <= held
    for record_id in blocker["recordIds"]:
        assert IDENTITY[record_id]["identity"] == "unidentified", record_id
    required = blocker["requiredEvidence"]
    assert required["authorisation"] and required["mustRecord"]
    assert required["procedure"][0].startswith("Start from a fresh clone")
    assert "git status --porcelain --untracked-files=all" in required["procedure"][1]
    assert required["procedure"][-1] == required["procedure"][1]
    assert len(blocker["alternative"]) > 40


def test_every_blocked_claim_says_so_where_the_claim_is_published() -> None:
    """A blocker the dashboard cannot show is a blocker a reader never meets."""
    stating = {
        claim_id
        for claim_id, claim in CLAIMS.items()
        if BLOCKER_SENTENCE in claim["limitation"]
    }
    assert stating == BLOCKED_CLAIMS
    dashboard = normalised(read("docs/proof/dashboard.md"))
    for claim_id in BLOCKED_CLAIMS:
        sentence = CLAIMS[claim_id]["limitation"].split(BLOCKER_SENTENCE, 1)[1]
        assert normalised(BLOCKER_SENTENCE + sentence) in dashboard, claim_id
    blocked_in_index = {
        claim["claimId"] for claim in INDEX["claims"] if claim["releaseBlockers"]
    }
    assert blocked_in_index == BLOCKED_CLAIMS


# ------------------------------------------------------------- code identity


def _stated(record_id: str) -> bool:
    readings = [
        reading
        for ledger in (NORMALIZATION, COMPLETENESS)
        for reading in ledger["codeRevisions"]
        if reading["recordId"] == record_id
    ]
    return any(
        entry["relation"] == "stated-revision"
        for reading in readings
        for entry in reading["entries"]
    )


def test_every_executed_record_has_exactly_one_identity_reading() -> None:
    assert sorted(IDENTITY) == sorted(EXECUTED)
    assert len(COMPLETENESS["codeIdentity"]) == len(IDENTITY)


@pytest.mark.parametrize("record_id", sorted(EXECUTED))
def test_every_identity_is_derived_rather_than_asserted(record_id: str) -> None:
    """The identity follows from the register, the readings, and the pins."""
    claim, record = EXECUTED[record_id]
    row = IDENTITY[record_id]
    material = set(claim.get("claimMaterialComponents") or [])
    executed = {
        item["componentId"] for item in record["execution"]["executedComponents"]
    }
    repository = {row["componentId"] for row in COMPLETENESS["repositoryComponents"]}
    third_party = {
        row["componentId"]: row["requiredIdentifierKinds"]
        for row in COMPLETENESS["thirdPartyComponents"]
    }
    assert row["claimId"] == claim["claimId"]
    assert row["executedClaimMaterialComponents"] == sorted(executed & material)
    assert row["repositoryCodeAmongThem"] == sorted(executed & material & repository)
    assert (executed & material) <= repository | set(third_party), record_id
    pinned = {pin["recordId"] for pin in COMPLETENESS["contentPins"]}
    if _stated(record_id):
        expected = "stated-revision"
    elif record_id in pinned:
        expected = "content-pinned"
    elif not row["repositoryCodeAmongThem"]:
        expected = "no-repository-code"
        kinds = {version["kind"] for version in record.get("versions", [])}
        for component in executed & material:
            assert set(third_party[component]) <= kinds, (record_id, component)
    else:
        expected = "unidentified"
    assert row["identity"] == expected


def test_a_certified_claim_whose_code_nothing_identifies_is_a_blocker() -> None:
    """The freeze rule itself: no certified claim rests only on unidentified code."""
    for claim in REGISTER["claims"]:
        if claim["status"] != "certified":
            continue
        identities = [
            IDENTITY[record["recordId"]]["identity"]
            for record in claim["evidenceRecords"]
            if record["recordId"] in IDENTITY
        ]
        if identities and set(identities) == {"unidentified"}:
            assert claim["claimId"] in BLOCKED_CLAIMS, claim["claimId"]


def test_every_claim_decision_rests_on_records_the_claim_holds() -> None:
    decided = {row["claimId"]: row for row in COMPLETENESS["claimCodeIdentity"]}
    with_unidentified = {
        IDENTITY[record_id]["claimId"]
        for record_id in IDENTITY
        if IDENTITY[record_id]["identity"] == "unidentified"
    }
    assert set(decided) == with_unidentified
    for claim_id, row in decided.items():
        held = {record["recordId"] for record in CLAIMS[claim_id]["evidenceRecords"]}
        assert set(row["identifiedByRecordIds"]) <= held, claim_id
        for record_id in row["identifiedByRecordIds"]:
            assert IDENTITY[record_id]["identity"] != "unidentified", record_id
        if row["state"] == "identified":
            assert row["identifiedByRecordIds"], claim_id
        if row["state"] == "blocked":
            assert claim_id in BLOCKED_CLAIMS
        if row["state"] == "not-a-release-claim":
            assert CLAIMS[claim_id]["status"] != "certified"
    assert {c for c, row in decided.items() if row["state"] == "blocked"} == (
        BLOCKED_CLAIMS
    )


@pytest.mark.parametrize(
    "pin", COMPLETENESS["contentPins"], ids=lambda pin: pin["recordId"]
)
def test_every_content_pin_is_cited_and_matches_the_repository_history(
    pin: dict[str, Any],
) -> None:
    """The uncommitted part of a run's tree, bound to repository objects by hash."""
    _, record = RECORDS[pin["recordId"]]
    assert pin["source"] in record["evidenceRefs"]
    document = json.loads(read(pin["source"]))
    repository = document
    for key in pin["sourcePointer"].strip("/").split("/"):
        repository = repository[key]
    assert repository["revision"] == pin["baseRevision"]
    assert repository["trackedChangesPresent"] is True
    assert {item["path"]: item["sha256"] for item in pin["files"]} == repository[
        "executedFiles"
    ]
    if _git("cat-file", "-e", f"{pin['filesCommittedIn']}^{{commit}}") is None:
        pytest.skip("the commit that carried the run's files is not in this clone")
    for item in pin["files"]:
        content = _git_bytes("show", f"{pin['filesCommittedIn']}:{item['path']}")
        assert content is not None, item["path"]
        lf = content.replace(b"\r\n", b"\n")
        assert hashlib.sha256(lf).hexdigest() == item["sha256"], item["path"]


@pytest.mark.parametrize(
    "pin", COMPLETENESS["contentPins"], ids=lambda pin: pin["recordId"]
)
def test_the_commit_behind_every_pin_changed_nothing_else_that_decides_a_run(
    pin: dict[str, Any],
) -> None:
    """Read beside the history, the pin reaches the chart and the source as well.

    The commit that carried a run's files sits directly on the run's base, and under
    the code paths compared it changes only what the run hashed and package
    ``__init__`` files. So nothing the run did not hash differs from the base.
    """
    commit = pin["filesCommittedIn"]
    parent = _git("rev-parse", f"{commit}^")
    if parent is None:
        pytest.skip("the commit that carried the run's files is not in this clone")
    assert parent.strip() == pin["baseRevision"]
    changed = _git(
        "diff",
        "--name-only",
        pin["baseRevision"],
        commit,
        "--",
        *pin["codePathsCompared"],
    )
    assert changed is not None
    hashed = {item["path"] for item in pin["files"]}
    other = sorted(set(changed.split()) - hashed)
    assert other == pin["otherFilesTheCommitChanged"]
    for path in other:
        assert path.endswith("/__init__.py"), path
    assert pin["codePathsCompared"] == [
        "charts",
        "src",
        "infra",
        "scripts",
        "tools",
        "deploy",
    ]


# ------------------------------------------------------------ immutability


def test_the_blob_name_is_what_git_calls_the_content(tmp_path: Path) -> None:
    empty = tmp_path / "empty.md"
    empty.write_bytes(b"")
    assert git_blob_id(empty) == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    hello = tmp_path / "hello.md"
    hello.write_bytes(b"hello\r\n")
    assert git_blob_id(hello) == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_every_cited_file_is_the_repository_object_the_index_names() -> None:
    """A release commit is checked against the index by blob name, not by a checkout."""
    listed = _git("ls-files", "-s", "--", "docs/proof")
    if listed is None:
        pytest.skip("git is not available to list staged objects")
    staged = {}
    for line in listed.splitlines():
        meta, path = line.split("\t", 1)
        staged[path] = meta.split()[1]
    for entry in INDEX["records"]:
        for item in entry["evidence"]:
            assert git_blob_id(REPO_ROOT / item["path"]) == item["gitBlob"]
            assert staged.get(item["path"]) == item["gitBlob"], item["path"]


def test_the_evidence_set_digest_covers_every_cited_file() -> None:
    cited = [item for entry in INDEX["records"] for item in entry["evidence"]]
    assert INDEX["summary"]["evidenceSetSha256"] == evidence_set_sha256(cited)
    assert len({item["path"] for item in cited}) == INDEX["summary"]["evidenceFiles"]


def test_no_record_is_left_unmigrated() -> None:
    assert {record["migrationState"] for _, record in RECORDS.values()} == {"migrated"}


def test_every_immutable_identifier_a_record_pins_is_in_a_file_it_cites() -> None:
    for _, record in RECORDS.values():
        cited = normalised("\n".join(read(path) for path in record["evidenceRefs"]))
        for version in record.get("versions", []):
            if version["kind"] in {
                "commit",
                "image-digest",
                "model-revision",
                "artifact-hash",
            }:
                value = version["value"].removeprefix("sha256:")
                assert value in cited, (record["recordId"], version)


# ------------------------------------------------------------ the pinned run


def test_the_pinned_run_names_a_commit_this_history_holds() -> None:
    text = read(RUN_RECORD)
    commits = set(re.findall(r"\b[0-9a-f]{40}\b", text))
    assert len(commits) == 1
    (commit,) = commits
    if _git("cat-file", "-e", f"{commit}^{{commit}}") is None:
        pytest.skip("the pinned commit is not in this clone")
    assert _git("merge-base", "--is-ancestor", commit, "HEAD") is not None
    added = [
        change["record"]
        for change in COMPLETENESS["registerChanges"]
        if change["operation"] == "add-record"
    ]
    assert added
    for record in added:
        assert record["evidenceRefs"] == [RUN_RECORD]
        assert {
            "component": "inferops repository",
            "kind": "commit",
            "value": commit,
        } in (record["versions"])


# ------------------------------------------------- one authoritative state


def test_no_current_consumer_reads_the_superseded_register() -> None:
    assert REGISTER_PATH.name == "claim-evidence-matrix.v1alpha2.json"
    for path in tracked("tools/*.py"):
        if path.startswith("tools/evidence_model/"):
            continue
        assert "claim-evidence-matrix.v1alpha1" not in read(path), path


_SUPERSEDED_TEXT = re.compile(
    r"\b(?:C3\W{1,3}(?:[\w-]+\W+){0,2}?failure|C4\W{1,3}(?:[\w-]+\W+){0,2}?composed)\b",
    re.IGNORECASE,
)


def _superseded(value: Any) -> list[str]:
    """Every place a JSON document pairs a level with a superseded meaning."""
    found: list[str] = []
    if isinstance(value, str):
        if _SUPERSEDED_TEXT.search(value):
            found.append(value[:80])
    elif isinstance(value, dict):
        texts = {item.lower() for item in value.values() if isinstance(item, str)}
        for level, meaning in (("c3", "failure"), ("c4", "composed")):
            named = re.compile(rf"{meaning}(?:\s|$)")
            if level in texts and any(named.match(text) for text in texts):
                found.append(f"{level} {meaning}")
        for item in value.values():
            found.extend(_superseded(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_superseded(item))
    return found


def test_the_superseded_meaning_scan_finds_what_it_is_for() -> None:
    assert _superseded({"notes": "Full C3 failure certification is out of scope."})
    assert _superseded({"levelId": "C4", "name": "Composed"})
    assert _superseded({"levelId": "C3", "name": "Failure and recovery"})
    assert not _superseded({"layerId": "failure-and-resilience", "levelId": "C3"})
    assert not _superseded({"areaId": "reliability", "name": "Failure and recovery"})


def test_no_current_data_file_pairs_a_level_with_a_superseded_meaning() -> None:
    """The prose guard reads Markdown; this reads the data beside it.

    `V1-S5-006-PR2` found a strategy-data note that said full `C3` failure
    certification was out of scope, which the Markdown guard could not see. Dated
    evidence under `docs/proof/` is outside the scan; the superseded register is
    inside it, because it never carried the level names and has nothing to excuse.
    """
    found = []
    for path in tracked("docs/*.json"):
        if path.startswith("docs/proof/"):
            continue
        for hit in _superseded(json.loads(read(path))):
            found.append((path, hit))
    assert not found, found


#: Sentences that described the freeze as still to be decided. The pages under
#: `docs/proof/` that are current rather than dated are checked for them.
UNDECIDED = (
    r"is the open decision",
    r"whether v1 freezes with",
    r"it is the input to that decision",
    r"carried to `?v1-s5-006-pr2`? as the one release blocker",
)
CURRENT_PROOF_PAGES = (
    "docs/proof/v1-evidence-index.md",
    "docs/proof/README.md",
    "docs/proof/dashboard.md",
    "README.md",
    "docs/testing/README.md",
    "docs/testing/claim-evidence-matrix.md",
    "docs/testing/evidence-record-model.md",
)


@pytest.mark.parametrize("path", CURRENT_PROOF_PAGES)
def test_no_current_page_describes_the_freeze_as_undecided(path: str) -> None:
    text = normalised(read(path)).lower()
    assert not [pattern for pattern in UNDECIDED if re.search(pattern, text)]


def test_the_index_page_states_the_gate_and_the_blocker_count() -> None:
    page = normalised(read("docs/proof/v1-evidence-index.md"))
    summary = INDEX["summary"]
    assert f"the release gate is **{summary['releaseGate']}**" in page
    assert f"**{summary['releaseBlockers']} release blockers**" in page
    assert f"`{summary['evidenceSetSha256']}`" in page
    identities = summary["executedRecordsByCodeIdentity"]
    for name in CODE_IDENTITIES:
        assert f"| `{name}` | {identities[name]} |" in page, name


def test_the_readme_states_the_record_count_the_register_holds() -> None:
    """The claim counts were checked and the record count was not.

    `V1-S5-006-PR1` moved the register to 57 records and this change to 60; the
    README's matrix row still said 57 until this change's own sweep found it.
    """
    records = sum(len(claim["evidenceRecords"]) for claim in REGISTER["claims"])
    stated = re.findall(r"\b(\d+) evidence records\b", read("README.md"))
    assert stated, "the README states no record count"
    assert set(stated) == {str(records)}, stated


def test_the_readme_row_states_the_gate() -> None:
    row = next(
        line
        for line in read("README.md").splitlines()
        if line.startswith("| V1 evidence index |")
    )
    assert f"release gate is {INDEX['summary']['releaseGate']}" in row
    assert f"{INDEX['summary']['releaseBlockers']} certified claims" in row


# ------------------------------------------------------------ the report


def test_the_completeness_report_states_what_the_ledger_produces() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    flat = normalised(report)
    states = [
        *[row["finalState"] for row in COMPLETENESS["findingStates"]],
        *[row["finalState"] for row in COMPLETENESS["findings"]],
    ]
    identities = INDEX["summary"]["executedRecordsByCodeIdentity"]
    expected = {
        "Findings given a final state": len(states),
        "Findings the normalization answered": len(COMPLETENESS["findingStates"]),
        "Findings this verification made": len(COMPLETENESS["findings"]),
        **{f"Final state `{state}`": states.count(state) for state in FINAL_STATES},
        "Executed records": len(IDENTITY),
        **{f"Code identity `{name}`": identities[name] for name in CODE_IDENTITIES},
        "Register changes named in the ledger": len(COMPLETENESS["registerChanges"]),
        "Evidence records added": sum(
            1
            for change in COMPLETENESS["registerChanges"]
            if change["operation"] == "add-record"
        ),
        "Claim statuses changed": 0,
        "Record levels changed": 0,
        "Release blockers": len(COMPLETENESS["blockers"]),
    }
    for label, count in expected.items():
        line = next(
            line for line in report.splitlines() if line.startswith(f"| {label} |")
        )
        assert line.split("|")[2].strip() == str(count), (label, count)
    for row in [*COMPLETENESS["findingStates"], *COMPLETENESS["findings"]]:
        assert f"`{row['findingId']}`" in report, row["findingId"]
    for blocker in COMPLETENESS["blockers"]:
        assert f"`{blocker['blockerId']}`" in report, blocker["blockerId"]
        for step in blocker["requiredEvidence"]["procedure"]:
            if step.startswith(("scripts/", "uv run", "helm ")):
                assert step in flat, step
    assert f"**{COMPLETENESS['releaseGate']['decision'].upper()}**" in report


#: A tracked file with one of these suffixes would be a model artifact in history.
MODEL_SUFFIXES = (".gguf", ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".ckpt")


def test_the_report_states_the_largest_committed_object_and_no_model_artifact() -> None:
    """A size is the committed object's, not a checkout's.

    The first commit of this change quoted the largest file's size in a Windows
    checkout, with CRLF line endings, which an independent review caught.
    """
    listed = _git("ls-tree", "-r", "-l", "HEAD")
    if listed is None:
        pytest.skip("git is not available to read the committed tree")
    sizes = []
    for line in listed.splitlines():
        meta, path = line.split("\t", 1)
        size = meta.split()[3]
        if size != "-":
            sizes.append((int(size), path))
    assert not [p for _, p in sizes if p.lower().endswith(MODEL_SUFFIXES)]
    largest, _ = max(sizes)
    stated = f"{largest:,}".replace(",", " ")
    report = normalised(REPORT_PATH.read_text(encoding="utf-8"))
    assert f"committed object is {stated} bytes" in report, stated
    assert "No model artifact is tracked" in report


def test_the_ledgers_and_the_run_record_name_no_private_path() -> None:
    for path in (COMPLETENESS_PATH, INDEX_PATH, REPO_ROOT / RUN_RECORD, REPORT_PATH):
        text = path.read_text(encoding="utf-8")
        assert not re.search(
            r"(?i)(?<![a-z])[a-z]:[\\/]|/users/|scratchpad|planning[\\/]|/tmp/", text
        ), path
