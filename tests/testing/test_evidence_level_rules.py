"""The evidence-level classification rules, each watched failing.

`V1-S5-011-PR2` published a schema that holds the *shape* of a record at each level.
This module holds the rules a schema cannot express -- the ones in
`tools/evidence_model/rules.py` -- and, for every rule the catalogue says is enforced
by either, drives it over a register corrupted to break it. A rule nobody has watched
fail is a rule that may already be unreachable.

What it establishes is narrow. It establishes that the published rules refuse the
documents they were written to refuse, that they accept an illustrative register
holding one claim at three levels and records at all five, that a synthetic workload
changes no verdict below `C4`, and that the committed `v1alpha1` register, read into
the new shape in memory, passes every rule with every cited file present. It
establishes **nothing** about whether any committed record is classified correctly:
no committed record carries a current evidence level yet, and reading each one against
the definitions is `V1-S5-012-PR2`.

Six rules are marked `review` in the catalogue and have no mutation here. That is the
point of marking them. Whether a declared claim-material component is the right one,
whether a workload represents intended use, whether a criterion flagged as declared
first really was, whether a production context is genuine, whether a limitation is the
right one, and whether evidence is relevant to its claim are judgements. A validator
that pretended to make them would be string-matching sentences, and the first honest
record to phrase something differently would fail while a dishonest one sailed through.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_model import (
    RULES,
    check_claim,
    check_record,
    check_register,
    load_legacy_register,
    read_legacy_as_v1alpha2,
    unimplemented_rules,
)
from tools.evidence_model.core import Refusal

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "testing" / "fixtures" / "evidence-level-rules"
SHAPES = REPO_ROOT / "tests" / "testing" / "fixtures" / "evidence-record-v1alpha2"
CATALOGUE = REPO_ROOT / "docs" / "testing" / "evidence-level-rules.md"

REGISTER: dict[str, Any] = json.loads(
    (FIXTURES / "register.json").read_text(encoding="utf-8")
)
MUTATIONS: list[dict[str, Any]] = json.loads(
    (FIXTURES / "mutations.json").read_text(encoding="utf-8")
)["mutations"]
MUTATION_BY_ID = {entry["mutationId"]: entry for entry in MUTATIONS}
RULE_BY_ID = {entry.rule_id: entry for entry in RULES}

ENFORCED = [entry for entry in RULES if entry.enforced_by != "review"]
REVIEWED = [entry for entry in RULES if entry.enforced_by == "review"]


# -------------------------------------------------------------- the helpers


def _pointer(path: str) -> list[str]:
    return [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]


def _resolve(document: Any, parts: list[str]) -> Any:
    node = document
    for part in parts:
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def apply(document: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    """A deep copy of `document` with a subset of RFC 6902 applied to it."""
    result = copy.deepcopy(document)
    for operation in operations:
        parts = _pointer(operation["path"])
        parent = _resolve(result, parts[:-1])
        key = parts[-1]
        kind = operation["op"]
        if kind == "copy":
            value = copy.deepcopy(_resolve(result, _pointer(operation["from"])))
            kind = "add"
        else:
            value = copy.deepcopy(operation.get("value"))
        if kind == "remove":
            del parent[int(key) if isinstance(parent, list) else key]
        elif kind == "replace":
            parent[int(key) if isinstance(parent, list) else key] = value
        elif kind == "add":
            if isinstance(parent, list):
                parent.insert(len(parent) if key == "-" else int(key), value)
            else:
                parent[key] = value
        else:
            raise ValueError(f"unsupported operation {kind!r}")
    return result


def _touches(refusal: Refusal, declared: str) -> bool:
    return (
        refusal.path == declared
        or refusal.path.startswith(f"{declared}.")
        or refusal.path.startswith(f"{declared}[")
    )


def _references(document: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for claim in document["claims"]:
        for record in claim["evidenceRecords"]:
            found.update(record.get("evidenceRefs", []))
            if "versionsRecordedIn" in record:
                found.add(record["versionsRecordedIn"])
            workflow = record.get("procedure", {}).get("workflowRef")
            if workflow:
                found.add(workflow)
    return found


def _repository(document: dict[str, Any], root: Path) -> Path:
    """A throwaway repository holding every file the document cites."""
    for reference in _references(document):
        target = root / reference
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("An illustrative record.\n", encoding="utf-8")
    return root


def refused(mutation_id: str, tmp_path: Path | None = None) -> list[Refusal]:
    entry = MUTATION_BY_ID[mutation_id]
    mutated = apply(REGISTER, entry["operations"])
    if entry.get("withRepository"):
        assert tmp_path is not None, mutation_id
        return check_register(mutated, repo_root=_repository(REGISTER, tmp_path))
    return check_register(mutated)


def assert_refused_by_its_rule(mutation_id: str, found: list[Refusal]) -> None:
    entry = MUTATION_BY_ID[mutation_id]
    declared = RULE_BY_ID[entry["rule"]]
    at = entry["refusedAt"]
    if declared.enforced_by == "validator":
        matching = [r for r in found if r.rule == declared.rule_id and _touches(r, at)]
    else:
        # A schema refusal carries the JSON Schema keyword that failed, not a
        # catalogue identifier, so it is matched by where it landed and by the
        # keyword the mutation declares. Matching any keyword at that place let a
        # mutation pass by tripping an unrelated clause; an independent review of
        # this change found that and the declared keyword closes it.
        keyword = entry["schemaKeyword"]
        matching = [r for r in found if r.rule == keyword and _touches(r, at)]
    assert matching, {
        "mutation": mutation_id,
        "rule": declared.rule_id,
        "enforced by": declared.enforced_by,
        "expected at": at,
        "why it must fail": entry["reason"],
        "refused instead": [(r.rule, r.path) for r in found],
    }


# ------------------------------------------------------------- the catalogue


def test_every_rule_identifier_is_unique_and_a_slug() -> None:
    identifiers = [entry.rule_id for entry in RULES]

    assert len(identifiers) == len(set(identifiers))
    slug = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    assert all(slug.match(identifier) for identifier in identifiers), identifiers


def test_every_level_named_by_a_rule_is_a_level() -> None:
    named = {level for entry in RULES for level in entry.levels}

    assert named <= {"C0", "C1", "C2", "C3", "C4"}, named


def test_every_validator_rule_the_catalogue_names_is_implemented() -> None:
    """A catalogue entry with no code behind it is the overclaim this module exists
    to refuse: a rule published as enforced that nothing enforces."""
    assert unimplemented_rules() == []


def test_every_level_has_at_least_one_enforced_rule() -> None:
    covered = {level for entry in ENFORCED for level in entry.levels}

    assert covered == {"C0", "C1", "C2", "C3", "C4"}, covered


def test_every_enforced_rule_has_a_mutation_that_breaks_it() -> None:
    watched = {entry["rule"] for entry in MUTATIONS}
    unwatched = sorted(
        entry.rule_id for entry in ENFORCED if entry.rule_id not in watched
    )

    assert not unwatched, {
        "rules nobody has watched fail": unwatched,
        "why": "a rule that has never refused anything may already be unreachable",
    }


def test_no_mutation_claims_to_break_a_judgement() -> None:
    """A mutation against a `review` rule would be testing a sentence, not a rule."""
    against_review = [
        entry["mutationId"]
        for entry in MUTATIONS
        if RULE_BY_ID[entry["rule"]].enforced_by == "review"
    ]

    assert not against_review, against_review


def test_every_mutation_names_a_catalogued_rule_and_says_why() -> None:
    for entry in MUTATIONS:
        assert entry["rule"] in RULE_BY_ID, entry["mutationId"]
        assert len(entry["reason"]) > 40, entry["mutationId"]


def test_the_review_rules_are_the_six_judgements() -> None:
    """Pinned by count, so adding a judgement is a visible decision."""
    assert len(REVIEWED) == 6, [entry.rule_id for entry in REVIEWED]


def _published_rows() -> dict[str, str]:
    text = CATALOGUE.read_text(encoding="utf-8")
    return dict(
        re.findall(
            r"^\|\s*`([a-z0-9-]+)`\s*\|[^|\n]*\|[^|\n]*\|\s*(schema|validator|review)\s*\|",
            text,
            flags=re.MULTILINE,
        )
    )


def test_the_catalogue_document_publishes_every_rule_and_nothing_else() -> None:
    published = _published_rows()
    defined = {entry.rule_id: entry.enforced_by for entry in RULES}

    assert set(published) == set(defined), {
        "in the code and not the document": sorted(set(defined) - set(published)),
        "in the document and not the code": sorted(set(published) - set(defined)),
    }


def test_the_catalogue_document_says_who_enforces_each_rule_truthfully() -> None:
    """The column a reader trusts most, checked against the code that decides it."""
    published = _published_rows()
    wrong = {
        entry.rule_id: {
            "published": published.get(entry.rule_id),
            "actual": entry.enforced_by,
        }
        for entry in RULES
        if published.get(entry.rule_id) != entry.enforced_by
    }

    assert not wrong, wrong


# ---------------------------------------------------------- what must pass


def test_the_illustrative_register_passes_every_rule() -> None:
    assert check_register(REGISTER) == []


def test_the_illustrative_register_passes_with_every_cited_file_present(
    tmp_path: Path,
) -> None:
    assert check_register(REGISTER, repo_root=_repository(REGISTER, tmp_path)) == []


def test_the_illustrative_register_holds_a_record_at_every_level() -> None:
    reached = {
        record["evidenceLevel"]
        for claim in REGISTER["claims"]
        for record in claim["evidenceRecords"]
        if record["evidenceLevel"]
    }

    assert reached == {"C0", "C1", "C2", "C3", "C4"}, reached


def test_one_claim_may_hold_several_valid_records_at_different_levels() -> None:
    """The requirement the whole `v1alpha2` version exists for, now under the rules."""
    claim = REGISTER["claims"][0]
    levels = [record["evidenceLevel"] for record in claim["evidenceRecords"]]

    assert levels == ["C0", "C1", "C2"], levels
    assert check_claim(claim, evidence_classes=REGISTER["evidenceClasses"]) == []


@pytest.mark.parametrize(
    "path",
    sorted((SHAPES / "records" / "valid").glob("*.json")),
    ids=lambda path: path.stem,
)
def test_every_published_valid_shape_still_passes_the_record_rules(path: Path) -> None:
    """The `V1-S5-011-PR2` shapes are not made invalid by rules added after them."""
    assert check_record(json.loads(path.read_text(encoding="utf-8"))) == []


@pytest.mark.parametrize(
    "path",
    sorted((SHAPES / "records" / "invalid").glob("*.json")),
    ids=lambda path: path.stem,
)
def test_every_published_invalid_shape_is_still_refused(path: Path) -> None:
    assert check_record(json.loads(path.read_text(encoding="utf-8")))


def test_the_published_shapes_cite_a_template_and_the_register_rule_says_so() -> None:
    """A gap in the `V1-S5-011-PR2` fixtures, measured rather than papered over.

    Every valid record shape cites `docs/proof/templates/TEMPLATE-claim-evidence.md`
    as its evidence, because each is checked as a lone record and the template was a
    path that existed. A register holding them is refused by
    `a-template-is-not-evidence`, once per shape. They stay as they are: they are
    shapes, the record rules above accept them, and rewriting them to pass a rule
    written after them would hide that the rule is register-scoped.
    """
    shapes = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((SHAPES / "records" / "valid").glob("*.json"))
    ]
    document = copy.deepcopy(REGISTER)
    document["claims"][0]["evidenceRecords"] = []
    document["claims"][0]["status"] = "not-claimed"
    document["claims"][0]["notClaimedReason"] = (
        "A container for the published shapes, which are not evidence for anything."
    )
    document["claims"][0]["claimMaterialComponents"] = ["inference-api"]
    for shape in shapes:
        shape["claimId"] = document["claims"][0]["claimId"]
    document["claims"][0]["evidenceRecords"] = shapes

    templates = [
        r for r in check_register(document) if r.rule == "a-template-is-not-evidence"
    ]

    held = re.compile(r"^\$\.claims\[0\]\.evidenceRecords\[\d+\]")
    records = {match.group(0) for r in templates if (match := held.match(r.path))}
    assert len(records) == len(shapes), [(r.path, r.message) for r in templates]


# ------------------------------------------- the committed register, read


def test_the_committed_register_passes_every_rule_when_read_into_the_new_shape() -> (
    None
):
    """The replacement guard, run over the only real data there is.

    The two ceiling guards bound to `v1alpha1` read `claim.certificationLevel`, and
    `v1alpha2` has no such field, so the migration cannot leave them running. This
    is what has to be running instead. Every cited file must exist, every carried
    classification must sit under its legacy ceiling, and every certified
    real-behaviour claim must rest on a class that may support one -- all of which
    the `v1alpha1` suite already enforces on the same values, so agreement here is
    the check that the replacement is at least as strict as what it replaces.
    """
    assert check_register(read_legacy_as_v1alpha2(), repo_root=REPO_ROOT) == []


def test_the_legacy_ceiling_rule_refuses_what_the_v1alpha1_rule_refuses() -> None:
    """The `v1alpha1` negative control, repeated against the replacement."""
    legacy = load_legacy_register()
    row = copy.deepcopy(
        next(row for row in legacy["claims"] if row["status"] == "certified")
    )
    row["evidenceLabel"] = "mock"
    row["certificationLevel"] = "C2"
    corrupted = dict(legacy, claims=[row])

    found = check_register(read_legacy_as_v1alpha2(corrupted))

    assert any(
        r.rule == "a-legacy-classification-stays-under-its-legacy-ceiling"
        for r in found
    ), found


def test_the_real_behaviour_rule_refuses_what_the_v1alpha1_rule_refuses() -> None:
    legacy = load_legacy_register()
    row = copy.deepcopy(
        next(
            row
            for row in legacy["claims"]
            if row["status"] == "certified" and row["assertsRealBehaviour"]
        )
    )
    row["evidenceLabel"] = "local-static"
    row["certificationLevel"] = "C0"
    corrupted = dict(legacy, claims=[row])

    found = check_register(read_legacy_as_v1alpha2(corrupted))

    assert any(
        r.rule == "a-real-behaviour-claim-rests-on-real-evidence" for r in found
    ), found


def test_a_legacy_claim_checked_alone_cannot_borrow_a_ceiling_it_was_not_given() -> (
    None
):
    """Without the register's classes a carried label cannot be read, and the claim
    is refused with a message that says so rather than silently passed."""
    claim = REGISTER["claims"][3]

    found = check_claim(claim)

    assert [r.rule for r in found] == ["a-real-behaviour-claim-rests-on-real-evidence"]
    assert "evidence classes" in found[0].message


# --------------------------------------------------------- what must fail


@pytest.mark.parametrize("mutation_id", sorted(MUTATION_BY_ID))
def test_every_mutation_is_refused_by_the_rule_it_breaks(
    mutation_id: str, tmp_path: Path
) -> None:
    assert_refused_by_its_rule(mutation_id, refused(mutation_id, tmp_path))


# The misclassifications these rules exist for, named so a reader can find them.


def test_a_mock_backed_record_marked_c2_is_refused_however_it_is_flagged() -> None:
    """Honestly flagged, the schema refuses it. Flagged immaterial, the claim does."""
    assert_refused_by_its_rule(
        "a-mock-backed-record-honestly-flagged-and-marked-c2",
        refused("a-mock-backed-record-honestly-flagged-and-marked-c2"),
    )
    dishonest = refused("a-mock-backed-record-flagged-immaterial-and-marked-c2")
    assert_refused_by_its_rule(
        "a-mock-backed-record-flagged-immaterial-and-marked-c2", dishonest
    )
    assert any(
        r.rule == "a-real-record-executed-every-claim-material-component"
        for r in dishonest
    ), "the runtime is missing from what executed as well"
    assert not [r for r in dishonest if r.rule not in RULE_BY_ID], (
        "the schema alone accepts the dishonest version; that is why the claim rule exists"
    )


def test_a_c1_record_with_no_material_substitution_is_refused() -> None:
    assert_refused_by_its_rule(
        "a-c1-record-with-no-substitution", refused("a-c1-record-with-no-substitution")
    )


@pytest.mark.parametrize(
    "mutation_id",
    [
        "a-c3-record-without-representativeness",
        "a-c3-record-without-acceptance-criteria",
        "a-c3-record-with-no-workload-shape",
        "a-c3-record-with-no-declared-conditions",
    ],
)
def test_a_c3_record_missing_representativeness_or_criteria_is_refused(
    mutation_id: str,
) -> None:
    assert_refused_by_its_rule(mutation_id, refused(mutation_id))


@pytest.mark.parametrize(
    "mutation_id",
    [
        "a-cloud-experiment-marked-c4",
        "a-c4-record-without-a-production-context",
        "a-c4-record-under-synthetic-load",
    ],
)
def test_a_cloud_experiment_marked_c4_is_refused(mutation_id: str) -> None:
    assert_refused_by_its_rule(mutation_id, refused(mutation_id))


@pytest.mark.parametrize(
    "mutation_id",
    [
        "a-c2-record-with-no-limitations",
        "a-c2-record-that-does-not-say-what-it-does-not-establish",
        "a-limitation-that-says-none",
        "a-boundary-that-says-not-applicable",
    ],
)
def test_an_important_record_without_limitations_is_refused(mutation_id: str) -> None:
    assert_refused_by_its_rule(mutation_id, refused(mutation_id))


def test_a_real_path_classified_c1_because_its_prompts_were_synthetic_is_refused() -> (
    None
):
    """The misclassification ADR 0016 D3 names, dressed as a substitution.

    The schema accepts it: the record is `C1` and names a claim-material
    substitution. What it substituted is the prompt set, which is input, not a
    component the claim depends on. The declaration on the claim is what refuses it.
    """
    found = refused("a-real-path-classified-c1-because-its-prompts-were-synthetic")

    assert_refused_by_its_rule(
        "a-real-path-classified-c1-because-its-prompts-were-synthetic", found
    )
    assert not [r for r in found if r.rule not in RULE_BY_ID], (
        "the schema alone accepts this record; the rule it needs is claim-relative"
    )


# ---------------------------------------------------------- the synthetic rule


_EXECUTED_BELOW_C4 = [
    (claim_index, record_index)
    for claim_index, claim in enumerate(REGISTER["claims"])
    for record_index, record in enumerate(claim["evidenceRecords"])
    if record["evidenceLevel"] in ("C1", "C2", "C3")
]


@pytest.mark.parametrize("source", ["synthetic", "captured", "operator-issued"])
@pytest.mark.parametrize(
    "location",
    _EXECUTED_BELOW_C4,
    ids=lambda location: f"claim{location[0]}-record{location[1]}",
)
def test_workload_origin_changes_no_verdict_below_c4(
    source: str, location: tuple[int, int]
) -> None:
    """Synthetic input imposes no ceiling: swapping the origin moves nothing.

    `C4` is excluded on purpose. Operational evidence is defined by genuine production
    traffic, so it is the one level at which origin is part of the definition, and
    `a-c4-record-observed-production-traffic` says so.
    """
    claim_index, record_index = location
    document = copy.deepcopy(REGISTER)
    document["claims"][claim_index]["evidenceRecords"][record_index]["workload"][
        "source"
    ] = source

    assert check_register(document) == []


def test_no_rule_below_c4_reads_the_workload_source() -> None:
    """The same property, stated against the code rather than the fixtures.

    Only the `C0` rule, which requires that nothing was issued, and the `C4` rule,
    which requires production traffic, may mention it.
    """
    source = (REPO_ROOT / "tools" / "evidence_model" / "rules.py").read_text(
        encoding="utf-8"
    )
    readers = re.findall(
        r'@_record_check\("([a-z0-9-]+)"\)\ndef [^\n]+\n(?:(?!@_).*\n)*?.*get\("source"\)',
        source,
    )

    assert set(readers) == {
        "a-c0-record-ran-only-inspection",
        "a-c4-record-observed-production-traffic",
    }, readers


# --------------------------------------------------------- the heuristic's edge


def test_the_limitation_heuristic_accepts_a_sentence_that_says_little() -> None:
    """A measured gap, kept visible. The rule refuses placeholders, not vacuity.

    `a-limitation-is-the-right-limitation` is a review rule because this sentence
    passes. If a later change makes it fail, the catalogue's description of the
    heuristic has become too modest and should be corrected with it.
    """
    document = copy.deepcopy(REGISTER)
    document["claims"][0]["evidenceRecords"][2]["limitations"] = [
        "Limitations are recorded here."
    ]

    assert check_register(document) == []


def test_every_schema_mutation_names_the_keyword_that_must_refuse_it() -> None:
    for entry in MUTATIONS:
        declared = RULE_BY_ID[entry["rule"]]
        if declared.enforced_by == "schema":
            assert entry.get("schemaKeyword"), entry["mutationId"]
        else:
            assert "schemaKeyword" not in entry, entry["mutationId"]


# ------------------------------------------------------ what the review found


def _under_declared(claim: int, record: int, executed_index: int) -> dict[str, Any]:
    """Claim `claim` declares only the API, and its record mocks the runtime."""
    at = f"/claims/{claim}/evidenceRecords/{record}/execution"
    return apply(
        REGISTER,
        [
            {
                "op": "replace",
                "path": f"/claims/{claim}/claimMaterialComponents",
                "value": ["inference-api"],
            },
            {"op": "remove", "path": f"{at}/executedComponents/{executed_index}"},
            {
                "op": "add",
                "path": f"{at}/substitutions/-",
                "value": {
                    "componentId": "inference-runtime",
                    "role": "inference-runtime",
                    "substituteKind": "mock",
                    "claimMaterial": False,
                    "rationale": "The mock is faithful to the contract.",
                },
            },
        ],
    )


def test_an_under_declared_claim_still_lets_a_mocked_runtime_pass_at_c2() -> None:
    """A measured gap, kept visible, found by the independent review of this change.

    Every rule that refuses a mock-backed `C2` record holds the record to the claim's
    declaration. A claim that leaves the runtime out of `claimMaterialComponents`
    lets a record mock the runtime, call the mock immaterial, and pass -- here the
    `C3` record, whose claim holds no other record. Whether the declaration is
    complete is the review rule
    `the-declared-claim-material-components-are-the-right-ones`. If a later change
    makes this fail, the catalogue's account of that rule has become too modest.
    """
    assert check_register(_under_declared(claim=1, record=0, executed_index=1)) == []
    assert (
        RULE_BY_ID[
            "the-declared-claim-material-components-are-the-right-ones"
        ].enforced_by
        == "review"
    )


def test_an_under_declaration_is_caught_when_another_record_flags_the_component() -> (
    None
):
    """The gap's edge. A claim that also holds a `C1` record substituting the runtime
    as material cannot leave the runtime undeclared: that record's substitution then
    names a component the claim does not declare, and it is refused."""
    found = check_register(_under_declared(claim=0, record=2, executed_index=2))

    assert [r.rule for r in found] == [
        "a-claim-material-substitution-replaces-a-declared-component"
    ], found


@pytest.mark.parametrize("value", [["not", "a", "record"], "a string", None, 3])
@pytest.mark.parametrize("check", [check_record, check_claim, check_register])
def test_a_document_that_is_not_an_object_is_refused_rather_than_raising(
    check: Any, value: Any
) -> None:
    """The entry points return refusals. The first draft raised on a non-object."""
    assert check(value)


def test_malformed_evidence_classes_do_not_raise() -> None:
    claim = REGISTER["claims"][3]

    found = check_claim(claim, evidence_classes=[{"notClassId": "x"}])

    assert any(r.rule == "a-real-behaviour-claim-rests-on-real-evidence" for r in found)


def test_two_records_missing_an_identifier_are_not_reported_as_duplicates() -> None:
    """Two missing identifiers are two schema refusals, not one duplicate."""
    document = apply(
        REGISTER,
        [
            {"op": "remove", "path": "/claims/0/evidenceRecords/0/recordId"},
            {"op": "remove", "path": "/claims/2/evidenceRecords/0/recordId"},
        ],
    )

    found = check_register(document)

    assert not [r for r in found if r.rule == "a-record-identifier-is-unique"], found
    assert len([r for r in found if r.rule == "required"]) == 2, found
