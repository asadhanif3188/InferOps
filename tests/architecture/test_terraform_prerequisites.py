"""The Terraform prerequisite layer against the ownership inventory.

This is the check the ownership document said did not exist. Its own closing
paragraph read: *"Not checked by anything, because there is nothing to check it
against: that the inventory describes the Terraform that gets written."* There is
now something to check it against, and this module is it.

Everything here reads files. It runs no `apply`, contacts no cluster, provisions
nothing, and reads no state, so a passing run is `local-static` evidence about a
configuration and says **nothing** about whether that configuration applies. The
prerequisite rows in the inventory are still `planned` for exactly that reason --
the same reason every Helm row stayed `planned` after the chart was written.

Four properties are what this module exists for, and each is a rule stated
elsewhere that a Terraform configuration is in a position to break quietly.

**Terraform may declare only what Terraform is allowed to own.** The inventory
gives it the namespace, the namespace metadata, and the model cache claim, and
gives Helm the release. So the declared resource set is compared against the
inventory in both directions: every declared resource maps to a Terraform-owned
row, and every Terraform-owned row is either declared or recorded as deferred.
A `kubernetes_deployment` or a `helm_release` appearing here would put one
resource under two reconcilers, and the loser would be whichever ran last.

**The handoff is by name, and the names have to match.** The chart mounts a claim
it must never create; this configuration creates a claim nothing else does. If
those two names drift the release does not fail loudly -- it fails at schedule
time with a claim that does not exist. The claim name here is compared against
the chart's own real values file, and the namespace against the constant the
release lifecycle installs into.

**A pin is a pin everywhere or it is not a pin.** The provider version is
compared across the module, the environment, and the lock file, and the lock file
is required to carry checksums for every platform a contributor may run on -- a
lock recorded on one operating system silently stops being a lock on another.

**Nothing may inherit an ambient target.** The provider names the kubeconfig and
the context explicitly, the same rule every `kubectl` and `helm` call in this
repository already follows, because `terraform apply` following a context left
selected from other work is how a local experiment becomes a namespace in
somebody's real cluster.

The HCL is read with regular expressions rather than a parser. These are files
this repository wrote and keeps in one shape, the properties asked about are
literal tokens, and a dependency added to parse four small files would be a
larger risk than the one it removes. Where that reading is approximate it is
approximate in the safe direction: a check fires on a shape it does not
understand rather than passing it.

`terraform fmt` and `terraform validate` need the binary itself and are skipped,
loudly, where it is absent -- the same arrangement `helm`, `kubeconform`, and
`shellcheck` already have.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]

TERRAFORM_ROOT = REPO_ROOT / "infra" / "terraform"
MODULE_DIR = TERRAFORM_ROOT / "modules" / "platform-prerequisites"
ENVIRONMENT_DIR = TERRAFORM_ROOT / "environments" / "local"
LOCK_PATH = ENVIRONMENT_DIR / ".terraform.lock.hcl"

WRAPPER_PATH = REPO_ROOT / "scripts" / "environment" / "terraform-prerequisites.sh"
LIB_PATH = REPO_ROOT / "scripts" / "environment" / "lib.sh"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

INVENTORY_PATH = (
    REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
)
OWNERSHIP_DOCUMENT_PATH = REPO_ROOT / "docs" / "architecture" / "resource-ownership.md"
PREREQUISITE_DOCUMENT_PATH = (
    REPO_ROOT / "docs" / "environment" / "platform-prerequisites.md"
)
CHART_REAL_VALUES_PATH = (
    REPO_ROOT / "charts" / "inferops-llm" / "ci" / "real-values.yaml"
)
MODEL_SOURCE_PATH = REPO_ROOT / "docs" / "serving" / "model-source.v1.json"

# The label that carries the boundary. Every object this project creates has
# `app.kubernetes.io/part-of: inferops`, so a scoped sweep matching only that
# would delete a prerequisite and give one resource two destroyers. This is the
# label such a sweep has to exclude, and the namespace is where it is set.
PREREQUISITE_LIFECYCLE_LABEL = "inferops.io/lifecycle"
PREREQUISITE_LIFECYCLE_VALUE = "prerequisite"

# The label each declared resource carries to say which inventory row it is. It
# is what makes the comparison below a mapping rather than a guess from a
# Terraform resource name.
COMPONENT_LABEL = "app.kubernetes.io/component"

# Provider resource types that would put Terraform on the wrong side of the
# boundary. The first group is the release -- every one of these is a Helm-owned
# row. The second is derived: a controller creates and keeps rewriting them, so
# adopting one means owning something that will not hold still. The last entry is
# the one that would collapse the boundary outright.
FORBIDDEN_RESOURCE_TYPES = (
    "kubernetes_deployment",
    "kubernetes_deployment_v1",
    "kubernetes_service",
    "kubernetes_service_v1",
    "kubernetes_service_account",
    "kubernetes_service_account_v1",
    "kubernetes_config_map",
    "kubernetes_config_map_v1",
    "kubernetes_secret",
    "kubernetes_secret_v1",
    "kubernetes_job",
    "kubernetes_job_v1",
    "kubernetes_cron_job",
    "kubernetes_cron_job_v1",
    "kubernetes_network_policy",
    "kubernetes_network_policy_v1",
    "kubernetes_pod",
    "kubernetes_pod_v1",
    "kubernetes_stateful_set",
    "kubernetes_stateful_set_v1",
    "kubernetes_daemon_set",
    "kubernetes_daemonset_v1",
    "kubernetes_persistent_volume",
    "kubernetes_persistent_volume_v1",
    "kubernetes_ingress",
    "kubernetes_ingress_v1",
    "kubernetes_resource_quota",
    "kubernetes_resource_quota_v1",
    "helm_release",
)

# Providers that would take this configuration outside a local cluster
# altogether. V1 provisions no cloud infrastructure and pays for nothing, and a
# provider block is how that stops being true in one commit. `helm` is here for a
# different reason from the cloud entries: a Helm provider would let Terraform
# install a release, which is the ownership collapse the boundary exists to
# prevent.
FORBIDDEN_PROVIDERS = (
    "aws",
    "azurerm",
    "azuread",
    "google",
    "google-beta",
    "digitalocean",
    "kind",
    "docker",
    "helm",
)

# Every platform the lock file has to carry a checksum for. A lock generated by
# `terraform init` records only the platform it ran on, which makes it a lock on
# one contributor's machine and an unpinned dependency on everybody else's.
#
# Six, not five: the sixth is `windows_386`, which is what the Terraform build on
# the reference host reports. A lock that omitted the platform it was generated
# on would be a lock for other people and not for the person who wrote it.
REQUIRED_LOCK_PLATFORMS = 6

# Leading whitespace is allowed on purpose, and the first version of these
# patterns was wrong for exactly that reason. Anchored at column 0, a block
# indented by a single space -- from a bad merge, a pasted example, or an editor
# -- was invisible to every rule below, including the allowlist that is supposed
# to be the backstop. A forbidden kind would have passed the entire suite. The
# only check that would have caught it was `terraform fmt`, which is skipped
# where the binary is absent, so the guarantee rested on a tool that may not be
# installed. These patterns now find a block wherever it sits on its line, and
# the adversarial tests at the end of this module apply them to the shapes they
# exist to refuse.
RESOURCE_BLOCK = re.compile(
    r'^[^\S\n]*resource\s+"(?P<type>[\w-]+)"\s+"(?P<name>[\w-]+)"\s*\{', re.MULTILINE
)
PROVIDER_BLOCK = re.compile(
    r'^[^\S\n]*provider\s+"(?P<name>[\w-]+)"\s*\{', re.MULTILINE
)
REQUIRED_PROVIDER_ENTRY = re.compile(
    r"^[^\S\n]*(?P<name>[\w-]+)\s*=\s*\{[^\S\n]*$", re.MULTILINE
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def terraform_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.tf"))


def strip_comments(text: str) -> str:
    """HCL line comments removed, so a rule does not fire on its own rationale.

    These files explain the boundary by naming the things it forbids: the comment
    above the module's resources lists the namespace-creating flag and every kind
    Terraform may not own. A check that read comments would fail on the
    documentation written to prevent the failure.

    Only `#` is recognised, which is the form `terraform fmt` produces and the
    only form these files use. HCL also accepts `//` and `/* */`, and a rule
    reading one of those would fire on a comment rather than on code. That is the
    safe direction for this to be wrong in -- a false refusal a contributor sees
    immediately, rather than a violation nobody sees at all -- and it is stated
    here so that a reader who introduces a `//` comment knows why the suite
    complained.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


MODULE_TEXT = "\n".join(read(path) for path in terraform_files(MODULE_DIR))
ENVIRONMENT_TEXT = "\n".join(read(path) for path in terraform_files(ENVIRONMENT_DIR))
ALL_TERRAFORM_CODE = strip_comments(f"{MODULE_TEXT}\n{ENVIRONMENT_TEXT}")

INVENTORY = json.loads(read(INVENTORY_PATH))
RESOURCES: list[dict] = INVENTORY["resources"]
TERRAFORM_ROWS = [row for row in RESOURCES if row["owner"] == "terraform"]


def lib_constant(name: str) -> str:
    match = re.search(
        rf'^readonly {re.escape(name)}="([^"]*)"', read(LIB_PATH), flags=re.MULTILINE
    )
    assert match is not None, f"lib.sh does not define {name}"
    return match.group(1)


def variable_default(text: str, name: str) -> str:
    """The `default` of one `variable` block, as written.

    Deliberately narrow: it reads the first `default =` in the block and stops at
    the end of that line. Every default in these files is a scalar on one line,
    and a multi-line one would return something that fails a comparison rather
    than something that passes one.
    """
    block = re.search(
        rf'^variable\s+"{re.escape(name)}"\s*\{{(?P<body>.*?)^\}}',
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert block is not None, f"no variable named {name!r}"
    default = re.search(
        r"^\s*default\s*=\s*(?P<value>.+)$", block.group("body"), flags=re.MULTILINE
    )
    assert default is not None, f"variable {name!r} declares no default"
    return default.group("value").strip().strip('"')


def declared_resource_types(text: str | None = None) -> set[str]:
    """Every `resource` type in some HCL. Defaults to the committed configuration.

    It takes text so that the adversarial tests at the end of this module can put
    the rule to a violation and watch it fire. A second copy of the rule written
    for those tests would drift, and the copy that drifted would be the one
    certifying that the rule works.
    """
    subject = ALL_TERRAFORM_CODE if text is None else text
    return {match.group("type") for match in RESOURCE_BLOCK.finditer(subject)}


def configured_providers(text: str | None = None) -> set[str]:
    """Every `provider "..."` block."""
    subject = ALL_TERRAFORM_CODE if text is None else text
    return {match.group("name") for match in PROVIDER_BLOCK.finditer(subject)}


def required_providers(text: str | None = None) -> set[str]:
    """Every name assigned a block, which is how `required_providers` entries read.

    Deliberately broader than its name: `annotations = {` matches it too. That
    costs nothing, because the only question asked of the result is whether a
    forbidden provider is in it, and it means a `required_providers` entry cannot
    hide behind an indentation this pattern did not anticipate.
    """
    subject = ALL_TERRAFORM_CODE if text is None else text
    return {match.group("name") for match in REQUIRED_PROVIDER_ENTRY.finditer(subject)}


def declared_components() -> set[str]:
    """The inventory row each declared resource says it is, from its label."""
    pattern = rf'"{re.escape(COMPONENT_LABEL)}"\s*=\s*"([\w-]+)"'
    return set(re.findall(pattern, MODULE_TEXT))


# --------------------------------------------------------------------------
# The configuration exists and is where everything else says it is
# --------------------------------------------------------------------------


def test_the_module_and_the_environment_are_committed() -> None:
    assert MODULE_DIR.is_dir(), MODULE_DIR
    assert ENVIRONMENT_DIR.is_dir(), ENVIRONMENT_DIR
    assert terraform_files(MODULE_DIR), "the module declares no Terraform at all"
    assert terraform_files(ENVIRONMENT_DIR), "the environment declares no Terraform"


def test_the_lock_file_is_committed() -> None:
    """An uncommitted lock means `init` resolves the provider afresh each time."""
    assert LOCK_PATH.is_file(), LOCK_PATH


def test_the_wrapper_script_is_committed() -> None:
    assert WRAPPER_PATH.is_file(), WRAPPER_PATH


# --------------------------------------------------------------------------
# Terraform declares only what Terraform owns
# --------------------------------------------------------------------------


def test_every_declared_resource_maps_to_a_terraform_owned_row() -> None:
    """A resource here that the inventory does not give Terraform has no owner."""
    owned = {row["resourceId"] for row in TERRAFORM_ROWS}
    declared = declared_components()
    assert declared, "no resource declares which inventory row it is"
    assert declared <= owned, sorted(declared - owned)


def test_every_terraform_row_in_scope_is_declared_or_deferred() -> None:
    """The other direction: a row Terraform owns and no configuration creates.

    `namespace-metadata` is the one row with no resource block of its own. It is
    the labels and annotations on the namespace -- one Kubernetes object, two
    inventory rows -- so it is satisfied by the namespace carrying the metadata
    rather than by a resource, and the label checks below are what hold it.
    """
    declared = declared_components()
    missing = [
        row["resourceId"]
        for row in TERRAFORM_ROWS
        if row["v1Status"] != "deferred"
        and row["resourceId"] not in declared
        and row["resourceId"] != "namespace-metadata"
    ]
    assert not missing, missing


def test_a_deferred_row_is_not_quietly_implemented() -> None:
    """`platform-resource-quota` is out of V1 and must stay out.

    It is named in the inventory so that if a quota is ever added it lands on
    this side of the boundary rather than inside a chart. Naming it is not
    permission to build it.
    """
    deferred = {
        row["resourceId"] for row in TERRAFORM_ROWS if row["v1Status"] == "deferred"
    }
    assert deferred, "no deferred Terraform row to check"
    overlap = deferred & declared_components()
    assert not overlap, sorted(overlap)


@pytest.mark.parametrize("resource_type", FORBIDDEN_RESOURCE_TYPES)
def test_terraform_declares_no_release_or_derived_resource(resource_type: str) -> None:
    assert resource_type not in declared_resource_types(), (
        f"{resource_type} is owned by Helm or by a controller. A resource in "
        "Terraform state and in a chart is reconciled by both, and the loser is "
        "whichever ran last."
    )


def test_the_declared_resource_types_are_the_two_expected_ones() -> None:
    """The allowlist beside the denylist, so a new kind cannot arrive unnoticed.

    A denylist can only refuse what somebody thought of. This fails on anything
    new, which forces the ownership question to be answered in review rather than
    after an apply.
    """
    assert declared_resource_types() == {
        "kubernetes_namespace_v1",
        "kubernetes_persistent_volume_claim_v1",
    }, sorted(declared_resource_types())


@pytest.mark.parametrize("provider", FORBIDDEN_PROVIDERS)
def test_no_provider_reaches_beyond_a_local_cluster(provider: str) -> None:
    assert provider not in configured_providers(), provider
    assert provider not in required_providers(), provider


def test_the_only_provider_is_the_kubernetes_one() -> None:
    assert configured_providers() == {"kubernetes"}, sorted(configured_providers())


def test_nothing_creates_or_deletes_a_cluster() -> None:
    """Neither tool may create, reconfigure, or delete a cluster (ADR 0004 D3)."""
    for forbidden in ("kind_cluster", "docker_container", "kubernetes_node"):
        assert forbidden not in ALL_TERRAFORM_CODE, forbidden


def test_the_configuration_never_hands_helm_the_namespace() -> None:
    """The one flag the whole boundary is about, on the Terraform side.

    Terraform creating the namespace is correct. What would not be is this
    configuration also handing Helm a way to create it, so the string is refused
    in code here exactly as it is in the environment scripts.
    """
    assert "--create-namespace" not in ALL_TERRAFORM_CODE


# --------------------------------------------------------------------------
# The prerequisite marker, which is what keeps a sweep away
# --------------------------------------------------------------------------


def test_the_lifecycle_marker_is_set_and_is_the_prerequisite_one() -> None:
    pattern = rf'"{re.escape(PREREQUISITE_LIFECYCLE_LABEL)}"\s*=\s*"([\w-]+)"'
    values = set(re.findall(pattern, MODULE_TEXT))
    assert values == {PREREQUISITE_LIFECYCLE_VALUE}, sorted(values)


def test_the_project_label_is_set_on_what_terraform_creates() -> None:
    """Without it, a prerequisite is invisible to every project-scoped query."""
    assert re.search(r'"app\.kubernetes\.io/part-of"\s*=\s*"inferops"', MODULE_TEXT)


def test_terraform_says_it_manages_what_it_manages() -> None:
    """`managed-by` answers, on the object itself, which tool destroys it."""
    assert re.search(r'"app\.kubernetes\.io/managed-by"\s*=\s*"Terraform"', MODULE_TEXT)


# --------------------------------------------------------------------------
# The handoff is by name, and the names have to match
# --------------------------------------------------------------------------


def test_the_namespace_default_is_the_one_the_release_installs_into() -> None:
    """A prerequisite namespace nothing installs into is a namespace, not a
    prerequisite."""
    expected = lib_constant("INFEROPS_RELEASE_NAMESPACE")
    assert variable_default(MODULE_TEXT, "namespace") == expected
    assert variable_default(ENVIRONMENT_TEXT, "namespace") == expected


def test_the_namespace_default_carries_the_isolation_prefix() -> None:
    """ADR 0001 (D5). The prefix is how a scoped teardown finds this project."""
    assert variable_default(MODULE_TEXT, "namespace").startswith("inferops-")


def test_the_namespace_is_not_the_one_another_script_deletes_outright() -> None:
    """ADR 0004 requires the platform namespace to be distinct from the smoke one.

    `cluster-down.sh` deletes the smoke namespace by name. A prerequisite inside
    it would have two destroyers, which is the thing the inventory exists to
    prevent.
    """
    assert variable_default(MODULE_TEXT, "namespace") != lib_constant(
        "INFEROPS_NAMESPACE"
    )


def test_the_claim_name_is_the_one_the_chart_mounts() -> None:
    """The handoff fails at schedule time, not at render time, if these drift."""
    values = yaml.safe_load(read(CHART_REAL_VALUES_PATH))
    chart_claim = values["model"]["cache"]["claimName"]
    assert variable_default(MODULE_TEXT, "model_cache_claim_name") == chart_claim
    assert variable_default(ENVIRONMENT_TEXT, "model_cache_claim_name") == chart_claim


def test_the_default_claim_holds_the_pinned_artifact() -> None:
    """The size is checked against the artifact this project actually pins.

    Two copies, because the layout inside the claim is keyed by revision: a
    second pinned revision lands beside the first rather than replacing it, and a
    claim sized for exactly one would fail the first time a revision moved.
    """
    artifact_bytes = json.loads(read(MODEL_SOURCE_PATH))["expectedSizeBytes"]
    default = variable_default(MODULE_TEXT, "model_cache_size")
    match = re.fullmatch(r"(\d+)Gi", default)
    assert match is not None, default
    requested_bytes = int(match.group(1)) * 1024**3
    assert requested_bytes >= 2 * artifact_bytes, {
        "requested": default,
        "artifact bytes": artifact_bytes,
    }


def test_the_environment_and_the_module_agree_on_every_default() -> None:
    """A default changed in one file and not the other is a silent divergence."""
    for name in ("namespace", "model_cache_claim_name", "model_cache_size"):
        assert variable_default(MODULE_TEXT, name) == variable_default(
            ENVIRONMENT_TEXT, name
        ), name


# --------------------------------------------------------------------------
# A pin is a pin everywhere
# --------------------------------------------------------------------------


def provider_pin(text: str) -> str:
    match = re.search(
        r'kubernetes\s*=\s*\{[^}]*?version\s*=\s*"([^"]+)"', text, flags=re.DOTALL
    )
    assert match is not None, "no kubernetes provider version is declared"
    return match.group(1)


def test_the_provider_pin_is_exact() -> None:
    """A range resolves to whatever was published most recently.

    Everywhere else here a pin is exact -- the node image and the runtime image
    by digest, the model by revision and per-file hash -- and a provider is no
    different: a range makes "it worked yesterday" a statement about the registry
    rather than about this configuration.
    """
    for text, label in ((MODULE_TEXT, "module"), (ENVIRONMENT_TEXT, "environment")):
        pin = provider_pin(text)
        assert re.fullmatch(r"\d+\.\d+\.\d+", pin), (label, pin)


def test_every_copy_of_the_provider_pin_is_the_same_pin() -> None:
    module_pin = provider_pin(MODULE_TEXT)
    assert provider_pin(ENVIRONMENT_TEXT) == module_pin
    locked = re.search(r'^\s*version\s*=\s*"([^"]+)"', read(LOCK_PATH), re.MULTILINE)
    assert locked is not None, "the lock file records no version"
    assert locked.group(1) == module_pin, (locked.group(1), module_pin)


def test_the_lock_file_covers_every_platform_a_contributor_may_run_on() -> None:
    """A lock recorded by `init` on one machine is not a lock on another.

    `terraform init` records the checksum for the platform it ran on and nothing
    else, so the next contributor on a different operating system gets a fresh
    resolution with no verification against what was reviewed.
    """
    hashes = re.findall(r'"h1:[^"]+"', read(LOCK_PATH))
    assert len(hashes) >= REQUIRED_LOCK_PLATFORMS, len(hashes)


def test_the_terraform_version_floor_is_declared() -> None:
    for text, label in ((MODULE_TEXT, "module"), (ENVIRONMENT_TEXT, "environment")):
        assert re.search(r"required_version\s*=", text), label


# --------------------------------------------------------------------------
# Nothing inherits an ambient target
# --------------------------------------------------------------------------


def test_the_provider_names_both_the_kubeconfig_and_the_context() -> None:
    """The same rule every kubectl and helm call in this repository follows.

    A provider with neither follows `KUBECONFIG` and the current context, which
    on a developer machine is routinely a real cluster.
    """
    provider = re.search(
        r'provider\s+"kubernetes"\s*\{(?P<body>.*?)^\}',
        ENVIRONMENT_TEXT,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert provider is not None, "the environment configures no kubernetes provider"
    body = provider.group("body")
    assert "config_path" in body, body
    assert "config_context" in body, body


def test_the_context_default_is_a_project_cluster() -> None:
    default = variable_default(ENVIRONMENT_TEXT, "kube_context")
    assert default.startswith("kind-inferops-"), default


def test_the_context_variable_refuses_a_foreign_context() -> None:
    """A name check, and the configuration says so rather than implying more.

    V1-S3-010-PR2 generalised this from one pinned kind cluster to either
    supported provider: a kind context of any selected cluster name, or
    exactly `docker-desktop`.
    """
    assert 'can(regex("^kind-.+$"' in ENVIRONMENT_TEXT
    assert 'var.kube_context == "docker-desktop"' in ENVIRONMENT_TEXT


def test_the_kubeconfig_default_is_relative_to_the_configuration() -> None:
    """An absolute path is one contributor's filesystem in everybody's checkout."""
    default = variable_default(ENVIRONMENT_TEXT, "kubeconfig_path")
    assert default.startswith("../"), default
    assert default.endswith(lib_constant("INFEROPS_KUBECONFIG_REL")), default


def test_no_host_path_is_committed() -> None:
    offenders = [
        line
        for line in ALL_TERRAFORM_CODE.splitlines()
        if re.search(r"[A-Za-z]:\\|[A-Za-z]:/|/home/|/Users/|/mnt/[a-z]/", line)
    ]
    assert not offenders, offenders


def test_no_secret_material_is_written_into_the_configuration() -> None:
    """A credential in a default is a credential in every checkout.

    The provider can take a client certificate, a client key, a cluster CA, a
    bearer token, a username and password, or an `exec` credential plugin
    in-line. None of them belongs in a committed file, and the kubeconfig this
    configuration reads by path is git-ignored for the same reason.
    """
    forbidden = re.compile(
        r"\b(client_certificate|client_key|cluster_ca_certificate|password|token"
        r"|exec)\b",
        re.IGNORECASE,
    )
    offenders = [
        line for line in ALL_TERRAFORM_CODE.splitlines() if forbidden.search(line)
    ]
    assert not offenders, offenders


# --------------------------------------------------------------------------
# The claim cannot hang an apply
# --------------------------------------------------------------------------


def test_the_apply_does_not_wait_for_a_binding_that_needs_a_pod() -> None:
    """The trap this configuration would otherwise fall into on first use.

    The accepted local provisioner binds a claim on first consumer, so a claim
    nothing mounts stays `Pending` by design. The provider's own default is to
    wait, which would hang `terraform apply` until its timeout and then report a
    correctly-provisioned prerequisite as a failure.
    """
    assert variable_default(MODULE_TEXT, "wait_until_bound") == "false"
    assert "wait_until_bound = var.wait_until_bound" in MODULE_TEXT


def test_the_claim_asks_for_a_single_writer() -> None:
    """`ReadWriteMany` would claim a capability the local provisioner lacks."""
    assert 'access_modes = ["ReadWriteOnce"]' in MODULE_TEXT


def test_the_claim_names_no_storage_class() -> None:
    """Naming one would tie the prerequisite layer to a distribution it does not own."""
    assert variable_default(MODULE_TEXT, "storage_class_name") == "null"


# --------------------------------------------------------------------------
# The wrapper, and what it refuses
# --------------------------------------------------------------------------


def test_the_wrapper_establishes_cluster_identity_before_it_reaches_one() -> None:
    """Terraform can check a context's name; it cannot check which cluster it is.

    V1-S3-010-PR2: the provider-aware inferops::resolve_target replaces the
    kind-pinned inferops::assert_target_cluster here.
    """
    assert "inferops::resolve_target" in read(WRAPPER_PATH)


def test_the_wrapper_hands_terraform_the_target_rather_than_letting_it_find_one() -> (
    None
):
    body = read(WRAPPER_PATH)
    assert 'TF_VAR_kubeconfig_path="${INFEROPS_TARGET_KUBECONFIG}"' in body
    assert 'TF_VAR_kube_context="${INFEROPS_TARGET_CONTEXT}"' in body


def test_the_wrapper_refuses_to_destroy_without_confirmation() -> None:
    """Destroying the namespace cascades over anything still inside it."""
    assert 'inferops::fail "destroy needs --confirm' in read(WRAPPER_PATH)


def test_the_wrapper_refuses_to_destroy_underneath_an_installed_release() -> None:
    """The cascade would take the release and leave Helm's record claiming it
    exists."""
    assert "is still installed in" in read(WRAPPER_PATH)


def test_the_check_action_needs_no_cluster() -> None:
    """A contributor with no cluster is still told the configuration is malformed."""
    assert "init -backend=false" in read(WRAPPER_PATH)


# --------------------------------------------------------------------------
# State is host state, and stays out of version control
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pattern", ("*.tfstate", "*.tfstate.*", "*.tfplan", ".terraform/")
)
def test_state_and_plans_are_ignored(pattern: str) -> None:
    """State describes one contributor's cluster; a plan embeds the prior state."""
    assert pattern in read(GITIGNORE_PATH), pattern


def test_the_lock_file_is_not_ignored() -> None:
    """Ignoring the lock would leave the provider resolved afresh on every machine."""
    result = subprocess.run(
        ["git", "check-ignore", LOCK_PATH.relative_to(REPO_ROOT).as_posix()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, result.stdout


def test_no_state_and_no_plan_was_committed() -> None:
    """Asked of git rather than of the filesystem, which is the difference
    between "committed" and "present".

    Terraform writes `terraform.tfstate` beside its configuration, so the moment
    somebody actually runs `terraform apply` against a local cluster the file
    exists in this tree -- ignored, untracked, and entirely correct. A check that
    globbed the directory failed on exactly the machines that had done the thing
    this repository is trying to get done, and passed on the ones that had not.
    V1-S3-011 was the first story to apply these prerequisites for real and the
    first to hit it.

    What must never happen is committing one: state carries resource ids and, for
    some providers, secrets. `git ls-files` answers that question directly.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "--", "infra/terraform"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode == 0, tracked.stderr
    committed = tracked.stdout.split()

    assert not [name for name in committed if name.endswith(".tfstate")], (
        "state was committed"
    )
    assert not [name for name in committed if name.endswith(".tfstate.backup")], (
        "a state backup was committed"
    )
    assert not [name for name in committed if name.endswith(".tfplan")], (
        "a plan was committed"
    )
    # The check above is only as good as the ignore rules that keep a careless
    # `git add` from tracking one in the first place.
    for pattern in ("*.tfstate", "*.tfplan"):
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", f"infra/terraform/x{pattern[1:]}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert ignored.returncode == 0, (
            f"{pattern} under infra/terraform is not ignored"
        )


# --------------------------------------------------------------------------
# The documents say what this is and what it is not
# --------------------------------------------------------------------------


def test_the_prerequisite_document_exists_and_cites_the_inventory() -> None:
    assert "resource-ownership.md" in read(PREREQUISITE_DOCUMENT_PATH)


def test_the_prerequisite_document_states_that_nothing_has_been_applied() -> None:
    """The rule the whole repository runs on, applied to this document.

    Every Terraform row in the inventory is still `planned`. A document that read
    as though the layer were running would be the overclaim this project treats
    as a defect, so the status has to be stated where a reader meets it.
    """
    assert "has never been applied" in read(PREREQUISITE_DOCUMENT_PATH)


def test_the_terraform_rows_stay_planned_until_something_applies_them() -> None:
    """Writing a configuration is not running one.

    This mirrors the chart exactly: `V1-S3-002` wrote every template and every
    Helm row stayed `planned`, because a rendered object is a file. A row here may
    become `implemented` when an apply is recorded against a cluster, and the
    evidence rule in `test_resource_ownership.py` will then require the record.
    """
    for row in TERRAFORM_ROWS:
        if row["v1Status"] == "deferred":
            continue
        assert row["v1Status"] == "planned", (row["resourceId"], row["v1Status"])
        assert row["evidenceRef"] is None, row["resourceId"]


def test_the_ownership_document_no_longer_says_this_check_cannot_exist() -> None:
    """It said this check could not exist. It exists, so the sentence had to go."""
    assert "test_terraform_prerequisites.py" in read(OWNERSHIP_DOCUMENT_PATH)


# --------------------------------------------------------------------------
# The rules refuse the shapes they exist to refuse
# --------------------------------------------------------------------------
#
# Every rule above passes over the committed configuration, which is what a rule
# that reads nothing at all also does. These put each rule to a violation and
# require it to fire.
#
# They are not decoration. The first version of `RESOURCE_BLOCK` was anchored at
# column 0, so a resource block indented by one space was invisible to the whole
# ownership comparison -- allowlist included -- and every check above went on
# passing. Nothing here would have caught it; these tests would have.

#: A forbidden resource written in four positions HCL allows and a reviewer might
#: not notice. Every one but the first is indented, and an indented block is
#: exactly what the first version of these patterns could not see.
VIOLATING_RESOURCE_SHAPES = (
    'resource "kubernetes_config_map" "leaked" {\n  metadata {}\n}',
    ' resource "kubernetes_secret" "leaked" {\n  metadata {}\n}',
    '\tresource "helm_release" "leaked" {\n  name = "x"\n}',
    'locals {}\n   resource "kubernetes_deployment" "leaked" {\n}',
)

#: The same, for a provider block that would reach outside the local cluster.
VIOLATING_PROVIDER_SHAPES = (
    'provider "aws" {\n  region = "us-east-1"\n}',
    '  provider "helm" {\n}',
)

#: And for a `required_providers` entry, at two different indents. Terraform
#: downloads what is declared here whether or not a `provider` block configures
#: it, so this is a second way in.
VIOLATING_REQUIRED_PROVIDER_SHAPES = (
    'terraform {\n  required_providers {\n    aws = {\n      source = "x"\n'
    "    }\n  }\n}",
    'terraform {\n required_providers {\n  helm = {\n   source = "x"\n  }\n }\n}',
)


@pytest.mark.parametrize("sample", VIOLATING_RESOURCE_SHAPES)
def test_a_forbidden_resource_is_found_wherever_it_sits_on_its_line(
    sample: str,
) -> None:
    found = declared_resource_types(sample)
    assert found, f"the rule saw no resource at all in: {sample!r}"
    assert found & set(FORBIDDEN_RESOURCE_TYPES), sorted(found)


@pytest.mark.parametrize("sample", VIOLATING_PROVIDER_SHAPES)
def test_a_forbidden_provider_block_is_found_wherever_it_sits(sample: str) -> None:
    found = configured_providers(sample)
    assert found & set(FORBIDDEN_PROVIDERS), sorted(found)


@pytest.mark.parametrize("sample", VIOLATING_REQUIRED_PROVIDER_SHAPES)
def test_a_forbidden_required_provider_entry_is_found_at_any_indent(
    sample: str,
) -> None:
    found = required_providers(sample)
    assert found & set(FORBIDDEN_PROVIDERS), sorted(found)


def test_the_rules_accept_what_the_configuration_legitimately_declares() -> None:
    """The other half: a rule that refuses everything is not a rule.

    Without this, tightening a pattern until it fired on the committed
    configuration would still look like a passing suite.
    """
    assert declared_resource_types() == {
        "kubernetes_namespace_v1",
        "kubernetes_persistent_volume_claim_v1",
    }
    assert not configured_providers() & set(FORBIDDEN_PROVIDERS)
    assert not required_providers() & set(FORBIDDEN_PROVIDERS)


# --------------------------------------------------------------------------
# Terraform's own opinion, where Terraform is installed
# --------------------------------------------------------------------------

TERRAFORM_BINARY = shutil.which("terraform")
needs_terraform = pytest.mark.skipif(
    TERRAFORM_BINARY is None,
    reason="terraform is not installed; format and validation are skipped, loudly",
)


@needs_terraform
def test_the_configuration_is_formatted() -> None:
    result = subprocess.run(
        [str(TERRAFORM_BINARY), "fmt", "-check", "-recursive", str(TERRAFORM_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@needs_terraform
def test_the_configuration_validates() -> None:
    """`-backend=false` keeps this offline: no state is read and no cluster is
    contacted.

    `init` still resolves the provider, which needs either a populated
    `.terraform/` directory or the network. Where it has neither this skips with
    the reason rather than failing, because an absent registry is a fact about
    the machine and not about this configuration.
    """
    init = subprocess.run(
        [
            str(TERRAFORM_BINARY),
            f"-chdir={ENVIRONMENT_DIR}",
            "init",
            "-backend=false",
            "-input=false",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if init.returncode != 0:
        pytest.skip(f"terraform init could not run: {init.stderr.strip()[:200]}")
    result = subprocess.run(
        [str(TERRAFORM_BINARY), f"-chdir={ENVIRONMENT_DIR}", "validate"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
