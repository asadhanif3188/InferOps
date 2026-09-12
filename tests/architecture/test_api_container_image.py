"""The API container image, its entrypoint, and what the image may contain.

Sprint 3 shipped a chart that mounts an API image nobody could build. The values
carried a digest that was the SHA-256 of the ASCII string
`inferops-api-image-not-yet-published` -- honest, clearly labelled, and not a
digest of anything -- and no Dockerfile was committed. So the release could not
install, `helm test` had never run, and every probe, grace period and security
setting the chart declared was a statement about a container that did not exist.

This module covers the build path that closes that. It checks four things, and
each is a way the path could be complete on paper and broken in practice.

**The image is pinned, unprivileged, and writes nothing.** The chart runs every
container as uid 65534 with a read-only root filesystem and all capabilities
dropped. An image built to run as root, or one that needs to write bytecode
beside its source, satisfies none of that and fails at the point where it is
hardest to debug -- inside a pod, behind a probe that never passes.

**The image contains the application and nothing else.** `tools/` holds a model
downloader, a container packager, a certification driver and a manifest reader.
None belongs in a serving container, and the ignore file plus the copy list are
what keep them out. This is also why the HTTP carrier moved to
`tools.api_carrier`: reaching it through `tools.local_composition` imported that
package's `__init__`, and through it the host tooling.

**The entrypoint states its address rather than defaulting it.** The host
composition binds loopback and `tools.local_composition.core` refuses a
composition that does not. A container has to bind something reachable from a
Service, and the way to keep that from eroding the host rule by proximity is to
require the value, name it, and refuse when it is absent -- which is asserted
here by running the entrypoint and reading its exit status.

**No unverified digest replaces the old one.** The placeholder is still in the
committed values, because the honest replacement is a digest read back from an
image that was actually built, and that belongs in a generated overlay rather
than in version control. A test says so, so that a future change that pastes some
digest into the committed values has to delete this test to do it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = REPO_ROOT / "deploy" / "api" / "Dockerfile"
DOCKERIGNORE_PATH = REPO_ROOT / ".dockerignore"
IMAGE_SCRIPT_PATH = REPO_ROOT / "scripts" / "environment" / "api-image.sh"
SHIM_PATH = REPO_ROOT / "tools" / "local_composition" / "http_server.py"
CHART_VALUES_PATH = REPO_ROOT / "charts" / "inferops-llm" / "values.yaml"
REAL_VALUES_PATH = REPO_ROOT / "charts" / "inferops-llm" / "ci" / "real-values.yaml"

DOCKERFILE = DOCKERFILE_PATH.read_text(encoding="utf-8")
DOCKERIGNORE = DOCKERIGNORE_PATH.read_text(encoding="utf-8")
IMAGE_SCRIPT = IMAGE_SCRIPT_PATH.read_text(encoding="utf-8")
CHART_VALUES = yaml.safe_load(CHART_VALUES_PATH.read_text(encoding="utf-8"))
REAL_VALUES = yaml.safe_load(REAL_VALUES_PATH.read_text(encoding="utf-8"))

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")

# The placeholder the chart has carried since V1-S3-002: the SHA-256 of the
# ASCII string below, which anyone can recompute and no registry serves.
PLACEHOLDER_SOURCE = "inferops-api-image-not-yet-published"


def run_entrypoint(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the container entrypoint out of process and report what it did.

    Out of process because the property under test is an exit status, and because
    the entrypoint installs signal handlers -- which a test importing it into the
    session would install into the test runner.
    """
    env = dict(os.environ)
    env.pop("INFEROPS_BIND_HOST", None)
    env.pop("INFEROPS_BIND_PORT", None)
    env["PYTHONPATH"] = os.pathsep.join(["src", str(REPO_ROOT)])
    env.update(environment)
    return subprocess.run(
        [sys.executable, "-m", "tools.api_container"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


# --------------------------------------------------------------------------
# The image is pinned, unprivileged, and writes nothing
# --------------------------------------------------------------------------


def test_the_build_definition_is_committed() -> None:
    """The gap the review named: a chart that mounts an image with no Dockerfile."""
    assert DOCKERFILE_PATH.is_file(), DOCKERFILE_PATH


def test_the_base_image_is_pinned_by_digest() -> None:
    """A tag is a name somebody can move; the chart pins every other image too."""
    from_lines = [line for line in DOCKERFILE.splitlines() if line.startswith("FROM ")]
    assert len(from_lines) == 1, from_lines
    assert "@sha256:" in from_lines[0], from_lines[0]
    assert DIGEST.search(from_lines[0]), from_lines[0]


def test_the_image_runs_as_the_user_the_chart_declares() -> None:
    """65534, the same uid the pod security context sets.

    An image that runs as root passes `docker run` and then fails
    `runAsNonRoot: true` at admission, which is a worse place to find out.
    """
    expected = CHART_VALUES["security"]["runAsUser"]
    assert f"USER {expected}:{expected}" in DOCKERFILE, expected


def test_the_image_writes_no_bytecode() -> None:
    """The root filesystem is read-only, so a `__pycache__` write is a crash."""
    assert "PYTHONDONTWRITEBYTECODE=1" in DOCKERFILE


def test_the_entrypoint_is_exec_form_so_it_receives_the_signal() -> None:
    """Shell form puts `/bin/sh` at PID 1, and it does not forward SIGTERM.

    That is the usual reason a pod burns its whole termination grace period and
    is then killed on every rollout.
    """
    assert 'ENTRYPOINT ["python", "-m", "tools.api_container"]' in DOCKERFILE


def test_the_declared_port_is_the_one_the_chart_routes_to() -> None:
    """A Service targeting a port nothing listens on fails only once deployed."""
    expected = CHART_VALUES["api"]["containerPort"]
    assert f"INFEROPS_BIND_PORT={expected}" in DOCKERFILE, expected
    assert f"EXPOSE {expected}" in DOCKERFILE, expected


def test_the_image_binds_an_address_a_service_can_reach() -> None:
    """Stated in the image, and required by the entrypoint rather than defaulted."""
    assert "INFEROPS_BIND_HOST=0.0.0.0" in DOCKERFILE


# --------------------------------------------------------------------------
# The image contains the application and nothing else
# --------------------------------------------------------------------------


COPIED_PATHS = [
    line.split()[1] for line in DOCKERFILE.splitlines() if line.startswith("COPY ")
]


def test_the_image_copies_only_the_application_and_its_carrier() -> None:
    """A serving container has no business holding the host's tooling."""
    assert COPIED_PATHS == [
        "src/inferops",
        "tools/__init__.py",
        "tools/api_carrier",
        "tools/api_container",
    ], COPIED_PATHS


@pytest.mark.parametrize(
    "package",
    (
        "model_acquisition",
        "runtime_packaging",
        "runtime_configuration",
        "kubernetes_certification",
        "serving_baseline",
        "local_composition",
    ),
)
def test_no_host_tooling_package_is_copied_into_the_image(package: str) -> None:
    """Asserted against the COPY directives, not the file.

    The prose above them names `tools/local_composition` while explaining why the
    carrier left it, and a substring search over the whole Dockerfile would read
    that explanation as a violation of the thing it explains.
    """
    assert not any(path.startswith(f"tools/{package}") for path in COPIED_PATHS), (
        package
    )


@pytest.mark.parametrize("excluded", (".cache/", ".venv/", ".kube/", "**/*.tfstate"))
def test_the_build_context_excludes_host_state(excluded: str) -> None:
    """Chiefly the model cache: 1.71 GiB streamed to the daemon for nothing.

    It is a boundary as much as an optimisation. Weights, virtual environments,
    kubeconfigs and Terraform state have no business being readable by a build,
    and the surest way for one to reach an image is for it to be in the context
    when somebody widens a COPY later.
    """
    assert excluded in DOCKERIGNORE, excluded


def test_the_carrier_can_be_imported_without_the_host_tooling() -> None:
    """The property that justified moving the carrier out of `local_composition`.

    Asserted by importing it in a fresh interpreter and reading `sys.modules`,
    rather than by reading the import statements -- an `__init__` three packages
    away can undo this without any line here changing.
    """
    probe = (
        "import json, sys; import tools.api_carrier; "
        "print(json.dumps(sorted(n for n in sys.modules if n.startswith('tools'))))"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(["src", str(REPO_ROOT)])
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    loaded = set(json.loads(result.stdout))
    assert loaded == {"tools", "tools.api_carrier", "tools.api_carrier.http_server"}, (
        loaded
    )


def test_the_old_carrier_path_still_resolves() -> None:
    """The proof records for V1-S2-003, V1-S2-005 and V1-S2-008 name it.

    A record describing a file that no longer exists is a record a reader cannot
    check, and those are history rather than documentation to be edited. So the
    path keeps working and the implementation lives elsewhere.
    """
    assert SHIM_PATH.is_file()
    assert "from tools.api_carrier.http_server import" in SHIM_PATH.read_text(
        encoding="utf-8"
    )


# --------------------------------------------------------------------------
# The entrypoint states its address rather than defaulting it
# --------------------------------------------------------------------------


BASE_ENVIRONMENT = {
    "INFEROPS_SERVING_ADAPTER": "mock",
    "INFEROPS_REQUEST_TIMEOUT_MS": "120000",
    "INFEROPS_MAX_OUTPUT_TOKENS": "128",
    "INFEROPS_DRAIN_TIMEOUT_MS": "15000",
    "INFEROPS_DEPLOYMENT_ENVIRONMENT": "dev",
    "INFEROPS_CAPABILITY_ID": "inferops-mock-serving",
    "INFEROPS_RELEASE_ID": "inferops",
    "INFEROPS_SERVICE_VERSION": "",
    "INFEROPS_WORKLOAD_ID": "support-assistant-mock",
    "INFEROPS_WORKLOAD_VERSION": "0.1.0",
    "INFEROPS_OWNER_ID": "team-platform-demo",
    "INFEROPS_MODEL_IDENTIFIER": "mock-fixed-fixture",
}


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    (
        pytest.param({}, "INFEROPS_BIND_HOST", id="no-bind-host"),
        pytest.param(
            {"INFEROPS_BIND_HOST": "0.0.0.0"}, "INFEROPS_BIND_PORT", id="no-bind-port"
        ),
        pytest.param(
            {"INFEROPS_BIND_HOST": "0.0.0.0", "INFEROPS_BIND_PORT": "80"},
            "privileged",
            id="privileged-port",
        ),
        pytest.param(
            {"INFEROPS_BIND_HOST": "0.0.0.0", "INFEROPS_BIND_PORT": "not-a-port"},
            "whole number",
            id="port-is-not-a-number",
        ),
        pytest.param(
            {"INFEROPS_BIND_HOST": "0.0.0.0", "INFEROPS_BIND_PORT": "99999"},
            "1-65535",
            id="port-out-of-range",
        ),
    ),
)
def test_an_unstated_or_impossible_address_refuses(
    overrides: dict[str, str], expected_fragment: str
) -> None:
    """It refuses rather than guessing, and the refusal names the variable.

    A default here would be the quiet way the host composition's loopback rule
    stops meaning anything: the two would differ by a value nobody had to state.
    """
    result = run_entrypoint({**BASE_ENVIRONMENT, **overrides})
    assert result.returncode == 2, result.stdout + result.stderr
    assert expected_fragment in result.stderr, result.stderr


def test_a_refusal_never_prints_the_value_it_refused() -> None:
    """An endpoint is exactly where a credential arrives in somebody's deployment."""
    secret = "super-secret-host-value"
    result = run_entrypoint(
        {**BASE_ENVIRONMENT, "INFEROPS_BIND_HOST": " ", "INFEROPS_BIND_PORT": secret}
    )
    assert result.returncode == 2
    assert secret not in result.stdout + result.stderr


def test_an_unselected_adapter_refuses_as_configuration() -> None:
    """The selection has no default and no fallback; the exit status says so.

    Distinct from a shutdown failure, so that a crash loop is diagnosable from
    the exit status without reading the log.
    """
    environment = {k: v for k, v in BASE_ENVIRONMENT.items()}
    environment.pop("INFEROPS_SERVING_ADAPTER")
    result = run_entrypoint(
        {
            **environment,
            "INFEROPS_BIND_HOST": "127.0.0.1",
            "INFEROPS_BIND_PORT": "18131",
        }
    )
    assert result.returncode == 2, result.stdout + result.stderr


# --------------------------------------------------------------------------
# No unverified digest replaces the old one
# --------------------------------------------------------------------------


def test_the_committed_real_values_still_carry_the_labelled_placeholder() -> None:
    """The correction is a digest read back from a built image, not a new guess.

    The review's instruction was explicit: do not replace the fake digest with
    another unverified digest. An image built on a host and loaded into a node
    has no registry digest to commit, so the value belongs in a generated overlay
    that version control ignores. This test is what a future paste has to delete.
    """
    placeholder = "sha256:" + hashlib.sha256(PLACEHOLDER_SOURCE.encode()).hexdigest()
    assert REAL_VALUES["api"]["image"]["digest"] == placeholder
    assert REAL_VALUES["api"]["image"]["pullPolicy"] == "Never"


def test_the_image_script_derives_the_digest_rather_than_declaring_one() -> None:
    assert "inferops::api_image_digest" in IMAGE_SCRIPT
    assert "docker image inspect" in IMAGE_SCRIPT
    # No digest literal is committed in the script either.
    assert not DIGEST.search(IMAGE_SCRIPT), "the script hard-codes a digest"


def test_the_image_script_establishes_cluster_identity_before_it_loads() -> None:
    """A load names a cluster, and would happily name somebody else's.

    V1-S3-010-PR2 replaced the kind-pinned inferops::assert_target_cluster here
    with the provider-aware inferops::resolve_target. V1-S3-011 then established
    Docker Desktop's own image-preparation mechanism, so the capability check
    that used to refuse every provider but kind moved inside
    inferops::target_load_image, which dispatches on the verified provider's
    mechanism and refuses one it does not implement. What this test asserts is
    unchanged: nothing reaches a node before a target is verified.
    """
    identity = _called(IMAGE_SCRIPT, "inferops::resolve_target")
    load = _called(IMAGE_SCRIPT, "inferops::target_load_image")
    assert identity < load, "the load happens before the target is established"


def _called(script: str, function: str) -> int:
    """Where `function` is actually invoked, not where prose first mentions it.

    The comments here name the functions they explain, and a plain `.index()`
    would find the comment rather than the call -- which puts the two in the
    wrong order and fails a script that is correct.
    """
    match = re.search(rf"^\s*{re.escape(function)}\b", script, re.M)
    assert match is not None, f"{function} is never called"
    return match.start()


def test_the_image_script_names_no_provider_mechanism_itself() -> None:
    """Which mechanism puts an image into a node is the verified target's
    property, not this script's. A `kind load` spelled here would be a second
    place that has to learn about every provider."""
    commands = "\n".join(
        line for line in IMAGE_SCRIPT.splitlines() if not line.lstrip().startswith("#")
    )

    assert "kind load" not in commands
    assert "ctr --namespace" not in commands


def test_the_image_script_pushes_to_no_registry() -> None:
    """Publication is not required, and this workflow is the reason why."""
    assert "docker push" not in IMAGE_SCRIPT


# --------------------------------------------------------------------------
# Shutdown, which is the part a container gets wrong
# --------------------------------------------------------------------------

# Windows cannot deliver a POSIX signal to a child process -- a `kill` there
# terminates it rather than raising SIGTERM in it -- so the handler under test
# would never run and the assertion would be about the harness. It skips loudly
# instead of passing for the wrong reason. The same property was observed
# directly on the built image, where `docker stop -t 30` returned exit 0 with
# `drained=true` inside 1.78 seconds against a 30 second grace period.
posix_signals_only = pytest.mark.skipif(
    os.name == "nt",
    reason="Windows delivers no POSIX SIGTERM to a child; the drain path is skipped, loudly",
)

SERVING_ENVIRONMENT = {
    **BASE_ENVIRONMENT,
    "INFEROPS_BIND_HOST": "127.0.0.1",
    "INFEROPS_BIND_PORT": "18137",
    "INFEROPS_POD_NAME": "entrypoint-drain-test",
}


@posix_signals_only
def test_a_terminated_server_drains_and_exits_clean() -> None:
    """SIGTERM must produce a clean drain, not a process killed by its own signal.

    A container that is `SIGKILL`ed after its whole grace period on every rollout
    is the normal outcome of an entrypoint that installs no handler, and it is
    invisible until somebody measures a rollout.
    """
    import signal as signal_module
    import time

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(["src", str(REPO_ROOT)])
    env.update(SERVING_ENVIRONMENT)
    process = subprocess.Popen(
        [sys.executable, "-m", "tools.api_container"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.2)
            break
        time.sleep(3)
        assert process.poll() is None, "the server exited before it was signalled"
        process.send_signal(signal_module.SIGTERM)
        _, stderr = process.communicate(timeout=60)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=30)
    assert process.returncode == 0, stderr
    assert "shutdown.complete drained=true" in stderr, stderr


def test_a_startup_failure_has_its_own_exit_status() -> None:
    """Distinct from a configuration refusal and from a failed drain.

    A crash-looping pod should be diagnosable from `kubectl get pod` without
    reading a traceback out of the log, and a carrier that cannot open its socket
    is a different problem from a deployment that named no adapter.
    """
    from tools.api_container.__main__ import (
        EXIT_CONFIGURATION,
        EXIT_OK,
        EXIT_SHUTDOWN,
        EXIT_STARTUP,
    )

    assert len({EXIT_OK, EXIT_CONFIGURATION, EXIT_SHUTDOWN, EXIT_STARTUP}) == 4


def test_a_signal_arriving_before_the_serving_thread_is_not_swallowed() -> None:
    """`request_stop` does nothing until the serving thread is alive.

    Between `start()` returning and that thread coming up there is a window where
    acting on the signal alone would do nothing and the process would then block
    in `join()` with nothing left to wake it -- deaf until `SIGKILL`, which is the
    failure the module exists to prevent. So the handler records as well as acts,
    the flag is re-read once the thread exists, and repeat deliveries are not
    discarded by the record of the one that did nothing.
    """
    body = (REPO_ROOT / "tools" / "api_container" / "__main__.py").read_text(
        encoding="utf-8"
    )
    assert "if stopping.is_set():\n            # A signal landed before" in body
    assert "if not stopping.is_set():" in body, (
        "the handler returns early on a repeat signal and would swallow it"
    )


# --------------------------------------------------------------------------
# The digest is the one Kubernetes resolves by
# --------------------------------------------------------------------------


def test_the_digest_is_the_manifest_digest_and_not_the_config_digest() -> None:
    """`.Id` is a different hash on a graphdriver-backed daemon.

    A `repository@digest` reference resolves by the manifest digest. Handing the
    chart the config digest builds a reference that is well formed, unresolvable,
    and fails at schedule time as `ErrImageNeverPull` -- long after the build
    looked successful.
    """
    assert ".RepoDigests" in IMAGE_SCRIPT
    assert "{{.Id}}" not in IMAGE_SCRIPT


def test_the_load_resolves_the_reference_the_chart_will_actually_use() -> None:
    """A successful load is not a resolvable reference, and only one of them matters.

    The check itself now lives in inferops::target_load_image, because it is the
    same claim for both providers -- not "the load command exited zero" but "the
    reference the chart will ask containerd for resolves inside the node". This
    asserts the script hands it the repository and the digest that reference is
    built from, and that lib.sh makes the claim after the bytes are in.
    """
    lib = (REPO_ROOT / "scripts/environment/lib.sh").read_text(encoding="utf-8")

    assert "crictl inspecti" in lib
    assert 'inferops::target_load_image "${INFEROPS_API_IMAGE_REF}"' in IMAGE_SCRIPT
    assert '"${INFEROPS_API_IMAGE_REPOSITORY}" "${digest}"' in IMAGE_SCRIPT

    body = lib[lib.index("inferops::target_load_image() {") :]
    for mechanism in ("kind load docker-image", "ctr --namespace=k8s.io images import"):
        assert body.index(mechanism) < body.index("crictl inspecti"), (
            f"{mechanism} is not checked after it runs"
        )


@pytest.mark.parametrize(
    "pattern",
    ("tools/api_carrier/**/__pycache__/", "tools/api_container/**/*.pyc"),
)
def test_bytecode_is_excluded_after_the_directory_re_include(pattern: str) -> None:
    """Docker applies ignore rules in order, and the last match wins.

    `!tools/api_carrier/` re-includes the whole subtree, which overrides the
    earlier `**/__pycache__/` rule for anything inside it. Without restating the
    exclusion afterwards the image ships whatever bytecode the building machine
    happened to have lying there -- so two people building the same commit get
    different image content, and therefore a different digest. That digest is the
    thing this build path exists to make trustworthy.
    """
    assert pattern in DOCKERIGNORE, pattern
    assert DOCKERIGNORE.index("!tools/api_carrier/") < DOCKERIGNORE.index(pattern)
