"""The collector of the V2 capacity gate, read as text and executed against stubs.

``scripts/environment/capacity-preflight.sh`` reads a cluster and writes one
directory. ``tools.capacity_preflight`` decides from that directory. This suite
holds the script to three properties.

*It changes nothing.* Each kubectl call the script holds is a ``get`` or a
``version``, and an executed run makes no other call.

*It agrees with the tool.* The file names, the schema, and the refusal exit
status are restated in the script, and each is compared with the tool's.

*A read that does not answer is not an empty result.* An executed run whose
read fails writes no file for that read, and the record is REFUSED.

The executed tests need ``bash`` and skip without it. The stubs stand in for
kubectl, kind, docker, and git. No test contacts a cluster.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools import capacity_preflight as gate
from tools.capacity_preflight import core

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = "scripts/environment/capacity-preflight.sh"
LIB_REL = "scripts/environment/lib.sh"
SCRIPT_TEXT = (REPO_ROOT / SCRIPT_REL).read_text(encoding="utf-8")
COLLECTIONS = ".artifacts/capacity-preflight/collections"

BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(
    BASH is None,
    reason="bash is not installed; the executed collector tests skip, loudly",
)

# Restated on purpose. A fixture that imported these from the script would agree
# with the script by construction.
KUBE_CONTEXT = "kind-inferops-dev"
CONTROL_PLANE = "inferops-dev-control-plane"
NAMESPACE = "inferops-release"
COMMIT = "1" * 40

# The kubectl calls that change nothing, as the first words after the pinned
# flags. Every other call counts as a mutation.
READ_CALLS = (
    ("get",),
    ("version",),
    ("config", "get-contexts"),
    ("config", "view"),
    ("config", "current-context"),
)


def code_lines() -> list[str]:
    """The script's lines that are not comments."""
    return [
        line
        for line in SCRIPT_TEXT.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


# --------------------------------------------------------------------------
# The script, as text
# --------------------------------------------------------------------------


def test_each_kubectl_call_of_the_script_is_a_read() -> None:
    """An allow-list: the script holds two kubectl verbs, and both read.

    Each cluster call goes through the one ``collect`` function, which appends
    ``-o json``. So the calls are the arguments of ``collect``.
    """
    direct = [line for line in code_lines() if "target_kubectl" in line]
    assert direct == [
        '  if inferops::target_kubectl "$@" -o json >"${collection_dir}/${file}" '
        "2>/dev/null; then"
    ]
    assert not [
        line for line in code_lines() if re.search(r"(^|[\s(|;&])kubectl\s", line)
    ]
    assert not [line for line in code_lines() if re.search(r"\bhelm\b", line)]

    calls = [line.split() for line in code_lines() if line.startswith("collect ")]
    assert [(call[1], call[2]) for call in calls] == [
        ("nodes.json", "get"),
        ("pods.json", "get"),
        ("namespace-limits.json", "get"),
        ("claims.json", "get"),
        ("version.json", "version"),
    ]


def test_each_docker_call_of_the_script_reads_the_engine() -> None:
    docker = [line.strip() for line in code_lines() if re.search(r"\bdocker\b", line)]
    assert len(docker) == 2
    for line in docker:
        assert re.search(r"\$\(docker info --format '\{\{\.\w+\}\}' 2>/dev/null", line)


def test_the_script_removes_only_what_it_wrote_in_its_own_directory() -> None:
    removals = [line.strip() for line in code_lines() if re.search(r"\brm\b", line)]
    assert removals == [
        'rm -f "${collection_dir}/${file}"',
        'rm -f "${collection_dir}/record.v1alpha1.json"',
    ]


def test_the_script_restates_the_tools_names_and_each_agrees() -> None:
    def constant(name: str) -> str:
        found = re.search(rf'^readonly {name}="?([^"\n]*)"?$', SCRIPT_TEXT, re.M)
        assert found is not None, name
        return found.group(1)

    assert constant("COLLECTION_SCHEMA") == gate.COLLECTION_SCHEMA
    assert int(constant("REFUSED_EXIT")) == gate.REFUSED_EXIT
    assert constant("PREFLIGHT_MODULE") == "tools.capacity_preflight"
    for file in (*core._READS.values(), core._VERSION_FILE):
        assert re.search(rf"^collect {re.escape(file)} ", SCRIPT_TEXT, re.M), file
    for file in (
        core._FOOTPRINT_FILE,
        core._ENGINE_FILE,
        core._HEADER_FILE,
        gate.RECORD_FILE,
    ):
        assert f'"${{collection_dir}}/{file}"' in SCRIPT_TEXT, file


def test_the_footprint_is_written_before_the_first_read_of_the_cluster() -> None:
    footprint = SCRIPT_TEXT.index("--footprint)")
    first_read = SCRIPT_TEXT.index("\ncollect nodes.json")
    assert SCRIPT_TEXT.index("inferops::resolve_target\n") < footprint < first_read


# --------------------------------------------------------------------------
# The script, executed against stubs
# --------------------------------------------------------------------------

_KUBECTL_STUB = """#!/usr/bin/env bash
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
  *"get nodes -o json") cat "${STUB_READS}/nodes.json" || exit 1 ;;
  *"get pods --all-namespaces -o json") cat "${STUB_READS}/pods.json" || exit 1 ;;
  *"get resourcequotas,limitranges --namespace ${STUB_NAMESPACE} -o json")
    cat "${STUB_READS}/namespace-limits.json" || exit 1 ;;
  *"get persistentvolumeclaims --namespace ${STUB_NAMESPACE} -o json")
    cat "${STUB_READS}/claims.json" || exit 1 ;;
  *"version -o json"*) printf '%s' "${STUB_VERSION_JSON}" ;;
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
  info)
    case "$*" in
      *NCPU*) printf '%s\\n' "${STUB_ENGINE_CPUS:-}" ;;
      *MemTotal*) printf '%s\\n' "${STUB_ENGINE_MEMORY:-}" ;;
      *) printf '\\n' ;;
    esac
    ;;
esac
exit 0
"""

_GIT_STUB = """#!/usr/bin/env bash
printf 'git %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
[ -z "${STUB_COMMIT}" ] && exit 128
printf '%s\\n' "${STUB_COMMIT}"
"""

# The interpreter that runs this suite, with the repository on its path. The
# sandbox holds no copy of the tool.
_PYTHON_STUB = """#!/usr/bin/env bash
if [ "$1" = "-m" ]; then
  printf 'python %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
else
  printf 'python %s\\n' "$1" >>"${INFEROPS_STUB_LOG}"
fi
PYTHONPATH="${STUB_REPOSITORY}" exec "${STUB_PYTHON}" "$@"
"""

_STUBS = {
    "kubectl": _KUBECTL_STUB,
    "kind": _KIND_STUB,
    "docker": _DOCKER_STUB,
    "git": _GIT_STUB,
    "python": _PYTHON_STUB,
}


def listed(items: list[dict]) -> dict:
    return {"apiVersion": "v1", "kind": "List", "items": items}


def one_node(memory: str = "16Gi") -> dict:
    figures = {"cpu": "12", "memory": memory, "pods": "110"}
    return {
        "kind": "Node",
        "metadata": {"name": CONTROL_PLANE},
        "spec": {},
        "status": {
            "capacity": figures,
            "allocatable": figures,
            "conditions": [{"type": "Ready", "status": "True"}],
            "nodeInfo": {"kubeletVersion": "v1.34.3"},
        },
    }


def one_pod() -> dict:
    return {
        "kind": "Pod",
        "metadata": {"name": "dns", "namespace": "kube-system"},
        "spec": {
            "nodeName": CONTROL_PLANE,
            "containers": [
                {
                    "name": "c",
                    "resources": {"requests": {"cpu": "100m", "memory": "70Mi"}},
                }
            ],
        },
        "status": {"phase": "Running"},
    }


class Run:
    """One execution of the script, and what it actually ran."""

    def __init__(
        self, completed: subprocess.CompletedProcess[str], log: Path, directory: Path
    ) -> None:
        self.returncode = completed.returncode
        self.output = completed.stdout + completed.stderr
        self.directory = directory
        self.calls = [
            line for line in log.read_text(encoding="utf-8").splitlines() if line
        ]

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
    def files(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(path.name for path in self.directory.iterdir())

    @property
    def record(self) -> dict:
        return json.loads(
            (self.directory / gate.RECORD_FILE).read_text(encoding="utf-8")
        )

    @staticmethod
    def collected(calls: list[str]) -> list[list[str]]:
        """The reads that the script collects, without the flags the wrapper pins.

        The target verification also reads the nodes and the version. It asks
        for none of the four lists as JSON, and its calls precede the footprint.
        """
        found = []
        for line in calls:
            words = line.split()
            if words[0] != "kubectl" or words[-2:] != ["-o", "json"]:
                continue
            rest = words[1:-2]
            while rest and rest[0] in ("--kubeconfig", "--context"):
                rest = rest[2:]
            if rest[0] == "get" or rest == ["version"]:
                found.append(rest)
        return found

    def index_of(self, *fragments: str) -> int:
        for index, line in enumerate(self.calls):
            if all(fragment in line for fragment in fragments):
                return index
        raise AssertionError(f"no call holds {fragments}: {self.calls}")


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A directory laid out like the repository, holding the committed scripts.

    The script derives its root from its own location, so a copy two directories
    below the sandbox root treats the sandbox as the repository.
    """
    for rel in (LIB_REL, SCRIPT_REL):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, target)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in _STUBS.items():
        stub = bin_dir / name
        stub.write_text(body, encoding="utf-8", newline="\n")
        stub.chmod(0o755)
    reads = tmp_path / "reads"
    reads.mkdir()
    for name, document in (
        ("nodes.json", listed([one_node()])),
        ("pods.json", listed([one_pod()])),
        ("namespace-limits.json", listed([])),
        ("claims.json", listed([])),
    ):
        (reads / name).write_text(json.dumps(document), encoding="utf-8")
    return tmp_path


def run_script(
    sandbox: Path,
    *args: str,
    name: str = "reading-1",
    provider: str | None = "kind",
    commit: str = COMMIT,
    **stub: str,
) -> Run:
    """Execute the committed script inside the sandbox and report what it ran."""
    log = sandbox / "calls.log"
    log.write_text("", encoding="utf-8")

    assert BASH is not None
    # The stub directory and the shell's own toolbox, and nothing else. A real
    # kubectl behind the stubs would make a test contact a cluster.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("INFEROPS_", "STUB_", "KUBE", "PYTHON"))
    }
    env["PATH"] = os.pathsep.join([str(sandbox / "bin"), str(Path(BASH).parent)])
    env["INFEROPS_STUB_LOG"] = str(log)
    env["STUB_CONTEXT"] = KUBE_CONTEXT
    env["STUB_NODE"] = CONTROL_PLANE
    env["STUB_KIND_NODE"] = CONTROL_PLANE
    env["STUB_NAMESPACE"] = NAMESPACE
    env["STUB_VERSION_JSON"] = json.dumps(
        {
            "clientVersion": {"major": "1", "minor": "34", "gitVersion": "v1.34.1"},
            "serverVersion": {"major": "1", "minor": "34", "gitVersion": "v1.34.3"},
        }
    )
    env["STUB_READS"] = (sandbox / "reads").as_posix()
    env["STUB_COMMIT"] = commit
    env["STUB_PYTHON"] = sys.executable
    env["STUB_REPOSITORY"] = str(REPO_ROOT)
    env["STUB_ENGINE_CPUS"] = "12"
    env["STUB_ENGINE_MEMORY"] = str(16 * 2**30)
    if provider is not None:
        env["INFEROPS_PROVIDER"] = provider
        env["INFEROPS_KIND_CLUSTER_NAME"] = "inferops-dev"
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
    return Run(completed, log, sandbox / COLLECTIONS / name)


@needs_bash
def test_an_accepted_reading_writes_each_read_and_changes_nothing(
    sandbox: Path,
) -> None:
    run = run_script(sandbox, "--into", "reading-1")
    assert run.returncode == 0, run.output
    assert run.mutations == []
    assert run.files == [
        "claims.json",
        "engine.json",
        "footprint.json",
        "namespace-limits.json",
        "nodes.json",
        "pods.json",
        "record.v1alpha1.json",
        "run.json",
        "version.json",
    ]
    record = run.record
    assert record["result"] == gate.ACCEPTED
    assert record["collection"] == {
        "provider": "kind",
        "context": KUBE_CONTEXT,
        "releaseKey": "local-docker-desktop/support-assistant",
        "namespace": NAMESPACE,
        "executingCommit": COMMIT,
        "collectedAt": record["collection"]["collectedAt"],
    }
    assert re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["collection"]["collectedAt"], re.A
    )
    assert record["environment"] == {
        "provider": "kind",
        "kubernetesServerVersion": "v1.34.3",
        "containerEngine": {"cpus": 12, "memoryBytes": 16 * 2**30},
    }
    assert record["footprint"] == gate.declared_footprint()
    # The record on disk is what the tool gives for the directory, in LF bytes.
    written = (run.directory / gate.RECORD_FILE).read_bytes()
    assert written == gate.record_text(gate.build_record(run.directory)).encode()
    assert "result: ACCEPTED" in run.output
    assert "does not establish that a pod starts" in run.output

    # The footprint is asked for before the first read that the script collects.
    # Each kubectl call before it is the target verification's, which asks for
    # none of the four lists.
    footprint = run.index_of("python", "--footprint")
    assert [
        call for call in run.collected(run.calls[:footprint]) if call[0] == "get"
    ] == []
    assert run.collected(run.calls[footprint:]) == [
        ["get", "nodes"],
        ["get", "pods", "--all-namespaces"],
        ["get", "resourcequotas,limitranges", "--namespace", NAMESPACE],
        ["get", "persistentvolumeclaims", "--namespace", NAMESPACE],
        ["version"],
    ]


@needs_bash
def test_a_refused_reading_exits_5_and_keeps_the_directory(sandbox: Path) -> None:
    (sandbox / "reads" / "nodes.json").write_text(
        json.dumps(listed([one_node(memory="8Gi")])), encoding="utf-8"
    )
    run = run_script(sandbox, "--into", "reading-1")
    assert run.returncode == gate.REFUSED_EXIT == 5, run.output
    assert run.mutations == []
    assert run.record["result"] == gate.REFUSED
    assert run.record["refusal"] == {
        "categories": [gate.INSUFFICIENT],
        "rules": ["memory-limits-fit"],
    }
    assert "result: REFUSED" in run.output
    assert "no figure was lowered" in run.output
    assert "nodes.json" in run.files


@needs_bash
@pytest.mark.parametrize(
    ("fail_on", "file"),
    [
        ("get nodes -o json", "nodes.json"),
        ("get pods --all-namespaces", "pods.json"),
        ("get resourcequotas,limitranges", "namespace-limits.json"),
        ("get persistentvolumeclaims", "claims.json"),
    ],
)
def test_a_read_that_does_not_answer_writes_no_file_and_refuses(
    sandbox: Path, fail_on: str, file: str
) -> None:
    """An unanswered query is not an empty list, and the reading is REFUSED."""
    run = run_script(sandbox, "--into", "reading-1", fail_on=fail_on)
    assert run.returncode == gate.REFUSED_EXIT, run.output
    assert file not in run.files
    record = run.record
    assert record["result"] == gate.REFUSED
    assert record["refusal"]["categories"] == [gate.AMBIGUOUS]
    [complete] = [
        f for f in record["findings"] if f["ruleId"] == "cluster-reads-complete"
    ]
    assert complete["state"] == gate.NOT_OBSERVED
    assert file in complete["detail"]
    assert "did not answer" in run.output
    assert run.mutations == []


@needs_bash
def test_an_engine_that_does_not_answer_leaves_no_engine_figure(sandbox: Path) -> None:
    run = run_script(sandbox, "--into", "reading-1", engine_cpus="", engine_memory="")
    assert run.returncode == 0, run.output
    assert "engine.json" not in run.files
    assert run.record["environment"]["containerEngine"] is None
    assert "states no engine figure" in run.output


@needs_bash
def test_an_earlier_reading_is_not_written_into(sandbox: Path) -> None:
    first = run_script(sandbox, "--into", "reading-1")
    assert first.returncode == 0, first.output
    before = {name: (first.directory / name).read_bytes() for name in first.files}
    second = run_script(sandbox, "--into", "reading-1")
    assert second.returncode == 1
    assert "already exists" in second.output
    assert second.kubectl == []
    assert {
        name: (second.directory / name).read_bytes() for name in second.files
    } == before


@needs_bash
@pytest.mark.parametrize("name", ["../outside", ".hidden", "a/b", "a b", ""])
def test_a_name_that_leaves_the_collections_directory_is_refused(
    sandbox: Path, name: str
) -> None:
    run = run_script(sandbox, "--into", name)
    assert run.returncode == 1
    assert run.kubectl == []
    assert not (sandbox / ".artifacts").exists()


@needs_bash
def test_no_provider_means_no_read_and_no_directory(sandbox: Path) -> None:
    run = run_script(sandbox, "--into", "reading-1", provider=None)
    assert run.returncode == 1
    assert "refusing to select a target" in run.output
    assert not run.collected(run.calls) or run.collected(run.calls) == [["version"]]
    assert not (sandbox / ".artifacts").exists()


@needs_bash
def test_a_working_tree_without_a_commit_means_no_read(sandbox: Path) -> None:
    run = run_script(sandbox, "--into", "reading-1", commit="")
    assert run.returncode == 1
    assert "could not read the commit" in run.output
    assert not run.collected(run.calls) or run.collected(run.calls) == [["version"]]
    assert not (sandbox / ".artifacts").exists()


@needs_bash
def test_without_a_name_the_directory_is_named_by_the_time(sandbox: Path) -> None:
    run = run_script(sandbox)
    assert run.returncode == 0, run.output
    [directory] = list((sandbox / COLLECTIONS).iterdir())
    assert re.fullmatch(r"\d{8}T\d{6}Z", directory.name, re.A)
    assert (directory / gate.RECORD_FILE).is_file()
