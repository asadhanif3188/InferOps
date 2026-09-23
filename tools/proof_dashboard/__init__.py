"""The V1 proof dashboard: one reviewer-facing view over the claim register.

The register in ``docs/testing/claim-evidence-matrix.v1alpha2.json`` is the
authoritative claim state, and this package holds no second copy of it. What it
adds is a selection -- which claims a reviewer is shown first, grouped by the
capability they belong to -- and a projection of the register's own values into a
page. Every status, evidence record, level, environment, provider, substitution,
evidence path, and limitation the page prints is read from the register at render
time, and the register's own evidence rules are run again before a page is
produced, so the page cannot say more than the register does.

See docs/proof/dashboard.md, which this package generates, and
tests/testing/test_proof_dashboard.py, which regenerates it and refuses a
committed page that no longer matches.
"""

from .core import (
    CAPABILITIES,
    DASHBOARD_PATH,
    LEVEL_ORDER,
    RECORD_PATH,
    RULES,
    SUPPORTED_CONTRACT_VERSIONS,
    Capability,
    Finding,
    Rule,
    check_view,
    claim_levels,
    claims_by_id,
    environment_counts,
    evidence_records,
    grouped_claims,
    legacy_level,
    level_counts,
    load_record,
    named_providers,
    provider_counts,
    reclassified_claims,
    record_providers,
    selection_findings,
    status_counts,
    strongest_level,
    uncertified_claims,
    unmigrated_records,
    unrecorded_provider_records,
)
from .render import render_dashboard

__all__ = [
    "CAPABILITIES",
    "DASHBOARD_PATH",
    "LEVEL_ORDER",
    "RECORD_PATH",
    "RULES",
    "SUPPORTED_CONTRACT_VERSIONS",
    "Capability",
    "Finding",
    "Rule",
    "check_view",
    "claim_levels",
    "claims_by_id",
    "environment_counts",
    "evidence_records",
    "grouped_claims",
    "legacy_level",
    "level_counts",
    "load_record",
    "named_providers",
    "provider_counts",
    "reclassified_claims",
    "record_providers",
    "render_dashboard",
    "selection_findings",
    "status_counts",
    "strongest_level",
    "uncertified_claims",
    "unmigrated_records",
    "unrecorded_provider_records",
]
