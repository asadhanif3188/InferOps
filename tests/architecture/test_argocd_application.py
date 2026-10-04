"""The one Argo CD Application and its project, read as committed files.

ADR 0019 decides one Application for one release path, the project that holds it,
and the procedure that applies both. This suite reads the two manifests under
`infra/argocd/`, the procedure as text, and the documents that describe them.

What it holds:

- the Application reads the chart and the generated values of the declared
  desired-state release, and nothing else;
- its hand-written values set nothing that the generated values hold, and carry
  no API image digest;
- its sync policy is automated sync with self-heal and without pruning, and
  nothing else;
- the project admits one repository, one destination, the namespaced kinds the
  chart's real profile renders, and no cluster-scoped kind;
- no kind the project admits is a kind another owner holds in that destination;
- the procedure restates the manifests' names, and its mutating commands are the
  four it documents.

What it establishes about whether Argo CD reconciles the release, or whether the
release serves a request: nothing. It reads files.
`tests/architecture/test_argocd_application_procedure.py` executes the procedure
against stubs, and the record of a run on a provider is the evidence that a
controller applied the release.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain.render.helm_values import manual_value_findings
from tools.gitops_desired_state import DESIRED_STATE_RELEASES, expected_directory

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_REL = "infra/argocd/workloads-project.yaml"
APPLICATION_REL = "infra/argocd/local-docker-desktop-support-assistant.yaml"
PROCEDURE_REL = "scripts/environment/argocd-application.sh"
PROCEDURE_PATH = REPO_ROOT / PROCEDURE_REL
LIB_PATH = REPO_ROOT / "scripts" / "environment" / "lib.sh"
DOCUMENT_PATH = REPO_ROOT / "docs" / "environment" / "argocd-application.md"
DECISION_PATH = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0019-argocd-application-and-sync-policy.md"
)
OWNERSHIP_PATH = (
    REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
)
REAL_RENDER_PATH = (
    REPO_ROOT / "charts" / "inferops-llm" / "ci" / "rendered" / "real.expected.yaml"
)
MANUAL_FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "domain"
    / "fixtures"
    / "helm-values"
    / "support-assistant-local.manual-values.yaml"
)
VALUES_FILE_NAME = "values.generated.yaml"

# Restated on purpose. A value read from the manifest would agree with the
# manifest by construction.
ARGOCD_NAMESPACE = "argocd"
IN_CLUSTER_SERVER = "https://kubernetes.default.svc"
FOLLOWED_REVISION = "main"
MARKER = {"inferops.io/lifecycle": "reconciliation"}
OWNER_ID = "argocd-application"

#: The kubectl calls of the procedure that change nothing, as the first words
#: after `inferops::target_kubectl`. Every other call is a mutation.
READ_CALLS = (("get",), ("describe",), ("patch", "--local"))

#: The mutations the procedure documents, as the words each must begin with.
MUTATIONS = (
    ("apply", "--server-side"),
    ("patch", "applications.argoproj.io"),
    ("delete", "applications.argoproj.io"),
    ("delete", "appprojects.argoproj.io"),
)

#: A progressive-delivery or rollback object, as a manifest declares it.
ROLLOUT_KIND = re.compile(
    r"^\s*kind:\s*[\"']?(Rollout|AnalysisTemplate|ClusterAnalysisTemplate"
    r"|AnalysisRun|Experiment)\b",
    flags=re.MULTILINE,
)


def text_of(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_manifest(relative: str) -> dict[str, Any]:
    documents = [
        document
        for document in yaml.safe_load_all(text_of(REPO_ROOT / relative))
        if document is not None
    ]
    assert len(documents) == 1, f"{relative} must hold one object"
    assert isinstance(documents[0], dict)
    return documents[0]


def shell_constant(path: Path, name: str) -> str:
    matched = re.search(
        rf'^readonly {name}="([^"]*)"$', text_of(path), flags=re.MULTILINE
    )
    assert matched, f"{name} is not a readonly constant of {path.name}"
    return matched.group(1)


def procedure_commands() -> list[str]:
    """Every command of the procedure, as one logical line each, without comments."""
    commands: list[str] = []
    pending: list[str] = []
    for raw in text_of(PROCEDURE_PATH).splitlines():
        stripped = raw.strip()
        if not pending and (not stripped or stripped.startswith("#")):
            continue
        pending.append(stripped.removesuffix("\\").strip())
        if stripped.endswith("\\"):
            continue
        commands.append(" ".join(pending))
        pending = []
    return commands


def kubectl_calls() -> list[list[str]]:
    """The words after each `inferops::target_kubectl` of the procedure."""
    calls: list[list[str]] = []
    for command in procedure_commands():
        for fragment in command.split("inferops::target_kubectl ")[1:]:
            calls.append(fragment.split())
    return calls


def tracked_files() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True, capture_output=True
    ).stdout.decode("utf-8")
    return sorted(filter(None, listed.split("\0")))


PROJECT = load_manifest(PROJECT_REL)
APPLICATION = load_manifest(APPLICATION_REL)
SPEC = APPLICATION["spec"]
HELM = SPEC["source"]["helm"]
(DECLARED,) = DESIRED_STATE_RELEASES


# --------------------------------------------------------------------------
# The two objects
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("manifest", "kind"), ((PROJECT, "AppProject"), (APPLICATION, "Application"))
)
def test_each_manifest_is_one_marked_object_in_the_argocd_namespace(
    manifest: dict[str, Any], kind: str
) -> None:
    assert manifest["apiVersion"] == "argoproj.io/v1alpha1"
    assert manifest["kind"] == kind
    assert set(manifest) == {"apiVersion", "kind", "metadata", "spec"}
    metadata = manifest["metadata"]
    # No finalizer and no annotation is committed. The procedure adds the pin
    # annotation, and the removal adds the cascade finalizer.
    assert set(metadata) == {"name", "namespace", "labels"}
    assert metadata["namespace"] == ARGOCD_NAMESPACE
    assert metadata["labels"] == MARKER


def test_one_desired_state_release_is_declared_and_one_application_reads_it() -> None:
    """One Application for one release path. A second path is a second decision."""
    directory = expected_directory(DECLARED)
    assert directory is not None
    binding_name, workload = directory.split("/")[2], directory.split("/")[4]
    assert APPLICATION["metadata"]["name"] == f"{binding_name}-{workload}"
    assert Path(APPLICATION_REL).stem == APPLICATION["metadata"]["name"]
    assert HELM["valueFiles"] == [f"/{directory}/{VALUES_FILE_NAME}"]
    assert (REPO_ROOT / directory / VALUES_FILE_NAME).is_file()


def test_the_application_source_is_the_chart_at_the_followed_revision() -> None:
    source = SPEC["source"]
    assert set(source) == {"repoURL", "targetRevision", "path", "helm"}
    assert source["targetRevision"] == FOLLOWED_REVISION
    assert source["path"] == shell_constant(LIB_PATH, "INFEROPS_CHART_PATH")
    assert (REPO_ROOT / source["path"] / "Chart.yaml").is_file()
    assert set(HELM) == {"releaseName", "valueFiles", "valuesObject"}
    assert HELM["releaseName"] == shell_constant(LIB_PATH, "INFEROPS_RELEASE_NAME")
    # One source. A second source, or a source that is a directory of manifests,
    # would be a second thing this suite does not read.
    assert "sources" not in SPEC


def test_the_application_destination_is_the_bindings_namespace() -> None:
    binding = yaml.safe_load(text_of(REPO_ROOT / DECLARED.bindings[0]))
    assert binding["metadata"]["name"] == DECLARED.binding_name
    assert SPEC["destination"] == {
        "server": IN_CLUSTER_SERVER,
        "namespace": binding["spec"]["destination"]["namespace"],
    }
    assert SPEC["destination"]["namespace"] == shell_constant(
        LIB_PATH, "INFEROPS_RELEASE_NAMESPACE"
    )
    assert SPEC["destination"]["namespace"] != ARGOCD_NAMESPACE


def test_the_sync_policy_is_self_heal_without_pruning_and_nothing_else() -> None:
    """The whole policy, compared as one value.

    A sync option, a retry, a managed-namespace block, or an ignored difference
    is a decision that ADR 0019 did not take. `CreateNamespace` in particular
    would make the controller an owner of a namespace that Terraform owns.
    """
    assert SPEC["syncPolicy"] == {"automated": {"prune": False, "selfHeal": True}}
    assert set(SPEC) == {"project", "source", "destination", "syncPolicy"}


# --------------------------------------------------------------------------
# Hand-written values
# --------------------------------------------------------------------------


def leaves(node: Any, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if isinstance(node, dict) and node:
        found: set[tuple[str, ...]] = set()
        for key, value in node.items():
            found |= leaves(value, (*prefix, key))
        return found
    return {prefix}


def test_the_hand_written_values_set_nothing_the_generated_values_hold() -> None:
    """Two readings. The admission check's, and the committed file's own leaves."""
    assert list(manual_value_findings(HELM["valuesObject"])) == []
    generated = yaml.safe_load(
        text_of(REPO_ROOT / str(expected_directory(DECLARED)) / VALUES_FILE_NAME)
    )
    assert not leaves(HELM["valuesObject"]) & leaves(generated)


def test_the_hand_written_values_carry_no_api_image_digest() -> None:
    """The digest names a build on one host. The procedure supplies it."""
    assert "digest" not in HELM["valuesObject"]["api"]["image"]
    assert "parameters" not in HELM
    assert "sha256:" not in text_of(REPO_ROOT / APPLICATION_REL)


def test_the_hand_written_values_are_the_admitted_fixture_without_the_digest() -> None:
    """One shape of hand-written values, not two that drift apart."""
    fixture = yaml.safe_load(text_of(MANUAL_FIXTURE_PATH))
    del fixture["api"]["image"]["digest"]
    assert HELM["valuesObject"] == fixture


# --------------------------------------------------------------------------
# The project
# --------------------------------------------------------------------------


def test_the_project_admits_one_repository_and_one_destination() -> None:
    spec = PROJECT["spec"]
    assert set(spec) == {
        "description",
        "sourceRepos",
        "destinations",
        "clusterResourceWhitelist",
        "namespaceResourceWhitelist",
    }
    assert spec["sourceRepos"] == [SPEC["source"]["repoURL"]]
    assert spec["destinations"] == [SPEC["destination"]]
    assert SPEC["project"] == PROJECT["metadata"]["name"]
    assert "*" not in json.dumps(spec)


def test_the_project_admits_no_cluster_scoped_kind() -> None:
    assert PROJECT["spec"]["clusterResourceWhitelist"] == []


def rendered_kinds() -> set[tuple[str, str]]:
    """The kinds of the committed real render, without the `helm test` pod."""
    kinds: set[tuple[str, str]] = set()
    for document in yaml.safe_load_all(text_of(REAL_RENDER_PATH)):
        if not isinstance(document, dict):
            continue
        annotations = document.get("metadata", {}).get("annotations") or {}
        if annotations.get("helm.sh/hook") == "test":
            continue
        group = document["apiVersion"].rpartition("/")[0]
        kinds.add((group, document["kind"]))
    return kinds


def test_the_project_admits_exactly_the_kinds_the_real_profile_renders() -> None:
    admitted = {
        (entry["group"], entry["kind"])
        for entry in PROJECT["spec"]["namespaceResourceWhitelist"]
    }
    assert len(admitted) == len(PROJECT["spec"]["namespaceResourceWhitelist"])
    assert admitted == rendered_kinds()


def test_the_application_reaches_no_object_another_owner_holds() -> None:
    """The restriction that ADR 0017 D9 left to the first Application.

    Terraform owns a Namespace and a claim. The bootstrap owns a Namespace, three
    definitions, one cluster role and its binding, and the objects in `argocd`.
    The project admits no cluster-scoped kind, one destination namespace that is
    not `argocd`, and no claim. So the one Application is refused each of them.

    This holds for an Application in this project. It does not narrow the grant
    of the application controller, and it does not see an Application that a
    person creates in another project.
    """
    inventory = json.loads(text_of(OWNERSHIP_PATH))
    admitted = {
        entry["kind"] for entry in PROJECT["spec"]["namespaceResourceWhitelist"]
    }
    for row in inventory["resources"]:
        if row["owner"] != "terraform":
            continue
        kinds = set(re.findall(r"\b[A-Z][A-Za-z]+\b", row["kind"]))
        assert not kinds & admitted, row["resourceId"]
    assert "Namespace" not in admitted
    assert "PersistentVolumeClaim" not in admitted
    assert "CustomResourceDefinition" not in admitted
    assert not {kind for kind in admitted if kind.startswith("Cluster")}
    assert [entry["namespace"] for entry in PROJECT["spec"]["destinations"]] != [
        ARGOCD_NAMESPACE
    ]


def test_no_rollout_object_is_committed() -> None:
    """No Argo Rollouts object and no analysis object. A rollback is a Git change."""
    this_module = Path(__file__).relative_to(REPO_ROOT).as_posix()
    offenders = [
        relative
        for relative in tracked_files()
        if relative != this_module
        and (REPO_ROOT / relative).is_file()
        and ROLLOUT_KIND.search(text_of(REPO_ROOT / relative))
    ]
    assert offenders == []


# --------------------------------------------------------------------------
# The ownership inventory
# --------------------------------------------------------------------------


def test_the_inventory_gives_the_two_objects_one_owner() -> None:
    inventory = json.loads(text_of(OWNERSHIP_PATH))
    owners = {owner["ownerId"]: owner for owner in inventory["owners"]}
    assert owners[OWNER_ID]["createdBy"] == PROCEDURE_REL
    assert owners[OWNER_ID]["destroyedBy"] == PROCEDURE_REL
    rows = {row["resourceId"]: row for row in inventory["resources"]}
    owned = [row for row in rows.values() if row["owner"] == OWNER_ID]
    assert [row["resourceId"] for row in owned] == ["argocd-workload-application"]
    assert rows["argocd-application-manifests"]["owner"] == "repository"
    assert rows["argocd-application-manifests"]["referencedBy"] == [OWNER_ID]
    for relative in (PROJECT_REL, APPLICATION_REL):
        assert relative in rows["argocd-application-manifests"]["handoff"]


# --------------------------------------------------------------------------
# The procedure, as text
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("constant", "expected"),
    (
        ("INFEROPS_GITOPS_PROJECT_MANIFEST", PROJECT_REL),
        ("INFEROPS_GITOPS_APPLICATION_MANIFEST", APPLICATION_REL),
        ("INFEROPS_GITOPS_PROJECT_NAME", PROJECT["metadata"]["name"]),
        ("INFEROPS_GITOPS_APPLICATION_NAME", APPLICATION["metadata"]["name"]),
        ("INFEROPS_GITOPS_REPOSITORY_URL", SPEC["source"]["repoURL"]),
        ("INFEROPS_GITOPS_TARGET_REVISION", SPEC["source"]["targetRevision"]),
        ("INFEROPS_GITOPS_DESTINATION_SERVER", SPEC["destination"]["server"]),
        ("INFEROPS_GITOPS_MARKER_LABEL", next(iter(MARKER))),
        ("INFEROPS_GITOPS_MARKER_VALUE", next(iter(MARKER.values()))),
        ("INFEROPS_ARGOCD_NAMESPACE", ARGOCD_NAMESPACE),
    ),
)
def test_the_procedure_restates_the_manifests(constant: str, expected: str) -> None:
    assert shell_constant(PROCEDURE_PATH, constant) == expected


def test_the_procedure_names_the_claim_the_generated_values_name() -> None:
    generated = yaml.safe_load(
        text_of(REPO_ROOT / str(expected_directory(DECLARED)) / VALUES_FILE_NAME)
    )
    assert (
        shell_constant(PROCEDURE_PATH, "INFEROPS_GITOPS_MODEL_CACHE_CLAIM")
        == generated["model"]["cache"]["claimName"]
    )


def test_the_procedure_asks_for_every_kind_the_project_admits() -> None:
    """The removal's residue question covers what the Application may create."""
    asked = set(
        shell_constant(PROCEDURE_PATH, "INFEROPS_GITOPS_RESIDUE_KINDS").split(",")
    )
    plural = {
        "ConfigMap": "configmaps",
        "Service": "services",
        "ServiceAccount": "serviceaccounts",
        "Deployment": "deployments",
        "Job": "jobs",
        "NetworkPolicy": "networkpolicies",
        "Role": "roles",
        "RoleBinding": "rolebindings",
    }
    admitted = {
        plural[entry["kind"]] for entry in PROJECT["spec"]["namespaceResourceWhitelist"]
    }
    assert admitted <= asked
    assert asked - admitted == {"replicasets", "pods"}


def test_the_procedure_mutates_with_the_four_commands_it_documents() -> None:
    """An allow-list of reads. Everything else must be a documented mutation."""
    calls = kubectl_calls()
    assert len(calls) > 10, "the procedure's commands were not read"
    mutating = [
        call
        for call in calls
        if not any(tuple(call[: len(read)]) == read for read in READ_CALLS)
    ]
    assert len(mutating) == len(MUTATIONS), mutating
    for call, expected in zip(mutating, MUTATIONS, strict=True):
        assert tuple(call[: len(expected)]) == expected, call


def test_the_procedure_forces_nothing_and_deletes_no_prerequisite() -> None:
    body = "\n".join(procedure_commands())
    for forbidden in (
        "--force",
        "--grace-period",
        "--all ",
        "delete namespace",
        "delete persistentvolumeclaim",
        "delete pvc",
        "create namespace",
        " exec ",
        "CreateNamespace",
        "helm ",
    ):
        assert forbidden not in body, forbidden
    for call in kubectl_calls():
        if call[0] == "delete":
            assert any(word.startswith("--timeout=") for word in call), call
            assert "-n" in call, call


def test_the_procedure_reads_no_secret_value() -> None:
    """One command names a Secret, and it asks for names.

    The whole text of every command is read for the word, in either number, so
    a read by another spelling is counted too.
    """
    naming = [
        command
        for command in procedure_commands()
        if re.search(r"\bsecrets?\b", command)
        and "inferops::" in command
        and not command.lstrip().startswith("inferops::fail")
        and not command.lstrip().startswith("inferops::log")
    ]
    assert len(naming) == 1, naming
    (command,) = naming
    assert command == (
        'if ! helm_records="$(inferops::target_kubectl get secrets'
        ' -n "${INFEROPS_RELEASE_NAMESPACE}"'
        ' -l "owner=helm,name=${INFEROPS_RELEASE_NAME}" -o name)"; then'
    )


def test_every_kubectl_call_goes_through_the_target_wrapper() -> None:
    """A direct call would not be read by the allow-list above, or by the guard."""
    for command in procedure_commands():
        for found in re.finditer(r"(?<![\w:-])kubectl\b", command):
            before = command[: found.start()]
            assert before.endswith("inferops::require_cmd ") or (
                "inferops::log" in before
                or "inferops::fail" in before
                or "inferops::warn" in before
            ), command
    body = "\n".join(procedure_commands())
    assert "inferops::kubectl " not in body
    assert "inferops::target_helm" not in body and "inferops::helm" not in body


def test_the_procedure_says_that_its_report_is_not_a_caller_outcome() -> None:
    """The boundary, in the output an operator reads.

    The procedure prints the states that Argo CD reports. Each operation that
    prints them also prints that they are not a caller outcome. Review holds the
    rule that no record derives a caller outcome from them.
    """
    body = text_of(PROCEDURE_PATH)
    assert "They are not a caller outcome." in body
    assert (
        body.count("This does not establish that the workload serves a request.") == 2
    )
    commands = procedure_commands()
    report = commands.index("gitops::report_application() {")
    end = commands.index("}", report)
    assert 'inferops::log "${NOT_CALLER_TRUTH}"' in commands[report:end]


# --------------------------------------------------------------------------
# The documents
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", (DOCUMENT_PATH, DECISION_PATH))
def test_the_documents_name_what_the_manifests_hold(path: Path) -> None:
    text = text_of(path)
    for expected in (
        APPLICATION["metadata"]["name"],
        PROJECT["metadata"]["name"],
        PROJECT_REL,
        APPLICATION_REL,
        PROCEDURE_REL,
    ):
        assert expected in text, expected


def test_the_document_publishes_every_refusal_the_procedure_states() -> None:
    stated = set(re.findall(r"refusing: ([a-z0-9-]+):", text_of(PROCEDURE_PATH)))
    stated.add("target-not-selected-or-not-verified")
    document = text_of(DOCUMENT_PATH)
    published = set(
        re.findall(r"^\|\s*`([a-z0-9][a-z0-9-]*)`\s*\|", document, flags=re.MULTILINE)
    )
    assert stated <= published, stated - published
    # The header of the procedure lists the same refusals, and no other.
    header = set(
        re.findall(
            r"^#   ([a-z0-9-]+) +[a-z]", text_of(PROCEDURE_PATH), flags=re.MULTILINE
        )
    )
    assert header == stated
