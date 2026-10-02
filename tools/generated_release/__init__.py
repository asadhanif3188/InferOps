"""Committed generated releases, checked against the sources they are derived from.

A generated release - ``values.generated.yaml`` and the RenderedWorkloadRelease
naming it - is committed only as the platform wrote it. This package derives each
committed release again from its declared inputs and compares the bytes. A
difference is drift, reported with the release fields it moves and a unified diff,
and it is repaired only by regenerating the release on purpose.

See docs/domain/helm-values-renderer.md, which describes the workflow, and
tests/domain/test_generated_release_drift.py, which runs the check over every
declared release and plants each kind of drift it reports.
"""

from .core import (
    DECLARED_RELEASES,
    FIELD_CAUSES,
    GENERATED_FILES,
    MATRIX_PATH,
    REPO_ROOT,
    RULES,
    DeclaredRelease,
    Finding,
    RegenerationRefused,
    Rule,
    SourcesRefused,
    declared_release,
    derive,
    regenerate,
    regenerate_command,
    verify,
)

__all__ = [
    "DECLARED_RELEASES",
    "FIELD_CAUSES",
    "GENERATED_FILES",
    "MATRIX_PATH",
    "REPO_ROOT",
    "RULES",
    "DeclaredRelease",
    "Finding",
    "RegenerationRefused",
    "Rule",
    "SourcesRefused",
    "declared_release",
    "derive",
    "regenerate",
    "regenerate_command",
    "verify",
]
