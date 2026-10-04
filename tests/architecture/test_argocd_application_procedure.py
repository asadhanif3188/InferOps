"""The Application procedure, executed against stub tools.

`tests/architecture/test_argocd_application.py` reads the procedure as text. This
suite runs it. Every external tool is a stub that logs its call and answers from
the environment, so each test states what the cluster holds and reads what the
procedure did about it.

Evidence level: `C1`, substituted execution. The procedure and `lib.sh` are the
committed bytes. kubectl, kind, docker, and sleep are stubs. No cluster is
contacted, no Argo CD runs, and no chart is rendered.

What it establishes: the order of the procedure's calls, that each refusal comes
before the first mutation, what the two apply requests are given, and what the
removal deletes. What it does not establish: that Argo CD reconciles the release,
that a cascade deletes the workload, or anything a real API server answers. The
stub answers what the test tells it to answer. No test reaches a time limit.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = "scripts/environment/argocd-application.sh"
LIB_REL = "scripts/environment/lib.sh"
PROJECT_REL = "infra/argocd/workloads-project.yaml"
APPLICATION_REL = "infra/argocd/local-docker-desktop-support-assistant.yaml"

BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(
    BASH is None,
    reason="bash is not installed; the executed Application tests skip, loudly",
)

# Restated on purpose. A fixture that imported these from the script would agree
# with the script by construction.
ARGOCD_NAMESPACE = "argocd"
RELEASE_NAMESPACE = "inferops-release"
APPLICATION = "local-docker-desktop-support-assistant"
PROJECT = "inferops-workloads"
CLAIM = "persistentvolumeclaim/inferops-model-cache"
DIGEST = "sha256:" + "b" * 64
REVISION = "2" * 40
PIN = "c" * 64

BOOTSTRAPPED = f"Active|bootstrap|{PIN}"
OWN_APPLICATION = f"Application/{ARGOCD_NAMESPACE}/{APPLICATION}|reconciliation|{PIN}\n"
OWN_PROJECT = f"AppProject/{ARGOCD_NAMESPACE}/{PROJECT}|reconciliation|{PIN}\n"
RECONCILED = "2026-01-01T00:00:02Z"
SYNCED = f"Synced|{REVISION}|Healthy|Succeeded|{REVISION}|{RECONCILED}"
LIVE_SPEC = (
    f"{PROJECT}|https://github.com/asadhanif3188/InferOps.git|main|charts/inferops-llm|"
    f"https://kubernetes.default.svc|{RELEASE_NAMESPACE}|false|true|"
)

KUBE_CONTEXT = "kind-inferops-dev"
CONTROL_PLANE = "inferops-dev-control-plane"

# The kubectl calls that change nothing, as the first words after the pinned
# flags. Every other call counts as a mutation.
READ_CALLS = (
    ("get",),
    ("describe",),
    ("version",),
    ("patch", "--local"),
    ("config", "get-contexts"),
    ("config", "view"),
    ("config", "current-context"),
)


def version_json(minor: str = "34") -> str:
    return (
        '{\n  "clientVersion": {\n    "major": "1",\n'
        f'    "minor": "{minor}",\n    "gitVersion": "v1.{minor}.1"\n  }},\n'
        '  "serverVersion": {\n    "major": "1",\n'
        f'    "minor": "{minor}",\n    "gitVersion": "v1.{minor}.3"\n  }}\n}}\n'
    )


# The kubectl stub logs the call, then fails it when the test named it in
# STUB_FAIL_ON, then answers from the environment. After a `delete` of the
# Application or of the project is in the log, that object is gone. The status
# of the Application is STUB_STATUS_PENDING for the first STUB_SYNC_POLLS reads.
# `apply -f -` logs what it was given on stdin.
_KUBECTL_STUB = """#!/usr/bin/env bash
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
  *"get namespace argocd"*) printf '%s' "${STUB_NAMESPACE:-}" ;;
  *"get applications.argoproj.io --all-namespaces"*)
    if logged ' delete applications.argoproj.io '; then
      :
    elif logged ' apply --server-side'; then
      printf '%s' "${STUB_APPLICATIONS_AFTER_APPLY:-${STUB_APPLICATIONS:-}}"
    else
      printf '%s' "${STUB_APPLICATIONS:-}"
    fi
    ;;
  *"get appprojects.argoproj.io --all-namespaces"*)
    logged ' delete appprojects.argoproj.io ' || printf '%s' "${STUB_PROJECTS:-}"
    ;;
  *"get applicationsets.argoproj.io --all-namespaces"*) printf '%s' "${STUB_APPLICATION_SETS:-}" ;;
  *"get persistentvolumeclaims"*)
    if [ -n "${STUB_CLAIMS_AFTER+set}" ] && logged ' delete '; then
      printf '%s' "${STUB_CLAIMS_AFTER}"
    else
      printf '%s' "${STUB_CLAIMS:-}"
    fi
    ;;
  *"get secrets"*) printf '%s' "${STUB_HELM_RECORDS:-}" ;;
  *"patch --local"*) printf '{"stub":"document"}\\n' ;;
  *"apply --server-side"*)
    sed 's/^/kubectl-stdin /' >>"${INFEROPS_STUB_LOG}"
    printf 'object serverside-applied\\n'
    ;;
  *"get applications.argoproj.io local-docker-desktop-support-assistant"*"{.spec.project}"*)
    printf '%s' "${STUB_LIVE_SPEC:-}"
    ;;
  *"get applications.argoproj.io local-docker-desktop-support-assistant"*"{.metadata.generation}"*)
    if logged ' apply --server-side'; then
      printf '%s' "${STUB_GENERATION_AFTER:-1}"
    else
      printf '%s' "${STUB_BEFORE:-}"
    fi
    ;;
  *"get applications.argoproj.io local-docker-desktop-support-assistant"*"{.status.sync.status}"*)
    reads="$(grep -c '{.status.sync.status}' "${INFEROPS_STUB_LOG}" || true)"
    if [ "${reads}" -gt "${STUB_SYNC_POLLS:-0}" ]; then
      printf '%s' "${STUB_STATUS:-}"
    else
      printf '%s' "${STUB_STATUS_PENDING:-}"
    fi
    ;;
  *"get statefulset argocd-application-controller"*) printf '%s' "${STUB_CONTROLLER_READY:-}" ;;
  *"get deployments,replicasets,pods"*)
    if logged ' delete applications.argoproj.io '; then
      reads="$(sed -n '/ delete applications.argoproj.io /,$p' "${INFEROPS_STUB_LOG}" | grep -c 'get deployments,replicasets,pods' || true)"
      [ "${reads}" -gt "${STUB_RESIDUE_POLLS:-0}" ] || printf 'pod/inferops-runtime-0\\n'
    else
      printf '%s' "${STUB_WORKLOAD:-}"
    fi
    ;;
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

# The procedure waits between two reads of the Application. The stub returns at
# once, and logs the wait so that a test can count the reads.
_SLEEP_STUB = """#!/usr/bin/env bash
printf 'sleep %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
exit 0
"""

_STUBS = {
    "kubectl": _KUBECTL_STUB,
    "kind": _KIND_STUB,
    "docker": _DOCKER_STUB,
    "sleep": _SLEEP_STUB,
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

    @property
    def kubectl(self) -> list[list[str]]:
        """Each kubectl call, as its words after the two flags the wrapper pins."""
        found = []
        for line in self.calls:
            words = line.split()
            if words[0] != "kubectl":
                continue
            rest = words[1:]
            while rest and rest[0] in ("--kubeconfig", "--context"):
                rest = rest[2:]
            found.append(rest)
        return found

    @property
    def mutations(self) -> list[str]:
        """Every kubectl call that is not a known read."""
        return [
            " ".join(call)
            for call in self.kubectl
            if not any(tuple(call[: len(read)]) == read for read in READ_CALLS)
        ]

    @property
    def stdin(self) -> list[str]:
        """What each `kubectl apply -f -` was given."""
        return [
            line.removeprefix("kubectl-stdin ")
            for line in self.calls
            if line.startswith("kubectl-stdin ")
        ]

    def index_of(self, *fragments: str) -> int:
        for index, line in enumerate(self.calls):
            if all(fragment in line for fragment in fragments):
                return index
        raise AssertionError(f"no call holds {fragments}: {self.calls}")


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A directory laid out like the repository, holding the committed bytes.

    The script derives its root from its own location, so a copy two directories
    below the sandbox root treats the sandbox as the repository.
    """
    for rel in (LIB_REL, SCRIPT_REL, PROJECT_REL, APPLICATION_REL):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, target)

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
    **stub: str,
) -> Run:
    """Execute the committed script inside the sandbox and report what it ran.

    The defaults describe a prepared cluster: Argo CD installed by the bootstrap,
    the claim present, no Helm release, and no Argo CD custom resource.
    """
    log = sandbox / "calls.log"
    log.write_text("", encoding="utf-8")

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
    env["STUB_VERSION_JSON"] = version_json()
    env["STUB_NAMESPACE"] = BOOTSTRAPPED
    env["STUB_CLAIMS"] = CLAIM + "\n"
    env["STUB_STATUS"] = SYNCED
    env["STUB_LIVE_SPEC"] = LIVE_SPEC
    env["STUB_CONTROLLER_READY"] = "1"
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


APPLY = ("apply", "--api-image-digest", DIGEST)
APPLIED = {"applications": OWN_APPLICATION, "projects": OWN_PROJECT}


# --------------------------------------------------------------------------
# The harness must reach a mutation before its negative results mean anything
# --------------------------------------------------------------------------


@needs_bash
def test_the_sandbox_reaches_the_two_applies(sandbox: Path) -> None:
    run = run_script(sandbox, *APPLY)
    assert run.returncode == 0, run.output
    assert [m.split()[:2] for m in run.mutations] == [["apply", "--server-side"]] * 2


@needs_bash
def test_the_sandbox_reaches_the_deletions(sandbox: Path) -> None:
    run = run_script(sandbox, "remove", "--confirm", **APPLIED)
    assert run.returncode == 0, run.output
    assert [m.split()[0] for m in run.mutations] == ["patch", "delete", "delete"]


# --------------------------------------------------------------------------
# The target
# --------------------------------------------------------------------------

OPERATIONS = (APPLY, ("verify",), ("remove", "--confirm"))


@needs_bash
@pytest.mark.parametrize("operation", OPERATIONS, ids=lambda o: o[0])
def test_no_selected_provider_refuses_before_any_call(
    sandbox: Path, operation: tuple[str, ...]
) -> None:
    run = run_script(sandbox, *operation, provider=None)
    assert run.refused
    assert "INFEROPS_PROVIDER" in run.output
    assert run.kubectl == []


@needs_bash
@pytest.mark.parametrize("operation", OPERATIONS, ids=lambda o: o[0])
def test_a_cluster_that_is_not_the_selected_one_refuses(
    sandbox: Path, operation: tuple[str, ...]
) -> None:
    run = run_script(sandbox, *operation, api_node="some-other-control-plane")
    assert run.refused
    assert run.mutations == []
    assert not any("argoproj.io" in " ".join(call) for call in run.kubectl)


# --------------------------------------------------------------------------
# apply: the refusals
# --------------------------------------------------------------------------


@needs_bash
@pytest.mark.parametrize(
    "arguments",
    (
        ("apply",),
        ("apply", "--api-image-digest", "sha256:abc"),
        ("apply", "--api-image-digest", "b" * 64),
        ("apply", "--api-image-digest", "sha256:" + "B" * 64),
        ("apply", "--api-image-digest", "localhost/inferops-api:dev"),
    ),
)
def test_apply_refuses_without_a_digest_before_any_call(
    sandbox: Path, arguments: tuple[str, ...]
) -> None:
    run = run_script(sandbox, *arguments)
    assert run.refused
    assert "api-image-digest-not-given" in run.output
    assert run.kubectl == []


@needs_bash
@pytest.mark.parametrize(
    "namespace",
    (
        "",
        "Active||",
        "Active|bootstrap|",
        f"Active|other|{PIN}",
        f"Terminating|bootstrap|{PIN}",
    ),
    ids=("absent", "unmarked", "no-pin", "other-marker", "terminating"),
)
@pytest.mark.parametrize("operation", OPERATIONS, ids=lambda o: o[0])
def test_an_argocd_the_bootstrap_did_not_install_refuses(
    sandbox: Path, operation: tuple[str, ...], namespace: str
) -> None:
    run = run_script(sandbox, *operation, namespace=namespace, **APPLIED)
    assert run.refused
    assert "argocd-not-installed-by-the-bootstrap" in run.output
    assert run.mutations == []


@needs_bash
def test_apply_refuses_a_destination_without_the_claim(sandbox: Path) -> None:
    run = run_script(sandbox, *APPLY, claims="persistentvolumeclaim/another\n")
    assert run.refused
    assert "destination-not-prepared" in run.output
    assert run.mutations == []


@needs_bash
def test_apply_refuses_a_destination_it_cannot_read(sandbox: Path) -> None:
    """An absent namespace and an unanswered query are refused the same way."""
    run = run_script(sandbox, *APPLY, fail_on="get persistentvolumeclaims")
    assert run.refused
    assert "destination-not-prepared" in run.output
    assert run.mutations == []


@needs_bash
def test_apply_refuses_while_a_helm_release_is_recorded(sandbox: Path) -> None:
    run = run_script(
        sandbox, *APPLY, helm_records="secret/sh.helm.release.v1.inferops.v1\n"
    )
    assert run.refused
    assert "helm-release-present" in run.output
    assert run.mutations == []


@needs_bash
def test_apply_reads_helm_records_by_name_only(sandbox: Path) -> None:
    run = run_script(sandbox, *APPLY)
    (read,) = [call for call in run.kubectl if "secrets" in call]
    assert read[-2:] == ["-o", "name"]
    assert "owner=helm,name=inferops" in read


@needs_bash
@pytest.mark.parametrize(
    "stub",
    (
        {"applications": "Application/argocd/another||\n"},
        {"applications": f"Application/argocd/{APPLICATION}||\n"},
        {"applications": f"Application/argocd/{APPLICATION}|reconciliation|\n"},
        {"applications": f"Application/other/{APPLICATION}|reconciliation|{PIN}\n"},
        {"projects": "AppProject/argocd/default||\n"},
        {"projects": f"AppProject/argocd/{PROJECT}|other|{PIN}\n"},
        {"application_sets": "ApplicationSet/argocd/fleet||\n"},
    ),
    ids=(
        "another-application",
        "own-name-unmarked",
        "own-name-no-pin",
        "own-name-other-namespace",
        "default-project",
        "own-project-other-marker",
        "application-set",
    ),
)
def test_apply_refuses_an_object_it_did_not_create(
    sandbox: Path, stub: dict[str, str]
) -> None:
    run = run_script(sandbox, *APPLY, **stub)
    assert run.refused
    assert "foreign-argocd-custom-resource" in run.output
    assert run.mutations == []


@needs_bash
@pytest.mark.parametrize(
    "query",
    (
        "get namespace argocd",
        "get secrets",
        "get applications.argoproj.io --all-namespaces",
        "get appprojects.argoproj.io --all-namespaces",
        "get applicationsets.argoproj.io --all-namespaces",
        "{.metadata.generation}",
    ),
)
def test_apply_does_not_read_an_unanswered_query_as_absence(
    sandbox: Path, query: str
) -> None:
    run = run_script(sandbox, *APPLY, fail_on=query)
    assert run.refused
    assert run.mutations == []


# --------------------------------------------------------------------------
# apply: what it applies
# --------------------------------------------------------------------------


@needs_bash
def test_apply_applies_the_project_and_then_the_application(sandbox: Path) -> None:
    run = run_script(sandbox, *APPLY)
    assert run.returncode == 0, run.output
    patches = [call for call in run.kubectl if call[:2] == ["patch", "--local"]]
    assert len(patches) == 2
    assert any("workloads-project.yaml" in word for word in patches[0])
    assert any(
        "local-docker-desktop-support-assistant.yaml" in word for word in patches[1]
    )
    # Each local patch is followed by one apply, and nothing mutates before the
    # first one.
    first_patch = run.index_of("patch --local", "workloads-project.yaml")
    first_apply = run.index_of("apply --server-side")
    assert first_patch < first_apply
    assert run.stdin == ['{"stub":"document"}'] * 2
    for mutation in run.mutations:
        assert "--field-manager=inferops-argocd-application" in mutation
        assert "--force" not in mutation
        assert mutation.endswith("-f -")


@needs_bash
def test_apply_adds_the_pin_to_both_and_the_digest_to_the_application(
    sandbox: Path,
) -> None:
    run = run_script(sandbox, *APPLY)
    project_patch, application_patch = [
        " ".join(call) for call in run.kubectl if call[:2] == ["patch", "--local"]
    ]
    annotation = "inferops.io/argocd-application-manifest-sha256"
    for patch, relative in (
        (project_patch, PROJECT_REL),
        (application_patch, APPLICATION_REL),
    ):
        committed = (
            subprocess.run(
                ["sha256sum", str(sandbox / relative)],
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.split()[0]
            .lstrip("\\")
        )
        assert f'"{annotation}":"{committed}"' in patch
    assert DIGEST not in project_patch
    assert (
        '{"op":"add","path":"/spec/source/helm/parameters",'
        f'"value":[{{"name":"api.image.digest","value":"{DIGEST}"}}]}}'
    ) in application_patch


@needs_bash
def test_a_second_apply_over_its_own_objects_applies_again(sandbox: Path) -> None:
    run = run_script(sandbox, *APPLY, **APPLIED)
    assert run.returncode == 0, run.output
    assert len(run.mutations) == 2


@needs_bash
def test_apply_waits_until_the_operation_succeeded_at_the_compared_revision(
    sandbox: Path,
) -> None:
    """Synced alone does not end the wait."""
    run = run_script(
        sandbox,
        *APPLY,
        sync_polls="3",
        status_pending=f"Synced|{REVISION}|Progressing|Running||{RECONCILED}",
    )
    assert run.returncode == 0, run.output
    assert sum(1 for line in run.calls if line.startswith("sleep ")) == 3
    assert f"applied revision {REVISION}" in run.output


@needs_bash
def test_apply_does_not_accept_a_report_from_before_it_changed_the_application(
    sandbox: Path,
) -> None:
    """A second apply with another digest must not return on the old report."""
    earlier = "2026-01-01T00:00:01Z"
    run = run_script(
        sandbox,
        *APPLY,
        before=f"3|{earlier}",
        generation_after="4",
        sync_polls="2",
        status_pending=f"Synced|{REVISION}|Healthy|Succeeded|{REVISION}|{earlier}",
        **APPLIED,
    )
    assert run.returncode == 0, run.output
    assert sum(1 for line in run.calls if line.startswith("sleep ")) == 2
    assert "has not compared the changed Application yet" in run.output


@needs_bash
def test_apply_that_changes_nothing_accepts_the_current_report(sandbox: Path) -> None:
    run = run_script(
        sandbox, *APPLY, before=f"3|{RECONCILED}", generation_after="3", **APPLIED
    )
    assert run.returncode == 0, run.output
    assert not any(line.startswith("sleep ") for line in run.calls)
    assert "did not change the Application" in run.output


@needs_bash
def test_apply_reports_that_its_result_is_not_a_caller_outcome(sandbox: Path) -> None:
    run = run_script(sandbox, *APPLY)
    assert "They are not a caller outcome." in run.output
    assert "This does not establish that the workload serves a request." in run.output


@needs_bash
@pytest.mark.parametrize(
    ("live", "finding"),
    (
        (LIVE_SPEC.replace("|false|true|", "|true|true|"), "automated pruning"),
        (LIVE_SPEC.replace("|false|true|", "|false|false|"), "automated self-heal"),
        (LIVE_SPEC.replace("|main|", "|feature|"), "followed revision"),
        (LIVE_SPEC.replace(RELEASE_NAMESPACE, "default"), "destination namespace"),
        (LIVE_SPEC + '["resources-finalizer.argocd.argoproj.io"]', "finalizers"),
    ),
)
def test_apply_fails_when_the_live_application_is_not_the_decided_one(
    sandbox: Path, live: str, finding: str
) -> None:
    run = run_script(sandbox, *APPLY, live_spec=live)
    assert run.refused
    assert finding in run.output
    assert "left in place" in run.output


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------


@needs_bash
def test_verification_passes_on_the_applied_objects_and_changes_nothing(
    sandbox: Path,
) -> None:
    run = run_script(
        sandbox, "verify", workload="deployment.apps/inferops-api\n", **APPLIED
    )
    assert run.returncode == 0, run.output
    assert run.mutations == []
    assert "deployment.apps/inferops-api" in run.output
    assert f"resolved by Argo CD to {REVISION}" in run.output
    assert "They are not a caller outcome." in run.output


@needs_bash
@pytest.mark.parametrize(
    "stub",
    ({}, {"applications": OWN_APPLICATION}, {"projects": OWN_PROJECT}),
    ids=("neither", "no-project", "no-application"),
)
def test_verification_fails_when_the_two_objects_do_not_both_exist(
    sandbox: Path, stub: dict[str, str]
) -> None:
    run = run_script(sandbox, "verify", **stub)
    assert run.refused
    assert run.mutations == []


@needs_bash
def test_verification_fails_on_a_live_policy_that_prunes(sandbox: Path) -> None:
    run = run_script(
        sandbox,
        "verify",
        live_spec=LIVE_SPEC.replace("|false|true|", "|true|true|"),
        **APPLIED,
    )
    assert run.refused
    assert "automated pruning" in run.output
    assert run.mutations == []


@needs_bash
def test_verification_takes_no_option(sandbox: Path) -> None:
    run = run_script(sandbox, "verify", "--confirm", **APPLIED)
    assert run.refused
    assert run.kubectl == []


# --------------------------------------------------------------------------
# remove
# --------------------------------------------------------------------------


@needs_bash
def test_removal_without_confirmation_runs_nothing(sandbox: Path) -> None:
    run = run_script(sandbox, "remove", **APPLIED)
    assert run.refused
    assert "--confirm" in run.output
    assert run.kubectl == []


@needs_bash
def test_removal_with_nothing_applied_changes_nothing(sandbox: Path) -> None:
    run = run_script(sandbox, "remove", "--confirm")
    assert run.refused
    assert "Nothing is left to remove" in run.output
    assert run.mutations == []


@needs_bash
def test_removal_refuses_beside_an_object_it_did_not_create(sandbox: Path) -> None:
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        applications=OWN_APPLICATION + "Application/argocd/another||\n",
        projects=OWN_PROJECT,
    )
    assert run.refused
    assert "foreign-argocd-custom-resource" in run.output
    assert run.mutations == []


@needs_bash
@pytest.mark.parametrize("ready", ("", "0"))
def test_removal_refuses_while_the_controller_is_not_ready(
    sandbox: Path, ready: str
) -> None:
    run = run_script(sandbox, "remove", "--confirm", controller_ready=ready, **APPLIED)
    assert run.refused
    assert "application-controller-not-ready" in run.output
    assert run.mutations == []


@needs_bash
def test_removal_cascades_and_then_deletes_the_project(sandbox: Path) -> None:
    run = run_script(sandbox, "remove", "--confirm", residue_polls="2", **APPLIED)
    assert run.returncode == 0, run.output
    finalizer, application, project = run.mutations
    assert finalizer.startswith(
        f"patch applications.argoproj.io {APPLICATION} -n argocd"
    )
    assert "resources-finalizer.argocd.argoproj.io" in finalizer
    assert application.startswith(
        f"delete applications.argoproj.io {APPLICATION} -n argocd"
    )
    assert project.startswith(f"delete appprojects.argoproj.io {PROJECT} -n argocd")
    # The project is deleted only after the residue question returned nothing.
    residue_reads = [
        index
        for index, line in enumerate(run.calls)
        if "get deployments,replicasets,pods" in line
    ]
    assert len(residue_reads) == 3
    assert residue_reads[-1] < run.index_of("delete appprojects.argoproj.io")
    for deletion in (application, project):
        assert "--timeout=" in deletion


@needs_bash
def test_removal_keeps_the_project_when_it_cannot_ask_for_residue(
    sandbox: Path,
) -> None:
    run = run_script(
        sandbox,
        "remove",
        "--confirm",
        fail_on="get deployments,replicasets,pods",
        **APPLIED,
    )
    assert run.refused
    assert not any(m.startswith("delete appprojects") for m in run.mutations)


@needs_bash
def test_removal_fails_when_a_claim_is_gone_afterwards(sandbox: Path) -> None:
    run = run_script(sandbox, "remove", "--confirm", claims_after="", **APPLIED)
    assert run.refused
    assert "must not delete a claim" in run.output


@needs_bash
def test_removal_of_a_project_alone_deletes_no_application(sandbox: Path) -> None:
    run = run_script(sandbox, "remove", "--confirm", projects=OWN_PROJECT)
    assert run.returncode == 0, run.output
    (deletion,) = run.mutations
    assert deletion.startswith(f"delete appprojects.argoproj.io {PROJECT}")


@needs_bash
def test_removal_touches_only_the_two_named_objects(sandbox: Path) -> None:
    run = run_script(sandbox, "remove", "--confirm", **APPLIED)
    for mutation in run.mutations:
        words = mutation.split()
        assert words[1] in ("applications.argoproj.io", "appprojects.argoproj.io")
        assert words[2] in (APPLICATION, PROJECT)
        assert words[3:5] == ["-n", ARGOCD_NAMESPACE]
        assert "--all" not in mutation
        assert "-l" not in words


@needs_bash
@pytest.mark.parametrize(
    "arguments",
    (
        ("install",),
        ("apply", "--api-image-digest", DIGEST, "--confirm"),
        ("apply", "--api-image-digest", DIGEST, "--api-image-digest", DIGEST),
        ("remove", "--confirm", "--api-image-digest", DIGEST),
        ("verify", "--prune"),
        (),
    ),
)
def test_an_argument_the_procedure_does_not_understand_runs_nothing(
    sandbox: Path, arguments: tuple[str, ...]
) -> None:
    run = run_script(sandbox, *arguments)
    assert run.refused
    assert run.kubectl == []
