"""Figures derived from a committed performance record, with no saturation judged."""

from .core import (
    BOUNDARY,
    FindingsError,
    FindingsRefused,
    checked_record,
    completion_gaps_ms,
    derive_findings,
    gauge_maximum,
    ratio_milli,
    read_inputs,
    reading_at,
)

__all__ = [
    "BOUNDARY",
    "FindingsError",
    "FindingsRefused",
    "checked_record",
    "completion_gaps_ms",
    "derive_findings",
    "gauge_maximum",
    "ratio_milli",
    "read_inputs",
    "reading_at",
]
