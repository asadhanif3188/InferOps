"""Behavioural checks of the provider-aware target guard in
scripts/environment/lib.sh -- the mechanism
docs/environment/local-cluster-provider-contract.md describes and
test_local_cluster_provider_contract.py reads only as text.

That module is explicit about what it cannot establish: "that a provider is
positively identified, or that a wrong cluster is refused, belongs to a layer
that contacts one." This module is that layer, without contacting a real
cluster. It sources the real lib.sh in a real bash subprocess -- Git Bash is
this project's committed shell, per docs/environment/local-cluster.md -- with
`kubectl`, `kind`, and `docker` replaced on `PATH` by small fake executables
whose answers a test controls through environment variables. Nothing here
starts a container, a cluster, or a network listener; every fake prints a
canned answer to a recognised argument shape and fails closed on anything else.

Every refusal `inferops::resolve_target` can produce is exercised at least once
for `kind`, and every one both providers can produce is exercised for
`docker-desktop` too, alongside one positive (successfully verified) case per
provider. `capability-unknown-or-insufficient` is exercised against
`inferops::target_load_image`, which dispatches on the verified provider's
image-preparation mechanism and must refuse one it does not implement rather than
fall through to whichever branch happens to be last.

The Docker Desktop cases are worth reading with the guard's own limits in mind.
V1-S3-011-PR1 established that the kind labels a check can read here are *not*
distinguishing -- an ordinary `kind create cluster --name desktop` reproduces
them exactly -- so the binding that carries the weight, and that the tests below
exercise in both directions, is that the node container must publish the very API
server port the verified kubeconfig dials. The residual same-name collision is
accepted as `EX-06` in docs/security/deferred-risks.md and is deliberately not
asserted here as though it were refused.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "scripts" / "environment" / "lib.sh"

# Resolved once through shutil.which, the same way
# tests/architecture/test_model_acquisition_job.py and
# tests/architecture/test_terraform_destroy_guard.py already do. Handing the bare
# string "bash" to subprocess.run instead lets Windows' own process search find
# its WSL launcher stub at System32\bash.exe ahead of Git Bash's real
# interpreter, and only the latter can run this project's scripts.
BASH = shutil.which("bash")

pytestmark = pytest.mark.architecture

# A realistic `kubectl version -o json` document: multi-line, one key per line,
# the shape inferops::resolve_target's awk-based parser is written against. A
# compact single-line document parses differently and would silently test the
# wrong thing.
MATCHING_VERSION_JSON = textwrap.dedent(
    """\
    {
      "clientVersion": {
        "major": "1",
        "minor": "34",
        "gitVersion": "v1.34.1"
      },
      "serverVersion": {
        "major": "1",
        "minor": "34",
        "gitVersion": "v1.34.8"
      }
    }
    """
)

# Eleven minor versions away from the fake server above -- comfortably past the
# one-minor-version skew ADR 0001 states -- for the client-outside-skew case.
SKEWED_VERSION_JSON = textwrap.dedent(
    """\
    {
      "clientVersion": {
        "major": "1",
        "minor": "23",
        "gitVersion": "v1.23.0"
      },
      "serverVersion": {
        "major": "1",
        "minor": "34",
        "gitVersion": "v1.34.8"
      }
    }
    """
)

FAKE_KUBECTL = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    # Fake kubectl. Understands only the shapes inferops::resolve_target uses.
    set -eu
    joined=" $* "
    case "$joined" in
      *" config get-contexts "*)
        printf '%s\\n' "${FAKE_OPERATOR_CONTEXTS:-}"
        exit 0
        ;;
    esac
    if [ "${1:-}" = "--context" ]; then
      ctx="${2:-}"
      found=0
      while IFS= read -r c; do
        [ "$c" = "$ctx" ] && found=1
      done <<<"${FAKE_OPERATOR_CONTEXTS:-}"
      [ "$found" -eq 1 ] || exit 1
      printf 'kind: Config\\ncurrent-context: %s\\n' "$ctx"
      exit 0
    fi
    case "$joined" in
      *"cluster.server"*)
        printf '%s\\n' "${FAKE_API_SERVER_URL-https://127.0.0.1:50351}"
        exit 0
        ;;
      *" config current-context"*)
        printf '%s\\n' "${FAKE_TARGET_CONTEXT:-}"
        exit 0
        ;;
      *" get nodes -o name"*)
        printf '%s\\n' "${FAKE_NODES:-}"
        exit 0
        ;;
      *" version "*)
        cat "${FAKE_VERSION_JSON_FILE:?FAKE_VERSION_JSON_FILE not set}"
        exit 0
        ;;
    esac
    exit 1
    """
)

FAKE_KIND = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    # Fake kind. Understands only `kind get clusters`.
    set -eu
    if [ "${1:-}" = "get" ] && [ "${2:-}" = "clusters" ]; then
      printf '%s\\n' "${FAKE_KIND_CLUSTERS:-}"
      exit 0
    fi
    exit 1
    """
)

FAKE_DOCKER = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    # Fake docker. Understands `docker ps` (kind's node-container lookup) and
    # `docker inspect` (Docker Desktop's, which has to ask by name because
    # Docker Desktop's API proxy filters its own containers out of `docker ps`),
    # and answers `info`/`version` with fixed values nothing here asserts on.
    #
    # FAKE_NODE_CONTAINER_LABELS maps a container name to its kind cluster and
    # role, one `name=cluster:role` per line. A name absent from it is a name
    # this engine has no container for, which is what `docker inspect` reports
    # by failing.
    set -eu
    joined=" $* "
    case "$joined" in
      *" ps "*)
        printf '%s\\n' "${FAKE_KIND_NODE_CONTAINERS:-}"
        exit 0
        ;;
      *" inspect "*)
        wanted=""
        for argument in "$@"; do
          case "$argument" in
            inspect | --format | -f | *'{{'*) ;;
            *) [ -n "$wanted" ] || wanted="$argument" ;;
          esac
        done
        entry="$(printf '%s\\n' "${FAKE_NODE_CONTAINER_LABELS:-}" |
          grep "^${wanted}=" || true)"
        [ -n "$entry" ] || exit 1
        value="${entry#*=}"
        case "$joined" in
          *"NetworkSettings.Ports"*)
            # One host port per published binding, space separated, the shape
            # the real `{{range}}` format produces.
            printf '%s\\n' "${FAKE_NODE_PUBLISHED_PORTS-50351 }"
            ;;
          *"io.x-k8s.kind.cluster"*) printf '%s\\n' "${value%%:*}" ;;
          *"io.x-k8s.kind.role"*) printf '%s\\n' "${value#*:}" ;;
          *) printf '%s\\n' "$value" ;;
        esac
        exit 0
        ;;
      *" info "*)
        printf '%s' "1"
        exit 0
        ;;
      *" version "*)
        printf '%s' "1.0.0"
        exit 0
        ;;
    esac
    exit 1
    """
)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture()
def fake_bin(tmp_path: Path) -> Path:
    """A directory holding fake kubectl, kind, and docker, all executable."""
    if BASH is None:
        pytest.skip("bash is not installed; these tests skip, loudly")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "kubectl", FAKE_KUBECTL)
    _write_executable(bin_dir / "kind", FAKE_KIND)
    _write_executable(bin_dir / "docker", FAKE_DOCKER)
    return bin_dir


def run_target(
    fake_bin: Path,
    tmp_path: Path,
    env: dict[str, str],
    command: str = "inferops::resolve_target",
) -> subprocess.CompletedProcess[str]:
    """Sources the real lib.sh and runs `command`, with fakes ahead on PATH.

    The project-scoped target kubeconfig is redirected into `tmp_path` rather
    than this checkout's real .kube/ directory -- lib.sh makes that path
    overridable for exactly this reason. PATH is Windows-style
    (os.pathsep-joined, native path separators): Git Bash's own runtime
    translates that transparently, the same way the fixtures in
    test_model_acquisition_job.py and test_terraform_destroy_guard.py already
    rely on it doing.
    """
    assert BASH is not None

    version_file = tmp_path / "version.json"
    if "FAKE_VERSION_JSON" in env:
        version_file.write_text(env.pop("FAKE_VERSION_JSON"), encoding="utf-8")
    elif not version_file.exists():
        version_file.write_text(MATCHING_VERSION_JSON, encoding="utf-8")

    child_env = dict(os.environ)
    ambient_path = child_env.get("PATH", "")
    child_env["PATH"] = os.pathsep.join([str(fake_bin), ambient_path])
    child_env["INFEROPS_TARGET_KUBECONFIG_POSIX_PATH"] = (
        tmp_path / "target.kubeconfig"
    ).as_posix()
    child_env["FAKE_VERSION_JSON_FILE"] = version_file.as_posix()
    child_env.update(env)

    script = f'source "{LIB_PATH.as_posix()}"; {command}'
    return subprocess.run(
        [BASH, "-c", script],
        capture_output=True,
        text=True,
        env=child_env,
        timeout=30,
        check=False,
    )


KIND_GOOD_ENV = {
    "INFEROPS_PROVIDER": "kind",
    "INFEROPS_KIND_CLUSTER_NAME": "inferops-dev",
    "FAKE_OPERATOR_CONTEXTS": "kind-inferops-dev",
    "FAKE_TARGET_CONTEXT": "kind-inferops-dev",
    "FAKE_NODES": "node/inferops-dev-control-plane",
    "FAKE_KIND_CLUSTERS": "inferops-dev",
    "FAKE_KIND_NODE_CONTAINERS": "inferops-dev-control-plane",
}

DOCKER_DESKTOP_GOOD_ENV = {
    "INFEROPS_PROVIDER": "docker-desktop",
    "FAKE_OPERATOR_CONTEXTS": "docker-desktop",
    "FAKE_NODES": "node/desktop-control-plane",
    # Docker Desktop provisions its Kubernetes with kind and labels the node
    # container for its own cluster, `desktop`. V1-S3-011 established that this
    # is observable from the operator's own engine, which is what closed
    # `the-nodes-are-bound-to-the-local-engine`.
    "FAKE_NODE_CONTAINER_LABELS": "desktop-control-plane=desktop:control-plane",
}


# --------------------------------------------------------------------------
# Positive cases: one verified target per provider
# --------------------------------------------------------------------------


def test_a_correctly_labelled_kind_target_verifies(
    fake_bin: Path, tmp_path: Path
) -> None:
    result = run_target(fake_bin, tmp_path, dict(KIND_GOOD_ENV))
    assert result.returncode == 0, result.stderr
    assert "provider=kind" in result.stdout
    assert "cluster=inferops-dev" in result.stdout
    assert "context=kind-inferops-dev" in result.stdout


def test_a_correctly_shaped_docker_desktop_target_verifies(
    fake_bin: Path, tmp_path: Path
) -> None:
    result = run_target(fake_bin, tmp_path, dict(DOCKER_DESKTOP_GOOD_ENV))
    assert result.returncode == 0, result.stderr
    assert "provider=docker-desktop" in result.stdout
    assert "cluster=docker-desktop" in result.stdout
    assert "context=docker-desktop" in result.stdout


def test_the_verified_target_reports_the_facts_certification_and_evidence_need(
    fake_bin: Path, tmp_path: Path
) -> None:
    """docs/environment/local-cluster-provider-contract.md's target-facts table."""
    command = (
        "inferops::resolve_target; "
        'echo "PROVIDER=$INFEROPS_TARGET_PROVIDER"; '
        'echo "CLUSTER=$INFEROPS_TARGET_CLUSTER_NAME"; '
        'echo "CONTEXT=$INFEROPS_TARGET_CONTEXT"; '
        'echo "SERVER=$INFEROPS_TARGET_SERVER_VERSION"; '
        'echo "NODES=$INFEROPS_TARGET_NODE_NAMES"; '
        'echo "IMAGEPREP=$INFEROPS_TARGET_IMAGE_PREPARATION"; '
        'echo "NETPOL=$INFEROPS_TARGET_NETWORK_POLICY_ENFORCEMENT"; '
        'echo "REVISION=$INFEROPS_TARGET_VERIFIED_REVISION"'
    )
    result = run_target(fake_bin, tmp_path, dict(KIND_GOOD_ENV), command=command)
    assert result.returncode == 0, result.stderr
    fields = dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )
    assert fields["PROVIDER"] == "kind"
    assert fields["CLUSTER"] == "inferops-dev"
    assert fields["CONTEXT"] == "kind-inferops-dev"
    assert fields["SERVER"] == "v1.34.8"
    assert fields["NODES"] == "inferops-dev-control-plane"
    assert fields["IMAGEPREP"] == "kind-load"
    assert fields["NETPOL"] == "not-enforced"
    assert fields["REVISION"], "verifiedRevision must not be empty"


# --------------------------------------------------------------------------
# Negative cases shared by both providers: the six-of-nine dispatcher
# --------------------------------------------------------------------------


def test_no_provider_selected_refuses(fake_bin: Path, tmp_path: Path) -> None:
    result = run_target(fake_bin, tmp_path, {})
    assert result.returncode != 0
    assert "no-provider-selected" in result.stderr


def test_unsupported_provider_refuses(fake_bin: Path, tmp_path: Path) -> None:
    result = run_target(fake_bin, tmp_path, {"INFEROPS_PROVIDER": "openshift"})
    assert result.returncode != 0
    assert "unsupported-provider" in result.stderr


def test_kind_with_no_cluster_name_is_ambiguous(fake_bin: Path, tmp_path: Path) -> None:
    result = run_target(fake_bin, tmp_path, {"INFEROPS_PROVIDER": "kind"})
    assert result.returncode != 0
    assert "ambiguous-target" in result.stderr


def test_kind_cluster_kind_does_not_list_is_missing(
    fake_bin: Path, tmp_path: Path
) -> None:
    env = dict(KIND_GOOD_ENV)
    env["FAKE_KIND_CLUSTERS"] = ""
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "target-missing" in result.stderr


def test_kind_named_twice_by_kind_is_ambiguous(fake_bin: Path, tmp_path: Path) -> None:
    """Defensive: kind cluster names are unique by construction, and this pins
    that a duplicate is still refused rather than silently accepted as one."""
    env = dict(KIND_GOOD_ENV)
    env["FAKE_KIND_CLUSTERS"] = "inferops-dev\ninferops-dev"
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "ambiguous-target" in result.stderr


def test_kind_target_unreachable_when_the_api_server_reports_no_nodes(
    fake_bin: Path, tmp_path: Path
) -> None:
    env = dict(KIND_GOOD_ENV)
    env["FAKE_NODES"] = ""
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "target-unreachable" in result.stderr


def test_kind_reports_provider_mismatch_for_a_node_kind_did_not_label(
    fake_bin: Path, tmp_path: Path
) -> None:
    """The attack ADR 0001 D5 was accepted against: a real foreign cluster
    wearing this project's context name, refused because its node carries no
    kind label for the selected cluster."""
    env = dict(KIND_GOOD_ENV)
    env["FAKE_KIND_NODE_CONTAINERS"] = ""
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "provider-mismatch" in result.stderr


def test_docker_desktop_with_no_context_is_missing(
    fake_bin: Path, tmp_path: Path
) -> None:
    env = dict(DOCKER_DESKTOP_GOOD_ENV)
    env["FAKE_OPERATOR_CONTEXTS"] = ""
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "target-missing" in result.stderr


def test_docker_desktop_context_listed_twice_is_ambiguous(
    fake_bin: Path, tmp_path: Path
) -> None:
    env = dict(DOCKER_DESKTOP_GOOD_ENV)
    env["FAKE_OPERATOR_CONTEXTS"] = "docker-desktop\ndocker-desktop"
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "ambiguous-target" in result.stderr


def test_docker_desktop_target_unreachable_when_the_api_server_reports_no_nodes(
    fake_bin: Path, tmp_path: Path
) -> None:
    env = dict(DOCKER_DESKTOP_GOOD_ENV)
    env["FAKE_NODES"] = ""
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "target-unreachable" in result.stderr


def test_docker_desktop_refuses_a_node_shape_it_has_not_observed(
    fake_bin: Path, tmp_path: Path
) -> None:
    """every-node-has-an-observed-docker-desktop-shape: a node set of any shape
    but the one this project recorded is refused rather than accepted because
    it might be legitimate."""
    env = dict(DOCKER_DESKTOP_GOOD_ENV)
    env["FAKE_NODES"] = "node/worker-1\nnode/worker-2"
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "provider-mismatch" in result.stderr


def test_a_docker_desktop_cluster_is_refused_when_kind_is_selected(
    fake_bin: Path, tmp_path: Path
) -> None:
    """provider-mismatch in the implemented direction: the reachable cluster is
    the other supported provider's."""
    env = dict(KIND_GOOD_ENV)
    env["FAKE_NODES"] = "node/desktop-control-plane"
    env["FAKE_KIND_NODE_CONTAINERS"] = ""
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "provider-mismatch" in result.stderr


@pytest.mark.parametrize("provider_env", [KIND_GOOD_ENV, DOCKER_DESKTOP_GOOD_ENV])
def test_client_outside_skew_refuses_for_both_providers(
    fake_bin: Path, tmp_path: Path, provider_env: dict[str, str]
) -> None:
    env = dict(provider_env)
    env["FAKE_VERSION_JSON"] = SKEWED_VERSION_JSON
    result = run_target(fake_bin, tmp_path, env)
    assert result.returncode != 0
    assert "client-outside-skew" in result.stderr


# --------------------------------------------------------------------------
# capability-unknown-or-insufficient: inferops::require_target_capability
# --------------------------------------------------------------------------


def test_each_provider_reports_the_image_preparation_it_actually_has(
    fake_bin: Path, tmp_path: Path
) -> None:
    """Before V1-S3-011 Docker Desktop's imagePreparation was
    `not-established` and `load` refused on it. The story established what the
    mechanism is: this cluster does not share the local engine's image store, so
    a load step is required, and `kind load` is not it -- Docker Desktop's API
    proxy filters the very node container `kind load` would have to find out of
    `docker ps`. The two providers now report two different implemented
    mechanisms rather than one mechanism and one gap."""
    command = "inferops::resolve_target && "
    command += 'printf "%s\\n" "$INFEROPS_TARGET_IMAGE_PREPARATION"'

    kind = run_target(fake_bin, tmp_path, dict(KIND_GOOD_ENV), command=command)
    desktop = run_target(
        fake_bin, tmp_path, dict(DOCKER_DESKTOP_GOOD_ENV), command=command
    )

    assert kind.returncode == 0, kind.stderr
    assert "kind-load" in kind.stdout
    assert desktop.returncode == 0, desktop.stderr
    assert "node-ctr-import" in desktop.stdout


def test_a_mechanism_this_project_does_not_implement_refuses_before_loading(
    fake_bin: Path, tmp_path: Path
) -> None:
    """inferops::target_load_image dispatches on the verified provider's
    mechanism, and a mechanism it has no branch for must refuse rather than fall
    through to whichever branch happened to be last."""
    command = (
        "inferops::resolve_target && "
        'INFEROPS_TARGET_IMAGE_PREPARATION="not-established" '
        "inferops::target_load_image localhost/x:dev localhost/x sha256:0"
    )
    result = run_target(
        fake_bin, tmp_path, dict(DOCKER_DESKTOP_GOOD_ENV), command=command
    )

    assert result.returncode != 0
    assert "capability-unknown-or-insufficient" in result.stderr


def test_a_node_the_local_engine_does_not_hold_is_refused(
    fake_bin: Path, tmp_path: Path
) -> None:
    """the-nodes-are-bound-to-the-local-engine, in the refusing direction. A
    reachable API server reporting a correctly named and shaped node that is not
    a container on this machine is not this machine's Docker Desktop, and a name
    and a shape alone must not certify it."""
    env = dict(DOCKER_DESKTOP_GOOD_ENV)
    env["FAKE_NODE_CONTAINER_LABELS"] = ""
    result = run_target(fake_bin, tmp_path, env)

    assert result.returncode != 0
    assert "provider-mismatch" in result.stderr


def test_an_operators_own_kind_node_is_not_accepted_as_docker_desktops(
    fake_bin: Path, tmp_path: Path
) -> None:
    """Selecting `docker-desktop` must not reach a kind cluster the operator
    created themselves, even one whose node they named `desktop-control-plane`.
    That cluster is selected as provider `kind`, by name.

    This refuses a kind cluster under any name *other* than Docker Desktop's own
    `desktop`. The same-name collision is not refusable from these labels and is
    recorded as EX-06 in docs/security/deferred-risks.md; the test below pins the
    binding that does the remaining work.
    """
    env = dict(DOCKER_DESKTOP_GOOD_ENV)
    env["FAKE_NODE_CONTAINER_LABELS"] = (
        "desktop-control-plane=somebody-elses:control-plane"
    )
    result = run_target(fake_bin, tmp_path, env)

    assert result.returncode != 0
    assert "provider-mismatch" in result.stderr


def test_a_cluster_reached_on_a_port_the_node_does_not_publish_is_refused(
    fake_bin: Path, tmp_path: Path
) -> None:
    """The binding the labels cannot give.

    `io.x-k8s.kind.cluster=desktop` is kind's own generic label and an ordinary
    `kind create cluster --name desktop` reproduces it exactly, so the labels
    alone cannot say which cluster is being talked to. The port can: the
    container that must answer is the one the verified kubeconfig actually
    dials. A reachable API server somewhere else -- remote, another engine, a
    second local cluster -- fails here even with a perfectly shaped node.
    """
    env = dict(DOCKER_DESKTOP_GOOD_ENV)
    env["FAKE_API_SERVER_URL"] = "https://127.0.0.1:6443"
    env["FAKE_NODE_PUBLISHED_PORTS"] = "50351 "
    result = run_target(fake_bin, tmp_path, env)

    assert result.returncode != 0
    assert "provider-mismatch" in result.stderr
    assert "not the container being inspected" in result.stderr


def test_a_node_publishing_no_api_server_port_is_refused(
    fake_bin: Path, tmp_path: Path
) -> None:
    """A container that publishes nothing cannot be the thing answering on the
    port the kubeconfig names, and an unpublished port is not an empty match."""
    env = dict(DOCKER_DESKTOP_GOOD_ENV)
    env["FAKE_NODE_PUBLISHED_PORTS"] = ""
    result = run_target(fake_bin, tmp_path, env)

    assert result.returncode != 0
    assert "provider-mismatch" in result.stderr


def test_a_kubeconfig_naming_no_port_is_refused(fake_bin: Path, tmp_path: Path) -> None:
    """An unanswered question is not a passing comparison: with no port to read,
    the binding cannot be established and the target is refused rather than
    accepted on the labels alone."""
    env = dict(DOCKER_DESKTOP_GOOD_ENV)
    env["FAKE_API_SERVER_URL"] = ""
    result = run_target(fake_bin, tmp_path, env)

    assert result.returncode != 0
    assert "target-unreachable" in result.stderr


def test_kind_has_the_image_preparation_capability_certification_needs(
    fake_bin: Path, tmp_path: Path
) -> None:
    command = (
        "inferops::resolve_target && "
        "inferops::require_target_capability imagePreparation kind-load "
        '"$INFEROPS_TARGET_IMAGE_PREPARATION" && echo CAPABILITY_OK'
    )
    result = run_target(fake_bin, tmp_path, dict(KIND_GOOD_ENV), command=command)
    assert result.returncode == 0, result.stderr
    assert "CAPABILITY_OK" in result.stdout
