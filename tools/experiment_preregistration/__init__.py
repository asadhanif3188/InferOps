"""The preregistration of the reliability experiments, checked against its sources.

The freeze records of V2-E02A, V2-E02B, V2-E02C, V2-E04, and V2-E05 name one
qualification, one bound record, and, for the controlled comparison, one baseline
comparison. This package checks that each named record is committed with the
stated digest and states what the freeze record states, that the bounds are the
latest committed ones, that V2-E02A and V2-E02B differ in the runtime topology
alone, and that every executable a record names is pinned. Each record is read
under its own rule set: rule set 2 adds one clock policy and the rules that hold a
record to it.

See docs/proof/experiments/README.md, which describes the records, and
tests/testing/test_experiment_preregistration.py, which checks the committed
records and plants each defect that the check refuses.
"""

from .core import (
    BASELINE,
    CLOCK_RULE_SET,
    CLOCK_SOURCES,
    CLOCKS,
    EXPERIMENTS,
    PERMITTED_TOPOLOGY,
    RECONCILIATION_COMPONENTS,
    REPO_ROOT,
    REVISION_ONE_RECORDS,
    RULE_SETS,
    RULES,
    SHARED_DEFINITION,
    SHARED_FIELDS,
    TARGET,
    Experiment,
    Finding,
    check_records,
    check_repository,
    latest_records,
    record_revisions,
    superseded_count,
)

__all__ = [
    "BASELINE",
    "CLOCKS",
    "CLOCK_RULE_SET",
    "CLOCK_SOURCES",
    "EXPERIMENTS",
    "PERMITTED_TOPOLOGY",
    "RECONCILIATION_COMPONENTS",
    "REPO_ROOT",
    "REVISION_ONE_RECORDS",
    "RULES",
    "RULE_SETS",
    "SHARED_DEFINITION",
    "SHARED_FIELDS",
    "TARGET",
    "Experiment",
    "Finding",
    "check_records",
    "check_repository",
    "latest_records",
    "record_revisions",
    "superseded_count",
]
