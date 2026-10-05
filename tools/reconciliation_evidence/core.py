"""The reconciliation state a GitOps controller reported, as an evidence record.

The Application procedure's ``observe`` operation reads the Application and the
workload objects a bounded number of times and writes what each read returned
into one directory. This module reads that directory. It reads no cluster. It
returns one record: what the controller reported at each sample, which fields
it did not report, and which reported values changed between two samples.

**A value that was not reported is not a value.** Each field of a sample has one
of four states. ``reported`` carries the value. ``missing`` means that the
object was read and did not hold the field. ``malformed`` means that the field
held a value of another type. ``not-collected`` means that no object was read:
the read did not answer, the object was absent, or the answer was not one JSON
object. No state other than ``reported`` carries a value, and no function here
replaces one with a default. :func:`settled` is false for every sample that
lacks one required field, and it names the field.

**What is read from an object is an allowlist.** The record holds the fields
named in :data:`REQUIRED_FIELDS` and :data:`OPTIONAL_FIELDS`, the type and a
bounded, redacted message of each condition, and three labels of each workload
object. It holds no other part of an object. Each distinct list of objects is
held once, and a sample names the list that it read.

**What a reported state is.** It is what the controller wrote about its own
work: a commit, a sync state, and a health state that it derives from
Kubernetes objects. It is reconciliation evidence. It is not a caller outcome,
and :data:`DOES_NOT_ESTABLISH` is part of every record.

**A transition is a difference between two consecutive samples.** What happened
between two samples was not observed. A state that began and ended between two
samples leaves no transition.

Given a clone that holds the commit a sample reports, the record also compares
that sample with the provenance of the desired-state release at that commit:
the reported commits, the source the Application declares, and the labels of
the workload objects. A comparison that could not be made is recorded as not
compared. It is never recorded as consistent.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

from inferops.domain.release import is_credential_shaped
from tools.desired_state_provenance import (
    CHART_LABEL,
    VERSION_LABEL,
    WORKLOAD_LABEL,
    Provenance,
    ProvenanceRefused,
    ReconciliationSource,
    is_immutable_revision,
    metadata_findings,
    observed_revision_findings,
    resolve,
    source_findings,
)
from tools.generated_release import REPO_ROOT, DeclaredRelease

__all__ = [
    "APPLICATION_STATES",
    "DOES_NOT_ESTABLISH",
    "FIELD_STATES",
    "OPTIONAL_FIELDS",
    "RECORD_SCHEMA",
    "REPOSITORY",
    "REPO_ROOT",
    "REQUIRED_FIELDS",
    "TRANSITION_FIELDS",
    "CollectionRefused",
    "Field",
    "Sample",
    "application_fields",
    "build_record",
    "diagnostic_text",
    "read_collection",
    "settled",
    "transitions",
]

#: The identifier of the record :func:`build_record` returns.
RECORD_SCHEMA: Final = "inferops.io/reconciliation-observation/v1alpha1"

#: The address this repository is published at. Restated on purpose: a test
#: compares it with the committed Application.
REPOSITORY: Final = "https://github.com/asadhanif3188/InferOps.git"

REPORTED: Final = "reported"
MISSING: Final = "missing"
MALFORMED: Final = "malformed"
NOT_COLLECTED: Final = "not-collected"

#: The states of one field of one sample. Only ``reported`` carries a value.
FIELD_STATES: Final = (REPORTED, MISSING, MALFORMED, NOT_COLLECTED)

#: The states of one read of the Application. ``not-taken`` is a sample the
#: collection was asked for and did not write.
APPLICATION_STATES: Final = (
    "reported",
    "absent",
    "unanswered",
    "unreadable",
    "not-taken",
)

_TEXT: Final = "text"
_FLAG: Final = "flag"
_TEXTS: Final = "texts"
_NUMBER: Final = "number"

#: The fields a sample needs before :func:`settled` can be true, with the path
#: of each in the Application object and its type.
REQUIRED_FIELDS: Final[Mapping[str, tuple[tuple[str, ...], str]]] = {
    "syncStatus": (("status", "sync", "status"), _TEXT),
    "resolvedRevision": (("status", "sync", "revision"), _TEXT),
    "healthStatus": (("status", "health", "status"), _TEXT),
    "operationPhase": (("status", "operationState", "phase"), _TEXT),
    "operationRevision": (
        ("status", "operationState", "syncResult", "revision"),
        _TEXT,
    ),
}

#: The other fields the record holds. An absent one does not change
#: :func:`settled`.
OPTIONAL_FIELDS: Final[Mapping[str, tuple[tuple[str, ...], str]]] = {
    "repository": (("spec", "source", "repoURL"), _TEXT),
    "followedRevision": (("spec", "source", "targetRevision"), _TEXT),
    "chartPath": (("spec", "source", "path"), _TEXT),
    "valueFiles": (("spec", "source", "helm", "valueFiles"), _TEXTS),
    "automatedSelfHeal": (("spec", "syncPolicy", "automated", "selfHeal"), _FLAG),
    "automatedPrune": (("spec", "syncPolicy", "automated", "prune"), _FLAG),
    "reconciledAt": (("status", "reconciledAt"), _TEXT),
    "operationStartedAt": (("status", "operationState", "startedAt"), _TEXT),
    "operationFinishedAt": (("status", "operationState", "finishedAt"), _TEXT),
    "operationAutomated": (
        ("status", "operationState", "operation", "initiatedBy", "automated"),
        _FLAG,
    ),
    "deletionTimestamp": (("metadata", "deletionTimestamp"), _TEXT),
}

#: Fields of the last entry of ``status.history``.
_HISTORY_FIELDS: Final[Mapping[str, tuple[str, str]]] = {
    "historyId": ("id", _NUMBER),
    "historyRevision": ("revision", _TEXT),
    "historyDeployedAt": ("deployedAt", _TEXT),
}

#: The fields whose changes :func:`transitions` reports, in report order.
TRANSITION_FIELDS: Final = (
    "syncStatus",
    "resolvedRevision",
    "healthStatus",
    "operationPhase",
    "operationRevision",
    "operationStartedAt",
    "operationFinishedAt",
    "historyId",
)

#: What no record of this kind establishes. :func:`build_record` copies it into
#: every record.
DOES_NOT_ESTABLISH: Final = (
    "That a caller request was answered. A sync state and a health state are what "
    "the controller reports. They are not a caller outcome.",
    "That a field with a state other than reported had any value. A field that "
    "was not reported is not healthy, not synced, and not unhealthy.",
    "What happened between two samples. A state that began and ended between two "
    "samples leaves no transition.",
    "That the controller applied the commit it reports, or that an applied object "
    "was rendered at that commit.",
    "That the reported commit is on a branch, or that a merge was reviewed.",
    "Anything about the API image or the hand-written values. Neither is read "
    "from the reported commit.",
    "That the record holds no secret. It is built from an allowlist of fields, "
    "and a message is cut and passed through a prefix heuristic.",
)

_MESSAGE_LIMIT: Final = 240
_CONDITION_LIMIT: Final = 10
_OBJECT_LIMIT: Final = 200
_USERINFO: Final = re.compile(r"//[^/@\s]+@")
_SAMPLE_META: Final = re.compile(r"sample-(\d{3})\.meta")
_PROVENANCE_LABELS: Final = (CHART_LABEL, VERSION_LABEL, WORKLOAD_LABEL)


class CollectionRefused(Exception):
    """A directory that is not one collection of the ``observe`` operation."""


@dataclass(frozen=True)
class Field:
    """One field of one sample: a state, and a value only when it was reported."""

    state: str
    value: Any = None

    def as_document(self) -> dict[str, Any]:
        if self.state == REPORTED:
            return {"state": self.state, "value": self.value}
        return {"state": self.state}


_NOT_COLLECTED: Final = Field(NOT_COLLECTED)


@dataclass(frozen=True)
class Sample:
    """One read of the Application and one read of the workload objects."""

    index: int
    observed_at: Field
    application_state: str
    fields: Mapping[str, Field]
    conditions: tuple[Mapping[str, Any], ...]
    operation_message: Field
    objects_state: str
    objects: tuple[Mapping[str, Any], ...]
    objects_not_recorded: int = 0

    def field(self, name: str) -> Field:
        return self.fields.get(name, _NOT_COLLECTED)


# --------------------------------------------------------------------------
# One object, as fields
# --------------------------------------------------------------------------


def diagnostic_text(value: object) -> str:
    """A message as one bounded line, without the credential shapes this knows.

    White space is collapsed. The user part of an address is replaced. A word
    that the release domain's prefix heuristic calls credential-shaped is
    replaced. The result is cut to a fixed length. The heuristic knows only the
    prefixes it was given.
    """
    text = " ".join(str(value).split())
    text = _USERINFO.sub("//<redacted>@", text)
    words = [
        "<redacted>" if is_credential_shaped(word) else word for word in text.split(" ")
    ]
    text = " ".join(words)
    if len(text) > _MESSAGE_LIMIT:
        return text[: _MESSAGE_LIMIT - 3] + "..."
    return text


def _typed(value: object, kind: str) -> Field:
    if kind == _TEXT:
        return Field(REPORTED, value) if isinstance(value, str) and value else _bad()
    if kind == _FLAG:
        return Field(REPORTED, value) if isinstance(value, bool) else _bad()
    if kind == _NUMBER:
        usable = isinstance(value, int) and not isinstance(value, bool)
        return Field(REPORTED, value) if usable else _bad()
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return Field(REPORTED, list(value))
    return _bad()


def _bad() -> Field:
    return Field(MALFORMED)


def _at(document: Mapping[str, Any], path: Sequence[str], kind: str) -> Field:
    """The field at ``path``. An absent key and a null are both ``missing``."""
    current: Any = document
    for key in path:
        if not isinstance(current, Mapping):
            return Field(MALFORMED)
        if key not in current or current[key] is None:
            return Field(MISSING)
        current = current[key]
    return _typed(current, kind)


def application_fields(document: Mapping[str, Any]) -> dict[str, Field]:
    """Every allowlisted field of one Application object, each with its state."""
    fields = {
        name: _at(document, path, kind)
        for name, (path, kind) in {**REQUIRED_FIELDS, **OPTIONAL_FIELDS}.items()
    }
    status = document.get("status")
    history = status.get("history") if isinstance(status, Mapping) else None
    if history is None:
        last: Any = None
        state = MISSING
    elif isinstance(history, list) and history and isinstance(history[-1], Mapping):
        last, state = history[-1], REPORTED
    elif isinstance(history, list) and not history:
        last, state = None, MISSING
    else:
        last, state = None, MALFORMED
    for name, (key, kind) in _HISTORY_FIELDS.items():
        fields[name] = _at(last, (key,), kind) if state == REPORTED else Field(state)
    return fields


def _conditions(document: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    status = document.get("status")
    listed = status.get("conditions") if isinstance(status, Mapping) else None
    found = []
    for entry in listed if isinstance(listed, list) else []:
        if not isinstance(entry, Mapping):
            continue
        found.append(
            {
                "type": _at(entry, ("type",), _TEXT).as_document(),
                "message": _message(entry.get("message")).as_document(),
                "lastTransitionTime": _at(
                    entry, ("lastTransitionTime",), _TEXT
                ).as_document(),
            }
        )
    return tuple(found[:_CONDITION_LIMIT])


def _message(value: object) -> Field:
    if value is None:
        return Field(MISSING)
    if not isinstance(value, str):
        return Field(MALFORMED)
    return Field(REPORTED, diagnostic_text(value))


def _operation_message(document: Mapping[str, Any]) -> Field:
    status = document.get("status")
    state = status.get("operationState") if isinstance(status, Mapping) else None
    return _message(state.get("message") if isinstance(state, Mapping) else None)


# --------------------------------------------------------------------------
# One directory, as samples
# --------------------------------------------------------------------------


def _pairs(path: Path) -> dict[str, str]:
    """The ``key=value`` lines of one file the collection wrote."""
    found = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key:
            found[key] = value
    return found


def _stated(pairs: Mapping[str, str], key: str) -> Field:
    value = pairs.get(key)
    return Field(REPORTED, value) if value else Field(MISSING)


def _count(pairs: Mapping[str, str], key: str) -> Field:
    value = pairs.get(key)
    if not value:
        return Field(MISSING)
    return (
        Field(REPORTED, int(value)) if value.isascii() and value.isdigit() else _bad()
    )


def _objects(text: str) -> tuple[list[dict[str, Any]], int]:
    """The workload objects of one read: kind, name, and the three labels."""
    found: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        kind, _, rest = line.partition("\t")
        name, _, labels_text = rest.partition("\t")
        try:
            labels = json.loads(labels_text) if labels_text.strip() else None
        except (ValueError, RecursionError):
            labels = MALFORMED
        if labels is None:
            carried: dict[str, Any] = {
                label: Field(MISSING).as_document() for label in _PROVENANCE_LABELS
            }
        elif not isinstance(labels, Mapping):
            carried = {
                label: Field(MALFORMED).as_document() for label in _PROVENANCE_LABELS
            }
        else:
            carried = {
                label: _at(labels, (label,), _TEXT).as_document()
                for label in _PROVENANCE_LABELS
            }
        found.append({"kind": kind.strip(), "name": name.strip(), "labels": carried})
    found.sort(key=lambda entry: (entry["kind"], entry["name"]))
    return found[:_OBJECT_LIMIT], max(0, len(found) - _OBJECT_LIMIT)


def _sample(directory: Path, index: int) -> Sample:
    stem = f"sample-{index:03d}"
    meta_path = directory / f"{stem}.meta"
    if not meta_path.is_file():
        return Sample(
            index, Field(MISSING), "not-taken", {}, (), _NOT_COLLECTED, "not-taken", ()
        )
    meta = _pairs(meta_path)

    application_state = "unanswered"
    fields: dict[str, Field] = {}
    conditions: tuple[Mapping[str, Any], ...] = ()
    operation_message = _NOT_COLLECTED
    application_path = directory / f"{stem}.application.json"
    if meta.get("applicationRead") == "answered" and application_path.is_file():
        text = application_path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            application_state = "absent"
        else:
            try:
                document = json.loads(text)
            except (ValueError, RecursionError):
                document = None
            if isinstance(document, dict):
                application_state = "reported"
                fields = application_fields(document)
                conditions = _conditions(document)
                operation_message = _operation_message(document)
            else:
                application_state = "unreadable"

    objects_state = "unanswered"
    objects: list[dict[str, Any]] = []
    dropped = 0
    objects_path = directory / f"{stem}.objects.txt"
    if meta.get("objectsRead") == "answered" and objects_path.is_file():
        objects_state = "collected"
        objects, dropped = _objects(
            objects_path.read_text(encoding="utf-8", errors="replace")
        )
    return Sample(
        index=index,
        observed_at=_stated(meta, "observedAt"),
        application_state=application_state,
        fields=fields,
        conditions=conditions,
        operation_message=operation_message,
        objects_state=objects_state,
        objects=tuple(objects),
        objects_not_recorded=dropped,
    )


def read_collection(directory: Path) -> tuple[dict[str, Any], tuple[Sample, ...]]:
    """What one ``observe`` collection wrote: its header and its samples.

    A sample that the collection was asked for and did not write is returned
    with the state ``not-taken``. A sample file with a higher number than the
    collection asked for is also returned.

    Raises:
        CollectionRefused: the directory holds no ``collection.meta``, or that
            file does not state how many samples were asked for.
    """
    header_path = directory / "collection.meta"
    if not header_path.is_file():
        raise CollectionRefused(
            "the directory holds no collection.meta; it is not a collection of "
            "the observe operation"
        )
    header = _pairs(header_path)
    requested = _count(header, "requestedSamples")
    if requested.state != REPORTED or not 1 <= requested.value <= 999:
        raise CollectionRefused(
            "collection.meta does not state requestedSamples as a number from 1 to 999"
        )
    end_path = directory / "collection.end"
    end = _pairs(end_path) if end_path.is_file() else {}
    completed = _count(end, "completedSamples")
    written = [
        int(match.group(1))
        for entry in sorted(directory.iterdir())
        if (match := _SAMPLE_META.fullmatch(entry.name)) is not None
    ]
    last = max([requested.value, *written])
    samples = tuple(_sample(directory, index) for index in range(1, last + 1))
    collection = {
        "provider": _stated(header, "provider").as_document(),
        "serverVersion": _stated(header, "serverVersion").as_document(),
        "repositoryRevision": _stated(header, "repositoryRevision").as_document(),
        "procedureSha256": _stated(header, "procedureSha256").as_document(),
        "librarySha256": _stated(header, "librarySha256").as_document(),
        "application": _stated(header, "application").as_document(),
        "applicationNamespace": _stated(header, "applicationNamespace").as_document(),
        "workloadNamespace": _stated(header, "workloadNamespace").as_document(),
        "requestedSamples": requested.value,
        "intervalSeconds": _count(header, "intervalSeconds").as_document(),
        "completedSamples": completed.as_document(),
        "complete": completed.state == REPORTED
        and completed.value == requested.value
        and all(sample.application_state != "not-taken" for sample in samples),
    }
    return collection, samples


# --------------------------------------------------------------------------
# What the samples say
# --------------------------------------------------------------------------


def settled(sample: Sample) -> tuple[bool, tuple[str, ...]]:
    """Whether the controller reported a succeeded sync of a healthy Application.

    True needs every required field reported, and then: the sync state
    ``Synced``, the health state ``Healthy``, the operation phase ``Succeeded``,
    a resolved revision that is a full commit identifier, an operation at that
    revision, and no deletion timestamp. Each reason names one condition that
    does not hold. A field that was not reported is a reason. It is never read
    as a passing value.

    True says what the controller reported. It says nothing about a caller.
    """
    if sample.application_state != "reported":
        return False, (f"the Application read is {sample.application_state}",)
    reasons = [
        f"{name} is {sample.field(name).state}"
        for name in REQUIRED_FIELDS
        if sample.field(name).state != REPORTED
    ]
    if reasons:
        return False, tuple(reasons)
    for name, wanted in (
        ("syncStatus", "Synced"),
        ("healthStatus", "Healthy"),
        ("operationPhase", "Succeeded"),
    ):
        value = sample.field(name).value
        if value != wanted:
            reasons.append(f"{name} is reported as {value}, and not {wanted}")
    resolved = sample.field("resolvedRevision").value
    if not is_immutable_revision(resolved):
        reasons.append("resolvedRevision is not a full commit identifier")
    if sample.field("operationRevision").value != resolved:
        reasons.append("operationRevision is not the resolved revision")
    # An Application that is being deleted keeps its last states for a time.
    if sample.field("deletionTimestamp").state != MISSING:
        reasons.append("the Application has a deletion timestamp")
    return not reasons, tuple(reasons)


def transitions(samples: Sequence[Sample]) -> list[dict[str, Any]]:
    """Every tracked field that differs between two consecutive samples.

    A field that was reported and is then not reported is a transition to that
    state. No value is carried across a sample that did not report it. The read
    state of the Application is tracked as ``applicationRead``.

    A sample that the collection did not take is not an observation, and no
    transition leads to it or from it. The collection's ``complete`` field says
    that samples are absent.
    """
    found = []
    taken = [sample for sample in samples if sample.application_state != "not-taken"]
    for before, after in pairwise(taken):
        pairs = [
            (
                "applicationRead",
                Field(REPORTED, before.application_state),
                Field(REPORTED, after.application_state),
            )
        ]
        pairs.extend(
            (name, before.field(name), after.field(name)) for name in TRANSITION_FIELDS
        )
        for name, old, new in pairs:
            if old != new:
                found.append(
                    {
                        "field": name,
                        "fromSample": before.index,
                        "toSample": after.index,
                        "fromObservedAt": before.observed_at.as_document(),
                        "toObservedAt": after.observed_at.as_document(),
                        "from": old.as_document(),
                        "to": new.as_document(),
                    }
                )
    return found


def _finding_documents(findings: Sequence[Any]) -> list[dict[str, str]]:
    return [
        {"rule": f.rule_id, "subject": f.subject, "detail": f.detail} for f in findings
    ]


def _not_compared(reason: str) -> dict[str, Any]:
    return {"state": "not-compared", "reason": reason}


def _consistency(
    sample: Sample, provenances: Mapping[str, Provenance | tuple[str, ...]]
) -> dict[str, Any]:
    """One sample beside the provenance at the commit that sample reports."""
    if sample.application_state != "reported":
        return _not_compared(f"the Application read is {sample.application_state}")
    resolved = sample.field("resolvedRevision")
    if resolved.state != REPORTED:
        return _not_compared(f"resolvedRevision is {resolved.state}")
    provenance = provenances.get(resolved.value)
    if provenance is None:
        return _not_compared("no provenance was asked for")
    if not isinstance(provenance, Provenance):
        return _not_compared(
            "the provenance at the reported commit was refused: "
            + ", ".join(provenance)
        )

    reported = {
        name: sample.field(name).value
        for name in ("resolvedRevision", "operationRevision", "historyRevision")
        if sample.field(name).state == REPORTED
    }
    not_reported = [
        name
        for name in ("operationRevision", "historyRevision")
        if sample.field(name).state != REPORTED
    ]
    result: dict[str, Any] = {
        "state": "compared",
        "releaseId": provenance.release_id,
        "revisionFindings": _finding_documents(
            observed_revision_findings(provenance, reported)
        ),
        "revisionsNotReported": not_reported,
    }

    source_names = ("repository", "followedRevision", "chartPath", "valueFiles")
    absent = [n for n in source_names if sample.field(n).state != REPORTED]
    if absent:
        result["source"] = _not_compared(
            "not reported: "
            + ", ".join(f"{n} is {sample.field(n).state}" for n in absent)
        )
    else:
        source = ReconciliationSource(
            repository=sample.field("repository").value,
            followed_revision=sample.field("followedRevision").value,
            chart_path=sample.field("chartPath").value,
            value_files=tuple(sample.field("valueFiles").value),
        )
        result["source"] = {
            "state": "compared",
            "findings": _finding_documents(
                source_findings(provenance, source, REPOSITORY)
            ),
        }

    if sample.objects_state != "collected":
        result["labels"] = _not_compared(f"the object read is {sample.objects_state}")
    elif not sample.objects:
        result["labels"] = _not_compared("the object read returned no object")
    else:
        label_findings = []
        for entry in sample.objects:
            carried = {
                label: field["value"]
                for label, field in entry["labels"].items()
                if field["state"] == REPORTED
            }
            for finding in metadata_findings(provenance, carried):
                label_findings.append(
                    {
                        "rule": finding.rule_id,
                        "subject": f"{entry['kind']}/{entry['name']}: {finding.subject}",
                        "detail": finding.detail,
                    }
                )
        result["labels"] = {
            "state": "compared",
            "objects": len(sample.objects),
            "findings": label_findings,
        }
    return result


def _object_set_id(objects: Sequence[Mapping[str, Any]]) -> str:
    """A name for one list of objects: the start of the SHA-256 of its JSON.

    Most samples of one observation read the same objects with the same labels.
    The record holds each distinct list once, under this name.
    """
    canonical = json.dumps(list(objects), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _sample_document(
    sample: Sample, provenances: Mapping[str, Provenance | tuple[str, ...]]
) -> dict[str, Any]:
    is_settled, reasons = settled(sample)
    names = (*REQUIRED_FIELDS, *OPTIONAL_FIELDS, *_HISTORY_FIELDS)
    return {
        "index": sample.index,
        "observedAt": sample.observed_at.as_document(),
        "applicationRead": sample.application_state,
        "fields": {name: sample.field(name).as_document() for name in names},
        "notReported": [
            name for name in REQUIRED_FIELDS if sample.field(name).state != REPORTED
        ],
        "conditions": list(sample.conditions),
        "operationMessage": sample.operation_message.as_document(),
        "settled": {"value": is_settled, "reasons": list(reasons)},
        "objectsRead": sample.objects_state,
        "objectSet": _object_set_id(sample.objects)
        if sample.objects_state == "collected"
        else None,
        "objectCount": len(sample.objects),
        "objectsNotRecorded": sample.objects_not_recorded,
        "consistency": _consistency(sample, provenances),
    }


def build_record(
    directory: Path,
    declared: DeclaredRelease | None = None,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """The evidence record of one ``observe`` collection.

    ``declared`` names the desired-state release to compare each sample with,
    read at the commit that sample reports, from the clone at ``root``. Without
    it, every comparison is recorded as not compared.

    Raises:
        CollectionRefused: the directory is not a collection.
    """
    collection, samples = read_collection(directory)
    provenances: dict[str, Provenance | tuple[str, ...]] = {}
    if declared is not None:
        for sample in samples:
            resolved = sample.field("resolvedRevision")
            if resolved.state != REPORTED or resolved.value in provenances:
                continue
            try:
                provenances[resolved.value] = resolve(resolved.value, declared, root)
            except ProvenanceRefused as refused:
                provenances[resolved.value] = tuple(
                    dict.fromkeys(finding.rule_id for finding in refused.findings)
                )
    states = [sample.application_state for sample in samples]
    return {
        "schema": RECORD_SCHEMA,
        "collection": collection,
        "samples": [_sample_document(sample, provenances) for sample in samples],
        "objectSets": {
            _object_set_id(sample.objects): list(sample.objects)
            for sample in samples
            if sample.objects_state == "collected"
        },
        "transitions": transitions(samples),
        "summary": {
            "samples": len(samples),
            "applicationReads": {
                state: states.count(state) for state in APPLICATION_STATES
            },
            "samplesWithEveryRequiredField": sum(
                1
                for sample in samples
                if sample.application_state == "reported"
                and all(sample.field(n).state == REPORTED for n in REQUIRED_FIELDS)
            ),
            "samplesSettled": sum(1 for sample in samples if settled(sample)[0]),
            "resolvedRevisions": sorted(
                {
                    sample.field("resolvedRevision").value
                    for sample in samples
                    if sample.field("resolvedRevision").state == REPORTED
                }
            ),
        },
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }
