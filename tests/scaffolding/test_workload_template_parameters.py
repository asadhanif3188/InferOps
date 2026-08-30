"""What the workload template refuses, and what a refusal is allowed to say.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness.

Most of this suite is refusals, and that is the point. A scaffolder is judged by
what it will not generate: a workload with no owner, a mock that does not say it
is one, a replica range no count satisfies, or a model the platform has never
heard of. Each of those would produce a document that looks generated and is
wrong, and the wrongness is cheapest to see here.

Two properties travel with every refusal and are asserted rather than trusted:

* **every reason arrives at once**, so an author fixing a parameter set learns
  all of it in one pass rather than one problem per attempt;
* **no reason repeats the value it refused**, because a refusal is the surface
  most likely to be logged, pasted into a ticket, and kept.

Nothing here writes a file, because there is nothing in this layer that could.
That is what makes the acceptance criterion "invalid input fails before files are
written" a property of the design rather than an ordering somebody has to
preserve.
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

import pytest

from inferops.scaffolding import (
    ACCELERATOR_COUNT_CEILING,
    MOCK_ENVIRONMENT,
    MOCK_NAME_SUFFIX,
    OPTIONAL_PARAMETERS,
    REPLICAS_CEILING,
    REQUIRED_PARAMETERS,
    InvalidTemplateParametersError,
    WorkloadTemplateParameters,
    render_workload,
    validate_parameters,
)
from tests.support.workload_template_cases import (
    MINIMAL_MOCK,
    MINIMAL_REAL,
    REPRESENTATIVE_CASES,
    case_id,
)

pytestmark = pytest.mark.contract

#: The parameters an author must supply, published so a walkthrough and a command
#: can name the same set. Retyped here on purpose: a list derived from the same
#: dataclass in both places would agree with itself and with nothing else.
EXPECTED_REQUIRED_PARAMETERS = (
    "name",
    "owner",
    "environment",
    "profile",
    "runtime_profile",
    "cpu",
    "memory",
    "tenant",
    "cost_center",
    "data_classification",
    "description",
)

EXPECTED_OPTIONAL_PARAMETERS = (
    "version",
    "model_ref",
    "accelerator_type",
    "accelerator_count",
    "minimum_replicas",
    "maximum_replicas",
)


def altered(
    base: WorkloadTemplateParameters, **overrides: Any
) -> WorkloadTemplateParameters:
    """One case with named parameters replaced, including with a wrong type.

    Typed as ``Any`` on purpose. Several checks below supply a value the
    dataclass's annotation forbids — a string where an integer belongs, a
    ``bool`` where an integer belongs — because that is exactly what an author
    reading a value out of a form or a file will hand it, and refusing it is the
    validator's job rather than the annotation's. Going through this helper is
    what keeps a ``# type: ignore`` out of every one of those lines.
    """
    return replace(base, **overrides)


def reasons_for(parameters: WorkloadTemplateParameters, parameter: str) -> list[str]:
    return [
        error.reason
        for error in validate_parameters(parameters)
        if error.parameter == parameter
    ]


def refused_parameters(parameters: WorkloadTemplateParameters) -> set[str]:
    return {error.parameter for error in validate_parameters(parameters)}


# --------------------------------------------------------------------------
# The declared parameter set
# --------------------------------------------------------------------------


def test_the_required_parameters_are_the_ones_the_story_names() -> None:
    """Name, owner, environment, model and runtime profile, resources, attribution."""
    assert REQUIRED_PARAMETERS == EXPECTED_REQUIRED_PARAMETERS


def test_the_optional_parameters_are_the_ones_with_a_published_default() -> None:
    assert OPTIONAL_PARAMETERS == EXPECTED_OPTIONAL_PARAMETERS


def test_every_field_is_either_required_or_optional_and_never_both() -> None:
    declared = tuple(entry.name for entry in fields(WorkloadTemplateParameters))
    assert set(REQUIRED_PARAMETERS) | set(OPTIONAL_PARAMETERS) == set(declared)
    assert set(REQUIRED_PARAMETERS) & set(OPTIONAL_PARAMETERS) == set()


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_representative_parameter_set_is_accepted(
    parameters: WorkloadTemplateParameters,
) -> None:
    assert validate_parameters(parameters) == []


# --------------------------------------------------------------------------
# Identity, vocabulary, and format
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["Support-Assistant", "support assistant", "-support", "support-", "", "a" * 64],
    ids=[
        "uppercase",
        "space",
        "leading-hyphen",
        "trailing-hyphen",
        "empty",
        "too-long",
    ],
)
def test_a_name_that_is_not_dns_safe_is_refused(value: str) -> None:
    assert reasons_for(altered(MINIMAL_REAL, name=value), "name")


@pytest.mark.parametrize(
    "value", ["Team-Platform", "team platform", ""], ids=["case", "space", "empty"]
)
def test_an_owner_that_is_not_dns_safe_is_refused(value: str) -> None:
    assert reasons_for(altered(MINIMAL_REAL, owner=value), "owner")


@pytest.mark.parametrize(
    "parameter, value",
    [
        ("environment", "prod"),
        ("environment", "Local"),
        ("profile", "asynchronous-llm"),
        ("profile", "mock"),
        ("runtime_profile", "fast"),
        ("data_classification", "secret"),
        ("accelerator_type", "tpu"),
    ],
)
def test_a_value_outside_a_published_vocabulary_is_refused(
    parameter: str, value: str
) -> None:
    candidate = altered(MINIMAL_REAL, **{parameter: value})
    assert reasons_for(candidate, parameter)


@pytest.mark.parametrize(
    "value",
    ["6 cpu", "-1", "2GB", ""],
    ids=["units", "negative", "wrong-unit", "empty"],
)
def test_a_resource_quantity_outside_the_published_format_is_refused(
    value: str,
) -> None:
    assert reasons_for(altered(MINIMAL_REAL, cpu=value), "cpu")
    assert reasons_for(altered(MINIMAL_REAL, memory=value), "memory")


@pytest.mark.parametrize(
    "value",
    ["1.0", "v1.0.0", "latest", ""],
    ids=["two-part", "prefixed", "tag", "empty"],
)
def test_a_version_that_is_not_a_semantic_version_is_refused(value: str) -> None:
    assert reasons_for(altered(MINIMAL_REAL, version=value), "version")


def test_a_description_longer_than_the_schema_permits_is_refused() -> None:
    assert reasons_for(altered(MINIMAL_REAL, description="x" * 501), "description")


def test_an_empty_description_is_refused() -> None:
    """A generated workload that cannot say what it is gives a reviewer nothing."""
    assert reasons_for(altered(MINIMAL_REAL, description=""), "description")


# --------------------------------------------------------------------------
# Numbers, including the one Python calls an integer and nobody means
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value", [True, False], ids=["true", "false"])
def test_a_boolean_is_not_an_integer_here(value: Any) -> None:
    """`bool` subclasses `int`, and `True` would otherwise pass every bound.

    It would then render into a document that declared an integer, which the
    schema refuses — one layer later than it should.
    """
    assert reasons_for(
        altered(MINIMAL_REAL, minimum_replicas=value), "minimum_replicas"
    )
    assert reasons_for(
        altered(MINIMAL_REAL, accelerator_count=value), "accelerator_count"
    )


@pytest.mark.parametrize("value", ["1", 1.5, None], ids=["string", "float", "none"])
def test_a_replica_count_that_is_not_an_integer_is_refused(value: Any) -> None:
    assert reasons_for(
        altered(MINIMAL_REAL, maximum_replicas=value), "maximum_replicas"
    )


def test_a_replica_count_outside_the_published_bounds_is_refused() -> None:
    assert reasons_for(altered(MINIMAL_REAL, minimum_replicas=-1), "minimum_replicas")
    assert reasons_for(
        altered(MINIMAL_REAL, minimum_replicas=REPLICAS_CEILING + 1), "minimum_replicas"
    )
    assert reasons_for(altered(MINIMAL_REAL, maximum_replicas=0), "maximum_replicas")
    assert reasons_for(
        altered(MINIMAL_REAL, maximum_replicas=REPLICAS_CEILING + 1), "maximum_replicas"
    )


def test_an_inverted_replica_range_is_refused() -> None:
    """The `replica-range-inverted` rule, applied before a document exists."""
    candidate = altered(MINIMAL_REAL, minimum_replicas=4, maximum_replicas=2)
    assert reasons_for(candidate, "minimum_replicas")


def test_an_accelerator_count_above_the_published_ceiling_is_refused() -> None:
    candidate = altered(
        MINIMAL_REAL,
        accelerator_type="nvidia-gpu",
        accelerator_count=ACCELERATOR_COUNT_CEILING + 1,
    )
    assert reasons_for(candidate, "accelerator_count")


def test_an_accelerator_declaration_that_contradicts_itself_is_refused() -> None:
    """Neither half of this pair is refused by the schema; the pair is incoherent.

    A workload that names a device and asks for zero of them is asking for
    nothing and saying it needs something, and a workload that asks for none and
    then requests two would be scheduled by whichever of the two a reader
    believed.
    """
    asks_for_nothing = altered(
        MINIMAL_REAL, accelerator_type="nvidia-gpu", accelerator_count=0
    )
    assert reasons_for(asks_for_nothing, "accelerator_count")

    contradicts = altered(MINIMAL_REAL, accelerator_type="none", accelerator_count=2)
    assert reasons_for(contradicts, "accelerator_count")


# --------------------------------------------------------------------------
# The mock and real boundary, before a document exists
# --------------------------------------------------------------------------


def test_a_mock_workload_must_carry_the_mock_label_in_its_own_name() -> None:
    """Boundary rule 1: a mock is identifiable from the artifact, not the directory."""
    candidate = altered(MINIMAL_MOCK, name="support-assistant")
    reasons = reasons_for(candidate, "name")
    assert reasons
    assert MOCK_NAME_SUFFIX in reasons[0]


def test_the_mock_name_rule_does_not_apply_to_a_real_workload() -> None:
    assert reasons_for(altered(MINIMAL_REAL, name="support-assistant"), "name") == []


def test_a_mock_workload_outside_continuous_integration_is_refused() -> None:
    candidate = altered(MINIMAL_MOCK, environment="production")
    reasons = reasons_for(candidate, "environment")
    assert reasons
    assert MOCK_ENVIRONMENT.value in reasons[0]


def test_a_mock_workload_asking_for_an_accelerator_is_refused() -> None:
    """A fixture replayer loads no weights and reaches no device."""
    candidate = altered(
        MINIMAL_MOCK, accelerator_type="nvidia-gpu", accelerator_count=1
    )
    assert reasons_for(candidate, "accelerator_type")
    assert reasons_for(candidate, "accelerator_count")


@pytest.mark.parametrize(
    "case, unregistered",
    [
        (MINIMAL_REAL, "mock-fixed-fixture"),
        (MINIMAL_REAL, "gpt-4"),
        (MINIMAL_MOCK, "qwen3-1-7b-q8-0"),
    ],
    ids=["real-names-the-mock", "real-names-a-stranger", "mock-names-the-real-model"],
)
def test_a_model_the_catalogue_does_not_publish_is_refused(
    case: WorkloadTemplateParameters, unregistered: str
) -> None:
    """Including the two the platform *does* have, on the wrong profile.

    A `synchronous-llm` workload naming the mock's fixture identity is the
    failure that would put a mock label on a real serving path, and it is a
    single-word edit away from a valid document.
    """
    assert reasons_for(altered(case, model_ref=unregistered), "model_ref")


# --------------------------------------------------------------------------
# What a refusal is allowed to say, and how many arrive at once
# --------------------------------------------------------------------------


def test_every_reason_arrives_at_once() -> None:
    candidate = altered(
        MINIMAL_REAL,
        name="Support Assistant",
        owner="Team Platform",
        cpu="6 cpu",
        minimum_replicas=9,
        maximum_replicas=2,
    )
    assert refused_parameters(candidate) == {
        "name",
        "owner",
        "cpu",
        "minimum_replicas",
    }


def test_a_cross_field_rule_does_not_pile_onto_a_field_that_already_failed() -> None:
    """A second refusal about the first problem is noise in a list meant to be acted on."""
    candidate = altered(MINIMAL_REAL, minimum_replicas="two")
    assert reasons_for(candidate, "minimum_replicas") == ["must be an integer"]


def test_no_refusal_repeats_the_value_it_refused() -> None:
    """The field most likely to be refused is the field most likely to hold a secret."""
    # NOT A CREDENTIAL. `AKIAIOSFODNN7EXAMPLE` is the placeholder access key
    # identifier published in AWS's own documentation; it is not an account's key
    # and grants nothing. It appears here only so that a refusal can be asserted
    # *not* to repeat it, and it is the form
    # `.github/secret-scanning-allowlist.md` already names.
    secretish = "AKIAIOSFODNN7EXAMPLE"
    candidate = altered(
        MINIMAL_REAL,
        name=secretish,
        owner=secretish,
        cpu=secretish,
        memory=secretish,
        tenant=secretish,
        cost_center=secretish,
        version=secretish,
        environment=secretish,
        profile=secretish,
        runtime_profile=secretish,
        data_classification=secretish,
        accelerator_type=secretish,
    )
    errors = validate_parameters(candidate)
    assert errors
    for error in errors:
        assert secretish not in error.reason
        assert secretish not in str(error)
        assert secretish not in str(error.as_dict())


def test_a_refusal_may_print_a_closed_vocabulary() -> None:
    """Permitted values come from the schema and are safe to print; the input is not."""
    reasons = reasons_for(altered(MINIMAL_REAL, environment="prod"), "environment")
    assert reasons
    assert "staging" in reasons[0]
    assert "prod," not in reasons[0]


# --------------------------------------------------------------------------
# Rendering refuses before it reads a template
# --------------------------------------------------------------------------


def test_rendering_refuses_an_invalid_parameter_set_with_every_reason() -> None:
    candidate = altered(
        MINIMAL_MOCK, name="support-assistant", environment="production"
    )
    with pytest.raises(InvalidTemplateParametersError) as refusal:
        render_workload(candidate)
    refused = {error.parameter for error in refusal.value.errors}
    assert refused == {"name", "environment"}
    assert refusal.value.as_dicts() == sorted(
        refusal.value.as_dicts(),
        key=lambda entry: (entry["parameter"], entry["reason"]),
    )


def test_a_refused_render_produces_no_output_at_all() -> None:
    """There is nothing to clean up, because there was never a partial result."""
    candidate = altered(MINIMAL_REAL, cpu="6 cpu")
    with pytest.raises(InvalidTemplateParametersError):
        render_workload(candidate)


def test_the_refusal_summary_names_the_parameters_and_no_values() -> None:
    candidate = altered(MINIMAL_REAL, name="Bad Name", cpu="6 cpu")
    with pytest.raises(InvalidTemplateParametersError) as refusal:
        render_workload(candidate)
    summary = str(refusal.value)
    assert "name" in summary
    assert "cpu" in summary
    assert "Bad Name" not in summary
