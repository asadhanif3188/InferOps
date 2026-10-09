"""The Ready endpoint state of the API Service and the runtime Service, as a record.

A collector writes two cluster reads into one directory: the Services and the
EndpointSlices of the release namespace. This package reads that directory and
returns one record. For each of the two tiers, the record states the number of
endpoints, the number that were Ready, and the pod name and pod UID of each.
The result is ``OBSERVED`` or ``REFUSED``. Zero Ready endpoints is ``OBSERVED``.
A read that was not made is ``REFUSED``.

See docs/environment/service-endpoint-state.md, which describes the collection,
the rules, the identities, and the limits of a record, and
tests/domain/test_service_endpoint_state.py, which gives the tool each ambiguous
collection.
"""

from .core import (
    CASES_PATTERN,
    COLLECTION_SCHEMA,
    DOES_NOT_ESTABLISH,
    HEADER_FILE,
    HELD,
    LIMITATIONS,
    MAX_ENDPOINTS,
    NOT_HELD,
    NOT_OBSERVED,
    OBSERVED,
    OMITTED,
    RECORD_FILE,
    RECORD_SCHEMA,
    REFUSED,
    REFUSED_EXIT,
    REPO_ROOT,
    RESULT_STATES,
    RULES,
    RUNS_PATTERN,
    SERVICES_FILE,
    SLICE_CONTROLLER,
    SLICES_FILE,
    TIER_NOT_OBSERVED,
    TIER_OBSERVED,
    TIER_REFUSED,
    TIERS,
    CollectionRefused,
    Rule,
    build_record,
    check_committed,
    committed_collections,
    observe,
    record_text,
)

__all__ = [
    "CASES_PATTERN",
    "COLLECTION_SCHEMA",
    "DOES_NOT_ESTABLISH",
    "HEADER_FILE",
    "HELD",
    "LIMITATIONS",
    "MAX_ENDPOINTS",
    "NOT_HELD",
    "NOT_OBSERVED",
    "OBSERVED",
    "OMITTED",
    "RECORD_FILE",
    "RECORD_SCHEMA",
    "REFUSED",
    "REFUSED_EXIT",
    "REPO_ROOT",
    "RESULT_STATES",
    "RULES",
    "RUNS_PATTERN",
    "SERVICES_FILE",
    "SLICES_FILE",
    "SLICE_CONTROLLER",
    "TIERS",
    "TIER_NOT_OBSERVED",
    "TIER_OBSERVED",
    "TIER_REFUSED",
    "CollectionRefused",
    "Rule",
    "build_record",
    "check_committed",
    "committed_collections",
    "observe",
    "record_text",
]
