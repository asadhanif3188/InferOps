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

from inferops.api import surface

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
    assert status["state"] == "served-in-part"
    assert status["meaning"].strip()


def test_every_in_scope_endpoint_names_what_serves_it() -> None:
    for row in ENDPOINTS:
        assert row["servedBy"].startswith("inferops.api"), row["endpointId"]


def test_no_contract_artifact_for_this_surface_was_published() -> None:
    """Serving a shape is not publishing it. `contracts/` is still untouched."""
    published = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted((REPO_ROOT / "contracts").rglob("*"))
        if path.is_file() and "inference-api" in path.name
    ]
    assert published == []
    assert SURFACE["implementationStatus"]["publishedArtifacts"].startswith("none")


def test_the_references_the_module_names_exist() -> None:
    for ref in (
        surface.SURFACE_DECISION_REF,
        surface.SURFACE_DATA_REF,
        surface.SURFACE_DOCUMENT_REF,
    ):
        assert (REPO_ROOT / ref).is_file(), ref
