"""Commands for the Kubernetes C2 certification of the installed release.

`check` reads committed files and contacts nothing: it prints what an authorized
run would do, which is the only thing that can be established without a cluster.
`observe` is the half that runs while a release is installed, and it is invoked
by `scripts/environment/kubernetes-certification.sh` rather than by hand -- that
script owns the cluster, the forward, and the cleanup, and this command refuses a
base URL that is not the loopback forward the script opened.

There is deliberately no flag naming the collected cluster facts. Their location
is the descriptor's, because the whole cluster half of the record is copied out
of that file: a flag there would make the base-URL guard decorative, since a run
could reach a real Service and describe an environment read from somewhere else.
"""

from __future__ import annotations

import argparse
import sys

from .core import (
    Certification,
    CertificationError,
    CertificationFailed,
    Diagnostics,
    EvidenceDirectory,
    KubernetesCertificationResult,
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
        prog="python -m tools.kubernetes_certification",
        description=(
            "Validate, or observe, the Kubernetes real-inference certification. "
            "No command installs a release, creates a cluster, or opens a "
            "forward, and `check` contacts nothing at all."
        ),
    )
    parser.add_argument("command", choices=("check", "observe"))
    parser.add_argument(
        "--confirm-real-kubernetes",
        action="store_true",
        help=(
            "confirm that this invocation may drive a real installed release, "
            "read a real model's answer, and produce a local real Kubernetes record"
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


def _print_check(certification: Certification) -> None:
    release = certification.release
    print(
        f"certification {certification.certification_id} "
        f"({certification.certification_level}; {certification.evidence_class})"
    )
    print(f"lane          {certification.lane}; outside the default check lane")
    print(f"chart         {certification.chart_ref}; profile {release.profile}")
    print(
        f"release       {release.name} in {release.namespace}; "
        f"{release.replicas} replica(s) of {release.api_component} and "
        f"{release.runtime_component}"
    )
    print(
        f"service       {release.api_service_name}:{release.api_service_port}, "
        f"forwarded to {certification.request_host}"
    )
    budgets = certification.budgets
    print(
        f"readiness     install {budgets.install_ms} ms; runtime startup "
        f"{budgets.runtime_startup_ms} ms within a {budgets.runtime_rollout_ms} ms "
        f"rollout; api startup {budgets.api_startup_ms} ms within a "
        f"{budgets.api_rollout_ms} ms rollout; release test "
        f"{budgets.release_test_ms} ms"
    )
    print(
        f"request       POST {certification.request_path}; identity GET "
        f"{certification.models_path}; budget {certification.request_timeout_ms} ms"
    )
    print(
        f"model cache   claim {certification.model_cache.claim_name}, mounted "
        f"read-only, verified by the '"
        f"{certification.model_cache.verification_init_container}' init container"
    )
    for target in certification.clusters:
        pin = (
            f"the pinned node image {target.node_image_digest}"
            if target.node_image_pinned
            else "a node image the provider chooses, recorded but not pinned"
        )
        print(f"cluster       {target.provider_id}: {target.name} on {pin}")
    print(
        "assertions    real adapter kind, pinned model revision, digest-pinned "
        "images, pinned node image, every replica ready, artifact hash compared "
        "in cluster, runtime-derived counts, non-empty content; mock identity "
        "refused"
    )
    print(
        f"evidence      {certification.evidence_directory.as_posix()}/"
        f"{certification.result_file}; labelled {certification.evidence_label}; "
        "generated text never retained"
    )
    print(
        "cleanup       uninstalls the release; removes neither the Terraform "
        "prerequisites nor the cluster"
    )
    print("execution     not started (offline certification validation only)")


def _print_certified(result: KubernetesCertificationResult, record: str) -> None:
    facts = result.facts
    print(
        f"certification {result.certification_id} "
        f"({result.certification_level}; {result.evidence_class})"
    )
    print(f"evidence      labelled {result.evidence_label}")
    print(
        f"cluster       {facts.provider}: {facts.cluster_name} on "
        f"{facts.server_version}; "
        f"release revision {facts.release_revision} of {facts.chart_version}"
    )
    print(
        f"readiness     prerequisites {facts.prerequisites_ms} ms; install "
        f"{facts.install_ms} ms; runtime {facts.runtime_ready_ms} ms; api "
        f"{facts.api_ready_ms} ms"
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
    print(f"record        {record}")


def _write_diagnostics(certification: Certification, error: CertificationError) -> str:
    """Store why the run stopped, or say plainly that storing it also failed."""
    diagnostics = Diagnostics(stage=error.stage, reason=str(error))
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
        result = certify(
            certification,
            confirmed=args.confirm_real_kubernetes,
            base_url=args.base_url,
        )
        evidence = EvidenceDirectory(certification)
        written = evidence.write(evidence.result_path, result_document(result))
        _print_certified(result, written.relative_to(evidence.root).as_posix())
    except CertificationError as error:
        failed = isinstance(error, CertificationFailed)
        # Nothing was observed when the confirmation flag was absent, and a
        # diagnostics record for an unentered lane is noise rather than evidence.
        location = (
            _write_diagnostics(certification, error)
            if certification is not None and args.confirm_real_kubernetes
            else "not written"
        )
        print(
            f"{'FAILED' if failed else 'REFUSED'} Kubernetes certification at stage "
            f"{error.stage}: {error}",
            file=sys.stderr,
        )
        print(f"diagnostics   {location}", file=sys.stderr)
        return EXIT_FAILED if failed else EXIT_REFUSED
    except KeyboardInterrupt:
        print(
            "STOPPED Kubernetes certification: the operating script owns cleanup",
            file=sys.stderr,
        )
        return 130
    except Exception:
        print(
            "FAILED Kubernetes certification: unexpected local failure", file=sys.stderr
        )
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    sys.exit(main())
