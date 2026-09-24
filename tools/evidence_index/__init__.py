"""The V1 evidence index: one entry per evidence record, bound to its files by hash.

The index is generated from
[the claim and evidence register](../../docs/testing/claim-evidence-matrix.v1alpha2.json)
and [the normalization ledger](../../docs/proof/testing/v1-s5-006-pr1-normalization.v1alpha1.json),
and it says nothing either of them does not. See
[the index's own page](../../docs/proof/v1-evidence-index.md).
"""

from __future__ import annotations

from .core import (
    CODE_REVISION_RELATIONS,
    DISPOSITIONS,
    INDEX_CONTRACT_VERSION,
    INDEX_PATH,
    LEDGER_PATH,
    LEVEL_ORDER,
    TEXT_SUFFIXES,
    apply_register_changes,
    build_index,
    content_sha256,
    entry_sha256,
    load_index,
    load_ledger,
    recorded_date,
    render_index,
    restore_migrated_register,
    states_authorisation,
)

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
