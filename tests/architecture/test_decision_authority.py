"""Deterministic checks over the V1 decision-ownership and sign-off register.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness.

What this suite establishes is narrow and worth stating, because the gap is the
point. It establishes that **no V1 architectural decision is left without an
accountable owner, and that no document still says one is**: every record under
``docs/architecture/decisions/`` has exactly one entry in the committed register,
every entry names a record that exists, every owner is a declared role, no entry
carries a placeholder, each record's own metadata row names the owner the register
assigns it, and the retired vocabulary of the gap -- an unassigned owner, an absent
roster given as the reason nobody signs off -- does not survive anywhere in the
decision set or the governance documents.

It establishes **nothing about whether the model is a good one**, whether the role
is held by a suitable person, or whether any accountability was ever exercised.
Those are review questions. A test that answered them would be the failure the rest
of this repository's suites exist to prevent: a rule written down being counted as a
rule enforced.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_DIR = REPO_ROOT / "docs" / "governance"
DECISIONS_DIR = REPO_ROOT / "docs" / "architecture" / "decisions"
REGISTER_PATH = GOVERNANCE_DIR / "decision-authority.v1alpha1.json"

EXPECTED_REGISTER_ID = "https://inferops.io/governance/decision-authority.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

#: Identifiers are lowercase, hyphen-separated, and safe anywhere a name is needed.
SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

#: A decision record's file name, and the identifier the register uses for it.
DECISION_FILE = re.compile(r"^(?P<decisionId>ADR-\d{4})-[a-z0-9-]+\.md$")

#: The metadata row every decision record carries. The value is whatever sits
#: between the second and third pipe, which is where the owner has to be.
OWNER_ROW = re.compile(r"^\|\s*Decision owner\s*\|(?P<value>[^|]*)\|", re.MULTILINE)

#: A role or authority identifier as a document publishes it: an inline code span.
CODE_SPAN = re.compile(r"`([a-z0-9][a-z0-9-]*)`")

#: An ADR identifier as a document publishes it, in the two spellings these
#: documents use: "ADR-0008" in a path, and "ADR 0008" in prose and link text.
ADR_MENTION = re.compile(r"\bADR[- ](\d{4})\b")

REQUIRED_ROLE_FIELDS = (
    "roleId",
    "name",
    "heldBy",
    "conferredBy",
    "publicRoster",
    "holderCountToday",
    "whyNotAPerson",
)
REQUIRED_AUTHORITY_FIELDS = (
    "authorityId",
    "name",
    "question",
    "heldBy",
    "exercisedBy",
    "doesNotEstablish",
)
REQUIRED_OWNER_FIELDS = ("decisionId", "path", "owner", "assignedOn", "basis")

#: The vocabulary this change retires. A decision record or a governance document
#: that still uses one of these about decision ownership or sign-off authority is
#: describing a gap that has been closed, which is a worse failure than the gap
#: was: a reader trusts the stalest sentence they find.
RETIRED_PHRASES = (
    "unassigned; no public maintainer roster",
    "no public maintainer roster exists yet",
    "roster pending",
)

#: An inline code span. Stripping these is what lets a document quote the retired
#: wording without asserting it -- but only in the two files below, because a code
#: span is typesetting and not a quotation mark, and any document could reintroduce
#: the unassigned-owner claim inside backticks. The independent review of the change
#: that added this file raised exactly that: the first version stripped spans
#: everywhere, which would have let a future assertion through anywhere at all.
INLINE_CODE = re.compile(r"`[^`\n]*`")

#: The only two documents permitted to contain the retired wording at all. Both
#: exist to retire it and cannot say what changed without reproducing it. Everywhere
#: else the phrase is refused outright, code span or not.
QUOTING_DOCUMENTS = frozenset(
    {
        "docs/architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md",
        "docs/governance/decision-authority.md",
    }
)


def prose_only(text: str) -> str:
    """The document with every inline code span removed, lowercased."""
    return INLINE_CODE.sub(" ", text).lower()


def searchable(relative_path: str, text: str) -> str:
    """The text a retired phrase is looked for in, for one document.

    In a document that retires the vocabulary, inline code spans are removed, so
    a quotation passes and a bare assertion in the same file still fails. In every
    other document nothing is removed, so backticks buy nothing.
    """
    if relative_path in QUOTING_DOCUMENTS:
        return prose_only(text)
    return text.lower()


#: Placeholder owners. An entry carrying one of these is the state this register
#: exists to make impossible.
PLACEHOLDER_OWNERS = ("unassigned", "none", "tbd", "todo", "pending", "undecided")

#: Governance and decision documents that must agree with the register. Evidence
#: records under docs/proof/ and the changelog are deliberately excluded: both are
#: statements about a moment that has passed, and rewriting one to match today
#: would be falsifying a record rather than fixing a document.
GOVERNED_DOCUMENTS = (
    "CONTRIBUTING.md",
    "docs/governance/repository.md",
    "docs/governance/decision-authority.md",
    "docs/architecture/README.md",
    "docs/releases.md",
    "docs/testing/certification.md",
    "docs/testing/claim-test-matrix.md",
    "docs/testing/claim-evidence-matrix.md",
    "docs/security/control-matrix.md",
    "docs/architecture/boundary-review-checklist.md",
    "docs/architecture/system-architecture.md",
    "docs/architecture/resource-ownership.md",
    "docs/architecture/project-boundaries.md",
    "docs/testing/test-inventory.md",
    "README.md",
)


def load_register() -> dict:
    return json.loads(REGISTER_PATH.read_text(encoding="utf-8"))


REGISTER = load_register()
ROLES = REGISTER["roles"]
AUTHORITIES = REGISTER["authorities"]
DECISION_OWNERS = REGISTER["decisionOwners"]
OWNERSHIP_BASES = REGISTER["ownershipBases"]
ROLE_BY_ID = {role["roleId"]: role for role in ROLES}
OWNER_BY_DECISION = {entry["decisionId"]: entry for entry in DECISION_OWNERS}


def decision_files() -> dict[str, Path]:
    """Every decision record on disk, keyed by the identifier in its file name."""
    found: dict[str, Path] = {}
    for path in sorted(DECISIONS_DIR.glob("ADR-*.md")):
        match = DECISION_FILE.match(path.name)
        assert match, f"{path.name} does not follow ADR-NNNN-short-slug.md"
        found[match.group("decisionId")] = path
    return found


DECISION_FILES = decision_files()


def authority_document() -> str:
    return (GOVERNANCE_DIR / "decision-authority.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# The register itself
# --------------------------------------------------------------------------


def test_the_register_declares_its_identity_and_contract_version() -> None:
    assert REGISTER["$id"] == EXPECTED_REGISTER_ID
    assert REGISTER["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_the_register_points_back_at_the_records_it_describes() -> None:
    for field in ("decisionRef", "documentRef", "governanceRef", "decisionIndexRef"):
        referenced = REPO_ROOT / REGISTER[field]
        assert referenced.is_file(), {field: REGISTER[field]}


def test_the_register_is_not_empty() -> None:
    assert ROLES, "no role is declared"
    assert AUTHORITIES, "no authority is declared"
    assert DECISION_OWNERS, "no decision has an owner"


@pytest.mark.parametrize("role", ROLES, ids=lambda role: role["roleId"])
def test_every_role_declares_every_required_field(role: dict) -> None:
    assert set(role) == set(REQUIRED_ROLE_FIELDS), role["roleId"]
    assert SLUG.match(role["roleId"]), role["roleId"]
    assert isinstance(role["publicRoster"], bool)
    assert isinstance(role["holderCountToday"], int)
    assert role["holderCountToday"] >= 1, role["roleId"]


@pytest.mark.parametrize("authority", AUTHORITIES, ids=lambda row: row["authorityId"])
def test_every_authority_declares_every_required_field(authority: dict) -> None:
    assert set(authority) == set(REQUIRED_AUTHORITY_FIELDS), authority["authorityId"]
    assert SLUG.match(authority["authorityId"]), authority["authorityId"]


@pytest.mark.parametrize("authority", AUTHORITIES, ids=lambda row: row["authorityId"])
def test_every_authority_is_held_by_a_declared_role(authority: dict) -> None:
    assert authority["heldBy"] in ROLE_BY_ID, {
        "authority": authority["authorityId"],
        "held by": authority["heldBy"],
        "declared roles": sorted(ROLE_BY_ID),
    }


@pytest.mark.parametrize("authority", AUTHORITIES, ids=lambda row: row["authorityId"])
def test_every_authority_says_what_it_does_not_establish(authority: dict) -> None:
    """The load-bearing half of this register.

    An authority that lists only what it grants reads as more than it is. Every
    one of these four is exercised by merging a pull request, and a merge is not
    evidence, not an external review, and not a promotion of anything.
    """
    limits = authority["doesNotEstablish"]
    assert isinstance(limits, list) and limits, authority["authorityId"]
    for limit in limits:
        assert isinstance(limit, str) and limit.strip(), authority["authorityId"]


def test_the_four_kinds_of_authority_are_kept_apart() -> None:
    """Collapsing them is the failure this register was written against.

    They are all held by one role today, because the role has one holder. That
    is a fact about the project, not a reason to publish one authority where
    there are four: the day a second maintainer arrives, splitting them has to
    be an amendment to a list that exists.
    """
    required = {
        "adr-decision-ownership",
        "adr-acceptance-and-amendment",
        "claim-evidence-sign-off",
        "v1-release-approval",
    }
    declared = {authority["authorityId"] for authority in AUTHORITIES}
    assert required <= declared, {
        "missing": sorted(required - declared),
        "declared": sorted(declared),
    }


def test_identifiers_are_unique() -> None:
    role_ids = [role["roleId"] for role in ROLES]
    authority_ids = [authority["authorityId"] for authority in AUTHORITIES]
    decision_ids = [entry["decisionId"] for entry in DECISION_OWNERS]
    assert len(role_ids) == len(set(role_ids))
    assert len(authority_ids) == len(set(authority_ids))
    assert len(decision_ids) == len(set(decision_ids))


def test_every_declared_role_is_used() -> None:
    """A role nothing points at is a role that will drift without being noticed."""
    used = {authority["heldBy"] for authority in AUTHORITIES}
    used |= {entry["owner"] for entry in DECISION_OWNERS}
    assert set(ROLE_BY_ID) == used, {
        "declared": sorted(ROLE_BY_ID),
        "used": sorted(used),
    }


def test_the_register_declares_its_limits() -> None:
    for field in ("transferRules", "limits"):
        rules = REGISTER[field]
        assert isinstance(rules, list) and rules, field
        for rule in rules:
            assert isinstance(rule, str) and rule.strip(), field


# --------------------------------------------------------------------------
# Every decision, and exactly one owner each
# --------------------------------------------------------------------------


def test_every_decision_record_has_an_entry() -> None:
    """The direction that matters: a new record cannot arrive unowned."""
    assert set(DECISION_FILES) == set(OWNER_BY_DECISION), {
        "records with no entry": sorted(set(DECISION_FILES) - set(OWNER_BY_DECISION)),
        "entries with no record": sorted(set(OWNER_BY_DECISION) - set(DECISION_FILES)),
    }


@pytest.mark.parametrize("entry", DECISION_OWNERS, ids=lambda row: row["decisionId"])
def test_every_entry_declares_every_required_field(entry: dict) -> None:
    assert set(entry) == set(REQUIRED_OWNER_FIELDS), entry["decisionId"]


@pytest.mark.parametrize("entry", DECISION_OWNERS, ids=lambda row: row["decisionId"])
def test_every_entry_names_the_file_it_owns(entry: dict) -> None:
    path = REPO_ROOT / entry["path"]
    assert path.is_file(), entry
    assert path == DECISION_FILES[entry["decisionId"]], entry


@pytest.mark.parametrize("entry", DECISION_OWNERS, ids=lambda row: row["decisionId"])
def test_every_entry_has_an_owner_that_is_a_declared_role(entry: dict) -> None:
    assert entry["owner"] in ROLE_BY_ID, {
        "decision": entry["decisionId"],
        "owner": entry["owner"],
        "declared roles": sorted(ROLE_BY_ID),
    }


@pytest.mark.parametrize("entry", DECISION_OWNERS, ids=lambda row: row["decisionId"])
def test_no_entry_carries_a_placeholder_owner(entry: dict) -> None:
    """The exact state this register exists to make impossible.

    Fourteen records carried ``Unassigned`` for fourteen records' worth of time,
    and no check read the field. This is that check.
    """
    owner = entry["owner"].strip().lower()
    assert owner not in PLACEHOLDER_OWNERS, entry
    assert owner, entry


@pytest.mark.parametrize("entry", DECISION_OWNERS, ids=lambda row: row["decisionId"])
def test_every_entry_declares_a_recognised_basis(entry: dict) -> None:
    assert entry["basis"] in OWNERSHIP_BASES, {
        "decision": entry["decisionId"],
        "basis": entry["basis"],
        "declared": sorted(OWNERSHIP_BASES),
    }


@pytest.mark.parametrize("entry", DECISION_OWNERS, ids=lambda row: row["decisionId"])
def test_every_entry_records_the_date_it_was_assigned(entry: dict) -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["assignedOn"]), entry


def test_every_declared_basis_is_used() -> None:
    used = {entry["basis"] for entry in DECISION_OWNERS}
    assert set(OWNERSHIP_BASES) == used, {
        "declared": sorted(OWNERSHIP_BASES),
        "used": sorted(used),
    }


# --------------------------------------------------------------------------
# The records themselves
# --------------------------------------------------------------------------


@pytest.mark.parametrize("entry", DECISION_OWNERS, ids=lambda row: row["decisionId"])
def test_every_record_publishes_the_owner_the_register_assigns_it(
    entry: dict,
) -> None:
    """The register and the record have to say the same thing.

    Reading the register alone would let a record's own metadata drift back to
    ``Unassigned`` while the data said otherwise, which is the shape of drift
    this repository has hit in four other documents.
    """
    text = DECISION_FILES[entry["decisionId"]].read_text(encoding="utf-8")
    rows = OWNER_ROW.findall(text)
    assert len(rows) == 1, {
        "decision": entry["decisionId"],
        "Decision owner rows found": len(rows),
    }

    value = rows[0]
    published = CODE_SPAN.findall(value)
    assert published == [entry["owner"]], {
        "decision": entry["decisionId"],
        "the register assigns": entry["owner"],
        "the record publishes": published,
        "row": value.strip(),
    }


@pytest.mark.parametrize("entry", DECISION_OWNERS, ids=lambda row: row["decisionId"])
def test_a_retrospective_assignment_says_so_in_the_record(entry: dict) -> None:
    """C3 of the decision that added this file, enforced.

    A change that gives fourteen records an owner on one day looks, in a diff,
    exactly like a change that reviewed fourteen records on one day. The two are
    not close to the same thing and the difference is not recoverable from the
    row, so the row has to carry it.
    """
    row = OWNER_ROW.search(
        DECISION_FILES[entry["decisionId"]].read_text(encoding="utf-8")
    )
    assert row is not None, entry["decisionId"]
    value = row.group("value")
    says_retrospective = "retrospectively" in value.lower()
    expected = entry["basis"] == "assigned-retrospectively"
    assert says_retrospective is expected, {
        "decision": entry["decisionId"],
        "basis in the register": entry["basis"],
        "row": value.strip(),
    }


@pytest.mark.parametrize("decision_id", sorted(DECISION_FILES), ids=lambda row: row)
def test_no_decision_record_still_describes_its_owner_as_unassigned(
    decision_id: str,
) -> None:
    """Quoting the retired wording is allowed; asserting it is not.

    ADR 0015 and the document beside it both have to reproduce the sentence they
    retire, or a reader cannot tell what changed. Both put it in an inline code
    span, and this check reads prose with the spans removed.
    """
    path = DECISION_FILES[decision_id]
    relative = path.relative_to(REPO_ROOT).as_posix()
    text = searchable(relative, path.read_text(encoding="utf-8"))
    for phrase in RETIRED_PHRASES:
        assert phrase not in text, {
            "decision": decision_id,
            "retired phrase still asserted": phrase,
            "quoting it is allowed only in": sorted(QUOTING_DOCUMENTS),
        }


@pytest.mark.parametrize("document", GOVERNED_DOCUMENTS, ids=lambda row: row)
def test_no_governance_document_still_describes_the_authority_as_unassigned(
    document: str,
) -> None:
    text = searchable(document, (REPO_ROOT / document).read_text(encoding="utf-8"))
    for phrase in RETIRED_PHRASES:
        assert phrase not in text, {
            "document": document,
            "retired phrase still asserted": phrase,
            "quoting it is allowed only in": sorted(QUOTING_DOCUMENTS),
        }


def test_the_security_baseline_no_longer_leaves_sign_off_undecided() -> None:
    """ADR 0008 D13 was the one decision that named this gap as its whole support.

    It is checked by identifier rather than by prose: the row has to stop saying
    it is not decided, and the committed open question behind it has to stop
    giving the absent roster as the reason.
    """
    record = (DECISIONS_DIR / "ADR-0008-v1-security-baseline.md").read_text(
        encoding="utf-8"
    )
    d13_rows = [line for line in record.splitlines() if line.startswith("| D13 |")]
    assert len(d13_rows) == 1, d13_rows
    assert "not decided" not in d13_rows[0].lower(), d13_rows[0]

    baseline = json.loads(
        (REPO_ROOT / "docs" / "security" / "security-baseline.v1alpha1.json").read_text(
            encoding="utf-8"
        )
    )
    questions = {row["questionId"]: row for row in baseline["openQuestions"]}
    assert "who-owns-security-verification" in questions
    why = questions["who-owns-security-verification"]["whyNotAnswered"].lower()
    assert "adr 0015" in why, why
    assert "claim-evidence-sign-off" in why, why


# --------------------------------------------------------------------------
# The document beside the register
# --------------------------------------------------------------------------


def test_the_document_publishes_every_role_and_authority() -> None:
    published = set(CODE_SPAN.findall(authority_document()))
    required = set(ROLE_BY_ID) | {row["authorityId"] for row in AUTHORITIES}
    required |= set(OWNERSHIP_BASES)
    assert required <= published, {
        "missing from the document": sorted(required - published)
    }


def test_the_document_publishes_every_decision_the_register_owns() -> None:
    document = authority_document()
    published = {f"ADR-{number}" for number in ADR_MENTION.findall(document)}
    assert set(OWNER_BY_DECISION) <= published, {
        "missing from the document": sorted(set(OWNER_BY_DECISION) - published)
    }


def test_the_document_publishes_no_decision_the_register_lacks() -> None:
    """The mirror. A row for a record that is not owned would be the drift
    running the other way, and is the easier one to introduce by hand."""
    published = {
        f"ADR-{number}" for number in ADR_MENTION.findall(authority_document())
    }
    assert published <= set(OWNER_BY_DECISION), {
        "published but not owned": sorted(published - set(OWNER_BY_DECISION))
    }


def test_the_document_counts_the_decisions_the_register_holds() -> None:
    """A count in prose beside a list in data is the sentence that drifts.

    This repository has watched it drift in the test inventory three times and
    in the architecture index once, each time with the document narrating the
    drift as the reason it was not checked.
    """
    words = {
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
    total = len(DECISION_OWNERS)
    retrospective = sum(
        1 for entry in DECISION_OWNERS if entry["basis"] == "assigned-retrospectively"
    )
    document = authority_document()
    assert f"{words[total].capitalize()} records." in document, {
        "the register holds": total,
        "expected sentence": f"{words[total].capitalize()} records.",
    }
    assert f"{words[retrospective].capitalize()} of the {words[total]}" in document, {
        "assigned retrospectively": retrospective,
        "expected phrase": f"{words[retrospective].capitalize()} of the {words[total]}",
    }


@pytest.mark.parametrize("document", sorted(QUOTING_DOCUMENTS), ids=lambda row: row)
def test_a_document_allowed_to_quote_the_retired_wording_actually_quotes_it(
    document: str,
) -> None:
    """The exemption list is two entries and must stay earned.

    A path that stops quoting the retired sentence does not need the exemption,
    and leaving it on the list would quietly weaken the check for that file. A
    path added to the list without quoting anything would weaken it outright.
    """
    text = (REPO_ROOT / document).read_text(encoding="utf-8")
    raw = text.lower()
    assert any(phrase in raw for phrase in RETIRED_PHRASES), {
        "document": document,
        "why this failed": (
            "it is on the quoting list but contains none of the retired phrases; "
            "remove it from QUOTING_DOCUMENTS rather than leaving the exemption on"
        ),
    }
    stripped = prose_only(text)
    assert not any(phrase in stripped for phrase in RETIRED_PHRASES), {
        "document": document,
        "why this failed": (
            "it asserts a retired phrase outside a code span; quoting is allowed, "
            "asserting is not, even here"
        ),
    }


def test_every_quoting_document_is_a_file_that_exists() -> None:
    for document in QUOTING_DOCUMENTS:
        assert (REPO_ROOT / document).is_file(), document


def test_the_register_reads_as_data_it_did_not_execute() -> None:
    """Nothing in this suite imports the register or runs anything from it.

    It is read with json.loads from a path this module computes, exactly like
    the ownership inventory beside it. Stated as a test so that a later change
    that made it importable would have to delete this rather than slip past.
    """
    assert REGISTER_PATH.suffix == ".json"
    assert REGISTER_PATH.is_file()
