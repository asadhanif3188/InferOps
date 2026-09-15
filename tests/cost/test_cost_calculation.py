"""Deterministic checks over the V1 cost calculation in `tools/cost_calculation`.

Every check here reads files from this repository or builds an input in memory. No
network, no cluster, no model, no clock, no randomness, and no price is read from
anywhere but the committed cost method.

What this suite establishes is that the calculation applies the cost method as ADR
0007 and ADR 0014 decide: it reaches the estimated basis and refuses the other two;
it reads a price only from a committed source and refuses one that could not be
cited, reproduced, or read as synthetic; it converts processor, binary memory, and
device quantities exactly; it rounds once, half-even, from exact values; a missing
input is null with a reason and so is every figure depending on it; a unit cost
carries its denominator and vanishes below the declared minimum; the unallocated
line closes the workload lines against the node; confidence is derived from each
record's facts; and every record validates against the output shape the method
publishes. The committed fixtures regenerate byte for byte, and their figures are
held here to values worked out by hand, not only to what the tool printed.

What it does not establish is what anything costs. Every fixture is synthetic, the
only rate card is invented, and no usage value here was measured.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from tools.cost_calculation import (
    BOUNDARY,
    CostCalculationError,
    CostCalculationRefused,
    calculate,
    check_method,
    check_price_source,
    check_record,
    derive_confidence,
    load_method,
    loads,
    memory_gibibytes,
    parse_quantity,
    round_half_even,
)
from tools.cost_calculation import core as calculation
from tools.cost_calculation.__main__ import EXIT_FAILED, EXIT_OK, EXIT_REFUSED, main

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cost-calculation"
FIXTURE_NAMES = ("estimate-closes", "estimate-incomplete")
STRATEGY_PATH = REPO_ROOT / "docs" / "testing" / "test-strategy.v1alpha1.json"

METHOD = load_method()

# A committed local-real record a measured input may name. The calculation reads
# nothing from it but its evidence class; the digest is over LF line endings.
MEASURED_RECORD = "docs/proof/serving/v1-s4-004-pr1-performance-record.v1alpha1.json"


def measured_evidence() -> dict[str, str]:
    text = (
        (REPO_ROOT / MEASURED_RECORD).read_text(encoding="utf-8").replace("\r\n", "\n")
    )
    return {
        "path": MEASURED_RECORD,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def measured_input() -> dict[str, Any]:
    document = closes_input()
    document["classification"] = "local-real-cpu"
    document["warning"] = "Usage typed in by hand for a test; the record named is real."
    document["usageEvidence"] = measured_evidence()
    return document


def fixture_input(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.input.json").read_text(encoding="utf-8"))


def fixture_result(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.result.json").read_text(encoding="utf-8"))


def closes_input() -> dict[str, Any]:
    return fixture_input("estimate-closes")


def refused(document: Any, fragment: str) -> None:
    with pytest.raises(CostCalculationRefused) as caught:
        calculate(document, METHOD)
    assert fragment in str(caught.value), str(caught.value)


def record(result: dict[str, Any], record_id: str) -> dict[str, Any]:
    return next(row for row in result["records"] if row["recordId"] == record_id)


# --------------------------------------------------------------------------
# The committed fixtures
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_every_committed_fixture_regenerates_byte_for_byte(name: str) -> None:
    expected = calculation.dumps(calculate(fixture_input(name), METHOD))
    committed = (FIXTURES / f"{name}.result.json").read_text(encoding="utf-8")
    assert committed.replace("\r\n", "\n") == expected


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_every_calculated_record_validates_against_the_published_shape(
    name: str,
) -> None:
    result = fixture_result(name)
    shape_paths = {field["path"] for field in METHOD["recordShape"]["fields"]}
    assert "cost.priceSourceVersion" in shape_paths
    assert "evidence.usageEvidenceClass" in shape_paths
    for row in result["records"]:
        check_record(row, METHOD)


def test_the_record_shape_check_refuses_a_missing_field_a_wrong_type_and_a_tenant() -> (
    None
):
    row = fixture_result("estimate-closes")["records"][0]
    missing = copy.deepcopy(row)
    del missing["cost"]["priceSourceVersion"]
    with pytest.raises(CostCalculationError, match=r"lacks cost\.priceSourceVersion"):
        check_record(missing, METHOD)
    wrong = copy.deepcopy(row)
    wrong["cost"]["amount"] = "0.039"
    with pytest.raises(CostCalculationError, match="is not a decimal-or-null"):
        check_record(wrong, METHOD)
    tenant = copy.deepcopy(row)
    tenant["identity"]["tenantId"] = "someone"
    with pytest.raises(CostCalculationError, match="no committed record may carry"):
        check_record(tenant, METHOD)
    instant = copy.deepcopy(row)
    instant["period"]["start"] = "not-an-instant"
    with pytest.raises(CostCalculationError, match="is not a instant"):
        check_record(instant, METHOD)
    billed = copy.deepcopy(row)
    billed["identity"]["workloadId"] = "billed-assistant"
    with pytest.raises(CostCalculationError, match="uses the word 'billed'"):
        check_record(billed, METHOD)


def test_every_fixture_says_it_is_synthetic_and_publishes_no_figure() -> None:
    for name in FIXTURE_NAMES:
        document = fixture_input(name)
        result = fixture_result(name)
        assert document["classification"] == "synthetic"
        assert "invented" in document["warning"]
        assert result["classification"] == "estimated"
        assert result["usageEvidenceClass"] == "synthetic"
        assert result["publishedCostFigure"] is False
        assert result["boundary"] == BOUNDARY
        assert result["priceSource"]["class"] == "synthetic-illustrative"
        for row in result["records"]:
            assert row["cost"]["confidence"] == "none", row["recordId"]


# --------------------------------------------------------------------------
# The figures, worked out by hand
# --------------------------------------------------------------------------


def test_the_closing_fixture_publishes_the_figures_worked_out_by_hand() -> None:
    """Rates: 0.04 per core-hour, 0.005 per GiB-hour, one hour.

    0001: 2160 s is 0.6 core-hours (0.024) and 3 GiB held for the hour is 0.015, so
    0.039; per thousand of 1,200 requests 0.0325; per million of 576,000 tokens
    0.0677083... -> 0.067708; share of 0.4 is 0.0975.
    0002: 300 s is 1/12 core-hour (0.0033333...) and half a GiB is 0.0025, so
    0.0058333... -> 0.005833; 40 requests is below the minimum; no tokens.
    Unallocated: 0.4 - (0.039 + 0.005833) = 0.355167, a share of 0.8879175, which is a
    tie at the sixth place and rounds half-even to 0.887918.
    """
    result = fixture_result("estimate-closes")
    first = record(result, "example-estimate-0001")
    assert first["cost"]["amount"] == "0.039000"
    assert first["derived"]["amountPerHour"] == "0.039000"
    assert first["derived"]["costPerThousandRequests"] == "0.032500"
    assert first["derived"]["costPerThousandRequestsDenominator"] == 1200
    assert first["derived"]["costPerMillionTokens"] == "0.067708"
    assert first["derived"]["costPerMillionTokensDenominator"] == 576000
    assert first["derived"]["shareOfNodeCapacity"] == "0.097500"
    assert first["reserved"] == {
        "cpuCoreHours": "2.000000",
        "memoryGibibyteHours": "4.000000",
        "acceleratorDeviceHours": "0.000000",
    }

    second = record(result, "example-estimate-0002")
    assert second["cost"]["amount"] == "0.005833"
    assert second["derived"]["costPerThousandRequests"] is None
    assert second["derived"]["costPerThousandRequestsDenominator"] == 40
    assert second["derived"]["costPerMillionTokens"] is None
    assert second["derived"]["costPerMillionTokensDenominator"] is None
    assert second["completeness"]["reasons"] == [
        "below-minimum-sample",
        "no-telemetry-source",
    ]

    assert result["capacity"]["amount"] == "0.400000"
    assert result["totals"]["workloadAmountSum"] == "0.044833"
    assert result["unallocated"]["amount"] == "0.355167"
    assert result["unallocated"]["shareOfNodeCapacity"] == "0.887918"
    assert result["prerequisites"][0]["amount"] == "0.000500"
    assert result["totals"]["environmentAmount"] == "0.400500"
    assert result["totals"]["closes"] is True


def exact(text: str) -> Decimal:
    return Decimal(text)


def test_every_amount_recomputes_independently_in_decimal() -> None:
    """A second route to each amount: Decimal at 60 digits, not the tool's Fraction."""
    method_rates = {
        row["unit"]: Decimal(row["ratePerHour"])
        for row in METHOD["priceSources"][0]["rates"]
    }
    for name in FIXTURE_NAMES:
        document = fixture_input(name)
        result = fixture_result(name)
        for workload in document["workloads"]:
            row = record(result, workload["recordId"])
            usage = workload["usage"]
            if usage["cpuSeconds"] is None or usage["memoryByteSeconds"] is None:
                assert row["cost"]["amount"] is None, workload["recordId"]
                continue
            with localcontext() as context:
                context.prec = 60
                amount = (
                    Decimal(usage["cpuSeconds"]) * method_rates["cpu-core-hour"]
                    + Decimal(usage["memoryByteSeconds"])
                    / Decimal(2**30)
                    * method_rates["memory-gibibyte-hour"]
                ) / Decimal(3600)
                published = amount.quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_EVEN
                )
            assert row["cost"]["amount"] == str(published), workload["recordId"]


def test_the_workload_lines_and_the_unallocated_line_close_against_the_node() -> None:
    result = fixture_result("estimate-closes")
    workloads = sum(exact(row["cost"]["amount"]) for row in result["records"])
    assert workloads == exact(result["totals"]["workloadAmountSum"])
    assert workloads + exact(result["unallocated"]["amount"]) == exact(
        result["capacity"]["amount"]
    )


def test_a_unit_cost_is_divided_from_the_exact_amount_not_the_rounded_one() -> None:
    """0.036 processor seconds at 0.04 per hour is 0.0000004: published as 0.000000.

    Divided by 100 requests and multiplied by a thousand, the exact amount gives
    0.000004. Dividing the rounded amount would have published zero, a figure no
    input supports.
    """
    document = closes_input()
    workload = document["workloads"][0]
    workload["usage"].update(
        {"requests": 100, "cpuSeconds": "0.036", "memoryByteSeconds": "0"}
    )
    document["workloads"] = [workload]
    row = calculate(document, METHOD)["records"][0]
    assert row["cost"]["amount"] == "0.000000"
    assert row["derived"]["costPerThousandRequests"] == "0.000004"


def test_a_reserved_device_needs_measured_device_seconds() -> None:
    document = closes_input()
    document["capacity"]["acceleratorDevices"] = 2  # two replicas, one device each
    workload = document["workloads"][0]
    workload["declaration"].update(
        {"acceleratorType": "nvidia-gpu", "acceleratorCount": 1}
    )
    document["workloads"] = [workload]
    # With a device reserved, missing device seconds are a gap and need a reason.
    refused(
        copy.deepcopy(document), "is null and workloads[0].unavailable gives no reason"
    )
    workload["unavailable"] = {"accelerator-seconds": "no-telemetry-source"}
    without = calculate(document, METHOD)["records"][0]
    assert without["cost"]["amount"] is None
    assert without["derived"]["amountPerHour"] is None
    assert without["completeness"]["reasons"] == ["no-telemetry-source"]

    workload["usage"]["acceleratorSeconds"] = "1800"
    workload["unavailable"] = {}
    with_seconds = calculate(document, METHOD)["records"][0]
    # 0.039 as before, plus half a device-hour at 1.2.
    assert with_seconds["cost"]["amount"] == "0.639000"
    assert with_seconds["reserved"]["acceleratorDeviceHours"] == "2.000000"


# --------------------------------------------------------------------------
# Basis and price source
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("basis", "fragment"),
    [
        ("allocated", "V1 calculates the estimated basis only"),
        ("actual", "never been billed"),
        ("estimate", "not a basis the cost method declares"),
    ],
)
def test_a_basis_v1_does_not_reach_is_refused(basis: str, fragment: str) -> None:
    document = closes_input()
    document["basis"] = basis
    refused(document, fragment)


def test_a_price_source_not_committed_in_the_method_is_refused() -> None:
    document = closes_input()
    document["priceSourceId"] = "provider-list-price-v1"
    refused(document, "is not committed in the cost method")


def synthetic_source() -> dict[str, Any]:
    return copy.deepcopy(METHOD["priceSources"][0])


def _set_rate(source: dict[str, Any], unit: str, value: Any) -> None:
    next(row for row in source["rates"] if row["unit"] == unit)["ratePerHour"] = value


INVALID_PRICE_SOURCES: list[tuple[str, Any, str]] = [
    (
        "fetched",
        lambda s: s.update(retrieval="fetched"),
        "no price is fetched at runtime",
    ),
    (
        "url",
        lambda s: s.update(notes=s["notes"] + " https://example.invalid"),
        "carries a URL",
    ),
    (
        "unversioned",
        lambda s: s.update(version=""),
        "version must be a non-empty string",
    ),
    ("undated", lambda s: s.update(effectiveDate="2026-02-30"), "is not a date"),
    ("date-shape", lambda s: s.update(effectiveDate="2026-8-26"), "is not a date"),
    ("currency", lambda s: s.update(currency="usd"), "three-letter code"),
    ("unknown-class", lambda s: s.update(**{"class": "guessed"}), "does not declare"),
    (
        "not-self-identifying",
        lambda s: s.update(selfIdentifies=False),
        "does not say so",
    ),
    ("publishable-synthetic", lambda s: s.update(publishable=True), "does not say so"),
    (
        "ceiling",
        lambda s: s.update(maxConfidence="high"),
        "ceiling its class does not allow",
    ),
    ("not-invented", lambda s: s.update(notes="Plausible rates."), "does not say so"),
    ("float-shaped", lambda s: _set_rate(s, "cpu-core-hour", 0.04), "six places"),
    ("five-places", lambda s: _set_rate(s, "cpu-core-hour", "0.04000"), "six places"),
    ("negative", lambda s: _set_rate(s, "cpu-core-hour", "-0.040000"), "six places"),
    ("exponent", lambda s: _set_rate(s, "cpu-core-hour", "4.000000E-2"), "six places"),
    ("missing-unit", lambda s: s["rates"].pop(), "does not price every priced unit"),
    (
        "duplicate-unit",
        lambda s: s["rates"].append(dict(s["rates"][0])),
        "twice",
    ),
    (
        "unpriced-unit",
        lambda s: s["rates"].append({"unit": "request", "ratePerHour": "0.000001"}),
        "not a priced unit",
    ),
    ("extra-field", lambda s: s.update(region="nowhere"), "unexpected ['region']"),
]


@pytest.mark.parametrize(
    ("case", "corrupt", "fragment"),
    INVALID_PRICE_SOURCES,
    ids=[case for case, _, _ in INVALID_PRICE_SOURCES],
)
def test_an_invalid_price_source_is_refused(
    case: str, corrupt: Any, fragment: str
) -> None:
    source = synthetic_source()
    corrupt(source)
    with pytest.raises(CostCalculationRefused) as caught:
        check_price_source(source, METHOD)
    assert fragment in str(caught.value), (case, str(caught.value))


def test_the_committed_price_source_is_accepted_as_it_stands() -> None:
    source = check_price_source(synthetic_source(), METHOD)
    assert source.price_class == "synthetic-illustrative"
    assert source.rate("cpu-core-hour") == Fraction(4, 100)
    assert (source.version, source.effective_date, source.currency) == (
        "1",
        "2026-08-26",
        "USD",
    )


def test_a_method_that_reaches_another_basis_is_not_applied() -> None:
    method = copy.deepcopy(METHOD)
    for row in method["bases"]:
        if row["basisId"] == "allocated":
            row["v1Reachable"] = True
    with pytest.raises(CostCalculationError, match="V1 calculates 'estimated' only"):
        check_method(method)
    method = copy.deepcopy(METHOD)
    for row in method["allocationMethods"]:
        row["selected"] = row["methodId"] == "requested-resource-share"
    with pytest.raises(CostCalculationError, match="observed-utilisation-share"):
        check_method(method)


# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------


def test_synthetic_usage_never_counts_as_measured_utilisation() -> None:
    synthetic = calculate(closes_input(), METHOD)
    for row in synthetic["records"]:
        assert row["facts"]["hasMeasuredUtilisation"] is False, row["recordId"]
        assert row["evidence"]["usageEvidenceClass"] == "synthetic"

    measured = calculate(measured_input(), METHOD)
    assert measured["usageEvidence"] == measured_evidence()
    for row in measured["records"]:
        assert row["facts"]["hasMeasuredUtilisation"] is True, row["recordId"]
        # Measured use does not lift a synthetic rate card above none.
        assert row["cost"]["confidence"] == "none", row["recordId"]

    unmeasured = closes_input()
    unmeasured["classification"] = "mock"
    refused(unmeasured, "is not an evidence class a usage input may come from")


def test_measured_use_does_not_depend_on_the_accelerator_term() -> None:
    """Processor and memory measured, a reserved device's seconds unavailable."""
    document = measured_input()
    document["capacity"]["acceleratorDevices"] = 2  # two replicas, one device each
    workload = document["workloads"][0]
    workload["declaration"].update(
        {"acceleratorType": "nvidia-gpu", "acceleratorCount": 1}
    )
    workload["unavailable"] = {"accelerator-seconds": "no-telemetry-source"}
    document["workloads"] = [workload]
    row = calculate(document, METHOD)["records"][0]
    assert row["cost"]["amount"] is None
    assert row["facts"]["hasMeasuredUtilisation"] is True


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (lambda d: d.update(usageEvidence=None), "must name the committed record"),
        (
            lambda d: d["usageEvidence"].update(sha256="0" * 64),
            "does not match the record",
        ),
        (
            lambda d: d["usageEvidence"].update(
                path="docs/cost/cost-method.v1alpha1.json"
            ),
            "under docs/proof/",
        ),
        (
            lambda d: d["usageEvidence"].update(
                path="docs/proof/../cost/cost-method.md"
            ),
            "under docs/proof/",
        ),
        (
            lambda d: d["usageEvidence"].update(path="docs/proof/serving/absent.json"),
            "names no readable committed record",
        ),
        (
            lambda d: d["usageEvidence"].update(sha256="ABC"),
            "64 lowercase hex digits",
        ),
        (
            lambda d: d.update(classification="cloud-real-cpu"),
            "declares evidence class 'local-real-cpu'",
        ),
        (
            lambda d: d.update(classification="synthetic", warning="Synthetic."),
            "usageEvidence must be null",
        ),
    ],
)
def test_a_measured_class_must_name_matching_committed_evidence(
    change: Any, fragment: str
) -> None:
    document = measured_input()
    change(document)
    refused(document, fragment)


@pytest.mark.parametrize(
    ("measured", "complete", "expected"),
    [(True, True, "medium"), (False, True, "low"), (True, False, "low")],
)
def test_confidence_on_the_estimated_basis_is_derived_from_its_facts(
    measured: bool, complete: bool, expected: str
) -> None:
    facts = {
        "basis": "estimated",
        "priceSourceClass": "provider-list-price",
        "hasMeasuredUtilisation": measured,
        "windowComplete": complete,
        "shapeChangedInWindow": False,
    }
    assert derive_confidence(facts, METHOD) == expected


def test_the_usage_evidence_classes_are_classes_the_test_strategy_declares() -> None:
    strategy = json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))
    declared = {row["classId"] for row in strategy["evidenceClasses"]}
    allowed = calculation.MEASURED_USAGE_CLASSES | calculation.UNMEASURED_USAGE_CLASSES
    assert allowed <= declared, sorted(allowed - declared)
    assert "estimated" in declared


# --------------------------------------------------------------------------
# Missing data
# --------------------------------------------------------------------------


def test_the_incomplete_fixture_is_null_with_a_reason_and_never_zero() -> None:
    result = fixture_result("estimate-incomplete")
    row = result["records"][0]
    assert row["usage"]["memoryByteSeconds"] is None
    assert "memory-byte-seconds" in row["completeness"]["unavailableInputs"]
    for key in (
        "amountPerHour",
        "shareOfNodeCapacity",
        "costPerThousandRequests",
        "costPerMillionTokens",
    ):
        assert row["derived"][key] is None, key
    assert row["cost"]["amount"] is None
    assert row["completeness"]["reasons"] == ["no-telemetry-source"]
    assert row["completeness"]["windowComplete"] is False
    assert result["unallocated"]["amount"] is None
    assert result["unallocated"]["unavailableReasons"] == ["no-telemetry-source"]
    assert result["totals"]["workloadAmountSum"] is None
    assert result["totals"]["closes"] is None
    # The node's own amount does not depend on use, so it is still stated.
    assert result["capacity"]["amount"] == "0.200000"


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (
            lambda w: w["usage"].update(requests=None),
            "is null and workloads[0].unavailable gives no reason",
        ),
        (
            lambda w: w["unavailable"].update({"requests": "no-telemetry-source"}),
            "is set and also declared unavailable",
        ),
        (
            lambda w: (
                w["usage"].update(requests=None),
                w["unavailable"].update({"requests": "because"}),
            ),
            "a reason the method does not declare",
        ),
        (
            lambda w: (
                w["usage"].update(requests=None),
                w["unavailable"].update({"requests": "below-minimum-sample"}),
            ),
            "describes an output, not a missing input",
        ),
        (
            lambda w: w["unavailable"].update({"ready-seconds": "no-telemetry-source"}),
            "is not a usage input",
        ),
        (
            lambda w: w["unavailable"].update(
                {"accelerator-seconds": "no-telemetry-source"}
            ),
            "accelerator seconds are not missing",
        ),
        (lambda w: w["usage"].update(requests=-1), "an integer of at least 0"),
        (lambda w: w["usage"].update(requests=True), "an integer of at least 0"),
        (lambda w: w["usage"].update(cpuSeconds=2160), "non-negative decimal string"),
        (lambda w: w["usage"].pop("inputTokens"), "must declare exactly"),
    ],
)
def test_a_missing_input_must_be_null_with_a_declared_reason(
    change: Any, fragment: str
) -> None:
    document = closes_input()
    change(document["workloads"][0])
    refused(document, fragment)


def test_a_measured_zero_is_a_measurement_and_is_priced_as_one() -> None:
    document = closes_input()
    workload = document["workloads"][0]
    workload["usage"].update({"cpuSeconds": "0", "memoryByteSeconds": "0"})
    document["workloads"] = [workload]
    row = calculate(document, METHOD)["records"][0]
    assert row["cost"]["amount"] == "0.000000"
    # Accelerator seconds are not applicable with no device reserved: no gap is listed.
    assert row["completeness"] == {
        "unavailableInputs": [],
        "reasons": [],
        "windowComplete": True,
    }


# --------------------------------------------------------------------------
# Units, precision, and parsing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("quantity", "base"),
    [
        ("500m", Fraction(1, 2)),
        ("2", Fraction(2)),
        ("1.5", Fraction(3, 2)),
        ("2Gi", Fraction(2 * 2**30)),
        ("1500Mi", Fraction(1500 * 2**20)),
        ("2G", Fraction(2 * 10**9)),
        ("64Ki", Fraction(64 * 1024)),
    ],
)
def test_a_kubernetes_quantity_converts_exactly(quantity: str, base: Fraction) -> None:
    assert parse_quantity(quantity, "q") == base


def test_memory_is_binary_and_a_decimal_suffix_is_not_read_as_binary() -> None:
    assert memory_gibibytes("2Gi", "m") == 2
    # 2G is 2 x 10^9 bytes: 1.862645149... GiB, the 7.4 per cent ADR 0007 D6 names.
    assert memory_gibibytes("2G", "m") == Fraction(2 * 10**9, 2**30)
    assert round_half_even(memory_gibibytes("2G", "m")) == "1.862645"


@pytest.mark.parametrize("quantity", ["1e3", "-1", "1.5Gb", "", "1 Gi", "0x10", ".5"])
def test_a_quantity_the_workload_contract_would_refuse_is_refused(
    quantity: str,
) -> None:
    with pytest.raises(CostCalculationRefused):
        parse_quantity(quantity, "q")


def test_the_quantity_pattern_is_the_workload_contracts() -> None:
    schema = json.loads(
        (
            REPO_ROOT
            / "contracts"
            / "workload"
            / "workload-contract.v1alpha1.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        schema["$defs"]["kubernetesQuantity"]["pattern"] == calculation.QUANTITY.pattern
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Fraction(5, 10**7), "0.000000"),
        (Fraction(15, 10**7), "0.000002"),
        (Fraction(25, 10**7), "0.000002"),
        (Fraction(35, 10**7), "0.000004"),
        (Fraction(1, 3), "0.333333"),
        (Fraction(2, 3), "0.666667"),
        (Fraction(8879175, 10**7), "0.887918"),
        (Fraction(12, 1), "12.000000"),
        (Fraction(-15, 10**7), "-0.000002"),
    ],
)
def test_rounding_is_half_even_once_at_six_places(
    value: Fraction, expected: str
) -> None:
    assert round_half_even(value) == expected


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ('{"a": 1.5}', "binary floating-point"),
        ('{"a": NaN}', "non-numeric constant"),
        ('{"a": 1, "a": 2}', "appears twice"),
        ("{", "is not JSON"),
    ],
)
def test_an_input_is_read_without_floats_constants_or_duplicate_keys(
    text: str, fragment: str
) -> None:
    with pytest.raises(CostCalculationRefused, match=fragment):
        loads(text, "calculation input")


# --------------------------------------------------------------------------
# Windows, shape changes, and inputs that conflict
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end", "fragment"),
    [
        ("2026-08-26T01:00:00Z", "2026-08-26T00:00:00Z", "must be after"),
        ("2026-08-26T00:00:00Z", "2026-08-26T00:00:59Z", "at least one minute"),
        ("2026-08-26T00:00:00Z", "2026-08-27T00:00:01Z", "at most one day"),
        ("2026-08-26T00:00:00+00:00", "2026-08-26T01:00:00Z", "ending in Z"),
        ("2026-02-30T00:00:00Z", "2026-03-01T01:00:00Z", "is not a real instant"),
    ],
)
def test_a_window_outside_the_method_rules_is_refused(
    start: str, end: str, fragment: str
) -> None:
    document = closes_input()
    document["window"] = {"start": start, "end": end}
    refused(document, fragment)


def test_a_window_of_exactly_one_minute_and_one_day_is_accepted() -> None:
    for end in ("2026-08-26T00:01:00Z", "2026-08-27T00:00:00Z"):
        document = closes_input()
        document["window"] = {"start": "2026-08-26T00:00:00Z", "end": end}
        for workload in document["workloads"]:
            workload["usage"].update({"cpuSeconds": "1", "memoryByteSeconds": "1"})
        assert calculate(document, METHOD)["basis"] == "estimated"


def test_a_declared_shape_change_is_refused_rather_than_averaged() -> None:
    document = closes_input()
    document["workloads"][0]["shapeChangedInWindow"] = True
    refused(document, "split the window at the change")


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (
            lambda d: d["workloads"][0]["identity"].update(tenantId="acme"),
            "carries a tenant identifier",
        ),
        (
            lambda d: d["workloads"][0]["usage"].update(cpuSeconds="28801"),
            "more processor seconds than the node's declared capacity",
        ),
        (
            lambda d: d["workloads"][0]["usage"].update(
                memoryByteSeconds=str(16 * 2**30 * 3600 + 1)
            ),
            "more memory byte-seconds",
        ),
        (
            lambda d: [w["usage"].update(cpuSeconds="15000") for w in d["workloads"]],
            "the workloads together report more measured use",
        ),
        (
            lambda d: (
                d["workloads"][0]["usage"].update(acceleratorSeconds="1"),
                d["workloads"][0]["unavailable"].clear(),
            ),
            "reserves no accelerator and reports accelerator seconds",
        ),
        (
            lambda d: d["workloads"][0]["declaration"].update(acceleratorCount=1),
            "reserves accelerator type 'none' with count 1",
        ),
        (
            lambda d: d["workloads"][0]["declaration"].update(replicas=0),
            "an integer of at least 1",
        ),
        (
            lambda d: d["workloads"][1].update(recordId="example-estimate-0001"),
            "appears twice",
        ),
        (
            lambda d: d["workloads"][0]["identity"].update(environment="ci"),
            "the calculation covers 'dev'",
        ),
        (lambda d: d.update(workloads=[]), "at least one workload"),
        (lambda d: d["capacity"].update(cpuCores="0"), "above zero"),
        (
            lambda d: d["capacity"].update(
                cpuCores="0.000001", memoryGibibytes="0.000001"
            ),
            "rounds to zero",
        ),
        (
            lambda d: d["prerequisites"][0].update(attributedTo="support-assistant"),
            "never to a workload",
        ),
        (
            lambda d: d.update(
                classification="local-real-cpu",
                warning="x",
                usageEvidence=measured_evidence(),
            ),
            None,
        ),
        (
            lambda d: (
                d["capacity"].update(acceleratorDevices=1),
                d["workloads"][0]["declaration"].update(
                    acceleratorType="nvidia-gpu", acceleratorCount=1
                ),
                d["workloads"][0]["usage"].update(acceleratorSeconds="3601"),
                d["workloads"][0]["declaration"].update(replicas=1),
            ),
            "more accelerator seconds than the node's declared capacity",
        ),
        (
            lambda d: (
                d["capacity"].update(acceleratorDevices=1),
                [
                    (
                        w["declaration"].update(
                            acceleratorType="nvidia-gpu", acceleratorCount=1
                        ),
                        w["declaration"].update(replicas=1),
                        w["usage"].update(acceleratorSeconds="1801"),
                    )
                    for w in d["workloads"]
                ],
            ),
            "the workloads together report more measured use",
        ),
        (
            lambda d: d["workloads"][0]["declaration"].update(
                acceleratorType="nvidia-gpu", acceleratorCount=1
            ),
            "reserves 2 accelerator device(s) and the node declares 0",
        ),
        (
            lambda d: d.update(
                window={"start": "2026-08-26T00:30:00Z", "end": "2026-08-26T01:30:00Z"}
            ),
            "starts on the hour",
        ),
        (
            lambda d: d["workloads"][0]["identity"].update(ownerId="/home/x"),
            "shaped like a host path",
        ),
        (
            lambda d: d["workloads"][0]["identity"].update(runtimeId="10.1.2.3"),
            "shaped like a host path",
        ),
        (lambda d: d.update(warning="Invented numbers."), "must say it is synthetic"),
        (lambda d: d.update(kind="CostRecord"), "CostCalculationInput"),
        (lambda d: d.update(extra=True), "unexpected ['extra']"),
        (
            lambda d: d["workloads"][0]["identity"].update(ownerId="C:\\work\\owner"),
            "shaped like a host path",
        ),
    ],
)
def test_an_input_the_method_forbids_is_refused(
    change: Any, fragment: str | None
) -> None:
    document = closes_input()
    change(document)
    if fragment is None:
        # A measured class with any warning is accepted; only synthetic must say so.
        assert calculate(document, METHOD)["usageEvidenceClass"] == "local-real-cpu"
        return
    refused(document, fragment)


# --------------------------------------------------------------------------
# The document that describes the calculation
# --------------------------------------------------------------------------

DECIMAL_IN_PROSE = re.compile(r"(?<![\d.])\d+\.\d{6}(?![\d])")


def fixture_decimals() -> set[str]:
    found: set[str] = set()
    for name in FIXTURE_NAMES:
        for _, value in calculation._walk(fixture_result(name)):
            if isinstance(value, str) and calculation.DECIMAL_STRING.match(value):
                found.add(value)
    found |= {row["ratePerHour"] for row in METHOD["priceSources"][0]["rates"]}
    return found


def test_the_calculation_document_invents_no_figure_the_fixtures_lack() -> None:
    document = (REPO_ROOT / "docs" / "cost" / "cost-calculation.md").read_text(
        encoding="utf-8"
    )
    quoted = set(DECIMAL_IN_PROSE.findall(document))
    assert quoted, "the document quotes no fixture figure"
    assert not quoted - fixture_decimals(), sorted(quoted - fixture_decimals())
    for name in FIXTURE_NAMES:
        assert f"{name}.input.json" in document, name
        assert f"{name}.result.json" in document, name
    for row in fixture_result("estimate-closes")["records"]:
        assert f"`{row['recordId']}`" in document, row["recordId"]


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------


def test_the_command_calculates_verifies_fails_and_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = FIXTURES / "estimate-closes.input.json"
    result = tmp_path / "result.json"
    assert (
        main(["calculate", "--input", str(source), "--result", str(result)]) == EXIT_OK
    )
    assert result.read_text(encoding="utf-8") == (
        FIXTURES / "estimate-closes.result.json"
    ).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert main(["verify", "--input", str(source), "--result", str(result)]) == EXIT_OK

    result.write_text(
        result.read_text(encoding="utf-8").replace("0.039000", "0.039001"),
        encoding="utf-8",
    )
    assert (
        main(["verify", "--input", str(source), "--result", str(result)]) == EXIT_FAILED
    )
    assert "FAILED cost calculation" in capsys.readouterr().err

    allocated = tmp_path / "allocated.json"
    document = closes_input()
    document["basis"] = "allocated"
    allocated.write_text(json.dumps(document), encoding="utf-8")
    assert (
        main(
            [
                "calculate",
                "--input",
                str(allocated),
                "--result",
                str(tmp_path / "x.json"),
            ]
        )
        == EXIT_REFUSED
    )
    assert "REFUSED cost calculation" in capsys.readouterr().err
    assert not (tmp_path / "x.json").exists()
