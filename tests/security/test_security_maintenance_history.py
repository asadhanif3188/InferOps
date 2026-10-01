"""Checks that the V1 security decision keeps its released text, and later state stays additive.

ADR 0008 is an accepted V1 record. The change that accepted ``EX-07`` on
2026-09-30, pull request #103, rewrote two of its sentences from "six" to "seven"
exceptions, so the record read as if ``EX-07`` had existed when the decision was
made. ``V2-S1-004-PR2`` restored both sentences and added a dated note after each.
This module holds that shape:

- the record, with its registered post-release notes taken out, is byte for byte
  the text ``v1.0.0`` released, so an in-place edit anywhere fails here, and a
  new note fails until it is registered below with the change that added it;
- each note sits after the sentence it amends, inside that sentence's section;
- the note and the security baseline agree on what ``EX-07`` is;
- the surfaces that describe the current register state the count the data
  produces, so the restoration cannot be mistaken for rolling the current
  count back;
- ``EX-07``'s scope is the scope the maintenance reconciliation records;
- the ``EX-07`` assessment is kept as it was merged, with a dated correction.

What it does not establish: that a note's prose is accurate beyond the facts it
names, or that any other V1 record is unedited. It reads committed files; it
runs no scanner and reads no git history, so the released text is identified by
the digest pinned below rather than read from the tag.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0008-v1-security-baseline.md"
)
BASELINE_PATH = REPO_ROOT / "docs" / "security" / "security-baseline.v1alpha1.json"
SECURITY_PROOF = REPO_ROOT / "docs" / "proof" / "security"
ASSESSMENT_PATH = SECURITY_PROOF / "ex-07-runtime-image-exception.md"
RECONCILIATION_PATH = (
    SECURITY_PROOF / "v2-s1-004-pr2-security-maintenance-reconciliation.md"
)
VALIDATION_PATH = SECURITY_PROOF / "v2-s1-004-pr2-validation.md"
RUNTIME_IGNORE_PATH = REPO_ROOT / "scripts" / "security" / "runtime-image.trivyignore"
DEPENDENCY_IGNORE_PATH = REPO_ROOT / "scripts" / "security" / "dependencies.trivyignore"

# SHA-256 of ADR 0008 as `v1.0.0` released it: the git blob c1f8d977 at the tag's
# commit 718ad2e0, with LF line endings. Recorded in
# docs/proof/security/v2-s1-004-pr2-validation.md.
RELEASED_DECISION_SHA256 = (
    "cbcbb4579449e361f399423b40787bc7b8093aeed9e71b1fd0eeea20c0fa535d"
)

# Every note added to ADR 0008 after `v1.0.0`, by the opening of its paragraph,
# and the change that added it. A note is a paragraph of its own; adding one
# means adding a row here, which is the point: it is a dated, visible act.
POST_RELEASE_NOTES = (
    ("> **Note, 2026-09-27, after the release.**", "V1-S5-009-PR1"),
    (
        "> **Note, 2026-10-01: a seventh exception, accepted on 2026-09-30.**",
        "V2-S1-004-PR2",
    ),
    ("> **Note, 2026-10-01.** The register bullet above", "V2-S1-004-PR2"),
)
D11_NOTE = POST_RELEASE_NOTES[1][0]
CONSEQUENCES_NOTE = POST_RELEASE_NOTES[2][0]

# The two sentences pull request #103 rewrote, as `v1.0.0` released them, each
# with the section it belongs to and the section that follows it.
RESTORED_SENTENCES = (
    ("Six exceptions are recorded.", "## D11 ", "## D12 "),
    (
        "Twelve deferred risks, ten of them blocking production use, and six "
        "accepted exceptions.",
        "## Consequences",
        "## Compatibility impact",
    ),
)
# What #103 had put in their place. Neither may come back.
REWRITTEN_SENTENCES = (
    "Seven exceptions are recorded.",
    "and seven accepted exceptions. A shorter register",
)

# The scope `EX-07` was accepted with, as the reconciliation records it. This is
# a tripwire: if a later change rotates the image, retires `EX-07`, or moves its
# deadline, this fails, and that change says so in its own record and updates
# this table. The 2026-10-01 reconciliation stays as it was written.
RECONCILED_EX07_SCOPE = {
    "scanner": "trivy",
    "findingId": "CVE-2026-84782",
    "severity": "HIGH",
    "subject": (
        "ghcr.io/ggml-org/llama.cpp@sha256:"
        "100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"
    ),
    "packages": ["libssl3t64", "openssl"],
    "installedVersion": "3.0.13-0ubuntu3.12",
    "fixedVersion": "3.0.13-0ubuntu3.16",
    "ignoreFile": "scripts/security/runtime-image.trivyignore",
    "owner": "security",
    "acceptedOn": "2026-09-30",
    "reviewBy": "2026-10-30",
}

# SHA-256 of the EX-07 assessment as pull request #103 merged it, blob d1b59189 at
# 51cddd1, with LF line endings. Everything before its later correction must
# still hash to this.
MERGED_ASSESSMENT_SHA256 = (
    "d1b59189d9ec34e79e4348062efe52ad1f03e7584bce164bf824392106186acf"
)

NUMBER_WORDS = {6: "six", 7: "seven", 8: "eight", 9: "nine", 12: "twelve"}

BASELINE = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
EXCEPTIONS = {row["exceptionId"]: row for row in BASELINE["exceptions"]}


def _word(value: int) -> str:
    assert value in NUMBER_WORDS, f"no word for {value}; the register moved further"
    return NUMBER_WORDS[value]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _without_post_release_notes(text: str) -> str:
    paragraphs = text.split("\n\n")
    openings = tuple(opening for opening, _ in POST_RELEASE_NOTES)
    return "\n\n".join(p for p in paragraphs if not p.startswith(openings))


def _decision() -> str:
    return DECISION_PATH.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end)]


# --------------------------------------------------------------------------
# The released decision text
# --------------------------------------------------------------------------


def test_the_decision_is_the_released_text_plus_registered_notes() -> None:
    """Any in-place edit to ADR 0008, or an unregistered note, changes this digest."""
    assert _sha256(_without_post_release_notes(_decision())) == (
        RELEASED_DECISION_SHA256
    ), (
        "ADR 0008, without its registered post-release notes, is no longer the text "
        "v1.0.0 released. Later state belongs in a dated note registered in "
        "POST_RELEASE_NOTES, never in the released sentences."
    )


@pytest.mark.parametrize("opening,added_by", POST_RELEASE_NOTES)
def test_every_registered_note_is_there_once(opening: str, added_by: str) -> None:
    paragraphs = _decision().split("\n\n")
    assert sum(1 for p in paragraphs if p.startswith(opening)) == 1, (
        f"the note {added_by} added is missing or repeated: {opening!r}"
    )


def test_the_history_check_refuses_the_edit_it_exists_for() -> None:
    """The digest check passes on the committed file, so prove it can fail.

    Each variant is made in memory from the committed text: pull request #103's
    own rewrite, the same rewrite with the note kept, and a correct note that
    nobody registered.
    """
    text = _decision()
    rewrites = (
        text.replace("Six exceptions are recorded.", "Seven exceptions are recorded."),
        text.replace("and six accepted exceptions.", "and seven accepted exceptions."),
        text.replace(
            "## D12 ", "> **Note, 2099-01-01.** An unregistered note.\n\n## D12 "
        ),
    )
    for rewritten in rewrites:
        assert rewritten != text
        assert _sha256(_without_post_release_notes(rewritten)) != (
            RELEASED_DECISION_SHA256
        )


@pytest.mark.parametrize(
    "sentence,section,next_section",
    RESTORED_SENTENCES,
    ids=["d11", "consequences"],
)
def test_each_restored_sentence_is_in_its_section_once(
    sentence: str, section: str, next_section: str
) -> None:
    flat = _flat(_decision())
    assert flat.count(_flat(sentence)) == 1, sentence
    within = _flat(_section(_decision(), section, next_section))
    assert _flat(sentence) in within, f"{sentence!r} is not under {section!r}"


def test_the_rewritten_wording_is_not_back() -> None:
    flat = _flat(_decision())
    for rewritten in REWRITTEN_SENTENCES:
        assert _flat(rewritten) not in flat, rewritten


@pytest.mark.parametrize(
    "note,sentence,section,next_section",
    [
        (D11_NOTE, *RESTORED_SENTENCES[0]),
        (CONSEQUENCES_NOTE, *RESTORED_SENTENCES[1]),
    ],
    ids=["d11", "consequences"],
)
def test_each_note_follows_the_sentence_it_amends(
    note: str, sentence: str, section: str, next_section: str
) -> None:
    """Chronology on the page: the released sentence first, the dated note second."""
    body = _flat(_section(_decision(), section, next_section))
    assert _flat(note) in body, f"the note is not under {section!r}"
    assert body.index(_flat(note)) > body.index(_flat(sentence))


# --------------------------------------------------------------------------
# The note, the register, and the current-facing surfaces
# --------------------------------------------------------------------------


def _d11_note() -> str:
    paragraphs = _decision().split("\n\n")
    (note,) = [p for p in paragraphs if p.startswith(D11_NOTE)]
    return _flat(note.replace("\n>", "\n"))


def test_the_note_and_the_baseline_agree_on_ex07() -> None:
    """The note names EX-07's finding, its acceptance, and its deadline from the data."""
    note = _d11_note()
    finding = EXCEPTIONS["EX-07"]["scanFinding"]
    assert "`EX-07`" in note
    assert f"`{finding['findingId']}`" in note
    assert f"accepted on {finding['acceptedOn']}" in note
    assert f"until {finding['reviewBy']}" in note
    assert "bound to that image's digest" in note
    assert "v2-s1-004-pr2-security-maintenance-reconciliation.md" in note


def test_ex07_is_the_seventh_exception_and_the_released_six_are_the_others() -> None:
    """The note says six were recorded at release and EX-07 made seven.

    EX-01 to EX-06 are the six the released sentence counted; EX-07 is the
    seventh. A register that renumbered or dropped one would make the note
    false, so this fails first.
    """
    released = [f"EX-0{number}" for number in range(1, 7)]
    assert sorted(EXCEPTIONS)[:7] == [*released, "EX-07"]
    assert all("scanFinding" not in EXCEPTIONS[name] for name in released)
    note = _d11_note()
    assert '"six" was true then' in note
    assert "the register now records seven" in note


def _current_count_sentences() -> list[tuple[str, str]]:
    exceptions = _word(len(EXCEPTIONS))
    risks = _word(len(BASELINE["deferredRisks"]))
    return [
        (
            "README.md",
            f"{risks.capitalize()} risks and {exceptions} accepted exceptions",
        ),
        (
            "SECURITY.md",
            f"{risks.capitalize()} risks V1 carries rather than reduces, and "
            f"{exceptions} weaknesses it accepts",
        ),
        (
            "docs/architecture/README.md",
            f"{exceptions} exceptions are recorded with a compensating control each",
        ),
        (
            "docs/security/deferred-risks.md",
            f"{exceptions.capitalize()} weaknesses this project accepts rather than fixes",
        ),
        (
            "docs/security/security-method.md",
            f"{exceptions.capitalize()} weaknesses are accepted rather than fixed",
        ),
        ("docs/security/security-method.md", f"**All {exceptions}**"),
    ]


@pytest.mark.parametrize(
    "relative,sentence",
    _current_count_sentences(),
    ids=lambda value: str(value)[:40],
)
def test_the_current_facing_surfaces_state_the_current_count(
    relative: str, sentence: str
) -> None:
    """Restoring the released sentence must not roll the current count back."""
    body = _flat((REPO_ROOT / relative).read_text(encoding="utf-8"))
    assert _flat(sentence) in body, (
        f"{relative} does not state the count the baseline produces: {sentence!r}"
    )


# --------------------------------------------------------------------------
# EX-07's scope, and the records that describe it
# --------------------------------------------------------------------------


def test_ex07_keeps_the_scope_it_was_reconciled_with() -> None:
    assert EXCEPTIONS["EX-07"]["scanFinding"] == RECONCILED_EX07_SCOPE
    assert [name for name, row in EXCEPTIONS.items() if "scanFinding" in row] == [
        "EX-07"
    ], "a second scan exception exists; it needs its own record, not this one's"


def _entries(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def test_the_ignore_files_accept_exactly_what_was_reconciled() -> None:
    scope = RECONCILED_EX07_SCOPE
    assert _entries(RUNTIME_IGNORE_PATH) == [
        f"{scope['findingId']} exp:{scope['reviewBy']}"
    ]
    assert f"# assessed-image: {scope['subject']}" in RUNTIME_IGNORE_PATH.read_text(
        encoding="utf-8"
    )
    assert _entries(DEPENDENCY_IGNORE_PATH) == []


def test_the_reconciliation_says_what_the_change_was() -> None:
    body = _flat(RECONCILIATION_PATH.read_text(encoding="utf-8"))
    for phrase in (
        "pull request #103",
        "`51cddd1`",
        "`1c9a686` and `98aa117`",
        "**Out-of-band security maintenance.**",
        "It was not one of the changes planned for the first V2 sprint",
        "it adds no V2 capability",
        "No claim moved, in V1 or in V2.",
        "**`v1.0.0`.** The tag and the release were not touched.",
        "**It rewrote V1 decision history in place.**",
        "## Why the image was not rotated in that change",
        f"`{RECONCILED_EX07_SCOPE['findingId']}`",
        f"until {RECONCILED_EX07_SCOPE['reviewBy']}",
        "(ex-07-runtime-image-exception.md)",
        "(v2-s1-004-pr2-validation.md)",
    ):
        assert _flat(phrase) in body, phrase


def test_the_assessment_is_kept_as_merged_with_a_dated_correction() -> None:
    text = ASSESSMENT_PATH.read_text(encoding="utf-8")
    heading = "\n## Later correction\n"
    assert text.count(heading) == 1
    merged = text[: text.index(heading)]
    assert _sha256(merged) == MERGED_ASSESSMENT_SHA256, (
        "the EX-07 assessment above its later correction is no longer the record "
        "pull request #103 merged"
    )
    correction = _flat(text[text.index(heading) :])
    assert "Added on 2026-10-01 by `V2-S1-004-PR2`." in correction
    assert "v2-s1-004-pr2-security-maintenance-reconciliation.md" in correction


def test_the_validation_record_names_the_identity_it_restored_from() -> None:
    body = _flat(VALIDATION_PATH.read_text(encoding="utf-8"))
    for identity in (
        RELEASED_DECISION_SHA256,
        "c1f8d9778a825ca1bacf3d95a53cd2f7eae371bf",
        "718ad2e0fac8ae70c6d053a2decb00e61ff3de39",
        "0fd2dfa734ce197ad63cd5793d729e97030e1c24",
    ):
        assert identity in body, identity
