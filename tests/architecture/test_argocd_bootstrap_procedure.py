"""The Argo CD bootstrap procedure, executed against recording stubs.

`tests/architecture/test_argocd_bootstrap.py` reads the script as text. A test
that reads a script cannot tell a refusal that fires from one that is written
down. This module runs the committed script.

It copies the script and `lib.sh` into a sandbox laid out like the repository,
puts a directory of stubs at the front of a closed `PATH`, and invokes `bash` on
the real file. `kubectl`, `kind`, `docker`, and `curl` are stubs. Each stub
appends its arguments to a log, so "did a mutation run?" is read from a file.
No cluster is contacted, no network is used, and nothing outside the sandbox is
written.

The assertion in a refusal case is that **no mutating `kubectl` call is in the
log**, where a mutating call is any call that is not one of the reads the
procedure is known to make. A guard that prints a refusal and then applies the
manifest fails these tests. One refusal is different by design: the removal
checks for a custom resource a second time after it deletes the four workloads,
and the test for it asserts that nothing else was deleted.

What this module does not establish:

* That the procedure installs Argo CD. The stubs answer what a test tells them
  to answer. A run on a cluster is the evidence for that.
* That the real `sha256sum` accepts the real manifest. A test cannot hold bytes
  with the pinned SHA-256, because the manifest is not committed. The tests of
  the path after the digest check replace `sha256sum` with a stub that reports
  the pin. The first version of this module had no such tests, and said so; the
  namespace creation, the apply, and their order ran only on a cluster.
* A wait that reaches its time limit. The stubs let a pod or the namespace stay
  for a few polls and then go. No test waits 300 seconds.
* A query that fails inside the residue check. The stub fails a named query
  every time, and the same queries must answer earlier in the removal.
* The real `curl`. The stub is a shell script. It did not reproduce the path
  defect that the first run on Windows exposed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = "scripts/environment/argocd-bootstrap.sh"
LIB_REL = "scripts/environment/lib.sh"

BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(
    BASH is None,
    reason="bash is not installed; the executed bootstrap tests skip, loudly",
)

# Restated on purpose. A fixture that imported these from the script would agree
# with the script by construction.
NAMESPACE = "argocd"
PIN = "1a87025d8eb2eae621653fd312fb9ca51df1b4b3b6992a030e3a9ef38e45c448"
ARGOCD_DIGEST = (
    "sha256:dd3f47d5a5e4da563a7a398506e892481b358a7cec50abdf320c71aa55904bfa"
)
REDIS_DIGEST = "sha256:08ad0b1d280850169a790dba1393ff7a90aef951fc19632cf4d3ce4f78e679ba"
OTHER_DIGEST = "sha256:" + "0" * 64

MARKED = f"Active|bootstrap|{PIN}"
CLUSTER_OBJECTS = "\n".join(
    (
        "customresourcedefinition.apiextensions.k8s.io/applications.argoproj.io",
        "customresourcedefinition.apiextensions.k8s.io/applicationsets.argoproj.io",
        "customresourcedefinition.apiextensions.k8s.io/appprojects.argoproj.io",
        "clusterrole.rbac.authorization.k8s.io/argocd-application-controller",
        "clusterrolebinding.rbac.authorization.k8s.io/argocd-application-controller",
    )
)
PINNED_STATUSES = "\n".join(
    (
        f"argocd-application-controller quay.io/argoproj/argocd@{ARGOCD_DIGEST}",
        f"argocd-applicationset-controller quay.io/argoproj/argocd@{ARGOCD_DIGEST}",
        f"secret-init quay.io/argoproj/argocd@{ARGOCD_DIGEST}",
        f"redis public.ecr.aws/docker/library/redis@{REDIS_DIGEST}",
        f"copyutil quay.io/argoproj/argocd@{ARGOCD_DIGEST}",
        f"argocd-repo-server quay.io/argoproj/argocd@{ARGOCD_DIGEST}",
    )
)

KUBE_CONTEXT = "kind-inferops-dev"
CONTROL_PLANE = "inferops-dev-control-plane"

# The kubectl calls that change nothing, as the first words after the pinned
# flags. Every other call counts as a mutation. The first version of this module
# listed eight mutating verbs instead, so a refusal path that ran `rollout
# restart`, `exec`, `set`, or `config use-context` would have shown no mutation.
READ_CALLS = (
    ("get",),
    ("describe",),
    ("version",),
    ("rollout", "status"),
    ("config", "get-contexts"),
    ("config", "view"),
    ("config", "current-context"),
)


def version_json(minor: str) -> str:
    return (
        '{\n  "clientVersion": {\n    "major": "1",\n'
        f'    "minor": "{minor}",\n    "gitVersion": "v1.{minor}.1"\n  }},\n'
        '  "serverVersion": {\n    "major": "1",\n'
        f'    "minor": "{minor}",\n    "gitVersion": "v1.{minor}.3"\n  }}\n}}\n'
    )


# --------------------------------------------------------------------------
# The stubs
# --------------------------------------------------------------------------
#
# The kubectl stub logs the call, then fails it when the test named it in
# STUB_FAIL_ON, then answers from the environment. After a `delete namespace`
# call is in the log, the cluster-scoped objects are gone, and the namespace is
# gone after STUB_RESIDUE_POLLS more reads of it. Pods are reported for the
# first STUB_PODS_POLLS reads. `create -f -` logs what it was given on stdin.

_KUBECTL_STUB = """#!/usr/bin/env bash
# Each branch reads the log only when its answer depends on an earlier call. A
# stub that read it on every call made this suite several times slower on Windows.
# The current call is already in the log when a branch counts, so a count of
# reads includes this one.
logged() { grep -q "$1" "${INFEROPS_STUB_LOG}" 2>/dev/null; }
printf 'kubectl %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
if [ -n "${STUB_FAIL_ON:-}" ]; then
  case "$*" in
    *"${STUB_FAIL_ON}"*)
      printf 'Error from server (ServiceUnavailable): the server is currently unable to handle the request\\n' >&2
      exit 1
      ;;
  esac
fi
case "$*" in
  *"config get-contexts"*) printf '%s\\n' "${STUB_CONTEXT}" ;;
  *"config view --minify"*) printf 'kind: Config\\ncurrent-context: %s\\n' "${STUB_CONTEXT}" ;;
  *"config current-context"*) printf '%s\\n' "${STUB_CONTEXT}" ;;
  *"get namespace argocd"*)
    if ! logged ' delete namespace '; then
      printf '%s' "${STUB_NAMESPACE:-}"
    else
      reads="$(sed -n '/ delete namespace /,$p' "${INFEROPS_STUB_LOG}" | grep -c 'get namespace argocd' || true)"
      [ "${reads}" -gt "${STUB_RESIDUE_POLLS:-0}" ] || printf '%s' "${STUB_NAMESPACE:-}"
    fi
    ;;
  *"get customresourcedefinition/"*)
    if logged ' delete namespace '; then
      :
    elif logged ' apply '; then
      printf '%s' "${STUB_CLUSTER_OBJECTS_AFTER_APPLY:-${STUB_CLUSTER_OBJECTS:-}}"
    else
      printf '%s' "${STUB_CLUSTER_OBJECTS:-}"
    fi
    ;;
  *"create -f -"*)
    sed 's/^/kubectl-stdin /' >>"${INFEROPS_STUB_LOG}"
    printf 'namespace/argocd created\\n'
    ;;
  *"apply --server-side"*)
    i=0
    while [ "${i}" -lt "${STUB_APPLIED_COUNT:-34}" ]; do
      printf 'object/%s serverside-applied\\n' "${i}"
      i=$((i + 1))
    done
    ;;
  *"get applications.argoproj.io --all-namespaces"*)
    printf '%s' "${STUB_APPLICATIONS:-}"
    if [ -n "${STUB_APPLICATIONS_AFTER_STOP:-}" ] && logged ' delete statefulset '; then
      printf '%s' "${STUB_APPLICATIONS_AFTER_STOP}"
    fi
    ;;
  *"get appprojects.argoproj.io --all-namespaces"*) printf '%s' "${STUB_PROJECTS:-}" ;;
  *"get applicationsets.argoproj.io --all-namespaces"*) printf '%s' "${STUB_APPLICATION_SETS:-}" ;;
  *"get pods -n argocd -o name"*)
    if [ "${STUB_PODS_POLLS:-0}" -gt 0 ]; then
      reads="$(grep -c 'get pods -n argocd -o name' "${INFEROPS_STUB_LOG}" || true)"
      [ "${reads}" -gt "${STUB_PODS_POLLS}" ] || printf 'pod/argocd-redis-0\\n'
    fi
    ;;
  *"get pods -n argocd -o jsonpath"*) printf '%s\\n' "${STUB_STATUSES:-}" ;;
  *"get serviceaccount/"*)
    i=0
    while [ "${i}" -lt "${STUB_NAMESPACED_COUNT:-29}" ]; do
      printf 'object/%s\\n' "${i}"
      i=$((i + 1))
    done
    ;;
  *"get secrets,leases,configmaps"*) printf 'secret/argocd-secret\\n' ;;
  *"rollout status"*) printf 'rolled out\\n' ;;
  *"get nodes"*) printf 'node/%s\\n' "${STUB_NODE}" ;;
  *"version"*) printf '%s' "${STUB_VERSION_JSON}" ;;
esac
exit 0
"""

_KIND_STUB = """#!/usr/bin/env bash
printf 'kind %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
case "$*" in
  "get clusters") printf '%s\\n' "${STUB_KIND_CLUSTERS:-inferops-dev}" ;;
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

# The download. It writes what the test tells it to write to the path after
# `--output`, or fails as an unreachable host does.
_CURL_STUB = """#!/usr/bin/env bash
printf 'curl %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
if [ "${STUB_CURL_MODE:-tampered}" = "unreachable" ]; then
  printf 'curl: (6) Could not resolve host\\n' >&2
  exit 6
fi
target=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output" ]; then
    target="$2"
  fi
  shift
done
printf 'kind: ConfigMap\\n' >"${target}"
exit 0
"""

# Stands in for `sha256sum` in the tests that need the path after the digest
# check. It reports the pin for the manifest, until the read numbered
# STUB_SHA_FLIP_AT, and another digest for any other file. It is installed only
# when a test asks for it; every other test runs the real tool.
_SHA256SUM_STUB = (
    """#!/usr/bin/env bash
case "$1" in
  *core-install.yaml)
    printf 'sha256sum-manifest\\n' >>"${INFEROPS_STUB_LOG}"
    reads="$(grep -c '^sha256sum-manifest$' "${INFEROPS_STUB_LOG}")"
    if [ -n "${STUB_SHA_FLIP_AT:-}" ] && [ "${reads}" -ge "${STUB_SHA_FLIP_AT}" ]; then
      digest="@OTHER@"
    else
      digest="@PIN@"
    fi
    ;;
  *) digest="@SCRIPT@" ;;
esac
printf '%s *%s\\n' "${digest}" "$1"
""".replace("@PIN@", PIN)
    .replace("@OTHER@", "0" * 64)
    .replace("@SCRIPT@", "a" * 64)
)

_STUBS = {
    "kubectl": _KUBECTL_STUB,
    "kind": _KIND_STUB,
    "docker": _DOCKER_STUB,
    "curl": _CURL_STUB,
}


class Run:
    """One execution of the script, and what it actually ran."""

    def __init__(self, completed: subprocess.CompletedProcess[str], log: Path) -> None:
        self.returncode = completed.returncode
        self.output = completed.stdout + completed.stderr
        self.calls = [
            line for line in log.read_text(encoding="utf-8").splitlines() if line
        ]

    @property
    def refused(self) -> bool:
        return self.returncode != 0

    def kubectl_calls(self, *verbs: str) -> list[str]:
        """Every logged kubectl call whose subcommand is one of `verbs`.

        The subcommand is the first word after the two flags the wrapper pins,
        so a resource named `create` or a path holding `apply` is not counted.
        """
        found = []
        for line in self.calls:
            words = line.split()
            if words[0] != "kubectl":
                continue
            rest = [word for word in words[1:]]
            while rest and rest[0] in ("--kubeconfig", "--context"):
                rest = rest[2:]
            if rest and rest[0] in verbs:
                found.append(line)
        return found

    @property
    def mutations(self) -> list[str]:
        """Every logged kubectl call that is not a known read."""
        found = []
        for line in self.calls:
            words = line.split()
            if words[0] != "kubectl":
                continue
            rest = words[1:]
            while rest and rest[0] in ("--kubeconfig", "--context"):
                rest = rest[2:]
            if not any(tuple(rest[: len(read)]) == read for read in READ_CALLS):
                found.append(line)
        return found

    @property
    def stdin(self) -> str:
        """What `kubectl create -f -` was given."""
        return "\n".join(
            line.removeprefix("kubectl-stdin ")
            for line in self.calls
            if line.startswith("kubectl-stdin ")
        )

    def index_of(self, *fragments: str) -> int:
        for index, line in enumerate(self.calls):
            if all(fragment in line for fragment in fragments):
                return index
        raise AssertionError(f"no call holds {fragments}: {self.calls}")


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A directory laid out like the repository, holding the committed scripts.

    The script derives its root from its own location, so a copy two
    directories below the sandbox root treats the sandbox as the repository.
    The scripts are copied byte for byte.
    """
    scripts = tmp_path / "scripts" / "environment"
    scripts.mkdir(parents=True)
    for rel in (LIB_REL, SCRIPT_REL):
        shutil.copyfile(REPO_ROOT / rel, scripts / Path(rel).name)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in _STUBS.items():
        stub = bin_dir / name
        stub.write_text(body, encoding="utf-8", newline="\n")
        stub.chmod(0o755)
    return tmp_path


def run_script(
    sandbox: Path,
    *args: str,
    provider: str | None = "kind",
    cluster_name: str | None = "inferops-dev",
    api_node: str = CONTROL_PLANE,
    minor: str = "34",
    pinned_manifest: bool = False,
    **stub: str,
) -> Run:
    """Execute the committed script inside the sandbox and report what it ran.

    `pinned_manifest` puts the `sha256sum` stub on PATH and a file named
    `core-install.yaml` in the sandbox, so the path after the digest check runs.
    """
    log = sandbox / "calls.log"
    log.write_text("", encoding="utf-8")
    if pinned_manifest:
        fake = sandbox / "bin" / "sha256sum"
        fake.write_text(_SHA256SUM_STUB, encoding="utf-8", newline="\n")
        fake.chmod(0o755)
        (sandbox / "core-install.yaml").write_text(
            "kind: ConfigMap\n", encoding="utf-8", newline="\n"
        )

    assert BASH is not None
    # The stub directory and the shell's own toolbox, and nothing else. A real
    # kubectl behind the stubs would make a refusal test contact a cluster.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("INFEROPS_", "STUB_", "KUBE"))
    }
    env["PATH"] = os.pathsep.join([str(sandbox / "bin"), str(Path(BASH).parent)])
    env["INFEROPS_STUB_LOG"] = str(log)
    env["STUB_CONTEXT"] = KUBE_CONTEXT
    env["STUB_NODE"] = api_node
    env["STUB_KIND_NODE"] = CONTROL_PLANE
    env["STUB_VERSION_JSON"] = version_json(minor)
    if provider is not None:
        env["INFEROPS_PROVIDER"] = provider
    if cluster_name is not None:
        env["INFEROPS_KIND_CLUSTER_NAME"] = cluster_name
    env["INFEROPS_TARGET_KUBECONFIG_POSIX_PATH"] = (
        sandbox / ".kube" / "inferops-target.config"
    ).as_posix()
    for key, value in stub.items():
        env[f"STUB_{key.upper()}"] = value

    completed = subprocess.run(
        [BASH, SCRIPT_REL, *args],
        cwd=sandbox,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    return Run(completed, log)


# --------------------------------------------------------------------------
# The harness must reach a mutation before its negative results mean anything
# --------------------------------------------------------------------------


@needs_bash
def test_the_sandbox_reaches_the_deletions(sandbox: Path) -> None:
    """The control case, and the order ADR 0017 D11 decides.

    Every refusal test below asserts that no mutating call ran. That is worth
    nothing unless the sandbox can reach one. A marked namespace, no custom
    resource, and `--confirm` remove the installation.
    """
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
    )
    assert run.returncode == 0, run.output
    deletions = run.kubectl_calls("delete")
    assert len(deletions) == 10, deletions

    first_check = run.index_of("get applications.argoproj.io")
    stop = run.index_of("delete statefulset argocd-application-controller")
    last_stop = run.index_of("delete deployment argocd-repo-server")
    pods = run.index_of("get pods -n argocd -o name")
    second_check = max(
        index
        for index, line in enumerate(run.calls)
        if "get applications.argoproj.io" in line
    )
    definition = run.index_of("delete customresourcedefinition")
    binding = run.index_of("delete clusterrolebinding argocd-application-controller")
    role = run.index_of("delete clusterrole argocd-application-controller")
    namespace = run.index_of("delete namespace argocd")

    assert first_check < stop < last_stop < pods < second_check < definition
    assert definition < binding < role < namespace
    assert run.mutations == deletions, "removal ran a mutation that is not a deletion"
    assert "no Argo CD definition" in run.output


@needs_bash
def test_removal_deletes_only_named_objects_in_one_namespace(sandbox: Path) -> None:
    """Every deletion names its object, and none reaches another namespace."""
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
    )
    expected = {
        "delete statefulset argocd-application-controller -n argocd",
        "delete deployment argocd-applicationset-controller -n argocd",
        "delete deployment argocd-redis -n argocd",
        "delete deployment argocd-repo-server -n argocd",
        "delete customresourcedefinition applications.argoproj.io",
        "delete customresourcedefinition applicationsets.argoproj.io",
        "delete customresourcedefinition appprojects.argoproj.io",
        "delete clusterrolebinding argocd-application-controller",
        "delete clusterrole argocd-application-controller",
        "delete namespace argocd",
    }
    for line in run.kubectl_calls("delete"):
        # The whole of the call up to its first flag after the name. A fragment
        # match accepted `-n argocd-other`, because `-n argocd` is inside it.
        named = line[line.index(" delete ") + 1 :].split(" --ignore-not-found")[0]
        assert named in expected, line
        assert "--all" not in line and " -A" not in line, line
        assert "inferops-release" not in line and "inferops-smoke" not in line, line
        assert f"--context {KUBE_CONTEXT}" in line and "--kubeconfig" in line, line
    for fragment in expected:
        run.index_of(fragment)


# --------------------------------------------------------------------------
# target-not-selected-or-not-verified
# --------------------------------------------------------------------------

OPERATIONS = (("install",), ("verify",), ("remove", "--confirm"))


@needs_bash
@pytest.mark.parametrize("operation", OPERATIONS, ids=lambda args: args[0])
def test_no_selected_provider_refuses_before_any_call(
    sandbox: Path, operation: tuple[str, ...]
) -> None:
    run = run_script(sandbox, *operation, provider=None, namespace=MARKED)
    assert run.refused, run.output
    assert "no-provider-selected" in run.output
    assert not [call for call in run.calls if call.startswith("kubectl ")], run.calls


@needs_bash
@pytest.mark.parametrize("operation", OPERATIONS, ids=lambda args: args[0])
def test_an_unsupported_provider_refuses(
    sandbox: Path, operation: tuple[str, ...]
) -> None:
    run = run_script(sandbox, *operation, provider="minikube", namespace=MARKED)
    assert run.refused, run.output
    assert "unsupported-provider" in run.output
    assert not run.mutations, run.calls


@needs_bash
@pytest.mark.parametrize("operation", OPERATIONS, ids=lambda args: args[0])
def test_an_ambiguous_kind_target_refuses(
    sandbox: Path, operation: tuple[str, ...]
) -> None:
    """Provider `kind` with no cluster name selects nothing."""
    run = run_script(sandbox, *operation, cluster_name=None, namespace=MARKED)
    assert run.refused, run.output
    assert "ambiguous-target" in run.output
    assert not run.mutations, run.calls


@needs_bash
@pytest.mark.parametrize("operation", OPERATIONS, ids=lambda args: args[0])
def test_a_cluster_that_is_not_the_selected_one_refuses(
    sandbox: Path, operation: tuple[str, ...]
) -> None:
    """The API server reports a node the selected provider did not create."""
    run = run_script(
        sandbox,
        *operation,
        api_node="some-other-cluster-node",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
    )
    assert run.refused, run.output
    assert "provider-mismatch" in run.output
    assert not run.mutations, run.calls
    assert not any("get namespace argocd" in line for line in run.calls), (
        "the procedure read the installation before the target was verified"
    )


# --------------------------------------------------------------------------
# install: every refusal comes before the first mutation
# --------------------------------------------------------------------------


@needs_bash
def test_a_kubernetes_minor_upstream_did_not_test_refuses(sandbox: Path) -> None:
    run = run_script(sandbox, "install", minor="32")
    assert run.refused, run.output
    assert "refusing: kubernetes-minor-not-tested" in run.output
    assert not run.mutations, run.calls


@needs_bash
def test_an_unreadable_server_version_refuses(sandbox: Path) -> None:
    """No version is not a tested version."""
    run = run_script(sandbox, "install", version_json="{}")
    assert run.refused, run.output
    assert "refusing: kubernetes-minor-not-tested" in run.output
    assert not run.mutations, run.calls


@needs_bash
@pytest.mark.parametrize(
    "namespace",
    ("Active||", f"Active|prerequisite|{PIN}", f"Active||{PIN}"),
    ids=("no-marker", "another-marker", "pin-without-marker"),
)
def test_install_refuses_a_namespace_it_did_not_create(
    sandbox: Path, namespace: str
) -> None:
    run = run_script(
        sandbox, "install", namespace=namespace, cluster_objects=CLUSTER_OBJECTS
    )
    assert run.refused, run.output
    assert "refusing: foreign-argocd-present" in run.output
    assert not run.mutations, run.calls


@needs_bash
@pytest.mark.parametrize(
    "present",
    CLUSTER_OBJECTS.splitlines(),
    ids=lambda name: name.split(".", 1)[0] + "-" + name.rsplit("/", 1)[1],
)
def test_install_refuses_a_cluster_scoped_object_without_a_marked_namespace(
    sandbox: Path, present: str
) -> None:
    """One definition, or the cluster role, or its binding, is enough.

    Server-side apply with `--force-conflicts` takes over a field another
    manager holds. Without this refusal the apply would adopt the object.
    """
    run = run_script(sandbox, "install", cluster_objects=present)
    assert run.refused, run.output
    assert "refusing: foreign-argocd-present" in run.output
    assert not run.mutations, run.calls


@needs_bash
def test_install_refuses_an_installation_with_another_pin(sandbox: Path) -> None:
    run = run_script(
        sandbox,
        "install",
        namespace=f"Active|bootstrap|{'0' * 64}",
        cluster_objects=CLUSTER_OBJECTS,
    )
    assert run.refused, run.output
    assert "refusing: installed-pin-differs" in run.output
    assert not run.mutations, run.calls


@needs_bash
@pytest.mark.parametrize(
    "operation",
    (("install",), ("verify",), ("remove", "--confirm")),
    ids=lambda a: a[0],
)
@pytest.mark.parametrize(
    "pin",
    ("", "not-a-digest", "0" * 63, "0" * 65, "G" * 64),
    ids=("none", "a-word", "short", "long", "not-hex"),
)
def test_a_label_without_a_recorded_digest_is_not_the_marker(
    sandbox: Path, operation: tuple[str, ...], pin: str
) -> None:
    """The procedure writes the label and the SHA-256 in one request.

    A namespace that carries the label alone was labelled by somebody else. The
    first version of the removal accepted it and warned. It would have deleted
    that namespace, and three definitions, a cluster role, and its binding.
    """
    run = run_script(
        sandbox,
        *operation,
        namespace=f"Active|bootstrap|{pin}",
        cluster_objects=CLUSTER_OBJECTS,
        statuses=PINNED_STATUSES,
    )
    assert run.refused, run.output
    assert "refusing: foreign-argocd-present" in run.output
    assert "does not record a manifest SHA-256" in run.output
    assert not run.mutations, run.calls


@needs_bash
def test_removal_accepts_an_installation_with_an_older_pin(sandbox: Path) -> None:
    """Removal is how an installation with another pin is replaced."""
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=f"Active|bootstrap|{'0' * 64}",
        cluster_objects=CLUSTER_OBJECTS,
    )
    assert run.returncode == 0, run.output
    assert "not the pinned one" in run.output
    assert len(run.kubectl_calls("delete")) == 10


@needs_bash
def test_install_refuses_a_namespace_that_is_being_deleted(sandbox: Path) -> None:
    run = run_script(sandbox, "install", namespace=f"Terminating|bootstrap|{PIN}")
    assert run.refused, run.output
    assert "phase 'Terminating'" in run.output
    assert not run.mutations, run.calls


@needs_bash
def test_install_refuses_manifest_bytes_that_are_not_the_pin(sandbox: Path) -> None:
    manifest = sandbox / "core-install.yaml"
    manifest.write_text("kind: ConfigMap\n", encoding="utf-8", newline="\n")
    run = run_script(sandbox, "install", "--manifest", "core-install.yaml")
    assert run.refused, run.output
    assert "refusing: manifest-digest-mismatch" in run.output
    assert not run.mutations, run.calls
    assert not any(line.startswith("curl ") for line in run.calls), run.calls


@needs_bash
def test_install_refuses_a_download_that_is_not_the_pin(sandbox: Path) -> None:
    """The download is verified like a file, and a wrong one is never applied."""
    run = run_script(sandbox, "install", curl_mode="tampered")
    assert run.refused, run.output
    assert any(
        line.startswith("curl ") and "c9c369efcc5b2a0bd720803f8d14a1c3eaddf579" in line
        for line in run.calls
    ), run.calls
    assert "refusing: manifest-digest-mismatch" in run.output
    assert not run.mutations, run.calls


@needs_bash
def test_install_refuses_when_the_download_fails(sandbox: Path) -> None:
    run = run_script(sandbox, "install", curl_mode="unreachable")
    assert run.refused, run.output
    assert "could not be downloaded" in run.output
    assert not run.mutations, run.calls


@needs_bash
def test_install_refuses_a_manifest_path_that_does_not_exist(sandbox: Path) -> None:
    run = run_script(sandbox, "install", "--manifest", "absent.yaml")
    assert run.refused, run.output
    assert "no such manifest file" in run.output
    assert not run.mutations, run.calls


@needs_bash
@pytest.mark.parametrize(
    "query",
    ("get namespace argocd", "get customresourcedefinition/"),
    ids=("namespace", "cluster-scoped-objects"),
)
def test_install_does_not_read_an_unanswered_query_as_absence(
    sandbox: Path, query: str
) -> None:
    """An API server that refuses the query is not a cluster with no Argo CD."""
    run = run_script(sandbox, "install", fail_on=query)
    assert run.refused, run.output
    assert "not an empty result" in run.output
    assert not run.mutations, run.calls


# --------------------------------------------------------------------------
# remove: every refusal comes before the first deletion
# --------------------------------------------------------------------------


@needs_bash
def test_removal_without_confirmation_runs_nothing(sandbox: Path) -> None:
    run = run_script(
        sandbox, "remove", namespace=MARKED, cluster_objects=CLUSTER_OBJECTS
    )
    assert run.refused, run.output
    assert "--confirm" in run.output
    assert run.calls == [], run.calls


@needs_bash
@pytest.mark.parametrize(
    "namespace",
    ("", "Active||", f"Active|prerequisite|{PIN}"),
    ids=("no-namespace", "no-marker", "another-marker"),
)
def test_removal_refuses_an_installation_it_did_not_create(
    sandbox: Path, namespace: str
) -> None:
    """The marker is read before any deletion, cluster-scoped ones included."""
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=namespace,
        cluster_objects=CLUSTER_OBJECTS,
    )
    assert run.refused, run.output
    assert "refusing: foreign-argocd-present" in run.output
    assert not run.mutations, run.calls


@needs_bash
def test_removal_refuses_a_namespace_that_is_being_deleted(sandbox: Path) -> None:
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=f"Terminating|bootstrap|{PIN}",
        cluster_objects=CLUSTER_OBJECTS,
    )
    assert run.refused, run.output
    assert not run.mutations, run.calls


@needs_bash
@pytest.mark.parametrize(
    "stub",
    (
        {"applications": "application.argoproj.io/workload\n"},
        {"application_sets": "applicationset.argoproj.io/fleet\n"},
        {"projects": "appproject.argoproj.io/default\n"},
    ),
    ids=("an-application", "an-application-set", "a-project"),
)
def test_removal_refuses_while_a_custom_resource_exists(
    sandbox: Path, stub: dict[str, Any]
) -> None:
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
        **stub,
    )
    assert run.refused, run.output
    assert "refusing: argocd-custom-resources-present" in run.output
    assert not run.mutations, run.calls


@needs_bash
def test_removal_checks_again_after_the_controllers_stop(sandbox: Path) -> None:
    """An object created after the first check keeps its definition.

    The controllers are deleted, and no definition, cluster role, binding, or
    namespace is. A second run can continue from there.
    """
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
        applications_after_stop="application.argoproj.io/late\n",
    )
    assert run.refused, run.output
    assert "after the controllers stopped" in run.output
    deleted = " ".join(run.kubectl_calls("delete"))
    assert "delete statefulset" in deleted and "delete deployment" in deleted
    for kind in ("customresourcedefinition", "clusterrole", "namespace"):
        assert f"delete {kind}" not in deleted, deleted


@needs_bash
@pytest.mark.parametrize(
    "query",
    (
        "get namespace argocd",
        "get customresourcedefinition/",
        "get applications.argoproj.io",
    ),
    ids=("namespace", "cluster-scoped-objects", "custom-resources"),
)
def test_removal_does_not_read_an_unanswered_query_as_absence(
    sandbox: Path, query: str
) -> None:
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
        fail_on=query,
    )
    assert run.refused, run.output
    assert "not an empty result" in run.output
    assert not run.mutations, run.calls


@needs_bash
def test_removal_does_not_query_a_definition_that_does_not_exist(
    sandbox: Path,
) -> None:
    """A second run after the definitions are gone finishes the removal.

    `kubectl get` on a kind with no definition is an error, and reading that
    error as an unanswered query would make an interrupted removal permanent.
    """
    run = run_script(sandbox, "remove", "--confirm", namespace=MARKED)
    assert run.returncode == 0, run.output
    assert not any("--all-namespaces" in line for line in run.calls), run.calls
    run.index_of("delete namespace argocd")


@needs_bash
def test_removal_deletes_no_definition_while_a_pod_remains(sandbox: Path) -> None:
    """The controllers stop before a definition goes (ADR 0017 D11).

    The stub reports a pod for the first two reads. The removal must ask again
    and must not reach a definition until the answer is empty.
    """
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
        pods_polls="2",
    )
    assert run.returncode == 0, run.output
    polls = [
        i for i, line in enumerate(run.calls) if "get pods -n argocd -o name" in line
    ]
    assert len(polls) == 3, polls
    assert polls[-1] < run.index_of("delete customresourcedefinition")
    assert polls[-1] < run.index_of("delete clusterrole ")
    assert polls[-1] < run.index_of("delete namespace argocd")


@needs_bash
def test_removal_stops_when_it_cannot_ask_whether_a_pod_remains(sandbox: Path) -> None:
    """An unanswered pod query is not "no pod remains"."""
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
        fail_on="get pods -n argocd -o name",
    )
    assert run.refused, run.output
    assert "not an empty result" in run.output
    deleted = " ".join(run.kubectl_calls("delete"))
    for kind in ("customresourcedefinition", "clusterrole", "namespace"):
        assert f"delete {kind}" not in deleted, deleted


@needs_bash
def test_removal_waits_until_the_namespace_is_gone(sandbox: Path) -> None:
    """The removal reports success only after it sees nothing left.

    The stub keeps the namespace for two reads after its deletion. With the
    residue check removed, this test fails on the count of reads.
    """
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
        residue_polls="2",
    )
    assert run.returncode == 0, run.output
    deleted_at = run.index_of("delete namespace argocd")
    reads_after = [
        line for line in run.calls[deleted_at + 1 :] if "get namespace argocd" in line
    ]
    assert len(reads_after) == 3, reads_after
    assert "no Argo CD definition" in run.output


@needs_bash
def test_every_deletion_is_bounded(sandbox: Path) -> None:
    """A deletion that waits on a finalizer must not wait without a limit."""
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
    )
    for line in run.kubectl_calls("delete"):
        assert "--timeout=300s" in line, line


# --------------------------------------------------------------------------
# install: the path after the digest check, with `sha256sum` replaced
# --------------------------------------------------------------------------


@needs_bash
def test_install_creates_the_marked_namespace_and_then_applies(sandbox: Path) -> None:
    """The mutations of a first install, their order, and what each is given."""
    run = run_script(
        sandbox,
        "install",
        "--manifest",
        "core-install.yaml",
        pinned_manifest=True,
        cluster_objects_after_apply=CLUSTER_OBJECTS,
        statuses=PINNED_STATUSES,
    )
    assert run.returncode == 0, run.output
    assert len(run.mutations) == 2, run.mutations
    create, apply = run.mutations
    assert create.endswith(" create -f -"), create
    assert run.stdin == (
        '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"argocd",'
        '"labels":{"inferops.io/lifecycle":"bootstrap"},'
        f'"annotations":{{"inferops.io/argocd-manifest-sha256":"{PIN}"}}}}}}'
    )
    for fragment in (
        f"--context {KUBE_CONTEXT}",
        " apply --server-side --force-conflicts",
        "--field-manager=inferops-argocd-bootstrap",
        "-n argocd",
        "core-install.yaml",
    ):
        assert fragment in apply, (fragment, apply)
    assert run.index_of(" create -f -") < run.index_of(" apply --server-side")
    assert run.index_of(" apply --server-side") < run.index_of("rollout status")
    assert "Argo CD v3.5.3 is installed in 'argocd'" in run.output


@needs_bash
def test_a_second_install_applies_again_and_creates_no_namespace(sandbox: Path) -> None:
    run = run_script(
        sandbox,
        "install",
        "--manifest",
        "core-install.yaml",
        pinned_manifest=True,
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
        statuses=PINNED_STATUSES,
    )
    assert run.returncode == 0, run.output
    assert len(run.mutations) == 1, run.mutations
    assert " apply --server-side" in run.mutations[0]
    assert run.stdin == ""


@needs_bash
def test_install_fails_when_the_apply_reports_another_object_count(
    sandbox: Path,
) -> None:
    run = run_script(
        sandbox,
        "install",
        "--manifest",
        "core-install.yaml",
        pinned_manifest=True,
        cluster_objects_after_apply=CLUSTER_OBJECTS,
        statuses=PINNED_STATUSES,
        applied_count="33",
    )
    assert run.refused, run.output
    assert "the apply reported 33 objects, and the manifest declares 34" in run.output
    assert (
        "Remove it with: scripts/environment/argocd-bootstrap.sh remove --confirm"
        in (run.output)
    )


@needs_bash
def test_install_withholds_success_when_a_container_is_not_at_its_pin(
    sandbox: Path,
) -> None:
    """The image rule, on the install path it was written for."""
    run = run_script(
        sandbox,
        "install",
        "--manifest",
        "core-install.yaml",
        pinned_manifest=True,
        cluster_objects_after_apply=CLUSTER_OBJECTS,
        statuses=PINNED_STATUSES.replace(REDIS_DIGEST, OTHER_DIGEST),
    )
    assert run.refused, run.output
    assert "container 'redis' runs" in run.output
    assert "does not report success" in run.output
    assert "is installed in 'argocd'" not in run.output


@needs_bash
def test_install_applies_nothing_when_the_manifest_changes_after_the_check(
    sandbox: Path,
) -> None:
    """The file is hashed again just before the apply.

    Its path is predictable, and the namespace is created between the two
    hashes. The stub reports the pin on the first read and another digest on
    the second.
    """
    run = run_script(
        sandbox,
        "install",
        "--manifest",
        "core-install.yaml",
        pinned_manifest=True,
        sha_flip_at="2",
    )
    assert run.refused, run.output
    assert "changed after they were verified" in run.output
    assert not run.kubectl_calls("apply"), run.calls


# --------------------------------------------------------------------------
# verify: reads, and the image rule
# --------------------------------------------------------------------------


@needs_bash
def test_verification_passes_on_the_pinned_installation_and_changes_nothing(
    sandbox: Path,
) -> None:
    run = run_script(
        sandbox,
        "verify",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
        statuses=PINNED_STATUSES,
    )
    assert run.returncode == 0, run.output
    assert not run.mutations, run.calls
    assert "every container runs its pinned digest at this moment" in run.output


@needs_bash
@pytest.mark.parametrize(
    ("statuses", "finding"),
    (
        (
            PINNED_STATUSES.replace(
                f"copyutil quay.io/argoproj/argocd@{ARGOCD_DIGEST}",
                f"copyutil quay.io/argoproj/argocd@{OTHER_DIGEST}",
            ),
            "container 'copyutil' runs",
        ),
        (
            PINNED_STATUSES.replace(REDIS_DIGEST, ARGOCD_DIGEST),
            "container 'redis' runs",
        ),
        (
            "\n".join(PINNED_STATUSES.splitlines()[:-1]),
            "no running pod reports a container named 'argocd-repo-server'",
        ),
        (
            PINNED_STATUSES + f"\nsidecar quay.io/argoproj/argocd@{ARGOCD_DIGEST}",
            "container 'sidecar' is not one the record lists",
        ),
        (
            PINNED_STATUSES.replace(
                f"secret-init quay.io/argoproj/argocd@{ARGOCD_DIGEST}", "secret-init "
            ),
            "container 'secret-init' runs 'no image identity'",
        ),
    ),
    ids=(
        "another-digest",
        "the-other-image",
        "a-missing-container",
        "an-unlisted-container",
        "no-identity-yet",
    ),
)
def test_verification_fails_when_a_container_does_not_run_its_pin(
    sandbox: Path, statuses: str, finding: str
) -> None:
    """`images-run-at-their-pinned-digests`, executed.

    An init container counts. So does a container the record does not list,
    and a container the runtime reports no image identity for.
    """
    run = run_script(
        sandbox,
        "verify",
        namespace=MARKED,
        cluster_objects=CLUSTER_OBJECTS,
        statuses=statuses,
    )
    assert run.refused, run.output
    assert finding in run.output, run.output
    assert "does not report success" in run.output
    assert not run.mutations, run.calls


@needs_bash
@pytest.mark.parametrize(
    ("stub", "message"),
    (
        ({"namespace": ""}, "is not installed by this procedure"),
        ({"namespace": "Active||"}, "refusing: foreign-argocd-present"),
        ({"namespace": f"Active|bootstrap|{'0' * 64}"}, "and the pin is"),
        (
            {
                "namespace": MARKED,
                "cluster_objects": "\n".join(CLUSTER_OBJECTS.splitlines()[:4]),
            },
            "expected 5 cluster-scoped objects",
        ),
        (
            {
                "namespace": MARKED,
                "cluster_objects": CLUSTER_OBJECTS,
                "namespaced_count": "28",
            },
            "expected 29 namespaced objects",
        ),
    ),
    ids=(
        "no-namespace",
        "no-marker",
        "another-pin",
        "a-missing-cluster-object",
        "a-missing-namespaced-object",
    ),
)
def test_verification_fails_on_an_installation_that_is_not_the_recorded_one(
    sandbox: Path, stub: dict[str, Any], message: str
) -> None:
    run = run_script(sandbox, "verify", statuses=PINNED_STATUSES, **stub)
    assert run.refused, run.output
    assert message in run.output, run.output
    assert not run.mutations, run.calls


# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------


@needs_bash
@pytest.mark.parametrize(
    "args",
    (
        (),
        ("upgrade",),
        ("install", "--confirm"),
        ("install", "--force"),
        ("install", "--manifest"),
        ("install", "--manifest", ""),
        ("install", "--manifest", "a.yaml", "--manifest", "b.yaml"),
        ("verify", "--manifest", ""),
        ("verify", "--confirm"),
        ("verify", "--manifest", "x.yaml"),
        ("remove", "--confirm", "--manifest", "x.yaml"),
        ("remove", "--confirm", "extra"),
    ),
    ids=lambda args: " ".join(args) or "none",
)
def test_an_argument_the_procedure_does_not_understand_runs_nothing(
    sandbox: Path, args: tuple[str, ...]
) -> None:
    run = run_script(sandbox, *args, namespace=MARKED, cluster_objects=CLUSTER_OBJECTS)
    assert run.refused, run.output
    assert "Usage: argocd-bootstrap.sh" in run.output
    assert run.calls == [], run.calls
