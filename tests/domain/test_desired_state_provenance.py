"""The provenance of the desired-state release, read at a Git commit.

An Argo CD Application follows ``main``, and ``main`` is a name that moves. The
controller reports the commit it resolved. ``tools.desired_state_provenance``
reads the desired-state release as a commit holds it, and this suite holds that
tool to the committed release, to the Application's declared source, and to the
labels the chart derives.

Five things are held:

* a full commit identifier resolves to one record, a branch name, a tag name,
  an abbreviated commit, and a placeholder are refused before Git runs, and the
  identifier of a tag object or a tree is refused after it;
* the declared files are read from the commit and not from the working tree, the
  record holds identifiers and digests only, and one commit gives one document;
* each defect planted in a commit of a temporary repository is refused under the
  rules it breaks: an absent file, an edited values file, an edited release
  identifier, a changed contract, a contract that has no digest, and a chart
  without an application version or with a numeric version;
* the record agrees with the committed Application's source, with the commit the
  three recorded runs reported, and with the labels of every rendered object;
* the tool derives no label that the chart does not already set, no scrape job
  reads one of those labels, and the tool runs one Git subcommand, `cat-file`, in
  two read-only forms, without the caller's `GIT_*` variables.

What this establishes about a cluster: nothing. No test reads one. The labels are
read from a render, and the reported commit is read from committed transcripts.
Whether an applied object carries the labels, and which commit a controller
reports now, are observations that this suite does not make.

Most tests run Git. The planted-defect tests create a repository under pytest's
temporary directory. One test reads a commit of this repository's history and
skips in a checkout that does not hold it.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain.release import is_credential_shaped
from inferops.domain.render import RELEASE_FILE_NAME, VALUES_FILE_NAME
from tools.desired_state_provenance import (
    CHART_LABEL,
    RECORD_SCHEMA,
    RULES,
    VERSION_LABEL,
    WORKLOAD_LABEL,
    Provenance,
    ProvenanceRefused,
    ReconciliationSource,
    is_immutable_revision,
    metadata_findings,
    observed_revision_findings,
    resolve,
    source_findings,
)
from tools.desired_state_provenance import core as provenance_core
from tools.generated_release import GENERATED_FILES
from tools.gitops_desired_state import DESIRED_STATE_RELEASES, release_key

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
DECLARED = DESIRED_STATE_RELEASES[0]
RELEASE_REL = f"{DECLARED.directory}/rendered-workload-release.yaml"
VALUES_REL = f"{DECLARED.directory}/values.generated.yaml"
CHART_REL = "charts/inferops-llm"
CHART_FILE_REL = f"{CHART_REL}/Chart.yaml"
HELPERS_PATH = REPO_ROOT / CHART_REL / "templates" / "_helpers.tpl"
REAL_RENDER_PATH = REPO_ROOT / CHART_REL / "ci" / "rendered" / "real.expected.yaml"
APPLICATION_PATH = (
    REPO_ROOT / "infra" / "argocd" / "local-docker-desktop-support-assistant.yaml"
)
DOCUMENT_PATH = REPO_ROOT / "docs" / "environment" / "desired-state-provenance.md"
TOOL_CORE_PATH = REPO_ROOT / "tools" / "desired_state_provenance" / "core.py"
TRANSCRIPTS = tuple(
    REPO_ROOT
    / "docs"
    / "proof"
    / "environment"
    / f"v2-s3-002-pr2-argocd-application-run-{run}-transcript.txt"
    for run in (1, 2, 3)
)

# Restated on purpose. A value read from the manifest would agree with the
# manifest by construction.
REPOSITORY = "https://github.com/asadhanif3188/InferOps.git"
FOLLOWED_REVISION = "main"
RECORDED_RELEASE_ID = "eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae"
RECORDED_RUN_REVISION = "293767b6c27d858e911e5e43104ad74fbfac4b02"
PLACEHOLDER_DIGEST = "sha256:" + "0" * 64

#: A full commit identifier that this repository does not hold.
UNKNOWN_REVISION = "0123456789abcdef0123456789abcdef01234567"


def run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not on PATH")
    # A hook sets GIT_DIR and GIT_INDEX_FILE. Without this, a commit meant for a
    # temporary repository would go to the repository the hook runs in.
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith("GIT_")
    }
    return subprocess.run(
        [
            git,
            "-C",
            str(root),
            "-c",
            "user.name=InferOps test",
            "-c",
            "user.email=test@inferops.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.autocrlf=false",
            *arguments,
        ],
        capture_output=True,
        check=False,
        timeout=120,
        env=environment,
    )


def head_of(root: Path) -> str:
    result = run_git(root, "rev-parse", "HEAD")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout.decode("ascii").strip()


def blob_at(revision: str, path: str) -> bytes:
    result = run_git(REPO_ROOT, "cat-file", "blob", f"{revision}:{path}")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout


def rule_ids(refused: ProvenanceRefused) -> set[str]:
    return {finding.rule_id for finding in refused.findings}


@pytest.fixture(scope="module")
def head() -> str:
    return head_of(REPO_ROOT)


@pytest.fixture(scope="module")
def record(head: str) -> Provenance:
    return resolve(head, DECLARED)


# --------------------------------------------------------------------------
# The committed release at a commit
# --------------------------------------------------------------------------


def test_one_desired_state_release_is_declared() -> None:
    """The suite reads one release. A second one is a second set of assertions."""
    assert len(DESIRED_STATE_RELEASES) == 1
    assert release_key(DECLARED) == "local-docker-desktop/support-assistant"


def test_the_head_commit_resolves_to_the_committed_release(
    head: str, record: Provenance
) -> None:
    release = yaml.safe_load(blob_at(head, RELEASE_REL))
    chart = yaml.safe_load(blob_at(head, CHART_FILE_REL))
    assert record.revision == head
    assert record.key == release_key(DECLARED)
    assert record.directory == DECLARED.directory
    assert record.release_id == release["metadata"]["releaseId"]
    assert record.workload_id == release["metadata"]["workloadId"]
    assert record.workload_version == release["metadata"]["workloadVersion"]
    assert record.values_sha256 == release["output"]["helmValues"]["sha256"]
    assert record.contract_sha256 == release["source"]["contract"]["sha256"]
    binding = release["source"]["environmentBinding"]
    assert record.binding_name == binding["name"] == DECLARED.binding_name
    assert record.binding_environment == binding["environment"]
    assert record.binding_sha256 == binding["sha256"]
    assert record.renderer_revision == release["source"]["renderer"]["revision"]
    assert (
        record.platform_defaults_revision
        == release["source"]["platformDefaults"]["revision"]
    )
    assert record.chart_path == CHART_REL
    assert (record.chart_name, record.chart_version, record.chart_app_version) == (
        chart["name"],
        chart["version"],
        chart["appVersion"],
    )
    assert record.release_path == RELEASE_REL
    assert record.values_path == VALUES_REL


def test_the_record_is_a_document_of_identifiers_and_digests(
    record: Provenance,
) -> None:
    document = record.as_document()
    assert document["schema"] == RECORD_SCHEMA
    assert set(document) == {
        "schema",
        "git",
        "desiredState",
        "release",
        "chart",
        "workloadLabels",
    }
    assert set(document["git"]) == {"revision"}
    assert set(document["release"]) == {
        "releaseId",
        "workloadId",
        "workloadVersion",
        "valuesSha256",
        "contractSha256",
        "environmentBinding",
        "rendererRevision",
        "platformDefaultsRevision",
    }

    def leaves(node: Any) -> Iterator[Any]:
        if isinstance(node, dict):
            for value in node.values():
                yield from leaves(value)
        else:
            yield node

    values = list(leaves(document))
    assert all(isinstance(value, str) and value for value in values)
    # No leaf has the published prefix of a credential format, at its start or
    # after a separator. This is the release domain's heuristic, and it is a
    # heuristic: it knows the prefixes it was given.
    assert not [value for value in values if is_credential_shaped(value)]
    # The record names no host, no user, and no time.
    text = json.dumps(document, sort_keys=True)
    assert not re.search(r"\d{4}-\d{2}-\d{2}T|[A-Za-z]:\\\\|/home/|/Users/", text)


def test_one_commit_gives_one_document(head: str, record: Provenance) -> None:
    again = resolve(head, DECLARED)
    assert again == record
    assert json.dumps(again.as_document(), sort_keys=True) == json.dumps(
        record.as_document(), sort_keys=True
    )


# --------------------------------------------------------------------------
# A revision is a commit, in full
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "revision",
    [
        FOLLOWED_REVISION,
        "HEAD",
        "refs/heads/main",
        "v1.0.0",
        "293767b",
        RECORDED_RUN_REVISION[:39],
        RECORDED_RUN_REVISION + "0",
        RECORDED_RUN_REVISION.upper(),
        f" {RECORDED_RUN_REVISION}",
        f"{RECORDED_RUN_REVISION}\n",
        f"{RECORDED_RUN_REVISION}^",
        "a" * 40,
        "",
    ],
)
def test_a_name_that_can_move_is_refused_before_git_runs(
    revision: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_git(*_: object, **__: object) -> None:
        raise AssertionError("Git ran for a revision that is not a full commit")

    monkeypatch.setattr(provenance_core, "_git", no_git)
    assert not is_immutable_revision(revision)
    with pytest.raises(ProvenanceRefused) as refused:
        resolve(revision, DECLARED)
    assert rule_ids(refused.value) == {"revision-not-immutable"}


@pytest.mark.parametrize("value", [None, 7, b"a" * 40, ("main",)])
def test_a_value_that_is_not_text_is_not_a_revision(value: object) -> None:
    assert not is_immutable_revision(value)


def test_a_commit_the_repository_does_not_hold_is_refused() -> None:
    assert is_immutable_revision(UNKNOWN_REVISION)
    with pytest.raises(ProvenanceRefused) as refused:
        resolve(UNKNOWN_REVISION, DECLARED)
    assert rule_ids(refused.value) == {"revision-not-readable"}


def test_an_object_that_is_not_a_commit_is_refused(head: str) -> None:
    tree = run_git(REPO_ROOT, "rev-parse", f"{head}^{{tree}}")
    assert tree.returncode == 0
    with pytest.raises(ProvenanceRefused) as refused:
        resolve(tree.stdout.decode("ascii").strip(), DECLARED)
    assert rule_ids(refused.value) == {"revision-not-readable"}


def test_the_identifier_of_a_tag_object_is_refused(clone: tuple[Path, str]) -> None:
    """Git peels a tag object to its commit. The tool does not: the record would
    name an identifier that is not a commit."""
    root, revision = clone
    assert run_git(root, "tag", "-a", "v1", "-m", "a tag").returncode == 0
    tag = run_git(root, "rev-parse", "v1").stdout.decode("ascii").strip()
    assert is_immutable_revision(tag) and tag != revision
    assert run_git(root, "cat-file", "-t", tag).stdout.strip() == b"tag"
    with pytest.raises(ProvenanceRefused) as refused:
        resolve(tag, DECLARED, root)
    assert rule_ids(refused.value) == {"revision-not-readable"}
    assert resolve(revision, DECLARED, root).revision == revision


def test_a_directory_that_is_not_a_repository_is_refused(
    head: str, tmp_path: Path
) -> None:
    with pytest.raises(ProvenanceRefused) as refused:
        resolve(head, DECLARED, tmp_path)
    assert rule_ids(refused.value) == {"revision-not-readable"}


def test_the_callers_git_variables_do_not_replace_the_root(
    head: str, record: Provenance, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hook sets `GIT_DIR`. The tool reads the repository it is given."""
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "no-such-repository"))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(tmp_path / "no-objects"))
    assert resolve(head, DECLARED) == record


def test_a_host_without_git_is_refused_and_not_an_error(
    head: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(ProvenanceRefused) as refused:
        resolve(head, DECLARED)
    assert rule_ids(refused.value) == {"revision-not-readable"}


# --------------------------------------------------------------------------
# Defects planted in a commit
# --------------------------------------------------------------------------


def _committed_inputs() -> tuple[str, ...]:
    return (
        RELEASE_REL,
        VALUES_REL,
        DECLARED.contract,
        *DECLARED.bindings,
        CHART_FILE_REL,
    )


def _commit(root: Path, message: str) -> str:
    assert run_git(root, "add", "--all").returncode == 0
    committed = run_git(root, "commit", "--quiet", "--allow-empty", "-m", message)
    assert committed.returncode == 0, committed.stderr.decode("utf-8", "replace")
    return head_of(root)


@pytest.fixture
def clone(tmp_path: Path, head: str) -> tuple[Path, str]:
    """A repository that holds the release's inputs as this repository's commit does."""
    root = tmp_path / "repository"
    root.mkdir()
    assert run_git(root, "init", "--quiet").returncode == 0
    for relative in _committed_inputs():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob_at(head, relative))
    return root, _commit(root, "the release and its inputs")


def test_the_copied_commit_resolves_to_the_same_identities(
    clone: tuple[Path, str], record: Provenance
) -> None:
    root, revision = clone
    copied = resolve(revision, DECLARED, root)
    assert copied.revision == revision != record.revision
    assert copied.release_id == record.release_id
    assert copied.as_document()["release"] == record.as_document()["release"]
    assert copied.as_document()["chart"] == record.as_document()["chart"]


def test_the_working_tree_is_not_read(clone: tuple[Path, str]) -> None:
    """An uncommitted edit changes nothing, and neither does a deleted file."""
    root, revision = clone
    before = resolve(revision, DECLARED, root)
    (root / VALUES_REL).write_text("edited: true\n", encoding="utf-8")
    (root / RELEASE_REL).unlink()
    (root / CHART_FILE_REL).write_text("name: other\n", encoding="utf-8")
    assert resolve(revision, DECLARED, root) == before


def test_a_commit_without_the_release_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    assert run_git(root, "init", "--quiet").returncode == 0
    revision = _commit(root, "an empty commit")
    with pytest.raises(ProvenanceRefused) as refused:
        resolve(revision, DECLARED, root)
    assert rule_ids(refused.value) == {"desired-state-absent-at-revision"}
    assert sorted(f.subject for f in refused.value.findings) == sorted(
        _committed_inputs()
    )


def _edit(relative: str, old: str, new: str) -> Callable[[Path], None]:
    def apply(root: Path) -> None:
        path = root / relative
        text = path.read_bytes().decode("utf-8")
        assert text.count(old) >= 1, f"{old!r} is not in {relative}"
        path.write_bytes(text.replace(old, new, 1).encode("utf-8"))

    return apply


def _remove(relative: str) -> Callable[[Path], None]:
    return lambda root: (root / relative).unlink()


def _write(relative: str, content: str) -> Callable[[Path], None]:
    def apply(root: Path) -> None:
        (root / relative).write_bytes(content.encode("utf-8"))

    return apply


def _other(identifier: str) -> str:
    """The same identifier with another first character, so its form still holds."""
    return ("0" if identifier[0] != "0" else "1") + identifier[1:]


#: The release the tree holds, read from the committed file. Two planted defects
#: below edit these values, whichever release is committed.
_COMMITTED_RELEASE = yaml.safe_load(
    (REPO_ROOT / RELEASE_REL).read_text(encoding="utf-8")
)
COMMITTED_RELEASE_ID: str = _COMMITTED_RELEASE["metadata"]["releaseId"]
COMMITTED_RENDERER_REVISION: str = _COMMITTED_RELEASE["source"]["renderer"]["revision"]

PLANTED: tuple[tuple[str, Callable[[Path], None], set[str]], ...] = (
    (
        "an edited value",
        _edit(VALUES_REL, "maxOutputTokens: 128", "maxOutputTokens: 129"),
        {"values-digest-mismatch"},
    ),
    (
        "values that name another workload",
        _edit(VALUES_REL, 'workloadId: "support-assistant"', 'workloadId: "other"'),
        {"values-digest-mismatch", "release-sources-mismatch"},
    ),
    (
        "values that are not a mapping",
        _write(VALUES_REL, "- a list\n"),
        {"values-digest-mismatch", "release-sources-mismatch"},
    ),
    (
        "an edited release identifier",
        _edit(RELEASE_REL, COMMITTED_RELEASE_ID, _other(COMMITTED_RELEASE_ID)),
        {"release-not-accepted"},
    ),
    (
        "a release that records another renderer revision",
        _edit(
            RELEASE_REL,
            f'renderer:\n    revision: "{COMMITTED_RENDERER_REVISION}',
            f'renderer:\n    revision: "{_other(COMMITTED_RENDERER_REVISION)}',
        ),
        {"release-not-accepted"},
    ),
    (
        "a release document that is not a release",
        _write(RELEASE_REL, "kind: Other\n"),
        {"release-not-accepted"},
    ),
    (
        "a release document that is not YAML",
        _write(RELEASE_REL, "{unclosed\n"),
        {"release-not-accepted"},
    ),
    (
        "a contract that changed after the release was rendered",
        _edit(DECLARED.contract, "version: 0.1.0", "version: 0.1.1"),
        {"release-sources-mismatch"},
    ),
    (
        "a contract that parses and has no digest",
        _edit(DECLARED.contract, "sizeBytes: 1834426016", f"sizeBytes: 1{'0' * 400}"),
        {"release-sources-mismatch"},
    ),
    (
        "a release that names another values file",
        _edit(RELEASE_REL, 'path: "values.generated.yaml"', 'path: "other.yaml"'),
        {"release-not-accepted"},
    ),
    (
        "a contract that does not parse",
        _write(DECLARED.contract, "kind: Other\n"),
        {"release-sources-mismatch"},
    ),
    (
        "a binding that does not parse",
        _write(DECLARED.bindings[0], "kind: Other\n"),
        {"release-sources-mismatch"},
    ),
    (
        "a removed values file",
        _remove(VALUES_REL),
        {"desired-state-absent-at-revision"},
    ),
    (
        "a removed chart file",
        _remove(CHART_FILE_REL),
        {"desired-state-absent-at-revision"},
    ),
    (
        "a chart without an application version",
        _write(CHART_FILE_REL, "name: inferops-llm\nversion: 0.3.0\n"),
        {"chart-identity-unreadable"},
    ),
    (
        "a chart whose version is a number",
        _write(CHART_FILE_REL, "name: inferops-llm\nversion: 3\nappVersion: '1'\n"),
        {"chart-identity-unreadable"},
    ),
)


@pytest.mark.parametrize(
    ("plant", "expected"),
    [pytest.param(plant, expected, id=name) for name, plant, expected in PLANTED],
)
def test_a_planted_defect_is_refused_under_the_rules_it_breaks(
    plant: Callable[[Path], None], expected: set[str], clone: tuple[Path, str]
) -> None:
    root, clean = clone
    plant(root)
    revision = _commit(root, "a planted defect")
    with pytest.raises(ProvenanceRefused) as refused:
        resolve(revision, DECLARED, root)
    assert rule_ids(refused.value) == expected
    # The commit before the defect still resolves: the defect is in one commit.
    assert resolve(clean, DECLARED, root).revision == clean


def test_every_refusing_rule_has_a_planted_defect() -> None:
    planted = set().union(*(expected for _, _, expected in PLANTED))
    refusing = {rule.rule_id for rule in RULES[:7]}
    # The first two rules are held by the tests of the revision's form.
    assert planted == refusing - {"revision-not-immutable", "revision-not-readable"}


def test_the_rules_are_ten_and_each_has_one_statement() -> None:
    assert [rule.rule_id for rule in RULES] == [
        "revision-not-immutable",
        "revision-not-readable",
        "desired-state-absent-at-revision",
        "release-not-accepted",
        "values-digest-mismatch",
        "release-sources-mismatch",
        "chart-identity-unreadable",
        "source-not-the-release",
        "observed-revision-mismatch",
        "workload-metadata-mismatch",
    ]
    assert all(rule.statement.endswith(".") for rule in RULES)


# --------------------------------------------------------------------------
# The record beside the Application
# --------------------------------------------------------------------------


def application_source() -> ReconciliationSource:
    documents = [
        document
        for document in yaml.safe_load_all(APPLICATION_PATH.read_text("utf-8"))
        if document is not None
    ]
    assert len(documents) == 1
    source = documents[0]["spec"]["source"]
    return ReconciliationSource(
        repository=source["repoURL"],
        followed_revision=source["targetRevision"],
        chart_path=source["path"],
        value_files=tuple(source["helm"]["valueFiles"]),
    )


def test_the_application_reads_the_release_the_record_names(
    record: Provenance,
) -> None:
    assert source_findings(record, application_source(), REPOSITORY) == ()


def test_the_application_follows_a_name_and_the_tool_refuses_that_name() -> None:
    """The followed revision is a branch. It is never used as an identity."""
    followed = application_source().followed_revision
    assert followed == FOLLOWED_REVISION
    assert not is_immutable_revision(followed)
    with pytest.raises(ProvenanceRefused) as refused:
        resolve(followed, DECLARED)
    assert rule_ids(refused.value) == {"revision-not-immutable"}


@pytest.mark.parametrize(
    ("change", "subject"),
    [
        ({"repository": "https://example.invalid/other.git"}, "repository"),
        ({"chart_path": "charts/other"}, "chart path"),
        ({"value_files": ()}, "value files"),
        ({"value_files": ("/gitops/environments/other/values.yaml",)}, "value files"),
        ({"value_files": (f"/{VALUES_REL}", VALUES_REL)}, "value files"),
        ({"value_files": (f"/{VALUES_REL}", "/extra.yaml")}, "value files"),
        ({"value_files": ("/extra.yaml", f"/{VALUES_REL}")}, "value files"),
    ],
)
def test_a_source_that_is_not_the_release_is_reported(
    change: dict[str, Any], subject: str, record: Provenance
) -> None:
    source = ReconciliationSource(**{**vars(application_source()), **change})
    findings = source_findings(record, source, REPOSITORY)
    assert [(f.rule_id, f.subject) for f in findings] == [
        ("source-not-the-release", subject)
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"value_files": (VALUES_REL,)},
        {"value_files": (f"./{VALUES_REL}",)},
        {"value_files": (f"//{VALUES_REL.replace('/', '//', 1)}",)},
        {"chart_path": f"/{CHART_REL}/"},
        {"chart_path": f"./{CHART_REL}/."},
        {"followed_revision": "another-branch"},
    ],
)
def test_a_path_is_compared_in_its_normal_form(
    change: dict[str, Any], record: Provenance
) -> None:
    """The followed revision is not compared: it is not an identity."""
    source = ReconciliationSource(**{**vars(application_source()), **change})
    assert source_findings(record, source, REPOSITORY) == ()


def test_a_reported_commit_is_compared_with_the_record(record: Provenance) -> None:
    same = {"compared": record.revision, "last sync operation": record.revision}
    assert observed_revision_findings(record, same) == ()
    assert [f.rule_id for f in observed_revision_findings(record, {})] == [
        "observed-revision-mismatch"
    ]
    other = observed_revision_findings(
        record, {"compared": record.revision, "last sync operation": UNKNOWN_REVISION}
    )
    assert [(f.rule_id, f.subject) for f in other] == [
        ("observed-revision-mismatch", "last sync operation")
    ]
    named = observed_revision_findings(record, {"compared": FOLLOWED_REVISION})
    assert [(f.rule_id, f.subject) for f in named] == [
        ("revision-not-immutable", "compared")
    ]
    assert [
        f.rule_id for f in observed_revision_findings(record, {"compared": ""})
    ] == ["revision-not-immutable"]


def reported_revisions(transcript: Path) -> set[str]:
    """Each commit a recorded run printed as one Argo CD resolved, synced, or applied.

    Three line shapes are read. Before the first sync a line says `nothing yet` or
    `none`, and neither begins as a commit does. A transcript holds other
    identifiers too, such as the model revision, and they are not read.
    """
    text = transcript.read_text(encoding="utf-8", errors="replace")
    return (
        set(
            re.findall(
                r"Argo CD reports that it applied revision (\S+) of 'main'", text
            )
        )
        | set(re.findall(r"resolved by Argo CD to ([0-9a-f]{7,})", text))
        | set(re.findall(r"last sync operation: ([0-9a-f]{7,}),", text))
    )


def test_the_recorded_runs_reported_one_commit_and_it_resolves_to_the_release() -> None:
    """The three recorded runs, read as files. Nothing is observed again here.

    The transcripts record the commit Argo CD reported. They record no label of an
    applied object, so this relates the reported commit to a release and relates no
    object to it. The release identifier is restated here, and the desired-state
    document states the same one.
    """
    for transcript in TRANSCRIPTS:
        assert reported_revisions(transcript) == {RECORDED_RUN_REVISION}, transcript
    assert is_immutable_revision(RECORDED_RUN_REVISION)
    exists = run_git(REPO_ROOT, "cat-file", "-e", f"{RECORDED_RUN_REVISION}^{{commit}}")
    if exists.returncode != 0:
        pytest.skip("this checkout does not hold the commit the runs reported")
    recorded = resolve(RECORDED_RUN_REVISION, DECLARED)
    assert recorded.release_id == RECORDED_RELEASE_ID
    assert recorded.values_sha256 == (
        "1849af0c88c2ef646b4f6eddfb515ba5fd3f3cbc5ac44950a35b9bf8cec864ce"
    )
    assert (recorded.chart_name, recorded.chart_version) == ("inferops-llm", "0.3.0")
    reported = {"applied": RECORDED_RUN_REVISION}
    assert observed_revision_findings(recorded, reported) == ()
    assert source_findings(recorded, application_source(), REPOSITORY) == ()


# --------------------------------------------------------------------------
# The record beside the labels the chart derives
# --------------------------------------------------------------------------


def labelled_metadata(rendered: str) -> list[tuple[str, dict[str, str]]]:
    """Every ``metadata.labels`` of a render: each object, and each pod template."""
    found = []
    for document in yaml.safe_load_all(rendered):
        if not isinstance(document, dict):
            continue
        name = f"{document['kind']}/{document['metadata']['name']}"
        found.append((name, document["metadata"].get("labels") or {}))
        template = (document.get("spec") or {}).get("template")
        if isinstance(template, dict) and "metadata" in template:
            found.append((f"{name} pod template", template["metadata"]["labels"]))
    return found


def test_the_derived_labels_are_labels_the_chart_already_sets(
    record: Provenance,
) -> None:
    """The tool adds no label. Each one it derives is in the chart's own list."""
    helpers = HELPERS_PATH.read_text(encoding="utf-8")
    block = re.search(
        r'define "inferops-llm\.derivedLabelKeys" -}}\n(.*?)\{\{- end -}}',
        helpers,
        flags=re.DOTALL,
    )
    assert block is not None
    chart_keys = set(re.findall(r"^- (\S+)$", block.group(1), flags=re.MULTILINE))
    assert set(record.workload_labels()) == {CHART_LABEL, VERSION_LABEL, WORKLOAD_LABEL}
    assert set(record.workload_labels()) <= chart_keys
    # The helper sets the workload label from the value the release names.
    assert "inferops.io/workload: {{ .Values.ownership.workloadId }}" in helpers
    assert 'helm.sh/chart: {{ include "inferops-llm.chart" . }}' in helpers
    assert "app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}" in helpers


def test_every_object_of_the_committed_render_carries_the_derived_labels(
    record: Provenance,
) -> None:
    """The chart's committed real render, which is rendered from the chart's own
    test values and not from the generated values. Those values name the same
    workload, so all three labels are compared."""
    labelled = labelled_metadata(REAL_RENDER_PATH.read_text(encoding="utf-8"))
    assert len(labelled) > 10
    for name, labels in labelled:
        assert metadata_findings(record, labels) == (), name


def test_every_object_rendered_from_the_generated_values_carries_the_derived_labels(
    record: Provenance, tmp_path: Path
) -> None:
    """The chart, rendered as the Application gives it values: the generated values,
    the Application's hand-written values, and a placeholder API image digest."""
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is not on PATH; see CONTRIBUTING.md for the commands")
    application = yaml.safe_load(APPLICATION_PATH.read_text(encoding="utf-8"))
    manual = tmp_path / "manual-values.yaml"
    manual.write_text(
        yaml.safe_dump(application["spec"]["source"]["helm"]["valuesObject"]),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            helm,
            "template",
            application["spec"]["source"]["helm"]["releaseName"],
            str(REPO_ROOT / CHART_REL),
            "--namespace",
            application["spec"]["destination"]["namespace"],
            "--values",
            str(REPO_ROOT / VALUES_REL),
            "--values",
            str(manual),
            "--set",
            f"api.image.digest={PLACEHOLDER_DIGEST}",
        ],
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    labelled = labelled_metadata(result.stdout.decode("utf-8"))
    assert len(labelled) > 10
    for name, labels in labelled:
        assert metadata_findings(record, labels) == (), name


def test_no_scrape_job_reads_a_provenance_label() -> None:
    """A commit and a release identifier are unbounded values. No metric carries one,
    and the scrape configuration reads none of the three labels the record derives.

    The helper is read as text. It names each pod label that a scrape job reads, and
    it holds no rule that copies every pod label.
    """
    helpers = HELPERS_PATH.read_text(encoding="utf-8")
    read = set(re.findall(r"__meta_kubernetes_pod_label_(\w+)", helpers))
    assert read == {
        "app_kubernetes_io_part_of",
        "app_kubernetes_io_instance",
        "app_kubernetes_io_component",
    }
    assert "labelmap" not in helpers
    for label in (CHART_LABEL, VERSION_LABEL, WORKLOAD_LABEL):
        assert re.sub(r"[^A-Za-z0-9]", "_", label) not in read, label


@pytest.mark.parametrize("label", [CHART_LABEL, VERSION_LABEL, WORKLOAD_LABEL])
def test_a_label_that_is_absent_or_different_is_reported(
    label: str, record: Provenance
) -> None:
    labels = record.workload_labels()
    assert metadata_findings(record, labels) == ()
    absent = {key: value for key, value in labels.items() if key != label}
    different = {**labels, label: "other"}
    for planted in (absent, different):
        findings = metadata_findings(record, planted)
        assert [(f.rule_id, f.subject) for f in findings] == [
            ("workload-metadata-mismatch", label)
        ]
    # A label the record does not derive is not read.
    assert metadata_findings(record, {**labels, "team": "other"}) == ()


def test_an_object_without_labels_carries_none_of_the_three(
    record: Provenance,
) -> None:
    expected = [CHART_LABEL, VERSION_LABEL, WORKLOAD_LABEL]
    assert [f.subject for f in metadata_findings(record, None)] == expected
    assert [f.subject for f in metadata_findings(record, {})] == expected


def test_the_chart_label_is_formed_as_the_charts_helper_forms_it(
    record: Provenance,
) -> None:
    """`+` becomes `_`, the value is cut to 63 characters, a trailing `-` goes."""
    helpers = HELPERS_PATH.read_text(encoding="utf-8")
    assert (
        '{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" '
        '| trunc 63 | trimSuffix "-" -}}'
    ) in helpers
    built = replace(record, chart_version="0.3.0+build.1")
    assert built.workload_labels()[CHART_LABEL] == "inferops-llm-0.3.0_build.1"
    long = replace(record, chart_name="a" * 62, chart_version="1.0.0")
    assert long.workload_labels()[CHART_LABEL] == "a" * 62


# --------------------------------------------------------------------------
# The command, and what the tool runs
# --------------------------------------------------------------------------


def run_command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.desired_state_provenance", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_the_command_prints_one_record_for_the_commit(
    head: str, record: Provenance
) -> None:
    result = run_command("--revision", head)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [record.as_document()]
    keyed = run_command("--revision", head, release_key(DECLARED))
    assert keyed.returncode == 0 and keyed.stdout == result.stdout
    twice = run_command(
        "--revision", head, release_key(DECLARED), release_key(DECLARED)
    )
    assert twice.returncode == 0 and twice.stdout == result.stdout


def test_the_command_refuses_a_branch_name_and_prints_no_record() -> None:
    result = run_command("--revision", FOLLOWED_REVISION)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "REFUSED  revision-not-immutable" in result.stderr


def test_the_command_needs_a_revision_and_a_known_key(head: str) -> None:
    assert run_command().returncode == 2
    unknown = run_command("--revision", head, "local-kind/support-assistant")
    assert unknown.returncode == 2
    assert "no desired-state release has the key" in unknown.stderr


def test_the_tool_restates_the_two_generated_file_names() -> None:
    """The tool does not import the render package, so it restates the two names."""
    assert (
        RELEASE_FILE_NAME,
        str(VALUES_FILE_NAME),
    ) == (provenance_core._RELEASE_FILE, provenance_core._VALUES_FILE)
    assert {provenance_core._RELEASE_FILE, provenance_core._VALUES_FILE} == set(
        GENERATED_FILES
    )


def test_the_tool_runs_git_as_cat_file_in_two_read_only_forms() -> None:
    """Every Git call goes through one function, with `cat-file` as its subcommand.

    This reads the source and pins its shape. It is a tripwire for a new Git call,
    and it does not observe a process.
    """
    tree = ast.parse(TOOL_CORE_PATH.read_text(encoding="utf-8"))
    subcommands = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_git"
        ):
            words = [
                argument.value
                for argument in node.args[1:3]
                if isinstance(argument, ast.Constant)
            ]
            subcommands.append(tuple(words))
    assert sorted(subcommands) == [("cat-file", "-t"), ("cat-file", "blob")]
    runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in {"run", "Popen", "call", "check_output", "check_call"}
    ]
    assert len(runs) == 1, "one subprocess call, inside the Git wrapper"
    source = TOOL_CORE_PATH.read_text(encoding="utf-8")
    assert '"--no-replace-objects"' in source
    assert 'environment["GIT_NO_LAZY_FETCH"] = "1"' in source


def test_the_document_publishes_every_rule_and_the_record_schema() -> None:
    document = DOCUMENT_PATH.read_text(encoding="utf-8")
    flattened = " ".join(document.split())
    for rule in RULES:
        assert f"`{rule.rule_id}`" in document, rule.rule_id
        assert rule.statement in flattened, rule.rule_id
    assert RECORD_SCHEMA in document
    for label in (CHART_LABEL, VERSION_LABEL, WORKLOAD_LABEL):
        assert f"`{label}`" in document, label
