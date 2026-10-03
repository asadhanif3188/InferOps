"""Deterministic checks over the Argo CD bootstrap record.

Every check here reads files from this repository and nothing else. No network,
no cluster, no container engine, no clock, no randomness.

ADR 0017 decided how V2 installs Argo CD and who owns that installation, and
pinned the inputs. It installed nothing. This suite holds four things:

* the record's pins have the form of immutable identifiers and agree with one
  another;
* every object the pinned manifest declares maps to a row of the ownership
  inventory that the bootstrap owner holds, and no such object is also Terraform's
  or Helm's;
* nothing committed gives Argo CD an object to reconcile, and no serving
  component refers to Argo CD;
* every rule the record states names a test that exists, or says that nothing
  enforces it yet.

It also pins what is not built, so that the change which builds it has to move
the record in the same commit: the bootstrap rows are `planned`, the record says
`decided-not-implemented`, and no bootstrap script exists.

What it establishes about whether Argo CD installs, reconciles, or can be
removed: nothing. The pins were read from upstream once, and no test here
contacts upstream, so it does not establish that the pinned bytes are still
served either.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.ci_gates.ownership_overlap import (
    kind_of_terraform_type,
    terraform_resource_types,
)

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
THIS_MODULE = Path(__file__)
THIS_MODULE_REL = "tests/architecture/test_argocd_bootstrap.py"
RECORD_PATH = REPO_ROOT / "docs" / "environment" / "argocd-bootstrap.v1alpha1.json"
DOCUMENT_PATH = REPO_ROOT / "docs" / "environment" / "argocd-bootstrap.md"
DECISION_PATH = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0017-argocd-bootstrap-and-ownership.md"
)
ARCHITECTURE_INDEX_PATH = REPO_ROOT / "docs" / "architecture" / "README.md"
OWNERSHIP_PATH = (
    REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
)
OWNERSHIP_DOCUMENT_PATH = REPO_ROOT / "docs" / "architecture" / "resource-ownership.md"
LIB_PATH = REPO_ROOT / "scripts" / "environment" / "lib.sh"
TERRAFORM_DIR = REPO_ROOT / "infra" / "terraform"
TERRAFORM_ENVIRONMENT_VARIABLES = (
    TERRAFORM_DIR / "environments" / "local" / "variables.tf"
)
CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
RENDER_DIR = CHART_DIR / "ci" / "rendered"

EXPECTED_RECORD_ID = "https://inferops.io/environment/argocd-bootstrap.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
RELEASE_VERSION = re.compile(r"^v\d+\.\d+\.\d+$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")

#: An identifier as a document publishes it: an inline code span in the first
#: column of a Markdown table row.
FIRST_TABLE_COLUMN = re.compile(
    r"^\|\s*`([a-z0-9][a-z0-9-]*)`\s*\|", flags=re.MULTILINE
)

#: A Kubernetes kind inside the inventory's free-text `kind` field.
KIND_WORD = re.compile(r"\b[A-Z][A-Za-z]+\b")

#: Any spelling of the controller's name that a file could address it by.
ARGOCD_REFERENCE = re.compile(r"argocd|argoproj|argo[- ]cd", flags=re.IGNORECASE)

#: An Argo CD custom resource, as a manifest or a template would declare it.
ARGOCD_CUSTOM_RESOURCE = re.compile(
    r"argoproj\.io/v1alpha1|^\s*kind:\s*(Application|ApplicationSet|AppProject)\s*$",
    flags=re.MULTILINE,
)

CLUSTER_SCOPED_KINDS = frozenset(
    {"CustomResourceDefinition", "ClusterRole", "ClusterRoleBinding"}
)
ENFORCEMENTS = frozenset({"tested", "not-implemented", "review"})
PROCEDURES = frozenset({"bootstrap", "removal"})

#: The directories whose files a cluster, a release, or a serving process is
#: built from. `docs/` and `tests/` are left out on purpose: this record and this
#: suite have to name the controller to say anything about it.
BUILD_ROOTS = (
    "charts",
    "contracts",
    "deploy",
    "infra",
    "scripts",
    "src",
    "tools",
    ".github",
)

#: The directories a request is served from.
SERVING_ROOTS = ("src", "charts", "deploy")

SKIPPED_DIRECTORIES = frozenset({".terraform", "__pycache__", ".venv", "node_modules"})

NUMBER_WORDS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


RECORD = load(RECORD_PATH)
INVENTORY = load(OWNERSHIP_PATH)
PINS = RECORD["pinnedInputs"]
BOOTSTRAP_OWNER = RECORD["bootstrapOwnerId"]
NAMESPACE = RECORD["namespace"]["name"]
RESOURCE_BY_ID = {row["resourceId"]: row for row in INVENTORY["resources"]}
BOOTSTRAP_ROWS = [
    row for row in INVENTORY["resources"] if row["owner"] == BOOTSTRAP_OWNER
]
RULES = RECORD["rules"]
REFUSALS = RECORD["refusals"]


def committed_files(roots: tuple[str, ...]) -> list[Path]:
    """Every file under the named top-level directories, as the tree holds it."""
    found: list[Path] = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if SKIPPED_DIRECTORIES & set(path.relative_to(REPO_ROOT).parts):
                continue
            found.append(path)
    return found


def text_of(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def kinds_owned_by(owner_id: str) -> frozenset[str]:
    kinds: set[str] = set()
    for row in INVENTORY["resources"]:
        if row["owner"] == owner_id:
            kinds.update(KIND_WORD.findall(row["kind"]))
    return frozenset(kinds)


def shell_constant(name: str) -> str:
    matched = re.search(
        rf'^readonly {name}="([^"]+)"', text_of(LIB_PATH), flags=re.MULTILINE
    )
    assert matched, f"{name} is not a readonly constant in lib.sh"
    return matched.group(1)


def terraform_default(variable: str) -> str:
    matched = re.search(
        rf'variable "{variable}" \{{.*?default\s*=\s*"([^"]+)"',
        text_of(TERRAFORM_ENVIRONMENT_VARIABLES),
        flags=re.DOTALL,
    )
    assert matched, f"variable {variable} has no string default"
    return matched.group(1)


def rendered_documents() -> list[tuple[str, dict[str, Any]]]:
    documents: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(RENDER_DIR.glob("*.yaml")):
        for document in yaml.safe_load_all(text_of(path)):
            if isinstance(document, dict):
                documents.append((path.name, document))
    return documents


@pytest.fixture(scope="module")
def document() -> str:
    return text_of(DOCUMENT_PATH)


@pytest.fixture(scope="module")
def decision() -> str:
    return text_of(DECISION_PATH)


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


def test_the_record_declares_its_identity_and_contract_version() -> None:
    assert RECORD["$id"] == EXPECTED_RECORD_ID
    assert RECORD["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_the_record_references_documents_that_exist() -> None:
    for key in ("decisionRef", "documentRef", "ownershipRef", "providerContractRef"):
        assert (REPO_ROOT / RECORD[key]).is_file(), RECORD[key]
    assert REPO_ROOT / RECORD["decisionRef"] == DECISION_PATH
    assert REPO_ROOT / RECORD["documentRef"] == DOCUMENT_PATH


def test_the_record_says_what_it_does_not_establish() -> None:
    limits = RECORD["doesNotEstablish"]
    assert isinstance(limits, list) and limits
    for limit in limits:
        assert isinstance(limit, str) and limit.strip()


# --------------------------------------------------------------------------
# What is not built, pinned so that building it moves the record
# --------------------------------------------------------------------------


def test_the_record_says_the_bootstrap_is_not_implemented() -> None:
    """A pin, not a rule.

    The change that implements the bootstrap must change this value, and with it
    the five rules below that say nothing enforces them. A record that still said
    `decided-not-implemented` beside a working script would be describing the
    past.
    """
    assert RECORD["implementationState"] == "decided-not-implemented"
    scripts = sorted(
        path.name
        for path in (REPO_ROOT / "scripts" / "environment").glob("*")
        if ARGOCD_REFERENCE.search(path.name)
    )
    assert not scripts, (
        f"{scripts} exists. The record still says the bootstrap is not "
        "implemented; move implementationState and the rules it owes."
    )


@pytest.mark.parametrize("row", BOOTSTRAP_ROWS, ids=lambda row: row["resourceId"])
def test_every_bootstrap_row_is_planned_and_cites_nothing(row: dict) -> None:
    """No cluster holds these objects, so no row may say one does."""
    assert row["v1Status"] == "planned", row["resourceId"]
    assert row["evidenceRef"] is None, row["resourceId"]
    assert row["lifecycle"] == "bootstrap", row["resourceId"]


def test_the_two_input_rows_have_the_owners_the_decision_gives_them() -> None:
    inputs = RESOURCE_BY_ID["argocd-bootstrap-inputs"]
    assert inputs["owner"] == "repository"
    assert inputs["v1Status"] == "implemented"
    assert BOOTSTRAP_OWNER in inputs["referencedBy"]

    upstream = RESOURCE_BY_ID["argocd-upstream-release"]
    assert upstream["owner"] == "external-publisher"
    assert upstream["v1Status"] == "planned"
    assert BOOTSTRAP_OWNER in upstream["referencedBy"]


# --------------------------------------------------------------------------
# The pins
# --------------------------------------------------------------------------


def test_the_pins_are_immutable_identifiers() -> None:
    """A tag is a name; a commit and a digest are identities.

    This checks the form of each pin and that the pins agree with one another.
    It contacts no network, so it cannot establish that upstream still serves
    these bytes or ever did.
    """
    release = PINS["release"]
    manifest = PINS["installManifest"]

    assert RELEASE_VERSION.match(release["version"]), release["version"]
    assert release["prerelease"] is False
    assert COMMIT.match(release["tagCommit"]), release["tagCommit"]

    assert SHA256.match(manifest["sha256"]), manifest["sha256"]
    assert manifest["sourceUrl"] == (
        "https://raw.githubusercontent.com/argoproj/argo-cd/"
        f"{release['tagCommit']}/{manifest['repositoryPath']}"
    )
    assert release["version"] not in manifest["sourceUrl"], (
        "the source URL addresses the manifest by tag, and a tag can be moved"
    )
    for floating in ("/master/", "/main/", "/stable/", "/HEAD/", "latest"):
        assert floating not in manifest["sourceUrl"], floating

    images = PINS["images"]
    assert images, "no image is pinned"
    for image in images:
        assert IMAGE_DIGEST.match(image["digest"]), image
        repository, _, tag = image["manifestReference"].rpartition(":")
        assert repository and tag and tag != "latest", image["manifestReference"]
        assert "@" not in image["manifestReference"], image["manifestReference"]
        assert image["pinnedReference"] == f"{repository}@{image['digest']}", image
        assert image["containers"], image["imageId"]
    assert len({image["imageId"] for image in images}) == len(images)
    assert len({image["digest"] for image in images}) == len(images)


def test_the_argocd_image_tag_is_the_pinned_release() -> None:
    """One release, not two: the manifest's own image is the release it came from."""
    by_id = {image["imageId"]: image for image in PINS["images"]}
    tag = by_id["argocd"]["manifestReference"].rpartition(":")[2]
    assert tag == PINS["release"]["version"]


def test_the_pinned_release_lists_a_tested_kubernetes_minor() -> None:
    tested = PINS["testedKubernetesMinors"]
    assert tested["minors"] == sorted(tested["minors"], key=lambda m: int(m[2:]))
    for minor in tested["minors"]:
        assert re.match(r"^1\.\d+$", minor), minor
    # Upstream's statement, read from a page. No provider ran this release.
    assert tested["howKnown"] == "documented"


def test_the_manifest_is_not_copied_into_the_repository() -> None:
    """The record says the manifest is pinned and not vendored. Hold it to that."""
    manifest = PINS["installManifest"]
    assert manifest["committedCopy"] is False
    name = Path(manifest["repositoryPath"]).name
    copies = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in committed_files((*BUILD_ROOTS, "docs", "tests"))
        if path.name == name
    ]
    assert not copies, copies


# --------------------------------------------------------------------------
# The objects, and the rows that hold them
# --------------------------------------------------------------------------


def test_the_object_list_adds_up_to_the_manifest_count() -> None:
    objects = RECORD["manifestObjects"]
    assert (
        sum(len(entry["names"]) for entry in objects)
        == (PINS["installManifest"]["objectCount"])
    )
    kinds = [entry["kind"] for entry in objects]
    assert len(kinds) == len(set(kinds)), "a kind is listed twice"
    for entry in objects:
        assert entry["names"] == sorted(set(entry["names"])), entry["kind"]


@pytest.mark.parametrize(
    "entry",
    RECORD["manifestObjects"] + RECORD["runtimeCreatedObjects"],
    ids=lambda entry: entry["kind"],
)
def test_every_object_maps_to_a_row_the_bootstrap_owns(entry: dict) -> None:
    row = RESOURCE_BY_ID.get(entry["resourceId"])
    assert row is not None, entry["resourceId"]
    assert row["owner"] == BOOTSTRAP_OWNER, entry["resourceId"]
    assert entry["kind"] in KIND_WORD.findall(row["kind"]), (
        f"row '{row['resourceId']}' does not name the kind {entry['kind']}"
    )
    expected_scope = "cluster" if entry["kind"] in CLUSTER_SCOPED_KINDS else "namespace"
    assert entry["scope"] == expected_scope, entry["kind"]


def test_every_bootstrap_row_is_named_by_the_record() -> None:
    """The other direction: a row the inventory gives the bootstrap and the record forgot."""
    named = {entry["resourceId"] for entry in RECORD["manifestObjects"]}
    named |= {entry["resourceId"] for entry in RECORD["runtimeCreatedObjects"]}
    named.add(RECORD["namespace"]["resourceId"])
    assert named == {row["resourceId"] for row in BOOTSTRAP_ROWS}


def test_the_upstream_cluster_role_is_recorded_as_it_is_granted() -> None:
    """The grant is wide, and the record must not describe it as narrower.

    A change that narrows the grant changes the applied bytes or adds a second
    manifest. Either is a decision, and this pin makes it a visible one.
    """
    cluster_roles = [
        grant
        for grant in RECORD["requiredPrivileges"]["grantedToArgoCd"]
        if grant["kind"] == "ClusterRole"
    ]
    assert len(cluster_roles) == 1
    assert cluster_roles[0]["rules"] == [
        {"apiGroups": ["*"], "resources": ["*"], "verbs": ["*"]},
        {"nonResourceURLs": ["*"], "verbs": ["*"]},
    ]
    declared = {
        (entry["kind"], name)
        for entry in RECORD["manifestObjects"]
        for name in entry["names"]
    }
    for grant in RECORD["requiredPrivileges"]["grantedToArgoCd"]:
        assert (grant["kind"], grant["name"]) in declared, grant


# --------------------------------------------------------------------------
# One owner for every object
# --------------------------------------------------------------------------


def test_the_namespace_is_not_one_another_owner_holds() -> None:
    """Terraform owns a Namespace too. The two are told apart by name."""
    declared = RECORD["namespace"]
    release_namespace = shell_constant("INFEROPS_RELEASE_NAMESPACE")
    smoke_namespace = shell_constant("INFEROPS_NAMESPACE")
    terraform_namespace = terraform_default("namespace")

    for other in (release_namespace, smoke_namespace, terraform_namespace):
        assert other != NAMESPACE
        assert other in declared["mustNotBe"], (
            f"{other} is a namespace another owner holds and the record does not "
            "list it"
        )
    assert NAMESPACE not in declared["mustNotBe"]
    assert not NAMESPACE.startswith(declared["mustNotStartWith"])
    # The prefix the scoped sweep is written against.
    for other in (release_namespace, smoke_namespace, terraform_namespace):
        assert other.startswith(declared["mustNotStartWith"]), other
    assert RESOURCE_BY_ID[declared["resourceId"]]["owner"] == BOOTSTRAP_OWNER


def test_the_bootstrap_owner_shares_no_object_with_terraform_or_helm() -> None:
    """A kind two owners hold needs a named boundary, and a cluster-scoped kind none.

    The inventory assigns kinds, and the bootstrap holds kinds that Terraform and
    Helm hold too. That is one owner per object only while something tells the
    objects apart. This refuses a shared kind with no declared boundary, a
    declared boundary nothing needs, and a cluster-scoped kind shared at all.
    """
    bootstrap_kinds = kinds_owned_by(BOOTSTRAP_OWNER)
    boundaries = {
        (entry["otherOwner"], entry["kind"]): entry["boundary"]
        for entry in RECORD["sharedKindBoundaries"]
    }
    namespaced = {
        entry["kind"]
        for entry in RECORD["manifestObjects"]
        if entry["scope"] == "namespace"
    }

    with_terraform = bootstrap_kinds & kinds_owned_by("terraform")
    assert with_terraform == {"Namespace"}, sorted(with_terraform)
    assert boundaries.get(("terraform", "Namespace")) == "name"

    with_helm = bootstrap_kinds & kinds_owned_by("helm")
    assert with_helm, "the bootstrap and a release share no kind; drop the boundary"
    assert with_helm <= namespaced, sorted(with_helm - namespaced)
    assert boundaries.get(("helm", "namespaced objects")) == "namespace"

    assert len(boundaries) == 2, sorted(boundaries)
    for other in ("terraform", "helm", "kubernetes-control-plane"):
        shared = CLUSTER_SCOPED_KINDS & kinds_owned_by(other)
        assert not shared, f"{other} also owns {sorted(shared)}"


def test_no_other_tool_declares_a_bootstrap_owned_object() -> None:
    """Read from what the other two tools would create, not from the inventory.

    Neither committed render carries a cluster-scoped kind the bootstrap owns or
    an object in its namespace, the Terraform configuration declares no such
    kind, and neither the chart nor the configuration names the namespace. A
    values file a caller supplies at install time is not read.
    """
    documents = rendered_documents()
    assert documents, "no committed render was read"
    for render, rendered in documents:
        metadata = rendered.get("metadata") or {}
        assert rendered.get("kind") not in CLUSTER_SCOPED_KINDS, (
            render,
            rendered.get("kind"),
            metadata.get("name"),
        )
        assert rendered.get("kind") != "Namespace", (render, metadata.get("name"))
        assert metadata.get("namespace") != NAMESPACE, (render, metadata.get("name"))

    resource_types = terraform_resource_types(TERRAFORM_DIR)
    assert resource_types, "no Terraform resource was read"
    for resource_type in resource_types:
        assert kind_of_terraform_type(resource_type) not in CLUSTER_SCOPED_KINDS, (
            resource_type
        )

    for path in committed_files(("charts", "infra")):
        assert not ARGOCD_REFERENCE.search(text_of(path)), (
            f"{path.relative_to(REPO_ROOT).as_posix()} refers to Argo CD"
        )


def test_no_argocd_custom_resource_is_committed() -> None:
    """An absence, and a pin on it.

    Argo CD reconciles what an Application names. None is committed, so it has
    nothing to reconcile: not its own installation, not a Terraform-owned object,
    not an ApplicationSet, not a second cluster. That is all this establishes.

    It restricts nothing about what an Application may target. The change that
    adds the first Application must replace this test with a check of that
    Application's destination and of the kinds it may manage.
    """
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in committed_files(BUILD_ROOTS)
        if ARGOCD_CUSTOM_RESOURCE.search(text_of(path))
    ]
    assert not offenders, offenders
    assert not (REPO_ROOT / "gitops").exists(), (
        "a desired-state directory exists; this record decided none"
    )


def test_no_serving_component_refers_to_argocd() -> None:
    """The request path, read as source.

    A reference would be the first sign of a dependency: an address, an API
    group, a status read. This refuses one in the package, the chart, and the
    deployment files. It does not establish that a request is served while
    Argo CD is absent or stopped; no run has measured that.
    """
    files = committed_files(SERVING_ROOTS)
    assert files, "no serving file was read"
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in files
        if ARGOCD_REFERENCE.search(text_of(path))
    ]
    assert not offenders, offenders


# --------------------------------------------------------------------------
# Rules and refusals say what enforces them
# --------------------------------------------------------------------------


def test_rule_and_refusal_identifiers_are_unique_slugs() -> None:
    for identifiers in (
        [rule["ruleId"] for rule in RULES],
        [refusal["refusalId"] for refusal in REFUSALS],
    ):
        assert len(identifiers) == len(set(identifiers)), identifiers
        for identifier in identifiers:
            assert SLUG.match(identifier), identifier


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule["ruleId"])
def test_every_rule_says_what_enforces_it(rule: dict) -> None:
    """A rule written down is not a rule enforced, and the record must say which."""
    assert set(rule) == {
        "ruleId",
        "statement",
        "enforcement",
        "enforcedBy",
        "owedBy",
        "limit",
    }, rule["ruleId"]
    assert rule["enforcement"] in ENFORCEMENTS, rule["enforcement"]
    assert rule["statement"].strip() and rule["limit"].strip(), rule["ruleId"]

    if rule["enforcement"] == "tested":
        module, _, function = rule["enforcedBy"].partition("::")
        assert module == THIS_MODULE_REL, rule["enforcedBy"]
        assert re.search(
            rf"^def {re.escape(function)}\(", text_of(THIS_MODULE), flags=re.MULTILINE
        ), f"rule '{rule['ruleId']}' names a test that does not exist"
        assert rule["owedBy"] is None, rule["ruleId"]
    elif rule["enforcement"] == "not-implemented":
        assert rule["enforcedBy"] is None, rule["ruleId"]
        assert rule["owedBy"] and rule["owedBy"].strip(), (
            f"rule '{rule['ruleId']}' is enforced by nothing and owed by nobody"
        )
    else:
        assert rule["enforcedBy"] is None and rule["owedBy"] is None, rule["ruleId"]


def test_no_rule_about_a_procedure_claims_a_test_while_none_exists() -> None:
    """While nothing is implemented, a rule about running the bootstrap is owed."""
    assert RECORD["implementationState"] == "decided-not-implemented"
    for rule in RULES:
        if rule["enforcement"] == "not-implemented":
            assert "implements the bootstrap" in rule["owedBy"], rule["ruleId"]


@pytest.mark.parametrize("refusal", REFUSALS, ids=lambda refusal: refusal["refusalId"])
def test_every_refusal_names_the_procedure_it_applies_to(refusal: dict) -> None:
    assert set(refusal) == {"refusalId", "appliesTo", "condition"}
    assert refusal["appliesTo"], refusal["refusalId"]
    assert set(refusal["appliesTo"]) <= PROCEDURES, refusal["appliesTo"]
    assert refusal["condition"].strip(), refusal["refusalId"]


def test_removal_refuses_while_an_application_exists() -> None:
    """Deleting a definition deletes every object of its kind, workloads included."""
    by_id = {refusal["refusalId"]: refusal for refusal in REFUSALS}
    assert "removal" in by_id["applications-present"]["appliesTo"]
    assert "removal" in by_id["foreign-argocd-present"]["appliesTo"]
    assert "bootstrap" in by_id["foreign-argocd-present"]["appliesTo"]

    removal = RECORD["removal"]
    assert removal["steps"] and removal["doesNotTouch"]
    refuse_step = next(
        index
        for index, step in enumerate(removal["steps"])
        if "Application" in step and step.startswith("Refuse")
    )
    delete_step = next(
        index
        for index, step in enumerate(removal["steps"])
        if step.startswith("Delete")
    )
    assert refuse_step < delete_step, "removal deletes before it refuses"
    assert "the cluster" in removal["doesNotTouch"]


# --------------------------------------------------------------------------
# The documents and the data cannot drift apart
# --------------------------------------------------------------------------


def test_the_document_publishes_every_rule_and_refusal(document: str) -> None:
    published = set(FIRST_TABLE_COLUMN.findall(document))
    for rule in RULES:
        assert rule["ruleId"] in published, rule["ruleId"]
    for refusal in REFUSALS:
        assert refusal["refusalId"] in published, refusal["refusalId"]


def test_the_document_publishes_no_identifier_the_record_lacks(document: str) -> None:
    known = {rule["ruleId"] for rule in RULES}
    known |= {refusal["refusalId"] for refusal in REFUSALS}
    published = set(FIRST_TABLE_COLUMN.findall(document))
    assert published, "no identifier column found; the document layout changed"
    assert published <= known, sorted(published - known)


def test_the_document_states_the_enforcement_split_the_data_produces(
    document: str,
) -> None:
    counts = Counter(rule["enforcement"] for rule in RULES)
    sentence = (
        f"{NUMBER_WORDS[counts['tested']].capitalize()} rules are tested, "
        f"{NUMBER_WORDS[counts['not-implemented']]} are not implemented, and "
        f"{NUMBER_WORDS[counts['review']]} is held by review."
    )
    assert sentence in document, sentence
    for rule in RULES:
        row = next(
            line for line in document.splitlines() if f"| `{rule['ruleId']}` |" in line
        )
        expected = rule["enforcement"].replace("-", " ")
        assert f"| {expected}" in row, (rule["ruleId"], row)


def test_the_document_publishes_the_object_table_the_data_holds(document: str) -> None:
    for entry in RECORD["manifestObjects"]:
        row = (
            f"| `{entry['kind']}` | {entry['scope']} | {len(entry['names'])} | "
            f"`{entry['resourceId']}` |"
        )
        assert row in document, row


@pytest.mark.parametrize("path", (DOCUMENT_PATH, DECISION_PATH), ids=lambda p: p.name)
def test_the_documents_publish_the_pins_the_record_holds(path: Path) -> None:
    """A pin retyped in prose is a pin that can drift from the data."""
    text = text_of(path)
    release = PINS["release"]
    for value in (
        release["version"],
        release["tagCommit"],
        PINS["installManifest"]["sha256"],
        f"`{NAMESPACE}`",
    ):
        assert value in text, (path.name, value)
    for image in PINS["images"]:
        assert image["digest"] in text, (path.name, image["imageId"])
        assert image["manifestReference"] in text, (path.name, image["imageId"])


def test_the_decision_argues_every_decision_it_lists(decision: str) -> None:
    listed = re.findall(r"^\| (D\d+) \|", decision, flags=re.MULTILINE)
    assert listed and len(listed) == len(set(listed)), listed
    for identifier in listed:
        assert re.search(rf"^## {identifier} — ", decision, flags=re.MULTILINE), (
            f"{identifier} is in the status table and has no section"
        )
    assert "**Accepted in part**" in decision


def test_the_architecture_documents_cite_the_record() -> None:
    index = text_of(ARCHITECTURE_INDEX_PATH)
    assert "decisions/ADR-0017-argocd-bootstrap-and-ownership.md" in index
    ownership = text_of(OWNERSHIP_DOCUMENT_PATH)
    assert "argocd-bootstrap.md" in ownership
    assert INVENTORY["lifecycles"].get("bootstrap"), "the bootstrap lifecycle is gone"
