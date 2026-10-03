"""V2-E01 static parts: run E01-A, E01-B, and E01-C as frozen, and judge a run.

The E01 family freeze record fixes three static parts. E01-A renders the reference
contract twice and compares the two releases. E01-B changes one claim-relevant
contract field and compares the result with the first render. E01-C runs six
invalid or conflicting inputs, each twice, and records each refusal. This module does
both halves of a run.

**Run.** :func:`execute_run` checks the record's preconditions, executes the three
parts, and writes their raw evidence into one new directory under :data:`RUNS_DIR`.
Every input, edit, and expected refusal is read from the freeze record, not from a
copy in this module. The second E01-A render runs in a second Python process with a
different ``PYTHONHASHSEED``. A precondition that fails stops the run before any part
starts, and the parts are recorded as REFUSED.

**Judge.** :func:`judge` computes the verdict of every acceptance criterion from the
raw evidence a run wrote: the bytes of the rendered files, the recorded refusals, and
the values the run recorded. :func:`check_run` compares that with the outcome states
and the result page the run committed, so a committed run is checked again without
executing it. A difference is a finding.

**Versioned analysis.** A run executes the latest E01 freeze revision,
:data:`CURRENT_REVISION`. A committed run is judged by the analysis of the revision it
names: :func:`judge`, :func:`result_page`, and the precondition check each take the
revision from the record, so the first run, registered under revision 1, is checked
by revision 1's criteria and page, byte for byte, and is never reinterpreted.

**Execution identity, from revision 2.** The runner is a pinned input of the record,
within the record's material scope. Before it starts, a run checks that the runner
module and the ``inferops`` package it imported are the ones in the checked-out tree,
that the record is registered and unedited, and that no material file differs from
the record - added files included. During the run it records every repository module
file it and its second process loaded, with its content digest; a loaded file outside
the frozen scope is an abort condition.

**What this does not do.** It renders nothing for E01-D, contacts no cluster or
network, and reads no model. It does not decide whether a moved input is material: a
moved input refuses the run. It cannot stop a full run of the parts outside this
command - in a throwaway repository, say. The record's rule against such previews is a
procedure, and this module does not enforce it.
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

import yaml

import inferops
from inferops.domain.environment import (
    EnvironmentBinding,
    EnvironmentBindingError,
    parse_environment_binding,
)
from inferops.domain.release import GitRevision, binding_digest, contract_digest
from inferops.domain.render import (
    DERIVED_HELM_VALUES,
    HELM_VALUE_DISPOSITIONS,
    RELEASE_FILE_NAME,
    RENDER_FIELD_OWNERSHIP,
    VALUES_FILE_NAME,
    GeneratedHelmValues,
    GeneratedRelease,
    HelmValuesRenderer,
    PlatformDefaults,
    RenderRefused,
    admit_manual_values,
    generate_release,
    write_release,
)
from inferops.domain.workload import (
    CompatibilityMatrixLoader,
    DnsLabel,
    WorkloadContract,
    get_matrix_loader,
    parse_workload_contract,
    set_matrix_loader,
)
from tools.experiment_freeze import (
    REGISTRY_PATH,
    changed_inputs,
    check_repository,
    content_digest,
)

# The freeze record names this reader for the platform defaults: "the api block of
# charts/inferops-llm/values.yaml, read as tools/generated_release reads them". The
# run calls that reader and does not copy it.
from tools.generated_release.core import _chart_api_defaults

__all__ = [
    "API_VERSION",
    "CHART_DEFAULTS",
    "CRITERIA",
    "CURRENT_REVISION",
    "FREEZE_PATH",
    "FREEZE_RECORDS",
    "HASH_SEEDS",
    "KIND",
    "MERGED_REF",
    "OUTCOME_STATES",
    "PARTS",
    "REPO_ROOT",
    "RUNS_DIR",
    "Criterion",
    "Judgement",
    "PatchError",
    "RunFinding",
    "apply_patch",
    "check_run",
    "committed_runs",
    "deep_merge",
    "execute_run",
    "identity_conditions",
    "imported_package",
    "judge",
    "leaves",
    "load_freeze",
    "loaded_modules",
    "package_directories",
    "precondition_findings",
    "render_second",
    "result_page",
    "run_id_problem",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: Every E01 freeze revision a committed run may name, by revision.
FREEZE_RECORDS: Final[Mapping[int, str]] = {
    1: "docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json",
    2: "docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json",
}

#: The revision a new run executes: the latest merged one.
CURRENT_REVISION: Final = 2

#: The freeze record a new run executes.
FREEZE_PATH: Final = FREEZE_RECORDS[CURRENT_REVISION]

#: The runner module, as a repository path, which a run from revision 2 on must have
#: imported from the checked-out tree.
RUNNER_FILE: Final = "tools/experiment_e01/core.py"

#: A hand-written string is compared with a generated contract value only when the
#: value is at least this long, as the V1 compatibility record check does: shorter
#: values - ``local``, ``real``, ``6`` - occur inside unrelated strings.
PIN_MIN_LENGTH: Final = 8

#: Where every run's evidence directory is written, by repository path.
RUNS_DIR: Final = "docs/proof/experiments/v2-e01/runs"

#: The chart values file whose api block holds the platform defaults, and whose
#: whole content is the chart's defaults for the E01-A merge.
CHART_DEFAULTS: Final = "charts/inferops-llm/values.yaml"

#: The static parts this module runs. E01-D is never run here.
PARTS: Final[tuple[str, ...]] = ("E01-A", "E01-B", "E01-C")

#: The outcome states the freeze record defines, in its order.
OUTCOME_STATES: Final[tuple[str, ...]] = (
    "PASSED",
    "FAILED",
    "INCONCLUSIVE",
    "REFUSED",
    "ABORTED",
)

#: The ``PYTHONHASHSEED`` of the process that writes render-a and of the second
#: process that writes render-b. They differ, as E01-A step 4 requires.
HASH_SEEDS: Final[Mapping[str, str]] = {"render-a": "1", "render-b": "2"}

API_VERSION: Final = "inferops.io/v1alpha1"
KIND: Final = "ExperimentRun"

MANIFEST: Final = "run.v1alpha1.json"
COMMANDS: Final = "commands.txt"
REFUSALS: Final = "refusals.json"
RESULT: Final = "result.md"
RENDER_A: Final = "render-a"
RENDER_B: Final = "render-b"
MUTATION: Final = "mutation"
RENDERED_FILES: Final[tuple[str, ...]] = (str(VALUES_FILE_NAME), RELEASE_FILE_NAME)

#: A run identifier: the run's UTC date, the parts it executes, and a sequence number.
_RUN_ID: Final = re.compile(r"^(?P<date>[0-9]{8})-e01-abc-(?P<sequence>[1-9][0-9]*)$")

#: The binding version every committed binding declares, as E01-AC3 names it.
BINDING_API_VERSION: Final = "inferops.io/v1alpha1"


@dataclass(frozen=True)
class Criterion:
    """One acceptance criterion of the freeze record, and the part it belongs to."""

    criterion_id: str
    part: str


#: The criteria this module judges, in the freeze record's order.
CRITERIA: Final[tuple[Criterion, ...]] = (
    Criterion("E01-AC1", "E01-A"),
    Criterion("E01-AC2", "E01-A"),
    Criterion("E01-AC3", "E01-A"),
    Criterion("E01-AC4", "E01-A"),
    Criterion("E01-AC5", "E01-A"),
    Criterion("E01-AC6", "E01-B"),
    Criterion("E01-AC7", "E01-C"),
)


@dataclass(frozen=True)
class RunFinding:
    """One way a committed run disagrees with its own evidence."""

    run: str
    location: str
    detail: str


@dataclass(frozen=True)
class Judgement:
    """The verdict of every criterion and the outcome of every part, for one run.

    A verdict is True when the criterion held, False when it did not, and None when
    the evidence it needs is absent. ``basis`` gives the evidence each verdict rests
    on, as short sentences.
    """

    verdicts: Mapping[str, bool | None]
    basis: Mapping[str, tuple[str, ...]]
    outcomes: Mapping[str, str]


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


class PatchError(ValueError):
    """A JSON Patch operation that cannot be applied to the document."""


def _pointer(path: str) -> list[str]:
    if not path.startswith("/"):
        raise PatchError(f"{path!r} is not a JSON Pointer")
    return [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]


def _patch_value(operation: Mapping[str, Any]) -> Any:
    if "value" not in operation:
        raise PatchError(
            f"{operation.get('path')}: an {operation.get('op')} needs a value"
        )
    return copy.deepcopy(operation["value"])


def apply_patch(document: Any, operations: Sequence[Mapping[str, Any]]) -> Any:
    """``document`` with the JSON Patch ``add``, ``remove``, and ``replace`` applied.

    The operations are the three the freeze record uses, with the meaning RFC 6902
    gives them, applied in order to a copy. The input is not changed.

    Raises:
        PatchError: an operation is unknown, or its path does not resolve.
    """
    patched = copy.deepcopy(document)
    for operation in operations:
        op = operation.get("op")
        parts = _pointer(str(operation.get("path")))
        parent: Any = patched
        for part in parts[:-1]:
            if isinstance(parent, dict) and part in parent:
                parent = parent[part]
            elif (
                isinstance(parent, list)
                and part.isascii()
                and part.isdigit()
                and int(part) < len(parent)
            ):
                parent = parent[int(part)]
            else:
                raise PatchError(f"{operation.get('path')}: {part!r} does not exist")
        last = parts[-1]
        if not isinstance(parent, dict):
            raise PatchError(f"{operation.get('path')}: the target is not an object")
        if op == "add":
            parent[last] = _patch_value(operation)
        elif op in {"remove", "replace"}:
            if last not in parent:
                raise PatchError(f"{operation.get('path')}: {last!r} does not exist")
            if op == "remove":
                del parent[last]
            else:
                parent[last] = _patch_value(operation)
        else:
            raise PatchError(f"{op!r} is not an operation this run applies")
    return patched


def leaves(document: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every leaf of a document by dotted path. An empty mapping is a leaf."""
    if isinstance(document, Mapping) and document:
        for key, value in document.items():
            yield from leaves(value, f"{prefix}{key}.")
    else:
        yield prefix.rstrip("."), document


def deep_merge(base: Mapping[str, Any], *overlays: Mapping[str, Any]) -> dict[str, Any]:
    """Values files merged the way Helm merges them: mappings by key, the rest replaced."""
    merged: dict[str, Any] = copy.deepcopy(dict(base))
    for overlay in overlays:
        for key, value in overlay.items():
            current = merged.get(key)
            if isinstance(current, Mapping) and isinstance(value, Mapping):
                merged[key] = deep_merge(current, value)
            else:
                merged[key] = copy.deepcopy(value)
    return merged


_ABSENT: Final = {"present": False}


def _side(found: Mapping[str, Any], path: str) -> dict[str, Any]:
    return {"present": True, "value": found[path]} if path in found else dict(_ABSENT)


def leaf_differences(before: Any, after: Any) -> list[dict[str, Any]]:
    """Every leaf path whose value differs, or that only one document has, sorted."""
    left, right = dict(leaves(before)), dict(leaves(after))
    return [
        {"path": path, "before": _side(left, path), "after": _side(right, path)}
        for path in sorted(set(left) | set(right))
        if (path in left) != (path in right) or left.get(path) != right.get(path)
    ]


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_freeze(
    root: Path = REPO_ROOT, revision: int = CURRENT_REVISION
) -> dict[str, Any]:
    """The E01 freeze record of ``revision``, read from ``root``: by default the one a
    new run executes."""
    path = FREEZE_RECORDS[revision]
    document = json.loads((root / path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} is not a JSON object")
    return document


def _revision(freeze: Mapping[str, Any]) -> int:
    revision = freeze["metadata"]["revision"]
    if revision not in FREEZE_RECORDS:
        raise ValueError(f"E01 freeze revision {revision!r} has no analysis")
    return int(revision)


def _part(freeze: Mapping[str, Any], part_id: str) -> Mapping[str, Any]:
    for part in freeze["parts"]:
        if part["id"] == part_id:
            found: Mapping[str, Any] = part
            return found
    raise KeyError(part_id)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


@contextmanager
def _matrix(root: Path, path: str) -> Iterator[None]:
    """The compatibility matrix at ``path`` set for the workload domain, then restored."""
    try:
        previous: CompatibilityMatrixLoader | None = get_matrix_loader()
    except ValueError:
        previous = None
    matrix = json.loads((root / path).read_text(encoding="utf-8"))
    set_matrix_loader(CompatibilityMatrixLoader(matrix))
    try:
        yield
    finally:
        if previous is not None:
            set_matrix_loader(previous)


def _defaults(root: Path, revision: str) -> PlatformDefaults:
    return _chart_api_defaults(root / CHART_DEFAULTS, revision)


@dataclass(frozen=True)
class _Rendered:
    contract: WorkloadContract
    bindings: tuple[EnvironmentBinding, ...]
    generated: GeneratedRelease


def _render(
    root: Path,
    revision: str,
    contract_document: Any,
    binding_documents: Sequence[Any],
    binding_name: str,
    record: Callable[[str], None] | None = None,
) -> _Rendered:
    """Parse the documents and call generate_release, as E01-A steps 1 and 2 say.

    ``record`` is told each step's name before the step runs, so a refusal is
    attributed to the step that raised it.
    """
    note = record or (lambda step: None)
    note("parse_workload_contract")
    contract = parse_workload_contract(contract_document)
    note("parse_environment_binding")
    bindings = tuple(parse_environment_binding(d) for d in binding_documents)
    note("generate_release")
    generated = generate_release(
        HelmValuesRenderer(GitRevision(revision)),
        contract,
        _defaults(root, revision),
        bindings,
        binding_name=DnsLabel(binding_name),
    )
    return _Rendered(contract, bindings, generated)


def _a_inputs(root: Path, freeze: Mapping[str, Any]) -> dict[str, Any]:
    inputs = _part(freeze, "E01-A")["inputs"]
    return {
        "matrix": inputs["compatibilityMatrix"],
        "contract": _load_yaml(root / inputs["workloadContract"]),
        "bindings": [_load_yaml(root / path) for path in inputs["environmentBindings"]],
        "bindingName": inputs["bindingName"],
        "handWritten": _load_yaml(root / inputs["handWrittenValues"]),
        "v1Values": _load_yaml(root / inputs["v1Values"]),
    }


def imported_package(root: Path) -> str:
    """Where the ``inferops`` package this process imported lives, said safely.

    The repository path when it is inside ``root``; otherwise a sentence that names
    no host path.
    """
    location = Path(inferops.__file__).resolve().parent
    try:
        return location.relative_to(root.resolve()).as_posix()
    except ValueError:
        return "outside the checked-out tree"


def package_directories(freeze: Mapping[str, Any]) -> tuple[str, ...]:
    """The repository directories of the record's package roots, such as
    ``src/inferops/`` and ``tools/``: where a loaded module is the experiment's own.

    Only these count. A virtual environment inside the checkout, ``.venv/``, holds
    third-party packages that uv.lock pins by version, not by content, so a module
    loaded from it is not compared with the pins.
    """
    roots = freeze.get("materialScope", {}).get("packageRoots", {})
    return tuple(
        sorted(
            f"{PurePosixPath(directory, package).as_posix()}/"
            for package, directory in roots.items()
        )
    )


def loaded_modules(root: Path, packages: Sequence[str]) -> dict[str, str]:
    """Every module file this process has loaded from the package directories under
    ``root``, by repository path, with its content digest. A module loaded from
    anywhere else - another checkout, the standard library, a virtual environment
    inside ``root`` - is not listed."""
    base = root.resolve()
    found: dict[str, str] = {}
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if not name:
            continue
        path = Path(name).resolve()
        try:
            relative = path.relative_to(base).as_posix()
        except ValueError:
            continue
        if (
            relative.startswith(tuple(packages))
            and path.is_file()
            and path.suffix == ".py"
        ):
            found[relative] = content_digest(path.read_bytes())
    return dict(sorted(found.items()))


#: The abort conditions the execution identity can meet, from revision 2.
LOADED_OUTSIDE: Final = (
    "a module file the run loaded is not a pinned input with its pinned content"
)
SECOND_OUTSIDE: Final = (
    "the second process imported the runner or the inferops package from outside "
    "the checked-out tree"
)


def identity_conditions(
    manifest: Mapping[str, Any], freeze: Mapping[str, Any]
) -> tuple[list[str], list[str]]:
    """From a revision-2 manifest's own records: the loaded module files that are not
    pinned inputs with their pinned content, and the abort conditions that gives.

    A condition applies only to a run whose preconditions held; a refused run ran no
    part, so what it loaded decides nothing.
    """
    identity = manifest["executionIdentity"]
    pinned = {item["path"]: item["sha256"] for item in freeze["pinnedInputs"]}
    outside = sorted(
        {
            path
            for loaded in (
                identity["loadedModules"],
                identity["loadedModulesSecondProcess"],
            )
            for path, digest in loaded.items()
            if pinned.get(path) != digest
        }
    )
    if manifest["preconditions"]["findings"]:
        return outside, []
    conditions = [LOADED_OUTSIDE] if outside else []
    second = (
        manifest.get("observations", {}).get("E01-A", {}).get("renderB") or {}
    ).get("reported") or {}
    if second and (
        second.get("runnerInCheckout") is not True
        or second.get("inferopsPackage") != "src/inferops"
    ):
        conditions.append(SECOND_OUTSIDE)
    return outside, conditions


def _runner_in_checkout(root: Path) -> bool:
    try:
        return (
            Path(__file__).resolve().relative_to(root.resolve()).as_posix()
            == RUNNER_FILE
        )
    except ValueError:
        return False


def render_second(root: Path, revision: str, out: Path) -> dict[str, Any]:
    """E01-A step 4: the three steps again, in this process, written to ``out``."""
    freeze = load_freeze(root)
    a = _a_inputs(root, freeze)
    with _matrix(root, a["matrix"]):
        rendered = _render(
            root, revision, a["contract"], a["bindings"], a["bindingName"]
        )
    write_release(rendered.generated, out)
    return {
        "pythonHashSeed": os.environ.get("PYTHONHASHSEED"),
        "hashRandomization": bool(sys.flags.hash_randomization),
        "inferopsPackage": imported_package(root),
        "runnerInCheckout": _runner_in_checkout(root),
        "loadedModules": loaded_modules(root, package_directories(freeze)),
    }


# --------------------------------------------------------------------------
# Preconditions
# --------------------------------------------------------------------------


def run_id_problem(run_id: str, started: datetime.datetime) -> str | None:
    """Why ``run_id`` is not a valid identifier for a run started at ``started``."""
    match = _RUN_ID.match(run_id)
    if match is None:
        return "a run identifier is YYYYMMDD-e01-abc-N, with N from 1"
    if match["date"] != started.astimezone(datetime.UTC).strftime("%Y%m%d"):
        return "the identifier's date is not the run's UTC date"
    return None


def precondition_findings(
    *,
    head: str,
    merged: bool,
    freeze_at_head: bool,
    status: Sequence[str],
    moved_inputs: Sequence[str],
    parts: Sequence[str],
    package_in_checkout: bool = True,
    revision: int,
    runner_in_checkout: bool = True,
    record_registered: bool = True,
) -> list[str]:
    """Each freeze precondition the observed state fails, in the record's order.

    Every argument is an observation the caller made: the commit checked out, whether
    it is reachable from the merged branch, whether the freeze record is in it, the
    porcelain status lines, the material files that differ from the record, the parts
    the run executes, and whether the ``inferops`` package imported is the one in the
    checked-out tree's ``src``. From ``revision`` 2: whether the runner module is the
    checked-out tree's, and whether the record is registered and unedited. Revision 1's
    findings are the ones that revision's runs recorded, word for word.
    """
    freeze_path = FREEZE_RECORDS[revision]
    findings = []
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        findings.append("the executing commit is not a full Git revision")
    if not merged:
        findings.append("the executing commit is not merged")
    if not freeze_at_head:
        findings.append(f"the executing commit holds no {freeze_path}")
    if status:
        findings.append("the working tree is not clean")
    if moved_inputs and revision == 1:
        findings.append(
            f"{len(moved_inputs)} pinned input(s) differ from their pins, and no "
            "merged revision classifies them"
        )
    elif moved_inputs:
        findings.append(
            f"{len(moved_inputs)} material file(s) differ from the freeze record - "
            "changed, absent, added, or out of scope - and no merged revision "
            "classifies them"
        )
    if "E01-D" in parts:
        findings.append("E01-D is refused while its environment identity is pending")
    if not package_in_checkout:
        findings.append(
            "the inferops package imported is not the one in the checked-out tree"
        )
    if revision >= 2 and not runner_in_checkout:
        findings.append(
            "the runner imported is not the one in the checked-out tree, at "
            f"{RUNNER_FILE}"
        )
    if revision >= 2 and not record_registered:
        findings.append(
            f"{freeze_path} is not registered, or differs from its registered pin"
        )
    return findings


#: The branch a run's commit must be merged into. ``check_run`` refuses a committed
#: run that names another, because a run on any other reference proves no merge.
MERGED_REF: Final = "origin/main"


def _recorded_findings(manifest: Mapping[str, Any], revision: int) -> list[str]:
    """The precondition findings the manifest's own observations give."""
    seen = manifest["preconditions"]
    package = seen.get("inferopsPackage", "src/inferops")
    return precondition_findings(
        head=manifest["executingRevision"],
        merged=seen["executingRevisionMerged"],
        freeze_at_head=seen["freezeRecordAtRevision"],
        status=seen["statusBefore"],
        moved_inputs=seen["movedPinnedInputs"],
        parts=manifest["metadata"]["parts"],
        package_in_checkout=package == "src/inferops",
        revision=revision,
        # Revision 1's runs did not record these checks; from revision 2 they must.
        runner_in_checkout=True if revision == 1 else seen["runnerInCheckout"],
        record_registered=True if revision == 1 else seen["freezeRecordRegistered"],
    )


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------


class _Log:
    """The commands of one run, in order, as commands.txt records them."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, command: str) -> None:
        self.lines.append(command)


def _git(root: Path, log: _Log, *arguments: str) -> subprocess.CompletedProcess[str]:
    log.add("git " + " ".join(arguments))
    return subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, check=False
    )


def _status(root: Path, log: _Log) -> list[str]:
    result = _git(root, log, "status", "--porcelain", "--untracked-files=all")
    return [line for line in result.stdout.splitlines() if line]


def _tool_version(command: Sequence[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError:
        return "not found"
    return result.stdout.strip() or "not reported"


def _distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def _digest_or_none(path: Path) -> str | None:
    return content_digest(path.read_bytes()) if path.is_file() else None


def _runner_files() -> dict[str, str]:
    here = Path(__file__).resolve().parent
    return {
        path.name: content_digest(path.read_bytes())
        for path in sorted(here.glob("*.py"))
    }


def _refusal(error: BaseException) -> dict[str, Any]:
    """A refusal as E01-C step 3 records it."""
    recorded: dict[str, Any] = {"exception": type(error).__name__}
    if isinstance(error, RenderRefused):
        recorded["findings"] = [
            {
                "rule": finding.rule_id,
                "category": finding.category.value,
                "code": finding.code,
                "field": finding.field,
                "reason": finding.reason,
            }
            for finding in error.findings
        ]
    elif isinstance(error, EnvironmentBindingError):
        recorded.update(code=error.code, field=error.field, reason=error.reason)
    else:
        recorded["message"] = str(error)
    return recorded


def _case_inputs(
    root: Path, case: Mapping[str, Any], a: Mapping[str, Any]
) -> dict[str, Any]:
    """A case's documents: the pinned files with its edits, else the E01-A inputs."""
    given = case.get("inputs", {})

    def edited(key: str) -> Any:
        spec = given[key]
        return apply_patch(_load_yaml(root / spec["file"]), spec.get("edits", []))

    return {
        "contract": edited("workloadContract")
        if "workloadContract" in given
        else a["contract"],
        "bindings": (
            [edited("environmentBinding")]
            if "environmentBinding" in given
            else a["bindings"]
        ),
        "bindingName": given.get("bindingName", a["bindingName"]),
        "handWritten": (
            edited("handWrittenValues")
            if "handWrittenValues" in given
            else a["handWritten"]
        ),
    }


def _execute_case(
    root: Path,
    revision: str,
    case: Mapping[str, Any],
    a: Mapping[str, Any],
    generated_values: GeneratedHelmValues,
    out: Path,
) -> dict[str, Any]:
    """One execution of one E01-C case: the step it names, and what happened."""
    inputs = _case_inputs(root, case, a)
    steps: list[str] = []
    refusal: dict[str, Any] | None = None
    try:
        if case["refusedBy"] == "admit_manual_values":
            steps.append("admit_manual_values")
            admit_manual_values(generated_values, inputs["handWritten"])
        else:
            rendered = _render(
                root,
                revision,
                inputs["contract"],
                inputs["bindings"],
                inputs["bindingName"],
                steps.append,
            )
            steps.append("write_release")
            write_release(rendered.generated, out)
    except Exception as error:  # every refusal is recorded, of whatever type
        refusal = {"step": steps[-1] if steps else None, **_refusal(error)}
    return {
        "steps": steps,
        "refusal": refusal,
        "outputDirectoryExists": out.exists(),
    }


def _write(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)


def _json(document: Any) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _run_parts(
    root: Path,
    revision: str,
    evidence: Path,
    scratch: Path,
    freeze: Mapping[str, Any],
    log: _Log,
    package: str,
    observations: dict[str, Any],
    refusals: list[dict[str, Any]],
) -> None:
    """Execute E01-A, E01-B, and E01-C, filling ``observations`` and ``refusals``.

    Both are filled as each step completes, so a step that raises leaves every
    earlier observation recorded.
    """
    a = _a_inputs(root, freeze)
    evidence_rel = evidence.relative_to(root).as_posix()

    # E01-A steps 1 to 3, in this process.
    log.add(f"# in process: E01-A steps 1 to 3, written to {evidence_rel}/{RENDER_A}")
    with _matrix(root, a["matrix"]):
        first = _render(root, revision, a["contract"], a["bindings"], a["bindingName"])
    write_release(first.generated, evidence / RENDER_A)

    # E01-A step 4, in a second process with another hash seed.
    child = [
        "-m",
        package,
        "--render-second",
        f"{evidence_rel}/{RENDER_B}",
        "--root",
        ".",
        "--revision",
        revision,
    ]
    log.add(f"PYTHONHASHSEED={HASH_SEEDS['render-b']} python " + " ".join(child))
    second = subprocess.run(
        [sys.executable, *child],
        cwd=root,
        env={**os.environ, "PYTHONHASHSEED": HASH_SEEDS["render-b"]},
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        reported = json.loads(second.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        reported = None
    observations["E01-A"] = {
        "renderA": {
            "pythonHashSeed": os.environ.get("PYTHONHASHSEED"),
            "hashRandomization": bool(sys.flags.hash_randomization),
        },
        "renderB": {"exitStatus": second.returncode, "reported": reported},
        # Step 6: values computed apart from the release.
        "contractDigest": str(contract_digest(first.contract)),
        "binding": {
            "name": a["bindingName"],
            "apiVersion": BINDING_API_VERSION,
            "sha256": str(binding_digest(first.bindings[0])),
        },
    }

    # E01-A step 7: the hand-written values admitted beside the render-a values.
    log.add("# in process: E01-A steps 6 to 9 and E01-B")
    try:
        admit_manual_values(first.generated.values, a["handWritten"])
        admission: dict[str, Any] = {"admitted": True, "refusal": None}
    except RenderRefused as error:
        admission = {"admitted": False, "refusal": _refusal(error)}
    observations["E01-A"]["admission"] = admission

    # E01-A step 8: every chart value a workload-intent context value renders to,
    # and, from revision 2, every value derived from workload-intent values only.
    owner = {row.name: row.layer.value for row in RENDER_FIELD_OWNERSHIP}
    targets = {
        target
        for name, disposition in HELM_VALUE_DISPOSITIONS.items()
        if owner.get(name) == "workload-intent"
        for target in disposition.targets
    }
    if _revision(freeze) >= 2:
        targets |= {
            path
            for path, derived in DERIVED_HELM_VALUES.items()
            if all(owner.get(name) == "workload-intent" for name in derived.sources)
        }
        # E01-A step 9 of revision 2: no hand-written string restates one of them.
        generated_values = dict(leaves(first.generated.values.as_document()))
        observations["E01-A"]["restatedPins"] = [
            {"path": path, "restates": restated}
            for path, value in leaves(a["handWritten"])
            if (
                restated := sorted(
                    target
                    for target in targets
                    if isinstance(value, str)
                    and isinstance(generated_values.get(target), str)
                    and len(generated_values[target]) >= PIN_MIN_LENGTH
                    and generated_values[target] in value
                )
            )
        ]
    observations["E01-A"]["workloadIntentTargets"] = sorted(targets)

    # E01-A step 9: both merges, and every value that differs.
    chart_defaults = _load_yaml(root / CHART_DEFAULTS)
    generated = yaml.safe_load(
        (evidence / RENDER_A / str(VALUES_FILE_NAME)).read_bytes()
    )
    v2 = deep_merge(chart_defaults, generated, a["handWritten"])
    v1 = deep_merge(chart_defaults, a["v1Values"])
    observations["E01-A"]["mergedDifferences"] = [
        {"path": d["path"], "v2": d["after"], "v1": d["before"]}
        for d in leaf_differences(v1, v2)
    ]

    # E01-B: the mutation, applied before parsing, rendered and written.
    b = _part(freeze, "E01-B")
    mutated = apply_patch(a["contract"], b["inputs"]["mutation"])
    with _matrix(root, a["matrix"]):
        changed = _render(root, revision, mutated, a["bindings"], a["bindingName"])
    write_release(changed.generated, evidence / MUTATION)
    observations["E01-B"] = {
        "mutatedContractDigest": str(contract_digest(changed.contract))
    }

    # E01-C: each case twice; an output directory must never appear.
    log.add("# in process: E01-C, each case twice, outputs under a temporary directory")
    with _matrix(root, a["matrix"]):
        for case in _part(freeze, "E01-C")["cases"]:
            attempts = []
            for attempt in (1, 2):
                out = scratch / f"{case['id']}-attempt-{attempt}"
                attempts.append(
                    {
                        "attempt": attempt,
                        **_execute_case(
                            root, revision, case, a, first.generated.values, out
                        ),
                    }
                )
            refusals.append({"case": case["id"], "attempts": attempts})


def execute_run(
    root: Path,
    run_id: str,
    *,
    merged_ref: str = MERGED_REF,
    prelude: Sequence[str] = (),
    invocation: str = "",
    package: str = "tools.experiment_e01",
    source_root: Path | None = None,
) -> tuple[Path, Judgement]:
    """Run the static parts once and write the evidence directory for ``run_id``.

    ``prelude`` is the commands the operator ran to prepare the checkout, stated by
    the operator; commands.txt marks them as stated and not executed by the runner.
    ``invocation`` is the command line that started this run. ``merged_ref`` and
    ``source_root`` exist for the test suite: the command uses ``origin/main`` and
    requires the ``inferops`` package to be the one under ``root/src``, and
    ``check_run`` refuses a committed run that named another reference.

    Raises:
        ValueError: ``run_id`` is not valid for a run started now. Nothing is written.
        FileExistsError: the evidence directory already exists. Nothing is written.
    """
    started = datetime.datetime.now(datetime.UTC)
    problem = run_id_problem(run_id, started)
    if problem is not None:
        raise ValueError(problem)
    evidence = root / RUNS_DIR / run_id
    if evidence.exists():
        raise FileExistsError(f"{RUNS_DIR}/{run_id} already exists")
    log = _Log()
    for line in prelude:
        log.add(f"# stated by the operator: {line}")
    log.add(invocation)

    freeze = load_freeze(root)
    revision = _revision(freeze)
    head = _git(root, log, "rev-parse", "HEAD").stdout.strip()
    merged = (
        _git(root, log, "merge-base", "--is-ancestor", "HEAD", merged_ref).returncode
        == 0
    )
    merged_at = _git(root, log, "rev-parse", merged_ref).stdout.strip()
    freeze_at_head = (
        _git(root, log, "cat-file", "-e", f"HEAD:{FREEZE_PATH}").returncode == 0
    )
    status_before = _status(root, log)
    log.add(
        "# in process: tools.experiment_freeze.changed_inputs over the freeze "
        f"record, the check behind python -m tools.experiment_freeze --changes "
        f"{FREEZE_PATH}"
    )
    inventory = changed_inputs(freeze, root)
    moved = [change.path for change in inventory]
    log.add(
        "# in process: tools.experiment_freeze.check_repository, the check behind "
        "python -m tools.experiment_freeze --check"
    )
    registered = not [f for f in check_repository(root) if f.record == FREEZE_PATH]
    location = imported_package(source_root or root)
    runner_here = _runner_in_checkout(source_root or root)
    findings = precondition_findings(
        head=head,
        merged=merged,
        freeze_at_head=freeze_at_head,
        status=status_before,
        moved_inputs=moved,
        parts=PARTS,
        package_in_checkout=location == "src/inferops",
        revision=revision,
        runner_in_checkout=runner_here,
        record_registered=registered,
    )

    evidence.mkdir(parents=True)
    observations: dict[str, Any] = {}
    refusals: list[dict[str, Any]] = []
    scratch_removed = None
    error: dict[str, str] | None = None
    if not findings:
        scratch = Path(tempfile.mkdtemp(prefix="e01-run-"))
        try:
            _run_parts(
                root,
                head,
                evidence,
                scratch,
                freeze,
                log,
                package,
                observations,
                refusals,
            )
        except Exception as raised:  # recorded, and judged as missing evidence
            error = {"exception": type(raised).__name__, "message": str(raised)}
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
            scratch_removed = not scratch.exists()
        if error is None:
            _write(evidence / REFUSALS, _json(refusals))

    head_after = _git(root, log, "rev-parse", "HEAD").stdout.strip()
    status_after = _status(root, log)
    prefix = f"?? {RUNS_DIR}/{run_id}/"
    aborts = []
    if head_after != head:
        aborts.append("the checked-out commit changed while the run executed")
    if any(not line.startswith(prefix) for line in status_after):
        aborts.append("a file outside the run's evidence directory changed")
    if scratch_removed is False:
        aborts.append("the run's temporary directory could not be removed")
    loaded = loaded_modules(source_root or root, package_directories(freeze))
    second = (observations.get("E01-A", {}).get("renderB") or {}).get("reported") or {}
    loaded_second = second.get("loadedModules") or {}

    _write(evidence / COMMANDS, ("\n".join(log.lines) + "\n").encode("utf-8"))
    files = {
        path.relative_to(evidence).as_posix(): _sha256(path.read_bytes())
        for path in sorted(evidence.rglob("*"))
        if path.is_file()
    }
    manifest: dict[str, Any] = {
        "apiVersion": API_VERSION,
        "kind": KIND,
        "metadata": {
            "runId": run_id,
            "experiment": freeze["metadata"]["experiment"],
            "freezeRecord": FREEZE_PATH,
            "freezeRevision": freeze["metadata"]["revision"],
            "freezeContentSha256": content_digest((root / FREEZE_PATH).read_bytes()),
            "parts": list(PARTS),
            "startedAt": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "finishedAt": datetime.datetime.now(datetime.UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        },
        "executingRevision": head,
        "preconditions": {
            "mergedRef": merged_ref,
            "mergedRefRevision": merged_at,
            "executingRevisionMerged": merged,
            "freezeRecordAtRevision": freeze_at_head,
            "statusBefore": status_before,
            "movedPinnedInputs": moved,
            "inventoryChanges": [
                {"path": change.path, "kind": change.kind} for change in inventory
            ],
            "inferopsPackage": location,
            "runnerInCheckout": runner_here,
            "freezeRecordRegistered": registered,
            "findings": findings,
        },
        "host": {
            "operatingSystem": platform.system(),
            "operatingSystemVersion": platform.version(),
            "python": platform.python_version(),
            "uv": _tool_version(["uv", "--version"]),
        },
        "runner": {"package": package, "files": _runner_files()},
        "executionIdentity": {
            "runnerFile": RUNNER_FILE
            if runner_here
            else "outside the checked-out tree",
            "inferopsPackage": location,
            "inferopsVersion": _distribution_version("inferops"),
            "registry": {
                "path": REGISTRY_PATH,
                "contentSha256": _digest_or_none(root / REGISTRY_PATH),
            },
            "loadedModules": loaded,
            "loadedModulesSecondProcess": loaded_second,
        },
        "observations": observations,
        "error": error,
        "abortChecks": {
            "revisionAfter": head_after,
            "statusAfter": status_after,
            "temporaryDirectoryRemoved": scratch_removed,
            "conditions": aborts,
        },
        "files": files,
    }
    outside, identity_aborts = identity_conditions(manifest, freeze)
    manifest["executionIdentity"]["loadedOutsideFrozenInputs"] = outside
    manifest["abortChecks"]["conditions"].extend(identity_aborts)
    try:
        judgement = judge(evidence, freeze, manifest)
    except Exception as raised:  # the run is still recorded, and answers nothing
        manifest["error"] = manifest["error"] or {
            "exception": type(raised).__name__,
            "message": str(raised),
        }
        judgement = Judgement(
            verdicts=dict.fromkeys((c.criterion_id for c in CRITERIA), None),
            basis={c.criterion_id: ("the judge raised",) for c in CRITERIA},
            outcomes=dict.fromkeys(PARTS, "INCONCLUSIVE"),
        )
    manifest["criteria"] = [
        {
            "id": criterion.criterion_id,
            "holds": judgement.verdicts[criterion.criterion_id],
        }
        for criterion in CRITERIA
    ]
    manifest["outcomes"] = dict(judgement.outcomes)
    _write(evidence / MANIFEST, _json(manifest))
    _write(evidence / RESULT, result_page(manifest, freeze, judgement).encode("utf-8"))
    return evidence, judgement


# --------------------------------------------------------------------------
# Judging
# --------------------------------------------------------------------------


def _bytes(evidence: Path, directory: str, name: str) -> bytes | None:
    path = evidence / directory / name
    return path.read_bytes() if path.is_file() else None


def _mapping(data: bytes | None) -> Mapping[str, Any] | None:
    """A YAML document's mapping, or None when it is absent, unreadable, or not one."""
    try:
        document = yaml.safe_load(data or b"")
    except yaml.YAMLError:
        return None
    return document if isinstance(document, Mapping) else None


def _field(document: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if not isinstance(document, Mapping) or part not in document:
            return None
        document = document[part]
    return document


def _judge_a(
    evidence: Path, manifest: Mapping[str, Any], freeze_revision: int = 1
) -> dict[str, tuple[bool | None, list[str]]]:
    seen = manifest.get("observations", {}).get("E01-A")
    out: dict[str, tuple[bool | None, list[str]]] = {}
    files_a = {name: _bytes(evidence, RENDER_A, name) for name in RENDERED_FILES}
    files_b = {name: _bytes(evidence, RENDER_B, name) for name in RENDERED_FILES}
    if seen is None or None in files_a.values() or None in files_b.values():
        for criterion in CRITERIA[:5]:
            out[criterion.criterion_id] = (None, ["the E01-A evidence is incomplete"])
        return out
    release_a = _mapping(files_a[RELEASE_FILE_NAME])
    release_b = _mapping(files_b[RELEASE_FILE_NAME])
    values_a = _mapping(files_a[str(VALUES_FILE_NAME)])
    if release_a is None or release_b is None or values_a is None:
        for criterion in CRITERIA[:5]:
            out[criterion.criterion_id] = (
                None,
                ["an E01-A file is not a YAML mapping"],
            )
        return out

    basis = []
    same = True
    for name in RENDERED_FILES:
        left, right = files_a[name] or b"", files_b[name] or b""
        equal = left == right
        same = same and equal
        basis.append(
            f"{name}: {'byte-identical' if equal else 'differs'}; "
            f"SHA-256 {_sha256(left)} and {_sha256(right)}"
        )
    id_a = _field(release_a, "metadata.releaseId")
    id_b = _field(release_b, "metadata.releaseId")
    same = same and id_a is not None and id_a == id_b
    basis.append(f"metadata.releaseId: {id_a} and {id_b}")
    second = seen.get("renderB", {})
    seeds = (
        seen.get("renderA", {}).get("pythonHashSeed"),
        (second.get("reported") or {}).get("pythonHashSeed"),
    )
    second_process = (
        second.get("exitStatus") == 0
        and seeds[0] is not None
        and seeds[1] is not None
        and seeds[0] != seeds[1]
    )
    basis.append(
        f"render-b written by a second process, exit status {second.get('exitStatus')}, "
        f"PYTHONHASHSEED {seeds[0]} then {seeds[1]}"
    )
    # Renders that differ fail whatever else is known; identical ones count only
    # when a second process with another seed wrote the second.
    out["E01-AC1"] = (False if not same else (True if second_process else None), basis)

    recorded = _field(release_a, "source.contract.sha256")
    computed = seen.get("contractDigest")
    out["E01-AC2"] = (
        recorded is not None and recorded == computed,
        [f"source.contract.sha256 {recorded}; contract_digest {computed}"],
    )

    binding = seen.get("binding", {})
    pairs = [
        (
            "name",
            _field(release_a, "source.environmentBinding.name"),
            binding.get("name"),
        ),
        (
            "apiVersion",
            _field(release_a, "source.environmentBinding.apiVersion"),
            binding.get("apiVersion"),
        ),
        (
            "sha256",
            _field(release_a, "source.environmentBinding.sha256"),
            binding.get("sha256"),
        ),
    ]
    out["E01-AC3"] = (
        all(left is not None and left == right for _, left, right in pairs),
        [
            f"source.environmentBinding.{key} {left}; expected {right}"
            for key, left, right in pairs
        ],
    )

    values_digest = _sha256(files_a[str(VALUES_FILE_NAME)] or b"")
    revision = manifest.get("executingRevision")
    checks = [
        ("output.helmValues.sha256", values_digest),
        ("source.renderer.revision", revision),
        ("source.platformDefaults.revision", revision),
    ]
    out["E01-AC4"] = (
        all(_field(release_a, path) == want for path, want in checks),
        [f"{path} {_field(release_a, path)}; expected {want}" for path, want in checks],
    )

    admission = seen.get("admission", {})
    targets = seen.get("workloadIntentTargets") or []
    generated_leaves = dict(leaves(values_a))
    missing = [target for target in targets if target not in generated_leaves]
    differences = seen.get("mergedDifferences")
    # The one difference E01-AC5 allows, with both values as its statement gives them.
    expected_difference = [
        {
            "path": "telemetry.deploymentEnvironment",
            "v2": {"present": True, "value": "local"},
            "v1": {"present": True, "value": "dev"},
        }
    ]
    if admission.get("admitted"):
        admitted = "admit_manual_values: admitted, no finding"
    else:
        admitted = f"admit_manual_values: refused {admission.get('refusal')}"
    if differences is None:
        merged = "the merged differences were not recorded"
    else:
        merged = "merged values differ at: " + (
            "; ".join(
                f"{d['path']} (V2 {json.dumps(d['v2'].get('value'))}, "
                f"V1 {json.dumps(d['v1'].get('value'))})"
                for d in differences
            )
            or "nothing"
        )
    basis5 = [
        admitted,
        f"{len(targets)} workload-intent chart values; {len(missing)} absent from "
        f"render-a/{VALUES_FILE_NAME}" + (f": {', '.join(missing)}" if missing else ""),
        merged,
    ]
    restated = seen.get("restatedPins")
    if freeze_revision >= 2:
        if restated is None:
            basis5.append("which hand-written strings restate a pin was not recorded")
        else:
            basis5.append(
                "hand-written strings that restate a workload-intent generated value: "
                + (
                    "; ".join(
                        f"{r['path']} ({', '.join(r['restates'])})" for r in restated
                    )
                    or "none"
                )
            )
    if (
        differences is None
        or not targets
        or (freeze_revision >= 2 and restated is None)
    ):
        out["E01-AC5"] = (None, basis5)
    else:
        out["E01-AC5"] = (
            admission.get("admitted") is True
            and not missing
            and differences == expected_difference
            and (freeze_revision == 1 or restated == []),
            basis5,
        )
    return out


def _judge_b(
    evidence: Path, freeze: Mapping[str, Any], manifest: Mapping[str, Any]
) -> tuple[bool | None, list[str]]:
    seen = manifest.get("observations", {}).get("E01-B")
    paths = {
        directory: {name: _bytes(evidence, directory, name) for name in RENDERED_FILES}
        for directory in (RENDER_A, MUTATION)
    }
    if seen is None or any(None in files.values() for files in paths.values()):
        return None, ["the E01-B evidence is incomplete"]
    expected = _part(freeze, "E01-B")["expectedChange"]

    def parsed(directory: str, name: str) -> Any:
        return _mapping(paths[directory][name])

    if any(
        parsed(directory, name) is None
        for directory in (RENDER_A, MUTATION)
        for name in RENDERED_FILES
    ):
        return None, ["an E01-B file is not a YAML mapping"]

    values = leaf_differences(
        parsed(RENDER_A, str(VALUES_FILE_NAME)), parsed(MUTATION, str(VALUES_FILE_NAME))
    )
    fields = leaf_differences(
        parsed(RENDER_A, RELEASE_FILE_NAME), parsed(MUTATION, RELEASE_FILE_NAME)
    )
    want_values = [
        {
            "path": path,
            "before": {"present": True, "value": change["from"]},
            "after": {"present": True, "value": change["to"]},
        }
        for path, change in sorted(expected["values"].items())
    ]
    recorded = _field(parsed(MUTATION, RELEASE_FILE_NAME), "source.contract.sha256")
    computed = seen.get("mutatedContractDigest")
    holds = (
        values == want_values
        and sorted(d["path"] for d in fields) == sorted(expected["releaseFields"])
        and recorded is not None
        and recorded == computed
    )

    def shown(side: Mapping[str, Any]) -> str:
        return json.dumps(side["value"]) if side["present"] else "(absent)"

    basis = [
        f"values.generated.yaml: {d['path']} {shown(d['before'])} -> {shown(d['after'])}"
        for d in values
    ] or ["values.generated.yaml: no leaf differs"]
    basis += [
        f"rendered-workload-release.yaml: {d['path']} differs" for d in fields
    ] or ["rendered-workload-release.yaml: no field differs"]
    basis.append(f"source.contract.sha256 {recorded}; contract_digest {computed}")
    return holds, basis


def _expected_refusal(case: Mapping[str, Any]) -> dict[str, Any]:
    expected = case["expected"]
    if "findings" in expected:
        return {
            "step": case["refusedBy"],
            "exception": expected["exception"],
            "findings": [
                {key: f[key] for key in ("rule", "category", "code", "field")}
                for f in expected["findings"]
            ],
        }
    return {
        "step": case["refusedBy"],
        "exception": expected["exception"],
        "code": expected["code"],
        "field": expected["field"],
    }


def _compared(refusal: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The parts of a recorded refusal E01-AC7 compares: no reason text."""
    if refusal is None:
        return None
    shown: dict[str, Any] = {
        "step": refusal.get("step"),
        "exception": refusal.get("exception"),
    }
    if "findings" in refusal:
        shown["findings"] = [
            {key: f.get(key) for key in ("rule", "category", "code", "field")}
            for f in refusal["findings"]
        ]
    else:
        shown["code"] = refusal.get("code")
        shown["field"] = refusal.get("field")
    return shown


def _judge_c(
    evidence: Path, freeze: Mapping[str, Any]
) -> tuple[bool | None, list[str]]:
    path = evidence / REFUSALS
    if not path.is_file():
        return None, ["refusals.json is absent"]
    recorded = {
        entry["case"]: entry for entry in json.loads(path.read_text(encoding="utf-8"))
    }
    cases = _part(freeze, "E01-C")["cases"]
    if sorted(recorded) != sorted(case["id"] for case in cases):
        return None, ["refusals.json does not hold exactly the registered cases"]
    holds = True
    basis = []
    for case in cases:
        attempts = recorded[case["id"]]["attempts"]
        if [a.get("attempt") for a in attempts] != [1, 2]:
            return None, [f"{case['id']} was not recorded as two attempts"]
        want = _expected_refusal(case)
        first, second = attempts
        matches = [_compared(a.get("refusal")) == want for a in attempts]
        written = [a.get("outputDirectoryExists") for a in attempts]
        repeated = first.get("refusal") == second.get("refusal")
        ok = all(matches) and written == [False, False] and repeated
        holds = holds and ok
        got = _compared(first.get("refusal"))
        if got is None:
            summary = "not refused"
        elif "findings" in got:
            summary = "; ".join(
                f"{f['rule']} {f['category']} {f['code']} {f['field']}"
                for f in got["findings"]
            )
        else:
            summary = f"{got['code']} {got['field']}"
        basis.append(
            f"{case['id']}: refused by {got and got['step']} with {got and got['exception']}: "
            f"{summary}; as registered: {'yes' if all(matches) else 'no'}; "
            f"output directory written: {'yes' if any(written) else 'no'}; "
            f"second execution the same: {'yes' if repeated else 'no'}"
        )
    return holds, basis


def judge(
    evidence: Path, freeze: Mapping[str, Any], manifest: Mapping[str, Any]
) -> Judgement:
    """Every criterion's verdict and every part's outcome, from a run's raw evidence."""
    refused = bool(manifest.get("preconditions", {}).get("findings"))
    aborted = bool(manifest.get("abortChecks", {}).get("conditions"))
    results: dict[str, tuple[bool | None, list[str]]] = {}
    if refused:
        reason = [
            "the run did not start: " + "; ".join(manifest["preconditions"]["findings"])
        ]
        results = {criterion.criterion_id: (None, reason) for criterion in CRITERIA}
    else:
        results.update(_judge_a(evidence, manifest, _revision(freeze)))
        results["E01-AC6"] = _judge_b(evidence, freeze, manifest)
        results["E01-AC7"] = _judge_c(evidence, freeze)
    outcomes = {}
    for part in PARTS:
        verdicts = [results[c.criterion_id][0] for c in CRITERIA if c.part == part]
        if refused:
            outcomes[part] = "REFUSED"
        elif aborted:
            outcomes[part] = "ABORTED"
        elif any(verdict is False for verdict in verdicts):
            # The part executed as registered and a criterion did not hold. That is
            # FAILED even when another criterion went unanswered, so it cannot be
            # repeated as an inconclusive run.
            outcomes[part] = "FAILED"
        elif any(verdict is None for verdict in verdicts):
            outcomes[part] = "INCONCLUSIVE"
        else:
            outcomes[part] = "PASSED"
    return Judgement(
        verdicts={key: value[0] for key, value in results.items()},
        basis={key: tuple(value[1]) for key, value in results.items()},
        outcomes=outcomes,
    )


# --------------------------------------------------------------------------
# The result page
# --------------------------------------------------------------------------


def _verdict(value: bool | None) -> str:
    return {True: "held", False: "did not hold", None: "not answered"}[value]


def result_page(
    manifest: Mapping[str, Any], freeze: Mapping[str, Any], judgement: Judgement
) -> str:
    """result.md: each criterion, its verdict, and its evidence, limitations first."""
    meta = manifest["metadata"]
    statements = {
        item["id"]: item["statement"]
        for entry in freeze["fields"]["acceptanceCriteria"]
        if entry["status"] == "value"
        for item in entry["value"]
    }
    lines = [
        f"# V2-E01 run {meta['runId']}: E01-A, E01-B, and E01-C",
        "",
        "Generated by the run from its raw evidence. `python -m tools.experiment_e01 "
        "--check` computes it again from the committed files and fails if they differ.",
        "",
        "## Limitations",
        "",
        "From the freeze record, unchanged:",
        "",
    ]
    lines += [f"- {item}" for item in freeze["definition"]["limitations"]]
    lines += ["", "Of this run:", ""]
    if _revision(freeze) == 1:
        lines.append(
            "- The runner is not a pinned input of the freeze record. It ran from "
            "outside the checked-out tree, and the manifest records the content digest "
            "of each runner file."
        )
    else:
        identity = manifest.get("executionIdentity", {})
        lines.append(
            "- The runner is a pinned input of the freeze record. The manifest records "
            "where the runner and the inferops package were imported from - "
            f"{identity.get('runnerFile')} and {identity.get('inferopsPackage')} - and "
            "every repository module file the run and its second process loaded, with "
            "its content digest."
        )
    lines += [
        "- The run executed on one host, named in the manifest. The evidence is C0: "
        "nothing was deployed, and no runtime component, cluster, or model executed.",
        "",
        "## Run",
        "",
        f"- Freeze record: `{meta['freezeRecord']}`, revision {meta['freezeRevision']}, "
        f"content SHA-256 `{meta['freezeContentSha256']}`.",
        f"- Executing revision: `{manifest['executingRevision']}`.",
        f"- Started {meta['startedAt']}, finished {meta['finishedAt']} (UTC).",
        "- Preconditions: "
        + (
            "every one held."
            if not manifest["preconditions"]["findings"]
            else "; ".join(manifest["preconditions"]["findings"]) + "."
        ),
        "- Abort conditions: "
        + (
            "none met."
            if not manifest["abortChecks"]["conditions"]
            else "; ".join(manifest["abortChecks"]["conditions"]) + "."
        ),
        "",
        "## Outcome",
        "",
        "| Part | Outcome |",
        "| --- | --- |",
    ]
    lines += [f"| {part} | {judgement.outcomes[part]} |" for part in PARTS]
    lines += ["", "## Criteria", ""]
    for criterion in CRITERIA:
        cid = criterion.criterion_id
        lines += [
            f"### {cid} ({criterion.part}): {_verdict(judgement.verdicts[cid])}",
            "",
            f"> {statements.get(cid, '')}",
            "",
        ]
        lines += [f"- {item}" for item in judgement.basis[cid]]
        lines.append("")
    lines += [
        "## Does not establish",
        "",
    ]
    lines += [f"- {item}" for item in freeze["definition"]["doesNotEstablish"]]
    lines += [
        "- That the release input deploys or serves. E01-D owns that, and it did not run.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Checking a committed run
# --------------------------------------------------------------------------


def committed_runs(root: Path = REPO_ROOT) -> list[Path]:
    """Every run directory under :data:`RUNS_DIR`, in name order."""
    base = root / RUNS_DIR
    if not base.is_dir():
        return []
    return sorted(path for path in base.iterdir() if path.is_dir())


def check_run(evidence: Path, root: Path = REPO_ROOT) -> list[RunFinding]:
    """Every way a committed run disagrees with its own raw evidence.

    The run's files have the digests its manifest records; the verdicts and outcomes
    computed again from those files are the ones it records; and result.md is the
    page they generate. The freeze record is read from ``root`` and must be the one
    the run names, by content digest.
    """
    name = evidence.name
    try:
        manifest = json.loads((evidence / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [RunFinding(name, MANIFEST, f"cannot be read: {type(error).__name__}")]
    try:
        return _check_manifest(evidence, name, manifest, root)
    except (KeyError, TypeError, AttributeError) as error:
        return [RunFinding(name, MANIFEST, f"is malformed: {type(error).__name__}")]


def _check_manifest(
    evidence: Path, name: str, manifest: Mapping[str, Any], root: Path
) -> list[RunFinding]:
    findings: list[RunFinding] = []
    named = manifest["metadata"]["freezeRecord"]
    revisions = {path: revision for revision, path in FREEZE_RECORDS.items()}
    if named not in revisions or manifest["metadata"]["freezeRevision"] != (
        revisions.get(named)
    ):
        return [
            RunFinding(
                name,
                "metadata.freezeRecord",
                "names no E01 freeze revision this analysis knows",
            )
        ]
    revision = revisions[named]
    preconditions = manifest["preconditions"]
    if preconditions["mergedRef"] != MERGED_REF:
        findings.append(
            RunFinding(name, "preconditions.mergedRef", f"is not {MERGED_REF}")
        )
    if preconditions["findings"] != _recorded_findings(manifest, revision):
        findings.append(
            RunFinding(
                name,
                "preconditions.findings",
                "are not the findings the recorded observations give",
            )
        )
    freeze = load_freeze(root, revision)
    if revision >= 2:
        # The execution identity is checked again from what the run recorded.
        outside, identity_aborts = identity_conditions(manifest, freeze)
        if manifest["executionIdentity"]["loadedOutsideFrozenInputs"] != outside:
            findings.append(
                RunFinding(
                    name,
                    "executionIdentity.loadedOutsideFrozenInputs",
                    "is not what the recorded loaded modules and the pins give",
                )
            )
        recorded = [
            c
            for c in manifest["abortChecks"]["conditions"]
            if c in (LOADED_OUTSIDE, SECOND_OUTSIDE)
        ]
        if recorded != identity_aborts:
            findings.append(
                RunFinding(
                    name,
                    "abortChecks.conditions",
                    "do not state the execution-identity conditions the record gives",
                )
            )
    pinned = manifest["metadata"]["freezeContentSha256"]
    if content_digest((root / named).read_bytes()) != pinned:
        findings.append(
            RunFinding(
                name,
                "metadata.freezeContentSha256",
                "is not the freeze record's digest",
            )
        )
    if manifest["metadata"]["runId"] != name:
        findings.append(
            RunFinding(name, "metadata.runId", "is not the directory's name")
        )
    present = {
        path.relative_to(evidence).as_posix()
        for path in evidence.rglob("*")
        if path.is_file()
    } - {MANIFEST, RESULT}
    recorded = manifest.get("files", {})
    for path in sorted(present | set(recorded)):
        if path not in recorded:
            findings.append(RunFinding(name, path, "is not in the manifest"))
        elif path not in present:
            findings.append(RunFinding(name, path, "is in the manifest and absent"))
        elif _sha256((evidence / path).read_bytes()) != recorded[path]:
            findings.append(
                RunFinding(name, path, "does not have the recorded SHA-256")
            )
    judgement = judge(evidence, freeze, manifest)
    for criterion in manifest.get("criteria", []):
        if judgement.verdicts.get(criterion["id"]) != criterion["holds"]:
            findings.append(
                RunFinding(
                    name,
                    f"criteria[{criterion['id']}]",
                    "is not the verdict its evidence gives",
                )
            )
    if [c["id"] for c in manifest.get("criteria", [])] != [
        c.criterion_id for c in CRITERIA
    ]:
        findings.append(
            RunFinding(name, "criteria", "does not list every criterion in order")
        )
    if manifest.get("outcomes") != dict(judgement.outcomes):
        findings.append(
            RunFinding(name, "outcomes", "are not the outcomes its evidence gives")
        )
    page = evidence / RESULT
    if not page.is_file() or page.read_text(encoding="utf-8") != result_page(
        manifest, freeze, judgement
    ):
        findings.append(
            RunFinding(name, RESULT, "is not the page its evidence generates")
        )
    return findings
