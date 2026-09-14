"""Commands for the repeatable LLM load profile.

`check` reads committed files and sends nothing. `rehearse` runs the whole tool over
loopback HTTP against an in-process stub and writes a synthetic record set. `run` is
the only command that sends load to a real release, and it refuses without explicit
confirmation, a loopback target, and an environment facts file. `summarize`
recomputes a summary from a raw record set and touches nothing else.

None of them contacts Kubernetes, starts a port-forward, installs anything, or reads a
model byte.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.model_acquisition import ModelAcquisitionError
from tools.runtime_configuration import RuntimeConfigurationError
from tools.runtime_packaging import RuntimePackagingError

from .core import (
    END_COMPLETED,
    MODE_REAL,
    MODE_REHEARSAL,
    LoadError,
    LoadRefused,
    Profile,
    execute,
    load_facts,
    load_profile,
    read_raw,
    run_to_raw,
    summarize,
    write_raw,
    write_summary,
)
from .rehearsal import rehearsal_profile, stub_server

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4
EXIT_NOT_USABLE = 6
EXIT_INTERRUPTED = 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.llm_load",
        description=(
            "Validate, rehearse, run, or summarize the repeatable LLM load profile. "
            "Every figure a run produces is bounded to that run and is never a "
            "portable capacity figure, a production SLO, or a benchmark."
        ),
    )
    parser.add_argument("command", choices=("check", "rehearse", "run", "summarize"))
    parser.add_argument(
        "--target-url",
        default=None,
        help="loopback base URL of a forward to the release's API Service (run only)",
    )
    parser.add_argument(
        "--environment-facts",
        type=Path,
        default=None,
        help="JSON file stating the provider and release a run is sent to (run only)",
    )
    parser.add_argument(
        "--confirm-real-load",
        action="store_true",
        help="confirm that this invocation may send real inference load (run only)",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=None,
        help="raw record set to summarize (summarize only)",
    )
    return parser


def _print_check(profile: Profile) -> None:
    fixture = profile.fixture
    levels = ", ".join(
        f"{level.level_id}={level.concurrency}" for level in profile.levels
    )
    print(
        f"profile      {profile.profile_id} {profile.profile_version} "
        f"sha256:{profile.profile_sha256}"
    )
    print(f"evidence     {profile.evidence_class} ({profile.evidence_label})")
    print(
        f"fixture      {fixture.fixture_id}; POST {fixture.request_path}; {fixture.model}"
    )
    print(
        "generation   "
        f"maxOutputTokens={profile.max_output_tokens} "
        f"temperature={profile.temperature:g} "
        f"context={profile.context_size_tokens} "
        f"parallelSlots={profile.parallel_slots}"
    )
    print(
        f"warmup       {profile.warmup_requests} requests at concurrency "
        f"{profile.warmup_concurrency}"
    )
    print(f"levels       {levels}")
    print(
        f"bounds       {profile.duration_seconds}s or "
        f"{profile.max_requests_per_level} requests per level, whichever first; "
        f"request timeout {profile.request_timeout_ms} ms; "
        f"worst case {profile.worst_case_seconds()} s"
    )
    print(
        f"success      HTTP {profile.required_status}, adapter "
        f"{profile.required_adapter_kind}, model {profile.required_model_ref}, "
        f"runtime '{profile.required_runtime_name}', usage required"
    )
    print(
        f"results      {profile.result_directory.as_posix()}/<mode>/"
        f"{profile.raw_file} and {profile.summary_file}"
    )
    print("claim        bounded to one run; not capacity, an SLO, or a benchmark")
    print("execution    not started (offline profile validation only)")


def _report(summary: dict[str, object], raw_path: Path, summary_path: Path) -> None:
    print(f"raw          {raw_path.name}")
    print(f"summary      {summary_path.name}")
    print(f"evidence     {summary['evidenceClass']} ({summary['evidenceLabel']})")
    print(f"end          {summary['end']}")
    print(f"accounting   {summary['accounting']}")
    print("claim        bounded to this run; not capacity, an SLO, or a benchmark")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile = load_profile()
        if args.command == "check":
            _print_check(profile)
            return EXIT_OK
        if args.command == "summarize":
            if args.raw is None:
                raise LoadRefused("summarize requires --raw")
            raw = read_raw(args.raw)
            summary = summarize(raw)
            path = write_summary(profile, summary, mode=str(raw.header["mode"]))
            _report(summary, args.raw, path)
            return EXIT_OK if summary["usable"] else EXIT_NOT_USABLE
        if args.command == "rehearse":
            if args.target_url or args.environment_facts or args.confirm_real_load:
                raise LoadRefused("rehearse takes no target, facts, or confirmation")
            rehearsal = rehearsal_profile(profile)
            with stub_server(rehearsal) as base_url:
                run = execute(
                    rehearsal,
                    base_url=base_url,
                    mode=MODE_REHEARSAL,
                    confirmed=False,
                    facts=None,
                )
        else:
            if args.target_url is None:
                raise LoadRefused("run requires --target-url")
            if args.environment_facts is None:
                raise LoadRefused("run requires --environment-facts")
            if not args.confirm_real_load:
                raise LoadRefused("a real load run requires --confirm-real-load")
            facts = load_facts(args.environment_facts)
            run = execute(
                profile,
                base_url=args.target_url,
                mode=MODE_REAL,
                confirmed=True,
                facts=facts,
            )
        raw_path = write_raw(profile, run)
        summary = summarize(run_to_raw(run))
        summary_path = write_summary(profile, summary, mode=str(run.header["mode"]))
        _report(summary, raw_path, summary_path)
        if run.end_state == END_COMPLETED:
            return EXIT_OK
        if run.end_state == "interrupted":
            return EXIT_INTERRUPTED
        if run.end_state == "aborted":
            return EXIT_REFUSED
        return EXIT_NOT_USABLE
    except (
        LoadError,
        ModelAcquisitionError,
        RuntimeConfigurationError,
        RuntimePackagingError,
    ) as error:
        print(f"REFUSED llm load: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except KeyboardInterrupt:
        print(
            "STOPPED llm load: interrupted before a record was written", file=sys.stderr
        )
        return EXIT_INTERRUPTED
    except Exception:
        print("FAILED llm load: unexpected local failure", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
