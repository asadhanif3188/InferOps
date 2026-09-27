"""The decision whether a second version proceeds, held to the evidence it cites.

`V1-S5-009-PR1` recorded a proceed, revise, or defer decision on a second version,
made from V1's evidence rather than from a plan. The failures this module exists to
prevent are the ones that let such a decision say more than its evidence: an outcome
that disagrees with its own entry gates; a finding whose claim has since changed
status or level; a record cited for a claim that does not cite it; a claim V1 does
not certify that the decision silently leaves out; an option compared on fewer
fields than the others; a figure no record reads back; a review date that never
arrives; and a surface that still says the decision has not been made, corrected
quietly or left standing without the page saying so.

What it does not establish is that a problem is correctly judged important, that an
experiment is feasible, that a boundary is drawn in the right place, or that
deferring is the right call. Those are the reasoning, and the reasoning is a reading.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_index import (
    POST_RELEASE_PATH,
    load_index,
    load_ledger,
    released_register,
)
from tools.evidence_model import load_register

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = (
    REPO_ROOT / "docs" / "governance" / "v2-investment-decision.v1alpha1.json"
)
DATA: dict[str, Any] = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
DECISION = DATA["decision"]
INDEX = load_index()
#: The decision reads the pack `v1.0.0` was cut over: the counts and digests the index
#: recomputes with the post-release ledger undone, and the register as released.
SUMMARY = {**INDEX["summary"], **INDEX["summary"]["releasedPack"]}
CURRENT_REGISTER = load_register()
REGISTER = released_register(CURRENT_REGISTER, load_ledger(POST_RELEASE_PATH))
CLAIMS = {claim["claimId"]: claim for claim in REGISTER["claims"]}
CASE_STUDY_DATA = json.loads(
    (REPO_ROOT / DATA["caseStudyDataRef"]).read_text(encoding="utf-8")
)

FINDINGS = {row["findingId"]: row for row in DATA["findings"]}
PROBLEMS = {row["problemId"]: row for row in DATA["problems"]}
GATES = {row["gateId"]: row for row in DATA["entryGates"]}
OPTIONS = {row["optionId"]: row for row in DATA["options"]}

OUTCOMES = ("proceed", "revise", "defer")
#: The options that open a version. Either one while a gate is unmet is the outcome
#: disagreeing with the conditions the record states for it.
OPENS_A_VERSION = frozenset({"proceed", "revise"})
GATE_STATES = ("met", "met-on-merge", "unmet")
ANSWERS = ("yes", "partly", "no")
PLACEMENTS = (
    "inferops-v1-completion",
    "inferops-later-version",
    "split",
    "elsewhere",
)
REACHABLE_LEVELS = ("C0", "C1", "C2", "C3")
REQUIRED_OPTION_FIELDS = (
    "summary",
    "problemAddressed",
    "motivation",
    "expectedEvidence",
    "prerequisites",
    "costsAndRisks",
    "remainsUnproven",
    "overlap",
    "why",
)

#: A number written beside a unit of time, a percentage, a unit of memory, or a rate:
#: the same scan the release notes are held to.
MEASUREMENT = re.compile(
    r"\b\d+(?:[ .,]\d+)*\s?(?:ms|%|GiB|MiB|GB|MB|seconds?|per second|min|times)(?!\w)"
)
CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")

#: Wording that would assume a second version's scope, or put a reason that is not an
#: engineering one in the place of evidence. The page may deny demand; it may not
#: argue from it.
FORBIDDEN_PHRASES = (
    "v2 will",
    "the second version will",
    "v2 includes",
    "v2 scope includes",
    "revenue",
    "customers",
    "market demand",
)


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def normalised(text: str) -> str:
    return " ".join(text.split())


PAGE_TEXT = read(DATA["documentRef"])
PAGE = normalised(PAGE_TEXT)


def _section(heading: str) -> str:
    """One `## ` section of the page, up to the next one."""
    start = PAGE_TEXT.index(f"\n{heading}\n")
    rest = PAGE_TEXT[start + len(heading) + 2 :]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if not line.startswith("| ") or line.startswith("|---"):
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows[1:]


def _code(cell: str) -> str:
    match = CODE_SPAN.fullmatch(cell)
    assert match, cell
    return match.group(1)


def _record_levels(claim_id: str) -> list[str]:
    return sorted({row["evidenceLevel"] for row in CLAIMS[claim_id]["evidenceRecords"]})


# ------------------------------------------------------------------ the file


def test_the_data_names_the_files_it_is_held_to() -> None:
    assert DATA["$id"] == (
        "https://inferops.io/governance/v2-investment-decision.v1alpha1.json"
    )
    assert DATA["contractVersion"] == "inferops.io/v1alpha1"
    for key, value in DATA.items():
        if key.endswith("Ref"):
            assert (REPO_ROOT / value).is_file(), (key, value)


def test_no_decision_file_is_inside_the_evidence_pack() -> None:
    """A decision that edited a cited file, the register, or a ledger would move the pack."""
    pack = {row["path"] for row in INDEX["packSources"]}
    pack |= {row["path"] for record in INDEX["records"] for row in record["evidence"]}
    assert DATA["documentRef"] not in pack
    assert DECISION_PATH.relative_to(REPO_ROOT).as_posix() not in pack


# --------------------------------------------------------------- the outcome


def test_exactly_one_option_is_selected_and_it_is_the_outcome() -> None:
    assert DECISION["outcome"] in OUTCOMES
    assert sorted(OPTIONS) == sorted(OUTCOMES)
    selected = [row["optionId"] for row in DATA["options"] if row["selected"]]
    assert selected == [DECISION["outcome"]]


@pytest.mark.parametrize("option", DATA["options"], ids=lambda row: row["optionId"])
def test_every_option_states_every_field_a_comparison_needs(option: dict) -> None:
    for field in REQUIRED_OPTION_FIELDS:
        assert option[field].strip(), (option["optionId"], field)
    for finding_id in option["motivatingFindingIds"]:
        assert finding_id in FINDINGS, finding_id
    for claim_id in option["claimsThatCouldStrengthen"]:
        assert claim_id in CLAIMS, claim_id


def test_the_selected_option_rests_on_findings() -> None:
    """An outcome no finding motivates rests on something other than evidence."""
    assert OPTIONS[DECISION["outcome"]]["motivatingFindingIds"]


def test_no_option_that_opens_a_version_is_selected_while_a_gate_is_unmet() -> None:
    unmet = [row["gateId"] for row in DATA["entryGates"] if row["state"] == "unmet"]
    if DECISION["outcome"] in OPENS_A_VERSION:
        assert not unmet, unmet


def test_the_page_states_the_outcome_the_dates_and_which_option_is_selected() -> None:
    assert f"Status: **decided: {DECISION['outcome']}**" in PAGE
    assert f"in `{DECISION['decidedIn']}` on {DECISION['decidedOn']}" in PAGE
    assert f"Review by **{DECISION['reviewBy']}**" in PAGE
    for option_id in OUTCOMES:
        section = PAGE_TEXT.split(f"\n### {option_id.capitalize()}\n", 1)[1]
        section = section.split("\n### ", 1)[0].split("\n## ", 1)[0]
        assert ("**Selected.**" in section) is OPTIONS[option_id]["selected"], option_id


def test_the_review_follows_the_decision_within_six_months() -> None:
    """A deferral without a date it is looked at again is an abandonment."""
    decided = date.fromisoformat(DECISION["decidedOn"])
    review = date.fromisoformat(DECISION["reviewBy"])
    assert decided < review <= decided + timedelta(days=183)
    assert DATA["reviewTriggers"][0]["triggerId"] == "the-review-date"


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


# ------------------------------------------------------------------ the gates


@pytest.mark.parametrize("gate", DATA["entryGates"], ids=lambda row: row["gateId"])
def test_every_gate_has_a_state_evidence_and_real_claims(gate: dict) -> None:
    assert gate["state"] in GATE_STATES
    assert gate["gate"].strip() and gate["evidence"].strip()
    for claim_id in gate["claimIds"]:
        assert claim_id in CLAIMS, claim_id


def test_the_page_lists_every_gate_with_the_state_the_data_holds() -> None:
    rows = _table_rows(_section("## Entry gates"))
    # A list, not a dict: a duplicated or contradictory row must fail rather than
    # collapse into whichever copy comes last. The independent review of the first
    # commit showed the dict form accepting exactly that.
    published = [(_code(row[0]), _code(row[2])) for row in rows]
    assert published == [(row["gateId"], row["state"]) for row in DATA["entryGates"]]
    unmet = sum(1 for row in GATES.values() if row["state"] == "unmet")
    words = {0: "None", 1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    verb = "is" if unmet == 1 else "are"
    assert f"{words[unmet]} {verb} unmet today." in PAGE


def test_the_gates_that_are_claims_agree_with_the_register() -> None:
    """A gate stated unmet on a claim the register has since certified is stale."""
    road = GATES["the-road-is-closed-for-one-workload"]
    certified = all(CLAIMS[c]["status"] == "certified" for c in road["claimIds"])
    assert (road["state"] == "met") is certified


# --------------------------------------------------------------- the findings


def _cited_claims() -> set[str]:
    cited = {c["claimId"] for row in DATA["findings"] for c in row["claims"]}
    for row in DATA["problems"]:
        cited |= set(row["claimsThatCouldMove"])
    for row in DATA["entryGates"]:
        cited |= set(row["claimIds"])
    for row in DATA["options"]:
        cited |= set(row["claimsThatCouldStrengthen"])
    cited |= {row["claimId"] for row in DATA["uncertifiedClaims"]}
    cited.add(DATA["release"]["registerClaimId"])
    return cited


def test_every_claim_the_decision_cites_is_a_register_row() -> None:
    missing = sorted(_cited_claims() - set(CLAIMS))
    assert not missing, missing


@pytest.mark.parametrize("finding", DATA["findings"], ids=lambda row: row["findingId"])
def test_every_finding_states_the_register_s_status_and_levels(finding: dict) -> None:
    for claim in finding["claims"]:
        row = CLAIMS[claim["claimId"]]
        assert claim["status"] == row["status"], claim["claimId"]
        assert claim["recordLevels"] == _record_levels(claim["claimId"]), claim[
            "claimId"
        ]


@pytest.mark.parametrize("finding", DATA["findings"], ids=lambda row: row["findingId"])
def test_every_record_a_finding_points_to_is_cited_by_its_own_claims(
    finding: dict,
) -> None:
    claim_ids = {claim["claimId"] for claim in finding["claims"]}
    cited = {
        row["path"]
        for record in INDEX["records"]
        if record["claimId"] in claim_ids
        for row in record["evidence"]
    }
    for relative in finding["recordRefs"]:
        assert (REPO_ROOT / relative).is_file(), relative
        assert relative in cited, (finding["findingId"], relative)


def test_the_page_states_every_finding_with_its_claims_and_their_status() -> None:
    rows = _table_rows(_section("## What V1 found that bears on it"))
    assert [_code(row[0]) for row in rows] == list(FINDINGS)
    for row in rows:
        finding = FINDINGS[_code(row[0])]
        for claim in finding["claims"]:
            status = claim["status"].replace("-", " ")
            levels = (
                ", ".join(f"`{level}`" for level in claim["recordLevels"]) or "none"
            )
            assert f"`{claim['claimId']}` {status}, {levels}" in row[2], (
                finding["findingId"],
                claim["claimId"],
            )
        for relative in finding["recordRefs"]:
            target = Path(relative).relative_to("docs").as_posix()
            assert f"](../{target})" in row[3], (finding["findingId"], relative)
        if not finding["recordRefs"]:
            assert row[3].startswith("none"), finding["findingId"]


# --------------------------------------------------------------- the problems


@pytest.mark.parametrize("problem", DATA["problems"], ids=lambda row: row["problemId"])
def test_every_problem_answers_the_three_questions(problem: dict) -> None:
    for question in ("important", "feasibleNow"):
        assert problem[question]["answer"] in ANSWERS, question
        assert problem[question]["reason"].strip(), question
    assert problem["belongs"]["answer"] in PLACEMENTS
    assert problem["belongs"]["reason"].strip()
    assert problem["expectedLevel"] in REACHABLE_LEVELS, (
        "C4 needs organizational production operation, which this project has none of"
    )
    assert problem["findingIds"]
    for finding_id in problem["findingIds"]:
        assert finding_id in FINDINGS, finding_id
    assert problem["remainsUnproven"].strip()


def test_no_problem_lists_as_movable_a_claim_the_register_calls_unreachable() -> None:
    """The first draft listed one, and its own next field said it could not move."""
    for problem in DATA["problems"]:
        for claim_id in problem["claimsThatCouldMove"]:
            assert "not reachable" not in CLAIMS[claim_id]["limitation"], (
                problem["problemId"],
                claim_id,
            )


def test_every_finding_bears_on_a_problem() -> None:
    used = {finding for row in DATA["problems"] for finding in row["findingIds"]}
    assert used == set(FINDINGS), sorted(set(FINDINGS) - used)


def test_the_page_tabulates_every_problem_with_its_answers() -> None:
    section = _section("## The problems they expose, and three questions for each")
    rows = _table_rows(section.split("\n\n**", 1)[0])
    assert [_code(row[0]) for row in rows] == list(PROBLEMS)
    for row in rows:
        problem = PROBLEMS[_code(row[0])]
        assert row[1] == problem["important"]["answer"], problem["problemId"]
        assert row[2] == problem["feasibleNow"]["answer"], problem["problemId"]
        assert _code(row[3]) == problem["belongs"]["answer"], problem["problemId"]
        assert _code(row[4]) == problem["expectedLevel"], problem["problemId"]
        assert f"**`{problem['problemId']}`.**" in PAGE, problem["problemId"]


# ------------------------------------------------- every uncertified claim


def test_every_claim_v1_does_not_certify_is_placed_or_says_why() -> None:
    """Leaving a gap out of the decision would decide around it without saying so."""
    uncertified = {
        claim_id: row["status"]
        for claim_id, row in CLAIMS.items()
        if row["status"] != "certified"
    }
    placed = {row["claimId"]: row for row in DATA["uncertifiedClaims"]}
    assert set(placed) == set(uncertified)
    targets = set(PROBLEMS) | set(GATES)
    for claim_id, row in placed.items():
        assert row["status"] == uncertified[claim_id], claim_id
        for target in row["placedIn"]:
            assert target in targets, (claim_id, target)
        if not row["placedIn"]:
            assert row["whyNotPlaced"].strip(), claim_id


def test_the_page_places_every_uncertified_claim_as_the_data_does() -> None:
    rows = _table_rows(
        _section("## Every claim V1 does not certify, and where this decision puts it")
    )
    placed = {row["claimId"]: row for row in DATA["uncertifiedClaims"]}
    assert [_code(row[0]) for row in rows] == [
        row["claimId"] for row in DATA["uncertifiedClaims"]
    ]
    for row in rows:
        entry = placed[_code(row[0])]
        assert row[1] == entry["status"], entry["claimId"]
        if entry["placedIn"]:
            assert CODE_SPAN.findall(row[2]) == entry["placedIn"], entry["claimId"]
        else:
            assert row[2].startswith("nowhere:"), entry["claimId"]


# ------------------------------------------------------------ the evidence basis


def test_the_basis_is_the_frozen_pack_the_index_states() -> None:
    basis = DATA["evidenceBasis"]
    assert SUMMARY["evidenceFreeze"] == basis["evidenceFreeze"] == "frozen"
    assert SUMMARY["evidenceSetSha256"] == basis["evidenceSetSha256"]
    assert SUMMARY["evidencePackSha256"] == basis["evidencePackSha256"]
    for digest in (basis["evidenceSetSha256"], basis["evidencePackSha256"]):
        assert f"`{digest}`" in PAGE


def test_the_counts_are_the_index_s_and_the_register_s() -> None:
    basis = DATA["evidenceBasis"]
    assert basis["claims"] == SUMMARY["claims"] == len(REGISTER["claims"])
    by_status: dict[str, int] = {}
    for claim in REGISTER["claims"]:
        by_status[claim["status"]] = by_status.get(claim["status"], 0) + 1
    assert basis["claimsByStatus"] == SUMMARY["claimsByStatus"] == by_status
    assert basis["records"] == SUMMARY["records"]
    assert basis["recordsByLevel"] == SUMMARY["recordsByLevel"]


def test_the_page_states_the_counts_the_data_holds() -> None:
    basis = DATA["evidenceBasis"]
    status = basis["claimsByStatus"]
    level = basis["recordsByLevel"]
    assert (
        f"{basis['claims']} claims, of which {status['certified']} are certified, "
        f"{status['planned']} planned, {status['deferred']} deferred, and "
        f"{status['not-claimed']} not claimed"
    ) in PAGE
    assert (
        f"{basis['records']} evidence records, of which {level['C0']} are `C0`, "
        f"{level['C1']} are `C1`, {level['C2']} are `C2`, and none is `C3` or `C4`"
    ) in PAGE
    assert level["C3"] == level["C4"] == 0


def test_every_quoted_figure_is_one_the_case_study_reads_back() -> None:
    declared = {row["figureId"]: row for row in CASE_STUDY_DATA["figures"]}
    for figure in DATA["figures"]:
        assert declared[figure["caseStudyFigureId"]]["quoted"] == figure["quoted"]
        assert figure["quoted"] in PAGE, figure


def test_no_measurement_on_the_page_lacks_a_declared_figure() -> None:
    remainder = PAGE
    for figure in sorted(DATA["figures"], key=lambda row: -len(row["quoted"])):
        remainder = remainder.replace(figure["quoted"], " ")
    stray = MEASUREMENT.findall(remainder)
    assert not stray, stray


# ------------------------------------------------------------ the release state


def test_the_release_row_is_not_claimed_as_released_and_certified_on_main() -> None:
    """The tripwire this module set fired in the same change, as it was meant to.

    The row is read twice: in the register as released, which this record reads, and
    on `main`, where the post-release ledger moved it. The page says both.
    """
    release = DATA["release"]
    claim = CLAIMS[release["registerClaimId"]]
    assert claim["status"] == release["registerStatus"] == "not-claimed"
    (now,) = [
        row
        for row in CURRENT_REGISTER["claims"]
        if row["claimId"] == release["registerClaimId"]
    ]
    assert now["status"] == release["registerStatusOnMain"] == "certified"
    ledger = load_ledger(POST_RELEASE_PATH)
    assert release["movedBy"] in {c["changeId"] for c in ledger["registerChanges"]}
    assert release["recordRef"] == ledger["reportRef"]
    assert f"`{release['registerClaimId']}` as not claimed" in PAGE
    assert "certifies that row on `main`, at `C0`" in PAGE
    assert f"`{release['tag']}` exists on `{release['tagCommit'][:7]}`" in PAGE


def test_the_tag_is_on_the_commit_the_page_names() -> None:
    """Reads the repository's tags; a clone without them, as in CI, skips."""
    release = DATA["release"]
    try:
        resolved = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{release['tag']}^{{commit}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        pytest.skip("git is not available")
    if resolved.returncode != 0:
        pytest.skip("the release tag is not in this clone")
    assert resolved.stdout.strip() == release["tagCommit"]


# ------------------------------------------------ the surface left standing


def test_every_surface_left_standing_still_says_what_the_page_says_it_says() -> None:
    """A tripwire. If the case study is re-published, this section must go too."""
    for surface in DATA["describesTheRepositoryBeforeThisDecision"]:
        assert surface["says"] in normalised(read(surface["path"])), surface[
            "surfaceId"
        ]
    section = normalised(
        _section(
            "## Where the published evidence still describes the repository "
            "before this decision"
        )
    )
    assert '"is a separate decision that has not been made"' in section


# --------------------------------------------------------------- the page


def test_the_page_publishes_every_identifier_the_data_holds() -> None:
    spans = set(CODE_SPAN.findall(PAGE_TEXT))
    identifiers = (
        set(FINDINGS)
        | set(PROBLEMS)
        | set(GATES)
        | {row["triggerId"] for row in DATA["reviewTriggers"]}
        | {row["surfaceId"] for row in DATA["describesTheRepositoryBeforeThisDecision"]}
    )
    missing = sorted(identifiers - spans)
    assert not missing, missing


def test_the_page_assumes_no_scope_and_argues_from_no_appeal() -> None:
    lowered = PAGE.lower()
    found = [phrase for phrase in FORBIDDEN_PHRASES if phrase in lowered]
    assert not found, found
    assert "this record names no scope for one" in PAGE


def _slug(heading: str) -> str:
    """GitHub's heading anchor, approximately.

    It does not model the `-1`, `-2` suffixes GitHub gives a repeated heading, so a
    correct link to the second of two identical headings would fail here, loudly.
    """
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


def test_the_readme_and_the_governance_table_link_the_page() -> None:
    readme = read("README.md")
    roadmap = readme.split("\n## Roadmap\n", 1)[1].split("\n## ", 1)[0]
    assert "](docs/governance/v2-investment-decision.md)" in roadmap
    governance = read("docs/governance/repository.md")
    (row,) = [
        line for line in governance.splitlines() if line.startswith("| Next version |")
    ]
    assert "](v2-investment-decision.md)" in row
    for option_id in OUTCOMES:
        assert f"\n### {option_id.capitalize()}\n" in PAGE_TEXT, option_id
