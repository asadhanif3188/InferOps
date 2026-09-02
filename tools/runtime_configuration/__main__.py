"""Command line validation for the selected local runtime profile."""

from __future__ import annotations

import argparse
import shlex
import sys

from .core import RuntimeConfigurationError, validate_runtime_profile

EXIT_OK = 0
EXIT_INVALID = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.runtime_configuration",
        description=(
            "Validate and inspect the pinned local llama-server profile without "
            "starting a runtime or reading model bytes."
        ),
    )
    parser.add_argument("command", choices=("check",))
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    try:
        profile = validate_runtime_profile()
    except RuntimeConfigurationError as error:
        print(f"REFUSED configuration: {error}", file=sys.stderr)
        return EXIT_INVALID

    print(f"profile      {profile.profile_id} ({profile.environment})")
    print(f"runtime      {profile.image_reference}")
    print(f"command      {shlex.join(profile.startup_command())}")
    print(
        f"model        {profile.model_cache_root.as_posix()}/"
        f"{profile.model_artifact_relative_path.as_posix()} -> "
        f"{profile.model_container_path} (read-only)"
    )
    print(
        f"resources    cpu {profile.cpu_request_cores}-{profile.cpu_limit_cores}; "
        f"memory {profile.memory_request_mib}-{profile.memory_limit_mib} MiB; "
        f"accelerator {profile.accelerator_kind}"
    )
    print(
        f"serving      context {profile.context_size_tokens}; output "
        f"{profile.default_max_output_tokens}; slots {profile.parallel_slots}"
    )
    print(
        f"health       startup/readiness {profile.startup_path}; "
        f"liveness {profile.liveness_kind}; metrics {profile.metrics_path}"
    )
    print("execution    not started (offline validation only)")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess tests
    sys.exit(main())
