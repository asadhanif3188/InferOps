"""Commands for the Kubernetes pod-restart persistence experiment.

`check` reads committed files and contacts nothing: it prints what an authorized
run would do, which is the only thing that can be established without a cluster.
`evaluate` is the half that runs after the operating script has installed the
release, deleted one serving pod, and waited for the replacement; it is invoked
by `scripts/environment/kubernetes-pod-restart.sh` rather than by hand, because
that script owns the cluster, the forward, and the cleanup, and this command
refuses a base URL that is not the loopback forward the script opened.

There is deliberately no flag naming the collected lifecycle, readiness, or
cleanup documents. Their locations are the descriptor's, because the whole
cluster half of the record is copied out of those files: a flag there would make
the base-URL guard decorative, since a run could reach a real Service and
describe an experiment read from somewhere else.
"""

from __future__ import annotations

import argparse
import json
import sys

from .core import (
    REPO_ROOT,
    STAGE_BASELINE,
    Diagnostics,
    EvidenceDirectory,
    Experiment,
    ExperimentError,
    ExperimentFailed,
    ExperimentRefused,
    ExperimentResult,
    api_get,
    api_post,
    diagnostics_document,
    evaluate,
    load_certification,
    load_experiment,
    load_lifecycle_facts,
    merge_cleanup,
    observe_completion,
    observe_identity,
    observe_readiness,
    require_forwarded_base_url,
    result_document,
    summary_lines,
)

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.kubernetes_pod_restart",
        description=(
            "Validate, or evaluate, the Kubernetes pod-restart persistence "
            "experiment. No command installs a release, deletes a pod, or opens "
            "a forward, and `check` contacts nothing."
        ),
    )
    parser.add_argument(
        "command", choices=("check", "probe", "evaluate", "record-cleanup")
    )
    parser.add_argument(
        "--confirm-real-kubernetes",
        action="store_true",
        help=(
            "confirm that this invocation may read a real installed release, "
            "take a real model's answer, and produce a local real Kubernetes "
            "record"
        ),
    )
    parser.add_argument(
        "--base-url",
        default="",
        help=(
            "the loopback forward the operating script opened to the release's "
            "API Service, for example http://127.0.0.1:18092"
        ),
    )
    return parser


def _print_result(result: ExperimentResult, record: str) -> None:
    facts = result.facts
    before, after = facts.before, facts.after
    print(f"experiment    {result.experiment.experiment_id}")
    print(f"evidence      labelled {result.experiment.evidence_label}")
    print(
        f"cluster       provider {facts.provider}; {facts.cluster_name} on "
        f"{facts.server_version}; chart {facts.chart_version}"
    )
    print(
        f"replaced      {before.name} -> {after.name} "
        f"(different UID: {before.uid != after.uid})"
    )
    print(
        f"claim         {result.experiment.model_cache.claim_name} bound to "
        f"{facts.claim_bound_volume_after}, remounted read only: "
        f"{after.claim_read_only}"
    )
    print(
        f"artifact      {after.artifact_size_bytes} bytes, digest unchanged: "
        f"{before.artifact_sha256 == after.artifact_sha256}; verified by "
        f"'{after.init_container}' exit {after.init_exit_code}"
    )
    print(
        f"acquisition   jobs {facts.acquisition.job_count_before} -> "
        f"{facts.acquisition.job_count_after}; not repeated for the replacement"
    )
    print(
        f"readiness     {len(result.readiness.samples)} samples; "
        f"{result.readiness.observed_not_ready} at zero, "
        f"{result.readiness.observed_ready} above zero"
    )
    print(
        f"timing        replacement {facts.timings.replacement_ms} ms; recovery "
        f"{facts.timings.recovery_ms} ms. One run, one host: not a benchmark"
    )
    print(
        f"identity      adapter {result.identity.adapter_kind}; model "
        f"{result.identity.model_identifier}; runtime "
        f"{result.identity.runtime_name} {result.identity.runtime_version}; "
        f"revision {result.identity.model_revision}"
    )
    print(
        f"inference     HTTP {result.completion.status} in "
        f"{result.completion.elapsed_ms} ms; "
        f"{result.completion.total_tokens} tokens; content not retained"
    )
    print(f"record        {record}")


def _probe_baseline(experiment: Experiment, *, confirmed: bool, base_url: str) -> None:
    """Send one real completion before anything is deleted, and record it.

    "Real inference succeeds again" needs a *before*, and `helm test` is not it:
    it asks two Services for a health endpoint, which a runtime that loaded no
    weights would still answer. This is the same pair of calls the recovery
    makes, made first, so the two can be compared -- and it reads the collected
    lifecycle facts for the model identifier rather than being told one.
    """
    if not confirmed:
        raise ExperimentRefused(
            "the baseline probe sends a real inference request and runs only with "
            "explicit confirmation",
            STAGE_BASELINE,
        )
    url = require_forwarded_base_url(base_url, load_certification())
    facts = load_lifecycle_facts(experiment)
    observe_readiness(experiment, base_url=url, get=api_get, stage=STAGE_BASELINE)
    identity = observe_identity(
        experiment, facts, base_url=url, get=api_get, stage=STAGE_BASELINE
    )
    completion = observe_completion(
        experiment, facts, base_url=url, post=api_post, stage=STAGE_BASELINE
    )
    target = REPO_ROOT / experiment.baseline_completion_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "status": completion.status,
                "adapterKind": identity.adapter_kind,
                "modelIdentifier": identity.model_identifier,
                "promptTokens": completion.prompt_tokens,
                "completionTokens": completion.completion_tokens,
                "totalTokens": completion.total_tokens,
                "generatedTextRetained": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"baseline      HTTP {completion.status}; adapter {identity.adapter_kind}; "
        f"{completion.total_tokens} tokens; content not retained"
    )
    print(f"              written to {experiment.baseline_completion_file.as_posix()}")


def _write_diagnostics(experiment: Experiment, error: ExperimentError) -> str:
    """Store why the run stopped, or say plainly that storing it also failed."""
    diagnostics = Diagnostics(stage=error.stage, reason=str(error))
    try:
        evidence = EvidenceDirectory(experiment)
        written = evidence.write(
            evidence.diagnostics_path, diagnostics_document(experiment, diagnostics)
        )
    except ExperimentError:
        return "not written"
    return written.relative_to(evidence.root).as_posix()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    experiment: Experiment | None = None
    try:
        experiment = load_experiment()
        if args.command == "check":
            for line in summary_lines(experiment):
                print(line)
            print("execution     not started (offline descriptor validation only)")
            return EXIT_OK
        evidence = EvidenceDirectory(experiment)
        if args.command == "record-cleanup":
            written = evidence.write(evidence.result_path, merge_cleanup(experiment))
            print(
                "cleanup       added to "
                f"{written.relative_to(evidence.root).as_posix()}"
            )
            return EXIT_OK
        if args.command == "probe":
            _probe_baseline(
                experiment,
                confirmed=args.confirm_real_kubernetes,
                base_url=args.base_url,
            )
            return EXIT_OK
        result = evaluate(
            experiment,
            confirmed=args.confirm_real_kubernetes,
            base_url=args.base_url,
        )
        written = evidence.write(evidence.result_path, result_document(result))
        _print_result(result, written.relative_to(evidence.root).as_posix())
    except ExperimentError as error:
        # Nothing was observed when the confirmation flag was absent, and a
        # diagnostics record for an unentered lane is noise rather than evidence.
        location = (
            _write_diagnostics(experiment, error)
            if experiment is not None
            and (args.confirm_real_kubernetes or args.command == "record-cleanup")
            else "not written"
        )
        outcome = "FAILED" if isinstance(error, ExperimentFailed) else "REFUSED"
        print(
            f"{outcome} Kubernetes pod-restart experiment at stage {error.stage}: "
            f"{error}",
            file=sys.stderr,
        )
        print(f"diagnostics   {location}", file=sys.stderr)
        return EXIT_FAILED if isinstance(error, ExperimentFailed) else EXIT_REFUSED
    except KeyboardInterrupt:
        print(
            "STOPPED Kubernetes pod-restart experiment: the operating script owns "
            "cleanup",
            file=sys.stderr,
        )
        return 130
    except Exception:
        print(
            "FAILED Kubernetes pod-restart experiment: unexpected local failure",
            file=sys.stderr,
        )
        raise
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
