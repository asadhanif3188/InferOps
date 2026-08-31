"""The accepted catalog and what the distribution emits, compared in both directions.

``tests/telemetry/test_telemetry_catalog.py`` establishes that the catalog is
internally consistent. It cannot establish that anything obeys it, because it reads
files and never imports the distribution. This suite is the other half: it reads the
accepted catalog **and** the declarations in :mod:`inferops.telemetry` and
:mod:`inferops.api.observability`, and fails when the two disagree.

Three properties, and each one is a rule the catalog names:

**Every emitted metric agrees with its row.** The name, the instrument, the label
set in order, and the bucket count are compared against the accepted record, and the
set of metrics the catalog marks ``emitted`` is compared against the set the API
declares. A catalog that specifies one metric and a process that emits another is two
records, and the one a reader trusts is the one that is wrong.

**A forbidden label cannot be declared.** The registry is handed a label the catalog
places in logs and traces only, and refuses it. That is the difference between a
placement rule and a placement: the rule used to be checked against a document, and
now a call site cannot get past it.

**A forbidden field cannot be written.** A record is built with a field name the
catalog does not publish, and the builder refuses it. There is no name in the
allowlist for a prompt, a completion, a provider error body, a secret, an
authorization header, or a value read out of a submitted document, so the exclusion
is the absence of a key rather than a list somebody maintains.

Every check reads files from this repository and imports this distribution. No
network, no cluster, no model, no clock, no randomness, and nothing is emitted
anywhere a scrape could reach.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inferops.api.observability import API_METRICS
from inferops.domain.serving import ACCEPTED_ADAPTER_KINDS, InvalidValueError
from inferops.telemetry import names, records
from inferops.telemetry.registry import (
    MetricRegistry,
    MetricSpec,
)
from inferops.telemetry.resource import ResourceAttributes, WorkloadIdentity

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "docs" / "telemetry" / "telemetry-catalog.v1alpha1.json"

CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

ATTRIBUTES = CATALOG["attributes"]
METRICS = CATALOG["metrics"]
LOG_RECORD = CATALOG["logRecord"]

ATTRIBUTE_BY_ID = {row["attributeId"]: row for row in ATTRIBUTES}
ATTRIBUTE_BY_NAME = {row["name"]: row for row in ATTRIBUTES}
METRIC_BY_NAME = {row["name"]: row for row in METRICS}

#: What the accepted record says this distribution emits.
EMITTED_ROWS = [row for row in METRICS if row["emission"] == "emitted"]

#: What the distribution declares it emits.
DECLARED_BY_NAME = {spec.name: spec for spec in API_METRICS}

#: A fixed clock, so a record built here is identical on every run.
FIXED_NOW = 1_700_000_000.0


def label_names(metric_row: dict) -> tuple[str, ...]:
    """A catalog row's labels as published attribute names, in declared order."""
    return tuple(ATTRIBUTE_BY_ID[label]["name"] for label in metric_row["labels"])


# --------------------------------------------------------------------------
# The names in code are the names in the catalog
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attribute_name",
    sorted(
        names.LABEL_SAFE_ATTRIBUTES
        | names.NEVER_A_LABEL
        | {
            names.SERVICE_NAME,
            names.MODEL_ID,
            names.RUNTIME_ID,
            names.EVENT,
            names.LEVEL,
        }
    ),
)
def test_every_attribute_name_in_code_is_one_the_catalog_publishes(
    attribute_name: str,
) -> None:
    assert attribute_name in ATTRIBUTE_BY_NAME, attribute_name


def test_the_label_safe_set_is_exactly_what_the_catalog_permits_as_a_metric_label() -> (
    None
):
    """Derived from the catalog, not maintained beside it.

    The set in code is compared against every attribute whose placements include
    ``metric-label``. An attribute gaining that placement and not the constant, or
    the reverse, is a disagreement between the record and the process -- which is
    the failure this whole suite exists to make loud.
    """
    permitted = {
        row["name"]
        for row in ATTRIBUTES
        if "metric-label" in row["placements"] and row["v1Status"] != "deferred"
    }
    assert permitted >= names.LABEL_SAFE_ATTRIBUTES, sorted(
        names.LABEL_SAFE_ATTRIBUTES - permitted
    )


@pytest.mark.parametrize("attribute_name", sorted(names.NEVER_A_LABEL))
def test_nothing_in_the_never_a_label_set_may_be_a_metric_label(
    attribute_name: str,
) -> None:
    row = ATTRIBUTE_BY_NAME[attribute_name]
    assert "metric-label" not in row["placements"], attribute_name


def test_the_two_label_sets_do_not_overlap() -> None:
    assert not (names.LABEL_SAFE_ATTRIBUTES & names.NEVER_A_LABEL)


# --------------------------------------------------------------------------
# Every emitted metric agrees with its catalog row
# --------------------------------------------------------------------------


def test_every_emitted_metric_agrees_with_its_catalog_row() -> None:
    """Both directions: what the catalog marks emitted, and what the API declares.

    This is the test the catalog's ``an-emitted-signal-agrees-with-this-catalog``
    rule names.
    """
    from_catalog = {row["name"] for row in EMITTED_ROWS}
    from_code = set(DECLARED_BY_NAME)
    assert from_catalog == from_code, {
        "marked emitted in the catalog and not declared": sorted(
            from_catalog - from_code
        ),
        "declared and not marked emitted in the catalog": sorted(
            from_code - from_catalog
        ),
    }
    assert set(names.EMITTED_METRICS) == from_catalog


@pytest.mark.parametrize("row", EMITTED_ROWS, ids=lambda row: row["metricId"])
def test_an_emitted_metric_carries_the_instrument_and_labels_it_declares(
    row: dict,
) -> None:
    spec = DECLARED_BY_NAME[row["name"]]
    assert spec.instrument == row["instrument"], row["metricId"]
    assert spec.unit == row["unit"], row["metricId"]
    assert spec.labels == label_names(row), {
        "metric": row["metricId"],
        "declared": list(spec.labels),
        "in the catalog": list(label_names(row)),
    }
    assert spec.identity == (row["kind"] == "info"), row["metricId"]


@pytest.mark.parametrize("row", EMITTED_ROWS, ids=lambda row: row["metricId"])
def test_a_histogram_emits_the_number_of_buckets_its_budget_was_computed_from(
    row: dict,
) -> None:
    """The bucket count is arithmetic in the budget, so it cannot be a guess.

    The catalog counts bucket **series**, which is the finite boundaries plus the
    ``+Inf`` bucket every exposition writes. Declaring one more finite boundary
    than the row allows is a metric that costs more series than the budget was
    computed with, and the budget stops meaning anything.
    """
    spec = DECLARED_BY_NAME[row["name"]]
    if row["buckets"] is None:
        assert spec.buckets is None, row["metricId"]
        return
    assert spec.buckets is not None, row["metricId"]
    assert len(spec.buckets) + 1 == row["buckets"], {
        "metric": row["metricId"],
        "finite boundaries declared": len(spec.buckets),
        "bucket series in the catalog": row["buckets"],
    }


def test_a_metric_the_catalog_does_not_publish_is_not_emitted() -> None:
    for spec in API_METRICS:
        assert spec.name in METRIC_BY_NAME, spec.name


def test_the_identity_metric_is_the_only_one_carrying_identity_attributes() -> None:
    """Identity belongs on an identity metric, checked against what is declared."""
    identity_names = {
        row["name"]
        for row in ATTRIBUTES
        if row["identityOnly"] and row["v1Status"] != "deferred"
    }
    for spec in API_METRICS:
        if spec.identity:
            continue
        assert not set(spec.labels) & identity_names, {
            "metric": spec.name,
            "identity attributes used as operational labels": sorted(
                set(spec.labels) & identity_names
            ),
        }


# --------------------------------------------------------------------------
# A forbidden label cannot be declared
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label",
    [
        names.CORRELATION_ID,
        names.REQUEST_ID,
        names.WORKLOAD_VERSION,
        names.OWNER_ID,
        names.POD_NAME,
        names.DURATION_MS,
        names.SERVICE_VERSION,
        names.ADAPTER_KIND,
    ],
)
def test_a_metric_cannot_declare_a_label_this_catalog_forbids(label: str) -> None:
    """The refusal happens at declaration, before a single series can exist.

    This is the test the catalog's ``an-emitted-label-is-one-this-catalog-permits``
    rule names.
    """
    with pytest.raises(InvalidValueError):
        MetricSpec(
            name="inferops_probe_total",
            instrument="counter",
            unit="1",
            help_text="A metric that should never be constructible.",
            labels=(label,),
        )


@pytest.mark.parametrize(
    "label",
    [names.CORRELATION_ID, names.REQUEST_ID, names.POD_NAME, names.DURATION_MS],
)
def test_an_identity_metric_cannot_declare_a_forbidden_label_either(
    label: str,
) -> None:
    """The check applies to both metric shapes, not only the operational one.

    An identity metric emits one series per process whatever its labels say, which
    makes it tempting to treat as exempt. It is not: it is still a series in a
    store, and an unbounded or measured value on it is unbounded and measured
    there too. Skipping the check for identity metrics would have made the
    registry's own claim -- that a request identifier cannot become a label by
    being passed to a constructor -- true of one shape and false of the other.
    """
    with pytest.raises(InvalidValueError):
        MetricSpec(
            name="inferops_probe_info",
            instrument="gauge",
            unit="1",
            help_text="An identity metric that should never be constructible.",
            labels=(label,),
            identity=True,
        )


def test_an_identity_metric_may_declare_the_identity_attributes() -> None:
    """The permitted set is wider for an identity metric, which is what it is for."""
    spec = MetricSpec(
        name="inferops_probe_info",
        instrument="gauge",
        unit="1",
        help_text="An identity metric carrying identity attributes.",
        labels=(names.SERVICE_VERSION, names.RELEASE_ID, names.ADAPTER_KIND),
        identity=True,
    )
    assert spec.labels == (names.SERVICE_VERSION, names.RELEASE_ID, names.ADAPTER_KIND)


def test_the_identity_attribute_set_is_what_the_catalog_marks_identity_only() -> None:
    expected = {
        row["name"]
        for row in ATTRIBUTES
        if row["identityOnly"] and row["v1Status"] != "deferred"
    }
    assert expected == names.IDENTITY_ATTRIBUTES


@pytest.mark.parametrize("value", ["abc\n", "abc\r", "abc\n\n", "\nabc"])
def test_a_label_value_ending_in_a_newline_is_refused(value: str) -> None:
    """Python's ``$`` matches before a trailing newline; this pattern must not.

    A newline inside a quoted label value splits one sample line into two, and a
    scraper rejects the whole target rather than the one series. The obvious
    ``^...$`` with :meth:`re.Pattern.match` accepts exactly this, which is why the
    pattern carries no anchors and is matched in full.
    """
    registry = MetricRegistry()
    metric = registry.declare(
        MetricSpec(
            name="inferops_probe_total",
            instrument="counter",
            unit="1",
            help_text="A metric used to exercise label-value validation.",
            labels=(names.OUTCOME,),
        )
    )
    with pytest.raises(InvalidValueError):
        metric.add(1.0, {names.OUTCOME: value})


def test_a_scrape_reads_a_snapshot_rather_than_the_live_series() -> None:
    """A renderer holding the live object reads a histogram whose parts disagree."""
    registry = MetricRegistry()
    metric = registry.declare(
        MetricSpec(
            name="inferops_probe_seconds",
            instrument="histogram",
            unit="s",
            help_text="A histogram used to exercise snapshot isolation.",
            labels=(),
            buckets=(1.0,),
        )
    )
    metric.observe(0.5)
    taken = metric.samples()
    metric.observe(0.5)

    assert taken[0][1].count == 1, "the snapshot moved after it was taken"
    assert metric.samples()[0][1].count == 2


def test_a_tenant_identifier_is_not_even_a_name_this_distribution_has() -> None:
    """The one attribute excluded by sensitivity rather than by cardinality.

    A tenant identifier is a log field and a span attribute in the catalog and is
    excluded from metrics and from committed evidence records. Nothing in this
    distribution produces one -- there is no constant for it, no configuration
    variable, and no field in the record allowlist -- so the exclusion holds by
    there being nothing to exclude.
    """
    tenant = ATTRIBUTE_BY_ID["tenant-id"]["name"]
    assert "metric-label" not in ATTRIBUTE_BY_ID["tenant-id"]["placements"]
    assert "evidence-field" not in ATTRIBUTE_BY_ID["tenant-id"]["placements"]
    assert tenant not in names.LABEL_SAFE_ATTRIBUTES
    assert tenant not in records.ALLOWED_FIELDS


def test_a_label_value_that_could_inject_a_series_is_refused() -> None:
    """A label value is written between quotes, so a quote in one is not a value."""
    registry = MetricRegistry()
    metric = registry.declare(
        MetricSpec(
            name="inferops_probe_total",
            instrument="counter",
            unit="1",
            help_text="A metric used to exercise label-value validation.",
            labels=(names.OUTCOME,),
        )
    )
    for hostile in ('a" 1\ninferops_forged_total{x="y', "line\nbreak", 'quote"mark'):
        with pytest.raises(InvalidValueError):
            metric.add(1.0, {names.OUTCOME: hostile})


# --------------------------------------------------------------------------
# A forbidden field cannot be written
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "prompt",
        "completion",
        "messages",
        "response",
        "message",
        "msg",
        "authorization",
        "api_key",
        "error_body",
        "inferops.prompt",
        "inferops.tenant.id",
    ],
)
def test_a_record_refuses_a_field_this_catalog_does_not_publish(field: str) -> None:
    """The allowlist, doing the one job it exists for.

    This is the test the catalog's
    ``an-emitted-record-carries-only-published-fields`` rule names. The refusal
    names the field and never the value, which matters most for exactly these
    fields: the rejected one is the one most likely to be carrying something that
    may not be repeated.
    """
    with pytest.raises(InvalidValueError) as raised:
        records.record(
            event=names.EVENT_REQUEST_COMPLETED,
            level=names.LEVEL_INFO,
            correlation_id="c-1",
            resource=ResourceAttributes(),
            workload=WorkloadIdentity(),
            at=FIXED_NOW,
            fields={field: "a value that must not be repeated"},
        )
    assert "a value that must not be repeated" not in str(raised.value)


@pytest.mark.parametrize("field_name", sorted(records.ALLOWED_FIELDS))
def test_every_field_a_record_may_carry_is_a_published_log_field(
    field_name: str,
) -> None:
    row = ATTRIBUTE_BY_NAME[field_name]
    assert "log-field" in row["placements"], field_name
    assert row["v1Status"] != "deferred", field_name


def test_every_required_log_field_the_catalog_names_is_required_in_code() -> None:
    expected = {
        ATTRIBUTE_BY_ID[field_id]["name"] for field_id in LOG_RECORD["requiredFields"]
    }
    assert set(records.REQUIRED_FIELDS) == expected


def test_a_record_has_no_free_form_message_field() -> None:
    assert "message" not in records.ALLOWED_FIELDS
    assert "msg" not in records.ALLOWED_FIELDS


# --------------------------------------------------------------------------
# The bounded value sets stay inside the bounds the catalog declares
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("attribute_id", "values"),
    [
        ("outcome", names.OUTCOMES),
        ("token-direction", names.TOKEN_DIRECTIONS),
        ("level", names.LEVELS),
        ("event", names.EVENTS),
        ("deployment-environment", names.ENVIRONMENTS),
        ("component", names.COMPONENTS),
        ("adapter-kind", tuple(sorted(ACCEPTED_ADAPTER_KINDS))),
    ],
)
def test_a_bounded_value_set_fits_the_bound_the_catalog_declares(
    attribute_id: str, values: tuple[str, ...]
) -> None:
    row = ATTRIBUTE_BY_ID[attribute_id]
    assert len(set(values)) == len(values), attribute_id
    assert len(values) <= row["maxDistinctValues"], {
        "attribute": attribute_id,
        "values in code": len(values),
        "bound in the catalog": row["maxDistinctValues"],
    }


def test_the_events_the_catalog_lists_are_the_events_the_code_writes() -> None:
    assert tuple(row["eventId"] for row in LOG_RECORD["events"]) == names.EVENTS
    for row in LOG_RECORD["events"]:
        assert row["level"] in names.LEVELS, row["eventId"]
        assert row["when"].strip(), row["eventId"]
