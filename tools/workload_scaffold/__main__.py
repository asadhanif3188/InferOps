"""Generate a conforming LLM workload from the command line.

    uv run --locked python -m tools.workload_scaffold \\
        --name support-assistant --owner team-platform --environment local \\
        --profile synchronous-llm --runtime-profile resource-conscious \\
        --cpu 6 --memory 3Gi --tenant demo --cost-center demo-cost-center \\
        --data-classification internal \\
        --description "Answers support questions from the product knowledge base." \\
        --into workloads

Run it through ``uv run --locked`` from a checkout. This command is repository
tooling and lives outside the distribution on purpose, and it needs three things
a wheel does not carry on its own: the published JSON Schema, a YAML loader, and
an importable ``inferops``. That is the same prerequisite a generated workload's
own quick start already states for ``python -m tools.contract_validation``.

Exit status is a fact about what happened rather than a single pass-or-fail bit,
so the command is usable as a gate and a failure says which stage refused:

===== ===============================================================
    0 the workload was generated, and the contract validated on disk
    1 the parameter set was refused, with every reason. Nothing written
    2 a usage error, from ``argparse``
    3 the destination was refused. Nothing written
    4 the generated contract did not validate. Nothing written
    5 a write failed partway and was rolled back
===== ===============================================================

Output is deterministic. Findings and refusals are sorted, and ``--json``
produces a stable document a reviewer can diff between runs. Everything goes to
standard output, as ``tools.contract_validation`` does, so a caller can pipe it.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from inferops.scaffolding import InvalidTemplateParametersError

from .arguments import build_parser, parameters_from
from .generation import (
    DestinationRefusedError,
    GeneratedContractRefusedError,
    GenerationResult,
    PartialWriteError,
    generate,
)

EXIT_OK = 0
EXIT_PARAMETERS_REFUSED = 1
EXIT_USAGE = 2
EXIT_DESTINATION_REFUSED = 3
EXIT_CONTRACT_REFUSED = 4
EXIT_WRITE_FAILED = 5


def _render_result(result: GenerationResult) -> list[str]:
    verb = "would generate" if result.dry_run else "generated"
    lines = [f"ok      {verb} {result.workload_root.as_posix()}"]
    lines.extend(f"        {path.as_posix()}" for path in result.files)
    if result.dry_run:
        lines.append("        nothing was written; --dry-run stopped before the write")
    else:
        lines.append(
            "        the contract was validated from disk against the published "
            "schema and every semantic rule"
        )
    return lines


def _render_parameter_refusal(error: InvalidTemplateParametersError) -> list[str]:
    lines = [f"REFUSED parameters  ({len(error.errors)} refusal(s)); nothing written"]
    lines.extend(
        f"        {entry['parameter']}  {entry['reason']}" for entry in error.as_dicts()
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, generate one workload, and report what happened."""
    parser = build_parser()
    args = parser.parse_args(argv)

    payload: dict[str, Any]
    try:
        result = generate(
            parameters_from(args), args.into.resolve(), dry_run=args.dry_run
        )
    except InvalidTemplateParametersError as error:
        payload = {"refused": "parameters", "refusals": error.as_dicts()}
        lines = _render_parameter_refusal(error)
        status = EXIT_PARAMETERS_REFUSED
    except GeneratedContractRefusedError as error:
        payload = {"refused": "generated-contract", "findings": error.as_dicts()}
        lines = [
            f"REFUSED generated contract  ({len(error.findings)} finding(s)); "
            "nothing written",
            *(
                f"        {entry['code']}  {entry['rule']}  {entry['field']}  "
                f"{entry['message']}"
                for entry in error.as_dicts()
            ),
        ]
        status = EXIT_CONTRACT_REFUSED
    except DestinationRefusedError as error:
        payload = {"refused": "destination", "destination": error.as_dict()}
        lines = [f"REFUSED {error.path.as_posix()}  {error.reason}"]
        status = EXIT_DESTINATION_REFUSED
    except PartialWriteError as error:
        payload = {"refused": "write", "write": error.as_dict()}
        lines = [
            f"FAILED  {error.destination.as_posix()}  {error.reason}",
            *(f"        removed   {path.as_posix()}" for path in error.removed),
            *(f"        LEFT      {path.as_posix()}" for path in error.unremoved),
        ]
        status = EXIT_WRITE_FAILED
    else:
        payload = {"generated": result.as_dict()}
        lines = _render_result(result)
        status = EXIT_OK

    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("\n".join(lines))
    return status


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    sys.exit(main())
