"""Bind the analysis of an experiment run to its evidence, and compute it again.

    python -m tools.analysis_replay bind RUN_DIRECTORY --declaration FILE
    python -m tools.analysis_replay verify RUN_DIRECTORY [RUN_DIRECTORY ...]
    python -m tools.analysis_replay repository
    python -m tools.analysis_replay aggregate --metric NAME RUN_DIRECTORY ...
    python -m tools.analysis_replay sources

``bind`` reads one run directory and a declaration, and it prints one run
analysis. ``verify`` computes each run analysis of the given run directories
again and compares it with the stored file. ``repository`` does that for each
run directory under ``docs/proof/experiments`` that the pre-schema register
does not name. ``aggregate`` prints one figure of each run of one experiment
and the median of three counted runs, with each result state read from its
manifest. A run that is not counted is held to a reason that the freeze
record of its manifest registers, and that record and the freeze registry are
read from the commit that the manifest states as its executing revision.
``sources`` prints the digest of each source file of the analysis code.

**Exit status 0 says that nothing was refused.** For ``verify`` it says that
each given run directory names a run analysis and that each was reproduced
byte for byte. It does not say that a metric has a value or that a run passed.
Exit status 3 says that a rule refused a run directory, a declaration, or a
document: the output names the rule. Exit status 2 says that the arguments are
not usable.

**The command reads files and Git, and it writes no file.** ``bind`` and
``aggregate`` read the commit of the checkout and refuse while a source file
of the analysis code does not have the content that the commit holds for it.
``verify`` and ``repository`` compare the commit that a document states with
Git when the clone holds it. ``aggregate`` does not compare the commit of a
run analysis. For a run that is not counted it reads two files of the
executing revision from the objects of the clone, and it refuses when the
clone does not hold that commit. It checks out no commit. It tells Git to
fetch nothing, and it reads no commit of a partial clone, which fetches the
objects that it lacks. It holds each object that it reads to its SHA-1
identifier. No command contacts a cluster or a caller. See
docs/testing/analysis-replay.md.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from tools.experiment_evidence import REFUSED, Finding
from tools.experiment_evidence.core import printable
from tools.experiment_run.core import PRE_SCHEMA, REPO_ROOT
from tools.experiment_run.core import repository_report as manifest_listing
from tools.reliability_analysis import AGGREGATE_METRICS

from .core import (
    CODE_DIFFERS,
    NO_ANALYSIS,
    REFUSED_EXIT,
    REPLAYED,
    REVISION_HELD,
    REVISION_NOT_CHECKED,
    RULE_ANALYSIS,
    RULE_MISSING,
    RULE_REVISION,
    RULE_UNCOMMITTED,
    SOURCE_PACKAGES,
    History,
    ReplayRefused,
    RunReplay,
    aggregate_runs,
    analysis_code,
    analysis_sources,
    bind_run,
    record_text,
    replay_run,
    revision_state,
)

_GIT_TIMEOUT_SECONDS = 60
#: The longest file that is read from a commit for an aggregate.
MAX_HISTORY_BYTES = 4 * 1024 * 1024
_FULL_COMMIT = re.compile(r"[0-9a-f]{40}")


def _emit(text: str) -> None:
    """Write LF bytes on every host."""
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def _git(root: Path, *arguments: str) -> bytes | None:
    """What one Git command prints, or None when Git refuses or is absent."""
    try:
        done = subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def checkout_revision(root: Path = REPO_ROOT) -> str:
    """The commit of the checkout, when each source file is the file of that commit.

    The source files that are present are compared with the content that the
    commit holds, file by file, and the commit must hold no other Python file
    in a source package. The comparison does not read the index of Git, so a
    file that Git is told to leave out of its status is compared too, and so
    is a file that Git ignores. The status of Git is read as well, for a
    change that is staged.

    Raises:
        ReplayRefused: Git gives no commit, or a source file of the analysis
            code is changed, added, ignored, or not tracked.
    """
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    if head is None:
        raise ReplayRefused(RULE_UNCOMMITTED, "Git gives no commit for the checkout")
    revision = head.decode("ascii").strip()
    differs = ReplayRefused(
        RULE_UNCOMMITTED,
        "a source file of the analysis code is not the file of the commit of the "
        "checkout",
    )
    changed = _git(
        root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        *(f"tools/{package}" for package in SOURCE_PACKAGES),
    )
    if changed is None or changed.strip():
        raise differs
    state, _ = revision_state(
        analysis_code(revision, root),
        lambda stated: _commit_present(root, stated),
        lambda stated, path: _blob(root, stated, path),
        lambda stated, package: _tracked(root, stated, package),
    )
    if state != REVISION_HELD:
        raise differs
    return revision


def _commit_present(root: Path, revision: str) -> bool:
    """Whether the clone holds a commit with this identifier. A tag is not one."""
    kind = _git(root, "cat-file", "-t", revision)
    return kind is not None and kind.strip() == b"commit"


def _blob(root: Path, revision: str, path: str) -> bytes | None:
    return _git(root, "cat-file", "blob", f"{revision}:{path}")


def _tracked(root: Path, revision: str, package: str) -> list[str] | None:
    """Each path that a commit holds under one directory, or None."""
    listed = _git(root, "ls-tree", "-r", "--name-only", "-z", revision, "--", package)
    if listed is None:
        return None
    return [name for name in listed.decode("utf-8", "replace").split("\0") if name]


def _history_git(root: Path, data: bytes | None, *arguments: str) -> bytes | None:
    """What one Git command of the reader of commits prints, or None.

    The command gets no variable of the environment whose name starts with
    ``GIT_``, so no variable names another clone or another object directory.
    It is told to fetch no object that the clone lacks, to use no transport,
    to read no replacement object, and to ask no question.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith("GIT_")
    }
    environment.update(
        GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1", GIT_TERMINAL_PROMPT="0"
    )
    try:
        done = subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "-c",
                "protocol.allow=never",
                *arguments,
            ],
            cwd=root,
            input=b"" if data is None else data,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            env=environment,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _batch(printed: bytes, count: int) -> list[tuple[str, str, bytes]] | None:
    """The objects that ``git cat-file --batch`` printed: identifier, type, content."""
    objects: list[tuple[str, str, bytes]] = []
    at = 0
    for _ in range(count):
        line_end = printed.find(b"\n", at)
        if line_end < 0:
            return None
        head = printed[at:line_end].split(b" ")
        if len(head) != 3 or not head[2].isdigit():
            return None
        size = int(head[2])
        content = printed[line_end + 1 : line_end + 1 + size]
        if (
            len(content) != size
            or printed[line_end + 1 + size : line_end + 2 + size] != b"\n"
        ):
            return None
        objects.append(
            (
                head[0].decode("ascii", "replace"),
                head[1].decode("ascii", "replace"),
                content,
            )
        )
        at = line_end + 2 + size
    return objects if at == len(printed) else None


def _hash_held(held: tuple[str, str, bytes]) -> bool:
    """Whether an object has the SHA-1 identifier that Git states for it."""
    identifier, kind, content = held
    header = f"{kind} {len(content)}\0".encode("ascii", "replace")
    return (
        hashlib.sha1(header + content, usedforsecurity=False).hexdigest() == identifier
    )


def _tree_entry(tree: bytes, name: bytes) -> tuple[bytes, str] | None:
    """The mode and the object identifier of one name in a tree object, or None."""
    at = 0
    while at < len(tree):
        space = tree.find(b" ", at)
        null = tree.find(b"\0", space)
        if space < 0 or null < 0 or null + 21 > len(tree):
            return None
        if tree[space + 1 : null] == name:
            return tree[at:space], tree[null + 1 : null + 21].hex()
        at = null + 21
    return None


def verified_file(
    revision: str, parts: Sequence[str], objects: Sequence[tuple[str, str, bytes]]
) -> bytes | None:
    """The content of a file of a commit, when each object has its identifier.

    ``objects`` are the commit, its tree, and the object of each part of the
    path, in order. Each must have the SHA-1 identifier that Git states for
    it. The commit must have the identifier ``revision`` and name the tree,
    each tree must name the next object under the next part of the path, and
    the last object must be a regular file. So the content is the one that the
    commit identifier names, whatever a file of the object store holds.
    """
    if len(objects) != len(parts) + 2 or not _commit_held(revision, objects[:2]):
        return None
    if not all(_hash_held(held) for held in objects[2:]):
        return None
    for index, part in enumerate(parts):
        entry = _tree_entry(objects[index + 1][2], part.encode("utf-8"))
        held = objects[index + 2]
        last = index == len(parts) - 1
        if entry is None or entry[1] != held[0]:
            return None
        if last and (held[1] != "blob" or entry[0] not in (b"100644", b"100755")):
            return None
        if not last and (held[1] != "tree" or entry[0] != b"40000"):
            return None
    return objects[-1][2]


def history(root: Path = REPO_ROOT) -> History:
    """A reader of the commits of the clone that holds ``root``.

    Each read is a ``git cat-file`` of objects of the clone. No commit is
    checked out and no file of the working tree is read. Git is told to fetch
    nothing, and a clone that is set to fetch the objects that it lacks, a
    partial clone, gives no commit and no file. A path is a path under
    ``root``, with no part that is empty, ``.``, or ``..``.

    **Each object is held to its identifier.** The reader computes the SHA-1
    of the commit, of each tree on the path, and of the file, and it follows
    the path through the trees itself. So a file of the object store that was
    replaced, a replacement object, and another object directory do not give
    another content for a commit identifier. A file longer than
    ``MAX_HISTORY_BYTES`` is not read. A clone whose objects are not named by
    SHA-1 gives no commit.
    """
    state: dict[str, str | None] = {}

    def prefix() -> str | None:
        """The path of the root in the clone, or None for no clone or a partial one."""
        if "prefix" not in state:
            state["prefix"] = None
            lazy = _history_git(
                root,
                None,
                "config",
                "--get-regexp",
                r"^(extensions\.partialclone|remote\..*\.(promisor|partialclonefilter))$",
            )
            # The command exits 1 when no such setting is present.
            shown = _history_git(root, None, "rev-parse", "--show-prefix")
            if lazy is None and shown is not None:
                state["prefix"] = shown.decode("utf-8", "replace").strip()
        return state["prefix"]

    def objects(names: Sequence[str]) -> list[tuple[str, str, bytes]] | None:
        asked = ("\n".join(names) + "\n").encode("utf-8")
        sizes = _history_git(root, asked, "cat-file", "--batch-check")
        if sizes is None:
            return None
        lines = sizes.decode("utf-8", "replace").splitlines()
        if len(lines) != len(names):
            return None
        for line in lines:
            head = line.split(" ")
            if len(head) != 3 or not head[2].isdigit():
                return None
            if int(head[2]) > MAX_HISTORY_BYTES:
                return None
        printed = _history_git(root, asked, "cat-file", "--batch")
        return None if printed is None else _batch(printed, len(names))

    def read(revision: str, path: str) -> bytes | None:
        held = prefix()
        if held is None or _FULL_COMMIT.fullmatch(revision) is None:
            return None
        parts = [*(part for part in held.split("/") if part), *path.split("/")]
        if any(
            part in ("", ".", "..") or not part.isprintable() or "\\" in part
            for part in path.split("/")
        ):
            return None
        names = [revision, f"{revision}^{{tree}}"]
        names += [
            f"{revision}:{'/'.join(parts[:end])}" for end in range(1, len(parts) + 1)
        ]
        found = objects(names)
        return None if found is None else verified_file(revision, parts, found)

    def commit_present(revision: str) -> bool:
        if prefix() is None or _FULL_COMMIT.fullmatch(revision) is None:
            return False
        found = objects([revision, f"{revision}^{{tree}}"])
        return found is not None and _commit_held(revision, found)

    return History(commit_present, read)


def _commit_held(revision: str, objects: Sequence[tuple[str, str, bytes]]) -> bool:
    """Whether a commit and its tree have their identifiers, and the commit names the tree."""
    if len(objects) != 2 or not all(_hash_held(held) for held in objects):
        return False
    commit, tree = objects
    return (
        commit[0] == revision
        and commit[1] == "commit"
        and tree[1] == "tree"
        and commit[2].split(b"\n", 1)[0] == b"tree " + tree[0].encode("ascii")
    )


def _say(lines: Sequence[str]) -> None:
    """Print lines in ASCII. A name in another script cannot stop the output."""
    print("\n".join(lines).encode("ascii", "backslashreplace").decode("ascii"))


def _refusal(name: str, findings: Sequence[Finding]) -> list[str]:
    lines = [f"REFUSED     {name}  ({len(findings)} finding(s))"]
    lines.extend(f"            {f.rule}  {f.path}  {f.message}" for f in findings)
    return lines


def _replay_lines(replay: RunReplay, code_root: Path) -> tuple[list[str], bool]:
    """The output lines of one replay, and whether the run is refused.

    A run analysis that was reproduced is then held to Git: each source file
    must have its stated digest at the stated commit, when the clone holds that
    commit.
    """
    if replay.status == REFUSED:
        return _refusal(replay.path, replay.findings), True
    if replay.status == NO_ANALYSIS:
        return [f"no-analysis {replay.path}"], False
    lines: list[str] = []
    findings: list[Finding] = []
    for analysis in replay.analyses:
        shown = f"{replay.path}/{analysis.path}"
        code = analysis.document["analysisCode"]
        lines.append(
            f"replayed    {shown}  ({len(analysis.document['inputs'])} input "
            f"file(s), code {analysis.code})"
        )
        lines.extend(
            f"            source differs  {path}" for path in analysis.changed_sources
        )
        state, differing = revision_state(
            code,
            lambda revision: _commit_present(code_root, revision),
            lambda revision, path: _blob(code_root, revision, path),
            lambda revision, package: _tracked(code_root, revision, package),
        )
        if state == CODE_DIFFERS:
            findings.append(
                Finding(
                    shown,
                    RULE_REVISION,
                    f"{len(differing)} source file(s) of the stated commit are not "
                    "the stated ones",
                )
            )
        elif state == REVISION_NOT_CHECKED:
            lines.append(
                "            revision  not-checked: the clone does not hold the "
                "stated commit, or Git is not available"
            )
        else:
            lines.append("            revision  held")
    if findings:
        return [*lines, *_refusal(replay.path, findings)], True
    return lines, False


def _verify(paths: Sequence[Path], root: Path) -> int:
    refused = False
    for path in sorted(paths):
        replay = replay_run(path, root)
        lines, failed = _replay_lines(replay, REPO_ROOT)
        if replay.status == NO_ANALYSIS:
            lines = _refusal(
                replay.path,
                [
                    Finding(
                        replay.path,
                        RULE_MISSING,
                        "the manifest names no file with the role analysis, so "
                        "nothing was computed again",
                    )
                ],
            )
            failed = True
        refused = refused or failed
        _say(lines)
    return REFUSED_EXIT if refused else 0


def _repository(root: Path) -> int:
    listing = manifest_listing(root)
    refused = bool(listing.findings)
    for finding in listing.findings:
        print(f"REFUSED     the pre-schema register  {finding.rule}")
    counts = {PRE_SCHEMA: 0, NO_ANALYSIS: 0, REPLAYED: 0, REFUSED: 0}
    for manifest in listing.manifests:
        run_ref = manifest.path.rsplit("/", 1)[0]
        if manifest.status == PRE_SCHEMA:
            counts[PRE_SCHEMA] += 1
            _say([f"pre-schema  {printable(run_ref)}  (not replayed)"])
            continue
        replay = replay_run(root / run_ref, root)
        lines, failed = _replay_lines(replay, REPO_ROOT)
        counts[REFUSED if failed else replay.status] += 1
        refused = refused or failed
        _say(lines)
    print(
        f"runs        {sum(counts.values())}: {counts[PRE_SCHEMA]} pre-schema and "
        f"not replayed, {counts[NO_ANALYSIS]} with no analysis, "
        f"{counts[REPLAYED]} replayed, {counts[REFUSED]} refused"
    )
    return REFUSED_EXIT if refused else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.analysis_replay",
        description=(
            "Bind the analysis of an experiment run to its evidence, and compute "
            "it again. The command writes no file."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    binder = commands.add_parser("bind", help="print the run analysis of one run")
    binder.add_argument("run", type=Path, help="the run directory")
    binder.add_argument("--declaration", required=True, type=Path)
    verifier = commands.add_parser(
        "verify", help="compute each run analysis of the run directories again"
    )
    verifier.add_argument("runs", nargs="+", type=Path, help="run directories")
    lister = commands.add_parser(
        "repository", help="replay every run directory under docs/proof/experiments"
    )
    aggregator = commands.add_parser(
        "aggregate", help="print one figure of each run and the median of three"
    )
    aggregator.add_argument("--metric", required=True, choices=tuple(AGGREGATE_METRICS))
    aggregator.add_argument("runs", nargs="+", type=Path, help="run directories")
    commands.add_parser("sources", help="print the digest of each source file")
    for command in (binder, verifier, lister, aggregator):
        command.add_argument(
            "--root",
            type=Path,
            default=REPO_ROOT,
            help="the root of the tree that holds docs/proof/experiments",
        )
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "verify":
            return _verify(arguments.runs, arguments.root)
        if arguments.command == "repository":
            return _repository(arguments.root)
        if arguments.command == "sources":
            print(
                "\n".join(
                    f"{row['sha256']}  {row['path']}" for row in analysis_sources()
                )
            )
            return 0
        revision = checkout_revision()
        if arguments.command == "bind":
            try:
                declaration = arguments.declaration.read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError) as fault:
                raise ReplayRefused(
                    RULE_ANALYSIS, "the declaration is not readable UTF-8 text"
                ) from fault
            document = bind_run(arguments.run, declaration, revision, arguments.root)
        else:
            document = aggregate_runs(
                arguments.metric,
                arguments.runs,
                revision,
                arguments.root,
                history(arguments.root),
            )
    except ReplayRefused as refused:
        shown = str(refused).encode("ascii", "backslashreplace").decode("ascii")
        print(f"REFUSED  {shown}", file=sys.stderr)
        return REFUSED_EXIT
    _emit(record_text(document))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    raise SystemExit(main())
