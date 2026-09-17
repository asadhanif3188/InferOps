"""What the dashboard is allowed to show, and the rules that decide it.

A dashboard is the easiest place in a repository to overstate a result. It
summarises, and a summary is where a status loses its provider, a level loses its
evidence class, and an absence turns green because nothing was written in the
cell. So this module owns no claim state of its own. It owns two things: which
claims belong to which capability group, and the rules that are applied to the
register before a page is rendered at all.

The selection is a view. It decides reading order and nothing else: a claim named
here is shown, a claim named nowhere is still counted, and every value printed
beside it comes from the register. That is why adding a capability group cannot
promote anything -- there is no field here to promote it with.

The rules are the other half. They are re-applied at render time rather than
trusted to the register's own suite, because the page is a separate artefact and a
register corrupted between the two would otherwise be published. A finding renders
nothing.
"""

from __future__ import annotations

import json
import posixpath
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

__all__ = [
    "CAPABILITIES",
    "DASHBOARD_DIR",
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
    "labels_by_id",
    "level_counts",
    "link_from_dashboard",
    "load_record",
    "provider_counts",
    "selection_findings",
    "status_counts",
    "statuses_by_id",
    "uncertified_claims",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The authoritative claim state. Nothing in this package writes to it.
RECORD_PATH: Final = (
    REPO_ROOT / "docs" / "testing" / "claim-evidence-matrix.v1alpha1.json"
)

#: The generated page, and the directory every link on it is resolved from.
DASHBOARD_PATH: Final = REPO_ROOT / "docs" / "proof" / "dashboard.md"
DASHBOARD_DIR: Final = "docs/proof"

#: The certification ladder, so a level can be compared with a label's ceiling.
#: ``none`` is a ceiling rather than a level: a label carrying it certifies nothing.
_LEVEL_RANK: Final[dict[str, int]] = {"none": -1, "C0": 0, "C1": 1, "C2": 2}


@dataclass(frozen=True)
class Capability:
    """One capability group, and the register rows a reviewer is shown for it.

    ``claim_ids`` is a selection out of the register. It carries no status, no
    level, and no evidence of its own, and a claim it names that the register does
    not hold is a refusal rather than an empty row.
    """

    capability_id: str
    name: str
    question: str
    claim_ids: tuple[str, ...]


@dataclass(frozen=True)
class Rule:
    """A rule the register has to satisfy before a page is rendered from it."""

    rule_id: str
    statement: str


@dataclass(frozen=True)
class Finding:
    """One refusal: the rule, what it was applied to, and what was wrong."""

    rule_id: str
    subject: str
    detail: str


#: The capability groups, in the order the page shows them. The first ten are the
#: ones a reviewer of this project asks about by name; the eleventh is how the
#: other ten are governed, and it is here because a proof page that does not say
#: who checks it is asking to be taken on trust.
CAPABILITIES: Final[tuple[Capability, ...]] = (
    Capability(
        capability_id="real-serving",
        name="Real serving",
        question="Has a real model ever answered a request through this API?",
        claim_ids=(
            "the-selected-model-serves-a-real-completion-through-the-inferops-api",
            "the-selected-runtime-serves-a-real-completion-in-a-cluster",
            "the-inference-api-serves-five-routes-with-explicit-adapter-selection",
            "a-mock-result-can-never-certify-real-runtime-behaviour",
        ),
    ),
    Capability(
        capability_id="kubernetes-deployment",
        name="Kubernetes deployment",
        question="Does a release install, serve, and leave without residue?",
        claim_ids=(
            "inferops-consumes-an-operator-owned-cluster-and-verifies-it-before-mutating",
            "a-helm-release-installs-and-uninstalls-without-residue",
            "a-local-cluster-is-created-and-removed-without-residue",
            "kubernetes-diagnosis-and-four-cleanup-radii-are-published-and-executed",
        ),
    ),
    Capability(
        capability_id="model-integrity",
        name="Model integrity",
        question="Is the artifact that gets loaded the artifact that was published?",
        claim_ids=(
            "the-model-artifact-matches-its-published-hash",
            "the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim",
            "a-runtime-and-model-pair-was-selected-by-a-recorded-feasibility-procedure",
            "the-model-lifecycle-states-were-measured-across-six-real-starts",
        ),
    ),
    Capability(
        capability_id="pod-recovery",
        name="Pod recovery",
        question="What does a caller see when the serving pod goes away?",
        claim_ids=(
            "caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load",
            "an-unready-model-was-held-unready-and-recovered-by-an-operator",
        ),
    ),
    Capability(
        capability_id="rollback-and-recovery",
        name="Rollback and release recovery",
        question="Can a bad release be taken back, with real inference restored?",
        claim_ids=(
            "a-controlled-release-change-can-be-reversed-and-real-inference-restored",
        ),
    ),
    Capability(
        capability_id="telemetry",
        name="Telemetry, dashboard, and alerts",
        question="What can be seen while it runs, and what reaches a person?",
        claim_ids=(
            "the-api-emits-catalog-metrics-and-structured-request-records",
            "a-release-scoped-collector-scrapes-both-inferops-jobs-on-the-reference-provider",
            "the-inference-operations-dashboard-was-asked-of-a-real-prometheus-and-rendered",
            "six-v1-alerts-carry-an-owner-a-severity-an-evidence-query-and-a-runbook-link",
            "the-v1-alerts-were-replayed-over-the-telemetry-three-real-experiments-recorded",
            "the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label",
            "an-alert-reaches-somebody",
        ),
    ),
    Capability(
        capability_id="performance-evidence",
        name="Performance evidence",
        question="What was measured under load, and what does it not mean?",
        claim_ids=(
            "repeatable-llm-load-can-be-generated-from-a-versioned-profile",
            "a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed",
            "a-local-serving-baseline-was-measured-under-a-method-registered-first",
            "sustained-throughput-and-capacity-under-load",
        ),
    ),
    Capability(
        capability_id="cost-method",
        name="Cost method",
        question="What does this project say a run costs?",
        claim_ids=(
            "the-cost-method-was-applied-to-use-taken-from-a-measured-run",
            "a-cost-figure-cannot-be-presented-as-a-bill",
            "what-running-an-inference-workload-costs-on-a-provider",
        ),
    ),
    Capability(
        capability_id="security-boundary",
        name="Security boundary",
        question="What is enforced, and what is only rendered?",
        claim_ids=(
            "a-security-control-cannot-claim-enforcement-it-does-not-have",
            "a-workload-manifest-that-omits-a-required-security-control-is-refused",
            "the-pinned-image-and-the-locked-dependencies-were-scanned-and-a-bill-of-materials-published",
            "the-rendered-network-policy-is-enforced-by-the-cluster",
            "a-deployed-inferops-workload-is-defended",
        ),
    ),
    Capability(
        capability_id="multi-replica",
        name="Multi-replica serving",
        question="Has more than one serving replica ever been certified?",
        claim_ids=("multi-replica-serving-is-certified",),
    ),
    Capability(
        capability_id="delivery-and-evidence",
        name="Tests, continuous integration, and evidence",
        question="Who checks the rows above, and where does the proof live?",
        claim_ids=(
            "eleven-default-lane-gates-are-committed-and-mapped-to-the-claims-they-defend",
            "the-default-lane-cannot-execute-a-real-model",
            "every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary",
            "published-documents-link-only-to-things-that-exist",
            "the-published-strategy-and-its-data-cannot-drift-apart",
            "a-cluster-or-real-runtime-lane-runs-in-continuous-integration",
        ),
    ),
)

#: The rules applied to the register before a page is rendered. Each names the
#: thing a dashboard does wrong when nobody is checking, and each is driven over a
#: register corrupted to break it in tests/testing/test_proof_dashboard.py.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        rule_id="a-capability-names-only-claims-the-register-holds",
        statement=(
            "Every claim identifier a capability group names exists in the "
            "register. A group naming an identifier the register does not hold "
            "would show a capability with no claim state behind it."
        ),
    ),
    Rule(
        rule_id="a-capability-group-shows-at-least-one-claim",
        statement=(
            "No capability group is empty. An empty group is a heading a reader "
            "reads as a capability with nothing said against it."
        ),
    ),
    Rule(
        rule_id="no-claim-is-shown-under-two-capabilities",
        statement=(
            "A claim appears in at most one capability group, so no result is "
            "read twice as though it were two."
        ),
    ),
    Rule(
        rule_id="a-certified-claim-cites-a-record-that-exists",
        statement=(
            "Every certified claim cites at least one committed record under the "
            "register's evidence root, each of which exists and is not a template."
        ),
    ),
    Rule(
        rule_id="a-planned-or-deferred-claim-cites-no-record",
        statement=(
            "A planned or deferred claim cites no evidence record. A claim nothing "
            "has proven that points at a record reads as proven."
        ),
    ),
    Rule(
        rule_id="an-evidence-label-is-one-the-register-defines",
        statement=(
            "Every evidence label shown is one the register's own evidence "
            "vocabulary defines. A label the register does not define carries no "
            "ceiling, so nothing could hold a level against it."
        ),
    ),
    Rule(
        rule_id="a-level-may-not-exceed-its-labels-ceiling",
        statement=(
            "A certification level never exceeds the ceiling its evidence label "
            "carries, so a mock result cannot be shown at C2."
        ),
    ),
    Rule(
        rule_id="a-real-behaviour-capability-rests-on-real-evidence",
        statement=(
            "A certified claim asserting real runtime behaviour rests on an "
            "evidence label whose class may support one. Mock, synthetic, and "
            "estimated evidence may not appear behind a real-runtime capability."
        ),
    ),
    Rule(
        rule_id="a-real-cluster-result-names-its-provider",
        statement=(
            "A certified claim whose environment is a local Kubernetes cluster "
            "names the provider it ran on, so the page cannot generalise one "
            "provider's result to another."
        ),
    ),
    Rule(
        rule_id="a-cell-value-fits-in-one-table-row",
        statement=(
            "No text the page prints into a table cell carries a line break. A "
            "pipe is escaped on the way in; a line break cannot be, and one would "
            "end the row and take the rest of the value out of the table."
        ),
    ),
    Rule(
        rule_id="a-displayed-status-is-one-the-register-defines",
        statement=(
            "Every status shown is one the register's own status vocabulary "
            "defines, and a status the register refuses to have published as a "
            "capability is never displayed as a certified one."
        ),
    ),
)


def load_record(path: Path = RECORD_PATH) -> dict[str, Any]:
    """The register, as committed. This package never writes it."""
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def claims_by_id(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["claimId"]: row for row in record["claims"]}


def statuses_by_id(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["statusId"]: row for row in record["claimStatuses"]}


def labels_by_id(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["labelId"]: row for row in record["evidenceLabels"]}


def link_from_dashboard(target: str) -> str:
    """A repository path, rewritten to resolve from the page's own directory.

    Every link check in this repository resolves a relative link from the
    directory of the file containing it, and the register stores repository-root
    paths. Rewriting them here is what keeps the generated page's links live.
    """
    return posixpath.relpath(target, DASHBOARD_DIR)


def _ordered_statuses(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The status vocabulary, strongest first, as the register ranks it."""
    return sorted(record["claimStatuses"], key=lambda row: -int(row["rank"]))


def status_counts(record: Mapping[str, Any]) -> dict[str, int]:
    """How many claims carry each status, strongest first.

    Counted over the whole register rather than over the groups below, so a claim
    no capability group shows is still in the denominator.
    """
    claims = record["claims"]
    return {
        status["statusId"]: sum(
            1 for row in claims if row["status"] == status["statusId"]
        )
        for status in _ordered_statuses(record)
    }


def level_counts(record: Mapping[str, Any]) -> dict[str, int]:
    """How many certified claims sit at each certification level, weakest first.

    Only certified claims are counted. A level beside a claim that is not
    certified is not a level anybody reached.
    """
    levels = [
        row["certificationLevel"]
        for row in record["claims"]
        if row["status"] == "certified" and row["certificationLevel"]
    ]
    return {
        level: levels.count(level)
        for level in sorted(set(levels), key=lambda name: _LEVEL_RANK.get(name, 99))
    }


def label_counts(record: Mapping[str, Any]) -> dict[str, int]:
    """How many claims rest on each evidence label, in the register's own order."""
    claims = record["claims"]
    counted = {
        label["labelId"]: sum(
            1 for row in claims if row["evidenceLabel"] == label["labelId"]
        )
        for label in record["evidenceLabels"]
    }
    return {label: count for label, count in counted.items() if count}


def provider_counts(record: Mapping[str, Any]) -> dict[str, int]:
    """How many claims name each provider, among the claims that name one.

    The claims that do not name a provider are not some other provider's results;
    they are results no provider produced, and counting them here would make the
    reference provider look like a minority of the evidence rather than all of it.
    """
    providers = [
        row["provider"]
        for row in record["claims"]
        if row["provider"] and row["provider"] != "not-applicable"
    ]
    return {provider: providers.count(provider) for provider in sorted(set(providers))}


def grouped_claims(
    record: Mapping[str, Any],
) -> list[tuple[Capability, list[dict[str, Any]]]]:
    """Each capability group with its rows, in the order the group names them."""
    known = claims_by_id(record)
    return [
        (
            capability,
            [known[claim_id] for claim_id in capability.claim_ids if claim_id in known],
        )
        for capability in CAPABILITIES
    ]


def uncertified_claims(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every claim that is not certified, in the register's own order.

    This list is derived rather than selected. A claim that stops being certified
    joins it without anybody adding it, which is the only way a page like this one
    can be trusted about what is missing.
    """
    return [row for row in record["claims"] if row["status"] != "certified"]


def _evidence_findings(
    record: Mapping[str, Any], row: Mapping[str, Any]
) -> list[Finding]:
    """The citation rules, applied to one row."""
    evidence_root = str(record["evidenceRoot"])
    template_root = str(record["templateRoot"])
    claim_id = str(row["claimId"])
    findings: list[Finding] = []

    if row["status"] == "certified":
        if not row["evidenceRefs"]:
            findings.append(
                Finding(
                    "a-certified-claim-cites-a-record-that-exists",
                    claim_id,
                    "certified and cites no record",
                )
            )
        for reference in row["evidenceRefs"]:
            if str(reference).startswith(f"{template_root}/"):
                findings.append(
                    Finding(
                        "a-certified-claim-cites-a-record-that-exists",
                        claim_id,
                        f"cites {reference}, which is a template rather than a record",
                    )
                )
            elif not str(reference).startswith(f"{evidence_root}/"):
                findings.append(
                    Finding(
                        "a-certified-claim-cites-a-record-that-exists",
                        claim_id,
                        f"cites {reference}, which is outside {evidence_root}/",
                    )
                )
            elif not (REPO_ROOT / str(reference)).exists():
                findings.append(
                    Finding(
                        "a-certified-claim-cites-a-record-that-exists",
                        claim_id,
                        f"cites {reference}, which does not exist",
                    )
                )
    elif row["status"] in ("planned", "deferred") and row["evidenceRefs"]:
        findings.append(
            Finding(
                "a-planned-or-deferred-claim-cites-no-record",
                claim_id,
                f"{row['status']} and cites {', '.join(row['evidenceRefs'])}",
            )
        )
    return findings


def _row_findings(
    record: Mapping[str, Any],
    row: Mapping[str, Any],
    statuses: Mapping[str, Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
) -> list[Finding]:
    """Every rule that reads one register row, applied to it."""
    claim_id = str(row["claimId"])
    status = str(row["status"])

    if status not in statuses:
        return [
            Finding(
                "a-displayed-status-is-one-the-register-defines",
                claim_id,
                f"carries status {status}, which the register does not define",
            )
        ]

    findings = _evidence_findings(record, row)

    label = labels.get(str(row["evidenceLabel"]))
    if label is None:
        findings.append(
            Finding(
                "an-evidence-label-is-one-the-register-defines",
                claim_id,
                f"carries label {row['evidenceLabel']}, which the register "
                "does not define",
            )
        )
        return findings

    level = row["certificationLevel"]
    if level is not None and _LEVEL_RANK.get(str(level), 99) > _LEVEL_RANK.get(
        str(label["ceiling"]), -1
    ):
        findings.append(
            Finding(
                "a-level-may-not-exceed-its-labels-ceiling",
                claim_id,
                f"{level} exceeds the {label['ceiling']} ceiling "
                f"{row['evidenceLabel']} carries",
            )
        )

    if status != "certified":
        return findings

    if not statuses[status]["mayBePublishedAsACapability"]:
        findings.append(
            Finding(
                "a-displayed-status-is-one-the-register-defines",
                claim_id,
                f"status {status} may not be published as a capability",
            )
        )

    if row["assertsRealBehaviour"] and not label["maySupportRealBehaviour"]:
        findings.append(
            Finding(
                "a-real-behaviour-capability-rests-on-real-evidence",
                claim_id,
                f"asserts real behaviour on {row['evidenceLabel']} evidence",
            )
        )

    if row["environment"] == "local-kubernetes" and (
        not row["provider"] or row["provider"] == "not-applicable"
    ):
        findings.append(
            Finding(
                "a-real-cluster-result-names-its-provider",
                claim_id,
                "ran on a local Kubernetes cluster and names no provider",
            )
        )

    return findings


def selection_findings(
    record: Mapping[str, Any],
    capabilities: Sequence[Capability] = CAPABILITIES,
) -> list[Finding]:
    """The rules that read the capability selection rather than the register.

    ``capabilities`` is a parameter rather than the module constant so that each
    of these three rules can be driven over a selection built to break it. A rule
    nobody has watched refuse anything is a sentence, not a control.
    """
    known = claims_by_id(record)
    findings: list[Finding] = []
    seen: dict[str, str] = {}

    for capability in capabilities:
        if not capability.claim_ids:
            findings.append(
                Finding(
                    "a-capability-group-shows-at-least-one-claim",
                    capability.capability_id,
                    "names no claim",
                )
            )
        for claim_id in capability.claim_ids:
            if claim_id not in known:
                findings.append(
                    Finding(
                        "a-capability-names-only-claims-the-register-holds",
                        capability.capability_id,
                        f"names {claim_id}, which the register does not hold",
                    )
                )
            if claim_id in seen:
                findings.append(
                    Finding(
                        "no-claim-is-shown-under-two-capabilities",
                        claim_id,
                        f"shown under {seen[claim_id]} and {capability.capability_id}",
                    )
                )
            else:
                seen[claim_id] = capability.capability_id

    return findings


#: Every register field the page prints into a table cell, by the collection it
#: belongs to. A field added to a cell and not added here is a field nothing
#: checks, which is why the renderer takes its cell text from nowhere else.
_CELL_FIELDS: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (
    ("claims", "claimId", ("statement", "limitation", "notClaimedReason")),
    ("claimStatuses", "statusId", ("meaning",)),
    ("evidenceLabels", "labelId", ("meaning",)),
)


def _cell_findings(record: Mapping[str, Any]) -> list[Finding]:
    """A line break inside a cell value would take the rest of it out of the table."""
    findings: list[Finding] = []
    for collection, identifier, fields in _CELL_FIELDS:
        for row in record[collection]:
            for field in fields:
                value = row.get(field)
                if isinstance(value, str) and ("\n" in value or "\r" in value):
                    findings.append(
                        Finding(
                            "a-cell-value-fits-in-one-table-row",
                            str(row[identifier]),
                            f"its {field} carries a line break",
                        )
                    )
    return findings


def check_view(
    record: Mapping[str, Any],
    capabilities: Sequence[Capability] = CAPABILITIES,
) -> list[Finding]:
    """Apply every rule to the register. An empty list is what lets a page render."""
    statuses = statuses_by_id(record)
    labels = labels_by_id(record)

    findings = selection_findings(record, capabilities)
    findings.extend(_cell_findings(record))
    for row in record["claims"]:
        findings.extend(_row_findings(record, row, statuses, labels))
    return findings
