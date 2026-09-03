"""Commands for the loopback InferOps API plus selected real runtime."""

from __future__ import annotations

import argparse
import sys

from tools.runtime_packaging import RuntimePackagingError, SubprocessRunner

from .core import (
    CompositionError,
    cleanup,
    load_composition,
    read_logs,
    run_foreground,
    status,
)
from .http_server import LocalHttpServerError

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4
EXIT_NOT_READY = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.local_composition",
        description=(
            "Validate or explicitly operate the loopback InferOps API with the "
            "pinned real runtime. No command downloads a model or image implicitly."
        ),
    )
    parser.add_argument(
        "command",
        choices=("check", "start", "status", "logs", "cleanup"),
    )
    parser.add_argument(
        "--confirm-real-runtime",
        action="store_true",
        help=(
            "confirm that this invocation may inspect real model bytes and operate "
            "the local runtime container"
        ),
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=100,
        help="number of structured composition log lines to show (1-1000)",
    )
    return parser


def _print_check() -> None:
    composition = load_composition()
    print(f"composition  {composition.composition_id} ({composition.evidence_class})")
    print(f"adapter      {composition.adapter_selection}; mock fallback disabled")
    print(f"runtime      {composition.environment['INFEROPS_LLAMA_SERVER_ENDPOINT']}")
    print(f"api          {composition.api_base_url}; loopback only")
    print(f"readiness    {composition.api_readiness_url}")
    print(f"logs         {composition.log_path.as_posix()}; structured local records")
    print("execution    not started (offline composition validation only)")


def _print_ready(runtime_ms: int, api_ms: int) -> None:
    print(f"runtime      ready after {runtime_ms} ms")
    print(f"api          ready after {api_ms} ms; adapter real")
    print("lifecycle    attached in foreground; press Ctrl+C for ordered cleanup")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        composition = load_composition()
        if args.command == "check":
            _print_check()
            return EXIT_OK
        if args.command == "logs":
            records = read_logs(composition, lines=args.lines)
            if records:
                print("\n".join(records))
            else:
                print("logs         no composition records")
            return EXIT_OK

        runner = SubprocessRunner(
            timeout_seconds=composition.engine_command_timeout_seconds
        )
        if args.command == "start":
            run_foreground(
                composition,
                confirmed=args.confirm_real_runtime,
                runner=runner,
                on_ready=_print_ready,
            )
        elif args.command == "status":
            result = status(
                composition,
                runner,
                confirmed=args.confirm_real_runtime,
            )
            print(f"composition  {result.profile}; adapter {result.adapter}")
            print(
                "runtime      "
                f"owned={result.runtime_owned} running={result.runtime_running} "
                f"live={result.runtime_live} ready={result.runtime_ready}"
            )
            print(f"api          ready={result.api_ready}")
            return EXIT_OK if result.ready else EXIT_NOT_READY
        else:
            removed = cleanup(
                composition,
                runner,
                confirmed=args.confirm_real_runtime,
            )
            print(
                "runtime      stopped and removed" if removed else "runtime      absent"
            )
    except (CompositionError, RuntimePackagingError, LocalHttpServerError) as error:
        print(f"REFUSED local composition: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except KeyboardInterrupt:
        print("STOPPED local composition: ordered cleanup requested", file=sys.stderr)
        return 130
    except Exception:
        print("FAILED local composition: unexpected local failure", file=sys.stderr)
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
