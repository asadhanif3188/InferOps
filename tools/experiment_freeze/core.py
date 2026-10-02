"""Experiment freeze records: every required field, and no edit after merge.

A freeze record fixes an experiment family before its first result-bearing run: what
is run, against which inputs, how often, what counts as a pass, where the evidence
goes, when the run stops, how it is cleaned up, and which evidence level it aims at.
A result is only as good as the record it was frozen against, so this module checks
two things about every committed record.

**Every freeze field is answered.** :data:`FREEZE_FIELDS` lists the thirteen fields
the experiment freeze procedure requires. Each is a list of entries, and the entries
of one field together cover every part of the experiment exactly once. An entry
answers in one of three ways:

- ``value`` - a value that is not empty and is not a placeholder;
- ``not-applicable`` - with a ``reason``, for a field the part has no counterpart for,
  and never for a field in :data:`ALWAYS_ANSWERED`, which every run has;
- ``pending`` - only where :data:`PENDING_ALLOWED` names the experiment, the field,
  and the part, and only with the owner it names.

Every acceptance criterion has an identifier and a statement. A field that is
missing, an entry that is empty, a ``not-applicable`` without a
reason, and a ``pending`` anywhere else are refused. Nothing is inferred: a field
with no entry is not read as "not applicable".

**A merged record is never edited.** :data:`FROZEN_RECORDS` pins the content digest of
every committed record. A record whose content differs from its pin is refused, and
so is a record nobody pinned. A change is a new revision: ``freeze-r<N+1>`` names the
revision it supersedes by path and content digest, and classifies every pinned input
whose digest moved since that revision as material or not, with a reason.

**The content digest** of a file is the SHA-256 of its bytes with every CRLF replaced
by LF: the bytes Git stores for a text file under this repository's attributes. A
Windows checkout and a Linux one give the same digest.

**What this does not do.** It does not run an experiment, and it does not stop a
change to a pinned input from merging. :func:`changed_inputs` lists every pinned
input whose content differs from its pin, so the run that follows a freeze can refuse
to start until a merged revision classifies the change. Nothing here reads Git
history, and nothing checks that a revision a record names is a commit.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

__all__ = [
    "ALWAYS_ANSWERED",
    "API_VERSION",
    "EVIDENCE_LEVELS",
    "FREEZE_FIELDS",
    "FROZEN_RECORDS",
    "KIND",
    "PENDING_ALLOWED",
    "RECORDS_DIR",
    "REPO_ROOT",
    "RULES",
    "STATUSES",
    "Finding",
    "FreezeField",
    "InputChange",
    "PendingAllowance",
    "Rule",
    "changed_inputs",
    "check_record",
    "check_repository",
    "content_digest",
    "record_paths",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: Where freeze records are committed, one directory per experiment family.
RECORDS_DIR: Final = "docs/proof/experiments"

#: A freeze record's file name: its revision, counted from 1.
RECORD_NAME: Final = re.compile(r"^freeze-r([1-9][0-9]*)\.v1alpha1\.json$")

API_VERSION: Final = "inferops.io/v1alpha1"
KIND: Final = "ExperimentFreeze"

#: The three ways an entry can answer a freeze field.
STATUSES: Final = ("value", "not-applicable", "pending")

#: The project's evidence levels, as docs/testing/evidence-levels.md defines them.
EVIDENCE_LEVELS: Final = ("C0", "C1", "C2", "C3", "C4")

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")

#: Words that stand in for an answer rather than give one. A value that is only one
#: of these, or only a ``<...>`` placeholder, is refused: ``not-applicable`` and
#: ``pending`` are the statuses that say so, with a reason.
_PLACEHOLDER_WORDS: Final = frozenset(
    {
        "tbd",
        "tbc",
        "todo",
        "fixme",
        "n/a",
        "na",
        "unknown",
        "pending",
        "not applicable",
        "-",
        "?",
        ".",
        "...",
    }
)
_PLACEHOLDER: Final = re.compile(r"^<[^<>]*>$")


@dataclass(frozen=True)
class FreezeField:
    """One field the experiment freeze procedure requires a record to carry."""

    key: str
    statement: str


#: The thirteen fields, in the order the freeze procedure lists them.
FREEZE_FIELDS: Final[tuple[FreezeField, ...]] = (
    FreezeField("experimentIdVersion", "The experiment's identifier and version."),
    FreezeField(
        "gitRevision", "The Git revision, or the pinned inputs, the run must use."
    ),
    FreezeField("environmentIdentity", "The environment the run executes in."),
    FreezeField(
        "callerProfileRevision", "The revision of the caller profile selected."
    ),
    FreezeField("topology", "What is deployed, and how many of each."),
    FreezeField("fault", "The fault the run injects."),
    FreezeField("repetitionCount", "How many result-bearing runs, and of what."),
    FreezeField("acceptanceCriteria", "What must hold for the run to pass."),
    FreezeField(
        "derivedNumericBounds",
        "The numeric bounds derived from runtime-startup and stable-caller qualification.",
    ),
    FreezeField("evidencePaths", "Where the run's evidence is written."),
    FreezeField("abortConditions", "The conditions that stop a run that has started."),
    FreezeField("cleanupProcedure", "How the run is cleaned up afterwards."),
    FreezeField("intendedEvidenceLevel", "The evidence level the run aims at."),
)


@dataclass(frozen=True)
class PendingAllowance:
    """The one place a field may be answered ``pending``, and who must answer it."""

    experiment: str
    field: str
    part: str
    owner: str


#: Every field a record may leave pending. E01-D's environment is not built when
#: the E01 family is frozen; the freeze revision that names it has an owner.
PENDING_ALLOWED: Final[tuple[PendingAllowance, ...]] = (
    PendingAllowance("V2-E01", "environmentIdentity", "E01-D", "V2-S3-004-PR1"),
)

#: The fields every part of every experiment has, so ``not-applicable`` is refused for
#: them: a run always has an identity, a revision, a repetition count, criteria, an
#: evidence path, abort conditions, a cleanup, and an intended level. The other five -
#: the environment, a caller profile, a topology, a fault, and derived bounds - are
#: ones an experiment part can lack.
ALWAYS_ANSWERED: Final = frozenset(
    {
        "experimentIdVersion",
        "gitRevision",
        "repetitionCount",
        "acceptanceCriteria",
        "evidencePaths",
        "abortConditions",
        "cleanupProcedure",
        "intendedEvidenceLevel",
    }
)

#: The content digest of every committed freeze record. A record is pinned when it
#: is added, and the pin is never changed afterwards: a change is a new revision.
FROZEN_RECORDS: Final[Mapping[str, str]] = {
    "docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json": (
        "fcb19502d1d8350395b88293f4e3e2bf92076591e3fa8ecfc814defa46267fa9"
    ),
}


@dataclass(frozen=True)
class Rule:
    """A property every committed freeze record has to hold."""

    rule_id: str
    statement: str


#: The rules :func:`check_record` and :func:`check_repository` apply, in report order.
RULES: Final[tuple[Rule, ...]] = (
    Rule("freeze-record-unreadable", "A freeze record is a JSON object."),
    Rule(
        "freeze-record-shape",
        "A freeze record declares its version and kind, its metadata, and its parts.",
    ),
    Rule("freeze-field-missing", "A freeze record carries every freeze field."),
    Rule(
        "freeze-field-unknown",
        "A freeze record carries no field the procedure does not name.",
    ),
    Rule(
        "freeze-field-parts",
        "The entries of one field cover every part of the experiment exactly once.",
    ),
    Rule(
        "freeze-field-status-unknown",
        "An entry is a value, not-applicable, or pending.",
    ),
    Rule("freeze-field-empty", "A value is not empty, and is not a placeholder."),
    Rule(
        "freeze-field-reason-missing",
        "A not-applicable or pending entry states its reason.",
    ),
    Rule(
        "freeze-field-pending-not-allowed",
        "Only an allowed field of an allowed part is pending, and it names its owner.",
    ),
    Rule(
        "freeze-field-always-answered",
        "A field every run has is never answered not-applicable.",
    ),
    Rule(
        "freeze-criteria-malformed",
        "Every acceptance criterion has an identifier and a statement, and no identifier "
        "is used twice in a record.",
    ),
    Rule(
        "freeze-evidence-level-unknown",
        "An intended evidence level is one of the project's evidence levels.",
    ),
    Rule(
        "freeze-pinned-input-malformed",
        "Every pinned input names one repository path once, with a content digest.",
    ),
    Rule("freeze-record-unregistered", "Every committed freeze record is pinned."),
    Rule("freeze-record-missing", "Every pinned freeze record is committed."),
    Rule("freeze-record-edited", "A committed freeze record is what was pinned."),
    Rule(
        "freeze-revision-sequence",
        "An experiment's revisions are numbered from 1 without a gap, as their files are.",
    ),
    Rule(
        "freeze-revision-supersedes",
        "Revision 1 supersedes nothing; a later revision names the one before it and "
        "its content digest.",
    ),
    Rule(
        "freeze-input-change-unclassified",
        "A revision classifies every pinned input that changed since the revision it "
        "supersedes.",
    ),
)


@dataclass(frozen=True)
class Finding:
    """One way a committed freeze record breaks a rule."""

    rule_id: str
    record: str
    location: str
    detail: str


@dataclass(frozen=True)
class InputChange:
    """A pinned input whose content differs from its pin. ``actual`` is None when absent."""

    path: str
    pinned: str
    actual: str | None


def content_digest(data: bytes) -> str:
    """The SHA-256 of ``data`` with every CRLF replaced by LF."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


# --------------------------------------------------------------------------
# One record's content
# --------------------------------------------------------------------------


def _blank(value: Any) -> str | None:
    """Why ``value`` answers nothing, or None when it is an answer."""
    if value is None:
        return "null"
    if isinstance(value, bool | int | float):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "an empty string"
        if text.lower() in _PLACEHOLDER_WORDS or _PLACEHOLDER.match(text):
            return f"a placeholder, {text!r}"
        return None
    if isinstance(value, Mapping):
        if not value:
            return "an empty object"
        for key, member in value.items():
            reason = _blank(member)
            if reason is not None:
                return f"{reason} at {key}"
        return None
    if isinstance(value, Sequence):
        if not value:
            return "an empty list"
        for index, member in enumerate(value):
            reason = _blank(member)
            if reason is not None:
                return f"{reason} at [{index}]"
        return None
    return f"a {type(value).__name__}"


def _parts(record: Mapping[str, Any]) -> list[str] | None:
    parts = record.get("parts")
    if not isinstance(parts, list) or not parts:
        return None
    ids = [part.get("id") if isinstance(part, Mapping) else None for part in parts]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(
        set(ids)
    ) != len(ids):
        return None
    return [str(i) for i in ids]


def _pending_owner(experiment: object, field: str, parts: Sequence[str]) -> str | None:
    if len(parts) != 1:
        return None
    for allowance in PENDING_ALLOWED:
        if (allowance.experiment, allowance.field, allowance.part) == (
            experiment,
            field,
            parts[0],
        ):
            return allowance.owner
    return None


def _entry_findings(
    name: str, experiment: object, key: str, index: int, entry: Any
) -> Iterator[Finding]:
    where = f"fields.{key}[{index}]"
    if not isinstance(entry, Mapping):
        yield Finding(
            "freeze-field-status-unknown", name, where, "an entry is an object"
        )
        return
    status = entry.get("status")
    parts = [p for p in entry.get("parts", []) if isinstance(p, str)]
    if "note" in entry and _blank(entry["note"]) is not None:
        yield Finding(
            "freeze-field-empty", name, f"{where}.note", "a note says something"
        )
    if status == "value":
        reason = _blank(entry.get("value"))
        if reason is not None:
            yield Finding(
                "freeze-field-empty", name, f"{where}.value", f"the value is {reason}"
            )
        elif (
            key == "intendedEvidenceLevel" and entry.get("value") not in EVIDENCE_LEVELS
        ):
            yield Finding(
                "freeze-evidence-level-unknown",
                name,
                f"{where}.value",
                f"the level is one of {', '.join(EVIDENCE_LEVELS)}",
            )
    elif status in ("not-applicable", "pending"):
        if status == "not-applicable" and key in ALWAYS_ANSWERED:
            yield Finding(
                "freeze-field-always-answered",
                name,
                f"{where}.status",
                "every run has this field, so it is answered with a value",
            )
        if _blank(entry.get("reason")) is not None:
            yield Finding(
                "freeze-field-reason-missing",
                name,
                f"{where}.reason",
                f"{status} needs a reason",
            )
        if status == "pending":
            owner = _pending_owner(experiment, key, parts)
            if owner is None:
                yield Finding(
                    "freeze-field-pending-not-allowed",
                    name,
                    where,
                    "no allowance lets this field of these parts be pending",
                )
            elif entry.get("owner") != owner:
                yield Finding(
                    "freeze-field-pending-not-allowed",
                    name,
                    f"{where}.owner",
                    f"a pending entry here names its owner, {owner}",
                )
    else:
        yield Finding(
            "freeze-field-status-unknown",
            name,
            f"{where}.status",
            f"the status is one of {', '.join(STATUSES)}",
        )


def _pinned_input_findings(name: str, record: Mapping[str, Any]) -> Iterator[Finding]:
    pinned = record.get("pinnedInputs")
    if not isinstance(pinned, list) or not pinned:
        yield Finding(
            "freeze-pinned-input-malformed",
            name,
            "pinnedInputs",
            "a record pins its inputs",
        )
        return
    seen: set[str] = set()
    for index, item in enumerate(pinned):
        where = f"pinnedInputs[{index}]"
        path = item.get("path") if isinstance(item, Mapping) else None
        digest = item.get("sha256") if isinstance(item, Mapping) else None
        role = item.get("role") if isinstance(item, Mapping) else None
        if (
            not isinstance(path, str)
            or not path
            or PurePosixPath(path).is_absolute()
            or ".." in PurePosixPath(path).parts
            or "\\" in path
        ):
            yield Finding(
                "freeze-pinned-input-malformed",
                name,
                where,
                "a relative POSIX repository path",
            )
            continue
        if path in seen:
            yield Finding(
                "freeze-pinned-input-malformed", name, where, f"{path} is pinned twice"
            )
        seen.add(path)
        if not isinstance(digest, str) or not _SHA256.match(digest):
            yield Finding(
                "freeze-pinned-input-malformed",
                name,
                f"{where}.sha256",
                "64 lowercase hex digits",
            )
        if _blank(role) is not None:
            yield Finding(
                "freeze-pinned-input-malformed", name, f"{where}.role", "a role"
            )


def check_record(document: Any, name: str = "record") -> list[Finding]:
    """Every way one record's content breaks a rule. Empty when it holds them all.

    This reads only the document. Whether it is pinned, and whether its revision
    follows the one before it, is :func:`check_repository`'s.
    """
    if not isinstance(document, Mapping):
        return [Finding("freeze-record-unreadable", name, "$", "a JSON object")]
    findings: list[Finding] = []
    metadata = document.get("metadata")
    parts = _parts(document)
    if (
        document.get("apiVersion") != API_VERSION
        or document.get("kind") != KIND
        or not isinstance(metadata, Mapping)
        or not isinstance(metadata.get("experiment"), str)
        or not isinstance(metadata.get("revision"), int)
        or isinstance(metadata.get("revision"), bool)
        or parts is None
    ):
        findings.append(
            Finding(
                "freeze-record-shape",
                name,
                "$",
                f"apiVersion {API_VERSION}, kind {KIND}, metadata.experiment, an integer "
                "metadata.revision, and parts with unique ids",
            )
        )
        return findings
    experiment = metadata["experiment"]
    fields = document.get("fields")
    if not isinstance(fields, Mapping):
        fields = {}
    known = {field.key for field in FREEZE_FIELDS}
    for field in FREEZE_FIELDS:
        if field.key not in fields:
            findings.append(
                Finding(
                    "freeze-field-missing", name, f"fields.{field.key}", field.statement
                )
            )
    for key in sorted(set(fields) - known):
        findings.append(
            Finding(
                "freeze-field-unknown",
                name,
                f"fields.{key}",
                "the procedure names no such field",
            )
        )
    for field in FREEZE_FIELDS:
        entries = fields.get(field.key)
        if field.key not in fields:
            continue
        if not isinstance(entries, list) or not entries:
            findings.append(
                Finding(
                    "freeze-field-empty",
                    name,
                    f"fields.{field.key}",
                    "a field has entries",
                )
            )
            continue
        covered: list[str] = []
        for index, entry in enumerate(entries):
            findings.extend(_entry_findings(name, experiment, field.key, index, entry))
            if isinstance(entry, Mapping) and isinstance(entry.get("parts"), list):
                covered.extend(p for p in entry["parts"] if isinstance(p, str))
        if sorted(covered) != sorted(parts):
            missing = sorted(set(parts) - set(covered))
            extra = sorted(
                {p for p in covered if covered.count(p) > 1 or p not in parts}
            )
            findings.append(
                Finding(
                    "freeze-field-parts",
                    name,
                    f"fields.{field.key}",
                    f"uncovered {missing}, repeated or unknown {extra}",
                )
            )
    findings.extend(_criteria_findings(name, fields.get("acceptanceCriteria")))
    findings.extend(_pinned_input_findings(name, document))
    return _in_rule_order(findings)


def _criteria_findings(name: str, entries: Any) -> Iterator[Finding]:
    """Each criterion an object with an identifier and a statement, no identifier twice."""
    if not isinstance(entries, list):
        return
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or entry.get("status") != "value":
            continue
        value = entry.get("value")
        criteria = value if isinstance(value, list) else [value]
        for position, criterion in enumerate(criteria):
            where = f"fields.acceptanceCriteria[{index}].value[{position}]"
            identifier = criterion.get("id") if isinstance(criterion, Mapping) else None
            statement = (
                criterion.get("statement") if isinstance(criterion, Mapping) else None
            )
            if _blank(identifier) is not None or _blank(statement) is not None:
                yield Finding(
                    "freeze-criteria-malformed", name, where, "an id and a statement"
                )
            elif identifier in seen:
                yield Finding(
                    "freeze-criteria-malformed",
                    name,
                    where,
                    f"{identifier} is used twice",
                )
            else:
                seen.add(str(identifier))


# --------------------------------------------------------------------------
# The committed records, their pins, and their revisions
# --------------------------------------------------------------------------


def record_paths(root: Path = REPO_ROOT) -> list[str]:
    """Every committed freeze record under the records directory, by repository path."""
    base = root / RECORDS_DIR
    if not base.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in base.rglob("freeze-r*.json")
        if path.is_file()
    )


def _load(root: Path, path: str) -> tuple[bytes, Any]:
    data = (root / path).read_bytes()
    try:
        return data, json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return data, None


def _pinned(document: Any) -> dict[str, str]:
    if not isinstance(document, Mapping) or not isinstance(
        document.get("pinnedInputs"), list
    ):
        return {}
    return {
        item["path"]: item["sha256"]
        for item in document["pinnedInputs"]
        if isinstance(item, Mapping)
        and isinstance(item.get("path"), str)
        and isinstance(item.get("sha256"), str)
    }


def _revision_findings(
    path: str, document: Mapping[str, Any], previous: tuple[str, bytes, Any] | None
) -> Iterator[Finding]:
    supersedes = document.get("metadata", {}).get("supersedes")
    if previous is None:
        if supersedes is not None:
            yield Finding(
                "freeze-revision-supersedes",
                path,
                "metadata.supersedes",
                "revision 1 is null",
            )
        return
    previous_path, previous_bytes, previous_document = previous
    if (
        not isinstance(supersedes, Mapping)
        or supersedes.get("path") != previous_path
        or supersedes.get("contentSha256") != content_digest(previous_bytes)
    ):
        yield Finding(
            "freeze-revision-supersedes",
            path,
            "metadata.supersedes",
            f"names {previous_path} and its content digest",
        )
    before, after = _pinned(previous_document), _pinned(document)
    moved = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    classified: dict[str, Any] = {}
    changes = document.get("inputChanges")
    if isinstance(changes, list):
        for change in changes:
            if isinstance(change, Mapping) and isinstance(change.get("path"), str):
                classified[change["path"]] = change
    for moved_path in moved:
        change = classified.get(moved_path)
        if (
            change is None
            or not isinstance(change.get("material"), bool)
            or _blank(change.get("reason")) is not None
        ):
            yield Finding(
                "freeze-input-change-unclassified",
                path,
                f"inputChanges[{moved_path}]",
                "a moved input is classified as material true or false, with a reason",
            )


def check_repository(root: Path = REPO_ROOT) -> list[Finding]:
    """Every way the committed freeze records break a rule. Empty when none does."""
    findings: list[Finding] = []
    committed = record_paths(root)
    for path in sorted(set(FROZEN_RECORDS) - set(committed)):
        findings.append(
            Finding("freeze-record-missing", path, "$", "the pinned record is absent")
        )
    by_experiment: dict[str, list[tuple[int, str, bytes, Any]]] = {}
    for path in committed:
        data, document = _load(root, path)
        findings.extend(check_record(document, path))
        pinned = FROZEN_RECORDS.get(path)
        if pinned is None:
            findings.append(
                Finding(
                    "freeze-record-unregistered",
                    path,
                    "$",
                    "add its content digest to FROZEN_RECORDS",
                )
            )
        elif content_digest(data) != pinned:
            findings.append(
                Finding(
                    "freeze-record-edited",
                    path,
                    "$",
                    "the content differs from its pin; a change is a new revision",
                )
            )
        match = RECORD_NAME.match(PurePosixPath(path).name)
        metadata = document.get("metadata") if isinstance(document, Mapping) else None
        if match is None or not isinstance(metadata, Mapping):
            findings.append(
                Finding(
                    "freeze-revision-sequence",
                    path,
                    "$",
                    "named freeze-r<N>.v1alpha1.json",
                )
            )
            continue
        if metadata.get("revision") != int(match.group(1)):
            findings.append(
                Finding(
                    "freeze-revision-sequence",
                    path,
                    "metadata.revision",
                    "the revision is the one the file name carries",
                )
            )
        directory = PurePosixPath(path).parent.as_posix()
        by_experiment.setdefault(directory, []).append(
            (int(match.group(1)), path, data, document)
        )
    for directory, records in sorted(by_experiment.items()):
        records.sort()
        experiments = {
            r[3].get("metadata", {}).get("experiment")
            for r in records
            if isinstance(r[3], Mapping)
        }
        if [r[0] for r in records] != list(range(1, len(records) + 1)) or len(
            experiments
        ) != 1:
            findings.append(
                Finding(
                    "freeze-revision-sequence",
                    directory,
                    "$",
                    "one experiment per directory, revisions 1 to N without a gap",
                )
            )
        previous: tuple[str, bytes, Any] | None = None
        for _, path, data, document in records:
            if isinstance(document, Mapping):
                findings.extend(_revision_findings(path, document, previous))
            previous = (path, data, document)
    return _in_rule_order(findings)


def changed_inputs(
    document: Mapping[str, Any], root: Path = REPO_ROOT
) -> list[InputChange]:
    """Every pinned input of ``document`` whose content differs from its pin.

    A file that is absent is reported with ``actual`` None. This reads files and
    writes none, and says nothing about whether a change is material.
    """
    changes = []
    for path, pinned in sorted(_pinned(document).items()):
        target = root / path
        actual = content_digest(target.read_bytes()) if target.is_file() else None
        if actual != pinned:
            changes.append(InputChange(path, pinned, actual))
    return changes


def _in_rule_order(findings: list[Finding]) -> list[Finding]:
    order = {rule.rule_id: index for index, rule in enumerate(RULES)}
    return sorted(findings, key=lambda finding: order[finding.rule_id])
