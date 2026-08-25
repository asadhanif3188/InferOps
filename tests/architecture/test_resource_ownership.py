"""Deterministic checks over the V1 resource ownership inventory.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness.

What this suite can and cannot establish is worth stating, because the gap is the
whole point. It establishes that the ownership inventory is internally consistent:
that no resource has two owners, that Terraform's set and Helm's set do not
intersect, that every resource declares a lifecycle its owner actually has, that a
survival claim is a prefix of the teardown blast-radius ordering and never includes
the operation that destroys the resource, and that the document beside the inventory
and the inventory itself publish the same identifiers in both directions.

It establishes nothing about any Terraform configuration or Helm chart, because
neither exists. The inventory is a design commitment, and this suite is what stops
the commitment drifting before there is an implementation to check it against.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE_DIR = REPO_ROOT / "docs" / "architecture"
INVENTORY_PATH = ARCHITECTURE_DIR / "resource-ownership.v1alpha1.json"

EXPECTED_INVENTORY_ID = (
    "https://inferops.io/architecture/resource-ownership.v1alpha1.json"
)
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

# Identifiers are lowercase, hyphen-separated, and safe anywhere a name is needed.
SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# An identifier as the document publishes it: an inline code span in the first
# column of a Markdown table row.
FIRST_TABLE_COLUMN = re.compile(
    r"^\|\s*`([a-z0-9][a-z0-9-]*)`\s*\|", flags=re.MULTILINE
)

# The two layers whose overlap the parent decision forbids outright.
TOOL_OWNERS = ("terraform", "helm")

V1_STATUSES = frozenset({"implemented", "planned", "deferred"})

REQUIRED_RESOURCE_FIELDS = (
    "resourceId",
    "name",
    "kind",
    "owner",
    "lifecycle",
    "v1Status",
    "createdBy",
    "destroyedBy",
    "survives",
    "referencedBy",
    "handoff",
    "evidenceRef",
)

REQUIRED_OWNER_FIELDS = ("ownerId", "name", "lifecycle", "createdBy", "destroyedBy")


def load_inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


INVENTORY = load_inventory()
OWNERS = INVENTORY["owners"]
RESOURCES = INVENTORY["resources"]
OWNER_BY_ID = {owner["ownerId"]: owner for owner in OWNERS}


def resource_ids() -> list[str]:
    return [resource["resourceId"] for resource in RESOURCES]


def owned_by(owner_id: str) -> set[str]:
    return {r["resourceId"] for r in RESOURCES if r["owner"] == owner_id}


@pytest.fixture(scope="module")
def ownership_document() -> str:
    return (ARCHITECTURE_DIR / "resource-ownership.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


def test_inventory_declares_its_identity_and_contract_version() -> None:
    assert INVENTORY["$id"] == EXPECTED_INVENTORY_ID
    assert INVENTORY["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_inventory_is_not_empty() -> None:
    assert OWNERS, "an inventory with no owners cannot assign ownership"
    assert RESOURCES, "an inventory with no resources proves nothing"


@pytest.mark.parametrize("owner", OWNERS, ids=lambda o: o["ownerId"])
def test_every_owner_declares_every_required_field(owner: dict) -> None:
    for field in REQUIRED_OWNER_FIELDS:
        assert owner.get(field), f"owner '{owner.get('ownerId')}' is missing {field}"
    assert set(owner) == set(REQUIRED_OWNER_FIELDS), (
        f"owner '{owner['ownerId']}' carries an undeclared field"
    )


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_every_resource_declares_every_required_field(resource: dict) -> None:
    for field in REQUIRED_RESOURCE_FIELDS:
        assert field in resource, (
            f"resource '{resource.get('resourceId')}' is missing {field}"
        )
    assert set(resource) == set(REQUIRED_RESOURCE_FIELDS), (
        f"resource '{resource['resourceId']}' carries an undeclared field"
    )
    for field in REQUIRED_RESOURCE_FIELDS:
        if field in ("survives", "referencedBy", "evidenceRef"):
            continue
        assert isinstance(resource[field], str) and resource[field].strip(), (
            f"resource '{resource['resourceId']}' leaves {field} empty"
        )


def test_owner_and_resource_identifiers_are_unique() -> None:
    owner_ids = [owner["ownerId"] for owner in OWNERS]
    assert len(owner_ids) == len(set(owner_ids))
    ids = resource_ids()
    assert len(ids) == len(set(ids))


def test_owner_and_resource_identifiers_are_dns_safe_slugs() -> None:
    for owner in OWNERS:
        assert SLUG.match(owner["ownerId"]), owner["ownerId"]
    for resource in RESOURCES:
        assert SLUG.match(resource["resourceId"]), resource["resourceId"]


# --------------------------------------------------------------------------
# Single ownership, and the boundary the parent decision forbids crossing
# --------------------------------------------------------------------------


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_owner_is_a_single_declared_owner(resource: dict) -> None:
    """`owner` is one string, not a list. Two owners cannot be expressed at all."""
    assert isinstance(resource["owner"], str)
    assert resource["owner"] in OWNER_BY_ID, (
        f"resource '{resource['resourceId']}' names an undeclared owner"
    )


def test_terraform_and_helm_own_disjoint_sets() -> None:
    """The property the inventory exists to guarantee, asserted rather than inferred.

    Single ownership already makes an overlap unrepresentable. This stays because
    the property is the one a reviewer is looking for, and because a future
    loosening of the field to a list would have to delete this test rather than
    quietly pass it.
    """
    terraform, helm = (owned_by(owner_id) for owner_id in TOOL_OWNERS)
    assert terraform, "the inventory assigns Terraform nothing"
    assert helm, "the inventory assigns Helm nothing"
    assert terraform.isdisjoint(helm), sorted(terraform & helm)


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_a_reference_is_not_an_ownership_claim(resource: dict) -> None:
    for referrer in resource["referencedBy"]:
        assert referrer in OWNER_BY_ID, referrer
        assert referrer != resource["owner"], (
            f"resource '{resource['resourceId']}' lists its own owner as a referrer, "
            "which blurs the distinction this inventory exists to keep"
        )


def test_every_declared_owner_owns_something() -> None:
    """A dead owner is a boundary nobody is defending."""
    for owner_id in OWNER_BY_ID:
        assert owned_by(owner_id), f"owner '{owner_id}' owns no resource"


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_resource_lifecycle_matches_its_owner(resource: dict) -> None:
    assert resource["lifecycle"] in INVENTORY["lifecycles"], resource["lifecycle"]
    assert resource["lifecycle"] == OWNER_BY_ID[resource["owner"]]["lifecycle"], (
        f"resource '{resource['resourceId']}' claims a lifecycle its owner does not have"
    )


def test_every_declared_lifecycle_is_used() -> None:
    used = {resource["lifecycle"] for resource in RESOURCES}
    assert used == set(INVENTORY["lifecycles"]), sorted(
        set(INVENTORY["lifecycles"]) ^ used
    )


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_survival_is_drawn_from_the_declared_operations(resource: dict) -> None:
    operations = INVENTORY["operations"]
    assert len(operations) == len(set(operations))
    for operation in resource["survives"]:
        assert operation in operations, operation
    assert len(resource["survives"]) == len(set(resource["survives"]))


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_a_resource_never_survives_what_destroys_it(resource: dict) -> None:
    """Only bites where `destroyedBy` names a declared operation.

    Roughly half the inventory is destroyed by something that is not one of the
    five operations -- a contributor, a controller, an upstream publisher -- and
    for those rows this assertion cannot fail. The ordering test below is what
    carries the weight for them.
    """
    assert resource["destroyedBy"] not in resource["survives"], (
        f"resource '{resource['resourceId']}' claims to survive its own destruction"
    )


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_survival_respects_the_teardown_blast_radius_ordering(resource: dict) -> None:
    """`operations` is ordered by escalating blast radius, and survival is monotone.

    A pod restart touches least; deleting the cluster touches most, and every
    operation in between subsumes the one before it -- an uninstall removes what a
    restart would have left, destroying the namespace cascades over what an
    uninstall removed, and deleting the cluster takes all of it. So anything that
    survives one operation must survive every smaller one, which makes a valid
    `survives` list a prefix of `operations`.

    This is the check that catches a plausible-looking survival claim. It is not
    tautological for any row: an entry that skips an operation and claims a larger
    one fails here regardless of who owns it or what destroys it.
    """
    operations = INVENTORY["operations"]
    survives = resource["survives"]
    expected_prefix = operations[: len(survives)]
    assert survives == expected_prefix, (
        f"resource '{resource['resourceId']}' claims to survive {survives}, which is "
        f"not a prefix of the blast-radius ordering {operations}. A resource that "
        "survives a wider operation survives every narrower one."
    )


@pytest.mark.parametrize(
    "resource",
    [r for r in RESOURCES if r["owner"] in TOOL_OWNERS],
    ids=lambda r: r["resourceId"],
)
def test_a_tool_owned_resource_is_destroyed_by_its_own_tool(resource: dict) -> None:
    """Ownership is the right to destroy. A row that delegates that is not ownership."""
    assert resource["destroyedBy"] == OWNER_BY_ID[resource["owner"]]["destroyedBy"]
    assert resource["createdBy"] == OWNER_BY_ID[resource["owner"]]["createdBy"]


@pytest.mark.parametrize(
    "resource",
    [r for r in RESOURCES if r["owner"] == "terraform"],
    ids=lambda r: r["resourceId"],
)
def test_a_prerequisite_outlives_a_release(resource: dict) -> None:
    assert "helm uninstall" in resource["survives"], (
        f"prerequisite '{resource['resourceId']}' does not outlive a release, "
        "which is the only thing that makes it a prerequisite"
    )


@pytest.mark.parametrize(
    "resource",
    [r for r in RESOURCES if r["owner"] == "helm"],
    ids=lambda r: r["resourceId"],
)
def test_a_release_resource_does_not_outlive_the_prerequisite_layer(
    resource: dict,
) -> None:
    """Destroying the namespace cascades. Teardown order is not a preference."""
    assert "terraform destroy" not in resource["survives"]
    assert "scoped object teardown" not in resource["survives"]


@pytest.mark.parametrize(
    "resource",
    [r for r in RESOURCES if r["lifecycle"] == "derived"],
    ids=lambda r: r["resourceId"],
)
def test_a_derived_resource_is_owned_by_the_control_plane(resource: dict) -> None:
    assert resource["owner"] == "kubernetes-control-plane"
    # A derived object is never destroyed by a tool command. If it were, some
    # tool would be declaring it, and it would not be derived.
    assert resource["destroyedBy"] not in INVENTORY["operations"]


# --------------------------------------------------------------------------
# Status and evidence
# --------------------------------------------------------------------------


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_v1_status_is_from_the_controlled_vocabulary(resource: dict) -> None:
    assert resource["v1Status"] in V1_STATUSES, resource["v1Status"]


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_only_an_implemented_resource_may_cite_evidence(resource: dict) -> None:
    """The rule the whole repository runs on, applied to this file.

    A row for something that does not exist cannot have proof that it does.
    """
    reference = resource["evidenceRef"]
    if resource["v1Status"] == "implemented":
        assert reference, (
            f"resource '{resource['resourceId']}' is implemented and cites nothing"
        )
        assert (REPO_ROOT / reference).is_file(), reference
    else:
        assert reference is None, (
            f"resource '{resource['resourceId']}' is {resource['v1Status']} "
            "and cites evidence for something that has not been built"
        )


def test_an_undecided_owner_forces_the_resource_out_of_v1() -> None:
    for resource in RESOURCES:
        if resource["owner"] == "undecided":
            assert resource["v1Status"] == "deferred", (
                f"resource '{resource['resourceId']}' is in V1 scope with no owner, "
                "which is the ambiguity this inventory exists to prevent"
            )


def test_the_inventory_references_documents_that_exist() -> None:
    for key in ("decisionRef", "documentRef"):
        assert (REPO_ROOT / INVENTORY[key]).is_file(), INVENTORY[key]


# --------------------------------------------------------------------------
# The document and the data cannot drift apart
# --------------------------------------------------------------------------


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda r: r["resourceId"])
def test_the_ownership_document_publishes_every_resource(
    resource: dict, ownership_document: str
) -> None:
    assert resource["resourceId"] in ownership_document, (
        f"resource '{resource['resourceId']}' is in the inventory and not in the "
        "document a reviewer actually reads"
    )


@pytest.mark.parametrize("owner", OWNERS, ids=lambda o: o["ownerId"])
def test_the_ownership_document_publishes_every_owner(
    owner: dict, ownership_document: str
) -> None:
    assert owner["ownerId"] in ownership_document, owner["ownerId"]


def test_the_document_publishes_no_identifier_the_inventory_lacks(
    ownership_document: str,
) -> None:
    """The other direction: a row deleted from the data and left in the prose.

    The document publishes every identifier in the first column of a table, as an
    inline code span. Reading only that position keeps this precise: prose, other
    columns, and Kubernetes kinds are not scanned, and the inventory's own field
    names are camel case and cannot match the slug pattern.
    """
    known = set(resource_ids()) | set(OWNER_BY_ID)
    published = set(FIRST_TABLE_COLUMN.findall(ownership_document))
    assert published, "no identifier column found; the document layout changed"
    assert published <= known, sorted(published - known)


def test_the_architecture_documents_cite_the_inventory() -> None:
    """The narrative must point at the data, not restate it from memory."""
    for relative in ("resource-ownership.md", "system-architecture.md"):
        text = (ARCHITECTURE_DIR / relative).read_text(encoding="utf-8")
        assert "resource-ownership.v1alpha1.json" in text, relative
