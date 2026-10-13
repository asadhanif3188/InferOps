"""The analysis of an experiment run, bound to its evidence and computed again.

``tools.reliability_analysis`` computes figures from files that a command names.
Its document states no digest of an input and no revision of the code, and
nothing computes a stored document again. This module closes both.

*A run analysis.* ``bind_run`` reads one run directory: the ExperimentRun
manifest and the raw evidence files that the manifest names. It computes the
reliability analysis and returns one document that states the run, the digest
of each input, the raw evidence digest of the run, the declaration, the
analysis, and the code that computed it.

*A replay.* ``replay_run`` reads a run directory whose manifest names a run
analysis. It holds the directory to the layout check, computes the document
again from the manifest, the evidence files, and the declaration that the
document states, and compares the two byte for byte.

**A stored document is not authoritative. The replay is.** A figure, a digest,
or a statement that a person changed in a stored document is a difference, and
the replay refuses the document. So is an evidence file that changed or is
absent: the layout check refuses the run directory first.

**The analysis code has two identities.** The commit identifier is what the
command read from the checkout. The source digest is taken over the Python
files of the registered source packages. The replay compares the source rows
with the files that are present, and it states when they differ. The command
compares the commit with Git when the commit is in the clone.

*An aggregate of runs.* ``aggregate_runs`` reads the run directories of one
experiment, takes the result of each run from its manifest, and gives the
median of three counted runs with each run listed.

**A result state alone leaves no run out of the median.** A run in the state
INCONCLUSIVE, REFUSED, or ABORTED is not counted only when the reason that
its manifest states is one that the freeze record of the manifest registers
for the experiment, the state, and the run, and the freeze registry of the
tree pins that record. The aggregate then states the reason and the record.
Otherwise the aggregate is refused.

**The module registers no claim.** A document that replays changes no claim
status and no evidence level. ``gate_problems`` lets the evidence index refuse
a run whose analysis does not replay. It promotes nothing.

The module reads files and writes none. It reads no Git object: the command
does. See docs/testing/analysis-replay.md and tests/testing/test_analysis_replay.py.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from tools.evidence_index.core import evidence_set_sha256
from tools.experiment_evidence import (
    REFUSED,
    Finding,
    check_run,
    is_raw,
    run_digests,
)
from tools.experiment_evidence.core import printable
from tools.experiment_freeze import load_registry
from tools.experiment_run.core import (
    CONFORMING,
    MANIFEST_NAME,
    REPO_ROOT,
    RunDocumentError,
    content_digest,
    read_document,
)
from tools.reliability_analysis import (
    AGGREGATE_METRICS,
    EXCLUDED_STATES,
    INPUTS,
    AnalysisRefused,
    RunResult,
    aggregate,
    analyze,
    read_declaration,
)
from tools.reliability_analysis import SCHEMA as ANALYSIS_SCHEMA
from tools.reliability_analysis.core import RULE_EXCLUSION as ANALYSIS_EXCLUSION
from tools.reliability_analysis.core import (
    RULE_EXCLUSION_REASONS as ANALYSIS_EXCLUSION_REASONS,
)

__all__ = [
    "AGGREGATE_RULES",
    "AGGREGATE_SCHEMA",
    "ANALYSIS_ROLE",
    "AUTHORITY",
    "CODE_DIFFERS",
    "CODE_SAME",
    "DOES_NOT_ESTABLISH",
    "EXCLUSION_REASONS_MEMBER",
    "LIMITATIONS",
    "NO_ANALYSIS",
    "REFUSED",
    "REFUSED_EXIT",
    "REPLAYED",
    "REVISION_HELD",
    "REVISION_NOT_CHECKED",
    "RULES",
    "SCHEMA",
    "SOURCE_PACKAGES",
    "AnalysisReplay",
    "ReplayRefused",
    "RunReplay",
    "aggregate_runs",
    "analysis_code",
    "analysis_sources",
    "bind_run",
    "gate_problems",
    "record_text",
    "replay_run",
    "revision_state",
]

#: The schema name of a run analysis.
SCHEMA: Final = "inferops.io/run-analysis/v1alpha1"

#: The schema name of an aggregate of runs.
AGGREGATE_SCHEMA: Final = "inferops.io/run-aggregate/v1alpha2"

#: The role of the evidence layout that a run analysis has.
ANALYSIS_ROLE: Final = "analysis"

#: The exit status of a command that refused a run directory or a document.
REFUSED_EXIT: Final = 3

#: The packages under ``tools`` whose Python files the source digest covers: this
#: tool, the analysis, the reader of each input, the caller profile that the
#: reader of a caller record holds a header to, and the tier names they share.
SOURCE_PACKAGES: Final = (
    "analysis_replay",
    "experiment_events",
    "experiment_timeline",
    "reliability_analysis",
    "reliability_profile",
    "reliability_runner",
    "service_endpoint_state",
)

#: The states of a replay of one run directory. The third is ``refused``, the
#: status that the layout check gives a run directory that a rule refused.
REPLAYED: Final = "replayed"
NO_ANALYSIS: Final = "no-analysis"

#: Whether the source files that are present are those that a document states.
CODE_SAME: Final = "same"
CODE_DIFFERS: Final = "differs"

#: The states of the comparison of a stated commit with Git.
REVISION_HELD: Final = "held"
REVISION_NOT_CHECKED: Final = "not-checked"

RULE_RUN: Final = "replay-run-directory-refused"
RULE_INPUT_AMBIGUOUS: Final = "replay-input-ambiguous"
RULE_DECLARATION_IDENTITY: Final = "replay-declaration-identity-differs"
RULE_ANALYSIS: Final = "replay-analysis-refused"
RULE_MISSING: Final = "replay-analysis-missing"
RULE_RECORD_UNREADABLE: Final = "replay-record-unreadable"
RULE_RECORD_FORM: Final = "replay-record-form-unsupported"
RULE_EVIDENCE: Final = "replay-evidence-differs"
RULE_DOCUMENT: Final = "replay-document-differs"
RULE_REVISION: Final = "replay-revision-differs"
RULE_UNCOMMITTED: Final = "replay-code-not-committed"
RULE_AGGREGATE: Final = "replay-aggregate-unsupported"
RULE_AGGREGATE_OMITTED: Final = "replay-aggregate-run-omitted"
RULE_AGGREGATE_RUN: Final = "replay-aggregate-run-refused"
RULE_EXCLUSION_RECORD: Final = "replay-exclusion-record-unpinned"
RULE_EXCLUSION: Final = "replay-exclusion-refused"

#: The member of a freeze record that states its exclusion reasons.
EXCLUSION_REASONS_MEMBER: Final = "exclusionReasons"

#: Each rule of refusal, with its statement.
RULES: Final[Mapping[str, str]] = {
    RULE_RUN: (
        "The layout check accepts the run directory: each file that the manifest "
        "names is present with its stated digest, and each file that is present "
        "is named."
    ),
    RULE_INPUT_AMBIGUOUS: (
        "A run names at most one file with each role that the analysis reads."
    ),
    RULE_DECLARATION_IDENTITY: (
        "The declaration names the experiment and the run of the manifest."
    ),
    RULE_ANALYSIS: (
        "The reliability analysis accepts the declaration and the evidence files "
        "of the run. The refusal names the rule of that tool."
    ),
    RULE_MISSING: (
        "A run directory that is given to be computed again names at least one "
        "file with the role analysis."
    ),
    RULE_RECORD_UNREADABLE: (
        "A file with the role analysis is one JSON object with no member stated "
        "twice, and it states the schema name of a run analysis."
    ),
    RULE_RECORD_FORM: (
        "A run analysis states its declaration as an object, and its analysis code "
        "as a commit identifier, a source digest, and source rows in their form. "
        "The source digest is the digest of the rows."
    ),
    RULE_EVIDENCE: (
        "A run analysis states the experiment, the run, the run directory, the raw "
        "evidence digest, and the path and the digest of each input as the "
        "manifest of the run gives them."
    ),
    RULE_DOCUMENT: (
        "A run analysis is, byte for byte, the document that the tool computes from "
        "the manifest, the evidence files, and the declaration that the document "
        "states."
    ),
    RULE_REVISION: (
        "Each source file has, at the commit that a run analysis states, the digest "
        "that the run analysis states for it."
    ),
    RULE_UNCOMMITTED: (
        "A document is computed by source files that are the files of the commit "
        "that it states."
    ),
    RULE_AGGREGATE: (
        "An aggregate is asked for a registered metric of run directories of one "
        "runs directory and one experiment, each given once, and each with at most "
        "one run analysis."
    ),
    RULE_AGGREGATE_OMITTED: (
        "An aggregate is given each run directory of the runs directory whose "
        "manifest names the experiment, and each directory there that is not given "
        "conforms to the layout."
    ),
    RULE_AGGREGATE_RUN: (
        "Each run of an aggregate conforms to the layout, and its run analysis replays."
    ),
    RULE_EXCLUSION_RECORD: (
        "The freeze registry of the tree pins the freeze record that the manifest "
        "of each run that is not counted names, with the content digest that the "
        "manifest states, and that record is one JSON object."
    ),
    RULE_EXCLUSION: (
        "The reliability analysis accepts the reason of each run that is not "
        "counted against the exclusion reasons of the freeze record that the "
        "manifest of the run names. The refusal names the rule of that tool."
    ),
}

#: What a stored run analysis is, stated in each document.
AUTHORITY: Final = (
    "A replay computes this document from the manifest, the evidence files, and "
    "the declaration below. A copy that a replay does not reproduce byte for byte "
    "is not an analysis of the run."
)

#: The limits of a run analysis, stated in each document.
LIMITATIONS: Final[tuple[str, ...]] = (
    "The declaration is a part of this document, and it is not held to a frozen "
    "record of an experiment. A document with another declaration replays as "
    "another analysis.",
    "The source digest covers the Python files of the registered source packages. "
    "It does not cover a module of another package that those files import, the "
    "interpreter, or a library.",
    "The commit identifier is the one that the command read from its checkout. A "
    "replay compares it with Git only when the commit is in the clone.",
    "A replay with source files that differ from the stated ones compares the "
    "document with what the present code computes. It does not run the stated "
    "code.",
    "A run directory, its manifest, and this document, replaced together, replay. "
    "A replay reads one tree and not Git.",
    "A replay reads the files that the manifest names. It reads no correction of "
    "the run.",
    "The document does not state the digest of the manifest, because the manifest "
    "states the digest of this document.",
)

#: What a run analysis does not establish, stated in each document.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "That the evidence files are the evidence of a real run. A replay reads the "
    "files of a run directory.",
    "The result state of the run. The manifest states it, and no figure here is "
    "compared with a bound.",
    "A claim status or an evidence level. A document that replays registers no "
    "claim and certifies none.",
    "That the declared window, expected state, and signals are those that an "
    "experiment froze.",
    "That the stated commit is the code that computed the document, when the "
    "commit is not in the clone that replays it.",
)

#: The rules of an aggregate of runs, stated in each aggregate document.
AGGREGATE_RULES: Final[tuple[str, ...]] = (
    "Each run directory of the runs directory whose manifest names the experiment "
    "is given and is listed. No run is left out.",
    "The result state and the reason of each run are read from its manifest.",
    "A run in the state PASSED or FAILED is counted. A run that worsens the figure "
    "is not dropped.",
    "A run in the state INCONCLUSIVE, REFUSED, or ABORTED is not counted only when "
    "the reason of its manifest is, character for character, a reason that the "
    "freeze record of the manifest registers for the experiment, the result state, "
    "and the run, and the freeze registry of the tree pins that record. Otherwise "
    "the aggregate is refused. A result state alone leaves no run out.",
    "A run that is not counted is listed with its value, the reason of its "
    "manifest, the identifier of the registered reason, and the freeze record.",
    "A counted run with no run analysis, or with no value for the figure, leaves "
    "the aggregate with no median.",
    "The median is stated for exactly three counted runs. No confidence interval "
    "and no statistical significance is stated.",
)

_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_DIGEST: Final = re.compile(r"[0-9a-f]{64}")
_SOURCE_PATH: Final = re.compile(r"tools(/[A-Za-z0-9_]+)+\.py")
_CODE_MEMBERS: Final = frozenset({"revision", "sourceSha256", "sources"})
_ROW_MEMBERS: Final = frozenset({"path", "sha256"})


class ReplayRefused(Exception):
    """A run directory, a declaration, or a document that the tool does not accept."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule
        self.message = message
        #: The run directory as the layout check shows it, when that check refused.
        self.path: str | None = None


# --------------------------------------------------------------------------
# The analysis code
# --------------------------------------------------------------------------


def analysis_sources(root: Path = REPO_ROOT) -> list[dict[str, str]]:
    """Each Python file of the registered source packages, with its digest.

    The digest is the SHA-256 of the file's content with each CRLF replaced by
    LF, so a Windows checkout and the content that Git stores give one digest.
    The rows are in the order of their paths as text. A file is a source file
    when its name ends with ``.py`` in lower case: the suffix is compared as
    text, so a file system that ignores letter case gives the same rows.
    """
    rows = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": content_digest(path.read_bytes()),
        }
        for package in SOURCE_PACKAGES
        for path in (root / "tools" / package).rglob("*")
        if path.name.endswith(".py") and path.is_file()
    ]
    return sorted(rows, key=lambda row: row["path"])


def analysis_code(revision: str, root: Path = REPO_ROOT) -> dict[str, Any]:
    """The identity of the analysis code: a commit and the digest of its sources.

    ``revision`` is the commit of the checkout. The caller reads it from Git,
    and this function reads no Git object.

    Raises:
        ReplayRefused: the revision is not a full commit identifier, or a source
            file has a path that a run analysis cannot state.
    """
    if not isinstance(revision, str) or _COMMIT.fullmatch(revision) is None:
        raise ReplayRefused(
            RULE_UNCOMMITTED, "the revision is not a full commit identifier"
        )
    sources = analysis_sources(root)
    code = {
        "revision": revision,
        "sourceSha256": evidence_set_sha256(sources),
        "sources": sources,
    }
    # A document that this function gives must be one that a replay accepts.
    problem = _code_problem(code)
    if problem is not None:
        raise ReplayRefused(RULE_UNCOMMITTED, problem)
    return code


def _code_problem(code: object) -> str | None:
    """Why a stated analysis code does not have its form, or None when it has."""
    if not isinstance(code, dict) or set(code) != _CODE_MEMBERS:
        return "the analysis code does not have its members"
    revision, digest, rows = code["revision"], code["sourceSha256"], code["sources"]
    if not isinstance(revision, str) or _COMMIT.fullmatch(revision) is None:
        return "the analysis code states no full commit identifier"
    if not isinstance(rows, list) or not rows:
        return "the analysis code states no source row"
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != _ROW_MEMBERS
            or not isinstance(row["path"], str)
            or _SOURCE_PATH.fullmatch(row["path"]) is None
            or not isinstance(row["sha256"], str)
            or _DIGEST.fullmatch(row["sha256"]) is None
        ):
            return "a source row is not a path under tools and a digest"
    paths = [row["path"] for row in rows]
    if paths != sorted(set(paths)):
        return "the source rows are not in order, or one path is stated twice"
    if digest != evidence_set_sha256(rows):
        return "the source digest is not the digest of the source rows"
    return None


def _changed_sources(
    stated: Sequence[Mapping[str, str]], present: Sequence[Mapping[str, str]]
) -> tuple[str, ...]:
    """Each source path whose stated digest is not the digest that is present."""
    before = {row["path"]: row["sha256"] for row in stated}
    now = {row["path"]: row["sha256"] for row in present}
    return tuple(
        sorted(
            path
            for path in before.keys() | now.keys()
            if before.get(path) != now.get(path)
        )
    )


def revision_state(
    code: Mapping[str, Any],
    commit_present: Callable[[str], bool],
    blob: Callable[[str, str], bytes | None],
    tracked: Callable[[str, str], Sequence[str] | None],
) -> tuple[str, tuple[str, ...]]:
    """Whether the stated source rows are the source files of the stated commit.

    ``commit_present`` says whether the clone holds a commit. ``blob`` gives the
    content of one path at a commit, or None when the commit has no such file.
    ``tracked`` gives each path that a commit holds under one directory, or
    None when it cannot say. The command gives the three from Git.

    The result is ``held`` with no path, ``not-checked`` with no path when the
    commit is not in the clone, or ``differs`` with each path that differs. A
    path differs when its file does not have the stated digest at the commit,
    and when the commit holds a Python file in the directory of a stated row
    that no row states. So a document that states some of the files of a
    package is not held. A package that no row names is not read.
    """
    revision = code["revision"]
    if not commit_present(revision):
        return REVISION_NOT_CHECKED, ()
    stated = {row["path"] for row in code["sources"]}
    differing: set[str] = set()
    for row in code["sources"]:
        data = blob(revision, row["path"])
        if data is None or content_digest(data) != row["sha256"]:
            differing.add(row["path"])
    for package in sorted({"/".join(path.split("/")[:2]) for path in stated}):
        held = tracked(revision, package)
        if held is None:
            differing.add(package)
            continue
        differing.update(
            path for path in held if path.endswith(".py") and path not in stated
        )
    if differing:
        return CODE_DIFFERS, tuple(sorted(differing))
    return REVISION_HELD, ()


# --------------------------------------------------------------------------
# One run directory
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Run:
    """A run directory that the layout check accepts."""

    ref: str
    directory: Path
    manifest: Mapping[str, Any]
    manifest_sha256: str

    @property
    def entries(self) -> Sequence[Mapping[str, str]]:
        entries: Sequence[Mapping[str, str]] = self.manifest["evidence"]["files"]
        return entries


def _shown(run_dir: Path, root: Path) -> str:
    """A run directory for an output line: its path under the root, or its name.

    A directory outside the root is shown by its name alone, so no line holds a
    path of a host.
    """
    try:
        return printable(run_dir.resolve().relative_to(root.resolve()).as_posix())
    except (OSError, ValueError):
        return printable(run_dir.name)


def _load_run(run_dir: Path, root: Path) -> _Run:
    """One run directory, held to the layout check.

    Raises:
        ReplayRefused: the layout check refuses the directory. The message names
            each rule of the layout that refused it, and no text of a file.
    """
    report = check_run(run_dir, root)
    if report.status != CONFORMING:
        rules = sorted({finding.rule for finding in report.findings})
        refused = ReplayRefused(
            RULE_RUN,
            "the layout check refuses the run directory: " + ", ".join(rules),
        )
        refused.path = _shown(run_dir, root)
        raise refused
    manifest_path = run_dir / MANIFEST_NAME
    return _Run(
        report.path,
        run_dir,
        read_document(manifest_path),
        content_digest(manifest_path.read_bytes()),
    )


def _text(run: _Run, relative: str) -> str:
    """An evidence file as text, with each CRLF replaced by LF.

    The digest of a file does not move between a CRLF checkout and the stored
    content. So the analysis reads the same text on each host.
    """
    data = (run.directory / relative).read_bytes()
    return data.replace(b"\r\n", b"\n").decode("utf-8")


def _inputs(run: _Run) -> list[dict[str, str]]:
    """The one file of each role that the analysis reads, in the order of the roles."""
    found: list[dict[str, str]] = []
    for name in INPUTS:
        named = [entry for entry in run.entries if entry["role"] == name]
        if len(named) > 1:
            raise ReplayRefused(
                RULE_INPUT_AMBIGUOUS,
                f"the run names {len(named)} files with the role {name}",
            )
        if named:
            found.append(
                {"name": name, "path": named[0]["path"], "sha256": named[0]["sha256"]}
            )
    return found


def _analysis_refusal(refused: AnalysisRefused) -> ReplayRefused:
    """A refusal of the reliability analysis, with its rule and not its message.

    A message of that tool can quote a value of the declaration, such as the
    identifier of a signal. A stored document holds a declaration, so a refusal
    here names the rule alone.
    """
    return ReplayRefused(
        RULE_ANALYSIS, f"the reliability analysis refuses the inputs: {refused.rule}"
    )


def _record(
    run: _Run, declaration_text: str, code: Mapping[str, Any]
) -> dict[str, Any]:
    """The run analysis that a run directory, a declaration, and a code identity give."""
    try:
        declaration = read_declaration(declaration_text)
    except AnalysisRefused as refused:
        raise _analysis_refusal(refused) from refused
    metadata = run.manifest["metadata"]
    experiment, run_id = metadata["experimentId"], metadata["runId"]
    if (declaration["experimentId"], declaration["runId"]) != (experiment, run_id):
        raise ReplayRefused(
            RULE_DECLARATION_IDENTITY,
            "the declaration names another experiment or another run than the manifest",
        )
    inputs = _inputs(run)
    texts: dict[str, str | None] = dict.fromkeys(INPUTS)
    for entry in inputs:
        texts[entry["name"]] = _text(run, entry["path"])
    try:
        analysis = analyze(declaration_text, texts)
    except AnalysisRefused as refused:
        raise _analysis_refusal(refused) from refused
    given = {entry["name"] for entry in inputs}
    return {
        "schema": SCHEMA,
        "experimentId": experiment,
        "runId": run_id,
        "runDirectory": run.ref,
        "rawEvidence": {
            "sha256": run_digests(run.ref, run.manifest_sha256, run.manifest).raw,
            "files": sum(1 for entry in run.entries if is_raw(entry["role"])),
        },
        "inputs": inputs,
        "notGiven": [name for name in INPUTS if name not in given],
        "declaration": declaration,
        "analysisCode": dict(code),
        "analysis": analysis,
        "authority": AUTHORITY,
        "limitations": list(LIMITATIONS),
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def bind_run(
    run_dir: Path, declaration_text: str, revision: str, root: Path = REPO_ROOT
) -> dict[str, Any]:
    """The run analysis of one run directory.

    ``root`` is the root of the tree that holds the proof tree. ``revision`` is
    the commit of the checkout that holds the analysis code. The function reads
    the manifest and the raw evidence files that it names, and it writes
    nothing.

    Raises:
        ReplayRefused: a rule of :data:`RULES` is not held.
    """
    code = analysis_code(revision)
    return _record(_load_run(run_dir, root), declaration_text, code)


def record_text(document: Mapping[str, Any]) -> str:
    """A document as the text that is stored: sorted members, and one line feed last."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


class _Repeated(ValueError):
    """One JSON object states one member twice."""


def _no_repeat(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for name, value in pairs:
        if name in document:
            raise _Repeated(name)
        document[name] = value
    return document


@dataclass(frozen=True)
class AnalysisReplay:
    """One run analysis that a replay reproduced.

    ``code`` is ``same`` when each source file that is present has the digest
    that the document states, and ``differs`` otherwise. ``changed_sources``
    names each source path that differs. ``document`` is the run analysis.
    """

    path: str
    sha256: str
    code: str
    changed_sources: tuple[str, ...]
    document: Mapping[str, Any]


@dataclass(frozen=True)
class RunReplay:
    """What a replay found for one run directory.

    ``status`` is ``replayed`` when each run analysis of the run was reproduced,
    ``no-analysis`` when the manifest names no file with the role analysis, and
    ``refused`` otherwise.
    """

    path: str
    status: str
    analyses: tuple[AnalysisReplay, ...] = ()
    findings: tuple[Finding, ...] = ()


def _replay_one(
    run: _Run, entry: Mapping[str, str], present: Sequence[Mapping[str, str]]
) -> AnalysisReplay:
    """Compute one stored run analysis again, and hold the stored text to it."""
    stored = _text(run, entry["path"])
    try:
        document = json.loads(stored, object_pairs_hook=_no_repeat)
    except (ValueError, RecursionError):
        document = None
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise ReplayRefused(
            RULE_RECORD_UNREADABLE,
            "the file is not one JSON object that states the schema name of a run "
            "analysis",
        )
    declaration, code = document.get("declaration"), document.get("analysisCode")
    if not isinstance(declaration, dict):
        raise ReplayRefused(RULE_RECORD_FORM, "the declaration is not an object")
    problem = _code_problem(code)
    if problem is not None:
        raise ReplayRefused(RULE_RECORD_FORM, problem)
    assert isinstance(code, dict)
    try:
        declaration_text = json.dumps(declaration)
    except (ValueError, RecursionError) as fault:
        raise ReplayRefused(
            RULE_RECORD_FORM, "the declaration cannot be written as JSON"
        ) from fault
    expected = _record(run, declaration_text, code)
    for name in (
        "experimentId",
        "runId",
        "runDirectory",
        "rawEvidence",
        "inputs",
        "notGiven",
    ):
        if document.get(name) != expected[name]:
            raise ReplayRefused(
                RULE_EVIDENCE,
                f"the document states another {name} than the manifest gives",
            )
    changed = _changed_sources(code["sources"], present)
    if stored != record_text(expected):
        raise ReplayRefused(
            RULE_DOCUMENT,
            "the document is not what the evidence and its declaration give"
            + (
                f", and {len(changed)} source file(s) differ from the stated ones"
                if changed
                else ""
            ),
        )
    return AnalysisReplay(
        entry["path"],
        entry["sha256"],
        CODE_DIFFERS if changed else CODE_SAME,
        changed,
        document,
    )


def replay_run(run_dir: Path, root: Path = REPO_ROOT) -> RunReplay:
    """Compute each run analysis of a run directory again.

    The run directory is held to the layout check first, so an evidence file
    that changed or is absent refuses the replay before a figure is computed.
    Each file with the role analysis must be a run analysis, and each must be
    the text that the tool computes now. The function reads files and writes
    none.
    """
    try:
        run = _load_run(run_dir, root)
    except ReplayRefused as refused:
        shown = refused.path or _shown(run_dir, root)
        return RunReplay(
            shown, REFUSED, findings=(Finding(shown, refused.rule, refused.message),)
        )
    entries = [entry for entry in run.entries if entry["role"] == ANALYSIS_ROLE]
    if not entries:
        return RunReplay(run.ref, NO_ANALYSIS)
    present = analysis_sources()
    analyses: list[AnalysisReplay] = []
    findings: list[Finding] = []
    for entry in entries:
        try:
            analyses.append(_replay_one(run, entry, present))
        except ReplayRefused as refused:
            findings.append(
                Finding(f"{run.ref}/{entry['path']}", refused.rule, refused.message)
            )
    if findings:
        return RunReplay(run.ref, REFUSED, findings=tuple(sorted(findings)))
    return RunReplay(run.ref, REPLAYED, analyses=tuple(analyses))


def gate_problems(run_dir: Path, root: Path = REPO_ROOT) -> list[str]:
    """Why the analysis of a run does not replay, for the evidence index.

    A run whose manifest names no file with the role analysis has no problem:
    the gate holds an analysis and requires none. The manifest is read as JSON
    for that question and is not validated, so a manifest of an earlier shape
    is read too. A run that names such a file must replay in full. A role is
    read with its white space removed and in lower case, so a role in another
    spelling does not pass the gate, and the layout check then refuses it.

    A manifest that is present and cannot be read as one JSON object is a
    problem. So is an entry at the place of the manifest that is not a file,
    and a manifest whose ``evidence`` member is not an object with a list of
    objects that each state a role as text. A manifest with no ``evidence``
    member names no file. A run directory with no manifest names no analysis,
    and the gate does not hold it.

    The gate reads the role of a file and not its content. A document with the
    schema name of a run analysis under another role is not held.

    The gate promotes nothing. A run with no problem gets no claim, no claim
    status, and no evidence level from it.
    """
    manifest_path = run_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return []
    try:
        manifest = read_document(manifest_path)
    except (OSError, RunDocumentError):
        return ["the run manifest is not readable as one JSON object"]
    if "evidence" not in manifest:
        return []
    evidence = manifest["evidence"]
    files = evidence.get("files") if isinstance(evidence, dict) else None
    if not isinstance(files, list) or not all(
        isinstance(entry, dict) and isinstance(entry.get("role"), str)
        for entry in files
    ):
        return ["the run manifest does not state its evidence files with a role each"]
    if not any(entry["role"].strip().lower() == ANALYSIS_ROLE for entry in files):
        return []
    report = replay_run(run_dir, root)
    if report.status == NO_ANALYSIS:
        return ["the run manifest states the role analysis in another spelling"]
    return [f"{finding.rule}: {finding.message}" for finding in report.findings]


# --------------------------------------------------------------------------
# The aggregate of the runs of one experiment
# --------------------------------------------------------------------------


def _sibling_experiment(directory: Path, root: Path) -> str | None:
    """The experiment of a run directory that was not given, or None.

    The directory must conform to the layout. The layout check holds a caller
    record to the experiment of its manifest, so the experiment of a run with a
    caller record cannot be changed in the manifest alone to leave the run out.
    """
    try:
        run = _load_run(directory, root)
    except (OSError, ReplayRefused, RunDocumentError):
        return None
    experiment: str = run.manifest["metadata"]["experimentId"]
    return experiment


def _result(run: _Run, root: Path) -> RunResult:
    """The result of a run for an aggregate, with what its freeze record registers.

    A run in a counted state is given by its state, and no record is read for
    it. For another run the function reads the freeze record that the manifest
    names. The layout check held that record to the digest and the revision of
    the manifest. This function holds it to the freeze registry of the tree
    too, so a record that the registry does not pin registers no reason.

    Raises:
        ReplayRefused: the registry does not pin the record with the digest of
            the manifest, or the record cannot be read.
    """
    result = run.manifest["result"]
    state: str = result["state"]
    if state not in EXCLUDED_STATES:
        return RunResult(state)
    run_id = run.manifest["metadata"]["runId"]
    spec = run.manifest["metadata"]["spec"]
    try:
        pins = load_registry(root)
    except ValueError as fault:
        raise ReplayRefused(
            RULE_EXCLUSION_RECORD,
            f"the run {run_id} is not counted, and the tree has no freeze registry "
            "that can be read",
        ) from fault
    if pins.get(spec["freezeRecord"]) != spec["freezeContentSha256"]:
        raise ReplayRefused(
            RULE_EXCLUSION_RECORD,
            f"the run {run_id} is not counted, and the freeze registry does not pin "
            "its freeze record with the digest that its manifest states",
        )
    try:
        data = (root / spec["freezeRecord"]).read_bytes()
        record = json.loads(
            data.replace(b"\r\n", b"\n").decode("utf-8"), object_pairs_hook=_no_repeat
        )
    except (OSError, ValueError, RecursionError) as fault:
        raise ReplayRefused(
            RULE_EXCLUSION_RECORD,
            f"the freeze record of the run {run_id} cannot be read as one JSON object",
        ) from fault
    if (
        not isinstance(record, dict)
        or content_digest(data) != spec["freezeContentSha256"]
    ):
        raise ReplayRefused(
            RULE_EXCLUSION_RECORD,
            f"the freeze record of the run {run_id} is not the one JSON object that "
            "its manifest states",
        )
    return RunResult(
        state,
        result.get("reason"),
        record.get(EXCLUSION_REASONS_MEMBER),
        {
            "freezeRecord": spec["freezeRecord"],
            "freezeRevision": spec["freezeRevision"],
            "freezeContentSha256": spec["freezeContentSha256"],
        },
    )


def aggregate_runs(
    metric: str, run_dirs: Sequence[Path], revision: str, root: Path = REPO_ROOT
) -> dict[str, Any]:
    """One figure of each run of one experiment, with the median of three runs.

    Each run directory is held to the layout check, and its run analysis is
    computed again. The result state of a run is the one that its manifest
    states. A run in a state that is not counted is held to a reason that the
    freeze record of its manifest registers, and each row states how the
    manifest names that record.

    Each run directory of the same runs directory whose manifest names
    the experiment must be given, so no run is left out. The runs directory is
    read at its place under ``root``, and not at the spelling of an argument.
    The aggregate itself is the one of ``tools.reliability_analysis``.

    The function compares no commit with Git. Each row states the commit and
    the source digest that the run analysis of its run states, and whether the
    source files that are present are those.

    Raises:
        ReplayRefused: a rule of :data:`RULES` is not held.
    """
    if metric not in AGGREGATE_METRICS:
        raise ReplayRefused(RULE_AGGREGATE, "the metric is not registered")
    if not run_dirs:
        raise ReplayRefused(RULE_AGGREGATE, "no run directory was given")
    code = analysis_code(revision)
    rows: list[dict[str, Any]] = []
    documents: list[tuple[Mapping[str, Any], _Run]] = []
    experiments: set[str] = set()
    parents: set[str] = set()
    given: set[str] = set()
    for run_dir in run_dirs:
        replay = replay_run(run_dir, root)
        if replay.status == REFUSED:
            rules = sorted({finding.rule for finding in replay.findings})
            raise ReplayRefused(
                RULE_AGGREGATE_RUN,
                f"the run directory {printable(run_dir.name)} is refused: "
                + ", ".join(rules),
            )
        run = _load_run(run_dir, root)
        metadata = run.manifest["metadata"]
        experiment, run_id = metadata["experimentId"], metadata["runId"]
        if run_id in given:
            raise ReplayRefused(RULE_AGGREGATE, f"the run {run_id} is given twice")
        if len(replay.analyses) > 1:
            raise ReplayRefused(
                RULE_AGGREGATE, f"the run {run_id} names more than one run analysis"
            )
        given.add(run_id)
        experiments.add(experiment)
        parents.add(run.ref.rsplit("/", 1)[0])
        analysis = replay.analyses[0] if replay.analyses else None
        # A run with no run analysis has no figure. It is listed, and it is
        # counted when its state is counted, so it is not a run that is left out.
        document = (
            analysis.document["analysis"]
            if analysis is not None
            else {
                "schema": ANALYSIS_SCHEMA,
                "experimentId": experiment,
                "runId": run_id,
            }
        )
        documents.append((document, run))
        rows.append(
            {
                "runId": run_id,
                "runDirectory": run.ref,
                "manifestSha256": run.manifest_sha256,
                "preregistration": dict(metadata["spec"]),
                "rawEvidenceSha256": run_digests(
                    run.ref, run.manifest_sha256, run.manifest
                ).raw,
                "runAnalysis": None
                if analysis is None
                else {
                    "path": analysis.path,
                    "sha256": analysis.sha256,
                    "revision": analysis.document["analysisCode"]["revision"],
                    "sourceSha256": analysis.document["analysisCode"]["sourceSha256"],
                    "code": analysis.code,
                },
            }
        )
    if len(experiments) != 1 or len(parents) != 1:
        raise ReplayRefused(
            RULE_AGGREGATE,
            "the run directories are not of one runs directory and one experiment",
        )
    experiment = experiments.pop()
    runs_ref = next(iter(parents))
    runs_directory = root / runs_ref
    try:
        names = sorted(os.listdir(runs_directory))
    except OSError as fault:
        raise ReplayRefused(
            RULE_AGGREGATE_OMITTED, "the runs directory cannot be listed"
        ) from fault
    for name in names:
        sibling = runs_directory / name
        if name in given or not sibling.is_dir():
            continue
        named = _sibling_experiment(sibling, root)
        if named is None:
            raise ReplayRefused(
                RULE_AGGREGATE_OMITTED,
                f"the directory {printable(name)} beside the given runs does not "
                "conform to the layout, so its experiment is not known",
            )
        if named == experiment:
            raise ReplayRefused(
                RULE_AGGREGATE_OMITTED,
                f"the run directory {printable(name)} names the experiment and was "
                "not given",
            )
    # The result of each run is read after the all-run rule, so a run that
    # was left out is stated before a reason is.
    pairs: list[tuple[Mapping[str, Any], str | RunResult]] = [
        (document, _result(run, root)) for document, run in documents
    ]
    try:
        figures = aggregate(metric, pairs)
    except AnalysisRefused as refused:
        if refused.rule in (ANALYSIS_EXCLUSION, ANALYSIS_EXCLUSION_REASONS):
            raise ReplayRefused(RULE_EXCLUSION, str(refused)) from refused
        raise ReplayRefused(RULE_AGGREGATE, str(refused)) from refused
    return {
        "schema": AGGREGATE_SCHEMA,
        "experimentId": experiment,
        "runsDirectory": runs_ref,
        "metric": metric,
        "runs": sorted(rows, key=lambda row: str(row["runId"])),
        "aggregate": figures,
        "analysisCode": code,
        "rules": list(AGGREGATE_RULES),
        "authority": (
            "This document is the output of the command for the run directories "
            "that it lists. No check holds a stored copy. Run the command again and "
            "compare the two. The analysis code below is that of the command. Each "
            "run states the code of its own run analysis."
        ),
    }
