"""The independent review of the second E01 static run, held to the files it read.

A review record names a run and says what a reviewer found in it. It is worth
something only if it is about the run it names: the same files, the same freeze
record, the same executing revision. This suite holds the committed record to those
identities, so a record cannot drift from its subject or be pointed at another run.

It also repeats the one measurement behind the review's claim-material finding. The
finding is that a clause of the register omits a qualifier the frozen criterion
carries. The suite reads the run's generated values and the hand-written values, and
checks both halves: with the qualifier nothing matches, and without it the listed
strings do.

What this suite establishes is that the record describes the committed run and that
its finding can be reproduced from committed files. It does not establish that the
review took place, when, or that it was independent: those are statements of the
record. It does not read the register, so it neither requires nor forbids a
correction of the clause.

Every check reads files from this repository and nothing else. No network, no
cluster, no model, no clock, no randomness.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEWS_DIR = REPO_ROOT / "docs" / "proof" / "experiments" / "v2-e01" / "reviews"
RECORD_PATH = REVIEWS_DIR / "20261003-e01-abc-1-review-1.v1alpha1.json"
PAGE_PATH = REVIEWS_DIR / "20261003-e01-abc-1-review-1.md"

RECORD: dict[str, Any] = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
PAGE = PAGE_PATH.read_text(encoding="utf-8")
SUBJECT: dict[str, Any] = RECORD["subject"]
REVIEW: dict[str, Any] = RECORD["review"]
FINDINGS: list[dict[str, Any]] = RECORD["findings"]
MATERIAL: dict[str, Any] = RECORD["claimMaterialFinding"]

RUN_DIR = REPO_ROOT / SUBJECT["runPath"]
MANIFEST: dict[str, Any] = json.loads(
    (RUN_DIR / "run.v1alpha1.json").read_text(encoding="utf-8")
)
FREEZE: dict[str, Any] = json.loads(
    (REPO_ROOT / SUBJECT["freeze"]["path"]).read_text(encoding="utf-8")
)

SEVERITIES = {"claim-material", "non-material", "observation"}
DISPOSITIONS = {
    "open",
    "recorded-not-corrected",
    "recorded-as-the-sequencing-deviation",
    "no-action",
}
QUALIFIER = "of eight characters or more"
MINIMUM_LENGTH = 8


def content_sha256(path: Path) -> str:
    """The SHA-256 of a file's bytes with every CRLF replaced by LF."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def instant(text: str) -> datetime.datetime:
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def leaves(node: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Every leaf of a mapping, as a dotted path and its value."""
    if not isinstance(node, dict):
        return [(prefix, node)]
    found: list[tuple[str, Any]] = []
    for key, value in node.items():
        found.extend(leaves(value, f"{prefix}.{key}" if prefix else key))
    return found


def at(node: Any, dotted: str) -> Any:
    for key in dotted.split("."):
        node = node[key]
    return node


def literal_matches(minimum: int) -> list[dict[str, str]]:
    """Hand-written strings that contain a generated workload-intent string value."""
    generated = yaml.safe_load(
        (REPO_ROOT / MATERIAL["generatedValues"]).read_text(encoding="utf-8")
    )
    hand_written = yaml.safe_load(
        (REPO_ROOT / MATERIAL["handWrittenValues"]).read_text(encoding="utf-8")
    )
    matches: list[dict[str, str]] = []
    for target in MANIFEST["observations"]["E01-A"]["workloadIntentTargets"]:
        value = at(generated, target)
        if not isinstance(value, str) or len(value) < minimum:
            continue
        for path, text in leaves(hand_written):
            if isinstance(text, str) and value in text:
                matches.append(
                    {
                        "handWrittenPath": path,
                        "handWrittenValue": text,
                        "generatedPath": target,
                        "generatedValue": value,
                    }
                )
    return sorted(matches, key=lambda match: match["handWrittenPath"])


def criterion(identifier: str) -> str:
    for entry in FREEZE["fields"]["acceptanceCriteria"]:
        for item in entry.get("value", []):
            if item["id"] == identifier:
                return str(item["statement"])
    raise AssertionError(f"{identifier} is not in the freeze record")


def test_the_record_declares_its_kind_and_its_page() -> None:
    assert RECORD["apiVersion"] == "inferops.io/v1alpha1"
    assert RECORD["kind"] == "ExperimentResultReview"
    assert RECORD["metadata"]["reviewId"] == RECORD_PATH.name.removesuffix(
        ".v1alpha1.json"
    )
    assert REPO_ROOT / RECORD["metadata"]["page"] == PAGE_PATH


def test_the_review_names_the_run_its_file_name_names() -> None:
    assert RECORD_PATH.name.startswith(SUBJECT["runId"] + "-review-")
    assert RUN_DIR.name == SUBJECT["runId"]
    assert MANIFEST["metadata"]["runId"] == SUBJECT["runId"]
    assert MANIFEST["metadata"]["parts"] == SUBJECT["parts"]


def test_the_review_covers_every_file_of_the_run_and_no_other() -> None:
    committed = {
        path.relative_to(RUN_DIR).as_posix()
        for path in RUN_DIR.rglob("*")
        if path.is_file()
    }
    assert set(SUBJECT["files"]) == committed


@pytest.mark.parametrize("name", sorted(SUBJECT["files"]))
def test_every_reviewed_file_still_has_the_digest_the_review_recorded(
    name: str,
) -> None:
    assert content_sha256(RUN_DIR / name) == SUBJECT["files"][name]


def test_the_review_agrees_with_every_digest_the_manifest_records() -> None:
    for name, digest in MANIFEST["files"].items():
        assert SUBJECT["files"][name] == digest


def test_the_review_names_the_freeze_record_the_run_executed_under() -> None:
    freeze = SUBJECT["freeze"]
    assert freeze["path"] == MANIFEST["metadata"]["freezeRecord"]
    assert freeze["revision"] == MANIFEST["metadata"]["freezeRevision"]
    assert freeze["contentSha256"] == MANIFEST["metadata"]["freezeContentSha256"]
    assert freeze["contentSha256"] == content_sha256(REPO_ROOT / freeze["path"])


def test_the_review_names_the_registry_the_run_recorded() -> None:
    registry = SUBJECT["registry"]
    assert registry == MANIFEST["executionIdentity"]["registry"]
    assert registry["contentSha256"] == content_sha256(REPO_ROOT / registry["path"])


def test_the_review_names_the_revision_and_outcomes_the_run_recorded() -> None:
    assert SUBJECT["executingRevision"] == MANIFEST["executingRevision"]
    assert SUBJECT["outcomes"] == MANIFEST["outcomes"]


def test_the_review_states_a_full_revision_and_a_time_after_the_run() -> None:
    assert re.fullmatch(r"[0-9a-f]{40}", REVIEW["reviewedRevision"])
    assert REVIEW["reviewedRevision"] != SUBJECT["executingRevision"]
    started, finished = instant(REVIEW["startedAt"]), instant(REVIEW["finishedAt"])
    assert instant(MANIFEST["metadata"]["finishedAt"]) < started < finished


def test_the_review_says_how_it_was_done_and_what_limits_its_independence() -> None:
    assert REVIEW["access"] == "read-only"
    assert "tools.experiment_e01 --run" in REVIEW["notExecuted"]
    assert REVIEW["reviewer"]["description"].strip()
    assert REVIEW["reviewer"]["independenceLimits"]
    assert REVIEW["timeSource"].strip()


def test_the_review_records_the_register_it_read_and_does_not_claim_the_order() -> None:
    read = REVIEW["registerAtReviewedRevision"]
    for name in ("register", "ledger", "index"):
        assert re.fullmatch(r"[0-9a-f]{64}", read[name]["contentSha256"])
    conclusions = RECORD["conclusions"]
    assert conclusions["historicalSequencingCompliance"]["verdict"] == "not-established"
    assert conclusions["frozenRunSoundness"]["verdict"] == "no-defect-found"
    assert (
        conclusions["registerStatementCorrectness"]["verdict"]
        == "claim-material-defect-found"
    )
    assert conclusions["rerunJustified"] is False
    assert conclusions["rerunReason"].strip()


def test_the_findings_are_numbered_in_order_with_no_gap() -> None:
    assert [finding["id"] for finding in FINDINGS] == [
        f"F{number}" for number in range(1, len(FINDINGS) + 1)
    ]


@pytest.mark.parametrize("finding", FINDINGS, ids=lambda finding: finding["id"])
def test_every_finding_has_a_known_severity_a_summary_and_a_disposition(
    finding: dict[str, Any],
) -> None:
    assert finding["severity"] in SEVERITIES
    assert finding["disposition"] in DISPOSITIONS
    assert finding["summary"].strip()
    assert finding["owner"] is None or finding["disposition"] == "open"


def test_exactly_one_finding_is_claim_material_and_it_is_open_with_an_owner() -> None:
    material = [f for f in FINDINGS if f["severity"] == "claim-material"]
    assert [finding["id"] for finding in material] == [MATERIAL["finding"]]
    assert material[0]["disposition"] == "open"
    assert material[0]["owner"] == MATERIAL["correctionOwner"]
    assert MATERIAL["correctedHere"] is False
    assert (
        RECORD["conclusions"]["registerStatementCorrectness"]["finding"]
        == (MATERIAL["finding"])
    )


def test_the_criterion_clause_is_the_frozen_one_and_the_claim_clause_omits_the_qualifier() -> (
    None
):
    assert MATERIAL["omittedQualifier"] == QUALIFIER
    assert MATERIAL["criterionClause"] in criterion(MATERIAL["criterion"])
    assert QUALIFIER in MATERIAL["criterionClause"]
    assert QUALIFIER not in MATERIAL["claimClause"]


def test_no_hand_written_string_holds_a_generated_value_of_eight_characters_or_more() -> (
    None
):
    assert literal_matches(MINIMUM_LENGTH) == []
    assert MATERIAL["matchesAtEightCharactersOrMore"] == []


def test_without_the_qualifier_the_listed_hand_written_strings_do_match() -> None:
    recorded = sorted(
        MATERIAL["literalMatches"], key=lambda match: match["handWrittenPath"]
    )
    assert recorded
    assert literal_matches(1) == recorded


def test_the_page_names_the_review_the_run_the_revision_and_every_finding() -> None:
    assert RECORD["metadata"]["reviewId"] in PAGE
    assert SUBJECT["runId"] in PAGE
    assert REVIEW["reviewedRevision"] in PAGE
    assert REVIEW["startedAt"] in PAGE and REVIEW["finishedAt"] in PAGE
    for finding in FINDINGS:
        assert re.search(rf"^\| {finding['id']} \| ", PAGE, flags=re.MULTILINE)
    assert len(re.findall(r"^\| F\d+ \| ", PAGE, flags=re.MULTILINE)) == len(FINDINGS)


def test_the_page_carries_both_clauses_and_every_digest_the_record_holds() -> None:
    flat = " ".join(PAGE.replace("\n> ", " ").split())
    assert criterion(MATERIAL["criterion"]) in flat
    assert MATERIAL["claimClause"] in flat
    for digest in SUBJECT["files"].values():
        assert digest in PAGE
    assert SUBJECT["freeze"]["contentSha256"] in PAGE
    assert SUBJECT["registry"]["contentSha256"] in PAGE


def test_the_page_says_the_claim_is_not_corrected_and_the_order_is_not_established() -> (
    None
):
    flat = " ".join(PAGE.split())
    assert "This change corrects nothing." in flat
    assert "The review-before-register order is not established" in flat
    assert "This review does not repair that order." in flat
    assert MATERIAL["correctionOwner"] in flat
