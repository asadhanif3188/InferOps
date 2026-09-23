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
statement today and a false one the moment `V1-S5-011-PR2` versions the data model.
`test_the_enforcing_data_still_carries_the_superseded_names` fails on that day, on
purpose, so that whoever migrates the data has to come back and correct the page that
described the old state.
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

#: Documents that still carry a superseded meaning and are waiting for `V1-S5-012-PR2`
#: to migrate them. Each one must carry a supersession notice and send a reader to the
#: authoritative definition, and the set may shrink as the migration lands.
AWAITING_MIGRATION = frozenset({CERTIFICATION})

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

#: Statements `V1-S5-011-PR1` must not be readable as having made. A definition change
#: that promotes a claim is the one failure this whole area exists to prevent.
RECLASSIFIES_NOTHING = (
    "reclassifies nothing",
    "keeps the level it was given",
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


@pytest.mark.parametrize("relative", sorted(AWAITING_MIGRATION))
def test_every_surface_awaiting_migration_points_at_the_authoritative_definition(
    relative: str,
) -> None:
    """The pending list shrinks as the migration lands, and never rots in place."""
    assert "evidence-levels.md" in read(relative), (
        f"{relative} does not send a reader to the authoritative definition"
    )


@pytest.mark.parametrize("relative", sorted(AWAITING_MIGRATION))
def test_every_surface_awaiting_migration_opens_with_the_supersession_notice(
    relative: str,
) -> None:
    """The notice has to be where a reader arrives, not merely somewhere in the file.

    Without this, the banner at the top of the certification document could be
    deleted and the suite would still pass on an unrelated later mention of the word
    `superseded` -- which is exactly the failure the banner exists to prevent, since
    a reader who skims the level table and leaves never reaches the later mention.
    """
    opening = read(relative)[:NOTICE_WINDOW]

    assert "superseded" in opening.lower(), {
        "document": relative,
        "why": (
            "no supersession notice in the opening of the document; a reader who "
            "stops at the level table would take the superseded meanings as current"
        ),
    }
    assert "evidence-levels.md" in opening, (
        f"{relative} does not point at the authoritative definition where a reader lands"
    )


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
    assert phrase in read(SPECIFICATION), (
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


def test_the_enforcing_data_still_carries_the_superseded_names() -> None:
    """A tripwire, and it is meant to fire.

    The specification tells a reader that enforcement has not moved. When
    `V1-S5-011-PR2` versions the data model this test fails, and the page that made
    the claim has to be corrected in the same change rather than a later one.
    """
    strategy = json.loads(read(STRATEGY_DATA))
    published = {
        level["levelId"]: level["name"] for level in strategy["certificationLevels"]
    }

    assert published == dict(SUPERSEDED), {
        "published": published,
        "why": (
            "the enforcing data no longer matches the superseded names, so the "
            "specification's statement that enforcement is unchanged has stopped "
            "being true; correct docs/testing/evidence-levels.md and this module"
        ),
    }

    synthetic = next(
        entry
        for entry in strategy["evidenceClasses"]
        if entry["classId"] == "synthetic"
    )
    assert synthetic["maxCertification"] == "C1", {
        "ceiling": synthetic["maxCertification"],
        "why": (
            "the synthetic ceiling is the rule the specification records as still "
            "enforced and too broad; when V1-S5-012-PR1 replaces it, the specification "
            "and this module have to say so"
        ),
    }


def test_the_specification_records_that_it_is_not_yet_enforced() -> None:
    specification = read(SPECIFICATION)

    assert "not yet machine-enforced" in specification.lower(), (
        f"{SPECIFICATION} does not record that these rules are not yet enforced"
    )
    assert "test-strategy.v1alpha1.json" in specification, (
        f"{SPECIFICATION} does not name the data that still enforces the superseded rules"
    )
