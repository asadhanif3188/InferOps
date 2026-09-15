"""The V1 cost baseline in `tools/cost_baseline`, and the report that quotes it.

Nothing here contacts anything. The performance record, its inputs, and the baseline
are committed files; a refusal test builds a changed copy in memory or in a temporary
directory and breaks one thing.

It is heaviest where a baseline goes wrong without anyone noticing:

- **provenance** -- usage taken from a record that no longer regenerates from its raw
  evidence, that is not local real evidence, or that failed one of its own checks;
- **the reader** -- a window the samples do not bound, a counter reset stitched over,
  a missing reading interpolated, a request outside the window counted, or an
  identity guessed rather than observed;
- **independence** -- every usage value and every published figure recomputed here by
  a second route: integer sums over the committed JSONL lines, and `Decimal` over
  rates written out by hand, not the tool's own functions;
- **the report** -- a figure in the published baseline that the committed results do
  not hold.

The report's interpretation is checked by review only.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import re
import shutil
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from tools.cost_baseline import __main__ as cli
from tools.cost_baseline import core
from tools.cost_baseline.core import (
    CostBaselineError,
    CostBaselineRefused,
    derive_baseline,
    derive_run,
    exact_decimal,
    instant,
    observed_identity,
    pod_cpu_seconds,
    pod_memory_byte_seconds,
    read_sources,
    sample_window,
    workload_declaration,
)
from tools.cost_calculation import calculate, load_method
from tools.llm_load import core as load
from tools.performance_findings.core import checked_record
from tools.performance_scenarios.core import load_descriptor

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORD_DIR = REPO_ROOT / "docs" / "proof" / "serving"
RECORD_PREFIX = "v1-s4-004-pr1-"
BASELINE_DIR = REPO_ROOT / "docs" / "proof" / "cost"
BASELINE_PREFIX = "v1-s4-005-pr2-"
REPORT_PATH = BASELINE_DIR / "v1-s4-005-pr2-cost-baseline.md"
RUNS = (1, 2)

METHOD = load_method()
DESCRIPTOR = load_descriptor()
SOURCES = read_sources(DESCRIPTOR, RECORD_DIR, RECORD_PREFIX)
DERIVATION: dict[str, Any] = json.loads(
    (BASELINE_DIR / f"{BASELINE_PREFIX}baseline-derivation.v1alpha1.json").read_text(
        encoding="utf-8"
    )
)

#: The synthetic card's rates, written out here rather than read from the method.
CPU_RATE = Decimal("0.040000")
MEMORY_RATE = Decimal("0.005000")


def committed(name: str) -> dict[str, Any]:
    return json.loads((BASELINE_DIR / name).read_text(encoding="utf-8"))


def run_input(repetition: int) -> dict[str, Any]:
    return committed(f"{BASELINE_PREFIX}baseline-run-{repetition}.input.json")


def run_result(repetition: int) -> dict[str, Any]:
    return committed(f"{BASELINE_PREFIX}baseline-run-{repetition}.result.json")


def run_derivation(repetition: int) -> dict[str, Any]:
    return next(row for row in DERIVATION["runs"] if row["repetition"] == repetition)


def record_run(repetition: int) -> dict[str, Any]:
    return next(
        run for run in SOURCES.record["runs"] if run["repetition"] == repetition
    )


def six(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = 50
        return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))


def sample(at: int, cpu: int | None, memory: int | None) -> dict[str, Any]:
    reading = {"cpuNs": cpu, "memoryWorkingSetBytes": memory}
    return {
        "hostEpochMs": at,
        "hostReadMs": 1,
        "nodeClockNs": at * 1_000_000,
        "node": {"cpuNs": at * 10, "memoryWorkingSetBytes": 1},
        "pods": {role: dict(reading) for role in core.ROLES},
    }


# --------------------------------------------------------------------------
# The committed baseline
# --------------------------------------------------------------------------


def test_the_committed_baseline_regenerates_from_the_committed_evidence() -> None:
    files = derive_baseline(SOURCES, METHOD, BASELINE_PREFIX)
    assert sorted(files) == sorted(
        [
            *(
                f"{BASELINE_PREFIX}baseline-run-{n}.{kind}.json"
                for n in RUNS
                for kind in ("input", "result")
            ),
            f"{BASELINE_PREFIX}baseline-derivation.v1alpha1.json",
        ]
    )
    for name, text in files.items():
        on_disk = (
            (BASELINE_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        )
        assert on_disk == text, name


def test_every_committed_result_is_what_the_calculation_makes_of_its_input() -> None:
    for repetition in RUNS:
        assert calculate(run_input(repetition), METHOD) == run_result(repetition)


def test_the_verify_command_passes_on_the_committed_baseline(capsys) -> None:
    code = cli.main(
        [
            "verify",
            "--record-dir",
            str(RECORD_DIR),
            "--record-prefix",
            RECORD_PREFIX,
            "--dir",
            str(BASELINE_DIR),
            "--prefix",
            BASELINE_PREFIX,
        ]
    )
    assert code == cli.EXIT_OK, capsys.readouterr().err
    assert "5 committed baseline file(s) regenerate" in capsys.readouterr().out


def test_the_verify_command_fails_on_a_changed_result(tmp_path, capsys) -> None:
    for path in BASELINE_DIR.glob(f"{BASELINE_PREFIX}baseline-*.json"):
        shutil.copy(path, tmp_path / path.name)
    changed = tmp_path / f"{BASELINE_PREFIX}baseline-run-2.result.json"
    changed.write_text(
        changed.read_text(encoding="utf-8").replace("0.021775", "0.021776"),
        encoding="utf-8",
    )
    code = cli.main(
        [
            "verify",
            "--record-dir",
            str(RECORD_DIR),
            "--record-prefix",
            RECORD_PREFIX,
            "--dir",
            str(tmp_path),
            "--prefix",
            BASELINE_PREFIX,
        ]
    )
    assert code == cli.EXIT_FAILED
    assert "baseline-run-2.result.json" in capsys.readouterr().err


def test_every_input_is_measured_evidence_that_names_the_record_it_came_from() -> None:
    for repetition in RUNS:
        document = run_input(repetition)
        assert document["classification"] == "local-real-cpu"
        assert document["usageEvidence"]["path"] == (
            "docs/proof/serving/v1-s4-004-pr1-performance-record.v1alpha1.json"
        )
        assert "not typed in" in document["warning"]
        assert "synthetic rate card" in document["warning"]
        record = run_result(repetition)["records"][0]
        assert record["facts"]["hasMeasuredUtilisation"] is True
        assert record["cost"]["confidence"] == "none"
        assert record["cost"]["basis"] == "estimated"
        assert run_result(repetition)["publishedCostFigure"] is False


def test_a_result_is_one_workload_whose_lines_close_against_the_node() -> None:
    for repetition in RUNS:
        result = run_result(repetition)
        assert len(result["records"]) == 1
        amount = Decimal(result["records"][0]["cost"]["amount"])
        assert amount + Decimal(result["unallocated"]["amount"]) == Decimal(
            result["capacity"]["amount"]
        )
        assert result["totals"]["closes"] is True
        assert result["prerequisites"] == []


# --------------------------------------------------------------------------
# A second route to every value
# --------------------------------------------------------------------------


def _jsonl_samples() -> list[dict[str, Any]]:
    text = (RECORD_DIR / f"{RECORD_PREFIX}resource-samples.v1alpha1.jsonl").read_text(
        encoding="utf-8"
    )
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@pytest.mark.parametrize("repetition", RUNS)
def test_usage_recomputes_from_the_jsonl_lines_by_integer_sums(repetition: int) -> None:
    """Integers over the committed lines, without the tool's window or integral."""
    run = record_run(repetition)
    start = min(phase["startEpochMs"] for phase in run["phases"])
    end = max(phase["endEpochMs"] for phase in run["phases"])
    lines = _jsonl_samples()
    first = max(i for i, line in enumerate(lines) if line["hostEpochMs"] <= start)
    last = min(i for i, line in enumerate(lines) if line["hostEpochMs"] >= end)
    inside = lines[first : last + 1]

    cpu_ns = 0
    twice_memory_byte_ms = 0
    for role in ("api", "runtime"):
        cpu_ns += inside[-1]["pods"][role]["cpuNs"] - inside[0]["pods"][role]["cpuNs"]
        for a, b in pairwise(inside):
            twice_memory_byte_ms += (b["hostEpochMs"] - a["hostEpochMs"]) * (
                a["pods"][role]["memoryWorkingSetBytes"]
                + b["pods"][role]["memoryWorkingSetBytes"]
            )
    usage = run_input(repetition)["workloads"][0]["usage"]
    assert Decimal(usage["cpuSeconds"]) == Decimal(cpu_ns) / Decimal(10**9)
    assert Decimal(usage["memoryByteSeconds"]) == Decimal(
        twice_memory_byte_ms
    ) / Decimal(2000)
    window = run_input(repetition)["window"]
    assert window["start"] == instant(inside[0]["hostEpochMs"])
    assert window["end"] == instant(inside[-1]["hostEpochMs"])


@pytest.mark.parametrize("repetition", RUNS)
def test_traffic_recomputes_from_the_raw_lines(repetition: int) -> None:
    text = (RECORD_DIR / f"{RECORD_PREFIX}run-{repetition}-raw.jsonl").read_text(
        encoding="utf-8"
    )
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    requests = [row for row in rows if row.get("record") == "request"]
    assert requests, "the raw set holds no request line"
    successes = [row for row in requests if row["outcome"] == "success"]
    usage = run_input(repetition)["workloads"][0]["usage"]
    assert usage["requests"] == len(requests)
    assert usage["inputTokens"] == sum(row["inputTokens"] for row in successes)
    assert usage["outputTokens"] == sum(row["outputTokens"] for row in successes)
    # The record's own phase summaries say the same.
    phases = record_run(repetition)["phases"]
    assert usage["requests"] == sum(phase["load"]["dispatched"] for phase in phases)
    assert usage["inputTokens"] == sum(
        phase["load"]["tokens"]["inputTotal"] for phase in phases
    )


@pytest.mark.parametrize("repetition", RUNS)
def test_every_published_figure_recomputes_in_decimal_from_the_usage(
    repetition: int,
) -> None:
    usage = run_input(repetition)["workloads"][0]["usage"]
    derivation = run_derivation(repetition)
    result = run_result(repetition)
    record = result["records"][0]
    with localcontext() as context:
        context.prec = 60
        seconds = Decimal(derivation["window"]["hostSeconds"])
        hours = seconds / Decimal(3600)
        amount = (
            Decimal(usage["cpuSeconds"]) * CPU_RATE
            + Decimal(usage["memoryByteSeconds"]) / Decimal(2**30) * MEMORY_RATE
        ) / Decimal(3600)
        node = (
            Decimal(12) * CPU_RATE + Decimal("9.71605682373046875") * MEMORY_RATE
        ) * hours
        assert record["cost"]["amount"] == six(amount)
        assert record["derived"]["amountPerHour"] == six(amount / hours)
        assert record["derived"]["costPerThousandRequests"] == six(
            amount / Decimal(usage["requests"]) * 1000
        )
        assert record["derived"]["shareOfNodeCapacity"] == six(amount / node)
        assert result["capacity"]["amount"] == six(node)
        assert result["unallocated"]["amount"] == six(
            Decimal(six(node)) - Decimal(six(amount))
        )
        assert result["window"]["hours"] == six(hours)


@pytest.mark.parametrize("repetition", RUNS)
def test_the_token_unit_cost_is_null_below_the_minimum_and_says_so(
    repetition: int,
) -> None:
    record = run_result(repetition)["records"][0]
    tokens = record["usage"]["inputTokens"] + record["usage"]["outputTokens"]
    assert tokens < METHOD["denominatorRules"]["minimumTokensForUnitCost"]
    assert record["derived"]["costPerMillionTokens"] is None
    assert record["derived"]["costPerMillionTokensDenominator"] == tokens
    assert "below-minimum-sample" in record["completeness"]["reasons"]
    assert (
        record["usage"]["requests"]
        >= METHOD["denominatorRules"]["minimumRequestsForUnitCost"]
    )


@pytest.mark.parametrize("repetition", RUNS)
def test_the_window_average_agrees_with_the_records_own_phase_figures(
    repetition: int,
) -> None:
    """The record computed per-phase rates from inner samples; the window must agree."""
    check = run_derivation(repetition)["crossCheck"]
    phases = check["runtimePhaseMillicores"]
    window = check["runtimeWindowMillicores"]
    # The window also holds the idle seconds before the first phase, so it may sit a
    # little below every phase, and never above the busiest one.
    assert min(phases) * 0.99 <= window <= max(phases), (window, phases)


@pytest.mark.parametrize("repetition", RUNS)
def test_the_unallocated_use_closes_and_prices_to_the_unallocated_line(
    repetition: int,
) -> None:
    use = run_derivation(repetition)["unallocatedUse"]
    cpu = {key: Decimal(value) for key, value in use["processorSeconds"].items()}
    memory = {key: Decimal(value) for key, value in use["memoryByteSeconds"].items()}
    assert cpu["capacity"] == (
        cpu["workload"]
        + cpu["releasePlatformPods"]
        + cpu["nodeOutsideRelease"]
        + cpu["idle"]
    )
    assert memory["capacity"] == (
        memory["workload"]
        + memory["releasePlatformPods"]
        + memory["nodeOutsideRelease"]
        + memory["notInWorkingSet"]
    )
    with localcontext() as context:
        context.prec = 60
        unallocated = (
            (cpu["capacity"] - cpu["workload"]) * CPU_RATE
            + (memory["capacity"] - memory["workload"]) / Decimal(2**30) * MEMORY_RATE
        ) / Decimal(3600)
    published = Decimal(run_result(repetition)["unallocated"]["amount"])
    # The published line is taken from two published figures, so it may differ from
    # the exact value by the two roundings.
    assert abs(unallocated - published) <= Decimal("0.000001")


def test_the_collector_is_measured_and_left_on_the_unallocated_line() -> None:
    for repetition in RUNS:
        pods = run_derivation(repetition)["pods"]
        assert pods["collector"]["attributedTo"] == "unallocated"
        assert {pods[role]["attributedTo"] for role in ("api", "runtime")} == {
            "workload"
        }
        usage = run_input(repetition)["workloads"][0]["usage"]
        assert Decimal(usage["cpuSeconds"]) == Decimal(
            pods["api"]["cpuSeconds"]
        ) + Decimal(pods["runtime"]["cpuSeconds"])


# --------------------------------------------------------------------------
# The reader's rules
# --------------------------------------------------------------------------


def test_the_window_is_bounded_by_samples_on_both_sides() -> None:
    samples = [sample(at, 0, 0) for at in (1000, 2000, 3000, 4000)]
    window = sample_window(samples, 1500, 3500)
    assert (window.start_ms, window.end_ms) == (1000, 4000)
    exact = sample_window(samples, 2000, 3000)
    assert (exact.start_ms, exact.end_ms) == (2000, 3000)


@pytest.mark.parametrize(
    ("start", "end", "fragment"),
    [(500, 3500, "at or before its start"), (1500, 4500, "at or after its end")],
)
def test_a_window_the_samples_do_not_bound_is_refused(
    start: int, end: int, fragment: str
) -> None:
    samples = [sample(at, 0, 0) for at in (1000, 2000, 3000, 4000)]
    with pytest.raises(CostBaselineRefused, match=fragment):
        sample_window(samples, start, end)


def test_samples_out_of_time_order_are_refused() -> None:
    samples = [sample(at, 0, 0) for at in (1000, 3000, 2000, 4000)]
    with pytest.raises(CostBaselineError, match="time order"):
        sample_window(samples, 1000, 4000)


def test_processor_seconds_are_the_increase_between_the_bounding_samples() -> None:
    samples = [
        sample(1000, 5 * 10**9, 0),
        sample(2000, 6 * 10**9, 0),
        sample(3000, 8 * 10**9, 0),
    ]
    assert pod_cpu_seconds(sample_window(samples, 1000, 3000), "runtime") == 3


def test_a_counter_reset_inside_the_window_is_not_stitched() -> None:
    samples = [
        sample(1000, 5 * 10**9, 0),
        sample(2000, 10**9, 0),
        sample(3000, 2 * 10**9, 0),
    ]
    assert pod_cpu_seconds(sample_window(samples, 1000, 3000), "runtime") is None


def test_memory_is_integrated_trapezoidally_and_never_extrapolated() -> None:
    samples = [sample(1000, 0, 100), sample(2000, 0, 300), sample(4000, 0, 300)]
    window = sample_window(samples, 1000, 4000)
    # (1 s x (100 + 300) / 2) + (2 s x (300 + 300) / 2)
    assert pod_memory_byte_seconds(window, "api") == 200 + 600


def test_a_missing_reading_inside_the_window_is_refused_rather_than_interpolated() -> (
    None
):
    samples = [sample(1000, 0, 100), sample(2000, None, None), sample(3000, 0, 100)]
    window = sample_window(samples, 1000, 3000)
    with pytest.raises(CostBaselineRefused, match="no cpuNs reading"):
        pod_cpu_seconds(window, "runtime")
    with pytest.raises(CostBaselineRefused, match="no memoryWorkingSetBytes reading"):
        pod_memory_byte_seconds(window, "runtime")


def test_a_reset_makes_the_amount_and_the_unallocated_line_null() -> None:
    run = record_run(1)
    start = min(phase["startEpochMs"] for phase in run["phases"])
    samples = [dict(item) for item in SOURCES.samples]
    index = next(
        i for i, item in enumerate(samples) if item["hostEpochMs"] > start + 60_000
    )
    broken = copy.deepcopy(samples[index])
    broken["pods"]["runtime"]["cpuNs"] = 1
    samples[index] = broken
    for later in range(index + 1, len(samples)):
        moved = copy.deepcopy(samples[later])
        moved["pods"]["runtime"]["cpuNs"] = (
            samples[later]["pods"]["runtime"]["cpuNs"] - 10**12
        )
        samples[later] = moved
    sources = dataclasses.replace(SOURCES, samples=samples)
    identity = observed_identity(SOURCES.telemetry, SOURCES.values_text)
    document, derivation = derive_run(sources, run, identity)
    workload = document["workloads"][0]
    assert workload["usage"]["cpuSeconds"] is None
    assert workload["unavailable"] == {"cpu-seconds": "input-conflict"}
    assert derivation["pods"]["runtime"]["counterReset"] is True
    result = calculate(document, METHOD)
    assert result["records"][0]["cost"]["amount"] is None
    assert result["unallocated"]["amount"] is None
    assert result["unallocated"]["unavailableReasons"] == ["input-conflict"]


def test_a_request_outside_the_window_is_refused() -> None:
    run = record_run(1)
    raw = SOURCES.raw_sets[run["rawFile"]]
    late = dataclasses.replace(
        raw.records[-1], latency_ms=raw.records[-1].latency_ms + 60_000
    )
    sources = dataclasses.replace(
        SOURCES,
        raw_sets={
            **SOURCES.raw_sets,
            run["rawFile"]: dataclasses.replace(raw, records=(*raw.records[:-1], late)),
        },
    )
    identity = observed_identity(SOURCES.telemetry, SOURCES.values_text)
    with pytest.raises(CostBaselineRefused, match="outside the window"):
        derive_run(sources, run, identity)


def test_a_disagreeing_reconciliation_makes_the_count_null() -> None:
    run = copy.deepcopy(record_run(2))
    for row in run["reconciliation"]:
        row["agrees"] = False
    identity = observed_identity(SOURCES.telemetry, SOURCES.values_text)
    document, _ = derive_run(SOURCES, run, identity)
    workload = document["workloads"][0]
    assert workload["usage"]["requests"] is None
    assert workload["usage"]["outputTokens"] is None
    assert workload["unavailable"] == {
        "output-tokens": "input-conflict",
        "requests": "input-conflict",
    }
    record = calculate(document, METHOD)["records"][0]
    assert record["cost"]["amount"] is not None
    assert record["derived"]["costPerThousandRequests"] is None


# --------------------------------------------------------------------------
# Identity, declaration, and provenance
# --------------------------------------------------------------------------


def test_identity_is_observed_from_the_collectors_labels() -> None:
    identity = observed_identity(SOURCES.telemetry, SOURCES.values_text)
    assert identity == {
        "workloadId": "support-assistant",
        "modelId": "qwen3-1-7b-q8-0",
        "runtimeId": "llama-cpp-server",
        "environment": "dev",
        "ownerId": "team-platform-demo",
    }


def test_an_identity_label_with_two_values_is_refused() -> None:
    telemetry = copy.deepcopy(dict(SOURCES.telemetry))
    telemetry["extra"] = {"labels": {"inferops_workload_id": "another-workload"}}
    with pytest.raises(CostBaselineRefused, match="2 value"):
        observed_identity(telemetry, SOURCES.values_text)


def test_values_declaring_another_workload_are_refused() -> None:
    values = SOURCES.values_text.replace(
        "workloadId: support-assistant", "workloadId: another-workload"
    )
    with pytest.raises(CostBaselineRefused, match="workload the collector observed"):
        observed_identity(SOURCES.telemetry, values)


def test_the_declaration_sums_the_request_paths_pods() -> None:
    declaration = workload_declaration(SOURCES.environment)
    # api 100m + runtime 1 core; api 128Mi + runtime 2Gi.
    assert declaration == {
        "cpuRequest": "1100m",
        "memoryRequest": str(128 * 2**20 + 2 * 2**30),
        "acceleratorType": "none",
        "acceleratorCount": 0,
        "replicas": 1,
    }


def test_a_request_path_with_different_replica_counts_is_refused() -> None:
    environment = copy.deepcopy(dict(SOURCES.environment))
    environment["workloads"]["api"]["desiredReplicas"] = 2
    environment["workloads"]["api"]["availableReplicas"] = 2
    with pytest.raises(CostBaselineRefused, match="different replica counts"):
        workload_declaration(environment)


def test_a_record_that_is_not_local_real_evidence_is_refused(monkeypatch) -> None:
    original = checked_record

    def relabelled(*args: Any, **kwargs: Any) -> dict[str, Any]:
        record = copy.deepcopy(original(*args, **kwargs))
        record["evidenceClass"] = "mock"
        return record

    monkeypatch.setattr(core, "checked_record", relabelled)
    with pytest.raises(CostBaselineRefused, match="'mock' evidence"):
        read_sources(DESCRIPTOR, RECORD_DIR, RECORD_PREFIX)


def test_a_record_whose_own_check_failed_is_refused(monkeypatch) -> None:
    original = checked_record

    def failed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        record = copy.deepcopy(original(*args, **kwargs))
        for check in record["checks"]:
            if check["checkId"] == "zero-container-restarts":
                check["passed"] = False
        return record

    monkeypatch.setattr(core, "checked_record", failed)
    with pytest.raises(CostBaselineRefused, match="zero-container-restarts"):
        read_sources(DESCRIPTOR, RECORD_DIR, RECORD_PREFIX)


def test_a_record_that_does_not_regenerate_is_refused(tmp_path) -> None:
    for path in RECORD_DIR.glob(f"{RECORD_PREFIX}*"):
        shutil.copy(path, tmp_path / path.name)
    samples = tmp_path / f"{RECORD_PREFIX}resource-samples.v1alpha1.jsonl"
    text = samples.read_text(encoding="utf-8")
    samples.write_text(
        text.replace('"cpuNs":3266198000', '"cpuNs":3266198001', 1), encoding="utf-8"
    )
    with pytest.raises(CostBaselineRefused, match="cannot be read from"):
        read_sources(DESCRIPTOR, tmp_path, RECORD_PREFIX)


def test_a_record_outside_the_committed_evidence_is_refused(tmp_path) -> None:
    for path in RECORD_DIR.glob(f"{RECORD_PREFIX}*"):
        shutil.copy(path, tmp_path / path.name)
    with pytest.raises(CostBaselineRefused, match="not inside this repository"):
        read_sources(DESCRIPTOR, tmp_path, RECORD_PREFIX)


def test_a_values_file_the_experiment_did_not_execute_is_refused(monkeypatch) -> None:
    """The record regenerates from the real tree; only the values file's digest moves."""
    monkeypatch.setattr(core, "file_digest", lambda path: "0" * 64)
    with pytest.raises(
        CostBaselineRefused, match="not the file the experiment executed"
    ):
        read_sources(DESCRIPTOR, RECORD_DIR, RECORD_PREFIX)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Fraction(0), "0"),
        (Fraction(12), "12"),
        (Fraction(14311731, 5_000_000), "2.8623462"),
        (Fraction(10188024, 2**20), "9.71605682373046875"),
        (Fraction(1, 1000), "0.001"),
    ],
)
def test_exact_decimal_writes_every_digit_and_no_more(
    value: Fraction, text: str
) -> None:
    assert exact_decimal(value, "value") == text
    assert Fraction(text) == value


@pytest.mark.parametrize("value", [Fraction(1, 3), Fraction(-1, 2)])
def test_exact_decimal_refuses_a_value_it_would_have_to_round(value: Fraction) -> None:
    with pytest.raises(CostBaselineError):
        exact_decimal(value, "value")


def test_an_instant_is_utc_at_millisecond_precision() -> None:
    assert instant(1789402646077) == "2026-09-14T16:17:26.077Z"
    assert instant(1789402646000) == "2026-09-14T16:17:26.000Z"


def test_the_refusal_exit_code_is_returned_for_unreadable_evidence(
    tmp_path, capsys
) -> None:
    code = cli.main(
        [
            "derive",
            "--record-dir",
            str(tmp_path),
            "--record-prefix",
            RECORD_PREFIX,
            "--dir",
            str(tmp_path / "out"),
            "--prefix",
            BASELINE_PREFIX,
        ]
    )
    assert code == cli.EXIT_REFUSED
    assert "REFUSED cost baseline" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------

SIX_PLACES = re.compile(r"(?<![0-9.])[0-9]+\.[0-9]{6}(?![0-9])")


def test_the_report_quotes_no_six_place_figure_the_results_do_not_hold() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    held: set[str] = set()
    for repetition in RUNS:
        held |= set(SIX_PLACES.findall(json.dumps(run_result(repetition))))
    held |= {"0.040000", "0.005000", "1.200000", "0.000100"}
    quoted = set(SIX_PLACES.findall(report))
    assert quoted, "the report quotes no figure"
    assert quoted <= held, sorted(quoted - held)


def test_the_report_quotes_every_headline_figure_of_both_runs() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    for repetition in RUNS:
        result = run_result(repetition)
        record = result["records"][0]
        for figure in (
            record["cost"]["amount"],
            record["derived"]["amountPerHour"],
            record["derived"]["costPerThousandRequests"],
            result["unallocated"]["amount"],
            result["capacity"]["amount"],
        ):
            assert figure in report, (repetition, figure)


def test_the_report_carries_its_boundary() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    for phrase in (
        "synthetic",
        "confidence `none`",
        "not a bill",
        "no cost figure is published",
    ):
        assert phrase in report, phrase


@pytest.mark.parametrize("repetition", RUNS)
def test_the_warm_up_is_inside_the_window_and_its_requests_are_counted(
    repetition: int,
) -> None:
    """A run's cost covers its whole load span, warm-up included, and says so."""
    run = record_run(repetition)
    raw = SOURCES.raw_sets[run["rawFile"]]
    warm_up = [request for request in raw.records if request.phase == load.PHASE_WARMUP]
    assert warm_up, "the run holds no warm-up request"
    derivation = run_derivation(repetition)
    first_phase = run["phases"][0]
    assert first_phase["role"] == "warm-up"
    assert derivation["window"]["loadStartEpochMs"] == first_phase["startEpochMs"]
    assert derivation["traffic"]["requests"] == len(raw.records)
    assert derivation["traffic"]["requests"] == 60 * 3 + len(warm_up)


def test_the_report_prices_no_reservation_beside_the_estimate() -> None:
    """ADR 0014 D1: an allocation of the same window is never set beside an estimate."""
    report = REPORT_PATH.read_text(encoding="utf-8").lower()
    for phrase in (
        r"price on the reservation",
        r"allocation would have",
        r"\ballocated amount",
    ):
        assert not re.search(phrase, report), phrase


def test_the_synthetic_card_names_the_baseline_in_its_own_scope() -> None:
    """The card says what it prices; the baseline is one of those things."""
    source = next(
        row
        for row in METHOD["priceSources"]
        if row["priceSourceId"] == "synthetic-illustrative-v1"
    )
    assert "cost baseline" in source["scope"]
    assert source["scope"].endswith("and nothing else")
