"""The Kubernetes troubleshooting and cleanup guide, held to what it describes.

A troubleshooting page is read by somebody who has already run out of patience,
and every command on it is trusted rather than checked. Drift here is more
expensive than drift in most documents: a page naming a subcommand that no longer
exists, a port the chart no longer publishes, a probe the values file no longer
renders, or a cleanup script that was renamed sends the reader further from the
fault — and one of the operations it documents deletes a namespace.

So the page is compared against the things it quotes rather than proofread. Nine
properties, each corresponding to a way this particular document rots:

1. **A command that does not exist.** Every ``python -m tools.<module>`` it
   prints must name a module in this repository, and either a subcommand that
   module's parser accepts or a path that is really there.
2. **A script that was renamed.** Every ``scripts/environment/*.sh`` it names must
   exist and be the file that carries the behaviour described.
3. **A target that is not the project's.** Every cluster name, context, namespace,
   release name, kubeconfig path, and pin the page publishes is compared against
   ``scripts/environment/lib.sh``, which is the one place they are defined.
4. **A number whose owner disagrees.** Ports, probe periods and thresholds,
   progress deadlines, resource requests and limits, the claim's name and size,
   the artifact's byte count, and its in-claim path are each compared against the
   record that owns them — the committed render, the values file, the Terraform
   variables, the model source record — never against a second copy.
5. **An exit code the tools do not return.** The vocabulary table is compared
   against the constants both Kubernetes tools define.
6. **A measurement the evidence does not hold.** Every model-load figure quoted
   must appear in the proof record the page links it to.
7. **A link that goes nowhere.** Every relative Markdown target outside a fenced
   block resolves from this document's own directory.
8. **An unscoped or credential-bearing command.** No fenced ``kubectl`` or
   ``helm`` sample may rely on an ambient context, and no fenced block may carry a
   token, header, password, or alternate-server flag.
9. **A claim the page is not entitled to make.** It must keep saying that the
   release has never been installed, that the network policy is not enforced on
   this plugin, and that the executed evidence is one Windows host's.

What this suite establishes is that the document describes this repository. It
establishes nothing about whether following it repairs anything: no cluster has
installed the release, and every recovery below the cluster layer is described
rather than executed.

Every check reads files from this repository and nothing else. No network, no
cluster, no engine, no clock, no randomness.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
ENVIRONMENT_DIR = DOCS_DIR / "environment"
DOCUMENT_PATH = ENVIRONMENT_DIR / "kubernetes-troubleshooting.md"

LIB_PATH = REPO_ROOT / "scripts" / "environment" / "lib.sh"
CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
VALUES_PATH = CHART_DIR / "values.yaml"
RENDERED_REAL_PATH = CHART_DIR / "ci" / "rendered" / "real.expected.yaml"
MODEL_SOURCE_PATH = DOCS_DIR / "serving" / "model-source.v1.json"
TERRAFORM_VARIABLES_PATH = (
    REPO_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "platform-prerequisites"
    / "variables.tf"
)

DOCUMENT = DOCUMENT_PATH.read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    """Everything outside a fenced code block, joined by newlines."""
    kept: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


def _fenced_blocks(text: str) -> list[str]:
    """Every fenced code block's body, one string per block."""
    blocks: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
            continue
        if current is not None:
            current.append(line)
    return blocks


PROSE = _strip_fences(DOCUMENT)
BLOCKS = _fenced_blocks(DOCUMENT)
FENCED = "\n".join(BLOCKS)

#: The prose as one line, without emphasis or code markers. A sentence this
#: document is required to keep is a sentence rather than a line: reflowing a
#: paragraph must not fail a check, and emphasising or code-quoting a phrase
#: inside it must not evade one.
FLOWED = " ".join(PROSE.replace("**", "").replace("`", "").split())


def _grouped(value: int) -> str:
    """A whole number the way this repository writes one: 1,834,426,016."""
    return f"{value:,}"


def _lib_constant(name: str) -> str:
    """One ``readonly NAME="value"`` out of lib.sh.

    Read as text rather than by sourcing the file, because sourcing it sets
    ``errexit`` in the caller's shell and because a test that runs the scripts is
    a different test from one that reads them.
    """
    source = LIB_PATH.read_text(encoding="utf-8")
    match = re.search(
        rf'^readonly {re.escape(name)}="(?P<value>[^"]*)"', source, re.MULTILINE
    )
    assert match is not None, f"{name} is not defined in scripts/environment/lib.sh"
    value = match.group("value")
    #: One constant is derived from another -- the context name is the cluster
    #: name with kind's fixed prefix -- so the reference is expanded rather than
    #: compared literally. Expanding it here keeps the derivation in lib.sh,
    #: where it belongs, instead of copying the resolved string into this suite.
    while reference := re.search(r"\$\{(?P<name>INFEROPS_[A-Z_]+)\}", value):
        value = value.replace(
            reference.group(0), _lib_constant(reference.group("name"))
        )
    return value


VALUES: dict[str, Any] = yaml.safe_load(VALUES_PATH.read_text(encoding="utf-8"))
MODEL_SOURCE: dict[str, Any] = json.loads(MODEL_SOURCE_PATH.read_text(encoding="utf-8"))
RENDERED_REAL: list[dict[str, Any]] = [
    document
    for document in yaml.safe_load_all(RENDERED_REAL_PATH.read_text(encoding="utf-8"))
    if isinstance(document, dict)
]


def _rendered(kind: str, name: str) -> dict[str, Any]:
    for document in RENDERED_REAL:
        if (
            document.get("kind") == kind
            and document.get("metadata", {}).get("name") == name
        ):
            return document
    raise AssertionError(f"{kind}/{name} is not in the committed real render")


def _container_by_kind_and_name(kind: str, name: str) -> str:
    """Every init-container command line in one rendered workload, as text.

    The refusals this page quotes are echoed by a shell script Helm renders into
    the pod template, so they are read out of the render rather than retyped.
    """
    spec = _rendered(kind, name)["spec"]["template"]["spec"]
    joined: list[str] = []
    for container in spec.get("initContainers", []):
        joined.extend(str(part) for part in container.get("command", []))
    return "\n".join(joined)


def _container(deployment: dict[str, Any], name: str) -> dict[str, Any]:
    spec = deployment["spec"]["template"]["spec"]
    for container in spec["containers"]:
        if container["name"] == name:
            return container
    raise AssertionError(f"container {name} is not in {deployment['metadata']['name']}")


# --------------------------------------------------------------------------
# 1. The commands the page prints
# --------------------------------------------------------------------------

#: ``uv run --locked python -m tools.workload_policy charts/...`` and the bare
#: ``python -m tools.x y`` form. The first token after the module that is not a
#: flag is either a subcommand or a path, and which one it is depends on the
#: tool; both shapes are checked below.
TOOL_COMMAND = re.compile(
    r"python -m tools\.(?P<module>[a-z_]+)(?P<tail>(?: +[^\s`\"']+)*)"
)

#: Flags that would mean this workflow accepts a credential or a redirect.
#: Nothing on this page defines one, and a sample that appeared to would teach a
#: reader to look for a secret this repository does not hold. ``--kubeconfig``
#: and ``--context`` are deliberately absent from this list: they are the
#: opposite of a redirect, and requiring them is the next check.
FORBIDDEN_FLAGS = (
    "--token",
    "--password",
    "--header",
    "--auth",
    "--api-key",
    "--apikey",
    "--bearer",
    "--credential",
    "--server",
    "--insecure-skip-tls-verify",
    "--force",
)


def documented_tool_commands() -> set[tuple[str, str]]:
    """Every ``(module, first non-flag argument)`` pair the document prints."""
    found: set[tuple[str, str]] = set()
    for match in TOOL_COMMAND.finditer(DOCUMENT):
        module = match.group("module")
        arguments = match.group("tail").split()
        argument = next((word for word in arguments if not word.startswith("-")), "")
        found.add((module, argument))
    return found


def accepted_subcommands(module: str) -> set[str]:
    """The subcommands a tool's ``__main__`` accepts, read from its source.

    Read from the argument parser rather than executed, because these modules
    read committed JSON while building one. The two shapes this repository uses
    are a ``choices=(...)`` tuple on a positional argument and a series of
    ``add_parser("name", ...)`` calls; both are collected. A tool that declares
    neither takes a path, and returns the empty set.
    """
    source = (REPO_ROOT / "tools" / module / "__main__.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename=f"tools/{module}/__main__.py")
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        attribute = node.func
        if (
            isinstance(attribute, ast.Attribute)
            and attribute.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            names.add(str(node.args[0].value))
        for keyword in node.keywords:
            if keyword.arg != "choices":
                continue
            if isinstance(keyword.value, ast.Tuple | ast.List):
                names.update(
                    str(element.value)
                    for element in keyword.value.elts
                    if isinstance(element, ast.Constant)
                )
    return names


DOCUMENTED_COMMANDS = sorted(documented_tool_commands())


@pytest.mark.parametrize(
    "command", DOCUMENTED_COMMANDS, ids=lambda pair: f"{pair[0]}:{pair[1] or '<none>'}"
)
def test_every_documented_command_names_a_module_that_exists(
    command: tuple[str, str],
) -> None:
    module, _ = command
    assert (REPO_ROOT / "tools" / module / "__main__.py").is_file(), module


@pytest.mark.parametrize(
    "command", DOCUMENTED_COMMANDS, ids=lambda pair: f"{pair[0]}:{pair[1] or '<none>'}"
)
def test_every_documented_command_names_a_subcommand_or_a_path_that_exists(
    command: tuple[str, str],
) -> None:
    """The check that catches a renamed subcommand or a moved render directory."""
    module, argument = command
    accepted = accepted_subcommands(module)
    if accepted:
        assert argument in accepted, {
            "module": module,
            "documented": argument,
            "accepted": sorted(accepted),
        }
        return
    assert argument, {
        "module": module,
        "problem": "this tool takes a path and the page printed none",
    }
    assert (REPO_ROOT / argument).exists(), {
        "module": module,
        "documented path": argument,
    }


def test_the_page_reaches_every_offline_check_a_reader_may_need() -> None:
    """A guide that documents two of the four offline checks sends readers away."""
    reached = {module for module, _ in DOCUMENTED_COMMANDS}
    assert {
        "workload_policy",
        "telemetry_collection",
        "helm_upgrade_rollback",
        "model_acquisition",
    } <= reached, sorted(reached)


def test_every_repository_tool_sample_runs_from_the_locked_environment() -> None:
    """``--locked`` is not decoration, and a sample without it is a different run."""
    for block in BLOCKS:
        for line in block.splitlines():
            if "python -m tools." not in line:
                continue
            assert line.lstrip().startswith("uv run --locked"), line


# --------------------------------------------------------------------------
# 2. The scripts the page names
# --------------------------------------------------------------------------

SCRIPT_REFERENCE = re.compile(r"scripts/environment/(?P<name>[a-z0-9-]+\.sh)")
DOCUMENTED_SCRIPTS = sorted(
    {m.group("name") for m in SCRIPT_REFERENCE.finditer(DOCUMENT)}
)


@pytest.mark.parametrize("name", DOCUMENTED_SCRIPTS)
def test_every_documented_script_exists(name: str) -> None:
    assert (REPO_ROOT / "scripts" / "environment" / name).is_file(), name


def test_the_page_names_every_script_a_cleanup_decision_depends_on() -> None:
    """The four teardown radii are four scripts. Omitting one hides an option."""
    assert {
        "cluster-down.sh",
        "verify-clean.sh",
        "terraform-prerequisites.sh",
        "cluster-verify.sh",
        "preflight.sh",
    } <= set(DOCUMENTED_SCRIPTS), DOCUMENTED_SCRIPTS


def test_the_destroy_sample_carries_the_confirmation_the_wrapper_requires() -> None:
    """A destroy printed without ``--confirm`` is a command that would be refused."""
    for block in BLOCKS:
        for line in block.splitlines():
            if "terraform-prerequisites.sh destroy" not in line:
                continue
            assert "--confirm" in line, line


# --------------------------------------------------------------------------
# 3. The targets, read out of lib.sh
# --------------------------------------------------------------------------

LIB_CONSTANTS_THE_PAGE_PUBLISHES = (
    "INFEROPS_CLUSTER_NAME",
    "INFEROPS_KUBE_CONTEXT",
    "INFEROPS_KUBECONFIG_REL",
    "INFEROPS_NAMESPACE",
    "INFEROPS_RELEASE_NAME",
    "INFEROPS_RELEASE_NAMESPACE",
    "INFEROPS_CHART_PATH",
    "INFEROPS_PART_OF_SELECTOR",
    "INFEROPS_NODE_IMAGE_TAG",
    "INFEROPS_NODE_IMAGE_DIGEST",
    "INFEROPS_KIND_VERSION",
)


@pytest.mark.parametrize("name", LIB_CONSTANTS_THE_PAGE_PUBLISHES)
def test_every_target_the_page_publishes_is_the_one_lib_defines(name: str) -> None:
    value = _lib_constant(name)
    assert value in DOCUMENT, {"constant": name, "value": value}


def test_the_release_selector_is_the_one_a_residue_check_asks_about() -> None:
    """The label a scoped delete uses is the label the page tells you to filter on."""
    assert f"app.kubernetes.io/instance={_lib_constant('INFEROPS_RELEASE_NAME')}" in (
        DOCUMENT
    )


@pytest.mark.parametrize(
    "name",
    (
        "INFEROPS_MIN_ENGINE_MEM_BYTES",
        "INFEROPS_MIN_ENGINE_CPUS",
        "INFEROPS_MIN_FREE_DISK_BYTES",
    ),
)
def test_the_host_floor_the_page_quotes_is_the_enforced_one(name: str) -> None:
    """The page contrasts the host floor with the release's request. Both must be real."""
    assert _grouped(int(_lib_constant(name))) in DOCUMENT, name


def test_the_page_does_not_present_the_host_floor_as_a_release_requirement() -> None:
    """They size different things, and conflating them is the mistake this prevents."""
    assert "sizes the *cluster*, not the release" in DOCUMENT


# --------------------------------------------------------------------------
# 4. The numbers, read out of the records that own them
# --------------------------------------------------------------------------


def test_the_service_ports_are_the_ones_the_render_publishes() -> None:
    api = _rendered("Service", "inferops-inferops-llm")
    runtime = _rendered("Service", "inferops-inferops-llm-runtime")
    assert str(api["spec"]["ports"][0]["port"]) in DOCUMENT
    assert str(runtime["spec"]["ports"][0]["port"]) in DOCUMENT
    assert api["spec"]["type"] == "ClusterIP"
    assert runtime["spec"]["type"] == "ClusterIP"
    assert "Both Services are `ClusterIP`" in DOCUMENT


def test_the_service_names_are_the_ones_the_render_carries() -> None:
    """A page naming a Service that is not there sends the reader to an empty query."""
    for name in ("inferops-inferops-llm", "inferops-inferops-llm-runtime"):
        _rendered("Service", name)
        assert name in DOCUMENT, name


@pytest.mark.parametrize(
    ("deployment", "container"),
    (
        ("inferops-inferops-llm", "api"),
        ("inferops-inferops-llm-runtime", "runtime"),
    ),
)
def test_every_probe_the_page_tabulates_is_the_rendered_one(
    deployment: str, container: str
) -> None:
    rendered = _container(_rendered("Deployment", deployment), container)
    for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
        specification = rendered[probe]
        assert str(specification["periodSeconds"]) in DOCUMENT, (probe, "period")
        assert str(specification["failureThreshold"]) in DOCUMENT, (probe, "threshold")
        if "httpGet" in specification:
            assert specification["httpGet"]["path"] in DOCUMENT, (probe, "path")


def test_the_runtime_liveness_probe_really_is_the_only_tcp_one() -> None:
    """The page makes this the load-bearing distinction. It has to be true."""
    runtime = _container(
        _rendered("Deployment", "inferops-inferops-llm-runtime"), "runtime"
    )
    api = _container(_rendered("Deployment", "inferops-inferops-llm"), "api")
    assert "tcpSocket" in runtime["livenessProbe"]
    assert "httpGet" in runtime["startupProbe"]
    assert "httpGet" in runtime["readinessProbe"]
    assert all(
        "tcpSocket" not in api[probe]
        for probe in ("startupProbe", "readinessProbe", "livenessProbe")
    )
    assert "The runtime's liveness is a TCP connect and never an HTTP GET" in DOCUMENT


def test_the_two_load_budgets_are_the_values_file_s_and_are_not_confused() -> None:
    adapter_budget = VALUES["runtime"]["startupBudgetMs"]
    kubelet_budget = VALUES["runtime"]["probes"]["startup"]["budgetMs"]
    assert kubelet_budget > adapter_budget
    assert _grouped(adapter_budget) in DOCUMENT
    assert _grouped(kubelet_budget) in DOCUMENT
    assert _grouped(VALUES["api"]["probes"]["startup"]["budgetMs"]) in DOCUMENT


@pytest.mark.parametrize("workload", ("api", "runtime"))
def test_the_progress_deadlines_are_the_values_file_s(workload: str) -> None:
    deadline = VALUES[workload]["lifecycle"]["progressDeadlineSeconds"]
    assert str(deadline) in DOCUMENT, {"workload": workload, "deadline": deadline}


@pytest.mark.parametrize(
    ("path", "container"),
    (
        (("runtime", "resources"), "runtime"),
        (("api", "resources"), "api"),
        (("model", "integrity", "resources"), "verify-model"),
    ),
)
def test_every_resource_figure_the_page_tabulates_is_the_values_file_s(
    path: tuple[str, ...], container: str
) -> None:
    node: Any = VALUES
    for key in path:
        node = node[key]
    for side in ("requests", "limits"):
        for value in node[side].values():
            assert f"`{value}`" in DOCUMENT, {
                "container": container,
                side: value,
            }


def test_the_claim_name_and_size_are_terraform_s_defaults() -> None:
    variables = TERRAFORM_VARIABLES_PATH.read_text(encoding="utf-8")
    assert 'default     = "inferops-model-cache"' in variables
    assert 'default     = "4Gi"' in variables
    assert "inferops-model-cache" in DOCUMENT
    assert "`4Gi`" in DOCUMENT
    assert "`2Gi`" in DOCUMENT


def test_the_artifact_byte_count_and_in_claim_path_are_the_model_record_s() -> None:
    assert _grouped(MODEL_SOURCE["expectedSizeBytes"]) in DOCUMENT
    assert MODEL_SOURCE["cache"]["artifactRelativePath"] in DOCUMENT
    assert MODEL_SOURCE["revision"] in DOCUMENT


def test_the_cache_root_the_cleanup_refuses_to_leave_is_the_record_s() -> None:
    assert MODEL_SOURCE["cache"]["path"] in DOCUMENT


def test_the_forward_port_is_the_certification_script_s_default() -> None:
    script = (
        REPO_ROOT / "scripts" / "environment" / "kubernetes-certification.sh"
    ).read_text(encoding="utf-8")
    match = re.search(
        r'^readonly INFEROPS_DEFAULT_FORWARD_PORT="(?P<port>\d+)"', script, re.MULTILINE
    )
    assert match is not None
    assert match.group("port") in DOCUMENT


def test_every_artifact_directory_the_page_lists_is_one_a_script_writes() -> None:
    """A page pointing at a directory nothing creates sends the reader nowhere."""
    documented = set(re.findall(r"\.artifacts/([a-z-]+)/", DOCUMENT))
    written: set[str] = set()
    for script in (REPO_ROOT / "scripts" / "environment").glob("*.sh"):
        source = script.read_text(encoding="utf-8")
        written.update(re.findall(r'INFEROPS_ARTIFACT_DIR\}/([a-z-]+)"', source))
    written.add("terraform")
    assert documented <= written, sorted(documented - written)


# --------------------------------------------------------------------------
# 5. The exit codes
# --------------------------------------------------------------------------

EXIT_CODE_ROW = re.compile(r"^\| `(?P<code>\d+)` \| (?P<meaning>[^|]+)\|", re.MULTILINE)


def _tool_exit_codes(module: str) -> dict[str, int]:
    source = (REPO_ROOT / "tools" / module / "__main__.py").read_text(encoding="utf-8")
    return {
        name: int(value)
        for name, value in re.findall(r"^(EXIT_[A-Z]+) = (\d+)$", source, re.MULTILINE)
    }


def test_the_exit_vocabulary_is_the_one_both_tools_return() -> None:
    documented = {
        int(match.group("code")) for match in EXIT_CODE_ROW.finditer(DOCUMENT)
    }
    rollback = _tool_exit_codes("helm_upgrade_rollback")
    certification = _tool_exit_codes("kubernetes_certification")
    assert set(rollback.values()) <= documented, sorted(rollback.items())
    assert set(certification.values()) <= documented, sorted(certification.items())
    assert 130 in documented, "Ctrl-C is a documented outcome in both tools"
    assert documented <= set(rollback.values()) | {130}, sorted(documented)


def test_inconclusive_is_attributed_to_the_only_tool_that_returns_it() -> None:
    """Five is not in the certification tool, and a page implying it is misleads."""
    assert "EXIT_INCONCLUSIVE" in (
        REPO_ROOT / "tools" / "helm_upgrade_rollback" / "__main__.py"
    ).read_text(encoding="utf-8")
    assert "EXIT_INCONCLUSIVE" not in (
        REPO_ROOT / "tools" / "kubernetes_certification" / "__main__.py"
    ).read_text(encoding="utf-8")
    assert "`tools.helm_upgrade_rollback` only" in DOCUMENT


# --------------------------------------------------------------------------
# 6. The measurements
# --------------------------------------------------------------------------

MEASUREMENTS = (
    ("358,735 ms", "v1-s2-005-baseline-raw-results-first-attempt.md"),
    ("269,079 ms", "v1-s2-005-baseline-raw-results.md"),
    ("133,515", "v1-s2-007-pr1-cold-warm-start.md"),
    ("215,672", "v1-s2-007-pr1-cold-warm-start.md"),
)


@pytest.mark.parametrize(("figure", "record"), MEASUREMENTS)
def test_every_quoted_measurement_is_in_the_record_it_is_attributed_to(
    figure: str, record: str
) -> None:
    if figure not in DOCUMENT:
        pytest.skip(f"{figure} is no longer quoted")
    text = (DOCS_DIR / "proof" / "serving" / record).read_text(encoding="utf-8")
    assert figure.replace(" ms", "") in text, {"figure": figure, "record": record}


def test_the_network_policy_answer_is_the_one_the_experiment_recorded() -> None:
    """The page tells the reader not to investigate the policy. That has to be why.

    And it has to carry the qualifier the record carries. The experiment answered
    for one plugin build; independent review found the page stating the
    conclusion flatly at the point where it tells an operator to stop looking,
    which is the one place a missing caveat costs something.
    """
    record = (
        DOCS_DIR / "proof" / "security" / "v1-s3-004-pr1-network-policy-enforcement.md"
    ).read_text(encoding="utf-8")
    assert "The answer is no." in record
    assert "in the build tested" in record
    assert "kindnetd" in record
    assert "none of them was enforced in the build tested" in FLOWED
    assert "2026-09-06" in DOCUMENT and "2026-09-06" in record


def test_the_chart_still_renders_the_policies_the_page_calls_inert() -> None:
    policies = [d for d in RENDERED_REAL if d.get("kind") == "NetworkPolicy"]
    assert len(policies) == 5, [d["metadata"]["name"] for d in policies]
    assert "The chart renders five policy objects" in FLOWED


# --------------------------------------------------------------------------
# 7. Links
# --------------------------------------------------------------------------

MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\((?P<target>[^)\s]+)\)")


def relative_link_targets() -> list[str]:
    targets: list[str] = []
    for match in MARKDOWN_LINK.finditer(PROSE):
        target = match.group("target")
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        targets.append(target)
    return sorted(set(targets))


RELATIVE_LINKS = relative_link_targets()


def test_the_page_links_out_at_all() -> None:
    assert RELATIVE_LINKS


@pytest.mark.parametrize("target", RELATIVE_LINKS)
def test_every_relative_link_resolves(target: str) -> None:
    path, _, _ = target.partition("#")
    assert (ENVIRONMENT_DIR / path).resolve().exists(), target


def test_the_validation_record_this_page_cites_exists() -> None:
    """The page names its own evidence. A record that is not there is a claim."""
    assert (
        DOCS_DIR / "proof" / "environment" / "v1-s3-009-pr1-validation.md"
    ).is_file()


def test_the_page_names_the_suite_that_checks_it() -> None:
    assert "tests/architecture/test_kubernetes_troubleshooting.py" in DOCUMENT


# --------------------------------------------------------------------------
# 8. Safety of the samples
# --------------------------------------------------------------------------


@pytest.mark.parametrize("flag", FORBIDDEN_FLAGS)
def test_no_sample_carries_a_credential_or_a_redirect(flag: str) -> None:
    assert flag not in FENCED, flag


def test_every_kubectl_and_helm_sample_names_its_kubeconfig_and_context() -> None:
    """An unscoped sample is the accident every wrapper in this repository prevents."""
    joined: list[str] = []
    for block in BLOCKS:
        continued = ""
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.endswith("\\"):
                continued += stripped[:-1] + " "
                continue
            joined.append(continued + stripped)
            continued = ""
        if continued:
            joined.append(continued)

    for command in joined:
        if not command.startswith(("kubectl ", "helm ")):
            continue
        assert "--kubeconfig" in command, command
        assert "--context" in command or "--kube-context" in command, command


def test_every_kind_command_names_the_cluster_it_acts_on() -> None:
    """``kind`` defaults to a cluster called ``kind``, which is not this one.

    Independent review found ``kind load docker-image`` printed without
    ``--name``: run verbatim it targets kind's own default cluster, so it either
    errors or loads an image into somebody else's cluster. That is the accident
    rule 2 exists to prevent, and it escaped the scoping check below because it
    sits in a table cell rather than in a fenced block -- so this one reads the
    whole document.
    """
    cluster = _lib_constant("INFEROPS_CLUSTER_NAME")
    for match in re.finditer(r"`kind (?P<rest>[^`]+)`", DOCUMENT):
        rest = match.group("rest")
        if rest.split()[0] in {"get", "version", "delete"}:
            continue
        assert f"--name {cluster}" in rest, match.group(0)


def test_the_expected_image_failure_matches_the_committed_values_file() -> None:
    """The blocker's symptom is a different word under each pull policy.

    ``real-values.yaml`` sets ``Never``, so the kubelet never attempts a pull and
    reports ``ErrImageNeverPull``; the chart's own default is ``IfNotPresent``,
    which reports ``ErrImagePull``. A page naming only the second sends the
    reader looking for a string the committed fixture cannot produce.
    """
    fixture = yaml.safe_load(
        (CHART_DIR / "ci" / "real-values.yaml").read_text(encoding="utf-8")
    )
    assert fixture["api"]["image"]["pullPolicy"] == "Never"
    assert VALUES["api"]["image"]["pullPolicy"] == "IfNotPresent"
    assert "ErrImageNeverPull" in DOCUMENT
    assert "ErrImagePull" in DOCUMENT
    assert "ImagePullBackOff" in DOCUMENT


def test_both_model_verification_refusals_are_quoted() -> None:
    """The init container has two messages, and the absent one is the likeliest.

    The acquisition job is deferred and the claim is filled out of band, so an
    empty claim is the ordinary state. Quoting only the byte-count refusal sends
    that reader to the wrong row.
    """
    script = _container_by_kind_and_name("Deployment", "inferops-inferops-llm-runtime")
    refusals = re.findall(r"REFUSED: [^\"\n]+", script)
    assert len(refusals) == 2, refusals
    for refusal in refusals:
        assert refusal in DOCUMENT, refusal


def test_the_cluster_teardown_is_not_described_as_sparing_the_weights() -> None:
    """The accepted node declares no extraMounts, so a teardown takes them too.

    An earlier draft called the Terraform destroy "the only operation in this
    repository that reclaims the model weights". It is not: with the claim on the
    cluster's default storage class and no host mount, the bytes live inside the
    node container and ``cluster-down.sh`` reclaims them as well.
    """
    kind_config = yaml.safe_load(
        (REPO_ROOT / "deploy" / "kind" / "inferops-dev.yaml").read_text(
            encoding="utf-8"
        )
    )
    for node in kind_config["nodes"]:
        assert "extraMounts" not in node, node
    assert "without destroying the cluster" in DOCUMENT
    assert "the only operation in this repository that reclaims" not in FLOWED


def test_the_teardown_does_not_tell_the_reader_to_re_run_the_residue_check() -> None:
    """``cluster-down.sh`` runs ``verify-clean.sh`` itself at the end of every run."""
    teardown = (REPO_ROOT / "scripts" / "environment" / "cluster-down.sh").read_text(
        encoding="utf-8"
    )
    assert "verify-clean.sh" in teardown
    assert "runs `verify-clean.sh` itself" in DOCUMENT


def test_no_sample_deletes_a_namespace_or_prunes_the_engine_by_hand() -> None:
    """Both are the exact accidents the scoped scripts exist to prevent."""
    for forbidden in (
        "kubectl delete namespace",
        "docker system prune",
        "kubectl delete --all",
        "--all-namespaces --force",
    ):
        assert forbidden not in FENCED, forbidden


def test_every_destructive_sample_is_labelled_as_one() -> None:
    """A reader skimming for a command must not find an unmarked deletion."""
    for block in BLOCKS:
        lowered = block.lower()
        if not any(
            token in lowered
            for token in ("uninstall", "destroy", "cluster-down.sh", "clean --confirm")
        ):
            continue
        assert "destructive" in lowered, block


# --------------------------------------------------------------------------
# 9. The claims the page must keep making
# --------------------------------------------------------------------------

REQUIRED_STATEMENTS = (
    "has never been run by anybody, on any cluster",
    "still carry a placeholder digest for it",
    "Nothing on this page may be cited as evidence that the release installs",
    "The namespace, its metadata, and the model cache survive",
    "This is not the routine uninstall path.",
    "Neither Terraform nor Helm may delete a cluster",
    "The executed evidence behind this page is from one Windows host",
)


@pytest.mark.parametrize("statement", REQUIRED_STATEMENTS)
def test_the_page_keeps_the_statement_it_is_not_entitled_to_drop(
    statement: str,
) -> None:
    assert " ".join(statement.split()) in FLOWED, statement


def test_the_rule_count_matches_the_rules() -> None:
    """A numbered list whose headline count drifted is the cheapest kind of wrong."""
    numbers = {"Four": 4, "Five": 5, "Six": 6, "Seven": 7}
    match = re.search(r"^(?P<word>[A-Z][a-z]+) rules\.", PROSE, re.MULTILINE)
    assert match is not None, "the rules section lost its headline count"
    stated = numbers[match.group("word")]
    listed = len(re.findall(r"^\d+\. \*\*", PROSE, re.MULTILINE))
    assert stated == listed, {"headline says": stated, "list holds": listed}


def test_the_page_says_which_checks_need_a_cluster_and_which_need_the_tooling() -> None:
    """Only one of the three script checks needs a cluster to exist.

    ``preflight.sh`` is the pre-cluster check and ``verify-clean.sh`` asserts
    absence; grouping all three as "need a cluster" sends the reader with no
    working cluster past the one check that would have told them why.
    """
    preflight = (REPO_ROOT / "scripts" / "environment" / "preflight.sh").read_text(
        encoding="utf-8"
    )
    residue = (REPO_ROOT / "scripts" / "environment" / "verify-clean.sh").read_text(
        encoding="utf-8"
    )
    # Neither asserts the target cluster; both tolerate its absence.
    assert "inferops::assert_target_cluster" not in preflight
    assert "inferops::assert_target_cluster" not in residue
    assert "Run `preflight.sh` first when you have no working cluster" in DOCUMENT
    assert "Only the middle one needs a cluster to exist" in DOCUMENT


def test_the_cleanup_section_separates_all_four_radii() -> None:
    """The acceptance criterion is the separation, so it is checked as one."""
    for heading in (
        "### 1. Uninstall the workload",
        "### 2. Remove the Terraform prerequisites",
        "### 3. Delete the model cache",
        "### 4. Destroy the cluster",
    ):
        assert heading in DOCUMENT, heading
    assert "They are not a sequence and none" in FLOWED


def test_the_page_covers_every_area_the_story_requires() -> None:
    """Scheduling, OOM, model load, probes, service, telemetry, Helm, Terraform, storage."""
    for heading in (
        "## Cluster and context",
        "## Scheduling, resources, and out-of-memory",
        "## Model cache and storage",
        "## Slow or failed model load",
        "## Probes",
        "## Service, network, and the policy that is not enforced",
        "## Reading the API's and the runtime's logs",
        "## Telemetry scrape",
        "## The Helm release",
        "## Terraform state and ownership",
        "## Upgrading and rolling back",
        "## Cleanup",
    ):
        assert heading in DOCUMENT, heading
