"""What a committed workflow may do, given the lane it runs.

    python -m tools.ci_gates.workflow_boundary .github/workflows/checks.yml

A workflow runs one lane of the test strategy, and the lane decides the rules.
The `default-checks` lane runs on every change, from a fork as readily as from a
maintainer, so it may not reach a cluster at all: Helm and Terraform may run
there only as the offline subcommands that read files. A lane that needs a
cluster runs only when somebody asks for it, names the provider it is consuming,
and reaches that cluster only through the scripts that verify it first.

Those second rules describe a workflow this repository does not have. No
capable runner is labelled, because ADR 0005 D6's second half is still open, so
nothing here commits one. The rules exist anyway, and are held to the fixtures
under `tests/testing/fixtures/workflow-boundary/`, so that the first such
workflow meets a check rather than a paragraph.

**Everything here reads text.** A workflow can hand a cluster to a script, and a
script's contents are not the workflow's; the dispatch rules answer that by
admitting only scripts that call the provider guard, and the cluster-free rule
answers it by admitting no environment script at all. Exit status is 0 when the
workflow satisfies its lane and 1 when it does not.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGY_PATH = REPO_ROOT / "docs" / "testing" / "test-strategy.v1alpha1.json"
MATRIX_PATH = REPO_ROOT / "docs" / "testing" / "ci-gate-matrix.v1alpha1.json"
PROVIDER_CONTRACT_PATH = (
    REPO_ROOT / "docs" / "environment" / "local-cluster-provider-contract.v1alpha1.json"
)
ENVIRONMENT_SCRIPTS = REPO_ROOT / "scripts" / "environment"

#: A fixture names its lane in a comment, because a workflow file has no field
#: for one and a fixture is not in the gate matrix.
LANE_HEADER = re.compile(
    r"^#\s*inferops-lane:\s*(?P<lane>[a-z0-9-]+)\s*$", re.MULTILINE
)

#: The Helm and Terraform subcommands that read files and reach nothing. Every
#: other subcommand either contacts a cluster (`install`, `upgrade`, `test`,
#: `list`, `status`, `plan`, `apply`, `destroy`, `import`, `state`) or a
#: network location this lane never needs (`repo`, `pull`, `dependency`).
OFFLINE_HELM_SUBCOMMANDS = frozenset({"lint", "template", "version"})
OFFLINE_TERRAFORM_SUBCOMMANDS = frozenset({"fmt", "init", "validate", "version"})

#: Every occurrence of a tool name as a word, wherever it sits: after a space, a
#: quote, a slash, a bracket, or a `$(`. The first version of this check matched
#: only at a command position - after a space or a separator - and review found
#: that `"helm" install`, `sh -c 'helm install'`, `$(which helm) install`,
#: `/usr/local/bin/helm install`, and `terraform${IFS}apply` all walked past it.
#: So every occurrence is now read, and one that cannot be shown to be harmless
#: is refused rather than ignored. A name fused to a letter, digit, `.`, `_`, or
#: `-` (`helm-v3.19.0`, `get.helm.sh`, `terraform_1.15.8`) is part of another
#: word and is not read.
TOOL_WORD = re.compile(
    r"(?<![A-Za-z0-9_.-])(?P<tool>helm|terraform|kind)(?![A-Za-z0-9_-])"
)

#: The offline subcommands each tool may run. `kind` has none: a kind subcommand
#: creates, deletes, or reads a cluster.
OFFLINE_SUBCOMMANDS = {
    "helm": OFFLINE_HELM_SUBCOMMANDS,
    "terraform": OFFLINE_TERRAFORM_SUBCOMMANDS,
    "kind": frozenset(),
}

#: `eval` runs a string this check cannot read.
EVAL_CALL = re.compile(r"(?<![A-Za-z0-9_.-])eval[ \t]")

#: What names a cluster, a credential for one, or a way to select one. None of
#: them has an offline form.
CLUSTER_TOKENS = (
    "kubectl",
    "INFEROPS_PROVIDER",
    "KUBECONFIG",
    "kubeconfig",
    "--kube-context",
)

#: What fetches the pinned model artifact, or authorizes a script to.
MODEL_TOKENS = (
    "tools.model_acquisition",
    "tools.model_lifecycle",
    "--confirm-real-runtime",
    "huggingface.co",
)

#: What installs the real serving profile into a cluster. A release rendered from
#: the real fixture runs an acquisition job, so in a lane that installs, naming
#: it is downloading the artifact by another route.
REAL_INSTALL_TOKENS = ("real-values.yaml", "--confirm-real-kubernetes")

#: The two scripts that create or delete a cluster rather than consuming one.
CLUSTER_LIFECYCLE_SCRIPTS = frozenset({"cluster-up.sh", "cluster-down.sh"})

#: A repository script run from a workflow, by path.
ENVIRONMENT_SCRIPT_CALL = re.compile(
    r"scripts/environment/(?P<name>[A-Za-z0-9._-]+\.sh)"
)

USES = re.compile(r"^(?P<action>[^@\s]+)@(?P<ref>\S+)$")
FORTY_HEX = re.compile(r"^[0-9a-f]{40}$")

#: Runner labels GitHub hosts. A lane that consumes an externally owned cluster
#: cannot run on one: the cluster it needs is on somebody's host, not in a
#: disposable virtual machine.
HOSTED_RUNNER = re.compile(r"^(ubuntu|windows|macos)-")


@dataclass(frozen=True)
class Problem:
    """One broken rule, with the identifier a fixture records against it."""

    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.detail}"


def _load_json(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def lanes() -> dict[str, dict[str, Any]]:
    strategy = _load_json(STRATEGY_PATH)
    return {lane["laneId"]: lane for lane in strategy["lanes"]}


def supported_providers() -> list[str]:
    """The providers the S3-010 contract admits, in the order it lists them."""
    contract = _load_json(PROVIDER_CONTRACT_PATH)
    return [provider["providerId"] for provider in contract["providers"]]


def guarded_scripts() -> frozenset[str]:
    """Environment scripts that select their target through the provider guard.

    Derived rather than listed. `inferops::resolve_target` is the S3-010 guard:
    it refuses to run without an explicit provider and re-verifies the target
    before anything reaches it. A script that does not call it - `smoke.sh`, for
    one, still calls the older kind-only check - is not a script a dispatched
    workflow may hand a cluster to, however reasonable it looks.
    """
    return frozenset(
        path.name
        for path in ENVIRONMENT_SCRIPTS.glob("*.sh")
        if path.name != "lib.sh"
        and "inferops::resolve_target" in path.read_text(encoding="utf-8")
    )


def executable_text(text: str) -> str:
    """The workflow with its comment lines removed.

    A comment is where this repository writes down what a lane may not do, and a
    check that read comments would refuse the file for explaining itself.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _triggers(document: dict[Any, Any]) -> dict[str, Any]:
    """The `on:` block. YAML 1.1 loads the bare key `on` as the boolean True."""
    raw = document.get("on", document.get(True))
    if isinstance(raw, str):
        return {raw: None}
    if isinstance(raw, list):
        return {str(name): None for name in raw}
    if isinstance(raw, dict):
        return {str(name): value for name, value in raw.items()}
    return {}


def _jobs(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return {}
    return {str(name): job for name, job in jobs.items() if isinstance(job, dict)}


def _labels(runs_on: object) -> list[str]:
    if isinstance(runs_on, str):
        return [runs_on]
    if isinstance(runs_on, list):
        return [str(label) for label in runs_on]
    return []


# --------------------------------------------------------------------------
# Rules every workflow meets, whatever its lane
# --------------------------------------------------------------------------


def _common_problems(
    document: dict[str, Any], lane: dict[str, Any]
) -> Iterable[Problem]:
    if document.get("permissions") != {"contents": "read"}:
        yield Problem(
            "read-only-token",
            f"permissions are {document.get('permissions')!r}, expected "
            "{'contents': 'read'} declared at the top level",
        )
    for name, job in _jobs(document).items():
        timeout = job.get("timeout-minutes")
        if not isinstance(timeout, int) or timeout > lane["timeoutMinutes"]:
            yield Problem(
                "timeout-within-the-lane-budget",
                f"job {name} declares timeout {timeout!r}; the {lane['laneId']} "
                f"lane allows {lane['timeoutMinutes']} minutes",
            )
        for step in job.get("steps", []) or []:
            reference = step.get("uses") if isinstance(step, dict) else None
            if reference is None:
                continue
            matched = USES.match(str(reference))
            if not matched or not FORTY_HEX.match(matched.group("ref")):
                yield Problem(
                    "actions-pinned-by-commit-sha",
                    f"job {name} uses {reference!r}, which is not a commit SHA",
                )


def _model_problems(text: str, lane: dict[str, Any]) -> Iterable[Problem]:
    if lane["modelDownload"] != "none":
        return
    found = [token for token in MODEL_TOKENS if token in text]
    if lane["clusterRequired"]:
        found += [token for token in REAL_INSTALL_TOKENS if token in text]
    if found:
        yield Problem(
            "model-free-lane-downloads-nothing",
            f"the {lane['laneId']} lane downloads no model, and the workflow "
            f"names {sorted(set(found))}",
        )


# --------------------------------------------------------------------------
# A lane that needs no cluster may not reach one
# --------------------------------------------------------------------------


def _tool_occurrence(tool: str, after: str) -> str | None:
    """Why one occurrence of a tool name could reach a cluster, or None.

    ``after`` is the text following the name. The occurrence is harmless when it
    is a directory in a path (`infra/terraform/`), a YAML key (`terraform:`) or
    list member, a bare word ending its line
    (`no-skips helm`, `tar ... linux-amd64/helm`), a value in a list
    (`[kind, docker-desktop]`), or a program followed only by flags or by a path
    argument (`install ... linux-amd64/helm /usr/local/bin/helm`). It is a call
    when words follow it, and the first word that is not a flag must be an
    offline subcommand. Anything else - a quote, a `)`, a `$` - is refused,
    because it is how a call is hidden from a reader.
    """
    line = after.split("\n", 1)[0]
    if tool == "kind":
        # `kind` is also a provider name and an ordinary word. It is refused only
        # where it is followed, perhaps after a closing quote, by a subcommand.
        if re.match(r"""["']?[ \t]+[a-z]""", line):
            return f"runs kind: {('kind' + line).strip()!r}"
        return None
    if line == "" or line[0] in "/.:,]":
        return None
    if line[0] not in " \t":
        return (
            f"uses {tool} in a form this check cannot read: {(tool + line).strip()!r}"
        )
    words = [word for word in line.split() if not word.startswith("-")]
    if not words or words[0].startswith("/"):
        return None
    sub = words[0]
    if sub not in OFFLINE_SUBCOMMANDS[tool]:
        return f"runs {tool} {sub}"
    if tool == "terraform" and sub == "init" and "-backend=false" not in line:
        return "runs terraform init without -backend=false"
    return None


def cluster_calls(text: str) -> list[str]:
    """Every call in executable text that could reach a cluster, as a finding.

    Public because the refusal is only as good as what it can see, and the tests
    put it to the shapes it has to see.
    """
    found: list[str] = []
    found += [f"names {token}" for token in CLUSTER_TOKENS if token in text]
    for match in TOOL_WORD.finditer(text):
        finding = _tool_occurrence(match.group("tool"), text[match.end() :])
        if finding is not None:
            found.append(finding)
    if EVAL_CALL.search(text):
        found.append("runs eval, whose command this check cannot read")
    found += [
        f"runs scripts/environment/{match.group('name')}"
        for match in ENVIRONMENT_SCRIPT_CALL.finditer(text)
    ]
    return found


def _cluster_free_problems(
    document: dict[str, Any], text: str, runner: str
) -> Iterable[Problem]:
    for finding in cluster_calls(text):
        yield Problem("cluster-free-lane-reaches-no-cluster", finding)
    for name, job in _jobs(document).items():
        if job.get("runs-on") != runner:
            yield Problem(
                "cluster-free-lane-runs-on-the-pinned-hosted-image",
                f"job {name} runs on {job.get('runs-on')!r}, expected {runner!r}",
            )


# --------------------------------------------------------------------------
# A lane that needs a cluster is dispatched, provider-selected, and guarded
# --------------------------------------------------------------------------


def _dispatch_problems(
    document: dict[str, Any], text: str, lane: dict[str, Any]
) -> Iterable[Problem]:
    triggers = _triggers(document)
    if set(triggers) != {"workflow_dispatch"}:
        yield Problem(
            "dispatch-only",
            f"triggers are {sorted(triggers)}; a lane that needs a cluster runs "
            "only when somebody dispatches it",
        )
    dispatch = triggers.get("workflow_dispatch") or {}
    inputs = dispatch.get("inputs") if isinstance(dispatch, dict) else None
    inputs = inputs if isinstance(inputs, dict) else {}

    provider = inputs.get("provider")
    expected_options = supported_providers()
    if not isinstance(provider, dict):
        yield Problem(
            "provider-is-a-required-choice-with-no-default",
            "no `provider` input is declared",
        )
    else:
        if provider.get("required") is not True or provider.get("type") != "choice":
            yield Problem(
                "provider-is-a-required-choice-with-no-default",
                "`provider` must be `required: true` and `type: choice`",
            )
        if provider.get("options") != expected_options:
            yield Problem(
                "provider-is-a-required-choice-with-no-default",
                f"`provider` offers {provider.get('options')!r}; the provider "
                f"contract admits {expected_options!r}",
            )
        if "default" in provider:
            yield Problem(
                "provider-is-a-required-choice-with-no-default",
                f"`provider` defaults to {provider['default']!r}; the guard has "
                "no default and neither may the workflow",
            )

    workflow_env = _mapping(document.get("env"))
    for name, job in _jobs(document).items():
        job_env = _mapping(job.get("env"))
        selected = {**workflow_env, **job_env}.get("INFEROPS_PROVIDER")
        if not (
            isinstance(selected, str)
            and re.fullmatch(r"\$\{\{\s*inputs\.provider\s*\}\}", selected)
        ):
            yield Problem(
                "provider-handed-to-every-job",
                f"job {name} sets INFEROPS_PROVIDER to {selected!r}; it must be "
                "`${{ inputs.provider }}`",
            )
        labels = _labels(job.get("runs-on"))
        if "self-hosted" not in labels or any(HOSTED_RUNNER.match(x) for x in labels):
            yield Problem(
                "runs-where-the-external-cluster-is",
                f"job {name} runs on {job.get('runs-on')!r}; a lane that consumes "
                "an externally owned cluster runs on the self-hosted runner that "
                "can reach it, never on a hosted image",
            )
        if lane["authorizationRequired"]:
            condition = str(job.get("if", ""))
            if "inputs.authorize" not in condition:
                yield Problem(
                    "authorization-is-an-explicit-input",
                    f"job {name} does not run conditionally on inputs.authorize",
                )

    if lane["authorizationRequired"]:
        authorize = inputs.get("authorize")
        if not (
            isinstance(authorize, dict)
            and authorize.get("type") == "boolean"
            and authorize.get("required") is True
            and authorize.get("default") is False
        ):
            yield Problem(
                "authorization-is-an-explicit-input",
                "the lane requires authorization, and no required boolean "
                "`authorize` input defaulting to false is declared",
            )

    guarded = guarded_scripts()
    for match in ENVIRONMENT_SCRIPT_CALL.finditer(text):
        script = match.group("name")
        if script in CLUSTER_LIFECYCLE_SCRIPTS:
            yield Problem(
                "consumes-an-external-cluster",
                f"runs scripts/environment/{script}, which creates or deletes a "
                "cluster rather than consuming one",
            )
        elif script not in guarded:
            yield Problem(
                "cluster-reached-only-through-the-provider-guard",
                f"runs scripts/environment/{script}, which does not call "
                "inferops::resolve_target",
            )
    without_scripts = ENVIRONMENT_SCRIPT_CALL.sub("", text)
    for finding in cluster_calls(without_scripts):
        if finding.startswith("names INFEROPS_PROVIDER"):
            continue
        yield Problem("cluster-reached-only-through-the-provider-guard", finding)


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------


def problems(text: str, lane_id: str) -> list[Problem]:
    """Every rule the workflow in ``text`` breaks, for the lane ``lane_id``."""
    known = lanes()
    if lane_id not in known:
        return [Problem("lane-is-declared", f"no lane {lane_id!r} in the strategy")]
    lane = known[lane_id]
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        return [Problem("workflow-parses", "the file is not a YAML mapping")]
    executable = executable_text(text)
    runner = _load_json(MATRIX_PATH)["service"]["runner"]

    found: list[Problem] = []
    found += _common_problems(loaded, lane)
    found += _model_problems(executable, lane)
    if lane["clusterRequired"]:
        found += _dispatch_problems(loaded, executable, lane)
    else:
        found += _cluster_free_problems(loaded, executable, runner)
    return found


def lane_for(path: Path, text: str) -> str | None:
    """The lane a committed workflow runs, or the one a fixture declares."""
    try:
        relative = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        relative = None
    for entry in _load_json(MATRIX_PATH)["workflows"]:
        if entry["path"] == relative:
            lane: str = entry["lane"]
            return lane
    header = LANE_HEADER.search(text)
    return header.group("lane") if header else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.ci_gates.workflow_boundary",
        description=(
            "Check a workflow against the rules of the lane it runs: no cluster "
            "at all for the default lane, and dispatch, provider selection, and "
            "the provider guard for a lane that needs one."
        ),
    )
    parser.add_argument("workflow", type=Path, help="a workflow file")
    parser.add_argument(
        "--json", action="store_true", help="emit a machine-readable report"
    )
    arguments = parser.parse_args(argv)

    text = arguments.workflow.read_text(encoding="utf-8")
    lane_id = lane_for(arguments.workflow, text)
    if lane_id is None:
        print(
            "[inferops-workflow-boundary] FAILED: the workflow is not in the gate "
            "matrix and declares no `# inferops-lane:` header, so no lane's rules "
            "can be applied",
            file=sys.stderr,
        )
        return 1

    found = problems(text, lane_id)
    if arguments.json:
        report = {
            "lane": lane_id,
            "rules": sorted({problem.rule for problem in found}),
            "problems": [str(problem) for problem in found],
            "passed": not found,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for problem in found:
            print(f"[inferops-workflow-boundary] {problem}")
    if found:
        print(
            f"[inferops-workflow-boundary] FAILED: {len(found)} rule(s) of the "
            f"{lane_id} lane broken",
            file=sys.stderr,
        )
        return 1
    print(
        f"[inferops-workflow-boundary] the workflow satisfies the {lane_id} lane",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
