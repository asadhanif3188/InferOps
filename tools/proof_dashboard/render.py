"""The register, projected into one page a reviewer can read in a few minutes.

Nothing here decides a status or a level. Every cell is a value read out of the
register, a count computed from it, or fixed prose that says the same thing whatever
the register holds. The page is regenerated and compared byte for byte, so an edit
made to it by hand is a failing check rather than a new claim.

Two shapes carry most of the page. A capability table shows the rows behind one
capability group with every evidence record each claim holds -- its level, where it
ran, what it substituted, and the files behind it -- beside the claim's status and
limitation, because those are what a summary usually drops. The table after them is
the one that matters more: every claim this project does **not** certify, derived
from the register rather than selected, so an absence cannot be left out of the page
by leaving it out of a list.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final

from .core import (
    LEVEL_ORDER,
    UNRECORDED_PROVIDER,
    Capability,
    environment_counts,
    evidence_records,
    grouped_claims,
    level_counts,
    levels_by_id,
    link_from_dashboard,
    named_providers,
    provider_counts,
    reclassified_claims,
    record_providers,
    status_counts,
    statuses_by_id,
    strongest_level,
    uncertified_claims,
    unmigrated_records,
    unrecorded_provider_records,
)

__all__ = ["anchor", "render_dashboard"]

#: Printed where there is nothing to print. A claim with no classified record has
#: not reached a level, and an em dash says that without inventing a value.
ABSENT: Final = "—"

#: Between two evidence records in one cell. A line break would end the table row;
#: an HTML break is rendered inside the cell by the hosting service.
RECORD_BREAK: Final = "<br>"

#: Where the reasons behind every level change are written down. A fixed path: the
#: page links it and the link suite resolves it.
MIGRATION_REPORT: Final = "testing/v1-s5-012-pr2-migration-report.md"


def _cell(text: str) -> str:
    """One table cell. A pipe inside a value would end the cell early."""
    return text.replace("|", r"\|")


def anchor(heading: str) -> str:
    """The fragment a Markdown renderer gives a heading, so the page can link itself.

    Lower case, punctuation dropped, spaces to hyphens: the rule GitHub applies,
    and the one every heading on this page is simple enough to satisfy. A heading
    this cannot slug is a heading the overview cannot link, and the suite drives
    every overview link back to a heading on the page.
    """
    kept = "".join(
        character
        for character in heading.lower()
        if character.isalnum() or character in " -"
    )
    return kept.replace(" ", "-")


def _table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def _links(references: Iterable[Any]) -> str:
    """Every file a record cites, linked so the page can be walked into the proof."""
    return ", ".join(
        f"[`{link_from_dashboard(str(reference))}`]({link_from_dashboard(str(reference))})"
        for reference in references
    )


def _where(held: Mapping[str, Any]) -> str:
    """Where one record ran, with the provider kept beside the environment."""
    environment = held["environment"]
    provider = str(environment["provider"])
    placed = f"`{environment['environmentId']}`"
    if provider == UNRECORDED_PROVIDER:
        placed += ", provider not named by its record"
    elif provider != "not-applicable":
        placed += f" on `{provider}`"
    hardware = str(environment["hardwareClass"])
    if hardware != "not-applicable":
        placed += f", `{hardware}`"
    return placed


def _substituted(held: Mapping[str, Any]) -> str:
    """What the record replaced, and whether the replacement was material."""
    substitutions = (held.get("execution") or {}).get("substitutions") or []
    if not substitutions:
        return ""
    return "substituted " + ", ".join(
        f"`{entry['componentId']}` ({entry['substituteKind']}"
        + (", claim-material)" if entry["claimMaterial"] else ")")
        for entry in substitutions
    )


def _record(held: Mapping[str, Any]) -> str:
    """One evidence record as one line of a cell."""
    if held.get("migrationState") != "migrated" or not held.get("evidenceLevel"):
        carried = (held.get("legacyClassification") or {}).get("certificationLevel")
        was = f", superseded `{carried}`" if carried else ""
        return f"legacy, not migrated{was} · {_links(held['evidenceRefs'])}"
    parts = [f"`{held['evidenceLevel']}`", _where(held)]
    workload = str((held.get("workload") or {}).get("source", "none"))
    if workload != "none":
        parts.append(f"workload `{workload}`")
    substituted = _substituted(held)
    if substituted:
        parts.append(substituted)
    parts.append(_links(held["evidenceRefs"]))
    return " · ".join(parts)


def _records(row: Mapping[str, Any]) -> str:
    """Every record a claim holds, one per line of the cell."""
    held = evidence_records(row)
    if not held:
        if row["status"] in ("planned", "deferred"):
            return f"none, and a `{row['status']}` claim may hold none"
        return "none recorded"
    return RECORD_BREAK.join(_record(entry) for entry in held)


def _capability_counts(rows: Sequence[Mapping[str, Any]]) -> str:
    """The group's own tally, in the register's status vocabulary."""
    order = ("certified", "planned", "deferred", "not-claimed")
    seen = [status for status in order if any(r["status"] == status for r in rows)]
    parts = [
        f"{sum(1 for r in rows if r['status'] == status)} `{status}`" for status in seen
    ]
    return "**Tally:** " + ", ".join(parts) + "."


def _record_total(record: Mapping[str, Any]) -> int:
    return sum(len(evidence_records(row)) for row in record["claims"])


def _heading(record: Mapping[str, Any]) -> list[str]:
    counts = status_counts(record)
    total = len(record["claims"])
    certified = counts.get("certified", 0)
    return [
        "# The V1 proof dashboard",
        "",
        "Status: **generated page**. It is produced by",
        "`python -m tools.proof_dashboard` from",
        "[the claim and evidence register](../testing/claim-evidence-matrix.v1alpha2.json),",
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
        "> [!IMPORTANT]",
        "> **A claim's status and an evidence level are different things.** The status",
        "> says whether this project publishes a property at all. A level belongs to",
        f"> one evidence record — {_record_total(record)} of them sit behind these claims — and",
        "> says only how that record was obtained. The levels `C0` to `C4` are",
        "> [InferOps Evidence Levels](../testing/evidence-levels.md): **project-defined,",
        "> and not an ISO, NIST, regulatory, or industry certification standard.** Nobody",
        "> outside this repository has reviewed a claim or a record on this page.",
        "",
        "## Five minutes, in order",
        "",
        "1. **Read the overview.** [The capabilities at a",
        "   glance](#the-capabilities-at-a-glance) is one row per capability: how many",
        "   of its claims are certified, planned, deferred, or not claimed, the",
        "   highest level any record behind a certified claim reached, and the",
        "   provider the real results came from.",
        "2. **Open the capability you came for.** Each row of the overview links to",
        "   its section under [the capabilities](#the-capabilities), where every claim",
        "   is shown with its status, every evidence record behind it — each with its",
        "   own level, where it ran, what it substituted, and its files — and the",
        "   limitation that travels with the claim.",
        "3. **Follow a record.** Every certified row links the committed records under",
        "   `docs/proof/` that support it. A record carries the commands, the",
        "   versions, the host, and what it does not establish; the row is a summary",
        "   of it and never more than it.",
        "4. **Read what is absent.** [What V1 does not claim](#what-v1-does-not-claim)",
        "   lists every claim that is not certified, derived from the register.",
        "5. **Read the boundary.** [Where V1 stands](#where-v1-stands) says what each",
        "   status and each level may and may not be read as, and",
        "   [what this page is not](#what-this-page-is-not) says what the page itself",
        "   cannot tell you.",
        "",
    ]


def _where_v1_stands(record: Mapping[str, Any]) -> list[str]:
    statuses = statuses_by_id(record)
    levels = levels_by_id(record)

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

    unmigrated = unmigrated_records(record)
    if unmigrated:
        unmigrated_note = [
            f"{len(unmigrated)} records are left `legacy-unmigrated` and carry no level:",
            "a fact the current shape requires could not be taken from the files they",
            "cite, and their superseded classification is kept as history rather than",
            "read as a level. They are counted in no row of this table.",
        ]
    else:
        unmigrated_note = [
            "Every record carries a level: none was left `legacy-unmigrated`.",
        ]
    lines.extend(
        [
            "",
            "### The levels the evidence records reached",
            "",
            "A level belongs to one evidence record and says how it was obtained:",
            "statically, with a component material to the claim substituted, or with",
            "the real components running. The definitions are in",
            "[the evidence-level specification](../testing/evidence-levels.md). A claim",
            "may hold several records at several levels, so the two columns count",
            "different things: records, and the certified claims holding at least one",
            "record at that level.",
            "",
        ]
    )
    counted = level_counts(record)
    lines.extend(
        _table(
            ("Evidence level", "Records", "Certified claims holding one", "Defined as"),
            [
                (
                    f"`{level}`",
                    str(counted[level][0]),
                    str(counted[level][1]),
                    # Cited with a link rather than bound in the second column: the
                    # specification is the one document allowed to define a level,
                    # and a test refuses a second table that binds the names.
                    f"[{_cell(str(levels[level]['name']))}]"
                    f"(../testing/evidence-levels.md#{anchor(level + ' — ' + str(levels[level]['name']))})",
                )
                for level in LEVEL_ORDER
            ],
        )
    )
    lines.extend(
        [
            "",
            *unmigrated_note,
            "",
            "**`C0` to `C4` is not a maturity score.** The numbering tracks closeness to",
            "the intended operating context, and a record with a higher number is not",
            "better evidence for every claim: a static check is the right evidence for",
            "a claim about a schema, and no runtime record would be. Nothing in this",
            "repository is `C3` or `C4`; `C4` needs organizational production, and",
            "there is none.",
            "",
            "### Where the records ran",
            "",
            "Two records at the same level in different environments are not",
            "interchangeable, so the environment is counted per record.",
            "",
        ]
    )
    lines.extend(
        _table(
            ("Environment", "Provider", "Hardware", "Records"),
            [
                (f"`{environment}`", f"`{provider}`", f"`{hardware}`", str(count))
                for (environment, provider, hardware), count in environment_counts(
                    record
                ).items()
            ],
        )
    )

    providers = provider_counts(record)
    lines.extend(
        [
            "",
            "### Which provider the real results came from",
            "",
            "Only the records that name a provider are counted here. The rest named",
            "none because no provider produced them, and folding those in would make",
            "the reference provider look like a minority of the evidence rather than",
            "all of it.",
            "",
        ]
    )
    lines.extend(
        _table(
            ("Provider", "Records naming it", "Claims holding one"),
            [
                (f"`{provider}`", str(records), str(claims))
                for provider, (records, claims) in providers.items()
            ],
        )
    )
    unrecorded = unrecorded_provider_records(record)
    if unrecorded:
        lines.extend(
            [
                "",
                f"{len(unrecorded)} records ran on a Kubernetes cluster whose source",
                "record never names the provider. They say `unrecorded` rather than",
                "borrowing a provider from a neighbouring record, and they are counted",
                "under no provider here.",
            ]
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
    lines.extend(_migration(record))
    return lines


def _migration(record: Mapping[str, Any]) -> list[str]:
    """Where a record's level differs from what its claim carried before.

    Derived from the register: every claim carries its superseded ``v1alpha1``
    classification, and this compares it with the levels the claim's records hold.
    """
    changed = reclassified_claims(record)
    carried = sum(
        1
        for row in record["claims"]
        if (row.get("legacyClassification") or {}).get("certificationLevel")
    )
    lines = [
        "### What the migration changed",
        "",
        "Until `V1-S5-012-PR2` the register stored one level per claim, under",
        "meanings ADR 0016 supersedes. Every claim still carries that value as",
        "history, and the levels on its records are the result of reading each",
        f"record against the current definitions. {carried} claims carried a level;",
        f"{len(changed)} claims now hold records at a level other than the one they",
        "carried, or hold a level where they carried none. They are listed here, and",
        f"[the migration report]({MIGRATION_REPORT}) says why each one moved.",
        "",
        "This table cannot show a status that moved, because a claim carries its",
        "superseded level and not its superseded status. The migration report lists",
        "every status the migration changed, with the measurement that required it.",
        "",
    ]
    lines.extend(
        _table(
            (
                "Claim",
                "Status",
                "Carried before (superseded meanings)",
                "Levels its records hold",
            ),
            [
                (
                    _cell(str(row["statement"])),
                    f"`{row['status']}`",
                    f"`{before}`" if before else "none",
                    ", ".join(f"`{level}`" for level in after),
                )
                for row, before, after in changed
            ],
        )
    )
    lines.append("")
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
            ("Claim", "Status", "Evidence records", "Limitation"),
            [
                (
                    _cell(str(row["statement"])),
                    f"`{row['status']}`",
                    _records(row),
                    _cell(str(row["limitation"])),
                )
                for row in rows
            ],
        )
    )
    lines.append("")
    return lines


def _overview(record: Mapping[str, Any]) -> list[str]:
    """One row per capability group, every value counted from the group's rows.

    This is the table a reviewer with five minutes reads, and so it is the table
    most tempted to carry a colour. It carries counts instead: a group is four
    numbers, not one status, and the level shown is reached only by records behind
    the group's certified rows.
    """
    grouped = grouped_claims(record)
    lines = [
        "## The capabilities at a glance",
        "",
        f"{len(grouped)} capability groups, each linking to its own section below.",
        "Every count is the group's own rows. *Highest level reached* is the",
        "highest-numbered level any record behind a certified row reached — the one",
        "nearest the intended operating context, which is not the same as the best",
        "evidence for any one claim — and a group with no certified row shows none. A",
        "provider is named only where a record names one, and a result on one",
        "provider certifies that provider alone.",
        "",
    ]
    rows: list[tuple[str, ...]] = []
    for capability, shown in grouped:
        tally = {
            status: sum(1 for row in shown if row["status"] == status)
            for status in ("certified", "planned", "deferred", "not-claimed")
        }
        level = strongest_level(shown)
        providers = named_providers(shown)
        rows.append(
            (
                f"[{capability.name}](#{anchor(capability.name)})",
                str(tally["certified"]),
                str(tally["planned"]),
                str(tally["deferred"]),
                str(tally["not-claimed"]),
                f"`{level}`" if level else ABSENT,
                ", ".join(f"`{provider}`" for provider in providers)
                if providers
                else "none named",
            )
        )
    lines.extend(
        _table(
            (
                "Capability",
                "Certified",
                "Planned",
                "Deferred",
                "Not claimed",
                "Highest level reached",
                "Provider named",
            ),
            rows,
        )
    )
    lines.append("")
    return lines


def _capabilities(record: Mapping[str, Any]) -> list[str]:
    lines = [
        "## The capabilities",
        "",
        "Each group is a question a reviewer asks, and the rows under it are the",
        "register's answer with what a summary usually loses kept beside each one:",
        "every evidence record the claim holds, with its level, the environment and",
        "provider it ran on, the workload's origin where one was issued, anything it",
        "substituted, and its files; and the limitation that travels with the claim.",
        "A group's tally is counted from its own rows, and a group is never given a",
        "single colour, because a group holding one certified row and one measured",
        "absence is not one status.",
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
        "an advertisement. A record beside a claim here is the measurement of an",
        "absence or a refusal, at the level that measurement was obtained; it is not a",
        "weaker form of the capability.",
        "",
    ]
    lines.extend(
        _table(
            (
                "Claim",
                "Status",
                "Why it is not certified",
                "Evidence records, where any exist",
            ),
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


def _fleet_sentence(record: Mapping[str, Any]) -> list[str]:
    """Whether any claim holds records from more than one provider, derived."""
    spanning = [row for row in record["claims"] if len(record_providers(row)) > 1]
    if spanning:
        return [
            f"- **Fleet and environment comparison.** {len(spanning)} claims hold",
            "  records from more than one provider, and the page lists them side by",
            "  side without comparing them. A page that compared the same claim across",
            "  providers, hosts, or clusters would need a method for doing so, and V1",
            "  publishes none.",
        ]
    return [
        "- **Fleet and environment comparison.** Every row names at most one",
        "  provider, and no claim here was run on two. A page that compared the same",
        "  claim across providers, hosts, or clusters would need that claim's result",
        "  from more than one of each, and V1 has no claim with more than one.",
    ]


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
    if unshown:
        shown_note = [
            f"- **{unshown} certified claims appear on this page as a number only.** They",
            "  belong to no capability group, and a certified claim is not repeated in the",
            "  table of what V1 does not claim, so they are counted in every total above",
            "  and shown in no row. Every claim V1 does **not** certify is shown as a row",
            "  whether a group names it or not. A reader who wants all of them in one",
            "  table wants [the register](../testing/claim-evidence-matrix.md), which this",
            "  page is a view of rather than a replacement for.",
        ]
    else:
        shown_note = [
            f"- **Every one of the {len(record['claims'])} claims is shown as a row.** Each",
            "  is named by exactly one capability group, so nothing on this page is",
            "  counted in a total and absent from every table. That is a property of the",
            "  grouping today, not a rule: a claim added to the register and named by no",
            "  group would still be counted in every total, would still appear under what",
            "  V1 does not claim if it were uncertified, and this sentence would change to",
            "  say how many certified claims had no row.",
        ]
    return [
        "## What this page is not",
        "",
        "- **It is not a monitoring dashboard.** It reads committed files and asks",
        "  nothing of a cluster. The operations view is",
        "  [the inference operations dashboard](../telemetry/inference-operations-dashboard.md);",
        "  the two answer different questions and neither substitutes for the other.",
        "- **Operations evidence is kept apart from it.** The Grafana screenshots in",
        "  [`telemetry/v1-s4-002-pr2-screenshots/`](telemetry/v1-s4-002-pr2-screenshots/)",
        "  and the record of",
        "  [the dashboard asked of a real Prometheus](telemetry/v1-s4-002-pr2-dashboard-validation.md)",
        "  are **operations evidence**: what a running release showed on one day, on",
        "  one host. The record is linked from the telemetry rows above and the",
        "  screenshots are linked from the record; neither is a proof state, and no",
        "  panel in them is a certification.",
        "- **It is not a second source of truth.** Every status, level, environment,",
        "  provider, substitution, record, and limitation above is read from",
        "  [the register](../testing/claim-evidence-matrix.md) when the page is",
        "  generated, and the register's own evidence rules are run again before a",
        "  page is produced. This tool holds one thing the register does not: which",
        "  claims a reviewer is shown under which heading.",
        "- **It is not an external certification.** The levels are project-defined,",
        "  and no outside party has reviewed the register, a record, or this page.",
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
        "  largest: the checks establish that references resolve, that every record",
        "  carries what its level requires and passes the evidence-level rules, and",
        "  that the page and the register agree. None of them establishes that a",
        "  statement is true, that a record says what the row citing it says it says,",
        "  or that a claim declared the right components material — those are review",
        "  judgements, listed in [the rule catalogue](../testing/evidence-level-rules.md).",
        "- Every real result behind these rows was produced on one Windows host, by",
        "  one author, by hand. No outside party has reviewed a claim against its",
        "  evidence.",
        "- The capability grouping is a reading. Which claims belong under *model",
        "  integrity* rather than *real serving* is a judgement made in",
        "  `tools/proof_dashboard/core.py`, and no check decides it.",
        *shown_note,
        "- The bounded performance, recovery, and cost figures quoted in these rows",
        "  are observations of declared local experiments under",
        "  [ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)",
        "  and",
        "  [ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md).",
        "  They are not capacity, service-level objectives, availability figures,",
        "  error budgets, recovery-time objectives, benchmarks, or costs.",
        "",
        "## What a later version of this page might do, and V1 does not",
        "",
        "These are features of an assurance dashboard in an organisation that runs",
        "many environments. None is built, none is planned for V1, none is a claim,",
        "and this list exists so that their absence is read as a decision rather than",
        "an oversight.",
        "",
        "- **Freshness and expiry.** Nothing here ages a result. A record from",
        "  2026-08 and one from 2026-09 are shown alike, and no row says when it would",
        "  stop being believed.",
        *_fleet_sentence(record),
        "- **Continuous verification.** No schedule re-runs a record and no lane",
        "  reports that a certified claim still holds; every real result is a run",
        "  somebody made by hand and wrote down.",
        "- **Promotion gates.** No check reads this page to decide whether a change,",
        "  a release, or an environment may advance. The gates that exist are in",
        "  [the continuous-integration gate matrix](../testing/ci-gate-matrix.md) and",
        "  none of them consumes a proof state.",
        "",
    ]


def render_dashboard(record: Mapping[str, Any]) -> str:
    """The whole page. The caller is expected to have applied the rules first."""
    lines: list[str] = []
    lines.extend(_heading(record))
    lines.extend(_overview(record))
    lines.extend(_where_v1_stands(record))
    lines.extend(_capabilities(record))
    lines.extend(_not_claimed(record))
    lines.extend(_closing(record))
    return "\n".join(lines).rstrip("\n") + "\n"
