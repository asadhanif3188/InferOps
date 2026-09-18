"""The clean-clone checklist and the ledger of one run of it.

``docs/environment/clean-clone.v1alpha1.json`` names every step of the V1 journey
from a clean clone -- host prerequisites, the default-lane checks, model
acquisition, local real inference, scaffolding, provider verification, Terraform,
Helm, real Kubernetes inference, telemetry, load, a failure experiment, and scoped
cleanup -- and ``scripts/environment/clean-clone.sh`` runs them. This package holds
the rules for what a run may record: the order steps may pass in, when a step may
be recorded as not run, what an interval may be, and what the finished ledger may
be read as saying.

See docs/environment/clean-clone.md and tests/architecture/test_clean_clone_workflow.py.
"""

from .core import (
    DESCRIPTOR_PATH,
    LEDGER_PATH,
    CleanCloneError,
    Step,
    assert_same_run,
    begin,
    checkout_problems,
    descriptor_problems,
    load_descriptor,
    load_ledger,
    note,
    pending_steps,
    record,
    steps,
    summarise,
)

__all__ = [
    "DESCRIPTOR_PATH",
    "LEDGER_PATH",
    "CleanCloneError",
    "Step",
    "assert_same_run",
    "begin",
    "checkout_problems",
    "descriptor_problems",
    "load_descriptor",
    "load_ledger",
    "note",
    "pending_steps",
    "record",
    "steps",
    "summarise",
]
