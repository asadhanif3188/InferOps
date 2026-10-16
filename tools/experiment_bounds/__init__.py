"""Q4, the derived experiment bounds of the V2 reliability experiments.

This package reads one committed Q2 record and one committed Q3 record and
returns one record that states runtime_start_bound_ms, caller_gap_reference_ms,
reversal_recovery_bound_ms, and caller_total_unavailability_bound_ms by fixed
formulas, bound to the digest of each source record and of its freeze record.

See docs/proof/experiments/README.md, which describes the committed bound record.
"""

from .core import (
    BOUND_NAMES,
    BOUNDARY,
    BOUNDS_PATTERN,
    CALLER_FREEZE_RECORDS,
    CALLER_RECORD_PATTERN,
    CALLER_SCHEMA,
    DOES_NOT_ESTABLISH,
    FORMULAS,
    RECORD_SCHEMA,
    RECOVERY_ALLOWANCE_MS,
    REFUSED_EXIT,
    REPO_ROOT,
    RULES,
    STARTUP_FREEZE_RECORDS,
    STARTUP_RECORD_PATTERN,
    STARTUP_SCHEMA,
    UNAVAILABILITY_FLOOR_MS,
    BoundsRefused,
    SourceRecord,
    build_record,
    check_committed,
    committed_records,
    lf_digest,
    record_text,
    stated_bounds,
)

__all__ = [
    "BOUNDARY",
    "BOUNDS_PATTERN",
    "BOUND_NAMES",
    "CALLER_FREEZE_RECORDS",
    "CALLER_RECORD_PATTERN",
    "CALLER_SCHEMA",
    "DOES_NOT_ESTABLISH",
    "FORMULAS",
    "RECORD_SCHEMA",
    "RECOVERY_ALLOWANCE_MS",
    "REFUSED_EXIT",
    "REPO_ROOT",
    "RULES",
    "STARTUP_FREEZE_RECORDS",
    "STARTUP_RECORD_PATTERN",
    "STARTUP_SCHEMA",
    "UNAVAILABILITY_FLOOR_MS",
    "BoundsRefused",
    "SourceRecord",
    "build_record",
    "check_committed",
    "committed_records",
    "lf_digest",
    "record_text",
    "stated_bounds",
]
