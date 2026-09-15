"""The figures derived from the committed performance record, and the report quoting them.

Nothing here sends load or contacts anything. The record, its inputs, and the findings
are committed files; a refusal test copies them into a temporary directory and breaks
one thing.

It is heaviest where an analysis goes wrong without anyone noticing:

- **provenance** -- findings derived from a record that no longer regenerates from its
  raw evidence, that failed its own checks, or that claims a benchmark, capacity, or a
  saturation judgement;
- **arithmetic** -- a ratio, a completion gap, a gauge maximum, or a counter reading
  taken from outside the window it describes;
- **the report** -- a table in the published findings that no longer says what the
  findings file computes.

The report's prose, including its degradation statement, is checked by review only.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from tools.llm_load import core as load
from tools.performance_findings import __main__ as cli
from tools.performance_findings import core
from tools.performance_findings.core import (
    BOUNDARY,
    FindingsError,
    FindingsRefused,
    completion_gaps_ms,
    derive_findings,
    gauge_maximum,
    ratio_milli,
    read_inputs,
    reading_at,
)
from tools.performance_scenarios.core import dumps, load_descriptor

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
PROOF_DIR = REPO_ROOT / "docs/proof/serving"
RECORD_PREFIX = "v1-s4-004-pr1-"
FINDINGS_PATH = PROOF_DIR / "v1-s4-004-pr2-findings.v1alpha1.json"
REPORT_PATH = PROOF_DIR / "v1-s4-004-pr2-performance-findings.md"
FINDINGS: dict[str, Any] = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
REPORT = REPORT_PATH.read_text(encoding="utf-8")
DESCRIPTOR = load_descriptor()
#: The report writes a range with an en dash.
RANGE = chr(0x2013)


def _request(sequence: int, offset: int, latency: int, outcome: str = "success"):
    return load.RequestRecord(
        sequence=sequence,
        phase="measured",
        level_id="c2",
        concurrency=2,
        worker=0,
        dispatch_offset_ms=offset,
        latency_ms=latency,
        outcome=outcome,
        status=200,
        error_code=None,
        error_condition=None,
        finish_reason="stop",
        input_tokens=35,
        output_tokens=17,
        adapter_kind="real",
        model_ref="qwen3-1-7b-q8-0",
    )


@pytest.fixture
def copied(tmp_path: Path) -> Path:
    for path in PROOF_DIR.glob(f"{RECORD_PREFIX}*"):
        if path.suffix in (".json", ".jsonl"):
            shutil.copy(path, tmp_path / path.name)
    return tmp_path


def _edit_record(directory: Path, change) -> None:
    path = directory / f"{RECORD_PREFIX}performance-record.v1alpha1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(dumps(document), encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------


def test_the_committed_findings_regenerate_from_the_committed_record() -> None:
    derived = derive_findings(DESCRIPTOR, read_inputs(PROOF_DIR, RECORD_PREFIX))
    assert dumps(derived) == FINDINGS_PATH.read_text(encoding="utf-8").replace(
        "\r\n", "\n"
    )


def test_verify_passes_on_the_committed_findings(capsys) -> None:
    code = cli.main(
        [
            "verify",
            "--dir",
            str(PROOF_DIR),
            "--record-prefix",
            RECORD_PREFIX,
            "--findings",
            str(FINDINGS_PATH),
        ]
    )
    assert code == cli.EXIT_OK
    assert "regenerate" in capsys.readouterr().out


def test_verify_fails_when_the_committed_findings_differ(copied: Path, capsys) -> None:
    altered = copied / "findings.json"
    document = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    document["phases"][0]["p50ToBaselineMilli"] = 999
    altered.write_text(dumps(document), encoding="utf-8")
    code = cli.main(
        [
            "verify",
            "--dir",
            str(copied),
            "--record-prefix",
            RECORD_PREFIX,
            "--findings",
            str(altered),
        ]
    )
    assert code == cli.EXIT_FAILED
    assert "not what the record's inputs produce" in capsys.readouterr().err


@pytest.mark.parametrize(
    "flag", ["productionBenchmark", "portableCapacityClaim", "saturationJudged"]
)
def test_a_record_claiming_a_benchmark_capacity_or_saturation_is_refused(
    copied: Path, flag: str
) -> None:
    _edit_record(copied, lambda document: document.__setitem__(flag, True))
    with pytest.raises(FindingsRefused, match=flag):
        derive_findings(DESCRIPTOR, read_inputs(copied, RECORD_PREFIX))


def test_a_record_without_its_boundary_is_refused(copied: Path) -> None:
    _edit_record(copied, lambda document: document.__setitem__("boundary", " "))
    with pytest.raises(FindingsRefused, match="boundary"):
        derive_findings(DESCRIPTOR, read_inputs(copied, RECORD_PREFIX))


def test_an_unusable_record_is_refused(copied: Path) -> None:
    _edit_record(copied, lambda document: document.__setitem__("usable", False))
    with pytest.raises(FindingsRefused, match="not usable"):
        derive_findings(DESCRIPTOR, read_inputs(copied, RECORD_PREFIX))


def test_a_record_that_does_not_regenerate_is_refused(copied: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        document["runs"][0]["phases"][1]["load"]["latencyOfSuccesses"]["p50Ms"] = 1

    _edit_record(copied, change)
    with pytest.raises(FindingsRefused, match="does not regenerate"):
        derive_findings(DESCRIPTOR, read_inputs(copied, RECORD_PREFIX))


def test_a_changed_raw_set_is_refused_even_with_the_record_untouched(
    copied: Path,
) -> None:
    raw = copied / f"{RECORD_PREFIX}run-2-raw.jsonl"
    text = raw.read_text(encoding="utf-8")
    raw.write_text(
        text.replace('"latencyMs":1700,', '"latencyMs":1699,', 1),
        encoding="utf-8",
        newline="\n",
    )
    assert raw.read_text(encoding="utf-8") != text
    with pytest.raises(FindingsRefused):
        derive_findings(DESCRIPTOR, read_inputs(copied, RECORD_PREFIX))


def test_the_cli_refuses_a_missing_record_with_the_refusal_code(
    tmp_path: Path, capsys
) -> None:
    code = cli.main(
        [
            "derive",
            "--dir",
            str(tmp_path),
            "--record-prefix",
            RECORD_PREFIX,
            "--findings",
            str(tmp_path / "out.json"),
        ]
    )
    assert code == cli.EXIT_REFUSED
    assert "REFUSED" in capsys.readouterr().err
    assert not (tmp_path / "out.json").exists()


def test_the_findings_carry_their_boundary_and_their_source() -> None:
    assert FINDINGS["boundary"] == BOUNDARY
    assert FINDINGS["productionBenchmark"] is False
    assert FINDINGS["portableCapacityClaim"] is False
    assert FINDINGS["saturationJudged"] is False
    assert FINDINGS["evidenceClass"] == "local-real-cpu"
    assert FINDINGS["source"]["recordFile"] == (
        f"{RECORD_PREFIX}performance-record.v1alpha1.json"
    )


# --------------------------------------------------------------------------
# Arithmetic
# --------------------------------------------------------------------------


def test_a_ratio_is_in_thousandths_and_rounds_half_up() -> None:
    assert ratio_milli(3504, 1744) == 2009
    assert ratio_milli(1, 2000) == 1
    assert ratio_milli(1, 2001) == 0
    with pytest.raises(FindingsError):
        ratio_milli(1, 0)


def test_completion_gaps_are_taken_in_completion_order_not_dispatch_order() -> None:
    records = [
        _request(0, 0, 3500),
        _request(1, 0, 1700),
        _request(2, 1700, 3400),
    ]
    assert completion_gaps_ms(records) == [1800, 1600]


def test_a_gauge_maximum_uses_only_points_inside_the_window() -> None:
    points = [(1000, 9), (2000, 1), (3000, 3), (4000, 9)]
    assert gauge_maximum(points, 2000, 3000) == {"points": 2, "maximum": 3}
    assert gauge_maximum(points, 2500, 2600) == {"points": 0, "maximum": None}


def test_a_counter_reading_is_the_last_step_at_or_before_the_moment() -> None:
    points = [(1000, 0), (2000, 217), (3000, 400)]
    assert reading_at(points, 2999) == 217
    assert reading_at(points, 3000) == 400
    assert reading_at(points, 999) is None


def test_kubernetes_quantities_are_read_or_refused() -> None:
    assert core.cpu_millicores("6") == 6000
    assert core.cpu_millicores("500m") == 500
    assert core.memory_bytes("3Gi") == 3 * 1024**3
    with pytest.raises(FindingsError):
        core.cpu_millicores("1Gi")
    with pytest.raises(FindingsError):
        core.memory_bytes("1.5Gi")


def test_a_flag_set_twice_in_the_runtime_arguments_is_refused() -> None:
    assert core.argument_value(["--parallel", "1"], "--parallel") == "1"
    with pytest.raises(FindingsError):
        core.argument_value(["--parallel", "1", "--parallel", "2"], "--parallel")
    with pytest.raises(FindingsError):
        core.argument_value(["--parallel"], "--parallel")


# --------------------------------------------------------------------------
# The committed findings: the facts the report's statement rests on
# --------------------------------------------------------------------------


def _measured() -> list[dict[str, Any]]:
    return list(FINDINGS["phases"])


def test_every_measured_phase_of_both_runs_is_present() -> None:
    assert [(phase["repetition"], phase["scenarioId"]) for phase in _measured()] == [
        (1, "c1"),
        (1, "c2"),
        (1, "c4"),
        (2, "c1"),
        (2, "c2"),
        (2, "c4"),
    ]


def test_the_runtime_never_read_more_than_one_request_processing() -> None:
    for phase in _measured():
        collector = phase["collector"]
        assert collector["runtimeRequestsProcessing"]["maximum"] == 1
        assert (
            collector["runtimeRequestsDeferred"]["maximum"] == phase["concurrency"] - 1
        )
        assert collector["apiRequestsInFlight"]["maximum"] == phase["concurrency"]


def test_the_setup_the_statement_names_is_the_recorded_one() -> None:
    setup = FINDINGS["setup"]
    assert setup["provider"] == "docker-desktop"
    assert setup["runtime"]["parallelSlots"] == 1
    assert setup["runtime"]["threads"] == 6
    assert setup["runtime"]["cpuLimitMillicores"] == 6000
    assert setup["runtime"]["replicas"] == 1
    for text in (
        setup["runtime"]["image"],
        setup["model"]["revision"],
        setup["loadProfileSha256"],
        setup["descriptorSha256"],
    ):
        assert text in REPORT


def test_no_request_failed_and_every_input_token_was_counted() -> None:
    assert FINDINGS["acrossMeasuredPhases"]["unsuccessful"] == 0
    for run in FINDINGS["runs"]:
        assert run["tokens"]["apiInputCounter"]["agreesWithRawSet"] is True


# --------------------------------------------------------------------------
# The report's tables say what the findings compute
# --------------------------------------------------------------------------


def _decimal(milli: int) -> str:
    return f"{milli // 1000}.{milli % 1000:03d}"


def _percent(milli: int) -> str:
    return f"{milli // 10}.{milli % 10}%"


def _assert_rows(rows: list[str]) -> None:
    missing = [row for row in rows if row not in REPORT]
    assert not missing, "the report does not carry these rows:\n" + "\n".join(missing)


def test_the_latency_and_rate_table_matches_the_findings() -> None:
    _assert_rows(
        [
            f"| {p['repetition']} | `{p['scenarioId']}` | {p['concurrency']} | "
            f"{p['latencyMs']['p50Ms']} | {p['latencyMs']['p95Ms']} | "
            f"{p['latencyMs']['p99Ms']} | {_decimal(p['p50ToBaselineMilli'])} | "
            f"{_decimal(p['p95ToBaselineMilli'])} | "
            f"{_decimal(p['successfulRequestsPerSecondMilli'])} | "
            f"{_decimal(p['rateToBaselineMilli'])} |"
            for p in _measured()
        ]
    )


def test_the_serving_table_matches_the_findings() -> None:
    rows = []
    for p in _measured():
        gap = p["completionGapMs"]
        collector = p["collector"]
        rows.append(
            f"| {p['repetition']} | `{p['scenarioId']}` | "
            f"{gap['minMs']} / {gap['p50Ms']} / {gap['maxMs']} | "
            f"{collector['runtimeRequestsProcessing']['maximum']} | "
            f"{collector['runtimeRequestsDeferred']['maximum']} | "
            f"{collector['apiRequestsInFlight']['maximum']} | "
            f"{collector['runtimeRequestsProcessing']['points']} | "
            f"{p['fastestRequestPosition']} |"
        )
    _assert_rows(rows)


def test_the_resource_table_matches_the_findings() -> None:
    _assert_rows(
        [
            f"| {p['repetition']} | `{p['scenarioId']}` | "
            f"{p['runtimeCpu']['millicores']} | {_percent(p['runtimeCpu']['ofLimitMilli'])} | "
            f"{p['runtimeMemory']['peakWorkingSetBytes']} | "
            f"{_percent(p['runtimeMemory']['ofLimitMilli'])} | "
            f"{p['nodeOutsideReleaseCpuMillicores']} |"
            for p in _measured()
        ]
    )


def test_the_token_table_matches_the_findings() -> None:
    rows = []
    for run in FINDINGS["runs"]:
        tokens = run["tokens"]
        counter = tokens["apiInputCounter"]
        increase = str(counter["increase"]) + (
            " (absent before, read as 0)" if counter["absentBeforeReadAsZero"] else ""
        )
        requests = sum(
            p["requests"]["dispatched"]
            for p in _measured()
            if p["repetition"] == run["repetition"]
        ) + len(run["warmUp"]["latenciesMsInDispatchOrder"])
        rows.append(
            f"| {run['repetition']} | {requests} | {tokens['inputSentByRawSet']} | "
            f"{increase} | {tokens['outputRecordedByRawSet']} | "
            f"{tokens['runtimePromptTokens']['increase']} |"
        )
    _assert_rows(rows)


def test_the_between_runs_table_matches_the_findings() -> None:
    def span(values: list[int]) -> str:
        return f"{values[0]}{RANGE}{values[1]}"

    _assert_rows(
        [
            f"| `{level['scenarioId']}` | {span(level['p50MsRange'])} | "
            f"{span(level['p95MsRange'])} | {span(level['p99MsRange'])} | "
            f"{_decimal(level['successfulRequestsPerSecondMilliRange'][0])}{RANGE}"
            f"{_decimal(level['successfulRequestsPerSecondMilliRange'][1])} |"
            for level in FINDINGS["levels"]
        ]
    )


def test_the_dashboard_table_matches_the_findings() -> None:
    raw = {(p["repetition"], p["scenarioId"]): p for p in _measured()}
    rows = []
    for capture in FINDINGS["dashboardAtPhaseEnd"]:
        key = (capture["repetition"], capture["scenarioId"])
        if key not in raw:
            continue
        panel = capture["latencyQuantilesMs"]
        phase = raw[key]
        rows.append(
            f"| {key[0]} | `{key[1]}` | {panel['p50']} | {panel['p95']} | "
            f"{panel['p99']} | {phase['latencyMs']['p50Ms']} | "
            f"{phase['latencyMs']['p95Ms']} | {phase['latencyMs']['p99Ms']} | "
            f"{_decimal(capture['requestsPerSecondMilli'])} | "
            f"{_decimal(phase['successfulRequestsPerSecondMilli'])} |"
        )
    assert len(rows) == 6
    _assert_rows(rows)


def test_the_warm_up_latencies_the_report_quotes_are_the_recorded_ones() -> None:
    for run in FINDINGS["runs"]:
        first, second, third = run["warmUp"]["latenciesMsInDispatchOrder"]
        assert f"{first}, {second}, and {third} ms" in REPORT


def test_the_report_refuses_the_readings_adr_0013_forbids() -> None:
    for phrase in (
        "not InferOps's capacity",
        "not a production SLO",
        "not a\n> benchmark",
        "says nothing\n  about `kind`",
    ):
        assert phrase in REPORT, phrase


# --------------------------------------------------------------------------
# Refusals added after review: malformed setup values and short phases
# --------------------------------------------------------------------------


def _committed_record() -> dict[str, Any]:
    return json.loads(
        (PROOF_DIR / f"{RECORD_PREFIX}performance-record.v1alpha1.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.mark.parametrize(
    "key", ["INFEROPS_MAX_OUTPUT_TOKENS", "INFEROPS_REQUEST_TIMEOUT_MS"]
)
def test_a_non_numeric_configuration_value_is_a_named_refusal(key: str) -> None:
    record = _committed_record()
    record["environment"]["configuration"][key] = "abc"
    with pytest.raises(FindingsError, match=key):
        core._setup(record)


@pytest.mark.parametrize("flag", ["--parallel", "--threads", "--ctx-size"])
def test_a_non_numeric_runtime_argument_is_a_named_refusal(flag: str) -> None:
    record = _committed_record()
    arguments = record["environment"]["workloads"]["runtime"]["containers"][0]["args"]
    arguments[arguments.index(flag) + 1] = "abc"
    with pytest.raises(FindingsError, match=flag):
        core._setup(record)


def test_a_phase_with_one_completion_has_no_gap_and_says_so() -> None:
    with pytest.raises(FindingsError, match="fewer than two"):
        completion_gaps_ms([_request(0, 0, 100)])


def test_an_input_token_read_comes_from_the_scheduled_instant() -> None:
    telemetry = {
        "instants": [
            {
                "seriesId": "api-tokens-by-direction",
                "repetition": 1,
                "position": "after",
                "status": "success",
                "rows": [
                    {"labels": {"inferops_token_direction": "input"}, "value": "70"},
                    {"labels": {"inferops_token_direction": "output"}, "value": "34"},
                ],
            },
            {
                "seriesId": "api-tokens-by-direction",
                "repetition": 1,
                "position": "before",
                "status": "success",
                "rows": [],
            },
        ]
    }
    labels = {"inferops_token_direction": "input"}
    series = "api-tokens-by-direction"
    assert core.instant_total(telemetry, series, 1, "after", labels) == 70
    assert core.instant_total(telemetry, series, 1, "before", labels) is None
    with pytest.raises(FindingsError, match="exactly one"):
        core.instant_total(telemetry, series, 2, "after", labels)


# --------------------------------------------------------------------------
# The setup table and the figures quoted in prose
# --------------------------------------------------------------------------

#: The report with line breaks and blockquote markers folded into single spaces.
FLAT_REPORT = " ".join(
    line.removeprefix(">").strip() for line in REPORT.splitlines()
).replace("  ", " ")


def _grouped(number: int) -> str:
    return f"{number:,}".replace(",", " ")


def test_the_setup_table_carries_the_recorded_setup() -> None:
    setup = FINDINGS["setup"]
    runtime = setup["runtime"]
    engine = setup["engine"]
    host = setup["generatorHost"]
    expected = [
        f"| Provider | `{setup['provider']}`: one node, Kubernetes `{setup['kubernetesServerVersion']}`",
        f"kernel `{setup['nodeKernel']}`",
        f"allocatable {setup['nodeAllocatable']['cpu']} CPU and {setup['nodeAllocatable']['memory']}",
        f"Docker Desktop `{engine['serverVersion']}` with {engine['cpus']} processors and {_grouped(engine['memoryBytes'])} bytes",
        f"Windows {host['release']} with {host['logicalCpus']} logical processors",
        f"`{setup['model']['id']}`",
        f"`{runtime['image']}` with `--parallel {runtime['parallelSlots']} --threads {runtime['threads']} --ctx-size {runtime['contextSize']} --n-predict {setup['maxOutputTokens']} --temp 0`",
        f"limits {runtime['cpuLimitMillicores'] // 1000} CPU and {runtime['memoryLimitBytes'] // 1024**3}Gi",
        f"Chart `{setup['chart']}`",
        f"request deadline {_grouped(setup['requestTimeoutMs'])} ms; output-token limit {setup['maxOutputTokens']}",
    ]
    missing = [text for text in expected if text not in REPORT]
    assert not missing, missing
    assert runtime["replicas"] == 1
    assert "one runtime replica" in REPORT


def test_the_figures_quoted_in_prose_are_the_computed_ones() -> None:
    across = FINDINGS["acrossMeasuredPhases"]
    levels = {level["scenarioId"]: level for level in FINDINGS["levels"]}
    runs = {run["repetition"]: run for run in FINDINGS["runs"]}
    cpu_low, cpu_high = across["higherLoadRuntimeCpuMinusBaselineMillicoresRange"]
    first_run = runs[1]["warmUp"]["firstSlowerThanOthersMsRange"]
    second_run = runs[2]["warmUp"]["firstSlowerThanOthersMsRange"]
    medians = max(level["betweenRunsDifferenceMs"]["p50"] for level in levels.values())
    expected = [
        f"The spread across all measured phases, {_decimal(across['successfulRequestsPerSecondSpreadMilli'])} per second",
        f"at the **same** level, {_decimal(across['largestBetweenRunsRateDifferenceMilli'])} per second",
        f"a spread ({_decimal(across['successfulRequestsPerSecondSpreadMilli'])}) about the size of the largest difference between the two runs at one level ({_decimal(across['largestBetweenRunsRateDifferenceMilli'])})",
        f"between {_decimal(across['successfulRequestsPerSecondMilliRange'][0])} and {_decimal(across['successfulRequestsPerSecondMilliRange'][1])}",
        f"{cpu_low}{RANGE}{cpu_high} millicores above their run's `c1`",
        f"{first_run[0]}{RANGE}{first_run[1]} ms slower than the other two",
        f"in run 2 the first was {second_run[0]}{RANGE}{second_run[1]} ms slower",
        f"Medians differ by at most {medians} ms",
        f"differs by {_grouped(levels['c4']['betweenRunsDifferenceMs']['p95'])} ms at P95",
        f"{_grouped(levels['c4']['betweenRunsDifferenceMs']['p99'])} ms at P99",
    ]
    missing = [text for text in expected if text not in FLAT_REPORT]
    assert not missing, missing
