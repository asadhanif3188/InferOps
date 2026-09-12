"""The Helm chart against the ownership inventory and the accepted pins.

This suite reads files. It renders nothing by itself, contacts no cluster, pulls
no image, and installs nothing, so a passing run here is `local-static` evidence
about a chart and says nothing whatever about a release. Whether this chart
installs and uninstalls is answered by running
`scripts/environment/helm-lifecycle.sh`, which has never been run, and not by
reading anything here.

Three properties are what this module exists for, and each is a rule stated
somewhere else in the repository that a chart is in a position to break quietly.

**The chart may render only what Helm is allowed to own.** The ownership
inventory says Terraform owns the namespace and the model cache claim and Helm
owns the release. A chart that rendered a `Namespace` — which one flag,
`--create-namespace`, is enough to do — would give one resource two owners, and
the loser would be whichever ran last. So the rendered object set is compared
against the inventory in both directions: every rendered object maps to a
Helm-owned row, and every Helm-owned row is either rendered or named in the
chart's own deferred list.

**A real release may not be able to become a mock one, and the reverse.** The
selection is derived from `profile` in a single template helper, the serving
capability with it, and nothing in the values contract reaches either. The
checks below hold that: the shipped default selects nothing, the write site is
unique, and the two committed render fixtures carry identities the platform's
own adapters would each refuse from the other profile.

**A pin is a pin everywhere or it is not a pin.** The runtime image digest, the
model revision, and every runtime setting the chart passes as an argument are
compared against the accepted records they were copied from, so that a fixture
drifting from `ADR 0002` is a failing build rather than something a reader has
to notice.

**A probe mapping is read out of a record, not chosen here.** The runtime's
liveness probe is a TCP connect because its health endpoint answers `503` for
the whole of a model load, and the API's liveness and readiness paths are the two
the accepted surface record assigns those roles. Both mappings are compared
against those records, and the startup budget is compared against the largest
model load this project has actually measured — so a change that made the chart
internally consistent and externally wrong fails here.

The rendered manifests under `charts/inferops-llm/ci/rendered/` are committed
output from a real `helm template` run, recorded in the validation record beside
this change. The properties asserted over them run everywhere. The comparison
that catches drift needs `helm` itself and is skipped, loudly, where it is
absent — the same arrangement `kubeconform` and `shellcheck` already have.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.workload_policy import check_documents

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]

CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
CHART_YAML = CHART_DIR / "Chart.yaml"
VALUES_YAML = CHART_DIR / "values.yaml"
VALUES_SCHEMA = CHART_DIR / "values.schema.json"
TEMPLATES_DIR = CHART_DIR / "templates"
CI_DIR = CHART_DIR / "ci"
RENDERED_DIR = CI_DIR / "rendered"

INVENTORY_PATH = (
    REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
)
RUNTIME_PACKAGE_PATH = (
    REPO_ROOT / "deploy" / "serving" / "runtime" / "container-package.v1.json"
)
RUNTIME_PROFILE_PATH = REPO_ROOT / "docs" / "serving" / "runtime-profile.local.v1.json"
MODEL_SOURCE_PATH = REPO_ROOT / "docs" / "serving" / "model-source.v1.json"
API_SURFACE_PATH = (
    REPO_ROOT / "docs" / "serving" / "inference-api-surface.v1alpha1.json"
)

# The largest model load this project has measured, in milliseconds: the
# `V1-S2-005` first attempt on the reference host, which recorded 358,735 ms cold
# and 284,406 ms warm. The cold and warm start observation recorded 133,515 ms to
# 215,906 ms across six starts, and the later `V1-S2-005` recorded run loaded in
# 269,079 ms.
#
# It is quoted here for one purpose and may be cited for no other: a startup
# probe budget below it would have killed a container mid-load in a start this
# project actually observed. It is not a performance figure and says nothing
# about capacity, cold-start cost, or model-load cost.
LARGEST_MEASURED_LOAD_MS = 358_735

# The annotation that makes an object a hook rather than a resource. Helm renders
# hooks into `helm template` output alongside everything else, and a hook is
# created by the operation it is attached to and deleted by its delete policy —
# so it is not part of the installed release and not a row of the ownership
# inventory. Every check below that asks "what does this release own" reads the
# installed set; the hook has its own checks.
HOOK_ANNOTATION = "helm.sh/hook"

# The Kubernetes version this project pins, as CONTRIBUTING publishes it for
# `kubeconform`. The chart's own floor is compared against it so that a chart
# claiming to support an older API surface than the repository validates against
# is a failing assertion rather than a mismatch nobody runs into until a render.
PINNED_KUBERNETES_VERSION = "1.34.0"

# The one string that makes a placeholder verifiable rather than merely claimed.
# `ci/real-values.yaml` says the API digest is the SHA-256 of this text and that
# no image carries it; this suite recomputes the hash so that the claim is
# checked rather than believed.
PLACEHOLDER_IMAGE_SUBJECT = "inferops-api-image-not-yet-published"

DIGEST_PINNED = re.compile(r"^[^@]+@sha256:[0-9a-f]{64}$")

# A personal filesystem path, in the two shapes this project is developed
# through. Copied in form from the security suite, because a rendered manifest is
# exactly the kind of file a local path reaches by accident.
PERSONAL_PATH = re.compile(
    r"[A-Za-z]:[\\/](?:Users|home)[\\/]"
    r"|[\\/](?:Users|home)[\\/][A-Za-z0-9._-]+[\\/]",
    flags=re.IGNORECASE,
)

# The six properties every workload manifest in this repository carries. They are
# written out here rather than imported from the security suite so that a change
# to one file cannot quietly reduce what the other checks.
REQUIRED_POD_SECURITY = {
    "automountServiceAccountToken": False,
    "securityContext.runAsNonRoot": True,
    "securityContext.seccompProfile.type": "RuntimeDefault",
}
REQUIRED_CONTAINER_SECURITY = {
    "securityContext.allowPrivilegeEscalation": False,
    "securityContext.readOnlyRootFilesystem": True,
}

ABSENT = object()


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


CHART = _load_yaml(CHART_YAML)
VALUES = _load_yaml(VALUES_YAML)
SCHEMA = _load_json(VALUES_SCHEMA)
INVENTORY = _load_json(INVENTORY_PATH)
RUNTIME_PACKAGE = _load_json(RUNTIME_PACKAGE_PATH)
RUNTIME_PROFILE = _load_json(RUNTIME_PROFILE_PATH)
MODEL_SOURCE = _load_json(MODEL_SOURCE_PATH)
API_SURFACE = _load_json(API_SURFACE_PATH)

API_PATH_FOR_ROLE = {
    endpoint["servingContractRole"]: endpoint["path"]
    for endpoint in API_SURFACE["endpoints"]
}

FIXTURES = {
    "mock": _load_yaml(CI_DIR / "mock-values.yaml"),
    "real": _load_yaml(CI_DIR / "real-values.yaml"),
}


def _documents(path: Path) -> list[dict]:
    return [
        document
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(document, dict)
    ]


def _dig(node: object, dotted: str) -> Any:
    current = node
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return ABSENT
        current = current[part]
    return current


def _mapping(node: object, dotted: str) -> dict:
    """A nested mapping, or an empty one. `ABSENT` is a sentinel and not falsy."""
    found = _dig(node, dotted)
    return found if isinstance(found, dict) else {}


def _sequence(node: object, dotted: str) -> list:
    """A nested list, or an empty one. Same reason as `_mapping`: `ABSENT` is an
    object, so `_dig(...) or []` raises rather than defaulting."""
    found = _dig(node, dotted)
    return found if isinstance(found, list) else []


def _subject(document: dict) -> str:
    return f"{document.get('kind')}/{_dig(document, 'metadata.name')}"


RENDERED = {
    profile: _documents(RENDERED_DIR / f"{profile}.expected.yaml")
    for profile in ("mock", "real")
}


def _is_hook(document: dict) -> bool:
    return HOOK_ANNOTATION in _mapping(document, "metadata.annotations")


# What a release installs, and what Helm creates for the length of an operation.
# The distinction is read off the object rather than off the file it came from,
# so a hook annotation added to a resource template moves it here rather than
# quietly leaving it counted as something the release owns.
INSTALLED = {
    profile: [document for document in documents if not _is_hook(document)]
    for profile, documents in RENDERED.items()
}
HOOKS = {
    profile: [document for document in documents if _is_hook(document)]
    for profile, documents in RENDERED.items()
}

HELM_OWNED = frozenset(
    resource["resourceId"]
    for resource in INVENTORY["resources"]
    if resource["owner"] == "helm"
)
TERRAFORM_OWNED_KINDS = frozenset(
    resource["kind"].split("/")[-1].split()[-1]
    for resource in INVENTORY["resources"]
    if resource["owner"] == "terraform" and resource["kind"] != "object metadata"
)


def _annotation_set(name: str) -> frozenset[str]:
    raw = CHART["annotations"][name]
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


DECLARED_OWNED = _annotation_set("inferops.io/owned-resources")
DECLARED_DEFERRED = _annotation_set("inferops.io/deferred-resources")

# How a rendered object is recognised as one inventory row. The component label
# is what makes this a mapping rather than a guess: two Deployments and two
# Services are rendered, and the kind alone does not say which row either is.
ROW_FOR_RENDERED = {
    ("ServiceAccount", "workload-identity"): "workload-service-account",
    ("NetworkPolicy", "workload-network-policy"): "workload-network-policy",
    ("ConfigMap", "runtime-configuration"): "runtime-configuration",
    (
        "ConfigMap",
        "telemetry-scrape-configuration",
    ): "telemetry-scrape-configuration",
    ("Deployment", "platform-api"): "platform-api-deployment",
    ("Service", "platform-api"): "platform-api-service",
    ("Deployment", "serving-runtime"): "serving-runtime-deployment",
    ("Service", "serving-runtime"): "serving-runtime-service",
    # One row, six kinds. `telemetry-collector` is a platform service rather than
    # a single object -- it needs an identity, a permission, a binding, a
    # configuration, a Service and a Deployment to be one thing -- and the
    # inventory row says so in its `kind`. Mapping each kind separately is what
    # keeps a stray object from arriving under the same label unnoticed.
    ("ServiceAccount", "telemetry-collector"): "telemetry-collector",
    ("Role", "telemetry-collector"): "telemetry-collector",
    ("RoleBinding", "telemetry-collector"): "telemetry-collector",
    ("ConfigMap", "telemetry-collector"): "telemetry-collector",
    ("Service", "telemetry-collector"): "telemetry-collector",
    ("Deployment", "telemetry-collector"): "telemetry-collector",
}


def _pod_specs(documents: list[dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for document in documents:
        template = _dig(document, "spec.template.spec")
        label = f"{document.get('kind')}/{_dig(document, 'metadata.name')}"
        if isinstance(template, dict):
            out.append((label, template))
        elif document.get("kind") == "Pod":
            out.append((label, document["spec"]))
    return out


def _containers(documents: list[dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for label, spec in _pod_specs(documents):
        for key in ("initContainers", "containers"):
            for container in spec.get(key) or []:
                out.append((f"{label}.{key}[{container.get('name')}]", container))
    return out


ALL_RENDERED = [
    (profile, document)
    for profile, documents in RENDERED.items()
    for document in documents
]
ALL_INSTALLED = [
    (profile, document)
    for profile, documents in INSTALLED.items()
    for document in documents
]
ALL_POD_SPECS = [
    (f"{profile}:{label}", spec)
    for profile, documents in RENDERED.items()
    for label, spec in _pod_specs(documents)
]
ALL_CONTAINERS = [
    (f"{profile}:{label}", container)
    for profile, documents in RENDERED.items()
    for label, container in _containers(documents)
]


# --------------------------------------------------------------------------
# The chart exists and says what it is
# --------------------------------------------------------------------------


def test_the_chart_and_its_committed_inputs_were_found() -> None:
    """Guard against a suite that passes because it read nothing."""
    assert CHART_YAML.is_file()
    assert VALUES_SCHEMA.is_file()
    assert len(list(TEMPLATES_DIR.glob("*.yaml"))) >= 5
    assert len(INSTALLED["real"]) == 20, (
        "the real profile installs nineteen objects: three Deployments, three "
        "Services, the runtime ConfigMap, the telemetry scrape ConfigMap, the "
        "collector's own ConfigMap, three ServiceAccounts, the collector's Role "
        "and RoleBinding, and six network policies -- the acquisition job's "
        "egress and the collector's, both installed rather than hooked"
    )
    assert len(INSTALLED["mock"]) == 8, (
        "the mock profile installs eight: the API's Deployment, Service, "
        "ConfigMap and ServiceAccount, the telemetry scrape ConfigMap, and three "
        "network policies. It renders no runtime policy because it renders no "
        "runtime"
    )
    assert len(HOOKS["real"]) == 3, (
        "three hooks under real: the release test, the acquisition job that fills "
        "the claim before the runtime is created to read it, and the ServiceAccount "
        "that job names. The account has to be a hook itself, because Helm applies "
        "a phase's hooks before the release manifest, so an account rendered in the "
        "manifest does not exist yet when the hook Job is created"
    )
    assert len(HOOKS["mock"]) == 1, "a mock fills no claim, so it has only its test"
    assert len(ALL_CONTAINERS) == 8, (
        "five workload and hook containers, the model integrity init container "
        "the real profile runs before its runtime, the acquisition job's own, and "
        "the collector"
    )


def test_the_chart_declares_the_api_version_and_the_kubernetes_floor() -> None:
    assert CHART["apiVersion"] == "v2"
    assert CHART["name"] == "inferops-llm"
    assert CHART["type"] == "application"
    assert CHART["kubeVersion"] == f">={PINNED_KUBERNETES_VERSION}-0", (
        "the chart's Kubernetes floor and the version CONTRIBUTING validates "
        "manifests against are the same number, and drift between them means a "
        "chart that lints against a surface nothing else here checks"
    )


# --------------------------------------------------------------------------
# Ownership: the chart renders what Helm owns, and nothing else
# --------------------------------------------------------------------------


def test_the_chart_accounts_for_every_helm_owned_row() -> None:
    """Every Helm-owned resource is either rendered or declared deferred.

    A row that is neither is the failure mode this check exists for: a resource
    the inventory says Helm owns, that no chart renders and no document says is
    deferred, is owned on paper by a tool that has never heard of it.
    """
    assert DECLARED_OWNED | DECLARED_DEFERRED == HELM_OWNED, (
        "Chart.yaml's owned and deferred lists do not partition the Helm-owned "
        f"rows. Missing: {HELM_OWNED - (DECLARED_OWNED | DECLARED_DEFERRED)}; "
        f"unknown: {(DECLARED_OWNED | DECLARED_DEFERRED) - HELM_OWNED}"
    )
    assert not (DECLARED_OWNED & DECLARED_DEFERRED)


@pytest.mark.parametrize("profile", sorted(INSTALLED))
def test_every_rendered_object_maps_to_a_helm_owned_row(profile: str) -> None:
    for document in INSTALLED[profile]:
        kind = document["kind"]
        labels = _mapping(document, "metadata.labels")
        component = labels.get("app.kubernetes.io/component")
        key = (kind, component)
        assert key in ROW_FOR_RENDERED, (
            f"{profile} renders a {kind} labelled component={component!r}, which "
            "maps to no row of the ownership inventory"
        )
        assert ROW_FOR_RENDERED[key] in DECLARED_OWNED


@pytest.mark.parametrize("profile,document", ALL_RENDERED, ids=lambda v: str(v)[:60])
def test_the_chart_renders_nothing_terraform_owns(profile: str, document: dict) -> None:
    """The one flag that breaks this boundary is the default suggestion.

    `helm install --create-namespace` is a single flag, it appears in most
    documentation, and it silently makes both tools own the namespace. The chart
    renders no Namespace at all, so the flag is the only way to reach that state
    and the chart's own refusal names it.
    """
    assert document["kind"] not in TERRAFORM_OWNED_KINDS, (
        f"{profile} renders a {document['kind']}, which Terraform owns"
    )
    assert document["kind"] != "Namespace"
    assert document["kind"] != "PersistentVolumeClaim"


def test_the_model_cache_is_referenced_and_never_created() -> None:
    """Referencing is not owning, and this is the one place it is easy to blur.

    Two pods reference the claim and exactly one may write it. The serving
    runtime mounts it read only at a revision-scoped subdirectory; the
    acquisition job mounts it writable at its root, because `subPath` resolves at
    mount time and cannot create the revision directory on a claim Terraform has
    just provisioned empty.

    So the assertion is not "one reference" -- it is that every reference names
    the Terraform claim, that the chart creates none, and that the *only*
    writable one belongs to the job the ownership inventory names as the single
    sanctioned writer. A second writable mount appearing anywhere else is the
    failure this exists to catch.
    """
    assert not [d for d in RENDERED["real"] if d["kind"] == "PersistentVolumeClaim"], (
        "the chart creates a claim it is only allowed to reference"
    )

    writable = []
    for label, spec in _pod_specs(RENDERED["real"]):
        for volume in spec.get("volumes") or []:
            claim = volume.get("persistentVolumeClaim")
            if claim is None:
                continue
            assert claim["claimName"] == FIXTURES["real"]["model"]["cache"]["claimName"]
            if claim.get("readOnly") is not True:
                writable.append(label)

    assert len(writable) == 1, (
        f"exactly one pod may write the model cache; these can: {writable}"
    )
    assert "model-acquisition" in writable[0].lower(), (
        f"the writable mount belongs to {writable[0]}, not to the acquisition job"
    )


def test_the_acquisition_job_is_rendered_rather_than_deferred() -> None:
    """The writing side of the model cache handoff, which used to be absent.

    V1-S3-003 implemented the reference side -- the revision-scoped mount and the
    integrity check -- and left the writing side deferred. The consequence was a
    real profile installable only against a claim somebody had filled by hand,
    which is what the Sprint 3 review called a reproducibility gap.

    This asserts the pair rather than either half. A row declared owned and not
    rendered is owned on paper by a tool that has never heard of it; a row
    rendered while still declared deferred is the same problem inverted.
    """
    assert "model-acquisition-job" in DECLARED_OWNED
    assert "model-acquisition-job" not in DECLARED_DEFERRED
    assert any(
        resource["resourceId"] == "model-acquisition-job"
        and resource["owner"] == "helm"
        and resource["v1Status"] == "planned"
        for resource in INVENTORY["resources"]
    ), "the row stays planned until a release has actually installed it"

    # It is a hook, so it is not in INSTALLED. The real profile renders exactly
    # one; the mock renders none, because a mock fills no claim and a mock that
    # ran an acquisition would put real weights into a cluster on behalf of a
    # release that serves none of them.
    assert len([d for d in HOOKS["real"] if d["kind"] == "Job"]) == 1
    assert not [d for d in HOOKS["mock"] if d["kind"] == "Job"]
    for profile, documents in INSTALLED.items():
        assert not [d for d in documents if d["kind"] == "Job"], (
            f"{profile} renders the acquisition job as an ordinary release "
            "object, where it would race the Deployment it exists to serve"
        )


# --------------------------------------------------------------------------
# The model cache: which bytes a pod can reach, and what it checks first
# --------------------------------------------------------------------------

# The in-claim location, derived the way the chart derives it and compared
# against the layout the model source record already publishes for the
# workspace cache. One layout described in one place; a claim laid out
# differently from the checkout would be a second scheme nobody wrote down.
EXPECTED_CACHE_SUBPATH = "/".join(
    MODEL_SOURCE["cache"]["artifactRelativePath"].split("/")[:-1]
)


def _model_mounts(profile: str) -> list[tuple[str, dict]]:
    return [
        (label, mount)
        for label, container in _containers(INSTALLED[profile])
        for mount in container.get("volumeMounts") or []
        if mount["name"] == "model-cache"
    ]


def _verify_script(profile: str) -> str:
    """The init container script, which is the last member of its command."""
    return _init_containers(profile)["verify-model"]["command"][-1]


def test_the_model_cache_mount_is_scoped_to_the_declared_revision() -> None:
    """The acceptance criterion, as a mount rather than as a check.

    The claim is mounted at its repository-and-revision subdirectory and not at
    its root, so a release declaring one revision cannot see another revision
    directory at all. Before this the revision was required, compared against
    nothing, and had no bearing on which bytes a container read.
    """
    mounts = _model_mounts("real")
    assert mounts, "the real profile mounts the model cache somewhere"

    revision = FIXTURES["real"]["model"]["revision"]
    for label, mount in mounts:
        assert mount.get("subPath") == EXPECTED_CACHE_SUBPATH, (
            f"{label} mounts the claim at {mount.get('subPath')!r} rather than "
            f"at the revision-scoped {EXPECTED_CACHE_SUBPATH!r}"
        )
        assert revision in mount["subPath"], (
            f"{label} mounts a path the declared revision does not appear in, "
            "so the revision decides nothing about which bytes are readable"
        )
        assert mount["readOnly"] is True, label


def test_no_values_path_reaches_the_in_claim_location() -> None:
    """A settable subPath would put the hole back.

    Two halves, because either one alone is satisfiable while the other is not:
    the schema accepts no `model.cache.subPath` at all, and no template reads
    one. The templates are searched as text because the property being asserted
    is the absence of a read, and there is no rendered artifact of an absence.
    """
    cache_schema = SCHEMA["properties"]["model"]["properties"]["cache"]
    assert cache_schema["additionalProperties"] is False
    assert "subPath" not in cache_schema["properties"], (
        "the values contract accepts a free-form in-claim path again"
    )
    assert "subPath" not in VALUES["model"]["cache"]

    templates = sorted(TEMPLATES_DIR.rglob("*.tpl")) + sorted(
        TEMPLATES_DIR.rglob("*.yaml")
    )
    assert templates, "this check read no templates"
    for template in templates:
        text = template.read_text(encoding="utf-8")
        assert ".Values.model.cache.subPath" not in text, (
            f"{template.name} reads an in-claim path out of the values file"
        )


def test_the_verified_artifact_and_the_served_artifact_are_one_path() -> None:
    """An integrity check on a file nobody serves proves nothing.

    The path is derived once, so the --model argument, the environment the API
    reads, and the file the init container hashes are the same expression. This
    reads all three back out of the render and compares them.
    """
    runtime = _workload_containers()["runtime"]
    served = runtime["args"][runtime["args"].index("--model") + 1]

    cache = FIXTURES["real"]["model"]["cache"]
    artifact = FIXTURES["real"]["model"]["artifact"]
    derived = "{}/{}".format(cache["mountPath"], artifact["fileName"])

    assert served == derived
    assert served == RUNTIME_PROFILE["model"]["containerPath"], (
        "the derived path is no longer the one the accepted runtime profile "
        "publishes, so the chart and the record describe different files"
    )
    assert served.endswith(MODEL_SOURCE["file"])

    configuration = next(
        document for document in INSTALLED["real"] if document["kind"] == "ConfigMap"
    )
    assert configuration["data"]["INFEROPS_LLAMA_SERVER_MODEL_PATH"] == served
    assert served in _verify_script("real"), (
        "the init container reads a path the runtime does not load"
    )


def test_the_integrity_check_runs_before_the_runtime_and_on_every_start() -> None:
    """An init container rather than a job, and that is the restart property.

    A verification performed once at install time says nothing about the pod
    that replaced the one it ran in. This one runs on every pod start, so a
    replacement pod re-establishes that the surviving artifact is the artifact
    the release declared before anything serves from it.
    """
    runtime_deployment = next(
        document
        for document in INSTALLED["real"]
        if document["kind"] == "Deployment"
        and _mapping(document, "metadata.labels").get("app.kubernetes.io/component")
        == "serving-runtime"
    )
    spec = runtime_deployment["spec"]["template"]["spec"]
    assert [c["name"] for c in spec["initContainers"]] == ["verify-model"]
    assert [c["name"] for c in spec["containers"]] == ["runtime"]

    artifact = FIXTURES["real"]["model"]["artifact"]
    script = _verify_script("real")

    assert str(artifact["sizeBytes"]) in script, (
        "the pinned byte count is not in the rendered script as an integer. A "
        "large YAML number that reaches a template as a float renders in "
        "scientific notation, and the comparison then holds against a string "
        "no byte count will ever equal"
    )
    assert artifact["sha256"].removeprefix("sha256:") in script
    assert "sha256sum" in script


def test_the_integrity_container_is_given_no_environment() -> None:
    """Everything it compares against is rendered from a pinned value.

    An environment variable would be a second way to say what the artifact
    should be, and the kubelet resolves a duplicate name last-one-wins -- so a
    check configurable by environment is a check an extraEnv entry could
    satisfy.
    """
    verifier = _init_containers("real")["verify-model"]
    assert "env" not in verifier
    assert "envFrom" not in verifier


def test_the_mock_profile_mounts_nothing_and_verifies_nothing() -> None:
    """A mock that verified an artifact would describe a read it never did."""
    assert _model_mounts("mock") == []
    assert _init_containers("mock") == {}
    assert FIXTURES["mock"]["model"]["integrity"]["verifyOnStart"] == "none"
    assert "artifact" not in FIXTURES["mock"]["model"]
    assert "cache" not in FIXTURES["mock"]["model"]


def test_the_shipped_default_verifies_the_most_and_not_the_least() -> None:
    """The default is the strong setting, and the weak ones are stated choices.

    A chart defaulting to `size` would leave every release that did not think
    about it comparing a byte count, and a same-length substitution passes a
    byte count.
    """
    assert VALUES["model"]["integrity"]["verifyOnStart"] == "sha256"
    integrity = SCHEMA["properties"]["model"]["properties"]["integrity"]
    assert integrity["properties"]["verifyOnStart"]["enum"] == [
        "sha256",
        "size",
        "none",
    ]


def test_every_rendered_object_carries_the_isolation_and_lifecycle_labels() -> None:
    """ADR 0001 D5's label, plus the release half of the second one.

    The ownership document records that a scoped sweep matching
    `app.kubernetes.io/part-of=inferops` across `inferops-` namespaces would
    reach Terraform-owned prerequisites, and that the fix is a second label. This
    is the release side of it. The prerequisite side is now written --
    `infra/terraform/` sets the prerequisite marker, and
    `test_terraform_prerequisites.py` checks that it does -- but nothing has
    applied it and the environment scripts' sweep still does not exclude the
    marker, so that sweep stays bound to the smoke namespace.
    """
    for profile, document in ALL_RENDERED:
        labels = _dig(document, "metadata.labels")
        assert isinstance(labels, dict), profile
        assert labels.get("app.kubernetes.io/part-of") == "inferops"
        assert labels.get("inferops.io/lifecycle") == "release"
        assert labels.get("app.kubernetes.io/managed-by") == "Helm"
        assert labels.get("inferops.io/profile") == profile
        namespace = _dig(document, "metadata.namespace")
        assert isinstance(namespace, str) and namespace.startswith("inferops-")


def test_the_tenant_identifier_is_an_annotation_and_never_a_label() -> None:
    """A label is what a query groups by, and the redaction rules keep a tenant
    identifier out of exactly that."""
    for profile, document in ALL_RENDERED:
        labels = _mapping(document, "metadata.labels")
        assert not any("tenant" in key for key in labels), profile
        annotations = _mapping(document, "metadata.annotations")
        assert annotations.get("inferops.io/tenant") == "demo", profile


# --------------------------------------------------------------------------
# The values schema
# --------------------------------------------------------------------------


def test_the_values_schema_is_a_valid_2020_12_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


def test_every_object_in_the_schema_states_an_additional_property_policy() -> None:
    """The same rule the workload contract suite holds its schema to.

    A values object that neither permits nor forbids unknown members accepts a
    typo silently, and a typo in a values file is a setting that was never
    applied and never reported.
    """
    missing: list[str] = []

    def walk(node: object, trail: str) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "additionalProperties" not in node:
                missing.append(trail)
            for key, value in node.items():
                walk(value, f"{trail}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{trail}[{index}]")

    walk(SCHEMA, "#")
    assert not missing, missing


@pytest.mark.parametrize(
    "label,document",
    [
        ("values.yaml", VALUES),
        *[(f"ci/{k}-values.yaml", v) for k, v in FIXTURES.items()],
    ],
)
def test_the_shipped_values_and_every_fixture_satisfy_the_schema(
    label: str, document: dict
) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    # A fixture is a partial values file; Helm merges it over the defaults, and
    # the schema is applied to the merged result. Merging here is what makes the
    # assertion the one Helm actually makes.
    merged = _merge(VALUES, document) if label != "values.yaml" else document
    jsonschema.Draft202012Validator(SCHEMA).validate(merged)


def _merge(base: Any, overlay: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return overlay
    out = dict(base)
    for key, value in overlay.items():
        out[key] = _merge(base.get(key), value) if key in base else value
    return out


def test_a_secret_reference_has_no_member_that_could_hold_a_value() -> None:
    """There is no `value` member and there is not meant to be one.

    A chart that *could* carry a literal is a chart that will, and it would carry
    it into the rendered manifest, the release history, and whatever reads
    either.
    """
    item = SCHEMA["properties"]["security"]["properties"]["secretRefs"]["items"]
    assert set(item["properties"]) == {"name", "secretName", "key"}
    assert item["additionalProperties"] is False


@pytest.mark.parametrize(
    "repository,digest,accepted",
    [
        ("ghcr.io/ggml-org/llama.cpp", "sha256:" + "0" * 64, True),
        ("localhost:5000/inferops-api", "sha256:" + "a" * 64, True),
        # A tag, in the three shapes it arrives in: attached to the repository,
        # written into the digest field, and an immutable-looking digest that is
        # the wrong length.
        ("ghcr.io/ggml-org/llama.cpp:server", "sha256:" + "0" * 64, False),
        ("ghcr.io/ggml-org/llama.cpp", "latest", False),
        ("ghcr.io/ggml-org/llama.cpp", "sha256:" + "0" * 63, False),
        ("ghcr.io/ggml-org/llama.cpp@sha256:" + "0" * 64, "sha256:" + "0" * 64, False),
    ],
)
def test_no_image_field_accepts_a_tag(
    repository: str, digest: str, accepted: bool
) -> None:
    """Checked by validating references rather than by reading the pattern.

    A regular expression asserted against as text passes whenever somebody edits
    both it and the assertion, which is exactly when it is worth checking.
    """
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(
        {**SCHEMA["$defs"]["image"], "$defs": SCHEMA["$defs"]}
    )
    errors = list(validator.iter_errors({"repository": repository, "digest": digest}))
    assert (not errors) == accepted, (repository, digest, [e.message for e in errors])


def test_a_resource_block_requires_both_halves() -> None:
    assert SCHEMA["$defs"]["resources"]["required"] == ["requests", "limits"]
    quantities = SCHEMA["$defs"]["resourceQuantities"]
    assert quantities["required"] == ["cpu", "memory"]


def test_the_security_identifiers_cannot_select_root() -> None:
    assert SCHEMA["$defs"]["nonRootId"]["minimum"] == 1


# --------------------------------------------------------------------------
# The mock and real boundary
# --------------------------------------------------------------------------


def test_the_shipped_default_selects_no_adapter() -> None:
    """Rule 5, as a property of the file rather than a promise about it.

    If the mandatory serving path can be satisfied by a mock, the project has not
    built a serving path. A chart whose default were `mock` would satisfy it once
    per install.
    """
    assert VALUES["profile"] == ""
    assert SCHEMA["properties"]["profile"]["enum"] == ["", "mock", "real"]


def test_the_adapter_selection_has_exactly_one_write_site() -> None:
    """`INFEROPS_SERVING_ADAPTER` is written once, from `profile`, and the values
    contract offers no other path to it."""
    writers = [
        path
        for path in sorted(TEMPLATES_DIR.iterdir())
        if path.is_file() and "INFEROPS_SERVING_ADAPTER:" in path.read_text("utf-8")
    ]
    assert [path.name for path in writers] == ["_helpers.tpl"], writers
    body = (TEMPLATES_DIR / "_helpers.tpl").read_text(encoding="utf-8")
    assert "INFEROPS_SERVING_ADAPTER: {{ .Values.profile | quote }}" in body
    assert "adapterKind" not in json.dumps(SCHEMA)
    assert "capabilityId" not in json.dumps(SCHEMA), (
        "the serving capability is derived from the profile; a values member "
        "carrying it would be a way to install one adapter and publish the "
        "other's capability"
    )


@pytest.mark.parametrize(
    "profile,adapter,capability",
    [
        ("mock", "mock", "inferops-mock-serving"),
        ("real", "real", "inferops-native-serving"),
    ],
)
def test_each_rendered_profile_publishes_its_own_identity(
    profile: str, adapter: str, capability: str
) -> None:
    configuration = next(
        document for document in RENDERED[profile] if document["kind"] == "ConfigMap"
    )["data"]
    assert configuration["INFEROPS_SERVING_ADAPTER"] == adapter
    assert configuration["INFEROPS_CAPABILITY_ID"] == capability


def test_the_mock_render_carries_no_real_pin_and_no_runtime() -> None:
    """A mock that mounted the cache and named a revision would be
    indistinguishable, from the outside, from a release that had served from
    one."""
    kinds = sorted(document["kind"] for document in INSTALLED["mock"])
    assert kinds == [
        "ConfigMap",
        "ConfigMap",
        "Deployment",
        "NetworkPolicy",
        "NetworkPolicy",
        "NetworkPolicy",
        "Service",
        "ServiceAccount",
    ], (
        "the mock profile installs the API alone, with its own identity and its "
        "own policies; the test hook is not installed and is checked separately"
    )
    body = (RENDERED_DIR / "mock.expected.yaml").read_text(encoding="utf-8")
    for forbidden in (
        MODEL_SOURCE["revision"],
        RUNTIME_PROFILE["runtime"]["imageReference"],
        RUNTIME_PROFILE["model"]["containerPath"],
        "persistentVolumeClaim",
        "serving-runtime",
    ):
        assert forbidden not in body, f"the mock render carries {forbidden!r}"
    configuration = next(
        document for document in RENDERED["mock"] if document["kind"] == "ConfigMap"
    )["data"]
    assert configuration["INFEROPS_MODEL_IDENTIFIER"].startswith("mock-")
    assert "INFEROPS_MODEL_REVISION" not in configuration
    assert "INFEROPS_RUNTIME_IMAGE_DIGEST" not in configuration


def test_the_real_render_carries_no_mock_labelled_identity() -> None:
    """Checked field by field rather than by scanning the whole file.

    A whole-file search for the substring would also fail on an owner named
    `team-demock` or a workload named `unmocked-service`, both of which the
    schema permits and neither of which says anything about the adapter. A check
    that fails for a reason unrelated to the property it defends gets suppressed
    the first time it does, so it is scoped to the fields that carry identity.
    """
    configuration = next(
        document for document in RENDERED["real"] if document["kind"] == "ConfigMap"
    )["data"]
    assert configuration["INFEROPS_SERVING_ADAPTER"] == "real"
    assert not configuration["INFEROPS_MODEL_IDENTIFIER"].lower().startswith("mock-")
    assert "mock" not in configuration["INFEROPS_CAPABILITY_ID"]
    for document in RENDERED["real"]:
        labels = _mapping(document, "metadata.labels")
        assert labels["inferops.io/profile"] == "real"


def test_each_fixture_declares_what_its_profile_permits() -> None:
    mock = FIXTURES["mock"]
    assert mock["profile"] == "mock"
    assert mock["model"]["identifier"].startswith("mock-")
    assert "revision" not in mock["model"]
    assert "alias" not in mock["model"]
    assert "artifact" not in mock["model"]
    assert "cache" not in mock["model"]
    assert "security" not in mock
    assert mock["model"]["integrity"]["verifyOnStart"] == "none", (
        "stated rather than inherited: the shipped default is the strong "
        "setting, so a mock has to say out loud that it verifies nothing"
    )

    real = FIXTURES["real"]
    assert real["profile"] == "real"
    assert not real["model"]["identifier"].startswith("mock-")


def test_every_free_form_map_that_reaches_an_object_is_guarded() -> None:
    """The refusal set covers every values map that reaches a rendered object.

    Independent review of this change found the guard applied to `extraEnv` and
    `secretRefs` and not to the label and annotation maps, which meant a mock
    release could be rendered carrying `inferops.io/profile: real` from a
    schema-valid `--set`. Appending a key a mapping already has produces it
    twice, and every parser the output passes through keeps the appended one — so
    the merge was a relabelling rather than a decoration.

    This reads the guards rather than the render, because a render made from the
    committed fixtures cannot show a guard that is missing. The refusals
    themselves were exercised against `helm` and are recorded in
    `docs/proof/architecture/v1-s3-002-pr1-validation.md`.
    """
    guards = (TEMPLATES_DIR / "_validate.tpl").read_text(encoding="utf-8")
    for surface in (
        ".Values.commonLabels",
        ".Values.commonAnnotations",
        ".Values.api.service.annotations",
        ".Values.runtime.service.annotations",
        ".Values.security.serviceAccount.annotations",
        ".Values.security.secretRefs",
        "extraEnv",
        "INFEROPS_POD_NAME",
    ):
        assert surface in guards, (
            f"{surface} reaches a rendered object and no refusal names it"
        )


def test_the_guarded_label_and_annotation_keys_are_the_ones_the_chart_writes() -> None:
    """The refusal lists and the writers are compared, not trusted.

    Two lists that have to agree and are maintained separately drift. So the keys
    the guard refuses are read out of the helper that declares them, and every
    key the label and annotation helpers actually emit is checked against it — a
    label added to the helper and forgotten in the list fails here.
    """
    helpers = (TEMPLATES_DIR / "_helpers.tpl").read_text(encoding="utf-8")
    declared_labels = set(
        re.findall(r"^- (\S+)$", _define_body(helpers, "derivedLabelKeys"), re.M)
    )
    declared_annotations = set(
        re.findall(r"^- (\S+)$", _define_body(helpers, "derivedAnnotationKeys"), re.M)
    )

    written_labels: set[str] = set()
    written_annotations: set[str] = set()
    # Installed objects only. A hook carries `helm.sh/hook` and its delete
    # policy, which are Helm's keys rather than keys this chart derives, and
    # counting them here would mean adding them to a refusal list that exists to
    # protect identity.
    for _profile, document in ALL_INSTALLED:
        written_labels |= set(_mapping(document, "metadata.labels"))
        written_annotations |= set(_mapping(document, "metadata.annotations"))
        template = _dig(document, "spec.template.metadata")
        if isinstance(template, dict):
            written_labels |= set(template.get("labels") or {})
            written_annotations |= set(template.get("annotations") or {})

    # The fixtures supply no extra label or annotation of their own, so every key
    # in a render is one the chart wrote.
    assert written_labels <= declared_labels, written_labels - declared_labels
    assert written_annotations <= declared_annotations, (
        written_annotations - declared_annotations
    )
    # And the identity keys the whole boundary rests on are certainly in the list.
    assert {
        "inferops.io/profile",
        "inferops.io/lifecycle",
        "app.kubernetes.io/part-of",
    } <= declared_labels


def _define_body(source: str, name: str) -> str:
    """The body of one `define` block, by name."""
    match = re.search(
        rf'{{{{- define "inferops-llm\.{name}" -}}}}(.*?){{{{- end -}}}}',
        source,
        re.S,
    )
    assert match, name
    return match.group(1)


def test_the_derived_annotations_win_a_merge_they_are_not_meant_to_lose() -> None:
    """Sprig gives the destination precedence, and the destination was wrong.

    The refusal above makes a collision impossible, so this ordering is belt and
    braces — deliberately, because the two guards then fail independently rather
    than one silently covering for the other.
    """
    for name in ("serviceaccount.yaml", "api-service.yaml", "runtime-service.yaml"):
        body = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
        merge_line = next(
            line
            for line in body.splitlines()
            if "merge" in line and "annotations" in line
        )
        derived = merge_line.index('include "inferops-llm.annotations"')
        supplied = merge_line.index(".Values.")
        assert derived < supplied, (
            f"{name} merges the values-supplied annotations as the destination, "
            "which sprig gives precedence to"
        )


def test_the_runtime_container_receives_no_inferops_environment() -> None:
    """Stated because the documents say it, and it is easy to change by accident.

    `llama.cpp` reads no `INFEROPS_` variable; its configuration is its argument
    vector. Giving it variables it ignores would suggest it emitted something it
    does not, and `security.secretRefs` reaching it would suggest the runtime can
    hold a credential. Both are disclaimed in the chart README and in
    `values.yaml`, so both are checked here.
    """
    runtime = next(
        container
        for _, container in _containers(RENDERED["real"])
        if container["name"] == "runtime"
    )
    for entry in runtime.get("env") or []:
        assert not entry["name"].startswith("INFEROPS_"), entry["name"]
        assert "valueFrom" not in entry
    assert "envFrom" not in runtime


# --------------------------------------------------------------------------
# The pins, against the records they were copied from
# --------------------------------------------------------------------------


def test_the_runtime_image_is_the_one_the_accepted_records_pin() -> None:
    reference = "{}@{}".format(
        VALUES["runtime"]["image"]["repository"], VALUES["runtime"]["image"]["digest"]
    )
    assert reference == RUNTIME_PROFILE["runtime"]["imageReference"]
    assert reference == RUNTIME_PACKAGE["container"]["imageReference"]
    assert reference == "{}@{}".format(
        FIXTURES["real"]["runtime"]["image"]["repository"],
        FIXTURES["real"]["runtime"]["image"]["digest"],
    )


def test_the_runtime_settings_are_the_ones_the_profile_publishes() -> None:
    serving = RUNTIME_PROFILE["serving"]
    runtime = VALUES["runtime"]
    assert runtime["contextSizeTokens"] == serving["contextSizeTokens"]
    assert runtime["threads"] == serving["threads"]
    assert runtime["parallelSlots"] == serving["parallelSlots"]
    assert runtime["defaultMaxOutputTokens"] == serving["defaultMaxOutputTokens"]
    assert runtime["defaultTemperature"] == serving["defaultTemperature"]
    assert runtime["startupBudgetMs"] == RUNTIME_PROFILE["timeouts"]["startupBudgetMs"]
    assert runtime["command"] == RUNTIME_PROFILE["runtime"]["command"]
    assert runtime["containerPort"] == RUNTIME_PROFILE["network"]["containerPort"]
    assert runtime["healthPath"] == RUNTIME_PROFILE["health"]["readiness"]["path"]


def test_the_rendered_runtime_arguments_are_the_ones_that_were_measured() -> None:
    """The trial ran these arguments. A chart that passed different ones would
    make the recorded result evidence for a configuration nobody deployed."""
    container = next(
        container
        for _, container in _containers(RENDERED["real"])
        if container["name"] == "runtime"
    )
    rendered = [str(argument) for argument in container["args"]]
    expected = [str(argument) for argument in RUNTIME_PROFILE["runtime"]["arguments"]]
    assert rendered == expected
    assert container["command"] == [RUNTIME_PROFILE["runtime"]["command"]]


def test_the_real_fixture_pins_the_model_the_source_record_pins() -> None:
    model = FIXTURES["real"]["model"]
    assert model["revision"] == MODEL_SOURCE["revision"]
    assert model["identifier"] == RUNTIME_PROFILE["model"]["platformIdentifier"]
    assert model["alias"] == RUNTIME_PROFILE["model"]["alias"]


def test_the_real_fixture_pins_the_artifact_the_source_record_pins() -> None:
    """Four values that decide which bytes a pod reads and whether it accepts
    them, compared against the one record that publishes them.

    `repository` and `revision` derive the subdirectory of the claim the release
    mounts; `sizeBytes` and `sha256` are what the pod compares the mounted file
    against. A fixture free to state its own would be a release verifying an
    artifact against numbers it chose.
    """
    artifact = FIXTURES["real"]["model"]["artifact"]

    assert artifact["repository"] == MODEL_SOURCE["repository"]
    assert artifact["fileName"] == MODEL_SOURCE["file"]
    assert artifact["sizeBytes"] == MODEL_SOURCE["expectedSizeBytes"]
    assert artifact["sha256"] == MODEL_SOURCE["sha256"]


def test_the_api_image_digest_in_the_fixtures_is_the_documented_placeholder() -> None:
    """The fixtures say the API digest is a placeholder. This recomputes it.

    The fixtures have to satisfy the chart's digest refusal, so they carry the
    SHA-256 of a stated string rather than a plausible-looking digest -- which is
    the difference between a placeholder a reader can verify and one they have to
    trust.

    **The reason for the placeholder changed, and this test changed with it.**
    Until the Sprint 3 remediation there was no Dockerfile at all, and this
    asserted that -- if an image could not be built, no digest could be real. An
    image can now be built: `deploy/api/Dockerfile` is committed and
    `scripts/environment/api-image.sh` builds it, loads it into the node and
    verifies the reference resolves there. The placeholder stays for a different
    and narrower reason. The image is published to no registry, so its manifest
    digest is a fact about one contributor's build rather than about this
    repository, and `api-image.sh values` writes it into an overlay under
    `.artifacts/` that version control ignores.

    So the assertion inverted rather than relaxed. It used to require that no
    build path existed; it now requires that one does, that the workflow derives
    its digest instead of declaring one, and that nothing committed carries a
    digest for an image nobody else can verify. `platform-api-container-image`
    stays `planned` because no release has installed it -- a built image is not
    an installed one.
    """
    expected = (
        "sha256:"
        + hashlib.sha256(PLACEHOLDER_IMAGE_SUBJECT.encode("ascii")).hexdigest()
    )
    for name, fixture in FIXTURES.items():
        assert fixture["api"]["image"]["digest"] == expected, name
    assert any(
        resource["resourceId"] == "platform-api-container-image"
        and resource["v1Status"] == "planned"
        for resource in INVENTORY["resources"]
    ), (
        "the placeholder is justified by there being no published API image; if "
        "that row is implemented, the fixtures name a real digest instead"
    )
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--", "*Dockerfile*"],
        capture_output=True,
        text=True,
        check=False,
    )
    # Tracked files only. A repository-wide glob would also walk `.venv/`, where a
    # `Dockerfile` belonging to somebody else's package would be counted as this
    # project's build path.
    assert tracked.returncode == 0, tracked.stderr
    committed = sorted(tracked.stdout.split())
    assert committed == ["deploy/api/Dockerfile", "deploy/model-seed/Dockerfile"], (
        "the images this repository builds are the API's and the model seed's; "
        f"found {committed}"
    )

    # The digest is derived from a built image, never written down. A literal in
    # the build workflow would be somebody's host state committed as though it
    # were this repository's, and it is the one thing the review named outright:
    # do not replace the fake digest with another unverified digest.
    workflow = (REPO_ROOT / "scripts" / "environment" / "api-image.sh").read_text(
        encoding="utf-8"
    )
    assert "RepoDigests" in workflow, "the workflow does not derive a digest"
    assert not re.search(r"sha256:[0-9a-f]{64}", workflow), (
        "the build workflow commits a digest literal"
    )


# --------------------------------------------------------------------------
# The rendered manifests: security, exposure, and what is not in them
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label,spec", ALL_POD_SPECS, ids=lambda v: str(v)[:60])
def test_every_rendered_pod_spec_carries_every_required_field(
    label: str, spec: dict
) -> None:
    for dotted, expected in REQUIRED_POD_SECURITY.items():
        assert _dig(spec, dotted) == expected, f"{label}: {dotted}"
    assert _dig(spec, "securityContext.runAsUser") is not ABSENT, (
        f"{label} declares runAsNonRoot without a uid, which leaves the image to "
        "choose one"
    )
    assert _dig(spec, "securityContext.runAsUser") != 0


@pytest.mark.parametrize("label,container", ALL_CONTAINERS, ids=lambda v: str(v)[:60])
def test_every_rendered_container_carries_every_required_field(
    label: str, container: dict
) -> None:
    for dotted, expected in REQUIRED_CONTAINER_SECURITY.items():
        assert _dig(container, dotted) == expected, f"{label}: {dotted}"
    assert _dig(container, "securityContext.capabilities.drop") == ["ALL"], label
    assert _dig(container, "securityContext.capabilities.add") is ABSENT, label


@pytest.mark.parametrize("label,container", ALL_CONTAINERS, ids=lambda v: str(v)[:60])
def test_every_rendered_image_is_pinned_by_digest(label: str, container: dict) -> None:
    assert DIGEST_PINNED.match(container["image"]), (
        f"{label} names {container['image']}, which is a tag rather than a digest"
    )


@pytest.mark.parametrize("label,container", ALL_CONTAINERS, ids=lambda v: str(v)[:60])
def test_every_rendered_container_states_requests_and_limits(
    label: str, container: dict
) -> None:
    resources = container.get("resources") or {}
    for half in ("requests", "limits"):
        assert set(resources.get(half) or {}) == {"cpu", "memory"}, f"{label}: {half}"


@pytest.mark.parametrize("profile,document", ALL_RENDERED, ids=lambda v: str(v)[:60])
def test_no_rendered_object_exposes_a_service_outside_the_cluster(
    profile: str, document: dict
) -> None:
    assert document["kind"] != "Ingress", "V1 installs no ingress controller"
    if document["kind"] != "Service":
        return
    assert document["spec"]["type"] == "ClusterIP"
    for port in document["spec"].get("ports") or []:
        assert "nodePort" not in port


@pytest.mark.parametrize("profile", sorted(RENDERED))
def test_no_rendered_manifest_carries_a_personal_path_or_a_secret_value(
    profile: str,
) -> None:
    body = (RENDERED_DIR / f"{profile}.expected.yaml").read_text(encoding="utf-8")
    assert not PERSONAL_PATH.search(body), "a rendered manifest names a home directory"
    assert "secretKeyRef" not in body or "value:" not in body
    for shape in ("BEGIN PRIVATE KEY", "BEGIN RSA", "password:", "apiKey:"):
        assert shape not in body, f"{profile} carries {shape!r}"


# --------------------------------------------------------------------------
# The probes, against the records that decide what they may be
# --------------------------------------------------------------------------


def _workload_containers() -> dict[str, dict]:
    """The API and runtime containers from the real render, by name.

    The real profile is used because it is the only one that renders both. Two
    kinds of container are excluded, for the same reason: neither is a workload
    and neither carries a probe. The test hook's, because it is a hook; and the
    model integrity init container's, because an init container runs to
    completion before the kubelet probes anything.
    """
    return {
        container["name"]: container
        for label, container in _containers(INSTALLED["real"])
        if ".containers[" in label
    }


def _init_containers(profile: str) -> dict[str, dict]:
    return {
        container["name"]: container
        for label, container in _containers(INSTALLED[profile])
        if ".initContainers[" in label
    }


def test_every_workload_container_is_probed() -> None:
    """A workload with no liveness probe is a workload nothing restarts."""
    for name, container in _workload_containers().items():
        for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
            assert probe in container, f"{name} has no {probe}"


def test_the_runtime_liveness_probe_is_the_one_the_record_publishes() -> None:
    """The single line in this chart that would be wrong if made consistent.

    `llama-server` answers `/health` with `503` for the whole of a model load:
    correct readiness behaviour, and fatal as a liveness answer. The `V1-S2-007`
    observation recorded 2,753 samples across six starts in which a healthy
    process was loading a model and an HTTP liveness probe would have been
    failing. `runtime-profile.local.v1.json` publishes `health.liveness.kind` as
    `tcp` for that reason, and this compares the chart against it rather than
    against the comment beside it.
    """
    health = RUNTIME_PROFILE["health"]
    runtime = _workload_containers()["runtime"]

    assert health["liveness"]["kind"] == "tcp", (
        "the accepted record no longer publishes a TCP liveness probe; the "
        "chart's mapping was derived from it and has to be re-derived"
    )
    assert "tcpSocket" in runtime["livenessProbe"], (
        "the runtime's liveness probe is an HTTP GET. Its health endpoint "
        "answers 503 throughout a model load, so an HTTP liveness probe fails "
        "for minutes against a healthy process and restarts it into the same load"
    )
    assert "httpGet" not in runtime["livenessProbe"]

    for role in ("startup", "readiness"):
        assert health[role]["kind"] == "http"
        probe = runtime[f"{role}Probe"]
        assert probe["httpGet"]["path"] == health[role]["path"]
        assert probe["httpGet"]["path"] == VALUES["runtime"]["healthPath"]


def test_the_api_probes_ask_the_paths_the_surface_record_assigns() -> None:
    """Liveness and readiness are different questions with published answers.

    `/health/live` answers while the model is loading and while the API is
    draining; `/health/ready` is false whenever either the API or the selected
    adapter is unable. Pointing liveness at the readiness path would restart a
    pod for being not-ready, which is the runtime's defect written in the other
    workload.
    """
    api = _workload_containers()["api"]
    live = API_PATH_FOR_ROLE["liveness"]
    ready = API_PATH_FOR_ROLE["readiness"]

    assert api["livenessProbe"]["httpGet"]["path"] == live
    assert api["startupProbe"]["httpGet"]["path"] == live
    assert api["readinessProbe"]["httpGet"]["path"] == ready
    assert live != ready

    assert VALUES["api"]["livenessPath"] == live
    assert VALUES["api"]["readinessPath"] == ready


def test_the_runtime_startup_budget_covers_the_largest_measured_load() -> None:
    """A budget below a load this project observed is a restart loop.

    Two figures, and they measure different things. `startupBudgetMs` is how long
    the adapter waits for the runtime; the startup probe's budget is how long the
    kubelet waits for the container. A kubelet that gives up first makes the
    adapter's budget unreachable, so the chart refuses that ordering — and the
    kubelet's budget also has to cover a real load, or the refusal is satisfied
    by two numbers that are both too small.
    """
    startup = VALUES["runtime"]["probes"]["startup"]
    assert startup["budgetMs"] >= VALUES["runtime"]["startupBudgetMs"]
    assert startup["budgetMs"] >= LARGEST_MEASURED_LOAD_MS, (
        f"the startup probe budget is {startup['budgetMs']} ms and this project "
        f"has measured a {LARGEST_MEASURED_LOAD_MS} ms model load; a container "
        "would have been killed mid-load in a start that actually happened"
    )


@pytest.mark.parametrize("name", ("api", "runtime"))
def test_the_rendered_startup_threshold_is_the_configured_budget(name: str) -> None:
    """The threshold is derived, so the arithmetic is checked rather than read."""
    container = _workload_containers()[name]
    startup = VALUES[name]["probes"]["startup"]
    probe = container["startupProbe"]
    assert probe["periodSeconds"] == startup["periodSeconds"]
    granted_ms = probe["failureThreshold"] * probe["periodSeconds"] * 1000
    assert granted_ms >= startup["budgetMs"], (
        f"{name}'s startup probe grants {granted_ms} ms against a budget of "
        f"{startup['budgetMs']} ms; a threshold rounded down is a budget the "
        "kubelet does not actually give"
    )


@pytest.mark.parametrize("name", ("api", "runtime"))
def test_no_probe_may_take_longer_than_the_gap_between_probes(name: str) -> None:
    """A probe that overlaps itself makes its failure count mean something else."""
    container = _workload_containers()[name]
    for kind in ("startupProbe", "readinessProbe", "livenessProbe"):
        probe = container[kind]
        assert probe["timeoutSeconds"] < probe["periodSeconds"], f"{name}.{kind}"


# --------------------------------------------------------------------------
# Stopping
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ("api", "runtime"))
def test_the_grace_period_covers_the_pause_and_the_drain(name: str) -> None:
    """A drain that ends in SIGKILL was decoration.

    The API's ordering is readiness-false, drain, exit, with a preStop pause in
    front of it for the endpoint race. The grace period has to cover the pause
    and the drain together. The runtime does not drain, so it only has to
    outlast its own pause.
    """
    lifecycle = VALUES[name]["lifecycle"]
    needed = lifecycle["preStopSleepSeconds"]
    if name == "api":
        needed += -(-VALUES["api"]["drainTimeoutMs"] // 1000)
    assert lifecycle["terminationGracePeriodSeconds"] >= needed
    assert lifecycle["terminationGracePeriodSeconds"] > lifecycle["preStopSleepSeconds"]


@pytest.mark.parametrize("name", ("api", "runtime"))
def test_the_rendered_pod_carries_the_grace_period_and_the_pause(name: str) -> None:
    """A timing configured and not rendered is a timing nothing applies."""
    component = {"api": "platform-api", "runtime": "serving-runtime"}[name]
    spec = next(
        spec
        for _, spec in _pod_specs(INSTALLED["real"])
        for container in spec["containers"]
        if container["name"] == name
    )
    lifecycle = VALUES[name]["lifecycle"]
    assert (
        spec["terminationGracePeriodSeconds"]
        == lifecycle["terminationGracePeriodSeconds"]
    ), component

    container = _workload_containers()[name]
    pre_stop = _dig(container, "lifecycle.preStop")
    assert pre_stop is not ABSENT, f"{name} has no preStop pause"
    assert pre_stop["sleep"]["seconds"] == lifecycle["preStopSleepSeconds"]
    assert "exec" not in pre_stop, (
        "an exec preStop needs a shell inside the image, and no InferOps image "
        "is published to be asked whether it has one"
    )


def test_the_test_hook_image_is_the_pin_this_repository_already_carries() -> None:
    """Two copies of one pin are one pin only until somebody edits one of them.

    The hook needs an HTTP client, and this repository already pins one: four
    committed manifests under `deploy/` use the same `busybox:1.37.0` index
    digest. The chart copies that digest rather than choosing its own, so this
    compares them — a chart that drifted would introduce a second image under a
    name that reads like the first.
    """
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--", "deploy"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode == 0, tracked.stderr
    digests = {
        match
        for line in tracked.stdout.splitlines()
        if line.endswith(".yaml")
        for match in re.findall(
            r"image:\s*busybox:[^@\s]+@(sha256:[0-9a-f]{64})",
            (REPO_ROOT / line).read_text(encoding="utf-8"),
        )
    }
    assert digests, "no busybox pin was found under deploy/; this check read nothing"
    assert len(digests) == 1, f"deploy/ already disagrees with itself: {digests}"
    assert VALUES["tests"]["image"]["digest"] in digests, (
        "the chart's test image is a different busybox from the one this "
        f"repository already pins: {VALUES['tests']['image']['digest']} vs {digests}"
    )
    assert VALUES["model"]["integrity"]["image"]["digest"] in digests, (
        "the model integrity init container is a different busybox from the one "
        "this repository already pins"
    )
    # The repository strings differ deliberately: the chart states a fully
    # qualified name because its schema splits repository from digest, and the
    # manifests state the short name Kubernetes resolves the same way.
    assert VALUES["tests"]["image"]["repository"].endswith("busybox")
    assert VALUES["model"]["integrity"]["image"]["repository"].endswith("busybox")


@pytest.mark.parametrize("name", ("api", "runtime"))
def test_the_rollout_deadline_is_outside_the_startup_budget(name: str) -> None:
    """Three timeouts, and this is the one with a default that disagrees.

    `progressDeadlineSeconds` defaults to 600, and the runtime's startup budget
    is 600 by default too. They are not the same clock: the kubelet is still
    waiting for the container while the Deployment controller has already marked
    the rollout `ProgressDeadlineExceeded`, and an install waiting on that
    rollout reports a failure that is a slow model load.
    """
    budget_seconds = -(-VALUES[name]["probes"]["startup"]["budgetMs"] // 1000)
    deadline = VALUES[name]["lifecycle"]["progressDeadlineSeconds"]
    assert deadline > budget_seconds, (
        f"{name} gives the rollout {deadline} s and the container {budget_seconds} s"
    )

    component = {"api": "platform-api", "runtime": "serving-runtime"}[name]
    rendered = [
        _dig(document, "spec.progressDeadlineSeconds")
        for _profile, document in ALL_INSTALLED
        if document["kind"] == "Deployment"
        and _mapping(document, "metadata.labels").get("app.kubernetes.io/component")
        == component
    ]
    assert rendered, component
    assert all(value == deadline for value in rendered), (
        f"{component} does not carry the configured deadline; the Kubernetes "
        "default of 600 s would apply and it is not derived from anything here"
    )


# --------------------------------------------------------------------------
# The test hook, which is not a resource
# --------------------------------------------------------------------------


@pytest.mark.parametrize("profile", sorted(HOOKS))
def test_every_hook_deletes_itself_and_does_not_retry(profile: str) -> None:
    """A hook that outlived its operation would be residue an uninstall misses.

    That is not a stylistic preference. Helm removes no hook object on
    `helm uninstall` -- there is no delete policy meaning "when the release goes"
    -- so `hook-succeeded` is the only thing standing between a hook and an
    object that outlives the release which created it.

    Two hooks now, where there was one. The test Pod asks the release whether it
    works; the acquisition Job fills the claim the runtime reads, before the
    runtime exists to read it. Neither retries: a test that retried would report
    the retry rather than the failure, and an acquisition that retried would
    repeat either a transfer that ran out of budget or a hash that did not match,
    and the second must not be repeated at all.
    """
    events = {}
    for document in HOOKS[profile]:
        annotations = _dig(document, "metadata.annotations")
        event = annotations[HOOK_ANNOTATION]
        assert event in ("test", "pre-install,pre-upgrade"), event
        policy = annotations["helm.sh/hook-delete-policy"]
        assert "hook-succeeded" in policy, (
            f"{document['kind']} would outlive the release that created it"
        )
        assert "before-hook-creation" in policy
        restart = _dig(document, "spec.restartPolicy")
        if restart is ABSENT:
            restart = _dig(document, "spec.template.spec.restartPolicy")
        # A hook that runs something has to say it will not be run again. A hook
        # that runs nothing -- the acquisition job's ServiceAccount, which exists
        # only so that the Job has an identity to name at hook time -- has no
        # restart policy to state, and demanding one would be demanding a field
        # its kind does not have.
        if restart is not ABSENT or document["kind"] != "ServiceAccount":
            assert restart == "Never", document["kind"]
        events[document["kind"]] = event

    assert events.get("Pod") == "test", "the release test is not a test hook"
    if profile == "real":
        assert events.get("Job") == "pre-install,pre-upgrade", (
            "the acquisition job must complete before the runtime is created"
        )
        job = next(d for d in HOOKS[profile] if d["kind"] == "Job")
        assert _dig(job, "spec.backoffLimit") == 0
        assert _dig(job, "spec.activeDeadlineSeconds") > 0, (
            "an unbounded acquisition holds an install open indefinitely"
        )


def test_the_hook_is_not_counted_as_something_the_release_owns() -> None:
    """The one thing that would quietly break the ownership partition."""
    for profile in sorted(HOOKS):
        for document in HOOKS[profile]:
            component = _mapping(document, "metadata.labels").get(
                "app.kubernetes.io/component"
            )
            assert component in ("release-test", "model-acquisition"), component
            if component == "release-test":
                # The test pod is nobody's inventory row: it exists for the
                # duration of `helm test` and owns nothing. The acquisition job
                # is a row -- it is a hook because of when it has to run, not
                # because it is unowned.
                assert (document["kind"], component) not in ROW_FOR_RENDERED
    for profile in sorted(INSTALLED):
        for document in INSTALLED[profile]:
            assert not _is_hook(document)


def test_the_test_pod_asks_every_service_the_profile_renders() -> None:
    """A test that checked one half would pass on a release with one half up."""
    for profile in sorted(HOOKS):
        services = [
            document["metadata"]["name"]
            for document in INSTALLED[profile]
            if document["kind"] == "Service"
        ]
        assert services, profile
        # The release-test pod specifically. The acquisition job is a hook too,
        # and it asks no Service anything -- it writes a claim.
        test_pods = [
            document
            for document in HOOKS[profile]
            if _mapping(document, "metadata.labels").get("app.kubernetes.io/component")
            == "release-test"
        ]
        body = " ".join(
            argument
            for _, container in _containers(test_pods)
            for argument in container["args"]
        )
        for service in services:
            assert f"//{service}:" in body, (
                f"the {profile} test pod does not ask {service} for anything"
            )


# --------------------------------------------------------------------------
# What a rollback needs to be possible at all
# --------------------------------------------------------------------------


def test_a_selector_is_drawn_only_from_things_a_rollback_cannot_change() -> None:
    """`spec.selector` is immutable after a Deployment is created.

    A selector carrying the chart version, the profile, or anything from
    `commonLabels` would make the next revision a different object rather than an
    update to this one — and revision 1 would then be unreachable by a rollback,
    which is the failure mode that looks like a working chart until somebody
    needs it.
    """
    allowed = {
        "app.kubernetes.io/name",
        "app.kubernetes.io/instance",
        "app.kubernetes.io/component",
    }
    selectors = [
        _dig(document, "spec.selector.matchLabels")
        for _profile, document in ALL_INSTALLED
        if document["kind"] == "Deployment"
    ]
    assert len(selectors) == 4, (
        "three Deployments under real -- API, runtime and collector -- and one "
        "under mock"
    )
    for selector in selectors:
        assert set(selector) == allowed, selector
        assert "inferops.io/profile" not in selector
        assert "helm.sh/chart" not in selector


def test_the_configuration_object_is_named_stably() -> None:
    """A name carrying a hash orphans the old object on every upgrade.

    The checksum belongs on the pod template, where it rolls the pods, and not in
    the ConfigMap's name, where it would leave one object per revision behind and
    make a rollback re-create rather than re-point.
    """
    helpers = (TEMPLATES_DIR / "_helpers.tpl").read_text(encoding="utf-8")
    body = _define_body(helpers, "configMapName")
    for forbidden in ("sha256sum", "Chart.Version", "randAlpha", "now"):
        assert forbidden not in body, body
    for _profile, document in ALL_INSTALLED:
        if document["kind"] != "ConfigMap":
            continue
        name = document["metadata"]["name"]
        assert CHART["version"] not in name, name

    for _profile, document in ALL_INSTALLED:
        if document["kind"] != "Deployment":
            continue
        annotations = _mapping(document, "spec.template.metadata.annotations")
        assert "inferops.io/configuration-checksum" in annotations, (
            "a configuration change would not roll the pods, and the running "
            "processes would keep an environment nothing reports"
        )


# --------------------------------------------------------------------------
# The scrape annotations, which are configuration and not a collector
# --------------------------------------------------------------------------


def test_the_scrape_annotations_follow_the_switch_that_governs_them() -> None:
    """On in one fixture and off in the other, so both branches are committed."""
    keys = {"prometheus.io/scrape", "prometheus.io/port", "prometheus.io/path"}

    assert FIXTURES["real"]["telemetry"]["scrapeAnnotations"] is True
    assert VALUES["telemetry"]["scrapeAnnotations"] is False, (
        "the default has to stay off: nothing in this project collects anything"
    )

    seen = 0
    for profile, expected in (("real", True), ("mock", False)):
        for document in INSTALLED[profile]:
            if document["kind"] != "Deployment":
                continue
            seen += 1
            annotations = _mapping(document, "spec.template.metadata.annotations")
            assert (keys <= set(annotations)) is expected, (
                profile,
                document["metadata"]["name"],
            )
            if not expected:
                continue
            port = int(annotations["prometheus.io/port"])
            container = _dig(document, "spec.template.spec.containers")[0]
            assert port == container["ports"][0]["containerPort"], (
                "the annotated port is not the port the container listens on"
            )
            assert (
                annotations["prometheus.io/path"] == VALUES["telemetry"]["metricsPath"]
            )
    assert seen == 4, (
        "three Deployments under real -- API, runtime and collector -- and one "
        "under mock"
    )


def test_the_scrape_configuration_is_a_config_map_and_not_an_operator_object() -> None:
    """`telemetry-scrape-configuration` is rendered, and it is a plain ConfigMap.

    A ServiceMonitor or a PodMonitor is a custom resource whose CRD belongs to a
    Prometheus Operator installation. Rendering one would make this chart install
    only on a cluster carrying an add-on nobody has chosen -- the collector is
    still the open question `ADR 0004` deliberately leaves open -- and the release
    would fail on a cluster without it. A ConfigMap installs anywhere and is read
    by whatever eventually reads it.
    """
    assert "telemetry-scrape-configuration" in DECLARED_OWNED
    assert "telemetry-scrape-configuration" not in DECLARED_DEFERRED
    for _profile, document in ALL_RENDERED:
        assert document["kind"] not in ("ServiceMonitor", "PodMonitor")


@pytest.mark.parametrize("profile", sorted(INSTALLED))
def test_the_scrape_configuration_is_rendered_once_and_mounted_by_nothing(
    profile: str,
) -> None:
    """A workload publishes metrics. It does not collect them.

    This used to require that nothing mounted the scrape configuration, and that
    was the honest reading while nothing consumed it -- a ConfigMap mounted into
    the pod it describes would suggest the pod reads its own scrape configuration.
    The collector reads it now, which is the whole of what the Sprint 3
    remediation changed, so the rule became the sharper one it was standing in
    for: **no workload pod mounts it, and the only pod that does is the
    collector**. A release with two copies of its scrape configuration would be a
    release where the one that drifted is whichever nobody read.
    """
    configured = [
        document
        for document in INSTALLED[profile]
        if document["kind"] == "ConfigMap"
        and _mapping(document, "metadata.labels").get("app.kubernetes.io/component")
        == "telemetry-scrape-configuration"
    ]
    assert len(configured) == 1
    name = configured[0]["metadata"]["name"]
    assert set(configured[0]["data"]) == {"scrape-config.yaml", "recording-rules.yaml"}

    readers = []
    # Identified by the component label rather than by a name suffix: a future
    # workload whose fullname happened to end in `-collector` would satisfy a
    # suffix test without being the collector.
    collector_objects = {
        f"{document['kind']}/{_dig(document, 'metadata.name')}"
        for document in RENDERED[profile]
        if _mapping(document, "metadata.labels").get("app.kubernetes.io/component")
        == "telemetry-collector"
    }

    for label, spec in _pod_specs(RENDERED[profile]):
        component = label in collector_objects
        for volume in spec.get("volumes") or []:
            source = volume.get("configMap") or {}
            if source.get("name") != name:
                continue
            readers.append(label)
            assert component, (
                f"{label} mounts the scrape configuration, and it is not the "
                "collector; a workload publishes metrics and does not collect them"
            )
    if profile == "real":
        assert len(readers) == 1, readers
    else:
        assert not readers, "a mock renders no collector and nothing reads it"
    for _label, spec in _pod_specs(RENDERED[profile]):
        for container in spec.get("containers") or []:
            for source in container.get("envFrom") or []:
                assert (source.get("configMapRef") or {}).get("name") != name


def test_switching_collection_off_renders_no_scrape_configuration() -> None:
    """The switch is a switch, and the resource it governs is the whole resource."""
    result = _render("telemetry.collection.enabled=false")
    assert result.returncode == 0, result.stderr
    assert "telemetry-scrape-configuration" not in result.stdout


def test_the_collector_allowance_is_one_from_item_and_defaults_to_absent() -> None:
    """Two selectors in one `from` item are ANDed; two items are ORed.

    Written as two items the rule would mean "any pod in that namespace, or any pod
    anywhere with those labels", which is a materially wider hole and reads
    identically in a `kubectl get networkpolicy -o yaml`.
    """
    collector = VALUES["telemetry"]["collection"]["collector"]
    assert collector["namespace"] == ""
    assert collector["podSelector"] == {}
    assert collector["deploy"] is False, (
        "the shipped default installs no collector: a release that quietly "
        "started a second workload would be deciding for its operator"
    )

    # With the defaults, no allowance is rendered at all. The real profile turns
    # the collector on, and then the allowance names the collector this release
    # itself installs -- which is the case the two-selector rule below is about,
    # because that one really is a `namespaceSelector` beside a `podSelector`.
    for _profile, document in ALL_RENDERED:
        if document["kind"] != "NetworkPolicy":
            continue
        for rule in _sequence(document, "spec.ingress"):
            for source in rule.get("from") or []:
                if "namespaceSelector" not in source:
                    continue
                assert "podSelector" in source, (
                    "a namespace is opened without naming which pods in it"
                )
                assert (
                    source["podSelector"]["matchLabels"].get(
                        "app.kubernetes.io/component"
                    )
                    == "telemetry-collector"
                ), source

    # `deploy=false` as well, because the two are alternatives: a release that
    # installs its own collector names that one, and an override pointing
    # somewhere else would be a rule for a collector that is not the one running.
    result = _render(
        "telemetry.collection.collector.deploy=false",
        "telemetry.collection.collector.namespace=observability",
        "telemetry.collection.collector.podSelector.app=prometheus",
    )
    assert result.returncode == 0, result.stderr
    documents = [d for d in yaml.safe_load_all(result.stdout) if d]
    allowances = [
        source
        for document in documents
        if document["kind"] == "NetworkPolicy"
        for rule in _sequence(document, "spec.ingress")
        for source in rule.get("from") or []
        if "namespaceSelector" in source
    ]
    assert len(allowances) == 2, "one allowance per workload policy, API and runtime"
    for source in allowances:
        assert set(source) == {"namespaceSelector", "podSelector"}
        assert source["namespaceSelector"]["matchLabels"] == {
            "kubernetes.io/metadata.name": "observability"
        }
        assert source["podSelector"]["matchLabels"] == {"app": "prometheus"}


@pytest.mark.parametrize(
    "override,expected",
    [
        ("telemetry.collection.scrapeTimeoutSeconds=30", "shorter than"),
        (
            "telemetry.collection.collector.namespace=observability",
            "podSelector is required",
        ),
    ],
)
def test_a_collection_refusal_names_the_value_and_the_failure(
    override: str, expected: str
) -> None:
    """Every rule fails the render. There is none that warns, and none that
    substitutes a default."""
    result = _render(override)
    assert result.returncode != 0, "the render was accepted and should not have been"
    assert expected in result.stderr


# --------------------------------------------------------------------------
# The flag that would give one resource two owners
# --------------------------------------------------------------------------


# The flag, on a line that is not a comment. It is deliberately not matched
# against `helm` on the same line: a shell continuation puts the flag on a line
# of its own, which is exactly how a real one would be written, and a rule that
# needed both on one line would miss it.
#
# Prose that forbids the flag has to be able to name it, and `Chart.yaml`,
# `_validate.tpl`, the chart README, and CONTRIBUTING all do. So this reads the
# two places that run commands rather than describe them.
COMMENT = re.compile(r"^\s*#")
RUNNABLE_ROOTS = ("scripts", ".github")


def test_nothing_that_runs_passes_create_namespace() -> None:
    """One flag, and it is the default suggestion in most documentation.

    `helm install --create-namespace` makes Helm an owner of a namespace the
    ownership inventory assigns to Terraform, and the release's own uninstall
    then deletes a prerequisite. The chart cannot refuse a flag that creates the
    namespace it is being installed into, so the refusal has to live here — and
    in `tests/architecture/test_cluster_lifecycle_safety.py`, which reads the
    same rule off shell commands with their continuations joined.
    """
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--", *RUNNABLE_ROOTS],
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode == 0, tracked.stderr
    paths = [
        REPO_ROOT / line
        for line in tracked.stdout.splitlines()
        if line and not line.endswith(".md")
    ]
    assert len(paths) >= 5, "the file list is empty; this check would pass on air"

    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{number}"
        for path in paths
        if path.is_file()
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if "--create-namespace" in line and not COMMENT.match(line)
    ]
    assert not offenders, offenders


@pytest.mark.parametrize(
    "sample",
    (
        "helm install inferops charts/inferops-llm --create-namespace",
        "  --create-namespace \\",
        '  inferops::helm upgrade --install "${R}" "${C}" --create-namespace -n x',
    ),
)
def test_the_create_namespace_rule_rejects_what_it_exists_to_reject(
    sample: str,
) -> None:
    """A rule that has never been shown a violation may not have one.

    The second sample is the shape the first version of this rule let through: a
    shell continuation, with the flag on a line carrying nothing else.
    """
    assert "--create-namespace" in sample and not COMMENT.match(sample), sample


@pytest.mark.parametrize(
    "sample",
    (
        "# --create-namespace is deliberately absent and must stay absent.",
        "  # rather than passing `--create-namespace`, which would hand the",
    ),
)
def test_the_create_namespace_rule_accepts_a_comment_that_names_it(
    sample: str,
) -> None:
    assert COMMENT.match(sample), sample


# --------------------------------------------------------------------------
# Drift, when the tool that produced the snapshots is available
# --------------------------------------------------------------------------


@pytest.mark.parametrize("profile", sorted(RENDERED))
def test_the_committed_render_matches_what_helm_produces(profile: str) -> None:
    """The snapshots are committed output. This is what keeps them output.

    Skipped where `helm` is absent, which is the arrangement `kubeconform` and
    `shellcheck` already have: not vendored, named in CONTRIBUTING, and run by
    whoever has them. Everything asserted above runs either way.
    """
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is not on PATH; see CONTRIBUTING.md for the commands")
    # A fixed argument vector with no shell: `helm` is resolved from PATH by
    # `shutil.which` and every other member is a constant or a repository path.
    result = subprocess.run(
        [
            helm,
            "template",
            "inferops",
            str(CHART_DIR),
            "--namespace",
            "inferops-platform",
            "--values",
            str(CI_DIR / f"{profile}-values.yaml"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    produced = result.stdout.replace("\r\n", "\n")
    expected = (RENDERED_DIR / f"{profile}.expected.yaml").read_text(encoding="utf-8")
    assert produced == expected, (
        f"the committed {profile} render is out of date. Regenerate it with the "
        "command in charts/inferops-llm/ci/rendered/README.md"
    )


# --------------------------------------------------------------------------
# The identities, and the policy that starts from a denial
# --------------------------------------------------------------------------


def test_each_workload_presents_an_identity_of_its_own() -> None:
    """One service account per workload, and never one shared between two.

    Neither is granted anything today, so this establishes no privilege
    difference: what it establishes is that a RoleBinding written for one
    workload cannot reach the other, which is the failure a shared account
    produces the first time somebody grants anything at all.
    """
    for profile, documents in INSTALLED.items():
        accounts = {
            _dig(d, "metadata.name") for d in documents if d["kind"] == "ServiceAccount"
        }
        named = {_dig(spec, "serviceAccountName") for _, spec in _pod_specs(documents)}
        assert None not in named and ABSENT not in named, (
            f"{profile} renders a pod specification naming no service account"
        )
        assert "default" not in named, (
            f"{profile} names the namespace's shared default account"
        )
        assert named <= accounts, (
            f"{profile} names an account this release does not render: "
            f"{sorted(named - accounts)}"
        )
        # API, runtime, and the collector the real profile installs.
        expected = 3 if profile == "real" else 1
        assert len(accounts) == expected, (
            f"{profile} renders {len(accounts)} service accounts, expected {expected}"
        )
        workloads = [
            (label, spec)
            for label, spec in _pod_specs(documents)
            if "connection-test" not in label
        ]
        chosen = [_dig(spec, "serviceAccountName") for _, spec in workloads]
        assert len(set(chosen)) == len(chosen), (
            f"{profile} points two workloads at one identity: {chosen}"
        )


def test_the_chart_grants_exactly_one_identity_exactly_one_permission() -> None:
    """This used to assert that the chart granted nothing at all. It grants one thing.

    The collector discovers its targets through the Kubernetes API, so it needs a
    permission, and a chart that granted nothing could not have one. What replaces
    "nothing" is not "something": it is this exact list, checked. A `ClusterRole`
    or a `ClusterRoleBinding` is still refused outright -- namespace-scoped is not
    a restriction the collector works around, it is the whole of what it needs --
    and every other identity this chart renders is still bound to nothing.

    The verbs matter as much as the resources. `get`, `list` and `watch` on pods
    is what service discovery reads; anything that could create, patch or delete
    would be a collector that could change the release it observes.
    """
    for profile, documents in RENDERED.items():
        cluster_scoped = [
            d["kind"]
            for d in documents
            if d["kind"] in {"ClusterRole", "ClusterRoleBinding"}
        ]
        assert not cluster_scoped, (
            f"{profile} renders {cluster_scoped}, which grants something outside "
            "this namespace"
        )

        roles = [d for d in documents if d["kind"] == "Role"]
        bindings = [d for d in documents if d["kind"] == "RoleBinding"]
        if profile == "mock":
            assert not roles and not bindings, (
                "a mock collects nothing and needs nothing"
            )
            continue

        assert len(roles) == 1 and len(bindings) == 1, (roles, bindings)
        assert _sequence(roles[0], "rules") == [
            {
                "apiGroups": [""],
                "resources": ["pods"],
                "verbs": ["get", "list", "watch"],
            }
        ], "the collector's permission is not the one this test permits"

        # And it is bound to the collector's account and to nothing else.
        collector_account = f"{_dig(roles[0], 'metadata.name')}"
        subjects = _sequence(bindings[0], "subjects")
        assert [s["name"] for s in subjects] == [collector_account], subjects
        assert _dig(bindings[0], "roleRef.kind") == "Role"

    for label, spec in ALL_POD_SPECS:
        assert _dig(spec, "automountServiceAccountToken") is False, (
            f"{label} mounts a service account token it has no use for"
        )


def _policies(documents: list[dict]) -> list[dict]:
    return [d for d in documents if d["kind"] == "NetworkPolicy"]


@pytest.mark.parametrize("profile", sorted(INSTALLED))
def test_the_release_denies_both_directions_before_it_opens_anything(
    profile: str,
) -> None:
    """A deny that names only `Ingress` leaves egress wide open.

    That is the mistake this asserts against rather than a hypothetical one: the
    two halves are separate entries in `policyTypes`, omitting one is a single
    missing line, and the object still reads as a default-deny in a diff.
    """
    denies = [
        policy
        for policy in _policies(INSTALLED[profile])
        if not _sequence(policy, "spec.ingress")
        and not _sequence(policy, "spec.egress")
        and set(_sequence(policy, "spec.policyTypes")) == {"Ingress", "Egress"}
    ]
    assert len(denies) == 1, (
        f"{profile} renders {len(denies)} policies that deny both directions and "
        "open nothing; there should be exactly one"
    )
    selector = _mapping(denies[0], "spec.podSelector.matchLabels")
    assert selector, (
        "the default-deny selects every pod in the namespace, including "
        "Terraform-owned prerequisites this chart does not own"
    )
    assert "app.kubernetes.io/component" not in selector, (
        "the default-deny names a component, so it would stop covering the day a "
        "component is added -- and the uncovered pod would be the new one"
    )
    for document in INSTALLED[profile]:
        if not isinstance(_dig(document, "spec.template.spec"), dict):
            continue
        labels = _mapping(document, "spec.template.metadata.labels")
        for key, value in selector.items():
            assert labels.get(key) == value, (
                f"{_subject(document)} is not selected by the default-deny policy, "
                "so the release installs a pod nothing denies by default"
            )


def test_the_serving_runtime_is_given_no_egress_allowance() -> None:
    """`llama-server` reads a mounted file and answers a socket.

    It resolves no name and calls no API, so an egress rule it never uses would
    be a hole with no purpose. The acquisition path that would download is a
    separate Job, deferred, and it would carry its own policy.
    """
    runtime = [
        policy
        for policy in _policies(INSTALLED["real"])
        if _mapping(policy, "spec.podSelector.matchLabels").get(
            "app.kubernetes.io/component"
        )
        == "serving-runtime"
    ]
    assert len(runtime) == 1, "one policy names the serving runtime"
    assert not _sequence(runtime[0], "spec.egress"), (
        "the runtime policy opens an egress path the runtime does not use"
    )
    assert "Egress" not in _sequence(runtime[0], "spec.policyTypes"), (
        "the runtime policy restates the egress denial the default-deny already "
        "holds, which reads as a second decision where there is one"
    )


@pytest.mark.parametrize("profile", sorted(INSTALLED))
def test_every_policy_that_denies_egress_still_permits_name_resolution(
    profile: str,
) -> None:
    """The failure that makes people give up on network policy.

    Everything here is reached by Service name, so an egress denial with no DNS
    rule denies everything -- and it surfaces as a connection error rather than
    as a policy error. Both protocols, because a resolver falls back to TCP for
    a large answer and a UDP-only rule fails intermittently.
    """
    openers = [
        policy
        for policy in _policies(INSTALLED[profile])
        if _sequence(policy, "spec.egress")
    ]
    assert openers, f"{profile} renders no policy that opens an egress path"
    for policy in openers:
        rules = _sequence(policy, "spec.egress")
        peers = [
            peer
            for rule in rules
            for peer in rule.get("to") or []
            if "namespaceSelector" in peer and "podSelector" in peer
        ]
        assert peers, (
            f"{_dig(policy, 'metadata.name')} opens egress and names no resolver, "
            "so every Service name it reaches by would fail to resolve"
        )
        for peer in peers:
            assert _mapping(peer, "namespaceSelector.matchLabels"), (
                "an empty namespace selector matches every namespace"
            )
            assert _mapping(peer, "podSelector.matchLabels"), (
                "an empty pod selector matches every pod in those namespaces"
            )
        dns_rule = next(
            rule
            for rule in rules
            if any("namespaceSelector" in peer for peer in rule.get("to") or [])
        )
        protocols = {port["protocol"] for port in dns_rule["ports"]}
        assert protocols == {"UDP", "TCP"}, (
            "a resolver falls back to TCP for a large answer, so a UDP-only rule "
            "fails intermittently and for a reason nobody would look for here"
        )


def test_no_policy_reaches_outside_the_release_or_the_resolver() -> None:
    """A policy is scoped to this release, and the exceptions are named.

    Every peer is either a pod carrying this release's labels or the cluster
    resolver. An `ipBlock` reaches an address range this chart cannot see the
    membership of, and a bare `namespaceSelector` opens a whole namespace.

    **One policy is allowed an `ipBlock`, and only one.** The acquisition job's
    whole purpose is to fetch an artifact from outside the cluster, so a rule
    confining it to release pods would confine it to failing. That exception is
    bounded rather than granted: it is checked separately, below, for the exact
    port and the exact excluded ranges. Every other policy is held to the
    original rule, and a second policy acquiring an `ipBlock` fails here.
    """
    for profile, documents in INSTALLED.items():
        for policy in _policies(documents):
            reaches_out = policy["metadata"]["name"].endswith("-model-acquisition")
            for direction in ("ingress", "egress"):
                for rule in _sequence(policy, f"spec.{direction}"):
                    for peer in rule.get("to") or rule.get("from") or []:
                        if "ipBlock" in peer:
                            assert reaches_out, (
                                f"{profile}/{policy['metadata']['name']} opens an "
                                "address range rather than a pod set"
                            )
                            continue
                        if "namespaceSelector" in peer:
                            assert "podSelector" in peer, (
                                f"{profile} opens a whole namespace; the resolver "
                                "rule names a namespace AND a pod set"
                            )
                            continue
                        selector = _mapping(peer, "podSelector.matchLabels")
                        assert selector.get("app.kubernetes.io/instance"), (
                            f"{profile} opens a path to a pod outside this release"
                        )


# --------------------------------------------------------------------------
# The two settings that could hand the chart's own gate a release it refuses
# --------------------------------------------------------------------------


def _render(*overrides: str) -> subprocess.CompletedProcess[str]:
    """`helm template` with the real fixture and some `--set` overrides.

    A fixed argument vector with no shell: `helm` is resolved from PATH by
    `shutil.which` and every other member is a constant or a repository path.
    """
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is not on PATH; see CONTRIBUTING.md for the commands")
    argv = [
        helm,
        "template",
        "inferops",
        str(CHART_DIR),
        "--namespace",
        "inferops-platform",
        "--values",
        str(CI_DIR / "real-values.yaml"),
    ]
    for override in overrides:
        argv.extend(["--set", override])
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def test_an_unnamed_external_service_account_is_refused_rather_than_defaulted() -> None:
    """The escape hatch that used to defeat the control it sits beside.

    `security.serviceAccount.create: false` is documented, schema-legal, and
    exists for a cluster that provisions accounts elsewhere. With no names it
    used to point every pod at the namespace's `default` account -- so the chart
    rendered a release its own workload policy refuses, once per pod, and
    nothing said so. Independent review found it.

    A control a supported setting can switch off is a control that holds by
    default. The render is now refused instead, and naming `default` explicitly
    is refused too: a rule that only catches the omission teaches the workaround.
    """
    unnamed = _render("security.serviceAccount.create=false")
    assert unnamed.returncode != 0, (
        "create=false with no names renders, and what it renders is a release "
        "whose pods all present the namespace's shared identity"
    )
    assert "security.serviceAccount.api.name is required" in unnamed.stderr

    explicit = _render(
        "security.serviceAccount.create=false",
        "security.serviceAccount.api.name=default",
        "security.serviceAccount.runtime.name=external-runtime",
    )
    assert explicit.returncode != 0, "naming 'default' reaches the same place"
    assert "may not be 'default'" in explicit.stderr


def test_externally_provisioned_accounts_still_render_and_still_pass() -> None:
    """The half of the escape hatch that was worth keeping.

    Refusing the unnamed case would be worthless if it also refused the case the
    setting exists for, so this renders it and puts the result through the same
    validator the story ships.
    """
    result = _render(
        "security.serviceAccount.collector.name=external-collector",
        "security.serviceAccount.create=false",
        "security.serviceAccount.api.name=external-api",
        "security.serviceAccount.runtime.name=external-runtime",
    )
    assert result.returncode == 0, result.stderr
    documents = [
        document
        for document in yaml.safe_load_all(result.stdout.replace("\r\n", "\n"))
        if isinstance(document, dict)
    ]
    named = {_dig(spec, "serviceAccountName") for _, spec in _pod_specs(documents)}
    assert named == {"external-api", "external-runtime", "external-collector"}, named
    assert not [d for d in documents if d["kind"] == "ServiceAccount"], (
        "create=false must render no account; the cluster provisions them"
    )
    assert not check_documents(documents), (
        "a release naming externally provisioned accounts is refused by the "
        "policy, which would make the supported configuration unusable"
    )


def test_switching_the_network_policy_off_is_a_trade_the_gate_reports() -> None:
    """`networkPolicy.enabled: false` is a real choice and it gives up a control.

    It is not refused: a policy object a cluster ignores is clutter that reads
    as a control, and an operator on such a cluster may reasonably want none.
    What must not happen is the release quietly losing the property. It does not:
    the workload policy refuses the render, once per workload, and this asserts
    that rather than leaving the trade to a sentence in a values file.
    """
    result = _render("security.networkPolicy.enabled=false")
    assert result.returncode == 0, result.stderr
    documents = [
        document
        for document in yaml.safe_load_all(result.stdout.replace("\r\n", "\n"))
        if isinstance(document, dict)
    ]
    assert not [d for d in documents if d["kind"] == "NetworkPolicy"]
    findings = check_documents(documents)
    assert findings, "the release lost its default-deny and nothing reported it"
    assert {finding.rule for finding in findings} == {
        "network-policy-in-the-release-namespace"
    }, "switching the policy off should cost exactly the policy control"


def test_the_one_policy_that_reaches_outside_is_bounded_to_what_it_fetches() -> None:
    """The acquisition job's exception, checked rather than trusted.

    It may reach the publisher and the resolver, and nothing else. Every private
    range is excepted, so the rule cannot be a path to the API server, to the
    node, or to a pod in another namespace -- which is what an unqualified
    `0.0.0.0/0` would be. The port is 443 alone: the transport is not
    certificate-validated, the content hash is the whole of the defence, and this
    rule bounds where the job may reach rather than what it may believe.
    """
    policies = [
        policy
        for policy in _policies(INSTALLED["real"])
        if policy["metadata"]["name"].endswith("-model-acquisition")
    ]
    assert len(policies) == 1, "the real profile renders one acquisition policy"
    policy = policies[0]

    # The exemption above is keyed on the policy's name, so the name has to be
    # bound to the pods it actually selects. Without this, a second policy
    # renamed to end in `-model-acquisition` would inherit the right to open an
    # address range, and this one could be widened to select every pod in the
    # release while keeping its name.
    job = next(d for d in HOOKS["real"] if d["kind"] == "Job")
    job_labels = _mapping(job, "spec.template.metadata.labels")
    selector = _mapping(policy, "spec.podSelector.matchLabels")
    assert selector, "the acquisition policy selects every pod in the namespace"
    assert selector.items() <= job_labels.items(), {
        "policy selects": selector,
        "the job's pods carry": job_labels,
    }
    assert selector.get("app.kubernetes.io/component") == "model-acquisition", selector

    assert _sequence(policy, "spec.policyTypes") == ["Egress"], (
        "an acquisition job accepts no connections"
    )

    blocks = [
        peer["ipBlock"]
        for rule in _sequence(policy, "spec.egress")
        for peer in rule.get("to") or []
        if "ipBlock" in peer
    ]
    assert len(blocks) == 1, blocks
    assert set(blocks[0]["except"]) == {
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
    }, "a private range is reachable from the acquisition job"

    ports = {
        (port.get("port"), port.get("protocol"))
        for rule in _sequence(policy, "spec.egress")
        for peer in rule.get("to") or []
        if "ipBlock" in peer
        for port in rule.get("ports") or []
    }
    assert ports == {(443, "TCP")}, ports

    assert not [
        policy
        for policy in _policies(INSTALLED["mock"])
        if policy["metadata"]["name"].endswith("-model-acquisition")
    ], "a mock acquires nothing and needs no path out of the cluster"


@pytest.mark.parametrize(
    "hostile",
    (
        pytest.param("https://h/x';id;'", id="apostrophe-closes-the-shell-quote"),
        pytest.param("https://h/x;id", id="semicolon"),
        pytest.param("https://h/x$(id)", id="command-substitution"),
        pytest.param("https://h/x`id`", id="backtick"),
        pytest.param("https://h/x&id", id="ampersand"),
        pytest.param("https://h/x|id", id="pipe"),
        pytest.param("http://h/x", id="plaintext-transport"),
    ),
)
def test_a_source_url_that_could_reach_a_shell_is_refused(hostile: str) -> None:
    """`sourceUrl` is interpolated into a single-quoted argument in the job's script.

    Independent review found the pattern copied from RFC 3986's legal-URI
    alphabet, which includes the apostrophe. That closes the quote, and the rest
    of the URL is read as commands -- inside the very script whose SHA-256
    comparison is the only thing standing between the job and a substituted file.
    Shell access there does not merely bypass the check; it can write the bytes
    the check was protecting.

    The chart's own history records the identical bug in `cache.mountPath`, found
    by review, fixed by closing the character class. This is that fix applied
    where it was missed, and these are the characters it was missed for.
    """
    result = _render(f"model.artifact.sourceUrl={hostile}")
    assert result.returncode != 0, (
        f"the chart rendered a sourceUrl that reaches a shell: {hostile!r}"
    )


def test_the_committed_source_url_is_the_one_the_record_publishes() -> None:
    """A chart and a source record naming different bytes is two pinned artifacts."""
    import json

    record = json.loads(
        (REPO_ROOT / "docs" / "serving" / "model-source.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert FIXTURES["real"]["model"]["artifact"]["sourceUrl"] == record["sourceUrl"]
    assert FIXTURES["real"]["model"]["license"]["spdx"] == record["license"]["spdx"]
    assert (
        FIXTURES["real"]["model"]["license"]["reference"]
        == record["license"]["reference"]
    )
