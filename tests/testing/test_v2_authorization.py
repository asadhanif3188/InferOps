"""The decision that opens a second version, held to the record it supersedes.

`V2-S0-001-PR1` opened a second version for implementation and superseded the
outcome of `V1-S5-009-PR1`'s defer decision. The failures this module exists to
prevent are the ones that let a supersession rewrite history or say more than it
may: the earlier record edited rather than superseded; a trigger or a gate of the
earlier record left out, reordered, or restated with another state; an unmet gate
quietly called met; a moved placement that is not the earlier record's own; a
quotation the earlier record never wrote; a digest that is not the released pack's;
a claim moved by a record that says it moves none; and a current surface that still
says only that the version is deferred.

What it does not establish is that the thesis is the right one, that moving the
rendering is wise, that a gate is treated rightly, or that opening now is the right
call. Those are the reasoning, and the reasoning is a reading.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_index import (
    LEDGER_PATHS,
    POST_RELEASE_PATH,
    RELEASED_DIGESTS,
    content_sha256,
    load_index,
    load_ledger,
    released_register,
)
from tools.evidence_model import load_register

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "docs" / "governance" / "v2-authorization.v1alpha1.json"
DATA: dict[str, Any] = json.loads(DATA_PATH.read_text(encoding="utf-8"))
DECISION = DATA["decision"]
PRIOR = DATA["priorDecision"]
PRIOR_DATA: dict[str, Any] = json.loads(
    (REPO_ROOT / DATA["priorDecisionDataRef"]).read_text(encoding="utf-8")
)
INDEX = load_index()
#: This record reads the pack the earlier one read, the one `v1.0.0` was cut over.
REGISTER = released_register(load_register(), load_ledger(POST_RELEASE_PATH))
CLAIMS = {claim["claimId"]: claim for claim in REGISTER["claims"]}

PRIOR_FINDINGS = {row["findingId"]: row for row in PRIOR_DATA["findings"]}
PRIOR_PROBLEMS = {row["problemId"]: row for row in PRIOR_DATA["problems"]}
PRIOR_GATES = {row["gateId"]: row for row in PRIOR_DATA["entryGates"]}
PRIOR_OPTIONS = {row["optionId"]: row for row in PRIOR_DATA["options"]}

TREATMENTS = ("met", "v2-target", "deferred", "blocker")
BOUNDARIES = {
    "rule-1": "1-a-capability-a-contract-can-name-is-not-a-capability-this-project-provides",
    "rule-2": "2-standing-between-a-caller-and-a-choice-of-providers-is-not-this-projects-job",
    "rule-3": "3-making-one-runtime-work-is-not-the-same-as-engineering-the-runtime",
    "this-record": None,
}

#: A number written beside a unit of time, a percentage, a unit of memory, or a rate:
#: the scan the earlier record is held to. This page quotes no measurement at all.
MEASUREMENT = re.compile(
    r"\b\d+(?:[ .,]\d+)*\s?(?:ms|%|GiB|MiB|GB|MB|seconds?|per second|min|times)(?!\w)"
)
CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
#: A passage in straight or curly double quotes. The independent review of the first
#: commit showed a fabricated passage in curly quotes passing a straight-only pattern.
QUOTATION = re.compile(r"[\"“]([^\"“”]{20,})[\"”]")

#: The note added to the earlier page, pinned here rather than only in the data. A
#: note edited the same way in the page and the data kept every other check green in
#: the independent review; changing it now means changing this module too.
NOTE_SHA256 = "07de225e1992dba92583d5bb558265f97a35d2343e871185d23aa194a29e9bf8"

#: Wording that would overclaim what a second version establishes, or argue from an
#: appeal rather than from evidence, as the earlier record's list does.
FORBIDDEN_PHRASES = (
    "high availability",
    "highly available",
    "production-grade",
    "guarantee",
    "revenue",
    "customers",
    "market demand",
)


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def normalised(text: str) -> str:
    """Whitespace collapsed, and a blockquote's markers dropped with it."""
    return " ".join(re.sub(r"^> ?", "", text, flags=re.MULTILINE).split())


PAGE_TEXT = read(DATA["documentRef"])
PAGE = normalised(PAGE_TEXT)
PRIOR_PAGE_TEXT = read(DATA["priorDecisionRef"]).replace("\r\n", "\n")


def _section(heading: str) -> str:
    """One `## ` section of the page, up to the next one."""
    start = PAGE_TEXT.index(f"\n{heading}\n")
    rest = PAGE_TEXT[start + len(heading) + 2 :]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _tables(section: str) -> list[list[list[str]]]:
    """Every table in a section, each as its body rows, header dropped."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] | None = None
    for line in section.splitlines():
        if line.startswith("|---"):
            continue
        if not line.startswith("| "):
            current = None
            continue
        row = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if current is None:
            current = []
            tables.append(current)
            continue
        current.append(row)
    return tables


def _prose(cell: str) -> str:
    """A table cell as the data writes it, without the page's code spans."""
    return cell.replace("`", "")


def _code(cell: str) -> str:
    match = CODE_SPAN.fullmatch(cell)
    assert match, cell
    return match.group(1)


# ------------------------------------------------------------------ the file


def test_the_data_names_the_files_it_is_held_to() -> None:
    assert (
        DATA["$id"] == "https://inferops.io/governance/v2-authorization.v1alpha1.json"
    )
    assert DATA["contractVersion"] == "inferops.io/v1alpha1"
    for key, value in DATA.items():
        if key.endswith("Ref"):
            assert (REPO_ROOT / value).is_file(), (key, value)


def test_no_file_of_this_decision_is_inside_the_evidence_pack() -> None:
    """A decision that edited a cited file, the register, or a ledger would move the pack."""
    pack = {row["path"] for row in INDEX["packSources"]}
    pack |= {row["path"] for record in INDEX["records"] for row in record["evidence"]}
    for relative in (
        DATA["documentRef"],
        DATA_PATH.relative_to(REPO_ROOT).as_posix(),
        DATA["validationRef"],
        DATA["priorDecisionRef"],
        DATA["priorDecisionDataRef"],
    ):
        assert relative not in pack, relative


# ------------------------------------------------ the earlier record, unedited


def test_the_earlier_record_s_data_is_as_it_merged() -> None:
    """Superseding a decision is a new record; editing the old one is rewriting it."""
    assert (
        content_sha256(REPO_ROOT / DATA["priorDecisionDataRef"]) == PRIOR["dataSha256"]
    )


def test_the_earlier_record_s_page_differs_only_by_the_note() -> None:
    note = PRIOR["noteAdded"]
    assert PRIOR_PAGE_TEXT.count(note) == 1
    title = PRIOR_PAGE_TEXT.split("\n", 1)[0] + "\n\n"
    assert PRIOR_PAGE_TEXT.startswith(title + note), "the note sits under the title"
    original = PRIOR_PAGE_TEXT.replace(note, "", 1)
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
    assert digest == PRIOR["pageSha256WithoutNote"]


def test_the_note_points_here_and_says_what_it_supersedes() -> None:
    note = PRIOR["noteAdded"]
    assert f"**Superseded on {DECISION['decidedOn']}.**" in note
    target = Path(DATA["documentRef"]).name
    assert f"]({target})" in note
    assert f"`{DECISION['decidedIn']}`" in note
    assert "Nothing below is edited." in note
    assert hashlib.sha256(note.encode("utf-8")).hexdigest() == NOTE_SHA256


def test_what_the_data_says_of_the_earlier_record_is_that_record_s() -> None:
    prior = PRIOR_DATA["decision"]
    for key in ("decisionId", "decidedIn", "decidedOn", "outcome", "reviewBy"):
        assert PRIOR[key] == prior[key], key
    assert PRIOR["outcome"] == "defer"
    assert PRIOR["relation"] == "supersedes"
    assert PRIOR["adoptsProblemStatementOf"] in PRIOR_OPTIONS
    assert not PRIOR_OPTIONS[PRIOR["adoptsProblemStatementOf"]]["selected"]


# --------------------------------------------------------------- the outcome


def test_the_outcome_opens_for_implementation_and_follows_the_earlier_record() -> None:
    assert DECISION["outcome"] == "open"
    assert DECISION["authorizes"] == "implementation"
    decided = date.fromisoformat(DECISION["decidedOn"])
    assert date.fromisoformat(PRIOR["decidedOn"]) < decided
    assert decided < date.fromisoformat(PRIOR["reviewBy"]), (
        "a decision on or after the review date is the review itself; say so"
    )


def test_the_page_states_the_outcome_the_dates_and_the_supersession() -> None:
    assert f"Status: **decided: {DECISION['outcome']}**" in PAGE
    assert f"in `{DECISION['decidedIn']}` on {DECISION['decidedOn']}" in PAGE
    assert "**supersedes the outcome**" in PAGE
    target = Path(DATA["priorDecisionRef"]).name
    assert f"]({target})" in PAGE_TEXT
    assert (
        f"which `{PRIOR['decidedIn']}` decided as {PRIOR['outcome']} "
        f"on {PRIOR['decidedOn']}"
    ) in PAGE
    assert "it implements nothing" in PAGE


def test_the_role_that_accepts_it_exists_and_no_authority_is_claimed_for_it() -> None:
    authority = json.loads(read(DATA["authorityRef"]))
    roles = {row["roleId"] for row in authority["roles"]}
    assert DECISION["acceptedBy"]["roleId"] in roles
    assert DECISION["acceptedBy"]["authorityRegisterCovers"] is False
    authorities = {row["authorityId"] for row in authority["authorities"]}
    assert authorities == {
        "adr-decision-ownership",
        "adr-acceptance-and-amendment",
        "claim-evidence-sign-off",
        "v1-release-approval",
    }, "an authority was added; say whether it now covers this decision"


# ------------------------------------------------ the earlier record's triggers


def test_every_earlier_trigger_is_listed_once_in_its_order() -> None:
    listed = [row["triggerId"] for row in PRIOR["triggers"]]
    assert listed == [row["triggerId"] for row in PRIOR_DATA["reviewTriggers"]]
    for row in PRIOR["triggers"]:
        assert isinstance(row["fired"], bool), row["triggerId"]
        assert row["reading"].strip(), row["triggerId"]


def test_the_triggers_that_can_be_read_from_data_agree_with_it() -> None:
    """The date and the contract claims can be read; the other three are a reading."""
    fired = {row["triggerId"]: row["fired"] for row in PRIOR["triggers"]}
    past_review = DECISION["decidedOn"] >= PRIOR["reviewBy"]
    assert fired["the-review-date"] is past_review
    road = PRIOR_GATES["the-road-is-closed-for-one-workload"]["claimIds"]
    closed = all(CLAIMS[claim_id]["status"] == "certified" for claim_id in road)
    assert fired["the-road-closes"] is closed


def test_the_page_lists_every_trigger_with_the_data_s_reading() -> None:
    tables = _tables(_section("## Why now, when nothing new has been measured"))
    # The trigger table and the digest table, and nothing else: the first commit read
    # only the first table, and a contradicting one beside it passed the review.
    assert len(tables) == 2, len(tables)
    rows = tables[0]
    assert [_code(row[0]) for row in rows] == [
        row["triggerId"] for row in PRIOR["triggers"]
    ]
    for row, entry in zip(rows, PRIOR["triggers"], strict=True):
        assert row[1] == ("yes" if entry["fired"] else "no"), entry["triggerId"]
        assert row[2] == entry["reading"].rstrip("."), entry["triggerId"]


# ------------------------------------------------ the earlier record's gates


def test_every_earlier_gate_is_classified_once_in_its_order() -> None:
    assert [row["gateId"] for row in DATA["priorGates"]] == [
        row["gateId"] for row in PRIOR_DATA["entryGates"]
    ]
    assert tuple(DATA["gateTreatments"]) == TREATMENTS
    for row in DATA["priorGates"]:
        assert row["priorState"] == PRIOR_GATES[row["gateId"]]["state"], row["gateId"]
        assert row["treatment"] in TREATMENTS, row["gateId"]
        assert row["how"].strip(), row["gateId"]


def test_no_gate_unmet_then_is_called_met() -> None:
    """The one move this record may not make: closing a gate by reclassifying it."""
    for row in DATA["priorGates"]:
        if row["priorState"] == "unmet":
            assert row["treatment"] != "met", row["gateId"]
        else:
            assert row["treatment"] == "met", row["gateId"]


def test_the_road_gate_is_a_target_until_its_claims_are_certified() -> None:
    (row,) = [
        gate
        for gate in DATA["priorGates"]
        if gate["gateId"] == "the-road-is-closed-for-one-workload"
    ]
    claims = PRIOR_GATES[row["gateId"]]["claimIds"]
    assert row["treatment"] == "v2-target"
    assert all(CLAIMS[claim_id]["status"] == "planned" for claim_id in claims)


def test_the_page_tabulates_every_gate_and_counts_the_unmet_ones() -> None:
    section = _section("## The earlier record's entry gates, and how each is treated")
    gates, prerequisites = _tables(section)
    # Every column, the prose included: the first commit compared three of four, and
    # the review changed the page's "How" cells alone without a failure.
    assert [
        (_code(row[0]), _code(row[1]), _code(row[2]), _prose(row[3])) for row in gates
    ] == [
        (row["gateId"], row["priorState"], row["treatment"], row["how"].rstrip("."))
        for row in DATA["priorGates"]
    ]
    unmet = sum(1 for row in DATA["priorGates"] if row["priorState"] == "unmet")
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    total = words[len(DATA["priorGates"])].lower()
    assert (
        f"{words[unmet]} of the {total} were unmet when the earlier record was decided"
    ) in normalised(section)
    assert [
        (_code(row[0]), row[1], _code(row[2]), _prose(row[3])) for row in prerequisites
    ] == [
        (row["prerequisiteId"], row["quoted"], row["treatment"], row["how"].rstrip("."))
        for row in DATA["priorPrerequisites"]
    ]


def test_every_prerequisite_is_quoted_from_the_revise_option() -> None:
    written = PRIOR_OPTIONS["revise"]["prerequisites"]
    for row in DATA["priorPrerequisites"]:
        assert row["quoted"] in written, row["prerequisiteId"]
        assert row["treatment"] in TREATMENTS, row["prerequisiteId"]
        assert row["treatment"] != "met", row["prerequisiteId"]
        if row["treatment"] == "blocker":
            assert row["blocks"].strip(), "a blocker names the work it blocks"
            assert f"Blocks {row['blocks']}" in row["how"], row["prerequisiteId"]


# ------------------------------------------------------- the moved placement


@pytest.mark.parametrize("move", DATA["scopeMoves"], ids=lambda row: row["moveId"])
def test_the_moved_placement_is_the_earlier_record_s_own(move: dict) -> None:
    problem = PRIOR_PROBLEMS[move["problemId"]]
    assert move["from"] == problem["belongs"]["answer"]
    assert move["from"] != move["to"]
    assert move["claimIds"] == problem["claimsThatCouldMove"]
    assert move["claimIds"] == PRIOR_GATES[move["gateId"]]["claimIds"]
    for claim_id in move["claimIds"]:
        assert CLAIMS[claim_id]["status"] == "planned", claim_id
    assert move["reason"].strip() and move["consequence"].strip()


def test_only_one_placement_moves_and_the_page_says_so() -> None:
    assert len(DATA["scopeMoves"]) == 1
    section = normalised(_section("## Contract-to-deployment rendering moves into V2"))
    (move,) = DATA["scopeMoves"]
    assert f"placed `{move['problemId']}` in `{move['from']}`" in section
    for claim_id in move["claimIds"]:
        assert f"`{claim_id}`" in section, claim_id
    assert "This record moves no other placement." in section


# --------------------------------------------------------------- the thesis


def test_the_thesis_starts_from_the_earlier_record_s_findings_and_words() -> None:
    thesis = DATA["thesis"]
    for finding_id in thesis["motivatingFindingIds"]:
        assert finding_id in PRIOR_FINDINGS, finding_id
    revise = PRIOR_OPTIONS[PRIOR["adoptsProblemStatementOf"]]
    assert thesis["priorStatement"] in revise["summary"]
    for finding_id in revise["motivatingFindingIds"]:
        assert finding_id in thesis["motivatingFindingIds"], finding_id
    assert f"**{thesis['name'].capitalize()}**: {thesis['statement']}." in PAGE
    assert f"{thesis['name']}** — {thesis['statement']}." in PAGE


def test_the_page_says_what_v1_did_and_did_not_measure_of_release_change() -> None:
    """The first commit said V1 never rolled a bad release back. It had, twice."""
    section = normalised(_section("## The thesis"))
    for claim_id in DATA["thesis"]["relatedClaimIds"]:
        assert CLAIMS[claim_id]["status"] == "certified", claim_id
        levels = sorted(
            {row["evidenceLevel"] for row in CLAIMS[claim_id]["evidenceRecords"]}
        )
        count = len(CLAIMS[claim_id]["evidenceRecords"])
        assert f"`{claim_id}` is certified at `{'`, `'.join(levels)}`" in section
        assert f"on {['no', 'one', 'two', 'three'][count]} runs" in section, claim_id
    assert "What V1 never measured is what a caller under load meets" in section
    assert "Widening the thesis to that is this record's judgment, not a V1 result" in (
        section
    )
    for finding_id in DATA["thesis"]["motivatingFindingIds"]:
        assert f"`{finding_id}`" in section, finding_id


def test_every_quotation_on_the_page_is_the_earlier_page_s_words() -> None:
    """A supersession that misquotes what it supersedes argues with a record that
    does not exist."""
    earlier = normalised(PRIOR_PAGE_TEXT).replace("“", '"').replace("”", '"')
    quotations = QUOTATION.findall(PAGE)
    assert len(quotations) >= 5
    for quoted in quotations:
        assert quoted in earlier, quoted


# ------------------------------------------------------------ the evidence basis


def test_the_basis_is_the_released_pack() -> None:
    basis = DATA["evidenceBasis"]
    released = INDEX["summary"]["releasedPack"]
    assert basis["pack"] == "released"
    assert basis["evidenceSetSha256"] == released["evidenceSetSha256"]
    assert basis["evidencePackSha256"] == released["evidencePackSha256"]
    assert {
        "evidenceSetSha256": basis["evidenceSetSha256"],
        "evidencePackSha256": basis["evidencePackSha256"],
    } == RELEASED_DIGESTS[released["tag"]]
    prior = PRIOR_DATA["evidenceBasis"]
    assert basis["evidencePackSha256"] == prior["evidencePackSha256"]
    for digest in (basis["evidenceSetSha256"], basis["evidencePackSha256"]):
        assert f"`{digest}`" in PAGE


def test_the_decision_moves_no_claim_and_no_ledger_names_it() -> None:
    assert DATA["claimsMoved"] == []
    for path in LEDGER_PATHS:
        assert DECISION["decidedIn"] not in path.read_text(encoding="utf-8"), path.name


# ------------------------------------------------------------- the boundaries


@pytest.mark.parametrize("row", DATA["nonGoals"], ids=lambda row: row["nonGoalId"])
def test_every_non_goal_cites_a_boundary_that_exists(row: dict) -> None:
    assert row["boundary"] in BOUNDARIES, row["nonGoalId"]
    anchor = BOUNDARIES[row["boundary"]]
    if anchor is None:
        return
    link = f"](../architecture/project-boundaries.md#{anchor})"
    (line,) = [
        line for line in PAGE_TEXT.splitlines() if f"`{row['nonGoalId']}`" in line
    ]
    assert link in line, row["nonGoalId"]


def test_the_page_tabulates_every_non_goal() -> None:
    (rows,) = _tables(_section("## What V2 does not take on"))
    assert [_code(row[0]) for row in rows] == [
        row["nonGoalId"] for row in DATA["nonGoals"]
    ]
    for row, entry in zip(rows, DATA["nonGoals"], strict=True):
        assert row[1] == entry["nonGoal"].rstrip("."), entry["nonGoalId"]


# --------------------------------------------------------------- the page


def test_the_page_publishes_every_identifier_the_data_holds() -> None:
    spans = set(CODE_SPAN.findall(PAGE_TEXT))
    identifiers = (
        {row["triggerId"] for row in PRIOR["triggers"]}
        | {row["gateId"] for row in DATA["priorGates"]}
        | {row["prerequisiteId"] for row in DATA["priorPrerequisites"]}
        | {row["nonGoalId"] for row in DATA["nonGoals"]}
        | {row["triggerId"] for row in DATA["reopenTriggers"]}
        | set(DATA["gateTreatments"])
        | {row["surfaceId"] for row in DATA["describesTheRepositoryBeforeThisDecision"]}
    )
    missing = sorted(identifiers - spans)
    assert not missing, missing


def test_the_page_quotes_no_measurement_and_no_forbidden_phrase() -> None:
    assert not MEASUREMENT.findall(PAGE), MEASUREMENT.findall(PAGE)
    lowered = PAGE.lower()
    found = [
        phrase for phrase in FORBIDDEN_PHRASES if re.search(rf"\b{phrase}\b", lowered)
    ]
    assert not found, found


def _slug(heading: str) -> str:
    """GitHub's heading anchor, approximately, as the earlier record's test has it."""
    text = heading.strip().lower().replace("`", "")
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def _anchors(text: str) -> set[str]:
    return {
        _slug(line.lstrip("#"))
        for line in text.splitlines()
        if re.match(r"^#{1,6} ", line)
    }


def test_every_fragment_the_page_links_resolves_to_a_heading() -> None:
    """The document-link suite drops fragments; a decision's citations need them."""
    checked = 0
    for target in LINK.findall(PAGE_TEXT):
        if "#" not in target or target.startswith(("http://", "https://")):
            continue
        path, fragment = target.split("#", 1)
        source = (
            PAGE_TEXT
            if not path
            else read(
                (REPO_ROOT / DATA["documentRef"])
                .parent.joinpath(path)
                .resolve()
                .relative_to(REPO_ROOT)
                .as_posix()
            )
        )
        assert fragment in _anchors(source), target
        checked += 1
    assert checked >= 5


# ------------------------------------------------------- the current surfaces


def test_the_readme_and_the_governance_table_say_the_version_is_open() -> None:
    """Both still link the earlier record, which its own test requires, and now this."""
    readme = read("README.md")
    roadmap = readme.split("\n## Roadmap\n", 1)[1].split("\n## ", 1)[0]
    assert "](docs/governance/v2-authorization.md)" in roadmap
    assert "](docs/governance/v2-investment-decision.md)" in roadmap
    assert "No second version yet." not in roadmap
    governance = read("docs/governance/repository.md")
    (row,) = [
        line for line in governance.splitlines() if line.startswith("| Next version |")
    ]
    assert "](v2-authorization.md)" in row
    assert "](v2-investment-decision.md)" in row
    assert "[Deferred]" not in row
    # The roadmap's prose is the README's claim about this record; it may not say a
    # claim moved while the data moves none.
    assert DATA["claimsMoved"] == []
    assert "The decision adds no claim and moves none." in normalised(roadmap)


def test_every_surface_left_standing_still_says_what_the_page_says_it_says() -> None:
    """A tripwire. If the case study is re-published, this section must change too."""
    section = _section(
        "## Where the published evidence still describes the repository "
        "before this decision"
    )
    for surface in DATA["describesTheRepositoryBeforeThisDecision"]:
        assert surface["says"] in normalised(read(surface["path"])), surface[
            "surfaceId"
        ]
        assert f"`{surface['surfaceId']}`" in section, surface["surfaceId"]


def test_the_validation_record_links_the_page() -> None:
    record = read(DATA["validationRef"])
    assert "](../../governance/v2-authorization.md)" in record
