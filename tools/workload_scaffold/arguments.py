"""The command's parameter surface, and how it becomes a parameter set.

One option per template parameter, named after it, with the same required-or-
defaulted split the template publishes. The parser is *generated* from
:data:`PARAMETER_OPTIONS` rather than written out beside it, so the published
table and the command line cannot disagree, and a test compares that table
against the template's own parameter set in both directions: an option this
command forgot and a parameter no option supplies are both failures rather than
something a reader has to notice.

**The permitted values in the help text come from the schema's own vocabularies**
rather than being retyped beside them. Help that has drifted from what is
accepted costs an author an attempt.

**A closed vocabulary is not enforced by ``argparse``.** Using ``choices=`` would
turn a mistyped environment into a usage error that exits before the other ten
parameters are looked at, and the whole point of the template's validator is that
an author learns *every* reason at once. So the strings arrive unchecked and the
published validator refuses them together, in the schema's own words.

The four counts are the exception. They are ``type=int``, because "not a number
at all" is a usage error rather than a statement about a workload, and their
*bounds* are still applied by the validator alongside everything else.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from inferops.domain.workload.values import (
    AcceleratorType,
    DataClassification,
    Environment,
    Profile,
    RuntimeProfile,
)
from inferops.scaffolding import (
    ACCELERATOR_COUNT_CEILING,
    MAXIMUM_REPLICAS_FLOOR,
    MINIMUM_REPLICAS_FLOOR,
    REGISTERED_MODEL_REFS,
    REPLICAS_CEILING,
    WorkloadTemplateParameters,
)

PROGRAM = "python -m tools.workload_scaffold"

#: Options this command owns that are not template parameters: where the workload
#: lands and how the result is reported. Named so the drift check can tell the
#: two groups apart without a list of exceptions inside the test.
NON_PARAMETER_OPTIONS: Final = ("into", "dry_run", "as_json")


def _vocabulary(vocabulary: type[StrEnum]) -> str:
    """The published values of one closed vocabulary, comma separated."""
    return ", ".join(member.value for member in vocabulary)


def _model_refs() -> str:
    """Every model identity the catalogue publishes, across both capabilities.

    Which of them a profile permits is the validator's answer, not the help
    text's: a help string that narrowed the set would be a second copy of a rule.
    """
    return ", ".join(
        sorted({ref for refs in REGISTERED_MODEL_REFS.values() for ref in refs})
    )


@dataclass(frozen=True)
class ParameterOption:
    """One command-line option, and the template parameter it supplies.

    ``default`` is meaningful only when ``required`` is false, and it is the
    template's own default rather than a second opinion about it.
    """

    parameter: str
    help: str
    required: bool = True
    default: str | int | None = None
    integer: bool = False

    @property
    def flag(self) -> str:
        """The option as an author types it: ``cost_center`` is ``--cost-center``."""
        return "--" + self.parameter.replace("_", "-")


#: Every template parameter, in the order the template declares it, with the help
#: an author reads. The parser below is built from this and from nothing else.
PARAMETER_OPTIONS: Final[tuple[ParameterOption, ...]] = (
    ParameterOption(
        "name",
        "workload_id: DNS-safe, 1-63 characters. A mock-llm name must end in '-mock'.",
    ),
    ParameterOption(
        "owner",
        "owner_id: DNS-safe. A workload without an owner has nobody to page.",
    ),
    ParameterOption(
        "environment",
        f"one of: {_vocabulary(Environment)}. Pinned to 'ci' for mock-llm.",
    ),
    ParameterOption("profile", f"one of: {_vocabulary(Profile)}."),
    ParameterOption(
        "runtime_profile",
        "the sizing intent, not a measured result. One of: "
        f"{_vocabulary(RuntimeProfile)}.",
    ),
    ParameterOption(
        "cpu",
        "CPU request as a Kubernetes quantity, for example '6' or '250m'.",
    ),
    ParameterOption(
        "memory",
        "memory request as a Kubernetes quantity, for example '3Gi'.",
    ),
    ParameterOption("tenant", "tenant_id: DNS-safe. Attribution."),
    ParameterOption(
        "cost_center",
        "the cost centre this workload's spend is attributed to, kebab-case.",
    ),
    ParameterOption(
        "data_classification",
        f"one of: {_vocabulary(DataClassification)}. Not defaulted on purpose.",
    ),
    ParameterOption(
        "description",
        "what this workload is: a single line of printable text, 1-500 characters. "
        "Ordinary prose, including a colon or a '#', is escaped for each format it "
        "is rendered into.",
    ),
    ParameterOption(
        "version",
        "workload_version, a semantic version. Default: %(default)s.",
        required=False,
        default="0.1.0",
    ),
    ParameterOption(
        "model_ref",
        "the catalogue identity of the model. Default: the one entry the catalogue "
        f"holds for the profile. Published today: {_model_refs()}.",
        required=False,
        default=None,
    ),
    ParameterOption(
        "accelerator_type",
        f"one of: {_vocabulary(AcceleratorType)}. Default: %(default)s, the only "
        "shape this project has executed against.",
        required=False,
        default=AcceleratorType.NONE.value,
    ),
    ParameterOption(
        "accelerator_count",
        f"0 to {ACCELERATOR_COUNT_CEILING}. Must be 0 when the type is 'none' and "
        "at least 1 otherwise. Default: %(default)s.",
        required=False,
        default=0,
        integer=True,
    ),
    ParameterOption(
        "minimum_replicas",
        f"{MINIMUM_REPLICAS_FLOOR} to {REPLICAS_CEILING}. Default: %(default)s.",
        required=False,
        default=1,
        integer=True,
    ),
    ParameterOption(
        "maximum_replicas",
        f"{MAXIMUM_REPLICAS_FLOOR} to {REPLICAS_CEILING}. Default: %(default)s.",
        required=False,
        default=1,
        integer=True,
    ),
)


def build_parser() -> argparse.ArgumentParser:
    """The command's options: one per template parameter, plus the destination."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description=(
            "Generate a conforming LLM workload from the InferOps workload "
            "template and validate what was written. Nothing is deployed, "
            "nothing is served, and nothing already on disk is overwritten."
        ),
        epilog=(
            "Exit status: 0 generated, 1 the parameter set was refused, "
            "2 a usage error, 3 the destination was refused, 4 the generated "
            "contract did not validate, 5 a write failed and was rolled back."
        ),
    )

    required = parser.add_argument_group(
        "required parameters",
        "The ones the platform refuses to guess at.",
    )
    optional = parser.add_argument_group(
        "optional parameters",
        "Each default is a decision this repository has already published.",
    )
    for option in PARAMETER_OPTIONS:
        group = required if option.required else optional
        extra: dict[str, Any] = {}
        if option.integer:
            extra["type"] = int
        if not option.required:
            extra["default"] = option.default
        group.add_argument(
            option.flag,
            dest=option.parameter,
            help=option.help,
            required=option.required,
            **extra,
        )

    output = parser.add_argument_group("destination and output")
    output.add_argument(
        "--into",
        type=Path,
        default=Path(),
        help=(
            "the directory the workload's own directory is created in. Created "
            "if it is missing. Default: the working directory."
        ),
    )
    output.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "validate and report the paths that would be written, and write "
            "nothing. The same code path a real run takes, stopped before the "
            "first directory is created."
        ),
    )
    output.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="emit the result, or the refusal, as JSON instead of aligned text.",
    )
    return parser


def parameters_from(namespace: argparse.Namespace) -> WorkloadTemplateParameters:
    """Build the template's parameter set from parsed arguments, unvalidated.

    Deliberately does no checking of its own. Everything an author can get wrong
    is refused by :func:`inferops.scaffolding.validate_parameters`, in one pass,
    in the published vocabulary — and a second opinion here would be a second
    place for the rules to live.

    It reads the namespace and nothing else. A scaffolder that reached for an
    environment variable would generate two different workloads from one command
    line.
    """
    return WorkloadTemplateParameters(
        **{
            option.parameter: getattr(namespace, option.parameter)
            for option in PARAMETER_OPTIONS
        }
    )
