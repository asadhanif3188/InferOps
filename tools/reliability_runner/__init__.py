"""The RP-1 in-cluster reliability runner: its plan, its Job, and its caller record.

A run is one Kubernetes Job in the namespace of the release. Its pod executes one
file, ``incluster.py``, which sends the RP-1 request to the API Service by its
cluster DNS name and writes one line of JSON for each request. The runner reads no
readiness answer, no Kubernetes API, and no state of a delivery controller. It is
started for one experiment run and removed after it. It is not part of the release.

See docs/serving/reliability-runner.md, which states what a caller record holds and
what it does not establish, and tests/serving/test_reliability_runner.py, which runs
the loop against scripted answers and against a loopback server in its own process.
"""

from .core import (
    API_SERVICE,
    API_SERVICE_PORT,
    PAUSE_AFTER_NON_SUCCESS_MS,
    RELEASE_NAMESPACE,
    RULES,
    RUNNER_REF,
    CallerRecord,
    RunnerError,
    build_manifest,
    build_plan,
    manifest_text,
    plan_text,
    read_record,
    record_from,
    rehearse,
    runner_digest,
)

__all__ = [
    "API_SERVICE",
    "API_SERVICE_PORT",
    "PAUSE_AFTER_NON_SUCCESS_MS",
    "RELEASE_NAMESPACE",
    "RULES",
    "RUNNER_REF",
    "CallerRecord",
    "RunnerError",
    "build_manifest",
    "build_plan",
    "manifest_text",
    "plan_text",
    "read_record",
    "record_from",
    "rehearse",
    "runner_digest",
]
