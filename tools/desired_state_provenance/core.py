"""The provenance of a desired-state release, read at one Git commit.

A GitOps controller follows a branch, and a branch name is not an identity: it
names another commit after the next merge. The controller resolves the branch to
a commit and reports that commit. This module starts from that commit. It reads
the desired-state release as the commit holds it, and returns the identities that
bind an applied workload to its source: the release identifier, the digests the
release records, the workload identity, and the chart version.

**The revision is a commit, in full.** :func:`resolve` accepts 40 lowercase
hexadecimal characters that are not one repeated character. It refuses a branch
name, a tag name, and an abbreviated commit before it runs Git.

**Everything is read from the commit, and not from the working tree.** Each file
is read as the blob the commit holds, so an uncommitted edit and a line-ending
conversion of the checkout change nothing. Replacement objects are disabled.

**What is checked at the commit.** The release document parses, and its
identifier is the one its own fields derive. The values file hashes to the digest
the release records. The contract and the binding at the commit are the ones the
release names, by identity and by digest. The values name the workload the
release names. The chart declares a name, a version, and an application version.

**What is compared with an observation.** :func:`source_findings` compares the
record with what an Application declares that it reads.
:func:`observed_revision_findings` compares it with the commits a controller
reported. :func:`metadata_findings` compares it with the labels of an applied
object. Each takes plain values. This module reads no cluster, and the caller
collects the observation.

**What this does not do.** It does not render the release again at the commit, so
it does not establish that the values file is what the recorded renderer revision
derives. It does not establish that the commit is on a branch or was reviewed. It
writes no file and changes no label.

Git is the one program this module runs, and it runs two read-only subcommands.
Nothing here contacts a cluster, a registry, a network, or a model.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

import yaml

from inferops.domain.environment import parse_environment_binding
from inferops.domain.release import (
    RenderedWorkloadRelease,
    check_rendered_workload_release,
    output_digest,
    parse_rendered_workload_release,
    verify_release_sources,
)
from inferops.domain.workload import DomainError, parse_workload_contract
from tools.generated_release import REPO_ROOT, DeclaredRelease
from tools.gitops_desired_state import release_key

__all__ = [
    "CHART_LABEL",
    "RECORD_SCHEMA",
    "REPO_ROOT",
    "RULES",
    "VERSION_LABEL",
    "WORKLOAD_LABEL",
    "Finding",
    "Provenance",
    "ProvenanceRefused",
    "ReconciliationSource",
    "Rule",
    "is_immutable_revision",
    "metadata_findings",
    "observed_revision_findings",
    "resolve",
    "source_findings",
]

#: The identifier of the record :meth:`Provenance.as_document` returns.
RECORD_SCHEMA: Final = "inferops.io/desired-state-provenance/v1alpha1"

#: The three labels the chart already derives that carry a provenance identity.
#: This module adds none. The chart's label helper sets each one on every object.
CHART_LABEL: Final = "helm.sh/chart"
VERSION_LABEL: Final = "app.kubernetes.io/version"
WORKLOAD_LABEL: Final = "inferops.io/workload"

_CHART_FILE: Final = "Chart.yaml"

#: The two generated files of a release directory, restated. This module does not
#: import the render package, and a test compares these names with that package's.
_RELEASE_FILE: Final = "rendered-workload-release.yaml"
_VALUES_FILE: Final = "values.generated.yaml"
_FULL_REVISION: Final = re.compile(r"[0-9a-f]{40}")
_GIT_TIMEOUT_SECONDS: Final = 60


@dataclass(frozen=True)
class Rule:
    """A property a provenance record, or an observation beside it, has to hold."""

    rule_id: str
    statement: str


#: The rules, in the order they are reported. The first seven refuse a record.
#: The last three compare a record with an observation.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "revision-not-immutable",
        "A revision is 40 lowercase hexadecimal characters and not one repeated "
        "character. A branch name, a tag name, and an abbreviated commit are not "
        "identities.",
    ),
    Rule(
        "revision-not-readable",
        "The repository holds the revision as a commit, and Git is available to "
        "read it.",
    ),
    Rule(
        "desired-state-absent-at-revision",
        "The commit holds both generated files of the release, each contract and "
        "binding the release is declared from, and the chart's Chart.yaml.",
    ),
    Rule(
        "release-not-accepted",
        "The release document at the commit parses, and its identifier is the one "
        "its workload identity and source derive.",
    ),
    Rule(
        "values-digest-mismatch",
        "The values file at the commit hashes to the digest the release records.",
    ),
    Rule(
        "release-sources-mismatch",
        "The contract and the binding at the commit are the ones the release "
        "names, by identity and by digest, and the values name the workload the "
        "release names.",
    ),
    Rule(
        "chart-identity-unreadable",
        "The chart at the commit declares a name, a version, and an application "
        "version, each as a non-empty string.",
    ),
    Rule(
        "source-not-the-release",
        "An Application reads the chart the release was rendered for, and the "
        "values file of the release, from this repository.",
    ),
    Rule(
        "observed-revision-mismatch",
        "Each commit a controller reports is the commit the record was read at.",
    ),
    Rule(
        "workload-metadata-mismatch",
        "An applied object carries the chart label, the application-version label, "
        "and the workload label that the record derives.",
    ),
)


@dataclass(frozen=True)
class Finding:
    """One way a record, or an observation beside it, breaks a rule."""

    rule_id: str
    subject: str
    detail: str


class ProvenanceRefused(Exception):
    """A revision that yields no provenance record."""

    def __init__(self, findings: Sequence[Finding]) -> None:
        super().__init__("; ".join(f"{f.rule_id} {f.subject}" for f in findings))
        self.findings = tuple(findings)


@dataclass(frozen=True)
class ReconciliationSource:
    """What an Application declares that it reads.

    ``followed_revision`` is what the Application follows. It may be a branch
    name, and it is then not an identity. No comparison here uses it as one.
    """

    repository: str
    followed_revision: str
    chart_path: str
    value_files: tuple[str, ...]


@dataclass(frozen=True)
class Provenance:
    """The identities of one desired-state release at one commit."""

    revision: str
    key: str
    directory: str
    release_id: str
    workload_id: str
    workload_version: str
    values_sha256: str
    contract_sha256: str
    binding_name: str
    binding_environment: str
    binding_sha256: str
    renderer_revision: str
    platform_defaults_revision: str
    chart_path: str
    chart_name: str
    chart_version: str
    chart_app_version: str

    @property
    def values_path(self) -> str:
        return f"{self.directory}/{_VALUES_FILE}"

    @property
    def release_path(self) -> str:
        return f"{self.directory}/{_RELEASE_FILE}"

    def workload_labels(self) -> dict[str, str]:
        """The labels the chart sets on every object from these identities."""
        return {
            CHART_LABEL: f"{self.chart_name}-{self.chart_version}",
            VERSION_LABEL: self.chart_app_version,
            WORKLOAD_LABEL: self.workload_id,
        }

    def as_document(self) -> dict[str, Any]:
        """The record as plain data. It holds identifiers and digests only.

        The record has no timestamp and no host name, so one commit and one
        release give one document.
        """
        return {
            "schema": RECORD_SCHEMA,
            "git": {"revision": self.revision},
            "desiredState": {
                "key": self.key,
                "directory": self.directory,
                "releasePath": self.release_path,
                "valuesPath": self.values_path,
            },
            "release": {
                "releaseId": self.release_id,
                "workloadId": self.workload_id,
                "workloadVersion": self.workload_version,
                "valuesSha256": self.values_sha256,
                "contractSha256": self.contract_sha256,
                "environmentBinding": {
                    "name": self.binding_name,
                    "environment": self.binding_environment,
                    "sha256": self.binding_sha256,
                },
                "rendererRevision": self.renderer_revision,
                "platformDefaultsRevision": self.platform_defaults_revision,
            },
            "chart": {
                "path": self.chart_path,
                "name": self.chart_name,
                "version": self.chart_version,
                "appVersion": self.chart_app_version,
            },
            "workloadLabels": self.workload_labels(),
        }


def is_immutable_revision(revision: object) -> bool:
    """Whether a value has the form of a full commit identifier.

    The form is checked, and nothing else. A value of this form may name no commit.
    """
    return (
        isinstance(revision, str)
        and _FULL_REVISION.fullmatch(revision) is not None
        and len(set(revision)) > 1
    )


# --------------------------------------------------------------------------
# Reading a commit
# --------------------------------------------------------------------------


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes] | None:
    """Run one read-only Git command in ``root``, or ``None`` when Git is absent."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        return subprocess.run(
            [git, "--no-replace-objects", "-C", str(root), *arguments],
            capture_output=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _blob(root: Path, revision: str, path: str) -> bytes | None:
    """The bytes of ``path`` as the commit holds them, or ``None`` when absent."""
    result = _git(root, "cat-file", "blob", f"{revision}:{path}")
    if result is None or result.returncode != 0:
        return None
    return result.stdout


def _mapping(data: bytes) -> dict[str, Any] | None:
    """A YAML mapping, or ``None`` when the bytes are not one."""
    try:
        document = yaml.safe_load(data.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError, RecursionError):
        return None
    return document if isinstance(document, dict) else None


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _chart_path(declared: DeclaredRelease) -> str:
    """The chart directory: the one that holds the declared platform defaults."""
    return PurePosixPath(declared.platform_defaults).parent.as_posix()


def _source_findings_at(
    release: RenderedWorkloadRelease,
    declared: DeclaredRelease,
    blobs: Mapping[str, bytes],
) -> list[Finding]:
    """The release beside the contract and the binding the same commit holds."""
    contract_document = _mapping(blobs[declared.contract])
    try:
        contract = parse_workload_contract(contract_document)
    except (DomainError, ValueError, TypeError) as error:
        return [
            Finding(
                "release-sources-mismatch",
                declared.contract,
                f"the contract at the commit does not parse: {type(error).__name__}",
            )
        ]
    recorded_name = str(release.source.environment_binding.name)
    selected = []
    for path in declared.bindings:
        try:
            binding = parse_environment_binding(_mapping(blobs[path]))
        except (DomainError, ValueError, TypeError):
            continue
        if str(binding.metadata.name) == recorded_name:
            selected.append(binding)
    if len(selected) != 1:
        return [
            Finding(
                "release-sources-mismatch",
                "release.source.environmentBinding.name",
                f"{len(selected)} declared bindings at the commit parse and have "
                f"the name the release records, {recorded_name}; one is required",
            )
        ]
    return [
        Finding("release-sources-mismatch", refusal.field, refusal.reason)
        for refusal in verify_release_sources(release, contract, selected[0])
    ]


def _values_identity_findings(
    release: RenderedWorkloadRelease, values: bytes, path: str
) -> list[Finding]:
    document = _mapping(values) or {}
    ownership = document.get("ownership")
    ownership = ownership if isinstance(ownership, dict) else {}
    findings = []
    for field, recorded in (
        ("workloadId", str(release.metadata.workload_id)),
        ("workloadVersion", str(release.metadata.workload_version)),
    ):
        if ownership.get(field) != recorded:
            findings.append(
                Finding(
                    "release-sources-mismatch",
                    f"{path}: ownership.{field}",
                    f"the values do not name the {field} the release records",
                )
            )
    return findings


def resolve(
    revision: str, declared: DeclaredRelease, root: Path = REPO_ROOT
) -> Provenance:
    """The provenance of one desired-state release at one commit.

    ``declared`` names the release directory and the inputs it is derived from.
    Each path is read at ``revision``, from the repository at ``root``.

    Raises:
        ProvenanceRefused: the revision is not a full commit identifier, the
            repository does not hold it, a file is absent at it, or what the
            commit holds breaks a rule. Every finding of the first failing stage
            is carried, and no record is returned.
    """
    key = release_key(declared)
    if not is_immutable_revision(revision):
        raise ProvenanceRefused(
            [
                Finding(
                    "revision-not-immutable",
                    repr(revision),
                    "the value is not a full commit identifier; a name that can "
                    "move is not resolved here",
                )
            ]
        )
    exists = _git(root, "cat-file", "-e", f"{revision}^{{commit}}")
    if exists is None or exists.returncode != 0:
        detail = (
            "Git is not available, or did not answer"
            if exists is None
            else "the repository does not hold this commit; a shallow clone holds "
            "only the commits it fetched"
        )
        raise ProvenanceRefused([Finding("revision-not-readable", revision, detail)])

    chart_path = _chart_path(declared)
    chart_file = f"{chart_path}/{_CHART_FILE}"
    release_path = f"{declared.directory}/{_RELEASE_FILE}"
    values_path = f"{declared.directory}/{_VALUES_FILE}"
    paths = (
        release_path,
        values_path,
        declared.contract,
        *declared.bindings,
        chart_file,
    )
    blobs: dict[str, bytes] = {}
    absent = []
    for path in paths:
        data = _blob(root, revision, path)
        if data is None:
            absent.append(
                Finding(
                    "desired-state-absent-at-revision",
                    path,
                    f"the commit {revision} holds no file at this path",
                )
            )
        else:
            blobs[path] = data
    if absent:
        raise ProvenanceRefused(absent)

    try:
        release = parse_rendered_workload_release(_mapping(blobs[release_path]))
    except (DomainError, ValueError, TypeError) as error:
        raise ProvenanceRefused(
            [
                Finding(
                    "release-not-accepted",
                    release_path,
                    "the release document at the commit does not parse: "
                    f"{type(error).__name__}",
                )
            ]
        ) from None
    findings = [
        Finding("release-not-accepted", refusal.field, refusal.reason)
        for refusal in check_rendered_workload_release(release)
    ]
    if str(release.output.helm_values.path) != _VALUES_FILE:
        findings.append(
            Finding(
                "release-not-accepted",
                "release.output.helmValues.path",
                f"the release does not name {_VALUES_FILE}",
            )
        )
    if release.output.helm_values.sha256 != output_digest(blobs[values_path]):
        findings.append(
            Finding(
                "values-digest-mismatch",
                values_path,
                "the values file at the commit does not hash to "
                "release.output.helmValues.sha256",
            )
        )
    findings.extend(_source_findings_at(release, declared, blobs))
    findings.extend(_values_identity_findings(release, blobs[values_path], values_path))

    chart = _mapping(blobs[chart_file]) or {}
    name, version, app_version = (
        _text(chart.get(field)) for field in ("name", "version", "appVersion")
    )
    if name is None or version is None or app_version is None:
        findings.append(
            Finding(
                "chart-identity-unreadable",
                chart_file,
                "name, version, and appVersion are not each a non-empty string",
            )
        )
    if findings or name is None or version is None or app_version is None:
        order = {rule.rule_id: index for index, rule in enumerate(RULES)}
        raise ProvenanceRefused(sorted(findings, key=lambda f: order[f.rule_id]))

    source = release.source
    return Provenance(
        revision=revision,
        key=key,
        directory=declared.directory,
        release_id=str(release.metadata.release_id),
        workload_id=str(release.metadata.workload_id),
        workload_version=str(release.metadata.workload_version),
        values_sha256=str(release.output.helm_values.sha256),
        contract_sha256=str(source.contract.sha256),
        binding_name=str(source.environment_binding.name),
        binding_environment=str(source.environment_binding.environment.value),
        binding_sha256=str(source.environment_binding.sha256),
        renderer_revision=str(source.renderer.revision),
        platform_defaults_revision=str(source.platform_defaults.revision),
        chart_path=chart_path,
        chart_name=name,
        chart_version=version,
        chart_app_version=app_version,
    )


# --------------------------------------------------------------------------
# A record beside an observation
# --------------------------------------------------------------------------


def source_findings(
    provenance: Provenance, source: ReconciliationSource, repository: str
) -> tuple[Finding, ...]:
    """Every way an Application's declared source is not this release's.

    ``repository`` is the address this repository is published at. A value file is
    compared as a path from the repository root, with or without a leading ``/``.
    """
    findings = []
    if source.repository != repository:
        findings.append(
            Finding(
                "source-not-the-release",
                "repository",
                f"the source reads {source.repository}, and not {repository}",
            )
        )
    if source.chart_path.strip("/") != provenance.chart_path:
        findings.append(
            Finding(
                "source-not-the-release",
                "chart path",
                f"the source reads the chart at {source.chart_path}, and the "
                f"release was rendered for {provenance.chart_path}",
            )
        )
    value_files = [path.lstrip("/") for path in source.value_files]
    if value_files.count(provenance.values_path) != 1:
        findings.append(
            Finding(
                "source-not-the-release",
                "value files",
                f"the source does not read {provenance.values_path} exactly once",
            )
        )
    return tuple(findings)


def observed_revision_findings(
    provenance: Provenance, observed: Mapping[str, str]
) -> tuple[Finding, ...]:
    """Every reported revision that is not the commit the record was read at.

    ``observed`` maps a name for each report, such as the compared revision and
    the revision of the last sync operation, to the value the controller gave.
    An empty mapping is one finding: no observation binds nothing.
    """
    if not observed:
        return (
            Finding(
                "observed-revision-mismatch",
                "observed revisions",
                "no revision was observed, so nothing binds the record to a "
                "controller's report",
            ),
        )
    findings = []
    for name, value in sorted(observed.items()):
        if not is_immutable_revision(value):
            findings.append(
                Finding(
                    "revision-not-immutable",
                    name,
                    f"the reported value {value!r} is not a full commit identifier",
                )
            )
        elif value != provenance.revision:
            findings.append(
                Finding(
                    "observed-revision-mismatch",
                    name,
                    f"the controller reported {value}, and the record was read "
                    f"at {provenance.revision}",
                )
            )
    return tuple(findings)


def metadata_findings(
    provenance: Provenance, labels: Mapping[str, str]
) -> tuple[Finding, ...]:
    """Every provenance label an applied object does not carry as derived.

    ``labels`` is the ``metadata.labels`` of one object. Labels this module does
    not derive are not read.
    """
    findings = []
    for label, expected in provenance.workload_labels().items():
        actual = labels.get(label)
        if actual != expected:
            findings.append(
                Finding(
                    "workload-metadata-mismatch",
                    label,
                    f"the object carries {actual!r}, and the record derives "
                    f"{expected!r}",
                )
            )
    return tuple(findings)
