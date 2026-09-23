"""The `v1alpha2` schema, its validator, and the compatibility reader for `v1alpha1`.

Three things live here, and the third is the one that decides whether this version
is trustworthy.

**The schema** is data, in `docs/testing/claim-evidence-matrix.v1alpha2.schema.json`.
This module loads it and never restates a rule it already carries, because a
constraint expressed twice is a constraint that can disagree with itself.

**The validators** are thin. `validate_register` checks a whole document;
`validate_claim` and `validate_record` check one object against the subschema it
belongs to, so a fixture can be one claim rather than a whole register. All three
return refusals rather than raising, so a caller can show every problem at once.

**The compatibility reader** turns a committed `v1alpha1` register into a
`v1alpha2` document. It is deliberately dull: it moves fields, and it invents
nothing. Every claim it produces carries at most one evidence record, because
`v1alpha1` stored one level per claim and splitting that across a claim's several
evidence paths would assign each of them a level nobody ever gave it. Every record
it produces is `legacy-unmigrated`, carries no `evidenceLevel`, and keeps the
superseded `certificationLevel` verbatim under `legacyClassification`.

That last part is the whole design. The tempting transformation is to write
`evidenceLevel = certificationLevel` and call the register migrated, which would
silently restate every existing classification in a vocabulary it was not made in
-- and, for a `C3` or `C4` value, in a vocabulary where the old meaning has no
counterpart at all. There are no `C3` or `C4` values in the register today, so that
particular error is currently unreachable; the reader refuses to depend on that,
because the value it would mistranslate is exactly the value somebody would add
first.

**The migrated register** is `docs/testing/claim-evidence-matrix.v1alpha2.json`, and
since `V1-S5-012-PR2` it is the one every consumer reads. It was not produced by this
reader. Each of its records was written from a reading of the evidence files the
claim cites, and the reader's job is now the audit trail: it shows what the migration
started from, and a test compares the two so that no claim's statement, status, or
boundary changed on the way across.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from jsonschema import Draft202012Validator

__all__ = [
    "CONTRACT_VERSION",
    "LEGACY_CONTRACT_VERSION",
    "LEGACY_FIELD_DESTINATIONS",
    "LEGACY_REGISTER_PATH",
    "REGISTER_PATH",
    "SCHEMA_PATH",
    "Refusal",
    "load_legacy_register",
    "load_register",
    "load_schema",
    "read_legacy_as_v1alpha2",
    "refusals",
    "validate_claim",
    "validate_record",
    "validate_register",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The published schema for the new version.
SCHEMA_PATH: Final = (
    REPO_ROOT / "docs" / "testing" / "claim-evidence-matrix.v1alpha2.schema.json"
)

#: The superseded register, kept as the migration's starting point. Nothing reads it
#: as current, and this module never writes it.
LEGACY_REGISTER_PATH: Final = (
    REPO_ROOT / "docs" / "testing" / "claim-evidence-matrix.v1alpha1.json"
)

#: The authoritative claim and evidence register since `V1-S5-012-PR2`.
REGISTER_PATH: Final = (
    REPO_ROOT / "docs" / "testing" / "claim-evidence-matrix.v1alpha2.json"
)

CONTRACT_VERSION: Final = "inferops.io/v1alpha2"
LEGACY_CONTRACT_VERSION: Final = "inferops.io/v1alpha1"

SPECIFICATION_REF: Final = "docs/testing/evidence-levels.md"
DECISION_REF: Final = (
    "docs/architecture/decisions/ADR-0016-inferops-evidence-level-model.md"
)
SCHEMA_REF: Final = "docs/testing/claim-evidence-matrix.v1alpha2.schema.json"
MODEL_REF: Final = "docs/testing/evidence-record-model.md"

#: Where every field of a `v1alpha1` claim row ends up in `v1alpha2`. This mapping
#: is the audit: a test walks the committed register's own keys against it and
#: fails on a key that lands nowhere, which is how "no data is lost in the
#: transformation" stops being a sentence in a changelog.
LEGACY_FIELD_DESTINATIONS: Final[dict[str, tuple[str, ...]]] = {
    "claimId": ("claim.claimId", "claim.evidenceRecords[].claimId"),
    "area": ("claim.area",),
    "statement": ("claim.statement",),
    "status": ("claim.status",),
    "certificationLevel": (
        "claim.evidenceRecords[].legacyClassification.certificationLevel",
        "claim.legacyClassification.certificationLevel",
    ),
    "evidenceLabel": (
        "claim.evidenceRecords[].legacyClassification.evidenceLabel",
        "claim.legacyClassification.evidenceLabel",
    ),
    "assertsRealBehaviour": ("claim.assertsRealBehaviour",),
    "provider": (
        "claim.evidenceRecords[].legacyClassification.provider",
        "claim.legacyClassification.provider",
    ),
    "environment": (
        "claim.evidenceRecords[].legacyClassification.environment",
        "claim.legacyClassification.environment",
    ),
    "strategyClaimIds": ("claim.strategyClaimIds",),
    "implementationRefs": ("claim.implementationRefs",),
    "automatedTestRefs": ("claim.automatedTestRefs",),
    "recordedCoverageGaps": ("claim.recordedCoverageGaps",),
    "ciGateIds": ("claim.ciGateIds",),
    "evidenceRefs": ("claim.evidenceRecords[].evidenceRefs",),
    "versionsRecordedIn": (
        "claim.evidenceRecords[].versionsRecordedIn",
        "claim.legacyClassification.versionsRecordedIn",
    ),
    "limitation": ("claim.limitation",),
    "doesNotEstablish": ("claim.doesNotEstablish",),
    "readmeRefs": ("claim.readmeRefs",),
    "notClaimedReason": ("claim.notClaimedReason",),
}

#: The note every carried classification takes with it, so that a value read out of
#: the new model cannot be mistaken for one somebody assigned under the new model.
_CARRIED_NOTE: Final = (
    "Carried verbatim from the v1alpha1 register under the superseded level "
    "meanings, as the reader produces it. This reading is not re-examined against "
    "the current definitions; the migrated register is where that was done."
)


@dataclass(frozen=True)
class Refusal:
    """One thing the schema refused: where it was, and what was wrong."""

    path: str
    message: str
    rule: str


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    """The published schema, as committed."""
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def load_legacy_register(path: Path = LEGACY_REGISTER_PATH) -> dict[str, Any]:
    """The superseded `v1alpha1` register, as committed. Never written here."""
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def load_register(path: Path = REGISTER_PATH) -> dict[str, Any]:
    """The authoritative `v1alpha2` register, as committed. Never written here."""
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _validator(subschema: Mapping[str, Any] | None = None) -> Draft202012Validator:
    """A validator for the whole schema, or for one `$defs` entry inside it.

    Validating a subschema keeps a fixture down to the object it is about. A
    fixture that had to be a whole register to say something about one record
    would carry fifty lines of vocabulary nobody reads, and the line that matters
    would be the easiest one in the file to get wrong unnoticed.
    """
    schema = load_schema()
    if subschema is None:
        return Draft202012Validator(schema)
    combined = dict(subschema)
    combined["$defs"] = schema["$defs"]
    return Draft202012Validator(combined)


def _refusals(
    validator: Draft202012Validator, instance: Mapping[str, Any]
) -> list[Refusal]:
    found: Iterator[Any] = validator.iter_errors(instance)
    return [
        Refusal(
            path=error.json_path,
            message=error.message,
            rule=str(error.validator),
        )
        for error in sorted(found, key=lambda error: list(error.absolute_path))
    ]


def validate_register(document: Mapping[str, Any]) -> list[Refusal]:
    """Every way the document fails the published schema. Empty means it passes."""
    return _refusals(_validator(), document)


def validate_claim(claim: Mapping[str, Any]) -> list[Refusal]:
    """The same, for one claim object."""
    return _refusals(_validator({"$ref": "#/$defs/claim"}), claim)


def validate_record(record: Mapping[str, Any]) -> list[Refusal]:
    """The same, for one evidence record."""
    return _refusals(_validator({"$ref": "#/$defs/evidenceRecord"}), record)


def refusals(instance: Mapping[str, Any], against: str = "register") -> list[Refusal]:
    """Validate against `register`, `claim`, or `record` by name."""
    if against == "register":
        return validate_register(instance)
    if against == "claim":
        return validate_claim(instance)
    if against == "record":
        return validate_record(instance)
    raise ValueError(f"unknown subject {against!r}")


def _carried_classification(row: Mapping[str, Any]) -> dict[str, Any]:
    """The `v1alpha1` classification of one row, moved without being read."""
    carried: dict[str, Any] = {
        "sourceVersion": LEGACY_CONTRACT_VERSION,
        "certificationLevel": row["certificationLevel"],
        "evidenceLabel": row["evidenceLabel"],
        "vocabularyRef": DECISION_REF,
        "note": _CARRIED_NOTE,
    }
    if row.get("provider"):
        carried["provider"] = row["provider"]
    if row.get("environment"):
        carried["environment"] = row["environment"]
    return carried


def _legacy_record(row: Mapping[str, Any]) -> dict[str, Any]:
    """One unmigrated record for a `v1alpha1` row that cited evidence.

    One record and not one per citation. `v1alpha1` gave the claim a single level
    covering every path it named, so splitting the row would hand each cited
    record a level that nothing ever assigned to it individually.
    """
    carried = _carried_classification(row)
    record: dict[str, Any] = {
        "recordId": f"{row['claimId']}-legacy",
        "claimId": row["claimId"],
        "migrationState": "legacy-unmigrated",
        "evidenceLevel": None,
        "summary": (
            "Evidence carried from the v1alpha1 register. The execution context, "
            "workload source, versions, procedure, measurement, acceptance "
            "criteria, and results this model asks of a record are not present in "
            "the v1alpha1 row and are not reconstructed here."
        ),
        "evidenceRefs": list(row["evidenceRefs"]),
        "legacyClassification": carried,
    }
    if row.get("versionsRecordedIn"):
        record["versionsRecordedIn"] = row["versionsRecordedIn"]
    return record


def _claim(row: Mapping[str, Any]) -> dict[str, Any]:
    """One `v1alpha2` claim from one `v1alpha1` row."""
    records = [_legacy_record(row)] if row["evidenceRefs"] else []
    claim: dict[str, Any] = {
        "claimId": row["claimId"],
        "area": row["area"],
        "statement": row["statement"],
        "status": row["status"],
        "assertsRealBehaviour": row["assertsRealBehaviour"],
        "strategyClaimIds": list(row["strategyClaimIds"]),
        "implementationRefs": list(row["implementationRefs"]),
        "automatedTestRefs": list(row["automatedTestRefs"]),
        "recordedCoverageGaps": list(row["recordedCoverageGaps"]),
        "ciGateIds": list(row["ciGateIds"]),
        "evidenceRecords": records,
        "limitation": row["limitation"],
        "doesNotEstablish": row["doesNotEstablish"],
        "readmeRefs": list(row["readmeRefs"]),
        "notClaimedReason": row["notClaimedReason"],
    }
    if not records:
        # A row that named no record still carried a label, and a label saying
        # `documented-unexecuted` or `production-experience` is a statement about
        # an absence. Dropping it because there is no record to hang it on would
        # lose the only thing the row said about its evidence.
        carried = _carried_classification(row)
        if row.get("versionsRecordedIn"):
            carried["versionsRecordedIn"] = row["versionsRecordedIn"]
        claim["legacyClassification"] = carried
    return claim


def _evidence_classes(legacy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The `v1alpha1` evidence labels as `v1alpha2` classes.

    The ceiling comes across as `legacyCeiling` rather than as a rule. A ceiling is
    a constraint on what a test *layer* may certify, it is still enforced where it
    always was -- in `docs/testing/test-strategy.v1alpha1.json` -- and the
    `synthetic` ceiling in particular is the one ADR 0016 D3 records as too broad.
    Re-encoding it here as a live rule would carry that defect into the new version
    under a new name.
    """
    return [
        {
            "classId": label["labelId"],
            "meaning": label["meaning"],
            "maySupportRealBehaviour": label["maySupportRealBehaviour"],
            "reachedInV1": label["reachedInV1"],
            "legacyCeiling": label["ceiling"],
        }
        for label in legacy["evidenceLabels"]
    ]


def _evidence_levels() -> list[dict[str, Any]]:
    """The level vocabulary, pointing at the document that defines it."""
    return [
        {"levelId": level, "name": name, "definitionRef": SPECIFICATION_REF}
        for level, name in (
            ("C0", "Static Evidence"),
            ("C1", "Substituted Execution Evidence"),
            ("C2", "Runtime Evidence"),
            ("C3", "Representative Evidence"),
            ("C4", "Operational Evidence"),
        )
    ]


#: The `v1alpha1` reference fields that carry across unchanged.
_CARRIED_REFS: Final[tuple[str, ...]] = (
    "readmeRef",
    "strategyRef",
    "strategyDocumentRef",
    "matrixRef",
    "inventoryRef",
    "ciGateMatrixRef",
    "certificationRef",
    "providerContractRef",
    "costMethodRef",
    "boundariesRef",
    "contributingRef",
)


def read_legacy_as_v1alpha2(
    legacy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """A committed `v1alpha1` register, read as a `v1alpha2` document.

    This is a reader, not a migration. It produces a document in memory; nothing
    is written, no committed file changes, and no claim gains or loses a level.
    What it demonstrates is that the path from the old shape to the new one is a
    transformation somebody can review rather than an edit somebody has to trust.
    """
    source = dict(legacy) if legacy is not None else load_legacy_register()

    document: dict[str, Any] = {
        "$id": "https://inferops.io/testing/claim-evidence-matrix.v1alpha2.json",
        "contractVersion": CONTRACT_VERSION,
        "supersedes": LEGACY_CONTRACT_VERSION,
        "title": "V1 claim and evidence matrix, v1alpha2",
        "description": (
            "Every claim InferOps intends to publish about V1, bound to the "
            "evidence records that support it. Read from the committed v1alpha1 "
            "register: every record here is legacy-unmigrated, carries no evidence "
            "level, and keeps its superseded classification verbatim."
        ),
        "schemaRef": SCHEMA_REF,
        "documentRef": source["documentRef"],
        "modelRef": MODEL_REF,
        "specificationRef": SPECIFICATION_REF,
        "decisionRef": DECISION_REF,
        "evidenceRoot": source["evidenceRoot"],
        "templateRoot": source["templateRoot"],
        "claimStatuses": [dict(status) for status in source["claimStatuses"]],
        "evidenceLevels": _evidence_levels(),
        "evidenceClasses": _evidence_classes(source),
        "areas": [dict(area) for area in source["areas"]],
        "claims": [_claim(row) for row in source["claims"]],
    }
    for field in _CARRIED_REFS:
        if field in source:
            document[field] = source[field]
    for field in ("nonClaimSurfaces", "prohibitions"):
        if field in source:
            rows: Sequence[Mapping[str, Any]] = source[field]
            document[field] = [dict(row) for row in rows]
    if "limitations" in source:
        # A list of sentences in v1alpha1, and it stays one. The register's own
        # limitations are about the register, not about any claim in it.
        document["limitations"] = list(source["limitations"])
    return document
