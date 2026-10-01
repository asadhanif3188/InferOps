"""The render boundary: validated, typed input to a renderer, and nothing else.

A renderer turns workload intent, platform defaults, and the facts of one
environment into release output. This package is everything up to that point and
nothing after it: it decides what a renderer may be given, who owns each value it
may read, and how those values are gathered into one deterministic context. It
renders nothing, writes nothing, and reads no file.

The path through it has three steps, and each takes only what the one before it
produced:

1. :func:`validate_for_render` turns a parsed WorkloadContract into a
   :class:`ValidatedWorkloadContract`, or refuses it with every finding. It applies
   the domain's semantic pipeline and the schema's profile conditions, which the
   pipeline does not.
2. :func:`build_render_context` takes that, one :class:`PlatformDefaults`, and the
   parsed EnvironmentBindings, selects the binding that serves the contract, and
   returns a :class:`RenderContext`: every value a renderer may read, read from its
   one owner as :data:`RENDER_FIELD_OWNERSHIP` names it, and the identity and
   digest of every input.
3. A :class:`Renderer` takes that context. None exists yet.

:func:`record_release` is the one supported path from a context to a
RenderedWorkloadRelease. It reads only the fields :data:`RELEASE_PROVENANCE`
classifies, and only the two context values :data:`CONTEXT_FIELD_TRUST` classifies
as public-safe identities, and refuses a release the release domain's
single-release rules refuse. The policy and its limit are in ``recording``.

:func:`prepare_render` runs the first two steps as one, for a renderer's declared
:class:`RendererSupport`, and refuses with a :class:`RenderRefused` carrying every
finding of every step under one canonical vocabulary: a category, a code, and a
rule identifier each. :func:`render_with` calls a renderer only once that has
passed, so a refusal leaves no output behind.

The ownership table and the precedence rule - that no layer overrides another -
are in ``ownership``; the refusal of an input that supplies a value it does not
own in ``conflicts``; a renderer's declared support in ``support``; the defaults in
``defaults``; the refusal vocabulary in ``errors``.

The published document is ``docs/domain/renderer-input-boundary.md``.
"""

from __future__ import annotations

from .acceptance import (
    PROFILE_CONDITIONS,
    ProfileCondition,
    ValidatedWorkloadContract,
    profile_condition_findings,
    validate_for_render,
)
from .conflicts import ownership_findings
from .defaults import (
    MILLISECONDS_CEILING,
    MILLISECONDS_FLOOR,
    OUTPUT_TOKENS_CEILING,
    OUTPUT_TOKENS_FLOOR,
    SUPPORTED_PLATFORM_DEFAULTS_VERSIONS,
    ApiDefaults,
    PlatformDefaults,
)
from .errors import (
    CAPABILITY_UNAVAILABLE,
    CONTRACT_INVALID,
    RENDER_RULES,
    VERSION_UNSUPPORTED,
    RefusalCategory,
    RenderBoundaryError,
    RenderFinding,
    RenderRefused,
    RenderRule,
    RuleOrigin,
    WorkloadNotAcceptedError,
)
from .normalization import (
    RenderContext,
    RenderField,
    RenderSources,
    build_render_context,
    prepare_render,
)
from .ownership import (
    EXCLUDED_SOURCE_FIELDS,
    OVERRIDES,
    RENDER_FIELD_OWNERSHIP,
    FieldOwnership,
    Layer,
    may_override,
    owner_of,
    ownership_of,
)
from .recording import (
    CONTEXT_FIELD_TRUST,
    RECORDED_RELEASE_VERSION,
    RELEASE_PROVENANCE,
    ContextFieldTrust,
    ProvenanceField,
    ProvenanceOrigin,
    ProvenanceTrust,
    ReleaseNotRecordedError,
    provenance_field,
    record_release,
)
from .renderer import Renderer, render_with
from .support import RendererSupport

__all__ = [
    "CAPABILITY_UNAVAILABLE",
    "CONTEXT_FIELD_TRUST",
    "CONTRACT_INVALID",
    "EXCLUDED_SOURCE_FIELDS",
    "MILLISECONDS_CEILING",
    "MILLISECONDS_FLOOR",
    "OUTPUT_TOKENS_CEILING",
    "OUTPUT_TOKENS_FLOOR",
    "OVERRIDES",
    "PROFILE_CONDITIONS",
    "RECORDED_RELEASE_VERSION",
    "RELEASE_PROVENANCE",
    "RENDER_FIELD_OWNERSHIP",
    "RENDER_RULES",
    "SUPPORTED_PLATFORM_DEFAULTS_VERSIONS",
    "VERSION_UNSUPPORTED",
    "ApiDefaults",
    "ContextFieldTrust",
    "FieldOwnership",
    "Layer",
    "PlatformDefaults",
    "ProfileCondition",
    "ProvenanceField",
    "ProvenanceOrigin",
    "ProvenanceTrust",
    "RefusalCategory",
    "ReleaseNotRecordedError",
    "RenderBoundaryError",
    "RenderContext",
    "RenderField",
    "RenderFinding",
    "RenderRefused",
    "RenderRule",
    "RenderSources",
    "Renderer",
    "RendererSupport",
    "RuleOrigin",
    "ValidatedWorkloadContract",
    "WorkloadNotAcceptedError",
    "build_render_context",
    "may_override",
    "owner_of",
    "ownership_findings",
    "ownership_of",
    "prepare_render",
    "profile_condition_findings",
    "provenance_field",
    "record_release",
    "render_with",
    "validate_for_render",
]
