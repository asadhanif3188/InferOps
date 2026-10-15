"""Check the directory of an experiment run against its manifest.

A run of an experiment has one directory. The run directory holds the run's
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
file it corrects, so a correction of a file that was edited is refused while the
correction itself is unchanged.

**Qualifications.** ``docs/proof/experiments/v2-q1/runs`` holds the directories of
Q1, the environment and identity qualification, which are not runs of this layout
and have no manifest. ``tools.environment_qualification --check`` holds each to its
record. The ``repository`` command lists each and applies only the two text rules
to its files, and a corrections directory of one is refused.

**What this module does not do.** It reads one tree. It does not read Git, so it
does not show that a file was committed, or that a run directory and its
corrections were not replaced together. It does not judge a result. It does not
read a raw file for its meaning, except a caller record. It does not show that a
derived file was computed from the raw files. It assigns no evidence level and
reads no claim.

Everything here is offline and deterministic: no network, no cluster, no clock, no
randomness.
"""

from __future__ import annotations

import os
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

#: The status of a directory of a Q1 qualification. A qualification is not a run
#: of this layout: it has no ExperimentRun manifest, and
#: ``tools.environment_qualification --check`` holds it to its record. The
#: ``repository`` command lists it and applies the two text rules to each file.
QUALIFICATION: Final = "qualification"

#: The one experiment directory whose ``runs`` directory holds Q1 qualifications.
QUALIFICATIONS_REF: Final = f"{RUNS_ROOT_REF}/v2-q1"


@dataclass(frozen=True)
class Role:
    """One registered role of an evidence file."""

    kind: str
    holds: str


#: Every role an evidence file of a run directory can have. A raw role names what a
#: run read or wrote as it executed. A derived role names what is computed or
#: written from raw files.
ROLES: Final[Mapping[str, Role]] = {
    "caller": Role(
        RAW,
        "The caller's own record of its requests, as the reliability runner writes it.",
    ),
    "endpoints": Role(RAW, "Readings of the Service endpoints, each with its time."),
    "pods": Role(RAW, "Readings of the pods, each with its time."),
    "deployments": Role(RAW, "Readings of the Deployments, each with its time."),
    "argo": Role(
        RAW, "Readings of the delivery controller's Application, each with its time."
    ),
    "telemetry": Role(RAW, "Readings of the metrics that the frozen record registers."),
    "resources": Role(RAW, "Readings of resource use, each with its time."),
    "operator-events": Role(
        RAW,
        "The events that the control of the run and an operator recorded, each "
        "with its time.",
    ),
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
RULE_FILE_NOT_REGULAR: Final = "evidence-entry-is-a-link"
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
        "The freeze record that a manifest names is present, it is one JSON object "
        "with no member stated twice, and it has the integer revision and the "
        "content digest that the manifest states."
    ),
    RULE_FILE_MISSING: (
        "Each evidence file that a manifest or a correction names is present."
    ),
    RULE_FILE_UNLISTED: (
        "Each file of a run directory is the manifest or an evidence file that the "
        "manifest names, each file of the corrections directory of a run is a "
        "correction or a file that a correction names, and each entry of a runs "
        "directory and of a corrections directory is a directory."
    ),
    RULE_FILE_NOT_REGULAR: (
        "No entry of the proof tree that the check reads is a symbolic link or a "
        "directory junction."
    ),
    RULE_FILE_FORM: (
        "An evidence file is UTF-8 text with no NUL character, under a file suffix "
        "that the evidence index hashes as text, and it does not have the name of "
        "a run manifest."
    ),
    RULE_FILE_DIGEST: (
        "The digest stated for an evidence file is the SHA-256 of the file's "
        "content with each CRLF replaced by LF."
    ),
    RULE_FILE_CREDENTIAL: (
        "No evidence file and no correction holds the published prefix of a "
        "credential format after a character that is not a letter or a digit."
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
        "A caller record names the experiment, the run, the caller profile with "
        "its revision and digest, and the concurrency of its manifest, it names "
        "the release of its manifest or none, it is not a rehearsal, and its "
        "manifest states a caller profile."
    ),
    RULE_CORRECTION_RUN: (
        "A corrections directory of a run has the name of a run directory of this "
        "layout in the same experiment directory, and it is a directory."
    ),
    RULE_CORRECTION_UNREADABLE: (
        "A correction is one JSON object with exactly the registered members, each "
        "in its form."
    ),
    RULE_CORRECTION_NUMBER: (
        "The corrections of a run are numbered from 1 with no gap, and the number "
        "in each correction is the number in its file name."
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
        "digest: the manifest, an evidence file of the manifest, an earlier "
        "correction, or a file that an earlier correction adds."
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
MAXIMUM_CORRECTION_NUMBER: Final = 9999

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_INSTANT: Final = re.compile(
    r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.[0-9]{1,6})?Z"
)
_CORRECTION_FILE: Final = re.compile(r"correction-([1-9][0-9]{0,3})\.v1alpha1\.json")
# A published prefix after a character that is not a letter or a digit, or at the
# start of the text. A prefix inside a longer word, such as the last letters of an
# ordinary word, is not read.
_CREDENTIAL: Final = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    + "|".join(re.escape(prefix) for prefix in _CREDENTIAL_PREFIXES)
    + ")"
)
# The escapes of a JSON string. A file can hold a line break as a backslash and a
# letter. The letter would then stand before the next word, and a prefix after it
# would not be read.
_JSON_UNICODE_ESCAPE: Final = re.compile(r"\\u([0-9A-Fa-f]{4})")
_JSON_ESCAPE: Final = re.compile(r"\\[nrtbf/\"\\]")
# A path under a user directory, in any letter case: a drive letter before `Users`
# or `home`, or `Users` or `home` after a separator and before a name. A separator
# can be written twice, as JSON writes a backslash. It follows the pattern of the
# security baseline suite and is wider: it needs no separator after the name.
_PERSONAL_PATH: Final = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]{1,2}(?:Users|home)[\\/]"
    r"|[\\/](?:Users|home)[\\/]{1,2}[^\\/\s\"'`<>|]+",
    re.IGNORECASE,
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
    if path.name == MANIFEST_NAME:
        return "the file has the name of a run manifest"
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


def _without_json_escapes(text: str) -> str:
    """A text with each escape of a JSON string replaced by what it stands for."""
    decoded = _JSON_UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), text)
    return _JSON_ESCAPE.sub(" ", decoded)


def text_problems(text: str) -> list[tuple[str, str]]:
    """The public-safety rules a text breaks, each with its message.

    The credential rule reads a published prefix after a character that is not a
    letter or a digit. It reads the text as it is and with the escapes of a JSON
    string replaced. It does not apply the WorkloadContract's shape heuristic: raw
    evidence holds digests, identifiers, and encoded values that have that shape.
    """
    problems: list[tuple[str, str]] = []
    if _CREDENTIAL.search(text) or _CREDENTIAL.search(_without_json_escapes(text)):
        problems.append(
            (
                RULE_FILE_CREDENTIAL,
                "the file holds the published prefix of a credential format",
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


def _is_link(path: Path) -> bool:
    """Whether an entry is a symbolic link or a directory junction."""
    return path.is_symlink() or path.is_junction()


def _walk(directory: Path) -> tuple[dict[str, Path], list[str]]:
    """The regular files of a directory by relative path, and the links it holds.

    A link is listed and not followed. The files are in the order of their paths as
    text, so one tree gives one order on each host.
    """
    files: dict[str, Path] = {}
    links: list[str] = []
    pending = [directory]
    while pending:
        current = pending.pop()
        try:
            names = sorted(os.listdir(current))
        except OSError:
            continue
        for name in names:
            path = current / name
            relative = path.relative_to(directory).as_posix()
            if _is_link(path):
                links.append(relative)
            elif path.is_dir():
                pending.append(path)
            elif path.is_file():
                files[relative] = path
    return {name: files[name] for name in sorted(files)}, sorted(links)


def _text_of(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


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
    findings.extend(
        Finding(ref, rule, why) for rule, why in text_problems(_text_of(path))
    )
    return findings


def describe_file(run_dir: Path, relative: str, role: str) -> dict[str, str]:
    """One ``evidence.files`` entry for a file of a run directory.

    A writer of a manifest calls this for each file. A role that is not registered,
    a path that is not an evidence path, a file that is absent or reached through a
    link, a file that does not have the form of an evidence file, and a file that
    a text rule refuses each raise ``LayoutError``.

    The helper reads one file. It does not read a caller record, and it knows no
    manifest. So the check of the run directory can refuse an entry that this
    helper returned.
    """
    if not isinstance(role, str) or role not in ROLES:
        raise LayoutError(RULE_ROLE, "the role is not a registered role")
    if not isinstance(relative, str) or (
        _evidence_path_pattern().fullmatch(relative) is None
    ):
        raise LayoutError(RULE_FILE_FORM, "the path is not an evidence path")
    path = _walk(run_dir)[0].get(relative) if run_dir.is_dir() else None
    if path is None:
        raise LayoutError(RULE_FILE_MISSING, "the path names no regular file")
    problem = form_problem(path)
    if problem is not None:
        raise LayoutError(RULE_FILE_FORM, problem)
    for rule, why in text_problems(_text_of(path)):
        raise LayoutError(rule, why)
    return {"role": role, "path": relative, "sha256": file_digest(path)}


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


def _names(directory: Path) -> set[str]:
    try:
        return set(os.listdir(directory))
    except OSError:
        return set()


def _exact(root: Path, ref: str) -> Path | None:
    """The entry a path names under a root, with each segment compared as text.

    A file system that ignores letter case opens an entry under a name in another
    case. One tree would then pass on one host and fail on another.
    """
    current = root
    for segment in ref.split("/"):
        if segment not in _names(current):
            return None
        current = current / segment
    return current


def _linked_part(root: Path, ref: str) -> str | None:
    """The first part of a path under a root that is a link, or None."""
    current = root
    parts = ref.split("/")
    for index, segment in enumerate(parts):
        current = current / segment
        if _is_link(current):
            return "/".join(parts[: index + 1])
    return None


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
    differs = [
        Finding(
            ref,
            RULE_FREEZE,
            "the freeze record is absent, it is not one JSON object with each "
            "member once, or it does not have the integer revision and the "
            "content digest that the manifest states",
        )
    ]
    path = _exact(root, ref)
    if path is None or _is_link(path) or not path.is_file():
        return differs
    try:
        data = path.read_bytes()
        # The reader of a run manifest: one JSON object, no member stated twice,
        # and no value that is not JSON.
        document = read_document(path)
        revision = document["metadata"]["revision"]
    except (OSError, RunDocumentError, KeyError, TypeError):
        return differs
    if (
        content_digest(data) != spec["freezeContentSha256"]
        or type(revision) is not int
        or revision != spec["freezeRevision"]
    ):
        return differs
    return []


def _caller_findings(
    path: Path, ref: str, manifest: Mapping[str, Any]
) -> list[Finding]:
    try:
        record = read_record(_text_of(path))
    except RunnerError as error:
        return [
            Finding(
                ref,
                RULE_CALLER_RECORD,
                f"the reliability runner's reader refuses the file: {error.rule}",
            )
        ]
    except RecursionError:
        return [
            Finding(
                ref,
                RULE_CALLER_RECORD,
                "the reliability runner's reader cannot read the file",
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
            "the caller record is a rehearsal, its manifest states no caller "
            "profile, or it names another experiment, run, caller profile, "
            "concurrency, or release than the manifest",
        )
    ]


def _listed_findings(
    prefix: str,
    entries: Sequence[Mapping[str, str]],
    present: Mapping[str, Path],
    manifest: Mapping[str, Any],
) -> list[Finding]:
    """The findings of the files a manifest or a correction names.

    ``manifest`` is the manifest of the run. A file with the role caller is held to
    it, whether the manifest or a correction names the file.
    """
    findings: list[Finding] = []
    for entry in entries:
        ref = f"{prefix}/{entry['path']}"
        if entry["role"] not in ROLES:
            findings.append(
                Finding(ref, RULE_ROLE, "the role of the file is not registered")
            )
        path = present.get(entry["path"])
        if path is None:
            if entry["path"].rsplit("/", 1)[-1] == MANIFEST_NAME:
                findings.append(
                    Finding(
                        ref, RULE_FILE_FORM, "the file has the name of a run manifest"
                    )
                )
            else:
                findings.append(
                    Finding(ref, RULE_FILE_MISSING, "the file that is named is absent")
                )
            continue
        found = _file_findings(path, ref, entry["sha256"])
        findings.extend(found)
        if entry["role"] == CALLER_ROLE and not any(
            finding.rule == RULE_FILE_FORM for finding in found
        ):
            findings.extend(_caller_findings(path, ref, manifest))
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
    is_directory = run_dir.is_dir() and not _is_link(run_dir)
    present, links = _walk(run_dir) if is_directory else ({}, [])
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
    placed = expected is not None and run_ref == expected
    if not placed:
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
    findings.extend(_listed_findings(shown, entries, present, manifest))
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

    manifest_sha256 = file_digest(manifest_path)
    corrections = 0
    if placed:
        experiment_dir = run_dir.parent.parent
        correction_ref = f"{CORRECTIONS_DIRECTORY}/{manifest['metadata']['runId']}"
        correction_dir = _exact(experiment_dir, correction_ref)
        if correction_dir is not None:
            shown_dir = printable(f"{shown.rsplit('/', 2)[0]}/{correction_ref}")
            if _is_link(correction_dir) or not correction_dir.is_dir():
                findings.append(
                    Finding(
                        shown_dir,
                        RULE_CORRECTION_RUN,
                        "the corrections directory of the run is not a directory",
                    )
                )
            else:
                corrections, found = _correction_findings(
                    correction_dir, shown_dir, manifest, manifest_sha256, present
                )
                findings.extend(found)

    if findings or run_ref is None:
        return RunReport(shown, REFUSED, tuple(sorted(findings)))
    return RunReport(
        shown,
        CONFORMING,
        (),
        files=len(entries),
        raw_files=sum(1 for entry in entries if is_raw(entry["role"])),
        corrections=corrections,
        digests=run_digests(run_ref, manifest_sha256, manifest),
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
    if type(number) is not int or not 1 <= number <= MAXIMUM_CORRECTION_NUMBER:
        return "the number is not an integer from 1 to 9999"
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
    corrects = document["corrects"]
    if not _rows(corrects, _TARGET_MEMBERS) or not corrects:
        return "the corrected files are not one or more rows of a path and a digest"
    if len({row["path"] for row in corrects}) != len(corrects):
        return "one corrected file is named twice"
    statements = document["statements"]
    if (
        not isinstance(statements, list)
        or not statements
        or not all(
            isinstance(statement, str)
            and statement.strip()
            and len(statement) <= MAXIMUM_STATEMENT_LENGTH
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
    listed = {entry["path"] for entry in manifest["evidence"]["files"]}
    digests: dict[int, str] = {}
    added_by: dict[str, int] = {}
    for number in sorted(records):
        name = records[number]
        ref = f"{shown}/{name}"
        path = present[name]
        try:
            digests[number] = file_digest(path)
            text = _text_of(path)
            document = read_document(path)
        except (OSError, UnicodeDecodeError, RunDocumentError):
            findings.append(
                Finding(
                    ref,
                    RULE_CORRECTION_UNREADABLE,
                    "the file is not one JSON object with each member once",
                )
            )
            continue
        findings.extend(Finding(ref, rule, why) for rule, why in text_problems(text))
        problem = correction_problem(document)
        if problem is not None:
            findings.append(Finding(ref, RULE_CORRECTION_UNREADABLE, problem))
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
            target_path = target["path"]
            earlier = _CORRECTION_FILE.fullmatch(target_path)
            held: str | None = None
            if target_path == MANIFEST_NAME:
                held = manifest_sha256
            elif earlier is not None and int(earlier.group(1)) < number:
                held = digests.get(int(earlier.group(1)))
            elif added_by.get(target_path, number) < number:
                held = file_digest(present[target_path])
            elif (
                target_path in listed
                and target_path in run_files
                and form_problem(run_files[target_path]) is None
            ):
                held = file_digest(run_files[target_path])
            if held != target["sha256"]:
                findings.append(
                    Finding(
                        ref,
                        RULE_CORRECTION_TARGET,
                        "a corrected file is not the manifest, an evidence file of "
                        "the manifest, an earlier correction, or a file that an "
                        "earlier correction adds, or it does not have the digest "
                        "that the correction states",
                    )
                )
        folder = f"correction-{number}"
        added = {
            row["path"]: present[f"{folder}/{row['path']}"]
            for row in document["files"]
            if f"{folder}/{row['path']}" in present
        }
        for row in document["files"]:
            claimed.add(f"{folder}/{row['path']}")
            if row["path"] in added:
                added_by[f"{folder}/{row['path']}"] = number
        findings.extend(
            _listed_findings(f"{shown}/{folder}", document["files"], added, manifest)
        )
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


def _entries(parent: Path, shown: str) -> tuple[list[Path], list[Finding]]:
    """The directories of a ``runs`` or ``corrections`` directory, and the findings
    of each entry that is not a directory."""
    directories: list[Path] = []
    findings: list[Finding] = []
    for name in sorted(_names(parent)):
        path = parent / name
        ref = printable(f"{shown}/{name}")
        if _is_link(path):
            findings.append(Finding(ref, RULE_FILE_NOT_REGULAR, "the entry is a link"))
        elif path.is_dir():
            directories.append(path)
        else:
            findings.append(
                Finding(ref, RULE_FILE_UNLISTED, "the entry is not a directory")
            )
    return directories, findings


def _qualification_report(directory: Path, shown: str) -> RunReport:
    """List one Q1 qualification directory, and apply the text rules to each file.

    A link is a finding, and so is a file that is not UTF-8 text. The record of
    the qualification is not read here: ``tools.environment_qualification
    --check`` builds it again from the directory.
    """
    present, links = _walk(directory)
    findings = [
        Finding(
            printable(f"{shown}/{name}"), RULE_FILE_NOT_REGULAR, "the entry is a link"
        )
        for name in links
    ]
    for name, path in present.items():
        ref = printable(f"{shown}/{name}")
        try:
            text = _text_of(path)
        except (OSError, UnicodeDecodeError):
            findings.append(Finding(ref, RULE_FILE_FORM, "the file is not UTF-8 text"))
            continue
        findings.extend(Finding(ref, rule, why) for rule, why in text_problems(text))
    if findings:
        return RunReport(shown, REFUSED, tuple(sorted(findings)))
    return RunReport(shown, QUALIFICATION, files=len(present))


def repository_report(root: Path = REPO_ROOT) -> RepositoryReport:
    """Check every run directory under ``docs/proof/experiments`` of a tree.

    The listing of ``tools.experiment_run`` gives each manifest and its status. A
    manifest that the pre-schema register names is listed and its directory is not
    checked: it was committed before this layout. Each other manifest has its
    directory checked. A directory of ``docs/proof/experiments/v2-q1/runs`` with no
    manifest is a Q1 qualification: it is listed, and only the two text rules are
    applied to its files. Any other directory of a ``runs`` directory with no
    manifest is refused. A corrections directory of a run is refused when no run
    directory of this layout has its name: none, one that the pre-schema register
    names, or a qualification.

    The listing reads the files of the tree, tracked or not. It does not read Git.
    """
    listing = manifest_listing(root)
    findings = [
        Finding(RUNS_ROOT_REF, RULE_MANIFEST_REFUSED, f"{item.rule}: {item.message}")
        for item in listing.findings
    ]
    reports: dict[str, RunReport] = {}
    linked: set[str] = set()
    for entry in listing.manifests:
        run_ref = entry.path.rsplit("/", 1)[0]
        link = _linked_part(root, run_ref)
        if link is not None:
            # The manifest listing follows a link, so it lists the manifest of
            # one run under two paths. The link is the finding, and the path
            # through it is no run directory.
            linked.add(link)
        elif entry.status == PRE_SCHEMA:
            reports[run_ref] = RunReport(printable(run_ref), PRE_SCHEMA)
        else:
            reports[run_ref] = check_run(root / run_ref, root)
    runs_root = root / RUNS_ROOT_REF
    for name in sorted(_names(runs_root)):
        experiment = runs_root / name
        shown = f"{RUNS_ROOT_REF}/{name}"
        if _is_link(experiment):
            linked.add(shown)
        if _is_link(experiment) or not experiment.is_dir():
            continue
        children = _names(experiment)
        if RUNS_DIRECTORY in children:
            directories, found = _entries(
                experiment / RUNS_DIRECTORY, f"{shown}/{RUNS_DIRECTORY}"
            )
            findings.extend(found)
            for run_dir in directories:
                run_ref = f"{shown}/{RUNS_DIRECTORY}/{run_dir.name}"
                if run_ref in reports:
                    continue
                if shown == QUALIFICATIONS_REF:
                    reports[run_ref] = _qualification_report(
                        run_dir, printable(run_ref)
                    )
                else:
                    reports[run_ref] = check_run(run_dir, root)
        if CORRECTIONS_DIRECTORY in children:
            directories, found = _entries(
                experiment / CORRECTIONS_DIRECTORY, f"{shown}/{CORRECTIONS_DIRECTORY}"
            )
            findings.extend(found)
            for correction_dir in directories:
                report = reports.get(f"{shown}/{RUNS_DIRECTORY}/{correction_dir.name}")
                if report is None or report.status in (PRE_SCHEMA, QUALIFICATION):
                    findings.append(
                        Finding(
                            printable(
                                f"{shown}/{CORRECTIONS_DIRECTORY}/{correction_dir.name}"
                            ),
                            RULE_CORRECTION_RUN,
                            "no run directory of this layout has the name of the "
                            "corrections directory",
                        )
                    )
    findings.extend(
        Finding(printable(ref), RULE_FILE_NOT_REGULAR, "the entry is a link")
        for ref in linked
    )
    return RepositoryReport(
        tuple(reports[ref] for ref in sorted(reports)),
        tuple(sorted(set(findings))),
    )


def digest_lines(directory: Path) -> tuple[list[str], list[Finding]]:
    """One ``<sha256>  <path>`` line for each evidence file of a directory.

    It is the form that ``sha256sum`` prints, with the layout's digest, in the
    order of the paths as text. A writer of a manifest reads the digests from it.
    The manifest has no line. A link, a file that does not have the form of an
    evidence file, and a file that a text rule refuses are findings and have no
    line. A path that names no directory is a finding.
    """
    if not directory.is_dir() or _is_link(directory):
        return [], [
            Finding(
                printable(directory.as_posix()),
                RULE_FILE_MISSING,
                "the path names no directory",
            )
        ]
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
        problems = text_problems(_text_of(path))
        if problems:
            findings.extend(
                Finding(printable(name), rule, why) for rule, why in problems
            )
            continue
        lines.append(f"{file_digest(path)}  {name}")
    return lines, sorted(findings)
