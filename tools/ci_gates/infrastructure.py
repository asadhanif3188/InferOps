"""The infrastructure expected-failure controls, run through the real tools.

The controls in `core.py` run modules from this repository. These run the
programs this repository does not vendor - `helm`, `kubeconform`, `terraform`,
and `tflint` - against fixtures that each tool must refuse and inputs it must
accept, and read the exit status the way a workflow step would.

Two things make that harder than it looks, and both are handled here rather
than hoped about.

**A missing tool refuses everything.** A negative control run on a host without
`helm` exits non-zero, which is exactly what the control asks for. So nothing
runs until every tool a family needs is found **at the version this repository
pins**, and a host that cannot satisfy that fails the gate instead of passing
its negatives by accident.

**A refusal for the wrong reason is still a refusal.** A fixture meant to fail
the values schema also fails if the base values path is misspelled. Every
negative control therefore names the text its refusal must contain, and a
refusal that does not contain it is a failed control.

Nothing here reaches a cluster. `helm template` renders locally, `kubeconform`
reads schemas over the network from a pinned commit, `terraform` runs `fmt`,
`init -backend=false`, and `validate`, and `tflint` reads files. Terraform
fixtures are copied into a temporary directory first, so `init` writes its
working state there and never beside a committed file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .core import REPO_ROOT

#: The versions every result below was produced with. The workflow installs
#: exactly these, and a suite compares this table to the workflow and to the
#: gate matrix, so a bump in one place and not the others fails the build.
PINNED_VERSIONS = {
    "helm": "v3.19.0",
    "kubeconform": "v0.8.0",
    "terraform": "1.15.8",
    "tflint": "0.64.0",
}

#: The Kubernetes version the manifests are validated against, which is the
#: server version ADR 0001 pins.
KUBERNETES_VERSION = "1.34.0"

#: Where kubeconform reads its schemas. Its default is the `master` branch of the
#: schema repository, which moves; this is one commit of it, so a result is a
#: statement about a fixed set of schemas rather than about the day it ran.
KUBECONFORM_SCHEMA_COMMIT = "970cc70507e1880a7a3b64184b6aad417a1d8d85"
KUBECONFORM_SCHEMA_LOCATION = (
    "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/"
    f"{KUBECONFORM_SCHEMA_COMMIT}/"
    "{{.NormalizedKubernetesVersion}}-standalone{{.StrictSuffix}}/"
    "{{.ResourceKind}}{{.KindSuffix}}.json"
)

CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
CI_VALUES_DIR = CHART_DIR / "ci"
RELEASE_NAME = "inferops"
RELEASE_NAMESPACE = "inferops-platform"
SMOKE_MANIFEST_DIR = REPO_ROOT / "deploy" / "smoke"

TERRAFORM_ROOT = REPO_ROOT / "infra" / "terraform"
TERRAFORM_ENVIRONMENT = TERRAFORM_ROOT / "environments" / "local"
TFLINT_CONFIG = TERRAFORM_ROOT / ".tflint.hcl"

FIXTURE_ROOT = REPO_ROOT / "tests" / "architecture" / "fixtures" / "infrastructure"
FIXTURE_MANIFEST = FIXTURE_ROOT / "expected-refusals.json"
VALUES_FIXTURES = FIXTURE_ROOT / "helm-values"
SCHEMA_FIXTURES = FIXTURE_ROOT / "kubernetes-schema"
TERRAFORM_FIXTURES = FIXTURE_ROOT / "terraform"

#: The placeholder a stage writes its standard output to, and the one a later
#: stage reads it from. A pipe would hide which half of it failed.
RENDER = "{render}"
#: The temporary copy of a Terraform fixture.
WORKDIR = "{workdir}"

FAMILIES = ("kubernetes", "terraform")

#: The programs each family runs. `python` is this interpreter and is not probed.
TOOLS_BY_FAMILY = {
    "kubernetes": ("helm", "kubeconform"),
    "terraform": ("terraform", "tflint"),
}


@dataclass(frozen=True)
class Stage:
    """One program invocation. ``argv[0]`` is a tool name, or ``python``."""

    argv: tuple[str, ...]
    writes_render: bool = False
    #: Run from inside the temporary copy of a fixture rather than from the
    #: repository root.
    in_workdir: bool = False


@dataclass(frozen=True)
class ToolControl:
    """Stages run in order; ``fails_at`` names the one that must refuse.

    ``fails_at`` is None for a control whose every stage must succeed. Every
    stage before the refusing one must succeed, so a render that failed is not
    mistaken for a policy that refused it.
    """

    controlId: str
    stages: tuple[Stage, ...]
    fails_at: int | None
    reason: str | None = None
    copy_from: Path | None = None

    @property
    def published_command(self) -> str:
        """The stages as a reader would type them, with no host path in them."""
        rendered = []
        for stage in self.stages:
            words = [
                "<render>" if w == RENDER else "<copy>" if w == WORKDIR else w
                for w in stage.argv
            ]
            words = [w.replace(REPO_ROOT.as_posix() + "/", "") for w in words]
            line = " ".join(words)
            if stage.in_workdir:
                line = f"(cd <copy> && {line})"
            rendered.append(f"{line} > <render>" if stage.writes_render else line)
        return " && ".join(rendered)


@dataclass(frozen=True)
class ToolResult:
    control: ToolControl
    exits: tuple[int, ...]
    output: str

    @property
    def passed(self) -> bool:
        expected = self.control.fails_at
        if expected is None:
            return len(self.exits) == len(self.control.stages) and all(
                code == 0 for code in self.exits
            )
        if len(self.exits) != expected + 1:
            return False
        if any(code != 0 for code in self.exits[:expected]):
            return False
        if self.exits[expected] == 0:
            return False
        return self.control.reason is None or self.control.reason in self.output


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def manifest() -> dict[str, list[dict[str, str]]]:
    loaded: dict[str, list[dict[str, str]]] = json.loads(
        FIXTURE_MANIFEST.read_text(encoding="utf-8")
    )["groups"]
    return loaded


def _helm_template(*values: Path) -> Stage:
    argv = [
        "helm",
        "template",
        RELEASE_NAME,
        _relative(CHART_DIR),
        "--namespace",
        RELEASE_NAMESPACE,
    ]
    for path in values:
        argv += ["--values", _relative(path)]
    return Stage(tuple(argv), writes_render=True)


def _kubeconform(*targets: str) -> Stage:
    return Stage(
        (
            "kubeconform",
            "-strict",
            "-summary",
            "-kubernetes-version",
            KUBERNETES_VERSION,
            "-schema-location",
            KUBECONFORM_SCHEMA_LOCATION,
            *targets,
        )
    )


def _policy(target: str) -> Stage:
    return Stage(("python", "-m", "tools.workload_policy", target))


def _tflint(chdir: str | None, *extra: str) -> Stage:
    """tflint with the committed configuration, passed by absolute path.

    Measured on tflint 0.64.0: under `--recursive`, a `.tflint.hcl` that is
    merely present in the directory named by `--chdir` is not applied, and a
    relative `--config` is resolved against each module rather than against the
    root. Only an absolute path reaches every module.

    With no ``chdir`` the stage runs from inside the fixture's temporary copy.
    `--chdir` has to be expressible relative to the working directory, and a
    temporary directory on another drive is not - which on Windows is where the
    temporary directory usually is.
    """
    config = f"--config={TFLINT_CONFIG.as_posix()}"
    if chdir is None:
        return Stage(("tflint", *extra, config), in_workdir=True)
    return Stage(("tflint", *extra, f"--chdir={chdir}", config))


def kubernetes_controls() -> list[ToolControl]:
    groups = manifest()
    real = CI_VALUES_DIR / "real-values.yaml"
    found: list[ToolControl] = []
    for row in groups["values-refused"]:
        found.append(
            ToolControl(
                controlId=f"values-refused/{row['fixture']}",
                stages=(_helm_template(real, VALUES_FIXTURES / row["fixture"]),),
                fails_at=0,
                reason=row["reason"],
            )
        )
    for row in groups["render-refused-by-policy"]:
        found.append(
            ToolControl(
                controlId=f"render-refused-by-policy/{row['fixture']}",
                stages=(
                    _helm_template(real, VALUES_FIXTURES / row["fixture"]),
                    _policy(RENDER),
                ),
                fails_at=1,
                reason=row["reason"],
            )
        )
    for row in groups["schema-refused"]:
        found.append(
            ToolControl(
                controlId=f"schema-refused/{row['fixture']}",
                stages=(_kubeconform(_relative(SCHEMA_FIXTURES / row["fixture"])),),
                fails_at=0,
                reason=row["reason"],
            )
        )
    for profile in ("mock", "real"):
        found.append(
            ToolControl(
                controlId=f"render-accepted/{profile}-values.yaml",
                stages=(
                    _helm_template(CI_VALUES_DIR / f"{profile}-values.yaml"),
                    _kubeconform(RENDER),
                    _policy(RENDER),
                ),
                fails_at=None,
            )
        )
    for manifest_path in sorted(SMOKE_MANIFEST_DIR.glob("*.yaml")):
        found.append(
            ToolControl(
                controlId=f"schema-accepted/{manifest_path.name}",
                stages=(_kubeconform(_relative(manifest_path)),),
                fails_at=None,
            )
        )
    return found


def terraform_controls() -> list[ToolControl]:
    groups = manifest()
    found: list[ToolControl] = []
    for row in groups["terraform-format-refused"]:
        found.append(
            ToolControl(
                controlId=f"terraform-format-refused/{row['fixture']}",
                stages=(Stage(("terraform", "fmt", "-check", "-recursive", WORKDIR)),),
                fails_at=0,
                reason=row["reason"],
                copy_from=TERRAFORM_FIXTURES / row["fixture"],
            )
        )
    for row in groups["terraform-validate-refused"]:
        found.append(
            ToolControl(
                controlId=f"terraform-validate-refused/{row['fixture']}",
                stages=(
                    Stage(
                        (
                            "terraform",
                            f"-chdir={WORKDIR}",
                            "init",
                            "-backend=false",
                            "-input=false",
                            "-no-color",
                        )
                    ),
                    Stage(("terraform", f"-chdir={WORKDIR}", "validate", "-no-color")),
                ),
                fails_at=1,
                reason=row["reason"],
                copy_from=TERRAFORM_FIXTURES / row["fixture"],
            )
        )
    for row in groups["terraform-lint-refused"]:
        found.append(
            ToolControl(
                controlId=f"terraform-lint-refused/{row['fixture']}",
                stages=(_tflint(None, "--format=compact"),),
                fails_at=0,
                reason=row["reason"],
                copy_from=TERRAFORM_FIXTURES / row["fixture"],
            )
        )
    environment = _relative(TERRAFORM_ENVIRONMENT)
    found.append(
        ToolControl(
            controlId="terraform-accepted/infra/terraform",
            stages=(
                Stage(
                    (
                        "terraform",
                        "fmt",
                        "-check",
                        "-recursive",
                        _relative(TERRAFORM_ROOT),
                    )
                ),
                Stage(
                    (
                        "terraform",
                        f"-chdir={environment}",
                        "init",
                        "-backend=false",
                        "-input=false",
                        "-no-color",
                    )
                ),
                Stage(("terraform", f"-chdir={environment}", "validate", "-no-color")),
                _tflint(_relative(TERRAFORM_ROOT), "--recursive", "--format=compact"),
            ),
            fails_at=None,
        )
    )
    return found


def controls(family: str) -> list[ToolControl]:
    if family == "kubernetes":
        return kubernetes_controls()
    if family == "terraform":
        return terraform_controls()
    raise ValueError(f"unknown family {family!r}")


#: The smallest number of controls of each kind a run must find, for the same
#: reason `core.MINIMUM_CONTROLS` exists: a glob that matched nothing is an
#: empty, passing gate.
MINIMUM_TOOL_CONTROLS = {
    "values-refused": 9,
    "render-refused-by-policy": 1,
    "schema-refused": 4,
    "render-accepted": 2,
    "schema-accepted": 2,
    "terraform-format-refused": 1,
    "terraform-validate-refused": 1,
    "terraform-lint-refused": 3,
    "terraform-accepted": 1,
}

GROUPS_BY_FAMILY = {
    "kubernetes": (
        "values-refused",
        "render-refused-by-policy",
        "schema-refused",
        "render-accepted",
        "schema-accepted",
    ),
    "terraform": (
        "terraform-format-refused",
        "terraform-validate-refused",
        "terraform-lint-refused",
        "terraform-accepted",
    ),
}


def shortfalls(family: str, found: Sequence[ToolControl]) -> list[str]:
    counted = dict.fromkeys(GROUPS_BY_FAMILY[family], 0)
    for control in found:
        kind = control.controlId.split("/", 1)[0]
        if kind in counted:
            counted[kind] += 1
    return [
        f"{kind}: found {counted[kind]}, expected at least {MINIMUM_TOOL_CONTROLS[kind]}"
        for kind in GROUPS_BY_FAMILY[family]
        if counted[kind] < MINIMUM_TOOL_CONTROLS[kind]
    ]


# --------------------------------------------------------------------------
# The tools, found and version-checked before anything is allowed to run
# --------------------------------------------------------------------------


def _probe(tool: str, path: str) -> str:
    """The version string a tool reports, normalised to the pinned form."""
    # A fixed argument vector with no shell: the program path comes from
    # `shutil.which` and every other member is a constant.
    if tool == "helm":
        out = subprocess.run(
            [path, "version", "--short"], capture_output=True, text=True, check=False
        ).stdout.strip()
        return out.split("+", 1)[0]
    if tool == "kubeconform":
        return subprocess.run(
            [path, "-v"], capture_output=True, text=True, check=False
        ).stdout.strip()
    if tool == "terraform":
        out = subprocess.run(
            [path, "version", "-json"], capture_output=True, text=True, check=False
        ).stdout
        try:
            return str(json.loads(out)["terraform_version"])
        except (ValueError, KeyError):
            return out.strip()
    if tool == "tflint":
        out = subprocess.run(
            [path, "--version"], capture_output=True, text=True, check=False
        ).stdout
        first = out.splitlines()[0] if out else ""
        return first.removeprefix("TFLint version ").strip()
    raise ValueError(f"no version probe for {tool!r}")


def tool_problems(family: str) -> tuple[dict[str, str], list[str]]:
    """Resolved tool paths, and every reason the family may not run."""
    resolved: dict[str, str] = {}
    problems: list[str] = []
    for tool in TOOLS_BY_FAMILY[family]:
        path = shutil.which(tool)
        if path is None:
            problems.append(
                f"{tool} is not on PATH. A negative control run without it would "
                "pass by failing to start, so nothing runs."
            )
            continue
        reported = _probe(tool, path)
        if reported != PINNED_VERSIONS[tool]:
            problems.append(
                f"{tool} reports {reported!r}; this gate is pinned to "
                f"{PINNED_VERSIONS[tool]!r}"
            )
            continue
        resolved[tool] = path
    return resolved, problems


# --------------------------------------------------------------------------
# The runner
# --------------------------------------------------------------------------


def _argv(
    stage: Stage, tools: dict[str, str], render: Path, workdir: Path | None
) -> list[str]:
    program, *rest = stage.argv
    executable = sys.executable if program == "python" else tools[program]
    out = [executable]
    for word in rest:
        word = word.replace(RENDER, render.as_posix())
        if workdir is not None:
            word = word.replace(WORKDIR, workdir.as_posix())
        out.append(word)
    return out


def run(found: Sequence[ToolControl], tools: dict[str, str]) -> Iterator[ToolResult]:
    for control in found:
        with tempfile.TemporaryDirectory(prefix="inferops-ci-gate-") as scratch:
            scratch_dir = Path(scratch)
            render = scratch_dir / "render.yaml"
            workdir: Path | None = None
            if control.copy_from is not None:
                workdir = scratch_dir / "fixture"
                shutil.copytree(control.copy_from, workdir)
            exits: list[int] = []
            output: list[str] = []
            for stage in control.stages:
                # A fixed argument vector with no shell. Every program path comes
                # from `shutil.which` or is this interpreter, and every argument
                # is a constant, a repository path, or a temporary path.
                completed = subprocess.run(
                    _argv(stage, tools, render, workdir),
                    cwd=workdir if stage.in_workdir and workdir else REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                exits.append(completed.returncode)
                if stage.writes_render:
                    render.write_text(
                        completed.stdout.replace("\r\n", "\n"), encoding="utf-8"
                    )
                    output.append(completed.stderr)
                else:
                    output.append(completed.stdout + completed.stderr)
                if completed.returncode != 0:
                    break
            text = "\n".join(output)
            # A diagnostic names the temporary directory, which is a host path.
            # It is replaced before the text leaves this function.
            text = text.replace(scratch_dir.as_posix(), "<scratch>").replace(
                str(scratch_dir), "<scratch>"
            )
            yield ToolResult(control=control, exits=tuple(exits), output=text)
