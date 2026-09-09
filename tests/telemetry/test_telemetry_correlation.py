"""The correlation query record, the queries in it, and what they return.

Five files have to agree, and the point of the suite is that no two of them may
drift:

- `docs/telemetry/telemetry-correlation-queries.v1alpha1.json`, the record;
- `docs/telemetry/telemetry-correlation-queries.md`, the document that publishes it;
- `docs/telemetry/telemetry-catalog.v1alpha1.json`, which decides which label may key
  a series and is never restated here, only derived from;
- `docs/telemetry/kubernetes-telemetry-collection.v1alpha1.json` and the committed
  chart renders, which decide what a collector would attach and what recording rules
  it would evaluate;
- `docs/proof/telemetry/v1-s3-007-pr2-query-evaluation.md`, the record of what every
  query returned over every scenario, regenerated here and compared.

The property this defends is one the previous layer could not reach. The scrape
configuration can attach every right label and a query can still answer nothing: it
groups by a label the collector drops, joins on a key one side does not carry, or
reads a metric nothing emits -- and all three look, in a console, exactly like a
healthy quiet system. So the queries are checked statically against the catalog and
the collection record, and then *run*, against synthetic stores whose series carry
the label sets the render would produce.

**None of this establishes that anything is collected or that any query has been
answered.** No collector, store, dashboard, or alerting path is selected, nothing
scrapes either InferOps endpoint, this chart has never been installed, and no
Prometheus has parsed, loaded, or evaluated a single expression here. Every check
reads a file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tools.telemetry_correlation import (
    AGGREGATIONS,
    FUNCTIONS,
    IDENTIFIER,
    LOOKBACK_SECONDS,
    MAX_NESTING_DEPTH,
    MAX_PATTERN_WILDCARDS,
    RULE_IDS,
    SAFE_MESSAGE_CHARACTERS,
    EvaluationError,
    PromQLError,
    Series,
    Store,
    apply_metric_relabel,
    check_query,
    check_record,
    collector_dropped_labels,
    declared_metric_names,
    evaluate,
    evaluate_scenario,
    forbidden_metric_labels,
    format_vector,
    labels_read,
    load_fixture,
    metrics_read,
    not_emitted_metric_names,
    parse,
    permitted_query_labels,
    recorded_series_names,
    rendered_recording_rules,
    with_recording_rules,
)
from tools.telemetry_correlation.__main__ import _evidence
from tools.telemetry_correlation.core import _base_name
from tools.telemetry_correlation.promql import Binary

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]

RECORD_PATH = REPO_ROOT / "docs/telemetry/telemetry-correlation-queries.v1alpha1.json"
DOCUMENT_PATH = REPO_ROOT / "docs/telemetry/telemetry-correlation-queries.md"
CATALOG_PATH = REPO_ROOT / "docs/telemetry/telemetry-catalog.v1alpha1.json"
COLLECTION_PATH = (
    REPO_ROOT / "docs/telemetry/kubernetes-telemetry-collection.v1alpha1.json"
)
EVIDENCE_PATH = REPO_ROOT / "docs/proof/telemetry/v1-s3-007-pr2-query-evaluation.md"
FIXTURE_DIR = REPO_ROOT / "tests/telemetry/fixtures/correlation"

RECORD: dict[str, Any] = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
DOCUMENT = DOCUMENT_PATH.read_text(encoding="utf-8")
CATALOG: dict[str, Any] = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
COLLECTION: dict[str, Any] = json.loads(COLLECTION_PATH.read_text(encoding="utf-8"))

QUERIES: list[dict[str, Any]] = RECORD["queries"]
REFUSED: list[dict[str, Any]] = RECORD["refusedQueries"]
SCENARIOS: list[dict[str, Any]] = RECORD["scenarios"]

QUERY_IDS = [query["queryId"] for query in QUERIES]
SCENARIO_IDS = [scenario["scenarioId"] for scenario in SCENARIOS]

#: The release name and namespace the committed renders are produced with, and which
#: the fixtures therefore have to use: the recording rules name their own release's
#: jobs, so a fixture spelling a job differently would have no rule read it.
RELEASE_FULLNAME = "inferops-inferops-llm"
RELEASE_NAMESPACE = "inferops-platform"

METRIC_BY_NAME = {metric["name"]: metric for metric in CATALOG["metrics"]}


def scenario_results(scenario_id: str) -> dict[str, list[str]]:
    """Every query's result over one committed scenario."""
    fixture = load_fixture(FIXTURE_DIR / f"{scenario_id}.yaml")
    return evaluate_scenario(fixture, QUERIES)


def one_row(rows: list[str]) -> str:
    assert len(rows) == 1, rows
    return rows[0]


# --------------------------------------------------------------------------
# The files exist and refer to each other
# --------------------------------------------------------------------------


def test_the_record_the_document_the_fixtures_and_the_evidence_were_found() -> None:
    assert RECORD_PATH.is_file()
    assert DOCUMENT_PATH.is_file()
    assert EVIDENCE_PATH.is_file()
    assert sorted(path.stem for path in FIXTURE_DIR.glob("*.yaml")) == sorted(
        SCENARIO_IDS
    )


def test_every_reference_the_record_makes_resolves() -> None:
    """A record whose references have rotted is a record nobody can check."""
    for key, value in RECORD.items():
        if key.endswith("Ref") and isinstance(value, str):
            assert (REPO_ROOT / value).exists(), f"{key} names a path that is not there"
    assert (REPO_ROOT / RECORD["fixtureDir"]).is_dir()
    for scenario in SCENARIOS:
        assert (REPO_ROOT / scenario["fixtureRef"]).is_file()


def test_the_record_states_that_nothing_has_been_collected_or_evaluated() -> None:
    """The one claim this whole PR must not be read as making."""
    status = RECORD["verificationStatus"]
    assert status["collected"] is False
    assert status["everInstalled"] is False
    assert "not selected" in status["collector"]
    assert "No Prometheus has parsed, loaded, or evaluated" in status["engine"]
    assert status["evidenceClass"] == "local-static"
    assert "no Prometheus has parsed, loaded, or evaluated any expression" in DOCUMENT


# --------------------------------------------------------------------------
# The document and the record publish the same things
# --------------------------------------------------------------------------


@pytest.mark.parametrize("query_id", QUERY_IDS)
def test_the_document_names_every_query(query_id: str) -> None:
    assert f"`{query_id}`" in DOCUMENT


@pytest.mark.parametrize("refused", [row["refusedId"] for row in REFUSED])
def test_the_document_names_every_refused_query(refused: str) -> None:
    assert f"`{refused}`" in DOCUMENT


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_the_document_names_every_scenario(scenario_id: str) -> None:
    assert f"`{scenario_id}`" in DOCUMENT


@pytest.mark.parametrize("rule", RULE_IDS)
def test_the_document_names_every_rule_the_checker_can_produce(rule: str) -> None:
    assert f"`{rule}`" in DOCUMENT


def test_the_document_names_every_gap_and_every_limitation() -> None:
    for gap in RECORD["gaps"]:
        assert f"`{gap['gapId']}`" in DOCUMENT
        assert gap["statement"].endswith(".")
        assert gap["wouldRequire"]
    for limitation in RECORD["limitations"]:
        assert f"`{limitation['limitationId']}`" in DOCUMENT
        assert limitation["statement"].endswith(".")


def test_the_document_and_the_record_declare_the_same_promql_subset() -> None:
    """A subset the document widened silently would be a subset nobody checked."""
    assert set(RECORD["subset"]["aggregations"]) == set(AGGREGATIONS)
    assert set(RECORD["subset"]["functions"]) == set(FUNCTIONS)
    for name in sorted(AGGREGATIONS | set(FUNCTIONS)):
        assert f"`{name}`" in DOCUMENT, name


def test_every_query_declares_a_question_a_class_and_what_empty_means() -> None:
    """The three fields that make a published query usable rather than decorative."""
    classes = {row["classId"] for row in RECORD["answerabilityClasses"]}
    for query in QUERIES:
        assert query["question"].endswith("?"), query["queryId"]
        assert query["answerability"] in classes, query["queryId"]
        assert query["emptyMeans"], query["queryId"]
        assert query["profiles"], query["queryId"]
        if query["expr"] is None:
            assert query["answerability"] == "no-source", query["queryId"]
            assert query["wouldRequire"], query["queryId"]


def test_every_query_identifier_is_unique() -> None:
    assert len(QUERY_IDS) == len(set(QUERY_IDS))
    refused_ids = [row["refusedId"] for row in REFUSED]
    assert len(refused_ids) == len(set(refused_ids))
    assert not set(QUERY_IDS) & set(refused_ids)


# --------------------------------------------------------------------------
# The vocabulary is derived from the catalog, not copied from it
# --------------------------------------------------------------------------


def test_the_permitted_labels_are_exactly_what_the_two_records_derive() -> None:
    """Three sources and no fourth, recomputed on every run."""
    expected = {
        attribute["name"].replace(".", "_")
        for attribute in CATALOG["attributes"]
        if "metric-label" in attribute["placements"]
        or "info-label" in attribute["placements"]
    }
    expected.update(row["labelName"] for row in COLLECTION["targetLabels"])
    expected.add("le")
    assert permitted_query_labels() == expected


def test_the_barred_labels_are_the_ones_the_collector_drops() -> None:
    """The query vocabulary and the chart's drop list derive from one decision.

    If these ever disagreed, a query could ask for a label the collector removes --
    which is the failure that produces an empty panel and no explanation.
    """
    assert forbidden_metric_labels() == collector_dropped_labels("real")
    assert forbidden_metric_labels() == collector_dropped_labels("mock")


def test_no_permitted_label_is_also_a_barred_one() -> None:
    assert not permitted_query_labels() & forbidden_metric_labels()


@pytest.mark.parametrize("query", QUERIES, ids=QUERY_IDS)
def test_every_label_a_query_names_is_one_something_carries(
    query: dict[str, Any],
) -> None:
    if query["expr"] is None:
        return
    named = labels_read(parse(query["expr"]))
    assert not named - permitted_query_labels(), query["queryId"]


@pytest.mark.parametrize("query", QUERIES, ids=QUERY_IDS)
def test_no_published_query_names_a_release_scoped_job(query: dict[str, Any]) -> None:
    """A query naming a job is a query that works in exactly one installation."""
    if query["expr"] is None:
        return
    assert RELEASE_FULLNAME not in query["expr"], query["queryId"]
    assert "job=" not in query["expr"].replace(" ", ""), query["queryId"]


@pytest.mark.parametrize("query", QUERIES, ids=QUERY_IDS)
def test_every_series_a_query_reads_is_one_this_release_produces(
    query: dict[str, Any],
) -> None:
    if query["expr"] is None:
        return
    for profile in query["profiles"]:
        known = (
            {name for name in declared_metric_names()}
            | {
                f"{name}{suffix}"
                for name in declared_metric_names()
                for suffix in ("_bucket", "_count", "_sum")
            }
            | set(recorded_series_names(profile))
            | {"up", "scrape_duration_seconds"}
            | {
                entry["seriesName"]
                for entry in CATALOG["runtimeNativeSeries"]["series"]
            }
        )
        assert not metrics_read(parse(query["expr"])) - known, (
            query["queryId"],
            profile,
        )


def test_every_emitted_catalog_metric_is_read_by_a_published_query() -> None:
    """A signal that is emitted and that nobody published a question for.

    The catalog's whole argument is that a metric exists to answer a question. A
    metric the API emits and no query reads is either a metric nobody needed or a
    question nobody wrote down, and both are worth failing over.
    """
    read: set[str] = set()
    for query in QUERIES:
        if query["expr"] is not None:
            read.update(
                name.removesuffix("_bucket").removesuffix("_count").removesuffix("_sum")
                for name in metrics_read(parse(query["expr"]))
            )
    emitted = declared_metric_names() - not_emitted_metric_names()
    assert not emitted - read, sorted(emitted - read)


def test_every_metric_with_no_query_says_why_it_has_none() -> None:
    """The honest half: which questions this catalogue deliberately does not ask."""
    read: set[str] = set()
    for query in QUERIES:
        if query["expr"] is not None:
            read.update(
                name.removesuffix("_bucket").removesuffix("_count").removesuffix("_sum")
                for name in metrics_read(parse(query["expr"]))
            )
    unread = declared_metric_names() - read
    accounted = {row["metric"] for row in RECORD["notPublishedAsQueries"]}
    assert unread == accounted, {
        "unread": sorted(unread),
        "accounted": sorted(accounted),
    }
    for row in RECORD["notPublishedAsQueries"]:
        assert row["metric"] in METRIC_BY_NAME
        assert METRIC_BY_NAME[row["metric"]]["emission"] == "not-emitted"
        assert row["metric"] in DOCUMENT


# --------------------------------------------------------------------------
# The policy: the record passes, and each rule refuses what it is named for
# --------------------------------------------------------------------------


def test_the_committed_record_satisfies_the_query_policy() -> None:
    assert check_record() == []


@pytest.mark.parametrize("refused", REFUSED, ids=[r["refusedId"] for r in REFUSED])
def test_each_refused_query_trips_exactly_the_rule_it_declares(
    refused: dict[str, Any],
) -> None:
    findings = check_query(
        {
            "queryId": refused["refusedId"],
            "expr": refused["expr"],
            "answerability": refused.get("answerability"),
            "profiles": ["real"],
        }
    )
    assert {finding.rule for finding in findings} == {refused["refusedByRule"]}, [
        finding.rule for finding in findings
    ]
    assert refused["why"].endswith(".")


def test_every_rule_the_checker_can_produce_is_exercised_by_a_refused_query() -> None:
    """A rule with no case that trips it is a rule nobody has seen fire."""
    assert {row["refusedByRule"] for row in REFUSED} == set(RULE_IDS)


HOSTILE_EXPRESSIONS = (
    'inferops_inference_requests_total{inferops_tenant_id="\\u001b[31mred"}',
    'sum by (inferops_request_id) (inferops_inference_requests_total{x="a\\rb"})',
    'sum by (inferops_owner_id) (my_metric{y="\\u202eevil"})',
    'inferops_inference_requests_total{inferops_correlation_id="a\\nSEVERITY=ok"}',
)


@pytest.mark.parametrize("hostile", HOSTILE_EXPRESSIONS)
def test_no_finding_message_can_carry_a_value_out_of_a_record(hostile: str) -> None:
    """A checker that echoed what it refused would be the one place it got published.

    The same property `tools.telemetry_collection` holds, for the same reason: a
    finding is written into logs and terminals, so an unconstrained echo is how an
    escape sequence reaches a terminal and a forged line reaches a log.
    """
    findings = check_query(
        {"queryId": "hostile", "expr": hostile, "profiles": ["real"]}
    )
    assert findings, hostile
    for finding in findings:
        for character in finding.message + finding.field + finding.subject:
            assert character in SAFE_MESSAGE_CHARACTERS, (finding.rule, character)


def test_a_query_with_no_expression_produces_no_finding() -> None:
    """A question with no series to select is not a query that failed a rule."""
    for query in QUERIES:
        if query["expr"] is None:
            assert check_query(query) == []


# --------------------------------------------------------------------------
# The PromQL subset: what it reads, and what it refuses to read
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expression",
    [
        "up",
        'up{job="a"}',
        "sum(up)",
        "sum by (job) (up)",
        "sum(up) by (job)",
        "count without (instance) (up)",
        "rate(inferops_inference_requests_total[5m])",
        "increase(inferops_inference_requests_total[1h])",
        "absent(up)",
        'label_replace(up, "a", "b", "", "")',
        "histogram_quantile(0.5, up)",
        "up or up",
        "up and on (job) up",
        "up unless up",
        "up * on (job) group_left (a) up",
        "up / on (job) group_right (a) up",
        "up / ignoring (instance) up",
        "-up",
        "(up + up) * 2",
        "up > bool 1",
    ],
)
def test_the_subset_reads_the_forms_the_queries_are_written_in(
    expression: str,
) -> None:
    assert parse(expression) is not None


@pytest.mark.parametrize(
    "expression",
    [
        "topk(5, up)",
        "count_values('x', up)",
        "max_over_time(up[1h:5m])",
        "up @ 1234",
        "up offset 5m",
        "sum(up, up)",
        "not_a_function(up)",
        "up * group_left up",
        "up * ignoring (job) group_left up",
        "up / ignoring (instance) group_right up",
        "up[1.5m]",
        "{}",
        "up{",
        "up}",
        "",
        "by (job)",
        "sum by (0bad) (up)",
    ],
)
def test_the_subset_refuses_everything_else(expression: str) -> None:
    with pytest.raises(PromQLError):
        parse(expression)


def test_what_a_query_reads_is_derived_from_the_expression_and_not_declared() -> None:
    """The reason there is a parser here rather than a list beside each query."""
    tree = parse(
        'sum by (a) (rate(m_total[5m])) * on (a, b) group_left (c) other{d="1"}'
    )
    assert metrics_read(tree) == {"m_total", "other"}
    assert labels_read(tree) == {"a", "b", "c", "d"}


def test_label_replace_destination_and_source_are_read_as_labels() -> None:
    tree = parse('label_replace(m, "dest", "v", "src", ".*")')
    assert labels_read(tree) == {"dest", "src"}


# --------------------------------------------------------------------------
# The evaluator, on its own terms
# --------------------------------------------------------------------------


def _store(*series: tuple[str, dict[str, str], list[tuple[float, float]]]) -> Store:
    return Store(
        tuple(
            Series(tuple(sorted({**labels, "__name__": name}.items())), tuple(points))
            for name, labels, points in series
        ),
        600.0,
    )


def test_rate_is_a_plain_delta_over_the_observed_interval() -> None:
    """Declared, and different from Prometheus, so it is proved rather than assumed."""
    store = _store(("m", {"a": "1"}, [(300.0, 100.0), (600.0, 400.0)]))
    assert format_vector(evaluate(store, parse("rate(m[5m])"))) == ['{a="1"} 1']


def test_rate_adds_a_counter_reset_back() -> None:
    """100, then 10, then 110: the reset contributes its own value, not a negative.

    The counted delta is 10 + 100 = 110 over 300 seconds. Without the correction the
    plain difference would be 10, and a restarted process would read as an idle one.
    """
    store = _store(("m", {"a": "1"}, [(300.0, 100.0), (450.0, 10.0), (600.0, 110.0)]))
    assert format_vector(evaluate(store, parse("rate(m[5m])"))) == ['{a="1"} 0.366667']


def test_a_single_sample_produces_no_rate() -> None:
    store = _store(("m", {"a": "1"}, [(600.0, 100.0)]))
    assert evaluate(store, parse("rate(m[5m])")) == []


def test_absent_reproduces_the_equality_matchers_and_nothing_else() -> None:
    store = _store(("other", {}, [(600.0, 1.0)]))
    rows = format_vector(evaluate(store, parse('absent(m{a="1", b=~"x|y"})')))
    assert rows == ['{a="1"} 1']


def test_absent_over_something_present_is_empty() -> None:
    store = _store(("m", {"a": "1"}, [(600.0, 1.0)]))
    assert evaluate(store, parse('absent(m{a="1"})')) == []


def test_histogram_quantile_interpolates_inside_the_chosen_bucket() -> None:
    store = _store(
        ("h_bucket", {"le": "1"}, [(600.0, 0.0)]),
        ("h_bucket", {"le": "2"}, [(600.0, 5.0)]),
        ("h_bucket", {"le": "+Inf"}, [(600.0, 10.0)]),
    )
    rows = format_vector(evaluate(store, parse("histogram_quantile(0.5, h_bucket)")))
    assert rows == ["{} 2"]


def test_histogram_quantile_without_an_infinity_bucket_is_not_a_number() -> None:
    store = _store(
        ("h_bucket", {"le": "1"}, [(600.0, 1.0)]),
        ("h_bucket", {"le": "2"}, [(600.0, 5.0)]),
    )
    rows = format_vector(evaluate(store, parse("histogram_quantile(0.5, h_bucket)")))
    assert rows == ["{} NaN"]


def test_a_group_left_join_copies_only_the_labels_it_names() -> None:
    store = _store(
        ("left", {"job": "j", "instance": "i", "extra": "e"}, [(600.0, 2.0)]),
        (
            "right",
            {"job": "j", "instance": "i", "v": "1", "unwanted": "u"},
            [(600.0, 1.0)],
        ),
    )
    rows = format_vector(
        evaluate(store, parse("left * on (job, instance) group_left (v) right"))
    )
    assert rows == ['{extra="e", instance="i", job="j", v="1"} 2']


def test_a_join_whose_key_one_side_lacks_returns_nothing() -> None:
    """The empty panel this whole record exists to make impossible to write by accident."""
    store = _store(
        ("left", {"w": "a"}, [(600.0, 2.0)]),
        ("right", {"job": "j"}, [(600.0, 1.0)]),
    )
    assert evaluate(store, parse("left * on (w) group_left right")) == []


def test_a_many_to_many_match_is_refused_rather_than_guessed_at() -> None:
    store = _store(
        ("left", {"k": "1", "x": "a"}, [(600.0, 1.0)]),
        ("right", {"k": "1", "y": "b"}, [(600.0, 1.0)]),
        ("right", {"k": "1", "y": "c"}, [(600.0, 1.0)]),
    )
    with pytest.raises(EvaluationError):
        evaluate(store, parse("left * on (k) group_left right"))


def test_a_store_holding_one_label_set_twice_is_refused() -> None:
    store = Store(
        (
            Series((("__name__", "m"), ("a", "1")), ((600.0, 1.0),)),
            Series((("__name__", "m"), ("a", "1")), ((600.0, 2.0),)),
        ),
        600.0,
    )
    with pytest.raises(EvaluationError):
        evaluate(store, parse("m"))


def test_a_sample_older_than_the_lookback_is_not_selected() -> None:
    store = _store(("m", {"a": "1"}, [(200.0, 5.0)]))
    assert evaluate(store, parse("m")) == []


def test_sum_reads_zero_where_a_filtered_count_would_read_nothing() -> None:
    """The exact reason the chart's rule sums `up` rather than counting `up == 1`."""
    store = _store(
        ("up", {"job": "j", "instance": "a"}, [(600.0, 0.0)]),
        ("up", {"job": "j", "instance": "b"}, [(600.0, 0.0)]),
    )
    assert format_vector(evaluate(store, parse("sum by (job) (up)"))) == ['{job="j"} 0']
    assert evaluate(store, parse("count by (job) (up == 1)")) == []


# --------------------------------------------------------------------------
# The collector steps a fixture goes through
# --------------------------------------------------------------------------


def test_the_rendered_labeldrop_removes_every_barred_label() -> None:
    barred = sorted(collector_dropped_labels("real"))
    store = _store(
        ("m", {name: "x" for name in barred} | {"keep": "1"}, [(600.0, 1.0)]),
    )
    dropped = apply_metric_relabel(store, collector_dropped_labels("real"))
    assert dict(dropped.series[0].labels) == {"__name__": "m", "keep": "1"}


def test_a_labeldrop_that_would_collide_two_series_is_refused() -> None:
    store = _store(
        ("m", {"inferops_request_id": "a"}, [(600.0, 1.0)]),
        ("m", {"inferops_request_id": "b"}, [(600.0, 2.0)]),
    )
    with pytest.raises(ValueError):
        apply_metric_relabel(store, {"inferops_request_id"})


@pytest.mark.parametrize("profile", ["mock", "real"])
def test_every_recorded_series_a_query_reads_is_one_the_chart_renders(
    profile: str,
) -> None:
    rendered = recorded_series_names(profile)
    for query in QUERIES:
        if query["expr"] is None or profile not in query["profiles"]:
            continue
        for name in metrics_read(parse(query["expr"])):
            if name.startswith("inferops:"):
                assert name in rendered, (query["queryId"], profile, name)


def test_the_recording_rules_this_suite_evaluates_are_the_rendered_ones() -> None:
    """Read from the render, never restated, so an edit there reaches here."""
    real = {
        record
        for _, record in ((g, r["record"]) for g, r in rendered_recording_rules("real"))
    }
    mock = {
        record
        for _, record in ((g, r["record"]) for g, r in rendered_recording_rules("mock"))
    }
    assert "inferops:scrape_job_absent:serving_runtime" in real
    assert "inferops:scrape_job_absent:serving_runtime" not in mock
    assert mock < real


# --------------------------------------------------------------------------
# The scenarios: what each query actually returned
# --------------------------------------------------------------------------


def test_the_healthy_scenario_answers_every_answerable_query() -> None:
    """A query declared answerable that answers nothing on a healthy store is a defect."""
    results = scenario_results("healthy-real-two-replicas")
    for query in QUERIES:
        if query["answerability"] != "answerable-once-collected":
            continue
        if query["queryId"] not in results:
            continue
        if query["queryId"] in {
            # Three answerable queries are empty on a healthy store on purpose: each
            # reports an absence, and there is none.
            "platform-api-scrape-job-absent",
            "serving-runtime-scrape-job-absent",
            "identity-absent-on-a-target-that-answered",
        }:
            assert results[query["queryId"]] == [], query["queryId"]
            continue
        assert results[query["queryId"]], query["queryId"]


def test_the_healthy_scenario_correlates_throughput_with_the_build_identity() -> None:
    """The correlation the whole story turns on, read off a store rather than argued."""
    rows = scenario_results("healthy-real-two-replicas")[
        "throughput-joined-to-build-identity"
    ]
    assert len(rows) == 4  # two replicas x two outcomes
    for row in rows:
        for label in (
            'service_version="0.1.0"',
            'deployment_environment="dev"',
            'inferops_release_id="inferops"',
            'inferops_adapter_kind="real"',
            'inferops_model_revision="90862c4b9d2787eaed51d12237eafdfe7c5f6077"',
            'inferops_runtime_id="llama-cpp-server"',
            'inferops_workload_id="support-assistant"',
            'inferops_model_id="qwen3-1-7b-q8-0"',
        ):
            assert label in row, (label, row)
    assert sum(float(row.rsplit(" ", 1)[1]) for row in rows) == pytest.approx(3.15)


def test_the_healthy_scenario_reports_a_latency_quantile_that_can_be_checked_by_hand() -> (
    None
):
    """200 observations, the 95th falling in the (45, 60] bucket, interpolated."""
    row = one_row(
        scenario_results("healthy-real-two-replicas")[
            "request-latency-p95-by-workload-and-model"
        ]
    )
    assert row.endswith(" 57.5"), row


def test_the_healthy_scenario_distinguishes_the_two_replicas() -> None:
    """The one question `instance` is unbounded for."""
    rows = scenario_results("healthy-real-two-replicas")[
        "in-flight-requests-by-replica"
    ]
    assert len(rows) == 2
    assert {row.rsplit(" ", 1)[1] for row in rows} == {"3", "2"}


def test_the_healthy_scenario_shows_the_api_and_the_runtime_disagreeing() -> None:
    """A non-zero result is the expected one: the two count different boundaries."""
    row = one_row(
        scenario_results("healthy-real-two-replicas")[
            "api-and-runtime-in-flight-side-by-side"
        ]
    )
    assert row.endswith(" 2"), row


def test_the_healthy_scenario_reads_model_readiness_as_absent() -> None:
    """1 today, and until the adapter the catalog assigns the metric to emits it."""
    results = scenario_results("healthy-real-two-replicas")
    assert one_row(results["model-readiness-absent"]).endswith(" 1")
    assert results["model-readiness-by-workload"] == []


def test_a_job_that_discovered_nothing_is_visible_only_through_its_absence_rule() -> (
    None
):
    """The failure that reads as a healthy quiet system in every other query."""
    results = scenario_results("serving-runtime-not-discovered")
    assert one_row(results["serving-runtime-scrape-job-absent"]).endswith(" 1")
    assert results["platform-api-scrape-job-absent"] == []
    health = results["scrape-target-health-by-job"]
    assert len(health) == 1
    assert "platform-api" in health[0]
    # And the queries an operator would actually be looking at say nothing at all.
    assert results["tokens-by-direction-from-the-runtime"] == []
    assert results["runtime-deferred-requests"] == []


def test_a_target_that_is_up_and_publishes_no_identity_is_separated_from_a_good_one() -> (
    None
):
    results = scenario_results("api-target-up-without-identity")
    assert one_row(results["identity-absent-on-a-target-that-answered"]).endswith(" 1")
    assert results["build-identity-per-replica"] == []
    # Traffic is being served and cannot be attributed to a build.
    assert results["request-throughput-by-workload-model-and-outcome"]
    assert results["throughput-joined-to-build-identity"] == []
    # Both jobs have targets, so neither absence rule fires.
    assert results["platform-api-scrape-job-absent"] == []
    assert results["serving-runtime-scrape-job-absent"] == []


def test_every_target_down_reads_zero_rather_than_reading_nothing() -> None:
    results = scenario_results("every-target-down")
    health = results["scrape-target-health-by-job"]
    assert len(health) == 2
    assert all(row.endswith(" 0") for row in health), health
    # And no job is reported absent: they have targets, the targets are failing.
    assert results["platform-api-scrape-job-absent"] == []
    assert results["serving-runtime-scrape-job-absent"] == []


def test_the_mock_profile_renders_no_runtime_query_at_all() -> None:
    """Absent from the result, not empty in it: two different answers."""
    results = scenario_results("mock-single-replica")
    for query_id in (
        "tokens-by-direction-from-the-runtime",
        "runtime-deferred-requests",
        "api-and-runtime-in-flight-side-by-side",
        "serving-runtime-scrape-job-absent",
    ):
        assert query_id not in results, query_id
    assert "platform-api-scrape-job-absent" in results


def test_the_mock_profile_identity_says_it_is_a_mock() -> None:
    """A scrape of a mock deployment is a scrape that says so."""
    row = one_row(scenario_results("mock-single-replica")["build-identity-per-replica"])
    assert 'inferops_adapter_kind="mock"' in row
    assert 'inferops_capability_id="inferops-mock-serving"' in row


@pytest.mark.parametrize("label", sorted(forbidden_metric_labels()))
def test_no_barred_label_survives_the_collector_into_any_result(label: str) -> None:
    """The negative check, run over every scenario and every barred label."""
    for scenario_id in SCENARIO_IDS:
        for rows in scenario_results(scenario_id).values():
            for row in rows:
                assert f"{label}=" not in row, (scenario_id, label, row)


def test_the_hostile_exposition_still_answers_the_questions_it_should() -> None:
    """Dropping the barred labels must not drop the series carrying them."""
    results = scenario_results("forbidden-labels-on-the-exposition")
    assert results["request-throughput-by-workload-model-and-outcome"]
    assert results["error-rate-by-workload-and-code"]
    assert results["in-flight-requests-by-replica"]


# --------------------------------------------------------------------------
# The gaps, demonstrated rather than asserted
# --------------------------------------------------------------------------


def test_a_runtime_series_cannot_be_joined_to_the_apis_identity() -> None:
    """`no-cross-tier-identity-join`, shown on the store rather than argued about.

    With two API replicas, k8s_namespace and inferops_model_id are the same on both
    build_info series, so the only key a runtime series shares with them matches two
    elements. Prometheus refuses a many-to-many match and so does this evaluator; the
    gap is real and this is what makes it a fact rather than a claim.
    """
    fixture = load_fixture(FIXTURE_DIR / "healthy-real-two-replicas.yaml")
    store = with_recording_rules(
        apply_metric_relabel(
            Store(
                tuple(
                    Series(
                        tuple(
                            sorted(
                                {
                                    **(entry.get("labels") or {}),
                                    "__name__": entry["name"],
                                }.items()
                            )
                        ),
                        tuple((float(t), float(v)) for t, v in entry["points"]),
                    )
                    for entry in fixture["series"]
                ),
                float(fixture["evaluationInstant"]),
            ),
            collector_dropped_labels("real"),
        ),
        "real",
    )
    expression = (
        "sum by (k8s_namespace, inferops_model_id) "
        "(inferops:inference_requests_in_flight:runtime) "
        "* on (k8s_namespace, inferops_model_id) group_left (service_version) "
        "inferops_build_info"
    )
    with pytest.raises(EvaluationError):
        evaluate(store, parse(expression))


def test_the_gap_the_evaluator_demonstrates_is_the_one_the_record_declares() -> None:
    gaps = {gap["gapId"]: gap for gap in RECORD["gaps"]}
    assert "no-cross-tier-identity-join" in gaps
    assert (
        gaps["no-cross-tier-identity-join"]["demonstratedBy"]
        == "tests/telemetry/test_telemetry_correlation.py"
    )


def test_the_no_source_questions_name_what_would_provide_them() -> None:
    no_source = [q for q in QUERIES if q["answerability"] == "no-source"]
    assert no_source
    for query in no_source:
        assert query["expr"] is None
        assert query["wouldRequire"]
        assert query["wouldRequire"] in DOCUMENT or "kube-state-metrics" in DOCUMENT


def test_the_signals_with_no_source_agree_with_the_collection_record() -> None:
    """Neither record may say a signal is unavailable the other thinks is fine."""
    unavailable = {row["signal"] for row in COLLECTION["unavailableSignals"]}
    for query in QUERIES:
        if query["answerability"] != "not-answerable-nothing-emits":
            continue
        for name in metrics_read(parse(query["expr"])):
            base = (
                name.removesuffix("_bucket").removesuffix("_count").removesuffix("_sum")
            )
            assert base in not_emitted_metric_names(), (query["queryId"], base)
            assert base in unavailable, (query["queryId"], base)


# --------------------------------------------------------------------------
# The evidence record, regenerated
# --------------------------------------------------------------------------


def test_the_committed_evidence_is_what_the_queries_return_today() -> None:
    """A record of results that drifted from the results is a memory, not a record."""
    assert EVIDENCE_PATH.read_text(encoding="utf-8") == _evidence(RECORD), (
        "regenerate with: python -m tools.telemetry_correlation --evidence"
    )


def test_the_evidence_record_states_that_nothing_ran_it() -> None:
    evidence = EVIDENCE_PATH.read_text(encoding="utf-8")
    assert "local-static" in evidence
    assert "No" in evidence and "Prometheus parsed, loaded, or evaluated" in evidence
    assert "synthetic" in evidence


# --------------------------------------------------------------------------
# The command line agrees with the library
# --------------------------------------------------------------------------


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.telemetry_correlation", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        check=False,
    )


def test_the_command_line_accepts_the_committed_record() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout


def test_the_command_line_reports_the_same_thing_as_a_stable_document() -> None:
    result = _run("--json")
    assert result.returncode == 0
    document = json.loads(result.stdout)
    assert document["valid"] is True
    assert document["findings"] == []
    assert document["queries"] == len(QUERIES)
    assert document["scenarios"] == len(SCENARIOS)


def test_the_command_line_evaluates_every_scenario() -> None:
    result = _run("--evaluate")
    assert result.returncode == 0, result.stderr
    for scenario_id in SCENARIO_IDS:
        assert scenario_id in result.stdout


# --------------------------------------------------------------------------
# What independent review found, kept as tests so it cannot come back
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expression",
    [
        "(" * (MAX_NESTING_DEPTH + 1) + "up" + ")" * (MAX_NESTING_DEPTH + 1),
        "-" * (MAX_NESTING_DEPTH + 1) + "up",
    ],
    ids=["parentheses", "unary-signs"],
)
def test_a_deeply_nested_expression_is_refused_rather_than_crashing(
    expression: str,
) -> None:
    """It raised RecursionError, which is not the error a caller handles.

    The parser is recursive descent, so nesting maps onto the interpreter's call
    stack. A caller that had carefully handled "outside the subset" would have
    crashed instead, which makes the module's own refusal contract untrue.
    """
    with pytest.raises(PromQLError):
        parse(expression)


def test_a_nesting_depth_just_inside_the_bound_still_parses() -> None:
    """The bound has to be a bound, not a ceiling that nothing reaches."""
    depth = MAX_NESTING_DEPTH - 1
    assert parse("(" * depth + "up" + ")" * depth) is not None


def test_a_group_modifier_with_ignoring_is_refused() -> None:
    """The join rule reads the on set, so ignoring would slip past it unchecked.

    A rule enforced for half a syntax reads as enforced and is not. The parser
    refuses the combination rather than the checker silently skipping it.
    """
    with pytest.raises(PromQLError):
        parse("inferops_build_info * ignoring (le) group_left inferops_build_info")


def test_the_join_rule_cannot_be_bypassed_by_any_form_the_subset_accepts() -> None:
    """Every group modifier the subset accepts carries an on set the rule reads."""
    tree = parse("up * on (job) group_left (a) up")
    assert isinstance(tree, Binary)
    assert tree.matching.card == "group_left"
    assert tree.matching.on is not None


@pytest.mark.parametrize(
    "pattern",
    ["(a+)+$", "[abc]", "a{2,3}", "a+", "a?", ".*.*.*.*.*x"],
)
def test_a_matcher_regex_that_could_backtrack_into_itself_is_refused(
    pattern: str,
) -> None:
    """A nested-quantifier matcher hung the process for minutes on 35 characters.

    There is no group in the accepted subset for a pattern to backtrack into, and no
    more than MAX_PATTERN_WILDCARDS wildcards for it to multiply out.
    """
    store = _store(("up", {"job": "a" * 35 + "!"}, [(600.0, 1.0)]))
    with pytest.raises(EvaluationError):
        evaluate(store, parse('up{job=~"' + pattern + '"}'))


@pytest.mark.parametrize(
    ("pattern", "value", "matched"),
    [
        ("x|y", "x", True),
        ("x|y", "z", False),
        ("pre.*", "prefix", True),
        ("inferops-a|inferops-b", "inferops-b", True),
    ],
)
def test_the_matcher_forms_this_repository_actually_writes_still_work(
    pattern: str, value: str, matched: bool
) -> None:
    """The safe subset has to admit the chart's own filters, or it admits nothing."""
    store = _store(("up", {"job": value}, [(600.0, 1.0)]))
    rows = evaluate(store, parse('up{job=~"' + pattern + '"}'))
    assert bool(rows) is matched


def test_the_wildcard_bound_is_stated_and_enforced() -> None:
    assert MAX_PATTERN_WILDCARDS == 4
    store = _store(("up", {"job": "a"}, [(600.0, 1.0)]))
    assert evaluate(store, parse('up{job=~".*.*.*.*"}')) is not None
    with pytest.raises(EvaluationError):
        evaluate(store, parse('up{job=~".*.*.*.*.*"}'))


def test_a_comparison_without_bool_keeps_the_left_element_unchanged() -> None:
    """It filters rather than computing, so Prometheus keeps the metric name.

    An earlier version dropped the name for every operator, comparisons included,
    and reduced the result to the join key. Only the arithmetic operators drop it.
    """
    store = _store(
        ("a", {"job": "j", "extra": "e"}, [(600.0, 5.0)]),
        ("b", {"job": "j"}, [(600.0, 1.0)]),
    )
    rows = format_vector(evaluate(store, parse("a > ignoring (extra) b")))
    assert rows == ['{__name__="a", extra="e", job="j"} 5']


def test_a_comparison_with_bool_computes_and_therefore_drops_the_name() -> None:
    store = _store(
        ("a", {"job": "j"}, [(600.0, 5.0)]),
        ("b", {"job": "j"}, [(600.0, 1.0)]),
    )
    assert format_vector(evaluate(store, parse("a > bool b"))) == ['{job="j"} 1']


def test_an_arithmetic_operator_still_drops_the_name() -> None:
    store = _store(
        ("a", {"job": "j"}, [(600.0, 5.0)]),
        ("b", {"job": "j"}, [(600.0, 1.0)]),
    )
    assert format_vector(evaluate(store, parse("a - b"))) == ['{job="j"} 4']


def test_group_right_matches_the_other_way_round() -> None:
    """group_right had no evaluator test at all, only a parser one.

    The many side is the right operand and the one side is the left, and the result
    carries the many side's labels plus whatever the modifier names.
    """
    store = _store(
        ("one", {"job": "j", "v": "1"}, [(600.0, 3.0)]),
        ("many", {"job": "j", "instance": "a"}, [(600.0, 2.0)]),
        ("many", {"job": "j", "instance": "b"}, [(600.0, 4.0)]),
    )
    rows = format_vector(evaluate(store, parse("one * on (job) group_right (v) many")))
    assert rows == [
        '{instance="a", job="j", v="1"} 6',
        '{instance="b", job="j", v="1"} 12',
    ]


def test_the_instant_lookback_window_is_half_open_and_pinned() -> None:
    """A sample exactly LOOKBACK_SECONDS old is outside the window.

    Stated exactly rather than as "no older than", which review read as inclusive.
    No fixture sits on the boundary; this pins the behaviour so a change to it
    cannot be silent.
    """
    boundary = _store(("m", {"a": "1"}, [(600.0 - LOOKBACK_SECONDS, 5.0)]))
    assert evaluate(boundary, parse("m")) == []
    inside = _store(("m", {"a": "1"}, [(600.0 - LOOKBACK_SECONDS + 1, 5.0)]))
    assert format_vector(evaluate(inside, parse("m"))) == ['{__name__="m", a="1"} 5']


def test_a_metric_whose_own_name_ends_in_a_histogram_suffix_is_not_mis_mapped() -> None:
    """_base_name stripped unconditionally, which is a trap for a future metric."""
    for name in declared_metric_names():
        assert _base_name(name) == name, name
    assert (
        _base_name("inferops_inference_request_duration_seconds_bucket")
        == "inferops_inference_request_duration_seconds"
    )
    assert _base_name("something_nothing_declares_count") == (
        "something_nothing_declares_count"
    )


@pytest.mark.parametrize(
    "identifier",
    QUERY_IDS
    + [row["refusedId"] for row in REFUSED]
    + SCENARIO_IDS
    + [gap["gapId"] for gap in RECORD["gaps"]]
    + [row["limitationId"] for row in RECORD["limitations"]]
    + list(RULE_IDS),
)
def test_every_identifier_in_the_record_is_safe_to_print(identifier: str) -> None:
    """An identifier reaches a terminal, a log line, a heading, and a test id."""
    assert IDENTIFIER.fullmatch(identifier), identifier


def test_a_hostile_query_identifier_cannot_reach_a_terminal() -> None:
    """The safe-character promise covers subject, not only message.

    It did not at first: subject is the record's own queryId and was interpolated
    unfiltered into Finding.__str__, and from there into stdout.
    """
    hostile = "evil\x1b[31mID\r\nSEVERITY=ok‮"
    findings = check_query(
        {
            "queryId": hostile,
            "expr": "not_a_metric_anything_declares",
            "profiles": ["real"],
        }
    )
    assert findings
    for finding in findings:
        for character in str(finding):
            assert character in SAFE_MESSAGE_CHARACTERS, (finding.rule, character)
