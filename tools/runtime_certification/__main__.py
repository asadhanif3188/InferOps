"""Commands for the C2 real-runtime smoke certification of the composed path."""

from __future__ import annotations

import argparse
import sys

from tools.runtime_packaging import load_runtime_package

from .core import (
    Certification,
    CertificationError,
    CertificationFailed,
    CertificationResult,
    Diagnostics,
    EvidenceDirectory,
    certify,
    diagnostics_document,
    load_certification,
    result_document,
)

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.runtime_certification",
        description=(
            "Validate or explicitly run the C2 real-runtime smoke certification. "
            "No command downloads a model or image implicitly, and `check` "
            "contacts nothing at all."
        ),
    )
    parser.add_argument("command", choices=("check", "certify"))
    parser.add_argument(
        "--confirm-real-runtime",
        action="store_true",
        help=(
            "confirm that this invocation may inspect real model bytes, operate "
            "the local runtime container, and produce a local-real record"
        ),
    )
    return parser


def _print_check(certification: Certification) -> None:
    package = load_runtime_package()
    print(
        f"certification {certification.certification_id} "
        f"({certification.certification_level}; {certification.evidence_class})"
    )
    print(f"lane          {certification.lane}; outside the default check lane")
    print(f"composition   {certification.composition_ref}")
    print(f"runtime       {package.image_reference}")
    print(
        "prerequisites cpus>="
        f"{certification.minimum_logical_cpus}; engine memory>="
        f"{certification.minimum_engine_memory_bytes} bytes; free disk>="
        f"{certification.minimum_free_disk_bytes} bytes"
    )
    print(
        f"readiness     runtime {certification.runtime_budget_ms} ms; "
        f"api {certification.api_budget_ms} ms"
    )
    print(
        f"request       POST {certification.request_path}; identity GET "
        f"{certification.models_path}; budget {certification.request_timeout_ms} ms"
    )
    print(
        "assertions    real adapter kind, pinned model revision, runtime-derived "
        "counts, non-empty content; mock identity refused"
    )
    print(
        f"evidence      {certification.evidence_directory.as_posix()}/"
        f"{certification.result_file}; generated text never retained"
    )
    print("execution     not started (offline certification validation only)")


def _print_certified(
    certification: Certification, result: CertificationResult, record: str
) -> None:
    print(
        f"certification {result.certification_id} "
        f"({result.certification_level}; {result.evidence_class})"
    )
    print(f"evidence      labelled {certification.evidence_label}")
    print(
        f"readiness     runtime {result.runtime_readiness_ms} ms; "
        f"api {result.api_readiness_ms} ms"
    )
    print(
        f"identity      adapter {result.identity.adapter_kind}; "
        f"model {result.identity.model_identifier}; "
        f"runtime {result.identity.runtime_name} {result.identity.runtime_version}; "
        f"revision {result.identity.model_revision}"
    )
    print(
        f"inference     HTTP {result.inference.status} in "
        f"{result.inference.elapsed_ms} ms; {result.inference.total_tokens} tokens; "
        "content not retained"
    )
    print(
        f"cleanup       api drained {result.api_drained}; runtime removed "
        f"{result.runtime_removed}"
    )
    print(f"record        {record}")


def _write_diagnostics(certification: Certification, error: CertificationError) -> str:
    """Store why the run stopped, or say plainly that storing it also failed."""
    report = getattr(error, "report", None)
    diagnostics = Diagnostics(
        stage=error.stage,
        reason=str(error),
        host=None if report is None else report.host,
        prerequisites=() if report is None else report.checks,
    )
    try:
        evidence = EvidenceDirectory(certification)
        written = evidence.write(
            evidence.diagnostics_path, diagnostics_document(diagnostics)
        )
    except CertificationError:
        return "not written"
    return written.relative_to(evidence.root).as_posix()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    certification: Certification | None = None
    try:
        certification = load_certification()
        if args.command == "check":
            _print_check(certification)
            return EXIT_OK
        result = certify(certification, confirmed=args.confirm_real_runtime)
        evidence = EvidenceDirectory(certification)
        written = evidence.write(evidence.result_path, result_document(result))
        _print_certified(
            certification, result, written.relative_to(evidence.root).as_posix()
        )
    except CertificationError as error:
        failed = isinstance(error, CertificationFailed)
        # Nothing ran when the confirmation flag was absent, and a diagnostics
        # record for an unentered lane is noise rather than evidence.
        location = (
            _write_diagnostics(certification, error)
            if certification is not None and args.confirm_real_runtime
            else "not written"
        )
        print(
            f"{'FAILED' if failed else 'REFUSED'} C2 certification at stage "
            f"{error.stage}: {error}",
            file=sys.stderr,
        )
        print(f"diagnostics   {location}", file=sys.stderr)
        return EXIT_FAILED if failed else EXIT_REFUSED
    except KeyboardInterrupt:
        print("STOPPED C2 certification: ordered cleanup requested", file=sys.stderr)
        return 130
    except Exception:
        print("FAILED C2 certification: unexpected local failure", file=sys.stderr)
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
