"""The V1 proof dashboard: one reviewer-facing view over the claim register.

The register in ``docs/testing/claim-evidence-matrix.v1alpha1.json`` is the
authoritative claim state, and this package holds no second copy of it. What it
adds is a selection -- which claims a reviewer is shown first, grouped by the
capability they belong to -- and a projection of the register's own values into a
page. Every status, certification level, evidence label, provider, environment,
evidence path, and limitation the page prints is read from the register at render
time, so the page cannot say more than the register does.

See docs/proof/dashboard.md, which this package generates, and
tests/testing/test_proof_dashboard.py, which regenerates it and refuses a
committed page that no longer matches.
"""

from .core import (
    CAPABILITIES,
    DASHBOARD_PATH,
    RECORD_PATH,
    RULES,
    Capability,
    Finding,
    Rule,
    check_view,
    claims_by_id,
    grouped_claims,
    label_counts,
    level_counts,
    load_record,
    provider_counts,
    selection_findings,
    status_counts,
    uncertified_claims,
)
from .render import render_dashboard

__all__ = [
    "CAPABILITIES",
    "DASHBOARD_PATH",
    "RECORD_PATH",
    "RULES",
    "Capability",
    "Finding",
    "Rule",
    "check_view",
    "claims_by_id",
    "grouped_claims",
    "label_counts",
    "level_counts",
    "load_record",
    "provider_counts",
    "render_dashboard",
    "selection_findings",
    "status_counts",
    "uncertified_claims",
]
