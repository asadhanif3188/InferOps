"""Commands for the Helm upgrade and rollback experiment.

`check` reads committed files and contacts nothing: it prints what an authorized
run would do, which is the only thing that can be established without a cluster.
`evaluate` is the half that runs after the operating script has installed,
upgraded, broken, and rolled back the release; it is invoked by
`scripts/environment/helm-upgrade-rollback.sh` rather than by hand, because that
script owns the cluster, the forward, and the cleanup, and this command refuses a
base URL that is not the loopback forward the script opened.

There is deliberately no flag naming the collected lifecycle, impact, or cleanup
documents. Their locations are the descriptor's, because the whole cluster half
of the record is copied out of those files: a flag there would make the base-URL
guard decorative, since a run could reach a real Service and describe an
experiment read from somewhere else.
"""

from __future__ import annotations

import argparse
import sys

from .core import (
    Diagnostics,
    EvidenceDirectory,
    Experiment,
    ExperimentError,
    ExperimentFailed,
    ExperimentInconclusive,
    ExperimentResult,
    diagnostics_document,
    evaluate,
    load_experiment,
    merge_cleanup,
    result_document,
)

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4
EXIT_INCONCLUSIVE = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.helm_upgrade_rollback",
        description=(
            "Validate, or evaluate, the Helm upgrade and rollback experiment. "
            "No command installs a release, upgrades one, injects a fault, rolls "
            "anything back, or opens a forward, and `check` contacts nothing."
        ),
    )
    parser.add_argument("command", choices=("check", "evaluate", "record-cleanup"))
    parser.add_argument(
        "--confirm-real-kubernetes",
        action="store_true",
        help=(
            "confirm that this invocation may read a real installed release, "
            "take a real model's answer, and produce a local real Kubernetes record"
        ),
    )
    parser.add_argument(
        "--base-url",
        default="",
        help=(
            "the loopback forward the operating script opened to the release's "
            "API Service, for example http://127.0.0.1:18090"
        ),
    )
    return parser


def _print_check(experiment: Experiment) -> None:
    release = experiment.release
    budgets = experiment.budgets
    print(
        f"experiment    {experiment.experiment_id} "
        f"(ceiling {experiment.certification_ceiling}; "
        f"{experiment.evidence_class})"
    )
    print(f"lane          {experiment.lane}; outside the default check lane")
    print(f"chart         {experiment.chart_ref}; profile {release.profile}")
    print(
        f"release       {release.name} in {release.namespace}; "
        f"{release.replicas} replica(s) of {release.api_component} and "
        f"{release.runtime_component}"
    )
    print(f"baseline      agrees with {experiment.baseline_certification_ref}")
    print(f"stages        {' -> '.join(experiment.declared_stages)}")
    print(
        f"candidate     --set {experiment.candidate.values_path}="
        f"{experiment.candidate.candidate_value}, asserted at "
        f"{experiment.candidate.config_map_key} in "
        f"{release.config_map_name}"
    )
    print(
        f"fault         {experiment.fault.mechanism}: --set "
        f"{experiment.fault.values_path}="
        f"{experiment.fault.injected_size_bytes}, failing in the "
        f"'{experiment.fault.fails_in_container}' init container of "
        f"{experiment.fault.fails_in_workload}"
    )
    print(
        f"              scoped to the {experiment.fault.scope}, reversed by "
        f"{experiment.fault.reversible_by}; pulls no image and creates no object "
        "outside the release"
    )
    print(
        f"detection     decisive: {', '.join(experiment.detection.decisive_signals)}; "
        f"polled every {experiment.detection.poll_interval_ms} ms"
    )
    print(
        f"              a '{experiment.detection.deadline_signal}' is recorded as a "
        f"deadline, never as health; "
        f"{', '.join(experiment.detection.inconclusive_signals)} refuses the run"
    )
    print(
        f"rollback      to the {experiment.rollback.target}; configuration, fault "
        "removal, release test, and a real completion are each asserted separately"
    )
    print(
        f"impact        GET {experiment.impact.probe_path} every "
        f"{experiment.impact.probe_interval_ms} ms, at least "
        f"{experiment.impact.minimum_probes} probes across the failure window"
    )
    print(
        f"budgets       upgrade {budgets.upgrade_ms} ms; detection "
        f"{budgets.failure_detection_ms} ms; rollback {budgets.rollback_ms} ms; "
        f"recovery {budgets.recovery_ms} ms; uninstall {budgets.uninstall_ms} ms"
    )
    print(
        f"request       POST {experiment.request_path}; identity GET "
        f"{experiment.models_path}; budget {experiment.request_timeout_ms} ms"
    )
    print(
        f"evidence      {experiment.evidence_directory.as_posix()}/"
        f"{experiment.result_file}; labelled {experiment.evidence_label}; "
        "generated text never retained"
    )
    print(
        "cleanup       uninstalls the release; removes neither the Terraform "
        "prerequisites, the model cache claim, nor the cluster"
    )
    print(f"limitations   {len(experiment.limitations)} stated in the descriptor")
    print("execution     not started (offline descriptor validation only)")


def _print_result(result: ExperimentResult, record: str) -> None:
    facts = result.facts
    recovery = facts.recovery
    candidate = facts.stage("candidate")
    rollback = facts.stage("rollback")
    print(f"experiment    {result.experiment.experiment_id}")
    print(f"evidence      labelled {result.experiment.evidence_label}")
    print(
        f"cluster       {facts.cluster_name} on {facts.server_version}; chart "
        f"{facts.chart_version}"
    )
    print(
        "revisions     "
        + "; ".join(
            f"{stage.stage} r{stage.revision} {stage.outcome}" for stage in facts.stages
        )
    )
    print(
        f"detection     {facts.detection.signal} on "
        f"{facts.detection.workload}/{facts.detection.container} "
        f"(exit {facts.detection.exit_code}) after "
        f"{facts.detection.detected_after_ms} ms"
    )
    print(
        f"recovery      {recovery.recovery_ms} ms from detection to a served "
        f"completion; rollback {recovery.rollback_ms} ms; r{rollback.revision} "
        f"restored r{candidate.revision}"
    )
    print(
        f"impact        {result.impact.answered}/{len(result.impact.probes)} "
        f"readiness probes answered during the failure window"
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


def _write_diagnostics(experiment: Experiment, error: ExperimentError) -> str:
    """Store why the run stopped, or say plainly that storing it also failed."""
    diagnostics = Diagnostics(stage=error.stage, reason=str(error))
    try:
        evidence = EvidenceDirectory(experiment)
        written = evidence.write(
            evidence.diagnostics_path, diagnostics_document(diagnostics)
        )
    except ExperimentError:
        return "not written"
    return written.relative_to(evidence.root).as_posix()


def _outcome_word(error: ExperimentError) -> str:
    if isinstance(error, ExperimentInconclusive):
        return "INCONCLUSIVE"
    return "FAILED" if isinstance(error, ExperimentFailed) else "REFUSED"


def _exit_code(error: ExperimentError) -> int:
    if isinstance(error, ExperimentInconclusive):
        return EXIT_INCONCLUSIVE
    return EXIT_FAILED if isinstance(error, ExperimentFailed) else EXIT_REFUSED


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    experiment: Experiment | None = None
    try:
        experiment = load_experiment()
        if args.command == "check":
            _print_check(experiment)
            return EXIT_OK
        evidence = EvidenceDirectory(experiment)
        if args.command == "record-cleanup":
            written = evidence.write(evidence.result_path, merge_cleanup(experiment))
            print(
                f"cleanup       added to {written.relative_to(evidence.root).as_posix()}"
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
        print(
            f"{_outcome_word(error)} Helm upgrade and rollback experiment at stage "
            f"{error.stage}: {error}",
            file=sys.stderr,
        )
        print(f"diagnostics   {location}", file=sys.stderr)
        return _exit_code(error)
    except KeyboardInterrupt:
        print(
            "STOPPED Helm upgrade and rollback experiment: the operating script "
            "owns cleanup",
            file=sys.stderr,
        )
        return 130
    except Exception:
        print(
            "FAILED Helm upgrade and rollback experiment: unexpected local failure",
            file=sys.stderr,
        )
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
