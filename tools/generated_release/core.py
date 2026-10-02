"""Committed generated releases, compared with what their declared sources derive.

A generated release is two files the platform writes, ``values.generated.yaml`` and
``rendered-workload-release.yaml``. A copy committed to this repository is worth
reading only while it is still what its sources produce. This module holds that
check, and the one explicit way to bring a copy back in line.

**Nothing in a committed release is trusted.** :func:`derive` builds both files
again from the release's *declared inputs* - a WorkloadContract, the
EnvironmentBindings offered to the render boundary, the platform defaults, and the
renderer and platform-defaults revisions - through the one supported path,
``generate_release``. :func:`verify` then compares the committed bytes with the
derived bytes. The revisions are declared here, not read from the committed release,
so a release that records another revision than its declaration is drift too.

**Verification never writes.** :func:`verify` reads files and returns findings. A
finding carries the reason, the field it concerns where the release parses, and a
unified diff from the committed file to the derived one. Drift is repaired only by
:func:`regenerate`, which a contributor runs on purpose and which replaces both
files through ``write_release``. Regeneration is not a review: it overwrites a hand
edit, so the diff is read first.

**The platform defaults are read, and their revision is declared.** No
platform-defaults file exists yet. The reference release's defaults are the chart's
own ``api`` defaults, read from the chart's committed ``values.yaml`` - the same
values the generated-release suite uses. So a change to those defaults is drift,
because the derived values change. The revision a release records is still the one
its declaration states: nothing here reconstructs the defaults at that revision, or
checks that either revision names a commit.

**Offline.** Every function reads committed files under the root it is given, and
:func:`regenerate` writes only the declared release directory. Nothing here
contacts a cluster, a registry, a network, or a model, and nothing runs Helm.
"""

from __future__ import annotations

import difflib
import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

import yaml

from inferops.domain.environment import EnvironmentBinding, parse_environment_binding
from inferops.domain.release import GitRevision
from inferops.domain.render import (
    RELEASE_FILE_NAME,
    VALUES_FILE_NAME,
    ApiDefaults,
    GeneratedRelease,
    HelmValuesRenderer,
    PlatformDefaults,
    generate_release,
    staging_directory,
    write_release,
)
from inferops.domain.workload import (
    CompatibilityMatrixLoader,
    DnsLabel,
    DomainError,
    parse_workload_contract,
    set_matrix_loader,
)

__all__ = [
    "DECLARED_RELEASES",
    "FIELD_CAUSES",
    "GENERATED_FILES",
    "MATRIX_PATH",
    "REPO_ROOT",
    "RULES",
    "DeclaredRelease",
    "Finding",
    "RegenerationRefused",
    "Rule",
    "SourcesRefused",
    "declared_release",
    "derive",
    "regenerate",
    "regenerate_command",
    "verify",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The compatibility matrix a contract is validated against, under the root.
MATRIX_PATH: Final = (
    "contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json"
)

#: The two files a release directory holds, in the order the writer writes them.
GENERATED_FILES: Final[tuple[str, ...]] = (str(VALUES_FILE_NAME), RELEASE_FILE_NAME)


@dataclass(frozen=True)
class DeclaredRelease:
    """One committed release directory and the committed inputs it is derived from.

    Every path is relative to the repository root, in POSIX form. The revisions are
    full Git revisions, stated here because a release cannot name the commit that
    adds it.
    """

    directory: str
    contract: str
    bindings: tuple[str, ...]
    binding_name: str | None
    platform_defaults: str
    platform_defaults_revision: str
    renderer_revision: str

    @property
    def name(self) -> str:
        """How the command selects this release: its directory's own name."""
        return PurePosixPath(self.directory).name


#: Every committed generated release, and the inputs each is derived from.
#:
#: The one entry is the reference workload on the ``local-kind`` binding. Its two
#: revisions are placeholders that name no commit, the generated-release suite's
#: own, so it is a reference render and not the record of a render at any commit.
DECLARED_RELEASES: Final[tuple[DeclaredRelease, ...]] = (
    DeclaredRelease(
        directory="tests/domain/fixtures/helm-values/support-assistant-local-kind",
        contract="contracts/workload/examples/valid/synchronous-llm-local.yaml",
        bindings=("contracts/environment/examples/valid/local-kind.yaml",),
        binding_name="local-kind",
        platform_defaults="charts/inferops-llm/values.yaml",
        platform_defaults_revision="b" * 40,
        renderer_revision="a" * 40,
    ),
)


@dataclass(frozen=True)
class Rule:
    """A property every committed generated release has to hold."""

    rule_id: str
    statement: str


#: The rules :func:`verify` applies, in the order it reports them.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "generated-release-missing",
        "A declared release directory exists.",
    ),
    Rule(
        "generated-release-file-missing",
        "A release directory holds both generated files.",
    ),
    Rule(
        "generated-release-unexpected-entry",
        "A release directory holds the two generated files and nothing else.",
    ),
    Rule(
        "generated-release-staging-left",
        "No staging directory from an unfinished write is left beside a release.",
    ),
    Rule(
        "generated-release-sources-refused",
        "The declared sources of a release still derive a release.",
    ),
    Rule(
        "generated-release-values-unrecorded",
        "The committed values file's SHA-256 is the digest the committed release records.",
    ),
    Rule(
        "generated-release-field-drifted",
        "Each field of the committed release is the field its declared sources derive.",
    ),
    Rule(
        "generated-release-file-drifted",
        "Each committed file is, byte for byte, the file its declared sources derive.",
    ),
)

#: What a difference in one release field means, for the finding that reports it.
FIELD_CAUSES: Final[Mapping[str, str]] = {
    "metadata.releaseId": (
        "the release identifier the declared inputs derive is different: an input "
        "digest or a revision changed"
    ),
    "metadata.workloadId": "the contract names another workload",
    "metadata.workloadVersion": "the contract names another workload version",
    "output.helmValues.path": (
        "the release names another values file than the one the platform writes"
    ),
    "output.helmValues.sha256": (
        "the values the declared sources derive are not the values this release records"
    ),
    "source.contract.apiVersion": "the contract declares another version",
    "source.contract.sha256": (
        "the recorded contract digest is stale: the contract changed after this "
        "release was generated"
    ),
    "source.environmentBinding.apiVersion": "the binding declares another version",
    "source.environmentBinding.environment": (
        "the release names another environment than the declared binding serves"
    ),
    "source.environmentBinding.name": (
        "the release names another binding than the declared one"
    ),
    "source.environmentBinding.sha256": (
        "the recorded binding digest is stale: the binding changed after this "
        "release was generated"
    ),
    "source.platformDefaults.revision": (
        "the release records another platform-defaults revision than its "
        "declaration states"
    ),
    "source.renderer.revision": (
        "the release records another renderer revision than its declaration states"
    ),
}


@dataclass(frozen=True)
class Finding:
    """One way a committed release differs from what its declared sources derive.

    ``subject`` is a file name, a field path inside the release, or the directory.
    ``diff`` is a unified diff from the committed file to the derived one, empty
    when the finding has none.
    """

    rule_id: str
    release: str
    subject: str
    detail: str
    diff: tuple[str, ...] = ()


class SourcesRefused(Exception):
    """The declared sources do not derive a release, for the reasons given."""

    def __init__(self, release: str, reason: str) -> None:
        super().__init__(f"{release}: {reason}")
        self.release = release
        self.reason = reason


class RegenerationRefused(Exception):
    """A regeneration that would remove or overwrite something it did not write."""

    def __init__(self, findings: Sequence[Finding]) -> None:
        super().__init__("; ".join(f"{f.rule_id} {f.subject}" for f in findings))
        self.findings = tuple(findings)


def declared_release(name: str) -> DeclaredRelease:
    """The declared release with this directory name.

    Raises:
        KeyError: no declared release has this name.
    """
    for declared in DECLARED_RELEASES:
        if declared.name == name:
            return declared
    raise KeyError(name)


def regenerate_command(declared: DeclaredRelease) -> str:
    """The command that regenerates one release, as a finding prints it."""
    return f"python -m tools.generated_release --write {declared.name}"


# --------------------------------------------------------------------------
# Deriving a release from its declared inputs
# --------------------------------------------------------------------------


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _chart_api_defaults(path: Path, revision: str) -> PlatformDefaults:
    """The chart's own API defaults, read from its values file, at ``revision``."""
    document = _load_yaml(path)
    api = document.get("api") if isinstance(document, dict) else None
    if not isinstance(api, dict):
        raise ValueError(f"{path.name} has no api mapping to read the defaults from")
    try:
        settings = {
            "request_timeout_ms": api["requestTimeoutMs"],
            "drain_timeout_ms": api["drainTimeoutMs"],
            "max_output_tokens": api["maxOutputTokens"],
        }
    except KeyError as missing:
        raise ValueError(f"{path.name} sets no api.{missing.args[0]}") from None
    return PlatformDefaults("v1alpha1", GitRevision(revision), ApiDefaults(**settings))


def derive(declared: DeclaredRelease, root: Path = REPO_ROOT) -> GeneratedRelease:
    """Both files of ``declared``, derived again from its declared inputs.

    Raises:
        SourcesRefused: a declared input is missing, does not parse, or is refused
            by the render boundary, the renderer, or the release recorder.
    """
    try:
        matrix = json.loads((root / MATRIX_PATH).read_text(encoding="utf-8"))
        set_matrix_loader(CompatibilityMatrixLoader(matrix))
        contract = parse_workload_contract(_load_yaml(root / declared.contract))
        bindings: list[EnvironmentBinding] = [
            parse_environment_binding(_load_yaml(root / path))
            for path in declared.bindings
        ]
        defaults = _chart_api_defaults(
            root / declared.platform_defaults, declared.platform_defaults_revision
        )
        return generate_release(
            HelmValuesRenderer(GitRevision(declared.renderer_revision)),
            contract,
            defaults,
            bindings,
            binding_name=(
                None
                if declared.binding_name is None
                else DnsLabel(declared.binding_name)
            ),
        )
    except (DomainError, OSError, ValueError, yaml.YAMLError) as error:
        raise SourcesRefused(
            declared.name, f"{type(error).__name__}: {error}"
        ) from error


# --------------------------------------------------------------------------
# Comparing a committed release with the derived one
# --------------------------------------------------------------------------


def _text(data: bytes) -> list[str]:
    """Lines for a diff. A generated file is ASCII, so any other byte is escaped."""
    return data.decode("ascii", errors="backslashreplace").splitlines()


def _diff(
    declared: DeclaredRelease, name: str, committed: bytes, derived: bytes
) -> tuple[str, ...]:
    return tuple(
        difflib.unified_diff(
            _text(committed),
            _text(derived),
            fromfile=f"committed/{declared.directory}/{name}",
            tofile=f"derived/{declared.directory}/{name}",
            lineterm="",
        )
    )


def _leaves(document: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every leaf of a parsed document, by dotted path."""
    if isinstance(document, Mapping) and document:
        for key, value in document.items():
            yield from _leaves(value, f"{prefix}{key}.")
    else:
        yield prefix.rstrip("."), document


#: A field one side of a comparison does not have.
_ABSENT: Final = object()


def _shown(value: Any) -> str:
    return "(absent)" if value is _ABSENT else json.dumps(value, default=str)


def _field_findings(
    declared: DeclaredRelease, committed: Any, derived: GeneratedRelease
) -> list[Finding]:
    if not isinstance(committed, Mapping):
        return []
    old = dict(_leaves(committed))
    new = dict(_leaves(derived.release.as_document()))
    findings = []
    for path in sorted(set(old) | set(new)):
        before, after = old.get(path, _ABSENT), new.get(path, _ABSENT)
        if before == after:
            continue
        cause = FIELD_CAUSES.get(
            path, "this field is not what the declared sources derive"
        )
        findings.append(
            Finding(
                "generated-release-field-drifted",
                declared.name,
                path,
                f"{cause}; committed {_shown(before)}, derived {_shown(after)}",
            )
        )
    return findings


def _recorded_values_digest(committed: Any) -> str | None:
    try:
        recorded = committed["output"]["helmValues"]["sha256"]
    except (KeyError, TypeError):
        return None
    return recorded if isinstance(recorded, str) else None


def _file_finding(
    declared: DeclaredRelease, name: str, committed: bytes, derived: bytes
) -> Finding:
    if committed.replace(b"\r\n", b"\n") == derived:
        return Finding(
            "generated-release-file-drifted",
            declared.name,
            name,
            "the file differs only in line endings: generated files are LF only, and "
            "the directory must be pinned to eol=lf in .gitattributes",
        )
    return Finding(
        "generated-release-file-drifted",
        declared.name,
        name,
        "the committed file is not the file its declared sources derive",
        _diff(declared, name, committed, derived),
    )


def _layout_findings(declared: DeclaredRelease, directory: Path) -> list[Finding]:
    findings = []
    staging = staging_directory(directory)
    if staging.exists() or staging.is_symlink():
        findings.append(
            Finding(
                "generated-release-staging-left",
                declared.name,
                staging.name,
                "an earlier write did not finish; remove the staging directory",
            )
        )
    if not directory.is_dir():
        occupied = directory.exists() or directory.is_symlink()
        findings.insert(
            0,
            Finding(
                "generated-release-missing",
                declared.name,
                declared.directory,
                "the declared release path is not a directory"
                if occupied
                else "the declared release directory does not exist",
            ),
        )
        return findings
    for entry in sorted(directory.iterdir(), key=lambda path: path.name):
        if entry.name not in GENERATED_FILES or not entry.is_file():
            findings.append(
                Finding(
                    "generated-release-unexpected-entry",
                    declared.name,
                    entry.name,
                    "the platform writes nothing else into a release directory",
                )
            )
    for name in GENERATED_FILES:
        if not (directory / name).is_file():
            findings.append(
                Finding(
                    "generated-release-file-missing",
                    declared.name,
                    name,
                    "the release directory does not hold this generated file",
                )
            )
    return findings


def verify(declared: DeclaredRelease, root: Path = REPO_ROOT) -> tuple[Finding, ...]:
    """Every way the committed release differs from its declared sources' release.

    An empty result means both committed files are, byte for byte, the files the
    declared inputs derive today, and nothing else is in the directory. This reads
    files and writes none.
    """
    directory = root / declared.directory
    findings = _layout_findings(declared, directory)
    try:
        derived = derive(declared, root)
    except SourcesRefused as refused:
        findings.append(
            Finding(
                "generated-release-sources-refused",
                declared.name,
                declared.contract,
                f"nothing was compared: {refused.reason}",
            )
        )
        return _in_rule_order(findings)
    if not directory.is_dir():
        return _in_rule_order(findings)

    present = {
        name: (directory / name).read_bytes()
        for name in GENERATED_FILES
        if (directory / name).is_file()
    }
    committed_release: Any = None
    if RELEASE_FILE_NAME in present:
        try:
            committed_release = yaml.safe_load(present[RELEASE_FILE_NAME])
        except yaml.YAMLError:
            committed_release = None

    values = present.get(str(VALUES_FILE_NAME))
    recorded = _recorded_values_digest(committed_release)
    if values is not None and recorded is not None:
        actual = hashlib.sha256(values).hexdigest()
        if actual != recorded:
            findings.append(
                Finding(
                    "generated-release-values-unrecorded",
                    declared.name,
                    str(VALUES_FILE_NAME),
                    "the committed release does not record the committed values: the "
                    f"values file was changed after it was generated; recorded "
                    f"{recorded}, actual {actual}",
                )
            )

    if present.get(RELEASE_FILE_NAME, derived.release_bytes) != derived.release_bytes:
        findings.extend(_field_findings(declared, committed_release, derived))

    for name, derived_bytes in derived.files():
        committed = present.get(name)
        if committed is not None and committed != derived_bytes:
            findings.append(_file_finding(declared, name, committed, derived_bytes))
    return _in_rule_order(findings)


def _in_rule_order(findings: list[Finding]) -> tuple[Finding, ...]:
    """Findings in the order :data:`RULES` lists their rules; stable within one."""
    order = {rule.rule_id: index for index, rule in enumerate(RULES)}
    return tuple(sorted(findings, key=lambda finding: order[finding.rule_id]))


# --------------------------------------------------------------------------
# Regenerating a release, which a contributor asks for by name
# --------------------------------------------------------------------------


def regenerate(declared: DeclaredRelease, root: Path = REPO_ROOT) -> bool:
    """Write both files of ``declared`` again from its declared inputs.

    Returns ``True`` when the files were written, and ``False`` when the committed
    files were already the derived ones and nothing was touched.

    The directory is replaced only when it holds the two generated files and
    nothing else. The two files are removed, then ``write_release`` writes both or
    neither. If that write fails, the directory is absent rather than half written,
    and running this again writes it.

    Raises:
        SourcesRefused: the declared inputs derive no release; nothing is touched.
        RegenerationRefused: the directory holds something the platform did not
            write, or a staging directory is left beside it; nothing is touched.
    """
    derived = derive(declared, root)
    directory = root / declared.directory
    occupied = not directory.is_dir() and (directory.exists() or directory.is_symlink())
    blocking = [
        finding
        for finding in _layout_findings(declared, directory)
        if finding.rule_id
        in {"generated-release-unexpected-entry", "generated-release-staging-left"}
        or (finding.rule_id == "generated-release-missing" and occupied)
    ]
    if blocking:
        raise RegenerationRefused(blocking)
    if directory.is_dir():
        if all(
            (directory / name).is_file() and (directory / name).read_bytes() == data
            for name, data in derived.files()
        ):
            return False
        for name in GENERATED_FILES:
            (directory / name).unlink(missing_ok=True)
        directory.rmdir()
    write_release(derived, directory)
    return True
