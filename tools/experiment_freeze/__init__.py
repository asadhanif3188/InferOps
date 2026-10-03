"""Experiment freeze records, checked for every required field and for edits after merge.

A freeze record fixes an experiment family before its first result-bearing run. This
package checks that every committed record answers every field the freeze procedure
requires, that no committed record differs from the content pinned when it was added,
and that a later revision names the one it supersedes and classifies every pinned
input that moved. It also lists the pinned inputs whose content differs from a
record's pins - and, for a record with a material scope, every file in that scope it
does not pin - for the run that must refuse to start until a revision classifies them.

See docs/proof/experiments/README.md, which describes the record, and
tests/testing/test_experiment_freeze.py, which checks every committed record and
plants each defect the check refuses.
"""

from .core import (
    ALWAYS_ANSWERED,
    API_VERSION,
    CHANGE_KINDS,
    EVIDENCE_LEVELS,
    FREEZE_FIELDS,
    FROZEN_RECORDS,
    KIND,
    PENDING_ALLOWED,
    RECORDS_DIR,
    REGISTRY_PATH,
    REPO_ROOT,
    RULES,
    STATUSES,
    UNSCOPED_RECORDS,
    Finding,
    FreezeField,
    InputChange,
    PendingAllowance,
    Rule,
    changed_inputs,
    check_record,
    check_repository,
    content_digest,
    import_closure,
    load_registry,
    material_files,
    record_paths,
)

__all__ = [
    "ALWAYS_ANSWERED",
    "API_VERSION",
    "CHANGE_KINDS",
    "EVIDENCE_LEVELS",
    "FREEZE_FIELDS",
    "FROZEN_RECORDS",
    "KIND",
    "PENDING_ALLOWED",
    "RECORDS_DIR",
    "REGISTRY_PATH",
    "REPO_ROOT",
    "RULES",
    "STATUSES",
    "UNSCOPED_RECORDS",
    "Finding",
    "FreezeField",
    "InputChange",
    "PendingAllowance",
    "Rule",
    "changed_inputs",
    "check_record",
    "check_repository",
    "content_digest",
    "import_closure",
    "load_registry",
    "material_files",
    "record_paths",
]
