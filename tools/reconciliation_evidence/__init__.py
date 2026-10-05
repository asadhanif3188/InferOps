"""The reconciliation state a GitOps controller reported, as an evidence record.

The Application procedure's ``observe`` operation writes a bounded number of
reads into one directory. This package reads that directory and returns one
record: what was reported at each sample, what was not, and what changed between
two samples. A field that was not reported stays not reported. It is never read
as healthy.

See docs/environment/reconciliation-evidence.md, which describes the record, its
limits, and the boundary for a manual change, and
tests/domain/test_reconciliation_evidence.py, which gives the tool each missing
and unavailable field.
"""

from .core import (
    APPLICATION_STATES,
    DOES_NOT_ESTABLISH,
    FIELD_STATES,
    OPTIONAL_FIELDS,
    RECORD_SCHEMA,
    REPO_ROOT,
    REPOSITORY,
    REQUIRED_FIELDS,
    TRANSITION_FIELDS,
    CollectionRefused,
    Field,
    Sample,
    application_fields,
    build_record,
    diagnostic_text,
    read_collection,
    settled,
    transitions,
)

__all__ = [
    "APPLICATION_STATES",
    "DOES_NOT_ESTABLISH",
    "FIELD_STATES",
    "OPTIONAL_FIELDS",
    "RECORD_SCHEMA",
    "REPOSITORY",
    "REPO_ROOT",
    "REQUIRED_FIELDS",
    "TRANSITION_FIELDS",
    "CollectionRefused",
    "Field",
    "Sample",
    "application_fields",
    "build_record",
    "diagnostic_text",
    "read_collection",
    "settled",
    "transitions",
]
