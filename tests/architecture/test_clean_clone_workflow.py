"""The clean-clone workflow, executed rather than read.

`scripts/environment/clean-clone.sh` is an orchestrator: it runs workflows that
already exist, in the order `docs/environment/clean-clone.v1alpha1.json` states,
and records each one in a ledger `tools.clean_clone` keeps. What can go wrong with
an orchestrator is not in any one step. It is in the joins: a step run without the
consent it needs, a real step skipped quietly, a run resumed on top of a cleanup, a
failure that carries on to the next step, and -- the one that matters most -- a
cleanup that removes something the run did not create.

So this module runs the committed script. It copies `lib.sh` and `clean-clone.sh`
byte for byte into a sandbox laid out like the repository, together with the
`tools.clean_clone` package and the checklist, and replaces everything they call
with a recording stub: the sibling workflows beside them, and `kubectl`, `helm`,
`kind`, `docker`, `uv`, and `df` on a closed `PATH` that also holds the real
`git`, because the sandbox is a committed repository of its own and whether its
checkout is clean is a question the workflow asks git. `python` is a stub
that hands `-m tools.clean_clone` and `-c` to the real interpreter and records
everything else. Terraform's apply and destroy add and remove the release
namespace in a small state file the `kubectl` stub reads back, so what the
cleanup sees is what the run before it did.

No cluster is contacted, no image built, no model downloaded, and nothing outside
the sandbox is touched. The provider throughout is `kind`, because its identity
check can be satisfied by stubs without imitating Docker Desktop's port binding.
The orchestrator branches on the provider in two places -- `kind` is a required
tool only when it is selected, and only `kind` passes a cluster name to the ledger
-- and the `docker-desktop` side of both is not executed here. Whether a complete
run certifies anything *is* provider-specific and is tested on the ledger
directly, in `test_clean_clone_ledger.py`.

What this establishes is the orchestration: order, consent, resumption, the
ledger, and the boundary of the cleanup. It establishes nothing about whether any
step's real workflow works, which is each workflow's own evidence.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tools.clean_clone import load_descriptor, steps

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = "scripts/environment/clean-clone.sh"
LIB_REL = "scripts/environment/lib.sh"
DESCRIPTOR_REL = "docs/environment/clean-clone.v1alpha1.json"
BASE_VALUES_REL = "charts/inferops-llm/ci/real-values.yaml"

BASH = shutil.which("bash")
GIT = shutil.which("git")
needs_bash = pytest.mark.skipif(
    BASH is None or GIT is None,
    reason="bash or git is not installed; the executable clean-clone tests skip, loudly",
)

# Restated rather than imported from lib.sh, so that a change to either is noticed.
RELEASE_NAMESPACE = "inferops-release"
CLUSTER = "inferops-dev"
CONTEXT = f"kind-{CLUSTER}"
NODE = f"{CLUSTER}-control-plane"
ALL_CONSENT = (
    "--confirm-downloads",
    "--confirm-real-runtime",
    "--confirm-real-kubernetes",
)
NAMESPACES_BEFORE = (
    "namespace/default",
    "namespace/kube-system",
    "namespace/unrelated-work",
)
API_DIGEST = "sha256:" + "a" * 64
SEED_DIGEST = "sha256:" + "b" * 64

_VERSION_JSON = (
    '{"clientVersion": {"major": "1", "minor": "34", "gitVersion": "v1.34.1"},'
    ' "serverVersion": {"major": "1", "minor": "34", "gitVersion": "v1.34.8"}}'
)

# --------------------------------------------------------------------------
# The stubs
# --------------------------------------------------------------------------
#
# Each appends `<name> <arguments>` to $STUB_LOG first, so the log is the ordered
# record of everything the orchestrator tried to run, including what then failed.
# STUB_FAIL names one sibling workflow that exits 1, for the failure scenarios.

_LOG = 'printf \'%s %s\\n\' "$(basename "$0")" "$*" >>"${STUB_LOG}"\n'

_KUBECTL = (
    "#!/usr/bin/env bash\n"
    + _LOG
    + """case "$*" in
  *"config get-contexts"*) printf '%s\\n' "${STUB_CONTEXT}" ;;
  *"config view --minify"*) printf 'kind: Config\\ncurrent-context: %s\\n' "${STUB_CONTEXT}" ;;
  *"config current-context"*) printf '%s\\n' "${STUB_CONTEXT}" ;;
  *"get namespace kube-system"*) printf '%s' "${STUB_CLUSTER_UID:-uid-first-cluster}" ;;
  *"get namespaces -o name"*)
    if [ -n "${STUB_CRLF:-}" ]; then sed 's/$/\\r/' "${STUB_STATE}/namespaces"
    else cat "${STUB_STATE}/namespaces"; fi
    ;;
  *"get nodes -o name"*) printf 'node/%s\\n' "${STUB_NODE}" ;;
  *"get nodes"*"Ready"*)
    if [ -n "${STUB_CRLF:-}" ]; then printf '%s %s\\r\\n' "${STUB_NODE}" "${STUB_NODE_READY:-True}"
    else printf '%s %s\\n' "${STUB_NODE}" "${STUB_NODE_READY:-True}"; fi
    ;;
  *"version"*) printf '%s' "${STUB_VERSION_JSON}" ;;
esac
exit 0
"""
)

_HELM = (
    "#!/usr/bin/env bash\n"
    + _LOG
    + """case "$*" in
  *" list "*)
    [ "${STUB_HELM_LIST:-ok}" = "ok" ] || { printf 'Error: cluster unreachable\\n' >&2; exit 1; }
    cat "${STUB_STATE}/releases"
    ;;
  *" uninstall "*) : >"${STUB_STATE}/releases" ;;
esac
exit 0
"""
)

_KIND = (
    "#!/usr/bin/env bash\n"
    + _LOG
    + """[ "$*" = "get clusters" ] && printf '%s\\n' "${STUB_KIND_CLUSTERS}"
exit 0
"""
)

_DOCKER = (
    "#!/usr/bin/env bash\n"
    + _LOG
    + """case "$1" in
  version) printf '27.0.0\\n' ;;
  ps) printf '%s\\n' "${STUB_NODE}" ;;
  info)
    case "$*" in
      *NCPU*) printf '12\\n' ;;
      *MemTotal*) printf '10432532480\\n' ;;
    esac
    ;;
esac
exit 0
"""
)

_UV = (
    "#!/usr/bin/env bash\n"
    + _LOG
    + """[ "$1" = "sync" ] && mkdir -p .venv/bin
exit 0
"""
)

# Far more than the ADR 0001 tier, so the disk check passes on a test host whose
# temporary volume happens to be short of 20 GB.
_DF = """#!/usr/bin/env bash
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\n'
printf 'stub 1000000000 1 900000000 1%% /\\n'
"""

_PYTHON = (
    "#!/usr/bin/env bash\n"
    + """if [ "${1:-}" = "-c" ]; then exec "${REAL_PYTHON}" "$@"; fi
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "tools.clean_clone" ]; then
  # Only the subcommand itself, which reads the runtime package this sandbox does
  # not carry -- not `requires --step runtime-image`, which the real tool answers.
  case " $* " in
    *" --step runtime-image "*) ;;
    *" runtime-image "*)
      printf 'python %s\\n' "$*" >>"${STUB_LOG}"
      printf 'ghcr.io/example/runtime@sha256:%s\\n' "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
      exit 0
      ;;
  esac
  exec "${REAL_PYTHON}" "$@"
fi
"""
    + _LOG.replace('"$(basename "$0")"', "python")
    + "exit 0\n"
)

# The sibling workflows the orchestrator runs, by name.
_SIBLING = (
    "#!/usr/bin/env bash\n"
    + _LOG
    + """name="$(basename "$0")"
[ "${STUB_FAIL:-}" != "${name}" ] || exit 1
case "${name}:$1" in
  api-image.sh:values) printf 'api:\\n  image:\\n    repository: localhost/inferops-api\\n    digest: %s\\n    pullPolicy: Never\\n' "${STUB_API_DIGEST}" ;;
  model-seed-image.sh:values) printf 'model:\\n  acquisition:\\n    source: seed-image\\n    seedImage:\\n      digest: %s\\n' "${STUB_SEED_DIGEST}" ;;
  terraform-prerequisites.sh:apply)
    grep -Fxq "namespace/inferops-release" "${STUB_STATE}/namespaces" ||
      printf 'namespace/inferops-release\\n' >>"${STUB_STATE}/namespaces"
    ;;
  terraform-prerequisites.sh:destroy)
    [ ! -s "${STUB_STATE}/releases" ] || { printf 'refusing: a release is installed\\n' >&2; exit 1; }
    grep -Fxv "namespace/inferops-release" "${STUB_STATE}/namespaces" >"${STUB_STATE}/ns.tmp" || true
    mv "${STUB_STATE}/ns.tmp" "${STUB_STATE}/namespaces"
    ;;
esac
exit 0
"""
)

SIBLINGS = (
    "target-detect.sh",
    "api-image.sh",
    "model-seed-image.sh",
    "terraform-prerequisites.sh",
    "helm-lifecycle.sh",
    "kubernetes-certification.sh",
    "telemetry-collection-verify.sh",
    "performance-scenarios.sh",
    "inference-pod-recovery.sh",
)

_TOOLS = {
    "kubectl": _KUBECTL,
    "helm": _HELM,
    "kind": _KIND,
    "docker": _DOCKER,
    "uv": _UV,
    "df": _DF,
    # Asked for by the host prerequisites and run only by the sibling workflows,
    # which are stubs here; a call from the orchestrator itself would be logged.
    "terraform": "#!/usr/bin/env bash\n" + _LOG + "exit 0\n",
    "python": _PYTHON,
}


# --------------------------------------------------------------------------
# The harness
# --------------------------------------------------------------------------


@dataclass
class Run:
    returncode: int
    output: str
    calls: list[str]
    root: Path

    def ran(self, command: str, *fragments: str) -> bool:
        return any(
            line.startswith(f"{command} ") and all(f in line for f in fragments)
            for line in self.calls
        )

    def index(self, command: str, *fragments: str) -> int:
        for position, line in enumerate(self.calls):
            if line.startswith(f"{command} ") and all(f in line for f in fragments):
                return position
        raise AssertionError(f"{command} {fragments} never ran: {self.calls}")

    @property
    def ledger(self) -> dict:
        path = self.root / ".artifacts" / "clean-clone" / "ledger.v1alpha1.json"
        data: dict = json.loads(path.read_text(encoding="utf-8"))
        return data

    @property
    def has_ledger(self) -> bool:
        return (
            self.root / ".artifacts" / "clean-clone" / "ledger.v1alpha1.json"
        ).exists()

    def outcomes(self) -> dict[str, str]:
        return {a["stepId"]: a["outcome"] for a in self.ledger["attempts"]}

    def namespaces(self) -> list[str]:
        text = (self.root / "state" / "namespaces").read_text(encoding="utf-8")
        return [line for line in text.splitlines() if line]


class Sandbox:
    def __init__(self, root: Path) -> None:
        self.root = root

    def copy(self, destination: Path) -> Sandbox:
        """An independent copy, so that one expensive run can seed many scenarios."""
        shutil.copytree(self.root, destination)
        return Sandbox(destination)

    def write_state(self, name: str, lines: list[str]) -> None:
        (self.root / "state" / name).write_text(
            "".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n"
        )

    def run(self, *args: str, **env: str) -> Run:
        log = self.root / "calls.log"
        log.write_text("", encoding="utf-8")
        environment = dict(os.environ)
        for key in list(environment):
            if key.startswith(("INFEROPS_", "STUB_")):
                del environment[key]
        assert BASH is not None and GIT is not None
        environment.update(
            {
                "PATH": os.pathsep.join(
                    [
                        str(self.root / "bin"),
                        str(Path(BASH).parent),
                        str(Path(GIT).parent),
                    ]
                ),
                "STUB_LOG": str(log),
                "STUB_STATE": (self.root / "state").as_posix(),
                "STUB_CONTEXT": CONTEXT,
                "STUB_NODE": NODE,
                "STUB_KIND_CLUSTERS": CLUSTER,
                "STUB_VERSION_JSON": _VERSION_JSON,
                "STUB_API_DIGEST": API_DIGEST,
                "STUB_SEED_DIGEST": SEED_DIGEST,
                "REAL_PYTHON": Path(sys.executable).as_posix(),
                "INFEROPS_PROVIDER": "kind",
                "INFEROPS_KIND_CLUSTER_NAME": CLUSTER,
                "INFEROPS_TARGET_KUBECONFIG_POSIX_PATH": (
                    self.root / ".kube" / "inferops-target.config"
                ).as_posix(),
            }
        )
        environment.update(env)
        for key in [k for k, v in environment.items() if v == ""]:
            del environment[key]
        completed = subprocess.run(
            [BASH, SCRIPT_REL, *args],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        calls = [line for line in log.read_text(encoding="utf-8").splitlines() if line]
        return Run(
            completed.returncode, completed.stdout + completed.stderr, calls, self.root
        )


def build_sandbox(root: Path) -> Sandbox:
    """A directory laid out like the repository, holding the committed files.

    The orchestrator derives the repository root from `lib.sh`'s own location, so
    a copy two directories below the sandbox root treats the sandbox as the
    repository: its ledger, its snapshots, and its scaffolds all land here.
    `lib.sh`, `clean-clone.sh`, the checklist, and the `tools.clean_clone` package
    are copied byte for byte and never adapted.
    """
    scripts = root / "scripts" / "environment"
    scripts.mkdir(parents=True)
    for rel in (LIB_REL, SCRIPT_REL):
        shutil.copyfile(REPO_ROOT / rel, scripts / Path(rel).name)
    for name in SIBLINGS:
        stub = scripts / name
        stub.write_text(_SIBLING, encoding="utf-8", newline="\n")
        stub.chmod(0o755)

    for rel in (DESCRIPTOR_REL, BASE_VALUES_REL):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, root / rel)
    package = root / "tools" / "clean_clone"
    package.mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / "tools" / "__init__.py", root / "tools" / "__init__.py")
    for source in (REPO_ROOT / "tools" / "clean_clone").glob("*.py"):
        shutil.copyfile(source, package / source.name)

    bin_dir = root / "bin"
    bin_dir.mkdir()
    for name, body in _TOOLS.items():
        stub = bin_dir / name
        stub.write_text(body, encoding="utf-8", newline="\n")
        stub.chmod(0o755)

    sandbox = Sandbox(root)
    (root / "state").mkdir()
    sandbox.write_state("namespaces", list(NAMESPACES_BEFORE))
    sandbox.write_state("releases", [])

    # A committed repository, so that "is this checkout clean" has a real answer.
    # The ignore list is the harness's own scaffolding plus the paths the
    # repository's own .gitignore ignores that a run writes.
    (root / "README.md").write_text("sandbox\n", encoding="utf-8", newline="\n")
    (root / ".gitignore").write_text(
        "bin/\nstate/\ncalls.log\n.artifacts/\n.kube/\n.cache/\n.venv/\n__pycache__/\n",
        encoding="utf-8",
        newline="\n",
    )
    assert GIT is not None
    identity = ["-c", "user.name=sandbox", "-c", "user.email=sandbox@example.invalid"]
    for command in (
        ["init", "-q"],
        ["add", "-A"],
        [*identity, "commit", "-q", "-m", "sandbox"],
    ):
        subprocess.run([GIT, *command], cwd=root, check=True, capture_output=True)
    return sandbox


# Every orchestrator run starts dozens of processes, which is slow on Windows. The
# expensive runs are therefore made once per module, into a template, and each
# scenario that continues from one works on its own copy of it.


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    return build_sandbox(tmp_path / "repo")


@dataclass
class Seeded:
    sandbox: Sandbox
    run: Run

    def fork(self, destination: Path) -> Sandbox:
        return self.sandbox.copy(destination)


def _seed(factory: pytest.TempPathFactory, name: str, *args: str, **env: str) -> Seeded:
    sandbox = build_sandbox(factory.mktemp(name) / "repo")
    return Seeded(sandbox, sandbox.run(*args, **env))


@pytest.fixture(scope="module")
def completed(tmp_path_factory: pytest.TempPathFactory) -> Seeded:
    """The forward path and cleanup in one invocation, with every consent."""
    if BASH is None or GIT is None:
        pytest.skip("bash or git is not installed")
    return _seed(
        tmp_path_factory, "completed", "run", *ALL_CONSENT, "--confirm-cleanup"
    )


@pytest.fixture(scope="module")
def forward_done(tmp_path_factory: pytest.TempPathFactory) -> Seeded:
    """The forward path passed; nothing has been cleaned up."""
    if BASH is None or GIT is None:
        pytest.skip("bash or git is not installed")
    seeded = _seed(tmp_path_factory, "forward", "run", *ALL_CONSENT)
    assert seeded.run.returncode == 0, seeded.run.output
    return seeded


@pytest.fixture(scope="module")
def failed_at_helm(tmp_path_factory: pytest.TempPathFactory) -> Seeded:
    """A certification run that stopped when the Helm lifecycle failed."""
    if BASH is None or GIT is None:
        pytest.skip("bash or git is not installed")
    return _seed(
        tmp_path_factory,
        "failed",
        "run",
        *ALL_CONSENT,
        "--confirm-cleanup",
        STUB_FAIL="helm-lifecycle.sh",
    )


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> Seeded:
    """A preparation run given no consent at all."""
    if BASH is None or GIT is None:
        pytest.skip("bash or git is not installed")
    seeded = _seed(tmp_path_factory, "prepared", "run", "--prepare-only")
    assert seeded.run.returncode == 0, seeded.run.output
    return seeded


@pytest.fixture(scope="module")
def namespace_already_there(tmp_path_factory: pytest.TempPathFactory) -> Seeded:
    """A certification run against a cluster that already holds the release namespace."""
    if BASH is None or GIT is None:
        pytest.skip("bash or git is not installed")
    sandbox = build_sandbox(tmp_path_factory.mktemp("occupied") / "repo")
    sandbox.write_state(
        "namespaces", [*NAMESPACES_BEFORE, f"namespace/{RELEASE_NAMESPACE}"]
    )
    return Seeded(sandbox, sandbox.run("run", *ALL_CONSENT))


FORWARD_SIBLINGS_IN_ORDER = (
    ("target-detect.sh", ""),
    ("api-image.sh", "build"),
    ("api-image.sh", "load"),
    ("api-image.sh", "values"),
    ("model-seed-image.sh", "build"),
    ("model-seed-image.sh", "load"),
    ("model-seed-image.sh", "values"),
    ("terraform-prerequisites.sh", "check"),
    ("terraform-prerequisites.sh", "plan"),
    ("terraform-prerequisites.sh", "apply"),
    ("helm-lifecycle.sh", "--values"),
    ("kubernetes-certification.sh", "certify"),
    ("telemetry-collection-verify.sh", "verify"),
    ("performance-scenarios.sh", "run"),
    ("inference-pod-recovery.sh", "run"),
)


def assert_nothing_beyond_the_project(run: Run) -> None:
    """The properties no scenario may break, successful or not."""
    for line in run.calls:
        assert not line.startswith(("kind create", "kind delete")), line
        assert not re.match(r"kubectl .*\b(delete|apply|create|patch|label)\b", line), (
            line
        )
        assert not re.match(r"docker .*\b(rm|rmi|prune)\b", line), line
        assert "--create-namespace" not in line, line
    assert not any(
        line.startswith(("cluster-up", "cluster-down", "proof.sh"))
        for line in run.calls
    )


def write_target_before(
    root: Path, provider: str = "kind", cluster: str = CLUSTER
) -> None:
    directory = root / ".artifacts" / "clean-clone"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "target-before.txt").write_text(
        f"provider={provider}\ncluster={cluster}\nclusterUid=uid-first-cluster\n",
        encoding="utf-8",
        newline="\n",
    )
    (directory / "namespaces-before.txt").write_text(
        "".join(f"{ns}\n" for ns in sorted(NAMESPACES_BEFORE)),
        encoding="utf-8",
        newline="\n",
    )


# --------------------------------------------------------------------------
# The control case: the whole forward path, then cleanup
# --------------------------------------------------------------------------


@needs_bash
def test_a_complete_run_reaches_every_step_in_the_checklists_order(
    completed: Seeded,
) -> None:
    """The control case. Every negative result below is vacuous without it."""
    run = completed.run
    assert run.returncode == 0, run.output

    positions = [
        run.index(name, fragment) for name, fragment in FORWARD_SIBLINGS_IN_ORDER
    ]
    assert positions == sorted(positions), run.calls

    recorded = [a["stepId"] for a in run.ledger["attempts"]]
    assert recorded == [step.step_id for step in steps(load_descriptor())]
    assert set(run.outcomes().values()) == {"passed"}, run.outcomes()
    assert run.namespaces() == list(NAMESPACES_BEFORE)
    assert "status        complete" in run.output
    assert "certifies     no" in run.output, "a complete run on kind certifies nothing"
    assert_nothing_beyond_the_project(run)


@needs_bash
def test_the_default_lane_is_run_the_way_continuous_integration_runs_it(
    completed: Seeded,
) -> None:
    for fragment in (
        "sync --locked",
        "ruff format --check .",
        "ruff check .",
        "-m mypy",
        "-m pytest -q",
    ):
        assert completed.run.ran("uv", fragment), (fragment, completed.run.calls)


@needs_bash
def test_every_release_workflow_is_given_its_own_consent_and_the_composed_values(
    completed: Seeded,
) -> None:
    run = completed.run
    merged = ".artifacts/clean-clone/real-values.merged.yaml"
    assert run.ran("helm-lifecycle.sh", "--values", merged)
    for script in ("kubernetes-certification.sh", "telemetry-collection-verify.sh"):
        assert run.ran(script, "--values", merged, "--confirm-real-kubernetes"), script
    for script in ("performance-scenarios.sh", "inference-pod-recovery.sh"):
        assert run.ran(
            script,
            f"--values {BASE_VALUES_REL}",
            "--values .artifacts/clean-clone/api-image-values.yaml",
            "--values .artifacts/clean-clone/model-seed-values.yaml",
            "--confirm-real-kubernetes",
        ), script
    assert run.ran(
        "python", "tools.runtime_certification certify --confirm-real-runtime"
    )
    assert run.ran("docker", "pull", "@sha256:")


@needs_bash
def test_the_composed_values_layer_both_overlays_over_the_committed_file(
    completed: Seeded,
) -> None:
    """The file six workflows are given, which nothing composed for the operator before."""
    import yaml

    merged_path = (
        completed.sandbox.root
        / ".artifacts"
        / "clean-clone"
        / "real-values.merged.yaml"
    )
    merged = yaml.safe_load(merged_path.read_text(encoding="utf-8"))
    committed = yaml.safe_load(
        (REPO_ROOT / BASE_VALUES_REL).read_text(encoding="utf-8")
    )
    assert merged["api"]["image"]["digest"] == API_DIGEST
    assert merged["model"]["acquisition"]["seedImage"]["digest"] == SEED_DIGEST
    assert merged["model"]["acquisition"]["source"] == "seed-image"
    assert merged["profile"] == committed["profile"]
    assert merged["model"]["revision"] == committed["model"]["revision"]


@needs_bash
def test_every_attempt_is_timed_and_no_interval_is_negative(completed: Seeded) -> None:
    for attempt in completed.run.ledger["attempts"]:
        assert attempt["elapsedMs"] >= 0, attempt
        assert attempt["startedAt"] <= attempt["finishedAt"], attempt


@needs_bash
def test_a_cluster_answering_in_crlf_is_not_mistaken_for_a_changed_one(
    sandbox: Sandbox,
) -> None:
    """A Windows tool may end its lines with CRLF.

    The first draft compared the namespace snapshot with `comm` on the raw lines,
    and the survival check found two namespaces "gone" that were both still there.
    """
    run = sandbox.run("run", *ALL_CONSENT, "--confirm-cleanup", STUB_CRLF="1")
    assert run.returncode == 0, run.output
    assert run.outcomes()["cluster-survived"] == "passed"


# --------------------------------------------------------------------------
# Consent, and what a run refuses before it writes anything
# --------------------------------------------------------------------------


@needs_bash
@pytest.mark.parametrize("withheld", ALL_CONSENT)
def test_a_certification_run_without_every_consent_writes_nothing(
    sandbox: Sandbox, withheld: str
) -> None:
    given = [flag for flag in ALL_CONSENT if flag != withheld]
    run = sandbox.run("run", *given)
    assert run.returncode == 3, run.output
    assert not run.has_ledger
    assert not any(
        line.startswith(("uv", "docker", "kubectl", "helm", "kind"))
        for line in run.calls
    ), run.calls
    assert not any(line.split(" ")[0].endswith(".sh") for line in run.calls), run.calls


@needs_bash
def test_a_certification_run_without_a_provider_is_refused(sandbox: Sandbox) -> None:
    run = sandbox.run("run", *ALL_CONSENT, INFEROPS_PROVIDER="")
    assert run.returncode == 3, run.output
    assert not run.has_ledger


@needs_bash
def test_a_checkout_with_uncommitted_changes_is_refused_without_a_ledger(
    sandbox: Sandbox,
) -> None:
    (sandbox.root / "README.md").write_text("edited\n", encoding="utf-8")
    run = sandbox.run("run", *ALL_CONSENT)
    assert run.returncode == 3, run.output
    assert not run.has_ledger
    assert not run.ran("uv")


@needs_bash
@pytest.mark.parametrize("state", [".kube", ".cache/inferops", ".artifacts"])
def test_a_certification_run_refuses_state_a_previous_run_left(
    sandbox: Sandbox, state: str
) -> None:
    (sandbox.root / state).mkdir(parents=True)
    run = sandbox.run("run", *ALL_CONSENT)
    assert run.returncode == 3, run.output
    assert "previous-run state" in run.output
    assert not run.has_ledger
    assert not run.ran("uv")


@needs_bash
def test_a_preparation_run_records_every_real_step_as_not_run_and_touches_no_cluster(
    prepared: Seeded,
) -> None:
    run = prepared.run
    by_kind = {step.step_id: step.kind for step in steps(load_descriptor())}
    for step_id, outcome in run.outcomes().items():
        expected = "not-run" if by_kind[step_id] == "real" else "passed"
        assert outcome == expected, (step_id, outcome)
    assert not any(
        a["reason"] is None for a in run.ledger["attempts"] if a["outcome"] == "not-run"
    )
    assert not any(
        line.startswith(("kubectl", "helm", "kind")) for line in run.calls
    ), run.calls
    # The one engine question a preparation run may ask: where the engine keeps its
    # data, which `lib.sh`'s disk check reads to decide which volume to measure.
    docker = [line for line in run.calls if line.startswith("docker")]
    assert docker == ["docker info --format {{.DockerRootDir}}"], docker
    assert not any(line.split(" ")[0].endswith(".sh") for line in run.calls), run.calls
    assert "preparation-only" in run.output


@needs_bash
def test_a_preparation_run_runs_the_real_steps_it_was_given_consent_for(
    prepared: Seeded, tmp_path: Path
) -> None:
    run = prepared.fork(tmp_path / "repo").run(
        "run", "--prepare-only", "--confirm-downloads"
    )
    assert run.returncode == 0, run.output
    outcomes = run.outcomes()
    assert outcomes["model-acquisition"] == "passed"
    assert outcomes["runtime-image"] == "passed"
    assert outcomes["local-real-inference"] == "not-run"
    assert not run.ran("python", "runtime_certification")


@needs_bash
def test_a_preparation_ledger_is_never_resumed_as_a_certification_run(
    prepared: Seeded, tmp_path: Path
) -> None:
    run = prepared.fork(tmp_path / "repo").run("run", *ALL_CONSENT)
    assert run.returncode == 3, run.output
    assert not run.ran("kubectl")


# --------------------------------------------------------------------------
# Provider verification: the run starts from a cluster holding no InferOps
# --------------------------------------------------------------------------


@needs_bash
def test_a_cluster_already_holding_the_release_namespace_is_refused(
    namespace_already_there: Seeded,
) -> None:
    run = namespace_already_there.run
    assert run.returncode == 3, run.output
    assert run.outcomes()["provider-verification"] == "refused"
    root = namespace_already_there.sandbox.root
    assert not (root / ".artifacts" / "clean-clone" / "target-before.txt").exists()
    assert not run.ran("api-image.sh")
    assert not run.ran("terraform-prerequisites.sh")
    assert_nothing_beyond_the_project(run)


@needs_bash
def test_cleanup_after_that_refusal_touches_nothing_in_the_cluster(
    namespace_already_there: Seeded, tmp_path: Path
) -> None:
    """The namespace was there before the run, so it is not the run's to remove."""
    run = namespace_already_there.fork(tmp_path / "repo").run("cleanup", "--confirm")
    assert run.returncode == 0, run.output
    assert not run.ran("helm")
    assert not run.ran("terraform-prerequisites.sh")
    assert f"namespace/{RELEASE_NAMESPACE}" in run.namespaces()
    assert_nothing_beyond_the_project(run)


# --------------------------------------------------------------------------
# Failure, resumption, and the end of a run
# --------------------------------------------------------------------------


@needs_bash
def test_a_failed_step_stops_the_run_and_leaves_its_release_for_diagnosis(
    failed_at_helm: Seeded,
) -> None:
    run = failed_at_helm.run
    assert run.returncode == 1, run.output
    outcomes = run.outcomes()
    assert outcomes["helm-deployment"] == "failed"
    assert "kubernetes-inference" not in outcomes
    assert "cleanup" not in outcomes, "cleanup is a decision, not a reflex to a failure"
    assert not run.ran("kubernetes-certification.sh")
    assert not run.ran("terraform-prerequisites.sh", "destroy")


@needs_bash
def test_a_resumed_run_skips_what_passed_and_reverifies_the_cluster(
    failed_at_helm: Seeded, tmp_path: Path
) -> None:
    run = failed_at_helm.fork(tmp_path / "repo").run("run", *ALL_CONSENT)
    assert run.returncode == 0, run.output

    assert not run.ran("uv", "sync"), "a passed, resumable step ran again"
    assert not run.ran("api-image.sh")
    assert run.ran("target-detect.sh"), (
        "the target is verified again on every invocation"
    )
    assert run.ran("helm-lifecycle.sh")
    attempts = [a for a in run.ledger["attempts"] if a["stepId"] == "helm-deployment"]
    assert [a["outcome"] for a in attempts] == ["failed", "passed"]
    checkouts = [a for a in run.ledger["attempts"] if a["stepId"] == "clean-checkout"]
    assert len(checkouts) == 2, "the checkout is asked again on every invocation"


@needs_bash
def test_a_resumed_run_refuses_a_different_cluster(
    failed_at_helm: Seeded, tmp_path: Path
) -> None:
    run = failed_at_helm.fork(tmp_path / "repo").run(
        "run",
        *ALL_CONSENT,
        INFEROPS_KIND_CLUSTER_NAME="someone-else",
        STUB_KIND_CLUSTERS="someone-else",
        STUB_CONTEXT="kind-someone-else",
    )
    assert run.returncode == 3, run.output
    assert not run.ran("helm-lifecycle.sh")


@needs_bash
def test_a_resumed_run_refuses_a_checkout_that_has_changed(
    failed_at_helm: Seeded, tmp_path: Path
) -> None:
    forked = failed_at_helm.fork(tmp_path / "repo")
    (forked.root / "README.md").write_text("edited\n", encoding="utf-8")
    run = forked.run("run", *ALL_CONSENT)
    assert run.returncode != 0, run.output
    assert run.outcomes()["clean-checkout"] == "refused"
    assert not run.ran("helm-lifecycle.sh")


@needs_bash
def test_a_run_that_has_been_cleaned_up_cannot_be_resumed(
    completed: Seeded, tmp_path: Path
) -> None:
    run = completed.fork(tmp_path / "repo").run("run", *ALL_CONSENT)
    assert run.returncode == 3, run.output
    assert "already been cleaned up" in run.output
    assert not run.ran("uv")


# --------------------------------------------------------------------------
# Cleanup's boundary
# --------------------------------------------------------------------------


@needs_bash
def test_cleanup_without_confirmation_does_nothing(
    prepared: Seeded, tmp_path: Path
) -> None:
    run = prepared.fork(tmp_path / "repo").run("cleanup")
    assert run.returncode == 3, run.output
    assert run.calls == []


@needs_bash
def test_cleanup_without_a_ledger_does_nothing(sandbox: Sandbox) -> None:
    run = sandbox.run("cleanup", "--confirm")
    assert run.returncode == 3, run.output
    assert run.calls == []


@needs_bash
def test_cleanup_uninstalls_a_release_left_behind_before_destroying_the_prerequisites(
    forward_done: Seeded, tmp_path: Path
) -> None:
    forked = forward_done.fork(tmp_path / "repo")
    forked.write_state("releases", ["inferops"])
    run = forked.run("cleanup", "--confirm")
    assert run.returncode == 0, run.output
    uninstall = run.index(
        "helm", "uninstall inferops", f"--namespace {RELEASE_NAMESPACE}"
    )
    destroy = run.index("terraform-prerequisites.sh", "destroy --confirm")
    assert uninstall < destroy
    assert run.ran(
        "helm",
        "--kube-context",
        CONTEXT,
        "list --all",
        f"--namespace {RELEASE_NAMESPACE}",
    )
    assert run.namespaces() == list(NAMESPACES_BEFORE)
    assert run.outcomes()["cluster-survived"] == "passed"
    assert_nothing_beyond_the_project(run)


@needs_bash
def test_cleanup_refuses_when_the_release_listing_fails(
    forward_done: Seeded, tmp_path: Path
) -> None:
    """A listing that could not be made is never read as an empty one."""
    run = forward_done.fork(tmp_path / "repo").run(
        "cleanup", "--confirm", STUB_HELM_LIST="fail"
    )
    assert run.returncode != 0, run.output
    assert run.outcomes()["cleanup"] == "refused"
    assert not run.ran("helm", "uninstall")
    assert not run.ran("terraform-prerequisites.sh", "destroy")
    assert run.outcomes()["cluster-survived"] == "failed", (
        "the namespace is still there"
    )


@needs_bash
def test_cleanup_refuses_a_release_this_run_did_not_install(
    forward_done: Seeded, tmp_path: Path
) -> None:
    forked = forward_done.fork(tmp_path / "repo")
    forked.write_state("releases", ["someone-elses-thing"])
    run = forked.run("cleanup", "--confirm")
    assert run.returncode != 0, run.output
    assert run.outcomes()["cleanup"] == "refused"
    assert not run.ran("helm", "uninstall")
    assert not run.ran("terraform-prerequisites.sh", "destroy")


@needs_bash
def test_cleanup_refuses_a_cluster_other_than_the_one_this_run_verified(
    prepared: Seeded, tmp_path: Path
) -> None:
    forked = prepared.fork(tmp_path / "repo")
    write_target_before(forked.root, provider="kind", cluster="another-cluster")
    run = forked.run("cleanup", "--confirm")
    assert run.returncode != 0, run.output
    assert not run.ran("helm", "list")
    assert not run.ran("terraform-prerequisites.sh")


@needs_bash
def test_cluster_survival_fails_when_a_namespace_present_before_is_gone(
    forward_done: Seeded, tmp_path: Path
) -> None:
    """The check has to be able to fail, or its passes say nothing."""
    forked = forward_done.fork(tmp_path / "repo")
    remaining = [ns for ns in NAMESPACES_BEFORE if ns != "namespace/unrelated-work"]
    forked.write_state("namespaces", [*remaining, f"namespace/{RELEASE_NAMESPACE}"])
    run = forked.run("cleanup", "--confirm")
    assert run.returncode != 0, run.output
    assert run.outcomes()["cleanup"] == "passed"
    assert run.outcomes()["cluster-survived"] == "failed"
    assert "present before this run are gone" in run.output


@needs_bash
def test_cluster_survival_fails_when_a_node_is_not_ready(
    forward_done: Seeded, tmp_path: Path
) -> None:
    run = forward_done.fork(tmp_path / "repo").run(
        "cleanup", "--confirm", STUB_NODE_READY="False"
    )
    assert run.outcomes()["cleanup"] == "passed"
    assert run.outcomes()["cluster-survived"] == "failed"
    assert run.returncode != 0


@needs_bash
def test_cleanup_removes_the_runs_scaffolds_and_keeps_the_model_cache_by_default(
    prepared: Seeded, tmp_path: Path
) -> None:
    forked = prepared.fork(tmp_path / "repo")
    workloads = forked.root / ".artifacts" / "clean-clone" / "workloads" / "attempt-1"
    workloads.mkdir(parents=True)
    (workloads / "workload.yaml").write_text("x: 1\n", encoding="utf-8")
    run = forked.run("cleanup", "--confirm")
    assert run.returncode == 0, run.output
    assert not workloads.parent.exists()
    assert not run.ran("python", "model_acquisition clean")


@needs_bash
def test_the_model_cache_is_removed_by_the_locked_environments_python(
    prepared: Seeded, tmp_path: Path
) -> None:
    """The acquisition tool imports the platform package, which only `.venv` holds.

    The first draft ran it with whichever `python` came first on the operator's
    PATH, because nothing in a standalone cleanup had put the locked environment
    there. An independent review found it; the host's own python fails to import
    the tool.
    """
    forked = prepared.fork(tmp_path / "repo")
    venv_python = forked.root / ".venv" / "bin" / "python"
    venv_python.write_text(
        _PYTHON.replace("printf '%s %s\\n' python", "printf '%s %s\\n' venv-python"),
        encoding="utf-8",
        newline="\n",
    )
    venv_python.chmod(0o755)
    run = forked.run("cleanup", "--confirm", "--include-model-cache")
    assert run.returncode == 0, run.output
    assert run.ran("venv-python", "-m tools.model_acquisition clean --confirm"), (
        run.calls
    )
    assert not run.ran("python", "model_acquisition")


@needs_bash
def test_a_second_cleanup_after_one_that_passed_touches_nothing(
    prepared: Seeded, tmp_path: Path
) -> None:
    forked = prepared.fork(tmp_path / "repo")
    first = forked.run("cleanup", "--confirm")
    assert first.returncode == 0, first.output
    again = forked.run("cleanup", "--confirm", "--include-model-cache")
    assert again.returncode == 3, again.output
    assert "already cleaned up" in again.output
    assert again.calls == []
    assert [a["stepId"] for a in again.ledger["attempts"]].count("cleanup") == 1


@needs_bash
def test_cleanup_refuses_a_cluster_reset_under_the_same_name(
    forward_done: Seeded, tmp_path: Path
) -> None:
    """A provider and a cluster name survive a reset; the cluster does not.

    Docker Desktop's cluster is always called `docker-desktop`. The first draft
    compared only those two, so a reset cluster -- whose namespaces the snapshot
    no longer describes -- would have been cleaned up and judged against it.
    """
    run = forward_done.fork(tmp_path / "repo").run(
        "cleanup", "--confirm", STUB_CLUSTER_UID="uid-after-a-reset"
    )
    assert run.returncode != 0, run.output
    assert run.outcomes()["cleanup"] == "refused"
    assert not run.ran("helm")
    assert not run.ran("terraform-prerequisites.sh")


@needs_bash
def test_a_restart_moves_the_old_runs_cluster_snapshot_aside(
    prepared: Seeded, tmp_path: Path
) -> None:
    """Otherwise the restarted run reads as a resumption of the old one.

    Provider verification would skip the refusal of an existing release namespace
    and take no snapshot of its own, and survival would be judged against a
    cluster the new run never looked at. An independent review found it.
    """
    forked = prepared.fork(tmp_path / "repo")
    write_target_before(forked.root)
    run = forked.run("run", "--prepare-only", "--restart")
    assert run.returncode == 0, run.output
    directory = forked.root / ".artifacts" / "clean-clone"
    assert not (directory / "target-before.txt").exists()
    assert not (directory / "namespaces-before.txt").exists()
    assert len(list(directory.glob("target-before.txt.attempt-*"))) == 1
    assert len(list(directory.glob("namespaces-before.txt.attempt-*"))) == 1
    assert len(list(directory.glob("ledger.*.v1alpha1.json"))) == 1


def _python_reachable_without_the_stub() -> bool:
    assert BASH is not None and GIT is not None
    search = os.pathsep.join([str(Path(BASH).parent), str(Path(GIT).parent)])
    return shutil.which("python", path=search) is not None


@needs_bash
def test_a_host_with_no_python_is_told_so_before_anything_else(
    sandbox: Sandbox,
) -> None:
    if _python_reachable_without_the_stub():
        pytest.skip(
            "this host has a python beside bash or git; the case cannot be staged"
        )
    (sandbox.root / "bin" / "python").unlink()
    run = sandbox.run("run", *ALL_CONSENT)
    assert run.returncode == 1, run.output
    assert "no 'python' on PATH" in run.output
    assert not run.has_ledger
    assert run.calls == []


# --------------------------------------------------------------------------
# Arguments, and manual steps
# --------------------------------------------------------------------------


@needs_bash
@pytest.mark.parametrize(
    "args",
    [
        ("run", "--confirm"),
        ("cleanup", "--confirm-real-kubernetes"),
        ("plan", "--prepare-only"),
        ("note", "--bogus"),
        ("status", "extra"),
        ("destroy",),
    ],
)
def test_an_argument_the_action_does_not_take_is_refused(
    sandbox: Sandbox, args: tuple[str, ...]
) -> None:
    run = sandbox.run(*args)
    assert run.returncode != 0, run.output
    assert run.calls == []


@needs_bash
def test_a_manual_action_is_recorded_with_its_step(
    prepared: Seeded, tmp_path: Path
) -> None:
    forked = prepared.fork(tmp_path / "repo")
    run = forked.run(
        "note",
        "Placed a kubectl within one minor of the server first on PATH",
        "--step",
        "provider-verification",
    )
    assert run.returncode == 0, run.output
    actions = run.ledger["manualActions"]
    assert actions[-1]["stepId"] == "provider-verification"
    assert "kubectl" in actions[-1]["description"]


@needs_bash
@pytest.mark.parametrize("text", ["Copied the model from D:/models", "Edited /home/x"])
def test_a_manual_action_carrying_a_host_path_is_refused(
    prepared: Seeded, tmp_path: Path, text: str
) -> None:
    """The ledger's own rule, reached through the script. Every shape is in the ledger suite."""
    forked = prepared.fork(tmp_path / "repo")
    run = forked.run("note", text)
    assert run.returncode == 3, run.output
    assert run.ledger["manualActions"] == []


# --------------------------------------------------------------------------
# The script against its checklist, read
# --------------------------------------------------------------------------


SCRIPT_TEXT = (REPO_ROOT / SCRIPT_REL).read_text(encoding="utf-8")


def test_the_script_defines_one_step_function_per_checklist_step_in_order() -> None:
    defined = re.findall(
        r"^clean_clone::step_([a-z_]+)\(\) \{", SCRIPT_TEXT, re.MULTILINE
    )
    expected = [step.step_id.replace("-", "_") for step in steps(load_descriptor())]
    assert defined == expected


def test_every_consent_flag_the_checklist_names_is_the_one_the_script_parses() -> None:
    for entry in load_descriptor()["authorizations"]:
        flag, auth = entry["flag"], entry["authorizationId"]
        pattern = (
            rf"{re.escape(flag)}\)\s*(?:\n\s*confirm_cleanup=1)?\s*\n?\s*"
            rf'granted="\$\{{granted\}} {auth}"'
        )
        assert re.search(pattern, SCRIPT_TEXT), (flag, auth)


def test_every_workflow_a_step_names_is_one_its_function_runs() -> None:
    for entry in load_descriptor()["steps"]:
        name = entry["stepId"].replace("-", "_")
        body = re.search(
            rf"^clean_clone::step_{name}\(\) \{{\n(.*?)^\}}",
            SCRIPT_TEXT,
            re.MULTILINE | re.DOTALL,
        )
        assert body is not None, name
        for ref in entry["runs"]:
            if (
                ref.startswith("scripts/environment/")
                and ref.endswith(".sh")
                and "lib.sh" not in ref
            ):
                assert Path(ref).name in body.group(1), (entry["stepId"], ref)


def test_the_cleanup_never_names_a_cluster_lifecycle_or_an_unscoped_delete() -> None:
    body = re.search(
        r"^clean_clone::step_cleanup\(\) \{\n(.*?)^\}",
        SCRIPT_TEXT,
        re.MULTILINE | re.DOTALL,
    )
    assert body is not None
    code = "\n".join(
        line
        for line in body.group(1).splitlines()
        if not line.strip().startswith(("#", "inferops::log"))
    )
    for forbidden in (
        "kind delete",
        "kubectl delete",
        "delete namespace",
        "docker rm",
        "prune",
        "rm -rf",
    ):
        assert forbidden not in code, forbidden
    assert 'terraform-prerequisites.sh" destroy --confirm' in code
