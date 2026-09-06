"""The V1 Kubernetes workload security policy, applied to committed manifests.

It reads YAML and refuses a bundle whose workloads have dropped a control the
security baseline says every InferOps workload carries. It holds no credential,
contacts no cluster, and stops nothing being applied: a pod that would fail this
policy is a pod this policy will never see.
"""

from .core import (
    DEFAULT_SERVICE_ACCOUNT,
    DIGEST_PINNED,
    EXTERNAL_SERVICE_TYPES,
    LIFECYCLE_LABEL,
    RELEASE_LIFECYCLE,
    RELEASE_SCOPED_RULES,
    REQUIRED_CONTAINER_FIELDS,
    REQUIRED_POD_FIELDS,
    RULE_IDS,
    WORKLOAD_KINDS,
    Finding,
    check_documents,
    is_release_bundle,
    names_a_secret,
)

__all__ = [
    "DEFAULT_SERVICE_ACCOUNT",
    "DIGEST_PINNED",
    "EXTERNAL_SERVICE_TYPES",
    "LIFECYCLE_LABEL",
    "RELEASE_LIFECYCLE",
    "RELEASE_SCOPED_RULES",
    "REQUIRED_CONTAINER_FIELDS",
    "REQUIRED_POD_FIELDS",
    "RULE_IDS",
    "WORKLOAD_KINDS",
    "Finding",
    "check_documents",
    "is_release_bundle",
    "names_a_secret",
]
