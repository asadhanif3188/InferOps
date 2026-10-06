"""Deterministic checks over the Argo CD bootstrap record and its procedure.

Every check here reads files from this repository and nothing else. No network,
no cluster, no container engine, no clock, no randomness.

ADR 0017 decided how V2 installs Argo CD and who owns that installation, and
pinned the inputs. `scripts/environment/argocd-bootstrap.sh` implements the
decision. This suite holds five things:

* the record's pins have the form of immutable identifiers and agree with one
  another;
* every object the pinned manifest declares maps to a row of the ownership
  inventory that the bootstrap owner holds, and no such object is also Terraform's
  or Helm's;
* the procedure restates the record's pins, names, and refusals exactly, applies
  the manifest unmodified, and is the only build file that names the controller;
* nothing committed gives Argo CD an object to reconcile, and no serving
  component refers to Argo CD;
* every rule the record states names a test that exists, or says that nothing
  enforces it.

Until the procedure existed this suite pinned its absence: the record said
`decided-not-implemented`, the bootstrap rows were `planned`, and a build file
that named Argo CD failed. Those pins moved in the change that added the
procedure, as they were written to.

What it establishes about whether Argo CD installs, reconciles, or can be
removed: nothing. It reads the procedure as text.
`tests/architecture/test_argocd_bootstrap_procedure.py` executes the procedure
against stubs, and the record of a run on a provider is the evidence that it
installs. The pins were read from upstream once, and no test here contacts
upstream, so it does not establish that the pinned bytes are still served.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.ci_gates.ownership_overlap import (
    kind_of_terraform_type,
    terraform_resource_types,
)
from tools.gitops_desired_state import verify_tree

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
PROCEDURE_REL = "scripts/environment/argocd-bootstrap.sh"
PROCEDURE_PATH = REPO_ROOT / PROCEDURE_REL
PROCEDURE_MODULE_REL = "tests/architecture/test_argocd_bootstrap_procedure.py"
BASELINE_PATH = REPO_ROOT / "docs" / "security" / "security-baseline.v1alpha1.json"
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

#: Any spelling of the controller's name that a file could address it by:
#: `argocd`, `argo-cd`, `argo_cd`, `ARGO_CD`, `argo.cd`, `Argo CD`, `argoproj`. The
#: first version of this pattern missed the underscore, which is the spelling a
#: Python module or an environment variable would use.
ARGOCD_REFERENCE = re.compile(r"argoproj|argo[-_. ]?cd", flags=re.IGNORECASE)

#: An Argo CD custom resource, or a cluster registration, as a manifest declares
#: it. A cluster is registered with a Secret, not with a custom resource, so the
#: label that marks one is matched too. A manifest that a template assembles from
#: parts is not matched, and the record says so.
ARGOCD_CUSTOM_RESOURCE = re.compile(
    r"argoproj\.io/v1alpha1"
    r"|argocd\.argoproj\.io/secret-type"
    r"|^\s*kind:\s*[\"']?(Application|ApplicationSet|AppProject)\b",
    flags=re.MULTILINE,
)

#: Tracked files that hold an Argo CD custom resource as evidence: the object as a
#: cluster returned it, written by a run. Nothing applies such a file. The first
#: experiment's freeze record registers the one below as a file of a real-deployment
#: run. A file is listed here by its exact path, so a second one fails the test.
ARGOCD_RESOURCE_EVIDENCE = (
    "docs/proof/experiments/v2-e01/runs/20261006-e01-d-1/argo.json",
)

CLUSTER_SCOPED_KINDS = frozenset(
    {"CustomResourceDefinition", "ClusterRole", "ClusterRoleBinding"}
)
ENFORCEMENTS = frozenset({"tested", "tested-absence", "not-implemented", "review"})

#: How the document writes each enforcement in its rules table.
ENFORCEMENT_LABELS = {
    "tested": "tested",
    "tested-absence": "tested, as an absence",
    "not-implemented": "not implemented",
    "review": "review",
}

#: The one test that establishes an absence, and the rules that may cite it.
ABSENCE_TEST = "test_no_application_set_and_no_cluster_registration_is_committed"

#: The Argo CD custom resources that ADR 0019 decided: one Application and the
#: project that holds it. No other tracked file may declare one.
ARGOCD_MANIFESTS = (
    "infra/argocd/local-docker-desktop-support-assistant.yaml",
    "infra/argocd/workloads-project.yaml",
)
APPLICATION_PROCEDURE_REL = "scripts/environment/argocd-application.sh"
APPLICATION_MODULE_REL = "tests/architecture/test_argocd_application.py"
PROCEDURES = frozenset({"bootstrap", "removal"})

#: The directories whose files a cluster, a release, or a serving process is
#: built from. `docs/` and `tests/` are left out on purpose: this record and this
#: suite have to name the controller to say anything about it. `gitops/` joined
#: the list when ADR 0018 created it: a release is built from what it holds.
BUILD_ROOTS = (
    "charts",
    "contracts",
    "deploy",
    "gitops",
    "infra",
    "scripts",
    "src",
    "tools",
    ".github",
)

#: The directories a request is served from.
SERVING_ROOTS = ("src", "charts", "deploy")

#: The build files that may name the controller: the two manifests that ADR 0019
#: decided, the procedure that applies them, and the procedure that installs the
#: controller. A fifth file is a fifth thing that addresses Argo CD, and no suite
#: reads it. None of the four is under a directory a request is served from.
ALLOWED_REFERENCES = [*ARGOCD_MANIFESTS, APPLICATION_PROCEDURE_REL, PROCEDURE_REL]

#: The modules a rule may name as its enforcement: this one, which reads files,
#: the one that executes the procedure against stubs, and the one that reads the
#: Application and its project.
ENFORCING_MODULES = {
    THIS_MODULE_REL: THIS_MODULE,
    PROCEDURE_MODULE_REL: REPO_ROOT / PROCEDURE_MODULE_REL,
    APPLICATION_MODULE_REL: REPO_ROOT / APPLICATION_MODULE_REL,
}

#: How a manifest kind is written as a kubectl resource in the procedure.
RESOURCE_OF_KIND = {
    "ServiceAccount": "serviceaccount",
    "Role": "role",
    "RoleBinding": "rolebinding",
    "ConfigMap": "configmap",
    "Secret": "secret",
    "Service": "service",
    "Deployment": "deployment",
    "StatefulSet": "statefulset",
    "NetworkPolicy": "networkpolicy",
}

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


def tracked_files(roots: tuple[str, ...] | None = None) -> list[Path]:
    """Every file Git tracks, or those under the named top-level directories.

    Read from the index, not from the working tree, so an ignored or untracked
    file is not counted and a file in a directory nobody listed is.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    found: list[Path] = []
    for relative in sorted(filter(None, listed.split("\0"))):
        if roots is not None and relative.split("/", 1)[0] not in roots:
            continue
        path = REPO_ROOT / relative
        if path.is_file():
            found.append(path)
    return found


def references_to_argocd(roots: tuple[str, ...]) -> list[str]:
    """Tracked files under the roots that name the controller, in path or content."""
    return [
        path.relative_to(REPO_ROOT).as_posix()
        for path in tracked_files(roots)
        if ARGOCD_REFERENCE.search(path.relative_to(REPO_ROOT).as_posix())
        or ARGOCD_REFERENCE.search(text_of(path))
    ]


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


def procedure_text() -> str:
    return text_of(PROCEDURE_PATH)


def procedure_constant(name: str) -> str:
    matched = re.search(
        rf'^readonly {name}="([^"]*)"$', procedure_text(), flags=re.MULTILINE
    )
    assert matched, f"{name} is not a readonly constant of the procedure"
    return matched.group(1)


def procedure_commands() -> list[str]:
    """Every command of the procedure, as one logical line each.

    Comments are dropped and continuation lines are joined, so a rule about a
    command reads the whole command. A comment that quotes a command is not a
    command.
    """
    commands: list[str] = []
    pending: list[str] = []
    for raw in procedure_text().splitlines():
        stripped = raw.strip()
        if not pending and (not stripped or stripped.startswith("#")):
            continue
        pending.append(stripped.removesuffix("\\").strip())
        if stripped.endswith("\\"):
            continue
        commands.append(" ".join(pending))
        pending = []
    return commands


def objects_of(kinds: frozenset[str] | None = None) -> list[tuple[str, str]]:
    return [
        (entry["kind"], name)
        for entry in RECORD["manifestObjects"]
        for name in entry["names"]
        if kinds is None or entry["kind"] in kinds
    ]


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
# What is built, and the one file that builds it
# --------------------------------------------------------------------------


def test_the_record_says_the_bootstrap_is_implemented_by_one_procedure() -> None:
    """The record names the procedure, and no other build file names Argo CD.

    Until the procedure existed this test pinned `decided-not-implemented` and
    failed when any build file named the controller. It now pins the other
    side: the state is `implemented`, the procedure the record names is
    committed, and that file is the only one under the build directories that
    refers to Argo CD by path or by content. A second such file is a second
    procedure, a client, or a dependency, and this suite would not be reading
    it.
    """
    assert RECORD["implementationState"] == "implemented"
    procedure = RECORD["procedure"]
    assert procedure["path"] == PROCEDURE_REL
    assert PROCEDURE_PATH.is_file(), PROCEDURE_REL
    assert procedure["operations"] == ["install", "verify", "remove"]
    assert (REPO_ROOT / procedure["executedTestRef"]).is_file()
    assert procedure["executedTestRef"] == PROCEDURE_MODULE_REL

    manifest = PINS["installManifest"]
    assert manifest["mustBeAppliedUnmodified"] is True
    assert manifest["applied"] is True
    assert references_to_argocd(BUILD_ROOTS) == ALLOWED_REFERENCES


def test_every_run_the_record_cites_is_a_committed_record() -> None:
    """`applied` is a statement about a cluster, so it cites the run.

    One provider's run certifies no other provider. The record lists each run
    with its provider, and a provider with no run is listed as not executed.
    """
    runs = RECORD["runs"]
    assert runs, "the record says the manifest was applied and cites no run"
    for run in runs:
        assert set(run) == {
            "provider",
            "date",
            "serverVersion",
            "result",
            "evidenceLevel",
            "evidenceRef",
        }, run
        assert run["evidenceRef"].startswith("docs/proof/"), run["evidenceRef"]
        assert (REPO_ROOT / run["evidenceRef"]).is_file(), run["evidenceRef"]
    executed = {run["provider"] for run in runs}
    supported = set(shell_constant("INFEROPS_SUPPORTED_PROVIDERS").split())
    assert executed <= supported, sorted(executed - supported)
    assert set(RECORD["providersNotExecuted"]) == supported - executed


@pytest.mark.parametrize("row", BOOTSTRAP_ROWS, ids=lambda row: row["resourceId"])
def test_every_bootstrap_row_is_implemented_and_cites_a_run(row: dict) -> None:
    """A row is `implemented` because a run created and removed its objects.

    ADR 0017 set that condition. The row cites the record of the run, and it
    names the procedure as what creates and destroys it.
    """
    assert row["v1Status"] == "implemented", row["resourceId"]
    assert row["lifecycle"] == "bootstrap", row["resourceId"]
    assert row["createdBy"] == PROCEDURE_REL, row["resourceId"]
    assert row["destroyedBy"] == PROCEDURE_REL, row["resourceId"]
    assert row["evidenceRef"] in {run["evidenceRef"] for run in RECORD["runs"]}, row[
        "resourceId"
    ]


def test_the_two_input_rows_have_the_owners_the_decision_gives_them() -> None:
    inputs = RESOURCE_BY_ID["argocd-bootstrap-inputs"]
    assert inputs["owner"] == "repository"
    assert inputs["v1Status"] == "implemented"
    assert BOOTSTRAP_OWNER in inputs["referencedBy"]

    upstream = RESOURCE_BY_ID["argocd-upstream-release"]
    assert upstream["owner"] == "external-publisher"
    # A run downloaded the manifest and pulled both images, so the row is no
    # longer `planned`.
    assert upstream["v1Status"] == "implemented"
    assert upstream["evidenceRef"] in {run["evidenceRef"] for run in RECORD["runs"]}
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
    # The decision rests on one minor being in the list: the one both supported
    # providers last reported (ADR 0011 R3).
    assert tested["minorTheProvidersLastReported"] in tested["minors"]


def test_the_manifest_is_not_copied_into_the_repository() -> None:
    """The record says the manifest is pinned and not vendored. Hold it to that."""
    manifest = PINS["installManifest"]
    assert manifest["committedCopy"] is False
    name = Path(manifest["repositoryPath"]).name
    copies = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in tracked_files()
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

    assert not references_to_argocd(("charts",))
    # Under `infra/`, the two manifests of ADR 0019 name the controller, and no
    # Terraform file does.
    assert references_to_argocd(("infra",)) == list(ARGOCD_MANIFESTS)


def test_no_application_set_and_no_cluster_registration_is_committed() -> None:
    """Two Argo CD custom resources are committed, and this pins which two.

    Until ADR 0019 this was a plain absence: no Application, no ApplicationSet,
    and no AppProject was committed, so Argo CD had nothing to reconcile. ADR
    0019 decided one Application and the project that holds it. This test now
    holds that those two files are the only tracked files that declare an Argo CD
    custom resource, that neither is an ApplicationSet, and that no tracked file
    registers a cluster.

    What the one Application may reach is held elsewhere:
    `tests/architecture/test_argocd_application.py` reads its destination, its
    source, and the kinds its project admits.

    It reads every tracked file except this module and that one, which both
    have to quote a custom resource to test the pattern. A manifest that a
    template assembles from parts is not matched. It reads no cluster, so an
    object a person creates with kubectl is not seen.

    One more tracked file matches the pattern, and it is evidence, not a
    manifest: the Application as a cluster returned it in a recorded run. It is
    named by its exact path. This test holds that it is under the proof records,
    that it is JSON with a status that only a cluster writes, and that it is the
    committed Application and no other object. It does not hold that nothing
    applies it: no procedure reads that directory, and the procedure suite holds
    which files the procedure applies.
    """
    quoting = {THIS_MODULE, REPO_ROOT / APPLICATION_MODULE_REL}
    files = [path for path in tracked_files() if path not in quoting]
    assert len(files) > 100, "the tracked tree was not read"
    declaring = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in files
        if ARGOCD_CUSTOM_RESOURCE.search(text_of(path))
    ]
    assert declaring == sorted([*ARGOCD_RESOURCE_EVIDENCE, *ARGOCD_MANIFESTS]), (
        declaring
    )
    for relative in ARGOCD_RESOURCE_EVIDENCE:
        assert relative.startswith("docs/proof/"), relative
        observed = json.loads(text_of(REPO_ROOT / relative))
        assert observed["kind"] == "Application", relative
        assert observed["status"]["sync"]["revision"], relative
        assert observed["metadata"]["uid"], relative
        committed = yaml.safe_load(text_of(REPO_ROOT / ARGOCD_MANIFESTS[0]))
        assert observed["metadata"]["name"] == committed["metadata"]["name"], relative
        assert "argocd.argoproj.io/secret-type" not in text_of(REPO_ROOT / relative)

    kinds = []
    for relative in ARGOCD_MANIFESTS:
        body = text_of(REPO_ROOT / relative)
        documents = [
            document for document in yaml.safe_load_all(body) if document is not None
        ]
        assert len(documents) == 1, relative
        kinds.append(documents[0]["kind"])
        assert "argocd.argoproj.io/secret-type" not in body, relative
    assert kinds == ["Application", "AppProject"]

    # The desired-state tree holds generated releases and no custom resource.
    # The tree's own check accounts for every entry in it. That check reads the
    # working tree, while the scan above reads the index, so an untracked file
    # under `gitops/` fails this test although it is not committed. In a clean
    # checkout the two views are the same.
    desired_state = [
        path for path in files if path.is_relative_to(REPO_ROOT / "gitops")
    ]
    assert desired_state, "the desired-state tree was not read"
    assert not set(desired_state) & {REPO_ROOT / rel for rel in ARGOCD_MANIFESTS}
    assert verify_tree() == ()


def test_no_serving_component_refers_to_argocd() -> None:
    """The request path, read as source.

    A reference would be the first sign of a dependency: an address, an API
    group, a status read. This refuses one in the package, the chart, and the
    deployment files. It does not establish that a request is served while
    Argo CD is absent or stopped; no run has measured that. It also says nothing
    about what a running controller can do to serving objects once an Application
    exists.
    """
    assert tracked_files(SERVING_ROOTS), "no serving file was read"
    assert not references_to_argocd(SERVING_ROOTS)
    # The same reading over every build directory. One file may name the
    # controller: the procedure that installs it. A client, a second script, or
    # a workflow that addressed the controller would be the first dependency.
    assert references_to_argocd(BUILD_ROOTS) == ALLOWED_REFERENCES
    for allowed in ALLOWED_REFERENCES:
        assert allowed.split("/", 1)[0] not in SERVING_ROOTS, allowed


@pytest.mark.parametrize(
    "spelling",
    ("argocd", "ArgoCD", "argo-cd", "argo_cd", "ARGO_CD_URL", "argo.cd", "Argo CD"),
)
def test_the_reference_pattern_matches_every_spelling(spelling: str) -> None:
    """A tripwire nobody tripped is not known to work. Trip it."""
    assert ARGOCD_REFERENCE.search(spelling), spelling
    # The domain's own sentence about what it is not coupled to stays legal.
    assert not ARGOCD_REFERENCE.search("an Argo application is: a")


@pytest.mark.parametrize(
    "manifest",
    (
        "apiVersion: argoproj.io/v1alpha1\nkind: Application\n",
        "kind: Application\n",
        'kind: "ApplicationSet"\n',
        "  kind: AppProject # the default project\n",
        '{"apiVersion": "argoproj.io/v1alpha1"}',
        "    argocd.argoproj.io/secret-type: cluster\n",
    ),
)
def test_the_custom_resource_pattern_matches_what_it_is_for(manifest: str) -> None:
    assert ARGOCD_CUSTOM_RESOURCE.search(manifest), manifest


def test_the_custom_resource_pattern_does_not_match_a_template() -> None:
    """The gap the record admits, pinned so that nobody reads the test as wider."""
    assert not ARGOCD_CUSTOM_RESOURCE.search('kind: {{ printf "Appli%s" "cation" }}\n')


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

    if rule["enforcement"] in ("tested", "tested-absence"):
        module, _, function = rule["enforcedBy"].partition("::")
        # A rule held only by an absence says so in its enforcement, and no rule
        # that cites the absence test may call itself plainly tested.
        assert (function == ABSENCE_TEST) == (rule["enforcement"] == "tested-absence")
        assert module in ENFORCING_MODULES, rule["enforcedBy"]
        assert re.search(
            rf"^def {re.escape(function)}\(",
            text_of(ENFORCING_MODULES[module]),
            flags=re.MULTILINE,
        ), f"rule '{rule['ruleId']}' names a test that does not exist"
        assert rule["owedBy"] is None, rule["ruleId"]
    elif rule["enforcement"] == "not-implemented":
        assert rule["enforcedBy"] is None, rule["ruleId"]
        assert rule["owedBy"] and rule["owedBy"].strip(), (
            f"rule '{rule['ruleId']}' is enforced by nothing and owed by nobody"
        )
    else:
        assert rule["enforcedBy"] is None and rule["owedBy"] is None, rule["ruleId"]


def test_no_rule_is_still_owed_by_the_change_that_implemented_the_bootstrap() -> None:
    """The procedure exists, so nothing may still be owed by the change that added it.

    Six rules were `not-implemented` and owed by that change. Each now names a
    test. A rule that a later change owes names that change, and not this one.
    """
    assert RECORD["implementationState"] == "implemented"
    for rule in RULES:
        if rule["enforcement"] == "not-implemented":
            assert "implements the bootstrap" not in rule["owedBy"], rule["ruleId"]


def test_a_rule_about_running_the_procedure_names_an_executed_test() -> None:
    """Reading a script is not running it.

    A rule about what the procedure refuses is enforced by a test that executes
    the procedure. This holds each such rule to the module that does.
    """
    executed = {
        "bootstrap-acts-only-on-a-selected-and-verified-cluster",
        "the-manifest-is-verified-before-it-is-used",
        "images-run-at-their-pinned-digests",
        "a-foreign-argocd-installation-is-refused",
        "removal-is-scoped-and-refuses-while-an-application-exists",
    }
    by_id = {rule["ruleId"]: rule for rule in RULES}
    assert executed <= set(by_id), sorted(executed - set(by_id))
    for rule_id in sorted(executed):
        rule = by_id[rule_id]
        assert rule["enforcement"] == "tested", rule_id
        assert rule["enforcedBy"].startswith(f"{PROCEDURE_MODULE_REL}::"), rule_id
        assert "stub" in rule["limit"], (
            f"rule '{rule_id}' is executed against stubs and its limit does not say so"
        )


@pytest.mark.parametrize("refusal", REFUSALS, ids=lambda refusal: refusal["refusalId"])
def test_every_refusal_names_the_procedure_it_applies_to(refusal: dict) -> None:
    assert set(refusal) == {"refusalId", "appliesTo", "condition"}
    assert refusal["appliesTo"], refusal["refusalId"]
    assert set(refusal["appliesTo"]) <= PROCEDURES, refusal["appliesTo"]
    assert refusal["condition"].strip(), refusal["refusalId"]


def test_removal_refuses_before_it_deletes() -> None:
    """Every refusal comes before the first deletion, and the definitions go last.

    Deleting a definition deletes every object of its kind, workloads included.
    The first version of the steps deleted the manifest's objects, definitions
    first, and only then checked that the namespace was the bootstrap's own.
    """
    by_id = {refusal["refusalId"]: refusal for refusal in REFUSALS}
    assert by_id["argocd-custom-resources-present"]["appliesTo"] == ["removal"]
    for kind in ("Application", "ApplicationSet", "AppProject"):
        assert kind in by_id["argocd-custom-resources-present"]["condition"], kind
    assert set(by_id["foreign-argocd-present"]["appliesTo"]) == PROCEDURES
    # Removal deletes by the names the record lists, so it needs no download and
    # does not depend on upstream still serving the manifest.
    assert by_id["manifest-digest-mismatch"]["appliesTo"] == ["bootstrap"]

    removal = RECORD["removal"]
    steps = removal["steps"]
    assert steps and removal["doesNotTouch"] and removal["knownGaps"]
    assert "the cluster" in removal["doesNotTouch"]

    first_delete = next(i for i, step in enumerate(steps) if step.startswith("Delete"))
    marker = next(i for i, step in enumerate(steps) if "lifecycle marker" in step)
    custom = [
        i
        for i, step in enumerate(steps)
        if step.startswith("Refuse") and "Application" in step
    ]
    assert steps[marker].startswith("Refuse") and marker < first_delete
    assert custom and custom[0] < first_delete, "removal deletes before it refuses"

    controllers = next(i for i, step in enumerate(steps) if "StatefulSet" in step)
    definitions = next(
        i
        for i, step in enumerate(steps)
        if step.startswith("Delete") and "CustomResourceDefinition" in step
    )
    namespace = next(
        i for i, step in enumerate(steps) if step.startswith("Delete the namespace")
    )
    assert controllers < definitions < namespace, steps
    # The check is repeated between stopping the controllers and deleting the
    # definitions.
    assert any(controllers < index < definitions for index in custom), steps


# --------------------------------------------------------------------------
# The procedure restates the record, and does only what the record decides
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("constant", "expected"),
    (
        ("INFEROPS_ARGOCD_VERSION", PINS["release"]["version"]),
        ("INFEROPS_ARGOCD_MANIFEST_URL", PINS["installManifest"]["sourceUrl"]),
        ("INFEROPS_ARGOCD_MANIFEST_SHA256", PINS["installManifest"]["sha256"]),
        (
            "INFEROPS_ARGOCD_MANIFEST_OBJECT_COUNT",
            str(PINS["installManifest"]["objectCount"]),
        ),
        (
            "INFEROPS_ARGOCD_TESTED_MINORS",
            " ".join(PINS["testedKubernetesMinors"]["minors"]),
        ),
        ("INFEROPS_ARGOCD_NAMESPACE", RECORD["namespace"]["name"]),
        (
            "INFEROPS_ARGOCD_MARKER_LABEL",
            RECORD["namespace"]["lifecycleMarker"]["label"],
        ),
        (
            "INFEROPS_ARGOCD_MARKER_VALUE",
            RECORD["namespace"]["lifecycleMarker"]["value"],
        ),
        ("INFEROPS_ARGOCD_PIN_ANNOTATION", RECORD["namespace"]["appliedPinAnnotation"]),
        ("INFEROPS_ARGOCD_FIELD_MANAGER", RECORD["procedure"]["fieldManager"]),
    ),
    ids=lambda value: value if str(value).startswith("INFEROPS_") else "",
)
def test_the_procedure_restates_a_pin_exactly(constant: str, expected: str) -> None:
    """A pin retyped in a script is a pin that can drift from the record."""
    assert procedure_constant(constant) == expected


def test_the_procedure_names_the_objects_the_record_lists() -> None:
    """Removal deletes by these names, so each name is the record's."""
    names = {
        kind: sorted(name for entry_kind, name in objects_of() if entry_kind == kind)
        for kind in {kind for kind, _ in objects_of()}
    }
    assert (
        procedure_constant("INFEROPS_ARGOCD_DEFINITIONS").split()
        == names["CustomResourceDefinition"]
    )
    assert [procedure_constant("INFEROPS_ARGOCD_CLUSTER_ROLE")] == names["ClusterRole"]
    assert [procedure_constant("INFEROPS_ARGOCD_CLUSTER_ROLE_BINDING")] == (
        names["ClusterRoleBinding"]
    )
    assert (
        procedure_constant("INFEROPS_ARGOCD_STATEFULSETS").split()
        == names["StatefulSet"]
    )
    assert (
        procedure_constant("INFEROPS_ARGOCD_DEPLOYMENTS").split() == names["Deployment"]
    )

    namespaced = sorted(
        f"{RESOURCE_OF_KIND[kind]}/{name}"
        for kind, name in objects_of()
        if kind not in CLUSTER_SCOPED_KINDS
    )
    listed = procedure_constant("INFEROPS_ARGOCD_NAMESPACED_OBJECTS").split()
    assert sorted(listed) == namespaced
    assert len(listed) == len(set(listed)) == 29
    assert len(listed) + 5 == PINS["installManifest"]["objectCount"]


def test_the_procedure_checks_every_container_against_its_pinned_image() -> None:
    """Each container the record lists, init containers included, has one pin."""
    by_id = {image["imageId"]: image for image in PINS["images"]}
    assert set(by_id) == {"argocd", "redis"}
    assert (
        procedure_constant("INFEROPS_ARGOCD_IMAGE_DIGEST") == by_id["argocd"]["digest"]
    )
    assert (
        procedure_constant("INFEROPS_ARGOCD_REDIS_IMAGE_DIGEST")
        == by_id["redis"]["digest"]
    )
    for image_id, constant in (
        ("argocd", "INFEROPS_ARGOCD_CONTAINERS"),
        ("redis", "INFEROPS_ARGOCD_REDIS_CONTAINERS"),
    ):
        recorded = sorted(
            workload_and_container.split("/", 1)[1]
            for workload_and_container in by_id[image_id]["containers"]
        )
        assert sorted(procedure_constant(constant).split()) == recorded, image_id
    # The procedure keys the check on the container name alone, so a name that
    # two images share would be checked against one of them.
    containers = [
        entry.split("/", 1)[1]
        for image in PINS["images"]
        for entry in image["containers"]
    ]
    assert len(containers) == len(set(containers)) == 6


def test_the_procedure_states_every_refusal_the_record_lists() -> None:
    """Every refusal has its identifier in the message an operator reads."""
    body = procedure_text()
    for refusal in REFUSALS:
        identifier = refusal["refusalId"]
        if identifier == "target-not-selected-or-not-verified":
            # The provider contract's guard states this one, with its own
            # identifiers. The procedure calls the guard.
            assert "inferops::resolve_target" in procedure_commands()
            continue
        assert f'"refusing: {identifier}: ' in body, identifier
    stated = set(re.findall(r'"refusing: ([a-z0-9-]+): ', body))
    assert stated <= {refusal["refusalId"] for refusal in REFUSALS}, sorted(stated)


def test_the_procedure_verifies_the_target_before_it_reads_the_cluster() -> None:
    """One call, at the top level, before any function that reaches the cluster."""
    commands = procedure_commands()
    resolved = commands.index("inferops::resolve_target")
    first_reach = next(
        index for index, command in enumerate(commands) if "target_kubectl" in command
    )
    assert resolved < first_reach
    assert commands.count("inferops::resolve_target") == 1
    assert not [
        command for command in commands if re.search(r"(?<![:_\w])kubectl\s", command)
    ]


def test_the_procedure_applies_the_manifest_unmodified() -> None:
    """ADR 0017 D5: one digest identifies what was applied.

    The procedure applies the verified file and nothing derived from it. One
    command applies anything, it reads the verified file, and no command edits,
    templates, or patches an object.
    """
    commands = procedure_commands()
    applies = [command for command in commands if "target_kubectl apply" in command]
    assert len(applies) == 1, applies
    assert "--server-side" in applies[0] and "--force-conflicts" in applies[0]
    assert '--field-manager="${INFEROPS_ARGOCD_FIELD_MANAGER}"' in applies[0]
    assert '-n "${INFEROPS_ARGOCD_NAMESPACE}"' in applies[0]
    assert '-f "${manifest_native}"' in applies[0]

    for verb in ("patch", "edit", "replace", "set image", "annotate", "label", "scale"):
        assert not [c for c in commands if f"target_kubectl {verb}" in c], verb
    for tool in ("kustomize", "yq ", "envsubst", "helm "):
        assert not [c for c in commands if tool in c], tool
    # The file is hashed, moved into place, and handed to kubectl. Nothing
    # writes into it.
    for command in commands:
        if "manifest_file" not in command and "manifest_native" not in command:
            continue
        assert not re.search(r">>?\s*\"\$\{manifest_(file|native)\}\"", command), (
            command
        )
        assert "sed " not in command or "sha256sum" in command, command

    creates = [command for command in commands if "target_kubectl create" in command]
    assert len(creates) == 1 and creates[0].endswith("create -f -"), creates


def test_the_procedure_reads_no_secret_value_and_enters_no_container() -> None:
    """The installation holds one Secret the manifest declares and one it makes.

    The procedure reads their names. It never prints one, and it runs nothing
    inside a pod.
    """
    commands = procedure_commands()
    for command in commands:
        assert not re.search(
            r"target_kubectl (exec|cp|logs|attach|port-forward)\b", command
        ), command
        if re.search(r"target_kubectl (get|describe)\b.*\bsecrets?\b", command):
            assert "-o name" in command, command
    described = [c for c in commands if "target_kubectl describe" in c]
    assert all("describe pods" in command for command in described), described


def test_the_procedure_creates_no_argocd_custom_resource() -> None:
    """It installs the controller. It gives the controller nothing to reconcile."""
    body = procedure_text()
    assert not ARGOCD_CUSTOM_RESOURCE.search(body)
    for kind in ("Application", "ApplicationSet", "AppProject"):
        assert not re.search(rf'"kind":\s*"{kind}"', body), kind


def test_the_security_baseline_holds_rows_for_the_installation() -> None:
    """`security-baseline-rows-precede-the-first-install`, as far as a file shows it.

    The baseline holds a control for each guard of the procedure, a threat for
    the installation, and a deferred risk for the cluster-wide grant and for the
    unauthenticated pins. This establishes that the rows exist. It cannot
    establish that they were written before the first install; the record of
    the run states that order.
    """
    baseline = load(BASELINE_PATH)
    guards = {
        control["verification"]["symbol"]
        for control in baseline["controls"]
        if control["verification"]["ref"] == PROCEDURE_REL
    }
    assert guards == {
        "argocd::obtain_manifest",
        "argocd::assert_pinned_images",
        "argocd::refuse_foreign_installation",
        "argocd::refuse_custom_resources",
    }
    for guard in guards:
        assert f"{guard}() {{" in procedure_text(), guard

    threats = [
        threat
        for threat in baseline["threats"]
        if threat["assetId"] == "gitops-controller-installation"
    ]
    assert len(threats) == 3
    risks = {threat["deferredRiskRef"] for threat in threats} - {None}
    statements = " ".join(
        risk["statement"]
        for risk in baseline["deferredRisks"]
        if risk["riskId"] in risks
    )
    assert "every verb on every resource" in statements
    assert "not authenticated" in statements


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

    def verb(count: int) -> str:
        return "is" if count == 1 else "are"

    sentence = (
        f"{NUMBER_WORDS[counts['tested']].capitalize()} rules are tested, "
        f"{NUMBER_WORDS[counts['tested-absence']]} "
        f"{verb(counts['tested-absence'])} tested only as an absence, "
        f"{NUMBER_WORDS[counts['not-implemented']]} are not implemented, and "
        f"{NUMBER_WORDS[counts['review']]} is held by review."
    )
    assert sentence in document, sentence
    for rule in RULES:
        row = next(
            line for line in document.splitlines() if f"| `{rule['ruleId']}` |" in line
        )
        expected = ENFORCEMENT_LABELS[rule["enforcement"]]
        assert f"| {expected} |" in row, (rule["ruleId"], row)


def test_the_document_publishes_the_removal_steps_in_the_record_order(
    document: str,
) -> None:
    """The steps are an order, and an order retyped in prose can be reordered."""
    flattened = " ".join(document.split())
    position = -1
    for number, step in enumerate(RECORD["removal"]["steps"], start=1):
        found = flattened.find(f"{number}. {step.replace('argocd', '`argocd`')}")
        assert found > position, (number, step)
        position = found


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
