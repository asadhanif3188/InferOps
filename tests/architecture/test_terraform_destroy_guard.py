"""The Terraform destroy guard, executed rather than read.

`tests/architecture/test_terraform_prerequisites.py` checks that the wrapper
*says* the right things: that the string `is still installed in` appears in it,
that `--confirm` is demanded, that cluster identity is asserted. Every one of
those checks passed against a guard that failed open. They had to. A test that
greps a shell script for a reassuring sentence cannot tell a refusal that fires
from a refusal that is merely written down.

The defect they missed was this. The guard asked `helm status` and treated *any*
nonzero exit as "no release is installed". A nonzero exit from `helm status`
means the release is absent, or helm is not on PATH, or the API server is
unreachable, or RBAC forbids the read, or the release record will not
deserialise. Four of those five say the question went unanswered, and the guard
read all five as an answer of "nothing there" -- then let `terraform destroy`
run over a namespace that may still have held a release, taking it with the
cascade and leaving Helm's own record claiming it exists.

So this module runs the committed script. It copies the two shell files into a
sandbox laid out like the repository, puts a directory of recording stubs at the
front of `PATH`, and invokes `bash` on the real thing. `terraform`, `kubectl`,
`docker` and `helm` are all stubs that append their argument vector to a log,
which turns "did the destroy path execute?" into something a test reads off a
file rather than infers from an error message. No cluster is contacted, no
Terraform runs, and nothing outside the sandbox is touched.

The assertion that matters in every refusal case is the same one, and it is not
about wording: **no `terraform destroy` appears in the invocation log**. A guard
that prints an eloquent error and then destroys the namespace anyway fails these
tests, and that is precisely the failure the string-matching tests could not see.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = "scripts/environment/terraform-prerequisites.sh"
LIB_REL = "scripts/environment/lib.sh"

BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(
    BASH is None,
    reason="bash is not installed; the executable destroy-guard tests skip, loudly",
)

# The values lib.sh defines. Restated here on purpose: a fixture that imported
# them from lib.sh would agree with lib.sh by construction, and these tests have
# to notice if the guard starts asking about a different release or namespace.
RELEASE_NAME = "inferops"
RELEASE_NAMESPACE = "inferops-release"
KUBE_CONTEXT = "kind-inferops-dev"
CONTROL_PLANE = "inferops-dev-control-plane"

# `inferops::resolve_target` (docs/environment/local-cluster-provider-contract.md)
# now runs ahead of the destroy guard this module exists to test, and it selects
# `kind`/`inferops-dev` with no default -- exactly the target KUBE_CONTEXT and
# CONTROL_PLANE above already describe.
TARGET_PROVIDER = "kind"
TARGET_CLUSTER_NAME = "inferops-dev"

_VERSION_JSON = """{
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


# --------------------------------------------------------------------------
# The stubs
# --------------------------------------------------------------------------
#
# Each appends `<name> <arguments>` to $INFEROPS_STUB_LOG before doing anything
# else, so the log is a complete ordered record of what the script tried to run
# -- including the calls that then failed.

_TERRAFORM_STUB = """#!/usr/bin/env bash
printf 'terraform %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
exit 0
"""

_KUBECTL_STUB = """#!/usr/bin/env bash
printf 'kubectl %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
case "$*" in
  *"config get-contexts"*)
    printf '%s\\n' "${STUB_CONTEXT}"
    ;;
  *"config view --minify"*)
    printf 'kind: Config\\ncurrent-context: %s\\n' "${STUB_CONTEXT}"
    ;;
  *"config current-context"*)
    printf '%s\\n' "${STUB_CONTEXT}"
    ;;
  *"get nodes"*)
    printf 'node/%s\\n' "${STUB_NODE}"
    ;;
  *"version"*)
    printf '%s' "${STUB_VERSION_JSON}"
    ;;
esac
exit 0
"""

_KIND_STUB = """#!/usr/bin/env bash
printf 'kind %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
case "$*" in
  "get clusters")
    printf '%s\\n' "${STUB_KIND_CLUSTERS:-inferops-dev}"
    ;;
esac
exit 0
"""

_DOCKER_STUB = """#!/usr/bin/env bash
printf 'docker %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
case "$1" in
  version) printf '27.0.0\\n' ;;
  ps) printf '%s\\n' "${STUB_KIND_NODE}" ;;
  info) printf '\\n' ;;
esac
exit 0
"""

# The helm stub is where the scenarios live. Every branch writes to the stream a
# real helm writes to: an error goes to stderr with a nonzero exit, a listing
# goes to stdout with exit 0.
#
# `pending` is the branch that proves `--all` is passed rather than assumed. It
# answers as a `helm list` *without* `--all` would -- reporting nothing,
# successfully -- unless the flag is actually present, in which case it reports
# the release that is really sitting there mid-upgrade. A script that dropped
# `--all` would read that empty successful listing as absence and destroy a
# namespace with a release in it, so dropping the flag fails this test instead
# of passing it quietly.
_HELM_STUB = """#!/usr/bin/env bash
printf 'helm %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"

asked_for_all=0
for arg in "$@"; do
  if [ "${arg}" = "--all" ]; then
    asked_for_all=1
  fi
done

case "${STUB_HELM_MODE}" in
  present)
    printf 'inferops\\n'
    ;;
  absent)
    : # a successful listing of nothing, which is what absence looks like
    ;;
  pending)
    if [ "${asked_for_all}" -eq 1 ]; then
      printf 'inferops\\n'
    fi
    ;;
  foreign-release)
    printf 'someone-elses-thing\\n'
    ;;
  authfail)
    printf 'Error: query: failed to query with labels: secrets is forbidden\\n' >&2
    exit 1
    ;;
  transportfail)
    printf 'Error: Kubernetes cluster unreachable: dial tcp 127.0.0.1:6443: connection refused\\n' >&2
    exit 1
    ;;
  unreadable)
    printf 'Error: release: not loadable: unexpected end of JSON input\\n' >&2
    exit 1
    ;;
  malformed)
    printf '<html><title>502 Bad Gateway</title></html>\\n'
    ;;
  noisy)
    printf 'WARNING: Kubernetes configuration file is group-readable.\\n' >&2
    ;;
  *)
    printf 'stub misconfigured: %s\\n' "${STUB_HELM_MODE}" >&2
    exit 99
    ;;
esac
exit 0
"""

_STUBS = {
    "terraform": _TERRAFORM_STUB,
    "kubectl": _KUBECTL_STUB,
    "kind": _KIND_STUB,
    "docker": _DOCKER_STUB,
    "helm": _HELM_STUB,
}


class Run:
    """One execution of the wrapper, and what it actually did."""

    def __init__(self, completed: subprocess.CompletedProcess[str], log: Path) -> None:
        self.returncode = completed.returncode
        self.stdout = completed.stdout
        self.stderr = completed.stderr
        self.calls = [
            line for line in log.read_text(encoding="utf-8").splitlines() if line
        ]

    @property
    def output(self) -> str:
        return self.stdout + self.stderr

    @property
    def refused(self) -> bool:
        return self.returncode != 0

    def invoked(self, command: str, *fragments: str) -> bool:
        """Did any recorded call run `command` with all of `fragments` present?"""
        prefix = f"{command} "
        return any(
            line.startswith(prefix) and all(f in line for f in fragments)
            for line in self.calls
        )

    @property
    def destroyed(self) -> bool:
        """The one question every refusal test in this module asks."""
        return self.invoked("terraform", "destroy")


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A directory laid out like the repository, holding the committed scripts.

    The wrapper derives its root from its own location -- `dirname
    ${BASH_SOURCE[0]}/../..` -- so a copy two directories below the sandbox root
    treats the sandbox as the repository. That is what keeps these runs off the
    real tree: the artifact directory it writes, the kubeconfig it checks for and
    the Terraform environment it looks up are all the sandbox's own.

    The scripts are copied byte for byte. Nothing here edits, trims or re-stages
    them, because a test that runs an adapted copy of a safety guard certifies
    the adaptation and not the guard.
    """
    sandbox_scripts = tmp_path / "scripts" / "environment"
    sandbox_scripts.mkdir(parents=True)
    for rel in (LIB_REL, SCRIPT_REL):
        shutil.copyfile(REPO_ROOT / rel, sandbox_scripts / Path(rel).name)

    # The wrapper refuses without a project kubeconfig and asserts the Terraform
    # environment directory exists. No stub reads either, so both are empty.
    (tmp_path / ".kube").mkdir()
    (tmp_path / ".kube" / "inferops-dev.config").write_text("", encoding="utf-8")
    env_dir = tmp_path / "infra" / "terraform" / "environments" / "local"
    env_dir.mkdir(parents=True)
    (env_dir / "main.tf").write_text("", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in _STUBS.items():
        stub = bin_dir / name
        stub.write_text(body, encoding="utf-8", newline="\n")
        stub.chmod(0o755)

    return tmp_path


def run_wrapper(
    sandbox: Path,
    *args: str,
    helm_mode: str = "absent",
    helm_on_path: bool = True,
    context: str = KUBE_CONTEXT,
    api_node: str = CONTROL_PLANE,
    kind_node: str = CONTROL_PLANE,
) -> Run:
    """Execute the committed wrapper inside the sandbox and report what it ran."""
    if not helm_on_path:
        (sandbox / "bin" / "helm").unlink()

    log = sandbox / "calls.log"
    log.write_text("", encoding="utf-8")

    env = dict(os.environ)
    # The stub directory and the shell's own toolbox, and nothing else. Prepending
    # to the inherited PATH would leave whatever this host happens to have
    # installed reachable behind the stubs -- and this host does have a real
    # `helm` -- so the "helm is unavailable" scenario would silently run the real
    # binary and certify nothing. A closed PATH makes the stubs the only external
    # commands that exist, which is the only way a test about a missing executable
    # can mean anything.
    assert BASH is not None
    env["PATH"] = os.pathsep.join([str(sandbox / "bin"), str(Path(BASH).parent)])
    env["INFEROPS_STUB_LOG"] = str(log)
    env["STUB_HELM_MODE"] = helm_mode
    env["STUB_CONTEXT"] = context
    env["STUB_NODE"] = api_node
    env["STUB_KIND_NODE"] = kind_node
    env["STUB_VERSION_JSON"] = _VERSION_JSON
    # The provider-aware target every mutating workflow now requires explicitly
    # (docs/environment/local-cluster-provider-contract.md), and the
    # project-scoped kubeconfig it writes, redirected into the sandbox rather
    # than this checkout's real .kube/ directory.
    env["INFEROPS_PROVIDER"] = TARGET_PROVIDER
    env["INFEROPS_KIND_CLUSTER_NAME"] = TARGET_CLUSTER_NAME
    env["INFEROPS_TARGET_KUBECONFIG_POSIX_PATH"] = (
        sandbox / ".kube" / "inferops-target.config"
    ).as_posix()

    # A relative script path with a working directory, rather than an absolute
    # one: `dirname` inside the script is POSIX and a Windows path reaching it
    # would collapse to `.` and root the run in the wrong place.
    completed = subprocess.run(
        [BASH, SCRIPT_REL, *args],
        cwd=sandbox,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return Run(completed, log)


# --------------------------------------------------------------------------
# The harness has to be trustworthy before its negative results mean anything
# --------------------------------------------------------------------------


@needs_bash
def test_the_sandbox_reaches_the_destroy_path_at_all(sandbox: Path) -> None:
    """The control case.

    Every other test here asserts that `terraform destroy` did *not* run. That
    assertion is worth nothing if the sandbox could never have reached it, so one
    test establishes that it can: a successful listing showing no release, with
    `--confirm`, destroys. If this test ever fails, every negative result below
    stops meaning anything and should be read as broken rather than as passing.
    """
    run = run_wrapper(sandbox, "destroy", "--confirm", helm_mode="absent")
    assert run.returncode == 0, run.output
    assert run.destroyed, run.calls
    assert run.invoked("terraform", "-auto-approve"), run.calls


@needs_bash
def test_the_release_query_goes_through_the_scoped_helm_wrapper(sandbox: Path) -> None:
    """The query must not inherit an ambient kubeconfig or context.

    Every helm call in these scripts goes through `inferops::helm` so that none
    of them can reach a cluster the project does not own. The guard's query is no
    exception, and for a sharper reason than most: if it read a *different*
    cluster's releases, an empty answer would be perfectly true and completely
    irrelevant to the namespace about to be destroyed.
    """
    run = run_wrapper(sandbox, "destroy", "--confirm", helm_mode="absent")
    assert run.invoked("helm", "--kubeconfig", "--kube-context", KUBE_CONTEXT, "list")
    assert run.invoked("helm", "--namespace", RELEASE_NAMESPACE), run.calls


# --------------------------------------------------------------------------
# 1. A release is installed
# --------------------------------------------------------------------------


@needs_bash
def test_an_installed_release_refuses_and_destroys_nothing(sandbox: Path) -> None:
    run = run_wrapper(sandbox, "destroy", "--confirm", helm_mode="present")
    assert run.refused, run.output
    assert not run.destroyed, run.calls
    assert "is still installed in" in run.output


@needs_bash
def test_another_partys_release_in_the_namespace_also_refuses(sandbox: Path) -> None:
    """The cascade is indifferent to whose release it takes.

    The namespace goes as a unit. A release this project did not install is
    destroyed by that just as thoroughly, and its Helm record is left claiming it
    exists just as wrongly.
    """
    run = run_wrapper(sandbox, "destroy", "--confirm", helm_mode="foreign-release")
    assert run.refused, run.output
    assert not run.destroyed, run.calls
    assert "someone-elses-thing" in run.output


# --------------------------------------------------------------------------
# 2 and 7. Absence, and what still has to be true once it is established
# --------------------------------------------------------------------------


@needs_bash
def test_established_absence_without_confirmation_refuses(sandbox: Path) -> None:
    """Absence is necessary and not sufficient."""
    run = run_wrapper(sandbox, "destroy", helm_mode="absent")
    assert run.refused, run.output
    assert not run.destroyed, run.calls
    assert "--confirm" in run.output


@needs_bash
def test_a_routine_helm_warning_is_not_mistaken_for_a_release(sandbox: Path) -> None:
    """A guard that refuses on every stray warning is a guard that gets disabled.

    Helm writes advisories -- a group-readable kubeconfig, most commonly -- to
    stderr on calls that succeed. Those must not arrive on the same stream as the
    release names, or a correct empty listing would be read as unparseable output
    and a legitimate teardown would refuse for no reason. The script sends stderr
    to a diagnostic file for exactly this, and this test holds it there.
    """
    run = run_wrapper(sandbox, "destroy", "--confirm", helm_mode="noisy")
    assert run.returncode == 0, run.output
    assert run.destroyed, run.calls


# --------------------------------------------------------------------------
# 3. Helm is not available
# --------------------------------------------------------------------------


@needs_bash
def test_helm_absent_from_path_refuses_and_destroys_nothing(sandbox: Path) -> None:
    """The review's reproduction case, in the form the script now takes.

    Under the old guard this was the worst of the five. `helm` missing from PATH
    made `helm status` exit nonzero, the guard read that as absence, and
    `--confirm` carried execution into `terraform destroy` having established
    precisely nothing about the namespace it was about to remove.
    """
    run = run_wrapper(sandbox, "destroy", "--confirm", helm_on_path=False)
    assert run.refused, run.output
    assert not run.destroyed, run.calls
    assert "helm" in run.output
    assert not run.invoked("helm"), run.calls


# --------------------------------------------------------------------------
# 4, 5 and 6. The query ran and did not answer
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "expected_fragment"),
    (
        pytest.param("authfail", "forbidden", id="authorization-failure"),
        pytest.param("transportfail", "unreachable", id="transport-failure"),
        pytest.param("unreadable", "not loadable", id="unreadable-release-record"),
    ),
)
@needs_bash
def test_a_failed_inspection_refuses_and_destroys_nothing(
    sandbox: Path, mode: str, expected_fragment: str
) -> None:
    """An unanswered query is not an empty namespace.

    Each of these is a distinct real failure -- RBAC, the API server, a release
    secret that will not deserialise -- and each was indistinguishable from "no
    release installed" because all three exit nonzero. The refusal has to quote
    what Helm actually said, too: an operator told only "refusing" cannot tell a
    permissions problem from a cluster that is down, and will retry the wrong fix.
    """
    run = run_wrapper(sandbox, "destroy", "--confirm", helm_mode=mode)
    assert run.refused, run.output
    assert not run.destroyed, run.calls
    assert expected_fragment in run.output, run.output


@needs_bash
def test_unparseable_listing_output_refuses_and_destroys_nothing(sandbox: Path) -> None:
    """Output the script cannot read is not evidence that the namespace is empty.

    A proxy interposing an error page; a helm build printing something
    unexpected. The exit status says success and the content says nothing this
    script understands. A release name is a Kubernetes name, and a line that is
    not one stops the teardown rather than being skipped past as noise.
    """
    run = run_wrapper(sandbox, "destroy", "--confirm", helm_mode="malformed")
    assert run.refused, run.output
    assert not run.destroyed, run.calls
    assert "not a release name" in run.output


# --------------------------------------------------------------------------
# 8. The cluster is not this project's cluster
# --------------------------------------------------------------------------


@needs_bash
def test_an_unexpected_context_refuses_before_anything_is_queried(
    sandbox: Path,
) -> None:
    run = run_wrapper(
        sandbox, "destroy", "--confirm", context="docker-desktop", helm_mode="absent"
    )
    assert run.refused, run.output
    assert not run.destroyed, run.calls
    assert not run.invoked("helm", "list"), run.calls


@needs_bash
def test_a_cluster_reporting_foreign_nodes_refuses_and_destroys_nothing(
    sandbox: Path,
) -> None:
    """A context name is a label a human chose; the nodes are the evidence.

    A context can be called `kind-inferops-dev` and reach something else
    entirely. What the API server reports has to be containers kind itself
    labelled for this cluster, and here it is not.
    """
    run = run_wrapper(
        sandbox,
        "destroy",
        "--confirm",
        api_node="prod-control-plane-0",
        kind_node=CONTROL_PLANE,
        helm_mode="absent",
    )
    assert run.refused, run.output
    assert not run.destroyed, run.calls


# --------------------------------------------------------------------------
# 9. A release that is present but not healthy
# --------------------------------------------------------------------------


@needs_bash
def test_a_pending_release_is_seen_because_all_states_are_listed(
    sandbox: Path,
) -> None:
    """`helm list` without `--all` reports deployed releases and no others.

    A failed install, a pending upgrade, a rollback in progress, an uninstall
    that did not finish: the namespace cascade takes every one of them, and a
    listing restricted to healthy releases would report the namespace empty while
    one sat in it -- which is the same fail-open shape as the original defect,
    relocated from the exit code into the query.
    """
    run = run_wrapper(sandbox, "destroy", "--confirm", helm_mode="pending")
    assert run.refused, run.output
    assert not run.destroyed, run.calls
    assert run.invoked("helm", "--all"), run.calls


# --------------------------------------------------------------------------
# The shape of the guard, which no single scenario demonstrates
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidate", ("--force", "--yes", "--skip-release-check", "-f", "--no-verify")
)
@needs_bash
def test_no_argument_bypasses_the_guard(sandbox: Path, candidate: str) -> None:
    """There is no `--force`, and adding one would fail here.

    The wrapper accepts `check`, `plan`, `apply`, `destroy` and `--confirm`, and
    rejects everything else by name. This asserts the rejection rather than the
    absence of a string, so a future flag that did skip the release query would
    have to be added to this list to make it pass -- which is a deliberate act
    with a reviewer attached, rather than an accident.
    """
    run = run_wrapper(sandbox, "destroy", "--confirm", candidate, helm_mode="present")
    assert run.refused, f"{candidate}: {run.output}"
    assert not run.destroyed, f"{candidate}: {run.calls}"


def test_the_guard_asks_for_releases_rather_than_one_releases_status() -> None:
    """The source-level half of the fix, recorded once.

    The behavioural tests above establish what the guard does. This one records
    why the call is shaped as it is, so that a refactor back to `helm status` --
    which cannot separate absence from failure by exit code alone -- has to
    delete a test that says so.
    """
    body = (REPO_ROOT / SCRIPT_REL).read_text(encoding="utf-8")
    assert "inferops::target_helm list --all" in body
    assert "inferops::helm status" not in body
