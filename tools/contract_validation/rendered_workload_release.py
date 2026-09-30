"""Validation of a RenderedWorkloadRelease document, structural only.

A RenderedWorkloadRelease is the provenance of one rendered release: the workload
and version, the digests of the WorkloadContract and EnvironmentBinding it was
rendered from, the revisions of the renderer and the platform defaults, a release
identifier, and the name and digest of the Helm values it produced. It is a
repository document, never a cluster resource. Its published schema is closed on
every object, names every input by an immutable identity, and has no field that
could carry an input's content, a timestamp, or free text, so the refusals that
matter most at this layer - a missing input, a movable revision, a digest in a
second spelling, a credential or a document pasted where a reference belongs - are
structural.

This module applies that schema and translates each failure through the same
canonical error model the WorkloadContract uses: the same codes, the same rule
identifiers, the same rule that a message never repeats a value read out of the
document. It adds no rule of its own. Rules that need a recomputation or a second
document - whether the release identifier is the one its inputs derive, whether a
source digest is the digest of the document it names, whether the contract and the
binding it names agree - are not applied here. The platform domain applies them,
in ``inferops.domain.release``, so that this module stays what a consumer holding
only the schema file can reproduce.

Offline and deterministic, like its siblings: no network, no cluster, no clock, no
randomness. Validating a release renders and deploys nothing.
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
    REPO_ROOT
    / "contracts"
    / "release"
    / "rendered-workload-release.v1alpha1.schema.json"
)

SUPPORTED_API_VERSION = "inferops.io/v1alpha1"
KIND = "RenderedWorkloadRelease"


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
    """Validate one release document. Returns findings, sorted, possibly empty."""
    return ordered(structural_findings(document))


def is_valid(document: Any) -> bool:
    """True when validate() finds nothing to refuse."""
    return not validate(document)
