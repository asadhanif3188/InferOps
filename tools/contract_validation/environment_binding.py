"""Validation of an EnvironmentBinding document, structural only.

An EnvironmentBinding carries the facts one environment supplies to a workload
release that are not the workload's intent. Its published schema is closed on
every object and has no field a WorkloadContract owns, so the refusals that matter
most at this layer - an unknown field, a workload value written where only an
environment fact belongs, a value-shaped field beside a locator - are structural.

This module applies that schema and translates each failure through the same
canonical error model the WorkloadContract uses: the same codes, the same rule
identifiers, the same rule that a message never repeats a value read out of the
document. It adds no rule of its own. Rules that need a second document - whether
a contract's environment has a binding, whether two bindings claim the same
identity or destination - have no document to read here. The platform domain in
``inferops.domain.environment`` applies them, under the rule identifiers the
contract document publishes for them; this module does not.

Offline and deterministic, like its sibling: no network, no cluster, no clock, no
randomness. Validating a binding deploys nothing.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .errors import Finding
from .workload import findings_against, ordered

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "environment" / "environment-binding.v1alpha1.schema.json"
)

SUPPORTED_API_VERSION = "inferops.io/v1alpha1"
KIND = "EnvironmentBinding"


@lru_cache(maxsize=1)
def _cached_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema


def load_schema() -> dict[str, Any]:
    """The published schema, parsed. Each caller gets its own copy."""
    return copy.deepcopy(_cached_schema())


def structural_findings(document: Any) -> list[Finding]:
    """Findings from the published schema, translated into canonical rules."""
    return findings_against(load_schema(), document)


def validate(document: Any) -> list[Finding]:
    """Validate one binding document. Returns findings, sorted, possibly empty."""
    return ordered(structural_findings(document))


def is_valid(document: Any) -> bool:
    """True when validate() finds nothing to refuse."""
    return not validate(document)
