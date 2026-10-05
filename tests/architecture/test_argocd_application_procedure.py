"""The Application procedure, executed against stub tools.

`tests/architecture/test_argocd_application.py` reads the procedure as text. This
suite runs it. Every external tool is a stub that logs its call and answers from
the environment, so each test states what the cluster holds and reads what the
procedure did about it.

Evidence level: `C1`, substituted execution. The procedure and `lib.sh` are the
committed bytes. kubectl, kind, docker, and sleep are stubs. No cluster is
contacted, no Argo CD runs, and no chart is rendered.

What it establishes: the order of the procedure's calls, that each refusal comes
before the first mutation, what the two apply requests are given, what the
removal deletes, and what an observation reads and writes. What it does not establish: that Argo CD reconciles the release,
that a cascade deletes the workload, or anything a real API server answers. The
stub answers what the test tells it to answer. No test reaches a time limit.
"""

from __future__ import annotations

import hashlib
import json
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
SYNCED = (
    f"Synced|{REVISION}|Healthy|Succeeded|{REVISION}|{RECONCILED}|{DIGEST}|{DIGEST}"
)
DECIDED_TARGET = f"{PROJECT}|https://kubernetes.default.svc|{RELEASE_NAMESPACE}"
# What the stub prints for the spec of each committed manifest. The live
# objects print the same strings unless a test says otherwise.
PROJECT_SPEC = "committed-project-spec"
APPLICATION_SPEC = "committed-application-spec"
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
  *"get applications.argoproj.io local-docker-desktop-support-assistant"*"-o json")
    printf '%s' "${STUB_APPLICATION_JSON:-}"
    ;;
  *"patch --local"*"jsonpath={.spec}"*"workloads-project.yaml"*) printf 'committed-project-spec' ;;
  *"patch --local"*"jsonpath={.spec}"*) printf 'committed-application-spec' ;;
  *"patch --local"*) printf '{"stub":"document"}\\n' ;;
  *"get appprojects.argoproj.io inferops-workloads"*"|{.spec}"*) printf '%s' "${STUB_LIVE_PROJECT:-}" ;;
  *"get applications.argoproj.io local-docker-desktop-support-assistant"*"|{.spec}"*)
    printf '%s' "${STUB_LIVE_APPLICATION:-}"
    ;;
  *"get applications.argoproj.io local-docker-desktop-support-assistant"*"jsonpath={.spec.source.helm.parameters[0].value}")
    printf '%s' "${STUB_LIVE_DIGEST:-}"
    ;;
  *"get applications.argoproj.io local-docker-desktop-support-assistant"*"{.spec.project}|{.spec.destination.server}"*)
    printf '%s' "${STUB_LIVE_TARGET:-}"
    ;;
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


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document_patches(run: Run) -> list[list[str]]:
    """The two local patches that build the documents `apply` sends."""
    return [
        call
        for call in run.kubectl
        if call[:2] == ["patch", "--local"] and call[call.index("-o") + 1] == "json"
    ]


def patch_operations(call: list[str]) -> list[dict]:
    """The JSON patch a call was given, parsed. A malformed patch fails here."""
    return json.loads(call[call.index("-p") + 1])


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
    env["STUB_LIVE_PROJECT"] = f"{sha256_of(sandbox / PROJECT_REL)}|{PROJECT_SPEC}"
    env["STUB_LIVE_APPLICATION"] = (
        f"{sha256_of(sandbox / APPLICATION_REL)}|{APPLICATION_SPEC}"
    )
    env["STUB_LIVE_DIGEST"] = DIGEST
    env["STUB_LIVE_TARGET"] = DECIDED_TARGET
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
    patches = document_patches(run)
    assert len(patches) == 2
    assert any("workloads-project.yaml" in word for word in patches[0])
    assert any(
        "local-docker-desktop-support-assistant.yaml" in word for word in patches[1]
    )
    # Each local patch is followed by one apply, and nothing mutates before the
    # first one.
    # Both documents are built before the first apply, so a manifest that
    # cannot be read leaves nothing half applied.
    first_apply = run.index_of("apply --server-side")
    assert (
        run.index_of("patch --local", "-o json", "workloads-project.yaml") < first_apply
    )
    assert (
        run.index_of("patch --local", "-o json", "support-assistant.yaml") < first_apply
    )
    assert run.stdin == ['{"stub":"document"}'] * 2
    for mutation in run.mutations:
        assert "--field-manager=inferops-argocd-application" in mutation
        assert "--force" not in mutation
        assert mutation.endswith("-f -")


@needs_bash
def test_apply_adds_the_pin_to_both_and_the_digest_to_the_application(
    sandbox: Path,
) -> None:
    """Each patch is parsed, so a malformed one fails, and compared as a whole."""
    run = run_script(sandbox, *APPLY)
    project_patch, application_patch = document_patches(run)
    annotation = "inferops.io/argocd-application-manifest-sha256"

    def pin(relative: str) -> dict:
        return {
            "op": "add",
            "path": "/metadata/annotations",
            "value": {annotation: sha256_of(sandbox / relative)},
        }

    assert patch_operations(project_patch) == [pin(PROJECT_REL)]
    assert patch_operations(application_patch) == [
        pin(APPLICATION_REL),
        {
            "op": "add",
            "path": "/spec/source/helm/parameters",
            "value": [{"name": "api.image.digest", "value": DIGEST}],
        },
    ]


@needs_bash
def test_apply_applies_nothing_when_a_manifest_cannot_be_read(sandbox: Path) -> None:
    """The first version applied the project before it read the Application file."""
    run = run_script(sandbox, *APPLY, fail_on="support-assistant.yaml")
    assert run.refused
    assert "Nothing was changed" in run.output
    assert run.mutations == []


@needs_bash
def test_apply_does_not_end_on_a_report_about_another_digest(sandbox: Path) -> None:
    """A comparison that started before the apply can finish after it.

    It carries a new comparison time and the earlier digest. The wait ends only
    on the digest that this apply was given.
    """
    other = "sha256:" + "d" * 64
    run = run_script(
        sandbox,
        *APPLY,
        before="3|2026-01-01T00:00:01Z",
        generation_after="4",
        sync_polls="2",
        status_pending=(
            f"Synced|{REVISION}|Healthy|Succeeded|{REVISION}|{RECONCILED}|{other}|{other}"
        ),
        **APPLIED,
    )
    assert run.returncode == 0, run.output
    assert sum(1 for line in run.calls if line.startswith("sleep ")) == 2


@needs_bash
@pytest.mark.parametrize("operation", (APPLY, ("verify",)), ids=lambda o: o[0])
@pytest.mark.parametrize(
    ("stub", "finding"),
    (
        ({"live_project": "PIN|another-spec"}, "spec of the live project differs"),
        (
            {"live_application": "PIN|another-spec"},
            "spec of the live Application differs",
        ),
        ({"live_project": f"{'e' * 64}|{PROJECT_SPEC}"}, "applied from other bytes"),
        (
            {"live_application": f"{'e' * 64}|{APPLICATION_SPEC}"},
            "applied from other bytes",
        ),
    ),
    ids=("project-spec", "application-spec", "project-pin", "application-pin"),
)
def test_a_live_object_that_is_not_the_committed_one_is_a_finding(
    sandbox: Path, operation: tuple[str, ...], stub: dict[str, str], finding: str
) -> None:
    """The whole spec and the recorded SHA-256 of both objects are compared.

    The first version read nine fields of the Application and none of the
    project. A sync option, a second source, another values file, or a project
    that admits every kind passed it.
    """
    values = {
        key: value.replace(
            "PIN",
            sha256_of(
                sandbox / (PROJECT_REL if key == "live_project" else APPLICATION_REL)
            ),
        )
        for key, value in stub.items()
    }
    run = run_script(sandbox, *operation, **APPLIED, **values)
    assert run.refused
    assert finding in run.output
    assert "The live objects are not the ones that were decided" in run.output


@needs_bash
def test_verification_reads_the_digest_from_the_live_application(sandbox: Path) -> None:
    run = run_script(sandbox, "verify", live_digest="not-a-digest", **APPLIED)
    assert run.refused
    assert "is not an image digest" in run.output
    assert run.mutations == []


@needs_bash
def test_verification_refuses_beside_an_object_it_did_not_create(sandbox: Path) -> None:
    run = run_script(
        sandbox,
        "verify",
        applications=OWN_APPLICATION + "Application/argocd/another||\n",
        projects=OWN_PROJECT,
    )
    assert run.refused
    assert "foreign-argocd-custom-resource" in run.output
    assert run.mutations == []


@needs_bash
@pytest.mark.parametrize(
    "target",
    (
        f"{PROJECT}|https://kubernetes.default.svc|default",
        f"{PROJECT}|https://203.0.113.7|{RELEASE_NAMESPACE}",
        f"default|https://kubernetes.default.svc|{RELEASE_NAMESPACE}",
        "",
    ),
    ids=("namespace", "server", "project", "unreadable-fields"),
)
def test_removal_refuses_a_live_application_with_another_destination(
    sandbox: Path, target: str
) -> None:
    """The cascade deletes what the live Application manages."""
    run = run_script(sandbox, "remove", "--confirm", live_target=target, **APPLIED)
    assert run.refused
    assert "live-application-differs" in run.output
    assert run.mutations == []


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
    assert "has not compared the Application since the apply" in run.output


@needs_bash
def test_apply_that_changes_nothing_accepts_the_current_report(sandbox: Path) -> None:
    run = run_script(
        sandbox, *APPLY, before=f"3|{RECONCILED}", generation_after="3", **APPLIED
    )
    assert run.returncode == 0, run.output
    assert not any(line.startswith("sleep ") for line in run.calls)
    assert "did not change across the apply" in run.output


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


# --------------------------------------------------------------------------
# observe
# --------------------------------------------------------------------------

OBSERVE = ("observe", "--samples", "3", "--interval", "7", "--into", "run-1")
OBSERVATION_REL = ".artifacts/argocd-application/observations/run-1"
# The evidence tool does not accept one repeated character as a commit, so the
# observation reports another value than the apply cases use.
OBSERVED_REVISION = "0123456789abcdef0123456789abcdef01234567"
REPORTED_APPLICATION = json.dumps(
    {
        "kind": "Application",
        "metadata": {"name": APPLICATION},
        "spec": {"source": {"targetRevision": "main"}},
        "status": {
            "sync": {"status": "Synced", "revision": OBSERVED_REVISION},
            "health": {"status": "Healthy"},
            "operationState": {
                "phase": "Succeeded",
                "syncResult": {"revision": OBSERVED_REVISION},
            },
        },
    }
)
OBSERVED_OBJECT = (
    'Deployment\tinferops-inferops-llm\t{"helm.sh/chart":"inferops-llm-0.3.0"}\n'
)


@needs_bash
def test_observation_reads_a_bounded_number_of_times_and_changes_nothing(
    sandbox: Path,
) -> None:
    run = run_script(
        sandbox,
        *OBSERVE,
        application_json=REPORTED_APPLICATION,
        workload=OBSERVED_OBJECT,
    )
    assert run.returncode == 0, run.output
    assert run.mutations == []
    reads = [
        call for call in run.kubectl if call[:2] == ["get", "applications.argoproj.io"]
    ]
    assert len(reads) == 3
    for call in reads:
        assert call[2:6] == [APPLICATION, "-n", ARGOCD_NAMESPACE, "--ignore-not-found"]
        assert call[-2:] == ["-o", "json"]
    assert (
        sum(
            1
            for call in run.kubectl
            if call[:2]
            == [
                "get",
                "deployments,replicasets,pods,jobs,services,configmaps,serviceaccounts,networkpolicies,roles,rolebindings",
            ]
        )
        == 3
    )
    # One wait between two samples, and none after the last one.
    assert [line for line in run.calls if line.startswith("sleep ")] == ["sleep 7"] * 2
    assert "They are not a caller outcome." in run.output
    assert "It is not a healthy state." in run.output

    directory = sandbox / OBSERVATION_REL
    assert sorted(entry.name for entry in directory.iterdir()) == [
        "collection.end",
        "collection.meta",
        *(
            f"sample-00{n}.{suffix}"
            for n in (1, 2, 3)
            for suffix in ("application.json", "meta", "objects.txt")
        ),
    ]
    header = (directory / "collection.meta").read_text(encoding="utf-8")
    assert "requestedSamples=3\n" in header and "intervalSeconds=7\n" in header
    assert f"procedureSha256={sha256_of(sandbox / SCRIPT_REL)}\n" in header
    assert (directory / "collection.end").read_text(encoding="utf-8") == (
        "completedSamples=3\n"
    )


@needs_bash
def test_the_evidence_tool_reads_what_the_observation_wrote(sandbox: Path) -> None:
    """The file format, held by execution on both sides of it."""
    from tools.reconciliation_evidence import build_record

    run = run_script(
        sandbox,
        *OBSERVE,
        application_json=REPORTED_APPLICATION,
        workload=OBSERVED_OBJECT,
    )
    assert run.returncode == 0, run.output
    record = build_record(sandbox / OBSERVATION_REL)
    assert record["collection"]["complete"] is True
    assert record["collection"]["intervalSeconds"] == {"state": "reported", "value": 7}
    assert record["summary"]["applicationReads"]["reported"] == 3
    assert record["summary"]["samplesSettled"] == 3
    assert record["summary"]["resolvedRevisions"] == [OBSERVED_REVISION]
    assert record["transitions"] == []
    for sample in record["samples"]:
        assert sample["objectsRead"] == "collected"
        (entry,) = record["objectSets"][sample["objectSet"]]
        assert entry["kind"] == "Deployment"
        assert entry["labels"]["helm.sh/chart"] == {
            "state": "reported",
            "value": "inferops-llm-0.3.0",
        }
        assert entry["labels"]["inferops.io/workload"] == {"state": "missing"}


@needs_bash
def test_an_absent_application_is_an_observation_and_not_a_refusal(
    sandbox: Path,
) -> None:
    from tools.reconciliation_evidence import build_record

    run = run_script(sandbox, *OBSERVE, namespace="")
    assert run.returncode == 0, run.output
    record = build_record(sandbox / OBSERVATION_REL)
    assert record["summary"]["applicationReads"]["absent"] == 3
    assert record["summary"]["samplesSettled"] == 0
    for sample in record["samples"]:
        assert sample["objectsRead"] == "collected"
        assert record["objectSets"][sample["objectSet"]] == []


@needs_bash
@pytest.mark.parametrize(
    ("fail_on", "application_read", "objects_read"),
    (
        ("--ignore-not-found -o json", "unanswered", "collected"),
        ("get deployments,replicasets,pods", "reported", "unanswered"),
    ),
    ids=("application", "objects"),
)
def test_a_read_that_did_not_answer_is_recorded_as_unanswered(
    sandbox: Path, fail_on: str, application_read: str, objects_read: str
) -> None:
    from tools.reconciliation_evidence import build_record

    run = run_script(
        sandbox,
        *OBSERVE,
        application_json=REPORTED_APPLICATION,
        workload=OBSERVED_OBJECT,
        fail_on=fail_on,
    )
    # The observation goes on: an unanswered read is a sample.
    assert run.returncode == 0, run.output
    assert run.output.count("unanswered") >= 3
    directory = sandbox / OBSERVATION_REL
    kept = {entry.name for entry in directory.iterdir()}
    if application_read == "unanswered":
        assert not any(name.endswith(".application.json") for name in kept)
    else:
        assert not any(name.endswith(".objects.txt") for name in kept)
    record = build_record(directory)
    assert record["collection"]["complete"] is True
    for sample in record["samples"]:
        assert sample["applicationRead"] == application_read
        assert sample["objectsRead"] == objects_read
    assert record["summary"]["samplesSettled"] == (
        3 if application_read == "reported" else 0
    )


@needs_bash
def test_observation_does_not_write_into_an_existing_directory(sandbox: Path) -> None:
    existing = sandbox / OBSERVATION_REL
    existing.mkdir(parents=True)
    (existing / "kept.txt").write_text("kept", encoding="utf-8")
    run = run_script(sandbox, *OBSERVE, application_json=REPORTED_APPLICATION)
    assert run.refused
    assert "observation-directory-exists" in run.output
    # Before the target is verified. The first version of the procedure
    # verified the target first, which reads the cluster, and then said that
    # nothing was read.
    assert run.kubectl == []
    assert [entry.name for entry in existing.iterdir()] == ["kept.txt"]


@needs_bash
@pytest.mark.parametrize(
    "arguments",
    (
        ("observe",),
        ("observe", "--samples", "3", "--interval", "7"),
        ("observe", "--samples", "3", "--into", "run-1"),
        ("observe", "--interval", "7", "--into", "run-1"),
        ("observe", "--samples", "0", "--interval", "7", "--into", "run-1"),
        ("observe", "--samples", "121", "--interval", "7", "--into", "run-1"),
        ("observe", "--samples", "3x", "--interval", "7", "--into", "run-1"),
        ("observe", "--samples", "3", "--interval", "0", "--into", "run-1"),
        ("observe", "--samples", "3", "--interval", "31", "--into", "run-1"),
        ("observe", "--samples", "3", "--interval", "7", "--into", "../run"),
        ("observe", "--samples", "3", "--interval", "7", "--into", "Run"),
        ("observe", "--samples", "3", "--interval", "7", "--into", "a" * 64),
    ),
)
def test_observation_without_stated_bounds_reads_nothing(
    sandbox: Path, arguments: tuple[str, ...]
) -> None:
    run = run_script(sandbox, *arguments)
    assert run.refused
    assert "observation-bounds-not-given" in run.output
    assert run.kubectl == []
    assert not (sandbox / ".artifacts").exists()


@needs_bash
def test_the_largest_interval_and_the_longest_name_are_accepted(
    sandbox: Path,
) -> None:
    """The largest count is not executed here: 240 stub reads are slow. The
    static suite reads the two limits, and a count of 121 is refused above."""
    run = run_script(
        sandbox, "observe", "--samples", "2", "--interval", "30", "--into", "a" * 63
    )
    assert run.returncode == 0, run.output
    assert [line for line in run.calls if line.startswith("sleep ")] == ["sleep 30"]


@needs_bash
def test_observation_selects_and_verifies_the_target_first(sandbox: Path) -> None:
    run = run_script(sandbox, *OBSERVE, provider=None)
    assert run.refused
    assert run.kubectl == []
    run = run_script(sandbox, *OBSERVE, api_node="some-other-control-plane")
    assert run.refused
    assert not any("argoproj.io" in " ".join(call) for call in run.kubectl)
    assert not (sandbox / ".artifacts").exists()


@needs_bash
@pytest.mark.parametrize(
    "arguments",
    (
        ("install",),
        ("apply", "--api-image-digest", DIGEST, "--confirm"),
        ("apply", "--api-image-digest", DIGEST, "--api-image-digest", DIGEST),
        ("remove", "--confirm", "--api-image-digest", DIGEST),
        ("verify", "--prune"),
        ("verify", "--samples", "3"),
        ("apply", "--api-image-digest", DIGEST, "--into", "run-1"),
        ("remove", "--confirm", "--interval", "7"),
        (*OBSERVE, "--confirm"),
        (*OBSERVE, "--api-image-digest", DIGEST),
        (*OBSERVE, "--samples", "3"),
        (),
    ),
)
def test_an_argument_the_procedure_does_not_understand_runs_nothing(
    sandbox: Path, arguments: tuple[str, ...]
) -> None:
    run = run_script(sandbox, *arguments)
    assert run.refused
    assert run.kubectl == []
