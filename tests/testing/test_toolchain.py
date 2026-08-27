"""The toolchain decision, checked against the configuration it decided.

ADR 0009 names a build backend, a dependency manager, a lockfile policy, a
linter, a formatter, a type checker, and a rejected task runner. Every one of
those is a file in this repository, which means the record and the configuration
can disagree — and a record that disagrees with the configuration is worse than
no record, because a reader trusts it.

So the two tables in ADR 0009 are read here and compared against
``pyproject.toml`` and ``uv.lock``. A dependency bumped without updating the
record fails; a version typed into the record that the lockfile does not pin
fails. That is the same rule the cost suite applies to arithmetic and the
security suite applies to counts.

Three things this module deliberately does not check, because it cannot:

* that a contributor actually resolved from the lockfile rather than from an
  index — there is no lane to observe that in, and `DR-07` carries the gap;
* that any of the tools were ever run — the validation record carries that, and
  a record is a human artefact;
* that ``uv``, ``hatchling``, and the provisioned interpreter are at the versions
  the record names, because none of the three is pinned by a committed file.

It reads only files in this repository: no network, no cluster, no clock.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
LOCK_PATH = REPO_ROOT / "uv.lock"
PYTEST_INI_PATH = REPO_ROOT / "pytest.ini"
PYTHON_VERSION_PATH = REPO_ROOT / ".python-version"
DECISION_PATH = (
    REPO_ROOT / "docs" / "architecture" / "decisions" / "ADR-0009-python-toolchain.md"
)
VALIDATION_PATH = (
    REPO_ROOT / "docs" / "proof" / "toolchain" / "v1-s0-011-pr1-validation.md"
)
PACKAGE_ROOT = REPO_ROOT / "src" / "inferops"


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        document: dict[str, Any] = tomllib.load(handle)
    return document


PYPROJECT = _load_toml(PYPROJECT_PATH)
LOCK = _load_toml(LOCK_PATH)
DECISION = DECISION_PATH.read_text(encoding="utf-8")

# `| something | `name` | `constraint` |` - the third column of the pinning
# table and the second of the resolved-version table are both a single
# backticked token, which is what makes both tables parseable with one pattern.
_THREE_COLUMN_ROW = re.compile(
    r"^\|[^|]+\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*$", re.MULTILINE
)
_TWO_COLUMN_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*$", re.MULTILINE)


def _section(title: str) -> str:
    """The body of one `## ` section of the decision record."""
    start = DECISION.index(f"\n## {title}\n")
    rest = DECISION[start + 1 :]
    end = rest.find("\n## ", 1)
    return rest if end == -1 else rest[:end]


DECLARED_CONSTRAINTS = dict(
    _THREE_COLUMN_ROW.findall(_section("What is pinned, and where"))
)
DECLARED_LOCK_VERSIONS = dict(
    _TWO_COLUMN_ROW.findall(_section("What the committed lockfile resolved"))
)

LOCKED_VERSIONS = {row["name"]: row["version"] for row in LOCK["package"]}

# Every file that would mean a task runner had been adopted without ADR 0009
# being revisited. D7 rejects all of them, and a rejection nothing checks is a
# rejection that lasts until somebody is in a hurry.
TASK_RUNNER_FILES = (
    "Taskfile.yml",
    "Taskfile.yaml",
    "Taskfile.dist.yml",
    "justfile",
    "Justfile",
    ".justfile",
    "Makefile",
    "makefile",
    "GNUmakefile",
    "noxfile.py",
    "tasks.py",
)


# --------------------------------------------------------------------------
# The record and the configuration agree
# --------------------------------------------------------------------------


def test_the_record_publishes_a_constraint_for_every_tool_it_names() -> None:
    assert DECLARED_CONSTRAINTS, "the pinning table in ADR 0009 parsed as empty"
    assert set(DECLARED_CONSTRAINTS) == {
        "hatchling",
        "ruff",
        "mypy",
        "pytest",
        "jsonschema",
        "PyYAML",
        "types-PyYAML",
        "types-jsonschema",
    }


def test_the_build_backend_constraint_is_the_one_the_record_publishes() -> None:
    requires = PYPROJECT["build-system"]["requires"]
    assert requires == [DECLARED_CONSTRAINTS["hatchling"]], requires
    assert PYPROJECT["build-system"]["build-backend"] == "hatchling.build"


@pytest.mark.parametrize(
    "package",
    sorted(set(DECLARED_CONSTRAINTS) - {"hatchling"}),
)
def test_every_declared_constraint_is_committed_in_pyproject(package: str) -> None:
    """A constraint in the record is a constraint in a dependency group."""
    groups = PYPROJECT["dependency-groups"]
    declared: set[str] = set()
    for members in groups.values():
        declared.update(item for item in members if isinstance(item, str))
    assert DECLARED_CONSTRAINTS[package] in declared, (
        f"ADR 0009 publishes {DECLARED_CONSTRAINTS[package]!r} and no dependency "
        "group declares it"
    )


def test_no_dependency_is_declared_that_the_record_does_not_publish() -> None:
    """The table is the whole list, not a selection from it."""
    published = set(DECLARED_CONSTRAINTS.values())
    for name, members in PYPROJECT["dependency-groups"].items():
        for item in members:
            if not isinstance(item, str):
                continue  # an `include-group` reference, not a requirement
            assert item in published, (
                f"group {name!r} declares {item!r}, which ADR 0009 does not publish"
            )


def test_the_distribution_declares_no_runtime_dependency() -> None:
    """D1: nothing that installs `inferops` acquires a check tool."""
    assert PYPROJECT["project"]["dependencies"] == []


@pytest.mark.parametrize("package", sorted(DECLARED_LOCK_VERSIONS))
def test_every_version_the_record_publishes_is_the_version_the_lock_pins(
    package: str,
) -> None:
    assert package in LOCKED_VERSIONS, f"{package} is not in the lockfile at all"
    assert LOCKED_VERSIONS[package] == DECLARED_LOCK_VERSIONS[package], (
        f"ADR 0009 says {package} is at {DECLARED_LOCK_VERSIONS[package]} and the "
        f"lockfile pins {LOCKED_VERSIONS[package]}. A version typed into a record "
        "that the lockfile does not produce is a failing test."
    )


def test_the_lockfile_pins_every_tool_the_record_names() -> None:
    """Normalised names, because a lockfile lowercases what a record capitalises."""
    for package in DECLARED_CONSTRAINTS:
        if package == "hatchling":
            continue  # a build requirement, resolved in an isolated build environment
        assert package.lower() in LOCKED_VERSIONS, f"{package} is not locked"


def test_the_lockfile_carries_a_hash_for_every_distribution_it_pins() -> None:
    """D3 rule 2. A lock without hashes pins a name, not an artifact."""
    body = LOCK_PATH.read_text(encoding="utf-8")
    hashes = body.count('hash = "sha256:')
    assert hashes >= 100, f"the lockfile carries {hashes} hashes"
    assert f"{hashes} of them are committed" in " ".join(DECISION.split()), (
        f"ADR 0009 does not state the {hashes} artifact hashes the lockfile carries"
    )


def test_the_lock_and_the_project_agree_on_the_interpreter_series() -> None:
    """D3 rule 3, in all three places it is written down."""
    assert PYPROJECT["project"]["requires-python"] == ">=3.12,<3.13"
    assert LOCK["requires-python"] == "==3.12.*"
    assert PYTHON_VERSION_PATH.read_text(encoding="utf-8").strip() == "3.12"


# --------------------------------------------------------------------------
# D1 - the packaging layout
# --------------------------------------------------------------------------


def test_the_distribution_is_the_src_layout_the_record_decided() -> None:
    assert PYPROJECT["project"]["name"] == "inferops"
    assert (PACKAGE_ROOT / "__init__.py").is_file()
    packages = PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert packages == ["src/inferops"], packages


def test_repository_tooling_and_tests_stay_outside_the_distribution() -> None:
    """D1. `tools/` and `tests/` are not shipped, and no wheel target names them."""
    packages = PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert not any(entry.startswith(("tools", "tests")) for entry in packages)
    sdist = PYPROJECT["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    assert not any(entry.lstrip("/").startswith(("tools", "tests")) for entry in sdist)
    assert all(entry.startswith("/") for entry in sdist), (
        "an unanchored source-distribution include matches at every depth"
    )


def test_the_version_is_declared_once() -> None:
    """D1. The distribution version lives in one file, and it is not the package."""
    assert PYPROJECT["project"]["version"] == "0.0.0"
    body = (PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "__version__" not in body


def test_the_distribution_refuses_to_be_uploaded() -> None:
    """D1. V1 publishes nothing to an index, and the classifier is the guard."""
    assert "Private :: Do Not Upload" in PYPROJECT["project"]["classifiers"]


# --------------------------------------------------------------------------
# D7 - the rejection
# --------------------------------------------------------------------------


@pytest.mark.parametrize("filename", TASK_RUNNER_FILES)
def test_no_task_runner_file_is_committed(filename: str) -> None:
    assert not (REPO_ROOT / filename).exists(), (
        f"{filename} exists and ADR 0009 D7 rejects a task runner. Adopting one is "
        "an amendment to that record, not a new file."
    )


def test_the_rejection_is_recorded_as_a_decision_rather_than_a_silence() -> None:
    status = _section("Decision status")
    assert "| D7 |" in status
    assert "**Rejected**" in status


# --------------------------------------------------------------------------
# D8 - what did not move
# --------------------------------------------------------------------------


def test_the_pytest_configuration_did_not_move_into_pyproject() -> None:
    """D8, and the condition ADR 0005's consequences attached to this file."""
    assert "pytest" not in PYPROJECT["tool"], (
        "pyproject.toml declares a pytest table. ADR 0005 made the marker set and "
        "the default marker expression load-bearing and ADR 0009 D8 leaves them in "
        "pytest.ini; moving them is an amendment to both records."
    )
    assert PYTEST_INI_PATH.is_file()


def test_the_default_marker_expression_still_deselects_every_capable_host_lane() -> (
    None
):
    """The property ADR 0005 D2 depends on, re-checked from this record's side."""
    body = PYTEST_INI_PATH.read_text(encoding="utf-8")
    assert '-m "not cluster and not realruntime and not failure and not load"' in body
    assert "--strict-markers" in body
    assert "--strict-config" in body


# --------------------------------------------------------------------------
# D9, and the records that have to exist
# --------------------------------------------------------------------------


def test_the_record_states_that_continuous_integration_is_still_undecided() -> None:
    """D9 is a scope boundary, and the question behind it stays open either way.

    Checked case-insensitively on the second half: the row calls the boundary
    accepted and the service undecided, and it is the second that a reader must
    not lose. A record that adopted a linter, a formatter, a type checker, and a
    lockfile is exactly the record somebody will assume turned on a pipeline.
    """
    status = _section("Decision status")
    row = next(line for line in status.splitlines() if line.startswith("| D9 |"))
    assert "boundary" in row.lower()
    assert "not decided" in row.lower()
    assert "ADR 0005 D6" in DECISION


def test_the_decision_names_a_validation_record_that_exists() -> None:
    assert VALIDATION_PATH.is_file(), (
        "ADR 0009 cites a validation record that is not committed"
    )
    assert "v1-s0-011-pr1-validation.md" in DECISION


def test_the_record_declares_what_it_supersedes() -> None:
    """One ADR supersedes ADR 0001 D3 and D4; two accepted records may not disagree."""
    head = DECISION[: DECISION.index("## Decision status")]
    assert "| Supersedes | ADR 0001 D3 and ADR 0001 D4 |" in head
    superseded = (
        REPO_ROOT
        / "docs"
        / "architecture"
        / "decisions"
        / "ADR-0001-local-development-environment.md"
    ).read_text(encoding="utf-8")
    assert "| D3 | Task runner: Task (go-task) | **Superseded**" in superseded
    assert (
        "| D4 | Dependency installation: uv with a committed lockfile | **Superseded**"
        in superseded
    )


def test_the_decision_record_carries_the_sections_this_project_requires() -> None:
    for heading in (
        "## Decision status",
        "## Context",
        "## Decision criteria",
        "## Decision",
        "## Alternatives considered",
        "## Consequences",
        "## Compatibility impact",
        "## Security considerations",
        "## Evidence",
    ):
        assert f"\n{heading}\n" in DECISION, f"ADR 0009 is missing {heading}"
