"""ExperimentRun v1alpha1: the validator of a run manifest and the repository listing.

An ExperimentRun is the manifest of one run of one experiment against one delivered
release. It names the frozen record, the executing commit, the environment, the
release, the runtime image, the model, the caller profile, the fault, the result
state, the intended evidence level, the evidence files, and the cleanup state. The
result state, the evidence level, and a claim's status are three separate things.

See docs/contracts/experiment-run.md, which states each member, each rule, and what
no rule holds, and tests/contracts/test_experiment_run_v1alpha1.py, which holds each
fixture to its published refusal.
"""

from .core import (
    CALLER_ROLE,
    CONFORMING,
    EVIDENCE_LEVELS,
    KIND,
    MANIFEST_NAME,
    PRE_SCHEMA,
    PRE_SCHEMA_REGISTER_REF,
    REFUSED,
    REGISTERED_CALLER_PROFILES,
    REPOSITORY_RULES,
    RESULT_STATES,
    RUNS_ROOT_REF,
    SCHEMA_PATH,
    SCHEMA_REF,
    SEMANTIC_RULES,
    SUPPORTED_API_VERSION,
    ManifestStatus,
    RepositoryReport,
    RunDocumentError,
    content_digest,
    credential_shaped,
    holds_host_path,
    is_valid,
    load_pre_schema_register,
    load_schema,
    read_document,
    repository_report,
    semantic_findings,
    structural_findings,
    validate,
)

__all__ = [
    "CALLER_ROLE",
    "CONFORMING",
    "EVIDENCE_LEVELS",
    "KIND",
    "MANIFEST_NAME",
    "PRE_SCHEMA",
    "PRE_SCHEMA_REGISTER_REF",
    "REFUSED",
    "REGISTERED_CALLER_PROFILES",
    "REPOSITORY_RULES",
    "RESULT_STATES",
    "RUNS_ROOT_REF",
    "SCHEMA_PATH",
    "SCHEMA_REF",
    "SEMANTIC_RULES",
    "SUPPORTED_API_VERSION",
    "ManifestStatus",
    "RepositoryReport",
    "RunDocumentError",
    "content_digest",
    "credential_shaped",
    "holds_host_path",
    "is_valid",
    "load_pre_schema_register",
    "load_schema",
    "read_document",
    "repository_report",
    "semantic_findings",
    "structural_findings",
    "validate",
]
