"""The reusable LLM workload template, and what rendering it produces.

A generated workload is three files: the contract it declares, the quick start a
second engineer reads, and a test that reads the contract back. Nothing else is
generated, and in particular **no platform implementation code is copied into a
workload**. A workload declares; the platform serves. A scaffolder that pasted an
adapter into every generated directory would make that boundary a matter of
whichever copy was newest.

**Two profiles, two sets of files, no conditionals in the templates.** The
`mock-llm` and `synchronous-llm` profiles differ in what they pin, what they may
cite, and what an author may run against them, so each has its own contract,
quick start, and test skeleton. A single template with branches inside it would
put the mock and real boundary in the branch conditions, which is the one place a
reader does not look for it.

**Rendering produces text, not files.** :func:`render_workload` returns a mapping
of repository-relative path to content. Deciding where that lands, creating
directories, and refusing to overwrite are the scaffolding command's job in
``V1-S1-006-PR2``; this module has nothing to write and so cannot half-write it.

**Substitution is total.** Every placeholder is filled from the validated
parameter set or from a value this module pins, and :class:`string.Template`
refuses a placeholder it was given nothing for. A stale placeholder cannot
survive into generated output, because the render that would have produced one
raises instead.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from string import Template
from typing import Final

from ..domain.workload.values import Profile
from .parameters import (
    SERVING_CAPABILITY_FOR,
    ScaffoldingError,
    WorkloadTemplateParameters,
    require_valid,
)
from .templates import TEMPLATES

# --------------------------------------------------------------------------
# What a real workload is pinned to
# --------------------------------------------------------------------------

# ADR 0002 selected exactly one serving runtime image and one model revision, and
# the feasibility trial executed that pair and no other. A generated
# synchronous-llm workload carries those values rather than asking an author to
# paste a digest, and a test compares every constant below against the committed
# compatibility matrix and the committed valid fixture, so a drift between this
# template and the accepted decision is a test failure rather than something a
# reader has to notice.
#
# None of these is a credential. A digest and a content hash are public identities
# of published bytes; the whole point of writing them down is that anybody can
# check them.
PINNED_RUNTIME_IMAGE_REFERENCE: Final = (
    "ghcr.io/ggml-org/llama.cpp@sha256:"
    "100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"
)
PINNED_MODEL_REPOSITORY: Final = "Qwen/Qwen3-1.7B-GGUF"
PINNED_MODEL_REVISION: Final = "90862c4b9d2787eaed51d12237eafdfe7c5f6077"
PINNED_MODEL_FILE: Final = "Qwen3-1.7B-Q8_0.gguf"
PINNED_MODEL_SIZE_BYTES: Final = 1834426016
PINNED_MODEL_SHA256: Final = (
    "sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a"
)

#: The templates each profile is rendered from, named as
#: :mod:`inferops.scaffolding.templates` publishes them. Both profiles name three,
#: and the three produce the same output paths: two generated workloads differ in
#: what their files say, never in what their files are called.
TEMPLATE_NAMES: Final[dict[Profile, tuple[str, ...]]] = {
    Profile.MOCK_LLM: (
        "README.mock-llm.md",
        "test_workload_contract.mock-llm.py",
        "workload.mock-llm.yaml",
    ),
    Profile.SYNCHRONOUS_LLM: (
        "README.synchronous-llm.md",
        "test_workload_contract.synchronous-llm.py",
        "workload.synchronous-llm.yaml",
    ),
}

#: Output path inside a generated workload, per profile, mapped to the template
#: that produces it. Derived from the two published sets above rather than
#: retyped, so a template that changed its output path cannot disagree with this.
TEMPLATE_FILES: Final[dict[Profile, dict[str, str]]] = {
    profile: {TEMPLATES[name][0]: name for name in names}
    for profile, names in TEMPLATE_NAMES.items()
}

#: A placeholder as :class:`string.Template` writes one, used to report a
#: survivor. ``substitute`` already refuses to leave one behind; this exists so a
#: test can assert the property over rendered output rather than trusting that
#: the mechanism was used.
PLACEHOLDER_PATTERN: Final = re.compile(
    r"\$(?:\{[_a-zA-Z][_a-zA-Z0-9]*\}|[_a-zA-Z][_a-zA-Z0-9]*)"
)


class TemplateRenderingError(ScaffoldingError):
    """A template could not be rendered from the parameter set it was given.

    Carries the template it is about and the placeholder that had no value. It
    carries no value, for the reason every refusal in this package carries none.
    """

    def __init__(self, template_name: str, placeholder: str) -> None:
        super().__init__(
            f"{template_name}: no value was supplied for the placeholder "
            f"'{placeholder}'"
        )
        self.template_name = template_name
        self.placeholder = placeholder


@dataclass(frozen=True)
class RenderedWorkload:
    """One generated workload, in memory.

    ``files`` maps a path relative to the generated workload's own directory to
    that file's full text. ``directory_name`` is what that directory is called;
    where it is created is the scaffolding command's decision, not this one's.
    """

    parameters: WorkloadTemplateParameters
    directory_name: str
    files: Mapping[str, str]

    @property
    def paths(self) -> tuple[str, ...]:
        """Every generated path, in a stable order."""
        return tuple(sorted(self.files))


def substitutions(parameters: WorkloadTemplateParameters) -> dict[str, str]:
    """Every value a template may name, for a parameter set already validated.

    Includes the values an author supplied, the values derived from the profile
    — the serving capability and the catalogue model identity — and, for the
    synchronous-llm profile, the runtime and artifact pins this module holds.

    The profile itself is **not** among them. Each template is written for one
    profile and states it as a literal, so a template that had to be handed its
    own profile would be a template that could render the wrong one.
    """
    profile = Profile(parameters.profile)
    values: dict[str, str] = {
        "name": parameters.name,
        "owner": parameters.owner,
        "version": parameters.version,
        "description": parameters.description,
        "environment": parameters.environment,
        "serving_capability": SERVING_CAPABILITY_FOR[profile].value,
        "model_ref": parameters.resolved_model_ref(),
        "runtime_profile": parameters.runtime_profile,
        "cpu": parameters.cpu,
        "memory": parameters.memory,
        "accelerator_type": parameters.accelerator_type,
        "accelerator_count": str(parameters.accelerator_count),
        "minimum_replicas": str(parameters.minimum_replicas),
        "maximum_replicas": str(parameters.maximum_replicas),
        "tenant": parameters.tenant,
        "cost_center": parameters.cost_center,
        "data_classification": parameters.data_classification,
    }
    if profile is Profile.SYNCHRONOUS_LLM:
        values |= {
            "runtime_image_reference": PINNED_RUNTIME_IMAGE_REFERENCE,
            "model_repository": PINNED_MODEL_REPOSITORY,
            "model_revision": PINNED_MODEL_REVISION,
            "model_file": PINNED_MODEL_FILE,
            "model_size_bytes": str(PINNED_MODEL_SIZE_BYTES),
            "model_sha256": PINNED_MODEL_SHA256,
        }
    return values


def surviving_placeholders(text: str) -> tuple[str, ...]:
    """Every placeholder still present in rendered text, in a stable order.

    Empty for output a complete substitution produced. A test asserts that over
    every generated file; the assertion is cheap and the failure it catches — a
    generated document carrying the template's own variable names into a review —
    is the kind nobody notices until it is deployed.
    """
    return tuple(sorted(set(PLACEHOLDER_PATTERN.findall(text))))


def render_workload(parameters: WorkloadTemplateParameters) -> RenderedWorkload:
    """Render one workload from a parameter set. Nothing is written to disk.

    Refuses the whole parameter set before reading a template, with every reason
    it was refused, so an invalid name, profile, or resource declaration fails
    while there is nothing to clean up.
    """
    require_valid(parameters)
    profile = Profile(parameters.profile)
    values = substitutions(parameters)

    files: dict[str, str] = {}
    for output_path, template_name in TEMPLATE_FILES[profile].items():
        template = Template(TEMPLATES[template_name][1])
        try:
            files[output_path] = template.substitute(values)
        except KeyError as missing:
            raise TemplateRenderingError(template_name, missing.args[0]) from missing

    return RenderedWorkload(
        parameters=parameters,
        directory_name=parameters.name,
        files=files,
    )
