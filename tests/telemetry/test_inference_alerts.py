"""The V1 alert record, its policy, its scenarios, and the rule files it renders.

Five things have to agree:

- `docs/telemetry/inference-alerts.v1alpha1.json`, the record;
- `docs/telemetry/inference-alerts.md`, the document that publishes it;
- `docs/telemetry/telemetry-catalog.v1alpha1.json`, whose emitted metrics are the
  only signals an alert may claim to observe;
- `tests/telemetry/fixtures/alerts/`, the eight scenarios every alert is driven
  across instant by instant;
- `deploy/prometheus/inferops-inference-alerts.{mock,real}.yaml`, generated from the
  record and compared byte for byte.

The property this defends is the one the alert set exists for: **every alert fires
for something an operator can act on, and nothing else fires at all.** So every
alert is held to the correlation query policy, every rule the alert policy adds is
driven over a record corrupted to break it, and every alert is evaluated across
every committed scenario -- including one in which a single scrape interval's worth
of refusals must not page anybody, and one in which the API is not discovered and
every workload alert must go quiet for a reason the collection alert names.

**None of this establishes that a Prometheus has evaluated these rules, that an
alert has ever fired outside this evaluator, or that anybody would be told.** No
receiver, routing tree, or on-call rotation is selected. Every check here reads a
file.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.telemetry.registry import REQUEST_DURATION_BUCKETS
from tools.inference_alerts import (
    ALERT_RECORD_PATH,
    FIXTURE_DIR,
    GROUP_NAME,
    RENDER_PATHS,
    RULE_IDS,
    check_alerts,
    evaluate_alerts,
    firing_instants,
    load_alert_record,
    render_rules,
    runbook_anchors,
    serialise,
)
from tools.telemetry_correlation import (
    SAFE_MESSAGE_CHARACTERS,
    load_fixture,
    metrics_read,
    not_emitted_metric_names,
    parse,
    permitted_query_labels,
    recorded_series_names,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORD = load_alert_record()
DOCUMENT = (REPO_ROOT / RECORD["documentRef"]).read_text(encoding="utf-8")
ALERTS: dict[str, dict[str, Any]] = {
    alert["alertId"]: alert for alert in RECORD["alerts"]
}
SCENARIOS: dict[str, str] = {
    scenario["scenarioId"]: scenario["profile"] for scenario in RECORD["scenarios"]
}
FIXTURES = {
    scenario: load_fixture(FIXTURE_DIR / f"{scenario}.yaml") for scenario in SCENARIOS
}
FIRING: dict[str, dict[str, bool]] = {
    scenario: {
        alert_id: bool(firing_instants(alert, FIXTURES[scenario]))
        for alert_id, alert in ALERTS.items()
        if SCENARIOS[scenario] in (alert.get("profiles") or ["mock", "real"])
    }
    for scenario in SCENARIOS
}


# --------------------------------------------------------------------------
# The record, and what it says about itself
# --------------------------------------------------------------------------


def test_the_record_declares_its_identity_and_contract_version() -> None:
    assert (
        RECORD["$id"] == "https://inferops.io/telemetry/inference-alerts.v1alpha1.json"
    )
    assert RECORD["contractVersion"] == "inferops.io/v1alpha1"


def test_every_reference_the_record_makes_resolves() -> None:
    references = [
        RECORD[key]
        for key in (
            "decisionRef",
            "documentRef",
            "catalogRef",
            "queryRecordRef",
            "collectionRef",
            "dashboardRecordRef",
            "chartRef",
            "fixtureDir",
            "evidenceRef",
        )
    ]
    references += list(RECORD["renderRefs"].values())
    references += [scenario["fixtureRef"] for scenario in RECORD["scenarios"]]
    references += [
        reference for alert in RECORD["alerts"] for reference in alert["evidenceRefs"]
    ]
    references += [
        reference
        for entry in RECORD["deferredAlerts"]
        for reference in entry["evidenceRefs"]
    ]
    references += [
        scenario["shapedFrom"]
        for scenario in RECORD["scenarios"]
        if scenario.get("shapedFrom")
    ]
    for reference in references:
        assert (REPO_ROOT / reference).exists(), reference


def test_the_committed_record_satisfies_the_alert_policy() -> None:
    assert check_alerts(RECORD) == []


def test_the_record_claims_no_routing_and_no_evaluation_by_a_prometheus() -> None:
    """The one claim this record could make and must not.

    A rule file that has never been loaded, by a collector that has never been
    told where to send anything, is not an alerting system. The record says so in
    a field rather than in a sentence somebody could edit past.
    """
    routing = RECORD["routing"]
    assert routing["receiver"] is None
    assert routing["routingTree"] is None
    assert routing["onCall"] is None
    assert routing["alertmanager"] is None
    status = RECORD["verificationStatus"]
    assert status["evaluatedByAPrometheus"] is False
    assert status["everRouted"] is False
    assert status["everNotifiedAnybody"] is False
    assert status["policyChecked"] is True
    assert status["evaluatedAgainstFixtures"] is True


def test_the_published_counts_are_the_counts_the_record_has() -> None:
    """The document publishes numbers. A number nobody recomputes goes stale."""
    words = {5: "five", 6: "six", 8: "eight", 12: "twelve"}
    assert f"{words[len(RECORD['alerts'])]} alerts" in DOCUMENT.lower()
    assert f"{words[len(RECORD['deferredAlerts'])]} deferred" in DOCUMENT.lower()
    assert f"{words[len(RECORD['scenarios'])]} scenarios" in DOCUMENT.lower()
    assert f"{words[len(RULE_IDS)]} rules" in DOCUMENT.lower()
    limitation = RECORD["limitations"][0].lower()
    assert limitation.startswith(
        f"{words[len(RECORD['alerts'])]} alerts and "
        f"{words[len(RECORD['deferredAlerts'])]} deferred"
    )


def test_every_alert_and_every_deferral_appears_in_the_document() -> None:
    for alert in RECORD["alerts"]:
        assert alert["name"] in DOCUMENT, alert["name"]
    for entry in RECORD["deferredAlerts"]:
        assert entry["deferredId"] in DOCUMENT, entry["deferredId"]
    for entry in RECORD["refusedAlerts"]:
        assert entry["refusedId"] in DOCUMENT, entry["refusedId"]


def test_the_document_names_every_rule_the_policy_applies() -> None:
    for rule in RULE_IDS:
        assert rule in DOCUMENT, rule


# --------------------------------------------------------------------------
# What may be alerted on at all
# --------------------------------------------------------------------------


def test_no_alert_reads_a_metric_nothing_emits() -> None:
    """The rule the whole sprint turns on, stated directly rather than inherited.

    The correlation policy refuses it too, and this is here so that removing that
    refusal there does not quietly remove it here.
    """
    not_emitted = not_emitted_metric_names()
    for alert_id, alert in ALERTS.items():
        names = metrics_read(parse(alert["expr"]))
        bare = {
            re.sub(r"_(bucket|count|sum)$", "", name)
            for name in names
            if not name.startswith("inferops:")
        }
        assert not (bare & not_emitted), (alert_id, bare & not_emitted)


def test_every_recorded_series_an_alert_reads_is_one_the_chart_renders() -> None:
    for alert_id, alert in ALERTS.items():
        for profile in alert["profiles"]:
            recorded = recorded_series_names(profile)
            for name in metrics_read(parse(alert["expr"])):
                if name.startswith("inferops:"):
                    assert name in recorded, (alert_id, profile, name)


def test_no_alert_expression_names_a_label_outside_the_query_vocabulary() -> None:
    permitted = permitted_query_labels()
    for alert_id, alert in ALERTS.items():
        for label in _labels(alert["expr"]):
            assert label in permitted, (alert_id, label)


def _labels(expression: str) -> set[str]:
    from tools.telemetry_correlation import labels_read

    return set(labels_read(parse(expression)))


def test_every_deferred_condition_says_what_would_be_needed_and_what_not_to_use() -> (
    None
):
    for entry in RECORD["deferredAlerts"]:
        for field in (
            "condition",
            "whyDeferred",
            "notObserved",
            "whatWouldBeNeeded",
            "doNotApproximate",
        ):
            assert entry[field].strip(), (entry["deferredId"], field)


def test_every_refused_alert_names_a_rule_the_policy_has() -> None:
    from tools.telemetry_correlation import RULE_IDS as CORRELATION_RULE_IDS

    known = set(RULE_IDS) | {"alert-expression-refused-by-the-correlation-policy"}
    for entry in RECORD["refusedAlerts"]:
        assert entry["rule"] in known, entry["refusedId"]
        assert entry["why"].strip()
        assert entry["insteadUse"].strip()
    assert set(CORRELATION_RULE_IDS)  # the correlation policy still has rules


def test_every_refused_alert_is_actually_refused() -> None:
    """A negative catalogue nobody checks is a list of things somebody believes.

    Each entry is spliced into a copy of the record as though it had been written,
    and the rule it names has to be among the refusals.
    """
    for entry in RECORD["refusedAlerts"]:
        record = copy.deepcopy(RECORD)
        template = copy.deepcopy(record["alerts"][0])
        template["alertId"] = "refused-under-test"
        template["name"] = "InferOpsRefusedUnderTest"
        template["expr"] = entry["expr"]
        template["scenarioExpectations"] = {
            scenario: "silent" for scenario in SCENARIOS
        }
        if entry["refusedId"] == "in-flight-above-a-number":
            template["thresholdBasis"] = "not-a-declared-basis"
        if entry["refusedId"] == "token-throughput-dropped":
            template["thresholdBasis"] = "measurement"
        if entry["refusedId"] == "processor-time-rising":
            template["operatorAction"] = ""
        if entry["refusedId"] == "model-ready-absence-as-model-health":
            template["operatorAction"] = ""
        if entry["refusedId"] == "refusals-without-a-window":
            template["forSeconds"] = 30
        record["alerts"].append(template)
        rules = {finding.rule for finding in check_alerts(record)}
        assert entry["rule"] in rules, (entry["refusedId"], sorted(rules))


# --------------------------------------------------------------------------
# What an alert owes its operator
# --------------------------------------------------------------------------


def test_every_alert_names_an_owner_a_severity_and_a_runbook_section() -> None:
    owners = {owner["ownerId"] for owner in RECORD["owners"]}
    severities = {severity["severityId"] for severity in RECORD["severities"]}
    for alert_id, alert in ALERTS.items():
        assert alert["owner"] in owners, alert_id
        assert alert["severity"] in severities, alert_id
        path, _, fragment = alert["runbookRef"].partition("#")
        document = REPO_ROOT / path
        assert document.is_file(), alert_id
        assert fragment in runbook_anchors(document), (alert_id, fragment)


#: What a runbook section has to tell a reader to run. A section that only
#: describes the fault is a section that answers nothing at three in the morning.
COMMANDS = ("kubectl", "helm", "docker", "terraform", "python", "uv")


def test_every_runbook_section_an_alert_points_at_carries_a_command() -> None:
    """A runbook link that lands on prose is a link nobody can act on.

    The section an alert points at has to name something to run -- in a fenced
    block or in an inline code span, which are the two ways every operating
    document in this repository writes one.
    """
    for alert_id, alert in ALERTS.items():
        path, _, fragment = alert["runbookRef"].partition("#")
        section = _section(REPO_ROOT / path, fragment)
        assert any(command in section for command in COMMANDS), alert_id
        assert "`" in section, alert_id


def _section(document: Path, fragment: str) -> str:
    """One heading's own text, up to the next heading at that level or above.

    Fenced blocks are skipped rather than parsed: every operating document here
    writes its commands with `#` comments in them, and a comment read as a heading
    ends the section at its first command -- which is the one thing this check has
    to see.
    """
    lines = document.read_text(encoding="utf-8").splitlines()
    collected: list[str] = []
    depth = 0
    fenced = False
    for line in lines:
        if re.match(r"^[ 	]*(```|~~~)", line):
            fenced = not fenced
            if depth:
                collected.append(line)
            continue
        heading = None if fenced else re.match(r"^(#{1,6})\s+(?P<text>.+?)\s*$", line)
        if heading is not None:
            text = re.sub(r"`([^`]*)`", r"\1", heading.group("text"))
            text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
            slug = re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", text).strip().lower())
            if collected and len(heading.group(1)) <= depth:
                break
            if slug == fragment:
                depth = len(heading.group(1))
                collected.append(line)
                continue
        if depth:
            collected.append(line)
    return "\n".join(collected)


def test_no_threshold_is_a_figure_this_project_measured() -> None:
    bases = {basis["basisId"] for basis in RECORD["thresholdBases"]}
    assert "measurement" not in bases
    for alert_id, alert in ALERTS.items():
        assert alert["thresholdBasis"] in bases, alert_id
        assert alert["thresholdRationale"].strip(), alert_id


def test_the_latency_threshold_is_the_chart_value_it_claims_to_be() -> None:
    """The one threshold derived by arithmetic, checked against its source.

    A rationale that names a configuration key and a number that drifted from it
    is worse than a number with no rationale at all.
    """
    values = yaml.safe_load(
        (REPO_ROOT / "charts/inferops-llm/values.yaml").read_text(encoding="utf-8")
    )
    timeout_ms = values["api"]["requestTimeoutMs"]
    alert = ALERTS["inference-latency-past-half-the-request-budget"]
    assert f"> {timeout_ms // 2000}" in alert["expr"]
    assert str(timeout_ms) in alert["thresholdRationale"].replace(" ", "")
    assert float(timeout_ms // 2000) in REQUEST_DURATION_BUCKETS


def test_the_readiness_threshold_is_half_the_probe_cadence_the_chart_configures() -> (
    None
):
    values = yaml.safe_load(
        (REPO_ROOT / "charts/inferops-llm/values.yaml").read_text(encoding="utf-8")
    )
    period = values["api"]["probes"]["readiness"]["periodSeconds"]
    alert = ALERTS["readiness-refusals-sustained"]
    assert f"> {0.5 / period}" in alert["expr"]
    assert "periodSeconds" in alert["thresholdRationale"]


def test_the_saturation_threshold_names_the_parallelism_the_chart_configures() -> None:
    values = yaml.safe_load(
        (REPO_ROOT / "charts/inferops-llm/values.yaml").read_text(encoding="utf-8")
    )
    assert values["runtime"]["parallelSlots"] == 1
    assert "parallelSlots" in ALERTS["runtime-defers-requests"]["thresholdRationale"]


def test_every_window_is_at_least_the_range_window_the_expression_reads() -> None:
    for alert_id, alert in ALERTS.items():
        ranges = re.findall(r"\[(\d+)m\]", alert["expr"])
        longest = max((int(value) * 60 for value in ranges), default=0)
        assert alert["forSeconds"] >= longest, alert_id
        assert (
            alert["forSeconds"]
            >= 2 * RECORD["evaluation"]["ruleEvaluationIntervalSeconds"]
        ), alert_id


def test_only_the_collection_alert_declares_a_scrape_signal() -> None:
    scrape = [
        alert_id
        for alert_id, alert in ALERTS.items()
        if alert["signal"] == "scrape-reachability"
    ]
    assert scrape == ["platform-api-scrape-job-absent"]
    assert ALERTS["platform-api-scrape-job-absent"]["owner"] == "platform"


# --------------------------------------------------------------------------
# The rules, each driven over a record corrupted to break it
# --------------------------------------------------------------------------


def _mutate(change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    record = copy.deepcopy(RECORD)
    change(record)
    return record


def _alert(record: dict[str, Any], alert_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(
        alert for alert in record["alerts"] if alert["alertId"] == alert_id
    )
    return found


def _rules(record: dict[str, Any]) -> set[str]:
    return {finding.rule for finding in check_alerts(record)}


def _not_a_comparison(record: dict[str, Any]) -> None:
    _alert(record, "inference-callers-refused")["expr"] = (
        'sum by (inferops_workload_id) (rate(inferops_inference_errors_total{inferops_error_code="capability-unavailable"}[5m]))'
    )


def _refused_by_correlation(record: dict[str, Any]) -> None:
    _alert(record, "inference-callers-refused")["expr"] = (
        "sum(rate(inferops_model_load_duration_seconds_count[5m])) > 0"
    )


def _no_action(record: dict[str, Any]) -> None:
    _alert(record, "inference-callers-refused")["operatorAction"] = "   "


def _no_such_identifier(record: dict[str, Any]) -> None:
    _alert(record, "inference-callers-refused")["alertId"] = "Not Kebab Case"


def _no_expectation(record: dict[str, Any]) -> None:
    _alert(record, "inference-callers-refused")["scenarioExpectations"] = {
        scenario: "silent" for scenario in SCENARIOS
    }


def _names_a_job(record: dict[str, Any]) -> None:
    _alert(record, "platform-api-scrape-job-absent")["expr"] = (
        'absent(up{job="inferops-inferops-llm-platform-api"}) == 1'
    )


def _runbook_moved(record: dict[str, Any]) -> None:
    _alert(record, "inference-callers-refused")["runbookRef"] = (
        "docs/environment/kubernetes-troubleshooting.md#a-section-nobody-wrote"
    )


def _threshold_without_a_source(record: dict[str, Any]) -> None:
    _alert(record, "inference-callers-refused")["thresholdBasis"] = (
        "because-it-felt-right"
    )


def _scrape_as_workload(record: dict[str, Any]) -> None:
    _alert(record, "platform-api-scrape-job-absent")["signal"] = "workload"


def _window_too_short_for_the_interval(record: dict[str, Any]) -> None:
    _alert(record, "platform-api-scrape-job-absent")["forSeconds"] = 30


def _window_shorter_than_the_range(record: dict[str, Any]) -> None:
    _alert(record, "inference-callers-refused")["forSeconds"] = 120


def _no_alerts(record: dict[str, Any]) -> None:
    record["alerts"] = []


CORRUPTIONS: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
    (
        "selector-not-comparison",
        _not_a_comparison,
        "alert-condition-is-not-a-comparison",
    ),
    (
        "correlation",
        _refused_by_correlation,
        "alert-expression-refused-by-the-correlation-policy",
    ),
    ("no-action", _no_action, "alert-has-no-operator-action"),
    ("identifier", _no_such_identifier, "alert-identifier-is-malformed-or-repeated"),
    ("no-fires-expectation", _no_expectation, "alert-is-not-validated"),
    ("names-a-job", _names_a_job, "alert-names-a-job"),
    ("no-alerts", _no_alerts, "alert-record-is-malformed"),
    ("runbook-moved", _runbook_moved, "alert-runbook-does-not-resolve"),
    (
        "threshold",
        _threshold_without_a_source,
        "alert-threshold-has-no-declared-source",
    ),
    (
        "range-window",
        _window_shorter_than_the_range,
        "alert-window-is-shorter-than-its-range-window",
    ),
    (
        "evaluation-interval",
        _window_too_short_for_the_interval,
        "alert-window-is-shorter-than-two-evaluations",
    ),
    (
        "scrape-as-workload",
        _scrape_as_workload,
        "scrape-signal-presented-as-workload-health",
    ),
]


@pytest.mark.parametrize(
    ("change", "rule"),
    [(change, rule) for _, change, rule in CORRUPTIONS],
    ids=[name for name, _, _ in CORRUPTIONS],
)
def test_each_corruption_is_refused_by_the_rule_written_for_it(
    change: Callable[[dict[str, Any]], None], rule: str
) -> None:
    assert rule in _rules(_mutate(change))


def test_every_rule_has_a_corruption_that_proves_it_fires() -> None:
    assert {rule for _, _, rule in CORRUPTIONS} == set(RULE_IDS)


def test_a_workload_word_the_list_was_not_given_is_still_accepted() -> None:
    """The word list is a list. This pins one synonym it misses.

    The gap stays a committed fact rather than an assumption that it was closed.
    """

    def synonym(record: dict[str, Any]) -> None:
        _alert(record, "platform-api-scrape-job-absent")["condition"] = (
            "The collector's platform-api job has been fine for ten minutes."
        )

    assert "scrape-signal-presented-as-workload-health" not in _rules(_mutate(synonym))


@pytest.mark.parametrize(
    "malformed",
    [
        {"alerts": [None]},
        {"alerts": "not-a-list"},
        {},
        {"alerts": []},
        {"alerts": [{"alertId": "a", "expr": 5}]},
        {"alerts": [{"alertId": "a", "scenarioExpectations": "not-a-mapping"}]},
    ],
    ids=[
        "null-alert",
        "string-alerts",
        "no-alerts-key",
        "empty-alerts",
        "number-expression",
        "string-expectations",
    ],
)
def test_a_malformed_record_is_refused_rather_than_crashing(
    malformed: dict[str, Any],
) -> None:
    """The checker is a gate; a traceback is not a refusal anybody can read."""
    findings = check_alerts(malformed)
    assert findings
    assert {finding.rule for finding in findings} <= set(RULE_IDS)


def test_a_finding_never_echoes_a_hostile_identifier_or_expression() -> None:
    def hostile(record: dict[str, Any]) -> None:
        _alert(record, "inference-callers-refused")["alertId"] = "\x1b[31mred\x07"

    for finding in check_alerts(_mutate(hostile)):
        for field in finding.as_dict().values():
            assert set(field) <= SAFE_MESSAGE_CHARACTERS, field


# --------------------------------------------------------------------------
# The scenarios: what fires, and what does not
# --------------------------------------------------------------------------


def test_every_scenario_has_a_committed_fixture_and_nothing_else_is_there() -> None:
    committed = {path.stem for path in FIXTURE_DIR.glob("*.yaml")}
    assert committed == set(SCENARIOS)


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_every_alert_does_what_the_record_says_over_every_scenario(
    scenario: str,
) -> None:
    for alert_id, firing in FIRING[scenario].items():
        expected = ALERTS[alert_id]["scenarioExpectations"][scenario]
        assert firing == (expected == "fires"), (scenario, alert_id, expected)


def test_nothing_fires_in_either_healthy_scenario() -> None:
    for scenario in ("healthy-real-serving", "healthy-mock-serving"):
        assert not any(FIRING[scenario].values()), scenario


def test_one_scrape_interval_of_refusals_pages_nobody() -> None:
    """The scenario that decides whether the windows are long enough.

    The condition is true for a while -- a five-minute rate reads a single step
    for five minutes -- and no alert fires, because every `for` is at least as
    long as the range window the expression reads.
    """
    fixture = FIXTURES["one-scrape-of-trouble"]
    alert = ALERTS["inference-callers-refused"]
    assert not any(FIRING["one-scrape-of-trouble"].values())
    shortened = dict(alert, forSeconds=120)
    assert firing_instants(shortened, fixture), (
        "the fixture no longer exercises the window this test exists for"
    )


def test_the_two_recorded_failure_shapes_each_fire_the_availability_set() -> None:
    for scenario in ("serving-pod-lost", "model-never-becomes-ready"):
        assert FIRING[scenario]["inference-callers-refused"], scenario
        assert FIRING[scenario]["readiness-refusals-sustained"], scenario


def test_a_release_that_has_never_served_cannot_fire_the_no_successes_alert() -> None:
    """Recorded rather than assumed, and the reason is in the record.

    The success counter series does not exist until the first success, so a rate
    over it is empty and never zero. V1-S4-007-PR1 observed exactly this, and the
    alert's own `whatItCannotSee` says so.
    """
    assert not FIRING["model-never-becomes-ready"]["inference-serving-nothing"]
    assert FIRING["serving-pod-lost"]["inference-serving-nothing"]
    blind = ALERTS["inference-serving-nothing"]["whatItCannotSee"]
    assert "never served" in blind


def test_every_workload_alert_is_silent_when_the_api_is_not_discovered() -> None:
    """The scenario that says what the alert set cannot do.

    Silence here means nothing was asked, and the collection alert is the only
    thing that says so.
    """
    firing = FIRING["platform-api-not-discovered"]
    assert firing["platform-api-scrape-job-absent"]
    for alert_id, alert in ALERTS.items():
        if alert["signal"] == "workload":
            assert not firing[alert_id], alert_id


def test_each_fault_scenario_fires_only_the_alerts_written_for_it() -> None:
    expected = {
        "inference-slower-than-the-request-budget": {
            "inference-latency-past-half-the-request-budget"
        },
        "runtime-defers-requests": {"runtime-defers-requests"},
        "platform-api-not-discovered": {"platform-api-scrape-job-absent"},
    }
    for scenario, names in expected.items():
        assert {
            alert_id for alert_id, firing in FIRING[scenario].items() if firing
        } == names, scenario


def test_every_alert_both_fires_and_stays_silent_somewhere() -> None:
    for alert_id in ALERTS:
        outcomes = {
            FIRING[scenario].get(alert_id)
            for scenario in SCENARIOS
            if alert_id in FIRING[scenario]
        }
        assert outcomes == {True, False}, alert_id


def test_no_alert_result_carries_the_pod_name() -> None:
    """`instance` is the one unbounded label the collection record accepts.

    An alert grouped by it would produce one notification per replica for one
    fault, which is the shape that makes people turn alerting off.
    """
    for scenario in SCENARIOS:
        for rows in evaluate_alerts(RECORD, FIXTURES[scenario]).values():
            for row in rows:
                assert "instance=" not in row, (scenario, row)


# --------------------------------------------------------------------------
# The rendered rule files
# --------------------------------------------------------------------------


@pytest.mark.parametrize("profile", sorted(RENDER_PATHS))
def test_the_committed_rule_file_is_what_the_record_generates(profile: str) -> None:
    generated = serialise(render_rules(RECORD, profile), profile, RECORD)
    committed = RENDER_PATHS[profile].read_text(encoding="utf-8")
    assert committed == generated


@pytest.mark.parametrize("profile", sorted(RENDER_PATHS))
def test_the_rule_file_is_a_prometheus_rule_group_and_parses(profile: str) -> None:
    document = yaml.safe_load(RENDER_PATHS[profile].read_text(encoding="utf-8"))
    assert list(document) == ["groups"]
    group = document["groups"][0]
    assert group["name"] == GROUP_NAME
    assert group["interval"] == "30s"
    for rule in group["rules"]:
        assert set(rule) == {"alert", "expr", "for", "labels", "annotations"}
        parse(rule["expr"])


@pytest.mark.parametrize("profile", sorted(RENDER_PATHS))
def test_the_rule_file_carries_exactly_the_alerts_that_profile_declares(
    profile: str,
) -> None:
    document = yaml.safe_load(RENDER_PATHS[profile].read_text(encoding="utf-8"))
    rendered = {
        rule["labels"]["inferops_alert_id"] for rule in document["groups"][0]["rules"]
    }
    declared = {
        alert_id for alert_id, alert in ALERTS.items() if profile in alert["profiles"]
    }
    assert rendered == declared


def test_the_mock_rule_file_omits_the_alert_that_reads_a_runtime_series() -> None:
    """An expression that can only ever be empty is an alert that never fires.

    The deferral alert reads a recorded series the chart renders only under the
    real profile, so rendering it into a mock release would have shipped silence.
    """
    mock = yaml.safe_load(RENDER_PATHS["mock"].read_text(encoding="utf-8"))
    names = {rule["alert"] for rule in mock["groups"][0]["rules"]}
    assert "InferOpsRuntimeDefersRequests" not in names
    real = yaml.safe_load(RENDER_PATHS["real"].read_text(encoding="utf-8"))
    assert "InferOpsRuntimeDefersRequests" in {
        rule["alert"] for rule in real["groups"][0]["rules"]
    }


@pytest.mark.parametrize("profile", sorted(RENDER_PATHS))
def test_every_rendered_rule_carries_the_owner_severity_and_runbook(
    profile: str,
) -> None:
    document = yaml.safe_load(RENDER_PATHS[profile].read_text(encoding="utf-8"))
    for rule in document["groups"][0]["rules"]:
        alert = ALERTS[rule["labels"]["inferops_alert_id"]]
        assert rule["labels"]["owner"] == alert["owner"]
        assert rule["labels"]["severity"] == alert["severity"]
        assert rule["annotations"]["runbook"] == alert["runbookRef"]
        assert rule["annotations"]["action"].strip() == alert["operatorAction"]
        assert rule["annotations"]["impact"].strip() == alert["userImpact"]
        assert "No receiver" in rule["annotations"]["not_routed"]


@pytest.mark.parametrize("profile", sorted(RENDER_PATHS))
def test_the_rule_file_says_it_is_generated_and_names_its_source(profile: str) -> None:
    header = RENDER_PATHS[profile].read_text(encoding="utf-8").split("groups:")[0]
    assert "GENERATED -- do not edit" in header
    assert ALERT_RECORD_PATH.name in header
    assert "tools.inference_alerts" in header


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.inference_alerts", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_command_is_a_gate_over_the_committed_record() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{len(RECORD['alerts'])} alert(s)" in result.stdout


def test_the_command_reports_findings_as_json() -> None:
    result = _run("--json")
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["valid"] is True
    assert report["alerts"] == len(RECORD["alerts"])
    assert report["deferred"] == len(RECORD["deferredAlerts"])


@pytest.mark.parametrize("profile", sorted(RENDER_PATHS))
def test_the_command_prints_the_committed_rule_file(profile: str) -> None:
    result = _run("--rules", profile)
    assert result.returncode == 0, result.stderr
    assert result.stdout.replace("\r\n", "\n") == RENDER_PATHS[profile].read_text(
        encoding="utf-8"
    )


def test_the_command_evaluates_every_scenario_and_agrees_with_the_record() -> None:
    result = _run("--evaluate")
    assert result.returncode == 0, result.stderr
    assert "DISAGREES" not in result.stdout
    for scenario in SCENARIOS:
        assert f"== {scenario}" in result.stdout
