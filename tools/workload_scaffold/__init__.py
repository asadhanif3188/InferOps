"""The command that generates a workload from the template and validates it.

The outcome behind it is that a second engineer produces a valid, owned,
attributed, correctly labelled LLM workload **without editing platform
implementation code**. :mod:`inferops.scaffolding` holds the template and turns a
parameter set into text; this package is what puts that text on a disk, refuses
to overwrite anything, undoes a write that failed partway, and holds the result
to the published contract by reading it back.

Start at :mod:`.generate`, or run the command:

    uv run --locked python -m tools.workload_scaffold --help

**Why this is repository tooling rather than part of the distribution.** Nothing
under ``src/inferops`` reads a path — that rule is checked, and it is what keeps
a domain object constructible from a wheel with no repository around it — and
validating a generated project needs the published JSON Schema and a YAML loader,
which are a file and a development dependency the distribution deliberately does
not carry. So the writer lives beside :mod:`tools.contract_validation`, whose
validator it uses and whose command a generated workload's own quick start
already tells its author to run.

**It generates. It does not deploy, serve, or regenerate.** No controller, chart,
or reconciler in this repository acts on a WorkloadContract, and a generated
workload is an ordinary committed directory the moment it exists: nothing here
overwrites one, and re-running the command over it is not part of the change
loop.
"""

from __future__ import annotations

from .arguments import build_parser, parameters_from
from .generation import (
    CONTRACT_FILE,
    DestinationRefusedError,
    GeneratedContractRefusedError,
    GenerationResult,
    PartialWriteError,
    ScaffoldError,
    WritePlan,
    generate,
    plan_write,
    validate_rendered_contract,
)

__all__ = [
    "CONTRACT_FILE",
    "DestinationRefusedError",
    "GeneratedContractRefusedError",
    "GenerationResult",
    "PartialWriteError",
    "ScaffoldError",
    "WritePlan",
    "build_parser",
    "generate",
    "parameters_from",
    "plan_write",
    "validate_rendered_contract",
]
