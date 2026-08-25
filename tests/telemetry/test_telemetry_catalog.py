"""Deterministic checks over the V1 telemetry and evidence catalog.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness.

What this suite establishes is that the catalog is internally consistent and that
it agrees with the records and contracts already committed beside it: that every
signal states the question it answers; that a field's placement is a consequence of
its sensitivity class and its cardinality class rather than a judgement call, so a
prompt, a secret, a correlation identifier, a tenant identifier, and a measured
duration are each excluded from a metric label by rule; that every metric's series
count is arithmetic the suite recomputes rather than a number somebody typed; that
every required signal family has an active metric behind it; that every native
runtime series the catalog names appears in the record that measured it, and the
one that is missing is recorded as missing; that content capture is disabled and
has no policy that could enable it; and that the four evidence templates carry
every section a record needs to be reproducible.

What it does not establish is that any of this is emitted. Nothing in this
repository writes a metric, a log record, or a span, and this suite cannot tell the
difference between a catalog that will be implemented faithfully and one that will
be ignored. It stops the catalog drifting; it does not observe a single signal.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_DIR = REPO_ROOT / "docs" / "telemetry"
CATALOG_PATH = TELEMETRY_DIR / "telemetry-catalog.v1alpha1.json"
STRATEGY_PATH = REPO_ROOT / "docs" / "testing" / "test-strategy.v1alpha1.json"
THIS_MODULE = Path(__file__)

EXPECTED_CATALOG_ID = "https://inferops.io/telemetry/telemetry-catalog.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

# This suite is collected by the documentation layer of the test strategy, which
# has to name the directory it lives in or the layer selects nothing here.
DECLARING_LAYER = "documentation"
DECLARED_PATH = "tests/telemetry"

# Identifiers in the catalog are lowercase, hyphen-separated slugs.
SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# A published field or metric name: dotted attribute names, underscored metric
# names, and the runtime's colon-prefixed series all have to pass.
PUBLISHED_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")

# An identifier as a document publishes it: an inline code span in the first
# column of a Markdown table row.
FIRST_TABLE_COLUMN = re.compile(
    r"^\|\s*`([A-Za-z_][A-Za-z0-9_.:-]*)`\s*\|", flags=re.MULTILINE
)

# A level-two heading, as the evidence templates are required to publish one.
HEADING = re.compile(r"^##\s+(.+?)\s*$", flags=re.MULTILINE)

REQUIRED_PLACEMENT_FIELDS = ("placementId", "meaning", "retention")

REQUIRED_SENSITIVITY_FIELDS = ("classId", "meaning", "allowedPlacements")

REQUIRED_CARDINALITY_FIELDS = (
    "classId",
    "meaning",
    "minDistinctValues",
    "maxDistinctValues",
    "allowedPlacements",
)

REQUIRED_EMITTER_FIELDS = ("emitterId", "name", "exists", "notes")

REQUIRED_FAMILY_FIELDS = ("familyId", "question", "required")

REQUIRED_ATTRIBUTE_FIELDS = (
    "attributeId",
    "name",
    "layer",
    "question",
    "sensitivity",
    "cardinality",
    "maxDistinctValues",
    "identityOnly",
    "placements",
    "v1Status",
    "deferralReason",
    "notes",
)

REQUIRED_METRIC_FIELDS = (
    "metricId",
    "name",
    "kind",
    "instrument",
    "unit",
    "question",
    "families",
    "emitter",
    "labels",
    "seriesModel",
    "buckets",
    "maxSeries",
    "v1Status",
    "deferralReason",
    "runtimeSeries",
    "notes",
)

REQUIRED_FORBIDDEN_FIELDS = (
    "fieldId",
    "name",
    "sensitivity",
    "whyItIsTempting",
    "ruleRef",
)

REQUIRED_PROHIBITION_FIELDS = (
    "ruleId",
    "statement",
    "rationale",
    "enforcement",
    "enforcedBy",
)

REQUIRED_TEMPLATE_FIELDS = (
    "templateId",
    "path",
    "purpose",
    "v1Status",
    "recordsProduced",
)

REQUIRED_SECTION_FIELDS = ("sectionId", "heading", "why")

ATTRIBUTE_LAYERS = frozenset({"resource", "request", "record"})

SIGNAL_STATUSES = frozenset({"specified", "deferred"})

METRIC_KINDS = frozenset({"operational", "info"})

INSTRUMENTS = frozenset({"counter", "gauge", "histogram"})

SERIES_MODELS = frozenset({"label-product", "one-per-process"})

ENFORCEMENT_KINDS = frozenset({"test", "review"})

# The classes whose whole point is that they may not key a series.
UNKEYABLE_CARDINALITIES = frozenset({"unbounded", "measurement"})

# The classes that carry data this project does not own.
UNEMITTABLE_SENSITIVITIES = frozenset({"user-content", "secret"})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


CATALOG = load(CATALOG_PATH)

PLACEMENTS = CATALOG["placements"]
SENSITIVITY_CLASSES = CATALOG["sensitivityClasses"]
CARDINALITY_CLASSES = CATALOG["cardinalityClasses"]
EMITTERS = CATALOG["emitters"]
FAMILIES = CATALOG["signalFamilies"]
ATTRIBUTES = CATALOG["attributes"]
FORBIDDEN = CATALOG["forbiddenFields"]
METRICS = CATALOG["metrics"]
PROHIBITIONS = CATALOG["prohibitions"]
TEMPLATES = CATALOG["evidenceTemplates"]
SECTIONS = CATALOG["evidenceSections"]
LIMITATIONS = CATALOG["limitations"]
CORRELATION = CATALOG["correlation"]
LOG_RECORD = CATALOG["logRecord"]
CONTENT_CAPTURE = CATALOG["contentCapture"]
RUNTIME_SERIES = CATALOG["runtimeNativeSeries"]
BUDGET = CATALOG["cardinalityBudget"]

PLACEMENT_BY_ID = {row["placementId"]: row for row in PLACEMENTS}
SENSITIVITY_BY_ID = {row["classId"]: row for row in SENSITIVITY_CLASSES}
CARDINALITY_BY_ID = {row["classId"]: row for row in CARDINALITY_CLASSES}
EMITTER_BY_ID = {row["emitterId"]: row for row in EMITTERS}
FAMILY_BY_ID = {row["familyId"]: row for row in FAMILIES}
ATTRIBUTE_BY_ID = {row["attributeId"]: row for row in ATTRIBUTES}
METRIC_BY_ID = {row["metricId"]: row for row in METRICS}
PROHIBITION_BY_ID = {row["ruleId"]: row for row in PROHIBITIONS}
TEMPLATE_BY_ID = {row["templateId"]: row for row in TEMPLATES}

ATTRIBUTE_NAMES = {row["name"] for row in ATTRIBUTES}

ACTIVE_METRICS = [row for row in METRICS if row["v1Status"] != "deferred"]
ACTIVE_ATTRIBUTES = [row for row in ATTRIBUTES if row["v1Status"] != "deferred"]

# Everything the catalog publishes under a name, for the both-directions checks
# against the documents. A code span in a document that is in none of these is a
# typo or an identifier somebody removed from the data and left in the prose.
ALL_IDENTIFIERS = (
    {row["attributeId"] for row in ATTRIBUTES}
    | {row["name"] for row in ATTRIBUTES}
    | {row["metricId"] for row in METRICS}
    | {row["name"] for row in METRICS}
    | {row["fieldId"] for row in FORBIDDEN}
    | {row["ruleId"] for row in PROHIBITIONS}
    | {row["templateId"] for row in TEMPLATES}
    | {row["sectionId"] for row in SECTIONS}
    | {row["heading"] for row in SECTIONS}
    | {row["familyId"] for row in FAMILIES}
    | {row["placementId"] for row in PLACEMENTS}
    | {row["classId"] for row in SENSITIVITY_CLASSES}
    | {row["classId"] for row in CARDINALITY_CLASSES}
    | {row["emitterId"] for row in EMITTERS}
    | {row["limitationId"] for row in LIMITATIONS}
    | {row["seriesName"] for row in RUNTIME_SERIES["series"]}
    | {header["name"] for header in CORRELATION["headers"]}
)


@pytest.fixture(scope="module")
def catalog_document() -> str:
    return (TELEMETRY_DIR / "telemetry-catalog.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def redaction_document() -> str:
    return (TELEMETRY_DIR / "redaction.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def proof_readme() -> str:
    return (REPO_ROOT / "docs" / "proof" / "README.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def module_source() -> str:
    return THIS_MODULE.read_text(encoding="utf-8")


def effective_placements(attribute: dict) -> set[str]:
    """What both classes allow. Placement is derived, never chosen."""
    sensitivity = set(SENSITIVITY_BY_ID[attribute["sensitivity"]]["allowedPlacements"])
    cardinality = set(CARDINALITY_BY_ID[attribute["cardinality"]]["allowedPlacements"])
    return sensitivity & cardinality


def computed_series(metric: dict) -> int:
    if metric["seriesModel"] == "one-per-process":
        return metric["maxSeries"]
    product = 1
    for label in metric["labels"]:
        product *= ATTRIBUTE_BY_ID[label]["maxDistinctValues"]
    if metric["buckets"] is not None:
        # One series per bucket boundary, plus the sum and the count.
        product *= metric["buckets"] + 2
    return product


def published_ids(document: str) -> set[str]:
    return set(FIRST_TABLE_COLUMN.findall(document))


# --------------------------------------------------------------------------
# The catalog is well formed
# --------------------------------------------------------------------------


def test_the_catalog_declares_its_identity_and_contract_version() -> None:
    assert CATALOG["$id"] == EXPECTED_CATALOG_ID
    assert CATALOG["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_the_catalog_is_not_empty() -> None:
    for name, rows in (
        ("placements", PLACEMENTS),
        ("sensitivityClasses", SENSITIVITY_CLASSES),
        ("cardinalityClasses", CARDINALITY_CLASSES),
        ("emitters", EMITTERS),
        ("signalFamilies", FAMILIES),
        ("attributes", ATTRIBUTES),
        ("forbiddenFields", FORBIDDEN),
        ("metrics", METRICS),
        ("prohibitions", PROHIBITIONS),
        ("evidenceTemplates", TEMPLATES),
        ("evidenceSections", SECTIONS),
        ("limitations", LIMITATIONS),
    ):
        assert rows, name


@pytest.mark.parametrize("row", PLACEMENTS, ids=lambda row: row["placementId"])
def test_every_placement_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_PLACEMENT_FIELDS:
        assert row.get(field), (row["placementId"], field)


@pytest.mark.parametrize("row", SENSITIVITY_CLASSES, ids=lambda row: row["classId"])
def test_every_sensitivity_class_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_SENSITIVITY_FIELDS:
        assert field in row, (row["classId"], field)
    assert row["meaning"], row["classId"]


@pytest.mark.parametrize("row", CARDINALITY_CLASSES, ids=lambda row: row["classId"])
def test_every_cardinality_class_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_CARDINALITY_FIELDS:
        assert field in row, (row["classId"], field)
    assert row["meaning"], row["classId"]


@pytest.mark.parametrize("row", EMITTERS, ids=lambda row: row["emitterId"])
def test_every_emitter_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_EMITTER_FIELDS:
        assert field in row, (row["emitterId"], field)
    assert isinstance(row["exists"], bool), row["emitterId"]


@pytest.mark.parametrize("row", FAMILIES, ids=lambda row: row["familyId"])
def test_every_family_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_FAMILY_FIELDS:
        assert field in row, (row["familyId"], field)
    assert isinstance(row["required"], bool), row["familyId"]


@pytest.mark.parametrize("row", ATTRIBUTES, ids=lambda row: row["attributeId"])
def test_every_attribute_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_ATTRIBUTE_FIELDS:
        assert field in row, (row["attributeId"], field)
    assert SLUG.match(row["attributeId"]), row["attributeId"]
    assert PUBLISHED_NAME.match(row["name"]), row["name"]
    assert row["layer"] in ATTRIBUTE_LAYERS, row["layer"]
    assert row["v1Status"] in SIGNAL_STATUSES, row["v1Status"]
    assert isinstance(row["identityOnly"], bool), row["attributeId"]


@pytest.mark.parametrize("row", METRICS, ids=lambda row: row["metricId"])
def test_every_metric_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_METRIC_FIELDS:
        assert field in row, (row["metricId"], field)
    assert SLUG.match(row["metricId"]), row["metricId"]
    assert PUBLISHED_NAME.match(row["name"]), row["name"]
    assert row["kind"] in METRIC_KINDS, row["kind"]
    assert row["instrument"] in INSTRUMENTS, row["instrument"]
    assert row["seriesModel"] in SERIES_MODELS, row["seriesModel"]
    assert row["v1Status"] in SIGNAL_STATUSES, row["v1Status"]


@pytest.mark.parametrize("row", FORBIDDEN, ids=lambda row: row["fieldId"])
def test_every_forbidden_field_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_FORBIDDEN_FIELDS:
        assert row.get(field), (row["fieldId"], field)


@pytest.mark.parametrize("row", PROHIBITIONS, ids=lambda row: row["ruleId"])
def test_every_prohibition_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_PROHIBITION_FIELDS:
        assert field in row, (row["ruleId"], field)
    assert row["statement"] and row["rationale"], row["ruleId"]
    assert row["enforcement"] in ENFORCEMENT_KINDS, row["enforcement"]


@pytest.mark.parametrize("row", TEMPLATES, ids=lambda row: row["templateId"])
def test_every_template_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_TEMPLATE_FIELDS:
        assert field in row, (row["templateId"], field)
    assert row["purpose"], row["templateId"]


@pytest.mark.parametrize("row", SECTIONS, ids=lambda row: row["sectionId"])
def test_every_evidence_section_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_SECTION_FIELDS:
        assert row.get(field), (row["sectionId"], field)


def test_identifiers_are_unique() -> None:
    for name, ids in (
        ("placements", [row["placementId"] for row in PLACEMENTS]),
        ("sensitivityClasses", [row["classId"] for row in SENSITIVITY_CLASSES]),
        ("cardinalityClasses", [row["classId"] for row in CARDINALITY_CLASSES]),
        ("emitters", [row["emitterId"] for row in EMITTERS]),
        ("signalFamilies", [row["familyId"] for row in FAMILIES]),
        ("attributeIds", [row["attributeId"] for row in ATTRIBUTES]),
        ("attributeNames", [row["name"] for row in ATTRIBUTES]),
        ("metricIds", [row["metricId"] for row in METRICS]),
        ("metricNames", [row["name"] for row in METRICS]),
        ("forbiddenFields", [row["fieldId"] for row in FORBIDDEN]),
        ("prohibitions", [row["ruleId"] for row in PROHIBITIONS]),
        ("templates", [row["templateId"] for row in TEMPLATES]),
        ("evidenceSections", [row["sectionId"] for row in SECTIONS]),
        ("limitations", [row["limitationId"] for row in LIMITATIONS]),
        ("runtimeSeries", [row["seriesName"] for row in RUNTIME_SERIES["series"]]),
    ):
        assert len(ids) == len(set(ids)), name


def test_every_declared_class_and_placement_is_used() -> None:
    used_placements = {p for row in ATTRIBUTES for p in row["placements"]}
    assert set(PLACEMENT_BY_ID) - used_placements == set()

    used_sensitivities = {row["sensitivity"] for row in ATTRIBUTES} | {
        row["sensitivity"] for row in FORBIDDEN
    }
    assert set(SENSITIVITY_BY_ID) - used_sensitivities == set()

    used_cardinalities = {row["cardinality"] for row in ATTRIBUTES}
    assert set(CARDINALITY_BY_ID) - used_cardinalities == set()


def test_every_declared_emitter_emits_something() -> None:
    """An emitter with nothing behind it is a component nobody is observing."""
    used = {row["emitter"] for row in METRICS} | {RUNTIME_SERIES["emitter"]}
    assert set(EMITTER_BY_ID) - used == set(), sorted(set(EMITTER_BY_ID) - used)
    assert RUNTIME_SERIES["emitter"] in EMITTER_BY_ID, RUNTIME_SERIES["emitter"]


def test_every_declared_family_has_a_metric() -> None:
    used = {family for row in METRICS for family in row["families"]}
    assert set(FAMILY_BY_ID) - used == set(), sorted(set(FAMILY_BY_ID) - used)


# --------------------------------------------------------------------------
# References resolve
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "decisionRef",
        "documentRef",
        "redactionRef",
        "evidenceTemplatesRef",
        "architectureRef",
        "strategyRef",
    ],
)
def test_the_data_points_back_at_the_documents_that_describe_it(field: str) -> None:
    ref = CATALOG[field]
    assert (REPO_ROOT / ref).is_file(), f"{field} -> {ref}"


@pytest.mark.parametrize("row", ATTRIBUTES, ids=lambda row: row["attributeId"])
def test_every_attribute_names_declared_classes(row: dict) -> None:
    assert row["sensitivity"] in SENSITIVITY_BY_ID, row["sensitivity"]
    assert row["cardinality"] in CARDINALITY_BY_ID, row["cardinality"]
    for placement in row["placements"]:
        assert placement in PLACEMENT_BY_ID, placement


@pytest.mark.parametrize("row", METRICS, ids=lambda row: row["metricId"])
def test_every_metric_names_a_declared_emitter_family_and_labels(row: dict) -> None:
    assert row["emitter"] in EMITTER_BY_ID, row["emitter"]
    assert row["families"], row["metricId"]
    for family in row["families"]:
        assert family in FAMILY_BY_ID, family
    for label in row["labels"]:
        assert label in ATTRIBUTE_BY_ID, label


@pytest.mark.parametrize("row", FORBIDDEN, ids=lambda row: row["fieldId"])
def test_every_forbidden_field_names_a_rule_and_an_unemittable_class(row: dict) -> None:
    assert row["ruleRef"] in PROHIBITION_BY_ID, row["ruleRef"]
    assert row["sensitivity"] in UNEMITTABLE_SENSITIVITIES, row["sensitivity"]


def test_the_rule_identifier_label_is_bounded_by_something_committed() -> None:
    """The one label whose bound can be checked rather than asserted."""
    attribute = ATTRIBUTE_BY_ID["rule-id"]
    source = REPO_ROOT / attribute["valueSourceRef"]
    assert source.is_file(), attribute["valueSourceRef"]
    fixtures = json.loads(source.read_text(encoding="utf-8"))["fixtures"]
    published = {
        rejection["rule"]
        for fixture in fixtures.values()
        for rejection in fixture["expected"]
    }
    assert len(published) <= attribute["maxDistinctValues"], {
        "published rules": len(published),
        "declared budget": attribute["maxDistinctValues"],
    }


# --------------------------------------------------------------------------
# Placement is derived from sensitivity and cardinality, never chosen
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", ATTRIBUTES, ids=lambda row: row["attributeId"])
def test_every_placement_is_allowed_by_both_classes(row: dict) -> None:
    allowed = effective_placements(row)
    declared = set(row["placements"])
    assert declared <= allowed, {
        "attribute": row["attributeId"],
        "not permitted": sorted(declared - allowed),
        "sensitivity": row["sensitivity"],
        "cardinality": row["cardinality"],
    }


@pytest.mark.parametrize("row", ACTIVE_ATTRIBUTES, ids=lambda row: row["attributeId"])
def test_an_active_attribute_is_placed_somewhere(row: dict) -> None:
    assert row["placements"], row["attributeId"]


@pytest.mark.parametrize("row", ATTRIBUTES, ids=lambda row: row["attributeId"])
def test_a_bounded_attribute_declares_a_bound_inside_its_class(row: dict) -> None:
    cardinality = CARDINALITY_BY_ID[row["cardinality"]]
    if cardinality["maxDistinctValues"] is None:
        assert row["maxDistinctValues"] is None, row["attributeId"]
        return
    assert row["maxDistinctValues"] is not None, row["attributeId"]
    assert (
        cardinality["minDistinctValues"]
        <= row["maxDistinctValues"]
        <= cardinality["maxDistinctValues"]
    ), {
        "attribute": row["attributeId"],
        "declared": row["maxDistinctValues"],
        "class range": [
            cardinality["minDistinctValues"],
            cardinality["maxDistinctValues"],
        ],
    }


def test_a_forbidden_field_is_allowed_nowhere() -> None:
    """Content and credentials have no safe placement, so they have none at all."""
    for class_id in UNEMITTABLE_SENSITIVITIES:
        assert SENSITIVITY_BY_ID[class_id]["allowedPlacements"] == [], class_id

    forbidden_names = {row["name"] for row in FORBIDDEN}
    for row in ATTRIBUTES:
        assert row["sensitivity"] not in UNEMITTABLE_SENSITIVITIES, row["attributeId"]
        assert row["name"] not in forbidden_names, row["attributeId"]


def test_no_operational_metric_label_is_unbounded() -> None:
    for metric in METRICS:
        if metric["kind"] != "operational":
            continue
        for label in metric["labels"]:
            attribute = ATTRIBUTE_BY_ID[label]
            assert attribute["cardinality"] not in UNKEYABLE_CARDINALITIES, {
                "metric": metric["metricId"],
                "label": label,
                "cardinality": attribute["cardinality"],
            }
            assert "metric-label" in attribute["placements"], {
                "metric": metric["metricId"],
                "label": label,
            }


def test_no_metric_label_is_a_request_scoped_identifier() -> None:
    for metric in METRICS:
        for label in metric["labels"]:
            attribute = ATTRIBUTE_BY_ID[label]
            assert attribute["sensitivity"] != "request-scoped-identifier", {
                "metric": metric["metricId"],
                "label": label,
            }


def test_a_tenant_identifier_stays_out_of_metrics_and_evidence() -> None:
    allowed = set(SENSITIVITY_BY_ID["tenant-attributable"]["allowedPlacements"])
    assert "metric-label" not in allowed
    assert "info-label" not in allowed
    assert "evidence-field" not in allowed

    for row in ATTRIBUTES:
        if row["sensitivity"] != "tenant-attributable":
            continue
        assert set(row["placements"]) <= allowed, row["attributeId"]

    tenant_attributes = {
        row["attributeId"]
        for row in ATTRIBUTES
        if row["sensitivity"] == "tenant-attributable"
    }
    for metric in METRICS:
        assert not tenant_attributes & set(metric["labels"]), metric["metricId"]


def test_identity_attributes_appear_only_on_an_identity_metric() -> None:
    for row in ATTRIBUTES:
        if not row["identityOnly"]:
            continue
        assert "metric-label" not in row["placements"], row["attributeId"]
        assert "info-label" in row["placements"], row["attributeId"]

    for metric in METRICS:
        expected = "info-label" if metric["kind"] == "info" else "metric-label"
        for label in metric["labels"]:
            assert expected in ATTRIBUTE_BY_ID[label]["placements"], {
                "metric": metric["metricId"],
                "kind": metric["kind"],
                "label": label,
                "needs placement": expected,
            }


def test_an_identity_metric_emits_one_series_per_process() -> None:
    identity = [row for row in METRICS if row["kind"] == "info"]
    assert identity, "no identity metric is defined"
    for metric in identity:
        assert metric["seriesModel"] == "one-per-process", metric["metricId"]
        assert metric["instrument"] == "gauge", metric["metricId"]


# --------------------------------------------------------------------------
# Nothing exists because it was available
# --------------------------------------------------------------------------


def test_every_signal_states_the_question_it_answers() -> None:
    for row in ATTRIBUTES:
        assert row["question"].strip(), row["attributeId"]
        assert row["question"].strip().endswith("?"), row["attributeId"]
    for row in METRICS:
        assert row["question"].strip(), row["metricId"]
        assert row["question"].strip().endswith("?"), row["metricId"]
    for row in FAMILIES:
        assert row["question"].strip().endswith("?"), row["familyId"]


def test_a_deferred_signal_says_why_and_an_active_one_does_not() -> None:
    for row in ATTRIBUTES:
        if row["v1Status"] == "deferred":
            assert row["deferralReason"], row["attributeId"]
        else:
            assert row["deferralReason"] is None, row["attributeId"]
    for row in METRICS:
        if row["v1Status"] == "deferred":
            assert row["deferralReason"], row["metricId"]
        else:
            assert row["deferralReason"] is None, row["metricId"]


def test_every_required_family_is_covered_by_an_active_metric() -> None:
    covered = {family for row in ACTIVE_METRICS for family in row["families"]}
    required = {row["familyId"] for row in FAMILIES if row["required"]}
    assert required <= covered, sorted(required - covered)


def test_a_family_no_active_metric_covers_is_not_required() -> None:
    covered = {family for row in ACTIVE_METRICS for family in row["families"]}
    for row in FAMILIES:
        if row["familyId"] not in covered:
            assert not row["required"], row["familyId"]


def test_a_deferred_metric_is_not_the_only_cover_for_a_required_family() -> None:
    """A required family covered only by something deferred is an uncovered one."""
    for row in FAMILIES:
        if not row["required"]:
            continue
        active = [m for m in ACTIVE_METRICS if row["familyId"] in m["families"]]
        assert active, row["familyId"]


# --------------------------------------------------------------------------
# The cardinality budget is arithmetic, not a promise
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", METRICS, ids=lambda row: row["metricId"])
def test_every_metric_stays_inside_the_series_budget(row: dict) -> None:
    assert row["maxSeries"] == computed_series(row), {
        "metric": row["metricId"],
        "declared": row["maxSeries"],
        "computed from labels": computed_series(row),
    }
    assert row["maxSeries"] <= BUDGET["perMetricMaxSeries"], {
        "metric": row["metricId"],
        "maxSeries": row["maxSeries"],
        "ceiling": BUDGET["perMetricMaxSeries"],
    }


def test_the_active_catalog_stays_inside_the_total_budget() -> None:
    total = sum(row["maxSeries"] for row in ACTIVE_METRICS)
    assert total <= BUDGET["totalMaxSeries"], {
        "total": total,
        "ceiling": BUDGET["totalMaxSeries"],
    }


@pytest.mark.parametrize("row", METRICS, ids=lambda row: row["metricId"])
def test_a_histogram_declares_buckets_and_nothing_else_does(row: dict) -> None:
    if row["instrument"] == "histogram":
        assert isinstance(row["buckets"], int) and row["buckets"] > 0, row["metricId"]
    else:
        assert row["buckets"] is None, row["metricId"]


@pytest.mark.parametrize("row", METRICS, ids=lambda row: row["metricId"])
def test_a_label_free_metric_is_one_series_per_process(row: dict) -> None:
    if row["labels"]:
        return
    assert row["seriesModel"] == "one-per-process", row["metricId"]


# --------------------------------------------------------------------------
# Nothing claims to be emitted, and nothing claims a series that was not seen
# --------------------------------------------------------------------------


def test_the_catalog_states_that_nothing_emits_it() -> None:
    assert CATALOG["emissionStatus"]["state"] == "nothing-emits"
    assert CATALOG["emissionStatus"]["meaning"].strip()
    assert CATALOG["emissionStatus"]["collector"].strip()


def test_no_metric_borrows_the_credibility_of_a_component_that_exists() -> None:
    """The runtime is the only emitter here that emits anything at all.

    What it emits is recorded separately, under an evidence reference, because it
    was measured. A metric assigned to it would be a native series wearing an
    InferOps name — a specification for an unbuilt component made to look like a
    scrape that already happened.
    """
    assert CATALOG["emissionStatus"]["state"] == "nothing-emits"
    for metric in METRICS:
        assert metric["emitter"] != RUNTIME_SERIES["emitter"], {
            "metric": metric["metricId"],
            "assigned to the emitter whose series are recorded as evidence": (
                RUNTIME_SERIES["emitter"]
            ),
        }


def yes_no_column(document: str, header: str) -> dict[str, bool]:
    """Read a `yes`/`no` column keyed by the attribute name in the first cell.

    The document repeats two derived properties in prose form — whether an
    attribute is identity-only, and whether it may be a metric label. Prose that
    restates data is prose that drifts from it, so the column is parsed and
    compared rather than trusted.
    """
    answers: dict[str, bool] = {}
    column: int | None = None
    for line in document.splitlines():
        if not line.startswith("|"):
            column = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header in cells:
            column = cells.index(header)
            continue
        if column is None or column >= len(cells):
            continue
        name = cells[0].strip("`")
        if name not in ATTRIBUTE_NAMES:
            continue
        if cells[column] in ("yes", "no"):
            answers[name] = cells[column] == "yes"
    return answers


def test_the_document_agrees_with_the_data_on_what_is_identity_only(
    catalog_document: str,
) -> None:
    published = yes_no_column(catalog_document, "Identity only?")
    expected = {
        row["name"]: row["identityOnly"]
        for row in ATTRIBUTES
        if row["layer"] == "resource"
    }
    assert published == expected, {
        "in the document": published,
        "in the data": expected,
    }


def test_the_document_agrees_with_the_data_on_what_may_be_a_metric_label(
    catalog_document: str,
) -> None:
    published = yes_no_column(catalog_document, "Metric label?")
    expected = {
        row["name"]: "metric-label" in row["placements"]
        for row in ATTRIBUTES
        if row["layer"] == "request" and row["v1Status"] != "deferred"
    }
    assert published == expected, {
        "in the document": published,
        "in the data": expected,
    }


def test_every_runtime_series_appears_in_the_record_that_measured_it() -> None:
    record_path = REPO_ROOT / RUNTIME_SERIES["evidenceRef"]
    assert record_path.is_file(), RUNTIME_SERIES["evidenceRef"]
    record = record_path.read_text(encoding="utf-8")
    for row in RUNTIME_SERIES["series"]:
        assert row["seriesName"] in record, {
            "series": row["seriesName"],
            "record": RUNTIME_SERIES["evidenceRef"],
        }


def test_every_runtime_series_maps_to_a_declared_metric_or_to_nothing() -> None:
    for row in RUNTIME_SERIES["series"]:
        if row["mapsTo"] is None:
            assert row["note"], row["seriesName"]
            continue
        assert row["mapsTo"] in METRIC_BY_ID, row["mapsTo"]


def test_the_missing_request_counter_is_recorded_as_missing_and_covered() -> None:
    assert RUNTIME_SERIES["absentSeries"], "the measured gap is not recorded"
    for row in RUNTIME_SERIES["absentSeries"]:
        assert row["coveredBy"] in METRIC_BY_ID, row["coveredBy"]
        covering = METRIC_BY_ID[row["coveredBy"]]
        assert covering["instrument"] == "counter", covering["metricId"]
        assert covering["v1Status"] != "deferred", covering["metricId"]


def test_a_runtime_series_is_never_presented_as_an_inferops_metric() -> None:
    metric_names = {row["name"] for row in METRICS}
    for row in RUNTIME_SERIES["series"]:
        assert row["seriesName"] not in metric_names, row["seriesName"]


def test_the_runtime_series_carry_their_classification_and_its_caveat() -> None:
    assert RUNTIME_SERIES["classification"] == "local-real-cpu"
    assert RUNTIME_SERIES["measuredOn"]
    assert RUNTIME_SERIES["caveat"].strip()


# --------------------------------------------------------------------------
# Correlation, logs, and content capture
# --------------------------------------------------------------------------


def test_correlation_is_specified_and_admits_that_nothing_propagates() -> None:
    assert CORRELATION["standard"] == "W3C Trace Context"
    assert CORRELATION["v1Status"] == "specified"
    for field in (
        "assignment",
        "reuseAcrossRetries",
        "asyncRule",
        "placementRule",
        "limitation",
    ):
        assert CORRELATION[field].strip(), field
    assert CORRELATION["headers"], "no propagation header is named"
    for header in CORRELATION["headers"]:
        assert header["name"] and header["purpose"], header


def test_no_correlation_header_is_required_of_a_caller() -> None:
    """An absent trace context starts a trace; it does not refuse a request."""
    for header in CORRELATION["headers"]:
        assert header["required"] is False, header["name"]


@pytest.mark.parametrize("field_id", LOG_RECORD["requiredFields"])
def test_every_required_log_field_is_a_declared_attribute(field_id: str) -> None:
    assert field_id in ATTRIBUTE_BY_ID, field_id
    attribute = ATTRIBUTE_BY_ID[field_id]
    assert "log-field" in attribute["placements"], field_id
    assert attribute["v1Status"] != "deferred", field_id


@pytest.mark.parametrize(
    "row", LOG_RECORD["conditionalFields"], ids=lambda row: row["fieldId"]
)
def test_every_conditional_log_field_is_declared_and_says_when(row: dict) -> None:
    assert row["fieldId"] in ATTRIBUTE_BY_ID, row["fieldId"]
    attribute = ATTRIBUTE_BY_ID[row["fieldId"]]
    assert "log-field" in attribute["placements"], row["fieldId"]
    assert attribute["v1Status"] != "deferred", row["fieldId"]
    assert row["condition"].strip(), row["fieldId"]


def test_a_log_record_carries_a_correlation_identifier_from_the_start() -> None:
    assert "correlation-id" in LOG_RECORD["requiredFields"]
    assert "timestamp" in LOG_RECORD["requiredFields"]
    assert "event" in LOG_RECORD["requiredFields"]


def test_a_log_record_has_no_free_form_message_field() -> None:
    assert LOG_RECORD["messageRule"].strip()
    field_names = {
        ATTRIBUTE_BY_ID[field_id]["name"] for field_id in LOG_RECORD["requiredFields"]
    }
    assert "message" not in field_names
    assert "msg" not in field_names


def test_content_capture_is_disabled_and_has_no_policy_to_enable_it() -> None:
    assert CONTENT_CAPTURE["defaultState"] == "disabled"
    assert CONTENT_CAPTURE["policyStatus"] == "not defined"
    assert len(CONTENT_CAPTURE["requiresBeforeEnabling"]) >= 5
    assert (REPO_ROOT / CONTENT_CAPTURE["policyRef"]).is_file()


# --------------------------------------------------------------------------
# Every rule that claims a test has one
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", PROHIBITIONS, ids=lambda row: row["ruleId"])
def test_a_rule_claims_a_test_only_when_that_test_exists(
    row: dict, module_source: str
) -> None:
    if row["enforcement"] == "review":
        assert row["enforcedBy"] is None, row["ruleId"]
        return
    assert row["enforcedBy"], row["ruleId"]
    assert f"def {row['enforcedBy']}(" in module_source, {
        "rule": row["ruleId"],
        "names a test that does not exist": row["enforcedBy"],
    }


def test_at_least_one_rule_admits_it_is_enforced_by_review_alone() -> None:
    """If every rule claimed a test, the honest ones would have been dropped."""
    assert any(row["enforcement"] == "review" for row in PROHIBITIONS)


# --------------------------------------------------------------------------
# The evidence templates
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", TEMPLATES, ids=lambda row: row["templateId"])
def test_every_template_exists_where_the_catalog_says(row: dict) -> None:
    assert (REPO_ROOT / row["path"]).is_file(), row["path"]


@pytest.mark.parametrize("row", TEMPLATES, ids=lambda row: row["templateId"])
def test_every_template_carries_every_required_section(row: dict) -> None:
    text = (REPO_ROOT / row["path"]).read_text(encoding="utf-8")
    headings = HEADING.findall(text)
    for section in SECTIONS:
        assert headings.count(section["heading"]) == 1, {
            "template": row["templateId"],
            "missing or duplicated heading": section["heading"],
            "found": headings,
        }


@pytest.mark.parametrize("row", TEMPLATES, ids=lambda row: row["templateId"])
def test_every_template_says_it_is_a_template(row: dict) -> None:
    text = (REPO_ROOT / row["path"]).read_text(encoding="utf-8")
    assert "TEMPLATE" in text.splitlines()[0], row["path"]
    assert "is a **template**" in text, row["path"]


@pytest.mark.parametrize("row", TEMPLATES, ids=lambda row: row["templateId"])
def test_a_template_has_produced_nothing_and_says_so(row: dict) -> None:
    assert row["recordsProduced"] == 0, row["templateId"]


def test_no_template_is_cited_as_evidence_for_a_claim() -> None:
    """A format is not a result, and a citable template is a result-shaped hole."""
    strategy = load(STRATEGY_PATH)
    template_paths = {row["path"] for row in TEMPLATES}
    cited = {row.get("evidenceRef") for row in strategy["claims"]} | {
        row.get("evidenceRef") for row in strategy["layers"]
    }
    assert not template_paths & cited, sorted(template_paths & cited)


def test_the_required_sections_cover_what_a_record_needs_to_be_reproducible() -> None:
    required = {row["sectionId"] for row in SECTIONS}
    for section in (
        "classification",
        "provenance",
        "environment",
        "method",
        "results",
        "limitations",
    ):
        assert section in required, section


# --------------------------------------------------------------------------
# This suite is one the strategy knows about
# --------------------------------------------------------------------------


def test_the_strategy_names_the_directory_this_suite_lives_in() -> None:
    strategy = load(STRATEGY_PATH)
    layer = next(row for row in strategy["layers"] if row["layerId"] == DECLARING_LAYER)
    assert DECLARED_PATH in layer["paths"], {
        "layer": DECLARING_LAYER,
        "paths": layer["paths"],
    }


def test_the_catalog_declares_a_limitation_for_every_gap_it_has() -> None:
    """The gaps this catalog knows about are named, not left to be inferred."""
    declared = {row["limitationId"] for row in LIMITATIONS}
    for gap in (
        "nothing-emits",
        "no-collector",
        "no-tracer",
        "no-redacting-sink",
        "no-container-resource-source",
        "no-runtime-request-counter",
        "no-inference-error-vocabulary",
        "budget-is-not-measured",
        "templates-have-produced-nothing",
    ):
        assert gap in declared, gap
    for row in LIMITATIONS:
        assert row["statement"].strip(), row["limitationId"]


# --------------------------------------------------------------------------
# The documents and the data, compared in both directions
# --------------------------------------------------------------------------


def test_the_catalog_document_publishes_every_attribute_and_metric(
    catalog_document: str,
) -> None:
    published = published_ids(catalog_document)
    expected = {row["name"] for row in ATTRIBUTES} | {row["name"] for row in METRICS}
    assert not expected - published, sorted(expected - published)


def test_the_catalog_document_publishes_every_runtime_series(
    catalog_document: str,
) -> None:
    published = published_ids(catalog_document)
    expected = {row["seriesName"] for row in RUNTIME_SERIES["series"]}
    assert not expected - published, sorted(expected - published)


def test_the_redaction_document_publishes_every_forbidden_field_and_rule(
    redaction_document: str,
) -> None:
    published = published_ids(redaction_document)
    expected = {row["fieldId"] for row in FORBIDDEN} | {
        row["ruleId"] for row in PROHIBITIONS
    }
    assert not expected - published, sorted(expected - published)


def test_the_proof_readme_publishes_every_template_and_section(
    proof_readme: str,
) -> None:
    published = published_ids(proof_readme)
    expected = {row["templateId"] for row in TEMPLATES} | {
        row["sectionId"] for row in SECTIONS
    }
    assert not expected - published, sorted(expected - published)


@pytest.mark.parametrize(
    "document_name",
    ["telemetry-catalog.md", "redaction.md"],
)
def test_no_document_publishes_an_identifier_the_data_does_not_have(
    document_name: str,
) -> None:
    text = (TELEMETRY_DIR / document_name).read_text(encoding="utf-8")
    stray = published_ids(text) - ALL_IDENTIFIERS
    assert not stray, {"document": document_name, "not in the data": sorted(stray)}
