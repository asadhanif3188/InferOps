"""Commands for the model lifecycle state model and its cold/warm comparison."""

from __future__ import annotations

import argparse
import sys

from tools.runtime_packaging.core import (
    SubprocessRunner,
    http_get,
    http_post,
    load_runtime_package,
)

from .core import (
    LIFECYCLE_PATH,
    REPO_ROOT,
    CacheState,
    ModelLifecycleError,
    clean_results,
    compare_starts,
    load_lifecycle,
    observe_cache,
    read_results,
    summarize,
    write_results,
)

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.model_lifecycle",
        description=(
            "Read the accepted model lifecycle state model, classify the model "
            "cache offline, or run an authorized cold/warm start comparison. No "
            "command downloads a model or an image."
        ),
    )
    parser.add_argument(
        "command",
        choices=("check", "states", "cache", "measure", "results", "clean"),
    )
    parser.add_argument(
        "--confirm-real-runtime",
        action="store_true",
        help=(
            "confirm that this invocation may read real model bytes and operate "
            "the local runtime container"
        ),
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help=(
            "for 'cache', read the artifact end to end and compare its SHA-256; "
            "this warms the host file cache and is off by default"
        ),
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="for 'clean', actually remove this tool's own results directory",
    )
    return parser


def _print_check(lifecycle_id: str, states: int, transitions: int) -> None:
    print(f"lifecycle    {lifecycle_id}")
    print(f"states       {states}; transitions {transitions}")
    print("agreement    package, model source record, and API drain budget")
    print("execution    not started (offline record validation only)")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        # Named rather than left to the default, so that the record this
        # command reads is a seam a test can point somewhere else.
        lifecycle = load_lifecycle(LIFECYCLE_PATH)

        if args.command == "check":
            _print_check(
                lifecycle.lifecycle_id,
                len(lifecycle.states),
                len(lifecycle.transitions),
            )
            return EXIT_OK

        if args.command == "states":
            for rule in lifecycle.states:
                readiness = "ready" if rule.readiness else "not-ready"
                accepts = "accepts" if rule.accepts_work else "refuses"
                print(
                    f"{rule.state:<18} liveness {rule.liveness!s:<15} "
                    f"readiness {readiness:<10} {accepts}"
                )
            return EXIT_OK

        if args.command == "cache":
            observation = observe_cache(verify=args.verify)
            print(f"cache        {observation.cache_state}")
            print(
                f"bytes        {observation.bytes_present} of "
                f"{observation.expected_bytes}"
            )
            print(f"maps to      {observation.lifecycle_state}")
            print(
                "integrity    verified"
                if observation.verified
                else "integrity    not read (pass --verify to compare the digest)"
            )
            return (
                EXIT_OK if observation.cache_state is CacheState.HIT else EXIT_REFUSED
            )

        if args.command == "results":
            for document in read_results(lifecycle):
                print(
                    f"{document['observationId']:<6} ready {document['readyMs']} ms; "
                    f"cache {document['cacheState']}; "
                    f"loading observations {document['loadingObservations']}; "
                    f"liveness while loading {document['livenessHeldWhileLoading']}"
                )
            return EXIT_OK

        if args.command == "clean":
            cleanup = clean_results(lifecycle, confirm=args.confirm)
            # Printed relative to the checkout. An absolute path here would put
            # the operator's home directory into whatever this output is pasted
            # into, and the repository-relative form is the useful one anyway.
            print(f"directory    {cleanup.directory.relative_to(REPO_ROOT)}")
            print(f"bytes        {cleanup.bytes_found}")
            print(
                "removed      yes"
                if cleanup.removed
                else "removed      no (pass --confirm to remove)"
            )
            return EXIT_OK

        package = load_runtime_package()
        runner = SubprocessRunner()
        result = compare_starts(
            lifecycle,
            package,
            runner,
            confirmed=args.confirm_real_runtime,
            http_get=http_get,
            http_post=http_post,
        )
        raw, summary = write_results(lifecycle, result)
        document = summarize(lifecycle, result)
        for name in ("cold", "warm"):
            observation = document[name]
            print(
                f"{name:<6} ready {observation['readyMs']} ms; "
                f"create {observation['createMs']} ms; "
                f"first liveness {observation['firstLivenessMs']} ms; "
                f"inference {observation['inferenceMs']} ms; "
                f"stop {observation['stopMs']} ms"
            )
        print(f"verify       {document['artifactVerifyMs']} ms (SHA-256 re-read)")
        print(f"delta        {document['readyMsDelta']} ms warm minus cold")
        print(f"acceptance   {document['acceptance']}")
        print(f"raw          {raw.relative_to(REPO_ROOT)}")
        print(f"summary      {summary.relative_to(REPO_ROOT)}")
    except ModelLifecycleError as error:
        print(f"REFUSED model lifecycle: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception:
        print("FAILED model lifecycle: unexpected local failure", file=sys.stderr)
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
