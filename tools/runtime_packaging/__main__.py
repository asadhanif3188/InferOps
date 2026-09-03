"""Commands for the selected runtime's standalone local container package."""

from __future__ import annotations

import argparse
import sys

from .core import (
    RuntimePackagingError,
    SubprocessRunner,
    http_get,
    http_post,
    load_runtime_package,
    owned_container_exists,
    smoke,
    start,
    stop,
    tcp_is_live,
    wait_ready,
)

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.runtime_packaging",
        description=(
            "Validate or explicitly operate the pinned standalone llama-server "
            "container. No command downloads a model or image implicitly."
        ),
    )
    parser.add_argument(
        "command",
        choices=("check", "start", "live", "ready", "stop", "smoke"),
    )
    parser.add_argument(
        "--confirm-real-runtime",
        action="store_true",
        help=(
            "confirm that this invocation may inspect real model bytes and operate "
            "the local runtime container"
        ),
    )
    return parser


def _print_package() -> None:
    package = load_runtime_package()
    print(f"package      {package.package_id} ({package.engine})")
    print(f"runtime      {package.image_reference}")
    print(f"container    {package.container_name}; user {package.user}")
    print(
        f"exposure     {package.published_host}:{package.published_port} -> "
        f"{package.container_port}"
    )
    print(
        f"resources    cpu {package.cpu_request_cores}/{package.cpu_limit_cores}; "
        f"memory {package.memory_request_mib}/{package.memory_limit_mib} MiB; "
        f"accelerator {package.accelerator_kind}"
    )
    print("model        external verified cache artifact; read-only")
    print("execution    not started (offline package validation only)")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        package = load_runtime_package()
        if args.command == "check":
            _print_package()
            return EXIT_OK

        runner = SubprocessRunner()
        if args.command == "start":
            start(package, runner, confirmed=args.confirm_real_runtime)
            print("runtime      started; readiness not yet established")
        elif args.command == "live":
            if not args.confirm_real_runtime:
                raise RuntimePackagingError(
                    "real runtime execution requires --confirm-real-runtime"
                )
            if not owned_container_exists(package, runner):
                raise RuntimePackagingError("the owned runtime container is absent")
            if not tcp_is_live(package):
                raise RuntimePackagingError("the runtime TCP liveness check failed")
            print("liveness     TCP connection accepted")
        elif args.command == "ready":
            trace = wait_ready(
                package,
                runner,
                confirmed=args.confirm_real_runtime,
                http_get=http_get,
            )
            print(
                f"readiness    ready after {trace.elapsed_ms} ms; "
                f"observations {len(trace.statuses)}"
            )
        elif args.command == "stop":
            removed = stop(
                package,
                runner,
                confirmed=args.confirm_real_runtime,
            )
            print(
                "runtime      stopped and removed" if removed else "runtime      absent"
            )
        else:
            result = smoke(
                package,
                runner,
                confirmed=args.confirm_real_runtime,
                http_get=http_get,
                http_post=http_post,
            )
            print(
                f"readiness    ready after {result.readiness.elapsed_ms} ms; "
                f"observations {len(result.readiness.statuses)}"
            )
            print(f"inference    HTTP {result.inference_status}; content discarded")
            print(f"shutdown     {'complete' if result.stopped else 'incomplete'}")
    except RuntimePackagingError as error:
        print(f"REFUSED runtime package: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception:
        print("FAILED runtime package: unexpected local failure", file=sys.stderr)
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
