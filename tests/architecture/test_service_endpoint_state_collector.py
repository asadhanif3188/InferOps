"""The collector of the endpoint-state record, read as text and executed against stubs.

``scripts/environment/service-endpoint-state.sh`` reads a cluster and writes one
directory. ``tools.service_endpoint_state`` builds the record from that
directory. This suite holds the script to four properties.

*It changes nothing in the cluster.* Each kubectl call the script holds is a
``get``. An executed run makes no kubectl call that is not a known read: the
target verification adds ``config`` reads and its own ``get`` and ``version``
calls. The verification also writes the target's kubeconfig under ``.kube/``.

*It sends nothing to the release.* The script holds no ``curl``, no ``wget``,
no ``port-forward``, and no ``exec``. So a record is not a request that a caller
sent, and the script cannot make it one.

*It agrees with the tool.* The file names, the schema, and the refusal exit
status are restated in the script, and each is compared with the tool's.

*A read that does not answer is not an empty result.* An executed run whose
read fails writes no file for that read, and the record is REFUSED. It states
no endpoint count.

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

from tools import service_endpoint_state as state

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = "scripts/environment/service-endpoint-state.sh"
LIB_REL = "scripts/environment/lib.sh"
SCRIPT_TEXT = (REPO_ROOT / SCRIPT_REL).read_text(encoding="utf-8")
LIB_TEXT = (REPO_ROOT / LIB_REL).read_text(encoding="utf-8")
COLLECTIONS = ".artifacts/service-endpoint-state/collections"

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
RELEASE = "inferops"
SELECTOR = "app.kubernetes.io/instance=inferops"
COMMIT = "1" * 40
API_SERVICE = "inferops-inferops-llm"
RUNTIME_SERVICE = "inferops-inferops-llm-runtime"

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
    """An allow-list: the script holds one kubectl verb, and it reads.

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
    assert calls == [
        [
            "collect",
            "services.json",
            "get",
            "services",
            "--namespace",
            '"${INFEROPS_RELEASE_NAMESPACE}"',
            "--selector",
            '"${INFEROPS_RELEASE_SELECTOR}"',
        ],
        [
            "collect",
            "endpointslices.json",
            "get",
            "endpointslices.discovery.k8s.io",
            "--namespace",
            '"${INFEROPS_RELEASE_NAMESPACE}"',
        ],
    ]


def test_the_script_sends_nothing_to_the_release() -> None:
    """No request, no forwarded port, and no process inside a pod.

    A Ready endpoint is what the cluster published. The script has no way to
    ask the release whether it serves, so its record cannot stand in for a
    caller's result.
    """
    for word in ("curl", "wget", "port-forward", "exec", "docker", "nc"):
        assert not [
            line for line in code_lines() if re.search(rf"(^|[\s(|;&]){word}\b", line)
        ], word
    assert "/metrics" not in SCRIPT_TEXT
    assert "prometheus" not in SCRIPT_TEXT.lower()


def test_the_script_removes_only_what_it_wrote_in_its_own_directory() -> None:
    # The first removes the one file of a read that did not answer.
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

    assert constant("COLLECTION_SCHEMA") == state.COLLECTION_SCHEMA
    assert int(constant("REFUSED_EXIT")) == state.REFUSED_EXIT
    assert constant("STATE_MODULE") == "tools.service_endpoint_state"
    assert constant("COLLECTIONS_REL") == COLLECTIONS
    for file in (state.SERVICES_FILE, state.SLICES_FILE):
        assert re.search(rf"^collect {re.escape(file)} ", SCRIPT_TEXT, re.M), file
    for file in (state.HEADER_FILE, state.RECORD_FILE):
        assert f'"${{collection_dir}}/{file}"' in SCRIPT_TEXT, file


def test_the_script_reads_the_release_that_the_library_names() -> None:
    """The release, the namespace, and the selector are the library's."""

    def constant(name: str) -> str:
        found = re.search(rf'^readonly {name}="([^"\n]*)"$', LIB_TEXT, re.M)
        assert found is not None, name
        return found.group(1)

    assert constant("INFEROPS_RELEASE_NAME") == RELEASE
    assert constant("INFEROPS_RELEASE_NAMESPACE") == NAMESPACE
    assert (
        constant("INFEROPS_RELEASE_SELECTOR")
        == "app.kubernetes.io/instance=${INFEROPS_RELEASE_NAME}"
    )
    assert "app.kubernetes.io/instance" in SELECTOR


def test_the_two_instants_bracket_the_two_reads() -> None:
    started = SCRIPT_TEXT.index("read_started_at=")
    first = SCRIPT_TEXT.index("\ncollect services.json")
    second = SCRIPT_TEXT.index("\ncollect endpointslices.json")
    finished = SCRIPT_TEXT.index("read_finished_at=")
    assert SCRIPT_TEXT.index("inferops::resolve_target\n") < started
    assert started < first < second < finished
    assert SCRIPT_TEXT.count("date -u +%Y-%m-%dT%H:%M:%SZ") == 2


def test_the_header_names_the_provider_and_no_context() -> None:
    assert "INFEROPS_TARGET_PROVIDER" in SCRIPT_TEXT
    assert "INFEROPS_TARGET_CONTEXT" not in SCRIPT_TEXT


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
  *"get services --namespace ${STUB_NAMESPACE} --selector ${STUB_SELECTOR} -o json")
    cat "${STUB_READS}/services.json" || exit 1 ;;
  *"get endpointslices.discovery.k8s.io --namespace ${STUB_NAMESPACE} -o json")
    cat "${STUB_READS}/endpointslices.json" || exit 1 ;;
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
  *) printf '\\n' ;;
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


def a_service(name: str, component: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": NAMESPACE,
            "labels": {
                "app.kubernetes.io/instance": RELEASE,
                "app.kubernetes.io/component": component,
            },
        },
        "spec": {"type": "ClusterIP"},
    }


def a_slice(service: str, pods: list[tuple[str, int, bool]]) -> dict:
    return {
        "apiVersion": "discovery.k8s.io/v1",
        "kind": "EndpointSlice",
        "metadata": {
            "name": f"{service}-abcde",
            "namespace": NAMESPACE,
            "labels": {
                "kubernetes.io/service-name": service,
                "endpointslice.kubernetes.io/managed-by": (
                    "endpointslice-controller.k8s.io"
                ),
            },
        },
        "addressType": "IPv4",
        "endpoints": [
            {
                "addresses": [f"10.1.0.{number}"],
                "conditions": {
                    "ready": ready,
                    "serving": ready,
                    "terminating": False,
                },
                "targetRef": {
                    "kind": "Pod",
                    "name": name,
                    "namespace": NAMESPACE,
                    "uid": f"00000000-0000-4000-8000-{number:012d}",
                },
            }
            for name, number, ready in pods
        ],
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
    def collected(self) -> list[list[str]]:
        """The reads that the script collects: each ``get`` that asks for JSON.

        The target verification also reads the cluster. It asks for no list as
        JSON.
        """
        return [
            call[:-2]
            for call in self.kubectl
            if call[0] == "get" and call[-2:] == ["-o", "json"]
        ]

    @property
    def files(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(path.name for path in self.directory.iterdir())

    @property
    def record(self) -> dict:
        return json.loads(
            (self.directory / state.RECORD_FILE).read_text(encoding="utf-8")
        )


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
    services = [
        a_service(API_SERVICE, "platform-api"),
        a_service(RUNTIME_SERVICE, "serving-runtime"),
    ]
    slices = [
        a_slice(API_SERVICE, [("api-a", 1, True), ("api-b", 2, True)]),
        a_slice(RUNTIME_SERVICE, [("runtime-a", 11, True), ("runtime-b", 12, False)]),
    ]
    (reads / "services.json").write_text(json.dumps(listed(services)), "utf-8")
    (reads / "endpointslices.json").write_text(json.dumps(listed(slices)), "utf-8")
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
    env["STUB_SELECTOR"] = SELECTOR
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
def test_an_observed_reading_writes_each_read_and_changes_nothing(
    sandbox: Path,
) -> None:
    run = run_script(sandbox, "--into", "reading-1")
    assert run.returncode == 0, run.output
    assert run.mutations == []
    assert run.files == [
        "endpointslices.json",
        "record.v1alpha1.json",
        "run.json",
        "services.json",
    ]
    assert run.collected == [
        ["get", "services", "--namespace", NAMESPACE, "--selector", SELECTOR],
        ["get", "endpointslices.discovery.k8s.io", "--namespace", NAMESPACE],
    ]
    record = run.record
    assert record["result"] == state.OBSERVED
    collection = record["collection"]
    assert collection == {
        "schema": state.COLLECTION_SCHEMA,
        "provider": "kind",
        "namespace": NAMESPACE,
        "release": RELEASE,
        "executingCommit": COMMIT,
        "readStartedAt": collection["readStartedAt"],
        "readFinishedAt": collection["readFinishedAt"],
    }
    instant = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"
    assert re.fullmatch(instant, collection["readStartedAt"], re.A)
    assert re.fullmatch(instant, collection["readFinishedAt"], re.A)
    assert collection["readStartedAt"] <= collection["readFinishedAt"]
    # Neither the header nor the record names the kubeconfig context.
    assert KUBE_CONTEXT not in (run.directory / "run.json").read_text("utf-8")
    assert KUBE_CONTEXT not in json.dumps(record["collection"])

    figures = {tier["tier"]: tier["endpoints"] for tier in record["tiers"]}
    assert figures["platform-api"]["ready"] == 2
    assert (
        figures["serving-runtime"]["ready"],
        figures["serving-runtime"]["total"],
    ) == (
        1,
        2,
    )
    # The record on disk is what the tool gives for the directory, in LF bytes.
    written = (run.directory / state.RECORD_FILE).read_bytes()
    assert written == state.record_text(state.build_record(run.directory)).encode()
    assert "platform-api     observed: 2 Ready of 2 endpoint(s)" in run.output
    assert "serving-runtime  observed: 1 Ready of 2 endpoint(s)" in run.output
    assert "result: OBSERVED" in run.output
    assert "It is not a request that a caller sent." in run.output


@needs_bash
def test_a_reading_with_no_ready_endpoint_is_observed_and_exits_0(
    sandbox: Path,
) -> None:
    """Status 0 says that the reading is usable. It does not say Ready."""
    slices = [
        a_slice(API_SERVICE, [("api-a", 1, True)]),
        a_slice(RUNTIME_SERVICE, [("runtime-a", 11, False)]),
    ]
    (sandbox / "reads" / "endpointslices.json").write_text(
        json.dumps(listed(slices)), "utf-8"
    )
    run = run_script(sandbox, "--into", "reading-1")
    assert run.returncode == 0, run.output
    assert run.record["result"] == state.OBSERVED
    assert "serving-runtime  observed: 0 Ready of 1 endpoint(s)" in run.output


@needs_bash
@pytest.mark.parametrize(
    "fail_on,absent",
    [
        ("get services", "services.json"),
        ("get endpointslices.discovery.k8s.io", "endpointslices.json"),
    ],
)
def test_a_read_that_does_not_answer_leaves_no_file_and_refuses(
    sandbox: Path, fail_on: str, absent: str
) -> None:
    run = run_script(sandbox, "--into", "reading-1", fail_on=fail_on)
    assert run.returncode == state.REFUSED_EXIT == 5, run.output
    assert run.mutations == []
    assert absent not in run.files
    assert "record.v1alpha1.json" in run.files
    record = run.record
    assert record["result"] == state.REFUSED
    assert record["refusedBy"][0] == "each-read-was-made"
    assert {tier["endpoints"] for tier in record["tiers"]} == {None}
    assert "did not answer" in run.output
    assert "no figure is stated" in run.output
    assert "result: REFUSED" in run.output
    assert "keep the directory" in run.output


@needs_bash
def test_a_release_with_no_runtime_service_is_refused(sandbox: Path) -> None:
    (sandbox / "reads" / "services.json").write_text(
        json.dumps(listed([a_service(API_SERVICE, "platform-api")])), "utf-8"
    )
    run = run_script(sandbox, "--into", "reading-1")
    assert run.returncode == 5, run.output
    assert run.record["refusedBy"][0] == "one-service-carries-each-tier"
    assert "not-held      one-service-carries-each-tier" in run.output


@needs_bash
def test_an_earlier_collection_is_not_written_into(sandbox: Path) -> None:
    first = run_script(sandbox, "--into", "reading-1")
    assert first.returncode == 0, first.output
    before = {path.name: path.read_bytes() for path in first.directory.iterdir()}
    second = run_script(sandbox, "--into", "reading-1")
    assert second.returncode == 1
    assert "already exists" in second.output
    assert second.kubectl == []
    assert {
        path.name: path.read_bytes() for path in first.directory.iterdir()
    } == before


@needs_bash
@pytest.mark.parametrize(
    "args,message",
    [
        (("--into",), "--into needs a value"),
        (("--into", "a", "--into", "b"), "--into was given twice"),
        (("--into", "../x"), "is not usable"),
        (("--into", ".hidden"), "is not usable"),
        (("--samples", "3"), "unknown argument"),
    ],
)
def test_arguments_that_are_not_usable_are_refused_before_any_call(
    sandbox: Path, args: tuple[str, ...], message: str
) -> None:
    run = run_script(sandbox, *args)
    assert run.returncode == 1
    assert message in run.output
    assert run.kubectl == []
    assert not (sandbox / COLLECTIONS).exists()


@needs_bash
def test_no_provider_is_refused_before_any_read_is_collected(sandbox: Path) -> None:
    run = run_script(sandbox, "--into", "reading-1", provider=None)
    assert run.returncode != 0
    assert run.collected == []
    assert run.files == []


@needs_bash
def test_a_tree_with_no_commit_writes_no_collection(sandbox: Path) -> None:
    run = run_script(sandbox, "--into", "reading-1", commit="")
    assert run.returncode == 1
    assert "could not read the commit" in run.output
    assert run.collected == []
    assert run.files == []
