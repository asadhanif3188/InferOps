"""Commands for the multi-replica Kubernetes C2 certification.

Four of them, and the split is the order a run happens in rather than a menu.

`check` reads committed files and contacts nothing: it prints what an authorized
run would do, which is the only thing establishable without a cluster.

`preflight` is the one that must answer **before** anything is installed. It reads
the host and cluster figures the operating script measured and refuses, naming
every shortfall at once, when the profile will not fit. Its exit code is its own
so that a caller can tell "this host is too small" from "the release did not
certify" -- the first is a host to fix and the second is a platform to debug.

`certify` runs after the request set has been sent and the replicas' own records
collected. It asserts and writes the record, and it deliberately runs **before**
the teardown, so that a failed assertion leaves the release standing for
inspection.

`record-cleanup` runs after the teardown and rewrites the same record with the
cleanup outcome in it. The outcome cannot exist before the teardown and the
record may not be written after it, so the record is written twice rather than
carrying a cleanup nobody observed.

There is deliberately no flag naming any collected file. Every location is the
descriptor's, because the whole cluster half of the record is copied out of those
files: a path flag would let a run describe an environment read from somewhere
else entirely.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import multi_replica
from .core import CertificationError, CertificationFailed
from .multi_replica import (
    CapacityFacts,
    CapacityUnmet,
    Diagnostics,
    MultiReplicaCertification,
    MultiReplicaEvidence,
    MultiReplicaResult,
    assess_capacity,
    certify_multi_replica,
    diagnostics_document,
    load_capacity_facts,
    load_cleanup_facts,
    load_multi_replica_certification,
    require_capacity,
    result_document,
)


def _root() -> Path:
    """The repository root, read at call time rather than bound at import.

    Every reader in `multi_replica` takes the root as a keyword defaulting to
    the module's constant, and a default is bound once. Reading it here means a
    caller -- a test, or a future workflow rooted somewhere else -- can point
    the whole command at another tree without any reader growing a path flag.
    """
    return multi_replica.REPO_ROOT


EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4
EXIT_CAPACITY = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.kubernetes_certification.multi_replica_cli",
        description=(
            "Validate, preflight, or certify the multi-replica Kubernetes "
            "real-inference profile. No command installs a release, creates a "
            "cluster, sends a request, or removes anything, and `check` contacts "
            "nothing at all."
        ),
    )
    parser.add_argument(
        "command", choices=("check", "preflight", "certify", "record-cleanup")
    )
    parser.add_argument(
        "--confirm-real-kubernetes",
        action="store_true",
        help=(
            "confirm that this invocation may read what a real installed release "
            "reported and produce a local real Kubernetes record"
        ),
    )
    return parser


def _print_check(certification: MultiReplicaCertification) -> None:
    release = certification.release
    plan = certification.distribution
    capacity = certification.capacity
    budgets = certification.budgets
    print(
        f"certification {certification.certification_id} "
        f"({certification.certification_level}; {certification.evidence_class})"
    )
    print(f"lane          {certification.lane}; outside the default check lane")
    print(f"chart         {certification.chart_ref}; profile {release.profile}")
    print(
        f"release       {release.name} in {release.namespace}; "
        f"{release.api_replicas} replica(s) of {release.api_component} and "
        f"{release.runtime_replicas} of {release.runtime_component}"
    )
    print(
        f"service       {release.api_service_name}:{release.api_service_port}, "
        "addressed from inside the cluster so that the Service distributes"
    )
    print(
        f"capacity      engine at least {capacity.minimum_engine_cpus} cpus and "
        f"{capacity.minimum_engine_memory_bytes} bytes; the profile requests "
        f"{capacity.requested_cpu_millis} millicores and "
        f"{capacity.requested_memory_bytes} bytes and may peak at "
        f"{capacity.peak_memory_bytes} bytes"
    )
    print(
        f"readiness     install {budgets.install_ms} ms; runtime rollout "
        f"{budgets.runtime_rollout_ms} ms; api rollout {budgets.api_rollout_ms} ms; "
        f"release test {budgets.release_test_ms} ms; request set "
        f"{budgets.distribution_ms} ms"
    )
    print(
        f"distribution  {plan.request_count} POSTs to {plan.path} as "
        f"{plan.request_id_prefix}-001..{plan.request_count:03d}, correlated by "
        f"{plan.mechanism}, reaching at least {plan.minimum_distinct_replicas} "
        "distinct replicas"
    )
    print(
        f"driver        one {plan.driver_component} pod named {plan.driver_name}, "
        f"image {plan.driver_image}"
    )
    print(
        f"model cache   claim {certification.model_cache.claim_name}, mounted "
        f"read-only, verified by the '"
        f"{certification.model_cache.verification_init_container}' init container"
    )
    for entry in certification.clusters:
        pin = (
            f"the pinned node image {entry.node_image_digest}"
            if entry.node_image_pinned
            else "a node image the provider chooses, recorded but not pinned"
        )
        print(f"cluster       {entry.provider_id}: {entry.name} on {pin}")
    print(
        "assertions    every expected replica ready, every request successful "
        "with runtime-derived counts, one completion record per request, no "
        "request claimed twice, every serving pod a ready API replica, real "
        "adapter kind and pinned revision throughout; mock identity refused"
    )
    print(
        f"evidence      {certification.evidence_directory.as_posix()}/"
        f"{certification.result_file}; labelled {certification.evidence_label}; "
        "generated text never retained"
    )
    print(
        "cleanup       removes the request driver and uninstalls the release; "
        "removes neither the Terraform prerequisites nor the cluster"
    )
    for limitation in certification.limitations:
        print(f"limitation    {limitation}")
    print("execution     not started (offline certification validation only)")


def _print_capacity(
    certification: MultiReplicaCertification, facts: CapacityFacts
) -> None:
    need = certification.capacity
    print(
        f"engine        {facts.engine_cpus} cpus, {facts.engine_memory_bytes} "
        f"bytes (minimum {need.minimum_engine_cpus} cpus, "
        f"{need.minimum_engine_memory_bytes} bytes)"
    )
    print(
        f"cluster       {facts.node_count} schedulable node(s); "
        f"{facts.free_cpu_millis} millicores and {facts.free_memory_bytes} bytes "
        "uncommitted"
    )
    print(
        f"profile       {need.requested_cpu_millis} millicores and "
        f"{need.requested_memory_bytes} bytes requested, peaking at "
        f"{need.peak_memory_bytes} bytes, with {need.headroom_cpu_millis} "
        f"millicores and {need.headroom_memory_bytes} bytes of headroom"
    )


def _print_certified(result: MultiReplicaResult, record: str) -> None:
    certification = result.certification
    facts = result.facts
    release = certification.release
    print(
        f"certification {certification.certification_id} "
        f"({certification.certification_level}; {certification.evidence_class})"
    )
    print(f"evidence      labelled {certification.evidence_label}")
    print(
        f"cluster       {facts.provider}: {facts.cluster_name} on "
        f"{facts.server_version}; "
        f"release revision {facts.release_revision} of {facts.chart_version}"
    )
    ready = len(facts.ready_pods(release.api_component))
    print(
        f"replicas      {ready} of {release.api_replicas} platform API replicas "
        f"ready; {len(facts.ready_pods(release.runtime_component))} of "
        f"{release.runtime_replicas} serving runtime replicas ready"
    )
    print(
        f"requests      {len(result.observations.requests)} succeeded through the "
        f"API Service in {result.observations.elapsed_ms} ms; content not retained"
    )
    for replica in result.distribution:
        print(
            f"  replica     {replica.pod_name}: {replica.request_count} request(s), "
            f"ready after {replica.ready_after_ms} ms"
        )
    print(
        f"distribution  {len(result.distribution)} distinct API replicas, at "
        f"least {certification.distribution.minimum_distinct_replicas} required"
    )
    serving_plan = certification.runtime_distribution
    for entry in result.serving:
        print(
            f"  runtime     {entry.pod_name}: decoded {entry.decode_delta} "
            f"token(s), predicted {entry.predicted_token_delta}"
        )
    print(
        f"serving       {sum(1 for e in result.serving if e.decode_delta > 0)} "
        f"serving replicas ran the model, at least "
        f"{serving_plan.minimum_serving_replicas} required; per replica over the "
        "window, never per request"
    )
    if result.cleanup is not None:
        print(
            f"cleanup       release uninstalled in {result.cleanup.uninstall_ms} ms; "
            f"{result.cleanup.residue_objects} object(s) left; claims "
            f"{result.cleanup.claims_before} before and "
            f"{result.cleanup.claims_after} after"
        )
    print(f"record        {record}")


def _write_diagnostics(
    certification: MultiReplicaCertification, error: CertificationError
) -> str:
    """Store why the run stopped, or say plainly that storing it also failed."""
    diagnostics = Diagnostics(stage=error.stage, reason=str(error))
    try:
        evidence = MultiReplicaEvidence(certification, repo_root=_root())
        written = evidence.write(
            evidence.diagnostics_path, diagnostics_document(diagnostics)
        )
    except CertificationError:
        return "not written"
    return written.relative_to(evidence.root).as_posix()


def _run(args: argparse.Namespace, certification: MultiReplicaCertification) -> int:
    if args.command == "check":
        _print_check(certification)
        return EXIT_OK

    if args.command == "preflight":
        facts = load_capacity_facts(certification, repo_root=_root())
        findings = assess_capacity(certification, facts)
        _print_capacity(certification, facts)
        if findings:
            print(
                "REFUSED multi-replica certification at stage capacity: this host "
                "cannot hold the profile.",
                file=sys.stderr,
            )
            for finding in findings:
                print(f"  {finding}", file=sys.stderr)
            print(
                "  Nothing was installed. The replica count is not reduced to fit: "
                "a certification of fewer replicas than the profile requests is "
                "not this certification.",
                file=sys.stderr,
            )
            # Raised rather than returned, so that this refusal writes the same
            # diagnostics record every other refusal writes. A capacity refusal
            # is evidence -- it is the bounded answer a host that cannot hold the
            # profile is allowed to produce -- and until V1-S3-011 it produced
            # none: the detail above went to a terminal, and whatever
            # diagnostics file an earlier run had left behind stayed on disk as
            # the only record, describing a different run on a different day.
            #
            # `require_capacity` is what raises, rather than a second
            # construction of the same exception here, so that the refusal a
            # preflight reports and the refusal a certify run reports cannot
            # drift apart.
            require_capacity(certification, facts)
        print("capacity      sufficient; nothing has been installed")
        return EXIT_OK

    result = certify_multi_replica(
        certification, confirmed=args.confirm_real_kubernetes, repo_root=_root()
    )
    if args.command == "record-cleanup":
        result = MultiReplicaResult(
            certification=result.certification,
            capacity=result.capacity,
            facts=result.facts,
            observations=result.observations,
            distribution=result.distribution,
            counters=result.counters,
            serving=result.serving,
            cleanup=load_cleanup_facts(certification, repo_root=_root()),
        )
    evidence = MultiReplicaEvidence(certification, repo_root=_root())
    written = evidence.write(evidence.result_path, result_document(result))
    _print_certified(result, written.relative_to(evidence.root).as_posix())
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    certification: MultiReplicaCertification | None = None
    try:
        certification = load_multi_replica_certification()
        return _run(args, certification)
    except CertificationError as error:
        capacity = isinstance(error, CapacityUnmet)
        failed = isinstance(error, CertificationFailed)
        # Nothing was observed when the confirmation flag was absent, and a
        # diagnostics record for an unentered lane is noise rather than evidence.
        location = (
            _write_diagnostics(certification, error)
            if certification is not None and args.confirm_real_kubernetes
            else "not written"
        )
        label = "FAILED" if failed and not capacity else "REFUSED"
        print(
            f"{label} multi-replica Kubernetes certification at stage "
            f"{error.stage}: {error}",
            file=sys.stderr,
        )
        print(f"diagnostics   {location}", file=sys.stderr)
        if capacity:
            return EXIT_CAPACITY
        return EXIT_FAILED if failed else EXIT_REFUSED
    except KeyboardInterrupt:
        print(
            "STOPPED multi-replica certification: the operating script owns cleanup",
            file=sys.stderr,
        )
        return 130
    except Exception:
        print(
            "FAILED multi-replica certification: unexpected local failure",
            file=sys.stderr,
        )
        return EXIT_FAILED


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
