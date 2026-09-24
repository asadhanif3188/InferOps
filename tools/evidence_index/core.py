"""The V1 evidence index, and the normalization ledger it is built beside.

The claim and evidence register is authoritative, and it is organised by claim. A
release needs the other view as well: one entry per evidence record, saying what ran,
what was substituted, where, at which revision, with which immutable identifiers, and
which committed files hold the evidence -- each bound to its content by a hash, so a
file that changes after the index was written is caught rather than trusted. This
module builds that view. It owns no claim state: every value in an index entry is
either copied from the register, read mechanically from a cited file, or taken from
the normalization ledger, and the ledger is the only place a human judgement enters.

**The normalization ledger** is
`docs/proof/testing/v1-s5-006-pr1-normalization.v1alpha1.json`. It is the record of
what `V1-S5-006-PR1` did to the register after the `V1-S5-012-PR2` migration: every
field it changed, with the value before and after, every record it added, whole, and
the reason for each. It also carries the corrections to historical records that were
made beside them rather than inside them, and the reading of each executed record's
code revision. Two functions make the ledger checkable in both directions:
`restore_migrated_register` takes the current register back to what the migration
produced, which is what the migration suite still compares with `v1alpha1`, and
`apply_register_changes` goes forward again. A change the ledger does not name
cannot survive both.

**Content hashes** are SHA-256 over the committed content. A text file is hashed with
CRLF normalised to LF, because the repository stores text with LF and a Windows
checkout rewrites it; hashing the checkout's bytes would give two answers for one
committed file. Every other file is hashed as it is.

Nothing here contacts a cluster, a runtime, a model, or the network.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from tools.evidence_model import REGISTER_PATH, load_register

__all__ = [
    "CODE_REVISION_RELATIONS",
    "DISPOSITIONS",
    "INDEX_CONTRACT_VERSION",
    "INDEX_PATH",
    "LEDGER_PATH",
    "LEVEL_ORDER",
    "TEXT_SUFFIXES",
    "apply_register_changes",
    "build_index",
    "content_sha256",
    "entry_sha256",
    "load_index",
    "load_ledger",
    "recorded_date",
    "render_index",
    "restore_migrated_register",
    "states_authorisation",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The generated index. Written only by ``--write``.
INDEX_PATH: Final = REPO_ROOT / "docs" / "proof" / "v1-evidence-index.v1alpha1.json"

#: What V1-S5-006-PR1 changed in the register, and why.
LEDGER_PATH: Final = (
    REPO_ROOT
    / "docs"
    / "proof"
    / "testing"
    / "v1-s5-006-pr1-normalization.v1alpha1.json"
)

INDEX_CONTRACT_VERSION: Final = "inferops.io/v1alpha1"

#: The specification's numbering. It is an order of closeness to the intended
#: operating context, not a ranking of quality.
LEVEL_ORDER: Final = ("C0", "C1", "C2", "C3", "C4")

#: The five answers a finding may be given. Exactly one per finding.
DISPOSITIONS: Final = (
    "corrected-authoritative-metadata",
    "additive-historical-correction",
    "retained-with-narrower-claim-or-limitation",
    "downgraded",
    "carried-as-release-blocker",
)

#: How a commit a record names relates to the code that actually ran. Only the
#: first says the record names the revision it ran, and even that is the record's
#: word rather than something this index re-derives.
CODE_REVISION_RELATIONS: Final = (
    "stated-revision",
    "stated-revision-with-uncommitted-changes",
    "base-revision",
    "commit-created-after-the-run",
    "branch-name-only",
)

#: Files the repository stores as text. Everything else is hashed byte for byte.
TEXT_SUFFIXES: Final = frozenset(
    {".md", ".json", ".jsonl", ".txt", ".yaml", ".yml", ".csv"}
)

_DATE_LINE: Final = re.compile(
    r"(?m)^\**\s*(Date(?: [a-z]+)?)\s*\**\s*:\s*\**\s*(\d{4}-\d{2}-\d{2})"
)
_DATE_ROW: Final = re.compile(r"(?m)^\|\s*(Date)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|")
_AUTHORISATION_HEADING: Final = re.compile(r"(?mi)^#+ .*authori[sz]")


# ------------------------------------------------------------------- reading


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    """The committed normalization ledger."""
    ledger: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return ledger


def load_index(path: Path = INDEX_PATH) -> dict[str, Any]:
    """The committed evidence index."""
    index: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return index


def content_sha256(path: Path) -> str:
    """SHA-256 of a committed file's content, text normalised to LF."""
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def entry_sha256(value: Any) -> str:
    """SHA-256 of a register entry in a canonical JSON form.

    Keys sorted, no insignificant whitespace, UTF-8. The index stores this beside
    every record so an entry edited in the register after the index was written
    no longer matches it.
    """
    canonical = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def recorded_date(text: str) -> dict[str, str] | None:
    """The first date a Markdown record gives for itself, with the words it used.

    Records say ``Date:``, ``Date captured:``, ``Date produced:``, ``Date
    registered:``, and more, and those are not the same fact: a record produced
    on one day may describe a run on another. So the label is kept beside the
    value and nothing is normalised. A record that states no date gets ``None``;
    a date is never taken from a filename or from git.
    """
    found = [
        match for pattern in (_DATE_LINE, _DATE_ROW) for match in pattern.finditer(text)
    ]
    if not found:
        return None
    first = min(found, key=lambda match: match.start())
    return {"label": first.group(1), "value": first.group(2)}


def states_authorisation(text: str) -> bool:
    """Whether a Markdown record has a section headed for its authorisation.

    A heading, not a mention: the migration's lower-bound count accepts any use of
    the word, and this is the stricter question of whether the record gives the
    subject its own section.
    """
    return bool(_AUTHORISATION_HEADING.search(text))


# ----------------------------------------------------------- register changes


def _claim(register: Mapping[str, Any], claim_id: str) -> dict[str, Any]:
    for row in register["claims"]:
        if row["claimId"] == claim_id:
            found: dict[str, Any] = row
            return found
    raise KeyError(f"no claim {claim_id}")


def _record(claim: Mapping[str, Any], record_id: str) -> dict[str, Any]:
    for held in claim["evidenceRecords"]:
        if held["recordId"] == record_id:
            found: dict[str, Any] = held
            return found
    raise KeyError(f"no record {record_id} under {claim['claimId']}")


def _target(register: dict[str, Any], change: Mapping[str, Any]) -> dict[str, Any]:
    if change["operation"] == "set-register-field":
        return register
    claim = _claim(register, change["claimId"])
    if change["operation"] == "set-record-field":
        return _record(claim, change["recordId"])
    return claim


def restore_migrated_register(
    register: Mapping[str, Any], ledger: Mapping[str, Any]
) -> dict[str, Any]:
    """The register as the `V1-S5-012-PR2` migration left it.

    Every change the ledger names is undone, last first. Each undo first checks
    that the register holds exactly the value the ledger says it wrote, so a
    ledger that misdescribes a change raises rather than restoring something
    that never existed.
    """
    restored = copy.deepcopy(dict(register))
    for change in reversed(ledger["registerChanges"]):
        if change["operation"] == "add-record":
            claim = _claim(restored, change["claimId"])
            held = _record(claim, change["record"]["recordId"])
            if held != change["record"]:
                raise ValueError(f"{change['changeId']}: the added record differs")
            claim["evidenceRecords"].remove(held)
            continue
        target = _target(restored, change)
        field = change["field"]
        if target.get(field) != change["after"]:
            raise ValueError(f"{change['changeId']}: {field} is not what was written")
        if change["before"] is None:
            del target[field]
        else:
            target[field] = copy.deepcopy(change["before"])
    return restored


def apply_register_changes(
    migrated: Mapping[str, Any], ledger: Mapping[str, Any]
) -> dict[str, Any]:
    """The ledger's changes applied, in order, to the migration's register."""
    changed = copy.deepcopy(dict(migrated))
    for change in ledger["registerChanges"]:
        if change["operation"] == "add-record":
            claim = _claim(changed, change["claimId"])
            claim["evidenceRecords"].insert(
                change["position"], copy.deepcopy(change["record"])
            )
            continue
        target = _target(changed, change)
        field = change["field"]
        if target.get(field) != change["before"]:
            raise ValueError(f"{change['changeId']}: {field} is not what was read")
        target[field] = copy.deepcopy(change["after"])
    return changed


# -------------------------------------------------------------------- the index


def _levels(claim: Mapping[str, Any]) -> list[str]:
    held = {record.get("evidenceLevel") for record in claim["evidenceRecords"]}
    return [level for level in LEVEL_ORDER if level in held]


def _identifiers(record: Mapping[str, Any]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for version in record.get("versions", []):
        grouped.setdefault(version["kind"], []).append(
            {"component": version["component"], "value": version["value"]}
        )
    return {kind: grouped[kind] for kind in sorted(grouped)}


def _by_record(entries: Iterable[Mapping[str, Any]], key: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for entry in entries:
        for record_id in entry.get("recordIds", []):
            out.setdefault(record_id, []).append(entry[key])
    return out


def _evidence_file(
    path: str, repo_root: Path, corrections: Mapping[str, list[str]]
) -> dict[str, Any]:
    absolute = repo_root / path
    text = absolute.read_text(encoding="utf-8") if absolute.suffix == ".md" else ""
    return {
        "path": path,
        "sha256": content_sha256(absolute),
        "recordedDate": recorded_date(text) if text else None,
        "authorisationSection": states_authorisation(text) if text else None,
        "corrections": sorted(corrections.get(path, [])),
    }


def _code_revision(
    record: Mapping[str, Any], revisions: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any] | None:
    """The ledger's reading of the revision an executed record ran, or None.

    Only records that executed their target behaviour are read. A `C0` record's
    subject is committed files, which the content hashes below already bind.
    """
    if not record.get("execution", {}).get("targetBehaviourExecuted"):
        return None
    reading = revisions[record["recordId"]]
    entries = [
        {"value": entry["value"], "relation": entry["relation"], "path": entry["path"]}
        for entry in reading["entries"]
    ]
    return {
        "entries": entries,
        "statedRevision": any(
            entry["relation"] == "stated-revision" for entry in entries
        ),
        "note": reading["note"],
    }


def _record_entry(
    claim: Mapping[str, Any],
    record: Mapping[str, Any],
    pointer: str,
    repo_root: Path,
    revisions: Mapping[str, Mapping[str, Any]],
    corrections: Mapping[str, list[str]],
    findings: Mapping[str, list[str]],
) -> dict[str, Any]:
    execution = record.get("execution", {})
    workload = record.get("workload", {})
    environment = record.get("environment", {})
    procedure = record.get("procedure", {})
    measurement = record.get("measurement") or {}
    representativeness = workload.get("representativeness")
    return {
        "recordId": record["recordId"],
        "claimId": claim["claimId"],
        "claimStatus": claim["status"],
        "evidenceLevel": record.get("evidenceLevel"),
        "migrationState": record["migrationState"],
        "registerPointer": pointer,
        "registerEntrySha256": entry_sha256(record),
        "summary": record["summary"],
        "execution": {
            "targetBehaviourExecuted": execution.get("targetBehaviourExecuted"),
            "executedComponents": [
                {"componentId": item["componentId"], "role": item["role"]}
                for item in execution.get("executedComponents", [])
            ],
            "substitutions": [
                {
                    "componentId": item["componentId"],
                    "role": item["role"],
                    "substituteKind": item["substituteKind"],
                    "claimMaterial": item["claimMaterial"],
                }
                for item in execution.get("substitutions", [])
            ],
        },
        "workload": {
            "source": workload.get("source"),
            "representativenessDeclared": (
                representativeness["declared"] if representativeness else None
            ),
            "shape": workload.get("shape"),
        },
        "environment": {
            "environmentId": environment.get("environmentId"),
            "provider": environment.get("provider"),
            "hardwareClass": environment.get("hardwareClass"),
            "region": environment.get("region"),
        },
        "identifiers": _identifiers(record),
        "versionsRecordedIn": record.get("versionsRecordedIn"),
        "codeRevision": _code_revision(record, revisions),
        "procedure": {
            "commands": list(procedure.get("commands", [])),
            "workflowRef": procedure.get("workflowRef"),
            "scriptRefs": list(procedure.get("scriptRefs", [])),
        },
        "acceptanceCriteria": [
            {
                "criterionId": item["criterionId"],
                "declaredBefore": item["declaredBefore"],
                "outcome": item["outcome"],
            }
            for item in record.get("acceptanceCriteria", [])
        ],
        "observationPeriod": measurement.get("observationPeriod"),
        "results": [
            {"resultId": item["resultId"], "statement": item["statement"]}
            for item in record.get("results", [])
        ],
        "limitations": list(record.get("limitations", [])),
        "doesNotEstablish": list(record.get("doesNotEstablish", [])),
        "evidence": [
            _evidence_file(path, repo_root, corrections)
            for path in record["evidenceRefs"]
        ],
        "findings": sorted(findings.get(record["recordId"], [])),
    }


def _summary(
    claims: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    files = {item["path"] for record in records for item in record["evidence"]}
    executed = [record for record in records if record["codeRevision"] is not None]
    substituted = [record for record in records if record["execution"]["substitutions"]]
    return {
        "claims": len(claims),
        "claimsByStatus": dict(
            sorted(Counter(row["status"] for row in claims).items())
        ),
        "records": len(records),
        "recordsByLevel": {
            level: sum(1 for record in records if record["evidenceLevel"] == level)
            for level in LEVEL_ORDER
        },
        "recordsByEnvironment": dict(
            sorted(
                Counter(
                    record["environment"]["environmentId"] for record in records
                ).items()
            )
        ),
        "recordsByWorkloadSource": dict(
            sorted(Counter(record["workload"]["source"] for record in records).items())
        ),
        "recordsWithASubstitution": len(substituted),
        "recordsWithAClaimMaterialSubstitution": sum(
            1
            for record in substituted
            if any(
                item["claimMaterial"] for item in record["execution"]["substitutions"]
            )
        ),
        "executedRecords": len(executed),
        "executedRecordsNamingTheRevisionThatRan": sum(
            1 for record in executed if record["codeRevision"]["statedRevision"]
        ),
        "evidenceFiles": len(files),
        "findingsByDisposition": {
            name: sum(
                1 for finding in ledger["findings"] if finding["disposition"] == name
            )
            for name in DISPOSITIONS
        },
        "historicalCorrections": len(ledger["recordCorrections"]),
        "registerChanges": len(ledger["registerChanges"]),
    }


def build_index(
    register: Mapping[str, Any] | None = None,
    ledger: Mapping[str, Any] | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """The evidence index the register and the ledger produce today."""
    register = register if register is not None else load_register()
    ledger = ledger if ledger is not None else load_ledger()
    revisions = {entry["recordId"]: entry for entry in ledger["codeRevisions"]}
    corrections: dict[str, list[str]] = {}
    for correction in ledger["recordCorrections"]:
        corrections.setdefault(correction["path"], []).append(
            correction["correctionId"]
        )
    findings = _by_record(ledger["findings"], "findingId")

    claims: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for claim_index, claim in enumerate(register["claims"]):
        claims.append(
            {
                "claimId": claim["claimId"],
                "area": claim["area"],
                "status": claim["status"],
                "assertsRealBehaviour": claim["assertsRealBehaviour"],
                "statement": claim["statement"],
                "limitation": claim["limitation"],
                "doesNotEstablish": claim["doesNotEstablish"],
                "claimMaterialComponents": claim.get("claimMaterialComponents"),
                "levels": _levels(claim),
                "recordIds": [held["recordId"] for held in claim["evidenceRecords"]],
            }
        )
        for record_index, held in enumerate(claim["evidenceRecords"]):
            pointer = f"/claims/{claim_index}/evidenceRecords/{record_index}"
            records.append(
                _record_entry(
                    claim, held, pointer, repo_root, revisions, corrections, findings
                )
            )

    return {
        "$id": "https://inferops.io/proof/v1-evidence-index.v1alpha1.json",
        "contractVersion": INDEX_CONTRACT_VERSION,
        "title": "V1 evidence index",
        "description": (
            "One entry per evidence record in the claim and evidence register, with "
            "what executed, what was substituted, the workload source, the "
            "environment, the immutable identifiers the record pins, the code "
            "revision it names and how that revision relates to what ran, the "
            "procedure, the results, the limitations, and every cited file bound "
            "to its content by SHA-256. Generated by python -m tools.evidence_index "
            "--write from the register and the normalization ledger; it states "
            "nothing either of them does not."
        ),
        "generatedBy": "python -m tools.evidence_index --write",
        "registerRef": REGISTER_PATH.relative_to(REPO_ROOT).as_posix(),
        "registerContractVersion": register["contractVersion"],
        "ledgerRef": LEDGER_PATH.relative_to(REPO_ROOT).as_posix(),
        "documentRef": "docs/proof/v1-evidence-index.md",
        "specificationRef": "docs/testing/evidence-levels.md",
        "hashing": {
            "algorithm": "sha256",
            "textFiles": (
                "Files with a suffix in "
                + ", ".join(sorted(TEXT_SUFFIXES))
                + " are hashed with CRLF normalised to LF, which is how the "
                "repository stores them."
            ),
            "registerEntries": (
                "registerEntrySha256 is taken over the record's JSON with keys "
                "sorted, no insignificant whitespace, UTF-8."
            ),
        },
        "summary": _summary(claims, records, ledger),
        "claims": claims,
        "records": records,
    }


def render_index(index: Mapping[str, Any]) -> str:
    """The committed text of an index: two-space JSON, UTF-8, LF, one final newline."""
    return json.dumps(index, indent=2, ensure_ascii=False) + "\n"
