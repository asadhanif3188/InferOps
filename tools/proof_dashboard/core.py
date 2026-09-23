"""What the dashboard is allowed to show, and the rules that decide it.

A dashboard is the easiest place in a repository to overstate a result. It
summarises, and a summary is where a status loses its provider, a level loses the
record that reached it, and an absence turns green because nothing was written in
the cell. So this module owns no claim state of its own. It owns two things: which
claims belong to which capability group, and the rules that are applied to the
register before a page is rendered at all.

The selection is a view. It decides reading order and nothing else: a claim named
here is shown, a claim named nowhere is still counted, and every value printed
beside it comes from the register. That is why adding a capability group cannot
promote anything -- there is no field here to promote it with.

The rules are the other half. They are re-applied at render time rather than
trusted to the register's own suite, because the page is a separate artefact and a
register corrupted between the two would otherwise be published. The evidence rules
are not restated here: the page runs the same schema and validator the register's
suite runs, from ``tools.evidence_model``, so there is one implementation of what a
record at each level must carry and the page cannot hold a looser one. A finding
renders nothing.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from tools.evidence_model import REGISTER_PATH, check_register, load_register

__all__ = [
    "CAPABILITIES",
    "DASHBOARD_DIR",
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
    "levels_by_id",
    "link_from_dashboard",
    "load_record",
    "named_providers",
    "provider_counts",
    "reclassified_claims",
    "record_providers",
    "selection_findings",
    "status_counts",
    "statuses_by_id",
    "strongest_level",
    "uncertified_claims",
    "unmigrated_records",
    "unrecorded_provider_records",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The authoritative claim state. Nothing in this package writes to it.
RECORD_PATH: Final = REGISTER_PATH

#: The generated page, and the directory every link on it is resolved from.
DASHBOARD_PATH: Final = REPO_ROOT / "docs" / "proof" / "dashboard.md"
DASHBOARD_DIR: Final = "docs/proof"

#: The five levels in the order the specification numbers them. The order is
#: closeness to the intended operating context, not strength -- the specification
#: says in as many words that C0-C4 is not a maturity score. It puts columns in a
#: readable order and names the level nearest production that a group's records
#: reached, and nothing on the page calls a higher one better.
LEVEL_ORDER: Final[tuple[str, ...]] = ("C0", "C1", "C2", "C3", "C4")

#: The register versions this module knows how to read. Since ``V1-S5-012-PR2``
#: that is ``v1alpha2`` alone: a level is a property of an evidence record and a
#: claim may hold several. A ``v1alpha1`` register -- one level and one label per
#: claim -- is refused rather than read, because this renderer would find no
#: records in it and print every claim as unevidenced, which is a quieter failure
#: than a refusal and a worse one.
SUPPORTED_CONTRACT_VERSIONS: Final[frozenset[str]] = frozenset({"inferops.io/v1alpha2"})


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


#: The capability groups, in the order the page shows them. The ten a reviewer of
#: this project asks about by name come first, with the clean-clone journey placed
#: after the two serving groups it repeats. Then the safe path, because a reviewer
#: who ran the mock quick start should be able to find what it did and did not
#: prove; then the two absences a reader expects most -- a release and a production
#: platform -- as a group of their own, so neither can be missed in a long
#: table; and last how the rest are governed, because a proof page that does not
#: say who checks it is asking to be taken on trust.
#:
#: Every claim the register holds is named by exactly one group. That is checked,
#: not assumed: a claim added to the register and named by no group is still counted
#: in every total and is still shown in the table of what V1 does not claim if it is
#: uncertified, and the page says how many certified claims it shows no row for.
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
            "local-runtime-diagnosis-is-machine-checked-against-the-records-it-quotes",
            "a-model-that-is-not-ready-is-a-canonical-error",
            "an-unreachable-runtime-is-a-canonical-error",
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
            "a-v1-operator-runbook-covers-every-incident-class-and-every-alert-links-into-it",
        ),
    ),
    Capability(
        capability_id="clean-clone-reproduction",
        name="Clean-clone reproduction",
        question="Can a reviewer walk the whole V1 journey from a fresh clone?",
        claim_ids=("a-reviewer-can-reproduce-v1-from-a-clean-clone",),
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
            "no-prompt-response-or-secret-reaches-a-log-or-a-metric",
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
            "no-credential-or-model-artifact-enters-public-history",
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
        capability_id="contracts-and-quick-start",
        name="Contracts, scaffolding, and the safe quick start",
        question="What does the mock path prove, and what does it never prove?",
        claim_ids=(
            "the-workload-contract-and-its-rejection-matrix-are-published",
            "an-invalid-workload-document-is-refused-with-a-published-reason",
            "the-workload-domain-parses-a-contract-document-into-typed-objects",
            "a-workload-scaffold-is-generated-without-overwriting-anything",
            "the-developer-quick-start-runs-end-to-end-on-a-clean-checkout",
            "the-mock-serving-path-identifies-itself-as-a-mock",
            "deployment-values-derive-only-from-a-validated-document",
            "the-platform-serves-a-workload-the-contract-describes",
        ),
    ),
    Capability(
        capability_id="release-and-production",
        name="Release and production use",
        question="Is there a release, and can somebody else run this in production?",
        claim_ids=(
            "a-v1-release-has-been-published",
            "inferops-is-a-portable-production-platform",
        ),
    ),
    Capability(
        capability_id="delivery-and-evidence",
        name="Ownership, tests, continuous integration, and evidence",
        question="Who owns each resource, who checks the rows above, and where does the proof live?",
        claim_ids=(
            "no-resource-in-the-architecture-has-two-owners",
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
        rule_id="a-register-declares-a-version-the-page-can-read",
        statement=(
            "The register declares a contract version this renderer implements. "
            "Every value below is read out of the v1alpha2 shape, where a level "
            "belongs to an evidence record; a register in another shape would be "
            "summarised against fields that are not there."
        ),
    ),
    Rule(
        rule_id="the-register-passes-the-evidence-level-rules",
        statement=(
            "The register passes the v1alpha2 schema and every validator rule in "
            "tools/evidence_model, applied again at render time with every cited "
            "file required to exist. That is what stops the page showing a record "
            "at a level its execution does not support, a mock behind a claim about "
            "real behaviour, a certified claim with no classified evidence, a "
            "planned claim citing a record, or a citation that is a template or "
            "does not exist."
        ),
    ),
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
        rule_id="a-real-cluster-result-names-its-provider",
        statement=(
            "An evidence record that ran on a Kubernetes cluster names the provider "
            "it ran on, or says in so many words that its source does not name one, "
            "so the page cannot generalise one provider's result to another or leave "
            "a reader to assume which."
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

#: Where a record ran is a cluster, for the provider rule.
_CLUSTER_ENVIRONMENTS: Final = frozenset({"local-kubernetes", "cloud-kubernetes"})

#: What a cluster record says when its source file never names the provider. It is
#: an honest absence rather than a provider, so it is shown and counted apart from
#: the providers and never folded into one of them.
UNRECORDED_PROVIDER: Final = "unrecorded"

#: Provider values that name no provider: nothing was contacted, or the record
#: does not say which.
_NO_PROVIDER: Final = frozenset({"", "not-applicable", UNRECORDED_PROVIDER})


def load_record(path: Path = RECORD_PATH) -> dict[str, Any]:
    """The register, as committed. This package never writes it."""
    return load_register(path)


def claims_by_id(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["claimId"]: row for row in record["claims"]}


def statuses_by_id(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["statusId"]: row for row in record["claimStatuses"]}


def levels_by_id(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["levelId"]: row for row in record["evidenceLevels"]}


def link_from_dashboard(target: str) -> str:
    """A repository path, rewritten to resolve from the page's own directory.

    Every link check in this repository resolves a relative link from the
    directory of the file containing it, and the register stores repository-root
    paths. Rewriting them here is what keeps the generated page's links live.
    """
    return posixpath.relpath(target, DASHBOARD_DIR)


def evidence_records(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every evidence record a claim holds, in the register's own order."""
    return list(row.get("evidenceRecords") or [])


def claim_levels(row: Mapping[str, Any]) -> list[str]:
    """The distinct levels a claim's records reached, in specification order.

    A record left ``legacy-unmigrated`` carries no level and contributes none: its
    superseded classification is history, and printing it here as a level would be
    the promotion the migration exists to prevent.
    """
    reached = {
        str(held["evidenceLevel"])
        for held in evidence_records(row)
        if held.get("evidenceLevel")
    }
    return [level for level in LEVEL_ORDER if level in reached]


def legacy_level(row: Mapping[str, Any]) -> str | None:
    """The superseded ``v1alpha1`` level the claim carried, if any. History only."""
    carried = row.get("legacyClassification") or {}
    level = carried.get("certificationLevel")
    return str(level) if level else None


def record_providers(row: Mapping[str, Any]) -> list[str]:
    """Every provider a claim's records name, sorted.

    ``not-applicable`` and ``unrecorded`` are left out: neither is a provider, and
    counting either as one would make the page name a provider nobody named.
    """
    return sorted(
        {
            str((held.get("environment") or {}).get("provider"))
            for held in evidence_records(row)
            if (held.get("environment") or {}).get("provider") not in _NO_PROVIDER
            and (held.get("environment") or {}).get("provider") is not None
        }
    )


def unrecorded_provider_records(record: Mapping[str, Any]) -> list[str]:
    """Every record that ran on a cluster its source file does not name."""
    return [
        str(held["recordId"])
        for row in record["claims"]
        for held in evidence_records(row)
        if (held.get("environment") or {}).get("provider") == UNRECORDED_PROVIDER
    ]


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


def level_counts(record: Mapping[str, Any]) -> dict[str, tuple[int, int]]:
    """For each of the five levels: records at it, and certified claims holding one.

    All five are returned, including the ones nothing reached, so that a zero is
    printed rather than a row left out. The second number counts only certified
    claims, because a level beside a claim that is not published as a capability is
    not a level the capability reached; the first counts every record, because a
    measured absence is still a record at a level.
    """
    claims = record["claims"]
    return {
        level: (
            sum(
                1
                for row in claims
                for held in evidence_records(row)
                if held.get("evidenceLevel") == level
            ),
            sum(
                1
                for row in claims
                if row["status"] == "certified" and level in claim_levels(row)
            ),
        )
        for level in LEVEL_ORDER
    }


def unmigrated_records(record: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Every record still ``legacy-unmigrated``, with the claim that holds it."""
    return [
        (str(row["claimId"]), held)
        for row in record["claims"]
        for held in evidence_records(row)
        if held.get("migrationState") == "legacy-unmigrated"
    ]


def environment_counts(record: Mapping[str, Any]) -> dict[tuple[str, str, str], int]:
    """How many records ran in each environment, provider, and hardware class."""
    counted: dict[tuple[str, str, str], int] = {}
    for row in record["claims"]:
        for held in evidence_records(row):
            environment = held.get("environment")
            if not environment:
                continue
            key = (
                str(environment["environmentId"]),
                str(environment["provider"]),
                str(environment["hardwareClass"]),
            )
            counted[key] = counted.get(key, 0) + 1
    return dict(sorted(counted.items()))


def provider_counts(record: Mapping[str, Any]) -> dict[str, tuple[int, int]]:
    """For each provider named: records naming it, and claims holding such a record.

    The records that name no provider are not some other provider's results; they
    are results no provider produced, and counting them here would make the
    reference provider look like a minority of the evidence rather than all of it.
    """
    claims = record["claims"]
    providers = sorted({name for row in claims for name in record_providers(row)})
    return {
        provider: (
            sum(
                1
                for row in claims
                for held in evidence_records(row)
                if (held.get("environment") or {}).get("provider") == provider
            ),
            sum(1 for row in claims if provider in record_providers(row)),
        )
        for provider in providers
    }


def strongest_level(rows: Sequence[Mapping[str, Any]]) -> str | None:
    """The last level, in specification order, any certified row's records reached.

    Only certified rows count, for the reason ``level_counts`` gives. ``None`` when
    no certified row holds a classified record, so a group of absences shows no
    level rather than a low one. The result is the level nearest the intended
    operating context that any record in the group reached; it says nothing about
    which record is better evidence for which claim.
    """
    reached = {
        level
        for row in rows
        if row["status"] == "certified"
        for level in claim_levels(row)
    }
    ordered = [level for level in LEVEL_ORDER if level in reached]
    return ordered[-1] if ordered else None


def named_providers(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Every provider the rows' records name, sorted, ``not-applicable`` left out.

    Counted over all of a group's rows and not only its certified ones: a
    ``not-claimed`` row whose record names the provider it was measured on is part
    of where the group's evidence came from.
    """
    return sorted({provider for row in rows for provider in record_providers(row)})


def reclassified_claims(
    record: Mapping[str, Any],
) -> list[tuple[dict[str, Any], str | None, list[str]]]:
    """Every claim whose records' levels differ from the level it carried before.

    Derived from the register alone: the claim's carried ``v1alpha1``
    classification against the levels its migrated records hold. A claim whose
    records all sit at the level it used to carry is not listed, and neither is a
    claim that carried no level and holds no classified record.
    """
    changed: list[tuple[dict[str, Any], str | None, list[str]]] = []
    for row in record["claims"]:
        before = legacy_level(row)
        after = claim_levels(row)
        if after and after != ([before] if before else []):
            changed.append((dict(row), before, after))
    return changed


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


def _evidence_rule_findings(record: Mapping[str, Any]) -> list[Finding]:
    """The register's own evidence rules, run again by the page that summarises it."""
    return [
        Finding(
            "the-register-passes-the-evidence-level-rules",
            refusal.path,
            f"{refusal.rule}: {refusal.message}",
        )
        for refusal in check_register(record, repo_root=REPO_ROOT)
    ]


def _provider_findings(record: Mapping[str, Any]) -> list[Finding]:
    """A cluster result that names no provider could be read as any provider's."""
    findings: list[Finding] = []
    for row in record["claims"]:
        for held in evidence_records(row):
            environment = held.get("environment") or {}
            if environment.get("environmentId") not in _CLUSTER_ENVIRONMENTS:
                continue
            if environment.get("provider") in (None, "", "not-applicable"):
                findings.append(
                    Finding(
                        "a-real-cluster-result-names-its-provider",
                        str(held.get("recordId", row["claimId"])),
                        f"ran on {environment['environmentId']} and names no provider",
                    )
                )
    return findings


def _status_findings(
    row: Mapping[str, Any], statuses: Mapping[str, Mapping[str, Any]]
) -> list[Finding]:
    """A status the register does not define, or may not publish, is not shown."""
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
    if status == "certified" and not statuses[status]["mayBePublishedAsACapability"]:
        return [
            Finding(
                "a-displayed-status-is-one-the-register-defines",
                claim_id,
                f"status {status} may not be published as a capability",
            )
        ]
    return []


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
    ("evidenceLevels", "levelId", ("name",)),
)


def _cell_values(record: Mapping[str, Any]) -> Iterator[tuple[str, str, Any]]:
    """Every value the page prints into a cell, with what it belongs to."""
    for collection, identifier, fields in _CELL_FIELDS:
        for row in record[collection]:
            for field in fields:
                yield str(row[identifier]), field, row.get(field)
    for row in record["claims"]:
        for held in evidence_records(row):
            subject = str(held.get("recordId", row["claimId"]))
            environment = held.get("environment") or {}
            for field in ("environmentId", "provider", "hardwareClass"):
                yield subject, f"environment.{field}", environment.get(field)
            execution = held.get("execution") or {}
            for substitution in execution.get("substitutions") or []:
                yield subject, "substitutions", substitution.get("componentId")


def _cell_findings(record: Mapping[str, Any]) -> list[Finding]:
    """A line break inside a cell value would take the rest of it out of the table."""
    return [
        Finding(
            "a-cell-value-fits-in-one-table-row",
            subject,
            f"its {field} carries a line break",
        )
        for subject, field, value in _cell_values(record)
        if isinstance(value, str) and ("\n" in value or "\r" in value)
    ]


def _version_findings(record: Mapping[str, Any]) -> list[Finding]:
    """The register says which shape it is, before anything reads a field of it."""
    declared = str(record.get("contractVersion", ""))
    if declared in SUPPORTED_CONTRACT_VERSIONS:
        return []
    return [
        Finding(
            "a-register-declares-a-version-the-page-can-read",
            declared or "no contractVersion",
            "is not a version this page implements; supported: "
            + ", ".join(sorted(SUPPORTED_CONTRACT_VERSIONS)),
        )
    ]


def check_view(
    record: Mapping[str, Any],
    capabilities: Sequence[Capability] = CAPABILITIES,
) -> list[Finding]:
    """Apply every rule to the register. An empty list is what lets a page render.

    The version check comes first and returns alone. A register in a shape this
    module does not implement would produce a page of findings about fields that
    are missing because they moved, and the one finding that explains all of them
    would be buried among them.
    """
    version = _version_findings(record)
    if version:
        return version

    statuses = statuses_by_id(record)
    findings = selection_findings(record, capabilities)
    findings.extend(_evidence_rule_findings(record))
    findings.extend(_provider_findings(record))
    findings.extend(_cell_findings(record))
    for row in record["claims"]:
        findings.extend(_status_findings(row, statuses))
    return findings
