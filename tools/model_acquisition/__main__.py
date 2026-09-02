"""Command line for the selected model's acquisition and cache lifecycle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    AcquisitionError,
    CacheSafetyError,
    ModelAcquisitionError,
    PreflightError,
    VerificationError,
    acquire,
    check_prerequisites,
    clean_cache,
    load_manifest,
    verify_artifact,
)

EXIT_OK = 0
EXIT_PREFLIGHT = 3
EXIT_VERIFICATION = 4
EXIT_ACQUISITION = 5
EXIT_CLEANUP = 6


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.model_acquisition",
        description=(
            "Check, acquire, verify, or clean the revision-pinned open-model cache. "
            "The command accepts no credential and never downloads implicitly."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="run offline prerequisites and show cache state")
    commands.add_parser("acquire", help="download/resume and verify the selected model")
    commands.add_parser(
        "verify", help="verify the already-cached model without network"
    )
    clean = commands.add_parser("clean", help="inspect or remove only the model cache")
    clean.add_argument(
        "--confirm",
        action="store_true",
        help="remove the documented cache; without this flag, only report the target",
    )
    return parser


def _gib(value: int) -> str:
    return f"{value / (1024**3):.2f} GiB"


def _display_cache(path: Path) -> str:
    return path.relative_to(path.parents[2]).as_posix()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = load_manifest()
        if args.command == "check":
            report = check_prerequisites(manifest)
            print(f"source       {manifest.repository}")
            print(f"revision     {manifest.revision}")
            print(f"file         {manifest.file}")
            print(f"download     {manifest.source_url}")
            print(
                f"license      {manifest.license_spdx} ({manifest.license_reference})"
            )
            print(f"size         {manifest.expected_size_bytes} bytes")
            print(f"sha256       {manifest.sha256}")
            print(f"cache        {_display_cache(report.cache_root)}")
            print(
                f"state        {report.state} ({report.existing_bytes} bytes present)"
            )
            print(
                f"disk         {_gib(report.available_free_bytes)} free; "
                f"{_gib(report.required_free_bytes)} required"
            )
        elif args.command == "verify":
            size = verify_artifact(manifest.artifact_path(), manifest)
            print(f"verified     {manifest.file} ({size} bytes, SHA-256 matched)")
        elif args.command == "acquire":
            download_result = acquire(manifest)
            status = "cache hit" if download_result.cache_hit else "download verified"
            print(f"verified     {status}; {download_result.bytes_verified} bytes")
            if download_result.resumed_from_bytes:
                print(f"resumed      from {download_result.resumed_from_bytes} bytes")
        else:
            cleanup_result = clean_cache(confirm=args.confirm)
            action = "removed" if cleanup_result.removed else "retained"
            print(f"cache        {_display_cache(cleanup_result.cache_root)}")
            print(f"cleanup      {action}; {cleanup_result.bytes_found} bytes found")
            if not args.confirm:
                print("cleanup      dry run; pass --confirm to remove this cache")
    except PreflightError as error:
        print(f"REFUSED preflight: {error}", file=sys.stderr)
        return EXIT_PREFLIGHT
    except VerificationError as error:
        print(f"REFUSED verification: {error}", file=sys.stderr)
        return EXIT_VERIFICATION
    except AcquisitionError as error:
        print(f"FAILED acquisition: {error}", file=sys.stderr)
        return EXIT_ACQUISITION
    except CacheSafetyError as error:
        print(f"REFUSED cleanup: {error}", file=sys.stderr)
        return EXIT_CLEANUP
    except ModelAcquisitionError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return EXIT_PREFLIGHT
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess tests
    sys.exit(main())
