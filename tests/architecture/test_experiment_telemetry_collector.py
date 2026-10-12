"""The collector script of the telemetry streams, read as text and executed against stubs.

``scripts/environment/experiment-telemetry.sh`` asks the telemetry collector of
the release a registered set of queries a bounded number of times and writes one
directory. ``tools.experiment_telemetry`` builds two streams from that directory.
This suite holds the script to six properties.

*It changes nothing in the cluster.* Each kubectl call the script holds is a
``get`` with a request timeout. An executed run makes no kubectl call that is
not a known read: the target verification adds ``config`` reads and its own
``get`` and ``version`` calls. The verification also writes the target's
kubeconfig under ``.kube/``.

*It sends nothing to the API of the release.* The script holds no ``curl``, no
``wget``, no ``port-forward``, and no ``exec``, and each path that it asks for
is under the proxy path of the one Service of the telemetry collector. So a
stream is not a request that a caller sent, and the script cannot make it one.

*It holds no query of its own.* It asks the tool for each request, and it holds
each one to a fixed form before it gives it to kubectl.

*It is bounded.* The number of samples and the pause are arguments with a
minimum and a maximum, each read has a timeout, and arguments that are not
usable are refused before any call.

*It agrees with the tool.* The file names, the schema, the stream names, and
the bounds are restated in the script, and each is compared with the tool's.

*A read that does not answer is not an empty result.* An executed run whose
read fails writes no file for that read, and the streams state no result for
it. A run against a release with no collector states each read as absent.

The executed tests need ``bash`` and skip without it. The stubs stand in for
kubectl, kind, docker, and git. A fifth stub records each call of ``python`` and
passes it to the interpreter of this suite. The kubectl stub answers a ``get``
of a raw path from a table that the test writes, and it fails a path that the
table does not hold. No test contacts a cluster or a collector, so no test here
is evidence of telemetry of a real run.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tools import experiment_telemetry as telemetry

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_REL = "scripts/environment/experiment-telemetry.sh"
LIB_REL = "scripts/environment/lib.sh"
VERIFY_REL = "scripts/environment/telemetry-collection-verify.sh"
SCRIPT_TEXT = (REPO_ROOT / SCRIPT_REL).read_text(encoding="utf-8")
LIB_TEXT = (REPO_ROOT / LIB_REL).read_text(encoding="utf-8")
VERIFY_TEXT = (REPO_ROOT / VERIFY_REL).read_text(encoding="utf-8")
COLLECTIONS = ".artifacts/experiment-telemetry/collections"

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
SERVICE = "inferops-inferops-llm-collector"
PROXY = f"/api/v1/namespaces/{NAMESPACE}/services/{SERVICE}:http/proxy"
COMMIT = "1" * 40
SERVICE_READ = [
    "get",
    "service",
    SERVICE,
    "--namespace",
    NAMESPACE,
    "--ignore-not-found",
    "-o",
    "json",
    "--request-timeout",
    "10s",
]
INSTANT = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z"
NAMES = [query.name for query in telemetry.QUERIES]

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


def query_read(name: str) -> list[str]:
    query = next(q for q in telemetry.QUERIES if q.name == name)
    return [
        "get",
        "--raw",
        f"{PROXY}/{telemetry.request_path(query)}",
        "--request-timeout",
        "10s",
    ]


# --------------------------------------------------------------------------
# The script, as text
# --------------------------------------------------------------------------


def test_each_kubectl_call_of_the_script_is_a_get() -> None:
    """An allow-list: the script holds one kubectl line, and its verb is ``get``.

    Each cluster call goes through the one ``collect`` function, which states
    the verb and appends the read timeout. So the calls are the arguments of
    ``collect``.
    """
    # Every line that names kubectl in any spelling: a wrapper of the library,
    # the bare command, and a variable that holds it would each be one more.
    named = [line for line in code_lines() if "kubectl" in line.lower()]
    assert named == [
        "inferops::require_cmd kubectl",
        '  if inferops::target_kubectl get "$@" --request-timeout '
        '"${REQUEST_TIMEOUT_SECONDS}s" >"${file}" 2>/dev/null; then',
    ]
    assert not [line for line in code_lines() if re.search(r"\bhelm\b", line)]

    calls = [
        line.split() for line in code_lines() if re.match(r"\s*(if )?collect ", line)
    ]
    assert calls == [
        [
            "collect",
            '"${stem}.collector.json"',
            "service",
            '"${COLLECTOR_SERVICE}"',
            "--namespace",
            '"${INFEROPS_RELEASE_NAMESPACE}"',
            "--ignore-not-found",
            "-o",
            "json",
            "||",
        ],
        [
            "if",
            "collect",
            '"${stem}.query.${name}.json"',
            "--raw",
            '"${PROXY_PATH}/${query_paths[${position}]}";',
            "then",
        ],
    ]


def test_each_raw_path_is_under_the_proxy_of_the_one_collector_service() -> None:
    """The script can ask the collector's Service and no other one."""
    assert constant("PROXY_PATH") == (
        "/api/v1/namespaces/${INFEROPS_RELEASE_NAMESPACE}/services/"
        "${COLLECTOR_SERVICE}:${COLLECTOR_PORT}/proxy"
    )
    assert (
        constant("COLLECTOR_SERVICE")
        == "${INFEROPS_RELEASE_NAME}-inferops-llm-collector"
    )
    assert constant("COLLECTOR_PORT") == "http"
    # The collection verification names the same Service.
    assert '"${INFEROPS_RELEASE_NAME}-inferops-llm-collector"' in VERIFY_TEXT
    assert SCRIPT_TEXT.count("--raw") == 1
    assert SCRIPT_TEXT.count("PROXY_PATH") == 2
    # The chart names the port of the Service `http`.
    chart = (
        REPO_ROOT / "charts/inferops-llm/templates/telemetry-collector.yaml"
    ).read_text(encoding="utf-8")
    service = chart[chart.index("kind: Service\n") : chart.index("kind: Deployment\n")]
    assert "- name: http\n" in service


def test_the_delivered_release_installs_the_collector_and_the_chart_default_does_not() -> (
    None
):
    """The page says which release has a collector. The two files say so."""
    application = (
        REPO_ROOT / "infra/argocd/local-docker-desktop-support-assistant.yaml"
    ).read_text(encoding="utf-8")
    lines = application.splitlines()
    telemetry_at = lines.index("        telemetry:")
    block = [line for line in lines[telemetry_at + 1 :] if line.startswith(" " * 10)]
    assert "            collector:" in block
    assert (
        block[block.index("            collector:") + 1] == "              deploy: true"
    )
    values = (REPO_ROOT / "charts/inferops-llm/values.yaml").read_text(encoding="utf-8")
    lines = values.splitlines()
    # The first `collector:` at this depth is the one under telemetry.collection.
    after = lines[lines.index("    collector:") + 1 :]
    stated = [line for line in after if line.startswith("      deploy:")]
    assert stated[0] == "      deploy: false"


def test_the_script_sends_nothing_to_the_api_of_the_release() -> None:
    """No request to the release, no forwarded port, and no process inside a pod."""
    for word in ("curl", "wget", "port-forward", "exec", "docker", "nc", "logs"):
        assert not [
            line for line in code_lines() if re.search(rf"(^|[\s(|;&]){word}\b", line)
        ], word
    assert "/metrics" not in SCRIPT_TEXT
    assert "/v1/chat" not in SCRIPT_TEXT
    for line in code_lines():
        assert "urllib" not in line and "socket" not in line, line


def test_the_script_holds_no_query_and_holds_each_request_to_a_form() -> None:
    """The tool registers the queries. The script holds none of their text."""
    for query in telemetry.QUERIES:
        assert query.expression not in SCRIPT_TEXT, query.name
        assert query.name not in SCRIPT_TEXT, query.name
    for word in ("inferops_", "k8s_component", "sum(", "count(", "sum by"):
        assert word not in SCRIPT_TEXT, word
    assert 'inferops::python -m "${TELEMETRY_MODULE}" requests' in SCRIPT_TEXT
    assert r"^api/v1/query\?query=[A-Za-z0-9%._~-]+$" in SCRIPT_TEXT
    assert '"${#second}" -le 512' in SCRIPT_TEXT
    for query in telemetry.QUERIES:
        assert len(telemetry.request_path(query)) <= 512, query.name
    assert "^[0-9a-f]{64}$" in SCRIPT_TEXT
    # The requests are read before the target is resolved, so a tool that gives
    # no usable request stops the script before any call to a cluster.
    assert SCRIPT_TEXT.index("requests)") < SCRIPT_TEXT.index(
        "inferops::resolve_target\n"
    )


def test_the_script_removes_only_what_it_wrote_in_its_own_directory() -> None:
    # The first removes the one file of a read that did not answer.
    removals = [line.strip() for line in code_lines() if re.search(r"\brm\b", line)]
    assert removals == [
        'rm -f "${file}"',
        'rm -f "${collection_dir}/streams/${name}.jsonl"',
    ]


def test_the_script_restates_the_tools_names_and_bounds_and_each_agrees() -> None:
    assert constant("COLLECTION_SCHEMA") == telemetry.COLLECTION_SCHEMA
    assert constant("TELEMETRY_MODULE") == "tools.experiment_telemetry"
    assert constant("COLLECTIONS_REL") == COLLECTIONS
    assert tuple(constant("STREAM_NAMES").split()) == telemetry.STREAMS
    assert int(constant("MAX_SAMPLES")) == telemetry.MAX_SAMPLES
    assert int(constant("MIN_INTERVAL_SECONDS")) == telemetry.MIN_INTERVAL_SECONDS
    assert int(constant("MAX_INTERVAL_SECONDS")) == telemetry.MAX_INTERVAL_SECONDS
    assert (
        1
        <= int(constant("REQUEST_TIMEOUT_SECONDS"))
        <= telemetry.MAX_REQUEST_TIMEOUT_SECONDS
    )
    assert f'"${{collection_dir}}/{telemetry.HEADER_FILE}"' in SCRIPT_TEXT
    assert f'"${{collection_dir}}/{telemetry.END_FILE}"' in SCRIPT_TEXT
    assert telemetry.SAMPLE_STEM.format(index=7) == "sample-0007"
    assert "printf 'sample-%04d'" in SCRIPT_TEXT
    assert f'"${{stem}}{telemetry.COLLECTOR_SUFFIX}"' in SCRIPT_TEXT
    assert f'"${{stem}}{telemetry.META_SUFFIX}"' in SCRIPT_TEXT
    assert telemetry.QUERY_SUFFIX == ".query.{name}.json"
    assert '"${stem}.query.${name}.json"' in SCRIPT_TEXT
    for name in telemetry.STREAMS:
        assert telemetry.STREAM_FILES[name] == f"{name}.jsonl"
    assert '"${collection_dir}/streams/${name}.jsonl"' in SCRIPT_TEXT
    # The script admits as many queries as the tool registers.
    assert len(telemetry.QUERIES) <= 32
    assert '"${#query_names[@]}" -le 32' in SCRIPT_TEXT


def test_the_script_reads_the_release_that_the_library_names() -> None:
    assert constant("INFEROPS_RELEASE_NAME", LIB_TEXT) == RELEASE
    assert constant("INFEROPS_RELEASE_NAMESPACE", LIB_TEXT) == NAMESPACE
    assert "INFEROPS_RELEASE_SELECTOR" not in SCRIPT_TEXT


def test_two_instants_bracket_each_read_and_each_states_milliseconds() -> None:
    order = [
        'collector_started_at="$(instant)"',
        'collect "${stem}.collector.json"',
        'collector_finished_at="$(instant)"',
        'query_started_at="$(instant)"',
        'collect "${stem}.query.${name}.json"',
        'query_finished_at="$(instant)"',
        'printf \'%s\\n\' "${meta}" >"${stem}.meta"',
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
  *"get service ${STUB_SERVICE} --namespace ${STUB_NAMESPACE} --ignore-not-found -o json --request-timeout 10s")
    cat "${STUB_READS}/collector.json" || exit 1 ;;
  *"get --raw "*)
    previous=""
    path=""
    for word in "$@"; do
      [ "${previous}" = "--raw" ] && path="${word}"
      previous="${word}"
    done
    while IFS=' ' read -r known file; do
      if [ "${known}" = "${path}" ]; then
        cat "${STUB_READS}/${file}" || exit 1
        exit 0
      fi
    done <"${STUB_READS}/raw.table"
    printf 'Error from server (NotFound): the server could not find the requested resource\\n' >&2
    exit 1 ;;
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
# sandbox holds no copy of the tool. A test can replace what `requests` prints.
_PYTHON_STUB = """#!/usr/bin/env bash
if [ "$1" = "-m" ]; then
  printf 'python %s\\n' "$*" >>"${INFEROPS_STUB_LOG}"
  if [ "$3" = "requests" ] && [ -n "${STUB_REQUESTS_FILE:-}" ]; then
    cat "${STUB_REQUESTS_FILE}"
    exit "${STUB_REQUESTS_STATUS:-0}"
  fi
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

EVALUATED = 1791792000.04


def vector(*series: tuple[dict[str, str], str]) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": labels, "value": [EVALUATED, value]}
                for labels, value in series
            ],
        },
    }


def usual_answers() -> dict[str, Any]:
    return {
        "api-scrape-targets": vector(({}, "2")),
        "api-scrape-targets-up": vector(({}, "2")),
        "api-oldest-scrape": vector(({}, "1791791985.250")),
        "runtime-scrape-targets": vector(({}, "2")),
        "runtime-scrape-targets-up": vector(({}, "2")),
        "runtime-oldest-scrape": vector(({}, "1791791990.5")),
        "api-requests-by-outcome": vector(({"inferops_outcome": "success"}, "120")),
        "api-errors-by-code": vector(),
        "api-processes-reporting-cpu": vector(({}, "2")),
        "api-cpu-seconds": vector(({}, "12.5")),
        "api-resident-memory-bytes": vector(),
    }


class Run:
    """One execution of the script against the stubs."""

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
        """The reads that the script collects: each ``get`` with the read timeout.

        The target verification also reads the cluster. It states no request
        timeout of 10 seconds.
        """
        return [
            call
            for call in self.kubectl
            if call[0] == "get" and call[-2:] == ["--request-timeout", "10s"]
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

    def stream(self, name: str) -> telemetry.Stream:
        path = self.directory / "streams" / telemetry.STREAM_FILES[name]
        return telemetry.read_stream(path.read_bytes().decode("utf-8"))

    def meta(self, index: int) -> dict[str, str]:
        text = (self.directory / f"sample-{index:04d}.meta").read_text("utf-8")
        return dict(line.split("=", 1) for line in text.splitlines())


def write_answers(sandbox: Path, answers: dict[str, Any]) -> None:
    """The table of raw paths that the kubectl stub answers, and each answer."""
    reads = sandbox / "reads"
    table = []
    for query in telemetry.QUERIES:
        if query.name not in answers:
            continue
        (reads / f"{query.name}.json").write_text(
            json.dumps(answers[query.name]), "utf-8"
        )
        table.append(f"{PROXY}/{telemetry.request_path(query)} {query.name}.json\n")
    (reads / "raw.table").write_text("".join(table), "utf-8", newline="\n")


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
    (reads / "collector.json").write_text(
        json.dumps(
            {
                "kind": "Service",
                "metadata": {"name": SERVICE, "namespace": NAMESPACE},
                "spec": {"clusterIP": "10.96.44.7"},
            }
        ),
        "utf-8",
    )
    write_answers(tmp_path, usual_answers())
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
    env["STUB_SERVICE"] = SERVICE
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
        timeout=300,
    )
    return Run(completed, log, sandbox / COLLECTIONS / name)


USUAL = ("--experiment", "example-experiment", "--run", "run-1", "--interval", "5")
ONE = (*USUAL, "--samples", "1", "--into", "capture-1")


@needs_bash
def test_a_capture_writes_each_read_and_two_streams_and_changes_nothing(
    sandbox: Path,
) -> None:
    run = run_script(sandbox, *USUAL, "--samples", "2", "--into", "capture-1")
    assert run.returncode == 0, run.output
    assert run.mutations == []
    expected = ["collection.end", "collection.json"]
    for index in (1, 2):
        expected.append(f"sample-{index:04d}.collector.json")
        expected.append(f"sample-{index:04d}.meta")
        expected.extend(
            f"sample-{index:04d}.query.{name}.json" for name in sorted(NAMES)
        )
    expected.extend(["streams/resources.jsonl", "streams/telemetry.jsonl"])
    assert run.files == sorted(expected)
    assert run.collected == [SERVICE_READ, *(query_read(name) for name in NAMES)] * 2
    # Each raw path is under the proxy of the one Service.
    for call in run.kubectl:
        if "--raw" in call:
            assert call[call.index("--raw") + 1].startswith(f"{PROXY}/api/v1/query?")

    header = json.loads((run.directory / "collection.json").read_text("utf-8"))
    assert header == {
        "schema": telemetry.COLLECTION_SCHEMA,
        "experimentId": "example-experiment",
        "runId": "run-1",
        "provider": "kind",
        "serverVersion": "v1.34.3",
        "namespace": NAMESPACE,
        "release": RELEASE,
        "collectorService": SERVICE,
        "collectorPort": "http",
        "querySet": telemetry.QUERY_SET,
        "querySetSha256": telemetry.query_set_sha256(),
        "executingCommit": COMMIT,
        "procedureSha256": header["procedureSha256"],
        "librarySha256": header["librarySha256"],
        "requestedSamples": 2,
        "intervalSeconds": 5,
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
        assert meta["collectorRead"] == "answered"
        instants = [meta["collectorStartedAt"], meta["collectorFinishedAt"]]
        for name in NAMES:
            assert meta[f"query.{name}.read"] == "answered"
            instants += [
                meta[f"query.{name}.startedAt"],
                meta[f"query.{name}.finishedAt"],
            ]
        for instant in instants:
            assert re.fullmatch(INSTANT, instant, re.A), instant
        assert instants == sorted(instants)
        assert len(meta) == 3 + 3 * len(NAMES)
    # The pause is between the two samples.
    last = f"query.{NAMES[-1]}.finishedAt"
    assert run.meta(1)[last] < run.meta(2)["collectorStartedAt"]

    # Each stream on disk is what the tool gives for the directory, in LF bytes.
    built = telemetry.build_streams(run.directory)
    for name in telemetry.STREAMS:
        written = (run.directory / "streams" / f"{name}.jsonl").read_bytes()
        assert written == telemetry.stream_text(built[name]).encode("utf-8"), name
        assert run.stream(name).header["collection"]["complete"] is True
    stream = run.stream("telemetry")
    assert stream.end["byReadState"]["answered"] == 16
    assert stream.end["byResult"] == {"series": 14, "no-series": 2}
    assert stream.readings[0]["series"] == [
        {"labels": {}, "value": {"state": "reported", "value": 2}}
    ]
    memory = run.stream("resources").readings[2]
    assert memory["query"] == "api-resident-memory-bytes"
    assert (memory["result"], memory["series"]) == ("no-series", [])
    # The address of the Service is in the collection and in no stream.
    assert "10.96.44.7" in (run.directory / "sample-0001.collector.json").read_text(
        "utf-8"
    )
    for name in telemetry.STREAMS:
        text = (run.directory / "streams" / f"{name}.jsonl").read_text("utf-8")
        assert "10.96.44.7" not in text

    assert "READ     telemetry: 16 reading(s): 16 answered" in run.output
    assert "query set experiment-run-queries-r1: 11 queries" in run.output
    assert "This script judged none of them." in run.output
    assert "They are not a request that a caller sent." in run.output
    assert "An answer with no series is not a value of zero." in run.output
    assert "Do not commit it." in run.output


@needs_bash
def test_a_query_that_does_not_answer_leaves_no_file_and_no_result(
    sandbox: Path,
) -> None:
    failing = telemetry.request_path(telemetry.QUERIES[7])
    assert telemetry.QUERIES[7].name == "api-errors-by-code"
    run = run_script(sandbox, *ONE, fail_on=failing)
    assert run.returncode == 0, run.output
    assert run.mutations == []
    assert "sample-0001.query.api-errors-by-code.json" not in run.files
    assert "sample-0001.query.api-requests-by-outcome.json" in run.files
    assert run.meta(1)["query.api-errors-by-code.read"] == "unanswered"
    readings = {r["query"]: r for r in run.stream("telemetry").readings}
    reading = readings["api-errors-by-code"]
    assert reading["read"]["state"] == "unanswered"
    assert re.fullmatch(INSTANT, reading["read"]["startedAt"], re.A)
    assert (reading["result"], reading["series"]) == (None, None)
    # The other reads of the same sample are as they were.
    assert readings["api-requests-by-outcome"]["result"] == "series"
    assert "10 of 11 queries answered" in run.output
    assert "It is not a value of zero, and it is not a healthy state." in run.output
    assert "partial answer that must not be kept" not in "".join(
        path.read_text("utf-8") for path in run.directory.rglob("*") if path.is_file()
    )


@needs_bash
def test_a_release_with_no_collector_states_each_read_as_absent(sandbox: Path) -> None:
    """The Service read answers with no object, and the proxy answers no path."""
    (sandbox / "reads" / "collector.json").write_text("", "utf-8")
    write_answers(sandbox, {})
    run = run_script(sandbox, *ONE)
    assert run.returncode == 0, run.output
    assert run.mutations == []
    assert run.meta(1)["collectorRead"] == "answered"
    assert run.files == [
        "collection.end",
        "collection.json",
        "sample-0001.collector.json",
        "sample-0001.meta",
        "streams/resources.jsonl",
        "streams/telemetry.jsonl",
    ]
    for name in telemetry.STREAMS:
        stream = run.stream(name)
        assert {r["read"]["state"] for r in stream.readings} == {"absent"}
        assert {r["collector"] for r in stream.readings} == {"absent"}
        assert all(r["series"] is None for r in stream.readings)
        assert stream.end["byResult"] == {"series": 0, "no-series": 0}
    assert "READ     telemetry: 8 reading(s): 8 absent; 0 with series" in run.output
    assert "0 of 11 queries answered" in run.output


@needs_bash
def test_a_service_read_that_does_not_answer_leaves_the_queries(sandbox: Path) -> None:
    run = run_script(sandbox, *ONE, fail_on="get service")
    assert run.returncode == 0, run.output
    assert "sample-0001.collector.json" not in run.files
    assert run.meta(1)["collectorRead"] == "unanswered"
    stream = run.stream("telemetry")
    assert {r["collector"] for r in stream.readings} == {"not-read"}
    assert stream.end["byReadState"]["answered"] == 8
    assert "Service read unanswered, 11 of 11 queries answered" in run.output


@needs_bash
def test_an_earlier_collection_is_not_written_into(sandbox: Path) -> None:
    first = run_script(sandbox, *ONE)
    assert first.returncode == 0, first.output
    before = {name: (first.directory / name).read_bytes() for name in first.files}
    second = run_script(sandbox, *ONE)
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
        (("--experiment", "e", "--run", "r", "--samples", "721"), "--samples needs"),
        (("--experiment", "e", "--run", "r", "--samples", "2x"), "--samples needs"),
        (("--experiment", "e", "--run", "r", "--samples", "1"), "--interval needs"),
        (
            ("--experiment", "e", "--run", "r", "--samples", "1", "--interval", "121"),
            "--interval needs",
        ),
        (
            ("--experiment", "e", "--run", "r", "--samples", "1", "--interval", "4"),
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
        ((*USUAL, "--samples", "1", "--query", "up"), "unknown argument"),
    ],
)
def test_arguments_that_are_not_usable_are_refused_before_any_call(
    sandbox: Path, args: tuple[str, ...], message: str
) -> None:
    run = run_script(sandbox, *args)
    assert run.returncode == 1
    assert message in run.output
    assert run.kubectl == []
    assert not [call for call in run.calls if call.startswith("python")]
    assert not (sandbox / COLLECTIONS).exists()


@needs_bash
@pytest.mark.parametrize(
    "lines,message",
    [
        ("", "no query set, no query"),
        (f"query-set set-1 {'0' * 64}\n", "no query set, no query"),
        ("query a api/v1/query?query=up\n", "no query set, no query"),
        (
            f"query-set set-1 {'0' * 64}\nquery a api/v1/query?query=up extra\n",
            "more than three words",
        ),
        (f"query-set set-1 {'0' * 63}\n", "not a name and a SHA-256"),
        (
            f"query-set set-1 {'0' * 64}\nquery-set set-2 {'0' * 64}\n",
            "or it printed two",
        ),
        (
            f"query-set set-1 {'0' * 64}\nquery a api/v1/admin/tsdb/delete_series\n",
            "not a query name and an encoded instant query",
        ),
        (
            f"query-set set-1 {'0' * 64}\nquery a ../../pods/x/proxy/v1/chat\n",
            "not a query name and an encoded instant query",
        ),
        (
            f"query-set set-1 {'0' * 64}\nquery a api/v1/query?query=up&time=1\n",
            "not a query name and an encoded instant query",
        ),
        (
            f"query-set set-1 {'0' * 64}\nquery a api/v1/query?query=up;id\n",
            "not a query name and an encoded instant query",
        ),
        (
            f"query-set set-1 {'0' * 64}\nquery A/b api/v1/query?query=up\n",
            "not a query name and an encoded instant query",
        ),
        (
            f"query-set set-1 {'0' * 64}\ndelete a api/v1/query?query=up\n",
            "unknown kind",
        ),
        (
            f"query-set set-1 {'0' * 64}\nquery a api/v1/query?query=up\n"
            "query a api/v1/query?query=up\n",
            "one query name twice",
        ),
    ],
)
def test_a_request_that_does_not_have_the_form_stops_the_script_before_any_call(
    sandbox: Path, lines: str, message: str
) -> None:
    """The script gives kubectl no text that it did not hold to the form."""
    requests = sandbox / "requests.txt"
    requests.write_text(lines, "utf-8", newline="\n")
    run = run_script(sandbox, *ONE, requests_file=requests.as_posix())
    assert run.returncode == 1
    assert message in run.output
    assert "Nothing was read." in run.output
    assert run.kubectl == []
    assert not (sandbox / COLLECTIONS).exists()


@needs_bash
def test_a_tool_that_gives_no_request_stops_the_script_before_any_call(
    sandbox: Path,
) -> None:
    requests = sandbox / "requests.txt"
    requests.write_text("", "utf-8")
    run = run_script(
        sandbox, *ONE, requests_file=requests.as_posix(), requests_status="3"
    )
    assert run.returncode == 1
    assert "the tool gave no registered request" in run.output
    assert run.kubectl == []


@needs_bash
def test_a_collection_of_other_queries_gives_no_stream_and_is_kept(
    sandbox: Path,
) -> None:
    """Requests of the form that are not the tool's: the tool refuses the header."""
    requests = sandbox / "requests.txt"
    requests.write_text(
        f"query-set other-set {'0' * 64}\nquery other api/v1/query?query=up\n",
        "utf-8",
        newline="\n",
    )
    run = run_script(sandbox, *ONE, requests_file=requests.as_posix())
    assert run.returncode == 1
    assert run.mutations == []
    assert "the tool wrote no telemetry stream" in run.output
    assert "The reads are kept in that directory." in run.output
    assert "collection.json" in run.files
    assert not [name for name in run.files if name.startswith("streams/")]


@needs_bash
def test_no_provider_is_refused_before_any_read_is_collected(sandbox: Path) -> None:
    run = run_script(sandbox, *ONE, provider=None)
    assert run.returncode != 0
    assert run.collected == []
    assert run.files == []


@needs_bash
def test_a_tree_with_no_commit_writes_no_collection(sandbox: Path) -> None:
    run = run_script(sandbox, *ONE, commit="")
    assert run.returncode == 1
    assert "could not read the commit" in run.output
    assert run.collected == []
    assert run.files == []
