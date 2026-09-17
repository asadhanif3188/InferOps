"""The inference operations dashboard record, its policy, and its Grafana rendering.

Four files have to agree:

- `docs/telemetry/inference-operations-dashboard.v1alpha1.json`, the record;
- `docs/telemetry/inference-operations-dashboard.md`, the document that publishes it;
- `docs/telemetry/telemetry-correlation-queries.v1alpha1.json`, whose accepted
  queries a panel may repeat only verbatim;
- `deploy/grafana/inferops-inference-operations.json`, generated from the record and
  compared byte for byte.

The property this defends is the one the dashboard exists for: **an operator can
tell zero from missing, missing from not emitted, and not emitted from not
answerable**, and a scrape signal is never shown as readiness. So every panel is held
to the correlation policy, every rule the dashboard adds is driven over a record
corrupted to break it, and every panel expression is evaluated over the committed
synthetic scenarios to show that the states it claims to separate come apart.

**None of this establishes that Grafana accepts the rendered file or that any panel
returns these results from a real Prometheus.** Every check reads a file.
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

from tools.inference_dashboard import (
    DASHBOARD_RECORD_PATH,
    DATASOURCE,
    RENDER_PATH,
    RULE_IDS,
    check_dashboard,
    evaluate_dashboard,
    load_dashboard_record,
    render_grafana,
    serialise,
)
from tools.telemetry_correlation import (
    FIXTURE_DIR,
    SAFE_MESSAGE_CHARACTERS,
    declared_metric_names,
    forbidden_metric_labels,
    load_fixture,
    load_query_record,
    metrics_read,
    not_emitted_metric_names,
    parse,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORD = load_dashboard_record()
DOCUMENT = (REPO_ROOT / RECORD["documentRef"]).read_text(encoding="utf-8")
QUERY_RECORD = load_query_record()
PANELS: dict[str, dict[str, Any]] = {
    panel["panelId"]: panel for panel in RECORD["panels"]
}
SCENARIOS = [scenario["scenarioId"] for scenario in QUERY_RECORD["scenarios"]]


def _results(scenario: str) -> dict[str, list[str]]:
    return evaluate_dashboard(RECORD, load_fixture(FIXTURE_DIR / f"{scenario}.yaml"))


RESULTS = {scenario: _results(scenario) for scenario in SCENARIOS}


def _rules(record: dict[str, Any]) -> set[str]:
    return {finding.rule for finding in check_dashboard(record)}


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


def test_the_record_declares_its_identity_and_contract_version() -> None:
    assert RECORD["$id"].endswith("/inference-operations-dashboard.v1alpha1.json")
    assert RECORD["contractVersion"] == "inferops.io/v1alpha1"


def test_every_reference_the_record_makes_resolves() -> None:
    for key, value in RECORD.items():
        if key.endswith(("Ref", "Dir")) and isinstance(value, str):
            assert (REPO_ROOT / value).exists(), (key, value)
    assert REPO_ROOT / RECORD["renderRef"] == RENDER_PATH
    assert DASHBOARD_RECORD_PATH.is_file()


def test_the_committed_record_satisfies_the_dashboard_policy() -> None:
    assert check_dashboard() == []


def test_the_record_claims_a_run_only_with_a_record_of_it() -> None:
    """The first version of this test pinned both flags false; a real run moved them.

    A flag may say true only while the record names the evidence of the run, and the
    static evidence stays referenced beside it rather than being replaced.
    """
    status = RECORD["verificationStatus"]
    ran = status["importedIntoGrafana"] or status["evaluatedByPrometheus"]
    if ran:
        assert (REPO_ROOT / RECORD["realRunEvidenceRef"]).is_file()
        assert status["evidenceClass"] == "local-real-cpu"
    else:
        assert status["evidenceClass"] == "local-static"
    assert RECORD["evidenceRef"] == "docs/proof/telemetry/v1-s4-002-pr1-validation.md"


def test_the_questions_are_the_v1_operational_questions() -> None:
    """Removing a question is how a dashboard stops answering it quietly."""
    assert [question["questionId"] for question in RECORD["questions"]] == [
        "is-anything-collected",
        "is-it-ready",
        "what-traffic",
        "latency-and-throughput",
        "what-errors",
        "model-load-and-recovery",
        "resources-and-replicas",
        "what-is-running",
        "what-tokens",
    ]


def test_the_four_states_are_declared() -> None:
    assert [state["stateId"] for state in RECORD["states"]] == [
        "zero",
        "missing",
        "not-emitted",
        "not-answerable",
    ]


def test_every_catalog_metric_is_panelled_or_says_why_not() -> None:
    """Both directions, so a metric cannot fall out of the dashboard by omission."""
    read: set[str] = set()
    declared = declared_metric_names()
    for panel in RECORD["panels"]:
        for query in panel["queries"]:
            for series in metrics_read(parse(query["expr"])):
                base = re.sub(r"_(bucket|count|sum)$", "", series)
                read.add(base if base in declared else series)
    unpanelled = {entry["metric"] for entry in RECORD["notPanelled"]}
    assert declared - read == unpanelled
    assert not unpanelled & read


def test_every_not_emitted_metric_the_dashboard_reads_is_in_a_not_emitted_panel() -> (
    None
):
    not_emitted = not_emitted_metric_names()
    for panel in RECORD["panels"]:
        for query in panel["queries"]:
            for series in metrics_read(parse(query["expr"])):
                if re.sub(r"_(bucket|count|sum)$", "", series) in not_emitted:
                    assert panel["signal"] == "not-emitted", panel["panelId"]


def test_every_no_source_correlation_question_has_a_not_answerable_panel() -> None:
    no_source = [
        query
        for query in QUERY_RECORD["queries"]
        if query["answerability"] == "no-source"
    ]
    assert no_source
    requirements = " ".join(
        str(panel["wouldRequire"])
        for panel in RECORD["panels"]
        if panel["signal"] == "not-answerable"
    )
    for query in no_source:
        assert "kube-state-metrics" in query["wouldRequire"]
    assert "kube-state-metrics" in requirements


def test_the_published_counts_are_the_counts_the_record_has() -> None:
    """A miscount in published prose is a defect this project has shipped before."""
    queries = [query for panel in RECORD["panels"] for query in panel["queries"]]
    referenced = [query for query in queries if query["queryRef"] is not None]
    new = [query for query in queries if query["queryRef"] is None]
    words = {11: "eleven", 19: "nineteen", 29: "twenty-nine", 30: "thirty"}
    note = RECORD["verificationStatus"]["note"].lower()
    assert f"{words[len(referenced)]} of the {words[len(queries)]} expressions" in note
    assert f"the other {words[len(new)]} are new" in note
    limitation = next(
        entry
        for entry in RECORD["limitations"]
        if entry["limitationId"] == "new-expressions-evaluated-on-one-provider"
    )
    assert limitation["statement"].lower().startswith(f"{words[len(new)]} panel")
    per_replica = [panel for panel in RECORD["panels"] if panel["perReplica"]]
    evidence = (REPO_ROOT / RECORD["evidenceRef"]).read_text(encoding="utf-8")
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    for text in (DOCUMENT, evidence, changelog):
        assert f"{len(RECORD['panels'])} panels" in text
        assert f"{len(queries)} expressions" in text
    for text in (
        " ".join(DOCUMENT.lower().split()),
        " ".join(evidence.lower().split()),
    ):
        assert f"{words[len(referenced)]} of the expressions" in text
        assert f"{words[len(new)]} are new" in text
    numbers = {5: "five"}
    assert f"the {numbers[len(per_replica)]} panels declared per replica" in evidence


# --------------------------------------------------------------------------
# The rules, each driven over a record corrupted to break it
# --------------------------------------------------------------------------


def _mutate(change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    record = copy.deepcopy(RECORD)
    change(record)
    return record


def _panel(record: dict[str, Any], panel_id: str) -> dict[str, Any]:
    panel: dict[str, Any] = next(
        panel for panel in record["panels"] if panel["panelId"] == panel_id
    )
    return panel


def _drift(record: dict[str, Any]) -> None:
    _panel(record, "request-rate-by-outcome")["queries"][0]["expr"] = (
        "sum by (inferops_workload_id) (rate(inferops_inference_requests_total[5m]))"
    )


def _drift_answerability(record: dict[str, Any]) -> None:
    _panel(record, "model-readiness")["queries"][0]["answerability"] = "no-source"


def _scrape_as_readiness_title(record: dict[str, Any]) -> None:
    _panel(record, "scrape-targets-answering-by-tier")["title"] = (
        "Targets ready, scrape"
    )


def _scrape_without_signal(record: dict[str, Any]) -> None:
    _panel(record, "scrape-targets-discovered-by-tier")["signal"] = "value"


def _not_emitted_as_value(record: dict[str, Any]) -> None:
    _panel(record, "queue-wait-p95")["signal"] = "value"


def _not_answerable_with_a_query(record: dict[str, Any]) -> None:
    _panel(record, "cluster-provider")["queries"] = [
        copy.deepcopy(_panel(record, "requests-since-start")["queries"][0])
    ]


def _not_answerable_without_requirement(record: dict[str, Any]) -> None:
    _panel(record, "cluster-provider")["wouldRequire"] = " "


def _zero_without_meaning(record: dict[str, Any]) -> None:
    _panel(record, "errors-since-start")["zeroMeans"] = None


def _missing_as_zero(record: dict[str, Any]) -> None:
    _panel(record, "errors-since-start")["whenMissing"] = "0"


def _missing_as_nothing(record: dict[str, Any]) -> None:
    _panel(record, "errors-by-code")["whenMissing"] = ""


def _per_replica_undeclared(record: dict[str, Any]) -> None:
    _panel(record, "api-in-flight-by-replica")["perReplica"] = False


def _legend_outside_vocabulary(record: dict[str, Any]) -> None:
    _panel(record, "request-rate-by-outcome")["queries"][0]["legend"] = (
        "{{inferops_request_id}}"
    )


def _unanswered_question(record: dict[str, Any]) -> None:
    record["questions"].append(
        {"questionId": "what-does-it-cost", "question": "What does it cost?"}
    )


def _repeated_identifier(record: dict[str, Any]) -> None:
    record["panels"].append(copy.deepcopy(record["panels"][0]))


def _refused_by_correlation(record: dict[str, Any]) -> None:
    query = _panel(record, "request-rate-by-outcome")["queries"][0]
    query["queryRef"] = None
    query["expr"] = (
        "sum by (inferops_tenant_id) (rate(inferops_inference_requests_total[5m]))"
    )


def _zero_fill_spelled_negative(record: dict[str, Any]) -> None:
    """Review found `* -0` walking past a detector that read only a bare literal."""
    panel = _panel(record, "errors-since-start")
    panel["queries"][0]["expr"] = panel["queries"][0]["expr"].replace("* 0", "* -0")
    panel["zeroMeans"] = None


def _zero_fill_spelled_as_arithmetic(record: dict[str, Any]) -> None:
    panel = _panel(record, "errors-since-start")
    panel["queries"][0]["expr"] = panel["queries"][0]["expr"].replace(
        "* 0", "* (1 - 1)"
    )
    panel["zeroMeans"] = None


def _live_figure_under_not_emitted(record: dict[str, Any]) -> None:
    """Review appended a live query to a not-emitted panel and nothing refused it."""
    live = copy.deepcopy(_panel(record, "successful-requests-per-second")["queries"][0])
    live["refId"] = "Z"
    _panel(record, "queue-wait-p95")["queries"].append(live)


def _scrape_title_with_a_synonym(record: dict[str, Any]) -> None:
    _panel(record, "scrape-targets-answering-by-tier")["title"] = (
        "Scrape targets operational, by tier"
    )


def _bare_selector_undeclared(record: dict[str, Any]) -> None:
    """A bare selector returns `instance` without naming it."""
    _panel(record, "build-identity-per-replica")["perReplica"] = False


CORRUPTIONS: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
    (
        "zero-fill-negative",
        _zero_fill_spelled_negative,
        "panel-state-contradicts-its-queries",
    ),
    (
        "zero-fill-arithmetic",
        _zero_fill_spelled_as_arithmetic,
        "panel-state-contradicts-its-queries",
    ),
    (
        "live-under-not-emitted",
        _live_figure_under_not_emitted,
        "panel-state-contradicts-its-queries",
    ),
    (
        "scrape-title-synonym",
        _scrape_title_with_a_synonym,
        "scrape-signal-presented-as-readiness",
    ),
    (
        "bare-selector-per-replica",
        _bare_selector_undeclared,
        "panel-reads-a-per-replica-label-without-declaring-it",
    ),
    ("drift", _drift, "panel-query-drifted-from-the-accepted-query"),
    (
        "drift-answerability",
        _drift_answerability,
        "panel-query-drifted-from-the-accepted-query",
    ),
    (
        "scrape-title",
        _scrape_as_readiness_title,
        "scrape-signal-presented-as-readiness",
    ),
    ("scrape-signal", _scrape_without_signal, "scrape-signal-presented-as-readiness"),
    (
        "not-emitted-as-value",
        _not_emitted_as_value,
        "panel-state-contradicts-its-queries",
    ),
    (
        "not-answerable-query",
        _not_answerable_with_a_query,
        "panel-state-contradicts-its-queries",
    ),
    (
        "not-answerable-requirement",
        _not_answerable_without_requirement,
        "panel-state-contradicts-its-queries",
    ),
    ("zero-meaning", _zero_without_meaning, "panel-state-contradicts-its-queries"),
    ("missing-as-zero", _missing_as_zero, "panel-shows-missing-as-a-number"),
    ("missing-as-nothing", _missing_as_nothing, "panel-shows-missing-as-a-number"),
    (
        "per-replica",
        _per_replica_undeclared,
        "panel-reads-a-per-replica-label-without-declaring-it",
    ),
    (
        "legend",
        _legend_outside_vocabulary,
        "legend-names-a-label-outside-the-query-vocabulary",
    ),
    ("question", _unanswered_question, "operational-question-has-no-panel"),
    ("identifier", _repeated_identifier, "panel-identifier-is-malformed-or-repeated"),
    (
        "correlation",
        _refused_by_correlation,
        "panel-query-refused-by-the-correlation-policy",
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


def test_a_readiness_synonym_the_list_was_not_given_is_still_accepted() -> None:
    """The word list is a list. This pins one synonym it misses, so the gap is a
    committed fact rather than an assumption that it was closed."""

    def synonym(record: dict[str, Any]) -> None:
        _panel(record, "scrape-targets-answering-by-tier")["title"] = (
            "Scrape targets fine, by tier"
        )

    assert "scrape-signal-presented-as-readiness" not in _rules(_mutate(synonym))


@pytest.mark.parametrize(
    "malformed",
    [
        {"panels": [None]},
        {"panels": "not-a-list"},
        {"questions": [1, 2]},
        {"panels": [{"panelId": "a", "queries": "not-a-list"}]},
        {"panels": [{"panelId": "a", "queries": [None]}]},
    ],
    ids=[
        "null-panel",
        "string-panels",
        "number-questions",
        "string-queries",
        "null-query",
    ],
)
def test_a_malformed_record_is_refused_rather_than_crashing(
    malformed: dict[str, Any],
) -> None:
    """The checker is a gate; a traceback is not a refusal anybody can read."""
    findings = check_dashboard(malformed)
    assert findings
    assert {finding.rule for finding in findings} <= set(RULE_IDS)


def test_a_finding_never_echoes_a_hostile_identifier_or_expression() -> None:
    def hostile(record: dict[str, Any]) -> None:
        panel = _panel(record, "request-rate-by-outcome")
        panel["panelId"] = "bad\x1b[2Jid\nforged"
        panel["queries"][0]["queryRef"] = None
        panel["queries"][0]["expr"] = 'inferops_inference_requests_total{x="\x1b"}'
        panel["queries"][0]["legend"] = "{{\x1b[31m}}"

    findings = check_dashboard(_mutate(hostile))
    assert findings
    for finding in findings:
        for text in finding.as_dict().values():
            assert set(text) <= SAFE_MESSAGE_CHARACTERS, text


# --------------------------------------------------------------------------
# The states come apart over the committed scenarios
# --------------------------------------------------------------------------


def test_a_count_reads_zero_when_the_api_was_read_and_counted_nothing() -> None:
    """The mock scenario publishes an identity and no error series at all."""
    assert RESULTS["mock-single-replica"]["errors-since-start/A"] == ["{} 0"]
    assert RESULTS["mock-single-replica"]["readiness-checks-failed-since-start/A"] == [
        "{} 0"
    ]


def test_no_zero_filled_expression_takes_a_rate() -> None:
    """A labelled counter series is born at whatever it counted before its first scrape.

    At least 1, and on a real collector ten: a rate never sees those events.
    A zero filled over a rate would read 0 after a real first failure."""
    for panel in RECORD["panels"]:
        if panel["zeroMeans"] is None:
            continue
        for query in panel["queries"]:
            assert "rate(" not in query["expr"], panel["panelId"]
            assert "increase(" not in query["expr"], panel["panelId"]


def test_a_count_is_missing_rather_than_zero_when_nothing_was_read() -> None:
    down = RESULTS["every-target-down"]
    for key in (
        "errors-since-start/A",
        "requests-since-start/A",
        "readiness-checks-failed-since-start/A",
        "unsuccessful-request-ratio/A",
    ):
        assert down[key] == [], key


def test_a_count_is_missing_while_no_identity_is_published() -> None:
    """The count's zero fill is keyed to a published identity and nothing else, so
    it stays missing here even though requests are counted."""
    results = RESULTS["api-target-up-without-identity"]
    assert results["requests-since-start/A"] != []
    assert results["errors-since-start/A"] == []
    assert results["api-identity-not-published/A"] != []


def test_identity_absence_also_reads_when_every_target_is_down() -> None:
    """The recorded absence does not read up. Review found the first title claiming
    a target had answered; this scenario is the one where none did."""
    assert RESULTS["every-target-down"]["api-identity-not-published/A"] != []
    assert "answer" not in PANELS["api-identity-not-published"]["title"].lower()


def test_a_share_reads_zero_only_when_requests_were_finished() -> None:
    assert RESULTS["mock-single-replica"]["unsuccessful-request-ratio/A"] == ["{} 0"]
    assert RESULTS["healthy-real-two-replicas"]["unsuccessful-request-ratio/A"] != [
        "{} 0"
    ]


def test_scrape_reachability_reads_zero_when_every_target_is_down() -> None:
    """A present zero on the scrape panel is what makes every other panel's
    missing state legible."""
    rows = RESULTS["every-target-down"]["scrape-targets-answering-by-tier/A"]
    assert len(rows) == 2
    assert all(row.endswith(" 0") for row in rows)


def test_a_runtime_that_was_never_discovered_is_named_rather_than_silent() -> None:
    results = RESULTS["serving-runtime-not-discovered"]
    assert results["scrape-jobs-that-discovered-no-pod/B"] != []
    assert results["runtime-operating-identity/A"] == []


def test_not_emitted_queries_are_empty_in_every_scenario() -> None:
    for scenario, results in RESULTS.items():
        for panel in RECORD["panels"]:
            for query in panel["queries"]:
                if query["answerability"] != "not-answerable-nothing-emits":
                    continue
                key = f"{panel['panelId']}/{query['refId']}"
                assert results.get(key, []) == [], (scenario, key)


def test_model_readiness_says_not_emitted_rather_than_ready() -> None:
    for scenario, results in RESULTS.items():
        assert results["model-readiness/A"] == [], scenario
        assert results["model-readiness/B"] != [], scenario


def test_the_mock_profile_does_not_render_runtime_queries() -> None:
    """Absent from the result, not empty in it: those are different answers."""
    mock = RESULTS["mock-single-replica"]
    for panel in RECORD["panels"]:
        for query in panel["queries"]:
            key = f"{panel['panelId']}/{query['refId']}"
            assert (key in mock) == ("mock" in query["profiles"]), key


def test_every_value_panel_answers_in_the_healthy_scenario() -> None:
    healthy = RESULTS["healthy-real-two-replicas"]
    for panel in RECORD["panels"]:
        if panel["signal"] not in {"value", "scrape-reachability"}:
            continue
        if panel["valueText"]:
            # An absence panel: empty is the state it reports as healthy.
            continue
        answered = [
            healthy[f"{panel['panelId']}/{query['refId']}"]
            for query in panel["queries"]
        ]
        assert any(answered), panel["panelId"]


def test_the_quantiles_are_ordered_in_the_healthy_scenario() -> None:
    healthy = RESULTS["healthy-real-two-replicas"]
    values = [
        float(healthy[f"request-latency-quantiles/{ref}"][0].rsplit(" ", 1)[1])
        for ref in ("A", "B", "C")
    ]
    assert values == sorted(values)


def test_only_a_per_replica_panel_returns_the_pod_name_in_any_scenario() -> None:
    """The rule reads what it can derive statically; this reads what came back."""
    for scenario, results in RESULTS.items():
        for panel in RECORD["panels"]:
            if panel["perReplica"]:
                continue
            for query in panel["queries"]:
                key = f"{panel['panelId']}/{query['refId']}"
                for row in results.get(key, []):
                    assert 'instance="' not in row, (scenario, key)


def test_no_panel_result_carries_a_label_the_catalog_bars() -> None:
    forbidden = forbidden_metric_labels()
    for scenario, results in RESULTS.items():
        for key, rows in results.items():
            for row in rows:
                named = set(re.findall(r'([A-Za-z_][A-Za-z0-9_]*)="', row))
                assert not named & forbidden, (scenario, key, named & forbidden)


# --------------------------------------------------------------------------
# The Grafana rendering
# --------------------------------------------------------------------------

DASHBOARD = json.loads(RENDER_PATH.read_text(encoding="utf-8"))
RENDERED_PANELS = [panel for panel in DASHBOARD["panels"] if panel["type"] != "row"]


def test_the_committed_render_is_what_the_record_generates() -> None:
    assert RENDER_PATH.read_text(encoding="utf-8") == serialise(render_grafana(RECORD))


def test_the_command_prints_the_committed_render() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.inference_dashboard", "--grafana"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == DASHBOARD


def test_the_command_is_a_gate_over_the_committed_record() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.inference_dashboard", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert json.loads(completed.stdout)["valid"] is True


def test_the_render_carries_the_record_identity() -> None:
    assert DASHBOARD["uid"] == RECORD["renderer"]["uid"]
    assert DASHBOARD["schemaVersion"] == RECORD["renderer"]["schemaVersion"]
    variables = DASHBOARD["templating"]["list"]
    assert [variable["type"] for variable in variables] == ["datasource"]
    assert variables[0]["name"] == RECORD["dataSource"]["grafanaVariable"]


def test_every_record_panel_is_rendered_once_under_its_question() -> None:
    assert sorted(panel["title"] for panel in RENDERED_PANELS) == sorted(
        panel["title"] for panel in RECORD["panels"]
    )
    rows = [panel["title"] for panel in DASHBOARD["panels"] if panel["type"] == "row"]
    assert rows == [question["question"] for question in RECORD["questions"]]


def test_panel_identifiers_are_unique() -> None:
    identifiers = [panel["id"] for panel in DASHBOARD["panels"]]
    assert len(identifiers) == len(set(identifiers))


def test_no_two_panels_overlap_and_none_leaves_the_grid() -> None:
    occupied: set[tuple[int, int]] = set()
    for panel in DASHBOARD["panels"]:
        grid = panel["gridPos"]
        assert grid["x"] + grid["w"] <= 24, panel["title"]
        cells = {
            (x, y)
            for x in range(grid["x"], grid["x"] + grid["w"])
            for y in range(grid["y"], grid["y"] + grid["h"])
        }
        assert not cells & occupied, panel["title"]
        occupied |= cells


def test_every_query_reads_the_selected_release_collector_and_nothing_else() -> None:
    for panel in RENDERED_PANELS:
        if panel["type"] == "text":
            assert "targets" not in panel and "datasource" not in panel
            continue
        assert panel["datasource"] == DATASOURCE
        for target in panel["targets"]:
            assert target["datasource"] == DATASOURCE
    text = RENDER_PATH.read_text(encoding="utf-8")
    assert "http://" not in text and "https://" not in text
    assert 'job="' not in text and "job=~" not in text


def test_the_rendered_queries_are_the_record_queries() -> None:
    by_title = {panel["title"]: panel for panel in RECORD["panels"]}
    for panel in RENDERED_PANELS:
        source = by_title[panel["title"]]
        if panel["type"] == "text":
            assert source["wouldRequire"] in panel["options"]["content"]
            continue
        assert [target["expr"] for target in panel["targets"]] == [
            query["expr"] for query in source["queries"]
        ]


def test_every_query_panel_shows_its_missing_text_rather_than_a_default() -> None:
    by_title = {panel["title"]: panel for panel in RECORD["panels"]}
    for panel in RENDERED_PANELS:
        if panel["type"] == "text":
            continue
        assert (
            panel["fieldConfig"]["defaults"]["noValue"]
            == (by_title[panel["title"]]["whenMissing"])
        )


def test_a_table_hides_its_value_only_where_the_value_is_always_one() -> None:
    by_title = {panel["title"]: panel for panel in RECORD["panels"]}
    for panel in RENDERED_PANELS:
        if panel["type"] != "table":
            continue
        hidden = panel["transformations"][0]["options"]["excludeByName"]
        assert hidden.get("Value", False) is by_title[panel["title"]]["hideValueColumn"]
    assert PANELS["runtime-operating-identity"]["hideValueColumn"] is False


def test_no_panel_colours_a_value_as_health() -> None:
    for panel in RENDERED_PANELS:
        if panel["type"] == "text":
            continue
        defaults = panel["fieldConfig"]["defaults"]
        assert defaults["thresholds"]["steps"] == [{"color": "text", "value": None}]
        assert defaults["color"] == {"mode": "fixed", "fixedColor": "text"}
        if panel["type"] == "stat":
            assert panel["options"]["colorMode"] == "none"


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------


def test_the_document_names_every_panel_rule_and_unpanelled_metric() -> None:
    for panel_id in PANELS:
        assert f"`{panel_id}`" in DOCUMENT, panel_id
    for rule in RULE_IDS:
        assert f"`{rule}`" in DOCUMENT, rule
    for entry in RECORD["notPanelled"]:
        assert f"`{entry['metric']}`" in DOCUMENT, entry["metric"]


def test_the_document_names_no_panel_the_record_lacks() -> None:
    table = DOCUMENT.split("## The panels", 1)[1].split("\n## ", 1)[0]
    named = set(re.findall(r"^\| `([a-z0-9-]+)` \|", table, flags=re.MULTILINE))
    assert named == set(PANELS)


def test_the_document_says_what_has_not_been_done() -> None:
    flat = " ".join(DOCUMENT.lower().split())
    assert "one grafana, one provider, one release" in flat
    assert "grafana's own schema validation" in flat
    assert "a long missing text does not render legibly" in flat
    # Six alerts exist since V1-S4-008-PR1, so the limitation this pinned is no
    # longer that none is defined. What a panel still cannot do is tell anybody
    # anything, and that is what the document has to keep saying.
    assert "a panel does not tell anybody anything" in flat
    assert "nothing evaluates or routes one" in flat
