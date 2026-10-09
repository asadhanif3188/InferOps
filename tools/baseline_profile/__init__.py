"""The controlled single-runtime baseline, and its comparison with the target release.

The target is the desired-state release of the reference workload, with two API
replicas and two serving runtime replicas. The baseline is an experiment profile
with two API replicas and one serving runtime replica. This package declares the
baseline, derives both releases from their declared inputs, and returns one
comparison record. The result is ``COMPARABLE`` or ``REFUSED``. A difference
that the package does not state as permitted refuses the comparison.

See docs/environment/single-runtime-baseline-profile.md, which describes the
profile, the permitted differences, the rules, and the limits of a record, and
tests/domain/test_baseline_profile.py, which gives the tool each accidental
change.
"""

from .core import (
    BASELINE_CONTRACT,
    CHECK_RULES,
    COMPARABLE,
    DOES_NOT_ESTABLISH,
    ELIGIBILITY,
    HELD,
    INSTALL_PATH,
    INSTALL_SCHEMA,
    INTENDED,
    NOT_EVALUATED,
    NOT_HELD,
    PERMITTED,
    PROFILE_DIRECTORY,
    READINESS_INPUTS,
    RECORD_PATH,
    RECORD_SCHEMA,
    REFUSED,
    REFUSED_EXIT,
    REPO_ROOT,
    RESULT_STATES,
    RULES,
    TARGET_KEY,
    TOPOLOGY,
    Finding,
    Rule,
    WriteRefused,
    baseline_profile,
    build_record,
    record_text,
    target_release,
    verify_profile,
    write_profile,
)

__all__ = [
    "BASELINE_CONTRACT",
    "CHECK_RULES",
    "COMPARABLE",
    "DOES_NOT_ESTABLISH",
    "ELIGIBILITY",
    "HELD",
    "INSTALL_PATH",
    "INSTALL_SCHEMA",
    "INTENDED",
    "NOT_EVALUATED",
    "NOT_HELD",
    "PERMITTED",
    "PROFILE_DIRECTORY",
    "READINESS_INPUTS",
    "RECORD_PATH",
    "RECORD_SCHEMA",
    "REFUSED",
    "REFUSED_EXIT",
    "REPO_ROOT",
    "RESULT_STATES",
    "RULES",
    "TARGET_KEY",
    "TOPOLOGY",
    "Finding",
    "Rule",
    "WriteRefused",
    "baseline_profile",
    "build_record",
    "record_text",
    "target_release",
    "verify_profile",
    "write_profile",
]
