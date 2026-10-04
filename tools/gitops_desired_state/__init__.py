"""The Git desired-state tree, checked against the releases it is declared to hold.

``gitops/`` holds generated releases and nothing written by hand. This package
names each desired-state release and its inputs, derives the path each belongs at
from its EnvironmentBinding and WorkloadContract, compares each with what its
sources derive, and reports every entry in the tree that no declaration accounts
for. It regenerates a release a contributor names.

See docs/environment/git-desired-state.md, which describes the layout and the
promotion boundary, and tests/domain/test_gitops_desired_state.py, which checks
the committed tree and plants each defect the check refuses.
"""

from .core import (
    DESIRED_STATE_RELEASES,
    DESIRED_STATE_ROOT,
    ENVIRONMENTS_PATH,
    REPO_ROOT,
    RULES,
    TREE_DOCUMENT,
    WORKLOADS_SEGMENT,
    Finding,
    Rule,
    WriteRefused,
    desired_state_release,
    expected_directory,
    regenerate_release,
    release_key,
    verify_tree,
)

__all__ = [
    "DESIRED_STATE_RELEASES",
    "DESIRED_STATE_ROOT",
    "ENVIRONMENTS_PATH",
    "REPO_ROOT",
    "RULES",
    "TREE_DOCUMENT",
    "WORKLOADS_SEGMENT",
    "Finding",
    "Rule",
    "WriteRefused",
    "desired_state_release",
    "expected_directory",
    "regenerate_release",
    "release_key",
    "verify_tree",
]
