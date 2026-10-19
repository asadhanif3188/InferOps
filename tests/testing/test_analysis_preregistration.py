"""The freeze records of the two analysis experiments, held to their sources.

V2-S6-006-PR1 registered revision 1 of the freeze records of V2-E03 (signal
truthfulness) and V2-E06 (reliability resource and cost overhead), before any run
of an experiment whose runs they read. ``tools.experiment_freeze`` checks that each
record answers every freeze field. ``tools.analysis_preregistration`` reads the
answers: the source bindings, the values that each record states for its sources,
and the rules of each record.

The first part holds the committed records, with their identities written out so
that a change to one is visible in review. The second part plants each defect that
the V2-E03 rules refuse in a copy of the files that the check reads, and asserts the
exact findings. The third part does the same for the V2-E06 rules. No test runs an
analysis, computes a figure, or contacts a cluster.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tools.analysis_preregistration import (
    E03,
    E03_SIGNALS,
    E06,
    E06_METRICS,
    RULES,
    check_repository,
    core,
    policy_digest,
)
from tools.experiment_freeze.core import (
    FROZEN_RECORDS,
    changed_inputs,
    content_digest,
    material_files,
)
from tools.experiment_freeze.core import (
    check_repository as check_freezes,
)
from tools.experiment_preregistration import (
    check_repository as check_reliability_records,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "docs/proof/experiments/registry.v1alpha1.json"

E03_RECORD = "docs/proof/experiments/v2-e03/freeze-r1.v1alpha1.json"
E06_RECORD = "docs/proof/experiments/v2-e06/freeze-r1.v1alpha1.json"
#: The registered pins of the two records, written out so that a change is visible.
E03_PIN = "8efdb239bb1b3ad5901d31b8cc7c7d45edd7059366bc7e7ad7fcd389b004117a"
E06_PIN = "10e28991745dd5ad32ba3b6c55ef8aeefae26bb7f99c47302b7dcb6bb497f82f"

#: The latest freeze record of each source, which both records bind.
SOURCE_RECORDS = {
    "V2-E02A": "docs/proof/experiments/v2-e02a/freeze-r2.v1alpha1.json",
    "V2-E02B": "docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json",
    "V2-E02C": "docs/proof/experiments/v2-e02c/freeze-r2.v1alpha1.json",
    "V2-E04": "docs/proof/experiments/v2-e04/freeze-r2.v1alpha1.json",
}
SUPERSEDED_E02A = "docs/proof/experiments/v2-e02a/freeze-r1.v1alpha1.json"
PREREGISTRATION_CORE = "tools/experiment_preregistration/core.py"
EXPERIMENT_DIRECTORIES = ("v2-e02a", "v2-e02b", "v2-e02c", "v2-e04", "v2-e05")


def load(path: str, root: Path = REPO_ROOT) -> dict[str, Any]:
    document = json.loads((root / path).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def found(findings: list[Any]) -> set[tuple[str, str]]:
    return {(f.rule_id, f.location) for f in findings}


# --------------------------------------------------------------------------
# 1. The committed records
# --------------------------------------------------------------------------


def test_the_committed_records_hold_every_rule() -> None:
    assert check_repository() == []


def test_the_command_passes_over_the_committed_records() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.analysis_preregistration", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == (
        "PASSED: 2 analysis experiment(s), every rule held"
    )


def test_each_record_is_revision_1_registered_by_this_change() -> None:
    registry = load(REGISTRY)["records"]
    rows = {row["path"]: row for row in registry}
    for path, pin in ((E03_RECORD, E03_PIN), (E06_RECORD, E06_PIN)):
        assert rows[path] == {
            "path": path,
            "contentSha256": pin,
            "registeredBy": "V2-S6-006-PR1",
        }
        assert FROZEN_RECORDS[path] == pin
        assert content_digest((REPO_ROOT / path).read_bytes()) == pin
        metadata = load(path)["metadata"]
        assert metadata["revision"] == 1
        assert metadata["supersedes"] is None
        assert metadata["registeredBy"] == "V2-S6-006-PR1"
    # The two records are the last two rows: no earlier row moved.
    assert [row["path"] for row in registry[-2:]] == [E03_RECORD, E06_RECORD]


def test_each_record_binds_the_latest_source_revisions_by_digest() -> None:
    roles = {E03_RECORD: core.E03_SOURCES, E06_RECORD: core.E06_SOURCES}
    for path, expected in roles.items():
        sources = load(path)["definition"]["sources"]
        assert {s["experiment"]: s["role"] for s in sources} == dict(expected)
        for source in sources:
            assert source["path"] == SOURCE_RECORDS[source["experiment"]]
            assert source["revision"] == 2
            assert source["contentSha256"] == FROZEN_RECORDS[source["path"]]


def test_both_records_state_the_one_clock_policy_of_their_sources() -> None:
    digests = {
        policy_digest(load(p)["definition"]["clockPolicy"])
        for p in SOURCE_RECORDS.values()
    }
    assert len(digests) == 1
    for path in (E03_RECORD, E06_RECORD):
        assert load(path)["definition"]["sourceClockPolicy"]["sha256"] in digests


def test_the_e03_population_and_signals_are_as_frozen() -> None:
    definition = load(E03_RECORD)["definition"]
    population = definition["population"]
    assert population["initial"]["experiments"] == ["V2-E02A", "V2-E02B", "V2-E02C"]
    assert population["extension"]["experiments"] == ["V2-E04"]
    assert [e["experiment"] for e in population["excluded"]] == ["V2-E05"]
    signals = definition["signals"]
    assert [(s["number"], s["id"], s["stream"]) for s in signals] == [
        (number, ident, stream) for number, (ident, stream) in E03_SIGNALS.items()
    ]
    assert [s["role"] for s in signals] == ["reference", *["candidate"] * 9]
    assert not any("exploratory" in s or "winner" in s for s in signals)
    candidate = definition["operationalCandidate"]
    assert (candidate["signal"], candidate["role"], candidate["rankingPreference"]) == (
        2,
        "comparator",
        "none",
    )
    assert candidate["predeterminedWinner"] is False
    assert definition["ranking"]["comparator"] == "api-error-rate"
    assert [o["outcome"] for o in definition["callerFailures"]["outcomes"]] == [
        "http-error",
        "invalid-response",
        "timeout",
        "transport-error",
        "identity-refused",
    ]


def test_the_e06_views_metrics_and_statistic_are_as_frozen() -> None:
    definition = load(E06_RECORD)["definition"]
    assert [(v["id"], v["label"], v["reads"]) for v in definition["views"]] == [
        ("view-a", "static-allocation", ["requests"]),
        ("view-b", "static-allocation", ["requests"]),
    ]
    assert [m["id"] for m in definition["metrics"]] == list(E06_METRICS)
    measured = [m["id"] for m in definition["metrics"] if m["label"] == "measured"]
    assert measured == ["utilization"]
    utilization = definition["utilization"]
    assert utilization["stream"] == "resources"
    assert utilization["sourceRuns"]["experiments"] == ["V2-E02A", "V2-E02B"]
    assert "api-cpu-seconds" in utilization["queries"]
    assert definition["costBasis"]["basis"] == "local"
    assert definition["costBasis"]["cloud"]["used"] is False
    assert definition["evidenceTarget"]["allocation"] == "C0"
    assert definition["evidenceTarget"]["runDerived"] == "C2"


def test_each_record_pins_exactly_its_material_scope() -> None:
    """A tripwire: a file added to a scope, or one that moves, fails here."""
    for path in (E03_RECORD, E06_RECORD):
        document = load(path)
        pinned = {item["path"] for item in document["pinnedInputs"]}
        assert material_files(document["materialScope"], REPO_ROOT) == pinned
        assert changed_inputs(document, REPO_ROOT) == []


def test_every_source_revision_file_is_in_the_scope_so_a_later_one_is_added() -> None:
    for path, roles in ((E03_RECORD, core.E03_SOURCES), (E06_RECORD, core.E06_SOURCES)):
        paths = load(path)["materialScope"]["paths"]
        for source in roles:
            pattern = f"{core.SOURCE_DIRECTORIES[source]}/freeze-r*.v1alpha1.json"
            assert pattern in paths


def test_no_run_analysis_or_procedure_exists() -> None:
    """Nothing ran: no source run, no analysis, and no analysis code."""
    experiments = REPO_ROOT / "docs" / "proof" / "experiments"
    for directory in (*EXPERIMENT_DIRECTORIES, "v2-e03", "v2-e06"):
        assert not (experiments / directory / "runs").exists()
        assert not (experiments / directory / "procedure").exists()
    for directory in ("v2-e03", "v2-e06"):
        assert sorted(p.name for p in (experiments / directory).iterdir()) == [
            "freeze-r1.v1alpha1.json"
        ]


def test_every_existing_record_still_passes() -> None:
    assert check_freezes() == []
    assert check_reliability_records() == []


def test_this_change_moves_no_pin_of_a_source_record() -> None:
    """The four revisions 2 of rule set 2 differ from their pins in one file, which
    an earlier change moved. Revision 2 of V2-E04 differs in none. A file that this
    change adds or edits would be listed here."""
    for experiment, path in SOURCE_RECORDS.items():
        changes = changed_inputs(load(path), REPO_ROOT)
        expected = [] if experiment == "V2-E04" else [PREREGISTRATION_CORE]
        assert [(c.path, c.kind) for c in changes] == [(p, "changed") for p in expected]
    e05 = load("docs/proof/experiments/v2-e05/freeze-r2.v1alpha1.json")
    assert [c.path for c in changed_inputs(e05, REPO_ROOT)] == [PREREGISTRATION_CORE]


def test_the_rules_of_each_record_are_separate() -> None:
    e03 = [rule for rule in RULES if rule.startswith("e03-")]
    e06 = [rule for rule in RULES if rule.startswith("e06-")]
    assert len(e03) + len(e06) == len(RULES)
    assert len(e03) == 14
    assert len(e06) == 13


def test_the_streams_of_each_source_are_read_from_its_collection() -> None:
    for path in SOURCE_RECORDS.values():
        assert core._collected(load(path)) == {
            "caller": ("caller", None),
            "endpoints": ("timeline", 2000),
            "pods": ("timeline", 2000),
            "deployments": ("timeline", 2000),
            "argo": ("timeline", 2000),
            "telemetry": ("telemetry", 15000),
            "resources": ("telemetry", 15000),
        }


def test_no_public_text_names_a_section_of_another_document() -> None:
    for path in (E03_RECORD, E06_RECORD):
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        assert "§" not in text


# --------------------------------------------------------------------------
# A copy of the files that the check reads
# --------------------------------------------------------------------------


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A root that holds the registry and every freeze record of the check."""
    target = tmp_path / REGISTRY
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / REGISTRY, target)
    base = REPO_ROOT / "docs" / "proof" / "experiments"
    for directory in (*EXPERIMENT_DIRECTORIES, "v2-e03", "v2-e06"):
        for record in sorted((base / directory).glob("freeze-r*.v1alpha1.json")):
            relative = record.relative_to(REPO_ROOT)
            (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(record, tmp_path / relative)
    return tmp_path


def edit(root: Path, path: str, change: Callable[[dict[str, Any]], None]) -> None:
    document = load(path, root)
    change(document)
    (root / path).write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def e03_findings(root: Path) -> set[tuple[str, str]]:
    return found(core.check_records(root, [E03]))


def e06_findings(root: Path) -> set[tuple[str, str]]:
    return found(core.check_records(root, [E06]))


def test_the_copy_holds_every_rule(root: Path) -> None:
    assert core.check_records(root) == []


# --------------------------------------------------------------------------
# 2. V2-E03
# --------------------------------------------------------------------------


def _signal(number: int) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def get(document: dict[str, Any]) -> dict[str, Any]:
        signal = document["definition"]["signals"][number - 1]
        assert signal["number"] == number
        return signal

    return get


def test_e03_refuses_a_removed_signal(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["definition"]["signals"].pop(7))
    assert e03_findings(root) == {("e03-signal-set", "definition.signals")}


def test_e03_refuses_an_eleventh_signal_without_the_exploratory_label(
    root: Path,
) -> None:
    def add(document: dict[str, Any]) -> None:
        extra = copy.deepcopy(document["definition"]["signals"][6])
        extra.update(number=11, id="deployment-available-replicas")
        document["definition"]["signals"].append(extra)

    edit(root, E03_RECORD, add)
    assert e03_findings(root) == {("e03-signal-set", "definition.signals")}


def test_e03_accepts_an_eleventh_signal_labeled_exploratory_and_not_ranked(
    root: Path,
) -> None:
    def add(document: dict[str, Any], ranked: bool) -> None:
        extra = copy.deepcopy(document["definition"]["signals"][6])
        extra.update(
            number=11,
            id="deployment-available-replicas",
            exploratory=True,
            ranked=ranked,
        )
        document["definition"]["signals"].append(extra)

    edit(root, E03_RECORD, lambda d: add(d, False))
    assert e03_findings(root) == set()
    edit(root, E03_RECORD, lambda d: d["definition"]["signals"][10].update(ranked=True))
    assert e03_findings(root) == {("e03-signal-set", "definition.signals[10].ranked")}


def test_e03_refuses_a_stale_source_digest(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["sources"][1].update(contentSha256="0" * 64),
    )
    assert e03_findings(root) == {
        ("e03-sources-stale", "definition.sources[1].contentSha256")
    }


def test_e03_refuses_a_source_that_is_a_superseded_revision(root: Path) -> None:
    def supersede(document: dict[str, Any]) -> None:
        document["definition"]["sources"][0].update(
            path=SUPERSEDED_E02A,
            revision=1,
            contentSha256=FROZEN_RECORDS[SUPERSEDED_E02A],
        )

    edit(root, E03_RECORD, supersede)
    # Revision 1 states no clock policy, so its policy digest differs as well.
    assert e03_findings(root) == {
        ("e03-sources-stale", "definition.sources[0].revision"),
        ("e03-source-fields-differ", "definition.sourceClockPolicy.sha256"),
    }


def test_e03_refuses_once_a_later_source_revision_is_registered(root: Path) -> None:
    """A later source revision needs a later revision of the analysis record."""
    later = "docs/proof/experiments/v2-e02c/freeze-r3.v1alpha1.json"
    source = load(SOURCE_RECORDS["V2-E02C"], root)
    source["metadata"].update(
        revision=3,
        supersedes={
            "path": SOURCE_RECORDS["V2-E02C"],
            "contentSha256": FROZEN_RECORDS[SOURCE_RECORDS["V2-E02C"]],
        },
    )
    text = json.dumps(source, indent=2, ensure_ascii=False) + "\n"
    (root / later).write_text(text, encoding="utf-8")
    registry = load(REGISTRY, root)
    registry["records"].append(
        {
            "path": later,
            "contentSha256": content_digest(text.encode("utf-8")),
            "registeredBy": "a later change",
        }
    )
    (root / REGISTRY).write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )
    assert e03_findings(root) == {
        ("e03-sources-stale", "definition.sources[2].revision")
    }
    # V2-E06 does not read V2-E02C, so it is not stale.
    assert e06_findings(root) == set()


def test_e03_refuses_a_signal_stream_that_no_source_collects(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: _signal(8)(d).update(stream="scrape-targets"))
    findings = core.check_records(root, [E03])
    assert {f.rule_id for f in findings} == {"e03-signal-streams"}
    details = {
        f.detail for f in findings if f.location == "definition.signals[7].stream"
    }
    assert details == {
        "telemetry",
        *(f"{s} does not collect 'scrape-targets'" for s in SOURCE_RECORDS),
    }


def test_e03_refuses_a_sampling_interval_other_than_the_source_collection(
    root: Path,
) -> None:
    edit(root, E03_RECORD, lambda d: _signal(3)(d)["sampling"].update(intervalMs=1000))
    assert e03_findings(root) == {
        ("e03-signal-streams", "definition.signals[2].sampling")
    }


def test_e03_refuses_a_query_outside_the_registered_telemetry_queries(
    root: Path,
) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: _signal(2)(d)["derivation"].update(queries=["api-cpu-seconds"]),
    )
    assert e03_findings(root) == {
        ("e03-signal-streams", "definition.signals[1].derivation.queries")
    }


def test_e03_refuses_e05_in_the_ranking_population(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["population"]["initial"]["experiments"].append(
            "V2-E05"
        ),
    )
    assert e03_findings(root) == {
        ("e03-population", "definition.population.initial"),
        ("e03-population", "definition.population"),
    }


def test_e03_refuses_an_e05_scope_rule_without_its_reason(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["population"]["excluded"][0].pop("reason"),
    )
    assert e03_findings(root) == {("e03-population", "definition.population.excluded")}


def test_e03_refuses_e04_in_the_initial_population(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["population"]["initial"]["experiments"].append(
            "V2-E04"
        ),
    )
    assert e03_findings(root) == {
        ("e03-population", "definition.population.initial"),
        ("e03-population", "definition.population"),
    }


def test_e03_refuses_a_missing_operational_signal_candidate(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["definition"].pop("operationalCandidate"))
    assert e03_findings(root) == {("e03-candidate", "definition.operationalCandidate")}


def test_e03_refuses_a_candidate_declared_a_winner(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["operationalCandidate"].update(
            predeterminedWinner=True, rankingPreference="first"
        ),
    )
    assert e03_findings(root) == {
        ("e03-candidate", "definition.operationalCandidate.predeterminedWinner"),
        ("e03-candidate", "definition.operationalCandidate.rankingPreference"),
    }


def test_e03_refuses_any_signal_declared_a_winner(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: _signal(4)(d).update(winner=True))
    assert e03_findings(root) == {("e03-candidate", "definition.signals[3].winner")}


def test_e03_refuses_another_signal_as_the_candidate(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["operationalCandidate"].update(
            signal=3, id="api-ready-endpoints"
        ),
    )
    assert e03_findings(root) == {
        ("e03-candidate", "definition.operationalCandidate.signal")
    }


def test_e03_refuses_a_removed_comparator_role_statement(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["operationalCandidate"].pop("comparatorCondition"),
    )
    assert e03_findings(root) == {
        ("e03-candidate", "definition.operationalCandidate.comparatorCondition")
    }


@pytest.mark.parametrize("removed", ["compared with itself", "no ranking preference"])
def test_e03_refuses_a_comparator_statement_without_its_phrases(
    root: Path, removed: str
) -> None:
    def cut(document: dict[str, Any]) -> None:
        candidate = document["definition"]["operationalCandidate"]
        candidate["comparatorCondition"] = candidate["comparatorCondition"].replace(
            removed, "x"
        )

    edit(root, E03_RECORD, cut)
    assert e03_findings(root) == {
        ("e03-candidate", "definition.operationalCandidate.comparatorCondition")
    }


def test_e03_refuses_a_removed_uncounted_caller_failure_rule(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["definition"].pop("callerFailures"))
    assert e03_findings(root) == {("e03-caller-failures", "definition.callerFailures")}


def test_e03_refuses_a_failure_rule_that_misses_an_outcome_or_a_figure(
    root: Path,
) -> None:
    def cut(document: dict[str, Any]) -> None:
        failures = document["definition"]["callerFailures"]
        failures["outcomes"].pop(2)
        failures["report"].pop(1)
        failures["outcomes"][1]["canonicalErrorCode"] = "when-stated"

    edit(root, E03_RECORD, cut)
    assert e03_findings(root) == {
        ("e03-caller-failures", "definition.callerFailures.outcomes"),
        (
            "e03-caller-failures",
            "definition.callerFailures.outcomes[1].canonicalErrorCode",
        ),
        ("e03-caller-failures", "definition.callerFailures.report"),
    }


def test_e03_refuses_an_unanswered_freeze_field(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["fields"].pop("cleanupProcedure"))
    assert e03_findings(root) == {("e03-fields-unanswered", "fields.cleanupProcedure")}


def test_e03_refuses_a_pending_freeze_field(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["fields"]["topology"][0].update(
            status="pending", reason="later", owner="someone"
        ),
    )
    findings = e03_findings(root)
    assert ("e03-fields-unanswered", "fields.topology") in findings
    assert {rule for rule, _ in findings} == {
        "e03-fields-unanswered",
        "e03-source-fields-differ",
    }


def test_e03_refuses_a_source_field_that_differs_from_its_source(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        fields = document["fields"]
        fields["fault"][0]["value"]["sources"]["V2-E02C"] = "delete-runtime-pod"
        fields["topology"][0]["value"]["sources"]["V2-E02A"]["runtimeReplicas"] = 2
        fields["repetitionCount"][0]["value"]["sources"]["V2-E04"] = "2 runs"
        fields["environmentIdentity"][0]["value"]["environmentSha256"] = (
            "sha256:" + "0" * 64
        )

    edit(root, E03_RECORD, change)
    assert e03_findings(root) == {
        ("e03-source-fields-differ", "fields.fault.sources.V2-E02C"),
        ("e03-source-fields-differ", "fields.topology.sources.V2-E02A"),
        ("e03-source-fields-differ", "fields.repetitionCount.sources.V2-E04"),
        ("e03-source-fields-differ", "fields.environmentIdentity"),
    }


def test_e03_refuses_a_claim_of_synchronized_clocks(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["timeline"].update(
            meaning="The timelines are synchronized to the node clock."
        ),
    )
    assert e03_findings(root) == {
        ("e03-clock-contradiction", "definition.timeline.meaning")
    }


def test_e03_refuses_an_ordering_rule_without_the_margin(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"].update(ordering="A lag is stated when it is known."),
    )
    assert e03_findings(root) == {("e03-computations", "definition.ordering")}


def test_e03_refuses_a_missing_signal_read_as_healthy(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["computations"].update(
            notObserved="A signal that is not observed counts as healthy."
        ),
    )
    assert e03_findings(root) == {
        ("e03-computations", "definition.computations.notObserved")
    }


def test_e03_refuses_a_ranking_on_one_figure_alone(root: Path) -> None:
    edit(
        root, E03_RECORD, lambda d: d["definition"]["ranking"].update(figures=["outer"])
    )
    assert e03_findings(root) == {("e03-ranking", "definition.ranking.figures")}


def test_e03_refuses_a_scope_without_its_procedure_directory(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["materialScope"]["paths"].pop(0))
    assert e03_findings(root) == {("e03-analysis-code", "materialScope.paths")}


def test_e03_refuses_a_missing_record(root: Path) -> None:
    (root / E03_RECORD).unlink()
    assert e03_findings(root) == {("e03-record-missing", "$")}


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(definition=[]),
        lambda d: d["definition"].update(sources="V2-E02A"),
        lambda d: d["definition"].update(signals={"1": "caller"}),
        lambda d: d["definition"].update(population=[]),
        lambda d: d["definition"].update(operationalCandidate="api-error-rate"),
        lambda d: d["definition"].update(callerFailures=["timeout"]),
        lambda d: d["definition"]["signals"].__setitem__(1, "api-error-rate"),
        lambda d: d["definition"]["sources"].__setitem__(0, ["V2-E02A"]),
        lambda d: d.update(fields=[]),
        lambda d: d.update(materialScope=None),
    ],
)
def test_e03_reports_a_malformed_member_and_never_raises(
    root: Path, change: Callable[[dict[str, Any]], None]
) -> None:
    edit(root, E03_RECORD, change)
    findings = core.check_records(root, [E03])
    assert findings
    assert all(f.rule_id.startswith("e03-") for f in findings)


# --------------------------------------------------------------------------
# 3. V2-E06
# --------------------------------------------------------------------------


def test_e06_refuses_a_stale_source_digest(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["sources"][0].update(contentSha256="f" * 64),
    )
    assert e06_findings(root) == {
        ("e06-sources-stale", "definition.sources[0].contentSha256")
    }


def test_e06_refuses_a_view_labeled_measured_that_reads_requests_only(
    root: Path,
) -> None:
    edit(
        root, E06_RECORD, lambda d: d["definition"]["views"][0].update(label="measured")
    )
    assert e06_findings(root) == {("e06-labels", "definition.views[0].label")}


@pytest.mark.parametrize(
    "reads", [["limits"], ["claim-request"], ["requests", "limits"]]
)
def test_e06_refuses_a_metric_labeled_measured_that_reads_configuration_only(
    root: Path, reads: list[str]
) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["metrics"][4].update(label="measured", reads=reads),
    )
    assert e06_findings(root) == {("e06-labels", "definition.metrics[4].label")}


def test_e06_refuses_a_missing_utilization_statistic(root: Path) -> None:
    edit(root, E06_RECORD, lambda d: d["definition"]["utilization"].pop("statistic"))
    assert e06_findings(root) == {
        ("e06-utilization", "definition.utilization.statistic")
    }
    edit(root, E06_RECORD, lambda d: d["definition"].pop("utilization"))
    assert e06_findings(root) == {("e06-utilization", "definition.utilization")}


def test_e06_refuses_utilization_source_runs_that_are_not_fixed(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["utilization"]["sourceRuns"].update(
            experiments=["V2-E02B"]
        ),
    )
    assert e06_findings(root) == {
        ("e06-utilization", "definition.utilization.sourceRuns")
    }


def test_e06_refuses_a_missing_cost_basis(root: Path) -> None:
    edit(root, E06_RECORD, lambda d: d["definition"].pop("costBasis"))
    assert e06_findings(root) == {("e06-cost-basis", "definition.costBasis")}


def test_e06_refuses_a_cloud_cost_without_a_later_revision(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["costBasis"].update(
            basis="aws", cloud={"used": True}
        ),
    )
    assert e06_findings(root) == {
        ("e06-cost-basis", "definition.costBasis.basis"),
        ("e06-cost-basis", "definition.costBasis.cloud"),
    }


def test_e06_refuses_an_unanswered_freeze_field(root: Path) -> None:
    edit(root, E06_RECORD, lambda d: d["fields"].pop("evidencePaths"))
    assert e06_findings(root) == {("e06-fields-unanswered", "fields.evidencePaths")}


def test_e06_refuses_a_view_b_that_is_not_reconstructed(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["views"][1]["sides"][0].update(reconstructed=False),
    )
    assert e06_findings(root) == {("e06-views", "definition.views[view-b].sides")}


def test_e06_refuses_a_view_a_side_that_differs_from_its_source(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["views"][0]["sides"][0].update(runtimeReplicas=2),
    )
    assert e06_findings(root) == {("e06-views", "definition.views[view-a].sides")}


def test_e06_refuses_another_evidence_target(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["evidenceTarget"].update(allocation="C2"),
    )
    assert e06_findings(root) == {
        ("e06-evidence-target", "definition.evidenceTarget.allocation")
    }


def test_e06_refuses_a_missing_metric_or_headroom_definition(root: Path) -> None:
    def cut(document: dict[str, Any]) -> None:
        document["definition"]["metrics"].pop(5)
        document["definition"].pop("rolloutHeadroom")

    edit(root, E06_RECORD, cut)
    assert e06_findings(root) == {
        ("e06-metrics", "definition.metrics"),
        ("e06-metrics", "definition.rolloutHeadroom"),
    }


def test_e06_rules_do_not_read_the_e03_record(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["definition"].pop("signals"))
    assert e06_findings(root) == set()
    assert {rule for rule, _ in e03_findings(root)} >= {"e03-signal-set"}


def test_the_command_refuses_a_planted_defect(root: Path) -> None:
    edit(root, E06_RECORD, lambda d: d["definition"].pop("costBasis"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.analysis_preregistration",
            "--check",
            "--root",
            str(root),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "e06-cost-basis" in result.stdout
    assert "FAILED: 1 finding(s) across 2 analysis experiment(s)" in result.stdout
