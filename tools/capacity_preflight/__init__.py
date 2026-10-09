"""Whether one cluster can hold the two-replica release, as a gate record.

A collector writes a bounded set of cluster reads into one directory. This
package reads that directory and returns one record: the figures that the node
allocates, the requests of the pods that the node holds, the declared footprint
of the release with its rollout headroom, and the state of each rule. The result
is ``ACCEPTED`` or ``REFUSED``. A read that was not made refuses the cluster.

See docs/environment/capacity-preflight.md, which describes the collection, the
rules, the units, and the limits of a record, and
tests/domain/test_capacity_preflight.py, which gives the tool each insufficient
and each ambiguous cluster.
"""

from .core import (
    ACCEPTED,
    AMBIGUOUS,
    APPLICATIONS,
    CASES_PATTERN,
    COLLECTION_SCHEMA,
    DOES_NOT_ESTABLISH,
    FOOTPRINT_SCHEMA,
    HELD,
    INSUFFICIENT,
    NOT_HELD,
    NOT_OBSERVED,
    RECORD_FILE,
    RECORD_SCHEMA,
    REFUSED,
    REFUSED_EXIT,
    REPO_ROOT,
    RESERVE,
    RESULT_STATES,
    RULES,
    RUNS_PATTERN,
    UNITS,
    CollectionRefused,
    FootprintRefused,
    QuantityRefused,
    Rule,
    build_record,
    check_committed,
    committed_collections,
    declared_footprint,
    footprint_digest,
    footprint_text,
    parse_quantity,
    pod_request,
    record_text,
    stale_footprint,
)

__all__ = [
    "ACCEPTED",
    "AMBIGUOUS",
    "APPLICATIONS",
    "CASES_PATTERN",
    "COLLECTION_SCHEMA",
    "DOES_NOT_ESTABLISH",
    "FOOTPRINT_SCHEMA",
    "HELD",
    "INSUFFICIENT",
    "NOT_HELD",
    "NOT_OBSERVED",
    "RECORD_FILE",
    "RECORD_SCHEMA",
    "REFUSED",
    "REFUSED_EXIT",
    "REPO_ROOT",
    "RESERVE",
    "RESULT_STATES",
    "RULES",
    "RUNS_PATTERN",
    "UNITS",
    "CollectionRefused",
    "FootprintRefused",
    "QuantityRefused",
    "Rule",
    "build_record",
    "check_committed",
    "committed_collections",
    "declared_footprint",
    "footprint_digest",
    "footprint_text",
    "parse_quantity",
    "pod_request",
    "record_text",
    "stale_footprint",
]
