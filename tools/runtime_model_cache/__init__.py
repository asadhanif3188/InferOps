"""What the serving runtime replicas read from the model cache, as an evidence record.

A run driver writes a bounded set of cluster reads into one directory. This
package reads that directory and returns one record: the model identity each
runtime replica was given, how each replica mounts the claim, what each
verification container reported, and the state of each rule. A read that was not
made stays not made. It is never read as agreement.

See docs/environment/runtime-model-cache-observation.md, which describes the
collection, the rules, and the limits of a record, and
tests/domain/test_runtime_model_cache.py, which gives the tool each missing and
each disagreeing read.
"""

from .core import (
    CAPACITY_REFUSED_EXIT,
    COLLECTION_SCHEMA,
    DOES_NOT_ESTABLISH,
    EXPECTED_SCHEMA,
    HELD,
    NOT_HELD,
    NOT_OBSERVED,
    RECORD_FILE,
    RECORD_SCHEMA,
    REPO_ROOT,
    RESULT_STATES,
    RULES,
    RUNS_PATTERN,
    RUNTIME_COMPONENT,
    CollectionRefused,
    ExpectedRefused,
    Rule,
    build_record,
    cache_sub_path,
    check_committed_runs,
    committed_runs,
    evaluate,
    expected_identity,
    pin_findings,
    record_text,
    result_state,
)

__all__ = [
    "CAPACITY_REFUSED_EXIT",
    "COLLECTION_SCHEMA",
    "DOES_NOT_ESTABLISH",
    "EXPECTED_SCHEMA",
    "HELD",
    "NOT_HELD",
    "NOT_OBSERVED",
    "RECORD_FILE",
    "RECORD_SCHEMA",
    "REPO_ROOT",
    "RESULT_STATES",
    "RULES",
    "RUNS_PATTERN",
    "RUNTIME_COMPONENT",
    "CollectionRefused",
    "ExpectedRefused",
    "Rule",
    "build_record",
    "cache_sub_path",
    "check_committed_runs",
    "committed_runs",
    "evaluate",
    "expected_identity",
    "pin_findings",
    "record_text",
    "result_state",
]
