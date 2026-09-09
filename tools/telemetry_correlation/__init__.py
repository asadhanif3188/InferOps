"""The V1 correlation query policy, and an evaluator for the queries it accepts.

It reads the committed correlation query record, parses every expression with a
declared subset of PromQL, and refuses a query that could not answer the question it
claims to: one reading a series nothing in this release produces, grouping by a label
no series carries, joining on a key one side cannot have, naming a label the
telemetry catalog bars from a metric, or claiming an answer a signal nothing emits
cannot give.

It then evaluates the accepted queries against synthetic fixture stores, so that a
query which is well formed and still returns nothing -- the failure an operator meets
as an empty panel -- is caught here rather than there.

It contacts no cluster and scrapes nothing. No collector, store, dashboard, or
alerting path is selected in V1, so a query this accepts is a query nothing has run.
"""

from .core import (
    CATALOG_PATH,
    COLLECTION_RECORD_PATH,
    FIXTURE_DIR,
    IDENTIFIER,
    QUERY_RECORD_PATH,
    RULE_IDS,
    SAFE_MESSAGE_CHARACTERS,
    Finding,
    apply_metric_relabel,
    carriable_labels,
    check_query,
    check_record,
    collector_dropped_labels,
    declared_metric_names,
    evaluate_scenario,
    forbidden_metric_labels,
    load_fixture,
    load_query_record,
    not_emitted_metric_names,
    observed_native_series,
    permitted_query_labels,
    recorded_series_names,
    rendered_recording_rules,
    with_recording_rules,
)
from .evaluate import (
    EXTRAPOLATION,
    LOOKBACK_SECONDS,
    MAX_PATTERN_WILDCARDS,
    EvaluationError,
    Sample,
    Series,
    Store,
    evaluate,
    format_vector,
)
from .promql import (
    AGGREGATIONS,
    FUNCTIONS,
    MAX_NESTING_DEPTH,
    PromQLError,
    labels_read,
    metrics_read,
    parse,
)

__all__ = [
    "AGGREGATIONS",
    "CATALOG_PATH",
    "COLLECTION_RECORD_PATH",
    "EXTRAPOLATION",
    "FIXTURE_DIR",
    "FUNCTIONS",
    "IDENTIFIER",
    "LOOKBACK_SECONDS",
    "MAX_NESTING_DEPTH",
    "MAX_PATTERN_WILDCARDS",
    "QUERY_RECORD_PATH",
    "RULE_IDS",
    "SAFE_MESSAGE_CHARACTERS",
    "EvaluationError",
    "Finding",
    "PromQLError",
    "Sample",
    "Series",
    "Store",
    "apply_metric_relabel",
    "carriable_labels",
    "check_query",
    "check_record",
    "collector_dropped_labels",
    "declared_metric_names",
    "evaluate",
    "evaluate_scenario",
    "forbidden_metric_labels",
    "format_vector",
    "labels_read",
    "load_fixture",
    "load_query_record",
    "metrics_read",
    "not_emitted_metric_names",
    "observed_native_series",
    "parse",
    "permitted_query_labels",
    "recorded_series_names",
    "rendered_recording_rules",
    "with_recording_rules",
]
