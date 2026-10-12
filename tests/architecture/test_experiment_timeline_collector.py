"""The collector of the timeline streams, read as text and executed against stubs.

``scripts/environment/experiment-timeline.sh`` samples a cluster a bounded number
of times and writes one directory. ``tools.experiment_timeline`` builds four
streams from that directory. This suite holds the script to five properties.

*It changes nothing in the cluster.* Each kubectl call the script holds is a
``get`` with a request timeout. An executed run makes no kubectl call that is not a known read: the
target verification adds ``config`` reads and its own ``get`` and ``version``
calls. The verification also writes the target's kubeconfig under ``.kube/``.

*It sends nothing to the release.* The script holds no ``curl``, no ``wget``,
no ``port-forward``, and no ``exec``. So a stream is not a request that a caller
sent, and the script cannot make it one.

*It is bounded.* The number of samples and the pause are arguments with a
maximum, each read has a timeout, and arguments that are not usable are refused
before any call.

*It agrees with the tool.* The file names, the schema, the stream names, and
the bounds are restated in the script, and each is compared with the tool's.

*A read that does not answer is not an empty result.* An executed run whose
read fails writes no file for that read, and the streams state no value for it.
The other read of the same sample is not changed.

The executed tests need ``bash`` and skip without it. The stubs stand in for
kubectl, kind, docker, and git. A fifth stub records each call of ``python`` and
passes it to the interpreter of this suite. The kubectl stub answers a call it
does not know with nothing and exit status 0, so a test reads the recorded calls
and does not rely on a failure. No test contacts a cluster, so no test here is
evidence of a timeline of a real run.
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

from tools import experiment_timeline as timeline

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = "scripts/environment/experiment-timeline.sh"
LIB_REL = "scripts/environment/lib.sh"
APPLICATION_PROCEDURE_REL = "scripts/environment/argocd-application.sh"
SCRIPT_TEXT = (REPO_ROOT / SCRIPT_REL).read_text(encoding="utf-8")
LIB_TEXT = (REPO_ROOT / LIB_REL).read_text(encoding="utf-8")
PROCEDURE_TEXT = (REPO_ROOT / APPLICATION_PROCEDURE_REL).read_text(encoding="utf-8")
COLLECTIONS = ".artifacts/experiment-timeline/collections"

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
APPLICATION = "local-docker-desktop-support-assistant"
APPLICATION_NAMESPACE = "argocd"
COMMIT = "1" * 40
API_SERVICE = "inferops-inferops-llm"
RUNTIME_SERVICE = "inferops-inferops-llm-runtime"
WORKLOAD_READ = [
    "get",
    "services,endpointslices.discovery.k8s.io,pods,replicasets.apps,deployments.apps",
    "--namespace",
    NAMESPACE,
    "--request-timeout",
    "10s",
]
APPLICATION_READ = [
    "get",
    "applications.argoproj.io",
    APPLICATION,
    "--namespace",
    APPLICATION_NAMESPACE,
    "--ignore-not-found",
    "--request-timeout",
    "10s",
]
INSTANT = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z"

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


def constant(name: str, text: str = SCRIPT_TEXT) -> str:
    found = re.search(rf'^readonly {name}="?([^"\n]*)"?$', text, re.M)
    assert found is not None, name
    return found.group(1)


# --------------------------------------------------------------------------
# The script, as text
# --------------------------------------------------------------------------


def test_each_kubectl_call_of_the_script_is_a_read() -> None:
    """An allow-list: the script holds one kubectl verb, and it reads.

    Each cluster call goes through the one ``collect`` function, which appends
    the read timeout and ``-o json``. So the calls are the arguments of
    ``collect``.
    """
    direct = [line for line in code_lines() if "target_kubectl" in line]
    assert direct == [
        '  if inferops::target_kubectl "$@" --request-timeout '
        '"${REQUEST_TIMEOUT_SECONDS}s" -o json >"${file}" 2>/dev/null; then'
    ]
    assert not [
        line for line in code_lines() if re.search(r"(^|[\s(|;&])kubectl\s", line)
    ]
    assert not [line for line in code_lines() if re.search(r"\bhelm\b", line)]

    calls = [
        line.split() for line in code_lines() if line.lstrip().startswith("collect ")
    ]
    assert calls == [
        [
            "collect",
            '"${stem}.workload.json"',
            "get",
            '"${WORKLOAD_KINDS}"',
            "--namespace",
            '"${INFEROPS_RELEASE_NAMESPACE}"',
            "||",
        ],
        [
            "collect",
            '"${stem}.application.json"',
            "get",
            '"${APPLICATION_KIND}"',
            '"${APPLICATION_NAME}"',
            "--namespace",
            '"${APPLICATION_NAMESPACE}"',
            "--ignore-not-found",
            "||",
        ],
    ]


def test_the_script_sends_nothing_to_the_release() -> None:
    """No request, no forwarded port, and no process inside a pod.

    The script has no way to ask the release whether it serves, so a stream
    cannot stand in for a caller's result.
    """
    for word in ("curl", "wget", "port-forward", "exec", "docker", "nc", "logs"):
        assert not [
            line for line in code_lines() if re.search(rf"(^|[\s(|;&]){word}\b", line)
        ], word
    assert "/metrics" not in SCRIPT_TEXT
    assert "prometheus" not in SCRIPT_TEXT.lower()


def test_the_script_removes_only_what_it_wrote_in_its_own_directory() -> None:
    # The first removes the one file of a read that did not answer.
    removals = [line.strip() for line in code_lines() if re.search(r"\brm\b", line)]
    assert removals == [
        'rm -f "${file}"',
        'rm -f "${collection_dir}/streams/${name}.jsonl"',
    ]


def test_the_script_restates_the_tools_names_and_bounds_and_each_agrees() -> None:
    assert constant("COLLECTION_SCHEMA") == timeline.COLLECTION_SCHEMA
    assert constant("TIMELINE_MODULE") == "tools.experiment_timeline"
    assert constant("COLLECTIONS_REL") == COLLECTIONS
    assert tuple(constant("STREAM_NAMES").split()) == timeline.STREAMS
    assert int(constant("MAX_SAMPLES")) == timeline.MAX_SAMPLES
    assert int(constant("MAX_INTERVAL_SECONDS")) == timeline.MAX_INTERVAL_SECONDS
    assert (
        1
        <= int(constant("REQUEST_TIMEOUT_SECONDS"))
        <= timeline.MAX_REQUEST_TIMEOUT_SECONDS
    )
    assert f'"${{collection_dir}}/{timeline.HEADER_FILE}"' in SCRIPT_TEXT
    assert f'"${{collection_dir}}/{timeline.END_FILE}"' in SCRIPT_TEXT
    assert timeline.SAMPLE_STEM.format(index=7) == "sample-0007"
    assert "printf 'sample-%04d'" in SCRIPT_TEXT
    for suffix in (
        timeline.WORKLOAD_SUFFIX,
        timeline.APPLICATION_SUFFIX,
        timeline.META_SUFFIX,
    ):
        assert f'"${{stem}}{suffix}"' in SCRIPT_TEXT, suffix
    for name in timeline.STREAMS:
        assert timeline.STREAM_FILES[name] == f"{name}.jsonl"
    assert '"${collection_dir}/streams/${name}.jsonl"' in SCRIPT_TEXT


def test_the_workload_read_asks_for_the_kinds_that_the_tool_reads() -> None:
    resources = {
        "services": "Service",
        "endpointslices.discovery.k8s.io": "EndpointSlice",
        "pods": "Pod",
        "replicasets.apps": "ReplicaSet",
        "deployments.apps": "Deployment",
    }
    asked = constant("WORKLOAD_KINDS").split(",")
    assert tuple(resources[resource] for resource in asked) == timeline.WORKLOAD_KINDS


def test_the_script_reads_the_application_that_the_procedure_delivers() -> None:
    """The three values are the Application procedure's, restated."""
    assert constant("APPLICATION_NAME") == APPLICATION
    assert constant("APPLICATION_NAME") == constant(
        "INFEROPS_GITOPS_APPLICATION_NAME", PROCEDURE_TEXT
    )
    assert constant("APPLICATION_NAMESPACE") == constant(
        "INFEROPS_ARGOCD_NAMESPACE", PROCEDURE_TEXT
    )
    assert (
        constant("APPLICATION_KIND")
        in constant("INFEROPS_ARGOCD_KINDS", PROCEDURE_TEXT).split()
    )


def test_the_script_names_the_controller_only_to_read_one_application() -> None:
    """Two lines name the controller: the kind and the namespace of the read.

    The script holds no address of the controller, no command of its client,
    and no other kind of its API group.
    """
    reference = re.compile(r"argoproj|argo[-_. ]?cd", flags=re.IGNORECASE)
    assert [line for line in SCRIPT_TEXT.splitlines() if reference.search(line)] == [
        'readonly APPLICATION_KIND="applications.argoproj.io"',
        'readonly APPLICATION_NAMESPACE="argocd"',
    ]
    assert not re.search(r"(^|[\s(|;&])argocd\s", SCRIPT_TEXT, re.M)


def test_the_script_reads_the_release_that_the_library_names() -> None:
    assert constant("INFEROPS_RELEASE_NAME", LIB_TEXT) == RELEASE
    assert constant("INFEROPS_RELEASE_NAMESPACE", LIB_TEXT) == NAMESPACE
    assert "INFEROPS_RELEASE_SELECTOR" not in SCRIPT_TEXT


def test_two_instants_bracket_each_read_and_each_states_milliseconds() -> None:
    order = [
        'workload_started_at="$(instant)"',
        'collect "${stem}.workload.json"',
        'workload_finished_at="$(instant)"',
        'application_started_at="$(instant)"',
        'collect "${stem}.application.json"',
        'application_finished_at="$(instant)"',
    ]
    positions = [SCRIPT_TEXT.index(text) for text in order]
    assert positions == sorted(positions)
    assert SCRIPT_TEXT.index("inferops::resolve_target\n") < positions[0]
    assert SCRIPT_TEXT.count("$(instant)") == 5
    assert constant("INSTANT_FORMAT") == "+%Y-%m-%dT%H:%M:%S.%3NZ"
    assert 'date -u "${INSTANT_FORMAT}"' in SCRIPT_TEXT


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
      printf 'partial answer that must not be kept\\n'
      printf 'Error from server (ServiceUnavailable): the server is currently unable to handle the request\\n' >&2
      exit 1
      ;;
  esac
fi
case "$*" in
  *"config get-contexts"*) printf '%s\\n' "${STUB_CONTEXT}" ;;
  *"config view --minify"*) printf 'kind: Config\\ncurrent-context: %s\\n' "${STUB_CONTEXT}" ;;
  *"config current-context"*) printf '%s\\n' "${STUB_CONTEXT}" ;;
  *"get services,endpointslices.discovery.k8s.io,pods,replicasets.apps,deployments.apps --namespace ${STUB_NAMESPACE} --request-timeout 10s -o json")
    cat "${STUB_READS}/workload.json" || exit 1 ;;
  *"get applications.argoproj.io ${STUB_APPLICATION} --namespace argocd --ignore-not-found --request-timeout 10s -o json")
    cat "${STUB_READS}/application.json" || exit 1 ;;
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


def uid(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012d}"


def labels(component: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/instance": RELEASE,
        "app.kubernetes.io/component": component,
    }


def tier_objects(service: str, component: str, number: int) -> list[dict]:
    """One Service, one slice, one ReplicaSet, one pod, and one Deployment."""
    pod = f"{service}-5d4f8c7b9-abcde"
    return [
        {
            "kind": "Service",
            "metadata": {
                "name": service,
                "namespace": NAMESPACE,
                "labels": labels(component),
            },
            "spec": {"type": "ClusterIP"},
        },
        {
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
                        "ready": True,
                        "serving": True,
                        "terminating": False,
                    },
                    "targetRef": {
                        "kind": "Pod",
                        "name": pod,
                        "namespace": NAMESPACE,
                        "uid": uid(number),
                    },
                }
            ],
        },
        {
            "kind": "ReplicaSet",
            "metadata": {
                "name": f"{service}-5d4f8c7b9",
                "namespace": NAMESPACE,
                "uid": uid(number + 100),
                "annotations": {"deployment.kubernetes.io/revision": "3"},
            },
        },
        {
            "kind": "Pod",
            "metadata": {
                "name": pod,
                "namespace": NAMESPACE,
                "uid": uid(number),
                "labels": labels(component),
                "ownerReferences": [
                    {
                        "kind": "ReplicaSet",
                        "name": f"{service}-5d4f8c7b9",
                        "uid": uid(number + 100),
                        "controller": True,
                    }
                ],
            },
            "status": {
                "phase": "Running",
                "podIP": f"10.1.0.{number}",
                "conditions": [{"type": "Ready", "status": "True"}],
                "containerStatuses": [
                    {"name": "main", "ready": True, "restartCount": 0}
                ],
            },
        },
        {
            "kind": "Deployment",
            "metadata": {
                "name": service,
                "namespace": NAMESPACE,
                "uid": uid(number + 200),
                "labels": labels(component),
            },
            "spec": {"replicas": 1},
            "status": {"replicas": 1, "readyReplicas": 1},
        },
    ]


def an_application() -> dict:
    return {
        "kind": "Application",
        "metadata": {"name": APPLICATION, "namespace": APPLICATION_NAMESPACE},
        "spec": {"source": {"targetRevision": "main"}},
        "status": {
            "sync": {"status": "Synced", "revision": COMMIT},
            "health": {"status": "Healthy"},
        },
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

        The target verification also reads the cluster. It asks for no object
        as JSON.
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
        return sorted(
            path.relative_to(self.directory).as_posix()
            for path in self.directory.rglob("*")
            if path.is_file()
        )

    def stream(self, name: str) -> timeline.Stream:
        path = self.directory / "streams" / timeline.STREAM_FILES[name]
        return timeline.read_stream(path.read_bytes().decode("utf-8"))

    def meta(self, index: int) -> dict[str, str]:
        text = (self.directory / f"sample-{index:04d}.meta").read_text("utf-8")
        return dict(line.split("=", 1) for line in text.splitlines())


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
    items = [
        *tier_objects(API_SERVICE, "platform-api", 1),
        *tier_objects(RUNTIME_SERVICE, "serving-runtime", 11),
    ]
    (reads / "workload.json").write_text(
        json.dumps({"apiVersion": "v1", "kind": "List", "items": items}), "utf-8"
    )
    (reads / "application.json").write_text(json.dumps(an_application()), "utf-8")
    return tmp_path


def run_script(
    sandbox: Path,
    *args: str,
    name: str = "capture-1",
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
    env["STUB_APPLICATION"] = APPLICATION
    # kubectl prints one member on each line, and the library reads it by line.
    env["STUB_VERSION_JSON"] = json.dumps(
        {
            "clientVersion": {"major": "1", "minor": "34", "gitVersion": "v1.34.1"},
            "serverVersion": {"major": "1", "minor": "34", "gitVersion": "v1.34.3"},
        },
        indent=2,
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


USUAL = ("--experiment", "example-experiment", "--run", "run-1", "--interval", "1")


@needs_bash
def test_a_capture_writes_each_read_and_four_streams_and_changes_nothing(
    sandbox: Path,
) -> None:
    run = run_script(sandbox, *USUAL, "--samples", "2", "--into", "capture-1")
    assert run.returncode == 0, run.output
    assert run.mutations == []
    assert run.files == [
        "collection.end",
        "collection.json",
        "sample-0001.application.json",
        "sample-0001.meta",
        "sample-0001.workload.json",
        "sample-0002.application.json",
        "sample-0002.meta",
        "sample-0002.workload.json",
        "streams/argo.jsonl",
        "streams/deployments.jsonl",
        "streams/endpoints.jsonl",
        "streams/pods.jsonl",
    ]
    assert run.collected == [WORKLOAD_READ, APPLICATION_READ] * 2

    header = json.loads((run.directory / "collection.json").read_text("utf-8"))
    assert header == {
        "schema": timeline.COLLECTION_SCHEMA,
        "experimentId": "example-experiment",
        "runId": "run-1",
        "provider": "kind",
        "serverVersion": "v1.34.3",
        "namespace": NAMESPACE,
        "release": RELEASE,
        "application": APPLICATION,
        "applicationNamespace": APPLICATION_NAMESPACE,
        "executingCommit": COMMIT,
        "procedureSha256": header["procedureSha256"],
        "librarySha256": header["librarySha256"],
        "requestedSamples": 2,
        "intervalSeconds": 1,
        "requestTimeoutSeconds": 10,
    }
    assert re.fullmatch(r"[0-9a-f]{64}", header["procedureSha256"])
    assert header["procedureSha256"] != header["librarySha256"]
    # Neither the header nor a stream names the kubeconfig context.
    for path in run.directory.rglob("*"):
        if path.is_file():
            assert KUBE_CONTEXT not in path.read_text("utf-8"), path.name

    for index in (1, 2):
        meta = run.meta(index)
        assert meta["workloadRead"] == meta["applicationRead"] == "answered"
        instants = [
            meta["workloadStartedAt"],
            meta["workloadFinishedAt"],
            meta["applicationStartedAt"],
            meta["applicationFinishedAt"],
        ]
        for instant in instants:
            assert re.fullmatch(INSTANT, instant, re.A), instant
        assert instants == sorted(instants)
    # The pause is between the two samples.
    assert run.meta(1)["applicationFinishedAt"] < run.meta(2)["workloadStartedAt"]

    # Each stream on disk is what the tool gives for the directory, in LF bytes.
    built = timeline.build_streams(run.directory)
    for name in timeline.STREAMS:
        written = (run.directory / "streams" / f"{name}.jsonl").read_bytes()
        assert written == timeline.stream_text(built[name]).encode("utf-8"), name
        stream = run.stream(name)
        assert stream.header["collection"]["complete"] is True
        assert stream.end["byReadState"]["answered"] == 2
    endpoints = run.stream("endpoints").readings[0]
    assert [tier["endpoints"]["ready"] for tier in endpoints["tiers"]] == [1, 1]
    pods = run.stream("pods").readings[0]["pods"]
    assert [pod["revision"] for pod in pods] == [{"state": "reported", "value": 3}] * 2
    argo = run.stream("argo").readings[1]["application"]
    assert argo["syncStatus"] == {"state": "reported", "value": "Synced"}

    assert "READ     endpoints: 2 reading(s): 2 answered" in run.output
    assert "This script judged none of them." in run.output
    assert "They are not a request that a caller sent." in run.output
    assert "Do not commit it." in run.output


@needs_bash
def test_a_workload_read_that_does_not_answer_leaves_no_file_and_no_value(
    sandbox: Path,
) -> None:
    run = run_script(
        sandbox,
        *USUAL,
        "--samples",
        "1",
        "--into",
        "capture-1",
        fail_on="get services,",
    )
    assert run.returncode == 0, run.output
    assert run.mutations == []
    assert "sample-0001.workload.json" not in run.files
    assert "sample-0001.application.json" in run.files
    assert run.meta(1)["workloadRead"] == "unanswered"
    for name in ("endpoints", "pods", "deployments"):
        [reading] = run.stream(name).readings
        assert reading["read"]["state"] == "unanswered"
        assert re.fullmatch(INSTANT, reading["read"]["startedAt"], re.A)
    assert run.stream("pods").readings[0]["pods"] is None
    assert run.stream("deployments").readings[0]["tiers"] is None
    # The other read of the same sample is as it was.
    [argo] = run.stream("argo").readings
    assert argo["read"]["state"] == "answered"
    assert argo["application"]["healthStatus"]["value"] == "Healthy"
    assert "workload read unanswered, Application read answered" in run.output
    assert "did not answer" in run.output
    assert "It is not a healthy state, and it is not zero." in run.output
    assert "partial answer that must not be kept" not in "".join(
        path.read_text("utf-8") for path in run.directory.rglob("*") if path.is_file()
    )


@needs_bash
def test_an_application_read_that_does_not_answer_leaves_the_workload_streams(
    sandbox: Path,
) -> None:
    run = run_script(
        sandbox,
        *USUAL,
        "--samples",
        "1",
        "--into",
        "capture-1",
        fail_on="get applications.argoproj.io",
    )
    assert run.returncode == 0, run.output
    assert "sample-0001.application.json" not in run.files
    [argo] = run.stream("argo").readings
    assert argo["read"]["state"] == "unanswered"
    assert argo["application"] is None
    assert run.stream("endpoints").readings[0]["tiers"] is not None
    assert "partial answer that must not be kept" not in "".join(
        path.read_text("utf-8") for path in run.directory.rglob("*") if path.is_file()
    )
    assert "workload read answered, Application read unanswered" in run.output


@needs_bash
def test_an_absent_application_is_an_answer_and_not_a_failed_read(
    sandbox: Path,
) -> None:
    (sandbox / "reads" / "application.json").write_text("", "utf-8")
    run = run_script(sandbox, *USUAL, "--samples", "1", "--into", "capture-1")
    assert run.returncode == 0, run.output
    assert run.meta(1)["applicationRead"] == "answered"
    [argo] = run.stream("argo").readings
    assert argo["read"]["state"] == "absent"
    assert argo["application"] is None
    assert "Application read answered with no object" in run.output


@needs_bash
def test_an_earlier_collection_is_not_written_into(sandbox: Path) -> None:
    first = run_script(sandbox, *USUAL, "--samples", "1", "--into", "capture-1")
    assert first.returncode == 0, first.output
    before = {name: (first.directory / name).read_bytes() for name in first.files}
    second = run_script(sandbox, *USUAL, "--samples", "1", "--into", "capture-1")
    assert second.returncode == 1
    assert "already exists" in second.output
    assert second.kubectl == []
    assert {
        name: (first.directory / name).read_bytes() for name in first.files
    } == before


@needs_bash
@pytest.mark.parametrize(
    "args,message",
    [
        ((), "--experiment needs an experiment identifier"),
        (("--experiment", "example-experiment"), "--run needs a run identifier"),
        (("--experiment", "has space", "--run", "r"), "--experiment needs"),
        (("--experiment", "e", "--run", "../r"), "--run needs a run identifier"),
        (("--experiment", "e", "--run", "r"), "--samples needs a whole number"),
        (("--experiment", "e", "--run", "r", "--samples", "0"), "--samples needs"),
        (("--experiment", "e", "--run", "r", "--samples", "1801"), "--samples needs"),
        (("--experiment", "e", "--run", "r", "--samples", "2x"), "--samples needs"),
        (("--experiment", "e", "--run", "r", "--samples", "1"), "--interval needs"),
        (
            ("--experiment", "e", "--run", "r", "--samples", "1", "--interval", "31"),
            "--interval needs",
        ),
        (
            ("--experiment", "e", "--run", "r", "--samples", "1", "--interval", "0"),
            "--interval needs",
        ),
        ((*USUAL, "--samples", "1", "--into", "../x"), "is not usable"),
        ((*USUAL, "--samples", "1", "--into", ".hidden"), "is not usable"),
        ((*USUAL, "--samples"), "--samples needs a value"),
        ((*USUAL, "--samples", "1", "--samples", "2"), "--samples was given twice"),
        ((*USUAL, "--run", "again"), "--run was given twice"),
        ((*USUAL, "--samples", "1", "--watch"), "unknown argument"),
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
    run = run_script(
        sandbox, *USUAL, "--samples", "1", "--into", "capture-1", provider=None
    )
    assert run.returncode != 0
    assert run.collected == []
    assert run.files == []


@needs_bash
def test_a_tree_with_no_commit_writes_no_collection(sandbox: Path) -> None:
    run = run_script(
        sandbox, *USUAL, "--samples", "1", "--into", "capture-1", commit=""
    )
    assert run.returncode == 1
    assert "could not read the commit" in run.output
    assert run.collected == []
    assert run.files == []
