"""Q4, the derived experiment bounds, as one record.

Q4 computes four numeric bounds from two committed characterizations: S, the
maximum start-to-Ready interval of a Q2 runtime startup characterization, and G,
the gap reference of a Q3 stable caller characterization. The formulas are
constants of this module, fixed before any Q3 characterization ran:

    runtime_start_bound_ms               = S
    caller_gap_reference_ms              = G
    reversal_recovery_bound_ms           = (2 * S) + 30000
    caller_total_unavailability_bound_ms = max(2 * G, 5000)

This module reads the two committed records and returns one record that states
the four values and binds them to the path and the content digest of each source
record and of the freeze record that governed it. It contacts no cluster, and it
runs no procedure.

**A bound is stated only from a characterized source.** Each source record must
be of its schema, in its committed directory, ``CHARACTERIZED`` with each rule
held, and governed by a registered freeze record whose content the checkout
holds. The two must state the same provider, environment, release, and
qualification record. When one of these is not so, no record is stated.

**The bounds are experiment bounds.** They are not service levels, not
availability targets, and not thresholds of production operation. A later
freeze record of a reliability experiment cites them by the path and the digest
of the committed bound record.

See docs/proof/experiments/README.md, which describes the committed bound
record, and tests/domain/test_experiment_bounds.py, which gives the module each
refusal.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The schema name of a record.
RECORD_SCHEMA: Final = "inferops.io/experiment-bounds/v1alpha1"

#: The schema names of the two source records.
STARTUP_SCHEMA: Final = "inferops.io/runtime-startup-characterization/v1alpha1"
CALLER_SCHEMA: Final = "inferops.io/caller-characterization/v1alpha1"

#: Where a source record of each kind must be committed.
STARTUP_RECORD_PATTERN: Final = re.compile(
    r"docs/proof/experiments/v2-q2/runs/(q2-[1-9][0-9]?)/record\.v1alpha1\.json"
)
CALLER_RECORD_PATTERN: Final = re.compile(
    r"docs/proof/experiments/v2-q3/runs/(q3-[1-9][0-9]?)/record\.v1alpha1\.json"
)

#: The freeze records that may govern a source record. Revision 1 of Q2 governed
#: no characterization, so it is not listed.
STARTUP_FREEZE_RECORDS: Final = (
    "docs/proof/experiments/v2-q2/freeze-r2.v1alpha1.json",
)
CALLER_FREEZE_RECORDS: Final = ("docs/proof/experiments/v2-q3/freeze-r1.v1alpha1.json",)

#: Where committed bound records are found.
BOUNDS_PATTERN: Final = "docs/proof/experiments/v2-q4/bounds-r*.v1alpha1.json"

#: The two constants of the formulas, in milliseconds.
RECOVERY_ALLOWANCE_MS: Final = 30_000
UNAVAILABILITY_FLOOR_MS: Final = 5_000

#: The four bounds, in the order a record states them, with their formulas.
BOUND_NAMES: Final = (
    "runtime_start_bound_ms",
    "caller_gap_reference_ms",
    "reversal_recovery_bound_ms",
    "caller_total_unavailability_bound_ms",
)
FORMULAS: Final[Mapping[str, str]] = {
    "runtime_start_bound_ms": "S",
    "caller_gap_reference_ms": "G",
    "reversal_recovery_bound_ms": "(2 * S) + 30000",
    "caller_total_unavailability_bound_ms": "max(2 * G, 5000)",
}

#: The exit status of the command when no record is stated.
REFUSED_EXIT: Final = 5

#: Every rule that refuses, with its statement.
RULES: Final[Mapping[str, str]] = {
    "bounds-source-unreadable": (
        "Each source record is a committed file that holds one JSON object."
    ),
    "bounds-source-misplaced": (
        "Each source record is the record of its committed characterization "
        "directory, and it names that characterization."
    ),
    "bounds-source-not-characterized": (
        "Each source record is of its schema, CHARACTERIZED with each rule held, "
        "and states its bound as a whole number of milliseconds."
    ),
    "bounds-source-unfrozen": (
        "Each source record names a registered freeze record of its kind, with "
        "the content that the checkout holds."
    ),
    "bounds-environment-differs": (
        "The two source records state the same provider, environment digest, "
        "release identifier, and qualification record."
    ),
}

#: The sentence that every record carries.
BOUNDARY: Final = (
    "These are experiment bounds derived from two qualifications on one node. "
    "They are not service levels, availability targets, or production thresholds, "
    "and no figure of them is portable to another environment."
)

#: What no record establishes. Part of every record.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "A record does not establish a production SLO, an availability, or a "
    "service level.",
    "A record does not establish that a reliability experiment passes or fails. "
    "It states the bounds that a later freeze record holds a run to.",
    "A record does not establish that the formulas are right for another "
    "workload. The formulas are fixed, and the values are of one environment.",
    "A record does not establish that a source record is what its directory "
    "gives. The commands of the two characterization tools check that.",
    "A record does not establish anything about another provider, another node, "
    "another Kubernetes version, another release, or another model.",
)

_HEX64: Final = re.compile(r"[0-9a-f]{64}")


class BoundsRefused(ValueError):
    """No record is stated: one rule refused the sources."""

    def __init__(self, rule: str, reason: str) -> None:
        super().__init__(f"{rule}: {reason}")
        self.rule = rule
        self.reason = reason


def lf_digest(data: bytes) -> str:
    """The SHA-256 of a file's bytes with CRLF read as LF, as hexadecimal."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _dig(document: object, *path: str) -> Any:
    for member in path:
        if not isinstance(document, Mapping):
            return None
        document = document.get(member)
    return document


def _whole(value: object, least: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= least


def stated_bounds(s_ms: int, g_ms: int) -> dict[str, int]:
    """The four bounds of S and G, in milliseconds, by the fixed formulas."""
    return {
        "runtime_start_bound_ms": s_ms,
        "caller_gap_reference_ms": g_ms,
        "reversal_recovery_bound_ms": (2 * s_ms) + RECOVERY_ALLOWANCE_MS,
        "caller_total_unavailability_bound_ms": max(2 * g_ms, UNAVAILABILITY_FLOOR_MS),
    }


@dataclass(frozen=True)
class SourceRecord:
    """One source record, read and held to its kind."""

    path: str
    characterization_id: str
    record: Mapping[str, Any]
    content_sha256: str
    freeze_path: str
    freeze_sha256: str


def _source(
    path: str,
    root: Path,
    *,
    schema: str,
    pattern: re.Pattern[str],
    symbol: str,
    least: int,
    freeze_records: tuple[str, ...],
) -> SourceRecord:
    match = pattern.fullmatch(path)
    if match is None:
        raise BoundsRefused(
            "bounds-source-misplaced", f"{path} is not a record path of its kind"
        )
    try:
        data = (root / path).read_bytes()
        record = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise BoundsRefused(
            "bounds-source-unreadable", f"{path} is absent or is not JSON"
        ) from error
    if not isinstance(record, Mapping):
        raise BoundsRefused("bounds-source-unreadable", f"{path} is not an object")
    if _dig(record, "collection", "characterizationId") != match.group(1):
        raise BoundsRefused(
            "bounds-source-misplaced", f"{path} names another characterization"
        )
    findings = record.get("findings")
    if (
        record.get("schema") != schema
        or record.get("result") != "CHARACTERIZED"
        or not isinstance(findings, list)
        or not findings
        or any(_dig(item, "state") != "held" for item in findings)
        or _dig(record, "bound", "symbol") != symbol
        or not _whole(_dig(record, "bound", "valueMs"), least)
    ):
        raise BoundsRefused(
            "bounds-source-not-characterized",
            f"{path} is not a CHARACTERIZED record that states {symbol}",
        )
    freeze_path = _dig(record, "identities", "freezeRecord", "path")
    freeze_sha = _dig(record, "identities", "freezeRecord", "contentSha256")
    if freeze_path not in freeze_records or not (
        isinstance(freeze_sha, str) and _HEX64.fullmatch(freeze_sha)
    ):
        raise BoundsRefused(
            "bounds-source-unfrozen", f"{path} names no registered freeze record"
        )
    try:
        held = lf_digest((root / str(freeze_path)).read_bytes())
    except OSError as error:
        raise BoundsRefused(
            "bounds-source-unfrozen", f"the checkout holds no {freeze_path}"
        ) from error
    if held != freeze_sha:
        raise BoundsRefused(
            "bounds-source-unfrozen",
            f"{freeze_path} has other content than {path} names",
        )
    return SourceRecord(
        path=path,
        characterization_id=match.group(1),
        record=record,
        content_sha256=lf_digest(data),
        freeze_path=str(freeze_path),
        freeze_sha256=freeze_sha,
    )


def _environment(source: SourceRecord) -> dict[str, Any]:
    identities = source.record.get("identities")
    return {
        "provider": _dig(identities, "provider"),
        "environmentSha256": _dig(identities, "environmentSha256"),
        "releaseId": _dig(identities, "releaseId"),
        "qualification": _dig(identities, "qualification"),
    }


def _input(source: SourceRecord) -> dict[str, Any]:
    bound = source.record["bound"]
    stated: dict[str, Any] = {
        "characterizationId": source.characterization_id,
        "record": {"path": source.path, "contentSha256": source.content_sha256},
        "freezeRecord": {
            "path": source.freeze_path,
            "contentSha256": source.freeze_sha256,
        },
        "executingCommit": _dig(source.record, "identities", "executingCommit"),
        "valueMs": bound["valueMs"],
        "rule": bound["rule"],
    }
    if bound["symbol"] == "G":
        stated["percentileMeaningful"] = bound.get("percentileMeaningful")
        stated["successes"] = bound.get("successes")
    return stated


def build_record(
    startup_path: str, caller_path: str, root: Path = REPO_ROOT
) -> dict[str, Any]:
    """The bound record of one Q2 record and one Q3 record, by repository path.

    Raises:
        BoundsRefused: a rule refused one source, or the two together.
    """
    startup = _source(
        startup_path,
        root,
        schema=STARTUP_SCHEMA,
        pattern=STARTUP_RECORD_PATTERN,
        symbol="S",
        least=1,
        freeze_records=STARTUP_FREEZE_RECORDS,
    )
    caller = _source(
        caller_path,
        root,
        schema=CALLER_SCHEMA,
        pattern=CALLER_RECORD_PATTERN,
        symbol="G",
        least=0,
        freeze_records=CALLER_FREEZE_RECORDS,
    )
    environment = _environment(startup)
    if environment != _environment(caller) or None in (
        environment["provider"],
        environment["environmentSha256"],
        environment["releaseId"],
    ):
        raise BoundsRefused(
            "bounds-environment-differs",
            "the two records state another provider, environment, release, or "
            "qualification record",
        )
    values = stated_bounds(
        int(startup.record["bound"]["valueMs"]), int(caller.record["bound"]["valueMs"])
    )
    return {
        "schema": RECORD_SCHEMA,
        "boundary": BOUNDARY,
        "bounds": [
            {"name": name, "formula": FORMULAS[name], "valueMs": values[name]}
            for name in BOUND_NAMES
        ],
        "inputs": {"S": _input(startup), "G": _input(caller)},
        "environment": environment,
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def record_text(record: Mapping[str, Any]) -> str:
    """The text of a record: indented JSON with sorted members and one final LF."""
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def committed_records(root: Path = REPO_ROOT) -> list[Path]:
    """Every committed bound record."""
    return sorted(path for path in root.glob(BOUNDS_PATTERN) if path.is_file())


def check_committed(root: Path = REPO_ROOT) -> list[str]:
    """Build each committed bound record again from the sources it names."""
    findings = []
    for path in committed_records(root):
        name = path.relative_to(root).as_posix()
        try:
            stored = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
            document = json.loads(stored)
        except (OSError, UnicodeError, ValueError):
            findings.append(f"{name}: not JSON")
            continue
        startup = _dig(document, "inputs", "S", "record", "path")
        caller = _dig(document, "inputs", "G", "record", "path")
        if not isinstance(startup, str) or not isinstance(caller, str):
            findings.append(f"{name}: names no source record")
            continue
        try:
            built = record_text(build_record(startup, caller, root))
        except BoundsRefused as refused:
            findings.append(f"{name}: refused: {refused}")
            continue
        if stored != built:
            findings.append(f"{name}: is not what its source records give")
    return findings
