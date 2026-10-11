"""Validate an ExperimentRun v1alpha1 manifest, and list the run manifests of a tree.

An ExperimentRun is the manifest of one run of one experiment against one delivered
release. The published schema is at
``contracts/experiment/experiment-run.v1alpha1.schema.json``. This module applies it
in two layers, as the WorkloadContract validator does.

**Structural.** The published JSON Schema, applied by a draft 2020-12 validator and
translated through the canonical error model of ``tools.contract_validation``. A
consumer that holds only the schema file reaches the same verdict.

**Semantic.** The rules that JSON Schema cannot express: two instants compared, a
result state compared with the fault, a caller profile compared with the revisions
that ``tools.reliability_profile`` registers, and a shape heuristic over the text.
The semantic layer runs only on a document that the schema accepts. So a document
with a structural finding reports no semantic finding.

**The repository listing.** Three manifests named ``run.v1alpha1.json`` were
committed before this schema existed. They state the same ``apiVersion`` and
``kind`` and the schema refuses each. ``pre-schema-experiment-runs.v1alpha1.json``
registers each by path and content digest. ``repository_report`` reads every
manifest under ``docs/proof/experiments``: a registered one must have its registered
content, and every other one must validate.

**What this module does not do.** It reads one document. It does not open an
evidence file, so it does not show that a file exists or has the digest the
manifest states. It does not read the freeze record, the release, the binding, or
the cluster, so it does not show that an identity in the manifest is the identity
of anything. It does not judge a result: a manifest that says PASSED validates
whether or not the criteria held. It assigns no evidence level and reads no claim.

Everything here is offline and deterministic: no network, no cluster, no clock, no
randomness.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from tools.contract_validation.errors import CONTRACT_INVALID, Finding
from tools.contract_validation.workload import (
    findings_against,
    looks_like_a_pasted_credential,
    ordered,
)
from tools.reliability_profile.core import (
    CONCURRENCY as RP1_CONCURRENCY,
)
from tools.reliability_profile.core import (
    PROFILE_ID as RP1_PROFILE_ID,
)
from tools.reliability_profile.core import (
    REGISTERED_REVISIONS as RP1_REGISTERED_REVISIONS,
)

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
SCHEMA_REF: Final = "contracts/experiment/experiment-run.v1alpha1.schema.json"
SCHEMA_PATH: Final = REPO_ROOT / SCHEMA_REF
PRE_SCHEMA_REGISTER_REF: Final = (
    "contracts/experiment/compatibility/pre-schema-experiment-runs.v1alpha1.json"
)

SUPPORTED_API_VERSION: Final = "inferops.io/v1alpha1"
KIND: Final = "ExperimentRun"
PRE_SCHEMA_REGISTER_KIND: Final = "PreSchemaExperimentRunRegister"

#: The name of a run manifest, and the tree the repository listing reads.
MANIFEST_NAME: Final = "run.v1alpha1.json"
RUNS_ROOT_REF: Final = "docs/proof/experiments"

#: The five result states of a run. None is an evidence level.
RESULT_STATES: Final = ("PASSED", "FAILED", "INCONCLUSIVE", "REFUSED", "ABORTED")
#: InferOps Evidence Levels. None is a result state.
EVIDENCE_LEVELS: Final = ("C0", "C1", "C2", "C3", "C4")
#: The states that decide the frozen criteria from the evidence.
DECIDED_STATES: Final = frozenset({"PASSED", "FAILED"})

#: The role of the caller's own record of its requests.
CALLER_ROLE: Final = "caller"


@dataclass(frozen=True)
class CallerProfileRevision:
    """One registered revision of a caller profile."""

    content_sha256: str
    concurrency: int


#: Every caller profile revision a run can name. RP-1 is the only profile, and its
#: revisions and their digests are the ones ``tools.reliability_profile`` registers.
REGISTERED_CALLER_PROFILES: Final[Mapping[tuple[str, int], CallerProfileRevision]] = {
    (RP1_PROFILE_ID, revision): CallerProfileRevision(digest, RP1_CONCURRENCY)
    for revision, digest in RP1_REGISTERED_REVISIONS.items()
}

RULE_UNREADABLE: Final = "run-document-unreadable"
RULE_TIME: Final = "run-time-not-an-instant"
RULE_TIME_ORDER: Final = "run-time-order-inverted"
RULE_FAULT_TIME: Final = "run-fault-time-outside-run"
RULE_PASSED_WITHOUT_FAULT: Final = "run-passed-without-registered-fault"
RULE_REFUSED_AFTER_FAULT: Final = "run-refused-after-fault"
RULE_PROFILE_UNREGISTERED: Final = "run-caller-profile-unregistered"
RULE_PROFILE_DIGEST: Final = "run-caller-profile-digest-differs"
RULE_PROFILE_CONCURRENCY: Final = "run-caller-concurrency-differs"
RULE_CALLER_EVIDENCE: Final = "run-caller-evidence-missing"
RULE_EVIDENCE_DUPLICATED: Final = "run-evidence-path-duplicated"
RULE_EVIDENCE_MANIFEST: Final = "run-evidence-names-the-manifest"
RULE_TEXT_CREDENTIAL: Final = "run-value-credential-shaped"
RULE_TEXT_HOST_PATH: Final = "run-text-host-path"
RULE_REGISTER_UNREADABLE: Final = "run-pre-schema-register-unreadable"
RULE_PRE_SCHEMA_MISSING: Final = "run-pre-schema-record-missing"
RULE_PRE_SCHEMA_EDITED: Final = "run-pre-schema-record-edited"

#: The rules this module applies beside the structural rules of the canonical error
#: model, each with its statement. Every one has the code ``contract-invalid``. The
#: contract document publishes the same statements, and a test compares the two.
SEMANTIC_RULES: Final[Mapping[str, str]] = {
    RULE_TIME: "A time that has the form of a UTC instant is a real instant.",
    RULE_TIME_ORDER: "A run does not end before it starts.",
    RULE_FAULT_TIME: "A fault is injected between the start and the end of its run.",
    RULE_PASSED_WITHOUT_FAULT: (
        "A run whose frozen record registers a fault is PASSED only when it "
        "injected the fault."
    ),
    RULE_REFUSED_AFTER_FAULT: (
        "A REFUSED run did not start its procedure, so it injected no fault."
    ),
    RULE_PROFILE_UNREGISTERED: (
        "A caller profile a run names is a registered revision of a registered profile."
    ),
    RULE_PROFILE_DIGEST: (
        "The content digest a run states for a caller profile revision is the "
        "registered digest of that revision."
    ),
    RULE_PROFILE_CONCURRENCY: (
        "The concurrency a run states is the concurrency its caller profile fixes."
    ),
    RULE_CALLER_EVIDENCE: (
        "A PASSED or FAILED run that names a caller profile names at least one "
        "evidence file with the role caller."
    ),
    RULE_EVIDENCE_DUPLICATED: "A run names each evidence path once.",
    RULE_EVIDENCE_MANIFEST: "A run does not list its own manifest as evidence.",
    RULE_TEXT_CREDENTIAL: (
        "No string value, and no word of a statement, has the shape of a credential."
    ),
    RULE_TEXT_HOST_PATH: "No statement holds an absolute path of a host.",
}

#: The rules of the repository listing and of reading a file.
REPOSITORY_RULES: Final[Mapping[str, str]] = {
    RULE_UNREADABLE: (
        "A run manifest is one JSON object, with no member stated twice."
    ),
    RULE_REGISTER_UNREADABLE: (
        "The register of pre-schema run manifests is a JSON object that names each "
        "manifest once, by repository path and content digest."
    ),
    RULE_PRE_SCHEMA_MISSING: "Every registered pre-schema run manifest is present.",
    RULE_PRE_SCHEMA_EDITED: (
        "A registered pre-schema run manifest has its registered content."
    ),
}

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_REGISTER_PATH: Final = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*"
)
_INSTANT: Final = re.compile(
    r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]{1,6}))?Z"
)
# A drive letter that starts a path, or a directory that holds user accounts. The
# character before a drive letter is checked so that the scheme of a URL, which
# ends in a letter and a colon, is not read as a drive.
_HOST_PATH: Final = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?<![A-Za-z0-9._-])/(?:home|Users|root)/"
)
#: Characters that open a quotation or a bracket before a word.
_LEADING_PUNCTUATION: Final = "\"'`([{<"


class RunDocumentError(RuntimeError):
    """A file could not be read as a run manifest or as the pre-schema register."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule
        self.message = message


def _finding(rule: str, field: str, message: str) -> Finding:
    return Finding(field=field, rule=rule, code=CONTRACT_INVALID, message=message)


@lru_cache(maxsize=1)
def _cached_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema


def load_schema() -> dict[str, Any]:
    """The published schema, parsed. Each caller gets its own copy."""
    return copy.deepcopy(_cached_schema())


def content_digest(data: bytes) -> str:
    """The SHA-256 of a text file's bytes with each CRLF replaced by LF.

    A Windows checkout can hold a committed file with CRLF. This is the digest the
    freeze registry and the caller profile use, so one committed file has one digest.
    """
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


# --------------------------------------------------------------------------
# Reading a file
# --------------------------------------------------------------------------


class _Repeated(ValueError):
    pass


def _no_repeat(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for name, value in pairs:
        if name in record:
            raise _Repeated(name)
        record[name] = value
    return record


def _not_a_json_number(_: str) -> Any:
    raise ValueError("NaN and Infinity are not JSON")


def _read_object(path: Path, rule: str, what: str) -> dict[str, Any]:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RunDocumentError(rule, f"{what} is unreadable") from error
    try:
        document = json.loads(
            text, object_pairs_hook=_no_repeat, parse_constant=_not_a_json_number
        )
    except _Repeated as error:
        raise RunDocumentError(rule, f"{what} states one member twice") from error
    except (ValueError, RecursionError) as error:
        raise RunDocumentError(rule, f"{what} is not JSON") from error
    if not isinstance(document, dict):
        raise RunDocumentError(rule, f"{what} is not a JSON object")
    return document


def read_document(path: Path) -> dict[str, Any]:
    """Read one run manifest. A file that is not one JSON object is refused.

    A member stated twice is refused: a JSON reader keeps the last one, so a reader
    of the file and this validator could see two documents.
    """
    return _read_object(path, RULE_UNREADABLE, "the run manifest")


# --------------------------------------------------------------------------
# Structural layer
# --------------------------------------------------------------------------


def structural_findings(document: Any) -> list[Finding]:
    """Findings from the published schema, translated into canonical rules."""
    return findings_against(load_schema(), document)


# --------------------------------------------------------------------------
# Semantic layer
# --------------------------------------------------------------------------


def _instant(text: str) -> datetime | None:
    """The instant a schema-accepted time names, or None when it names none."""
    match = _INSTANT.fullmatch(text)
    if match is None:
        return None
    try:
        whole = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    fraction = (match.group(2) or "").ljust(6, "0")
    return whole.replace(microsecond=int(fraction) if fraction else 0, tzinfo=UTC)


def _time_findings(document: Mapping[str, Any]) -> list[Finding]:
    metadata = document["metadata"]
    fault = document["fault"]
    stated = {
        "$.metadata.startedAt": metadata["startedAt"],
        "$.metadata.finishedAt": metadata["finishedAt"],
    }
    if "injectedAt" in fault:
        stated["$.fault.injectedAt"] = fault["injectedAt"]
    instants = {field: _instant(text) for field, text in stated.items()}
    findings = [
        _finding(RULE_TIME, field, "the value has the form of a time and names none")
        for field, instant in instants.items()
        if instant is None
    ]
    started = instants["$.metadata.startedAt"]
    finished = instants["$.metadata.finishedAt"]
    if started is None or finished is None:
        return findings
    if finished < started:
        findings.append(
            _finding(
                RULE_TIME_ORDER,
                "$.metadata.finishedAt",
                "the run ends before it starts",
            )
        )
        return findings
    injected = instants.get("$.fault.injectedAt")
    if injected is not None and not started <= injected <= finished:
        findings.append(
            _finding(
                RULE_FAULT_TIME,
                "$.fault.injectedAt",
                "the fault is injected before the run starts or after it ends",
            )
        )
    return findings


def _fault_findings(document: Mapping[str, Any]) -> list[Finding]:
    fault = document["fault"]
    state = document["result"]["state"]
    if not fault["registered"]:
        return []
    if state == "PASSED" and not fault["injected"]:
        return [
            _finding(
                RULE_PASSED_WITHOUT_FAULT,
                "$.result.state",
                "the run is PASSED and it did not inject the registered fault",
            )
        ]
    if state == "REFUSED" and fault["injected"]:
        return [
            _finding(
                RULE_REFUSED_AFTER_FAULT,
                "$.result.state",
                "the run is REFUSED and it injected the registered fault",
            )
        ]
    return []


def _caller_findings(document: Mapping[str, Any]) -> list[Finding]:
    profile = document["callerProfile"]
    if not profile["applies"]:
        return []
    findings: list[Finding] = []
    registered = REGISTERED_CALLER_PROFILES.get(
        (profile["profileId"], profile["profileRevision"])
    )
    if registered is None:
        findings.append(
            _finding(
                RULE_PROFILE_UNREGISTERED,
                "$.callerProfile.profileRevision",
                "the profile identifier and revision name no registered caller "
                "profile revision",
            )
        )
    else:
        if profile["contentSha256"] != registered.content_sha256:
            findings.append(
                _finding(
                    RULE_PROFILE_DIGEST,
                    "$.callerProfile.contentSha256",
                    "the digest is not the registered digest of the profile revision",
                )
            )
        if profile["concurrency"] != registered.concurrency:
            findings.append(
                _finding(
                    RULE_PROFILE_CONCURRENCY,
                    "$.callerProfile.concurrency",
                    "the concurrency is not the one the profile revision fixes: "
                    f"{registered.concurrency}",
                )
            )
    roles = {entry["role"] for entry in document["evidence"]["files"]}
    if document["result"]["state"] in DECIDED_STATES and CALLER_ROLE not in roles:
        findings.append(
            _finding(
                RULE_CALLER_EVIDENCE,
                "$.evidence.files",
                "the run is PASSED or FAILED under a caller profile and names no "
                f"evidence file with the role {CALLER_ROLE}",
            )
        )
    return findings


def _evidence_findings(document: Mapping[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for index, entry in enumerate(document["evidence"]["files"]):
        path = entry["path"]
        field = f"$.evidence.files[{index}].path"
        if path == MANIFEST_NAME:
            findings.append(
                _finding(
                    RULE_EVIDENCE_MANIFEST,
                    field,
                    "the manifest is listed as its own evidence",
                )
            )
        if path in seen:
            findings.append(
                _finding(
                    RULE_EVIDENCE_DUPLICATED,
                    field,
                    "an earlier entry names the same evidence path",
                )
            )
        seen.add(path)
    return findings


def _strings(value: Any, field: str) -> Iterator[tuple[str, str]]:
    """Every string value of a document, with its field location, in a fixed order."""
    if isinstance(value, str):
        yield field, value
    elif isinstance(value, dict):
        for name in sorted(value):
            yield from _strings(value[name], f"{field}.{name}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{field}[{index}]")


def credential_shaped(value: str) -> bool:
    """Whether a string value, or one word of it, has the shape of a credential.

    The judgement is the WorkloadContract's heuristic, applied to each word of the
    value, with a leading quotation mark or bracket removed. A value with no white
    space is one word. The heuristic is not given a whole statement: it reads a
    sentence with a capital letter and a digit as one opaque segment. It is a
    heuristic over shape. A lowercase secret with no published prefix passes.
    """
    words = (word.lstrip(_LEADING_PUNCTUATION) for word in value.split())
    return any(looks_like_a_pasted_credential(word) is not None for word in words)


def holds_host_path(value: str) -> bool:
    """Whether a statement holds a drive-letter path or a path under a user root."""
    return _HOST_PATH.search(value) is not None


def _text_findings(document: Mapping[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for field, value in _strings(document, "$"):
        if credential_shaped(value):
            findings.append(
                _finding(
                    RULE_TEXT_CREDENTIAL,
                    field,
                    "the value, or a word of it, has the shape of a credential",
                )
            )
        if holds_host_path(value):
            findings.append(
                _finding(
                    RULE_TEXT_HOST_PATH,
                    field,
                    "the value holds an absolute path of a host",
                )
            )
    return findings


def semantic_findings(document: Mapping[str, Any]) -> list[Finding]:
    """Findings from the rules JSON Schema cannot express.

    The caller gives a document that the schema accepts. ``validate`` holds that.
    """
    return [
        *_time_findings(document),
        *_fault_findings(document),
        *_caller_findings(document),
        *_evidence_findings(document),
        *_text_findings(document),
    ]


def validate(document: Any) -> list[Finding]:
    """Validate one run manifest. Returns findings, sorted, possibly empty.

    The semantic rules run only when the schema accepts the document.
    """
    structural = structural_findings(document)
    if structural:
        return ordered(structural)
    return ordered(semantic_findings(document))


def is_valid(document: Any) -> bool:
    """True when validate() finds nothing to refuse."""
    return not validate(document)


# --------------------------------------------------------------------------
# The repository listing
# --------------------------------------------------------------------------

PRE_SCHEMA: Final = "pre-schema"
CONFORMING: Final = "conforming"
REFUSED: Final = "refused"


@dataclass(frozen=True)
class ManifestStatus:
    """What the listing found for one run manifest."""

    path: str
    status: str
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class RepositoryReport:
    """Every run manifest of a tree, in path order, and the register's own findings."""

    manifests: tuple[ManifestStatus, ...]
    findings: tuple[Finding, ...] = ()

    @property
    def refused(self) -> bool:
        return bool(self.findings) or any(
            entry.status == REFUSED for entry in self.manifests
        )


def load_pre_schema_register(root: Path = REPO_ROOT) -> dict[str, str]:
    """The registered pre-schema manifests of a tree: repository path to digest."""
    what = "the register of pre-schema run manifests"
    document = _read_object(
        root / PRE_SCHEMA_REGISTER_REF, RULE_REGISTER_UNREADABLE, what
    )
    records = document.get("records")
    if (
        document.get("schemaVersion") != SUPPORTED_API_VERSION
        or document.get("kind") != PRE_SCHEMA_REGISTER_KIND
        or not isinstance(records, list)
    ):
        raise RunDocumentError(
            RULE_REGISTER_UNREADABLE,
            f"{what} does not state its version, its kind, and its records",
        )
    register: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {"path", "contentSha256"}:
            raise RunDocumentError(
                RULE_REGISTER_UNREADABLE,
                f"{what} holds a record that is not one path and one digest",
            )
        path, digest = record["path"], record["contentSha256"]
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or _REGISTER_PATH.fullmatch(path) is None
            or not path.endswith(f"/{MANIFEST_NAME}")
            or _SHA256.fullmatch(digest) is None
            or path in register
        ):
            raise RunDocumentError(
                RULE_REGISTER_UNREADABLE,
                f"{what} holds a record whose path or digest is not usable, or "
                "names one path twice",
            )
        register[path] = digest
    return register


def _manifest_refs(root: Path) -> list[str]:
    runs_root = root / RUNS_ROOT_REF
    if not runs_root.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in runs_root.rglob(MANIFEST_NAME)
        if path.is_file()
    )


def _status_of(root: Path, ref: str, register: Mapping[str, str]) -> ManifestStatus:
    path = root / ref
    if ref in register:
        try:
            digest = content_digest(path.read_bytes())
        except OSError:
            digest = ""
        if digest != register[ref]:
            return ManifestStatus(
                ref,
                REFUSED,
                (
                    _finding(
                        RULE_PRE_SCHEMA_EDITED,
                        "$",
                        "the manifest does not have the content the register "
                        "states for it",
                    ),
                ),
            )
        return ManifestStatus(ref, PRE_SCHEMA)
    try:
        document = read_document(path)
    except RunDocumentError as error:
        return ManifestStatus(ref, REFUSED, (_finding(error.rule, "$", error.message),))
    findings = tuple(validate(document))
    return ManifestStatus(ref, REFUSED if findings else CONFORMING, findings)


def repository_report(root: Path = REPO_ROOT) -> RepositoryReport:
    """Read every run manifest under ``docs/proof/experiments`` of a tree.

    A registered pre-schema manifest must have its registered content, and it is not
    validated. Every other manifest must validate. A registered manifest that is
    absent is a finding of the register.

    The listing reads the files of the tree, tracked or not. It does not read Git.
    """
    try:
        register = load_pre_schema_register(root)
    except RunDocumentError as error:
        return RepositoryReport((), (_finding(error.rule, "$", error.message),))
    refs = _manifest_refs(root)
    missing = tuple(
        _finding(
            RULE_PRE_SCHEMA_MISSING,
            "$.records",
            f"a registered manifest is absent: {ref}",
        )
        for ref in sorted(set(register) - set(refs))
    )
    return RepositoryReport(
        tuple(_status_of(root, ref, register) for ref in refs), missing
    )
