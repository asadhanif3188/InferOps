"""The workload template a second engineer generates a workload from.

The outcome this package exists for is that somebody who is not on the platform
team can produce a valid, owned, attributed, correctly labelled LLM workload
**without editing platform implementation code**. What it holds is the template
for that: a contract, a quick start, and a test skeleton, in two profiles, with a
declared parameter set and a validation gate in front of it.

Start at :func:`render_workload`. The parameters it takes, what each one means,
and which are refused rather than guessed at, are in :mod:`.parameters`; the
files a render produces, and what each profile pins, are in :mod:`.template`.

**What this package is not.** It is not a command, it does not write files, and
it does not deploy anything. The command that takes a rendered workload and puts
it on a disk is ``tools.workload_scaffold``, deliberately outside the
distribution: writing the files is one thing, and validating them afterwards
needs the published JSON Schema and a YAML loader, which are a file and a
development dependency nothing that installs ``inferops`` should inherit. This
package renders text and stops. It is also not a second copy of the contract's
rules: every format, vocabulary, and bound it applies is imported from
:mod:`inferops.domain.workload.values`, which is itself compared against the
published schema by a test.

**A generated workload contains no platform code.** It declares what it wants and
cites where the procedure for it lives. That is the boundary the whole platform
rests on, and a scaffolder is the easiest place to lose it.

The published document is ``docs/scaffolding/workload-template.md``.
"""

from __future__ import annotations

from .parameters import (
    ACCELERATOR_COUNT_CEILING,
    MAXIMUM_REPLICAS_FLOOR,
    MINIMUM_REPLICAS_FLOOR,
    MOCK_ENVIRONMENT,
    MOCK_NAME_SUFFIX,
    OPTIONAL_PARAMETERS,
    REGISTERED_MODEL_REFS,
    REPLICAS_CEILING,
    REQUIRED_PARAMETERS,
    SERVING_CAPABILITY_FOR,
    InvalidTemplateParametersError,
    ScaffoldingError,
    TemplateParameterError,
    WorkloadTemplateParameters,
    require_valid,
    validate_parameters,
)
from .template import (
    PINNED_MODEL_FILE,
    PINNED_MODEL_REPOSITORY,
    PINNED_MODEL_REVISION,
    PINNED_MODEL_SHA256,
    PINNED_MODEL_SIZE_BYTES,
    PINNED_RUNTIME_IMAGE_REFERENCE,
    PLACEHOLDER_PATTERN,
    TEMPLATE_FILES,
    TEMPLATE_NAMES,
    RenderedWorkload,
    TemplateRenderingError,
    render_workload,
    substitutions,
    surviving_placeholders,
)
from .templates import TEMPLATES

__all__ = [
    "ACCELERATOR_COUNT_CEILING",
    "MAXIMUM_REPLICAS_FLOOR",
    "MINIMUM_REPLICAS_FLOOR",
    "MOCK_ENVIRONMENT",
    "MOCK_NAME_SUFFIX",
    "OPTIONAL_PARAMETERS",
    "PINNED_MODEL_FILE",
    "PINNED_MODEL_REPOSITORY",
    "PINNED_MODEL_REVISION",
    "PINNED_MODEL_SHA256",
    "PINNED_MODEL_SIZE_BYTES",
    "PINNED_RUNTIME_IMAGE_REFERENCE",
    "PLACEHOLDER_PATTERN",
    "REGISTERED_MODEL_REFS",
    "REPLICAS_CEILING",
    "REQUIRED_PARAMETERS",
    "SERVING_CAPABILITY_FOR",
    "TEMPLATES",
    "TEMPLATE_FILES",
    "TEMPLATE_NAMES",
    "InvalidTemplateParametersError",
    "RenderedWorkload",
    "ScaffoldingError",
    "TemplateParameterError",
    "TemplateRenderingError",
    "WorkloadTemplateParameters",
    "render_workload",
    "require_valid",
    "substitutions",
    "surviving_placeholders",
    "validate_parameters",
]
