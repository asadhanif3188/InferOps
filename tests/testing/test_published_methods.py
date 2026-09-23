"""Deterministic checks over the published V1 security, observability, and cost methods.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness.

Three method records are published: one beside the security baseline, one beside
the telemetry catalog, and one beside the cost method. Each walks a fixed list of
topics, and every topic keeps two lists apart: what is implemented, and what is
not. This suite exists so that the separation is a property of the data rather
than of the prose around it.

What it establishes is narrow and worth stating, because the gap is the point:

* an implemented item names at least one test or gate **and** at least one
  committed record, every one of which resolves -- a test function that is
  defined, a workflow job that exists, a file that is committed;
* an implemented item is never resting on an uncertified claim, a control the
  baseline does not call implemented, a metric the catalog says nothing emits, a
  cost rule enforced by review alone, or a basis V1 cannot reach;
* a not-implemented item is never resting on a certified claim or an implemented
  control, names something that carries it, and says what is not claimed in a
  sentence that denies;
* nothing is left out -- every control, register entry, exception, catalog metric,
  alert, cost rule, basis, cost limitation, and open cost question appears, on the
  side its own record puts it;
* each document says, section by section, the identifiers its record holds, and
  holds no identifier its record lacks;
* every figure the cost and capacity method quotes reads back out of the committed
  file and pointer it names, and the document quotes no six-place figure it does
  not declare.

It establishes **nothing about whether a named test is a strong one**, whether a
control works, or whether anything is defended or observed in operation. The
method records restate no status; every status here is read from the record that
owns it, and a method that disagreed with one would fail below rather than win.
"""

from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_EVEN, Decimal
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]

SECURITY_METHOD = "docs/security/security-method.v1alpha1.json"
OBSERVABILITY_METHOD = "docs/telemetry/observability-method.v1alpha1.json"
COST_METHOD = "docs/cost/cost-capacity-method.v1alpha1.json"
METHODS = (SECURITY_METHOD, OBSERVABILITY_METHOD, COST_METHOD)

BASELINE_PATH = REPO_ROOT / "docs" / "security" / "security-baseline.v1alpha1.json"
CATALOG_PATH = REPO_ROOT / "docs" / "telemetry" / "telemetry-catalog.v1alpha1.json"
ALERTS_PATH = REPO_ROOT / "docs" / "telemetry" / "inference-alerts.v1alpha1.json"
COST_RULES_PATH = REPO_ROOT / "docs" / "cost" / "cost-method.v1alpha1.json"
REGISTER_PATH = REPO_ROOT / "docs" / "testing" / "claim-evidence-matrix.v1alpha2.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "checks.yml"
PROOF_ROOT = "docs/proof/"

EXPECTED_ID = {
    SECURITY_METHOD: "https://inferops.io/security/security-method.v1alpha1.json",
    OBSERVABILITY_METHOD: "https://inferops.io/telemetry/observability-method.v1alpha1.json",
    COST_METHOD: "https://inferops.io/cost/cost-capacity-method.v1alpha1.json",
}
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

#: The topics each method must cover, in order. These are the subjects the V1
#: security, observability, and cost methods are published to answer; a record
#: that dropped one would still pass every other check here, so the list is fixed
#: in the suite rather than read from the record it constrains.
REQUIRED_TOPICS = {
    SECURITY_METHOD: (
        "assets-and-trust-boundaries",
        "model-and-image-supply-chain",
        "secrets",
        "api-and-network-exposure",
        "container-and-kubernetes-controls",
        "scan-and-policy-gates",
        "exceptions",
        "prompt-and-response-handling",
        "deferred-risks",
        "production-design-versus-certification",
    ),
    OBSERVABILITY_METHOD: (
        "resource-and-ai-attributes",
        "logs-and-redaction",
        "metrics-and-cardinality",
        "collection",
        "dashboard-semantics",
        "alerts",
        "retention-assumptions",
        "deferred-observability-risks",
        "production-design-versus-certification",
    ),
    COST_METHOD: (
        "billing-estimate-and-allocation",
        "formula-units-and-precision",
        "price-basis",
        "inputs-and-measurement-window",
        "allocation-idle-and-shared-cost",
        "outputs-and-record-mapping",
        "performance-linkage",
        "confidence-and-uncertainty",
        "excluded-costs",
        "dashboard-and-query-hooks",
        "capacity-limitations",
    ),
}

EVIDENCE_KINDS = ("test", "ci-gate", "record", "code", "configuration")

#: What a not-implemented item may be carried by. At least one must be named.
ANCHOR_FIELDS = (
    "controlIds",
    "registerRefs",
    "claimIds",
    "gapIds",
    "signals",
    "exceptionIds",
    "ruleIds",
    "basisIds",
    "limitationIds",
    "questionIds",
)

#: How a quoted figure is written from the value its pointer reaches. Each is the
#: one way the source record's own convention is spelled in prose.
FIGURE_TRANSFORMS = {
    "text": lambda value: str(value),
    "integer": lambda value: f"{value:,}",
    "milli": lambda value: f"{Decimal(value) / 1000:.3f}",
    "permille-as-percent": lambda value: f"{Decimal(value) / 10:.1f}%",
}
SIX_PLACE_FIGURE = re.compile(r"(?<![\d.])\d+\.\d{6}(?![\d])")

#: Evidence labels an implemented item may never rest on: a statement nothing
#: ran, and a class this repository cannot reach.
NEVER_IMPLEMENTED_LABELS = ("documented-unexecuted", "production-experience")

#: The same denial vocabulary the security baseline applies to what a register
#: entry does not claim, kept narrow on purpose: a notClaimed sentence has to
#: deny something, not merely mention it.
DENIAL = re.compile(
    r"\b(?:no|not|never|none|nothing|nobody|cannot|may not|must not|does not|is not)\b",
    flags=re.IGNORECASE,
)

REGISTER_ID = re.compile(r"\bDR-\d{2}\b")
EXCEPTION_ID = re.compile(r"\bEX-\d{2}\b")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
MARKDOWN_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")

#: Sentences that were true when written and are not now. Each was corrected by
#: the change that published these methods; a document still carrying one would be
#: telling a reader the stalest thing it knows. Evidence records and the changelog
#: are not searched: both describe a moment that has passed.
RETIRED_PHRASES = (
    "no job in it has executed on the selected service",
    "no job in it has executed on the service",
    "if one were ever run, which it has not been",
    "no record has been produced against a real runtime",
    "two rendered rule files that nothing has loaded",
    "the scanner is not installed on the host this work was done on",
    "no logger, formatter, or sink exists",
    "no log line has ever been inspected",
    "no logger exists to check",
    "none of them runs continuously",
    "no job in the committed workflow has executed",
    "security records that still say no job has executed",
    "no scanner is configured and no cadence is set",
    "every figure is synthetic",
)
GOVERNED_DOCUMENTS = (
    "SECURITY.md",
    "CONTRIBUTING.md",
    "docs/architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md",
    "docs/architecture/decisions/ADR-0009-python-toolchain.md",
    "docs/testing/claim-test-matrix.md",
    "docs/testing/ci-gate-matrix.md",
    "docs/security/README.md",
    "docs/security/threat-model.md",
    "docs/security/control-matrix.md",
    "docs/security/deferred-risks.md",
    "docs/security/security-baseline.v1alpha1.json",
    "docs/security/security-method.md",
    "docs/security/security-method.v1alpha1.json",
    "docs/architecture/decisions/ADR-0008-v1-security-baseline.md",
    "docs/telemetry/README.md",
    "docs/telemetry/redaction.md",
    "docs/telemetry/api-instrumentation.md",
    "docs/telemetry/observability-method.md",
    "docs/telemetry/observability-method.v1alpha1.json",
    "docs/testing/ci-gate-matrix.v1alpha1.json",
    "docs/cost/README.md",
    "docs/cost/cost-method.md",
    "docs/cost/cost-method.v1alpha1.json",
    "docs/cost/cost-calculation.md",
    "docs/cost/cost-capacity-method.md",
    "docs/cost/cost-capacity-method.v1alpha1.json",
)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@cache
def method(relative: str) -> dict[str, Any]:
    return _load(REPO_ROOT / relative)


@cache
def document(relative: str) -> str:
    return (REPO_ROOT / method(relative)["documentRef"]).read_text(encoding="utf-8")


BASELINE = _load(BASELINE_PATH)
CATALOG = _load(CATALOG_PATH)
ALERTS = _load(ALERTS_PATH)
REGISTER = _load(REGISTER_PATH)
COST_RULES = _load(COST_RULES_PATH)
WORKFLOW_JOBS = frozenset(
    yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))["jobs"]
)

CONTROLS = {row["controlId"]: row for row in BASELINE["controls"]}
IMPLEMENTABLE_STATUSES = frozenset(
    row["statusId"]
    for row in BASELINE["controlStatuses"]
    if row["mayBeCalledImplemented"]
)
RISK_IDS = frozenset(row["riskId"] for row in BASELINE["deferredRisks"])
EXCEPTION_IDS = frozenset(row["exceptionId"] for row in BASELINE["exceptions"])
METRICS = {row["name"]: row for row in CATALOG["metrics"]}
ALERT_IDS = frozenset(row["alertId"] for row in ALERTS["alerts"])
CLAIMS = {row["claimId"]: row for row in REGISTER["claims"]}
#: The evidence classes the register names. Since the register moved to v1alpha2 a
#: class is no longer a property of a record; each claim carries the class its
#: v1alpha1 row gave it, in its carried classification, and that is what a method
#: item's label is compared with.
LABELS = {row["classId"]: row for row in REGISTER["evidenceClasses"]}
RULES = {row["ruleId"]: row for row in COST_RULES["prohibitions"]}
BASES = {row["basisId"]: row for row in COST_RULES["bases"]}
COST_LIMITATION_IDS = frozenset(
    row["limitationId"] for row in COST_RULES["limitations"]
)
COST_QUESTION_IDS = frozenset(row["questionId"] for row in COST_RULES["openQuestions"])


def topics(relative: str) -> list[dict[str, Any]]:
    return method(relative)["topics"]


def items(relative: str, side: str) -> list[tuple[str, dict[str, Any]]]:
    """Every item on one side of every topic, with the topic it sits in."""
    return [
        (topic["topicId"], item) for topic in topics(relative) for item in topic[side]
    ]


def all_items() -> list[tuple[str, str, str, dict[str, Any]]]:
    return [
        (relative, side, topic_id, item)
        for relative in METHODS
        for side in ("implemented", "notImplemented")
        for topic_id, item in items(relative, side)
    ]


def _item_id(row: tuple[str, str, str, dict[str, Any]]) -> str:
    relative, side, _, item = row
    return f"{Path(relative).stem}:{side}:{item['itemId']}"


IMPLEMENTED = [row for row in all_items() if row[1] == "implemented"]
NOT_IMPLEMENTED = [row for row in all_items() if row[1] == "notImplemented"]


def evidence_resolves(kind: str, ref: str) -> bool:
    if kind == "ci-gate":
        return ref in WORKFLOW_JOBS
    if kind == "test":
        path, _, function = ref.partition("::")
        source = REPO_ROOT / path
        if not function or not source.is_file():
            return False
        pattern = rf"^(?:async )?def {re.escape(function)}\("
        return (
            re.search(pattern, source.read_text(encoding="utf-8"), re.MULTILINE)
            is not None
        )
    if kind == "record":
        return ref.startswith(PROOF_ROOT) and (REPO_ROOT / ref).is_file()
    return (REPO_ROOT / ref).is_file()


def section(relative: str, heading: str) -> str:
    """The body of one '## ' section of a method document."""
    body = document(relative)
    marker = f"\n## {heading}\n"
    assert marker in body, (
        f"{method(relative)['documentRef']} has no section '## {heading}'"
    )
    rest = body.split(marker, 1)[1]
    return rest.split("\n## ", 1)[0]


def topic_identifiers(topic: dict[str, Any]) -> dict[str, set[str]]:
    """Every identifier one topic of a record names, by kind."""
    found: dict[str, set[str]] = {
        "controlIds": set(),
        "claimIds": set(),
        "registerRefs": set(),
        "exceptionIds": set(),
        "signals": set(),
        "alertIds": set(),
        "ruleIds": set(),
        "basisIds": set(),
        "limitationIds": set(),
        "questionIds": set(),
    }
    for side in ("implemented", "notImplemented"):
        for item in topic[side]:
            for field, values in found.items():
                values.update(item.get(field, []))
    return found


# --------------------------------------------------------------------------
# Identity and shape
# --------------------------------------------------------------------------


@pytest.mark.parametrize("relative", METHODS)
def test_each_method_declares_its_identity_and_contract_version(relative: str) -> None:
    record = method(relative)
    assert record["$id"] == EXPECTED_ID[relative]
    assert record["contractVersion"] == EXPECTED_CONTRACT_VERSION


@pytest.mark.parametrize("relative", METHODS)
def test_every_reference_a_method_makes_resolves(relative: str) -> None:
    record = method(relative)
    for field, value in record.items():
        if field.endswith("Ref"):
            assert (REPO_ROOT / value).is_file(), (
                f"{relative} {field} names a missing {value}"
            )


@pytest.mark.parametrize("relative", METHODS)
def test_each_method_covers_exactly_its_required_topics_in_order(relative: str) -> None:
    assert (
        tuple(topic["topicId"] for topic in topics(relative))
        == REQUIRED_TOPICS[relative]
    )


@pytest.mark.parametrize("relative", METHODS)
def test_every_topic_keeps_what_is_implemented_apart_from_what_is_not(
    relative: str,
) -> None:
    """Both lists, in every topic. A topic with nothing on the second list would be
    a topic whose gaps somebody decided not to write down."""
    for topic in topics(relative):
        assert topic["implemented"], f"{topic['topicId']} implements nothing"
        assert topic["notImplemented"], f"{topic['topicId']} states no gap"


@pytest.mark.parametrize("relative", METHODS)
def test_item_identifiers_are_unique_within_a_method(relative: str) -> None:
    ids = [
        item["itemId"]
        for side in ("implemented", "notImplemented")
        for _, item in items(relative, side)
    ]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("relative", METHODS)
def test_each_method_declares_exactly_the_evidence_kinds_it_may_use(
    relative: str,
) -> None:
    assert (
        tuple(row["kindId"] for row in method(relative)["evidenceKinds"])
        == EVIDENCE_KINDS
    )


@pytest.mark.parametrize("relative", METHODS)
def test_each_method_says_what_it_does_not_establish(relative: str) -> None:
    limitations = " ".join(method(relative)["limitations"]).lower()
    assert "moves no claim" in limitations
    assert "strong one" in limitations


# --------------------------------------------------------------------------
# Implemented items
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", IMPLEMENTED, ids=_item_id)
def test_an_implemented_item_names_a_check_and_a_record(row: tuple) -> None:
    """Every implemented item links to tests or a gate, and to evidence."""
    kinds = {entry["kind"] for entry in row[3]["evidence"]}
    assert kinds & {"test", "ci-gate"}, f"{row[3]['itemId']} names no test and no gate"
    assert "record" in kinds, f"{row[3]['itemId']} names no committed record"
    assert kinds <= set(EVIDENCE_KINDS)


@pytest.mark.parametrize("row", IMPLEMENTED, ids=_item_id)
def test_every_piece_of_evidence_an_implemented_item_names_resolves(row: tuple) -> None:
    for entry in row[3]["evidence"]:
        assert evidence_resolves(entry["kind"], entry["ref"]), (
            f"{row[3]['itemId']} names {entry['kind']} {entry['ref']!r}, which does not resolve"
        )


@pytest.mark.parametrize("row", IMPLEMENTED, ids=_item_id)
def test_an_implemented_item_rests_only_on_certified_claims(row: tuple) -> None:
    for claim_id in row[3]["claimIds"]:
        assert claim_id in CLAIMS, (
            f"{claim_id} is not in the claim and evidence register"
        )
        assert CLAIMS[claim_id]["status"] == "certified", (
            f"{row[3]['itemId']} is listed as implemented and rests on {claim_id}, "
            f"which the register holds as {CLAIMS[claim_id]['status']}"
        )


@pytest.mark.parametrize("row", IMPLEMENTED, ids=_item_id)
def test_an_implemented_item_carries_an_evidence_label_it_can_reach(row: tuple) -> None:
    label = row[3]["evidenceLabel"]
    assert label in LABELS, f"{label} is not an evidence label the register declares"
    assert label not in NEVER_IMPLEMENTED_LABELS
    assert LABELS[label]["reachedInV1"] is True
    claim_labels = {
        CLAIMS[claim_id]["legacyClassification"]["evidenceLabel"]
        for claim_id in row[3]["claimIds"]
    }
    if claim_labels:
        assert label in claim_labels, (
            f"{row[3]['itemId']} says {label} while the claims it rests on say {sorted(claim_labels)}"
        )


# --------------------------------------------------------------------------
# Not-implemented items
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", NOT_IMPLEMENTED, ids=_item_id)
def test_a_gap_is_carried_by_something_and_says_what_is_not_claimed(row: tuple) -> None:
    item = row[3]
    assert any(item.get(field) for field in ANCHOR_FIELDS), (
        f"{item['itemId']} is not carried by a control, a register entry, a claim, a gap, "
        "a signal, or an exception"
    )
    assert DENIAL.search(item["notClaimed"]), (
        f"{item['itemId']} says what is not claimed in a sentence that denies nothing"
    )
    assert "evidence" not in item, (
        "a gap cites no evidence of a property it does not have"
    )


@pytest.mark.parametrize("row", NOT_IMPLEMENTED, ids=_item_id)
def test_a_gap_never_rests_on_a_certified_claim(row: tuple) -> None:
    for claim_id in row[3]["claimIds"]:
        assert claim_id in CLAIMS, (
            f"{claim_id} is not in the claim and evidence register"
        )
        assert CLAIMS[claim_id]["status"] != "certified", (
            f"{row[3]['itemId']} lists {claim_id} as a gap and the register certifies it"
        )


@pytest.mark.parametrize("row", NOT_IMPLEMENTED, ids=_item_id)
def test_a_gap_names_only_register_entries_and_gaps_that_exist(row: tuple) -> None:
    relative, _, _, item = row
    declared_gaps = {gap["gapId"] for gap in method(relative)["gaps"]}
    for risk in item.get("registerRefs", []):
        assert risk in RISK_IDS, (
            f"{item['itemId']} names {risk}, which the baseline lacks"
        )
    for gap in item["gapIds"]:
        assert gap in declared_gaps, (
            f"{item['itemId']} names gap {gap}, which is not declared"
        )
    for exception in item.get("exceptionIds", []):
        assert exception in EXCEPTION_IDS


@pytest.mark.parametrize("relative", METHODS)
def test_every_declared_gap_is_used_and_unique(relative: str) -> None:
    declared = [gap["gapId"] for gap in method(relative)["gaps"]]
    assert len(declared) == len(set(declared))
    used = {
        gap for _, item in items(relative, "notImplemented") for gap in item["gapIds"]
    }
    assert set(declared) == used


# --------------------------------------------------------------------------
# The security method against the baseline
# --------------------------------------------------------------------------


def test_no_security_control_sits_on_the_side_its_status_denies() -> None:
    """The separation, arithmetically: the baseline's derived status decides the side."""
    for side, topic_id, item in (
        (side, topic_id, item)
        for relative, side, topic_id, item in all_items()
        if relative == SECURITY_METHOD
    ):
        for control_id in item["controlIds"]:
            assert control_id in CONTROLS, (
                f"{control_id} is not a control the baseline declares"
            )
            implementable = CONTROLS[control_id]["v1Status"] in IMPLEMENTABLE_STATUSES
            assert implementable == (side == "implemented"), (
                f"{topic_id}/{item['itemId']} lists {control_id} as {side}; the baseline derives "
                f"{CONTROLS[control_id]['v1Status']}"
            )


def test_every_security_control_appears_in_the_method() -> None:
    named = {
        control_id
        for relative, _, _, item in all_items()
        if relative == SECURITY_METHOD
        for control_id in item["controlIds"]
    }
    assert set(CONTROLS) - named == set(), "controls the method leaves out"


def test_every_deferred_risk_is_carried_in_the_deferred_risk_topic() -> None:
    topic = next(t for t in topics(SECURITY_METHOD) if t["topicId"] == "deferred-risks")
    carried = {
        risk for item in topic["notImplemented"] for risk in item["registerRefs"]
    }
    assert carried == RISK_IDS


def test_every_accepted_exception_is_carried_in_the_exception_topic() -> None:
    topic = next(t for t in topics(SECURITY_METHOD) if t["topicId"] == "exceptions")
    carried = {
        ex for item in topic["notImplemented"] for ex in item.get("exceptionIds", [])
    }
    assert carried == EXCEPTION_IDS


# --------------------------------------------------------------------------
# The observability method against the catalog and the alert record
# --------------------------------------------------------------------------


def test_no_signal_sits_on_the_side_its_emission_denies() -> None:
    for side, item in (
        (side, item)
        for relative, side, _, item in all_items()
        if relative in (OBSERVABILITY_METHOD, COST_METHOD)
    ):
        for name in item.get("signals", []):
            assert name in METRICS, f"{name} is not a metric the catalog declares"
            emitted = METRICS[name]["emission"] == "emitted"
            assert emitted == (side == "implemented"), (
                f"{item['itemId']} lists {name} as {side}; the catalog says {METRICS[name]['emission']}"
            )


def test_every_catalog_metric_appears_in_the_method() -> None:
    named = {
        name
        for relative, _, _, item in all_items()
        if relative == OBSERVABILITY_METHOD
        for name in item.get("signals", [])
    }
    assert set(METRICS) - named == set(), "metrics the method leaves out"


def test_every_alert_appears_as_implemented_and_nothing_else_does() -> None:
    named = {
        alert
        for relative, side, _, item in all_items()
        if relative == OBSERVABILITY_METHOD and side == "implemented"
        for alert in item.get("alertIds", [])
    }
    assert named == ALERT_IDS


# --------------------------------------------------------------------------
# The cost and capacity method against the cost method and its evidence
# --------------------------------------------------------------------------


def _cost_items() -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (side, topic_id, item)
        for relative, side, topic_id, item in all_items()
        if relative == COST_METHOD
    ]


def test_no_cost_rule_sits_on_the_side_its_enforcement_denies() -> None:
    """A rule the cost method says a test enforces may be implemented; a rule it
    says review alone enforces may not, whatever the prose around it says."""
    for side, topic_id, item in _cost_items():
        for rule_id in item.get("ruleIds", []):
            assert rule_id in RULES, f"{rule_id} is not a rule the cost method declares"
            tested = RULES[rule_id]["enforcement"] == "test"
            assert tested == (side == "implemented"), (
                f"{topic_id}/{item['itemId']} lists {rule_id} as {side}; the cost method "
                f"enforces it by {RULES[rule_id]['enforcement']}"
            )


def test_every_cost_rule_appears_in_the_method() -> None:
    named = {rule for _, _, item in _cost_items() for rule in item.get("ruleIds", [])}
    assert set(RULES) - named == set(), "cost rules the method leaves out"


def test_no_basis_sits_on_the_side_its_reachability_denies() -> None:
    for side, topic_id, item in _cost_items():
        for basis_id in item.get("basisIds", []):
            assert basis_id in BASES, (
                f"{basis_id} is not a basis the cost method declares"
            )
            assert BASES[basis_id]["v1Reachable"] == (side == "implemented"), (
                f"{topic_id}/{item['itemId']} lists basis {basis_id} as {side}"
            )


def test_every_basis_appears_in_the_billing_topic() -> None:
    topic = next(
        t
        for t in topics(COST_METHOD)
        if t["topicId"] == "billing-estimate-and-allocation"
    )
    named = {
        basis
        for side in ("implemented", "notImplemented")
        for item in topic[side]
        for basis in item.get("basisIds", [])
    }
    assert named == set(BASES)


def test_every_cost_limitation_and_open_question_is_carried_as_a_gap() -> None:
    """A limitation or an open question is a statement of what is not done, so it
    may only carry a not-implemented item, and none may be left out."""
    carried: dict[str, set[str]] = {"limitationIds": set(), "questionIds": set()}
    for side, topic_id, item in _cost_items():
        for field, found in carried.items():
            values = item.get(field, [])
            assert not values or side == "notImplemented", (
                f"{topic_id}/{item['itemId']} is implemented and names {field} {values}"
            )
            found.update(values)
    assert carried["limitationIds"] == COST_LIMITATION_IDS
    assert carried["questionIds"] == COST_QUESTION_IDS


def _pointer(document_value: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON pointer, including its `~1` and `~0` escapes."""
    assert pointer.startswith("/"), f"{pointer!r} is not a JSON pointer"
    value = document_value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def test_the_pointer_helper_unescapes_as_rfc_6901_says() -> None:
    sample = {"a/b": {"m~n": [10, 20]}}
    assert _pointer(sample, "/a~1b/m~0n/1") == 20


FIGURES = method(COST_METHOD)["figures"]


@pytest.mark.parametrize("figure", FIGURES, ids=lambda figure: figure["figureId"])
def test_every_figure_reads_back_from_the_file_it_names(figure: dict[str, Any]) -> None:
    """A figure is quoted from a committed result or findings file, never typed."""
    source = figure["sourceRef"]
    assert source.startswith((PROOF_ROOT, "docs/cost/")), source
    record = _load(REPO_ROOT / source)
    value = _pointer(record, figure["pointer"])
    assert value is not None, f"{figure['figureId']} points at a null"
    if "divisorPointer" in figure:
        # A quotient of two published figures, quoted to show that dividing rounded
        # figures by hand does not reproduce the figure the tool divides exactly.
        assert figure["transform"] == "quotient-at-six-places"
        divisor = _pointer(record, figure["divisorPointer"])
        written = str(
            (Decimal(value) / Decimal(divisor)).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_EVEN
            )
        )
    else:
        written = FIGURE_TRANSFORMS[figure["transform"]](value)
    assert written == figure["quoted"], (
        f"{figure['figureId']} quotes {figure['quoted']!r}; {source}{figure['pointer']} "
        f"gives {written!r}"
    )


def test_figure_identifiers_are_unique() -> None:
    ids = [figure["figureId"] for figure in FIGURES]
    assert len(ids) == len(set(ids))


def test_the_document_quotes_every_declared_figure() -> None:
    body = document(COST_METHOD)
    for figure in FIGURES:
        assert figure["quoted"] in body, f"the document omits {figure['quoted']}"


def test_the_document_quotes_no_six_place_figure_the_record_lacks() -> None:
    """The other direction: a six-place amount in the prose that no file backs is a
    number somebody typed."""
    declared = {figure["quoted"] for figure in FIGURES}
    stray = set(SIX_PLACE_FIGURE.findall(document(COST_METHOD))) - declared
    assert not stray, f"figures quoted without a source: {sorted(stray)}"


def test_the_capacity_topic_carries_the_deferred_capacity_claim() -> None:
    """The portable capacity claim is deferred in the register. The method has to say
    so where a reader looks for capacity, rather than leave the question unasked."""
    topic = next(
        t for t in topics(COST_METHOD) if t["topicId"] == "capacity-limitations"
    )
    carried = {claim for item in topic["notImplemented"] for claim in item["claimIds"]}
    assert "sustained-throughput-and-capacity-under-load" in carried
    assert (
        CLAIMS["sustained-throughput-and-capacity-under-load"]["status"] == "deferred"
    )


# --------------------------------------------------------------------------
# Documents against records
# --------------------------------------------------------------------------


@pytest.mark.parametrize("relative", METHODS)
def test_the_document_publishes_every_topic_in_order(relative: str) -> None:
    body = document(relative)
    positions = []
    for topic in topics(relative):
        marker = f"\n## {topic['heading']}\n"
        assert marker in body, f"no section '## {topic['heading']}'"
        positions.append(body.index(marker))
    assert positions == sorted(positions)


@pytest.mark.parametrize("relative", METHODS)
def test_each_section_names_every_identifier_its_topic_holds(relative: str) -> None:
    for topic in topics(relative):
        text = section(relative, topic["heading"])
        spans = set(CODE_SPAN.findall(text))
        for field, values in topic_identifiers(topic).items():
            for value in values:
                if field in ("registerRefs", "exceptionIds"):
                    assert re.search(rf"\b{value}\b", text), (
                        f"{topic['topicId']} omits {value}"
                    )
                else:
                    assert value in spans, f"{topic['topicId']} does not name `{value}`"


@pytest.mark.parametrize("relative", METHODS)
def test_no_section_names_an_identifier_its_topic_lacks(relative: str) -> None:
    """The other direction. An identifier a section mentions that its record does not
    hold is a claim nothing checks."""
    known = {
        "controlIds": set(CONTROLS),
        "claimIds": set(CLAIMS),
        "signals": set(METRICS),
        "alertIds": set(ALERT_IDS),
        "ruleIds": set(RULES),
        "limitationIds": set(COST_LIMITATION_IDS),
        "questionIds": set(COST_QUESTION_IDS),
    }
    for topic in topics(relative):
        text = section(relative, topic["heading"])
        held = topic_identifiers(topic)
        spans = set(CODE_SPAN.findall(text))
        for field, universe in known.items():
            stray = (spans & universe) - held[field]
            assert not stray, (
                f"{topic['topicId']} names {sorted(stray)} and its record does not"
            )
        stray_risks = set(REGISTER_ID.findall(text)) - held["registerRefs"]
        assert not stray_risks, (
            f"{topic['topicId']} names {sorted(stray_risks)} and its record does not"
        )
        stray_exceptions = set(EXCEPTION_ID.findall(text)) - held["exceptionIds"]
        assert not stray_exceptions, (
            f"{topic['topicId']} names {sorted(stray_exceptions)} and its record does not"
        )


@pytest.mark.parametrize("relative", METHODS)
def test_each_section_links_every_record_its_topic_rests_on(relative: str) -> None:
    doc_dir = (REPO_ROOT / method(relative)["documentRef"]).parent
    for topic in topics(relative):
        text = section(relative, topic["heading"])
        linked = {
            (doc_dir / target).resolve().relative_to(REPO_ROOT).as_posix()
            for target in MARKDOWN_LINK.findall(text)
            if not target.startswith(("http://", "https://"))
        }
        for item in topic["implemented"]:
            for entry in item["evidence"]:
                if entry["kind"] == "record":
                    assert entry["ref"] in linked, (
                        f"{topic['topicId']} does not link {entry['ref']}"
                    )


@pytest.mark.parametrize("relative", METHODS)
def test_the_document_names_every_gap_the_record_declares(relative: str) -> None:
    body = document(relative)
    for gap in method(relative)["gaps"]:
        assert f"`{gap['gapId']}`" in body, (
            f"the document does not name gap {gap['gapId']}"
        )


# --------------------------------------------------------------------------
# What the publication corrected
# --------------------------------------------------------------------------


@pytest.mark.parametrize("relative", GOVERNED_DOCUMENTS)
def test_no_governed_document_still_carries_a_retired_sentence(relative: str) -> None:
    text = " ".join((REPO_ROOT / relative).read_text(encoding="utf-8").lower().split())
    for phrase in RETIRED_PHRASES:
        assert phrase not in text, f"{relative} still says {phrase!r}"


def test_the_retired_sentences_are_searched_in_files_that_exist() -> None:
    for relative in GOVERNED_DOCUMENTS:
        assert (REPO_ROOT / relative).is_file(), relative


@pytest.mark.parametrize("relative", METHODS)
def test_every_correction_is_recorded_with_an_identifier_and_a_statement(
    relative: str,
) -> None:
    corrections = method(relative)["corrections"]
    assert corrections, "a method that corrected nothing would not need this list"
    ids = [row["correctionId"] for row in corrections]
    assert len(ids) == len(set(ids))
    for row in corrections:
        assert row["statement"].strip()
