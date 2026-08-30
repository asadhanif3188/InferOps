"""The parameters a workload template is rendered from, and what refuses them.

A template with no declared parameter set is a template whose required inputs are
whatever the files happen to mention. This module is the declared set: one frozen
object, every field named, every constraint applied before a single byte of any
template is read.

**Every constraint here is the published one.** The identifier formats, the
vocabularies, and the bounds come from
:mod:`inferops.domain.workload.values` and from the schema those values are
already compared against, so the template cannot accept a value the contract
would refuse and cannot refuse one the contract would accept. Where this module
is *stricter* than the schema it says so in the rule's own docstring, because a
tightening nobody wrote down is a tightening nobody can argue with.

**Refusals are returned together, and a refusal never repeats the value.** Both
rules are inherited rather than invented: the domain's validation pipeline
returns every error at once so an author learns what is wrong in one pass, and
the domain's errors name the field and describe the constraint without echoing
what was supplied. The field most likely to be refused for looking wrong is the
field most likely to hold something that should not be printed.

**Nothing here writes a file.** Validation runs to completion before rendering
begins, and rendering itself returns text in memory. The acceptance criterion
that invalid input must fail *before files are written* is satisfied here by
construction: this layer has no file to write.
"""

from __future__ import annotations

from dataclasses import MISSING, dataclass, fields
from enum import StrEnum
from typing import Final

from ..domain.workload.errors import InvalidValueError
from ..domain.workload.values import (
    AcceleratorType,
    ConstrainedString,
    DataClassification,
    Description,
    DnsLabel,
    Environment,
    KebabCaseName,
    Profile,
    ResourceQuantity,
    RuntimeProfile,
    SemanticVersion,
    ServingCapability,
)

# --------------------------------------------------------------------------
# What the platform catalogue actually holds
# --------------------------------------------------------------------------

#: The model identities the platform catalogue publishes today, per serving
#: capability. V1 selected exactly one real model (`ADR 0002`) and the mock
#: replays exactly one committed fixture, so both sets have one member. A
#: generated workload may not name a model the platform does not have, which is
#: why this is a closed set rather than a free string: a `modelRef` the catalogue
#: has never heard of produces a document that validates and deploys nothing.
REGISTERED_MODEL_REFS: Final[dict[ServingCapability, tuple[str, ...]]] = {
    ServingCapability.NATIVE: ("qwen3-1-7b-q8-0",),
    ServingCapability.MOCK: ("mock-fixed-fixture",),
}

#: The serving capability each profile binds to. The schema fixes this pairing;
#: repeating it here is what lets the template derive the capability rather than
#: ask for it, and a test compares the two.
SERVING_CAPABILITY_FOR: Final[dict[Profile, ServingCapability]] = {
    Profile.SYNCHRONOUS_LLM: ServingCapability.NATIVE,
    Profile.MOCK_LLM: ServingCapability.MOCK,
}

#: The suffix a mock workload's name must carry.
#:
#: This is stricter than the schema, deliberately. Rule 1 of
#: ``docs/serving/mock-and-real-boundary.md`` is that a mock artifact must be
#: identifiable as a mock *from the artifact itself, not from the directory it
#: happens to sit in*, and a workload's name travels further than any of its
#: other fields: it is what a dashboard row, a log line, and a page carry. The
#: rule is enforced as a refusal rather than as a silent rename, because a
#: scaffolder that quietly renames what it was asked for teaches nobody the rule.
MOCK_NAME_SUFFIX: Final = "-mock"

#: The environment a mock workload is pinned to. The schema fixes it; the check
#: exists here so the refusal names the parameter the author typed.
MOCK_ENVIRONMENT: Final = Environment.CI

#: Bounds the schema publishes for the replica range and the accelerator count.
MINIMUM_REPLICAS_FLOOR: Final = 0
MAXIMUM_REPLICAS_FLOOR: Final = 1
REPLICAS_CEILING: Final = 100
ACCELERATOR_COUNT_CEILING: Final = 64


# --------------------------------------------------------------------------
# Failures
# --------------------------------------------------------------------------


class ScaffoldingError(Exception):
    """Base class for every failure this package raises."""


class TemplateParameterError(ScaffoldingError):
    """One template parameter did not satisfy its published constraint.

    Carries the parameter it is about and the constraint that was not met. It
    does not carry the value, for the reason the domain's errors give: an error
    is the surface most likely to be logged, pasted into a ticket, and kept.
    """

    def __init__(self, parameter: str, reason: str) -> None:
        super().__init__(f"{parameter}: {reason}")
        self.parameter = parameter
        self.reason = reason

    def as_dict(self) -> dict[str, str]:
        """A safe, structured form: the parameter and the constraint."""
        return {"parameter": self.parameter, "reason": self.reason}


class InvalidTemplateParametersError(ScaffoldingError):
    """A parameter set was refused, with every reason it was refused for.

    Raised instead of the first :class:`TemplateParameterError` so that an author
    fixing a generated workload's inputs learns all of them in one pass rather
    than one per attempt.
    """

    def __init__(self, errors: list[TemplateParameterError]) -> None:
        super().__init__(
            f"{len(errors)} template parameter(s) were refused: "
            + "; ".join(sorted(error.parameter for error in errors))
        )
        self.errors = tuple(errors)

    def as_dicts(self) -> list[dict[str, str]]:
        """Every refusal, in a stable order, in the safe structured form."""
        return [error.as_dict() for error in sorted(self.errors, key=_error_sort_key)]


def _error_sort_key(error: TemplateParameterError) -> tuple[str, str]:
    return (error.parameter, error.reason)


# --------------------------------------------------------------------------
# The parameter set
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkloadTemplateParameters:
    """Everything a generated workload needs, and nothing a template can invent.

    Required fields are the ones the platform refuses to guess at: who owns the
    workload, where it runs, what shape of serving it wants, what it asks the
    scheduler for, and who is billed. Optional fields carry a default only where
    the default is a *decision* the repository has already published — the
    accelerator this project has executed against is none, the replica range a
    single-replica workload declares is one to one, and the model identity for a
    profile is the one entry the catalogue holds.

    Constructing this object does **not** validate it. Call
    :func:`validate_parameters`, or use :func:`inferops.scaffolding.render_workload`,
    which validates first and refuses before it reads a template.
    """

    #: workload_id. DNS-safe, and for a mock, suffixed so the label travels.
    name: str
    #: owner_id. A workload without an owner has nobody to page.
    owner: str
    #: Deployment environment, from the schema's controlled vocabulary.
    environment: str
    #: The workload profile: ``synchronous-llm`` or ``mock-llm``.
    profile: str
    #: The runtime sizing intent. What the workload asks for, not what a host gave.
    runtime_profile: str
    #: CPU request, in documented Kubernetes units.
    cpu: str
    #: Memory request, in documented Kubernetes units.
    memory: str
    #: tenant_id, for attribution.
    tenant: str
    #: The cost centre this workload's spend is attributed to.
    cost_center: str
    #: What the workload handles, from the schema's controlled vocabulary.
    data_classification: str
    #: What the workload is. Required because a generated workload that cannot say
    #: what it is gives a reviewer nothing to check the rest of the document against.
    description: str

    #: workload_version. A generated workload starts at its first version.
    version: str = "0.1.0"
    #: The catalogue identity of the model. Defaults to the one entry the
    #: catalogue holds for the profile's serving capability.
    model_ref: str | None = None
    accelerator_type: str = AcceleratorType.NONE.value
    accelerator_count: int = 0
    minimum_replicas: int = 1
    maximum_replicas: int = 1

    def resolved_model_ref(self) -> str:
        """The model identity this parameter set names, default included.

        Only meaningful once :func:`validate_parameters` has returned nothing;
        for an unrecognised profile it falls back to the supplied value so that
        the refusal is produced by the validator rather than by this accessor.
        """
        if self.model_ref is not None:
            return self.model_ref
        capability = _serving_capability_for(self.profile)
        if capability is None:
            return ""
        return REGISTERED_MODEL_REFS[capability][0]


#: The parameters an author must supply. Derived from the dataclass rather than
#: retyped beside it, so the published list and the object cannot disagree.
REQUIRED_PARAMETERS: Final[tuple[str, ...]] = tuple(
    entry.name
    for entry in fields(WorkloadTemplateParameters)
    if entry.default is MISSING and entry.default_factory is MISSING
)

#: The parameters that carry a default, and what it is. A default here is a
#: decision the repository has already published, never a convenient guess.
OPTIONAL_PARAMETERS: Final[tuple[str, ...]] = tuple(
    entry.name
    for entry in fields(WorkloadTemplateParameters)
    if entry.name not in REQUIRED_PARAMETERS
)


def _serving_capability_for(profile: str) -> ServingCapability | None:
    try:
        return SERVING_CAPABILITY_FOR[Profile(profile)]
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def _vocabulary_reason(name: str, permitted: tuple[str, ...]) -> str:
    """A refusal that prints the permitted values and never the supplied one.

    The permitted values of a closed vocabulary are safe to print because they
    come from the schema. The value that failed to be one of them is not.
    """
    return f"must be one of the published {name}: {', '.join(permitted)}"


def _check_constrained(
    errors: list[TemplateParameterError],
    parameter: str,
    value: object,
    constructor: type[ConstrainedString],
) -> bool:
    """Apply one published string constraint, reporting rather than raising."""
    if not isinstance(value, str):
        errors.append(TemplateParameterError(parameter, "must be a string"))
        return False
    try:
        constructor(value)
    except InvalidValueError as refusal:
        errors.append(TemplateParameterError(parameter, refusal.reason))
        return False
    return True


def _check_vocabulary(
    errors: list[TemplateParameterError],
    parameter: str,
    value: object,
    vocabulary: type[StrEnum],
    described_as: str,
) -> bool:
    permitted = tuple(member.value for member in vocabulary)
    if not isinstance(value, str):
        errors.append(TemplateParameterError(parameter, "must be a string"))
        return False
    try:
        vocabulary(value)
    except ValueError:
        errors.append(
            TemplateParameterError(
                parameter, _vocabulary_reason(described_as, permitted)
            )
        )
        return False
    return True


def _check_integer(
    errors: list[TemplateParameterError],
    parameter: str,
    value: object,
    floor: int,
    ceiling: int,
) -> bool:
    """An integer inside a published bound. ``bool`` is not an integer here.

    Python's ``bool`` is a subclass of ``int``, so ``True`` would otherwise pass
    every bound check and render as ``True`` in a YAML document that declared an
    integer. The schema's own validator makes the same distinction.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(TemplateParameterError(parameter, "must be an integer"))
        return False
    if value < floor or value > ceiling:
        errors.append(
            TemplateParameterError(
                parameter, f"must be between {floor} and {ceiling} inclusive"
            )
        )
        return False
    return True


def validate_parameters(
    parameters: WorkloadTemplateParameters,
) -> list[TemplateParameterError]:
    """Every reason this parameter set could not produce a valid workload.

    Returns an empty list when the set is acceptable. The order is stable: field
    checks first, in declaration order, then the cross-field rules, so two runs
    over the same input produce the same list and a reviewer can diff them.
    """
    errors: list[TemplateParameterError] = []

    _check_constrained(errors, "name", parameters.name, DnsLabel)
    _check_constrained(errors, "owner", parameters.owner, DnsLabel)
    environment_ok = _check_vocabulary(
        errors, "environment", parameters.environment, Environment, "environments"
    )
    profile_ok = _check_vocabulary(
        errors, "profile", parameters.profile, Profile, "profiles"
    )
    _check_vocabulary(
        errors,
        "runtime_profile",
        parameters.runtime_profile,
        RuntimeProfile,
        "runtime profiles",
    )
    _check_constrained(errors, "cpu", parameters.cpu, ResourceQuantity)
    _check_constrained(errors, "memory", parameters.memory, ResourceQuantity)
    _check_constrained(errors, "tenant", parameters.tenant, DnsLabel)
    _check_constrained(errors, "cost_center", parameters.cost_center, KebabCaseName)
    _check_vocabulary(
        errors,
        "data_classification",
        parameters.data_classification,
        DataClassification,
        "data classifications",
    )
    _check_constrained(errors, "description", parameters.description, Description)
    _check_constrained(errors, "version", parameters.version, SemanticVersion)
    accelerator_ok = _check_vocabulary(
        errors,
        "accelerator_type",
        parameters.accelerator_type,
        AcceleratorType,
        "accelerator types",
    )
    count_ok = _check_integer(
        errors,
        "accelerator_count",
        parameters.accelerator_count,
        0,
        ACCELERATOR_COUNT_CEILING,
    )
    minimum_ok = _check_integer(
        errors,
        "minimum_replicas",
        parameters.minimum_replicas,
        MINIMUM_REPLICAS_FLOOR,
        REPLICAS_CEILING,
    )
    maximum_ok = _check_integer(
        errors,
        "maximum_replicas",
        parameters.maximum_replicas,
        MAXIMUM_REPLICAS_FLOOR,
        REPLICAS_CEILING,
    )

    errors.extend(
        _cross_field_errors(
            parameters,
            environment_ok=environment_ok,
            profile_ok=profile_ok,
            accelerator_ok=accelerator_ok,
            count_ok=count_ok,
            minimum_ok=minimum_ok,
            maximum_ok=maximum_ok,
        )
    )
    return errors


def _cross_field_errors(
    parameters: WorkloadTemplateParameters,
    *,
    environment_ok: bool,
    profile_ok: bool,
    accelerator_ok: bool,
    count_ok: bool,
    minimum_ok: bool,
    maximum_ok: bool,
) -> list[TemplateParameterError]:
    """The rules that need two fields, applied only where both fields are sound.

    A cross-field rule read against a field that already failed its own check
    produces a second refusal about the first problem, which is noise in a list
    whose whole purpose is that an author can act on all of it at once.
    """
    errors: list[TemplateParameterError] = []

    if (
        minimum_ok
        and maximum_ok
        and parameters.minimum_replicas > parameters.maximum_replicas
    ):
        errors.append(
            TemplateParameterError(
                "minimum_replicas",
                "must not exceed maximum_replicas; a replica range no count "
                "satisfies is the schema's `replica-range-inverted` refusal",
            )
        )

    if accelerator_ok and count_ok:
        is_none = parameters.accelerator_type == AcceleratorType.NONE.value
        if is_none and parameters.accelerator_count != 0:
            errors.append(
                TemplateParameterError(
                    "accelerator_count",
                    "must be 0 when accelerator_type is 'none'",
                )
            )
        if not is_none and parameters.accelerator_count < 1:
            errors.append(
                TemplateParameterError(
                    "accelerator_count",
                    "must be at least 1 when accelerator_type names an accelerator; "
                    "a workload that asks for a device and zero of them is asking "
                    "for nothing and saying it needs something",
                )
            )

    if not profile_ok:
        return errors

    profile = Profile(parameters.profile)
    capability = SERVING_CAPABILITY_FOR[profile]
    permitted_models = REGISTERED_MODEL_REFS[capability]
    if (
        parameters.model_ref is not None
        and parameters.model_ref not in permitted_models
    ):
        errors.append(
            TemplateParameterError(
                "model_ref",
                "must be a model identity the platform catalogue publishes for "
                f"this profile: {', '.join(permitted_models)}",
            )
        )

    if profile is not Profile.MOCK_LLM:
        return errors

    if not parameters.name.endswith(MOCK_NAME_SUFFIX):
        errors.append(
            TemplateParameterError(
                "name",
                f"must end with '{MOCK_NAME_SUFFIX}' for the mock-llm profile, so "
                "that the artifact is identifiable as a mock from itself rather "
                "than from the directory it sits in",
            )
        )
    if environment_ok and parameters.environment != MOCK_ENVIRONMENT.value:
        errors.append(
            TemplateParameterError(
                "environment",
                f"must be '{MOCK_ENVIRONMENT.value}' for the mock-llm profile; the "
                "schema pins the profile to continuous integration",
            )
        )
    if accelerator_ok and parameters.accelerator_type != AcceleratorType.NONE.value:
        errors.append(
            TemplateParameterError(
                "accelerator_type",
                "must be 'none' for the mock-llm profile; a fixture replayer "
                "loads no weights and reaches no device",
            )
        )
    if count_ok and parameters.accelerator_count != 0:
        errors.append(
            TemplateParameterError(
                "accelerator_count",
                "must be 0 for the mock-llm profile; a fixture replayer loads no "
                "weights and reaches no device",
            )
        )
    return errors


def require_valid(parameters: WorkloadTemplateParameters) -> None:
    """Raise :class:`InvalidTemplateParametersError` if anything is wrong.

    The gate every rendering entry point passes through, and the reason nothing
    downstream has to re-check a value.
    """
    errors = validate_parameters(parameters)
    if errors:
        raise InvalidTemplateParametersError(errors)
