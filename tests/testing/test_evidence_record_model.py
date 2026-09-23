"""The versioned claim and evidence data model, held to what it claims to be.

`V1-S5-011-PR1` decided that an evidence level belongs to an evidence record and
that one claim may have several. `v1alpha1` cannot represent either. This module
checks the version that can.

What it establishes is narrow and worth stating before the first assertion. It
establishes that the published schema has the shape the specification describes,
that a record at each of the five levels can be written down and validated, that
the shapes the model exists to refuse are refused, and that the committed
`v1alpha1` register reads into the new version without anything being lost or
invented. It establishes **nothing** about any claim, any record, or any run: no
committed evidence is reclassified here, the fixtures are illustrations rather
than results, and a fixture at `C3` or `C4` is a shape this repository has never
reached.

Two of the checks here were written to fail later: tripwires that passed while
the register was unmigrated, so that `V1-S5-012-PR2` would have to come back and
correct this module and the documents describing the unmigrated state in the same
change that migrated it. They fired there, and that change replaced them with the
state they were waiting for: the authoritative register is `v1alpha2`, it holds a
level on every record, and the superseded `v1alpha1` register is kept unchanged as
the migration's starting point. `tests/testing/test_evidence_migration.py` holds the
comparison between the two.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tools.evidence_model import (
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
    LEGACY_FIELD_DESTINATIONS,
    LEGACY_REGISTER_PATH,
    REGISTER_PATH,
    load_legacy_register,
    load_register,
    load_schema,
    read_legacy_as_v1alpha2,
    validate_claim,
    validate_record,
    validate_register,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]

SPECIFICATION = REPO_ROOT / "docs" / "testing" / "evidence-levels.md"
MODEL_DOCUMENT = REPO_ROOT / "docs" / "testing" / "evidence-record-model.md"
TESTING_INDEX = REPO_ROOT / "docs" / "testing" / "README.md"

FIXTURES = REPO_ROOT / "tests" / "testing" / "fixtures" / "evidence-record-v1alpha2"
REFUSALS = json.loads((FIXTURES / "refusals.json").read_text(encoding="utf-8"))

SCHEMA = load_schema()

#: The five identifiers, so that a missing fixture is a failure rather than a gap
#: nobody notices. The *names* are deliberately not written here: this module reads
#: them out of the specification, which is the only document allowed to bind them.
LEVELS = ("C0", "C1", "C2", "C3", "C4")


def fixtures(kind: str, verdict: str) -> list[Path]:
    return sorted((FIXTURES / kind / verdict).glob("*.json"))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


VALID_RECORDS = fixtures("records", "valid")
INVALID_RECORDS = fixtures("records", "invalid")
VALID_CLAIMS = fixtures("claims", "valid")
INVALID_CLAIMS = fixtures("claims", "invalid")


# ------------------------------------------------------------------- the schema


def test_the_schema_is_a_valid_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_the_schema_declares_the_version_and_what_it_supersedes() -> None:
    """A version that does not say what it replaces leaves the reader to guess."""
    assert SCHEMA["properties"]["contractVersion"]["const"] == CONTRACT_VERSION
    assert SCHEMA["properties"]["supersedes"]["const"] == LEGACY_CONTRACT_VERSION


def specification_level_names() -> dict[str, str]:
    """The five names, read out of the document that defines them.

    Read rather than restated. `tests/testing/test_evidence_levels.py` refuses a
    second document binding these identifiers to their names; this module would be
    a second *data* definition of the same thing if it held its own copy, and the
    two would be free to disagree the first time one of them was edited.
    """
    text = SPECIFICATION.read_text(encoding="utf-8")
    found = {}
    for identifier in LEVELS:
        match = re.search(
            rf"^\|\s*`{identifier}`\s*\|\s*([^|]+?)\s*\|", text, flags=re.MULTILINE
        )
        assert match is not None, f"{SPECIFICATION} no longer binds `{identifier}`"
        found[identifier] = match.group(1)
    return found


def test_the_level_identifiers_are_exactly_the_five_the_specification_publishes() -> (
    None
):
    published = SCHEMA["$defs"]["evidenceLevelId"]["enum"]

    assert published == list(LEVELS), published


def test_a_register_carrying_level_names_must_match_the_specification() -> None:
    """The data may copy the names; it may not become a second definition of them.

    The schema forces `definitionRef` to the specification, and the reader below
    is the only thing in this repository that writes the block. So the check that
    matters is that what the reader writes is what the specification says.
    """
    expected = specification_level_names()
    written = {
        level["levelId"]: level["name"]
        for level in read_legacy_as_v1alpha2()["evidenceLevels"]
    }

    assert written == expected, {
        "in the data": written,
        "in the specification": expected,
        "why": (
            "the level vocabulary carried in a register is a copy of the "
            "specification's table; a copy that drifts is the second definition "
            "ADR 0016 forbids"
        ),
    }
    definition_refs = {
        level["definitionRef"] for level in read_legacy_as_v1alpha2()["evidenceLevels"]
    }
    assert definition_refs == {"docs/testing/evidence-levels.md"}


def test_no_field_in_the_new_model_is_named_certification_level() -> None:
    """Except inside the block whose whole purpose is to carry a legacy value.

    The failure this refuses is the cheap migration: rename `certificationLevel`
    to `evidenceLevel`, leave it on the claim, and declare the model versioned.
    That change would keep every defect ADR 0016 identified and add a version
    number to it.
    """
    carrier = SCHEMA["$defs"]["legacyClassification"]["properties"]
    assert "certificationLevel" in carrier, (
        "the legacy value has to land somewhere or the transformation loses it"
    )

    def walk(node: object, trail: str) -> list[str]:
        found: list[str] = []
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "certificationLevel" and "legacyClassification" not in trail:
                    found.append(f"{trail}.{key}")
                found.extend(walk(value, f"{trail}.{key}"))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                found.extend(walk(value, f"{trail}[{index}]"))
        return found

    assert not walk(SCHEMA, "$"), walk(SCHEMA, "$")


def test_a_claim_may_not_carry_an_evidence_level() -> None:
    """The structural change, asserted against the schema rather than a fixture."""
    claim = SCHEMA["$defs"]["claim"]

    assert "evidenceLevel" not in claim["properties"]
    assert claim["additionalProperties"] is False, (
        "a claim that accepts unknown properties accepts a level on the claim"
    )
    assert "evidenceRecords" in claim["required"]


def test_an_evidence_record_carries_the_level() -> None:
    record = SCHEMA["$defs"]["evidenceRecord"]

    assert "evidenceLevel" in record["properties"]
    assert record["additionalProperties"] is False


@pytest.mark.parametrize(
    "field",
    [
        "execution",
        "workload",
        "environment",
        "versions",
        "procedure",
        "measurement",
        "acceptanceCriteria",
        "results",
        "evidenceRefs",
        "limitations",
        "doesNotEstablish",
    ],
)
def test_a_record_can_answer_every_question_the_specification_asks_of_one(
    field: str,
) -> None:
    """The list is the specification's own: what a record states, one field each."""
    assert field in SCHEMA["$defs"]["evidenceRecord"]["properties"], field


def migrated_block() -> dict:
    """The `then` clause that applies to a record claiming to be migrated."""
    for block in SCHEMA["$defs"]["evidenceRecord"]["allOf"]:
        if (
            block["if"]["properties"].get("migrationState", {}).get("const")
            == "migrated"
        ):
            return dict(block["then"])
    raise AssertionError("the schema no longer has a block for a migrated record")


def test_a_migrated_record_must_say_what_ran_where_and_how_to_repeat_it() -> None:
    """The fields the specification says every record states, made mandatory.

    The first draft of this schema made all four optional at every level, so a
    record could be classified `C2` -- *the actual components required to evaluate
    the claim executed* -- while naming no component, no workload, no immutable
    identifier, and no artifact a reader could open. Two independent reviews of
    this change found it. The refused fixtures beside this module drive each one.
    """
    block = migrated_block()

    assert {"execution", "workload", "environment", "procedure"} <= set(
        block["required"]
    ), block["required"]
    assert block["properties"]["evidenceRefs"]["minItems"] == 1
    assert [sorted(branch.get("required", [])) for branch in block["anyOf"]] == [
        ["versions"],
        ["versionsRecordedIn"],
    ], block["anyOf"]


def test_a_record_that_executed_something_names_what_executed() -> None:
    """`C1` to `C4` all assert an execution, so all four have to describe one."""
    for block in SCHEMA["$defs"]["evidenceRecord"]["allOf"]:
        levels = block["if"]["properties"].get("evidenceLevel", {}).get("enum")
        if levels == ["C1", "C2", "C3", "C4"]:
            execution = block["then"]["properties"]["execution"]
            assert "executedComponents" in execution["required"]
            assert execution["properties"]["executedComponents"]["minItems"] == 1
            return
    raise AssertionError("the schema no longer constrains execution at C1 to C4")


def test_substitution_and_workload_origin_are_separate_fields() -> None:
    """The defect ADR 0016 D3 names, refused in the shape rather than in review."""
    record = SCHEMA["$defs"]["evidenceRecord"]["properties"]
    substitution = SCHEMA["$defs"]["substitution"]["properties"]
    workload = SCHEMA["$defs"]["workload"]["properties"]

    assert "execution" in record and "workload" in record
    assert "claimMaterial" in substitution
    assert "source" in workload
    assert "claimMaterial" not in workload
    assert "source" not in substitution


def test_representativeness_is_workload_metadata_and_not_a_level() -> None:
    workload = SCHEMA["$defs"]["workload"]["properties"]
    representativeness = workload["representativeness"]["properties"]

    assert set(representativeness) == {"declared", "intendedUse", "assumptions"}
    assert representativeness["assumptions"]["minItems"] == 1


def test_an_observation_period_and_a_production_context_can_be_recorded() -> None:
    production = SCHEMA["$defs"]["productionContext"]

    assert set(production["required"]) == {
        "organization",
        "dependingWorkload",
        "observationPeriod",
        "knownGaps",
    }


# ------------------------------------------------------------------- the shapes


@pytest.mark.parametrize("path", VALID_RECORDS, ids=lambda path: path.stem)
def test_every_valid_record_fixture_validates(path: Path) -> None:
    assert validate_record(load(path)) == []


@pytest.mark.parametrize("path", VALID_CLAIMS, ids=lambda path: path.stem)
def test_every_valid_claim_fixture_validates(path: Path) -> None:
    assert validate_claim(load(path)) == []


@pytest.mark.parametrize("level", LEVELS)
def test_a_valid_record_shape_exists_for_every_level(level: str) -> None:
    """All five, including the two this repository has never reached.

    A model that can only express the levels a project has already reached is a
    model that will be extended under pressure, by whoever first needs the level
    it left out.
    """
    reached = {
        str(load(path)["evidenceLevel"])
        for path in VALID_RECORDS
        if load(path).get("evidenceLevel")
    }

    assert level in reached, {
        "level": level,
        "fixtures": sorted(reached),
        "why": "every level needs a committed valid shape, reached or not",
    }


def test_no_fixture_asserts_that_v1_holds_c3_or_c4_evidence() -> None:
    """The fixtures are shapes. Nothing in the register reaches either level.

    Without this, a `C4` fixture committed beside the register is one careless
    citation away from being read as a record. Two things keep it from becoming
    one: the document says so in words, and the register is checked for the
    values rather than trusted not to have acquired them.
    """
    document = MODEL_DOCUMENT.read_text(encoding="utf-8")
    assert "no evidence in this repository is `c3` or `c4`" in document.lower(), (
        f"{MODEL_DOCUMENT} does not say that the C3 and C4 fixtures are shapes "
        "rather than results"
    )

    reached = {
        row["certificationLevel"]
        for row in load_legacy_register()["claims"]
        if row["certificationLevel"]
    }
    assert not reached & {"C3", "C4"}, {
        "in the register": sorted(reached),
        "why": (
            "a committed claim reached C3 or C4 under either vocabulary; the "
            "fixtures stop being illustrations and the document stops being true"
        ),
    }


def test_a_claim_may_hold_several_records_at_several_levels() -> None:
    """The requirement the whole version exists for."""
    claim = load(
        FIXTURES / "claims/valid/claim-with-three-records-at-three-levels.json"
    )

    levels = [record["evidenceLevel"] for record in claim["evidenceRecords"]]

    assert validate_claim(claim) == []
    assert len(levels) == 3
    assert len(set(levels)) == 3, levels


def test_a_synthetic_workload_does_not_impose_a_c1_ceiling() -> None:
    """ADR 0016 D3, as a shape: origin is separate from substitution.

    The positive half. The negative half is the refused fixture below, which
    classifies the same run `C1` on the strength of its input and is refused for
    naming no claim-material substitution.
    """
    record = load(
        FIXTURES / "records/valid/c2-runtime-evidence-from-a-synthetic-workload.json"
    )

    assert record["workload"]["source"] == "synthetic"
    assert record["evidenceLevel"] == "C2"
    assert validate_record(record) == []
    assert not any(
        substitution["claimMaterial"]
        for substitution in record["execution"]["substitutions"]
    )


# --------------------------------------------------------------- the refusals


@pytest.mark.parametrize("path", INVALID_RECORDS, ids=lambda path: path.stem)
def test_every_invalid_record_fixture_is_refused_where_it_is_declared(
    path: Path,
) -> None:
    declared = REFUSALS["records"][path.stem]
    found = validate_record(load(path))

    assert found, {"fixture": path.stem, "why": declared["reason"]}
    assert _touches(found, declared["jsonPath"]), {
        "fixture": path.stem,
        "declared": declared["jsonPath"],
        "refused at": [refusal.path for refusal in found],
    }


@pytest.mark.parametrize("path", INVALID_CLAIMS, ids=lambda path: path.stem)
def test_every_invalid_claim_fixture_is_refused_where_it_is_declared(
    path: Path,
) -> None:
    declared = REFUSALS["claims"][path.stem]
    found = validate_claim(load(path))

    assert found, {"fixture": path.stem, "why": declared["reason"]}
    assert _touches(found, declared["jsonPath"]), {
        "fixture": path.stem,
        "declared": declared["jsonPath"],
        "refused at": [refusal.path for refusal in found],
    }


def _touches(found: list, declared: str) -> bool:
    return any(
        refusal.path == declared
        or refusal.path.startswith(f"{declared}.")
        or refusal.path.startswith(f"{declared}[")
        for refusal in found
    )


def test_the_refusal_matrix_and_the_fixtures_on_disk_agree() -> None:
    """In both directions, so neither side can grow silently."""
    assert {path.stem for path in INVALID_RECORDS} == set(REFUSALS["records"])
    assert {path.stem for path in INVALID_CLAIMS} == set(REFUSALS["claims"])


@pytest.mark.parametrize(
    "reason",
    [
        row["reason"]
        for kind in ("records", "claims")
        for row in REFUSALS[kind].values()
    ],
)
def test_every_declared_refusal_says_why_in_words(reason: str) -> None:
    assert len(reason) > 40, reason


# ------------------------------------------------------- the compatibility path


def test_the_committed_register_reads_into_the_new_version() -> None:
    document = read_legacy_as_v1alpha2()

    assert validate_register(document) == []
    assert document["contractVersion"] == CONTRACT_VERSION
    assert document["supersedes"] == LEGACY_CONTRACT_VERSION


def test_every_committed_claim_survives_the_read() -> None:
    legacy = load_legacy_register()
    document = read_legacy_as_v1alpha2()

    assert [row["claimId"] for row in document["claims"]] == [
        row["claimId"] for row in legacy["claims"]
    ]


def test_nothing_the_read_produces_is_given_an_evidence_level() -> None:
    """The one thing the compatibility path must not do.

    Copying `certificationLevel` into `evidenceLevel` would reclassify fifty-nine
    claims in a change whose diff contains no classification at all.
    """
    promoted = [
        record["recordId"]
        for claim in read_legacy_as_v1alpha2()["claims"]
        for record in claim["evidenceRecords"]
        if record["evidenceLevel"] is not None
        or record["migrationState"] != "legacy-unmigrated"
    ]

    assert not promoted, promoted


def test_every_carried_classification_matches_the_committed_row() -> None:
    """Verbatim, and checked value by value rather than asserted in a comment."""
    legacy = {row["claimId"]: row for row in load_legacy_register()["claims"]}
    mismatched = {}

    for claim in read_legacy_as_v1alpha2()["claims"]:
        row = legacy[claim["claimId"]]
        carried = (
            claim.get("legacyClassification")
            or (claim["evidenceRecords"][0]["legacyClassification"])
        )
        if (
            carried["certificationLevel"] != row["certificationLevel"]
            or carried["evidenceLabel"] != row["evidenceLabel"]
            or carried.get("provider") != (row["provider"] or None)
            or carried.get("environment") != (row["environment"] or None)
        ):
            mismatched[claim["claimId"]] = {"carried": carried, "committed": row}

    assert not mismatched, mismatched


def test_a_claim_that_cited_no_record_keeps_its_label_rather_than_losing_it() -> None:
    """`documented-unexecuted` and `production-experience` are statements too."""
    legacy = load_legacy_register()
    without_evidence = {
        row["claimId"] for row in legacy["claims"] if not row["evidenceRefs"]
    }
    assert without_evidence, "the register no longer holds a claim citing no record"

    for claim in read_legacy_as_v1alpha2()["claims"]:
        if claim["claimId"] in without_evidence:
            assert claim["evidenceRecords"] == []
            assert "legacyClassification" in claim, claim["claimId"]


def test_a_claim_that_cited_records_gets_one_record_and_not_one_per_citation() -> None:
    """`v1alpha1` gave the claim one level, so the read may produce one record.

    Splitting a row into one record per cited path would hand each path a level
    nothing ever assigned to it individually, which is a reclassification wearing
    the costume of a refactor.
    """
    legacy = {row["claimId"]: row for row in load_legacy_register()["claims"]}

    for claim in read_legacy_as_v1alpha2()["claims"]:
        row = legacy[claim["claimId"]]
        if row["evidenceRefs"]:
            assert len(claim["evidenceRecords"]) == 1, claim["claimId"]
            assert claim["evidenceRecords"][0]["evidenceRefs"] == row["evidenceRefs"]


def test_every_field_of_a_committed_row_has_a_declared_destination() -> None:
    """The audit that makes "nothing is lost" checkable rather than asserted."""
    keys = {key for row in load_legacy_register()["claims"] for key in row}

    assert keys == set(LEGACY_FIELD_DESTINATIONS), {
        "in the register and not mapped": sorted(keys - set(LEGACY_FIELD_DESTINATIONS)),
        "mapped and not in the register": sorted(set(LEGACY_FIELD_DESTINATIONS) - keys),
    }


@pytest.mark.parametrize("field", sorted(LEGACY_FIELD_DESTINATIONS))
def test_every_declared_destination_exists_in_the_new_model(field: str) -> None:
    """A destination naming a field the schema does not have is a broken promise."""
    claim_properties = set(SCHEMA["$defs"]["claim"]["properties"])
    record_properties = set(SCHEMA["$defs"]["evidenceRecord"]["properties"])
    carrier_properties = set(SCHEMA["$defs"]["legacyClassification"]["properties"])

    for destination in LEGACY_FIELD_DESTINATIONS[field]:
        parts = destination.split(".")
        if parts[1].startswith("evidenceRecords"):
            leaf = parts[-1]
            assert leaf in record_properties or leaf in carrier_properties, destination
        elif parts[1] == "legacyClassification":
            assert parts[-1] in carrier_properties, destination
        else:
            assert parts[1] in claim_properties, destination


def test_the_evidence_class_ceiling_is_carried_as_history_and_not_as_a_rule() -> None:
    """The `synthetic` ceiling is the rule ADR 0016 D3 calls too broad.

    Carrying it into the new version as a live constraint would move the defect
    rather than leave it where the replacement can find it. It comes across as
    `legacyCeiling`. `V1-S5-012-PR1` published what replaces it for classified
    records, and applies `legacyCeiling` only to carried legacy values; that is held
    by `tests/testing/test_evidence_level_rules.py`, not here.
    """
    legacy = {row["labelId"]: row for row in load_legacy_register()["evidenceLabels"]}
    classes = {
        row["classId"]: row for row in read_legacy_as_v1alpha2()["evidenceClasses"]
    }

    assert set(classes) == set(legacy)
    for class_id, row in classes.items():
        assert row["legacyCeiling"] == legacy[class_id]["ceiling"], class_id
        assert "ceiling" not in row, class_id

    assert "legacyCeiling" in SCHEMA["$defs"]["evidenceClass"]["properties"]
    assert "ceiling" not in SCHEMA["$defs"]["evidenceClass"]["properties"]


def test_the_production_experience_class_survives_alongside_the_operational_level() -> (
    None
):
    """ADR 0016 Q2, answered: a class is not a level, so neither absorbs the other.

    `production-experience` says where a result would have come from and is an
    evidence class; `C4` says how strongly it was obtained and is a level. Both
    are unreachable here, for the same reason and at different layers, and
    collapsing them would lose the distinction between a source this project has
    no access to and a strength it has not reached.
    """
    classes = {row["classId"] for row in read_legacy_as_v1alpha2()["evidenceClasses"]}

    assert "production-experience" in classes
    assert "C4" in SCHEMA["$defs"]["evidenceLevelId"]["enum"]


# ------------------------------------------------- what the tripwires became


def test_the_authoritative_register_declares_v1alpha2() -> None:
    """The first tripwire fired in `V1-S5-012-PR2`, and this is what replaced it."""
    register = load_register()

    assert register["contractVersion"] == CONTRACT_VERSION
    assert REGISTER_PATH.name == "claim-evidence-matrix.v1alpha2.json"
    assert not validate_register(register)


def test_the_authoritative_register_holds_levels_on_records_not_claims() -> None:
    """The second one: one level per claim is gone from the data every consumer reads."""
    register = load_register()

    assert not any("certificationLevel" in row for row in register["claims"])
    assert all("evidenceRecords" in row for row in register["claims"])
    assert any(
        record.get("evidenceLevel")
        for row in register["claims"]
        for record in row["evidenceRecords"]
    )


def test_the_superseded_register_is_kept_as_it_was() -> None:
    """History, not a second register: the reader still turns it into v1alpha2."""
    legacy = load_legacy_register()

    assert legacy["contractVersion"] == LEGACY_CONTRACT_VERSION
    assert LEGACY_REGISTER_PATH.name == "claim-evidence-matrix.v1alpha1.json"
    assert all("certificationLevel" in row for row in legacy["claims"])


# ----------------------------------------------------------- the documentation


def test_the_model_document_exists_and_names_the_schema() -> None:
    document = MODEL_DOCUMENT.read_text(encoding="utf-8")

    assert "claim-evidence-matrix.v1alpha2.schema.json" in document
    assert "evidence-levels.md" in document
    assert "ADR-0016" in document or "ADR 0016" in document


@pytest.mark.parametrize(
    "phrase",
    [
        "v1alpha2",
        "V1-S5-012-PR2",
        "breaking",
    ],
)
def test_the_model_document_justifies_the_version_it_chose(phrase: str) -> None:
    """A version number without a stated compatibility impact is a guess."""
    assert phrase in MODEL_DOCUMENT.read_text(encoding="utf-8"), phrase


def test_the_testing_index_sends_a_reader_to_the_model_document() -> None:
    assert "evidence-record-model.md" in TESTING_INDEX.read_text(encoding="utf-8")


def test_the_specification_says_the_register_is_migrated() -> None:
    """The statement `V1-S5-011-PR1` wrote about its own successor, finished.

    The specification said a versioned evidence-record model was what would make
    the page executable, and then that the register had not moved. Since
    `V1-S5-012-PR2` the register is migrated, and the page has to say so and point
    at it rather than at the schema alone.
    """
    specification = SPECIFICATION.read_text(encoding="utf-8")

    assert "claim-evidence-matrix.v1alpha2.json" in specification, (
        f"{SPECIFICATION} does not name the migrated register"
    )
    assert "not yet machine-enforced" not in specification.lower(), (
        f"{SPECIFICATION} still records the rules as unenforced over the register"
    )
    assert "test-strategy.v1alpha1.json" in specification
