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
record of its manifest registers. ``sources`` prints the digest of each source
file of the analysis
code.

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
Git when the clone holds it. ``aggregate`` does not. No command contacts a
cluster or a caller. See docs/testing/analysis-replay.md.
"""

from __future__ import annotations

import argparse
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
                arguments.metric, arguments.runs, revision, arguments.root
            )
    except ReplayRefused as refused:
        shown = str(refused).encode("ascii", "backslashreplace").decode("ascii")
        print(f"REFUSED  {shown}", file=sys.stderr)
        return REFUSED_EXIT
    _emit(record_text(document))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    raise SystemExit(main())
