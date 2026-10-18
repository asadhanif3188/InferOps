"""The preregistration of the reliability experiments, checked against its sources.

The freeze records of V2-E02A, V2-E02B, V2-E02C, V2-E04, and V2-E05 name one
qualification, one bound record, and, for the controlled comparison, one baseline
comparison. This package checks that each named record is committed with the
stated digest and states what the freeze record states, that the bounds are the
latest committed ones, that V2-E02A and V2-E02B differ in the runtime topology
alone, and that every executable a record names is pinned.

See docs/proof/experiments/README.md, which describes the records, and
tests/testing/test_experiment_preregistration.py, which checks the committed
records and plants each defect that the check refuses.
"""

from .core import (
    BASELINE,
    EXPERIMENTS,
    PERMITTED_TOPOLOGY,
    RECONCILIATION_COMPONENTS,
    REPO_ROOT,
    RULES,
    SHARED_DEFINITION,
    SHARED_FIELDS,
    TARGET,
    Experiment,
    Finding,
    check_repository,
    latest_records,
)

__all__ = [
    "BASELINE",
    "EXPERIMENTS",
    "PERMITTED_TOPOLOGY",
    "RECONCILIATION_COMPONENTS",
    "REPO_ROOT",
    "RULES",
    "SHARED_DEFINITION",
    "SHARED_FIELDS",
    "TARGET",
    "Experiment",
    "Finding",
    "check_repository",
    "latest_records",
]
