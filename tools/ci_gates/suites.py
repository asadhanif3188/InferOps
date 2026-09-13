"""Run a test module where its tool is installed, and refuse any skip.

The Helm chart suite and the Terraform prerequisite suite each carry checks that
need the tool itself: the committed renders are compared to a fresh
`helm template`, and the configuration is put through `terraform fmt` and
`terraform validate`. Where the tool is absent those checks skip, loudly, which
is right on a contributor's laptop and wrong in the one job that installed the
tool on purpose. A skipped drift check in that job is a green gate that checked
nothing.

So this runs the named modules and reads pytest's own report of what happened,
and a single skip fails the gate. It does not change the modules: on a host
without the tool they still skip, and the default lane still runs them that way.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .core import REPO_ROOT

#: The modules a no-skip run may be pointed at. Listed rather than accepted from
#: the command line, so the workflow cannot quietly aim the gate at a module
#: that has nothing to skip.
TOOL_BACKED_SUITES = {
    "helm": "tests/architecture/test_helm_chart.py",
    "terraform": "tests/architecture/test_terraform_prerequisites.py",
}


@dataclass(frozen=True)
class SuiteReport:
    tests: int
    failures: int
    errors: int
    skipped: tuple[str, ...]
    exit_status: int

    @property
    def passed(self) -> bool:
        return (
            self.exit_status == 0
            and self.tests > 0
            and self.failures == 0
            and self.errors == 0
            and not self.skipped
        )


def _report(junit: Path, exit_status: int) -> SuiteReport:
    root = ElementTree.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    skipped: list[str] = []
    for case in root.iter("testcase"):
        marker = case.find("skipped")
        if marker is not None:
            name = f"{case.get('classname')}::{case.get('name')}"
            skipped.append(f"{name} ({marker.get('message', '')})")
    return SuiteReport(
        tests=sum(int(suite.get("tests", "0")) for suite in suites),
        failures=sum(int(suite.get("failures", "0")) for suite in suites),
        errors=sum(int(suite.get("errors", "0")) for suite in suites),
        skipped=tuple(skipped),
        exit_status=exit_status,
    )


def run(tools: Sequence[str]) -> SuiteReport:
    modules = [TOOL_BACKED_SUITES[tool] for tool in tools]
    with tempfile.TemporaryDirectory(prefix="inferops-ci-suite-") as scratch:
        junit = Path(scratch) / "report.xml"
        # A fixed argument vector with no shell: this interpreter, constants, and
        # module paths from the table above.
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={junit}",
                *modules,
            ],
            cwd=REPO_ROOT,
            check=False,
        )
        return _report(junit, completed.returncode)
