"""Deterministic checks over the local cluster lifecycle scripts.

Every check here reads files from this repository and nothing else. No network,
no cluster, no container engine, no clock, no randomness. Nothing is executed:
the scripts are read as text.

The scripts under ``scripts/environment/`` are the only thing in this repository
that can delete something on a contributor's machine. What stops them deleting
the wrong thing is not the code's intent but four properties of how every command
in them is written -- the cluster is named, deletions are namespaced and
label-scoped, no invocation can inherit an ambient kubeconfig, and nothing
blanket-prunes an engine. Those properties are stated in ADR 0001 (D5, D6) and
were, until now, defended by review alone. A future edit that quietly drops a
``--name`` or a ``-l`` is exactly the edit review misses, so they are checked
here instead.

The same applies to the numbers. The host tiers live in ADR 0001 (D7) as a
Markdown table and in ``lib.sh`` as three constants, and a threshold that
disagrees with the requirement it enforces is worse than no threshold: it fails
hosts that are fine, or admits hosts that are not, and does either silently. The
table is parsed and the constants are compared against it.

What this suite establishes is that the scripts are written the way the decision
says they must be. It establishes nothing about what they do when run -- whether
a cluster is really created, whether a teardown really leaves no residue, whether
a guard really refuses a foreign cluster. Those are runtime questions, answered
by the cluster-smoke layer against a real engine and recorded in its own evidence.
A static reading of a shell script is not a substitute for running it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "environment"
LIB_PATH = SCRIPT_DIR / "lib.sh"
KIND_CONFIG_PATH = REPO_ROOT / "deploy" / "kind" / "inferops-dev.yaml"
ADR_PATH = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0001-local-development-environment.md"
)
OWNERSHIP_PATH = (
    REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
)

# The scripts a contributor runs. lib.sh is excluded because it is sourced rather
# than executed and holds the wrapper definitions the rules below are stated in
# terms of; it is checked separately.
ENTRY_POINTS = (
    "cluster-up.sh",
    "cluster-verify.sh",
    "cluster-down.sh",
    "preflight.sh",
    "proof.sh",
    "smoke.sh",
    "verify-clean.sh",
)

# Read-only by contract, and the contract is worth checking: cluster-verify.sh is
# the one script a contributor is invited to run repeatedly against a cluster
# they care about, and verify-clean.sh is what certifies a teardown. Either one
# acquiring the ability to change something would go unnoticed.
READ_ONLY_SCRIPTS = ("cluster-verify.sh", "verify-clean.sh", "preflight.sh")

# kubectl subcommands that change cluster state. `exec` and `cp` are here because
# both reach inside a running container, and `port-forward` is not because it
# does not.
MUTATING_KUBECTL_VERBS = (
    "annotate",
    "apply",
    "cordon",
    "cp",
    "create",
    "delete",
    "drain",
    "edit",
    "exec",
    "label",
    "patch",
    "replace",
    "scale",
    "taint",
    "uncordon",
)

# Operations whose blast radius is the whole machine rather than this project's
# own objects. ADR 0001 (D6) forbids every one of them, and a script is not the
# place to discover that a contributor's unrelated containers are gone.
#
# Patterns rather than substrings, because the shapes that matter here are tokens
# and a substring cannot tell a token from the middle of a word. `-A ` with a
# trailing space -- the first form of this rule -- missed `kubectl get pods -A`
# outright, because there is nothing after the flag to match the space against.
FORBIDDEN_PATTERNS = (
    (
        "engine-wide prune",
        r"\bdocker\s+(system|volume|image|container|network|builder)\s+prune\b",
    ),
    (
        "touching the default kubeconfig's contexts",
        r"kubectl\s+config\s+(delete|use)-context\b",
    ),
    (
        "recursive force delete",
        r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r\b",
    ),
)

# Every namespace at once, in either spelling. `-A` is matched as a token rather
# than as the substring `"-A "`, which was the first form of this rule and which
# missed the flag whenever it ended a line.
ACROSS_ALL_NAMESPACES = re.compile(r"--all-namespaces(?![\w-])|(?<![\w-])-A(?![\w-])")


def script_text(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def code_lines(name: str) -> list[tuple[int, str]]:
    """Every command in a script, as one logical line each.

    Two things happen here, and both are needed for any rule below to mean what
    it says.

    Comments are dropped. Comments in these files quote the very commands they
    explain -- the rule about `docker system prune` is written next to the prose
    saying why it is refused -- so a check reading them would fail on its own
    documentation.

    Continuations are joined. A `kubectl delete` and the `-n` and `-l` flags that
    scope it are routinely written across four lines, and a rule that read them
    separately would see an unscoped delete on the first line every time. Reading
    a shell command one physical line at a time does not read the command.

    Two shapes this does not understand, stated because a reader should not have
    to infer the boundary: a comment appearing part-way through a continuation is
    spliced into the command rather than dropped, and a heredoc body is read as
    if it were code. Neither occurs in these scripts. A rule that fired on either
    would be a false positive rather than a missed violation, which is the safe
    direction for this to be wrong in, and adding a shell parser to close a gap
    nothing exercises would cost more than it defends.
    """
    lines: list[tuple[int, str]] = []
    pending: list[str] = []
    start = 0
    for number, raw in enumerate(script_text(name).splitlines(), start=1):
        stripped = raw.strip()
        if not pending and (not stripped or stripped.startswith("#")):
            continue
        if not pending:
            start = number
        pending.append(stripped.removesuffix("\\").strip())
        if stripped.endswith("\\"):
            continue
        lines.append((start, " ".join(pending)))
        pending = []
    if pending:
        lines.append((start, " ".join(pending)))
    return lines


def all_code_lines() -> list[tuple[str, int, str]]:
    return [
        (name, number, line)
        for name in (*ENTRY_POINTS, "lib.sh")
        for number, line in code_lines(name)
    ]


LIB_TEXT = LIB_PATH.read_text(encoding="utf-8")


def lib_constant(name: str) -> str:
    match = re.search(
        rf'^readonly {re.escape(name)}="([^"]*)"', LIB_TEXT, flags=re.MULTILINE
    )
    assert match is not None, f"lib.sh does not define {name}"
    return match.group(1)


# --------------------------------------------------------------------------
# One definition of the target
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ENTRY_POINTS)
def test_every_script_sources_the_shared_library(name: str) -> None:
    """A script defining its own target could act on one nothing else agreed to."""
    body = script_text(name)
    assert 'source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"' in body, name


@pytest.mark.parametrize("name", ENTRY_POINTS)
def test_no_command_hardcodes_the_cluster_name(name: str) -> None:
    """The name is a constant, so that changing it changes every use of it.

    A literal `inferops-dev` inside a delete, a filter, or a label selector would
    survive a rename of the constant and go on acting on the old name -- which by
    then may belong to somebody else.

    Scoped to lines that invoke one of the three tools, because the same string
    is also part of a committed filename (`deploy/kind/inferops-dev.yaml`) and a
    path is not a target.
    """
    cluster_name = lib_constant("INFEROPS_CLUSTER_NAME")
    offenders = [
        f"{name}:{number}: {line}"
        for number, line in code_lines(name)
        if cluster_name in line and re.search(r"\b(kind|docker|kubectl)\s", line)
    ]
    assert not offenders, offenders


# --------------------------------------------------------------------------
# Nothing reaches a cluster this project does not own
# --------------------------------------------------------------------------


def test_a_mutating_kubectl_call_goes_through_the_wrapper() -> None:
    """`inferops::kubectl` pins --kubeconfig and --context on every invocation.

    A bare `kubectl apply` inherits whatever KUBECONFIG and current context the
    contributor's shell happens to carry, which on a developer machine is
    routinely a real cluster.
    """
    pattern = re.compile(rf"(?<!::)\bkubectl\s+({'|'.join(MUTATING_KUBECTL_VERBS)})\b")
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for name, number, line in all_code_lines()
        if pattern.search(line)
    ]
    assert not offenders, offenders


def test_the_wrapper_names_both_the_kubeconfig_and_the_context() -> None:
    assert (
        'kubectl --kubeconfig "${INFEROPS_KUBECONFIG}" '
        '--context "${INFEROPS_KUBE_CONTEXT}" "$@"' in LIB_TEXT
    )


def test_every_cluster_deletion_names_the_cluster() -> None:
    """`kind delete cluster` with no --name deletes whatever kind calls default."""
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for name, number, line in all_code_lines()
        if "kind delete cluster" in line
        and '--name "${INFEROPS_CLUSTER_NAME}"' not in line
    ]
    assert not offenders, offenders


# A resource name after `kubectl delete <kind>`. It may not begin with a hyphen,
# and that restriction is the whole point of writing it out: `[\w-]+` accepts
# `--all`, so the first form of this rule read `delete pod --all` as a named
# deletion and let the most dangerous shape in the vocabulary through.
DELETE_NAMES_A_RESOURCE = re.compile(r"delete\s+[\w,]+[/ ]+[A-Za-z0-9][\w.-]*")

# `--all` on a delete means every object of that kind. Inside the project's own
# namespace that is arguably harmless, but it is one mistyped `-n` away from not
# being, and nothing here needs it.
DELETE_TAKES_EVERYTHING = re.compile(r"(?<![\w-])--all(?![\w-])")

INVOKES_DELETE = re.compile(r"(?<!::)\bkubectl\s+delete\b|inferops::kubectl delete")


def deletion_lines() -> list[tuple[str, int, str]]:
    """Every kubectl deletion in the environment scripts, as a logical line."""
    return [row for row in all_code_lines() if INVOKES_DELETE.search(row[2])]


def test_there_are_deletions_to_check() -> None:
    """The rules below say nothing about a repository with no deletions in it."""
    assert len(deletion_lines()) >= 3


def deletion_is_scoped(line: str) -> bool:
    """A delete is namespaced *and* either label-selected or named.

    The one shape allowed without a namespace flag is the deletion of the
    project's own namespace, which names its target outright.

    One function rather than an assertion written inline, because the
    adversarial-input tests at the end of this module have to apply exactly the
    rule the suite enforces. A second copy of it would drift, and the copy that
    drifted would be the one certifying that the rule works.
    """
    if 'delete namespace "${INFEROPS_NAMESPACE}"' in line:
        return True
    scoped = '-n "${INFEROPS_NAMESPACE}"' in line
    selected = '-l "${INFEROPS_PART_OF_SELECTOR}"' in line or (
        DELETE_NAMES_A_RESOURCE.search(line) is not None
    )
    return scoped and selected


def test_every_object_deletion_is_scoped() -> None:
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for name, number, line in deletion_lines()
        if not deletion_is_scoped(line)
    ]
    assert not offenders, offenders


def test_no_deletion_takes_every_object_of_a_kind() -> None:
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for name, number, line in deletion_lines()
        if DELETE_TAKES_EVERYTHING.search(line)
    ]
    assert not offenders, offenders


def test_nothing_that_changes_state_crosses_every_namespace() -> None:
    """`-A` and `--all-namespaces` are refused on anything that changes something.

    Not on everything. `smoke.sh` reads `kubectl top pods -A` when in-cluster
    metrics happen to be available, and a read across namespaces has no blast
    radius: it deletes nothing, changes nothing, and leaves nothing behind. What
    ADR 0001 (D6) forbids is acting outside this project's own namespace, so that
    is what this refuses, rather than every appearance of the flag.
    """
    mutating = re.compile(rf"kubectl\s+({'|'.join(MUTATING_KUBECTL_VERBS)})\b")
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for name, number, line in all_code_lines()
        if mutating.search(line) and ACROSS_ALL_NAMESPACES.search(line)
    ]
    assert not offenders, offenders


@pytest.mark.parametrize(
    "label,pattern", FORBIDDEN_PATTERNS, ids=[label for label, _ in FORBIDDEN_PATTERNS]
)
def test_no_script_reaches_beyond_this_project(label: str, pattern: str) -> None:
    compiled = re.compile(pattern)
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for name, number, line in all_code_lines()
        if compiled.search(line)
    ]
    assert not offenders, (label, offenders)


def rules_reject(line: str) -> bool:
    """Whether any rule in this module would refuse a line."""
    mutating = re.search(rf"kubectl\s+({'|'.join(MUTATING_KUBECTL_VERBS)})\b", line)
    deletes = INVOKES_DELETE.search(line) is not None
    return (
        (deletes and DELETE_TAKES_EVERYTHING.search(line) is not None)
        or (deletes and not deletion_is_scoped(line))
        or (mutating is not None and ACROSS_ALL_NAMESPACES.search(line) is not None)
        or any(re.search(pattern, line) for _, pattern in FORBIDDEN_PATTERNS)
    )


@pytest.mark.parametrize(
    "sample",
    (
        # The shape that got through the first version of the scoping rule,
        # because `[\w-]+` read `--all` as a resource name.
        'inferops::kubectl delete pod --all -n "${INFEROPS_NAMESPACE}"',
        # Namespaced but naming nothing.
        'inferops::kubectl delete pod -n "${INFEROPS_NAMESPACE}"',
        # The shape that got through the first version of the sweep rule,
        # because the flag ended the line and `"-A "` needs a space after it.
        "inferops::kubectl delete pods -A",
        "inferops::kubectl delete pods --all-namespaces",
        "docker system prune -f",
        "docker volume prune",
        "kubectl config use-context kind-inferops-dev",
        "rm -rf /",
        "rm -fr /",
    ),
)
def test_the_rules_reject_the_shapes_they_exist_to_reject(sample: str) -> None:
    """A static rule that has never been shown a violation may not have one.

    Each line above is written to break a rule. Without this, the suite passing
    tells a reader only that these scripts are clean today, and nothing about
    whether the rules would notice if they stopped being. Two of these samples
    are the exact shapes an earlier version of this module let through.
    """
    assert rules_reject(sample), sample


@pytest.mark.parametrize(
    "sample",
    (
        # Every deletion the scripts actually make, and the read across
        # namespaces that has no blast radius and must not be refused.
        'inferops::kubectl delete namespace "${INFEROPS_NAMESPACE}" --ignore-not-found=true',
        'inferops::kubectl delete job hello-world-verify -n "${INFEROPS_NAMESPACE}"',
        "inferops::kubectl top pods -A",
        "inferops::kubectl get pods -n kube-system -o wide",
    ),
)
def test_the_rules_accept_what_the_scripts_legitimately_do(sample: str) -> None:
    """A rule that refuses everything is as useless as one that refuses nothing."""
    assert not rules_reject(sample), sample


def test_nothing_writes_to_the_default_kubeconfig() -> None:
    """Reading it is allowed and done once, deliberately. Writing to it is not.

    verify-clean.sh asks the default kubeconfig whether it carries a context
    named like this project's, purely so that it can say the context is not this
    teardown's residue. Every other kubectl config call is confined to the
    project's own file.
    """
    offenders = []
    for name, number, line in all_code_lines():
        if not re.search(r"(?<!::)\bkubectl\s+config\b", line):
            continue
        if '--kubeconfig "${INFEROPS_KUBECONFIG}"' in line:
            continue
        if "config get-contexts -o name" in line:
            continue
        offenders.append(f"{name}:{number}: {line.strip()}")
    assert not offenders, offenders


@pytest.mark.parametrize("name", READ_ONLY_SCRIPTS)
def test_a_read_only_script_cannot_change_anything(name: str) -> None:
    pattern = re.compile(rf"kubectl\s+({'|'.join(MUTATING_KUBECTL_VERBS)})\b")
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for number, line in code_lines(name)
        if pattern.search(line)
        or "kind delete" in line
        or "kind create" in line
        or re.search(r"\bdocker (rm|rmi|image rm|volume rm|network rm)\b", line)
    ]
    assert not offenders, offenders


# --------------------------------------------------------------------------
# Every script refuses what it does not understand
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ENTRY_POINTS)
def test_every_script_refuses_an_argument_it_does_not_understand(name: str) -> None:
    """Silently ignoring an argument means running something else than was asked.

    On a destructive script that is the difference between a partial teardown and
    a full one, decided by a typo nobody was told about.
    """
    body = script_text(name)
    assert 'inferops::fail "unknown argument' in body or (
        'inferops::fail "expected no arguments' in body
    ), name


@pytest.mark.parametrize("name", ("cluster-up.sh", "cluster-down.sh", "proof.sh"))
def test_every_script_taking_options_bounds_its_argument_count(name: str) -> None:
    """A trailing argument nobody inspected is an instruction nobody obeyed."""
    body = script_text(name)
    assert '[ "$#" -le 1 ]' in body or 'while [ "$#" -gt 0 ]' in body, name


# --------------------------------------------------------------------------
# The thresholds are the documented ones
# --------------------------------------------------------------------------


def minimum_tier_row() -> list[str]:
    """The cells of ADR 0001 (D7)'s minimum-tier row, in table order."""
    for line in ADR_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0].startswith("**Minimum**"):
            return cells
    pytest.fail("ADR 0001 (D7) publishes no minimum-tier row")


MINIMUM_TIER = minimum_tier_row()

# | Tier | Logical CPUs | Host memory | Must reach the container VM | Free disk | Basis |
CPU_CELL, VM_MEMORY_CELL, DISK_CELL = 1, 3, 4


def quantity(cell: str) -> int:
    """A `6 GiB` or `20 GB` cell as bytes. Binary and decimal are not the same."""
    match = re.fullmatch(r"(\d+) (GiB|GB)", cell)
    assert match is not None, f"unparseable tier quantity: {cell!r}"
    scale = 1024**3 if match.group(2) == "GiB" else 1000**3
    return int(match.group(1)) * scale


def test_the_processor_threshold_is_the_documented_one() -> None:
    assert lib_constant("INFEROPS_MIN_ENGINE_CPUS") == MINIMUM_TIER[CPU_CELL]


def test_the_memory_threshold_is_the_documented_one() -> None:
    assert int(lib_constant("INFEROPS_MIN_ENGINE_MEM_BYTES")) == quantity(
        MINIMUM_TIER[VM_MEMORY_CELL]
    )


def test_the_disk_threshold_is_the_documented_one() -> None:
    assert int(lib_constant("INFEROPS_MIN_FREE_DISK_BYTES")) == quantity(
        MINIMUM_TIER[DISK_CELL]
    )


def test_preflight_checks_every_figure_the_tier_states() -> None:
    """A tier with an unchecked column is a requirement nobody has to meet."""
    body = script_text("preflight.sh")
    for constant in (
        "INFEROPS_MIN_ENGINE_CPUS",
        "INFEROPS_MIN_ENGINE_MEM_BYTES",
        "INFEROPS_MIN_FREE_DISK_BYTES",
    ):
        assert constant in body, constant


# --------------------------------------------------------------------------
# The pin is one value, wherever it is written
# --------------------------------------------------------------------------

PINNED_IMAGE = (
    f"kindest/node:{lib_constant('INFEROPS_NODE_IMAGE_TAG')}"
    f"@{lib_constant('INFEROPS_NODE_IMAGE_DIGEST')}"
)


@pytest.mark.parametrize(
    "path",
    (
        KIND_CONFIG_PATH,
        ADR_PATH,
        REPO_ROOT / "docs" / "environment" / "local-cluster.md",
    ),
    ids=lambda path: path.name,
)
def test_every_published_copy_of_the_pin_is_the_same_pin(path: Path) -> None:
    """kind resolves the digest; a stale tag beside it documents a lie."""
    assert PINNED_IMAGE in path.read_text(encoding="utf-8"), PINNED_IMAGE


def test_the_expected_server_minor_follows_the_pinned_tag() -> None:
    """The skew check is only as good as the number it compares against."""
    tag = lib_constant("INFEROPS_NODE_IMAGE_TAG")
    assert tag.split(".")[1] == lib_constant("INFEROPS_SERVER_MINOR"), tag


def test_the_digest_is_a_full_sha256() -> None:
    digest = lib_constant("INFEROPS_NODE_IMAGE_DIGEST")
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest), digest


# --------------------------------------------------------------------------
# The ownership inventory names things that exist
# --------------------------------------------------------------------------


def test_every_script_the_ownership_inventory_names_is_committed() -> None:
    """An inventory naming a script that was renamed points nowhere, silently."""
    inventory = json.loads(OWNERSHIP_PATH.read_text(encoding="utf-8"))
    referenced = {
        value
        for resource in inventory["resources"]
        for value in (resource["createdBy"], resource["destroyedBy"])
        if value.endswith(".sh")
    }
    assert referenced, "the inventory names no lifecycle script at all"
    missing = [ref for ref in referenced if not (REPO_ROOT / ref).is_file()]
    assert not missing, missing
