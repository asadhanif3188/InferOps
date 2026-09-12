"""The collector verifier answers about a collector, not about a file.

`tools.telemetry_collection.verify` is the one checker in this repository that
reads a running Prometheus, and that is exactly what makes it hard to test: the
thing it talks to cannot be committed. So the HTTP layer is replaced here and
everything else -- what counts as discovered, what counts as scraped, what
counts as answerable, and what it refuses -- is exercised for real.

What these tests are careful about is the difference between "returned nothing"
and "failed". An empty query result is a legitimate answer whose meaning lives in
the query record's own `emptyMeans`, and a verifier that quietly treated it as a
pass, or as a failure, would be inventing an interpretation. The tests below pin
that it is reported and counted, and that only an engine *refusing* an expression
is a refusal.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast

import pytest

from tools.telemetry_collection import verify
from tools.telemetry_correlation.core import load_query_record

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts/environment/telemetry-collection-verify.sh"
SCRIPT_TEXT = SCRIPT_PATH.read_text(encoding="utf-8")

API_JOB = "inferops-inferops-llm-platform-api"
RUNTIME_JOB = "inferops-inferops-llm-serving-runtime"

# The documentation lane, alongside the other telemetry suites: what this
# module protects is that a published record and a running collector agree,
# and it contacts nothing itself.
pytestmark = pytest.mark.docs


def target(job: str, health: str = "up", last_error: str = "") -> dict[str, Any]:
    return {"labels": {"job": job}, "health": health, "lastError": last_error}


class FakeCollector:
    """Stands in for the collector's HTTP API.

    `targets` may be a list, in which case each call to /api/v1/targets consumes
    the next entry -- which is how a collector that has not finished its first
    scrape yet is represented, rather than by sleeping.
    """

    def __init__(
        self,
        *,
        targets: list[list[dict[str, Any]]] | list[dict[str, Any]],
        query_result: Any = None,
        query_errors: dict[str, str] | None = None,
        samples_for: str | None = None,
    ) -> None:
        first = targets[0] if targets else None
        rounds: list[list[dict[str, Any]]]
        if isinstance(first, list):
            rounds = [
                list(entry) for entry in cast(list[list[dict[str, Any]]], targets)
            ]
        else:
            rounds = [cast(list[dict[str, Any]], targets)]
        self.rounds = rounds
        self.query_result = query_result if query_result is not None else []
        self.query_errors = query_errors or {}
        # When set, only this expression returns samples. The default of "every
        # query returns the same thing" is wrong for any test that touches the
        # catalog's `not-answerable-nothing-emits` class, which must return
        # nothing however long anybody waits.
        self.samples_for = samples_for
        self.queries_asked: list[str] = []

    def __call__(self, base_url: str, path: str, **params: str) -> dict[str, Any]:
        if path == "/api/v1/targets":
            active = self.rounds[0] if len(self.rounds) == 1 else self.rounds.pop(0)
            return {"status": "success", "data": {"activeTargets": active}}
        if path == "/api/v1/query":
            expression = params["query"]
            self.queries_asked.append(expression)
            if expression in self.query_errors:
                raise verify.VerificationFailed(self.query_errors[expression])
            result = self.query_result
            if self.samples_for is not None and expression != self.samples_for:
                result = []
            return {
                "status": "success",
                "data": {"resultType": "vector", "result": result},
            }
        if path == "/api/v1/status/buildinfo":
            return {
                "status": "success",
                "data": {"version": "3.5.0", "revision": "abc"},
            }
        raise AssertionError(f"unexpected path {path}")


@pytest.fixture()
def collector_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "INFEROPS_COLLECTOR_BASE_URL": "http://127.0.0.1:19090",
        "INFEROPS_API_JOB": API_JOB,
        "INFEROPS_RUNTIME_JOB": RUNTIME_JOB,
        "INFEROPS_SCRAPE_BUDGET_SECONDS": "1",
        "INFEROPS_TARGET_PROVIDER": "docker-desktop",
        "INFEROPS_TARGET_CLUSTER_NAME": "docker-desktop",
        "INFEROPS_TARGET_SERVER_VERSION": "v1.34.3",
        "INFEROPS_RELEASE_NAMESPACE": "inferops-release",
    }.items():
        monkeypatch.setenv(name, value)


def install(monkeypatch: pytest.MonkeyPatch, collector: FakeCollector) -> None:
    monkeypatch.setattr(verify, "_get", collector)
    # `time.sleep` is patched on the standard library module itself, which is the
    # same object the verifier imported, so that a bounded poll spends its budget
    # in iterations rather than in real seconds.
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


# --------------------------------------------------------------------------
# Discovery and scraping
# --------------------------------------------------------------------------


def test_a_job_that_discovered_nothing_is_not_healthy() -> None:
    """The failure a query cannot distinguish from its own empty result.

    A selector that matched no pod and a target that never answered both produce
    an empty result for every query over that job, which is why the rendered
    rules carry `inferops:scrape_job_absent:*`. Here they are separated at the
    source.
    """
    summary = verify.TargetSummary(job=API_JOB, discovered=0, up=0, last_error="")

    assert not summary.healthy


def test_a_discovered_target_that_never_answered_is_not_healthy() -> None:
    summary = verify.TargetSummary(job=API_JOB, discovered=2, up=1, last_error="boom")

    assert not summary.healthy


def test_both_jobs_up_is_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = FakeCollector(targets=[target(API_JOB), target(RUNTIME_JOB)])
    install(monkeypatch, collector)

    summaries = verify.wait_for_scrapes(
        "http://collector", (API_JOB, RUNTIME_JOB), budget_seconds=1
    )

    assert {job: summary.up for job, summary in summaries.items()} == {
        API_JOB: 1,
        RUNTIME_JOB: 1,
    }


def test_a_collector_that_has_not_scraped_yet_is_waited_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prometheus discovers and scrapes on its own schedule, so asking the
    instant the forward opens would report a healthy collector as broken."""
    collector = FakeCollector(
        targets=[
            [],
            [target(API_JOB, health="unknown"), target(RUNTIME_JOB, health="unknown")],
            [target(API_JOB), target(RUNTIME_JOB)],
        ]
    )
    install(monkeypatch, collector)

    summaries = verify.wait_for_scrapes(
        "http://collector", (API_JOB, RUNTIME_JOB), budget_seconds=60
    )

    assert all(summary.healthy for summary in summaries.values())


def test_a_target_that_never_comes_up_refuses_within_the_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = FakeCollector(
        targets=[target(API_JOB), target(RUNTIME_JOB, health="down", last_error="EOF")]
    )
    install(monkeypatch, collector)

    with pytest.raises(verify.VerificationFailed, match="did not scrape"):
        verify.wait_for_scrapes(
            "http://collector", (API_JOB, RUNTIME_JOB), budget_seconds=0
        )


def test_the_refusal_names_the_error_the_target_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure that says only that it happened costs a second run to diagnose."""
    collector = FakeCollector(
        targets=[
            target(API_JOB),
            target(RUNTIME_JOB, health="down", last_error="connection refused"),
        ]
    )
    install(monkeypatch, collector)

    with pytest.raises(verify.VerificationFailed, match="connection refused"):
        verify.wait_for_scrapes(
            "http://collector", (API_JOB, RUNTIME_JOB), budget_seconds=0
        )


# --------------------------------------------------------------------------
# Query answerability
# --------------------------------------------------------------------------


def test_every_accepted_query_that_has_an_expression_is_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read from the accepted record rather than listed in the verifier, so a
    query added there and never asked here is impossible.

    The two `no-source` queries publish no expression -- that class means there
    is no series to write one against -- so they are reported as not asked
    rather than quietly dropped from a count.
    """
    collector = FakeCollector(targets=[target(API_JOB)])
    install(monkeypatch, collector)
    record = load_query_record()
    expressible = [query for query in record["queries"] if query.get("expr")]

    results = verify.evaluate_queries("http://collector")

    assert [entry["queryId"] for entry in results] == [
        query["queryId"] for query in record["queries"]
    ]
    assert collector.queries_asked == [query["expr"] for query in expressible]
    not_asked = [entry for entry in results if not entry["asked"]]
    assert {entry["answerability"] for entry in not_asked} == {"no-source"}


def test_a_query_with_no_expression_outside_no_source_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`no-source` is the one class allowed to publish nothing. A query in any
    other class with an empty expression is a record that has drifted, and
    skipping it silently would hide that.
    """
    collector = FakeCollector(targets=[target(API_JOB)])
    install(monkeypatch, collector)
    broken = json.loads(json.dumps(load_query_record()))
    broken["queries"][0]["expr"] = ""
    monkeypatch.setattr(verify, "load_query_record", lambda: broken)

    with pytest.raises(verify.VerificationFailed, match="publishes no expression"):
        verify.evaluate_queries("http://collector")


def test_a_query_the_catalog_says_emits_nothing_may_not_return_samples(
    monkeypatch: pytest.MonkeyPatch, collector_env: None
) -> None:
    """Not a better-than-expected result. A sample here means the catalog is
    wrong about what this release publishes, and the catalog is what every other
    check in this repository is measured against.
    """
    silent = next(
        query
        for query in load_query_record()["queries"]
        if query.get("answerability") == "not-answerable-nothing-emits"
    )
    collector = FakeCollector(
        targets=[target(API_JOB), target(RUNTIME_JOB)],
        query_result=[{"metric": {}, "value": [0, "1"]}],
        samples_for=silent["expr"],
    )
    install(monkeypatch, collector)

    with pytest.raises(verify.VerificationFailed, match="returned samples"):
        verify.build_evidence()


def test_an_empty_result_is_reported_and_is_not_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A counter's value depends on how much traffic happened to be sent, and the
    workflow sends three requests to move counters off zero rather than to
    measure anything. `emptyMeans` in the query record interprets an empty
    result; the verifier reports it and does not."""
    collector = FakeCollector(targets=[target(API_JOB)], query_result=[])
    install(monkeypatch, collector)

    results = verify.evaluate_queries("http://collector")

    assert all(entry["parsed"] for entry in results if entry["asked"])
    assert all(entry["sampleCount"] == 0 for entry in results)


def test_an_engine_that_refuses_an_expression_is_a_failure(
    monkeypatch: pytest.MonkeyPatch, collector_env: None
) -> None:
    """The one thing a static check cannot establish: that a real engine accepts
    the expression. A query the collector rejects fails the verification."""
    record = load_query_record()
    first = record["queries"][0]["expr"]
    collector = FakeCollector(
        targets=[target(API_JOB), target(RUNTIME_JOB)],
        query_errors={first: "parse error"},
    )
    install(monkeypatch, collector)

    with pytest.raises(verify.VerificationFailed, match="refused an accepted"):
        verify.build_evidence()


# --------------------------------------------------------------------------
# The evidence document
# --------------------------------------------------------------------------


def test_the_evidence_names_the_provider_and_the_engine(
    monkeypatch: pytest.MonkeyPatch, collector_env: None
) -> None:
    answerable = next(
        query
        for query in load_query_record()["queries"]
        if query.get("answerability") == "answerable-once-collected"
    )
    collector = FakeCollector(
        targets=[target(API_JOB), target(RUNTIME_JOB)],
        query_result=[{"metric": {}, "value": [0, "1"]}],
        samples_for=answerable["expr"],
    )
    install(monkeypatch, collector)

    document = verify.build_evidence()

    assert document["outcome"] == "verified"
    assert document["environment"]["provider"] == "docker-desktop"
    assert document["collector"] == {
        "product": "prometheus",
        "version": "3.5.0",
        "revision": "abc",
    }
    assert document["queries"]["evaluatedBy"] == "prometheus"
    assert document["queries"]["parsed"] == document["queries"]["asked"]
    assert document["queries"]["notAsked"] == 2


def test_the_evidence_carries_no_prompt_completion_or_label_value(
    monkeypatch: pytest.MonkeyPatch, collector_env: None
) -> None:
    """Counts, names and booleans. A label value carried out of a query result
    would put workload content into a record that is meant to hold none."""
    answerable = next(
        query
        for query in load_query_record()["queries"]
        if query.get("answerability") == "answerable-once-collected"
    )
    collector = FakeCollector(
        targets=[target(API_JOB), target(RUNTIME_JOB)],
        query_result=[
            {"metric": {"workload_id": "support-assistant"}, "value": [0, "1"]}
        ],
        samples_for=answerable["expr"],
    )
    install(monkeypatch, collector)

    serialised = json.dumps(verify.build_evidence())

    assert "support-assistant" not in serialised
    assert "metric" not in serialised


def test_an_environment_the_script_did_not_set_is_refused(
    monkeypatch: pytest.MonkeyPatch, collector_env: None
) -> None:
    """A record that named an empty provider would be a record about nothing."""
    monkeypatch.delenv("INFEROPS_TARGET_PROVIDER")
    collector = FakeCollector(targets=[target(API_JOB), target(RUNTIME_JOB)])
    install(monkeypatch, collector)

    with pytest.raises(verify.VerificationFailed, match="INFEROPS_TARGET_PROVIDER"):
        verify.build_evidence()


# --------------------------------------------------------------------------
# The operating script
# --------------------------------------------------------------------------


def test_the_script_verifies_the_target_before_it_installs() -> None:
    identity = SCRIPT_TEXT.index("inferops::resolve_target")
    install_index = SCRIPT_TEXT.index("inferops::target_helm install")

    assert identity < install_index


def test_the_script_never_creates_a_namespace_or_removes_a_prerequisite() -> None:
    """The namespace and the claim are Terraform's and outlive every release."""
    # Asked of what the script runs, not of what it says. Each of these choices
    # is explained in a comment directly above the line that makes it -- and the
    # closing message names `destroy --confirm` on purpose, to tell an operator
    # what would reclaim the claim this script deliberately leaves behind.
    commands = "\n".join(
        line for line in SCRIPT_TEXT.splitlines() if not line.lstrip().startswith("#")
    )

    assert "--create-namespace" not in commands
    assert "delete namespace" not in commands
    assert "terraform destroy" not in commands
    assert 'terraform-prerequisites.sh" destroy' not in commands


def test_the_script_uninstalls_what_it_installed() -> None:
    install_index = SCRIPT_TEXT.index("inferops::target_helm install")
    uninstall = SCRIPT_TEXT.index("inferops::target_helm uninstall")

    assert install_index < uninstall


def test_the_script_reads_the_model_name_from_the_cluster() -> None:
    """A literal here would be a second place that has to agree with the values
    file, and the first time it disagreed the answer would be an HTTP 400."""
    assert "INFEROPS_MODEL_IDENTIFIER}" in SCRIPT_TEXT
    assert "qwen3" not in SCRIPT_TEXT.lower()


def test_the_evidence_carries_no_request_timing(
    monkeypatch: pytest.MonkeyPatch, collector_env: None
) -> None:
    """ADR 0005 refuses a published latency or throughput figure for V1, and a
    number in an evidence file is published whatever the sentence beside it
    says. The assertion is on the document rather than on the script text,
    because prose explaining why there is no figure is not a figure.
    """
    collector = FakeCollector(targets=[target(API_JOB), target(RUNTIME_JOB)])
    install(monkeypatch, collector)

    document = verify.build_evidence()

    assert "not a measurement" in SCRIPT_TEXT

    def field_names(node: Any) -> set[str]:
        if isinstance(node, dict):
            names = set(node)
            for value in node.values():
                names |= field_names(value)
            return names
        if isinstance(node, list):
            collected: set[str] = set()
            for value in node:
                collected |= field_names(value)
            return collected
        return set()

    # Field names, because the *values* legitimately include query identifiers
    # and one accepted query is called `request-latency-p95-by-workload-and-model`.
    # Naming a question is not publishing its answer.
    for name in field_names(document):
        for forbidden in ("elapsed", "latency", "throughput", "duration", "p95", "ms"):
            assert forbidden not in name.lower(), name
