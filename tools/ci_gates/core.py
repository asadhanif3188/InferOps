"""The expected-failure controls, and the runner that executes them.

A **control** is one command, one input, and the exit status the repository
says that pair must produce. A control whose command exits the other way is a
failure of this gate regardless of which way it went: a refusal that stopped
refusing and an acceptance that started being refused are the same defect seen
from two sides, and a gate that only checked one of them would pass a validator
that had been broken into refusing its own valid examples.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Workload documents the contract package publishes as refusable, and the
#: documents it publishes as acceptable. Both directories are read rather than
#: listed, so a fixture added to either is covered by this gate on the run that
#: adds it.
INVALID_CONTRACT_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "invalid"
VALID_CONTRACT_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "valid"

#: Manifest bundles the workload security policy publishes as refusable, and the
#: committed chart renders it publishes as acceptable.
INSECURE_MANIFEST_DIR = (
    REPO_ROOT / "tests" / "security" / "fixtures" / "workload-policy" / "invalid"
)
RENDERED_MANIFEST_DIR = REPO_ROOT / "charts" / "inferops-llm" / "ci" / "rendered"

#: Workflows the dispatch and cluster-free rules must refuse, and the ones they
#: must accept. The committed workflows are accepted too: a rule that refused
#: the file this repository actually runs would be a rule nobody could merge.
WORKFLOW_FIXTURE_DIR = (
    REPO_ROOT / "tests" / "testing" / "fixtures" / "workflow-boundary"
)
COMMITTED_WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

#: Renders and Terraform configurations that reach across the ownership
#: boundary, and the committed pair that does not.
OWNERSHIP_FIXTURE_DIR = (
    REPO_ROOT / "tests" / "testing" / "fixtures" / "ownership-overlap"
)
TERRAFORM_ROOT = REPO_ROOT / "infra" / "terraform"


@dataclass(frozen=True)
class Control:
    """One command, one input, and the exit status it is required to produce."""

    controlId: str
    module: str
    target: Path
    expected_exit: int
    #: Arguments that precede the target, as repository-relative strings.
    arguments: tuple[str, ...] = ()

    @property
    def relative_target(self) -> str:
        return self.target.relative_to(REPO_ROOT).as_posix()

    @property
    def argv(self) -> list[str]:
        return [
            sys.executable,
            "-m",
            self.module,
            *self.arguments,
            self.relative_target,
        ]

    @property
    def published_command(self) -> str:
        """The command as a reader would run it, with no interpreter path.

        `argv` names the interpreter absolutely, because that is the one the
        gate must actually invoke. Printing it would put a contributor's own
        filesystem path into a diagnostic, which is the one thing every record
        in this repository is redacted for.
        """
        return " ".join(
            ["python", "-m", self.module, *self.arguments, self.relative_target]
        )


@dataclass(frozen=True)
class Result:
    control: Control
    actual_exit: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.actual_exit == self.control.expected_exit


def _yaml_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.yaml"))


def controls() -> list[Control]:
    """Every control this gate runs, in a stable order.

    The groups come in pairs, a negative and a positive. The first two
    negatives are the acceptance criterion — an invalid contract document and an
    insecure manifest must fail — and every positive is what stops the gate
    being satisfied by a command that refuses everything it is handed. The
    workflow and ownership pairs were added by V1-S4-001-PR2: a workflow that
    reaches across its lane's boundary, and a render or Terraform configuration
    that reaches across the ownership inventory's, are refused by the same
    reading of an exit status.
    """
    found: list[Control] = []
    for target in _yaml_files(INVALID_CONTRACT_DIR):
        found.append(
            Control(
                controlId=f"contract-refused/{target.name}",
                module="tools.contract_validation",
                target=target,
                expected_exit=1,
            )
        )
    for target in _yaml_files(VALID_CONTRACT_DIR):
        found.append(
            Control(
                controlId=f"contract-accepted/{target.name}",
                module="tools.contract_validation",
                target=target,
                expected_exit=0,
            )
        )
    for target in _yaml_files(INSECURE_MANIFEST_DIR):
        found.append(
            Control(
                controlId=f"manifest-refused/{target.name}",
                module="tools.workload_policy",
                target=target,
                expected_exit=1,
            )
        )
    for target in sorted(RENDERED_MANIFEST_DIR.glob("*.expected.yaml")):
        found.append(
            Control(
                controlId=f"manifest-accepted/{target.name}",
                module="tools.workload_policy",
                target=target,
                expected_exit=0,
            )
        )
    for target in _yaml_files(WORKFLOW_FIXTURE_DIR / "invalid"):
        found.append(
            Control(
                controlId=f"workflow-refused/{target.name}",
                module="tools.ci_gates.workflow_boundary",
                target=target,
                expected_exit=1,
            )
        )
    for target in [
        *_yaml_files(WORKFLOW_FIXTURE_DIR / "valid"),
        *sorted(COMMITTED_WORKFLOW_DIR.glob("*.yml")),
    ]:
        found.append(
            Control(
                controlId=f"workflow-accepted/{target.name}",
                module="tools.ci_gates.workflow_boundary",
                target=target,
                expected_exit=0,
            )
        )
    committed_terraform = (
        "--terraform",
        TERRAFORM_ROOT.relative_to(REPO_ROOT).as_posix(),
    )
    for target in _yaml_files(OWNERSHIP_FIXTURE_DIR / "release-renders"):
        found.append(
            Control(
                controlId=f"ownership-refused/{target.name}",
                module="tools.ci_gates.ownership_overlap",
                target=target,
                expected_exit=1,
                arguments=committed_terraform,
            )
        )
    real_render = RENDERED_MANIFEST_DIR / "real.expected.yaml"
    for directory in sorted(
        path
        for path in (OWNERSHIP_FIXTURE_DIR / "terraform-declares").iterdir()
        if path.is_dir()
    ):
        found.append(
            Control(
                controlId=f"ownership-refused/{directory.name}",
                module="tools.ci_gates.ownership_overlap",
                target=real_render,
                expected_exit=1,
                arguments=(
                    "--terraform",
                    directory.relative_to(REPO_ROOT).as_posix(),
                ),
            )
        )
    for target in sorted(RENDERED_MANIFEST_DIR.glob("*.expected.yaml")):
        found.append(
            Control(
                controlId=f"ownership-accepted/{target.name}",
                module="tools.ci_gates.ownership_overlap",
                target=target,
                expected_exit=0,
                arguments=committed_terraform,
            )
        )
    return found


#: The smallest number of controls of each kind that a run must find. A glob
#: that matched nothing would otherwise produce an empty, passing gate - which
#: is the failure mode of every check built on a directory listing.
MINIMUM_CONTROLS = {
    "contract-refused": 15,
    "contract-accepted": 3,
    "manifest-refused": 8,
    "manifest-accepted": 2,
    "workflow-refused": 21,
    "workflow-accepted": 3,
    "ownership-refused": 6,
    "ownership-accepted": 2,
}


def shortfalls(found: Sequence[Control]) -> list[str]:
    """Kinds of control that turned up thinner than the repository promises."""
    counted = {kind: 0 for kind in MINIMUM_CONTROLS}
    for control in found:
        kind = control.controlId.split("/", 1)[0]
        if kind in counted:
            counted[kind] += 1
    return [
        f"{kind}: found {counted[kind]}, expected at least {minimum}"
        for kind, minimum in sorted(MINIMUM_CONTROLS.items())
        if counted[kind] < minimum
    ]


def run(found: Sequence[Control]) -> Iterator[Result]:
    for control in found:
        # A fixed argv, no shell, and a path out of this repository.
        completed = subprocess.run(
            control.argv,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        yield Result(
            control=control,
            actual_exit=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
