"""Commands for the registered local serving baseline experiment.

`check` and `environment` read committed files and the host; neither starts a
runtime. `run` is the only command that executes the experiment, and it refuses
without explicit confirmation. `summarize` recomputes the summary from a raw
result set and touches nothing else, which is what makes a published summary
checkable against the records it claims to describe.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.local_composition import CompositionError
from tools.model_acquisition import ModelAcquisitionError
from tools.runtime_configuration import RuntimeConfigurationError
from tools.runtime_packaging import RuntimePackagingError, SubprocessRunner

from .core import (
    BaselineError,
    BaselineRefused,
    capture_environment,
    execute,
    load_experiment,
    read_raw,
    summarize,
    write_raw,
    write_summary,
)

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4
EXIT_CRITERIA_UNMET = 6


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.serving_baseline",
        description=(
            "Validate, execute, or summarize the local serving baseline. The "
            "baseline is a descriptive local measurement and never a benchmark; "
            "no command downloads a model or pulls an image implicitly."
        ),
    )
    parser.add_argument(
        "command",
        choices=("check", "environment", "run", "summarize"),
    )
    parser.add_argument(
        "--confirm-real-runtime",
        action="store_true",
        help=(
            "confirm that this invocation may operate the local runtime container "
            "and send real inference requests through the InferOps API"
        ),
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=None,
        help="raw result set to summarize; defaults to the experiment's own path",
    )
    return parser


def _print_check() -> None:
    experiment = load_experiment()
    fixture = experiment.fixture
    print(f"experiment   {experiment.experiment_id} ({experiment.evidence_class})")
    print(f"fixture      {fixture.fixture_id}; {len(fixture.messages)} messages")
    print(f"request      POST {fixture.request_path}; model {fixture.model}")
    print(
        "generation   "
        f"maxOutputTokens={experiment.max_output_tokens} "
        f"temperature={experiment.temperature} "
        f"context={experiment.context_size_tokens}"
    )
    print(
        "execution    "
        f"warmup={experiment.warmup_requests} "
        f"measured={experiment.measured_requests} "
        f"concurrency={experiment.concurrency} "
        f"maxDuration={experiment.max_duration_seconds}s"
    )
    print(
        "success      "
        f"{experiment.minimum_successful_requests} successes, at most "
        f"{experiment.maximum_failed_requests} failures, adapter "
        f"{experiment.required_adapter_kind}"
    )
    print(
        "results      "
        f"{(experiment.result_directory / experiment.raw_file).as_posix()} and "
        f"{(experiment.result_directory / experiment.summary_file).as_posix()}"
    )
    print(
        "percentiles  "
        f"{experiment.percentile_method}; "
        + ", ".join(f"P{value}" for value in experiment.reported_percentiles)
    )
    print("claim        descriptive local measurement; not a production benchmark")
    print("execution    not started (offline experiment validation only)")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        experiment = load_experiment()
        if args.command == "check":
            _print_check()
            return EXIT_OK
        if args.command == "environment":
            record = capture_environment(runner=SubprocessRunner(timeout_seconds=30))
            print(json.dumps(record.document(), indent=2, sort_keys=True))
            return EXIT_OK
        if args.command == "summarize":
            run = read_raw(experiment, path=args.raw)
            summary = summarize(experiment, run)
            path = write_summary(experiment, summary)
            print(
                f"summary      {path.name} regenerated from {len(run.records)} records"
            )
            print(f"requests     {summary['requests']}")
            print(f"latency      {summary['latency']}")
            print("claim        descriptive local measurement; not a benchmark")
            return EXIT_OK if summary["successCriteria"]["met"] else EXIT_CRITERIA_UNMET

        run = execute(experiment, confirmed=args.confirm_real_runtime)
        raw_path = write_raw(experiment, run)
        summary = summarize(experiment, run)
        summary_path = write_summary(experiment, summary)
        print(f"raw          {raw_path.name}; {len(run.records)} request records")
        print(f"summary      {summary_path.name}")
        print(
            f"startup      modelLoadMs={run.model_load_ms} apiReadyMs={run.api_ready_ms}"
        )
        print(f"requests     {summary['requests']}")
        print("claim        local real runtime; descriptive, not a benchmark")
        return EXIT_OK if summary["successCriteria"]["met"] else EXIT_CRITERIA_UNMET
    except BaselineRefused as error:
        print(f"REFUSED serving baseline: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except (
        BaselineError,
        CompositionError,
        ModelAcquisitionError,
        RuntimeConfigurationError,
        RuntimePackagingError,
    ) as error:
        print(f"REFUSED serving baseline: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except KeyboardInterrupt:
        print("STOPPED serving baseline: ordered cleanup requested", file=sys.stderr)
        return 130
    except Exception:
        print("FAILED serving baseline: unexpected local failure", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
