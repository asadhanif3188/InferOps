"""The provenance of a desired-state release, read at one Git commit.

A GitOps controller follows a branch and reports the commit it resolved. This
package reads the desired-state release as that commit holds it. It returns the
release identifier, the recorded digests, the workload identity, and the chart
version, and it compares them with what an Application declares and with what an
applied object carries. It refuses a branch name: a name that can move is not an
identity.

See docs/environment/desired-state-provenance.md, which describes the record and
its limits, and tests/domain/test_desired_state_provenance.py, which resolves the
committed release and plants each defect the tool refuses.
"""

from .core import (
    CHART_LABEL,
    RECORD_SCHEMA,
    REPO_ROOT,
    RULES,
    VERSION_LABEL,
    WORKLOAD_LABEL,
    Finding,
    Provenance,
    ProvenanceRefused,
    ReconciliationSource,
    Rule,
    is_immutable_revision,
    metadata_findings,
    observed_revision_findings,
    resolve,
    source_findings,
)

__all__ = [
    "CHART_LABEL",
    "RECORD_SCHEMA",
    "REPO_ROOT",
    "RULES",
    "VERSION_LABEL",
    "WORKLOAD_LABEL",
    "Finding",
    "Provenance",
    "ProvenanceRefused",
    "ReconciliationSource",
    "Rule",
    "is_immutable_revision",
    "metadata_findings",
    "observed_revision_findings",
    "resolve",
    "source_findings",
]
