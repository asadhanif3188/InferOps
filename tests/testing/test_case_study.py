"""The V1 engineering case study, held to the register and the records it quotes.

Every check here reads files from this repository and nothing else. No network, no
cluster, no model, no clock, no randomness.

The claim register has said, since it was written, that the case study it is meant to
govern did not exist, and that "a future case-study claim with no row here would be
caught by nothing". This module is the thing that catches it, for the draft that now
exists. It establishes:

* every claim the case study cites is a row of the register, each section cites
  exactly the claims its data file declares, and the claims appendix holds each cited
  claim once;
* every cell of the appendix -- status, the levels of the claim's records, and whether
  it is a release blocker -- is what the register and the completeness ledger say,
  so a claim that moves cannot leave the page behind;
* the section on what V1 does not prove cites every claim the register does not
  certify and every release blocker;
* every figure the page quotes reads back from the committed file it names, by JSON
  pointer or verbatim, and no duration, percentage, or memory size appears on the page
  without a declared source;
* every count the page states is recomputed from the register and the evidence index;
* the page names the evidence set it was verified against, and fails when the index's
  digest, gate, or blocker count moves, so the page is verified again rather than left
  behind;
* the results-first summary is the page's first section, stays short, and rests on no
  release blocker;
* every number in a text figure is declared, whatever its unit, every figure's caption
  states its boundary, and the architecture image it shows is committed;
* no reader surface says of the pod-loss experiment that nobody intervened, which is
  broader than the record;
* the page quotes no amount from a cost result, and stays a draft while the release
  gate is incomplete.

It establishes **nothing about whether a sentence says what its record says**. A
figure can be quoted correctly inside a sentence that misreads it, a verbatim figure
is only checked for being present in the file it names, and a drawn figure's
arrangement can imply more than its records. That is a reading, and the case study
says so itself.
"""

from __future__ import annotations

import json
import os
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = "docs/case-study/v1-engineering-case-study.v1alpha1.json"
EXPECTED_ID = "https://inferops.io/case-study/v1-engineering-case-study.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

#: The section that must account for every claim V1 does not certify. Fixed here
#: rather than read from the data it constrains, so dropping it fails a test.
NOT_PROVEN_SECTION = "not-proven"

#: The sections an engineering reader meets first, fixed here for the same reason.
SUMMARY_SECTIONS = ("at-a-glance", "what-this-demonstrates")

#: A proxy for "readable in about three minutes": the words from the top of the page
#: to the end of the results-first summary -- status, boundary, and summary -- at a
#: reading speed of about 250 words a minute. It bounds length and says nothing about
#: whether the words are the right ones.
FIRST_SCREEN_WORD_BUDGET = 850

#: Where readers meet the pod-loss experiment outside the dated records. A dated
#: record keeps the words it was written with.
READER_SURFACES = (
    "README.md",
    "docs/case-study/v1-engineering-case-study.md",
    "docs/environment/operator-runbook.md",
)

#: Wording broader than the pod-recovery record, which establishes only that the
#: workflow issued no mutating command between the delete and its closing uninstall.
BROADER_THAN_THE_RECORD = re.compile(
    r"\b(?:nobody|no one|no-one)\s+(?:intervened|had to intervene)\b", re.IGNORECASE
)

#: The heading the claims appendix sits under.
APPENDIX_HEADING = "Appendix: the claims this draft relies on"

#: Where the evidence levels are published; a row's levels are these, in this order.
LEVEL_ORDER = ("C0", "C1", "C2", "C3", "C4")

#: A number immediately followed by one of the units the case study quotes
#: measurements in. Every one must sit inside a declared figure.
MEASURED = re.compile(
    r"(?<![\w.])(\d+(?: \d{3})*(?:\.\d+)?)(?=\s?(?:ms\b|%|GiB\b|MiB\b))"
)

#: A whole numeral, as the page and the records write one. Numbers are compared as
#: whole tokens: comparing them as substrings of the declared figures, as the first
#: version of this module did, let a stray `5 ms` pass because some declared figure
#: happened to contain the digit 5.
NUMERAL = re.compile(r"(?<![\w.])\d+(?: \d{3})*(?:\.\d+)?")

CODE_SPAN = re.compile(r"`([^`\n]+)`")

NUMBER_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
    20: "twenty",
}


def _load(relative: str) -> Any:
    return json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def normalised(text: str) -> str:
    return " ".join(text.split())


DATA = _load(DATA_PATH)
DOCUMENT = _read(DATA["documentRef"])
REGISTER = _load(DATA["registerRef"])
INDEX = _load(DATA["indexRef"])
COMPLETENESS = _load(DATA["completenessRef"])

CLAIMS = {row["claimId"]: row for row in REGISTER["claims"]}
BLOCKED_CLAIMS = {row["claimId"] for row in COMPLETENESS["blockers"]}
SECTIONS = DATA["sections"]
FIGURES = DATA["figures"]
FIGURES_BY_ID = {figure["figureId"]: figure for figure in FIGURES}
VISUALS = DATA["visuals"]
TEXT_VISUALS = [visual for visual in VISUALS if visual["kind"] == "text"]


def _sections_of_document() -> list[tuple[str, str]]:
    """Each `## ` heading of the page and the text beneath it, in order.

    A line inside a fenced block is never a heading, however it starts, so a diagram
    that grew a `## ` line cannot split a section in two.
    """
    sections: list[tuple[str, list[str]]] = []
    fenced = False
    for line in DOCUMENT.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            sections.append((line[3:].strip(), [line[3:]]))
        elif sections:
            sections[-1][1].append(line)
    return [(heading, "\n".join(lines)) for heading, lines in sections]


DOCUMENT_SECTIONS = _sections_of_document()


def _cited(text: str) -> list[str]:
    """Register claim identifiers written as code spans, in first-mention order."""
    cited: list[str] = []
    for span in CODE_SPAN.findall(text):
        if span in CLAIMS and span not in cited:
            cited.append(span)
    return cited


def _appendix_rows() -> list[list[str]]:
    body = dict(DOCUMENT_SECTIONS)[APPENDIX_HEADING]
    rows = []
    for line in body.splitlines():
        if not line.startswith("| `"):
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def _levels(claim: dict[str, Any]) -> str:
    held = {record["evidenceLevel"] for record in claim.get("evidenceRecords", [])}
    ordered = [level for level in LEVEL_ORDER if level in held]
    return ", ".join(f"`{level}`" for level in ordered) if ordered else "none"


def _pointer(document: Any, pointer: str) -> Any:
    value = document
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def _render(value: Any, render: str) -> str:
    if render == "grouped":
        assert isinstance(value, int), f"{value!r} is not an integer"
        return f"{value:,}".replace(",", " ")
    if render == "thousandths":
        assert isinstance(value, int), f"{value!r} is not an integer"
        return str((Decimal(value) / 1000).quantize(Decimal("0.001")))
    if render == "percent-one-place":
        share = Decimal(str(value)) * 100
        return str(share.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    raise AssertionError(f"unknown render {render!r}")


# --------------------------------------------------------------- identity


def test_the_data_file_declares_its_identity_and_contract_version() -> None:
    assert DATA["$id"] == EXPECTED_ID
    assert DATA["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_every_reference_the_data_file_makes_resolves() -> None:
    for key in (
        "documentRef",
        "registerRef",
        "indexRef",
        "completenessRef",
    ):
        assert (REPO_ROOT / DATA[key]).is_file(), f"{key} does not resolve: {DATA[key]}"
    for ref in DATA["validationRefs"]:
        assert (REPO_ROOT / ref).is_file(), f"validationRefs does not resolve: {ref}"
    for figure in FIGURES:
        assert (REPO_ROOT / figure["sourceRef"]).is_file(), figure["figureId"]
    for visual in VISUALS:
        for ref in [*visual["derivedFrom"], *filter(None, [visual.get("imageRef")])]:
            assert (REPO_ROOT / ref).is_file(), f"{visual['visualId']}: {ref}"


def test_every_render_a_figure_names_is_declared() -> None:
    declared = set(DATA["renders"])
    used = {figure["render"] for figure in FIGURES if not figure.get("verbatim")}
    assert used <= declared, sorted(used - declared)


# ------------------------------------------------------ draft and the gate


def test_the_case_study_stays_a_draft_while_the_release_gate_is_incomplete() -> None:
    """A case study published over an unfrozen evidence pack is the failure this is for.

    When the gate completes, this test still passes for a draft; it is publishing
    while the gate is incomplete that it refuses.
    """
    gate = INDEX["summary"]["releaseGate"]
    assert COMPLETENESS["releaseGate"]["decision"].lower() == gate
    blocked = "V1-S5-007" in COMPLETENESS["releaseGate"]["consumersBlocked"]
    first_status = next(
        line for line in DOCUMENT.splitlines() if line.startswith("Status:")
    )
    if gate != "complete" or blocked:
        assert DATA["status"] == "draft"
        assert first_status.startswith("Status: **draft**"), first_status
        assert "**not frozen**" in DOCUMENT


def test_the_status_paragraph_counts_the_blockers_and_names_the_gate() -> None:
    blockers = INDEX["summary"]["releaseBlockers"]
    status = normalised(DOCUMENT.split("\n## ", 1)[0])
    assert f"{NUMBER_WORDS[blockers]} certified claims" in status
    assert "`python -m tools.evidence_index --gate` exits 1" in status


def test_the_page_names_the_evidence_set_it_was_verified_against() -> None:
    """A page verified against one evidence set is not verified against the next.

    When the index's digest, gate, or blocker count moves, this fails, and the change
    that moved them must verify the page again and restate what it was verified
    against, rather than leave a verification that no longer describes the evidence.
    """
    summary = INDEX["summary"]
    verified = DATA["verifiedAgainst"]
    assert verified["evidenceSetSha256"] == summary["evidenceSetSha256"]
    assert verified["releaseGate"] == summary["releaseGate"]
    assert verified["releaseBlockers"] == summary["releaseBlockers"]
    status = DOCUMENT.split("\n## ", 1)[0]
    assert f"`{summary['evidenceSetSha256']}`" in normalised(status)
    assert f"verified in `{DATA['verifiedIn']}`" in normalised(status)


# ---------------------------------------------------------------- summary


def test_the_results_first_summary_is_the_first_section() -> None:
    """An engineering reader meets the findings before the deep sections."""
    first = [head for head, _ in DOCUMENT_SECTIONS[: len(SUMMARY_SECTIONS)]]
    expected = [
        section["heading"]
        for section in SECTIONS
        if section["sectionId"] in SUMMARY_SECTIONS
    ]
    assert first == expected


def test_the_first_screen_stays_within_its_word_budget() -> None:
    bridge = next(s for s in SECTIONS if s["sectionId"] == SUMMARY_SECTIONS[1])
    first_screen = DOCUMENT.split(f"\n## {bridge['heading']}\n", 1)
    assert len(first_screen) == 2, "the summary's closing boundary was not found"
    words = len(first_screen[0].split())
    assert words <= FIRST_SCREEN_WORD_BUDGET, (
        f"{words} words up to the end of the summary; "
        f"the budget is {FIRST_SCREEN_WORD_BUDGET}"
    )


@pytest.mark.parametrize("section_id", SUMMARY_SECTIONS)
def test_the_summary_rests_on_no_release_blocker(section_id: str) -> None:
    """A finding led with must not depend on a claim the gate holds as a blocker."""
    section = next(s for s in SECTIONS if s["sectionId"] == section_id)
    leaning = set(section["claims"]) & BLOCKED_CLAIMS
    assert not leaning, sorted(leaning)
    assert all(CLAIMS[claim]["status"] == "certified" for claim in section["claims"])


def test_the_summary_links_every_finding_to_its_section() -> None:
    body = dict(DOCUMENT_SECTIONS)[SECTIONS[0]["heading"]]
    rows = [line for line in body.splitlines() if line.startswith("| ")][1:]
    assert rows, "the summary table is missing"
    for row in rows:
        assert re.search(r"\[Section \d+\]\(#[a-z0-9-]+\)", row), row


# --------------------------------------------------------------- sections


def test_the_sections_are_the_declared_ones_in_order() -> None:
    headings = [head for head, _ in DOCUMENT_SECTIONS if head != APPENDIX_HEADING]
    assert headings == [section["heading"] for section in SECTIONS]
    assert DOCUMENT_SECTIONS[-1][0] == APPENDIX_HEADING


def test_section_identifiers_are_unique_and_the_not_proven_section_exists() -> None:
    ids = [section["sectionId"] for section in SECTIONS]
    assert len(ids) == len(set(ids))
    assert NOT_PROVEN_SECTION in ids


@pytest.mark.parametrize("section", SECTIONS, ids=lambda section: section["sectionId"])
def test_each_section_cites_exactly_the_claims_it_declares(
    section: dict[str, Any],
) -> None:
    text = dict(DOCUMENT_SECTIONS)[section["heading"]]
    assert _cited(text) == section["claims"]


def test_every_claim_a_section_declares_is_a_register_row() -> None:
    unknown = {
        claim
        for section in SECTIONS
        for claim in section["claims"]
        if claim not in CLAIMS
    }
    assert not unknown, sorted(unknown)


def test_every_code_span_shaped_like_a_claim_is_a_register_row() -> None:
    """A mistyped or retired claim identifier would otherwise pass as prose."""
    shaped = {
        span
        for span in CODE_SPAN.findall(DOCUMENT)
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+){4,}", span)
    }
    assert shaped <= set(CLAIMS), sorted(shaped - set(CLAIMS))


def test_what_v1_does_not_prove_cites_every_uncertified_claim_and_every_blocker() -> (
    None
):
    section = next(s for s in SECTIONS if s["sectionId"] == NOT_PROVEN_SECTION)
    uncertified = {
        claim_id for claim_id, claim in CLAIMS.items() if claim["status"] != "certified"
    }
    missing = (uncertified | BLOCKED_CLAIMS) - set(section["claims"])
    assert not missing, sorted(missing)


# --------------------------------------------------------------- appendix


def test_the_appendix_holds_every_cited_claim_exactly_once() -> None:
    rows = [row[0].strip("`") for row in _appendix_rows()]
    cited = {claim for section in SECTIONS for claim in section["claims"]}
    assert len(rows) == len(set(rows)), "a claim appears twice in the appendix"
    assert set(rows) == cited


@pytest.mark.parametrize("row", _appendix_rows(), ids=lambda row: row[0].strip("`"))
def test_each_appendix_row_is_what_the_register_and_the_ledger_say(
    row: list[str],
) -> None:
    claim_id, status, levels, blocker = row
    claim = CLAIMS[claim_id.strip("`")]
    assert status == f"`{claim['status']}`"
    assert levels == _levels(claim)
    expected = "**yes**" if claim["claimId"] in BLOCKED_CLAIMS else "no"
    assert blocker == expected


def test_every_release_blocker_is_in_the_appendix() -> None:
    rows = {row[0].strip("`") for row in _appendix_rows()}
    assert rows >= BLOCKED_CLAIMS, sorted(BLOCKED_CLAIMS - rows)


# ---------------------------------------------------------------- figures


def test_figure_identifiers_are_unique() -> None:
    ids = [figure["figureId"] for figure in FIGURES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("figure", FIGURES, ids=lambda figure: figure["figureId"])
def test_every_figure_reads_back_from_the_file_it_names(figure: dict[str, Any]) -> None:
    source = figure["sourceRef"]
    if figure.get("verbatim"):
        assert figure["quoted"] in normalised(_read(source)), (
            f"{figure['figureId']}: {figure['quoted']!r} is not in {source}"
        )
        return
    record = _load(source)
    values = [
        _render(_pointer(record, pointer), figure["render"])
        for pointer in figure["pointers"]
    ]
    written = figure["template"].format(*values)
    assert written == figure["quoted"], (
        f"{figure['figureId']} quotes {figure['quoted']!r}; {source} gives {written!r}"
    )


@pytest.mark.parametrize("figure", FIGURES, ids=lambda figure: figure["figureId"])
def test_a_figure_names_a_claim_the_page_cites(figure: dict[str, Any]) -> None:
    """A figure belongs to a cited claim, or says in the data why it belongs to none."""
    if figure["claimId"] is None:
        assert len(figure.get("noClaimReason") or "") > 40, figure["figureId"]
        return
    assert "noClaimReason" not in figure, figure["figureId"]
    cited = {claim for section in SECTIONS for claim in section["claims"]}
    assert figure["claimId"] in cited, figure["figureId"]


def test_the_document_quotes_every_declared_figure() -> None:
    body = normalised(DOCUMENT)
    missing = [figure["quoted"] for figure in FIGURES if figure["quoted"] not in body]
    assert not missing, missing


def test_no_measurement_is_quoted_without_a_declared_figure() -> None:
    """A duration, a percentage, or a memory size on the page must have a source."""
    declared = {
        number for figure in FIGURES for number in NUMERAL.findall(figure["quoted"])
    }
    stray = sorted(
        {
            number
            for number in MEASURED.findall(normalised(DOCUMENT))
            if number not in declared
        }
    )
    assert not stray, f"measurements quoted without a declared source: {stray}"


# ---------------------------------------------------------------- visuals


def _fenced_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append(current)
                current = None
        elif current is not None:
            current.append(line)
    return blocks


def _section_text(section_id: str) -> str:
    heading = next(s["heading"] for s in SECTIONS if s["sectionId"] == section_id)
    return dict(DOCUMENT_SECTIONS)[heading]


def _visual_block(visual: dict[str, Any]) -> str:
    """The fenced block a text figure is, found by its first line inside its section."""
    blocks = [
        block
        for block in _fenced_blocks(_section_text(visual["sectionId"]))
        if block and block[0] == visual["firstLine"]
    ]
    assert len(blocks) == 1, f"{visual['visualId']}: found {len(blocks)} blocks"
    return "\n".join(blocks[0])


def _caption(visual: dict[str, Any]) -> str:
    """The paragraph that opens with the figure's number, inside its section."""
    marker = f"**Figure {visual['figureNumber']}.**"
    paragraphs = _section_text(visual["sectionId"]).split("\n\n")
    found = [p for p in paragraphs if p.startswith(marker)]
    assert len(found) == 1, f"{visual['visualId']}: {len(found)} captions"
    return normalised(found[0])


def test_visual_identifiers_and_figure_numbers_are_unique_and_in_order() -> None:
    ids = [visual["visualId"] for visual in VISUALS]
    assert len(ids) == len(set(ids))
    numbers = [visual["figureNumber"] for visual in VISUALS]
    assert numbers == list(range(1, len(VISUALS) + 1))
    positions = [DOCUMENT.index(f"**Figure {n}.**") for n in numbers]
    assert positions == sorted(positions), "figures are not numbered in page order"


@pytest.mark.parametrize("visual", VISUALS, ids=lambda visual: visual["visualId"])
def test_every_visual_has_a_caption_that_states_its_boundary(
    visual: dict[str, Any],
) -> None:
    caption = _caption(visual)
    missing = [phrase for phrase in visual["captionMustSay"] if phrase not in caption]
    assert not missing, f"{visual['visualId']}: the caption omits {missing}"


@pytest.mark.parametrize(
    "visual",
    [visual for visual in VISUALS if visual["kind"] == "image"],
    ids=lambda visual: visual["visualId"],
)
def test_every_image_the_page_shows_is_committed_and_in_its_section(
    visual: dict[str, Any],
) -> None:
    image = REPO_ROOT / visual["imageRef"]
    assert image.is_file()
    page_dir = (REPO_ROOT / DATA["documentRef"]).parent
    relative = Path(os.path.relpath(image, page_dir)).as_posix()
    assert f"]({relative})" in _section_text(visual["sectionId"])


@pytest.mark.parametrize("visual", TEXT_VISUALS, ids=lambda visual: visual["visualId"])
def test_every_number_in_a_text_figure_is_declared(visual: dict[str, Any]) -> None:
    """In a drawn figure a number carries more weight than in prose, so all are held.

    Every numeral must come from a figure the visual declares, or be listed as
    unpoliced with a reason; and every numeral those figures quote must be drawn, so a
    figure cannot be declared and then left out.
    """
    block = normalised(_visual_block(visual))
    drawn = set(NUMERAL.findall(block))
    declared: set[str] = set()
    for figure_id in visual["figures"]:
        declared |= set(NUMERAL.findall(FIGURES_BY_ID[figure_id]["quoted"]))
    unpoliced = set(visual["unpolicedNumerals"])
    assert all(len(reason) > 20 for reason in visual["unpolicedNumerals"].values())
    stray = sorted(drawn - declared - unpoliced)
    assert not stray, f"{visual['visualId']} draws numbers nothing declares: {stray}"
    undrawn = sorted(declared - drawn)
    assert not undrawn, (
        f"{visual['visualId']} declares numbers it does not draw: {undrawn}"
    )


@pytest.mark.parametrize("visual", TEXT_VISUALS, ids=lambda visual: visual["visualId"])
def test_every_figure_a_visual_draws_is_read_from_a_record_it_derives_from(
    visual: dict[str, Any],
) -> None:
    sources = set(visual["derivedFrom"])
    for figure_id in visual["figures"]:
        assert FIGURES_BY_ID[figure_id]["sourceRef"] in sources, figure_id


# ------------------------------------------------ wording broader than a record


def test_the_page_counts_the_claims_that_hold_no_record() -> None:
    """Figure 1's caption corrects the image's register box with the register's count."""
    holding_none = [c for c in CLAIMS.values() if not c.get("evidenceRecords")]
    assert all(claim["status"] != "certified" for claim in holding_none)
    word = NUMBER_WORDS[len(holding_none)]
    assert f"every certified claim is, and {word} uncertified claims hold none" in (
        normalised(DOCUMENT)
    )


@pytest.mark.parametrize("surface", READER_SURFACES)
def test_no_reader_surface_says_nobody_intervened_in_the_pod_loss(surface: str) -> None:
    """The record establishes that its workflow intervened in nothing, and no more."""
    found = BROADER_THAN_THE_RECORD.findall(_read(surface))
    assert not found, f"{surface}: {found}"


# ----------------------------------------------------------------- counts


def test_the_claim_counts_the_page_states_are_the_registers() -> None:
    summary = INDEX["summary"]
    by_status = {
        status: 0 for status in ("certified", "planned", "deferred", "not-claimed")
    }
    for claim in CLAIMS.values():
        by_status[claim["status"]] += 1
    assert by_status == summary["claimsByStatus"]
    sentence = (
        f"{len(CLAIMS)} claims: {by_status['certified']} certified, "
        f"{by_status['planned']} planned, {by_status['deferred']} deferred, and "
        f"{by_status['not-claimed']} not claimed"
    )
    assert sentence in normalised(DOCUMENT)


def test_the_record_counts_the_page_states_are_the_registers() -> None:
    by_level = {level: 0 for level in LEVEL_ORDER}
    for claim in CLAIMS.values():
        for record in claim.get("evidenceRecords", []):
            by_level[record["evidenceLevel"]] += 1
    assert by_level == INDEX["summary"]["recordsByLevel"]
    assert by_level["C3"] == by_level["C4"] == 0, (
        "a C3 or C4 record exists; the page's sentence about them must be rewritten"
    )
    total = sum(by_level.values())
    sentence = (
        f"{total} evidence records: {by_level['C0']} at `C0`, {by_level['C1']} at `C1`, "
        f"{by_level['C2']} at `C2`, and none at `C3` or `C4`"
    )
    assert sentence in normalised(DOCUMENT)


def test_the_code_identity_counts_the_page_states_are_the_indexs() -> None:
    summary = INDEX["summary"]
    body = normalised(DOCUMENT)
    assert (
        f"{summary['executedRecordsNamingTheRevisionThatRan']} of the "
        f"{summary['executedRecords']} executed records name the revision that ran"
    ) in body
    assert f"there are {summary['releaseBlockers']} release blockers" in body
    assert summary["releaseBlockers"] == len(BLOCKED_CLAIMS)


# ------------------------------------------------------------------- cost


def _cost_amounts() -> set[str]:
    """Every decimal string with four or more places in a committed cost result."""
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and re.fullmatch(r"\d+\.\d{4,}", value):
            found.add(value)

    for path in sorted((REPO_ROOT / "docs" / "proof" / "cost").glob("*.result.json")):
        walk(json.loads(path.read_text(encoding="utf-8")))
    return found


def test_the_case_study_quotes_no_amount_from_a_cost_result() -> None:
    """ADR 0007 D11 publishes no cost figure; a case study is not an exception."""
    amounts = _cost_amounts()
    assert amounts, "no cost result was read, so this check would pass vacuously"
    quoted = sorted(amount for amount in amounts if amount in DOCUMENT)
    assert not quoted, quoted
    assert "USD" not in DOCUMENT
