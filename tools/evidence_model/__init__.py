"""The versioned claim and evidence data model, and the path out of the old one.

`v1alpha1` stores one certification level per claim. `v1alpha2` stores evidence
records, each with its own level, because that is what
[the evidence-level specification](../../docs/testing/evidence-levels.md) says a
level is a property of. This package holds the schema for the new version, a
validator, and the reader that turns a committed `v1alpha1` register into a
`v1alpha2` document without inventing anything it does not contain.

Nothing here writes to a committed register. Migrating
`docs/testing/claim-evidence-matrix.v1alpha1.json` and the consumers that read it
is `V1-S5-012-PR2`; this package exists so that the migration can be reviewed as a
transformation rather than performed as an edit.
"""

from __future__ import annotations

from .core import (
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
    LEGACY_FIELD_DESTINATIONS,
    LEGACY_REGISTER_PATH,
    SCHEMA_PATH,
    Refusal,
    load_legacy_register,
    load_schema,
    read_legacy_as_v1alpha2,
    refusals,
    validate_claim,
    validate_record,
    validate_register,
)

__all__ = [
    "CONTRACT_VERSION",
    "LEGACY_CONTRACT_VERSION",
    "LEGACY_FIELD_DESTINATIONS",
    "LEGACY_REGISTER_PATH",
    "SCHEMA_PATH",
    "Refusal",
    "load_legacy_register",
    "load_schema",
    "read_legacy_as_v1alpha2",
    "refusals",
    "validate_claim",
    "validate_record",
    "validate_register",
]
