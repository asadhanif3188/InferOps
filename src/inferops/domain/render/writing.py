"""Writing a generated release to a directory a caller names: all of it, or none of it.

This is the one module of the render package that touches a file, and it does one
thing: :func:`write_release` puts the two files of a
:class:`~.generation.GeneratedRelease` in a directory the caller names. It decides
nothing about them - their names, bytes, and digests were fixed when the release
was generated - and it reads no clock, random source, or environment variable.

**All or nothing.** A reader of the output directory finds either both files,
complete and verified, or no directory at all:

1. The output directory must not exist yet, and its parent must. A directory that
   already holds something is never written into, so an earlier release cannot be
   half-replaced and a stray file cannot sit beside a new one.
2. The files are written into a **staging directory** beside it, named for it -
   ``.<name>.partial`` - created exclusively. Each file is created exclusively,
   written as bytes, and its bytes flushed with ``os.fsync``; then both are read back
   and compared with what was meant to be written.
3. The staging directory is **renamed** to the output directory, one operation that
   a reader sees happen or not happen.

**Failure leaves something recoverable, never something misleading.** If a step
raises, the files written so far and the staging directory are removed and the
error is raised; the output directory never appeared. If the removal itself fails,
or the process is killed before it can run, the staging directory is left behind
under its own name, and the next write to the same output directory refuses to
start until it is removed, naming it. A partial release is therefore always in a
directory whose name says it is partial.

**The one exemption from a rule, and its limit.** Nothing else under
``src/inferops`` opens a path, so that the distribution stays usable from a wheel
with no file system around it, and an architecture test enforces that for every
module but this one, by name. This module touches the file system only inside the
bodies of functions a caller invokes - importing it reads, writes, creates, moves,
and removes nothing - and the same suite holds that for every module-level
statement, decorator, and default value. Nothing constructs a domain object
through it.

**What it does not promise.** The all-or-nothing above holds for a running system
and a process that fails or is killed; it is not crash durability. Each file's bytes
are flushed with ``os.fsync``, but no directory is: not the staging directory after
the files are created in it, and not the parent after the rename. So after a power
loss or an operating-system crash, which names survived is the file system's
choice - the output directory may be missing, a staging directory left behind may
hold both files, one, or none, and a file system that does not order its metadata
writes could even show the output directory without both files. A release read
after a crash is checked against its digests, not trusted because its directory
exists. Where a release directory lives is the caller's choice and nothing here
constrains it. On POSIX systems a rename replaces an *empty* directory created at
the output path after the check in step 1 and before step 3; one that holds anything
is refused, as is any on Windows.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from .generation import GeneratedRelease

#: Appended to the output directory's name, after a leading dot, for the directory
#: a write is staged in.
STAGING_SUFFIX: Final = ".partial"


def staging_directory(directory: str | os.PathLike[str]) -> Path:
    """Where a write to ``directory`` is staged: ``.<name>.partial`` beside it."""
    target = Path(directory)
    return target.with_name(f".{target.name}{STAGING_SUFFIX}")


def _write_file(path: Path, data: bytes) -> None:
    """Create ``path``, which must not exist, holding exactly ``data``, flushed."""
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _discard(staging: Path, names: tuple[str, ...], error: BaseException) -> None:
    """Remove what a failed write staged; if that fails too, say where it is."""
    try:
        for name in names:
            (staging / name).unlink(missing_ok=True)
        staging.rmdir()
    except OSError:
        error.add_note(
            f"the staging directory {staging} could not be removed; it holds an "
            "incomplete release, and the next write to the same directory refuses "
            "to start until it is removed"
        )


def write_release(
    generated: GeneratedRelease, directory: str | os.PathLike[str]
) -> Path:
    """Write ``generated`` into ``directory``, which this creates, and return it.

    Raises:
        FileExistsError: ``directory`` already exists, or an earlier write to it
            left its staging directory behind; nothing is written.
        FileNotFoundError: the parent of ``directory`` does not exist.
        ValueError: ``directory`` names no directory of its own, such as ``.``.
        OSError: a file could not be written, read back as written, or moved into
            place; whatever was staged is removed first, or named in a note on the
            error if it cannot be.
        TypeError: ``generated`` is not a :class:`~.generation.GeneratedRelease`.
    """
    if not isinstance(generated, GeneratedRelease):
        raise TypeError("only a GeneratedRelease is written, never loose files")
    target = Path(directory)
    if target.name in {"", ".", ".."}:
        raise ValueError("the output directory must be a directory of its own name")
    if not target.parent.is_dir():
        raise FileNotFoundError(
            f"the parent of the output directory {target} does not exist"
        )
    if target.exists() or target.is_symlink():
        raise FileExistsError(
            f"the output directory {target} already exists; a release is written "
            "only to a directory that does not"
        )
    staging = staging_directory(target)
    try:
        staging.mkdir()
    except FileExistsError:
        raise FileExistsError(
            f"{staging} exists: an earlier write to {target} did not finish. "
            "Nothing was written. Remove it, then write again"
        ) from None
    files = generated.files()
    names = tuple(name for name, _ in files)
    try:
        for name, data in files:
            _write_file(staging / name, data)
        for name, data in files:
            if (staging / name).read_bytes() != data:
                raise OSError(f"{name} did not read back as it was written")
        os.rename(staging, target)
    except BaseException as error:
        # Once the rename has happened the staging directory is gone and the
        # release is complete in place; there is nothing to discard or report.
        if staging.is_dir():
            _discard(staging, names, error)
        raise
    return target


__all__ = ["STAGING_SUFFIX", "staging_directory", "write_release"]
