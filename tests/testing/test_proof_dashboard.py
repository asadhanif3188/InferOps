"""Deterministic checks over the generated V1 proof dashboard.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness.

What this suite establishes is that the page cannot say anything the claim and
evidence register does not: that the committed page is byte for byte what the
register produces today, so an edit made to it by hand is a failing build; that
every count on it recomputes from the register rather than being read off the
page; that every statement, status, level, evidence label, provider, environment,
record, and limitation printed for a claim is the register's own value; that every
claim the register does not certify appears in the page's own list of what V1 does
not claim, so an absence cannot be dropped by leaving it out of a list; that every
record the page links resolves from the page's own directory; that every rule
the generator applies has been watched refusing a register, or a capability
selection, corrupted to break it; that the overview a reviewer reads first
recomputes from each group's own rows and links only headings the page carries;
and that the README's route into the page -- its link beside the strongest
evidence, the counts it quotes, the number of groups it names, and the records its
strongest-evidence table links -- agrees with the register rather than with the
day the README was written.

What it does not establish is that any statement on the page is true. It checks
derivation. Whether a record says what the row citing it says it says is a reading,
and the register carries that limitation for both documents.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tools.proof_dashboard import (
    CAPABILITIES,
    RULES,
    Capability,
    check_view,
    claims_by_id,
    grouped_claims,
    label_counts,
    level_counts,
    load_record,
    named_providers,
    provider_counts,
    render_dashboard,
    selection_findings,
    status_counts,
    strongest_level,
    uncertified_claims,
)
from tools.proof_dashboard.core import link_from_dashboard
from tools.proof_dashboard.render import anchor

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORD_PATH = REPO_ROOT / "docs" / "testing" / "claim-evidence-matrix.v1alpha1.json"
DASHBOARD_PATH = REPO_ROOT / "docs" / "proof" / "dashboard.md"
README_PATH = REPO_ROOT / "README.md"

RECORD: dict[str, Any] = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
CLAIMS: list[dict[str, Any]] = RECORD["claims"]
BY_ID = claims_by_id(RECORD)

# Read in text mode: a checkout that gave the page CRLF has not changed what it
# says, and the comparison below is of content.
PAGE = DASHBOARD_PATH.read_text(encoding="utf-8")


def _corrupt() -> dict[str, Any]:
    """A private copy of the register, for driving a rule over a broken one."""
    return copy.deepcopy(RECORD)


def _row(record: dict[str, Any], claim_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(
        row for row in record["claims"] if row["claimId"] == claim_id
    )
    return found


def _rule_ids(findings: list[Any]) -> set[str]:
    return {finding.rule_id for finding in findings}


# ------------------------------------------------- the page is what is generated


def test_the_committed_page_is_what_the_register_produces_today() -> None:
    """The one check the whole page rests on.

    A dashboard that is edited rather than regenerated is a second source of
    truth wearing the first one's name.
    """
    assert render_dashboard(RECORD) == PAGE, (
        "regenerate with: python -m tools.proof_dashboard --write"
    )


def test_the_register_satisfies_every_dashboard_rule() -> None:
    assert check_view(RECORD) == []


def test_the_page_says_it_is_generated_and_must_not_be_edited() -> None:
    assert "**generated page**" in PAGE
    assert "**Do not edit it by hand.**" in PAGE
    assert "python -m tools.proof_dashboard" in PAGE


def test_the_page_distinguishes_itself_from_the_operations_dashboard() -> None:
    """The two dashboards answer different questions and must say so.

    A proof page that reads like a monitoring page invites a reader to treat an
    empty panel as a failure and a green one as a certification.
    """
    assert "what has this project actually proven?" in PAGE
    assert "It is not a monitoring dashboard." in PAGE
    assert "../telemetry/inference-operations-dashboard.md" in PAGE


# ------------------------------------------------------------- counts, recomputed


def test_the_headline_count_is_the_register_count() -> None:
    certified = sum(1 for row in CLAIMS if row["status"] == "certified")
    assert f"**Certified: {certified} of {len(CLAIMS)} claims.**" in PAGE


@pytest.mark.parametrize(
    "status_id", [row["statusId"] for row in RECORD["claimStatuses"]]
)
def test_every_status_count_recomputes_from_the_register(status_id: str) -> None:
    counted = sum(1 for row in CLAIMS if row["status"] == status_id)
    assert status_counts(RECORD)[status_id] == counted
    assert f"| `{status_id}` | {counted} |" in PAGE


def test_the_status_table_carries_every_status_the_register_defines() -> None:
    """Four states, and dropping one is how a deferral becomes a silence."""
    assert set(status_counts(RECORD)) == {
        row["statusId"] for row in RECORD["claimStatuses"]
    }


def test_only_a_certified_claim_is_counted_at_a_certification_level() -> None:
    levels = level_counts(RECORD)
    for level, count in levels.items():
        assert count == sum(
            1
            for row in CLAIMS
            if row["status"] == "certified" and row["certificationLevel"] == level
        )
        assert f"| `{level}` | {count} |" in PAGE
    uncertified_levels = {
        row["certificationLevel"]
        for row in CLAIMS
        if row["status"] != "certified" and row["certificationLevel"]
    }
    assert not uncertified_levels, uncertified_levels


def test_every_evidence_label_count_recomputes_from_the_register() -> None:
    for label, count in label_counts(RECORD).items():
        assert count == sum(1 for row in CLAIMS if row["evidenceLabel"] == label)
        assert f"| `{label}` | {count} |" in PAGE


def test_the_provider_count_excludes_the_claims_that_name_no_provider() -> None:
    """Folding them in would shrink the reference provider's share of the evidence."""
    counts = provider_counts(RECORD)
    assert "not-applicable" not in counts
    for provider, count in counts.items():
        assert count == sum(1 for row in CLAIMS if row["provider"] == provider)
        assert f"| `{provider}` | {count} |" in PAGE


def test_the_page_refuses_to_generalise_one_provider_to_another() -> None:
    assert "A result on one provider certifies that provider." in PAGE
    assert "It does not certify" in PAGE
    assert "another provider, a cloud cluster, a GPU, another host" in PAGE


# --------------------------------------------- the rows are the register's values


def _section(heading: str) -> str:
    """The page text under one `###` heading, up to the next one.

    Scoped rather than whole-page, so a row rendered under the wrong capability
    would fail here rather than passing because its statement appears somewhere.
    """
    after = PAGE.split(f"### {heading}\n", 1)[1]
    return after.split("\n### ", 1)[0].split("\n## ", 1)[0]


@pytest.mark.parametrize(
    "capability", CAPABILITIES, ids=lambda capability: capability.capability_id
)
def test_every_capability_group_shows_the_registers_own_values(capability: Any) -> None:
    section = _section(capability.name)
    for claim_id in capability.claim_ids:
        row = BY_ID[claim_id]
        assert row["statement"].replace("|", r"\|") in section, claim_id
        assert row["limitation"].replace("|", r"\|") in section, claim_id
        assert f"`{row['evidenceLabel']}`" in section, claim_id
        assert f"`{row['status']}`" in section, claim_id
        if row["certificationLevel"]:
            assert f"`{row['certificationLevel']}`" in section, claim_id
        for reference in row["evidenceRefs"]:
            relative = link_from_dashboard(reference)
            assert f"[`{relative}`]({relative})" in section, reference


@pytest.mark.parametrize(
    "capability", CAPABILITIES, ids=lambda capability: capability.capability_id
)
def test_every_capability_group_tally_recomputes_from_its_rows(capability: Any) -> None:
    rows = dict(
        (group.capability_id, shown) for group, shown in grouped_claims(RECORD)
    )[capability.capability_id]
    parts = [
        f"{sum(1 for row in rows if row['status'] == status)} `{status}`"
        for status in ("certified", "planned", "deferred", "not-claimed")
        if any(row["status"] == status for row in rows)
    ]
    assert "**Tally:** " + ", ".join(parts) + "." in PAGE, capability.capability_id


def test_no_capability_group_is_given_a_single_status_of_its_own() -> None:
    """A group with one certified row and one measured absence is not one status.

    The generator has no field for a group status, and this is the check that
    would notice one being added: the only statuses the page prints are the
    register's own, beside a claim.
    """
    for capability in CAPABILITIES:
        heading = f"### {capability.name}\n"
        assert heading in PAGE, capability.name
        after = PAGE.split(heading, 1)[1].splitlines()
        # The three lines after a capability heading are blank, the question, blank.
        assert after[0] == ""
        assert after[1] == f"*{capability.question}*"
        assert after[2] == ""
        assert after[3].startswith("**Tally:** ")


def test_every_claim_the_register_does_not_certify_is_on_the_page() -> None:
    """Derived, not selected. This is what stops an absence being dropped."""
    missing = [
        row["claimId"]
        for row in uncertified_claims(RECORD)
        if row["statement"].replace("|", r"\|") not in PAGE
    ]
    assert not missing, {"not certified and absent from the page": missing}


def test_the_page_states_how_many_certified_claims_it_shows_no_row_for() -> None:
    """The number is the page's own gap, and it is derived rather than asserted.

    A certified claim in no capability group is counted in every total and
    appears in no table. Saying so is the difference between a summary and a
    selection nobody mentioned.
    """
    grouped = {
        claim_id for capability in CAPABILITIES for claim_id in capability.claim_ids
    }
    unshown = [
        row
        for row in CLAIMS
        if row["status"] == "certified" and row["claimId"] not in grouped
    ]
    if unshown:
        assert (
            f"**{len(unshown)} certified claims appear on this page as a number only.**"
            in PAGE
        )
    else:
        assert f"**Every one of the {len(CLAIMS)} claims is shown as a row.**" in PAGE
        assert "appear on this page as a number only" not in PAGE
    for row in unshown:
        assert row["statement"].replace("|", r"\|") not in PAGE, row["claimId"]


def test_every_claim_in_the_register_is_named_by_one_capability_group() -> None:
    """True today, and the sentence on the page that says so depends on it.

    This is a check on the grouping rather than a rule of the generator. A claim
    added to the register and named by no group would not corrupt the page -- it
    would be counted, and listed under what V1 does not claim if uncertified -- but
    a reviewer would be reading a page that shows fewer rows than it counts, and
    the release page is meant not to.
    """
    grouped = [
        claim_id for capability in CAPABILITIES for claim_id in capability.claim_ids
    ]
    ungrouped = sorted(set(BY_ID) - set(grouped))
    assert not ungrouped, {
        "in the register and in no capability group": ungrouped,
        "add each to a group in": "tools/proof_dashboard/core.py",
    }


def test_a_certified_claim_in_no_group_is_counted_aloud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other form of that sentence, rendered by taking a group away.

    The page has two things it can say here and only one of them is on the
    committed page, so the other is rendered from a selection with the clean-clone
    group removed: the claim stays in every total, leaves every capability table,
    and the page must say one certified claim is a number only.
    """
    from tools.proof_dashboard import render as render_module

    without = [
        (capability, rows)
        for capability, rows in grouped_claims(RECORD)
        if capability.capability_id != "clean-clone-reproduction"
    ]
    monkeypatch.setattr(render_module, "grouped_claims", lambda record: without)
    page = render_module.render_dashboard(RECORD)
    assert "**1 certified claims appear on this page as a number only.**" in page
    assert "is shown as a row.**" not in page
    assert "### Clean-clone reproduction\n" not in page
    certified = sum(1 for row in CLAIMS if row["status"] == "certified")
    assert f"**Certified: {certified} of {len(CLAIMS)} claims.**" in page


def test_the_not_claimed_section_counts_what_the_register_holds() -> None:
    count = sum(1 for row in CLAIMS if row["status"] != "certified")
    assert f"{count} claims, derived from the register" in PAGE


@pytest.mark.parametrize(
    "row",
    [row for row in CLAIMS if row["status"] != "certified"],
    ids=lambda row: row["claimId"],
)
def test_an_uncertified_claim_states_why_rather_than_showing_a_blank(
    row: dict[str, Any],
) -> None:
    reason = row["notClaimedReason"] or row["limitation"]
    assert reason
    assert reason.replace("|", r"\|") in PAGE


@pytest.mark.parametrize(
    "row",
    [row for row in CLAIMS if row["status"] == "certified"],
    ids=lambda row: row["claimId"],
)
def test_every_certified_claim_the_page_shows_links_a_record_that_resolves(
    row: dict[str, Any],
) -> None:
    if row["claimId"] not in {
        claim_id for capability in CAPABILITIES for claim_id in capability.claim_ids
    }:
        pytest.skip("shown in the register rather than on the page")
    assert row["evidenceRefs"], row["claimId"]
    for reference in row["evidenceRefs"]:
        relative = link_from_dashboard(reference)
        assert f"[`{relative}`]({relative})" in PAGE, reference
        assert (DASHBOARD_PATH.parent / relative).exists(), reference


def test_no_link_on_the_page_escapes_the_repository() -> None:
    for capability in CAPABILITIES:
        for claim_id in capability.claim_ids:
            for reference in BY_ID[claim_id]["evidenceRefs"]:
                assert not link_from_dashboard(reference).startswith("../.."), reference


# ------------------------------------------------- the selection cannot promote


def test_every_capability_names_a_claim_the_register_holds() -> None:
    unknown = sorted(
        claim_id
        for capability in CAPABILITIES
        for claim_id in capability.claim_ids
        if claim_id not in BY_ID
    )
    assert not unknown, {"named by a capability, absent from the register": unknown}


def test_no_claim_is_shown_under_two_capabilities() -> None:
    shown = [
        claim_id for capability in CAPABILITIES for claim_id in capability.claim_ids
    ]
    assert len(shown) == len(set(shown)), sorted(
        claim_id for claim_id in set(shown) if shown.count(claim_id) > 1
    )


def test_the_capabilities_the_story_names_are_all_present() -> None:
    """The ten a reviewer asks about by name, plus how they are governed."""
    assert {capability.capability_id for capability in CAPABILITIES} >= {
        "real-serving",
        "kubernetes-deployment",
        "model-integrity",
        "pod-recovery",
        "rollback-and-recovery",
        "telemetry",
        "performance-evidence",
        "cost-method",
        "security-boundary",
        "multi-replica",
    }


def test_the_multi_replica_capability_is_shown_as_not_claimed() -> None:
    """The one group whose only row is an absence, and it stays an absence.

    It is here because this is the exact promotion a dashboard makes by accident:
    a capability heading with nothing under it reads as a capability.
    """
    assert BY_ID["multi-replica-serving-is-certified"]["status"] == "not-claimed"
    assert "### Multi-replica serving\n" in PAGE
    assert "**Tally:** 1 `not-claimed`." in PAGE


# ----------------------------------------------- the rules, each driven over a break


def test_every_rule_is_stated_and_watched() -> None:
    """Each rule names a control here, and no two rules share one."""
    controls = {
        f"test_the_rule_refusing_{rule.rule_id.replace('-', '_')}" for rule in RULES
    }
    missing = sorted(name for name in controls if name not in globals())
    assert not missing, {"rules with no control in this suite": missing}
    assert len(controls) == len(RULES)


def test_the_rule_refusing_a_capability_names_only_claims_the_register_holds() -> None:
    invented = Capability(
        capability_id="invented",
        name="Invented",
        question="What does a group with no claim behind it look like?",
        claim_ids=("a-capability-nobody-has-registered",),
    )
    assert "a-capability-names-only-claims-the-register-holds" in _rule_ids(
        selection_findings(RECORD, [*CAPABILITIES, invented])
    )


def test_the_rule_refusing_a_capability_group_shows_at_least_one_claim() -> None:
    empty = Capability(
        capability_id="empty",
        name="Empty",
        question="What does a heading with nothing under it promise?",
        claim_ids=(),
    )
    assert "a-capability-group-shows-at-least-one-claim" in _rule_ids(
        selection_findings(RECORD, [*CAPABILITIES, empty])
    )


def test_the_rule_refusing_no_claim_is_shown_under_two_capabilities() -> None:
    repeated = Capability(
        capability_id="repeated",
        name="Repeated",
        question="What happens when one result is read twice?",
        claim_ids=(CAPABILITIES[0].claim_ids[0],),
    )
    assert "no-claim-is-shown-under-two-capabilities" in _rule_ids(
        selection_findings(RECORD, [*CAPABILITIES, repeated])
    )


@pytest.mark.parametrize(
    ("what", "citation"),
    [
        (
            "a template rather than a record",
            ["docs/proof/templates/TEMPLATE-claim-evidence.md"],
        ),
        ("nothing at all", []),
        ("a path outside the evidence root", ["docs/testing/claim-evidence-matrix.md"]),
        ("a record that does not exist", ["docs/proof/serving/a-run-nobody-made.md"]),
    ],
)
def test_the_rule_refusing_a_certified_claim_cites_a_record_that_exists(
    what: str, citation: list[str]
) -> None:
    """All four ways a citation fails, not the two that are easiest to write.

    A rule with four branches and two controls is two-thirds of a rule. The last
    two are the ones that would catch a typo'd path and a record somebody deleted
    — the failures a reader of the page could not possibly notice.
    """
    record = _corrupt()
    _row(record, "a-helm-release-installs-and-uninstalls-without-residue")[
        "evidenceRefs"
    ] = citation
    assert "a-certified-claim-cites-a-record-that-exists" in _rule_ids(
        check_view(record)
    ), what


def test_the_rule_refusing_a_planned_or_deferred_claim_cites_no_record() -> None:
    record = _corrupt()
    _row(record, "sustained-throughput-and-capacity-under-load")["evidenceRefs"] = [
        "docs/proof/serving/v1-s4-004-pr1-validation.md"
    ]
    assert "a-planned-or-deferred-claim-cites-no-record" in _rule_ids(
        check_view(record)
    )


def test_the_rule_refusing_an_evidence_label_is_one_the_register_defines() -> None:
    """A label the register does not define carries no ceiling to be held to.

    It had been reported under the ceiling rule's name, which made one rule look
    like it was watching two different failures. An independent review of this
    change found it.
    """
    record = _corrupt()
    _row(record, "multi-replica-serving-is-certified")["evidenceLabel"] = "field-proven"
    assert "an-evidence-label-is-one-the-register-defines" in _rule_ids(
        check_view(record)
    )


def test_the_rule_refusing_a_level_may_not_exceed_its_labels_ceiling() -> None:
    record = _corrupt()
    row = _row(
        record, "the-inference-api-serves-five-routes-with-explicit-adapter-selection"
    )
    assert row["evidenceLabel"] == "mock"
    row["certificationLevel"] = "C2"
    assert "a-level-may-not-exceed-its-labels-ceiling" in _rule_ids(check_view(record))


def test_the_rule_refusing_a_real_behaviour_capability_rests_on_real_evidence() -> None:
    """The rule that stops a mock appearing behind a serving sentence."""
    record = _corrupt()
    row = _row(
        record, "the-selected-model-serves-a-real-completion-through-the-inferops-api"
    )
    row["evidenceLabel"] = "mock"
    row["certificationLevel"] = "C1"
    assert "a-real-behaviour-capability-rests-on-real-evidence" in _rule_ids(
        check_view(record)
    )


def test_the_rule_refusing_a_real_cluster_result_names_its_provider() -> None:
    record = _corrupt()
    _row(record, "the-selected-runtime-serves-a-real-completion-in-a-cluster")[
        "provider"
    ] = "not-applicable"
    assert "a-real-cluster-result-names-its-provider" in _rule_ids(check_view(record))


def test_the_rule_refusing_a_cell_value_fits_in_one_table_row() -> None:
    """A pipe is escaped on the way into a cell; a line break cannot be.

    It has never happened, which is the argument for checking it rather than
    against: the day a limitation is written across two lines, the rest of it
    leaves the table and nobody reading the page can tell.
    """
    record = _corrupt()
    _row(record, "multi-replica-serving-is-certified")["limitation"] = (
        "The refusal is the evidence.\nIt is recorded in the paved-road record."
    )
    assert "a-cell-value-fits-in-one-table-row" in _rule_ids(check_view(record))

    meanings = _corrupt()
    meanings["evidenceLabels"][0]["meaning"] = (
        "A statement in a document.\nNothing ran."
    )
    assert "a-cell-value-fits-in-one-table-row" in _rule_ids(check_view(meanings))


def test_the_rule_refusing_a_displayed_status_is_one_the_register_defines() -> None:
    """Both halves of the rule, because both are ways a status stops meaning what it says."""
    invented = _corrupt()
    _row(invented, "multi-replica-serving-is-certified")["status"] = "shipped"
    assert "a-displayed-status-is-one-the-register-defines" in _rule_ids(
        check_view(invented)
    )

    # And the quieter half: the register keeping the name `certified` while
    # withdrawing its permission to publish. The page would go on showing rows.
    redefined = _corrupt()
    for status in redefined["claimStatuses"]:
        if status["statusId"] == "certified":
            status["mayBePublishedAsACapability"] = False
    assert "a-displayed-status-is-one-the-register-defines" in _rule_ids(
        check_view(redefined)
    )


def test_a_refused_register_renders_no_page(monkeypatch, capsys) -> None:
    """The ordering every mode depends on: rules first, page second.

    A page produced from a register that broke a rule is exactly where a broken
    rule stops being visible, so no mode may reach the renderer past a finding.
    """
    from tools.proof_dashboard import __main__ as command_line

    record = _corrupt()
    _row(record, "sustained-throughput-and-capacity-under-load")["status"] = "certified"
    assert "a-certified-claim-cites-a-record-that-exists" in _rule_ids(
        check_view(record)
    )

    monkeypatch.setattr(command_line, "load_record", lambda: record)
    for mode in ("--page", "--check", "--write"):
        assert command_line.main([mode]) == 1, mode
        printed = capsys.readouterr()
        assert "REFUSED" in printed.err
        assert "# The V1 proof dashboard" not in printed.out
    assert DASHBOARD_PATH.read_text(encoding="utf-8") == PAGE


def test_a_promoted_claim_changes_the_page_it_would_render() -> None:
    """Proof that the page is derived rather than described.

    If the register moved a claim from `not-claimed` to `certified`, a page that
    had been written by hand would not notice. This one does.
    """
    record = _corrupt()
    row = _row(record, "an-alert-reaches-somebody")
    row["status"] = "certified"
    row["certificationLevel"] = "C0"
    row["evidenceLabel"] = "local-static"
    row["assertsRealBehaviour"] = False
    row["environment"] = "repository-only"
    row["evidenceRefs"] = ["docs/proof/telemetry/v1-s4-008-pr1-alert-validation.md"]
    assert check_view(record) == []
    assert render_dashboard(record) != PAGE


# ------------------------------------------------ the overview a reviewer reads first


def _overview_rows() -> dict[str, list[str]]:
    """The at-a-glance table, as cells, keyed by the capability name it links."""
    section = PAGE.split("## The capabilities at a glance\n", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        if not line.startswith("| ["):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        name = cells[0].split("](", 1)[0].lstrip("[")
        rows[name] = cells
    return rows


def test_the_overview_has_one_row_for_every_capability_group() -> None:
    rows = _overview_rows()
    assert list(rows) == [capability.name for capability in CAPABILITIES]
    assert f"{len(CAPABILITIES)} capability groups, each linking" in PAGE


@pytest.mark.parametrize(
    "capability", CAPABILITIES, ids=lambda capability: capability.capability_id
)
def test_every_overview_row_recomputes_from_the_groups_own_rows(
    capability: Any,
) -> None:
    """Four counts, a level, and a provider, none of them typed in.

    The overview is the table a reviewer with five minutes reads and the rest of
    the page is the table behind it, so a disagreement between the two is the
    exact drift this page exists to refuse.
    """
    shown = [BY_ID[claim_id] for claim_id in capability.claim_ids]
    cells = _overview_rows()[capability.name]
    for position, status in enumerate(
        ("certified", "planned", "deferred", "not-claimed"), start=1
    ):
        assert cells[position] == str(
            sum(1 for row in shown if row["status"] == status)
        ), (capability.capability_id, status)

    certified_levels = [
        row["certificationLevel"] for row in shown if row["status"] == "certified"
    ]
    level = strongest_level(shown)
    if certified_levels:
        assert level == max(certified_levels, key=["C0", "C1", "C2"].index)
        assert cells[5] == f"`{level}`"
    else:
        assert level is None
        assert cells[5] == "—"

    providers = sorted(
        {row["provider"] for row in shown if row["provider"] != "not-applicable"}
    )
    assert named_providers(shown) == providers
    assert cells[6] == (
        ", ".join(f"`{provider}`" for provider in providers)
        if providers
        else "none named"
    )


def test_the_overview_counts_add_up_to_the_registers_totals() -> None:
    """Every claim is in one group, so the columns sum to the status table."""
    rows = _overview_rows().values()
    for position, status in enumerate(
        ("certified", "planned", "deferred", "not-claimed"), start=1
    ):
        assert sum(int(cells[position]) for cells in rows) == sum(
            1 for row in CLAIMS if row["status"] == status
        ), status


def test_no_group_without_a_certified_row_shows_a_level() -> None:
    """The promotion an overview makes by accident: a level beside an absence."""
    rows = _overview_rows()
    for capability in CAPABILITIES:
        shown = [BY_ID[claim_id] for claim_id in capability.claim_ids]
        if not any(row["status"] == "certified" for row in shown):
            assert rows[capability.name][5] == "—", capability.capability_id
    assert rows["Multi-replica serving"][1] == "0"
    assert rows["Release and production use"][1] == "0"


def test_every_link_the_page_makes_to_itself_lands_on_a_heading() -> None:
    """The overview and the route are navigation, and navigation can break.

    The document link suite skips fragments, so nothing else in the repository
    would notice a capability renamed out from under its own overview row.
    """
    headings = {
        anchor(line.lstrip("#").strip())
        for line in PAGE.splitlines()
        if line.startswith("#")
    }
    fragments = set(re.findall(r"\]\(#([^)]+)\)", PAGE))
    assert fragments >= {anchor(capability.name) for capability in CAPABILITIES}
    assert not fragments - headings, sorted(fragments - headings)


def test_the_page_opens_with_a_route_a_reviewer_can_follow() -> None:
    route = PAGE.split("## Five minutes, in order\n", 1)[1].split("\n## ", 1)[0]
    for fragment in (
        "#the-capabilities-at-a-glance",
        "#the-capabilities",
        "#what-v1-does-not-claim",
        "#where-v1-stands",
        "#what-this-page-is-not",
    ):
        assert f"]({fragment})" in " ".join(route.split()), fragment
    assert PAGE.index("## Five minutes, in order") < PAGE.index("## Where V1 stands")


def test_operations_evidence_is_labelled_and_kept_apart() -> None:
    """Grafana screenshots are what a release showed, not what a claim reached."""
    closing = PAGE.split("## What this page is not\n", 1)[1].split("\n## ", 1)[0]
    assert "**operations evidence**" in closing
    assert "neither is a proof state" in " ".join(closing.split())
    # The page says the record is linked from the telemetry rows, so it must be.
    telemetry = _section("Telemetry, dashboard, and alerts")
    assert "](telemetry/v1-s4-002-pr2-dashboard-validation.md)" in telemetry
    for target in (
        "telemetry/v1-s4-002-pr2-screenshots/",
        "telemetry/v1-s4-002-pr2-dashboard-validation.md",
    ):
        assert f"]({target})" in closing, target
        assert (DASHBOARD_PATH.parent / target).exists(), target


def test_later_assurance_features_are_listed_as_absent_and_not_as_planned() -> None:
    """Freshness, fleet comparison, continuous verification, promotion gates.

    They are named so that their absence reads as a decision. They must not read
    as a roadmap: the register is the only place a `planned` state comes from.
    """
    later = PAGE.split(
        "## What a later version of this page might do, and V1 does not\n", 1
    )[1]
    flat = " ".join(later.split())
    assert "None is built, none is planned for V1, none is a claim" in flat
    for feature in (
        "**Freshness and expiry.**",
        "**Fleet and environment comparison.**",
        "**Continuous verification.**",
        "**Promotion gates.**",
    ):
        assert feature in later, feature
    assert "`planned`" not in later
    assert "`certified`" not in later


def test_the_fixed_prose_never_claims_a_single_provider() -> None:
    """The first draft of this section did, two headings under a table naming two.

    An independent review of this change found the page saying "One provider, one
    host, one column" while its own overview listed `docker-desktop` and `kind`.
    The check is scoped to the page's own fixed prose: a register row saying "One
    provider, `docker-desktop`" is that result's true scope and must stay.
    """
    assert len(provider_counts(RECORD)) > 1, "the premise of this check has changed"
    later = PAGE.split("## What a later version of this page might do", 1)[1]
    flat = " ".join(later.split())
    assert "one provider, one host" not in flat.lower()
    assert "Every row names at most one provider" in flat
    assert "no claim with more than one" in flat


#: What the hosting service makes of each heading the page links, written out by
#: hand from its published rule rather than produced by `anchor`. Without this the
#: fragment check below compares `anchor` with itself, which an independent review
#: of this change pointed out: a wrong slug rule would be wrong on both sides.
HOSTED_SLUGS = {
    "Five minutes, in order": "five-minutes-in-order",
    "The capabilities at a glance": "the-capabilities-at-a-glance",
    "Where V1 stands": "where-v1-stands",
    "The capabilities": "the-capabilities",
    "What V1 does not claim": "what-v1-does-not-claim",
    "What this page is not": "what-this-page-is-not",
    "Real serving": "real-serving",
    "Kubernetes deployment": "kubernetes-deployment",
    "Clean-clone reproduction": "clean-clone-reproduction",
    "Model integrity": "model-integrity",
    "Pod recovery": "pod-recovery",
    "Rollback and release recovery": "rollback-and-release-recovery",
    "Telemetry, dashboard, and alerts": "telemetry-dashboard-and-alerts",
    "Performance evidence": "performance-evidence",
    "Cost method": "cost-method",
    "Security boundary": "security-boundary",
    "Multi-replica serving": "multi-replica-serving",
    "Contracts, scaffolding, and the safe quick start": (
        "contracts-scaffolding-and-the-safe-quick-start"
    ),
    "Release and production use": "release-and-production-use",
    "Ownership, tests, continuous integration, and evidence": (
        "ownership-tests-continuous-integration-and-evidence"
    ),
}


def test_the_slug_rule_agrees_with_slugs_written_out_by_hand() -> None:
    for heading, slug in HOSTED_SLUGS.items():
        assert anchor(heading) == slug, heading
        assert f"# {heading}\n" in PAGE, heading
    linked = set(re.findall(r"\]\(#([^)]+)\)", PAGE))
    assert linked <= set(HOSTED_SLUGS.values()), sorted(
        linked - set(HOSTED_SLUGS.values())
    )
    assert {capability.name for capability in CAPABILITIES} <= set(HOSTED_SLUGS)


# --------------------------------------------- the README's route into the page

README = README_PATH.read_text(encoding="utf-8")
README_FLAT = " ".join(README.split())

NUMBER_WORDS = {
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
}


def _readme_section(heading: str) -> str:
    return README.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def test_the_readme_links_the_page_beside_its_strongest_evidence() -> None:
    """The acceptance criterion, as a check: a direct path, where the proof is."""
    assert "](docs/proof/dashboard.md)" in _readme_section("What V1 proves")
    assert "](docs/proof/dashboard.md)" in _readme_section("Five minutes, in order")
    assert (REPO_ROOT / "docs" / "proof" / "dashboard.md").exists()


def test_the_counts_the_readme_quotes_are_the_registers() -> None:
    """The one sentence in the README that restates the page's totals.

    Digits in prose are what drifts in this repository. The register moved from 41
    certified to 42 when the clean-clone run was certified, and nothing but a
    reader would have noticed the README still saying 41.
    """
    counts = status_counts(RECORD)
    sentence = (
        f"{len(CLAIMS)} claims, {counts['certified']} certified, "
        f"{counts['planned']} planned, {counts['deferred']} deferred, and "
        f"{counts['not-claimed']} that V1 states it does not have"
    )
    assert sentence in README_FLAT, sentence


def test_the_readme_names_the_number_of_capability_groups_the_page_has() -> None:
    written = NUMBER_WORDS[len(CAPABILITIES)]
    assert f"{written} capability groups" in README_FLAT, written
    others = [
        word
        for word in NUMBER_WORDS.values()
        if word != written and f"{word} capability groups" in README_FLAT
    ]
    assert not others, others


def _strongest_evidence_records() -> list[str]:
    """Every repository record the README's strongest-evidence table links."""
    table = [
        line
        for line in _readme_section("What V1 proves").splitlines()
        if line.startswith("| ") and "](docs/proof/" in line
    ]
    return sorted(
        {
            target
            for line in table
            for target in re.findall(r"\]\((docs/proof/[^)#]+)", line)
        }
    )


def test_the_readme_strongest_evidence_table_links_records() -> None:
    """Pinned, not bounded. The first draft asked for "at least eight".

    Nine rows, nine records. A row added to or taken out of the README's first
    table has to change this number on purpose, which is the only way the
    validation record's "nine" and the table can be kept in step.
    """
    assert len(_strongest_evidence_records()) == 9, _strongest_evidence_records()


@pytest.mark.parametrize("record_path", _strongest_evidence_records())
def test_every_record_the_readme_leads_with_is_cited_by_a_certified_claim(
    record_path: str,
) -> None:
    """A row on the README's first screen resolves to a claim on the page.

    The README's table is written by hand, which is the point of checking it: a
    record linked there that no certified claim cites would be a capability shown
    to a reviewer with no claim state behind it, in the one place the generator
    cannot reach.
    """
    assert (REPO_ROOT / record_path).exists(), record_path
    citing = [
        row["claimId"]
        for row in CLAIMS
        if row["status"] == "certified" and record_path in row["evidenceRefs"]
    ]
    assert citing, {
        "linked from the README and cited by no certified claim": record_path
    }
    relative = link_from_dashboard(record_path)
    assert f"]({relative})" in PAGE, record_path


def test_the_readme_does_not_lead_with_a_template_or_an_uncommitted_record() -> None:
    for record_path in _strongest_evidence_records():
        assert not record_path.startswith(f"{RECORD['templateRoot']}/"), record_path
        assert record_path.startswith(f"{RECORD['evidenceRoot']}/"), record_path


# ------------------------------------------------- the command line agrees with it


def test_the_command_line_reports_the_committed_page_as_current() -> None:
    finished = subprocess.run(
        [sys.executable, "-m", "tools.proof_dashboard", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "OK" in finished.stdout


def test_printing_the_page_reproduces_the_committed_file_byte_for_byte() -> None:
    """`--page` is meant to be comparable with the file, so its bytes are pinned.

    Left to the platform, a Windows console hands the printed page back in
    CP-1252 with CRLF endings: every em dash in the register becomes a
    replacement byte and every line ending becomes a diff. An independent review
    of this change found the repository claiming otherwise, which is what this
    check now settles rather than asserts.
    """
    finished = subprocess.run(
        [sys.executable, "-m", "tools.proof_dashboard", "--page"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr.decode("utf-8", "replace")
    assert b"\r\n" not in finished.stdout, "the printed page carries CRLF"
    assert finished.stdout.decode("utf-8") == PAGE, "the printed page is not the file"
    assert finished.stdout == DASHBOARD_PATH.read_bytes(), (
        "the committed page is not LF; `.gitattributes` pins it and this checkout "
        "did not honour that"
    )


def test_the_command_line_applies_the_rules_and_exits_zero() -> None:
    finished = subprocess.run(
        [sys.executable, "-m", "tools.proof_dashboard", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert json.loads(finished.stdout) == []


def test_the_page_is_reachable_from_the_evidence_index() -> None:
    """A dashboard nobody can find from docs/proof/ is a file, not an entry point."""
    index = (REPO_ROOT / "docs" / "proof" / "README.md").read_text(encoding="utf-8")
    assert "dashboard.md" in index


def test_the_record_the_page_reads_is_the_registers_own_file() -> None:
    assert load_record() == RECORD
