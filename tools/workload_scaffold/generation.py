"""Generate a workload from the template, and validate what was written.

This is the half of the scaffolder that touches a file system. The half that
renders is :mod:`inferops.scaffolding`, inside the distribution, where nothing
reads or writes a path; the split is not tidiness. A domain object must be
constructible from a wheel with no repository around it, and validating a
generated project needs the published JSON Schema and a YAML loader — a file and
a dependency the distribution deliberately does not carry. So the writer lives
here, beside ``tools.contract_validation``, which is the validator every
committed fixture goes through and the one a generated workload's own quick start
tells its author to run.

**Nothing invalid reaches a disk.** The order is fixed and it is the whole
design: refuse the parameter set, render into memory, put the rendered contract
through the validator, and only then plan a write. A document that would not
validate is refused while there is nothing to clean up, which is the acceptance
criterion's first clause satisfied by construction rather than by care.

**A write that fails partway is undone.** Every directory and every file this
module creates is recorded as it is created, and an :class:`OSError` anywhere in
the sequence rolls the destination back to what it was — in reverse order,
reporting anything it could not remove rather than claiming a clean rollback it
did not achieve. That is the criterion's second clause.

**Nothing is overwritten, ever.** A generated workload is an ordinary committed
directory the moment it exists; re-running the scaffolder over it is not part of
the change loop, and there is no flag here that would make it one. An occupied
destination is refused, and what is already there is not read, moved, or touched.

**What is on disk is what was validated.** After the write, every file is read
back and compared to the text that was rendered, and the written ``workload.yaml``
is validated again from disk. A mismatch is a rollback and a refusal, so the
success this module reports is a statement about files rather than about strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from inferops.scaffolding import (
    RenderedWorkload,
    WorkloadTemplateParameters,
    render_workload,
    surviving_placeholders,
)

from ..contract_validation.errors import Finding
from ..contract_validation.workload import validate

#: The rendered file whose content is a WorkloadContract. Named rather than
#: guessed at, because the validation below is about this file and not about the
#: quick start or the test skeleton beside it.
CONTRACT_FILE = "workload.yaml"


# --------------------------------------------------------------------------
# Failures
# --------------------------------------------------------------------------


class ScaffoldError(Exception):
    """Base class for every failure this module raises.

    A refusal of the parameter set is deliberately *not* one of these: it is
    :class:`inferops.scaffolding.InvalidTemplateParametersError`, raised by the
    library and left alone rather than re-wrapped. The scaffolder has nothing to
    add to it, and a wrapper that adds nothing is a wrapper that loses the field
    names on the way through.
    """


class DestinationRefusedError(ScaffoldError):
    """The destination could not be written into, and nothing was attempted.

    Carries the path and the reason. The path is one the author typed, so it is
    theirs to see; nothing is read out of whatever is already there.
    """

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path.as_posix()}: {reason}")
        self.path = path
        self.reason = reason

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path.as_posix(), "reason": self.reason}


class GeneratedContractRefusedError(ScaffoldError):
    """The generated contract did not validate, so nothing was left behind.

    Reaching this is a defect in the template rather than in what an author
    typed: the parameter set was already accepted, and every constraint that
    parameter set applies is imported from the same value objects the contract is
    built from. It is raised rather than assumed away because a scaffolder that
    wrote a document it had not checked would be a scaffolder whose central
    claim — *generated output validates without a source edit* — was a comment.
    """

    def __init__(self, findings: tuple[Finding, ...], *, on_disk: bool) -> None:
        where = "read back from disk" if on_disk else "as rendered"
        super().__init__(
            f"the generated contract was refused {where} with "
            f"{len(findings)} finding(s): "
            + "; ".join(sorted(f"{f.rule} at {f.field}" for f in findings))
        )
        self.findings = findings
        self.on_disk = on_disk

    def as_dicts(self) -> list[dict[str, object]]:
        return [finding.as_dict() for finding in self.findings]


class PartialWriteError(ScaffoldError):
    """A write failed partway. What this module created has been removed.

    ``removed`` is what the rollback took back and ``unremoved`` is what it could
    not, reported separately because a rollback claiming a success it did not
    achieve is worse than one that failed loudly. An empty ``unremoved`` is the
    ordinary case and means the destination is exactly as it was found.
    """

    def __init__(
        self,
        destination: Path,
        removed: tuple[Path, ...],
        unremoved: tuple[Path, ...],
        reason: str,
    ) -> None:
        super().__init__(
            f"{destination.as_posix()}: {reason}; "
            f"{len(removed)} path(s) removed, {len(unremoved)} left behind"
        )
        self.destination = destination
        self.removed = removed
        self.unremoved = unremoved
        self.reason = reason

    def as_dict(self) -> dict[str, object]:
        return {
            "destination": self.destination.as_posix(),
            "reason": self.reason,
            "removed": [path.as_posix() for path in self.removed],
            "unremoved": [path.as_posix() for path in self.unremoved],
            "rolledBack": not self.unremoved,
        }


# --------------------------------------------------------------------------
# The plan
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WritePlan:
    """Every path a generation would create, decided before anything is created.

    Separating the decision from the act is what makes ``--dry-run`` the same
    code path as a real run rather than a second implementation of it, and it is
    what lets a rollback know precisely which directories were this module's to
    remove and which were already there.
    """

    workload_root: Path
    #: Directories that do not exist yet, shallowest first, so creating them in
    #: order needs no ``parents=True`` — and so removing them in reverse order
    #: removes only what was created.
    directories: tuple[Path, ...]
    #: Target path and the exact text to write, in a stable order.
    files: tuple[tuple[Path, str], ...]

    @property
    def paths(self) -> tuple[Path, ...]:
        """Every file path this plan would write, in a stable order."""
        return tuple(path for path, _ in self.files)


def _missing_ancestors(directory: Path) -> list[Path]:
    """Every directory from ``directory`` upwards that does not exist, shallowest first."""
    missing: list[Path] = []
    current = directory
    while not current.exists():
        missing.append(current)
        parent = current.parent
        if parent == current:  # pragma: no cover - a filesystem root always exists
            break
        current = parent
    return list(reversed(missing))


def plan_write(rendered: RenderedWorkload, into: Path) -> WritePlan:
    """Where a rendered workload would land, refusing an occupied destination.

    Refuses before anything is created. The workload's own directory must not
    exist: a generated workload is an ordinary committed directory the moment it
    exists, and nothing here overwrites an author's edits.
    """
    if into.exists() and not into.is_dir():
        raise DestinationRefusedError(
            into, "is not a directory; a workload is generated into a directory"
        )

    workload_root = into / rendered.directory_name
    if workload_root.exists():
        raise DestinationRefusedError(
            workload_root,
            "already exists; a generated workload is an ordinary committed "
            "directory once it exists, and nothing here overwrites one. Remove it "
            "or generate into a different destination",
        )

    directories: list[Path] = []
    files: list[tuple[Path, str]] = []
    for relative in sorted(rendered.files):
        target = workload_root / relative
        for ancestor in _missing_ancestors(target.parent):
            if ancestor not in directories:
                directories.append(ancestor)
        files.append((target, rendered.files[relative]))

    return WritePlan(
        workload_root=workload_root,
        directories=tuple(directories),
        files=tuple(files),
    )


# --------------------------------------------------------------------------
# The result
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerationResult:
    """What a generation did, or — under ``dry_run`` — what it would have done."""

    parameters: WorkloadTemplateParameters
    workload_root: Path
    directories: tuple[Path, ...]
    files: tuple[Path, ...]
    dry_run: bool

    def as_dict(self) -> dict[str, Any]:
        """A stable structured form, for a reviewer who wants to diff two runs.

        The path keys are named for the plan rather than for the act, because
        under ``dry_run`` nothing was created and a key called ``filesWritten``
        would say otherwise. ``contractValidatedFrom`` carries the same
        distinction for the validation: a dry run validated the rendered text, a
        real run validated the file that is now on disk.
        """
        return {
            "workload": self.parameters.name,
            "profile": self.parameters.profile,
            "workloadRoot": self.workload_root.as_posix(),
            "directories": [path.as_posix() for path in self.directories],
            "files": [path.as_posix() for path in self.files],
            "dryRun": self.dry_run,
            "contractValidatedFrom": (
                "the rendered text" if self.dry_run else "the written file"
            ),
        }


# --------------------------------------------------------------------------
# Writing, and undoing a write
# --------------------------------------------------------------------------


def _roll_back(
    files: list[Path], directories: list[Path]
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Remove what was created, newest first, reporting what would not go.

    Files before directories, and each group in reverse creation order, because a
    directory with anything left in it does not go. Nothing outside the two lists
    is touched: a directory that was already there was never this module's.
    """
    removed: list[Path] = []
    unremoved: list[Path] = []
    for path in reversed(files):
        try:
            path.unlink()
        except OSError:
            unremoved.append(path)
        else:
            removed.append(path)
    for path in reversed(directories):
        try:
            path.rmdir()
        except OSError:
            unremoved.append(path)
        else:
            removed.append(path)
    return tuple(removed), tuple(unremoved)


def _write(plan: WritePlan) -> tuple[list[Path], list[Path]]:
    r"""Create the plan's directories and files, undoing everything on a failure.

    Files are opened with ``x`` — create exclusively — so a path that appeared
    between the plan and the write is a refusal rather than a silent overwrite,
    and written with an explicit ``\n`` newline so that what lands on disk is
    byte for byte the text that was rendered and validated, on every platform.
    """
    created_directories: list[Path] = []
    created_files: list[Path] = []
    try:
        for directory in plan.directories:
            directory.mkdir()
            created_directories.append(directory)
        for target, text in plan.files:
            with open(target, "x", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            created_files.append(target)
    except OSError as error:
        removed, unremoved = _roll_back(created_files, created_directories)
        raise PartialWriteError(
            plan.workload_root,
            removed,
            unremoved,
            f"{type(error).__name__} while writing the generated workload",
        ) from error
    return created_directories, created_files


def _verify(plan: WritePlan) -> None:
    """Read back what was written and hold it to what was validated.

    Three checks, and each is about the files rather than about the strings that
    produced them: every file reads back exactly as it was rendered, no
    placeholder survived into any of them, and the written contract validates
    from disk through the same function every committed fixture goes through.
    """
    for target, text in plan.files:
        on_disk = target.read_text(encoding="utf-8")
        if on_disk != text:
            raise OSError(f"{target.as_posix()} did not read back as it was written")
        survivors = surviving_placeholders(on_disk)
        if survivors:
            raise OSError(
                f"{target.as_posix()} carries an unsubstituted placeholder: "
                + ", ".join(survivors)
            )

    contract_path = plan.workload_root / CONTRACT_FILE
    document = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    findings = tuple(validate(document))
    if findings:
        raise GeneratedContractRefusedError(findings, on_disk=True)


# --------------------------------------------------------------------------
# The pipeline
# --------------------------------------------------------------------------


def validate_rendered_contract(rendered: RenderedWorkload) -> tuple[Finding, ...]:
    """Findings against the rendered contract, before it is anywhere near a disk."""
    document = yaml.safe_load(rendered.files[CONTRACT_FILE])
    return tuple(validate(document))


def generate(
    parameters: WorkloadTemplateParameters,
    into: Path,
    *,
    dry_run: bool = False,
) -> GenerationResult:
    """Generate one workload into ``into``, validating before and after the write.

    Raises, in the order the steps run:

    * :class:`inferops.scaffolding.InvalidTemplateParametersError` — the
      parameter set was refused, with every reason at once. Nothing was rendered
      and nothing was written.
    * :class:`GeneratedContractRefusedError` — the rendered contract did not
      validate. Nothing was written.
    * :class:`DestinationRefusedError` — the destination was occupied, or was not
      a directory. Nothing was written.
    * :class:`PartialWriteError` — a write or the read-back failed, and whatever
      had been created was removed.
    """
    rendered = render_workload(parameters)

    findings = validate_rendered_contract(rendered)
    if findings:
        raise GeneratedContractRefusedError(findings, on_disk=False)

    plan = plan_write(rendered, into)

    if dry_run:
        return GenerationResult(
            parameters=parameters,
            workload_root=plan.workload_root,
            directories=plan.directories,
            files=plan.paths,
            dry_run=True,
        )

    created_directories, created_files = _write(plan)
    try:
        _verify(plan)
    except (OSError, GeneratedContractRefusedError) as error:
        removed, unremoved = _roll_back(created_files, created_directories)
        raise PartialWriteError(
            plan.workload_root,
            removed,
            unremoved,
            f"the generated workload did not verify after it was written: {error}",
        ) from error

    return GenerationResult(
        parameters=parameters,
        workload_root=plan.workload_root,
        directories=tuple(created_directories),
        files=tuple(created_files),
        dry_run=False,
    )
