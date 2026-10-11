"""Check the evidence directory of an experiment run against its manifest.

A run of an experiment has one directory. The directory holds the run's
ExperimentRun manifest and the evidence files that the manifest names.
``tools.experiment_run`` validates the manifest and opens no evidence file. This
module opens the files: it holds a run directory to its manifest, to its place in
the proof tree, to its freeze record, and to the corrections that were added
beside it.

**The layout.**

    docs/proof/experiments/<experiment>/
        <freeze record>                        the record a manifest names
        runs/<runId>/run.v1alpha1.json         the manifest
        runs/<runId>/<evidence path>           each evidence file it names
        corrections/<runId>/correction-<n>.v1alpha1.json
        corrections/<runId>/correction-<n>/<evidence path>

**Hashing.** A digest is the SHA-256 of a file's content with each CRLF replaced by
LF. It is the digest that ``tools.evidence_index`` gives a text file, and this
module calls that function. An evidence file must have a suffix that the index
hashes as text, so one file has one digest in each tool and on each host.

**Raw and derived.** Each evidence file has a registered role, and each role is raw
or derived. A raw file is what a run read or wrote as it executed. A derived file is
computed or written from raw files. A run that names a derived file names a raw
file, and ``run_digests`` gives one digest over the raw files alone. A corrected
summary does not move it.

**Corrections.** A committed run directory is not edited. A correction is a new
file beside the ``runs`` directory. It states the digest of the manifest and of each
file it corrects, so a correction of a file that was edited is refused.

**What this module does not do.** It reads one tree. It does not read Git, so it
does not show that a file was committed, or that a run directory was not replaced
as a whole with its manifest. It does not judge a result. It does not read a raw
file for its meaning, except a caller record. It does not show that a derived file
was computed from the raw files. It assigns no evidence level and reads no claim.

Everything here is offline and deterministic: no network, no cluster, no clock, no
randomness.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

# The prefixes are the WorkloadContract validator's own list. A second list here
# could come to differ from it.
from tools.contract_validation.workload import _CREDENTIAL_PREFIXES
from tools.evidence_index.core import (
    TEXT_SUFFIXES,
    content_sha256,
    evidence_set_sha256,
)
from tools.experiment_run.core import (
    CONFORMING,
    MANIFEST_NAME,
    PRE_SCHEMA,
    REPO_ROOT,
    RUNS_ROOT_REF,
    SUPPORTED_API_VERSION,
    RunDocumentError,
    content_digest,
    load_schema,
    read_document,
    validate,
)
from tools.experiment_run.core import repository_report as manifest_listing
from tools.reliability_runner.core import RunnerError, read_record
from tools.reliability_runner.incluster import MODE_IN_CLUSTER

RUNS_DIRECTORY: Final = "runs"
CORRECTIONS_DIRECTORY: Final = "corrections"
CORRECTION_KIND: Final = "ExperimentRunCorrection"

#: The file suffixes of an evidence file: the ones the evidence index hashes as
#: text. It is the index's own set, so the two cannot come to differ.
EVIDENCE_SUFFIXES: Final = TEXT_SUFFIXES

RAW: Final = "raw"
DERIVED: Final = "derived"

#: The status of a run directory that a rule refused. The two other statuses are
#: those of the manifest listing: ``conforming`` and ``pre-schema``.
REFUSED: Final = "refused"


@dataclass(frozen=True)
class Role:
    """One registered role of an evidence file."""

    kind: str
    holds: str


#: Every role an evidence file of a run directory can have. A raw role names what a
#: run read or wrote as it executed. A derived role names what is computed or
#: written from raw files. No role requires a prompt, a response body, a
#: credential, or a path of a host.
ROLES: Final[Mapping[str, Role]] = {
    "caller": Role(
        RAW,
        "The caller's own record of its requests, as the reliability runner writes it.",
    ),
    "endpoints": Role(RAW, "Readings of the Service endpoints, each with its time."),
    "pods": Role(RAW, "Readings of the pods, each with its time."),
    "deployments": Role(RAW, "Readings of the Deployments, each with its time."),
    "argo": Role(RAW, "Readings of the Argo CD Application, each with its time."),
    "telemetry": Role(RAW, "Readings of the metrics that the frozen record registers."),
    "resources": Role(RAW, "Readings of resource use, each with its time."),
    "transcript": Role(RAW, "What the commands printed, with each exit status."),
    "commands": Role(RAW, "The commands of the run, in order, or the driver."),
    "environment": Role(RAW, "The environment identity as the run read it."),
    "release": Role(RAW, "The release and its provenance as the run read them."),
    "analysis": Role(DERIVED, "Figures that are computed from raw files."),
    "result": Role(DERIVED, "The result page: each criterion and its verdict."),
}

#: The role of the caller's own record. It is the one role a rule reads the file of.
CALLER_ROLE: Final = "caller"

RULE_MANIFEST_MISSING: Final = "evidence-manifest-missing"
RULE_MANIFEST_REFUSED: Final = "evidence-manifest-refused"
RULE_MISPLACED: Final = "evidence-run-directory-misplaced"
RULE_FREEZE: Final = "evidence-freeze-record-differs"
RULE_FILE_MISSING: Final = "evidence-file-missing"
RULE_FILE_UNLISTED: Final = "evidence-file-unlisted"
RULE_FILE_NOT_REGULAR: Final = "evidence-file-not-regular"
RULE_FILE_FORM: Final = "evidence-file-form-unsupported"
RULE_FILE_DIGEST: Final = "evidence-file-digest-differs"
RULE_FILE_CREDENTIAL: Final = "evidence-file-credential-prefix"
RULE_FILE_PERSONAL_PATH: Final = "evidence-file-personal-path"
RULE_ROLE: Final = "evidence-role-unregistered"
RULE_SUMMARY: Final = "evidence-summary-without-raw"
RULE_CALLER_RECORD: Final = "evidence-caller-record-refused"
RULE_CALLER_IDENTITY: Final = "evidence-caller-record-identity-differs"
RULE_CORRECTION_RUN: Final = "evidence-correction-run-unknown"
RULE_CORRECTION_UNREADABLE: Final = "evidence-correction-unreadable"
RULE_CORRECTION_NUMBER: Final = "evidence-correction-number-out-of-sequence"
RULE_CORRECTION_IDENTITY: Final = "evidence-correction-identity-differs"
RULE_CORRECTION_CHAIN: Final = "evidence-correction-chain-broken"
RULE_CORRECTION_TARGET: Final = "evidence-correction-target-differs"

#: Each rule with its statement. The layout document publishes the same statements,
#: and a test compares the two.
RULES: Final[Mapping[str, str]] = {
    RULE_MANIFEST_MISSING: (
        f"A run directory holds one run manifest, named {MANIFEST_NAME}."
    ),
    RULE_MANIFEST_REFUSED: (
        "The manifest of a run directory validates as an ExperimentRun."
    ),
    RULE_MISPLACED: (
        "A run directory is named by its run identifier, in the runs directory "
        "beside the freeze record that its manifest names, and that record is a "
        f"file of one directory of {RUNS_ROOT_REF}."
    ),
    RULE_FREEZE: (
        "The freeze record that a manifest names is present, and it has the "
        "revision and the content digest that the manifest states."
    ),
    RULE_FILE_MISSING: (
        "Each evidence file that a manifest or a correction names is present."
    ),
    RULE_FILE_UNLISTED: (
        "Each file of a run directory is the manifest or an evidence file that the "
        "manifest names, and each file of a corrections directory is a correction "
        "or a file that a correction names."
    ),
    RULE_FILE_NOT_REGULAR: "An evidence file is a regular file and not a link.",
    RULE_FILE_FORM: (
        "An evidence file is UTF-8 text with no NUL character, under a file suffix "
        "that the evidence index hashes as text."
    ),
    RULE_FILE_DIGEST: (
        "The digest stated for an evidence file is the SHA-256 of the file's "
        "content with each CRLF replaced by LF."
    ),
    RULE_FILE_CREDENTIAL: (
        "No word of an evidence file or of a correction starts with the published "
        "prefix of a credential format."
    ),
    RULE_FILE_PERSONAL_PATH: (
        "No evidence file and no correction holds a path under a user directory "
        "of a host."
    ),
    RULE_ROLE: "Each evidence file has a registered role.",
    RULE_SUMMARY: "A run that names a derived file names at least one raw file.",
    RULE_CALLER_RECORD: (
        "A file with the role caller is a caller record that the reliability "
        "runner's reader accepts."
    ),
    RULE_CALLER_IDENTITY: (
        "A caller record names the experiment, the run, the caller profile "
        "revision, the concurrency, and the release of its manifest, and it is not "
        "a rehearsal."
    ),
    RULE_CORRECTION_RUN: (
        "A corrections directory names a run directory of this layout in the same "
        "experiment directory."
    ),
    RULE_CORRECTION_UNREADABLE: (
        "A correction is one JSON object with exactly the registered members, each "
        "in its form."
    ),
    RULE_CORRECTION_NUMBER: (
        "The corrections of a run are numbered from 1 with no gap, and each file "
        "name states its number."
    ),
    RULE_CORRECTION_IDENTITY: (
        "A correction names the experiment, the run, and the present manifest "
        "digest of the run it corrects."
    ),
    RULE_CORRECTION_CHAIN: (
        "The first correction of a run names no earlier one, and each later one "
        "states the content digest of the correction before it."
    ),
    RULE_CORRECTION_TARGET: (
        "A correction names each file it corrects by its path and its present "
        "digest: the manifest, an evidence file of the manifest, or an earlier "
        "correction."
    ),
}

#: The members of a correction, and no other.
CORRECTION_MEMBERS: Final = frozenset(
    {
        "schemaVersion",
        "kind",
        "experimentId",
        "runId",
        "number",
        "recordedAt",
        "manifestSha256",
        "previousCorrectionSha256",
        "corrects",
        "statements",
        "files",
    }
)
_TARGET_MEMBERS: Final = frozenset({"path", "sha256"})
_FILE_MEMBERS: Final = frozenset({"role", "path", "sha256"})
MAXIMUM_STATEMENT_LENGTH: Final = 2000

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_INSTANT: Final = re.compile(
    r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.[0-9]{1,6})?Z"
)
_CORRECTION_FILE: Final = re.compile(r"correction-([1-9][0-9]{0,3})\.v1alpha1\.json")
_CORRECTION_DIRECTORY: Final = re.compile(r"correction-([1-9][0-9]{0,3})")
# The characters that end a word of an evidence file. A JSON document with no white
# space is one word to `str.split`, so the punctuation of JSON, of YAML, and of a
# shell assignment ends a word too.
_WORD_BREAK: Final = re.compile(r"[\s\"'`,;:=(){}\[\]<>\\|]+")
# A path under a user directory: a drive letter before `Users` or `home`, or
# `Users` or `home` before a name and a separator. It is the pattern of the
# security baseline suite, and it also reads a separator that JSON wrote twice.
_PERSONAL_PATH: Final = re.compile(
    r"[A-Za-z]:[\\/]{1,2}(?:Users|home)[\\/]"
    r"|[\\/](?:Users|home)[\\/]{1,2}[A-Za-z0-9._-]+[\\/]"
)


@dataclass(frozen=True, order=True)
class Finding:
    """One refusal: the file or directory, the rule, and why."""

    path: str
    rule: str
    message: str


class LayoutError(RuntimeError):
    """A helper was asked for something the layout refuses."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule
        self.message = message


def printable(name: str) -> str:
    """A name for one output line: a line break in a name cannot start a line."""
    return "".join(c if c.isprintable() else "?" for c in name)


def _evidence_path_pattern() -> re.Pattern[str]:
    """The form of an evidence path, read from the published schema."""
    return re.compile(load_schema()["$defs"]["evidencePath"]["pattern"])


# --------------------------------------------------------------------------
# One file
# --------------------------------------------------------------------------


def is_raw(role: str) -> bool:
    """Whether a registered role is raw. An unregistered role is not."""
    registered = ROLES.get(role)
    return registered is not None and registered.kind == RAW


def file_digest(path: Path) -> str:
    """The digest of one evidence file: the evidence index's digest of a text file."""
    return content_sha256(path)


def form_problem(path: Path) -> str | None:
    """Why a file cannot be an evidence file, or None when it can."""
    if path.suffix not in EVIDENCE_SUFFIXES:
        return "the file suffix is not one the evidence index hashes as text"
    try:
        data = path.read_bytes()
    except OSError:
        return "the file is unreadable"
    if b"\0" in data:
        return "the file holds a NUL character"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "the file is not UTF-8 text"
    return None


def text_problems(text: str) -> list[tuple[str, str]]:
    """The public-safety rules a text breaks, each with its message.

    The credential rule reads the start of each word for a published prefix. It
    does not apply the WorkloadContract's shape heuristic: raw evidence holds
    digests, identifiers, and encoded values that have that shape.
    """
    problems: list[tuple[str, str]] = []
    if any(word.startswith(_CREDENTIAL_PREFIXES) for word in _WORD_BREAK.split(text)):
        problems.append(
            (
                RULE_FILE_CREDENTIAL,
                "a word starts with the published prefix of a credential format",
            )
        )
    if _PERSONAL_PATH.search(text) is not None:
        problems.append(
            (
                RULE_FILE_PERSONAL_PATH,
                "the file holds a path under a user directory of a host",
            )
        )
    return problems


def _file_findings(path: Path, ref: str, stated: str) -> list[Finding]:
    """The form, digest, and public-safety findings of one present file."""
    problem = form_problem(path)
    if problem is not None:
        return [Finding(ref, RULE_FILE_FORM, problem)]
    findings: list[Finding] = []
    if file_digest(path) != stated:
        findings.append(
            Finding(
                ref,
                RULE_FILE_DIGEST,
                "the file does not have the digest that is stated for it",
            )
        )
    text = path.read_bytes().decode("utf-8")
    findings.extend(Finding(ref, rule, why) for rule, why in text_problems(text))
    return findings


def describe_file(run_dir: Path, relative: str, role: str) -> dict[str, str]:
    """One ``evidence.files`` entry for a file of a run directory.

    A writer of a manifest calls this for each file. A role that is not registered,
    a path that is not an evidence path, a file that is absent, and a file that the
    layout refuses each raise ``LayoutError``, so a manifest is not written for a
    directory that the check would refuse.
    """
    if role not in ROLES:
        raise LayoutError(RULE_ROLE, "the role is not a registered role")
    if (
        _evidence_path_pattern().fullmatch(relative) is None
        or relative == MANIFEST_NAME
    ):
        raise LayoutError(RULE_FILE_FORM, "the path is not an evidence path")
    path = run_dir / relative
    if path.is_symlink() or not path.is_file():
        raise LayoutError(RULE_FILE_MISSING, "the path names no regular file")
    problem = form_problem(path)
    if problem is not None:
        raise LayoutError(RULE_FILE_FORM, problem)
    for rule, why in text_problems(path.read_bytes().decode("utf-8")):
        raise LayoutError(rule, why)
    return {"role": role, "path": relative, "sha256": file_digest(path)}


def _walk(directory: Path) -> tuple[dict[str, Path], list[str]]:
    """The regular files of a directory by relative path, and the links it holds."""
    files: dict[str, Path] = {}
    links: list[str] = []
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink():
            links.append(relative)
        elif path.is_file():
            files[relative] = path
    return files, links


# --------------------------------------------------------------------------
# One run directory
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RunDigests:
    """The digests of a run directory that no rule refused.

    ``raw`` is over the raw evidence files alone, and it is None when the run names
    none. ``evidence_set`` is over the manifest and every evidence file. Each is the
    evidence index's set digest over repository paths. No correction is in either.
    """

    raw: str | None
    evidence_set: str


@dataclass(frozen=True)
class RunReport:
    """What the check found for one run directory."""

    path: str
    status: str
    findings: tuple[Finding, ...] = ()
    files: int = 0
    raw_files: int = 0
    corrections: int = 0
    digests: RunDigests | None = None


def _relative(root: Path, path: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _exact_file(root: Path, ref: str) -> Path | None:
    """The file a repository path names, with each segment compared as text.

    A file system that ignores letter case opens a file under a name in another
    case. One tree would then pass on one host and fail on another.
    """
    current = root
    for segment in ref.split("/"):
        try:
            names = {entry.name for entry in current.iterdir()}
        except OSError:
            return None
        if segment not in names:
            return None
        current = current / segment
    return current if current.is_file() and not current.is_symlink() else None


def expected_run_ref(manifest: Mapping[str, Any]) -> str | None:
    """Where the layout puts the run of a manifest, or None when it has no place.

    The place is ``runs/<runId>`` beside the freeze record. The freeze record must
    be a file of one directory of ``docs/proof/experiments``.
    """
    freeze = manifest["metadata"]["spec"]["freezeRecord"]
    parts = freeze.split("/")
    if len(parts) != 5 or "/".join(parts[:3]) != RUNS_ROOT_REF:
        return None
    return "/".join([*parts[:4], RUNS_DIRECTORY, manifest["metadata"]["runId"]])


def _freeze_findings(root: Path, manifest: Mapping[str, Any]) -> list[Finding]:
    spec = manifest["metadata"]["spec"]
    ref = spec["freezeRecord"]
    path = _exact_file(root, ref)
    differs = Finding(
        ref,
        RULE_FREEZE,
        "the freeze record is absent, or it does not have the revision and the "
        "content digest that the manifest states",
    )
    if path is None:
        return [differs]
    data = path.read_bytes()
    if content_digest(data) != spec["freezeContentSha256"]:
        return [differs]
    try:
        document = json.loads(data.decode("utf-8"))
        revision = document["metadata"]["revision"]
    except (ValueError, KeyError, TypeError):
        return [differs]
    if isinstance(revision, bool) or revision != spec["freezeRevision"]:
        return [differs]
    return []


def _caller_findings(
    path: Path, ref: str, manifest: Mapping[str, Any]
) -> list[Finding]:
    try:
        record = read_record(path.read_bytes().decode("utf-8"))
    except RunnerError as error:
        return [
            Finding(
                ref,
                RULE_CALLER_RECORD,
                f"the reliability runner's reader refuses the file: {error.rule}",
            )
        ]
    header = record.header
    profile = manifest["callerProfile"]
    same = (
        profile["applies"]
        and header["mode"] == MODE_IN_CLUSTER
        and header["experimentId"] == manifest["metadata"]["experimentId"]
        and header["runId"] == manifest["metadata"]["runId"]
        and header["profile"]
        == {
            "profileId": profile["profileId"],
            "profileRevision": profile["profileRevision"],
            "profileSha256": profile["contentSha256"],
        }
        and header["concurrency"] == profile["concurrency"]
        and header["release"]["releaseId"] in (None, manifest["release"]["releaseId"])
    )
    if same:
        return []
    return [
        Finding(
            ref,
            RULE_CALLER_IDENTITY,
            "the caller record is a rehearsal, or it names another experiment, "
            "run, caller profile revision, concurrency, or release than the "
            "manifest",
        )
    ]


def _listed_findings(
    prefix: str,
    entries: Sequence[Mapping[str, str]],
    present: Mapping[str, Path],
) -> list[Finding]:
    """The findings of the files a manifest or a correction names."""
    findings: list[Finding] = []
    for entry in entries:
        ref = f"{prefix}/{entry['path']}"
        if entry["role"] not in ROLES:
            findings.append(
                Finding(ref, RULE_ROLE, "the role of the file is not registered")
            )
        path = present.get(entry["path"])
        if path is None:
            findings.append(
                Finding(ref, RULE_FILE_MISSING, "the file that is named is absent")
            )
            continue
        findings.extend(_file_findings(path, ref, entry["sha256"]))
    return findings


def run_digests(
    run_ref: str, manifest_sha256: str, manifest: Mapping[str, Any]
) -> RunDigests:
    """The raw digest and the set digest of a run, from its stated digests."""
    rows = [
        {"path": f"{run_ref}/{entry['path']}", "sha256": entry["sha256"]}
        for entry in manifest["evidence"]["files"]
    ]
    raw = [
        row
        for row, entry in zip(rows, manifest["evidence"]["files"], strict=True)
        if is_raw(entry["role"])
    ]
    manifest_row = {"path": f"{run_ref}/{MANIFEST_NAME}", "sha256": manifest_sha256}
    return RunDigests(
        raw=evidence_set_sha256(raw) if raw else None,
        evidence_set=evidence_set_sha256([*rows, manifest_row]),
    )


def check_run(run_dir: Path, root: Path = REPO_ROOT) -> RunReport:
    """Hold one run directory to its manifest and to the layout.

    ``root`` is the root of the tree that holds the proof tree. The check reads the
    manifest, the freeze record it names, each file of the run directory, and the
    corrections beside the ``runs`` directory.
    """
    run_ref = _relative(root, run_dir)
    shown = printable(run_ref if run_ref is not None else run_dir.as_posix())
    manifest_path = run_dir / MANIFEST_NAME
    present, links = _walk(run_dir) if run_dir.is_dir() else ({}, [])
    if MANIFEST_NAME not in present:
        return RunReport(
            shown,
            REFUSED,
            (
                Finding(
                    shown, RULE_MANIFEST_MISSING, "the directory holds no run manifest"
                ),
            ),
        )
    try:
        manifest = read_document(manifest_path)
        refusals = len(validate(manifest))
    except RunDocumentError:
        manifest, refusals = {}, 1
    if refusals:
        return RunReport(
            shown,
            REFUSED,
            (
                Finding(
                    f"{shown}/{MANIFEST_NAME}",
                    RULE_MANIFEST_REFUSED,
                    f"the ExperimentRun validator refuses the manifest with "
                    f"{refusals} finding(s)",
                ),
            ),
        )

    findings: list[Finding] = []
    expected = expected_run_ref(manifest)
    if expected is None or run_ref != expected:
        findings.append(
            Finding(
                shown,
                RULE_MISPLACED,
                "the directory is not runs/<runId> beside the freeze record that "
                "the manifest names",
            )
        )
    findings.extend(_freeze_findings(root, manifest))

    entries = manifest["evidence"]["files"]
    listed = {entry["path"] for entry in entries}
    findings.extend(
        Finding(
            f"{shown}/{printable(name)}", RULE_FILE_NOT_REGULAR, "the entry is a link"
        )
        for name in links
    )
    findings.extend(
        Finding(
            f"{shown}/{printable(name)}",
            RULE_FILE_UNLISTED,
            "the manifest does not name the file",
        )
        for name in sorted(set(present) - listed - {MANIFEST_NAME})
    )
    findings.extend(_listed_findings(shown, entries, present))
    roles = {entry["role"] for entry in entries}
    if any(role in ROLES and not is_raw(role) for role in roles) and not any(
        is_raw(role) for role in roles
    ):
        findings.append(
            Finding(
                f"{shown}/{MANIFEST_NAME}",
                RULE_SUMMARY,
                "the run names a derived file and no raw file",
            )
        )
    for entry in entries:
        path = present.get(entry["path"])
        if (
            entry["role"] == CALLER_ROLE
            and path is not None
            and form_problem(path) is None
        ):
            findings.extend(
                _caller_findings(path, f"{shown}/{entry['path']}", manifest)
            )

    manifest_sha256 = file_digest(manifest_path)
    corrections = 0
    if expected is not None and run_ref == expected:
        correction_dir = (
            run_dir.parent.parent
            / CORRECTIONS_DIRECTORY
            / manifest["metadata"]["runId"]
        )
        if correction_dir.is_dir():
            corrections, found = _correction_findings(
                correction_dir,
                _relative(root, correction_dir) or correction_dir.as_posix(),
                manifest,
                manifest_sha256,
                present,
            )
            findings.extend(found)

    if findings:
        return RunReport(shown, REFUSED, tuple(sorted(findings)))
    return RunReport(
        shown,
        CONFORMING,
        (),
        files=len(entries),
        raw_files=sum(1 for entry in entries if is_raw(entry["role"])),
        corrections=corrections,
        digests=run_digests(shown, manifest_sha256, manifest),
    )


# --------------------------------------------------------------------------
# Corrections
# --------------------------------------------------------------------------


def _is_instant(value: object) -> bool:
    if not isinstance(value, str):
        return False
    match = _INSTANT.fullmatch(value)
    if match is None:
        return False
    try:
        datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _rows(value: object, members: frozenset[str]) -> bool:
    return isinstance(value, list) and all(
        isinstance(row, dict)
        and set(row) == members
        and all(isinstance(row[name], str) for name in members)
        and _is_digest(row["sha256"])
        for row in value
    )


def correction_problem(document: Any) -> str | None:
    """Why a document is not a correction in its form, or None when it is.

    The form is checked here and nothing else: not the run, the number in the
    sequence, or a digest of a file.
    """
    if not isinstance(document, dict) or set(document) != CORRECTION_MEMBERS:
        return "the document does not have exactly the registered members"
    if (
        document["schemaVersion"] != SUPPORTED_API_VERSION
        or document["kind"] != CORRECTION_KIND
    ):
        return "the document does not state the supported version and kind"
    number = document["number"]
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        return "the number is not a positive integer"
    if not isinstance(document["experimentId"], str) or not isinstance(
        document["runId"], str
    ):
        return "the experiment or the run identifier is not a string"
    if not _is_instant(document["recordedAt"]):
        return "the recorded time is not a UTC instant"
    if not _is_digest(document["manifestSha256"]):
        return "the manifest digest is not a SHA-256"
    previous = document["previousCorrectionSha256"]
    if previous is not None and not _is_digest(previous):
        return "the digest of the earlier correction is not a SHA-256 or null"
    if not _rows(document["corrects"], _TARGET_MEMBERS) or not document["corrects"]:
        return "the corrected files are not one or more rows of a path and a digest"
    statements = document["statements"]
    if (
        not isinstance(statements, list)
        or not statements
        or not all(
            isinstance(statement, str)
            and 0 < len(statement) <= MAXIMUM_STATEMENT_LENGTH
            for statement in statements
        )
    ):
        return "the statements are not one or more bounded statements"
    files = document["files"]
    pattern = _evidence_path_pattern()
    if not _rows(files, _FILE_MEMBERS) or not all(
        pattern.fullmatch(row["path"]) is not None for row in files
    ):
        return "the added files are not rows of a role, an evidence path, and a digest"
    if len({row["path"] for row in files}) != len(files):
        return "one added file is named twice"
    return None


def _correction_findings(
    directory: Path,
    shown: str,
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    run_files: Mapping[str, Path],
) -> tuple[int, list[Finding]]:
    """The corrections of one run, held to the run and to each other.

    Returns the number of correction files and the findings.
    """
    shown = printable(shown)
    present, links = _walk(directory)
    findings = [
        Finding(
            f"{shown}/{printable(name)}", RULE_FILE_NOT_REGULAR, "the entry is a link"
        )
        for name in links
    ]
    records: dict[int, str] = {}
    claimed: set[str] = set()
    for name in present:
        match = _CORRECTION_FILE.fullmatch(name)
        if match is not None:
            records[int(match.group(1))] = name
            claimed.add(name)
    if sorted(records) != list(range(1, len(records) + 1)):
        findings.append(
            Finding(
                shown,
                RULE_CORRECTION_NUMBER,
                "the correction files are not numbered from 1 with no gap",
            )
        )
    listed = {entry["path"]: entry["sha256"] for entry in manifest["evidence"]["files"]}
    digests: dict[int, str] = {}
    for number in sorted(records):
        name = records[number]
        ref = f"{shown}/{name}"
        path = present[name]
        problem = form_problem(path)
        if problem is not None:
            findings.append(Finding(ref, RULE_FILE_FORM, problem))
            continue
        digests[number] = file_digest(path)
        findings.extend(
            Finding(ref, rule, why)
            for rule, why in text_problems(path.read_bytes().decode("utf-8"))
        )
        try:
            document = read_document(path)
        except RunDocumentError:
            document = None
        problem = correction_problem(document)
        if document is None or problem is not None:
            findings.append(
                Finding(
                    ref,
                    RULE_CORRECTION_UNREADABLE,
                    problem or "the file is not one JSON object",
                )
            )
            continue
        if document["number"] != number:
            findings.append(
                Finding(
                    ref,
                    RULE_CORRECTION_NUMBER,
                    "the number in the correction is not the number in its file name",
                )
            )
        if (
            document["experimentId"] != manifest["metadata"]["experimentId"]
            or document["runId"] != manifest["metadata"]["runId"]
            or document["manifestSha256"] != manifest_sha256
        ):
            findings.append(
                Finding(
                    ref,
                    RULE_CORRECTION_IDENTITY,
                    "the correction names another experiment, another run, or a "
                    "manifest digest that the manifest does not have",
                )
            )
        if document["previousCorrectionSha256"] != digests.get(number - 1):
            findings.append(
                Finding(
                    ref,
                    RULE_CORRECTION_CHAIN,
                    "the correction does not state the digest of the correction "
                    "before it, or the first correction states one",
                )
            )
        for target in document["corrects"]:
            earlier = _CORRECTION_FILE.fullmatch(target["path"])
            if target["path"] == MANIFEST_NAME:
                held: str | None = manifest_sha256
            elif earlier is not None and int(earlier.group(1)) < number:
                held = digests.get(int(earlier.group(1)))
            elif target["path"] in listed and target["path"] in run_files:
                held = file_digest(run_files[target["path"]])
            else:
                held = None
            if held != target["sha256"]:
                findings.append(
                    Finding(
                        ref,
                        RULE_CORRECTION_TARGET,
                        "a corrected file is not the manifest, an evidence file of "
                        "the manifest, or an earlier correction, or it does not "
                        "have the digest that the correction states",
                    )
                )
        folder = f"correction-{number}"
        added = {
            row["path"]: present[f"{folder}/{row['path']}"]
            for row in document["files"]
            if f"{folder}/{row['path']}" in present
        }
        claimed.update(f"{folder}/{row['path']}" for row in document["files"])
        findings.extend(_listed_findings(f"{shown}/{folder}", document["files"], added))
    findings.extend(
        Finding(
            f"{shown}/{printable(name)}",
            RULE_FILE_UNLISTED,
            "the file is not a correction and no correction names it",
        )
        for name in sorted(set(present) - claimed)
    )
    return len(records), findings


# --------------------------------------------------------------------------
# The repository listing
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RepositoryReport:
    """Every run directory of a tree, in path order, and the findings of no one run."""

    runs: tuple[RunReport, ...]
    findings: tuple[Finding, ...] = ()

    @property
    def refused(self) -> bool:
        return bool(self.findings) or any(run.status == REFUSED for run in self.runs)


def _directories(parent: Path) -> list[Path]:
    if not parent.is_dir():
        return []
    return sorted(path for path in parent.iterdir() if path.is_dir())


def repository_report(root: Path = REPO_ROOT) -> RepositoryReport:
    """Check every run directory under ``docs/proof/experiments`` of a tree.

    The listing of ``tools.experiment_run`` gives each manifest and its status. A
    manifest that the pre-schema register names is listed and its directory is not
    checked: it was committed before this layout. A manifest that validates has its
    directory checked. A manifest that is refused gives a refused run. A directory
    of a ``runs`` directory with no manifest is refused, and so is a corrections
    directory with no run of this layout.

    The listing reads the files of the tree, tracked or not. It does not read Git.
    """
    listing = manifest_listing(root)
    findings = [
        Finding(
            RUNS_ROOT_REF, RULE_MANIFEST_REFUSED, f"{finding.rule}: {finding.message}"
        )
        for finding in listing.findings
    ]
    reports: dict[str, RunReport] = {}
    for entry in listing.manifests:
        run_ref = entry.path.rsplit("/", 1)[0]
        if entry.status == PRE_SCHEMA:
            reports[run_ref] = RunReport(printable(run_ref), PRE_SCHEMA)
        else:
            reports[run_ref] = check_run(root / run_ref, root)
    runs_root = root / RUNS_ROOT_REF
    for experiment in _directories(runs_root):
        for run_dir in _directories(experiment / RUNS_DIRECTORY):
            run_ref = run_dir.relative_to(root).as_posix()
            if run_ref not in reports:
                reports[run_ref] = check_run(run_dir, root)
        for correction_dir in _directories(experiment / CORRECTIONS_DIRECTORY):
            run_ref = (
                (experiment / RUNS_DIRECTORY / correction_dir.name)
                .relative_to(root)
                .as_posix()
            )
            report = reports.get(run_ref)
            if report is None or report.status == PRE_SCHEMA:
                findings.append(
                    Finding(
                        printable(correction_dir.relative_to(root).as_posix()),
                        RULE_CORRECTION_RUN,
                        "no run directory of this layout has the name of the "
                        "corrections directory",
                    )
                )
    return RepositoryReport(
        tuple(reports[ref] for ref in sorted(reports)), tuple(sorted(findings))
    )


def digest_lines(directory: Path) -> tuple[list[str], list[Finding]]:
    """One ``<sha256>  <path>`` line for each file of a directory but the manifest.

    It is the form that ``sha256sum`` prints, with the layout's digest. A writer of
    a manifest reads the digests from it. A file that cannot be an evidence file is
    a finding and has no line.
    """
    present, links = _walk(directory)
    lines: list[str] = []
    findings = [
        Finding(printable(name), RULE_FILE_NOT_REGULAR, "the entry is a link")
        for name in links
    ]
    for name, path in present.items():
        if name == MANIFEST_NAME:
            continue
        problem = form_problem(path)
        if problem is not None:
            findings.append(Finding(printable(name), RULE_FILE_FORM, problem))
            continue
        lines.append(f"{file_digest(path)}  {name}")
    return lines, sorted(findings)
