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
# `V1-S2-005` baseline run on the reference host. The cold and warm start
# observation recorded 133,515 ms to 215,672 ms across six starts, and that run
# recorded 358,735 ms and 284,406 ms on the same host.
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


RENDERED = {
    profile: _documents(RENDERED_DIR / f"{profile}.expected.yaml")
    for profile in ("mock", "real")
}


def _is_hook(document: dict) -> bool:
    return HOOK_ANNOTATION in (_dig(document, "metadata.annotations") or {})


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
    ("ConfigMap", "runtime-configuration"): "runtime-configuration",
    ("Deployment", "platform-api"): "platform-api-deployment",
    ("Service", "platform-api"): "platform-api-service",
    ("Deployment", "serving-runtime"): "serving-runtime-deployment",
    ("Service", "serving-runtime"): "serving-runtime-service",
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
    assert len(INSTALLED["real"]) == 6, "the real profile installs six objects"
    assert len(INSTALLED["mock"]) == 4, "the mock profile installs four"
    assert len(HOOKS["real"]) == 1, "one test hook, in both profiles"
    assert len(HOOKS["mock"]) == 1
    assert len(ALL_CONTAINERS) == 5


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
        labels = _dig(document, "metadata.labels") or {}
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
    """Referencing is not owning, and this is the one place it is easy to blur."""
    volumes = [
        volume
        for _, spec in _pod_specs(RENDERED["real"])
        for volume in spec.get("volumes") or []
    ]
    claims = [v for v in volumes if "persistentVolumeClaim" in v]
    assert len(claims) == 1, "the real profile mounts exactly one claim"
    claim = claims[0]["persistentVolumeClaim"]
    assert claim["claimName"] == FIXTURES["real"]["model"]["cache"]["claimName"]
    assert claim["readOnly"] is True, (
        "a serving replica that could write the model cache is a second writer "
        "nobody decided on; the acquisition job is the one sanctioned writer"
    )


def test_every_rendered_object_carries_the_isolation_and_lifecycle_labels() -> None:
    """ADR 0001 D5's label, plus the release half of the second one.

    The ownership document records that a scoped sweep matching
    `app.kubernetes.io/part-of=inferops` across `inferops-` namespaces would
    reach Terraform-owned prerequisites, and that the fix is a second label. This
    is the release side of it. The prerequisite side does not exist and is not
    claimed to: Terraform is not written, and the environment scripts' sweep
    stays bound to the smoke namespace until it is.
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
        labels = _dig(document, "metadata.labels") or {}
        assert not any("tenant" in key for key in labels), profile
        annotations = _dig(document, "metadata.annotations") or {}
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
    assert kinds == ["ConfigMap", "Deployment", "Service", "ServiceAccount"], (
        "the mock profile installs the API alone; the test hook is not installed "
        "and is checked separately"
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
        labels = _dig(document, "metadata.labels") or {}
        assert labels["inferops.io/profile"] == "real"


def test_each_fixture_declares_what_its_profile_permits() -> None:
    mock = FIXTURES["mock"]
    assert mock["profile"] == "mock"
    assert mock["model"]["identifier"].startswith("mock-")
    assert "revision" not in mock["model"]
    assert "alias" not in mock["model"]
    assert "containerPath" not in mock["model"]
    assert "cache" not in mock["model"]
    assert "security" not in mock

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
        written_labels |= set(_dig(document, "metadata.labels") or {})
        written_annotations |= set(_dig(document, "metadata.annotations") or {})
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
    assert model["containerPath"] == RUNTIME_PROFILE["model"]["containerPath"]
    assert model["containerPath"].endswith(MODEL_SOURCE["file"])


def test_the_api_image_digest_in_the_fixtures_is_the_documented_placeholder() -> None:
    """The fixtures say the API digest is a placeholder. This recomputes it.

    No InferOps image is published: `platform-api-container-image` is `planned`
    in the inventory and no Dockerfile is committed. The fixtures still have to
    satisfy the chart's digest refusal, so they carry the SHA-256 of a stated
    string rather than a plausible-looking digest — which is the difference
    between a placeholder a reader can verify and one they have to trust.
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
    # `Dockerfile` belonging to somebody else's package would fail this for a
    # reason that has nothing to do with whether InferOps publishes an image.
    assert tracked.returncode == 0, tracked.stderr
    assert not tracked.stdout.strip(), (
        "a Dockerfile is committed, so the reason the API image is a placeholder "
        "no longer holds"
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

    The real profile is used because it is the only one that renders both. The
    test hook's container is excluded: it is not a workload and carries no probe.
    """
    return {
        container["name"]: container for _, container in _containers(INSTALLED["real"])
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


# --------------------------------------------------------------------------
# The test hook, which is not a resource
# --------------------------------------------------------------------------


@pytest.mark.parametrize("profile", sorted(HOOKS))
def test_the_only_hook_is_a_test_and_it_deletes_itself(profile: str) -> None:
    """A hook that outlived its operation would be residue an uninstall misses."""
    for document in HOOKS[profile]:
        annotations = _dig(document, "metadata.annotations")
        assert annotations[HOOK_ANNOTATION] == "test", (
            "the only hook this chart renders is a test. An install or upgrade "
            "hook would run against a cluster as part of a release, and nothing "
            "here has established what that should do"
        )
        policy = annotations["helm.sh/hook-delete-policy"]
        assert "hook-succeeded" in policy
        assert "before-hook-creation" in policy
        assert document["kind"] == "Pod"
        assert _dig(document, "spec.restartPolicy") == "Never", (
            "a test that retries reports the retry rather than the failure"
        )


def test_the_hook_is_not_counted_as_something_the_release_owns() -> None:
    """The one thing that would quietly break the ownership partition."""
    for profile in sorted(HOOKS):
        for document in HOOKS[profile]:
            component = (_dig(document, "metadata.labels") or {}).get(
                "app.kubernetes.io/component"
            )
            assert component == "release-test"
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
        body = " ".join(
            argument
            for _, container in _containers(HOOKS[profile])
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
    assert len(selectors) == 3, "two Deployments under real, one under mock"
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
    assert seen == 3, "two Deployments under real, one under mock"


def test_no_scrape_resource_is_rendered() -> None:
    """`telemetry-scrape-configuration` is deferred, and stays deferred.

    Pod annotations are a field on a workload. A ServiceMonitor, a PodMonitor, or
    a scrape config is a resource beside it, and choosing one is `V1-S3-007`'s.
    """
    assert "telemetry-scrape-configuration" in DECLARED_DEFERRED
    for _profile, document in ALL_RENDERED:
        assert document["kind"] not in ("ServiceMonitor", "PodMonitor")


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
