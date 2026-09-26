"""The case study's publication and the V1 evidence freeze, held to what they rest on.

`V1-S5-013-PR1` closed the five release blockers and left the evidence as a
pre-publication freeze candidate. `V1-S5-013-PR2` published the case study through a
fourth ledger and froze the evidence pack. The failures this module exists to prevent
are the ones that make a publication or a freeze look finished when it is not: a
register change that no finding explains, or that moves a status, a statement, or a
level; a correction to a dated record that is really an edit; a carried item left
standing on a current surface; a freeze declared beside an open blocker, or read from a
stale index; a pack digest that does not cover what it says; and a report whose counts,
digests, or gate output have drifted from what the ledger and the index produce.

It also re-derives, from the committed telemetry and recovery record, the two readings
the corrections rest on, so a correction cannot outlive the data it was read from.

What it does not establish is that a correction is the right reading, or that the case
study's prose says what its records say. Those are readings, recorded with their basis
in the ledger and the report.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

import tools.evidence_index.__main__ as index_cli
from tools.evidence_index import (
    CLOSURE_PATH,
    COMPLETENESS_PATH,
    FREEZE_DECISIONS,
    INDEX_PATH,
    LEDGER_PATHS,
    PUBLICATION_PATH,
    content_sha256,
    evidence_freeze,
    evidence_set_sha256,
    load_index,
    load_ledger,
    open_blockers,
    pack_sources,
    release_gate,
    restore_migrated_register,
)
from tools.evidence_model import REGISTER_PATH, load_register

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = load_register()
COMPLETENESS = load_ledger(COMPLETENESS_PATH)
CLOSURE = load_ledger(CLOSURE_PATH)
PUBLICATION = load_ledger(PUBLICATION_PATH)
INDEX = load_index()
SUMMARY = INDEX["summary"]
FREEZE = PUBLICATION["freeze"]
REPORT_PATH = REPO_ROOT / PUBLICATION["reportRef"]
CASE_STUDY = PUBLICATION["caseStudyRef"]

#: The register as `V1-S5-013-PR1` left it: the current one with this ledger undone.
AT_PR1 = restore_migrated_register(REGISTER, PUBLICATION)
REGISTER_REF = REGISTER_PATH.relative_to(REPO_ROOT).as_posix()
CHANGES = PUBLICATION["registerChanges"]
CORRECTIONS = PUBLICATION["recordCorrections"]
FINDINGS = {finding["findingId"]: finding for finding in PUBLICATION["findings"]}

#: The only fields a publication may change. Publishing reconciles wording and the
#: surfaces a reader meets; it is not a place to move a status, a statement, a level,
#: or a citation, and a change to any other field fails here until it is argued for.
ALLOWED_FIELDS = {
    "set-register-field": {"limitations", "nonClaimSurfaces"},
    "set-claim-field": {"doesNotEstablish"},
    "set-record-field": {"results"},
}

#: The dated records `V1-S5-007-PR2` reported as saying more than their own data, each
#: to be answered by a correction beside it rather than an edit.
CARRIED_DATED_RECORDS = {
    "docs/proof/serving/v1-s4-006-pr1-inference-pod-recovery.md",
    "docs/proof/serving/v1-s4-007-pr1-unready-model-recovery.md",
    "docs/proof/environment/v1-s5-001-pr2-clean-clone-run.md",
}

POD_LOSS = "caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load"
RECOVERY = "docs/proof/serving/v1-s4-006-pr1-recovery-record.v1alpha1.json"
TELEMETRY = "docs/proof/serving/v1-s4-006-pr1-telemetry.v1alpha1.json"
RUNTIME_JOB = "inferops-inferops-llm-serving-runtime"

#: Sentences that described the publication or the freeze as still to come. A current
#: surface may not say them; the dated records under `docs/proof/` and the changelog
#: may, because they say what was true when they were written.
NOT_YET_PUBLISHED = (
    r"is (?:the|a) \**pre-publication freeze candidate",
    r"case study[^.]{0,80}has not been written",
    r"has not been written[^.]{0,40}case study",
    r"publishing it belongs to",
    r"\bstill a draft\b",
    r"\bstays a draft\b",
    r"the readme does not link",
    r"\bis not published\b",
    r"final freeze follows",
    r"\bnot yet (?:been )?(?:published|frozen|written)\b",
    r"\b(?:is|remains|stays) unpublished\b",
    r"\bremains? (?:a|the) (?:draft|\**pre-publication)",
    r"\byet to be (?:written|published|frozen)\b",
    r"\bfreeze will follow\b",
    r"\bdoes(?:n't| not) link (?:here|to it|the case study)",
)
CURRENT_SURFACES = (
    "README.md",
    "docs/case-study/v1-engineering-case-study.md",
    "docs/case-study/v1-engineering-case-study.v1alpha1.json",
    "docs/proof/README.md",
    "docs/proof/v1-evidence-index.md",
    "docs/testing/README.md",
    "docs/testing/claim-evidence-matrix.md",
    "docs/testing/claim-evidence-matrix.v1alpha2.json",
    "docs/testing/evidence-record-model.md",
    "docs/testing/test-inventory.md",
    "docs/testing/test-inventory.v1alpha1.json",
)


def normalised(text: str) -> str:
    return " ".join(text.split())


def read(path: str | Path) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _git_bytes(revision: str, path: str) -> bytes | None:
    try:
        return subprocess.run(
            ["git", "show", f"{revision}:{path}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


# -------------------------------------------------------- the register changes


def test_the_ledger_names_what_it_publishes_and_where_its_report_is() -> None:
    assert PUBLICATION["contractVersion"] == "inferops.io/v1alpha1"
    for key in (
        "registerRef",
        "priorLedgerRef",
        "reportRef",
        "indexRef",
        "caseStudyRef",
    ):
        assert (REPO_ROOT / PUBLICATION[key]).is_file(), key
    assert (
        PUBLICATION["priorLedgerRef"] == CLOSURE_PATH.relative_to(REPO_ROOT).as_posix()
    )
    assert LEDGER_PATHS[-1] == PUBLICATION_PATH


@pytest.mark.parametrize("change", CHANGES, ids=lambda change: change["changeId"])
def test_every_change_is_to_a_field_a_publication_may_change(
    change: dict[str, Any],
) -> None:
    assert change["operation"] in ALLOWED_FIELDS, change["changeId"]
    assert change["field"] in ALLOWED_FIELDS[change["operation"]], change["changeId"]
    assert change["findingId"] in FINDINGS, change["changeId"]
    assert len(change["reason"]) > 60, change["changeId"]


def test_undoing_the_ledger_gives_back_the_register_at_the_base_revision() -> None:
    """Publication changed the register only through this ledger's four changes.

    The first version of this test compared the register with itself with the ledger
    undone, which a direct edit outside the ledger survives on both sides, so it
    compared nothing the ledger does not already hold. The register the ledger
    restores must instead equal, as parsed data, the one committed at the base
    revision. Skipped in a clone without that revision, such as a shallow checkout.
    """
    base = _git_bytes(FREEZE["supersedes"]["baseRevision"], REGISTER_REF)
    if base is None:
        pytest.skip("the base revision is not in this clone")
    assert json.loads(base.decode("utf-8")) == AT_PR1


def test_every_finding_is_answered_and_every_answer_names_its_finding() -> None:
    answers = {change["changeId"] for change in CHANGES} | {
        item["correctionId"] for item in CORRECTIONS
    }
    named = set()
    for finding_id, finding in FINDINGS.items():
        assert finding["resolvedBy"], finding_id
        assert len(finding["observation"]) > 80, finding_id
        for answer in finding["resolvedBy"]:
            assert answer in answers or (
                answer.strip(" ./") and (REPO_ROOT / answer).exists()
            ), (finding_id, answer)
            named.add(answer)
        for record_id in finding["recordIds"]:
            assert any(
                record["recordId"] == record_id
                for claim in REGISTER["claims"]
                for record in claim["evidenceRecords"]
            ), record_id
    assert answers <= named, sorted(answers - named)
    for item in CORRECTIONS:
        assert item["findingId"] in FINDINGS, item["correctionId"]
        assert item["correctionId"] in FINDINGS[item["findingId"]]["resolvedBy"]


def test_the_items_the_case_study_verification_carried_are_closed() -> None:
    """The register edits `V1-S5-007-PR2` carried, read from the register itself."""
    register = normalised(json.dumps(REGISTER, ensure_ascii=False)).lower()
    assert "has not been written" not in register
    surfaces = {row["path"]: row for row in REGISTER["nonClaimSurfaces"]}
    assert CASE_STUDY in surfaces
    assert len(surfaces[CASE_STUDY]["reason"]) > 60
    pod = next(claim for claim in REGISTER["claims"] if claim["claimId"] == POD_LOSS)
    carried = normalised(json.dumps(pod, ensure_ascii=False)).lower()
    assert "for the whole outage" not in carried
    assert "at every readiness sample before the replacement was observed ready" in (
        carried
    )


# ---------------------------------------------------------------- corrections


def test_every_carried_dated_record_has_a_correction_beside_it() -> None:
    assert {item["path"] for item in CORRECTIONS} == CARRIED_DATED_RECORDS


@pytest.mark.parametrize("item", CORRECTIONS, ids=lambda item: item["correctionId"])
def test_every_correction_leaves_its_record_as_it_was(item: dict[str, Any]) -> None:
    """The hash in the ledger is the file's content now and at the base revision."""
    assert content_sha256(REPO_ROOT / item["path"]) == item["sha256"]
    base = _git_bytes(FREEZE["supersedes"]["baseRevision"], item["path"])
    if base is None:
        pytest.skip("the base revision is not in this clone")
    assert hashlib.sha256(base.replace(b"\r\n", b"\n")).hexdigest() == item["sha256"]


def _outage() -> tuple[int, int, int]:
    record = json.loads(read(RECOVERY))
    return (
        record["disruption"]["issuedEpochMs"],
        record["timings"]["firstUnservedCompletionEpochMs"],
        record["timings"]["serviceRestoredEpochMs"],
    )


def test_the_readiness_disagreement_was_sampled_only_before_the_outage() -> None:
    """Re-derived: every sample showing a pod Ready and no endpoint ended before it.

    A sample is stamped when its reads start, so its reads end at the stamp plus the
    time they took; each such end must precede the outage, and the next sample must
    be the replacement's: the deleted pod no longer listed, and an endpoint ready.
    """
    _, outage_start, _ = _outage()
    record = json.loads(read(RECOVERY))
    deleted = record["disruption"]["pod"]["name"]
    samples = record["readinessSamples"]
    disagreeing = [
        sample
        for sample in samples
        if sample["runtimePodsReady"] >= 1 and sample["runtimeEndpointsReady"] == 0
    ]
    assert disagreeing
    assert all(deleted in s["runtimePodNames"] for s in disagreeing)
    assert all(s["atEpochMs"] + s["readTookMs"] < outage_start for s in disagreeing)
    following = samples[samples.index(disagreeing[-1]) + 1]
    assert deleted not in following["runtimePodNames"]
    assert following["runtimeEndpointsReady"] >= 1


def _series(series_id: str) -> list[dict[str, Any]]:
    telemetry = json.loads(read(TELEMETRY))
    found = next(s for s in telemetry["series"] if s["seriesId"] == series_id)
    return list(found["result"])


def _seconds_after_delete(series_id: str, job: str) -> list[dict[float, str]]:
    """Each of a job's series in a query, keyed by tenths of a second after the delete."""
    delete, _, _ = _outage()
    found = [
        {round(float(t) - delete / 1000, 1): v for t, v in result["values"]}
        for result in _series(series_id)
        if result["labels"]["job"] == job
    ]
    assert found, f"no {series_id} series for {job}"
    return found


def test_scrape_health_fell_to_zero_for_the_runtime_job_inside_the_outage() -> None:
    """Re-derived: the exact readings the scrape-health correction states.

    Both up series of the runtime job read 0 at 32.3 s and 47.3 s after the delete,
    that job's targets-up ratio read 0 at 47.3 s and 62.3 s and 1 at every other step,
    the API job's ratio read 1 at every step, and all four zero readings fall inside
    the outage. The first version of this test asked only that some step and some
    reading were zero, and treated a missing reading as a zero.
    """
    delete, start, end = _outage()
    up = _seconds_after_delete("serving-runtime-scrape-up", RUNTIME_JOB)
    assert len(up) == 2
    for series in up:
        assert {step for step, value in series.items() if value == "0"} == {32.3, 47.3}
    (runtime,) = _seconds_after_delete("scrape-target-health-by-job", RUNTIME_JOB)
    assert {step for step, value in runtime.items() if value == "0"} == {47.3, 62.3}
    api = _seconds_after_delete(
        "scrape-target-health-by-job", "inferops-inferops-llm-platform-api"
    )
    assert all(value == "1" for series in api for value in series.values())
    outage = ((start - delete) / 1000, (end - delete) / 1000)
    for step in (32.3, 47.3, 62.3):
        assert outage[0] <= step <= outage[1], step


# -------------------------------------------------------------------- freeze


def test_the_freeze_is_declared_over_a_complete_gate() -> None:
    assert FREEZE["decision"] in FREEZE_DECISIONS
    assert release_gate(CLOSURE) == "complete"
    assert open_blockers(COMPLETENESS, CLOSURE) == []
    assert (
        evidence_freeze(CLOSURE, PUBLICATION) == SUMMARY["evidenceFreeze"] == "frozen"
    )
    assert FREEZE["storyId"] == "V1-S5-013"
    assert FREEZE["consumersUnblocked"] == ["V1-S5-008"]
    assert "every other P0" in FREEZE["consumerCondition"]
    assert {row["storyId"] for row in FREEZE["residualConditionsClosed"]} == {
        "V1-S5-006",
        "V1-S5-007",
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda closure, publication: closure["blockers"].append(
            copy.deepcopy(COMPLETENESS["blockers"][0])
        ),
        lambda closure, publication: publication["freeze"].update(
            {"decision": "frozen-enough"}
        ),
        lambda closure, publication: publication.pop("freeze"),
        lambda closure, publication: publication.update(
            {"blockers": copy.deepcopy(COMPLETENESS["blockers"][:1])}
        ),
    ],
    ids=[
        "frozen-over-an-open-blocker",
        "unknown-decision",
        "no-freeze",
        "a-blocker-in-the-publication-ledger",
    ],
)
def test_a_freeze_the_gate_forbids_is_refused(mutate: Any) -> None:
    closure = copy.deepcopy(CLOSURE)
    publication = copy.deepcopy(PUBLICATION)
    mutate(closure, publication)
    with pytest.raises(ValueError):
        evidence_freeze(closure, publication)


def test_no_file_the_pack_covers_states_the_pack_digest() -> None:
    """The pack digest cannot sit inside a file it covers.

    The first version of this test checked the ledger alone, which could not fail: a
    file stating the digest of a pack that includes it is a fixed point. What can go
    wrong is a consumer of the digest being made a cited file or a pack source, which
    would make the digest unstable, and that is what this reads.
    """
    digest = SUMMARY["evidencePackSha256"]
    covered = {item["path"] for item in INDEX["packSources"]} | {
        item["path"] for record in INDEX["records"] for item in record["evidence"]
    }
    stating = sorted(path for path in covered if digest in read(path))
    assert not stating, stating
    assert FREEZE["supersedes"]["evidencePackSha256"] != digest


def test_the_pack_covers_the_cited_files_the_register_and_every_ledger() -> None:
    sources = INDEX["packSources"]
    assert [item["path"] for item in sources] == [
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REGISTER_PATH, *LEDGER_PATHS)
    ]
    assert sources == pack_sources()
    cited = [item for record in INDEX["records"] for item in record["evidence"]]
    assert SUMMARY["evidenceSetSha256"] == evidence_set_sha256(cited)
    assert SUMMARY["evidencePackSha256"] == evidence_set_sha256([*cited, *sources])
    assert SUMMARY["evidencePackSha256"] != SUMMARY["evidenceSetSha256"]


def test_a_change_to_the_register_moves_the_pack_and_not_the_set() -> None:
    """The reason the pack digest exists, shown rather than asserted."""
    cited = [item for record in INDEX["records"] for item in record["evidence"]]
    edited = copy.deepcopy(INDEX["packSources"])
    edited[0]["sha256"] = hashlib.sha256(
        b"a register with one word changed"
    ).hexdigest()
    assert evidence_set_sha256(cited) == SUMMARY["evidenceSetSha256"]
    assert evidence_set_sha256([*cited, *edited]) != SUMMARY["evidencePackSha256"]


def test_the_superseded_candidate_is_the_one_pr1_named_and_recomputes() -> None:
    """The set digest did not move; the pack digest PR1's tree gives is the ledger's."""
    superseded = FREEZE["supersedes"]
    assert superseded["decidedIn"] == "V1-S5-013-PR1"
    assert superseded["evidenceSetSha256"] == SUMMARY["evidenceSetSha256"]
    base = superseded["baseRevision"]
    index_at_base = _git_bytes(base, "docs/proof/v1-evidence-index.v1alpha1.json")
    if index_at_base is None:
        pytest.skip("the base revision is not in this clone")
    at_base = json.loads(index_at_base)
    assert at_base["summary"]["evidenceSetSha256"] == superseded["evidenceSetSha256"]
    cited = [item for record in at_base["records"] for item in record["evidence"]]
    sources = []
    for path in (REGISTER_PATH, *LEDGER_PATHS[:-1]):
        relative = path.relative_to(REPO_ROOT).as_posix()
        data = _git_bytes(base, relative)
        assert data is not None, relative
        digest = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        sources.append({"path": relative, "sha256": digest})
    assert evidence_set_sha256([*cited, *sources]) == superseded["evidencePackSha256"]


def test_the_gate_prints_the_freeze_with_the_index_digests(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = index_cli.main(["--gate"])
    printed = capsys.readouterr().out
    assert code == 0
    assert f"FROZEN   {FREEZE['decidedIn']}: the committed index is current" in printed
    assert f"evidence set   {SUMMARY['evidenceSetSha256']}" in printed
    assert f"evidence pack  {SUMMARY['evidencePackSha256']}" in printed


def test_the_gate_says_so_when_the_pack_is_not_frozen(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exit 0 with a not-frozen ledger means a passing gate, and the output says which."""
    unfrozen = copy.deepcopy(PUBLICATION)
    unfrozen["freeze"]["decision"] = "not-frozen"
    real = load_ledger

    def load(path: Path) -> dict[str, Any]:
        return unfrozen if path == PUBLICATION_PATH else real(path)

    monkeypatch.setattr(index_cli, "load_ledger", load)
    assert index_cli.main(["--gate"]) == 0
    printed = capsys.readouterr().out
    assert "NOT FROZEN" in printed
    assert "FROZEN   " not in printed


def test_the_pack_sources_of_another_root_are_read_under_it(tmp_path: Path) -> None:
    for path in (REGISTER_PATH, *LEDGER_PATHS):
        copied = tmp_path / path.relative_to(REPO_ROOT)
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes(path.read_bytes())
    ledger = tmp_path / PUBLICATION_PATH.relative_to(REPO_ROOT)
    ledger.write_text(ledger.read_text(encoding="utf-8") + " ", encoding="utf-8")
    sources = {item["path"]: item for item in pack_sources(tmp_path)}
    original = {item["path"]: item for item in INDEX["packSources"]}
    assert sources.keys() == original.keys()
    changed = [path for path in sources if sources[path] != original[path]]
    assert changed == [PUBLICATION_PATH.relative_to(REPO_ROOT).as_posix()]


def test_the_gate_refuses_a_freeze_read_from_a_stale_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stale = tmp_path / INDEX_PATH.name
    stale.write_text(
        INDEX_PATH.read_text(encoding="utf-8").replace(
            SUMMARY["evidencePackSha256"], "0" * 64
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(index_cli, "INDEX_PATH", stale)
    assert index_cli.main(["--gate"]) == 1
    printed = capsys.readouterr().out
    assert "MISMATCH" in printed
    assert "FROZEN" not in printed


# ------------------------------------------------------------ current surfaces


@pytest.mark.parametrize("path", CURRENT_SURFACES)
def test_no_current_surface_describes_publication_as_still_to_come(path: str) -> None:
    text = normalised(read(path)).lower()
    found = [pattern for pattern in NOT_YET_PUBLISHED if re.search(pattern, text)]
    assert not found, (path, found)


@pytest.mark.parametrize(
    "sentence",
    [
        "That set is the **pre-publication freeze candidate**, not the final freeze.",
        "The case study this matrix is meant to govern has not been written.",
        "It is not published, and the README does not link here.",
        "The final freeze follows the case study's publication.",
        "It remains the pre-publication freeze candidate.",
        "The case study has not yet been published.",
        "It remains a draft, and the README doesn't link here.",
        "The page is unpublished until the freeze.",
        "The freeze will follow the publication.",
        "The case study has yet to be written.",
    ],
)
def test_the_stale_wording_scan_finds_what_it_is_for(sentence: str) -> None:
    text = normalised(sentence).lower()
    assert any(re.search(pattern, text) for pattern in NOT_YET_PUBLISHED), sentence


# -------------------------------------------------------------------- report


def _table(report: str, label: str) -> str:
    line = next(line for line in report.splitlines() if line.startswith(f"| {label} |"))
    return line.split("|")[2].strip()


def test_the_report_states_what_the_ledger_and_the_index_produce() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    flat = normalised(report)
    expected = {
        "Register changes named in the ledger": len(CHANGES),
        "Corrections written beside dated records": len(CORRECTIONS),
        "Findings answered": len(FINDINGS),
        "Claim statuses changed": 0,
        "Claim statements changed": 0,
        "Record levels changed": 0,
        "Evidence records added or removed": 0,
        "Release blockers open": SUMMARY["releaseBlockers"],
    }
    for label, count in expected.items():
        assert _table(report, label) == str(count), (label, count)
    statuses = SUMMARY["claimsByStatus"]
    levels = SUMMARY["recordsByLevel"]
    for phrase in (
        f"**{SUMMARY['claims']} claims** — {statuses['certified']} certified, "
        f"{statuses['planned']} planned, {statuses['deferred']} deferred, "
        f"{statuses['not-claimed']} not claimed",
        f"**{SUMMARY['records']} evidence records** — {levels['C0']} at `C0`, "
        f"{levels['C1']} at `C1`, {levels['C2']} at `C2`, none at `C3` or `C4`",
        f"`{SUMMARY['evidenceSetSha256']}`",
        f"`{SUMMARY['evidencePackSha256']}`",
        f"`{FREEZE['supersedes']['evidencePackSha256']}`",
    ):
        assert phrase in flat, phrase
    for finding_id in FINDINGS:
        assert f"`{finding_id}`" in report, finding_id
    for item in [*CHANGES, *CORRECTIONS]:
        key = item.get("changeId") or item["correctionId"]
        assert f"`{key}`" in report, key


def test_the_report_quotes_the_gate_it_ran(capsys: pytest.CaptureFixture[str]) -> None:
    index_cli.main(["--gate"])
    printed = capsys.readouterr().out.strip()
    assert printed in REPORT_PATH.read_text(encoding="utf-8")


def test_the_publication_files_name_no_private_path() -> None:
    for path in (PUBLICATION_PATH, REPORT_PATH, INDEX_PATH):
        text = path.read_text(encoding="utf-8")
        assert not re.search(
            r"(?i)(?<![a-z])[a-z]:[\\/]|/users/|scratchpad|planning[\\/]|/tmp/", text
        ), path
