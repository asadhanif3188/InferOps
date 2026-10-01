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

The ownership table and the precedence rule - that no layer overrides another -
are in ``ownership``; the defaults in ``defaults``; the refusal in ``errors``.

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
from .defaults import (
    MILLISECONDS_CEILING,
    MILLISECONDS_FLOOR,
    OUTPUT_TOKENS_CEILING,
    OUTPUT_TOKENS_FLOOR,
    SUPPORTED_PLATFORM_DEFAULTS_VERSIONS,
    ApiDefaults,
    PlatformDefaults,
)
from .errors import RenderBoundaryError, WorkloadNotAcceptedError
from .normalization import (
    RenderContext,
    RenderField,
    RenderSources,
    build_render_context,
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
from .renderer import Renderer

__all__ = [
    "EXCLUDED_SOURCE_FIELDS",
    "MILLISECONDS_CEILING",
    "MILLISECONDS_FLOOR",
    "OUTPUT_TOKENS_CEILING",
    "OUTPUT_TOKENS_FLOOR",
    "OVERRIDES",
    "PROFILE_CONDITIONS",
    "RENDER_FIELD_OWNERSHIP",
    "SUPPORTED_PLATFORM_DEFAULTS_VERSIONS",
    "ApiDefaults",
    "FieldOwnership",
    "Layer",
    "PlatformDefaults",
    "ProfileCondition",
    "RenderBoundaryError",
    "RenderContext",
    "RenderField",
    "RenderSources",
    "Renderer",
    "ValidatedWorkloadContract",
    "WorkloadNotAcceptedError",
    "build_render_context",
    "may_override",
    "owner_of",
    "ownership_of",
    "profile_condition_findings",
    "validate_for_render",
]
