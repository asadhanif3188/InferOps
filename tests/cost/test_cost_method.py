"""Deterministic checks over the V1 inference cost-calculation method.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness, and no price is retrieved from
anywhere.

What this suite establishes is that the method is internally consistent, that it
agrees with the telemetry catalog and the workload contract already committed
beside it, and that the worked example is arithmetic rather than typing: every
amount, share, and unit cost in it is recomputed here in exact decimal from the
declared inputs and the declared rates, and the workload lines plus the
unallocated residual are required to close against the machine exactly. It also
establishes the properties that keep an estimate from reading as a bill --- that
only an invoice-backed basis may reference an invoice, that confidence is the
lowest applicable ceiling rather than a value somebody typed, that a missing
input produces a null with a reason rather than a zero, that a unit cost carries
the denominator it was divided by, and that no record committed to this
repository carries a tenant identifier.

What it does not establish is that any of this is computed. Nothing in this
repository produces, emits, stores, or reads a cost record; no invoice has ever
been seen; and the only rate card committed here is synthetic, so every amount
the suite verifies is arithmetically correct and economically meaningless.
"""

from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
COST_DIR = REPO_ROOT / "docs" / "cost"
METHOD_PATH = COST_DIR / "cost-method.v1alpha1.json"
CATALOG_PATH = REPO_ROOT / "docs" / "telemetry" / "telemetry-catalog.v1alpha1.json"
STRATEGY_PATH = REPO_ROOT / "docs" / "testing" / "test-strategy.v1alpha1.json"
THIS_MODULE = Path(__file__)

EXPECTED_METHOD_ID = "https://inferops.io/cost/cost-method.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

# This suite is collected by the documentation layer of the test strategy, which
# has to name the directory it lives in or the layer selects nothing here.
DECLARING_LAYER = "documentation"
DECLARED_PATH = "tests/cost"

# Identifiers in the method are lowercase, hyphen-separated slugs.
SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# An identifier as a document publishes it: an inline code span in the first
# column of a Markdown table row.
FIRST_TABLE_COLUMN = re.compile(
    r"^\|\s*`([A-Za-z_][A-Za-z0-9_.:-]*)`\s*\|", flags=re.MULTILINE
)

# A decimal string at the record scale: exactly six places, optionally negative.
DECIMAL_STRING = re.compile(r"^-?\d+\.\d{6}$")

# The same shape as it appears in prose, for comparing a document to the data.
DECIMAL_IN_PROSE = re.compile(r"(?<![\d.])\d+\.\d{6}(?![\d])")

# Words that belong to an invoice and to nothing else.
BILLING_WORDS = re.compile(r"invoice|billing|billed|charge|spend", flags=re.IGNORECASE)

REQUIRED_BASIS_FIELDS = (
    "basisId",
    "meaning",
    "requires",
    "v1Reachable",
    "unreachableReason",
    "maxConfidence",
    "notes",
)

REQUIRED_ALLOCATION_FIELDS = (
    "methodId",
    "meaning",
    "inputsRequired",
    "selected",
    "v1Status",
    "deferralReason",
    "whyChosen",
    "honestCost",
)

REQUIRED_TREATMENT_FIELDS = ("treatmentId", "meaning", "selected", "why")

REQUIRED_UNIT_FIELDS = ("unitId", "priced", "meaning", "definition", "appliesTo")

REQUIRED_PRICE_SOURCE_FIELDS = (
    "priceSourceId",
    "class",
    "name",
    "currency",
    "version",
    "effectiveDate",
    "retrieval",
    "selfIdentifies",
    "maxConfidence",
    "scope",
    "publishable",
    "rates",
    "notes",
)

REQUIRED_PRICE_CLASS_FIELDS = (
    "classId",
    "meaning",
    "maxConfidence",
    "v1Status",
    "requirements",
)

REQUIRED_LEVEL_FIELDS = ("levelId", "rank", "meaning")

REQUIRED_CONFIDENCE_RULE_FIELDS = ("ruleId", "when", "ceiling", "why")

REQUIRED_INPUT_FIELDS = (
    "inputId",
    "name",
    "kind",
    "required",
    "unit",
    "source",
    "telemetrySignal",
    "telemetryCoverage",
    "coverageNote",
    "sensitivity",
    "question",
    "v1Available",
    "unavailableReason",
)

REQUIRED_OUTPUT_FIELDS = (
    "outputId",
    "name",
    "unit",
    "formula",
    "dependsOn",
    "scale",
    "question",
    "nullWhen",
)

REQUIRED_REASON_FIELDS = ("reasonId", "meaning", "v1Common")

REQUIRED_RECORD_FIELD_FIELDS = (
    "fieldId",
    "path",
    "type",
    "required",
    "sensitivity",
    "committedRecordAllowed",
    "meaning",
)

REQUIRED_PROHIBITION_FIELDS = (
    "ruleId",
    "statement",
    "rationale",
    "enforcement",
    "enforcedBy",
)

REQUIRED_LIMITATION_FIELDS = ("limitationId", "statement")

REQUIRED_GAP_FIELDS = ("gapId", "affects", "statement", "consequence")

REQUIRED_OPEN_QUESTION_FIELDS = ("questionId", "statement", "status", "why")

# Every source an input may declare. `unavailable` is a state, not a value.
SOURCES = {"measured", "derived", "declared", "unavailable"}

COVERAGES = {"full", "partial", "none"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


METHOD = load(METHOD_PATH)
CATALOG = load(CATALOG_PATH)
STRATEGY = load(STRATEGY_PATH)

BASES = METHOD["bases"]
ALLOCATION_METHODS = METHOD["allocationMethods"]
TREATMENTS = METHOD["residualTreatments"]
UNITS = METHOD["units"]
PRICE_SOURCES = METHOD["priceSources"]
PRICE_CLASSES = METHOD["priceSourceClasses"]
LEVELS = METHOD["confidenceLevels"]
CONFIDENCE_RULES = METHOD["confidenceRules"]
INPUTS = METHOD["inputs"]
OUTPUTS = METHOD["outputs"]
REASONS = METHOD["missingDataReasons"]
RECORD_FIELDS = METHOD["recordShape"]["fields"]
PROHIBITIONS = METHOD["prohibitions"]
LIMITATIONS = METHOD["limitations"]
GAPS = METHOD["telemetryMapping"]["gaps"]
OPEN_QUESTIONS = METHOD["openQuestions"]
EXAMPLE = METHOD["workedExample"]
EXAMPLE_RECORDS = EXAMPLE["records"]
COUNTERFACTUALS = EXAMPLE["counterfactuals"]
DENOMINATORS = METHOD["denominatorRules"]

BASIS_BY_ID = {row["basisId"]: row for row in BASES}
ALLOCATION_BY_ID = {row["methodId"]: row for row in ALLOCATION_METHODS}
UNIT_BY_ID = {row["unitId"]: row for row in UNITS}
PRICE_SOURCE_BY_ID = {row["priceSourceId"]: row for row in PRICE_SOURCES}
PRICE_CLASS_BY_ID = {row["classId"]: row for row in PRICE_CLASSES}
LEVEL_BY_ID = {row["levelId"]: row for row in LEVELS}
INPUT_BY_ID = {row["inputId"]: row for row in INPUTS}
OUTPUT_BY_ID = {row["outputId"]: row for row in OUTPUTS}
REASON_BY_ID = {row["reasonId"]: row for row in REASONS}

CATALOG_METRIC_NAMES = {row["name"] for row in CATALOG["metrics"]}
CATALOG_ATTRIBUTE_NAMES = {row["name"] for row in CATALOG["attributes"]}
CATALOG_SIGNAL_NAMES = CATALOG_METRIC_NAMES | CATALOG_ATTRIBUTE_NAMES
CATALOG_SENSITIVITY = {row["classId"]: row for row in CATALOG["sensitivityClasses"]}

SCALE = Decimal(1).scaleb(-METHOD["money"]["recordScale"])


def quantise(value: Decimal) -> Decimal:
    """Round once, half-even, at the record scale, exactly as the method says."""
    return value.quantize(SCALE, rounding=ROUND_HALF_EVEN)


def rate(price_source_id: str, unit_id: str) -> Decimal:
    for row in PRICE_SOURCE_BY_ID[price_source_id]["rates"]:
        if row["unit"] == unit_id:
            return Decimal(row["ratePerHour"])
    raise AssertionError(f"price source '{price_source_id}' has no {unit_id} rate")


def cores(quantity: str) -> Decimal:
    """A Kubernetes processor quantity as cores. 1000m is one core."""
    if quantity.endswith("m"):
        return Decimal(quantity[:-1]) / Decimal(1000)
    return Decimal(quantity)


def gibibytes(quantity: str) -> Decimal:
    """A Kubernetes memory quantity as gibibytes. Binary, never decimal."""
    if quantity.endswith("Gi"):
        return Decimal(quantity[:-2])
    if quantity.endswith("Mi"):
        return Decimal(quantity[:-2]) / Decimal(1024)
    raise AssertionError(f"unsupported memory quantity: {quantity}")


def walk(node: object) -> object:
    """Yield every scalar in the committed method, for whole-document checks."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield None, value
            yield from walk(value)


def declared_identifiers() -> set[str]:
    collections = (
        (BASES, "basisId"),
        (ALLOCATION_METHODS, "methodId"),
        (TREATMENTS, "treatmentId"),
        (UNITS, "unitId"),
        (PRICE_SOURCES, "priceSourceId"),
        (PRICE_CLASSES, "classId"),
        (LEVELS, "levelId"),
        (CONFIDENCE_RULES, "ruleId"),
        (INPUTS, "inputId"),
        (OUTPUTS, "outputId"),
        (REASONS, "reasonId"),
        (RECORD_FIELDS, "fieldId"),
        (PROHIBITIONS, "ruleId"),
        (LIMITATIONS, "limitationId"),
        (GAPS, "gapId"),
        (OPEN_QUESTIONS, "questionId"),
        (METHOD["sharedCostRules"], "ruleId"),
        (METHOD["priceSourceRules"], "ruleId"),
    )
    found: set[str] = set()
    for rows, key in collections:
        found |= {row[key] for row in rows}
    found |= {row["recordId"] for row in EXAMPLE_RECORDS}
    found |= {row["name"] for row in INPUTS}
    found |= {row["path"] for row in RECORD_FIELDS}
    found |= {row["name"] for row in OUTPUTS}
    found |= CATALOG_SIGNAL_NAMES
    return found


@pytest.fixture(scope="module")
def method_document() -> str:
    return (COST_DIR / "cost-method.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def example_document() -> str:
    return (COST_DIR / "worked-example.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cost_readme() -> str:
    return (COST_DIR / "README.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Shape: every row declares every field, and nothing is empty
# --------------------------------------------------------------------------


def test_the_method_declares_its_identity_and_contract_version() -> None:
    assert METHOD["$id"] == EXPECTED_METHOD_ID
    assert METHOD["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_the_method_is_not_empty() -> None:
    assert len(BASES) == 3
    assert len(ALLOCATION_METHODS) >= 3
    assert len(TREATMENTS) >= 3
    assert len(UNITS) >= 6
    assert len(LEVELS) == 4
    assert len(INPUTS) >= 20
    assert len(OUTPUTS) >= 8
    assert len(PROHIBITIONS) >= 10
    assert len(LIMITATIONS) >= 8
    assert len(EXAMPLE_RECORDS) >= 2


@pytest.mark.parametrize("row", BASES, ids=lambda row: row["basisId"])
def test_every_basis_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_BASIS_FIELDS), row["basisId"]
    assert SLUG.match(row["basisId"]), row["basisId"]
    assert row["meaning"].strip(), row["basisId"]
    assert row["maxConfidence"] in LEVEL_BY_ID, row["basisId"]


@pytest.mark.parametrize("row", ALLOCATION_METHODS, ids=lambda row: row["methodId"])
def test_every_allocation_method_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_ALLOCATION_FIELDS), row["methodId"]
    assert SLUG.match(row["methodId"]), row["methodId"]
    assert row["meaning"].strip(), row["methodId"]
    assert row["honestCost"].strip(), row["methodId"]
    assert isinstance(row["selected"], bool), row["methodId"]


@pytest.mark.parametrize("row", TREATMENTS, ids=lambda row: row["treatmentId"])
def test_every_residual_treatment_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_TREATMENT_FIELDS), row["treatmentId"]
    assert SLUG.match(row["treatmentId"]), row["treatmentId"]
    assert row["why"].strip(), row["treatmentId"]


@pytest.mark.parametrize("row", UNITS, ids=lambda row: row["unitId"])
def test_every_unit_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_UNIT_FIELDS), row["unitId"]
    assert SLUG.match(row["unitId"]), row["unitId"]
    assert row["definition"].strip(), row["unitId"]
    assert isinstance(row["priced"], bool), row["unitId"]


@pytest.mark.parametrize("row", PRICE_SOURCES, ids=lambda row: row["priceSourceId"])
def test_every_price_source_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_PRICE_SOURCE_FIELDS), row["priceSourceId"]
    assert SLUG.match(row["priceSourceId"]), row["priceSourceId"]
    assert row["class"] in PRICE_CLASS_BY_ID, row["priceSourceId"]
    assert row["maxConfidence"] in LEVEL_BY_ID, row["priceSourceId"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", row["effectiveDate"]), row["priceSourceId"]
    assert row["rates"], row["priceSourceId"]


@pytest.mark.parametrize("row", PRICE_CLASSES, ids=lambda row: row["classId"])
def test_every_price_class_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_PRICE_CLASS_FIELDS), row["classId"]
    assert SLUG.match(row["classId"]), row["classId"]
    assert row["maxConfidence"] in LEVEL_BY_ID, row["classId"]
    assert row["requirements"], row["classId"]


@pytest.mark.parametrize("row", LEVELS, ids=lambda row: row["levelId"])
def test_every_confidence_level_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_LEVEL_FIELDS), row["levelId"]
    assert SLUG.match(row["levelId"]), row["levelId"]
    assert isinstance(row["rank"], int), row["levelId"]


@pytest.mark.parametrize("row", CONFIDENCE_RULES, ids=lambda row: row["ruleId"])
def test_every_confidence_rule_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_CONFIDENCE_RULE_FIELDS), row["ruleId"]
    assert SLUG.match(row["ruleId"]), row["ruleId"]
    assert row["ceiling"] in LEVEL_BY_ID, row["ruleId"]
    assert row["when"], row["ruleId"]
    assert row["why"].strip(), row["ruleId"]


@pytest.mark.parametrize("row", INPUTS, ids=lambda row: row["inputId"])
def test_every_input_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_INPUT_FIELDS), row["inputId"]
    assert SLUG.match(row["inputId"]), row["inputId"]
    assert row["unit"] in UNIT_BY_ID, row["inputId"]
    assert row["source"] in SOURCES, row["inputId"]
    assert row["telemetryCoverage"] in COVERAGES, row["inputId"]
    assert row["sensitivity"] in CATALOG_SENSITIVITY, row["inputId"]
    assert row["coverageNote"].strip(), row["inputId"]
    assert isinstance(row["required"], bool), row["inputId"]
    assert isinstance(row["v1Available"], bool), row["inputId"]


@pytest.mark.parametrize("row", OUTPUTS, ids=lambda row: row["outputId"])
def test_every_output_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_OUTPUT_FIELDS), row["outputId"]
    assert SLUG.match(row["outputId"]), row["outputId"]
    assert row["unit"] in UNIT_BY_ID, row["outputId"]
    assert row["formula"].strip(), row["outputId"]
    assert row["scale"] == METHOD["money"]["recordScale"], row["outputId"]
    for dependency in row["dependsOn"]:
        assert dependency in INPUT_BY_ID or dependency in OUTPUT_BY_ID, dependency
    for reason in row["nullWhen"]:
        assert reason in REASON_BY_ID, reason


@pytest.mark.parametrize("row", REASONS, ids=lambda row: row["reasonId"])
def test_every_missing_data_reason_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_REASON_FIELDS), row["reasonId"]
    assert SLUG.match(row["reasonId"]), row["reasonId"]
    assert row["meaning"].strip(), row["reasonId"]


@pytest.mark.parametrize("row", RECORD_FIELDS, ids=lambda row: row["fieldId"])
def test_every_record_field_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_RECORD_FIELD_FIELDS), row["fieldId"]
    assert SLUG.match(row["fieldId"]), row["fieldId"]
    assert row["sensitivity"] in CATALOG_SENSITIVITY, row["fieldId"]
    assert row["meaning"].strip(), row["fieldId"]
    assert isinstance(row["committedRecordAllowed"], bool), row["fieldId"]


@pytest.mark.parametrize("row", PROHIBITIONS, ids=lambda row: row["ruleId"])
def test_every_prohibition_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_PROHIBITION_FIELDS), row["ruleId"]
    assert SLUG.match(row["ruleId"]), row["ruleId"]
    assert row["statement"].strip(), row["ruleId"]
    assert row["rationale"].strip(), row["ruleId"]
    assert row["enforcement"] in {"test", "review"}, row["ruleId"]


@pytest.mark.parametrize("row", LIMITATIONS, ids=lambda row: row["limitationId"])
def test_every_limitation_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_LIMITATION_FIELDS), row["limitationId"]
    assert SLUG.match(row["limitationId"]), row["limitationId"]
    assert row["statement"].strip(), row["limitationId"]


@pytest.mark.parametrize("row", GAPS, ids=lambda row: row["gapId"])
def test_every_gap_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_GAP_FIELDS), row["gapId"]
    assert SLUG.match(row["gapId"]), row["gapId"]
    for input_id in row["affects"]:
        assert input_id in INPUT_BY_ID, input_id
    assert row["consequence"].strip(), row["gapId"]


@pytest.mark.parametrize("row", OPEN_QUESTIONS, ids=lambda row: row["questionId"])
def test_every_open_question_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_OPEN_QUESTION_FIELDS), row["questionId"]
    assert SLUG.match(row["questionId"]), row["questionId"]
    assert row["status"].startswith("not decided"), row["questionId"]
    assert row["why"].strip(), row["questionId"]


def test_identifiers_are_unique() -> None:
    for rows, key in (
        (BASES, "basisId"),
        (ALLOCATION_METHODS, "methodId"),
        (TREATMENTS, "treatmentId"),
        (UNITS, "unitId"),
        (PRICE_SOURCES, "priceSourceId"),
        (PRICE_CLASSES, "classId"),
        (LEVELS, "levelId"),
        (CONFIDENCE_RULES, "ruleId"),
        (INPUTS, "inputId"),
        (OUTPUTS, "outputId"),
        (REASONS, "reasonId"),
        (RECORD_FIELDS, "fieldId"),
        (PROHIBITIONS, "ruleId"),
        (LIMITATIONS, "limitationId"),
        (GAPS, "gapId"),
        (OPEN_QUESTIONS, "questionId"),
        (EXAMPLE_RECORDS, "recordId"),
    ):
        seen = [row[key] for row in rows]
        assert len(seen) == len(set(seen)), f"duplicate {key}: {sorted(seen)}"


def test_confidence_levels_are_a_total_order_from_zero() -> None:
    ranks = sorted(row["rank"] for row in LEVELS)
    assert ranks == list(range(len(LEVELS))), ranks


def test_the_data_points_back_at_the_documents_that_describe_it() -> None:
    for field in (
        "decisionRef",
        "documentRef",
        "workedExampleRef",
        "telemetryCatalogRef",
        "workloadContractRef",
        "strategyRef",
        "boundariesRef",
    ):
        ref = METHOD[field]
        assert (REPO_ROOT / ref).is_file(), f"{field} -> {ref}"


# --------------------------------------------------------------------------
# One method, one treatment, and a basis nobody can reach by accident
# --------------------------------------------------------------------------


def test_exactly_one_allocation_method_is_selected() -> None:
    selected = [row["methodId"] for row in ALLOCATION_METHODS if row["selected"]]
    assert selected == ["requested-resource-share"], selected


def test_exactly_one_residual_treatment_is_selected() -> None:
    selected = [row["treatmentId"] for row in TREATMENTS if row["selected"]]
    assert selected == ["report-separately"], selected


def test_an_unselected_allocation_method_says_why_it_is_not_used() -> None:
    for row in ALLOCATION_METHODS:
        if row["selected"]:
            assert row["v1Status"] == "specified", row["methodId"]
            assert row["deferralReason"] is None, row["methodId"]
            assert row["whyChosen"], row["methodId"]
        else:
            assert row["v1Status"] in {"deferred", "rejected"}, row["methodId"]
            assert row["whyChosen"] is None, row["methodId"]
            if row["v1Status"] == "deferred":
                assert row["deferralReason"], row["methodId"]


def test_the_only_basis_v1_can_reach_is_an_allocation() -> None:
    reachable = [row["basisId"] for row in BASES if row["v1Reachable"]]
    assert reachable == ["allocated"], reachable


def test_an_unreachable_basis_says_why_and_a_reachable_one_does_not() -> None:
    for row in BASES:
        if row["v1Reachable"]:
            assert row["unreachableReason"] is None, row["basisId"]
        else:
            assert row["unreachableReason"], row["basisId"]


def test_only_an_actual_basis_may_reference_an_invoice() -> None:
    """A word is all it takes to turn a model of a cost into a claim about one."""
    for record in EXAMPLE_RECORDS:
        basis = record["cost"]["basis"]
        assert basis in BASIS_BY_ID, basis
        assert basis != "actual", record["recordId"]
        rendered = json.dumps(record)
        offending = BILLING_WORDS.search(rendered)
        assert offending is None, (
            f"record '{record['recordId']}' is {basis} and uses the word "
            f"'{offending.group(0) if offending else ''}'"
        )
    assert BASIS_BY_ID["actual"]["requires"], "the actual basis states no requirement"


def test_every_total_is_computed_within_one_basis() -> None:
    bases = {record["cost"]["basis"] for record in EXAMPLE_RECORDS}
    assert bases == {EXAMPLE["basis"]}, bases
    total = sum(Decimal(record["cost"]["amount"]) for record in EXAMPLE_RECORDS)
    assert quantise(total) == Decimal(EXAMPLE["totals"]["workloadAmountSum"])


# --------------------------------------------------------------------------
# Prices: committed, dated, and labelled for what they are
# --------------------------------------------------------------------------


def test_every_price_source_is_committed_rather_than_fetched() -> None:
    for row in PRICE_SOURCES:
        assert row["retrieval"] == "committed", row["priceSourceId"]
        rendered = json.dumps(row)
        assert "http://" not in rendered, row["priceSourceId"]
        assert "https://" not in rendered, row["priceSourceId"]


def test_a_synthetic_price_source_identifies_itself() -> None:
    for row in PRICE_SOURCES:
        if row["class"] != "synthetic-illustrative":
            continue
        assert row["selfIdentifies"] is True, row["priceSourceId"]
        assert row["publishable"] is False, row["priceSourceId"]
        assert row["maxConfidence"] == "none", row["priceSourceId"]
        assert "invented" in row["notes"], row["priceSourceId"]
    assert PRICE_CLASS_BY_ID["synthetic-illustrative"]["requirements"]


def test_the_only_published_price_source_is_synthetic() -> None:
    classes = {row["class"] for row in PRICE_SOURCES}
    assert classes == {"synthetic-illustrative"}, sorted(classes)
    for row in PRICE_CLASSES:
        published = row["v1Status"]
        if row["classId"] == "synthetic-illustrative":
            assert published == "one published", published
        else:
            assert published == "none published", (row["classId"], published)


def test_every_priced_unit_has_a_rate_and_every_rate_a_priced_unit() -> None:
    priced = {row["unitId"] for row in UNITS if row["priced"]}
    for source in PRICE_SOURCES:
        rated = {row["unit"] for row in source["rates"]}
        assert rated == priced, {
            "priced without a rate": sorted(priced - rated),
            "rated but not priced": sorted(rated - priced),
        }


def test_a_price_source_class_ceiling_is_never_above_its_source() -> None:
    for row in PRICE_SOURCES:
        ceiling = PRICE_CLASS_BY_ID[row["class"]]["maxConfidence"]
        assert (
            LEVEL_BY_ID[row["maxConfidence"]]["rank"] <= (LEVEL_BY_ID[ceiling]["rank"])
        ), row["priceSourceId"]


# --------------------------------------------------------------------------
# Confidence: derived from the record, never asserted by it
# --------------------------------------------------------------------------


def derived_confidence(facts: dict) -> str:
    applicable = []
    for rule in CONFIDENCE_RULES:
        matched = True
        for key, expected in rule["when"].items():
            actual = facts[key]
            if isinstance(expected, list):
                if actual not in expected:
                    matched = False
            elif actual != expected:
                matched = False
        if matched:
            applicable.append(rule["ceiling"])
    assert applicable, f"no confidence rule applies to {facts}"
    return min(applicable, key=lambda level: LEVEL_BY_ID[level]["rank"])


@pytest.mark.parametrize(
    "record", EXAMPLE_RECORDS, ids=lambda record: record["recordId"]
)
def test_declared_confidence_equals_derived_confidence(record: dict) -> None:
    facts = record["facts"]
    assert facts["basis"] == record["cost"]["basis"], record["recordId"]
    assert (
        facts["priceSourceClass"]
        == PRICE_SOURCE_BY_ID[EXAMPLE["priceSourceId"]]["class"]
    ), record["recordId"]
    assert record["cost"]["confidence"] == derived_confidence(facts), record["recordId"]


def test_a_synthetic_rate_card_caps_every_example_record_at_no_confidence() -> None:
    for record in EXAMPLE_RECORDS:
        assert record["cost"]["confidence"] == "none", record["recordId"]


def test_every_confidence_rule_fires_on_something_it_could_fire_on() -> None:
    """A rule whose condition names a fact no record carries checks nothing."""
    known_facts = set()
    for record in EXAMPLE_RECORDS:
        known_facts |= set(record["facts"])
    for rule in CONFIDENCE_RULES:
        unknown = set(rule["when"]) - known_facts
        assert not unknown, f"rule '{rule['ruleId']}' names unknown facts: {unknown}"


def test_no_basis_claims_more_confidence_than_its_rules_allow() -> None:
    for basis in BASES:
        facts = {
            "basis": basis["basisId"],
            "priceSourceClass": "provider-list-price",
            "hasMeasuredUtilisation": basis["basisId"] == "estimated",
            "windowComplete": True,
            "shapeChangedInWindow": False,
        }
        if basis["basisId"] == "actual":
            expected = "high"
        else:
            expected = derived_confidence(facts)
        assert basis["maxConfidence"] == expected, basis["basisId"]


# --------------------------------------------------------------------------
# Missing data is a state with a reason, never a zero
# --------------------------------------------------------------------------

DERIVED_KEY_TO_OUTPUT = {
    "shareOfNodeCapacity": "share-of-node-capacity",
    "costPerThousandRequests": "cost-per-thousand-requests",
    "costPerMillionTokens": "cost-per-million-tokens",
}

USAGE_INPUT_BY_RECORD_KEY = {
    "requests": "requests",
    "inputTokens": "input-tokens",
    "outputTokens": "output-tokens",
    "cpuSeconds": "cpu-seconds",
    "memoryByteSeconds": "memory-byte-seconds",
    "acceleratorSeconds": "accelerator-seconds",
}


@pytest.mark.parametrize(
    "record", EXAMPLE_RECORDS, ids=lambda record: record["recordId"]
)
def test_a_null_output_carries_a_reason_and_a_reason_carries_a_null(
    record: dict,
) -> None:
    """Both directions, because only one of them catches a substituted zero.

    An input declared unavailable must actually be null - which is what refuses a
    zero written in place of an absent signal - and an input that is null must be
    declared unavailable, which is what refuses a null nobody accounted for.
    """
    unavailable = set(record["completeness"]["unavailableInputs"])
    reasons = set(record["completeness"]["reasons"])

    for input_id in unavailable:
        assert input_id in INPUT_BY_ID, input_id
    for reason in reasons:
        assert reason in REASON_BY_ID, reason

    for key, input_id in USAGE_INPUT_BY_RECORD_KEY.items():
        value = record["usage"][key]
        if input_id in unavailable:
            assert value is None, f"{record['recordId']}.{key} is unavailable and set"
        else:
            assert value is not None, f"{record['recordId']}.{key} is set and absent"

    nulls = [
        key
        for key, value in record["derived"].items()
        if value is None and key in DERIVED_KEY_TO_OUTPUT
    ]
    if nulls:
        assert reasons, record["recordId"]
    for key in nulls:
        output = OUTPUT_BY_ID[DERIVED_KEY_TO_OUTPUT[key]]
        assert reasons & set(output["nullWhen"]), (
            f"{record['recordId']}.{key} is null and no declared reason explains it"
        )


def test_every_reason_the_method_calls_common_is_one_the_method_uses() -> None:
    """A reason nothing reaches for is a reason nobody has thought through."""
    used: set[str] = set()
    for record in EXAMPLE_RECORDS:
        used |= set(record["completeness"]["reasons"])
    used |= {
        row["unavailableReason"]
        for row in INPUTS
        if row["unavailableReason"] is not None
    }
    for row in REASONS:
        if row["v1Common"]:
            assert row["reasonId"] in used, (
                f"reason '{row['reasonId']}' is declared common and nothing uses it"
            )


# --------------------------------------------------------------------------
# The arithmetic, recomputed in exact decimal
# --------------------------------------------------------------------------


def window_hours() -> Decimal:
    return Decimal(EXAMPLE["window"]["hours"])


def recomputed_amount(record: dict) -> Decimal:
    source = EXAMPLE["priceSourceId"]
    reserved = record["reserved"]
    total = (
        Decimal(reserved["cpuCoreHours"]) * rate(source, "cpu-core-hour")
        + Decimal(reserved["memoryGibibyteHours"])
        * rate(source, "memory-gibibyte-hour")
        + Decimal(reserved["acceleratorDeviceHours"])
        * rate(source, "accelerator-device-hour")
    )
    return quantise(total)


@pytest.mark.parametrize(
    "record", EXAMPLE_RECORDS, ids=lambda record: record["recordId"]
)
def test_reserved_quantities_recompute_from_the_declaration(record: dict) -> None:
    declaration = record["declaration"]
    replicas = Decimal(declaration["replicas"])
    hours = window_hours()
    reserved = record["reserved"]
    assert Decimal(reserved["cpuCoreHours"]) == quantise(
        cores(declaration["cpuRequest"]) * replicas * hours
    ), record["recordId"]
    assert Decimal(reserved["memoryGibibyteHours"]) == quantise(
        gibibytes(declaration["memoryRequest"]) * replicas * hours
    ), record["recordId"]
    assert Decimal(reserved["acceleratorDeviceHours"]) == quantise(
        Decimal(declaration["acceleratorCount"]) * replicas * hours
    ), record["recordId"]


@pytest.mark.parametrize(
    "record", EXAMPLE_RECORDS, ids=lambda record: record["recordId"]
)
def test_every_amount_recomputes_from_the_reservation_and_the_rates(
    record: dict,
) -> None:
    assert Decimal(record["cost"]["amount"]) == recomputed_amount(record), record[
        "recordId"
    ]


def test_the_node_capacity_amount_recomputes_from_the_declared_capacity() -> None:
    source = EXAMPLE["priceSourceId"]
    capacity = EXAMPLE["capacity"]
    expected = quantise(
        (
            Decimal(capacity["cpuCores"]) * rate(source, "cpu-core-hour")
            + Decimal(capacity["memoryGibibytes"])
            * rate(source, "memory-gibibyte-hour")
            + Decimal(capacity["acceleratorDevices"])
            * rate(source, "accelerator-device-hour")
        )
        * window_hours()
    )
    assert Decimal(capacity["amount"]) == expected


def test_the_workload_lines_and_the_residual_close_against_the_node() -> None:
    node = Decimal(EXAMPLE["capacity"]["amount"])
    workloads = sum(Decimal(row["cost"]["amount"]) for row in EXAMPLE_RECORDS)
    residual = Decimal(EXAMPLE["unallocated"]["amount"])
    assert quantise(workloads) == Decimal(EXAMPLE["totals"]["workloadAmountSum"])
    assert quantise(node - workloads) == residual
    assert quantise(workloads + residual) == node
    assert EXAMPLE["totals"]["closes"] is True
    assert Decimal(EXAMPLE["totals"]["nodeCapacityAmount"]) == node


@pytest.mark.parametrize("row", COUNTERFACTUALS, ids=lambda row: row["treatmentId"])
def test_every_counterfactual_recomputes_from_the_treatment_it_names(
    row: dict,
) -> None:
    """The argument against a rejected treatment is arithmetic, not an estimate."""
    treatment = next(
        item for item in TREATMENTS if item["treatmentId"] == row["treatmentId"]
    )
    assert treatment["selected"] is False, row["treatmentId"]
    record = next(
        item for item in EXAMPLE_RECORDS if item["recordId"] == row["recordId"]
    )
    amount = Decimal(record["cost"]["amount"])
    workloads = sum(Decimal(item["cost"]["amount"]) for item in EXAMPLE_RECORDS)
    residual = Decimal(EXAMPLE["unallocated"]["amount"])
    if row["treatmentId"] == "spread-pro-rata":
        expected = quantise(amount + residual * (amount / workloads))
    elif row["treatmentId"] == "discard":
        expected = amount
    else:
        raise AssertionError(f"no recomputation for {row['treatmentId']}")
    assert Decimal(row["amount"]) == expected, row["treatmentId"]


def test_every_rejected_treatment_has_a_counterfactual() -> None:
    named = {row["treatmentId"] for row in COUNTERFACTUALS}
    unselected = {row["treatmentId"] for row in TREATMENTS if not row["selected"]}
    assert named == unselected, {
        "unselected without a counterfactual": sorted(unselected - named),
        "counterfactual for a selected treatment": sorted(named - unselected),
    }


def test_every_share_recomputes_against_the_node() -> None:
    node = Decimal(EXAMPLE["capacity"]["amount"])
    for record in EXAMPLE_RECORDS:
        share = Decimal(record["derived"]["shareOfNodeCapacity"])
        assert share == quantise(Decimal(record["cost"]["amount"]) / node), record[
            "recordId"
        ]
    residual = Decimal(EXAMPLE["unallocated"]["amount"])
    assert Decimal(EXAMPLE["unallocated"]["shareOfNodeCapacity"]) == quantise(
        residual / node
    )


@pytest.mark.parametrize(
    "record", EXAMPLE_RECORDS, ids=lambda record: record["recordId"]
)
def test_every_unit_cost_carries_its_denominator_or_is_null(record: dict) -> None:
    amount = Decimal(record["cost"]["amount"])
    derived = record["derived"]

    requests = derived["costPerThousandRequestsDenominator"]
    assert requests == record["usage"]["requests"], record["recordId"]
    if derived["costPerThousandRequests"] is None:
        assert (
            requests is None or requests < DENOMINATORS["minimumRequestsForUnitCost"]
        ), record["recordId"]
    else:
        assert requests >= DENOMINATORS["minimumRequestsForUnitCost"], record[
            "recordId"
        ]
        assert Decimal(derived["costPerThousandRequests"]) == quantise(
            amount / Decimal(requests) * Decimal(1000)
        ), record["recordId"]

    tokens = derived["costPerMillionTokensDenominator"]
    usage = record["usage"]
    if usage["inputTokens"] is None or usage["outputTokens"] is None:
        assert tokens is None, record["recordId"]
        assert derived["costPerMillionTokens"] is None, record["recordId"]
    else:
        assert tokens == usage["inputTokens"] + usage["outputTokens"], record[
            "recordId"
        ]
        assert tokens >= DENOMINATORS["minimumTokensForUnitCost"], record["recordId"]
        assert Decimal(derived["costPerMillionTokens"]) == quantise(
            amount / Decimal(tokens) * Decimal(1000000)
        ), record["recordId"]


def test_a_prerequisite_line_is_attributed_outside_every_workload() -> None:
    prerequisite = EXAMPLE["prerequisite"]
    assert prerequisite["attributedTo"] == "prerequisite-layer"
    workload_ids = {row["identity"]["workloadId"] for row in EXAMPLE_RECORDS}
    assert prerequisite["attributedTo"] not in workload_ids
    expected = quantise(
        Decimal(prerequisite["storageGibibytes"])
        * window_hours()
        * rate(EXAMPLE["priceSourceId"], "storage-gibibyte-hour")
    )
    assert Decimal(prerequisite["amount"]) == expected
    node = Decimal(EXAMPLE["capacity"]["amount"])
    assert Decimal(EXAMPLE["totals"]["environmentAmount"]) == quantise(
        node + Decimal(prerequisite["amount"])
    )


def test_every_amount_and_rate_is_a_decimal_string() -> None:
    """No binary float appears anywhere in the committed method."""
    monetary_keys = {
        "amount",
        "ratePerHour",
        "hours",
        "cpuCores",
        "memoryGibibytes",
        "acceleratorDevices",
        "storageGibibytes",
        "cpuCoreHours",
        "memoryGibibyteHours",
        "acceleratorDeviceHours",
        "shareOfNodeCapacity",
        "costPerThousandRequests",
        "costPerMillionTokens",
        "workloadAmountSum",
        "nodeCapacityAmount",
        "environmentAmount",
    }
    for key, value in walk(METHOD):
        assert not isinstance(value, float), f"{key} is a binary float: {value!r}"
        if key in monetary_keys and value is not None:
            assert isinstance(value, str), f"{key} is not a string: {value!r}"
            assert DECIMAL_STRING.match(value), f"{key} is not a decimal: {value!r}"


def test_the_record_scale_is_the_scale_every_number_is_written_at() -> None:
    assert METHOD["money"]["recordScale"] == 6
    assert METHOD["money"]["derivedScale"] == 6
    assert METHOD["money"]["ratioScale"] == 6
    assert METHOD["money"]["roundingMode"] == "half-even"
    assert EXAMPLE["amountScale"] == METHOD["money"]["recordScale"]


# --------------------------------------------------------------------------
# The telemetry catalog, the workload contract, and what may be committed
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", INPUTS, ids=lambda row: row["inputId"])
def test_every_input_names_a_declared_signal_or_no_source_at_all(row: dict) -> None:
    signal = row["telemetrySignal"]
    if signal is None:
        assert row["telemetryCoverage"] == "none", row["inputId"]
        assert row["coverageNote"].strip(), row["inputId"]
    else:
        assert signal in CATALOG_SIGNAL_NAMES, (
            f"input '{row['inputId']}' names '{signal}', which the telemetry "
            f"catalog does not declare"
        )
        assert row["telemetryCoverage"] in {"full", "partial"}, row["inputId"]


@pytest.mark.parametrize("row", INPUTS, ids=lambda row: row["inputId"])
def test_an_unavailable_input_says_why_and_an_available_one_does_not(
    row: dict,
) -> None:
    if row["v1Available"]:
        assert row["unavailableReason"] is None, row["inputId"]
    else:
        assert row["unavailableReason"] in REASON_BY_ID, row["inputId"]


def test_no_usage_input_is_available_because_nothing_emits_anything() -> None:
    """Coverage says what the catalog would supply; nothing supplies it yet."""
    for row in INPUTS:
        if row["kind"] != "usage":
            continue
        assert row["v1Available"] is False, (
            f"input '{row['inputId']}' claims to be available, and no component "
            f"in this repository emits a single signal"
        )


@pytest.mark.parametrize("row", RECORD_FIELDS, ids=lambda row: row["fieldId"])
def test_committed_record_permission_is_derived_from_the_telemetry_class(
    row: dict,
) -> None:
    """Whether a field may be committed is a property of its class, not a choice."""
    allowed = CATALOG_SENSITIVITY[row["sensitivity"]]["allowedPlacements"]
    assert row["committedRecordAllowed"] == ("evidence-field" in allowed), (
        f"record field '{row['fieldId']}' is {row['sensitivity']}, which "
        f"{'permits' if 'evidence-field' in allowed else 'forbids'} a committed "
        f"record, and declares the opposite"
    )


def test_no_committed_record_carries_a_tenant_identifier() -> None:
    tenant_fields = [
        row["fieldId"]
        for row in RECORD_FIELDS
        if row["sensitivity"] == "tenant-attributable"
    ]
    assert tenant_fields, "the record shape declares no tenant field to exclude"
    for field_id in tenant_fields:
        row = next(r for r in RECORD_FIELDS if r["fieldId"] == field_id)
        assert row["committedRecordAllowed"] is False, field_id
        assert row["required"] is False, field_id
    for record in EXAMPLE_RECORDS:
        rendered = json.dumps(record)
        assert "tenant" not in rendered.lower(), record["recordId"]


def test_no_content_or_secret_class_reaches_the_record_shape() -> None:
    for row in RECORD_FIELDS:
        allowed = CATALOG_SENSITIVITY[row["sensitivity"]]["allowedPlacements"]
        assert allowed, (
            f"record field '{row['fieldId']}' is classed '{row['sensitivity']}', "
            f"which has no permitted placement anywhere"
        )


def test_the_deferred_cost_attribute_is_the_one_this_method_names() -> None:
    """The catalog reserved a name for this; the method has to use that name."""
    reserved = [
        row["name"]
        for row in CATALOG["attributes"]
        if row["attributeId"] == "cost-record-id"
    ]
    assert reserved == ["inferops.cost.record.id"], reserved
    named = {row["telemetrySignal"] for row in INPUTS}
    assert "inferops.cost.record.id" in named


def test_every_declared_input_is_required_by_something() -> None:
    used: set[str] = set()
    for row in ALLOCATION_METHODS:
        used |= set(row["inputsRequired"])
    for row in OUTPUTS:
        used |= {dep for dep in row["dependsOn"] if dep in INPUT_BY_ID}
    for row in GAPS:
        used |= set(row["affects"])
    for row in INPUTS:
        if row["kind"] == "identity":
            continue
        assert row["inputId"] in used, (
            f"input '{row['inputId']}' is declared and no method, output, or gap "
            f"needs it"
        )


# --------------------------------------------------------------------------
# Overclaiming
# --------------------------------------------------------------------------


def test_the_method_states_that_nothing_computes_it() -> None:
    status = METHOD["computationStatus"]
    assert status["state"] == "nothing-computes"
    assert status["invoicesRead"] == 0
    assert status["costRecordsProduced"] == 0
    assert "not selected" in status["producer"]


def test_the_worked_example_says_it_is_synthetic_in_its_own_contents() -> None:
    assert EXAMPLE["classification"] == "synthetic"
    assert "invented" in EXAMPLE["warning"]


@pytest.mark.parametrize("row", PROHIBITIONS, ids=lambda row: row["ruleId"])
def test_a_rule_claims_a_test_only_when_that_test_exists(row: dict) -> None:
    module = THIS_MODULE.read_text(encoding="utf-8")
    if row["enforcement"] == "test":
        assert row["enforcedBy"], row["ruleId"]
        assert f"def {row['enforcedBy']}(" in module, (
            f"rule '{row['ruleId']}' names '{row['enforcedBy']}', which does not "
            f"exist in this module"
        )
    else:
        assert row["enforcedBy"] is None, row["ruleId"]


def test_at_least_one_rule_admits_it_is_enforced_by_review_alone() -> None:
    """A method whose every rule claims a test has mislabelled one of them."""
    review_only = [
        row["ruleId"] for row in PROHIBITIONS if row["enforcement"] == "review"
    ]
    assert review_only, "every rule claims a test, which is not credible"


def test_the_method_declares_a_limitation_for_every_gap_it_has() -> None:
    statements = " ".join(row["statement"] for row in LIMITATIONS).lower()
    for phrase in (
        "no component in this repository computes",
        "no provider account",
        "invented",
        "metrics server",
        "declared, not derived",
    ):
        assert phrase in statements, f"no limitation covers: {phrase}"


def test_no_output_claims_a_precision_the_method_does_not_declare() -> None:
    for row in OUTPUTS:
        assert row["scale"] == METHOD["money"]["recordScale"], row["outputId"]


def test_the_strategy_names_the_directory_this_suite_lives_in() -> None:
    layer = next(row for row in STRATEGY["layers"] if row["layerId"] == DECLARING_LAYER)
    assert DECLARED_PATH in layer["paths"], (
        f"layer '{DECLARING_LAYER}' does not name {DECLARED_PATH}, so nothing "
        f"here is collected by it"
    )


# --------------------------------------------------------------------------
# The documents and the data, compared in both directions
# --------------------------------------------------------------------------


def published_ids(document: str) -> set[str]:
    return set(FIRST_TABLE_COLUMN.findall(document))


def test_the_method_document_publishes_every_basis_method_and_treatment(
    method_document: str,
) -> None:
    published = published_ids(method_document)
    expected = (
        set(BASIS_BY_ID)
        | set(ALLOCATION_BY_ID)
        | {row["treatmentId"] for row in TREATMENTS}
    )
    assert not expected - published, sorted(expected - published)


def test_the_method_document_publishes_every_unit_level_and_reason(
    method_document: str,
) -> None:
    published = published_ids(method_document)
    expected = set(UNIT_BY_ID) | set(LEVEL_BY_ID) | set(REASON_BY_ID)
    assert not expected - published, sorted(expected - published)


def test_the_method_document_publishes_every_input_and_output(
    method_document: str,
) -> None:
    published = published_ids(method_document)
    expected = {row["name"] for row in INPUTS} | {row["name"] for row in OUTPUTS}
    assert not expected - published, sorted(expected - published)


def test_the_method_document_publishes_every_rule(method_document: str) -> None:
    published = published_ids(method_document)
    expected = {row["ruleId"] for row in PROHIBITIONS}
    assert not expected - published, sorted(expected - published)


def test_the_worked_example_document_publishes_every_record(
    example_document: str,
) -> None:
    published = published_ids(example_document)
    expected = {row["recordId"] for row in EXAMPLE_RECORDS}
    assert not expected - published, sorted(expected - published)


def test_the_worked_example_document_publishes_every_amount_the_data_declares(
    example_document: str,
) -> None:
    for value in declared_decimals():
        assert value in example_document, (
            f"the worked example document does not publish {value}"
        )


def test_the_worked_example_document_invents_no_number_the_data_lacks(
    example_document: str,
) -> None:
    declared = declared_decimals()
    found = set(DECIMAL_IN_PROSE.findall(example_document))
    assert not found - declared, sorted(found - declared)


def declared_decimals() -> set[str]:
    found: set[str] = set()
    for _, value in walk(EXAMPLE):
        if isinstance(value, str) and DECIMAL_STRING.match(value):
            found.add(value)
    for source in PRICE_SOURCES:
        for row in source["rates"]:
            found.add(row["ratePerHour"])
    return found


def test_no_document_publishes_an_identifier_the_data_does_not_have(
    method_document: str,
    example_document: str,
    cost_readme: str,
) -> None:
    known = declared_identifiers()
    for name, document in (
        ("cost-method.md", method_document),
        ("worked-example.md", example_document),
        ("README.md", cost_readme),
    ):
        stray = published_ids(document) - known
        assert not stray, f"{name} publishes {sorted(stray)}"
