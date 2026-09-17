"""The register, projected into one page a reviewer can read in a few minutes.

Nothing here decides a status. Every cell is a value read out of the register, a
count computed from it, or fixed prose that says the same thing whatever the
register holds. The page is regenerated and compared byte for byte, so an edit
made to it by hand is a failing check rather than a new claim.

Two shapes carry most of the page. A capability table shows the rows behind one
capability group with their level, evidence class, provider, environment, record,
and limitation side by side, because those are what a summary usually drops.
The table after them is the one that matters more: every claim this project does
**not** certify, derived from the register rather than selected, so an absence
cannot be left out of the page by leaving it out of a list.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final

from .core import (
    Capability,
    grouped_claims,
    label_counts,
    labels_by_id,
    level_counts,
    link_from_dashboard,
    provider_counts,
    status_counts,
    statuses_by_id,
    uncertified_claims,
)

__all__ = ["render_dashboard"]

#: Printed where a register field is null. A status with no certification level
#: has not reached one, and an em dash says that without inventing a value.
ABSENT: Final = "—"


def _cell(text: str) -> str:
    """One table cell. A pipe inside a value would end the cell early."""
    return text.replace("|", r"\|")


def _table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def _records(row: Mapping[str, Any]) -> str:
    """Every record a row cites, linked so the page can be walked into the proof."""
    if not row["evidenceRefs"]:
        if row["status"] in ("planned", "deferred"):
            return f"none, and a `{row['status']}` claim may cite none"
        return "none recorded"
    return ", ".join(
        f"[`{link_from_dashboard(str(reference))}`]({link_from_dashboard(str(reference))})"
        for reference in row["evidenceRefs"]
    )


def _scope(row: Mapping[str, Any]) -> str:
    """Where the result came from, with the provider kept beside the environment."""
    provider = str(row["provider"])
    environment = str(row["environment"])
    if provider == "not-applicable":
        return f"`{environment}`, no provider"
    return f"`{provider}`, `{environment}`"


def _capability_counts(rows: Sequence[Mapping[str, Any]]) -> str:
    """The group's own tally, in the register's status vocabulary."""
    order = ("certified", "planned", "deferred", "not-claimed")
    seen = [status for status in order if any(r["status"] == status for r in rows)]
    parts = [
        f"{sum(1 for r in rows if r['status'] == status)} `{status}`" for status in seen
    ]
    return "**Tally:** " + ", ".join(parts) + "."


def _heading(record: Mapping[str, Any]) -> list[str]:
    counts = status_counts(record)
    total = len(record["claims"])
    certified = counts.get("certified", 0)
    return [
        "# The V1 proof dashboard",
        "",
        "Status: **generated page**. It is produced by",
        "`python -m tools.proof_dashboard` from",
        "[the claim and evidence register](../testing/claim-evidence-matrix.v1alpha1.json),",
        "and [`tests/testing/test_proof_dashboard.py`](../../tests/testing/test_proof_dashboard.py)",
        "regenerates it and fails if the committed page and the register disagree.",
        "**Do not edit it by hand.** An edit here would be the only place in this",
        "repository where a capability status was asserted instead of derived, and it",
        "would survive exactly until the next check.",
        "",
        "This page answers one question: **what has this project actually proven?**",
        "It is not a monitoring view. What is happening inside a running release is",
        "[the inference operations dashboard](../telemetry/inference-operations-dashboard.md),",
        "which is asked of a Prometheus and shows nothing when nothing is running. This",
        "page reads committed files, says the same thing on every machine, and does not",
        "change when a cluster does.",
        "",
        f"**Certified: {certified} of {total} claims.** The remaining"
        f" {total - certified} are the rows worth",
        "reading, and they are listed in full under [what V1 does not",
        "claim](#what-v1-does-not-claim) rather than summarised away. Every number on",
        "this page is counted from the register at render time; there is no field",
        "anywhere in this tool that a count could be typed into.",
        "",
    ]


def _where_v1_stands(record: Mapping[str, Any]) -> list[str]:
    statuses = statuses_by_id(record)
    labels = labels_by_id(record)

    lines = [
        "## Where V1 stands",
        "",
        "Four states, and the difference between the last three is the difference",
        "between a promise, a decision, and a measured absence.",
        "",
    ]
    lines.extend(
        _table(
            ("Status", "Claims", "May be published as a capability", "What it means"),
            [
                (
                    f"`{status_id}`",
                    str(count),
                    "yes"
                    if statuses[status_id]["mayBePublishedAsACapability"]
                    else "no",
                    _cell(str(statuses[status_id]["meaning"])),
                )
                for status_id, count in status_counts(record).items()
            ],
        )
    )
    lines.extend(
        [
            "",
            "### The levels the certified claims reached",
            "",
            "A level says how strong a proof is, and it is not the same question as",
            "whether the claim may be published. The meanings are in",
            "[the certification document](../testing/certification.md).",
            "",
        ]
    )
    lines.extend(
        _table(
            ("Certification level", "Certified claims"),
            [
                (f"`{level}`", str(count))
                for level, count in level_counts(record).items()
            ],
        )
    )
    used = label_counts(record)
    silent = sum(
        1 for label_id in used if not labels[label_id]["maySupportRealBehaviour"]
    )
    lines.extend(
        [
            "",
            "### What the evidence behind them is",
            "",
            "The label decides the ceiling. A claim cannot be certified above what its",
            f"evidence class can support, and {silent} of the {len(used)} classes in use",
            "below can support no statement about real runtime behaviour at all.",
            "",
        ]
    )
    lines.extend(
        _table(
            (
                "Evidence label",
                "Claims",
                "Ceiling",
                "May support real runtime behaviour",
                "What it is",
            ),
            [
                (
                    f"`{label_id}`",
                    str(count),
                    f"`{labels[label_id]['ceiling']}`",
                    "yes" if labels[label_id]["maySupportRealBehaviour"] else "no",
                    _cell(str(labels[label_id]["meaning"])),
                )
                for label_id, count in used.items()
            ],
        )
    )

    providers = provider_counts(record)
    lines.extend(
        [
            "",
            "### Which provider the real results came from",
            "",
            "Only the claims that name a provider are counted here. The rest named none",
            "because no provider produced them, and folding those in would make the",
            "reference provider look like a minority of the evidence rather than all of",
            "it.",
            "",
        ]
    )
    lines.extend(
        _table(
            ("Provider", "Claims naming it"),
            [(f"`{provider}`", str(count)) for provider, count in providers.items()],
        )
    )
    lines.extend(
        [
            "",
            "A result on one provider certifies that provider. It does not certify",
            "another provider, a cloud cluster, a GPU, another host, another model,",
            "another runtime, or production, and no row on this page may be read as",
            "though it did. The providers themselves are published in",
            "[the local cluster provider contract](../environment/local-cluster-provider-contract.md).",
            "",
        ]
    )
    return lines


def _capability_section(
    capability: Capability, rows: Sequence[Mapping[str, Any]]
) -> list[str]:
    lines = [
        f"### {capability.name}",
        "",
        f"*{capability.question}*",
        "",
        _capability_counts(rows),
        "",
    ]
    lines.extend(
        _table(
            (
                "Claim",
                "Status",
                "Level",
                "Evidence class",
                "Provider and environment",
                "Record",
                "Limitation",
            ),
            [
                (
                    _cell(str(row["statement"])),
                    f"`{row['status']}`",
                    f"`{row['certificationLevel']}`"
                    if row["certificationLevel"]
                    else ABSENT,
                    f"`{row['evidenceLabel']}`",
                    _scope(row),
                    _records(row),
                    _cell(str(row["limitation"])),
                )
                for row in rows
            ],
        )
    )
    lines.append("")
    return lines


def _capabilities(record: Mapping[str, Any]) -> list[str]:
    lines = [
        "## The capabilities",
        "",
        "Each group is a question a reviewer asks, and the rows under it are the",
        "register's answer with the four things a summary usually loses kept beside",
        "each one: the level, the evidence class, the provider and environment, and",
        "the limitation that travels with the claim. A group's tally is counted from",
        "its own rows, and a group is never given a single colour, because a group",
        "holding one certified row and one measured absence is not one status.",
        "",
    ]
    for capability, rows in grouped_claims(record):
        lines.extend(_capability_section(capability, rows))
    return lines


def _not_claimed(record: Mapping[str, Any]) -> list[str]:
    rows = uncertified_claims(record)
    lines = [
        "## What V1 does not claim",
        "",
        f"{len(rows)} claims, derived from the register rather than listed here: a",
        "claim that stops being certified joins this table without anybody adding it.",
        "That is deliberate. A page that can only be complete about its successes is",
        "an advertisement.",
        "",
    ]
    lines.extend(
        _table(
            ("Claim", "Status", "Why it is not certified", "Record, where one exists"),
            [
                (
                    _cell(str(row["statement"])),
                    f"`{row['status']}`",
                    _cell(str(row["notClaimedReason"] or row["limitation"])),
                    _records(row),
                )
                for row in rows
            ],
        )
    )
    lines.append("")
    return lines


def _closing(record: Mapping[str, Any]) -> list[str]:
    grouped = {
        claim_id
        for capability, _ in grouped_claims(record)
        for claim_id in capability.claim_ids
    }
    # Certified and in no group is the only combination that appears nowhere as a
    # row: an uncertified claim in no group is still shown in the table above.
    unshown = sum(
        1
        for row in record["claims"]
        if row["status"] == "certified" and row["claimId"] not in grouped
    )
    return [
        "## What this page is not",
        "",
        "- **It is not a monitoring dashboard.** It reads committed files and asks",
        "  nothing of a cluster. The operations view is",
        "  [the inference operations dashboard](../telemetry/inference-operations-dashboard.md);",
        "  the two answer different questions and neither substitutes for the other.",
        "- **It is not a second source of truth.** Every status, level, label,",
        "  provider, environment, record, and limitation above is read from",
        "  [the register](../testing/claim-evidence-matrix.md) when the page is",
        "  generated. This tool holds one thing the register does not: which claims a",
        "  reviewer is shown under which heading.",
        "- **It is not a freshness or assurance signal.** Nothing here says when a",
        "  result was last re-run, whether the environment that produced it still",
        "  exists, or whether it would reproduce today. A record's own date and",
        "  provenance sections are the only answer to that, and they are in the record.",
        "- **It is not a release gate.** No check consumes this page to decide whether",
        "  anything may ship. The gates are in",
        "  [the continuous-integration gate matrix](../testing/ci-gate-matrix.md).",
        "",
        "## Limitations",
        "",
        "- The page inherits every limitation the register carries, including the",
        "  largest: the checks establish that references resolve, that ranks and",
        "  ceilings hold, and that the page and the register agree. None of them",
        "  establishes that a statement is true, or that a record says what the row",
        "  citing it says it says.",
        "- Every real result behind these rows was produced on one Windows host, by",
        "  one author, by hand. No outside party has reviewed a claim against its",
        "  evidence.",
        "- The capability grouping is a reading. Which claims belong under *model",
        "  integrity* rather than *real serving* is a judgement made in",
        "  `tools/proof_dashboard/core.py`, and no check decides it.",
        f"- **{unshown} certified claims appear on this page as a number only.** They",
        "  belong to no capability group, and a certified claim is not repeated in the",
        "  table of what V1 does not claim, so they are counted in every total above",
        "  and shown in no row. Every claim V1 does **not** certify is shown as a row",
        "  whether a group names it or not. A reader who wants all of them in one",
        "  table wants [the register](../testing/claim-evidence-matrix.md), which this",
        "  page is a view of rather than a replacement for.",
        "- The bounded performance, recovery, and cost figures quoted in these rows",
        "  are observations of declared local experiments under",
        "  [ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)",
        "  and",
        "  [ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md).",
        "  They are not capacity, service-level objectives, availability figures,",
        "  error budgets, recovery-time objectives, benchmarks, or costs.",
        "",
    ]


def render_dashboard(record: Mapping[str, Any]) -> str:
    """The whole page. The caller is expected to have applied the rules first."""
    lines: list[str] = []
    lines.extend(_heading(record))
    lines.extend(_where_v1_stands(record))
    lines.extend(_capabilities(record))
    lines.extend(_not_claimed(record))
    lines.extend(_closing(record))
    return "\n".join(lines).rstrip("\n") + "\n"
