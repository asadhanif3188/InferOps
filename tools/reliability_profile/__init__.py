"""The RP-1 reliability caller profile: its loader and the rules that refuse a drift.

RP-1 is one fixed public request, sent by two closed-loop callers to the API Service.
The committed profile reuses the fixture, the generation settings, the client
deadline, and four of the five members of the success rule of the V1 load profile,
and it pins that file by content digest. It is a reliability workload. It is not a
representative production workload, an overload test, or a benchmark.

See docs/serving/reliability-workload-rp-1.md, which states each value, where it
comes from, and what the profile does not establish, and
tests/serving/test_reliability_profile.py, which holds each reused value against the
V1 load profile and the V1 load harness, and gives the loader one drift at a time.
"""

from .core import (
    BOUNDARY_STATEMENT,
    CONCURRENCY,
    CONNECTION,
    DISPOSITIONS,
    PROFILE_ID,
    PROFILE_PATH,
    PROFILE_REF,
    REGISTERED_REVISIONS,
    RULES,
    SOURCE_DISPOSITION,
    SOURCE_PROFILE_REF,
    ProfileError,
    ReliabilityProfile,
    load_profile,
    profile_digest,
)

__all__ = [
    "BOUNDARY_STATEMENT",
    "CONCURRENCY",
    "CONNECTION",
    "DISPOSITIONS",
    "PROFILE_ID",
    "PROFILE_PATH",
    "PROFILE_REF",
    "REGISTERED_REVISIONS",
    "RULES",
    "SOURCE_DISPOSITION",
    "SOURCE_PROFILE_REF",
    "ProfileError",
    "ReliabilityProfile",
    "load_profile",
    "profile_digest",
]
