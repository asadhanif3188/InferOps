"""The API this repository serves, against the record that decided its shape.

[The surface suite beside this one](test_inference_api_surface.py) checks the
accepted record against itself and against the documents describing it. This one
checks the record against the **code that now implements it**, in both
directions:

- every endpoint the record puts in scope is a route the application registers,
  and every route it registers is an endpoint the record puts in scope;
- every request member, message role, response literal, capability identifier,
  extension member, and dropped runtime field the code names is the one the
  record publishes;
- what the record says is served, and by what, is what is actually there.

That last one is the reason this file exists. Before this change the record's
answer was "nothing serves it", and a suite checked exactly that. The answer is
now different for four endpoints and partly different for the fifth, and a claim
about what serves an API is the claim most worth checking from the source rather
than from a sentence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inferops.api import errors, selection, surface
from inferops.domain.serving import ACCEPTED_ADAPTER_KINDS

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
SURFACE_PATH = REPO_ROOT / "docs/serving/inference-api-surface.v1alpha1.json"
SURFACE = json.loads(SURFACE_PATH.read_text(encoding="utf-8"))

ENDPOINTS = [row for row in SURFACE["endpoints"] if row["v1Status"] == "in-scope"]
REQUEST_FIELDS = [
    row for row in SURFACE["requestFields"] if row["endpointId"] == "chat-completions"
]
CAPABILITIES = SURFACE["capabilities"]


# --------------------------------------------------------------------------
# The routes
# --------------------------------------------------------------------------


def test_the_application_registers_exactly_the_endpoints_in_scope() -> None:
    registered = {(row.method, row.path) for row in surface.ROUTES}
    decided = {(row["method"], row["path"]) for row in ENDPOINTS}
    assert registered == decided, {
        "registered and not decided": sorted(registered - decided),
        "decided and not registered": sorted(decided - registered),
    }


def test_every_route_carries_the_endpoint_identifier_the_record_publishes() -> None:
    registered = {row.endpoint_id for row in surface.ROUTES}
    decided = {row["endpointId"] for row in ENDPOINTS}
    assert registered == decided


@pytest.mark.parametrize("subject", [row["subject"] for row in SURFACE["outOfScope"]])
def test_no_out_of_scope_path_is_registered(subject: str) -> None:
    """Including every runtime-native path: the runtime's surface is not proxied."""
    paths = {row.path for row in surface.ROUTES}
    for candidate in subject.replace(",", " ").split():
        if candidate.startswith("/"):
            assert candidate not in paths, candidate


# --------------------------------------------------------------------------
# The shapes
# --------------------------------------------------------------------------


def test_the_accepted_request_subset_is_the_one_the_record_publishes() -> None:
    assert {row["field"] for row in REQUEST_FIELDS} == surface.ACCEPTED_REQUEST_FIELDS


def test_the_required_request_members_are_the_ones_the_record_marks_required() -> None:
    required = {row["field"] for row in REQUEST_FIELDS if row["required"]}
    assert required == surface.REQUIRED_REQUEST_FIELDS


def test_the_accepted_roles_are_the_ones_the_record_publishes() -> None:
    behaviour = next(
        row["v1Behaviour"] for row in REQUEST_FIELDS if row["field"] == "messages"
    )
    for role in surface.ACCEPTED_MESSAGE_ROLES:
        assert role in behaviour, role


def test_the_extension_namespace_is_the_one_the_record_publishes() -> None:
    namespace = SURFACE["extensionNamespace"]
    assert namespace["bodyMember"] == surface.EXTENSION_MEMBER
    assert namespace["headerPrefix"] == surface.HEADER_PREFIX
    assert surface.REQUEST_ID_HEADER.startswith(surface.HEADER_PREFIX)
    assert surface.CORRELATION_ID_HEADER.startswith(surface.HEADER_PREFIX)


def test_no_request_body_extension_member_is_read() -> None:
    """The record defines none, so accepting one would be accepting an unknown."""
    assert SURFACE["extensionNamespace"]["requestExtensionDefined"] is False
    assert surface.EXTENSION_MEMBER not in surface.ACCEPTED_REQUEST_FIELDS


def test_the_completion_extension_members_are_the_ones_the_record_lists() -> None:
    behaviour = next(
        row["v1Behaviour"]
        for row in SURFACE["responseFields"]
        if row["endpointId"] == "chat-completions" and row["field"] == "x_inferops"
    )
    for member in surface.COMPLETION_EXTENSION_FIELDS:
        assert member in behaviour, member


def test_the_contract_version_is_the_records_own() -> None:
    assert SURFACE["contractVersion"] == surface.CONTRACT_VERSION


def test_the_path_prefix_is_the_compatibility_targets_and_is_not_the_version() -> None:
    assert SURFACE["compatibilityTarget"]["pathPrefix"] == surface.PATH_PREFIX
    assert surface.PATH_PREFIX != surface.CONTRACT_VERSION


def test_the_dropped_runtime_fields_are_the_ones_the_record_drops() -> None:
    assert set(surface.NOT_PASSED_THROUGH) == {
        row["field"] for row in SURFACE["notPassedThrough"]
    }


def test_the_published_capability_identifiers_are_the_records_own() -> None:
    """The record publishes each one at a named member of ``x_inferops``."""
    published = {row["declaredAt"].rsplit(".", 1)[-1] for row in CAPABILITIES}
    assert published == {
        surface.CAPABILITY_STREAMING,
        surface.CAPABILITY_TOKEN_USAGE,
        surface.CAPABILITY_DETERMINISTIC_SAMPLING,
        surface.CAPABILITY_MULTI_MODEL,
    }


def test_only_capabilities_an_adapter_declares_are_read_from_an_adapter() -> None:
    """The two the frozen adapter interface has no declaration for are not faked.

    ``deterministicSampling`` and ``multiModel`` are absent from the mapping on
    purpose: an entry here would mean the API reads a declaration that does not
    exist, and the honest publication of a question nothing answers is an
    absence rather than someone else's measurement.
    """
    assert set(surface.ADAPTER_CAPABILITY_FOR) == {
        surface.CAPABILITY_STREAMING,
        surface.CAPABILITY_TOKEN_USAGE,
    }


# --------------------------------------------------------------------------
# What the record says is served
# --------------------------------------------------------------------------


def test_the_record_no_longer_claims_that_nothing_serves_it() -> None:
    status = SURFACE["implementationStatus"]
    assert status["state"] == "served"
    assert status["meaning"].strip()


def test_every_in_scope_endpoint_names_what_serves_it() -> None:
    for row in ENDPOINTS:
        assert row["servedBy"].startswith("inferops.api"), row["endpointId"]


def test_the_snapshot_is_designated_without_adding_a_contracts_artifact() -> None:
    """The tested JSON snapshot is canonical; `contracts/` stays untouched."""
    published = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted((REPO_ROOT / "contracts").rglob("*"))
        if path.is_file() and "inference-api" in path.name
    ]
    assert published == []
    publication = SURFACE["implementationStatus"]["publishedArtifacts"]
    assert "canonical, versioned, tested API snapshot" in publication


def test_the_references_the_module_names_exist() -> None:
    for ref in (
        surface.SURFACE_DECISION_REF,
        surface.SURFACE_DATA_REF,
        surface.SURFACE_DOCUMENT_REF,
    ):
        assert (REPO_ROOT / ref).is_file(), ref


# --------------------------------------------------------------------------
# The error contract
# --------------------------------------------------------------------------

ERROR_MAPPING = SURFACE["errorMapping"]
CONDITION_BY_ID = {row.condition_id: row for row in errors.CONDITIONS}


@pytest.mark.parametrize(
    "row", ERROR_MAPPING, ids=[row["conditionId"] for row in ERROR_MAPPING]
)
def test_every_condition_the_record_maps_is_a_condition_this_api_refuses_on(
    row: dict[str, object],
) -> None:
    """Nine rows, each one this API can produce or answer.

    Before this change the API could reach six of them; the three the record
    reserved for an API layer — a request outside the subset, a streaming
    request, and an unsupported version — are reachable now.
    """
    assert row["conditionId"] in CONDITION_BY_ID


@pytest.mark.parametrize(
    "row", ERROR_MAPPING, ids=[row["conditionId"] for row in ERROR_MAPPING]
)
def test_every_copied_condition_carries_the_code_the_record_publishes(
    row: dict[str, object],
) -> None:
    condition = CONDITION_BY_ID[str(row["conditionId"])]
    assert condition.code == row["code"]
    assert condition.in_accepted_record is True


@pytest.mark.parametrize(
    "row", ERROR_MAPPING, ids=[row["conditionId"] for row in ERROR_MAPPING]
)
def test_every_copied_condition_carries_the_retryable_the_record_publishes(
    row: dict[str, object],
) -> None:
    """Including the one override, which the record marks as an override."""
    condition = CONDITION_BY_ID[str(row["conditionId"])]
    assert condition.retryable is row["retryable"]
    assert condition.retryable_override is row["retryableOverride"]


def test_a_condition_this_api_added_says_so() -> None:
    """A row the record does not publish is marked as added rather than copied.

    The record maps request and runtime conditions and covers neither routing,
    nor a body above this deployment's bound, nor a deployment that has stopped
    accepting work. Those are this API's, and telling a copied row from an added
    one is what stops the second being read as a decision somebody accepted.
    """
    added = {
        row.condition_id for row in errors.CONDITIONS if not row.in_accepted_record
    }
    published = {str(row["conditionId"]) for row in ERROR_MAPPING}

    assert added
    assert added & published == set()


def test_every_code_this_api_can_answer_with_is_a_canonical_one() -> None:
    """Including the codes the record lists as not emitted, which are mapped
    rather than originated: a backend reporting its own limit is answered as what
    it is, and InferOps enforces none."""
    emitted = {row["code"] for row in ERROR_MAPPING}
    not_emitted = {row["code"] for row in SURFACE["codesNotEmitted"]}
    canonical = emitted | not_emitted

    assert {row.code for row in errors.CONDITIONS} <= canonical


def test_inferops_originates_no_rate_limit_refusal() -> None:
    """`rate-limited` is reachable only by an adapter raising it.

    The accepted record lists the code among those V1 does not emit, and its
    reason — V1 has no rate limiter — stays true: no refusal site in this API
    names this condition, and the only path to it is the adapter-code mapping.
    """
    originated = [
        row.condition_id
        for row in errors.CONDITIONS
        if row.code == "rate-limited" and row.in_accepted_record
    ]
    assert originated == []
    assert (
        errors.CONDITION_FOR_ADAPTER_CODE["rate-limited"] is errors.ADAPTER_RATE_LIMITED
    )


def test_the_error_body_carries_the_members_the_record_describes() -> None:
    described = next(
        row["v1Behaviour"]
        for row in SURFACE["responseFields"]
        if row["endpointId"] == "chat-completions" and row["field"] == "x_inferops"
    )
    # The two identifiers are the same two the extension member carries, which is
    # why the error body reuses their names rather than inventing a second pair.
    assert surface.EXTENSION_REQUEST_ID in described
    assert surface.EXTENSION_CORRELATION_ID in described
    assert set(surface.ERROR_BODY_FIELDS) == {
        surface.ERROR_CODE,
        surface.ERROR_MESSAGE,
        surface.EXTENSION_REQUEST_ID,
        surface.EXTENSION_CORRELATION_ID,
        surface.ERROR_RETRYABLE,
        surface.ERROR_RETRY_AFTER_MS,
        surface.ERROR_DETAILS,
    }


# --------------------------------------------------------------------------
# Adapter selection
# --------------------------------------------------------------------------


def test_the_selectable_adapters_are_the_domains_closed_vocabulary() -> None:
    """A third selection cannot be introduced without the domain admitting a
    third adapter kind, which is what makes `adapterKind` on a response mean
    something."""
    assert set(selection.ACCEPTED_ADAPTERS) == ACCEPTED_ADAPTER_KINDS
    assert set(selection.ADAPTER_KIND_FOR.values()) == ACCEPTED_ADAPTER_KINDS


def test_no_selection_value_is_a_default() -> None:
    """The variable is in the required list and in no optional one."""
    assert selection.ENV_ADAPTER in selection.REQUIRED_ENVIRONMENT_VARIABLES
    assert selection.ENV_ADAPTER not in selection.OPTIONAL_ENVIRONMENT_VARIABLES


def test_the_record_no_longer_says_the_error_body_is_a_subset() -> None:
    """The one sentence in the accepted record this change is allowed to move."""
    meaning = SURFACE["implementationStatus"]["meaning"]
    assert "canonical error body is served in a subset" not in meaning
