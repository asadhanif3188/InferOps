"""The Helm chart against the ownership inventory and the accepted pins.

This suite reads files. It renders nothing by itself, contacts no cluster, pulls
no image, and installs nothing, so a passing run here is `local-static` evidence
about a chart and says nothing whatever about a release. Whether this chart
installs and uninstalls is `V1-S3-002-PR2`'s question and is answered by running
it, not by reading it.

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


RENDERED = {
    profile: _documents(RENDERED_DIR / f"{profile}.expected.yaml")
    for profile in ("mock", "real")
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


def _dig(node: object, dotted: str) -> Any:
    current = node
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return ABSENT
        current = current[part]
    return current


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
    assert len(RENDERED["real"]) == 6, "the real profile renders six objects"
    assert len(RENDERED["mock"]) == 4, "the mock profile renders four"
    assert len(ALL_CONTAINERS) == 3


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


@pytest.mark.parametrize("profile", sorted(RENDERED))
def test_every_rendered_object_maps_to_a_helm_owned_row(profile: str) -> None:
    for document in RENDERED[profile]:
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
    kinds = sorted(document["kind"] for document in RENDERED["mock"])
    assert kinds == ["ConfigMap", "Deployment", "Service", "ServiceAccount"]
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
    configuration = next(
        document for document in RENDERED["real"] if document["kind"] == "ConfigMap"
    )["data"]
    assert not configuration["INFEROPS_MODEL_IDENTIFIER"].lower().startswith("mock-")
    assert "mock" not in (RENDERED_DIR / "real.expected.yaml").read_text("utf-8")


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
    assert not list(REPO_ROOT.glob("**/Dockerfile")), (
        "a Dockerfile appeared, so the reason the API image is a placeholder no "
        "longer holds"
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


def test_no_probe_is_rendered_and_the_deferral_is_recorded() -> None:
    """The absence is the point, and it is an argued absence.

    The feasibility trial found that the runtime's health endpoint returns 503
    while loading: correct readiness behaviour, wrong liveness behaviour, so a
    liveness probe aimed at it restarts the pod mid-load and never converges.
    Choosing the mapping is `V1-S3-002-PR2`'s work, and a probe added here
    without that argument would be the defect the trial already found.
    """
    for _, container in ALL_CONTAINERS:
        for probe in ("readinessProbe", "livenessProbe", "startupProbe"):
            assert probe not in container, (
                f"a {probe} is rendered; probes belong to V1-S3-002-PR2, where "
                "the mapping is argued rather than assumed"
            )
    assert VALUES["api"]["probes"]["enabled"] is False


def test_no_service_account_token_is_mounted_anywhere() -> None:
    account = next(
        document
        for document in RENDERED["real"]
        if document["kind"] == "ServiceAccount"
    )
    assert account["automountServiceAccountToken"] is False
    for _, spec in ALL_POD_SPECS:
        assert spec["automountServiceAccountToken"] is False


def test_the_chart_grants_the_service_account_nothing() -> None:
    """No Role and no RoleBinding is rendered, and none is a template.

    Least-privilege RBAC is `V1-S3-004`'s. What this chart can honestly say is
    that the identity it creates has been bound to nothing, which is checked here
    rather than asserted in prose.
    """
    for path in TEMPLATES_DIR.iterdir():
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8")
        for kind in ("kind: Role", "kind: ClusterRole", "kind: RoleBinding"):
            assert kind not in body, f"{path.name} renders a {kind}"


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
