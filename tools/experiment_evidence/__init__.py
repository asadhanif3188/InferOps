"""The directory of an experiment run: its layout and its integrity check.

A run directory holds one ExperimentRun manifest and the evidence files that the
manifest names. This package holds a directory to its manifest: each named file is
present with its stated digest, each file that is present is named, each file has a
registered role, a derived file has a raw file beside it, and a correction is a new
file beside the ``runs`` directory. A digest is the one that ``tools.evidence_index``
gives a text file.

See docs/testing/experiment-evidence-layout.md, which states the layout, each rule,
and what no rule holds, and tests/testing/test_experiment_evidence_layout.py.
"""

from .core import (
    CALLER_ROLE,
    CORRECTION_KIND,
    CORRECTION_MEMBERS,
    CORRECTIONS_DIRECTORY,
    DERIVED,
    EVIDENCE_SUFFIXES,
    RAW,
    REFUSED,
    ROLES,
    RULES,
    RUNS_DIRECTORY,
    Finding,
    LayoutError,
    RepositoryReport,
    Role,
    RunDigests,
    RunReport,
    check_run,
    correction_problem,
    describe_file,
    digest_lines,
    expected_run_ref,
    file_digest,
    form_problem,
    is_raw,
    repository_report,
    run_digests,
    text_problems,
)

__all__ = [
    "CALLER_ROLE",
    "CORRECTIONS_DIRECTORY",
    "CORRECTION_KIND",
    "CORRECTION_MEMBERS",
    "DERIVED",
    "EVIDENCE_SUFFIXES",
    "RAW",
    "REFUSED",
    "ROLES",
    "RULES",
    "RUNS_DIRECTORY",
    "Finding",
    "LayoutError",
    "RepositoryReport",
    "Role",
    "RunDigests",
    "RunReport",
    "check_run",
    "correction_problem",
    "describe_file",
    "digest_lines",
    "expected_run_ref",
    "file_digest",
    "form_problem",
    "is_raw",
    "repository_report",
    "run_digests",
    "text_problems",
]
