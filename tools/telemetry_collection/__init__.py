"""The V1 telemetry collection policy, applied to rendered scrape configuration.

It reads YAML and refuses a scrape configuration that would collect something the
accepted telemetry catalog does not permit in a metric, that maps a runtime series
nothing ever observed, or that leaves a job whose absence no query could see.

It contacts no cluster and scrapes nothing. No collector, store, dashboard, or
alerting path is selected in V1, so a configuration this accepts is a configuration
nothing has loaded.
"""

from .core import (
    CATALOG_PATH,
    COLLECTION_RECORD_PATH,
    CONFIG_MAP_COMPONENT,
    RULE_IDS,
    SAFE_MESSAGE_CHARACTERS,
    Finding,
    check_documents,
    emitted_metric_names,
    forbidden_metric_labels,
    is_scrape_config_map,
    observed_native_series,
)

__all__ = [
    "CATALOG_PATH",
    "COLLECTION_RECORD_PATH",
    "CONFIG_MAP_COMPONENT",
    "RULE_IDS",
    "SAFE_MESSAGE_CHARACTERS",
    "Finding",
    "check_documents",
    "emitted_metric_names",
    "forbidden_metric_labels",
    "is_scrape_config_map",
    "observed_native_series",
]
