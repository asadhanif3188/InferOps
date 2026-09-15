"""The V1 cost calculation: an estimated cost record from measured use and a committed rate card.

[ADR 0007](../../docs/architecture/decisions/ADR-0007-inference-cost-method.md)
decides how a V1 cost figure is produced and what it may be called, and
[ADR 0014](../../docs/architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md)
amends which basis V1 reaches. This module applies both to one declared input
document and nothing else:

- the **basis** is `estimated`, a committed price applied to measured processor and
  memory use. `actual` needs an invoice and `allocated` is not produced in V1, and a
  request for either is refused with the reason the method data gives;
- the **price source** is read from the committed method, never from a network, and
  is refused if it is not versioned, dated, committed, decimal, and complete;
- **capacity no workload in the calculation was measured using** is its own line,
  and the workload lines plus that line close against the node exactly;
- a **missing input** is null with a reason, and so is every output depending on it;
- **confidence** is derived from the record's own facts by the method's rules.

Arithmetic is exact. Every intermediate value is a rational number, and a published
figure is rounded once, half-even, to six places. Nothing here contacts anything,
and nothing here makes a figure publishable: the only committed rate card is
synthetic, and ADR 0007 D11 publishes no cost figure.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from tools.performance_scenarios.core import PRIVATE_SHAPES

REPO_ROOT = Path(__file__).resolve().parents[2]
METHOD_REF = "docs/cost/cost-method.v1alpha1.json"
METHOD_PATH = REPO_ROOT / METHOD_REF
ASSUMPTIONS_REF = "docs/cost/cost-calculation.md"
DECISION_REFS = (
    "docs/architecture/decisions/ADR-0007-inference-cost-method.md",
    "docs/architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md",
)

SCHEMA_VERSION = "inferops.io/v1alpha1"
INPUT_KIND = "CostCalculationInput"
RESULT_KIND = "CostCalculationResult"
METHOD_VERSION = "cost-method.v1alpha1"

BASIS = "estimated"
ALLOCATION_METHOD = "observed-utilisation-share"
RESIDUAL_TREATMENT = "report-separately"
PREREQUISITE_OWNER = "prerequisite-layer"
RESULT_CLASSIFICATION = "estimated"

#: Evidence classes a usage input may come from. Only the measured ones let a record
#: state that its utilisation was measured; a synthetic input never does.
MEASURED_USAGE_CLASSES = frozenset(
    {"local-real-cpu", "cloud-real-cpu", "cloud-real-gpu"}
)
UNMEASURED_USAGE_CLASSES = frozenset({"synthetic"})

BOUNDARY = (
    "An estimated cost computed from the price source named beside it. It is not a "
    "bill, not an allocation, and not a published figure for what running an "
    "inference workload costs: ADR 0007 D11 publishes none, and a record priced from "
    "a synthetic rate card is economically meaningless."
)

SCALE = 6
SECONDS_PER_HOUR = 3600
BYTES_PER_GIBIBYTE = 2**30
MINIMUM_WINDOW_SECONDS = 60
MAXIMUM_WINDOW_SECONDS = 86_400

# Kubernetes quantity suffixes, as multipliers of the base unit. Binary and decimal
# suffixes are kept apart: 1Gi is 2^30 bytes and 1G is 10^9 bytes.
# The workload contract's own pattern, character for character; a test compares them.
QUANTITY = re.compile(r"^[0-9]+(\.[0-9]+)?(m|k|M|G|T|P|E|Ki|Mi|Gi|Ti|Pi|Ei)?$")
SUFFIX_MULTIPLIER: dict[str, Fraction] = {
    "": Fraction(1),
    "m": Fraction(1, 1000),
    "k": Fraction(10**3),
    "M": Fraction(10**6),
    "G": Fraction(10**9),
    "T": Fraction(10**12),
    "P": Fraction(10**15),
    "E": Fraction(10**18),
    "Ki": Fraction(2**10),
    "Mi": Fraction(2**20),
    "Gi": Fraction(2**30),
    "Ti": Fraction(2**40),
    "Pi": Fraction(2**50),
    "Ei": Fraction(2**60),
}

INSTANT = re.compile(r"^(?P<body>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)Z$")
DECIMAL = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
RATE = re.compile(r"^[0-9]+\.[0-9]{6}$")
SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
CURRENCY = re.compile(r"^[A-Z]{3}$")

INPUT_KEYS = frozenset(
    {
        "schemaVersion",
        "kind",
        "classification",
        "warning",
        "environmentId",
        "basis",
        "priceSourceId",
        "window",
        "capacity",
        "prerequisites",
        "usageEvidence",
        "workloads",
    }
)
USAGE_EVIDENCE_KEYS = frozenset({"path", "sha256"})
EVIDENCE_ROOT = "docs/proof/"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
WORKLOAD_KEYS = frozenset(
    {
        "recordId",
        "identity",
        "declaration",
        "presentForWholeWindow",
        "shapeChangedInWindow",
        "usage",
        "unavailable",
    }
)
IDENTITY_KEYS = frozenset(
    {"workloadId", "ownerId", "environment", "modelId", "runtimeId"}
)
DECLARATION_KEYS = frozenset(
    {"cpuRequest", "memoryRequest", "acceleratorType", "acceleratorCount", "replicas"}
)
ACCELERATOR_TYPES = frozenset({"none", "integrated-gpu", "nvidia-gpu", "amd-gpu"})

#: Usage keys in a record, the method input each one is, and how it is written.
USAGE_INPUTS: tuple[tuple[str, str, str], ...] = (
    ("requests", "requests", "count"),
    ("inputTokens", "input-tokens", "count"),
    ("outputTokens", "output-tokens", "count"),
    ("cpuSeconds", "cpu-seconds", "decimal"),
    ("memoryByteSeconds", "memory-byte-seconds", "decimal"),
    ("acceleratorSeconds", "accelerator-seconds", "decimal"),
)
USAGE_INPUT_IDS = frozenset(input_id for _, input_id, _ in USAGE_INPUTS)
BELOW_MINIMUM = "below-minimum-sample"

PRICE_SOURCE_KEYS = frozenset(
    {
        "priceSourceId",
        "class",
        "name",
        "currency",
        "version",
        "effectiveDate",
        "retrieval",
        "selfIdentifies",
        "maxConfidence",
        "scope",
        "publishable",
        "rates",
        "notes",
    }
)


class CostCalculationError(RuntimeError):
    """The method, an input, or a result is not what the cost method requires."""


class CostCalculationRefused(CostCalculationError):
    """An input the method forbids a calculation from, refused before any figure."""


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def _refuse_float(text: str) -> Any:
    raise CostCalculationRefused(
        f"a binary floating-point number ({text}) appears; every quantity and rate "
        "is a decimal string or an integer"
    )


def _refuse_constant(text: str) -> Any:
    raise CostCalculationRefused(f"a non-numeric constant ({text}) appears")


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise CostCalculationRefused(f"the key '{key}' appears twice in one object")
        document[key] = value
    return document


def loads(text: str, what: str) -> Any:
    """Parse JSON refusing floats, NaN, and duplicate keys."""
    try:
        return json.loads(
            text,
            parse_float=_refuse_float,
            parse_constant=_refuse_constant,
            object_pairs_hook=_unique_keys,
        )
    except json.JSONDecodeError as error:
        raise CostCalculationRefused(f"the {what} is not JSON: {error.msg}") from error


def read_json(path: Path, what: str) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise CostCalculationError(f"the {what} is unreadable") from error
    return loads(text, what)


def dumps(document: Any) -> str:
    """The one serialization every committed JSON document here uses."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_method(path: Path = METHOD_PATH) -> dict[str, Any]:
    method = read_json(path, "cost method")
    if not isinstance(method, dict):
        raise CostCalculationError("the cost method is not an object")
    check_method(method)
    return method


def _object(
    value: Any, field: str, keys: frozenset[str] | None = None
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CostCalculationRefused(f"{field} must be an object")
    if keys is not None and set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        raise CostCalculationRefused(
            f"{field} must declare exactly {sorted(keys)}; missing {missing}, unexpected {extra}"
        )
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise CostCalculationRefused(f"{field} must be a list")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CostCalculationRefused(f"{field} must be a non-empty string")
    return value


def _slug(value: Any, field: str) -> str:
    text = _string(value, field)
    if not SLUG.match(text):
        raise CostCalculationRefused(
            f"{field} must be a lowercase hyphenated identifier"
        )
    return text


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise CostCalculationRefused(f"{field} must be true or false")
    return value


def _count(value: Any, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CostCalculationRefused(
            f"{field} must be an integer of at least {minimum}"
        )
    return value


def parse_decimal(value: Any, field: str) -> Fraction:
    """A non-negative decimal string, exactly. Never a float, never a sign."""
    if not isinstance(value, str) or not DECIMAL.match(value):
        raise CostCalculationRefused(
            f"{field} must be a non-negative decimal string such as '1.5', not {value!r}"
        )
    return Fraction(value)


def parse_instant(value: Any, field: str) -> datetime:
    """An RFC 3339 instant in UTC, written with a Z offset."""
    text = _string(value, field)
    match = INSTANT.match(text)
    if match is None:
        raise CostCalculationRefused(
            f"{field} must be an RFC 3339 instant in UTC ending in Z, not '{text}'"
        )
    try:
        parsed = datetime.fromisoformat(match.group("body"))
    except ValueError as error:
        raise CostCalculationRefused(
            f"{field} is not a real instant: '{text}'"
        ) from error
    return parsed.replace(tzinfo=UTC)


def parse_quantity(value: Any, field: str) -> Fraction:
    """A Kubernetes quantity in its base unit, exactly."""
    text = _string(value, field)
    match = QUANTITY.match(text)
    if match is None:
        raise CostCalculationRefused(
            f"{field} must be a Kubernetes quantity such as 500m, 2, 2Gi, or 1500Mi, not '{text}'"
        )
    suffix = match.group(2) or ""
    return Fraction(text[: len(text) - len(suffix)]) * SUFFIX_MULTIPLIER[suffix]


def cpu_cores(value: Any, field: str) -> Fraction:
    return parse_quantity(value, field)


def memory_gibibytes(value: Any, field: str) -> Fraction:
    return parse_quantity(value, field) / BYTES_PER_GIBIBYTE


def round_half_even(value: Fraction, scale: int = SCALE) -> str:
    """Round an exact value once, half-even, and write it at the record scale."""
    scaled = value * 10**scale
    floor = scaled.numerator // scaled.denominator
    remainder = scaled - floor
    if remainder > Fraction(1, 2) or (remainder == Fraction(1, 2) and floor % 2 == 1):
        floor += 1
    sign = "-" if floor < 0 else ""
    digits = str(abs(floor)).rjust(scale + 1, "0")
    return f"{sign}{digits[:-scale]}.{digits[-scale:]}"


def refuse_private(text: str, what: str) -> None:
    for shape in PRIVATE_SHAPES:
        match = shape.search(text)
        if match is not None:
            raise CostCalculationRefused(
                f"the {what} carries a value shaped like a host path, a user directory, "
                f"or a network address ('{match.group(0)}')"
            )


# --------------------------------------------------------------------------
# The method, and the price sources it commits
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PriceSource:
    price_source_id: str
    price_class: str
    version: str
    effective_date: str
    currency: str
    self_identifies: bool
    rates: Mapping[str, Fraction]

    def rate(self, unit: str) -> Fraction:
        return self.rates[unit]


def _level_rank(method: Mapping[str, Any]) -> dict[str, int]:
    return {row["levelId"]: row["rank"] for row in method["confidenceLevels"]}


def check_price_source(source: Any, method: Mapping[str, Any]) -> PriceSource:
    """Refuse a price source that could not be cited, reproduced, or read as synthetic."""
    row = _object(source, "a price source", PRICE_SOURCE_KEYS)
    source_id = _slug(row["priceSourceId"], "priceSourceId")
    field = f"price source '{source_id}'"
    classes = {item["classId"]: item for item in method["priceSourceClasses"]}
    price_class = _string(row["class"], f"{field} class")
    if price_class not in classes:
        raise CostCalculationRefused(
            f"{field} names a class the method does not declare: '{price_class}'"
        )
    if row["retrieval"] != "committed":
        raise CostCalculationRefused(
            f"{field} is not committed; no price is fetched at runtime (ADR 0007 D5)"
        )
    refuse_private(json.dumps(row), field)
    if "http://" in json.dumps(row) or "https://" in json.dumps(row):
        raise CostCalculationRefused(
            f"{field} carries a URL; a price is committed, never retrieved"
        )
    version = _string(row["version"], f"{field} version")
    effective = _string(row["effectiveDate"], f"{field} effectiveDate")
    try:
        date.fromisoformat(effective)
    except ValueError as error:
        raise CostCalculationRefused(
            f"{field} effectiveDate is not a date: '{effective}'"
        ) from error
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", effective):
        raise CostCalculationRefused(
            f"{field} effectiveDate must be written YYYY-MM-DD"
        )
    currency = _string(row["currency"], f"{field} currency")
    if not CURRENCY.match(currency):
        raise CostCalculationRefused(f"{field} currency must be a three-letter code")
    ranks = _level_rank(method)
    ceiling = row["maxConfidence"]
    if (
        ceiling not in ranks
        or ranks[ceiling] > ranks[classes[price_class]["maxConfidence"]]
    ):
        raise CostCalculationRefused(
            f"{field} claims a confidence ceiling its class does not allow"
        )
    self_identifies = _bool(row["selfIdentifies"], f"{field} selfIdentifies")
    publishable = _bool(row["publishable"], f"{field} publishable")
    if price_class == "synthetic-illustrative" and (
        not self_identifies
        or publishable
        or ceiling != "none"
        or "invented" not in _string(row["notes"], f"{field} notes")
    ):
        raise CostCalculationRefused(
            f"{field} is synthetic and does not say so in its own contents: it must "
            "self-identify, be unpublishable, cap confidence at none, and say its rates are invented"
        )
    priced = {unit["unitId"] for unit in method["units"] if unit["priced"]}
    rates: dict[str, Fraction] = {}
    for entry in _list(row["rates"], f"{field} rates"):
        item = _object(entry, f"{field} rate", frozenset({"unit", "ratePerHour"}))
        unit = _string(item["unit"], f"{field} rate unit")
        if unit not in priced:
            raise CostCalculationRefused(
                f"{field} prices '{unit}', which is not a priced unit"
            )
        if unit in rates:
            raise CostCalculationRefused(f"{field} prices '{unit}' twice")
        text = item["ratePerHour"]
        if not isinstance(text, str) or not RATE.match(text):
            raise CostCalculationRefused(
                f"{field} rate for '{unit}' must be a non-negative decimal string at six places, not {text!r}"
            )
        rates[unit] = Fraction(text)
    if set(rates) != priced:
        raise CostCalculationRefused(
            f"{field} does not price every priced unit; missing {sorted(priced - set(rates))}"
        )
    return PriceSource(
        price_source_id=source_id,
        price_class=price_class,
        version=version,
        effective_date=effective,
        currency=currency,
        self_identifies=self_identifies,
        rates=rates,
    )


def check_method(method: Mapping[str, Any]) -> None:
    """Refuse a method this calculation cannot apply as ADR 0007 and ADR 0014 decide."""
    try:
        reachable = [row["basisId"] for row in method["bases"] if row["v1Reachable"]]
        selected_methods = [
            row["methodId"] for row in method["allocationMethods"] if row["selected"]
        ]
        selected_treatments = [
            row["treatmentId"]
            for row in method["residualTreatments"]
            if row["selected"]
        ]
        sources = method["priceSources"]
        method["confidenceRules"]
        method["denominatorRules"]["minimumRequestsForUnitCost"]
        method["denominatorRules"]["minimumTokensForUnitCost"]
        method["recordShape"]["fields"]
    except (KeyError, TypeError) as error:
        raise CostCalculationError(
            f"the cost method lacks a section this calculation reads: {error}"
        ) from error
    if reachable != [BASIS]:
        raise CostCalculationError(
            f"the cost method reaches {reachable}; V1 calculates '{BASIS}' only"
        )
    if selected_methods != [ALLOCATION_METHOD]:
        raise CostCalculationError(
            f"the cost method selects {selected_methods}, not '{ALLOCATION_METHOD}'"
        )
    if selected_treatments != [RESIDUAL_TREATMENT]:
        raise CostCalculationError(
            f"the cost method selects {selected_treatments}, not '{RESIDUAL_TREATMENT}'"
        )
    identifiers = [row.get("priceSourceId") for row in sources]
    if len(identifiers) != len(set(identifiers)):
        raise CostCalculationError("the cost method declares a price source twice")
    for source in sources:
        check_price_source(source, method)


def price_source(method: Mapping[str, Any], source_id: str) -> PriceSource:
    for row in method["priceSources"]:
        if row["priceSourceId"] == source_id:
            return check_price_source(row, method)
    raise CostCalculationRefused(
        f"the price source '{source_id}' is not committed in the cost method; no other source is read"
    )


def derive_confidence(facts: Mapping[str, Any], method: Mapping[str, Any]) -> str:
    """The lowest ceiling among the rules whose conditions all hold. Never asserted."""
    ranks = _level_rank(method)
    ceilings: list[str] = []
    for rule in method["confidenceRules"]:
        holds = True
        for key, expected in rule["when"].items():
            actual = facts[key]
            if (isinstance(expected, list) and actual not in expected) or (
                not isinstance(expected, list) and actual != expected
            ):
                holds = False
        if holds:
            ceilings.append(rule["ceiling"])
    if not ceilings:
        raise CostCalculationError(f"no confidence rule applies to {dict(facts)}")
    return min(ceilings, key=lambda level: ranks[level])


# --------------------------------------------------------------------------
# The input document
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Window:
    start: str
    end: str
    seconds: Fraction

    @property
    def hours(self) -> Fraction:
        return self.seconds / SECONDS_PER_HOUR


def _window(value: Any) -> Window:
    window = _object(value, "window", frozenset({"start", "end"}))
    start = parse_instant(window["start"], "window.start")
    end = parse_instant(window["end"], "window.end")
    delta = end - start
    seconds = Fraction(delta.days * 86_400 + delta.seconds) + Fraction(
        delta.microseconds, 10**6
    )
    if seconds <= 0:
        raise CostCalculationRefused(
            "window.end must be after window.start; a window is half-open"
        )
    if seconds < MINIMUM_WINDOW_SECONDS or seconds > MAXIMUM_WINDOW_SECONDS:
        raise CostCalculationRefused(
            "a window is at least one minute and at most one day long"
        )
    if seconds == SECONDS_PER_HOUR and (
        start.minute,
        start.second,
        start.microsecond,
    ) != (
        0,
        0,
        0,
    ):
        raise CostCalculationRefused(
            "a window of the default length, one hour, starts on the hour"
        )
    return Window(start=window["start"], end=window["end"], seconds=seconds)


def _unavailable_reason(method: Mapping[str, Any], reason: Any, field: str) -> str:
    reasons = {row["reasonId"] for row in method["missingDataReasons"]}
    text = _string(reason, field)
    if text not in reasons:
        raise CostCalculationRefused(
            f"{field} gives a reason the method does not declare: '{text}'"
        )
    if text == BELOW_MINIMUM:
        raise CostCalculationRefused(
            f"{field} is '{BELOW_MINIMUM}', which describes an output, not a missing input"
        )
    return text


@dataclass(frozen=True, slots=True)
class Usage:
    counts: Mapping[str, int | None]
    quantities: Mapping[str, Fraction | None]
    unavailable: Mapping[str, str]


def _usage(
    workload: Mapping[str, Any], method: Mapping[str, Any], field: str, devices: int
) -> Usage:
    usage = _object(
        workload["usage"],
        f"{field}.usage",
        frozenset(key for key, _, _ in USAGE_INPUTS),
    )
    unavailable_raw = _object(workload["unavailable"], f"{field}.unavailable")
    for input_id in unavailable_raw:
        if input_id not in USAGE_INPUT_IDS:
            raise CostCalculationRefused(
                f"{field}.unavailable names '{input_id}', which is not a usage input"
            )
    counts: dict[str, int | None] = {}
    quantities: dict[str, Fraction | None] = {}
    unavailable: dict[str, str] = {}
    for key, input_id, kind in USAGE_INPUTS:
        value = usage[key]
        declared = input_id in unavailable_raw
        target: dict[str, Any] = counts if kind == "count" else quantities
        if input_id == "accelerator-seconds" and devices == 0:
            # Not reserved, so not applicable: neither a measurement nor a gap.
            if value is not None:
                raise CostCalculationRefused(
                    f"{field} reserves no accelerator and reports accelerator seconds; the inputs conflict"
                )
            if declared:
                raise CostCalculationRefused(
                    f"{field} reserves no accelerator, so accelerator seconds are not "
                    "missing; declare no reason for them"
                )
            target[key] = None
            continue
        if value is None:
            if not declared:
                raise CostCalculationRefused(
                    f"{field}.usage.{key} is null and {field}.unavailable gives no reason; "
                    "a missing input carries a reason"
                )
            unavailable[input_id] = _unavailable_reason(
                method, unavailable_raw[input_id], f"{field}.unavailable.{input_id}"
            )
            target[key] = None
            continue
        if declared:
            raise CostCalculationRefused(
                f"{field}.usage.{key} is set and also declared unavailable; an unavailable input is null"
            )
        if kind == "count":
            counts[key] = _count(value, f"{field}.usage.{key}")
        else:
            quantities[key] = parse_decimal(value, f"{field}.usage.{key}")
    return Usage(counts=counts, quantities=quantities, unavailable=unavailable)


# --------------------------------------------------------------------------
# The calculation
# --------------------------------------------------------------------------


def _optional(value: Fraction | None) -> str | None:
    return None if value is None else round_half_even(value)


def _usage_evidence(value: Any, classification: str) -> dict[str, str] | None:
    """The committed record a measured class names, checked to exist and to agree.

    A synthetic input names none. A measured one names a record under docs/proof by
    path and by the SHA-256 of its content with line endings normalized to LF, and
    that record must declare the same evidence class. This checks that the named
    evidence exists and is of the class claimed; it cannot check that the usage
    values typed into the input are the ones that evidence holds.
    """
    if classification in UNMEASURED_USAGE_CLASSES:
        if value is not None:
            raise CostCalculationRefused(
                "a synthetic input names no usage evidence; usageEvidence must be null"
            )
        return None
    if value is None:
        raise CostCalculationRefused(
            f"a '{classification}' input must name the committed record its usage came "
            "from in usageEvidence"
        )
    reference = _object(value, "usageEvidence", USAGE_EVIDENCE_KEYS)
    path = _string(reference["path"], "usageEvidence.path")
    digest = _string(reference["sha256"], "usageEvidence.sha256")
    parts = path.split("/")
    if not path.startswith(EVIDENCE_ROOT) or "\\" in path or ".." in parts:
        raise CostCalculationRefused(
            f"usageEvidence.path must be a repository-relative path under {EVIDENCE_ROOT}"
        )
    if not SHA256.match(digest):
        raise CostCalculationRefused(
            "usageEvidence.sha256 must be 64 lowercase hex digits"
        )
    try:
        text = (REPO_ROOT / path).read_text(encoding="utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeError) as error:
        raise CostCalculationRefused(
            f"usageEvidence.path names no readable committed record: '{path}'"
        ) from error
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:
        raise CostCalculationRefused(
            f"usageEvidence.sha256 does not match the record at '{path}'"
        )
    try:
        declared = json.loads(text).get("evidenceClass")
    except (json.JSONDecodeError, AttributeError) as error:
        raise CostCalculationRefused(
            f"the record at '{path}' is not a JSON object declaring an evidence class"
        ) from error
    if declared != classification:
        raise CostCalculationRefused(
            f"the record at '{path}' declares evidence class '{declared}', and the input "
            f"claims '{classification}'"
        )
    return {"path": path, "sha256": digest}


def _refuse_basis(method: Mapping[str, Any], basis: Any) -> None:
    if basis == BASIS:
        return
    for row in method["bases"]:
        if row["basisId"] == basis:
            raise CostCalculationRefused(
                f"the '{basis}' basis is not reachable in V1: {row['unreachableReason']}"
            )
    raise CostCalculationRefused(f"'{basis}' is not a basis the cost method declares")


def calculate(document: Any, method: Mapping[str, Any]) -> dict[str, Any]:
    """Compute a cost calculation result from one input document. Pure and exact."""
    check_method(method)
    top = _object(document, "the calculation input", INPUT_KEYS)
    refuse_private(json.dumps(top), "calculation input")
    if top["schemaVersion"] != SCHEMA_VERSION or top["kind"] != INPUT_KIND:
        raise CostCalculationRefused(
            f"the calculation input must be {SCHEMA_VERSION} {INPUT_KIND}"
        )
    _refuse_basis(method, top["basis"])

    classification = _string(top["classification"], "classification")
    if classification not in MEASURED_USAGE_CLASSES | UNMEASURED_USAGE_CLASSES:
        raise CostCalculationRefused(
            f"classification '{classification}' is not an evidence class a usage input may come from; "
            f"expected one of {sorted(MEASURED_USAGE_CLASSES | UNMEASURED_USAGE_CLASSES)}"
        )
    warning = _string(top["warning"], "warning")
    if classification == "synthetic" and "synthetic" not in warning.lower():
        raise CostCalculationRefused(
            "a synthetic input must say it is synthetic in its own warning"
        )

    usage_evidence = _usage_evidence(top["usageEvidence"], classification)

    environment = _slug(top["environmentId"], "environmentId")
    source = price_source(method, _slug(top["priceSourceId"], "priceSourceId"))
    window = _window(top["window"])
    hours = window.hours

    capacity = _object(
        top["capacity"],
        "capacity",
        frozenset({"cpuCores", "memoryGibibytes", "acceleratorDevices"}),
    )
    capacity_cpu = parse_decimal(capacity["cpuCores"], "capacity.cpuCores")
    capacity_memory = parse_decimal(
        capacity["memoryGibibytes"], "capacity.memoryGibibytes"
    )
    capacity_accelerators = _count(
        capacity["acceleratorDevices"], "capacity.acceleratorDevices"
    )
    if capacity_cpu <= 0 or capacity_memory <= 0:
        raise CostCalculationRefused(
            "node capacity must declare processor and memory above zero"
        )
    capacity_amount = (
        capacity_cpu * source.rate("cpu-core-hour")
        + capacity_memory * source.rate("memory-gibibyte-hour")
        + capacity_accelerators * source.rate("accelerator-device-hour")
    ) * hours
    capacity_published = round_half_even(capacity_amount)
    if Fraction(capacity_published) <= 0:
        raise CostCalculationRefused(
            "the node's capacity amount rounds to zero; nothing can be shared out of it"
        )

    minimum_requests: int = method["denominatorRules"]["minimumRequestsForUnitCost"]
    minimum_tokens: int = method["denominatorRules"]["minimumTokensForUnitCost"]

    workloads = _list(top["workloads"], "workloads")
    if not workloads:
        raise CostCalculationRefused("a calculation covers at least one workload")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    measured_cpu_total = Fraction(0)
    measured_memory_total = Fraction(0)
    measured_accelerator_total = Fraction(0)
    for index, raw in enumerate(workloads):
        field = f"workloads[{index}]"
        if (
            isinstance(raw, dict)
            and isinstance(raw.get("identity"), dict)
            and "tenantId" in raw["identity"]
        ):
            raise CostCalculationRefused(
                f"{field}.identity carries a tenant identifier; a committed cost record may not "
                "(the telemetry catalog classes it tenant-attributable)"
            )
        workload = _object(raw, field, WORKLOAD_KEYS)
        record_id = _slug(workload["recordId"], f"{field}.recordId")
        if record_id in seen:
            raise CostCalculationRefused(f"record '{record_id}' appears twice")
        seen.add(record_id)
        identity = _object(workload["identity"], f"{field}.identity", IDENTITY_KEYS)
        for key in sorted(IDENTITY_KEYS):
            _string(identity[key], f"{field}.identity.{key}")
        if identity["environment"] != environment:
            raise CostCalculationRefused(
                f"{field}.identity.environment is '{identity['environment']}' and the calculation covers '{environment}'"
            )
        if _bool(workload["shapeChangedInWindow"], f"{field}.shapeChangedInWindow"):
            raise CostCalculationRefused(
                f"{field} changed its resource requests, accelerator count, or replica count inside "
                "the window; split the window at the change and calculate each segment"
            )
        whole_window = _bool(
            workload["presentForWholeWindow"], f"{field}.presentForWholeWindow"
        )

        declaration = _object(
            workload["declaration"], f"{field}.declaration", DECLARATION_KEYS
        )
        cores = cpu_cores(declaration["cpuRequest"], f"{field}.declaration.cpuRequest")
        gibibytes = memory_gibibytes(
            declaration["memoryRequest"], f"{field}.declaration.memoryRequest"
        )
        accelerator_type = _string(
            declaration["acceleratorType"], f"{field}.declaration.acceleratorType"
        )
        devices = _count(
            declaration["acceleratorCount"], f"{field}.declaration.acceleratorCount"
        )
        replicas = _count(
            declaration["replicas"], f"{field}.declaration.replicas", minimum=1
        )
        if accelerator_type not in ACCELERATOR_TYPES:
            raise CostCalculationRefused(
                f"{field}.declaration.acceleratorType '{accelerator_type}' is not declared"
            )
        if (accelerator_type == "none") != (devices == 0):
            raise CostCalculationRefused(
                f"{field}.declaration reserves accelerator type '{accelerator_type}' with count {devices}"
            )

        if devices * replicas > capacity_accelerators:
            raise CostCalculationRefused(
                f"{field} reserves {devices * replicas} accelerator device(s) and the node "
                f"declares {capacity_accelerators}"
            )
        usage = _usage(workload, method, field, devices)
        unavailable = usage.unavailable
        cpu_seconds = usage.quantities["cpuSeconds"]
        memory_byte_seconds = usage.quantities["memoryByteSeconds"]
        accelerator_seconds = usage.quantities["acceleratorSeconds"]

        if (
            accelerator_seconds is not None
            and accelerator_seconds > capacity_accelerators * window.seconds
        ):
            raise CostCalculationRefused(
                f"{field} reports more accelerator seconds than the node's declared capacity holds in the window"
            )
        if cpu_seconds is not None and cpu_seconds > capacity_cpu * window.seconds:
            raise CostCalculationRefused(
                f"{field} reports more processor seconds than the node's declared capacity holds in the window"
            )
        if memory_byte_seconds is not None and memory_byte_seconds > (
            capacity_memory * BYTES_PER_GIBIBYTE * window.seconds
        ):
            raise CostCalculationRefused(
                f"{field} reports more memory byte-seconds than the node's declared capacity holds in the window"
            )

        # An accelerator term needs measured device seconds only when a device was
        # reserved. With none reserved the term is absent from the sum, not a zero
        # written in for a measurement nobody took.
        amount: Fraction | None = None
        accelerator_ready = devices == 0 or accelerator_seconds is not None
        if (
            cpu_seconds is not None
            and memory_byte_seconds is not None
            and accelerator_ready
        ):
            used = cpu_seconds * source.rate("cpu-core-hour") + (
                memory_byte_seconds
                / BYTES_PER_GIBIBYTE
                * source.rate("memory-gibibyte-hour")
            )
            if accelerator_seconds is not None:
                used += accelerator_seconds * source.rate("accelerator-device-hour")
            amount = used / SECONDS_PER_HOUR
        if cpu_seconds is not None:
            measured_cpu_total += cpu_seconds
        if memory_byte_seconds is not None:
            measured_memory_total += memory_byte_seconds
        if accelerator_seconds is not None:
            measured_accelerator_total += accelerator_seconds

        reasons = set(unavailable.values())
        requests = usage.counts["requests"]
        input_tokens = usage.counts["inputTokens"]
        output_tokens = usage.counts["outputTokens"]
        per_thousand: Fraction | None = None
        if amount is not None and requests is not None:
            if requests >= minimum_requests:
                per_thousand = amount / requests * 1000
            else:
                reasons.add(BELOW_MINIMUM)
        tokens: int | None = None
        per_million: Fraction | None = None
        if input_tokens is not None and output_tokens is not None:
            tokens = input_tokens + output_tokens
            if amount is not None:
                if tokens >= minimum_tokens:
                    per_million = amount / tokens * 1_000_000
                else:
                    reasons.add(BELOW_MINIMUM)

        facts = {
            "basis": BASIS,
            "priceSourceClass": source.price_class,
            # Processor and memory use both present and from a measured class
            # whose committed record was named and matched (ADR 0014 D3). The
            # accelerator term does not decide it.
            "hasMeasuredUtilisation": classification in MEASURED_USAGE_CLASSES
            and cpu_seconds is not None
            and memory_byte_seconds is not None,
            "windowComplete": whole_window,
            "shapeChangedInWindow": False,
        }
        records.append(
            {
                "recordId": record_id,
                "method": {"version": METHOD_VERSION},
                "period": {"start": window.start, "end": window.end},
                "identity": {key: identity[key] for key in sorted(IDENTITY_KEYS)},
                "reserved": {
                    "cpuCoreHours": round_half_even(cores * replicas * hours),
                    "memoryGibibyteHours": round_half_even(
                        gibibytes * replicas * hours
                    ),
                    "acceleratorDeviceHours": round_half_even(
                        Fraction(devices * replicas) * hours
                    ),
                },
                "usage": {
                    "requests": requests,
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "cpuSeconds": _optional(cpu_seconds),
                    "memoryByteSeconds": _optional(memory_byte_seconds),
                    "acceleratorSeconds": _optional(accelerator_seconds),
                },
                "cost": {
                    "amount": _optional(amount),
                    "currency": source.currency,
                    "amountScale": SCALE,
                    "basis": BASIS,
                    "allocationMethod": ALLOCATION_METHOD,
                    "priceSourceId": source.price_source_id,
                    "priceSourceClass": source.price_class,
                    "priceSourceVersion": source.version,
                    "priceSourceEffectiveDate": source.effective_date,
                    "confidence": derive_confidence(facts, method),
                },
                "derived": {
                    "amountPerHour": None
                    if amount is None
                    else round_half_even(amount / hours),
                    "shareOfNodeCapacity": None
                    if amount is None
                    else round_half_even(amount / capacity_amount),
                    "costPerThousandRequests": _optional(per_thousand),
                    "costPerThousandRequestsDenominator": requests,
                    "costPerMillionTokens": _optional(per_million),
                    "costPerMillionTokensDenominator": tokens,
                },
                "completeness": {
                    "unavailableInputs": sorted(unavailable),
                    "reasons": sorted(reasons),
                    "windowComplete": whole_window,
                },
                "facts": facts,
                "evidence": {
                    "assumptionsRef": ASSUMPTIONS_REF,
                    "usageEvidenceClass": classification,
                },
            }
        )

    if (
        measured_cpu_total > capacity_cpu * window.seconds
        or measured_memory_total > capacity_memory * BYTES_PER_GIBIBYTE * window.seconds
        or measured_accelerator_total > capacity_accelerators * window.seconds
    ):
        raise CostCalculationRefused(
            "the workloads together report more measured use than the node's declared capacity "
            "holds in the window; the inputs conflict"
        )

    amounts = [record["cost"]["amount"] for record in records]
    workload_sum: str | None = None
    unallocated: str | None = None
    unallocated_share: str | None = None
    # The residual is null exactly when a workload amount is, for the reasons that
    # made that amount null. A residual taken over the lines that exist would hand
    # the missing workload's use to "nobody".
    unallocated_reasons = sorted(
        {
            reason
            for record in records
            if record["cost"]["amount"] is None
            for reason in record["completeness"]["reasons"]
            if reason != BELOW_MINIMUM
        }
    )
    if all(value is not None for value in amounts):
        total = sum((Fraction(value) for value in amounts), Fraction(0))
        workload_sum = round_half_even(total)
        residual = Fraction(capacity_published) - total
        if residual < 0:
            raise CostCalculationRefused(
                "the workload amounts exceed the node's capacity amount; the inputs conflict"
            )
        unallocated = round_half_even(residual)
        unallocated_share = round_half_even(residual / Fraction(capacity_published))

    prerequisites: list[dict[str, Any]] = []
    prerequisite_total = Fraction(0)
    seen_prerequisites: set[str] = set()
    for index, raw in enumerate(_list(top["prerequisites"], "prerequisites")):
        field = f"prerequisites[{index}]"
        item = _object(
            raw, field, frozenset({"resourceId", "storageGibibytes", "attributedTo"})
        )
        resource_id = _slug(item["resourceId"], f"{field}.resourceId")
        if resource_id in seen_prerequisites:
            raise CostCalculationRefused(f"prerequisite '{resource_id}' appears twice")
        seen_prerequisites.add(resource_id)
        if item["attributedTo"] != PREREQUISITE_OWNER:
            raise CostCalculationRefused(
                f"{field} is attributed to '{item['attributedTo']}'; a resource that outlives a "
                f"release is attributed to the {PREREQUISITE_OWNER}, never to a workload"
            )
        storage = parse_decimal(item["storageGibibytes"], f"{field}.storageGibibytes")
        published = round_half_even(
            storage * hours * source.rate("storage-gibibyte-hour")
        )
        prerequisite_total += Fraction(published)
        prerequisites.append(
            {
                "resourceId": resource_id,
                "storageGibibytes": round_half_even(storage),
                "amount": published,
                "attributedTo": PREREQUISITE_OWNER,
            }
        )

    result: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": RESULT_KIND,
        "classification": RESULT_CLASSIFICATION,
        "usageEvidenceClass": classification,
        "usageEvidence": usage_evidence,
        "inputWarning": warning,
        "boundary": BOUNDARY,
        "publishedCostFigure": False,
        "methodRef": METHOD_REF,
        "decisionRefs": list(DECISION_REFS),
        "environmentId": environment,
        "basis": BASIS,
        "allocationMethod": ALLOCATION_METHOD,
        "residualTreatment": RESIDUAL_TREATMENT,
        "priceSource": {
            "priceSourceId": source.price_source_id,
            "class": source.price_class,
            "version": source.version,
            "effectiveDate": source.effective_date,
            "currency": source.currency,
            "selfIdentifies": source.self_identifies,
        },
        "window": {
            "start": window.start,
            "end": window.end,
            "hours": round_half_even(hours),
        },
        "capacity": {
            "cpuCores": round_half_even(capacity_cpu),
            "memoryGibibytes": round_half_even(capacity_memory),
            "acceleratorDevices": capacity_accelerators,
            "amount": capacity_published,
        },
        "records": records,
        "unallocated": {
            "amount": unallocated,
            "shareOfNodeCapacity": unallocated_share,
            "unavailableReasons": unallocated_reasons,
            "meaning": (
                "Node capacity no workload in this calculation was measured using: idle "
                "capacity, the platform and control plane, and any workload the input does "
                "not list. It is reported, never spread."
            ),
        },
        "prerequisites": prerequisites,
        "totals": {
            "workloadAmountSum": workload_sum,
            "nodeCapacityAmount": capacity_published,
            "closes": None if workload_sum is None else True,
            "prerequisiteAmountSum": round_half_even(prerequisite_total),
            "environmentAmount": round_half_even(
                Fraction(capacity_published) + prerequisite_total
            ),
        },
    }
    check_result(result, method)
    return result


# --------------------------------------------------------------------------
# The output shape the method publishes
# --------------------------------------------------------------------------

DECIMAL_STRING = re.compile(r"^-?[0-9]+\.[0-9]{6}$")
BILLING_WORDS = re.compile(r"invoice|billing|billed|charge|spend", flags=re.IGNORECASE)


def _at(record: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    node: Any = record
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _type_holds(kind: str, value: Any) -> bool:
    if kind == "instant":
        return isinstance(value, str) and bool(INSTANT.match(value))
    if kind == "string":
        return isinstance(value, str) and bool(value)
    if kind == "decimal":
        return isinstance(value, str) and bool(DECIMAL_STRING.match(value))
    if kind == "decimal-or-null":
        return value is None or (
            isinstance(value, str) and bool(DECIMAL_STRING.match(value))
        )
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "integer-or-null":
        return value is None or (isinstance(value, int) and not isinstance(value, bool))
    if kind == "object":
        return isinstance(value, Mapping)
    raise CostCalculationError(
        f"the record shape declares a type this check does not know: '{kind}'"
    )


def check_record(record: Mapping[str, Any], method: Mapping[str, Any]) -> None:
    """Validate one record against the output shape published in the cost method."""
    record_id = record.get("recordId", "?")
    for field in method["recordShape"]["fields"]:
        present, value = _at(record, field["path"])
        if not field["committedRecordAllowed"]:
            if present:
                raise CostCalculationError(
                    f"record '{record_id}' carries {field['path']}, which no committed record may carry"
                )
            continue
        if not present:
            if field["required"]:
                raise CostCalculationError(
                    f"record '{record_id}' lacks {field['path']}"
                )
            continue
        if not _type_holds(field["type"], value):
            raise CostCalculationError(
                f"record '{record_id}' {field['path']} is not a {field['type']}: {value!r}"
            )
    if "tenant" in json.dumps(record).lower():
        raise CostCalculationError(f"record '{record_id}' mentions a tenant")
    offending = BILLING_WORDS.search(json.dumps(record))
    if offending is not None:
        raise CostCalculationError(
            f"record '{record_id}' is {record['cost']['basis']} and uses the word '{offending.group(0)}'"
        )


def check_result(result: Mapping[str, Any], method: Mapping[str, Any]) -> None:
    """Validate a result: every record's shape, one basis, and lines that close."""
    for key, value in _walk(result):
        if isinstance(value, float):
            raise CostCalculationError(f"{key} is a binary float")
    if (
        result.get("publishedCostFigure") is not False
        or result.get("boundary") != BOUNDARY
    ):
        raise CostCalculationError(
            "a result must carry its boundary and publish no cost figure"
        )
    for record in result["records"]:
        check_record(record, method)
        if record["cost"]["basis"] != result["basis"]:
            raise CostCalculationError(
                "a result mixes bases; amounts on different bases are never summed"
            )
        if record["cost"]["confidence"] != derive_confidence(record["facts"], method):
            raise CostCalculationError(
                f"record '{record['recordId']}' asserts a confidence its facts do not derive"
            )
    totals = result["totals"]
    if totals["workloadAmountSum"] is not None:
        workloads = sum(
            (Fraction(record["cost"]["amount"]) for record in result["records"]),
            Fraction(0),
        )
        if Fraction(totals["workloadAmountSum"]) != workloads:
            raise CostCalculationError(
                "the workload amounts do not sum to the workload total"
            )
        if workloads + Fraction(result["unallocated"]["amount"]) != Fraction(
            totals["nodeCapacityAmount"]
        ):
            raise CostCalculationError(
                "the workload lines and the unallocated line do not close against the node"
            )


def _walk(node: Any, key: str = "$") -> Sequence[tuple[str, Any]]:
    found: list[tuple[str, Any]] = [(key, node)]
    if isinstance(node, Mapping):
        for name, value in node.items():
            found.extend(_walk(value, f"{key}.{name}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_walk(value, f"{key}[{index}]"))
    return found
