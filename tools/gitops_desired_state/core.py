"""The Git desired-state tree, and the generated releases it holds.

The directory ``gitops/`` is the desired state a GitOps controller is meant to read.
It holds generated releases and nothing else: each release directory is the two
files the platform writes, ``values.generated.yaml`` and
``rendered-workload-release.yaml``. No file in the tree is written by hand, except
the one page that says what the tree is.

**One path for one environment binding and one workload.** A release directory is
``<destinationPath>/workloads/<workloadId>``. The selected EnvironmentBinding
declares the destination path, and the WorkloadContract names the workload.
:func:`verify_tree` derives that path from the declared inputs and refuses a release
committed anywhere else.

**Declared here, derived there.** :data:`DESIRED_STATE_RELEASES` names each
desired-state release and the inputs it is derived from. The derivation and the
byte comparison are ``tools.generated_release``'s: this module calls its ``verify``
and ``regenerate`` and holds no second renderer. The releases are declared here and
not in that package because the first experiment's freeze record pins that package's
files, and a new declaration there would move a pin.

**Everything in the tree is accounted for.** :func:`verify_tree` walks ``gitops/``
and reports every entry that is not a generated file of a declared release, a
directory that leads to one, or the tree's own page. A hand-written values file, a
second copy of a release, and a symbolic link or a directory junction are each such
an entry. A link is reported at a declared path too, and is not followed.

**What a revision check holds.** A declared revision is 40 lowercase hexadecimal
characters and is not one repeated character. Nothing here reads Git, so whether
the revision names a commit is not checked by this module.

**Offline.** Every function reads files under the root it is given, and
:func:`regenerate_release` writes only the declared release directory and the
directories that lead to it. Nothing here contacts a cluster, a registry, a
network, or a model, and nothing runs Helm or Git.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

import yaml

from inferops.domain.environment import parse_environment_binding
from inferops.domain.workload import DomainError
from tools.generated_release import (
    GENERATED_FILES,
    REPO_ROOT,
    DeclaredRelease,
    SourcesRefused,
    derive,
    regenerate,
    verify,
)

__all__ = [
    "DESIRED_STATE_RELEASES",
    "DESIRED_STATE_ROOT",
    "ENVIRONMENTS_PATH",
    "REPO_ROOT",
    "RULES",
    "TREE_DOCUMENT",
    "WORKLOADS_SEGMENT",
    "Finding",
    "Rule",
    "WriteRefused",
    "desired_state_release",
    "expected_directory",
    "regenerate_release",
    "release_key",
    "verify_tree",
]

#: The directory the desired state is committed under, at the repository root.
DESIRED_STATE_ROOT: Final = "gitops"

#: The directory every environment binding's destination path is under.
ENVIRONMENTS_PATH: Final = f"{DESIRED_STATE_ROOT}/environments"

#: The directory, under a binding's destination path, that holds its workloads.
WORKLOADS_SEGMENT: Final = "workloads"

#: The one hand-written file the tree may hold: the page that says what it is.
TREE_DOCUMENT: Final = f"{DESIRED_STATE_ROOT}/README.md"

#: The commit the reference desired-state release was rendered at. The renderer and
#: the chart's platform defaults, the ``api`` defaults and the ``runtime.rollout``
#: bounds, were read at this commit. A release cannot name the commit that adds it.
#: The release was rendered again when the chart gained the runtime's two rollout
#: bounds and the release took the two-replica contract: this is the commit that
#: made those edits, and the release was regenerated in the commit after it. The
#: earlier releases named ``c056b977`` and then ``9bc07a57``, and are in Git history.
#: It was rendered once more when the chart moved to ``0.6.0``, which renders a
#: PodDisruptionBudget for a tier of two or more replicas and changes no value. The
#: renderer states the chart version, so the commit that made that edit is recorded
#: here. The release before it named ``40803f2f``, and is in Git history.
_REFERENCE_RENDER_REVISION: Final = "cdcfd62baf6fff56ca179711855510c93194ce80"

#: Every desired-state release, and the inputs each is derived from.
#:
#: The one entry is the two-replica version of the reference workload, on the
#: ``local-docker-desktop`` binding. The contract declares two serving runtime
#: replicas, and the binding states two API replicas.
#: That binding names the one provider on which the GitOps controller's bootstrap
#: was executed. One Application of that controller reads this release, on a
#: cluster where an operator applied the Application.
DESIRED_STATE_RELEASES: Final[tuple[DeclaredRelease, ...]] = (
    DeclaredRelease(
        directory=(
            f"{ENVIRONMENTS_PATH}/local-docker-desktop/"
            f"{WORKLOADS_SEGMENT}/support-assistant"
        ),
        contract="contracts/workload/examples/valid/synchronous-llm-two-replicas.yaml",
        bindings=("contracts/environment/examples/valid/local-docker-desktop.yaml",),
        binding_name="local-docker-desktop",
        platform_defaults="charts/inferops-llm/values.yaml",
        platform_defaults_revision=_REFERENCE_RENDER_REVISION,
        renderer_revision=_REFERENCE_RENDER_REVISION,
    ),
)


@dataclass(frozen=True)
class Rule:
    """A property the desired-state tree has to hold."""

    rule_id: str
    statement: str


#: The rules :func:`verify_tree` applies, in the order it reports them.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "desired-state-declaration-invalid",
        "A desired-state release selects one binding by name, and each of its two "
        "revisions is 40 lowercase hexadecimal characters and not one repeated "
        "character.",
    ),
    Rule(
        "desired-state-path-not-derived",
        "A desired-state release directory is the selected binding's destination "
        "path, under gitops/environments/, followed by workloads and the workload "
        "identifier the contract names.",
    ),
    Rule(
        "desired-state-entry-undeclared",
        "Every entry under gitops/ is a generated file of a declared release, a "
        "directory that leads to one, or the tree's README.md.",
    ),
    Rule(
        "desired-state-release-drifted",
        "Each desired-state release is, byte for byte, what its declared sources "
        "derive.",
    ),
)

_FULL_REVISION: Final = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class Finding:
    """One way the desired-state tree breaks a rule.

    ``subject`` is a path under the repository root, or a release key followed by
    the field or file the finding concerns. ``diff`` is the unified diff the drift
    check produced, empty when the finding has none.
    """

    rule_id: str
    subject: str
    detail: str
    diff: tuple[str, ...] = ()


class WriteRefused(Exception):
    """A regeneration that would write a release the rules refuse."""

    def __init__(self, findings: Sequence[Finding]) -> None:
        super().__init__("; ".join(f"{f.rule_id} {f.subject}" for f in findings))
        self.findings = tuple(findings)


def release_key(declared: DeclaredRelease) -> str:
    """How the command selects a release: ``<binding name>/<directory name>``.

    The directory name alone is the workload, and one workload may be released on
    two bindings.
    """
    return f"{declared.binding_name}/{PurePosixPath(declared.directory).name}"


def desired_state_release(key: str) -> DeclaredRelease:
    """The desired-state release with this key.

    Raises:
        KeyError: no desired-state release has this key.
    """
    for declared in DESIRED_STATE_RELEASES:
        if release_key(declared) == key:
            return declared
    raise KeyError(key)


# --------------------------------------------------------------------------
# One release: its declaration and its path
# --------------------------------------------------------------------------


def _is_placeholder(revision: str) -> bool:
    """A revision of one repeated character names no commit.

    This is the one shape the test fixtures use. Any other 40 hexadecimal
    characters pass, whether or not they name a commit.
    """
    return len(set(revision)) == 1


def _is_link(path: Path) -> bool:
    """A symbolic link, or a directory junction, which Windows does not call one."""
    return path.is_symlink() or path.is_junction()


def _declaration_findings(declared: DeclaredRelease) -> list[Finding]:
    key = release_key(declared)
    findings = []
    if declared.binding_name is None:
        findings.append(
            Finding(
                "desired-state-declaration-invalid",
                f"{key}: binding_name",
                "the release names no binding; a desired-state path belongs to one "
                "named binding",
            )
        )
    for field, revision in (
        ("renderer_revision", declared.renderer_revision),
        ("platform_defaults_revision", declared.platform_defaults_revision),
    ):
        if _FULL_REVISION.fullmatch(revision) is None:
            detail = "the revision is not 40 lowercase hexadecimal characters"
        elif _is_placeholder(revision):
            detail = "the revision is one repeated character, which names no commit"
        else:
            continue
        findings.append(
            Finding("desired-state-declaration-invalid", f"{key}: {field}", detail)
        )
    return findings


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _destination(declared: DeclaredRelease, root: Path) -> str | None:
    """The destination path of the binding the declaration selects, or ``None``."""
    destination = None
    for path in declared.bindings:
        try:
            binding = parse_environment_binding(_load_yaml(root / path))
        except (OSError, DomainError, ValueError, yaml.YAMLError, RecursionError):
            continue
        if str(binding.metadata.name) == declared.binding_name:
            destination = str(binding.spec.gitops.destination_path)
    return destination


def expected_directory(declared: DeclaredRelease, root: Path = REPO_ROOT) -> str | None:
    """The directory the declared inputs place this release in.

    ``None`` when the inputs do not say: no declared binding that parses has the
    selected name, or the sources derive no release. In each of those cases the
    drift check refuses the sources, so the release is still reported. A test
    holds that for a missing name, a missing file, and two bindings of one name.
    """
    destination = _destination(declared, root)
    if destination is None:
        return None
    try:
        release = derive(declared, root).release.as_document()
    except SourcesRefused:
        return None
    workload = release["metadata"]["workloadId"]
    return f"{destination}/{WORKLOADS_SEGMENT}/{workload}"


def _path_findings(declared: DeclaredRelease, root: Path) -> list[Finding]:
    key = release_key(declared)
    findings = []
    if not declared.directory.startswith(f"{ENVIRONMENTS_PATH}/"):
        findings.append(
            Finding(
                "desired-state-path-not-derived",
                f"{key}: {declared.directory}",
                f"the release directory is not under {ENVIRONMENTS_PATH}/",
            )
        )
    destination = _destination(declared, root)
    if destination is not None and not destination.startswith(f"{ENVIRONMENTS_PATH}/"):
        findings.append(
            Finding(
                "desired-state-path-not-derived",
                f"{key}: {declared.directory}",
                f"the selected binding's destination path, {destination}, is not "
                f"under {ENVIRONMENTS_PATH}/",
            )
        )
    expected = expected_directory(declared, root)
    if expected is not None and expected != declared.directory:
        findings.append(
            Finding(
                "desired-state-path-not-derived",
                f"{key}: {declared.directory}",
                f"the declared binding and contract place this release at {expected}",
            )
        )
    return findings


# --------------------------------------------------------------------------
# The tree: every entry is declared
# --------------------------------------------------------------------------


def _allowed(
    releases: Sequence[DeclaredRelease],
) -> tuple[frozenset[str], frozenset[str]]:
    """The directories and the files the tree may hold, as paths under the root."""
    directories = {DESIRED_STATE_ROOT}
    files = {TREE_DOCUMENT}
    for declared in releases:
        path = PurePosixPath(declared.directory)
        directories.add(path.as_posix())
        directories.update(parent.as_posix() for parent in path.parents)
        files.update(f"{declared.directory}/{name}" for name in GENERATED_FILES)
    directories.discard(".")
    return frozenset(directories), frozenset(files)


def _undeclared(subject: str, detail: str) -> Finding:
    return Finding("desired-state-entry-undeclared", subject, detail)


_LINK_DETAIL: Final = "a symbolic link or a junction is not followed"


def _ancestor_findings(declared: DeclaredRelease, root: Path) -> list[Finding]:
    """Each path from the tree's root to the release that a write must not pass.

    A link there would take the write out of the tree, and a file there is not a
    directory to write into. A path that does not exist yet is created by the write.
    """
    findings = []
    path = PurePosixPath(declared.directory)
    for ancestor in (*reversed(path.parents), path):
        relative = ancestor.as_posix()
        if relative == ".":
            continue
        entry = root / relative
        if _is_link(entry):
            findings.append(_undeclared(relative, _LINK_DETAIL))
        elif entry.exists() and not entry.is_dir():
            findings.append(_undeclared(relative, "the path is not a directory"))
    return findings


def _entry_findings(releases: Sequence[DeclaredRelease], root: Path) -> list[Finding]:
    tree = root / DESIRED_STATE_ROOT
    if _is_link(tree) or (tree.exists() and not tree.is_dir()):
        return [
            _undeclared(
                DESIRED_STATE_ROOT,
                "the desired-state root is a link or a file, not a directory",
            )
        ]
    if not tree.is_dir():
        return []
    directories, files = _allowed(releases)
    findings = []
    for current, names, file_names in os.walk(tree, followlinks=False):
        here = Path(current)
        for name in sorted(names):
            entry = here / name
            relative = entry.relative_to(root).as_posix()
            if _is_link(entry):
                findings.append(_undeclared(relative, _LINK_DETAIL))
            elif relative not in directories:
                findings.append(
                    _undeclared(relative, "the directory leads to no declared release")
                )
            else:
                continue
            names.remove(name)
        for name in sorted(file_names):
            entry = here / name
            relative = entry.relative_to(root).as_posix()
            if _is_link(entry):
                findings.append(_undeclared(relative, _LINK_DETAIL))
            elif relative not in files:
                findings.append(
                    _undeclared(
                        relative,
                        "the file is not a generated file of a declared release",
                    )
                )
    return sorted(findings, key=lambda finding: finding.subject)


# --------------------------------------------------------------------------
# Verification and regeneration
# --------------------------------------------------------------------------


def _drift_findings(declared: DeclaredRelease, root: Path) -> list[Finding]:
    key = release_key(declared)
    return [
        Finding(
            "desired-state-release-drifted",
            f"{key}: {finding.subject}",
            f"{finding.rule_id}: {finding.detail}",
            finding.diff,
        )
        for finding in verify(declared, root)
    ]


def verify_tree(
    root: Path = REPO_ROOT,
    releases: Sequence[DeclaredRelease] = DESIRED_STATE_RELEASES,
) -> tuple[Finding, ...]:
    """Every way the desired-state tree under ``root`` breaks a rule.

    An empty result means that each declared release is at the path its inputs
    derive, each is byte for byte what its declared sources derive, and the tree
    holds nothing else. This reads files and writes none.
    """
    findings: list[Finding] = []
    seen: set[str] = set()
    for declared in releases:
        findings.extend(_declaration_findings(declared))
        findings.extend(_path_findings(declared, root))
        if declared.directory in seen:
            findings.append(
                Finding(
                    "desired-state-path-not-derived",
                    f"{release_key(declared)}: {declared.directory}",
                    "another declared release has this directory",
                )
            )
        seen.add(declared.directory)
        findings.extend(_drift_findings(declared, root))
    findings.extend(_entry_findings(releases, root))
    order = {rule.rule_id: index for index, rule in enumerate(RULES)}
    return tuple(sorted(findings, key=lambda finding: order[finding.rule_id]))


def regenerate_release(declared: DeclaredRelease, root: Path = REPO_ROOT) -> bool:
    """Write both files of one desired-state release again from its declared inputs.

    Returns ``True`` when the files were written, and ``False`` when the committed
    files were already the derived ones and nothing was touched. The directories
    that lead to the release are created when they are absent.

    Raises:
        WriteRefused: the declaration or the path breaks a rule, or a path from the
            tree's root to the release is a link or a file; nothing is touched.
        SourcesRefused: the declared inputs derive no release; nothing is touched.
        RegenerationRefused: the release path holds something the platform did not
            write, or a staging directory is left beside it; nothing is touched.
        OSError: a file could not be removed or written.
    """
    refused = [
        *_declaration_findings(declared),
        *_path_findings(declared, root),
        *_ancestor_findings(declared, root),
    ]
    if refused:
        raise WriteRefused(refused)
    derive(declared, root)
    parent = (root / declared.directory).parent
    parent.mkdir(parents=True, exist_ok=True)
    return regenerate(declared, root)
