"""The InferOps evidence-level model, held to the repository that publishes it.

`V1-S5-011-PR1` redefines what `C0` to `C4` mean. The failure this module exists to
prevent is not a wrong definition -- no test can catch that -- but a *second* one: a
repository that says one thing in the specification, something else in the document
the specification supersedes, and a third thing in a page written next month by
somebody who read the wrong one first.

So the checks here are about agreement, not about evidence. They establish that one
current definition exists, that the superseded meanings survive only where a reader is
told they are superseded, and that the specification's own statements about what is
*not* yet enforced are still true of the enforcing data. They establish nothing about
any run, any claim, or any record.

One gap is known and deliberately open. These checks recognise two vocabularies --
the current names and the superseded ones -- so a document that invented a *third*
set of meanings for `C0` to `C4` would be caught by neither scan. Catching that needs
a rule about what a level table may say rather than a list of what it may not, and
nothing here attempts one. It is review's job, and this comment is where a reader
finds out that it is.

The last of those is the one worth understanding. The specification says, in as many
words, that the committed strategy data still carries the superseded level names and
still applies a `C1` ceiling to the `synthetic` evidence class. That is an honest
statement today and a false one the moment that data moves.
`test_the_enforcing_data_still_carries_the_superseded_names` fails on that day, on
purpose, so that whoever moves it has to come back and correct the page that described
the old state.

This module originally named `V1-S5-011-PR2` as that day, and it was wrong. That
change versioned the *evidence-record* model -- it published
`docs/testing/claim-evidence-matrix.v1alpha2.schema.json` -- and deliberately left
`test-strategy.v1alpha1.json` alone, so the tripwire did not fire and was not supposed
to. The day this test fails is `V1-S5-012-PR1`, which replaces the ceiling mechanism.
The wrong prediction was corrected on 2026-09-23, after an independent review of
`V1-S5-011-PR2` observed that a published tripwire had been announced and had not
tripped.

The corrected prediction was wrong too, and for a reason worth keeping.
`V1-S5-012-PR1` did replace the mechanism -- it published the classification rules in
`tools/evidence_model/rules.py` -- and deliberately left this data where it is: the only
register the `synthetic` ceiling governs is the committed `v1alpha1` one, whose rows
carry no substitution metadata for the replacement to read, so lifting the ceiling
first would have removed the guard from exactly the data the replacement cannot see.
The day this test fails is `V1-S5-012-PR2`, which migrates the register and the
strategy data's terminology together. Corrected 2026-09-23, in the change that did not
fire it.

It fired in `V1-S5-012-PR2`, on the third prediction, and the change corrected the
specification in the same commit, which is what it was for. The test that replaced it
holds the opposite: the strategy data carries the current names, and the `synthetic`
class no longer covers generated input. The certification document left the list of
surfaces awaiting migration at the same time, so that list is now empty and a test
keeps it that way.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]

SPECIFICATION = "docs/testing/evidence-levels.md"
DECISION = "docs/architecture/decisions/ADR-0016-inferops-evidence-level-model.md"
CERTIFICATION = "docs/testing/certification.md"
STRATEGY_DATA = "docs/testing/test-strategy.v1alpha1.json"
PRIOR_DECISION = (
    "docs/architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md"
)

#: The current meanings, as `V1-S5-011-PR1` accepted them. The identifiers are reused
#: from the superseded model deliberately; the names are what changed.
LEVELS = (
    ("C0", "Static Evidence"),
    ("C1", "Substituted Execution Evidence"),
    ("C2", "Runtime Evidence"),
    ("C3", "Representative Evidence"),
    ("C4", "Operational Evidence"),
)

#: The meanings ADR 0005 D4 accepted on 2026-08-25 and ADR 0016 supersedes. Every
#: record written before 2026-09-23 was classified under these, so they are kept
#: readable rather than deleted.
SUPERSEDED = (
    ("C0", "Schema"),
    ("C1", "Mock"),
    ("C2", "Real controlled"),
    ("C3", "Failure"),
    ("C4", "Composed"),
)

#: The two levels that lost their meaning outright rather than being reworded. Failure
#: is an experiment's purpose and composition is a property of the path; neither is a
#: strength, which is the whole argument of ADR 0016.
WITHOUT_A_MAPPING = ("C3", "C4")

#: Documents allowed to bind the identifiers to their *current* names, because
#: publishing the definition and its mapping is their job.
MAPPING_DOCUMENTS = frozenset({SPECIFICATION, DECISION})

#: Documents that still carried a superseded meaning and were waiting for
#: `V1-S5-012-PR2` to migrate them. The certification document was the only one, and
#: that change migrated it: it no longer publishes the superseded level table. The set
#: is empty and a test holds it empty; a document that needs the old meanings now
#: cites the mapping in the specification rather than restating it.
AWAITING_MIGRATION: frozenset[str] = frozenset()

#: Where dated records live. A record here was written under whichever vocabulary was
#: current when it ran, and it is kept readable rather than edited.
HISTORICAL_ROOT = "docs/proof/"

#: Every current document allowed to state a superseded pairing -- the two that publish
#: the mapping, the two that annotate the change where a reader of the old model will
#: arrive, and whatever is still awaiting migration. The set may shrink; it may not
#: grow, because a new document reaching for the old vocabulary is the drift this
#: module exists to refuse.
MAY_STATE_A_SUPERSEDED_MEANING = (
    MAPPING_DOCUMENTS
    | AWAITING_MIGRATION
    | frozenset({PRIOR_DECISION, "docs/architecture/README.md"})
)

#: Substance the specification's disclaimer has to carry. The word `certification`
#: invites a reader to assume an outside body reviewed something, and none has.
NOT_AN_EXTERNAL_STANDARD = ("project-defined", "ISO", "NIST", "industry certification")

#: Statements the specification must keep making about itself. A definition change
#: that promotes a claim is the one failure this whole area exists to prevent, and
#: since the migration the page says both that it grants no level and that every
#: level the migration moved was justified by what ran.
RECLASSIFIES_NOTHING = (
    "reclassifies nothing",
    "justified by what actually executed",
)


#: What may sit between an identifier and its name in prose. A document that means
#: "C1 means Mock" writes it as `C1 Mock`, `C1: Mock`, `C1 (Mock)`, or `C1 -- Mock`,
#: and a scan that only knows the first of those is a scan that can be walked around
#: without trying. The independent review of this change found it that way.
EN_DASH = chr(0x2013)
EM_DASH = chr(0x2014)
SEPARATOR = rf"(?:\s|\s*[:(\-{EN_DASH}{EM_DASH}]\s*)+"

#: How much of a document counts as "where a reader lands". A supersession notice
#: further down than this is a notice the reader who skims has already missed.
NOTICE_WINDOW = 2000


def binding(identifier: str, name: str) -> str:
    """A table row binding an identifier to a name, which is how this repository
    publishes a definition: an inline code span in the first cell, the name in the
    second, and whatever the table is for in the rest of the row."""
    return rf"^\|\s*`{identifier}`\s*\|\s*{re.escape(name)}\s*\|(?P<rest>[^\n]*)"


def read(relative: str) -> str:
    path = REPO_ROOT / relative
    assert path.is_file(), f"{relative} does not exist"
    return path.read_text(encoding="utf-8")


def committed_markdown() -> list[str]:
    """Every tracked Markdown file, as `git ls-files` reports it.

    Tracked rather than present: an uncommitted draft is not yet something a reader
    can arrive at, and the link suite makes the same choice for the same reason.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "*.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [name for name in listed.split("\0") if name]


MARKDOWN = committed_markdown()


def carries_a_superseded_meaning(text: str) -> list[str]:
    """The superseded pairings a document states, as `C3 Failure` or a table row.

    Matching the identifier and the name *together* is what keeps this usable. `C3`
    alone appears as a decision-criterion identifier, a review-checklist item, and a
    load-generation concurrency level; `Failure` alone is the name of a test layer and
    a marker. Neither on its own says anything about the evidence vocabulary.
    """
    found = []
    for identifier, name in SUPERSEDED:
        pairing = (
            rf"^\|\s*`?{identifier}`?\s*\|\s*{re.escape(name)}\s*\|"
            rf"|`?{identifier}`?{SEPARATOR}{re.escape(name)}\b"
            rf"|\b{re.escape(name)}{SEPARATOR}\(?`?{identifier}`?\)?"
        )
        if re.search(pairing, text, flags=re.MULTILINE):
            found.append(f"{identifier} {name}")
    return found


def test_the_specification_exists_and_is_named_by_its_decision() -> None:
    specification = read(SPECIFICATION)
    decision = read(DECISION)

    assert SPECIFICATION.rsplit("/", 1)[-1] in decision, (
        f"{DECISION} does not name the specification it makes authoritative"
    )
    assert "ADR-0016" in specification or "ADR 0016" in specification, (
        f"{SPECIFICATION} does not name the decision that accepted it"
    )


@pytest.mark.parametrize(("identifier", "name"), LEVELS, ids=[row[0] for row in LEVELS])
def test_the_specification_publishes_every_current_level(
    identifier: str, name: str
) -> None:
    specification = read(SPECIFICATION)

    assert re.search(binding(identifier, name), specification, flags=re.MULTILINE), (
        f"{SPECIFICATION} does not bind `{identifier}` to {name!r} in a table"
    )


@pytest.mark.parametrize(("identifier", "name"), LEVELS, ids=[row[0] for row in LEVELS])
def test_the_decision_publishes_every_current_level(identifier: str, name: str) -> None:
    decision = read(DECISION)

    assert name in decision, f"{DECISION} does not publish the name {name!r}"


def test_only_the_specification_defines_the_current_levels() -> None:
    """One authoritative definition, and a second cannot arrive unnoticed.

    A definition, here, is a table row binding the identifier to the current name --
    the form this repository uses to publish an identifier. Citing a level is not
    defining one, so a document may say `C2` freely.
    """
    defining = []
    for relative in MARKDOWN:
        text = read(relative)
        if any(
            re.search(binding(identifier, name), text, flags=re.MULTILINE)
            for identifier, name in LEVELS
        ):
            defining.append(relative)

    assert set(defining) <= MAPPING_DOCUMENTS, {
        "unexpected": sorted(set(defining) - MAPPING_DOCUMENTS),
        "why": (
            "only the specification and its decision may bind C0-C4 to the current "
            "names in a table; a second definition is the drift ADR 0016 forbids"
        ),
    }
    assert SPECIFICATION in defining, (
        f"{SPECIFICATION} no longer binds the identifiers to the current names"
    )


def stating_a_superseded_meaning() -> list[str]:
    return [
        relative
        for relative in MARKDOWN
        if carries_a_superseded_meaning(read(relative))
    ]


def test_a_current_document_states_a_superseded_meaning_only_if_registered() -> None:
    """The closed list applies to current-facing documents, not to history.

    A record under `docs/proof/` is a dated artifact: it was written under whichever
    vocabulary was current when it ran, and requiring every future one to be added to
    a list here would turn this guard into paperwork. The rule below still reaches
    them -- what they may not do is present a superseded meaning without saying so.
    """
    current = {
        relative
        for relative in stating_a_superseded_meaning()
        if not relative.startswith(HISTORICAL_ROOT)
    }

    assert current <= MAY_STATE_A_SUPERSEDED_MEANING, {
        "unexpected": sorted(current - MAY_STATE_A_SUPERSEDED_MEANING),
        "why": (
            "a current document states a superseded level meaning without being "
            "registered as one that publishes the mapping, annotates the change, or "
            "is awaiting migration"
        ),
    }


def test_every_document_stating_a_superseded_meaning_declares_it_superseded() -> None:
    """Stating the old pairing is allowed only together with saying it is the old one.

    This is the rule that makes the coexistence of two vocabularies survivable: a
    reader who meets `C3 Failure` anywhere in this repository meets the word
    `superseded` and the record that superseded it in the same document. It applies
    everywhere, including to history.
    """
    undeclared = {}
    for relative in stating_a_superseded_meaning():
        text = read(relative)
        missing = []
        if "superseded" not in text.lower():
            missing.append("does not say the meaning is superseded")
        if "ADR-0016" not in text and "ADR 0016" not in text:
            missing.append("does not name ADR 0016")
        if missing:
            undeclared[relative] = missing

    assert not undeclared, undeclared


@pytest.mark.parametrize("relative", sorted(MAY_STATE_A_SUPERSEDED_MEANING))
def test_every_registered_document_still_states_a_superseded_meaning(
    relative: str,
) -> None:
    """The list shrinks as the migration lands, and never rots in place."""
    assert carries_a_superseded_meaning(read(relative)), (
        f"{relative} no longer states a superseded meaning; remove it from "
        "MAY_STATE_A_SUPERSEDED_MEANING rather than leaving a stale entry"
    )


def test_no_surface_is_awaiting_migration_any_more() -> None:
    """The pending list closed in `V1-S5-012-PR2`, and it stays closed.

    The certification document was the one surface registered as still carrying
    the superseded level meanings. It now opens by sending a reader to the
    specification and publishes no superseded pairing, so it is neither awaiting
    migration nor allowed to state an old meaning.
    """
    assert not AWAITING_MIGRATION
    certification = read(CERTIFICATION)
    assert not carries_a_superseded_meaning(certification), (
        f"{CERTIFICATION} states a superseded meaning again"
    )
    assert CERTIFICATION not in MAY_STATE_A_SUPERSEDED_MEANING
    opening = certification[:NOTICE_WINDOW]
    assert "evidence-levels.md" in opening, (
        f"{CERTIFICATION} does not send a reader to the definition where they land"
    )
    assert "does not define what a level means" in opening


@pytest.mark.parametrize(
    ("identifier", "name"), SUPERSEDED, ids=[row[0] for row in SUPERSEDED]
)
@pytest.mark.parametrize("relative", sorted(MAPPING_DOCUMENTS))
def test_the_mapping_documents_publish_every_superseded_meaning(
    relative: str, identifier: str, name: str
) -> None:
    row = re.search(binding(identifier, name), read(relative), flags=re.MULTILINE)

    assert row is not None, (
        f"{relative} does not map the superseded meaning of `{identifier}` ({name})"
    )

    if identifier in WITHOUT_A_MAPPING:
        assert "No direct mapping" in row.group("rest"), {
            "document": relative,
            "row": row.group(0),
            "why": "failure is a scenario and composition is a topology; neither is a level",
        }


@pytest.mark.parametrize("phrase", NOT_AN_EXTERNAL_STANDARD)
def test_the_specification_denies_being_an_external_standard(phrase: str) -> None:
    assert phrase in read(SPECIFICATION), (
        f"{SPECIFICATION} does not state {phrase!r}; the framework is project-defined "
        "and no outside party has reviewed it"
    )


@pytest.mark.parametrize("phrase", RECLASSIFIES_NOTHING)
def test_the_specification_states_that_it_reclassifies_nothing(phrase: str) -> None:
    assert phrase in " ".join(read(SPECIFICATION).split()), (
        f"{SPECIFICATION} does not state {phrase!r}; a definition change that could be "
        "read as promoting a claim is the failure this model exists to prevent"
    )


def test_the_prior_decision_is_amended_rather_than_rewritten() -> None:
    """ADR 0005 keeps its accepted text and gains a dated note that points here."""
    prior = read(PRIOR_DECISION)

    assert "ADR-0016-inferops-evidence-level-model.md" in prior, (
        f"{PRIOR_DECISION} does not name the record that amended its D4"
    )
    assert "2026-09-23" in prior, f"{PRIOR_DECISION} does not date the amendment"
    assert "## D4 — C0 to C2, with class ceilings" in prior, (
        f"{PRIOR_DECISION} D4 has been retitled; its accepted text is history and "
        "is not edited to be currently correct"
    )
    assert "V1 certifies at C0, C1, and C2 as" in prior, (
        f"{PRIOR_DECISION} D4's accepted text has been rewritten rather than annotated"
    )


def test_the_enforcing_data_carries_the_current_names() -> None:
    """What the tripwire that stood here became when it fired.

    `V1-S5-012-PR2` moved the strategy data: its level names are the current ones,
    and its `synthetic` class names a simulated environment -- a substitution, which
    keeps its `C1` ceiling -- and no longer generated input, which ADR 0016 D3 says
    sets no ceiling. The identifiers, ranks, ceilings, and scope flags are unchanged,
    so no layer's verdict moved.
    """
    strategy = json.loads(read(STRATEGY_DATA))
    published = {
        level["levelId"]: level["name"] for level in strategy["certificationLevels"]
    }

    assert published == dict(LEVELS), published
    for level in strategy["certificationLevels"]:
        assert "evidence-levels.md" in level["meaning"], level["levelId"]
    assert {
        level["levelId"]: level["v1Scope"] for level in strategy["certificationLevels"]
    } == {"C0": True, "C1": True, "C2": True, "C3": False, "C4": False}

    synthetic = next(
        entry
        for entry in strategy["evidenceClasses"]
        if entry["classId"] == "synthetic"
    )
    assert synthetic["maxCertification"] == "C1"
    assert "Generated input is not this class" in synthetic["meaning"]
    assert "generated inputs or" not in synthetic["meaning"]


def test_the_specification_records_what_is_enforced_since_the_migration() -> None:
    """The page used to say it was not yet enforced, and a test held it to that.

    Since `V1-S5-012-PR2` that sentence is false, and the page says what is enforced,
    over which register, and what is left to review.
    """
    specification = read(SPECIFICATION)

    assert "not yet machine-enforced" not in specification.lower(), (
        f"{SPECIFICATION} still says the rules are not enforced"
    )
    assert "claim-evidence-matrix.v1alpha2.json" in specification
    assert "test-strategy.v1alpha1.json" in specification
    assert "v1-s5-012-pr2-migration-report.md" in specification
