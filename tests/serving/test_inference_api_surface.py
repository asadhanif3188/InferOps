"""Deterministic checks over the V1 inference API compatibility surface.

Every check here reads files from this repository and nothing else. No network, no
cluster, no model, no clock, no randomness, and no request is issued to anything.

What this suite establishes is that the decided surface is internally consistent and
that it agrees with the records already committed beside it: that every canonical
error code in the integration contract is either mapped to a condition or recorded as
never emitted, with a reason, so that a code can never be quietly dropped; that a row
claiming the trial observed a field names one the feasibility record carries as a JSON
member key inside a fenced block, rather than a word that happens to appear in its
prose; that every capability is declared with what supports it, and that a
capability claiming runtime observation cites the record that observed it; that the
serving contract's required endpoint roles are each covered by an in-scope endpoint or
by a stated equivalent; that a `retryable` value differing from the canonical default
is marked as an override rather than left to look like a discrepancy; that the
document and the data publish the same endpoints, codes, and capability values; and
that what the record says serves it is stated rather than assumed.

What it does not establish is that any of this works. `V1-S1-005-PR1` built the
component that answers these routes, and whether it answers them faithfully is
checked from the code in
[the implementation agreement suite](test_inference_api_implementation_agreement.py)
and exercised against the mock adapter under ``tests/api``. This suite still reads
files and nothing else: it stops the decision drifting from its own record, and it
observes no response.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVING_DIR = REPO_ROOT / "docs" / "serving"
SURFACE_PATH = SERVING_DIR / "inference-api-surface.v1alpha1.json"
DOCUMENT_PATH = SERVING_DIR / "inference-api-surface.md"
DECISION_PATH = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0010-inference-api-compatibility-surface.md"
)
FEASIBILITY_PATH = (
    REPO_ROOT / "docs" / "proof" / "serving" / "v1-s0-003-pr2-runtime-feasibility.md"
)
RUNTIME_DECISION_PATH = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0002-model-and-serving-runtime.md"
)
TELEMETRY_PATH = REPO_ROOT / "docs" / "telemetry" / "telemetry-catalog.v1alpha1.json"
STRATEGY_PATH = REPO_ROOT / "docs" / "testing" / "test-strategy.v1alpha1.json"
CONTRACTS_DIR = REPO_ROOT / "contracts"

# This suite is collected by the documentation layer of the test strategy, which has
# to name the directory it lives in or the layer selects nothing here.
DECLARING_LAYER = "documentation"
DECLARED_PATH = "tests/serving"

EXPECTED_SURFACE_ID = "https://inferops.io/serving/inference-api-surface.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# A value as the surface prints it in `seenAs`: a runtime field name or a build
# string, both of which carry an underscore or a hyphen. Ordinary prose words in the
# same sentence do not, which is what keeps this from asserting that "response" and
# "trial" appear in the record.
IDENTIFIER_LIKE = re.compile(r"[A-Za-z0-9]+[_-][A-Za-z0-9_-]+")

SURFACE = json.loads(SURFACE_PATH.read_text(encoding="utf-8"))
DOCUMENT = DOCUMENT_PATH.read_text(encoding="utf-8")
DECISION = DECISION_PATH.read_text(encoding="utf-8")
FEASIBILITY = FEASIBILITY_PATH.read_text(encoding="utf-8")
RUNTIME_DECISION = RUNTIME_DECISION_PATH.read_text(encoding="utf-8")

# The two records the surface is allowed to read the runtime's behaviour from. The
# trial log carries what came back; the runtime decision carries the endpoint
# thresholds that were registered before it ran and then met. Neither is vendor
# documentation, which is the source this surface may not cite.
RUNTIME_EVIDENCE = FEASIBILITY + RUNTIME_DECISION

# Only the fenced blocks of the feasibility record, which is where the bodies it
# captured verbatim actually live.
#
# The first version of this check searched the whole record for the field name, and
# that was too weak in a way worth recording: `data` matched the sentence "contains no
# host detail and no personal data", and `object` matched the chat completion's
# `"object":"chat.completion"` while being claimed for a different endpoint. A field
# name appearing somewhere in the prose is not evidence that a response carried it.
FENCE = re.compile(r"^```[a-z]*$(.*?)^```$", flags=re.MULTILINE | re.DOTALL)
FENCED_BLOCKS = " ".join(FENCE.findall(FEASIBILITY))
TELEMETRY = json.loads(TELEMETRY_PATH.read_text(encoding="utf-8"))
STRATEGY = json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))

ENDPOINTS = SURFACE["endpoints"]
OUT_OF_SCOPE = SURFACE["outOfScope"]
CAPABILITIES = SURFACE["capabilities"]
REQUEST_FIELDS = SURFACE["requestFields"]
RESPONSE_FIELDS = SURFACE["responseFields"]
NOT_PASSED_THROUGH = SURFACE["notPassedThrough"]
ERROR_MAPPING = SURFACE["errorMapping"]
CODES_NOT_EMITTED = SURFACE["codesNotEmitted"]

# The canonical error contract, transcribed from the integration specification with
# its retryable defaults. It is written out here rather than derived from the surface
# so that the surface has something independent to be checked against: a code the
# decision forgot has to appear as a missing key rather than as a shorter list.
CANONICAL_CODES = {
    "contract-invalid": False,
    "authentication-required": False,
    "authorization-denied": False,
    "policy-denied": False,
    "version-unsupported": False,
    "capability-unavailable": True,
    "model-not-ready": True,
    "rate-limited": True,
    "budget-exceeded": False,
    "evaluation-failed": False,
    "upstream-timeout": True,
    "request-timeout": True,
    "internal-error": True,
}

# The roles the model-serving contract requires an implementation to cover. Graceful
# shutdown is the one the contract permits an equivalent for, and the surface takes
# that permission, so it is required to appear as a stated equivalent rather than as
# an endpoint.
REQUIRED_SERVING_ROLES = {
    "liveness",
    "readiness",
    "model-and-runtime-metadata",
    "inference",
    "metrics",
}


# --------------------------------------------------------------------------
# Identity, and the claim that nothing serves this
# --------------------------------------------------------------------------


def test_the_surface_declares_its_identity_and_contract_version() -> None:
    assert SURFACE["$id"] == EXPECTED_SURFACE_ID
    assert SURFACE["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_every_reference_the_surface_names_exists() -> None:
    for key, value in SURFACE.items():
        if not key.endswith("Ref") or value is None:
            continue
        assert (REPO_ROOT / value).exists(), f"{key} -> {value}"


#: The states this record may report about itself, in the order it passes through
#: them. It began at `nothing-serves` and moved once, when `V1-S1-005-PR1` built
#: the component that answers these routes. A state outside this set is a claim
#: nobody defined.
IMPLEMENTATION_STATES = ("nothing-serves", "served-in-part", "served")


def test_the_record_states_what_serves_it_in_a_vocabulary_it_defines() -> None:
    """The one claim this record is most likely to drift into overstating."""
    status = SURFACE["implementationStatus"]
    assert status["state"] in IMPLEMENTATION_STATES, status["state"]
    assert status["meaning"].strip()
    assert status["publishedArtifacts"].startswith("none")


def test_a_served_surface_is_still_not_a_published_contract_artifact() -> None:
    """Serving a shape and publishing it are different, and D9 stays undecided.

    This is the distinction the record was built around, and it is the one that
    survives the surface being implemented: `contracts/` is where a client binds,
    and nothing was added to it.
    """
    assert "D9" in DECISION
    assert SURFACE["implementationStatus"]["publishedArtifacts"].startswith("none")


def test_no_contract_artifact_for_this_surface_was_published() -> None:
    """`contracts/` is where a client binds. The decision says it stays untouched."""
    published = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted(CONTRACTS_DIR.rglob("*"))
        if path.is_file() and "inference-api" in path.name
    ]
    assert published == [], published


def test_the_path_prefix_is_not_presented_as_an_inferops_version() -> None:
    target = SURFACE["compatibilityTarget"]
    assert target["pathPrefix"] == "/v1"
    assert "not an InferOps version claim" in target["prefixMeaning"]
    assert EXPECTED_CONTRACT_VERSION in target["prefixMeaning"]


def test_the_compatibility_shape_was_read_from_the_evidence_not_from_a_vendor() -> None:
    read_from = SURFACE["compatibilityTarget"]["shapeReadFrom"]
    assert "feasibility record" in read_from
    assert "No vendor documentation was read" in read_from


def test_the_compatibility_target_states_what_bounds_it_and_what_permits_it() -> None:
    """Both were carried as data no check read, and one of them is the decision."""
    target = SURFACE["compatibilityTarget"]
    assert SLUG.match(target["targetId"]), target["targetId"]
    assert len(target["name"]) > 20
    assert "frozen" in target["boundedBy"]
    assert "not a commitment to track" in target["boundedBy"]
    assert len(target["specificationBasis"]) > 60


def test_the_surface_says_what_it_is_and_what_it_is_for() -> None:
    assert len(SURFACE["title"]) > 20
    assert "Nothing in this repository serves any of it" in SURFACE["description"]


def test_the_telemetry_pointer_in_the_data_is_the_file_the_suite_reads() -> None:
    """Otherwise the pointer and the checked file can drift apart in silence."""
    assert (REPO_ROOT / SURFACE["telemetryRef"]) == TELEMETRY_PATH


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda row: row["endpointId"])
def test_every_endpoint_declares_every_required_field(endpoint: dict) -> None:
    required = (
        "endpointId",
        "method",
        "path",
        "origin",
        "purpose",
        "servingContractRole",
        "v1Status",
        "servedBy",
        "runtimeCounterpart",
        "runtimeCounterpartObserved",
    )
    for field in required:
        assert field in endpoint, f"{endpoint.get('endpointId')} is missing {field}"
    assert SLUG.match(endpoint["endpointId"]), endpoint["endpointId"]
    assert endpoint["path"].startswith("/"), endpoint["path"]
    assert endpoint["method"] in {"GET", "POST"}, endpoint["method"]
    assert endpoint["origin"] in {"compatibility-target", "inferops-native"}
    assert endpoint["v1Status"] == "in-scope"


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda row: row["endpointId"])
def test_every_endpoint_says_what_serves_it_and_what_is_unfinished(
    endpoint: dict,
) -> None:
    """An endpoint claiming a server names one, and one claiming none says so.

    The check that matters is not which of the two it is — it is that the row is
    a statement a reader can check rather than a blank. The suite that checks the
    statement against the code is
    ``tests/serving/test_inference_api_implementation_agreement.py``.
    """
    served_by = endpoint["servedBy"]
    assert served_by.strip(), endpoint["endpointId"]
    assert served_by.startswith(("none", "inferops.api")), endpoint["endpointId"]


def test_endpoint_identifiers_and_paths_are_unique() -> None:
    ids = [row["endpointId"] for row in ENDPOINTS]
    routes = [(row["method"], row["path"]) for row in ENDPOINTS]
    assert len(ids) == len(set(ids)), ids
    assert len(routes) == len(set(routes)), routes


def test_every_required_serving_role_is_covered() -> None:
    covered = {row["servingContractRole"] for row in ENDPOINTS}
    assert covered >= REQUIRED_SERVING_ROLES, REQUIRED_SERVING_ROLES - covered


def test_graceful_shutdown_is_recorded_as_an_equivalent_rather_than_forgotten() -> None:
    """The contract permits an equivalent. Taking that permission has to be visible."""
    rows = [row for row in OUT_OF_SCOPE if "shutdown" in row["subject"]]
    assert len(rows) == 1, [row["subject"] for row in OUT_OF_SCOPE]
    assert rows[0]["origin"] == "serving-contract"
    assert "SIGTERM" in rows[0]["reason"]


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda row: row["endpointId"])
def test_an_endpoint_claiming_an_observed_counterpart_names_one(endpoint: dict) -> None:
    """The flag and the name have to agree in both directions.

    An earlier version excused `/metrics` from the unobserved branch. That branch was
    unreachable, because `/metrics` is marked observed - and had the flag ever been
    flipped, the exemption would have excused precisely the claim this check exists to
    refuse. A special case with no case is worse than no check.
    """
    if endpoint["runtimeCounterpartObserved"]:
        assert endpoint["runtimeCounterpart"], endpoint["endpointId"]
    else:
        assert endpoint["runtimeCounterpart"] is None, endpoint["endpointId"]


@pytest.mark.parametrize(
    "endpoint",
    [row for row in ENDPOINTS if row["runtimeCounterpartObserved"]],
    ids=lambda row: row["endpointId"],
)
def test_an_observed_runtime_counterpart_appears_in_the_record(endpoint: dict) -> None:
    """A counterpart claimed observed has to be findable in what was observed.

    This is the check that stops the surface citing a runtime endpoint that only
    vendor documentation says exists. The two records the trial produced and the
    decision it settled are the whole of the permitted source.
    """
    path = endpoint["runtimeCounterpart"].split()[-1]
    assert path in RUNTIME_EVIDENCE, (
        f"{endpoint['endpointId']} claims the trial observed {path}, and neither "
        "the feasibility record nor the runtime decision mentions it"
    )


@pytest.mark.parametrize("row", OUT_OF_SCOPE, ids=lambda row: row["subject"][:40])
def test_every_out_of_scope_entry_states_a_reason(row: dict) -> None:
    assert row["subject"].strip(), row
    assert row["origin"] in {
        "compatibility-target",
        "serving-contract",
        "serving-runtime",
    }, row["origin"]
    assert len(row["reason"]) > 40, row["subject"]


def test_the_runtime_surface_is_not_proxied() -> None:
    rows = [row for row in OUT_OF_SCOPE if row["origin"] == "serving-runtime"]
    assert rows, "no row records what happens to the runtime's own paths"
    assert any("not proxied" in row["reason"] for row in rows)


# --------------------------------------------------------------------------
# Capabilities: declared, with what supports them
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", CAPABILITIES, ids=lambda row: row["capabilityId"])
def test_every_capability_declares_every_required_field(row: dict) -> None:
    required = (
        "capabilityId",
        "question",
        "v1Value",
        "declaredAt",
        "requestField",
        "onUnsupportedRequest",
        "evidenceRef",
        "basis",
        "runtimeObserved",
        "runtimeNote",
    )
    for field in required:
        assert field in row, f"{row.get('capabilityId')} is missing {field}"
    assert SLUG.match(row["capabilityId"]), row["capabilityId"]
    assert isinstance(row["v1Value"], bool), row["capabilityId"]
    assert row["declaredAt"].startswith("GET /v1/models"), row["capabilityId"]
    assert len(row["basis"]) > 40, row["capabilityId"]


@pytest.mark.parametrize("row", CAPABILITIES, ids=lambda row: row["capabilityId"])
def test_a_capability_claiming_runtime_observation_cites_the_record(row: dict) -> None:
    """A capability is a declaration. What it rests on decides how it may be read."""
    if row["runtimeObserved"]:
        assert row["evidenceRef"], row["capabilityId"]
        assert (REPO_ROOT / row["evidenceRef"]).exists(), row["evidenceRef"]
    else:
        assert row["evidenceRef"] is None, (
            f"{row['capabilityId']} was not observed at runtime and cites evidence"
        )


@pytest.mark.parametrize("row", CAPABILITIES, ids=lambda row: row["capabilityId"])
def test_an_unsupported_capability_names_the_code_it_refuses_with(row: dict) -> None:
    if row["v1Value"] or row["requestField"] is None:
        return
    assert row["onUnsupportedRequest"] in CANONICAL_CODES, row["capabilityId"]


def test_streaming_is_declared_false_and_asserts_nothing_about_the_runtime() -> None:
    row = next(r for r in CAPABILITIES if r["capabilityId"] == "streaming")
    assert row["v1Value"] is False
    assert row["runtimeObserved"] is False
    assert "not exercised" in row["runtimeNote"]
    assert "asserts nothing" in row["runtimeNote"]


def test_streaming_agrees_with_the_deferral_already_recorded_in_telemetry() -> None:
    """Two records saying different things about streaming is the failure here."""
    metric = next(
        m
        for m in TELEMETRY["metrics"]
        if m["name"] == "inferops_inference_time_to_first_token_seconds"
    )
    assert metric["v1Status"] == "deferred"
    assert "no streaming path" in metric["deferralReason"]
    streaming = next(r for r in CAPABILITIES if r["capabilityId"] == "streaming")
    assert streaming["v1Value"] is False


def test_token_usage_is_supported_by_the_recorded_response() -> None:
    row = next(r for r in CAPABILITIES if r["capabilityId"] == "token-usage")
    assert row["v1Value"] is True
    assert row["runtimeObserved"] is True
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        assert field in FEASIBILITY, field
    assert "never estimated" in row["runtimeNote"]


def test_usage_is_null_rather_than_estimated_or_zero_filled() -> None:
    row = next(r for r in RESPONSE_FIELDS if r["field"] == "usage")
    assert "null" in row["v1Behaviour"]
    assert "Never estimated" in row["v1Behaviour"]
    assert "zero-filled" in row["v1Behaviour"]


# --------------------------------------------------------------------------
# Request and response shapes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "row", REQUEST_FIELDS, ids=lambda row: f"{row['endpointId']}.{row['field']}"
)
def test_every_request_field_declares_every_required_field(row: dict) -> None:
    for field in ("endpointId", "field", "type", "required", "v1Behaviour"):
        assert field in row, f"{row.get('field')} is missing {field}"
    assert isinstance(row["required"], bool)
    assert isinstance(row["observedInTrial"], bool)


@pytest.mark.parametrize(
    "row",
    REQUEST_FIELDS + RESPONSE_FIELDS,
    ids=lambda row: f"{row['endpointId']}.{row['field']}",
)
def test_every_shape_row_belongs_to_an_in_scope_endpoint(row: dict) -> None:
    known = {endpoint["endpointId"] for endpoint in ENDPOINTS}
    assert row["endpointId"] in known, row


@pytest.mark.parametrize(
    "row",
    [r for r in REQUEST_FIELDS + RESPONSE_FIELDS if r["observedInTrial"]],
    ids=lambda row: f"{row['endpointId']}.{row['field']}",
)
def test_a_field_claimed_observed_appears_in_the_feasibility_record(row: dict) -> None:
    """The distinction the whole record rests on, made checkable.

    A field marked observed was read from a body the trial captured. A field marked
    unobserved is a specification. Only the first kind may name the record, and it has
    to appear as a JSON member key inside a fenced block rather than as a word
    somewhere in the surrounding prose.
    """
    assert f'"{row["field"]}"' in FENCED_BLOCKS, (
        f"{row['endpointId']}.{row['field']} claims the trial observed it, and no "
        "fenced block in the feasibility record carries it as a member key"
    )


def test_no_field_of_the_models_endpoint_is_claimed_observed() -> None:
    """The endpoint was called. Its response envelope was never captured.

    The trial printed the runtime's own model metadata as text for this endpoint, not
    a list envelope, so `object`, `data`, and everything under them are specifications.
    Marking them observed because the endpoint was reached is the slippage the
    observed column exists to catch, and it is pinned here because it happened once.
    """
    for row in RESPONSE_FIELDS:
        if row["endpointId"] != "models-list":
            continue
        assert row["observedInTrial"] is False, row["field"]
    endpoint = next(row for row in ENDPOINTS if row["endpointId"] == "models-list")
    assert endpoint["runtimeCounterpartObserved"] is True
    assert endpoint["responseShapeObserved"] is False
    assert len(endpoint["responseShapeNote"]) > 40


def test_the_observation_check_reads_something() -> None:
    """A regex that matches nothing turns every check built on it into a pass.

    This is the guard for the check above rather than a check on the surface: if the
    feasibility record's fencing changes and the pattern stops matching, every field
    claiming observation would be verified against an empty string and would pass.
    """
    assert len(FENCED_BLOCKS) > 1000, len(FENCED_BLOCKS)
    assert '"usage"' in FENCED_BLOCKS
    assert '"data"' not in FENCED_BLOCKS, (
        "the record now carries a `data` member key, and the /v1/models envelope "
        "rows have to be re-examined rather than left marked unobserved"
    )


def test_the_extension_member_is_never_claimed_observed() -> None:
    for row in REQUEST_FIELDS + RESPONSE_FIELDS:
        if row["field"] == SURFACE["extensionNamespace"]["bodyMember"]:
            assert row["observedInTrial"] is False, row


def test_the_unknown_field_policy_is_declared_with_its_cost() -> None:
    policy = SURFACE["unknownFieldPolicy"]
    assert policy["policy"] == "refuse"
    assert policy["code"] in CANONICAL_CODES
    for field in ("meaning", "rationale", "cost", "rejectedAlternative"):
        assert len(policy[field]) > 40, field


@pytest.mark.parametrize("row", NOT_PASSED_THROUGH, ids=lambda row: row["field"])
def test_a_dropped_runtime_field_was_actually_seen(row: dict) -> None:
    assert f'"{row["field"]}"' in FENCED_BLOCKS, row["field"]
    assert len(row["reason"]) > 40, row["field"]


@pytest.mark.parametrize("row", NOT_PASSED_THROUGH, ids=lambda row: row["field"])
def test_the_values_a_dropped_field_was_seen_as_are_in_the_record(row: dict) -> None:
    """These values are republished to a reader, so they are claims like any other.

    `seenAs` is the only place this surface prints something the runtime actually
    returned. It was carried as data nothing read, which is how a value drifts from
    the record it came from without anyone noticing.
    """
    tokens = IDENTIFIER_LIKE.findall(row["seenAs"])
    assert tokens, f"{row['field']} names no value it was seen as"
    for token in tokens:
        assert token in FEASIBILITY, f"{row['field']} was seen as {token}, nowhere"


def test_no_dropped_field_is_also_a_response_field() -> None:
    emitted = {row["field"] for row in RESPONSE_FIELDS}
    dropped = {row["field"] for row in NOT_PASSED_THROUGH}
    assert not (emitted & dropped), emitted & dropped


# --------------------------------------------------------------------------
# The extension namespace
# --------------------------------------------------------------------------


def test_the_extension_namespace_names_both_halves_and_keeps_them_apart() -> None:
    namespace = SURFACE["extensionNamespace"]
    assert namespace["bodyMember"] == "x_inferops"
    assert namespace["headerPrefix"] == "X-InferOps-"
    assert namespace["bodyMember"] != namespace["headerPrefix"]
    assert len(namespace["bodyMemberMeaning"]) > 40
    assert len(namespace["headerPrefixMeaning"]) > 40


def test_no_request_body_extension_member_is_defined_and_the_reason_is_stated() -> None:
    namespace = SURFACE["extensionNamespace"]
    assert namespace["requestExtensionDefined"] is False
    assert len(namespace["requestExtensionReason"]) > 40


def test_the_extension_member_is_used_by_at_least_one_response() -> None:
    member = SURFACE["extensionNamespace"]["bodyMember"]
    assert any(row["field"] == member for row in RESPONSE_FIELDS), member


def test_the_response_extension_carries_the_adapter_kind() -> None:
    """Which adapter served a response decides what the response may claim."""
    member = SURFACE["extensionNamespace"]["bodyMember"]
    rows = [row for row in RESPONSE_FIELDS if row["field"] == member]
    assert rows
    assert any("adapterKind" in row["v1Behaviour"] for row in rows)


# --------------------------------------------------------------------------
# Errors: every canonical code accounted for, exactly once
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", ERROR_MAPPING, ids=lambda row: row["conditionId"])
def test_every_error_row_declares_every_required_field(row: dict) -> None:
    required = (
        "conditionId",
        "condition",
        "observedInTrial",
        "observation",
        "code",
        "retryable",
        "retryableOverride",
    )
    for field in required:
        assert field in row, f"{row.get('conditionId')} is missing {field}"
    assert SLUG.match(row["conditionId"]), row["conditionId"]
    assert row["code"] in CANONICAL_CODES, row["code"]
    assert isinstance(row["retryable"], bool)
    assert isinstance(row["retryableOverride"], bool)


def test_every_canonical_code_is_either_mapped_or_recorded_as_not_emitted() -> None:
    """The check that stops a code being dropped by being forgotten."""
    mapped = {row["code"] for row in ERROR_MAPPING}
    refused = {row["code"] for row in CODES_NOT_EMITTED}
    accounted = mapped | refused
    missing = set(CANONICAL_CODES) - accounted
    assert not missing, f"canonical codes accounted for nowhere: {sorted(missing)}"


def test_no_code_is_both_mapped_and_recorded_as_not_emitted() -> None:
    mapped = {row["code"] for row in ERROR_MAPPING}
    refused = {row["code"] for row in CODES_NOT_EMITTED}
    assert not (mapped & refused), sorted(mapped & refused)


@pytest.mark.parametrize("row", CODES_NOT_EMITTED, ids=lambda row: row["code"])
def test_a_code_that_is_never_emitted_says_why(row: dict) -> None:
    assert row["code"] in CANONICAL_CODES, row["code"]
    assert len(row["reason"]) > 40, row["code"]


@pytest.mark.parametrize("row", ERROR_MAPPING, ids=lambda row: row["conditionId"])
def test_a_retryable_value_matches_the_default_or_is_marked_an_override(
    row: dict,
) -> None:
    """A difference from the canonical default is an argument, not a discrepancy."""
    default = CANONICAL_CODES[row["code"]]
    if row["retryable"] == default:
        assert not row["retryableOverride"], (
            f"{row['conditionId']} marks an override and agrees with the default"
        )
    else:
        assert row["retryableOverride"], (
            f"{row['conditionId']} differs from the canonical default for "
            f"{row['code']} and does not mark itself an override"
        )


def test_the_one_override_is_the_streaming_refusal() -> None:
    overrides = [row for row in ERROR_MAPPING if row["retryableOverride"]]
    assert [row["conditionId"] for row in overrides] == ["streaming-requested"]
    assert overrides[0]["retryable"] is False


@pytest.mark.parametrize("row", ERROR_MAPPING, ids=lambda row: row["conditionId"])
def test_an_error_row_claiming_observation_carries_one(row: dict) -> None:
    if row["observedInTrial"]:
        assert row["observation"], row["conditionId"]
    else:
        assert row["observation"] is None, (
            f"{row['conditionId']} was not observed and carries an observation"
        )


def test_exactly_one_error_condition_was_observed_and_it_is_the_recorded_503() -> None:
    """Eight of nine rows are specifications, and the record must keep saying so."""
    observed = [row for row in ERROR_MAPPING if row["observedInTrial"]]
    assert [row["conditionId"] for row in observed] == ["model-loading"]
    assert "503" in observed[0]["observation"]
    assert "503" in FEASIBILITY


def test_error_condition_identifiers_are_unique() -> None:
    ids = [row["conditionId"] for row in ERROR_MAPPING]
    assert len(ids) == len(set(ids)), ids


# --------------------------------------------------------------------------
# The request counter the runtime does not have
# --------------------------------------------------------------------------


def test_the_request_counter_gap_is_recorded_with_the_series_that_do_not_close_it() -> (
    None
):
    counting = SURFACE["requestCounting"]
    assert "no cumulative request counter" in counting["runtimeGap"]
    assert "T7" in counting["runtimeGap"]
    assert counting["runtimeSeriesPresent"] == [
        "llamacpp:requests_processing",
        "llamacpp:requests_deferred",
    ]
    assert "gauge" in counting["whyThoseDoNotClose"]


@pytest.mark.parametrize(
    "series",
    ["llamacpp:requests_processing", "llamacpp:requests_deferred"],
)
def test_the_named_runtime_series_appear_in_the_record_that_measured_them(
    series: str,
) -> None:
    assert series in FEASIBILITY, series


def test_the_request_counter_this_surface_owns_already_exists_in_the_catalog() -> None:
    """This record binds two catalog entries to this surface. It adds no metric."""
    counting = SURFACE["requestCounting"]
    names = {metric["name"] for metric in TELEMETRY["metrics"]}
    assert counting["metric"] in names, counting["metric"]
    assert counting["errorMetric"] in names, counting["errorMetric"]
    assert "adds no metric" in counting["decidedElsewhere"]
    assert "InferOps" in counting["platformObligation"]
    assert set(counting) == {
        "runtimeGap",
        "runtimeSeriesPresent",
        "whyThoseDoNotClose",
        "platformObligation",
        "metric",
        "errorMetric",
        "decidedElsewhere",
    }, sorted(counting)


def test_the_error_metric_is_labelled_by_the_code_this_mapping_produces() -> None:
    """A mapping nothing can be grouped by is a mapping nobody can observe."""
    counting = SURFACE["requestCounting"]
    metric = next(
        m for m in TELEMETRY["metrics"] if m["name"] == counting["errorMetric"]
    )
    assert "error-code" in metric["labels"], metric["labels"]


# --------------------------------------------------------------------------
# What this decides about the adapter interface
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "row", SURFACE["adapterConsequences"], ids=lambda row: row["consequenceId"]
)
def test_every_adapter_consequence_states_a_reason(row: dict) -> None:
    assert SLUG.match(row["consequenceId"]), row["consequenceId"]
    assert len(row["statement"]) > 40, row["consequenceId"]
    assert len(row["why"]) > 40, row["consequenceId"]


def test_the_adapter_interface_is_kept_runtime_neutral() -> None:
    """The consequence that protects the domain boundary from the borrowed shape."""
    row = next(
        r
        for r in SURFACE["adapterConsequences"]
        if r["consequenceId"] == "translation-at-the-edge"
    )
    assert "runtime-neutral" in row["statement"]
    assert "API layer" in row["statement"]


def test_the_adapter_signature_agrees_with_the_streaming_decision() -> None:
    row = next(
        r
        for r in SURFACE["adapterConsequences"]
        if r["consequenceId"] == "synchronous-signature"
    )
    streaming = next(r for r in CAPABILITIES if r["capabilityId"] == "streaming")
    assert streaming["v1Value"] is False
    assert "non-streaming" in row["statement"]


def test_something_is_recorded_as_not_decided_here() -> None:
    assert len(SURFACE["notDecidedHere"]) >= 4
    for entry in SURFACE["notDecidedHere"]:
        assert len(entry) > 30, entry


# --------------------------------------------------------------------------
# The document and the decision publish the same surface
# --------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda row: row["endpointId"])
def test_the_document_publishes_every_in_scope_endpoint(endpoint: dict) -> None:
    assert f"`{endpoint['path']}`" in DOCUMENT, endpoint["path"]


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda row: row["endpointId"])
def test_the_decision_publishes_every_in_scope_endpoint(endpoint: dict) -> None:
    assert f"`{endpoint['path']}`" in DECISION, endpoint["path"]


@pytest.mark.parametrize("row", CODES_NOT_EMITTED, ids=lambda row: row["code"])
def test_both_documents_list_every_code_that_is_never_emitted(row: dict) -> None:
    assert f"`{row['code']}`" in DOCUMENT, row["code"]
    assert f"`{row['code']}`" in DECISION, row["code"]


@pytest.mark.parametrize("row", ERROR_MAPPING, ids=lambda row: row["conditionId"])
def test_both_documents_list_every_mapped_code(row: dict) -> None:
    assert f"`{row['code']}`" in DOCUMENT, row["code"]
    assert f"`{row['code']}`" in DECISION, row["code"]


@pytest.mark.parametrize("row", CAPABILITIES, ids=lambda row: row["capabilityId"])
def test_every_capability_is_published_and_decided(row: dict) -> None:
    """A published capability with no decision behind it is a flag nobody stands for.

    The document is checked because a reader needs the member name a response carries,
    not the internal slug. The decision is checked because two capabilities were once
    published here and named nowhere in the record that is supposed to have decided
    them, and nothing caught it.
    """
    member = row["declaredAt"].rsplit(".", 1)[-1]
    path = row["declaredAt"].split(", ", 1)[-1]
    assert f"`{member}`" in DOCUMENT, f"{member} is not published to a reader"
    assert path in DECISION, f"{path} is published and never decided"


def test_the_document_and_the_decision_both_refuse_to_claim_a_published_contract() -> (
    None
):
    """Neither may claim an artifact a client can bind to, served or not.

    The decision record is dated and is not rewritten when the thing it decided
    gets built, so it still says the API did not exist when it was written. The
    document beside it describes the surface as it stands. What both have to keep
    saying is the part that has not changed: no OpenAPI document is published.
    """
    for body, name in ((DOCUMENT, DOCUMENT_PATH.name), (DECISION, DECISION_PATH.name)):
        assert "No OpenAPI document" in body or "no OpenAPI document" in body, name
    assert "does not exist" in DECISION, DECISION_PATH.name


def test_the_decision_carries_the_sections_a_record_here_is_required_to_carry() -> None:
    for heading in (
        "## Decision status",
        "## Context",
        "## Decision",
        "## Consequences",
        "## Compatibility impact",
        "## Security considerations",
        "## Evidence",
    ):
        assert heading in DECISION, f"{DECISION_PATH.name} is missing {heading}"


def test_the_decision_and_the_data_name_each_other() -> None:
    assert SURFACE_PATH.name in DECISION
    assert DOCUMENT_PATH.name in DECISION
    assert SURFACE["decisionRef"].endswith(DECISION_PATH.name)
    assert SURFACE["documentRef"].endswith(DOCUMENT_PATH.name)


# --------------------------------------------------------------------------
# This suite is reachable by the lane that claims to run it
# --------------------------------------------------------------------------


def test_the_declaring_layer_names_the_directory_this_suite_lives_in() -> None:
    """A suite no layer names is a suite no lane runs."""
    layer = next(row for row in STRATEGY["layers"] if row["layerId"] == DECLARING_LAYER)
    assert DECLARED_PATH in layer["paths"], layer["paths"]
    assert f"pytestmark = pytest.mark.{layer['marker']}" in Path(__file__).read_text(
        encoding="utf-8"
    )
