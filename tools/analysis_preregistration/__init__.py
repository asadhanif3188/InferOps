"""The preregistration of the two analysis experiments, checked against its sources.

The freeze records of V2-E03 (signal truthfulness) and V2-E06 (reliability
resource and cost overhead) bind the latest freeze records of the experiments
whose runs they read, by path, revision, and content digest, before any of those
runs exists. This package checks that each binding is the latest registered
revision, that each record states what its sources state, and the rules of each
record: for V2-E03 its population, its ten signals, its operational signal
candidate, its rule for caller failures that the API error counter does not
count, its computations, and its ranking rule; for V2-E06 its views, its labels,
its metrics, its utilization statistic, its cost basis, and its evidence target.

See docs/proof/experiments/README.md, which describes the records, and
tests/testing/test_analysis_preregistration.py, which checks the committed records
and plants each defect that the check refuses.
"""

from .core import (
    CONFIGURATION_READS,
    E03,
    E03_EXCLUDED,
    E03_EXTENSION,
    E03_INITIAL,
    E03_SIGNALS,
    E06,
    E06_METRICS,
    E06_SOURCES,
    EXPERIMENTS,
    LABELS,
    REPO_ROOT,
    RULES,
    RUN_READS,
    AnalysisExperiment,
    Finding,
    check_records,
    check_repository,
    policy_digest,
)

__all__ = [
    "CONFIGURATION_READS",
    "E03",
    "E03_EXCLUDED",
    "E03_EXTENSION",
    "E03_INITIAL",
    "E03_SIGNALS",
    "E06",
    "E06_METRICS",
    "E06_SOURCES",
    "EXPERIMENTS",
    "LABELS",
    "REPO_ROOT",
    "RULES",
    "RUN_READS",
    "AnalysisExperiment",
    "Finding",
    "check_records",
    "check_repository",
    "policy_digest",
]
