"""The architecture's dependency rule, checked rather than remembered.

> Nothing in the platform domain may import a Kubernetes client, a Helm library,
> a serving-runtime SDK, or an HTTP framework.

That rule is in [ADR 0004](../../docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
and in the system architecture, and it is question **B1** on the boundary review
checklist. Until now it was a question a reviewer answered. This suite answers it
from the source: it reads every module under ``src/inferops`` with the standard
library's own parser and fails if one imports anything outside the standard
library and this distribution.

The check is an allowlist rather than a list of forbidden packages, which matters
more than it looks. A denylist stops the imports somebody thought of; the
dependency rule is about everything the domain is not, including whatever ships
next year. A second test names the forbidden families anyway, so that a reader
scanning this file sees the rule in the words the ADR uses.

What this establishes is exactly one thing: what the domain imports. It does not
establish that the domain is well factored, that its objects are the right ones,
or that anything downstream respects the same rule — no adapter, API, or chart
exists to check.

Every check reads files from this repository and nothing else. No network, no
cluster, no model, no clock, no randomness.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
DISTRIBUTION_ROOT = REPO_ROOT / "src" / "inferops"

#: The one distribution a module here may import from. Everything under
#: ``src/inferops`` is platform domain today; when the API and the adapters
#: arrive they will live outside it, and this constant is where that shows.
OWN_DISTRIBUTION = "inferops"

#: The families ADR 0004 names, in the words it names them. Redundant with the
#: allowlist above by construction, and kept because a rule stated only as
#: "nothing outside the standard library" is a rule whose reason has been lost.
FORBIDDEN_IMPORT_PREFIXES = (
    # Kubernetes clients and tooling
    "kubernetes",
    "kubernetes_asyncio",
    "kubernetes_client",
    "kr8s",
    "pykube",
    "lightkube",
    "openshift",
    # Helm and Terraform tooling
    "helm",
    "pyhelm",
    "helmpy",
    "terraform",
    "python_terraform",
    "cdktf",
    # Serving-runtime and model SDKs
    "vllm",
    "llama_cpp",
    "transformers",
    "torch",
    "openai",
    "huggingface_hub",
    "tokenizers",
    # HTTP frameworks and clients
    "fastapi",
    "flask",
    "django",
    "starlette",
    "uvicorn",
    "aiohttp",
    "httpx",
    "requests",
    "tornado",
)


def domain_modules() -> list[Path]:
    return sorted(DISTRIBUTION_ROOT.rglob("*.py"))


def module_ids() -> list[str]:
    return [
        path.relative_to(REPO_ROOT).as_posix().replace("/", ".").removesuffix(".py")
        for path in domain_modules()
    ]


def imported_roots(path: Path) -> set[str]:
    """The top-level name of every absolute import in one module.

    A relative import — ``from ..context import RequestContext`` — resolves
    inside this distribution by construction and is not reported.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module is not None
        ):
            roots.add(node.module.split(".")[0])
    return roots


def test_the_distribution_has_modules_to_check() -> None:
    """A sweep over an empty directory passes by finding nothing."""
    assert len(domain_modules()) >= 2, module_ids()


@pytest.mark.parametrize("path", domain_modules(), ids=module_ids())
def test_a_domain_module_imports_only_the_standard_library(path: Path) -> None:
    """The allowlist. The domain's dependencies are Python's, and its own."""
    outside = {
        root
        for root in imported_roots(path)
        if root != OWN_DISTRIBUTION and root not in sys.stdlib_module_names
    }
    assert not outside, (path.relative_to(REPO_ROOT).as_posix(), sorted(outside))


@pytest.mark.parametrize("path", domain_modules(), ids=module_ids())
def test_a_domain_module_imports_no_infrastructure(path: Path) -> None:
    """The rule in ADR 0004's own words: no Kubernetes, Helm, Terraform,
    serving-runtime SDK, or HTTP framework."""
    forbidden = {
        root for root in imported_roots(path) if root in FORBIDDEN_IMPORT_PREFIXES
    }
    assert not forbidden, (path.relative_to(REPO_ROOT).as_posix(), sorted(forbidden))


def test_the_domain_does_not_import_its_own_development_dependencies() -> None:
    """``jsonschema`` and ``PyYAML`` are test-group inputs, not runtime ones.

    The distribution declares no runtime dependency at all, and a domain object
    that could not be constructed without a validator or a YAML loader would have
    made one of them a runtime dependency in everything but the metadata. The
    schema is still the published contract; the agreement between it and the
    domain's copy of it is checked in ``tests/domain/``, where reading a file is
    what a test is for.
    """
    imported: set[str] = set()
    for path in domain_modules():
        imported |= imported_roots(path)
    assert not imported & {"jsonschema", "yaml", "pydantic", "attrs"}, sorted(imported)


#: The one module under the distribution that touches a file: the writer of a
#: generated release, which puts bytes another module computed into a directory its
#: caller names. It does so only when called, and the test after the next holds that.
RELEASE_WRITER = DISTRIBUTION_ROOT / "domain" / "render" / "writing.py"

#: Attribute names that open or read a path.
FILE_ACCESS = {"read_text", "read_bytes", "open"}


def test_no_module_under_the_distribution_reads_a_file_at_import_time() -> None:
    """A domain object must be constructible without a file system.

    Nothing under ``src/inferops`` opens a path, which is what keeps the domain
    usable from a wheel with no repository around it. The published schema and the
    compatibility matrix are read by ``tools/`` and by the test suites, which are
    both outside the distribution on purpose.

    One module is exempt, by name: the release writer, whose purpose is to write
    the files of a generated release where a caller asks. Nothing constructs a
    domain object through it, and the test below holds that it touches a file only
    when it is called, never when it is imported.
    """
    offenders: list[str] = []
    for path in domain_modules():
        if path == RELEASE_WRITER:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "open":
                    offenders.append(path.relative_to(REPO_ROOT).as_posix())
            elif isinstance(node, ast.Attribute) and node.attr in FILE_ACCESS:
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert not offenders, sorted(set(offenders))


def test_the_release_writer_touches_a_file_only_when_it_is_called() -> None:
    """The exemption above is for calls, not for importing the writer.

    Every name that opens or reads a path sits inside a function body, so
    importing the module - and so the package that re-exports it - reads and
    writes nothing. The writer is the only exempt module, and it does exist.
    """
    assert RELEASE_WRITER in domain_modules()
    tree = ast.parse(RELEASE_WRITER.read_text(encoding="utf-8"))
    in_functions = {
        id(node)
        for function in ast.walk(tree)
        if isinstance(function, ast.FunctionDef)
        for node in ast.walk(function)
    }
    file_access = [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.Attribute) and node.attr in FILE_ACCESS)
        or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        )
    ]
    assert file_access, "the writer no longer touches a file; drop the exemption"
    assert all(id(node) in in_functions for node in file_access)
