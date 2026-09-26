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

**The completeness ledger** is
`docs/proof/testing/v1-s5-006-pr2-completeness.v1alpha1.json`, the record of what
`V1-S5-006-PR2` verified before the evidence could be frozen: a final state for every
finding, how each executed record identifies the repository code that ran, the
register changes it made in the same before-and-after form, the release blockers, and
the release gate they decide.

**The closure ledger** is `docs/proof/testing/v1-s5-013-pr1-closure.v1alpha1.json`,
the record of how `V1-S5-013-PR1` closed those blockers: the new records its reruns
added and every other register change, in the same before-and-after form, how each new
executed record identifies the code that ran, one disposition per blocker, and the
release gate that is current. The completeness ledger's blockers and gate stay as it
decided them, as history; the gate is read from the closure ledger, and it refuses
a closure that leaves any of those blockers without a disposition.

**The publication ledger** is
`docs/proof/testing/v1-s5-013-pr2-publication.v1alpha1.json`, the record of what
`V1-S5-013-PR2` changed to publish the case study: its register changes in the same
before-and-after form, the corrections it wrote beside dated records, and the freeze
it declares. It raises and closes no blocker; the gate stays the closure ledger's.

The four ledgers are applied in order, and undone in reverse, so the register's
history since the migration is the four of them together.

**Two digests.** `evidenceSetSha256` covers every file a record cites and nothing else,
so a change to the register's wording or to a ledger does not move it.
`evidencePackSha256` covers the same files together with the register and every
ledger of register changes, which are every input file the index is built from; it
is the digest a freeze quotes. Neither covers the index itself, which states both,
the code that builds it, or any page that reads the register.

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
    "BLOCKER_CLOSURES",
    "CLOSURE_PATH",
    "CODE_IDENTITIES",
    "CODE_REVISION_RELATIONS",
    "COMPLETENESS_PATH",
    "DISPOSITIONS",
    "FINAL_STATES",
    "FREEZE_DECISIONS",
    "INDEX_CONTRACT_VERSION",
    "INDEX_PATH",
    "LEDGER_PATH",
    "LEDGER_PATHS",
    "LEVEL_ORDER",
    "PUBLICATION_PATH",
    "TEXT_SUFFIXES",
    "apply_register_changes",
    "build_index",
    "content_sha256",
    "entry_sha256",
    "evidence_freeze",
    "evidence_set_sha256",
    "git_blob_id",
    "load_index",
    "load_ledger",
    "load_ledgers",
    "merged_identities",
    "open_blockers",
    "pack_sources",
    "recorded_date",
    "release_gate",
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

#: What V1-S5-006-PR2 verified, and the release gate it decided.
COMPLETENESS_PATH: Final = (
    REPO_ROOT
    / "docs"
    / "proof"
    / "testing"
    / "v1-s5-006-pr2-completeness.v1alpha1.json"
)

#: How V1-S5-013-PR1 closed the completeness ledger's blockers, and the current gate.
CLOSURE_PATH: Final = (
    REPO_ROOT / "docs" / "proof" / "testing" / "v1-s5-013-pr1-closure.v1alpha1.json"
)

#: What V1-S5-013-PR2 changed to publish the case study, and the freeze it declares.
PUBLICATION_PATH: Final = (
    REPO_ROOT / "docs" / "proof" / "testing" / "v1-s5-013-pr2-publication.v1alpha1.json"
)

#: Every ledger of register changes since the migration, in the order applied.
LEDGER_PATHS: Final = (LEDGER_PATH, COMPLETENESS_PATH, CLOSURE_PATH, PUBLICATION_PATH)

#: The only freeze decisions a publication ledger may state.
FREEZE_DECISIONS: Final = ("frozen", "not-frozen")

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

#: The one final state each finding ends in, after V1-S5-006-PR2 verified it.
FINAL_STATES: Final = (
    "RESOLVED",
    "NARROWED",
    "DOWNGRADED",
    "HISTORICAL-CORRECTION",
    "BLOCKER",
)

#: How an executed record identifies the repository code that ran. Only the last
#: leaves it unknown; a certified claim resting on such a record alone is a blocker.
CODE_IDENTITIES: Final = (
    "stated-revision",
    "content-pinned",
    "no-repository-code",
    "unidentified",
)

#: The three honest ways a blocker may be closed, and no fourth. A rerun is a new
#: execution at a named revision with a record of its own; a re-anchoring cites
#: committed evidence that already existed and executed what the claim needs; a
#: claim decision narrows the statement or moves the status so the claim says only
#: what identified evidence supports.
BLOCKER_CLOSURES: Final = (
    "closed-by-rerun",
    "closed-by-re-anchoring",
    "closed-by-claim-decision",
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


def load_ledgers(paths: Sequence[Path] = LEDGER_PATHS) -> list[dict[str, Any]]:
    """Every committed ledger of register changes, in the order they were applied."""
    return [load_ledger(path) for path in paths]


def load_index(path: Path = INDEX_PATH) -> dict[str, Any]:
    """The committed evidence index."""
    index: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return index


def _committed_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return data


def content_sha256(path: Path) -> str:
    """SHA-256 of a committed file's content, text normalised to LF."""
    return hashlib.sha256(_committed_bytes(path)).hexdigest()


def git_blob_id(path: Path) -> str:
    """The object name git gives the file's committed content.

    Git names a blob by the SHA-1 of a header and the content it stores, which for
    a text file is the LF form. So this is the repository object the file is: the
    value `git ls-files -s` and `git ls-tree` print for it at any commit holding
    this content, which lets a release commit be checked against the index without
    trusting a checkout.
    """
    data = _committed_bytes(path)
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def evidence_set_sha256(files: Iterable[Mapping[str, str]]) -> str:
    """One SHA-256 over every cited file, so a release can quote the whole set.

    Taken over the sorted, distinct lines ``<sha256>  <path>``, each ending in LF,
    which is the form ``sha256sum`` prints and checks.
    """
    lines = sorted({f"{item['sha256']}  {item['path']}\n" for item in files})
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


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


def _changes(
    ledgers: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Every register change, in the order applied, from one ledger or several."""
    if isinstance(ledgers, Mapping):
        ledgers = [ledgers]
    return [change for ledger in ledgers for change in ledger["registerChanges"]]


def restore_migrated_register(
    register: Mapping[str, Any],
    ledger: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The register as the `V1-S5-012-PR2` migration left it.

    Every change the ledgers name is undone, last first. Each undo first checks
    that the register holds exactly the value the ledger says it wrote, so a
    ledger that misdescribes a change raises rather than restoring something
    that never existed. Given one ledger, only its changes are undone.
    """
    restored = copy.deepcopy(dict(register))
    for change in reversed(_changes(ledger)):
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
    migrated: Mapping[str, Any],
    ledger: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The ledgers' changes applied, in order, to the migration's register."""
    changed = copy.deepcopy(dict(migrated))
    for change in _changes(ledger):
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
        "gitBlob": git_blob_id(absolute),
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


def _code_identity(
    record: Mapping[str, Any], identities: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any] | None:
    """How the completeness ledger reads the code an executed record ran, or None."""
    if not record.get("execution", {}).get("targetBehaviourExecuted"):
        return None
    reading = identities[record["recordId"]]
    return {
        "identity": reading["identity"],
        "repositoryCode": list(reading["repositoryCodeAmongThem"]),
    }


def release_gate(gate: Mapping[str, Any]) -> str:
    """``complete`` only when the ledger that decides the gate names no blocker.

    Derived, not read: a ledger that says ``complete`` beside a blocker is caught
    by comparing its stated decision with this one.
    """
    return "incomplete" if gate["blockers"] else "complete"


def evidence_freeze(closure: Mapping[str, Any], publication: Mapping[str, Any]) -> str:
    """The freeze the publication ledger declares, refused where the gate forbids it.

    A ledger may declare ``frozen`` only over a complete gate: a freeze stated beside
    an open blocker raises rather than being reported, as does a decision outside
    the two this module knows, a ledger with no freeze to read, and a publication
    ledger that raises or closes a blocker of its own, which is the closure ledger's
    to do.
    """
    if "freeze" not in publication:
        raise ValueError("the publication ledger declares no freeze")
    if publication.get("blockers") or publication.get("blockerDispositions"):
        raise ValueError("the publication ledger raises or closes a blocker")
    decision = publication["freeze"]["decision"]
    if decision not in FREEZE_DECISIONS:
        raise ValueError(f"no freeze decision {decision!r}")
    if decision == "frozen" and release_gate(closure) != "complete":
        raise ValueError("the publication ledger declares a freeze over an open gate")
    return str(decision)


def pack_sources(
    repo_root: Path = REPO_ROOT,
    register_path: Path = REGISTER_PATH,
    ledger_paths: Sequence[Path] = LEDGER_PATHS,
) -> list[dict[str, str]]:
    """The register and every ledger, each bound to its content like a cited file.

    These are the input files the index is built from besides the cited files, so
    the evidence pack digest covers them too: a change to a claim's wording, a
    status, or a ledger's decision moves it, where it cannot move the evidence-set
    digest. Each path is read under ``repo_root``, so another root reads its own
    copies rather than this checkout's.
    """
    relative = [
        path.relative_to(REPO_ROOT) if path.is_absolute() else path
        for path in (register_path, *ledger_paths)
    ]
    return [
        {
            "path": path.as_posix(),
            "sha256": content_sha256(repo_root / path),
            "gitBlob": git_blob_id(repo_root / path),
        }
        for path in relative
    ]


def open_blockers(
    completeness: Mapping[str, Any], closure: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """The blockers still standing after the closure ledger, checked against history.

    Every blocker the completeness ledger raised must end in exactly one place: a
    disposition in the closure ledger, using one of the three closure mechanisms,
    or the closure ledger's own list of blockers still open. A blocker in neither,
    in both, or disposed of twice raises, and so does one the completeness ledger
    never raised, so a closure cannot make a blocker disappear by leaving it out.
    A disposition or an open blocker must also name the claim the blocker was
    raised on, so a closure cannot close one blocker by pointing at another claim.
    """
    raised = {blocker["blockerId"]: blocker for blocker in completeness["blockers"]}
    disposed = [row["blockerId"] for row in closure["blockerDispositions"]]
    still_open = [blocker["blockerId"] for blocker in closure["blockers"]]
    for row in closure["blockerDispositions"]:
        if row["mechanism"] not in BLOCKER_CLOSURES:
            raise ValueError(
                f"{row['blockerId']}: no closure mechanism {row['mechanism']!r}"
            )
    for row in [*closure["blockerDispositions"], *closure["blockers"]]:
        blocker = raised.get(row["blockerId"])
        if blocker is not None and row.get("claimId") != blocker["claimId"]:
            raise ValueError(
                f"{row['blockerId']}: names claim {row.get('claimId')!r}, "
                f"and the blocker was raised on {blocker['claimId']!r}"
            )
    accounted = Counter(disposed + still_open)
    missing = sorted(set(raised) - set(accounted))
    twice = sorted(name for name, count in accounted.items() if count > 1)
    unknown = sorted(set(accounted) - set(raised))
    if missing or twice or unknown:
        raise ValueError(
            f"blockers without one disposition: missing {missing}, "
            f"accounted twice {twice}, never raised {unknown}"
        )
    return [dict(blocker) for blocker in closure["blockers"]]


def merged_identities(
    completeness: Mapping[str, Any], closure: Mapping[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Every record's code identity, and every claim's decision, across both ledgers.

    A record's identity is read once, by the ledger that first read it: a closure
    row for a record the completeness ledger already read raises rather than
    overriding it. A claim's decision is the latest ledger's, and the closure may
    re-decide only the claims the completeness ledger raised a blocker on; a
    closure row for any other claim raises.
    """
    first = {row["recordId"]: dict(row) for row in completeness["codeIdentity"]}
    reread = sorted({row["recordId"] for row in closure["codeIdentity"]} & set(first))
    if reread:
        raise ValueError(f"records read twice for their code identity: {reread}")
    identities = {
        **first,
        **{row["recordId"]: dict(row) for row in closure["codeIdentity"]},
    }
    blocked = {blocker["claimId"] for blocker in completeness["blockers"]}
    redecided = {row["claimId"] for row in closure["claimCodeIdentity"]}
    if redecided - blocked:
        raise ValueError(
            f"claims re-decided that no blocker was raised on: {sorted(redecided - blocked)}"
        )
    claim_identity = {
        row["claimId"]: dict(row)
        for one in (completeness, closure)
        for row in one["claimCodeIdentity"]
    }
    return identities, claim_identity


def _record_entry(
    claim: Mapping[str, Any],
    record: Mapping[str, Any],
    pointer: str,
    repo_root: Path,
    revisions: Mapping[str, Mapping[str, Any]],
    corrections: Mapping[str, list[str]],
    findings: Mapping[str, list[str]],
    identities: Mapping[str, Mapping[str, Any]],
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
        "codeIdentity": _code_identity(record, identities),
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
    completeness: Mapping[str, Any],
    closure: Mapping[str, Any],
    publication: Mapping[str, Any],
    sources: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    cited = [item for record in records for item in record["evidence"]]
    files = {item["path"] for item in cited}
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
        "executedRecordsByCodeIdentity": {
            name: sum(
                1 for record in executed if record["codeIdentity"]["identity"] == name
            )
            for name in CODE_IDENTITIES
        },
        # The completeness ledger's final states are its own, as it decided them;
        # the two BLOCKER findings carried the blockers the closure counts below.
        "findingsByFinalStateDecidedBy": completeness["releaseGate"]["storyId"],
        "findingsByFinalState": {
            name: sum(
                1
                for finding in [
                    *completeness["findingStates"],
                    *completeness["findings"],
                ]
                if finding["finalState"] == name
            )
            for name in FINAL_STATES
        },
        "completenessRegisterChanges": len(completeness["registerChanges"]),
        "closureRegisterChanges": len(closure["registerChanges"]),
        "blockersRaised": len(completeness["blockers"]),
        "blockersClosedBy": {
            name: sum(
                1 for row in closure["blockerDispositions"] if row["mechanism"] == name
            )
            for name in BLOCKER_CLOSURES
        },
        "releaseBlockers": len(open_blockers(completeness, closure)),
        "releaseGate": release_gate(closure),
        "publicationRegisterChanges": len(publication["registerChanges"]),
        "publicationCorrections": len(publication["recordCorrections"]),
        "evidenceFreeze": evidence_freeze(closure, publication),
        "evidenceSetSha256": evidence_set_sha256(cited),
        "evidencePackSha256": evidence_set_sha256([*cited, *sources]),
    }


def build_index(
    register: Mapping[str, Any] | None = None,
    ledgers: Sequence[Mapping[str, Any]] | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """The evidence index the register and the four ledgers produce today.

    The pack sources are read from the committed files, not from the arguments: the
    pack digest binds what is on disk, which is what a release ships.
    """
    register = register if register is not None else load_register()
    ledgers = ledgers if ledgers is not None else load_ledgers()
    ledger, completeness, closure, publication = ledgers
    sources = pack_sources(repo_root)
    revisions = {
        entry["recordId"]: entry for one in ledgers for entry in one["codeRevisions"]
    }
    corrections: dict[str, list[str]] = {}
    for correction in (item for one in ledgers for item in one["recordCorrections"]):
        corrections.setdefault(correction["path"], []).append(
            correction["correctionId"]
        )
    findings = _by_record(
        [finding for one in ledgers for finding in one["findings"]], "findingId"
    )
    identities, claim_identity = merged_identities(completeness, closure)
    blockers: dict[str, list[str]] = {}
    for blocker in open_blockers(completeness, closure):
        blockers.setdefault(blocker["claimId"], []).append(blocker["blockerId"])
    closed: dict[str, list[str]] = {}
    for row in closure["blockerDispositions"]:
        closed.setdefault(row["claimId"], []).append(row["blockerId"])

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
                "codeIdentity": (
                    claim_identity[claim["claimId"]]["state"]
                    if claim["claimId"] in claim_identity
                    else None
                ),
                "releaseBlockers": blockers.get(claim["claimId"], []),
                "closedBlockers": closed.get(claim["claimId"], []),
            }
        )
        for record_index, held in enumerate(claim["evidenceRecords"]):
            pointer = f"/claims/{claim_index}/evidenceRecords/{record_index}"
            records.append(
                _record_entry(
                    claim,
                    held,
                    pointer,
                    repo_root,
                    revisions,
                    corrections,
                    findings,
                    identities,
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
            "to its content by SHA-256 and to its repository object by git blob "
            "name, with how the record identifies the repository code that ran and "
            "the blockers the completeness ledger raised, how the closure ledger "
            "closed each, the release gate the closure ledger's open blockers "
            "decide, and the freeze the publication ledger declares over it. "
            "Generated by python -m tools.evidence_index --write from the register, "
            "the normalization ledger, the completeness ledger, the closure ledger, "
            "and the publication ledger; it states nothing they do not."
        ),
        "generatedBy": "python -m tools.evidence_index --write",
        "registerRef": REGISTER_PATH.relative_to(REPO_ROOT).as_posix(),
        "registerContractVersion": register["contractVersion"],
        "ledgerRef": LEDGER_PATH.relative_to(REPO_ROOT).as_posix(),
        "completenessRef": COMPLETENESS_PATH.relative_to(REPO_ROOT).as_posix(),
        "closureRef": CLOSURE_PATH.relative_to(REPO_ROOT).as_posix(),
        "publicationRef": PUBLICATION_PATH.relative_to(REPO_ROOT).as_posix(),
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
            "gitBlobs": (
                "gitBlob is the object name git gives the committed content: SHA-1 "
                "over 'blob <length>' and a NUL byte followed by the content, text in "
                "its LF form. It is what git ls-files -s prints for the file."
            ),
            "evidenceSet": (
                "evidenceSetSha256 is SHA-256 over the sorted, distinct lines "
                "'<sha256>  <path>' of every cited file, each ending in LF."
            ),
            "evidencePack": (
                "evidencePackSha256 is SHA-256 over the same lines for every cited "
                "file and every file in packSources: the register and each ledger. "
                "It covers every input file this index is built from, not the index "
                "and not the code that builds it."
            ),
        },
        "packSources": sources,
        "summary": _summary(
            claims, records, ledger, completeness, closure, publication, sources
        ),
        "claims": claims,
        "records": records,
    }


def render_index(index: Mapping[str, Any]) -> str:
    """The committed text of an index: two-space JSON, UTF-8, LF, one final newline."""
    return json.dumps(index, indent=2, ensure_ascii=False) + "\n"
