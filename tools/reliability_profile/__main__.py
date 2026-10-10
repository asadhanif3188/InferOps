"""Check the committed RP-1 reliability caller profile.

    python -m tools.reliability_profile check

The command loads the profile, compares it with the V1 load profile it pins, and
prints its identity, both digests, and the main values. It does not print each
member. Exit status 0 says that each rule accepted the profile. Exit status 3 says
that one rule refused it, and the message names the rule. Exit status 2 says that
the arguments are not usable. Exit status 4 says that the command failed in a way
that no rule names.

**The command reads committed files and writes nothing.** It sends no request, it
contacts no cluster, and it reads no model byte. See
docs/serving/reliability-workload-rp-1.md.
"""

from __future__ import annotations

import argparse
import json
import sys

from .core import PROFILE_REF, ProfileError, ReliabilityProfile, load_profile

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4


def _print_check(profile: ReliabilityProfile) -> None:
    print(f"profile      {profile.profile_id} revision {profile.profile_revision}")
    print(f"file         {PROFILE_REF}")
    print(f"sha256       {profile.profile_sha256}")
    print(
        f"source       {profile.source_profile_ref} version "
        f"{profile.source_profile_version}"
    )
    print(f"source       sha256 {profile.source_profile_sha256}")
    print(
        f"caller       {profile.concurrency} closed-loop workers, in-cluster, to "
        "the API Service"
    )
    print(
        f"request      {profile.fixture_id}; {profile.request_method} "
        f"{profile.request_path}; {profile.request_body['model']}; "
        f"{len(profile.request_body['messages'])} message(s); stream "
        f"{json.dumps(profile.request_body['stream'])}"
    )
    print(
        "generation   "
        f"maxOutputTokens={profile.max_output_tokens} "
        f"temperature={profile.temperature:g} "
        f"samplingSeed={profile.sampling_seed} "
        f"context={profile.context_size_tokens} "
        f"parallelSlots={profile.parallel_slots}; not sent in the request"
    )
    print(f"deadline     {profile.request_timeout_ms} ms for each request")
    print(
        f"success      HTTP {profile.required_status}, adapter "
        f"{profile.required_adapter_kind}, model {profile.required_model_ref}, "
        f"usage required {json.dumps(profile.require_usage)}, one choice, within "
        "the deadline"
    )
    print(
        "claim        a reliability workload; not representative, not an overload "
        "test, not a benchmark"
    )
    print("execution    not started (offline profile validation only)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.reliability_profile",
        description=(
            "Check the RP-1 reliability caller profile against the V1 load profile "
            "it pins. The command sends nothing."
        ),
    )
    parser.add_argument("command", choices=("check",))
    parser.parse_args(argv)
    try:
        profile = load_profile()
    except ProfileError as error:
        print(f"REFUSED  {error}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception:
        print("FAILED   reliability profile: unexpected local failure", file=sys.stderr)
        return EXIT_FAILED
    _print_check(profile)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
