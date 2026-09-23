"""The versioned claim and evidence data model, and the path out of the old one.

`v1alpha1` stores one certification level per claim. `v1alpha2` stores evidence
records, each with its own level, because that is what
[the evidence-level specification](../../docs/testing/evidence-levels.md) says a
level is a property of. This package holds the schema for the new version, a
validator, the reader that turns a committed `v1alpha1` register into a
`v1alpha2` document without inventing anything it does not contain, and -- in
`rules` -- the classification rules the schema cannot express.

Nothing here writes to a committed register. Since `V1-S5-012-PR2` the register
every consumer reads is `docs/testing/claim-evidence-matrix.v1alpha2.json`, loaded by
`load_register`; `docs/testing/claim-evidence-matrix.v1alpha1.json` is the superseded
register the migration started from, and the reader keeps it inspectable.
"""

from __future__ import annotations

from .core import (
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
    LEGACY_FIELD_DESTINATIONS,
    LEGACY_REGISTER_PATH,
    REGISTER_PATH,
    SCHEMA_PATH,
    Refusal,
    load_legacy_register,
    load_register,
    load_schema,
    read_legacy_as_v1alpha2,
    refusals,
    validate_claim,
    validate_record,
    validate_register,
)
from .rules import (
    RULES,
    Rule,
    check_claim,
    check_record,
    check_register,
    unimplemented_rules,
)

__all__ = [
    "CONTRACT_VERSION",
    "LEGACY_CONTRACT_VERSION",
    "LEGACY_FIELD_DESTINATIONS",
    "LEGACY_REGISTER_PATH",
    "REGISTER_PATH",
    "RULES",
    "SCHEMA_PATH",
    "Refusal",
    "Rule",
    "check_claim",
    "check_record",
    "check_register",
    "load_legacy_register",
    "load_register",
    "load_schema",
    "read_legacy_as_v1alpha2",
    "refusals",
    "unimplemented_rules",
    "validate_claim",
    "validate_record",
    "validate_register",
]
