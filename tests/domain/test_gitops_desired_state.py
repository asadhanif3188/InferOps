"""The Git desired-state tree, checked against the releases it is declared to hold.

``gitops/`` holds generated releases, one directory for one environment binding and
one workload. This suite holds that layout to the inputs it is derived from, and
plants each defect the check refuses in a copy of those inputs.

Four things are held:

* the committed tree breaks no rule, through the library and through the command,
  and Git tracks exactly the declared files and the tree's own page;
* each release is at the path its EnvironmentBinding and WorkloadContract derive,
  it is what its declared sources derive, and its two revisions are full Git
  revisions and not placeholders;
* a hand-written file, a second copy of a release, a release at another path, an
  edited file, and a placeholder revision are each refused under their own rule;
* verification writes nothing, and regeneration needs a key and refuses a release
  the rules refuse.

What this establishes about a cluster: nothing. No controller reads the tree, no
Application names it, and nothing in it was installed. Every check here reads
committed files, or a copy of them under pytest's temporary directory. Three tests
run Git, to list tracked files, to read attributes, and to read one file at a
declared revision. The last one skips when the checkout does not hold that commit.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from inferops.domain.render import (
    MANUAL_VALUES_SUFFIX,
    RELEASE_FILE_NAME,
    VALUES_FILE_NAME,
)
from tools.generated_release import (
    DECLARED_RELEASES,
    GENERATED_FILES,
    MATRIX_PATH,
    REPO_ROOT,
    DeclaredRelease,
)
from tools.gitops_desired_state import (
    DESIRED_STATE_RELEASES,
    DESIRED_STATE_ROOT,
    ENVIRONMENTS_PATH,
    RULES,
    TREE_DOCUMENT,
    WORKLOADS_SEGMENT,
    Finding,
    WriteRefused,
    desired_state_release,
    expected_directory,
    regenerate_release,
    release_key,
    verify_tree,
)
from tools.gitops_desired_state.__main__ import main

pytestmark = pytest.mark.unit

DOCUMENT = REPO_ROOT / "docs" / "environment" / "git-desired-state.md"
TREE_PAGE = REPO_ROOT / TREE_DOCUMENT
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"

REFERENCE = DESIRED_STATE_RELEASES[0]
KEY = "local-docker-desktop/support-assistant"
VALUES = str(VALUES_FILE_NAME)
RELEASE = RELEASE_FILE_NAME

GIT = shutil.which("git")
needs_git = pytest.mark.skipif(GIT is None, reason="git is not on PATH")


# --------------------------------------------------------------------------
# A copy of the tree and of its declared inputs, to plant defects in
# --------------------------------------------------------------------------


def copy_inputs(root: Path) -> Path:
    """Copy the desired-state tree and every input a release is derived from."""
    relatives = {DESIRED_STATE_ROOT, MATRIX_PATH}
    for declared in DESIRED_STATE_RELEASES:
        relatives.update(
            (declared.contract, *declared.bindings, declared.platform_defaults)
        )
    for relative in sorted(relatives):
        source, target = REPO_ROOT / relative, root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copyfile(source, target)
    return root


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return copy_inputs(tmp_path / "repository")


def edit(path: Path, old: str, new: str) -> None:
    """Replace the one occurrence of ``old`` in a text file, keeping LF."""
    text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert text.count(old) == 1, (path.name, old)
    path.write_bytes(text.replace(old, new).encode("utf-8"))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def found(findings: tuple[Finding, ...]) -> list[tuple[str, str]]:
    return [(finding.rule_id, finding.subject) for finding in findings]


def rules_of(findings: tuple[Finding, ...]) -> set[str]:
    return {finding.rule_id for finding in findings}


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    """Every file under ``root``, with its bytes and modification time."""
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def git(*arguments: str) -> subprocess.CompletedProcess[str]:
    assert GIT is not None
    return subprocess.run(
        [GIT, *arguments], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def load(relative: str) -> dict:
    return yaml.safe_load((REPO_ROOT / relative).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 1. The committed tree
# --------------------------------------------------------------------------


def test_the_committed_tree_breaks_no_rule() -> None:
    assert verify_tree() == ()


def test_the_check_command_passes_on_the_committed_tree() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.gitops_desired_state", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for declared in DESIRED_STATE_RELEASES:
        assert f"OK       {release_key(declared)}: {declared.directory}" in (
            result.stdout
        )


def test_a_copy_of_the_tree_verifies_so_every_planted_defect_is_its_own(
    root: Path,
) -> None:
    assert verify_tree(root) == ()


@needs_git
def test_git_tracks_the_declared_files_and_the_tree_page_and_nothing_else() -> None:
    """The check walks the working tree. This reads what is committed."""
    result = git("ls-files", "--", DESIRED_STATE_ROOT)
    assert result.returncode == 0, result.stderr
    declared = [
        f"{release.directory}/{name}"
        for release in DESIRED_STATE_RELEASES
        for name in GENERATED_FILES
    ]
    assert sorted(result.stdout.splitlines()) == sorted([TREE_DOCUMENT, *declared])


@needs_git
@pytest.mark.parametrize("declared", DESIRED_STATE_RELEASES, ids=release_key)
def test_every_desired_state_file_is_pinned_to_lf(declared: DeclaredRelease) -> None:
    """A checkout that wrote CRLF would change both files' digests."""
    paths = [f"{declared.directory}/{name}" for name in GENERATED_FILES]
    result = git("check-attr", "eol", "--", *paths)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f"{path}: eol: lf" for path in paths]


def test_one_release_is_declared_and_it_is_the_reference_workload() -> None:
    """A pin. A second path, or another binding, is a decision and not an edit."""
    assert [release_key(declared) for declared in DESIRED_STATE_RELEASES] == [KEY]
    assert REFERENCE.directory == (
        "gitops/environments/local-docker-desktop/workloads/support-assistant"
    )
    assert REFERENCE.contract == (
        "contracts/workload/examples/valid/synchronous-llm-local.yaml"
    )
    assert REFERENCE.bindings == (
        "contracts/environment/examples/valid/local-docker-desktop.yaml",
    )
    assert REFERENCE.binding_name == "local-docker-desktop"
    assert REFERENCE.platform_defaults == "charts/inferops-llm/values.yaml"
    assert desired_state_release(KEY) is REFERENCE
    with pytest.raises(KeyError):
        desired_state_release("support-assistant")


def test_release_keys_and_directories_are_distinct_and_no_test_fixture_is_one() -> None:
    keys = [release_key(declared) for declared in DESIRED_STATE_RELEASES]
    directories = [declared.directory for declared in DESIRED_STATE_RELEASES]
    assert len(set(keys)) == len(keys)
    assert len(set(directories)) == len(directories)
    # The drift check's own declarations are test fixtures, outside the tree.
    for fixture in DECLARED_RELEASES:
        assert not fixture.directory.startswith(f"{DESIRED_STATE_ROOT}/")
        assert fixture.directory not in directories


@pytest.mark.parametrize("declared", DESIRED_STATE_RELEASES, ids=release_key)
def test_each_release_is_at_the_path_its_binding_and_contract_derive(
    declared: DeclaredRelease,
) -> None:
    """Read from the documents, not through the tool that is under test."""
    bindings = [load(path) for path in declared.bindings]
    selected = [b for b in bindings if b["metadata"]["name"] == declared.binding_name]
    assert len(selected) == 1
    destination = selected[0]["spec"]["gitops"]["destinationPath"]
    workload = load(declared.contract)["metadata"]["name"]
    assert destination.startswith(f"{ENVIRONMENTS_PATH}/")
    assert declared.directory == f"{destination}/{WORKLOADS_SEGMENT}/{workload}"
    assert expected_directory(declared) == declared.directory

    release = load(f"{declared.directory}/{RELEASE}")
    assert release["metadata"]["workloadId"] == workload
    assert release["source"]["environmentBinding"]["name"] == declared.binding_name
    assert release["output"]["helmValues"]["path"] == VALUES


@pytest.mark.parametrize("declared", DESIRED_STATE_RELEASES, ids=release_key)
def test_each_release_records_one_full_revision_that_is_not_a_placeholder(
    declared: DeclaredRelease,
) -> None:
    """The form of the revision. Whether it names a commit is the next test."""
    release = load(f"{declared.directory}/{RELEASE}")
    recorded = {
        release["source"]["renderer"]["revision"],
        release["source"]["platformDefaults"]["revision"],
    }
    assert recorded == {declared.renderer_revision}
    assert declared.platform_defaults_revision == declared.renderer_revision
    assert re.fullmatch(r"[0-9a-f]{40}", declared.renderer_revision)
    assert len(set(declared.renderer_revision)) > 1


@needs_git
@pytest.mark.parametrize("declared", DESIRED_STATE_RELEASES, ids=release_key)
def test_the_declared_revision_names_a_commit_that_holds_the_defaults_read_today(
    declared: DeclaredRelease,
) -> None:
    """The revision is a statement, and this checks it where history allows.

    The drift check reads the platform defaults from the working tree and takes the
    revision from the declaration. So a defaults change that kept the old revision
    would move the values and leave the revision false. This reads the defaults
    file at the declared revision and compares its ``api`` block with the one read
    today. It needs the commit object, which a shallow checkout does not hold, and
    it skips there. It does not compare the renderer's source at that revision.
    """
    revision = declared.platform_defaults_revision
    if git("cat-file", "-e", f"{revision}^{{commit}}").returncode != 0:
        pytest.skip(f"this checkout does not hold the commit {revision}")
    shown = git("show", f"{revision}:{declared.platform_defaults}")
    assert shown.returncode == 0, shown.stderr
    then = yaml.safe_load(shown.stdout)["api"]
    now = load(declared.platform_defaults)["api"]
    for setting in ("requestTimeoutMs", "drainTimeoutMs", "maxOutputTokens"):
        assert then[setting] == now[setting], setting


def test_the_values_are_the_reference_release_values_and_only_provenance_differs() -> (
    None
):
    """The two local bindings render the same chart values.

    So what the chart suite establishes about the reference release's values file
    holds for this one: the chart's guards still require four hand-written values,
    and the pair renders the V1 workload. The releases differ only in the binding
    they name, its digest, the two revisions, and the identifier derived from them.
    """
    fixture = DECLARED_RELEASES[0]
    assert (REPO_ROOT / REFERENCE.directory / VALUES).read_bytes() == (
        REPO_ROOT / fixture.directory / VALUES
    ).read_bytes()

    def leaves(document: dict, prefix: str = "") -> dict[str, object]:
        flat: dict[str, object] = {}
        for key, value in document.items():
            if isinstance(value, dict):
                flat.update(leaves(value, f"{prefix}{key}."))
            else:
                flat[f"{prefix}{key}"] = value
        return flat

    ours = leaves(load(f"{REFERENCE.directory}/{RELEASE}"))
    theirs = leaves(load(f"{fixture.directory}/{RELEASE}"))
    assert {path for path in ours if ours[path] != theirs[path]} == {
        "metadata.releaseId",
        "source.environmentBinding.name",
        "source.environmentBinding.sha256",
        "source.platformDefaults.revision",
        "source.renderer.revision",
    }


def test_the_tree_holds_no_hand_written_values_file_and_no_cluster_object() -> None:
    """Read from the working tree, so an untracked file is seen too."""
    files = [
        path
        for path in (REPO_ROOT / DESIRED_STATE_ROOT).rglob("*")
        if path.is_file() and path.relative_to(REPO_ROOT).as_posix() != TREE_DOCUMENT
    ]
    assert files, "the tree was not read"
    for path in files:
        assert path.name in GENERATED_FILES, path
        assert not path.name.endswith(MANUAL_VALUES_SUFFIX), path
    # A generated release is a repository document. It is not a cluster resource,
    # and the one kind in the tree is the release's own.
    kinds = {
        yaml.safe_load(path.read_text(encoding="utf-8")).get("kind")
        for path in files
        if path.name == RELEASE
    }
    assert kinds == {"RenderedWorkloadRelease"}


# --------------------------------------------------------------------------
# 2. Refused: something in the tree that no declaration accounts for
# --------------------------------------------------------------------------


def test_a_hand_written_values_file_beside_a_release_is_refused(root: Path) -> None:
    stray = f"{REFERENCE.directory}/support-assistant{MANUAL_VALUES_SUFFIX}"
    write(root / stray, "api:\n  replicaCount: 3\n")
    findings = verify_tree(root)
    assert ("desired-state-entry-undeclared", stray) in found(findings)
    # The drift check refuses the same file as an entry the platform did not write.
    drifted = [f for f in findings if f.rule_id == "desired-state-release-drifted"]
    assert [f.detail.split(":")[0] for f in drifted] == [
        "generated-release-unexpected-entry"
    ]


@pytest.mark.parametrize(
    "stray",
    (
        "gitops/values.yaml",
        "gitops/environments/values.yaml",
        "gitops/environments/local-docker-desktop/values.yaml",
        "gitops/environments/local-docker-desktop/workloads/values.override.yaml",
        f"gitops/environments/local-docker-desktop/shared{MANUAL_VALUES_SUFFIX}",
    ),
)
def test_a_file_anywhere_else_in_the_tree_is_refused(root: Path, stray: str) -> None:
    write(root / stray, "runtime:\n  replicaCount: 2\n")
    assert found(verify_tree(root)) == [("desired-state-entry-undeclared", stray)]


@pytest.mark.parametrize("stage", ("dev", "staging", "production", "local-kind"))
def test_a_second_environment_directory_is_refused_as_one_entry(
    root: Path, stage: str
) -> None:
    """A copy of a release under another environment name is not a release.

    The finding names the directory, once, and not each file beneath it. A second
    environment is added by declaring a release for a binding, not by copying one.
    """
    copy = f"{ENVIRONMENTS_PATH}/{stage}"
    shutil.copytree(root / ENVIRONMENTS_PATH / "local-docker-desktop", root / copy)
    assert found(verify_tree(root)) == [("desired-state-entry-undeclared", copy)]


def test_a_second_workload_directory_nobody_declared_is_refused(root: Path) -> None:
    copy = f"{ENVIRONMENTS_PATH}/local-docker-desktop/{WORKLOADS_SEGMENT}/other"
    shutil.copytree(root / REFERENCE.directory, root / copy)
    assert found(verify_tree(root)) == [("desired-state-entry-undeclared", copy)]


def test_an_empty_directory_in_the_tree_is_refused(root: Path) -> None:
    (root / ENVIRONMENTS_PATH / "empty").mkdir()
    assert found(verify_tree(root)) == [
        ("desired-state-entry-undeclared", f"{ENVIRONMENTS_PATH}/empty")
    ]


def test_a_file_where_the_tree_belongs_is_refused(root: Path) -> None:
    shutil.rmtree(root / DESIRED_STATE_ROOT)
    write(root / DESIRED_STATE_ROOT, "not a directory\n")
    findings = verify_tree(root)
    assert ("desired-state-entry-undeclared", DESIRED_STATE_ROOT) in found(findings)
    assert "desired-state-release-drifted" in rules_of(findings)


def _symlink(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("this host cannot create a symbolic link")


def test_a_symbolic_link_in_the_tree_is_refused_and_not_followed(
    root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    write(outside / "values.yaml", "api:\n  replicaCount: 9\n")
    link = root / ENVIRONMENTS_PATH / "linked"
    _symlink(link, outside)
    assert found(verify_tree(root)) == [
        ("desired-state-entry-undeclared", f"{ENVIRONMENTS_PATH}/linked")
    ]


def test_the_tree_page_is_allowed_and_not_required(root: Path) -> None:
    (root / TREE_DOCUMENT).unlink()
    assert verify_tree(root) == ()


# --------------------------------------------------------------------------
# 3. Refused: a release that is not what, or where, its inputs derive
# --------------------------------------------------------------------------


def test_a_hand_edited_value_is_drift(root: Path) -> None:
    edit(root / REFERENCE.directory / VALUES, 'cpu: "6"', 'cpu: "8"')
    findings = verify_tree(root)
    assert rules_of(findings) == {"desired-state-release-drifted"}
    assert [f.subject for f in findings] == [f"{KEY}: {VALUES}", f"{KEY}: {VALUES}"]
    assert [f.detail.split(":")[0] for f in findings] == [
        "generated-release-values-unrecorded",
        "generated-release-file-drifted",
    ]
    assert any(line == '-      cpu: "8"' for line in findings[1].diff)


def test_a_release_edited_to_name_a_placeholder_revision_is_drift(root: Path) -> None:
    edit(
        root / REFERENCE.directory / RELEASE,
        f'renderer:\n    revision: "{REFERENCE.renderer_revision}"',
        f'renderer:\n    revision: "{"a" * 40}"',
    )
    findings = verify_tree(root)
    assert rules_of(findings) == {"desired-state-release-drifted"}
    assert f"{KEY}: source.renderer.revision" in [f.subject for f in findings]


def test_a_missing_release_is_drift(root: Path) -> None:
    shutil.rmtree(root / REFERENCE.directory)
    findings = verify_tree(root)
    assert [f.detail.split(":")[0] for f in findings] == ["generated-release-missing"]
    assert rules_of(findings) == {"desired-state-release-drifted"}


def test_a_binding_that_moves_its_destination_leaves_the_release_at_the_wrong_path(
    root: Path,
) -> None:
    """The binding owns the path. A release left behind is at a path nobody derives."""
    edit(
        root / REFERENCE.bindings[0],
        "destinationPath: gitops/environments/local-docker-desktop",
        "destinationPath: gitops/environments/elsewhere",
    )
    findings = verify_tree(root)
    path = [f for f in findings if f.rule_id == "desired-state-path-not-derived"]
    assert [(f.subject, f.detail) for f in path] == [
        (
            f"{KEY}: {REFERENCE.directory}",
            "the declared binding and contract place this release at "
            "gitops/environments/elsewhere/workloads/support-assistant",
        )
    ]
    # The binding's digest moved too, so the committed release is stale.
    assert f"{KEY}: source.environmentBinding.sha256" in [f.subject for f in findings]


def test_a_contract_that_renames_its_workload_leaves_the_release_at_the_wrong_path(
    root: Path,
) -> None:
    edit(root / REFERENCE.contract, "name: support-assistant", "name: other-assistant")
    findings = verify_tree(root)
    path = [f for f in findings if f.rule_id == "desired-state-path-not-derived"]
    assert [f.detail for f in path] == [
        "the declared binding and contract place this release at "
        "gitops/environments/local-docker-desktop/workloads/other-assistant"
    ]
    assert f"{KEY}: metadata.workloadId" in [f.subject for f in findings]


def test_a_release_declared_outside_the_environments_directory_is_refused(
    root: Path,
) -> None:
    moved = replace(REFERENCE, directory="gitops/support-assistant")
    findings = verify_tree(root, (moved,))
    details = [
        f.detail for f in findings if f.rule_id == "desired-state-path-not-derived"
    ]
    assert details == [
        "the release directory is not under gitops/environments/",
        f"the declared binding and contract place this release at {REFERENCE.directory}",
    ]


def test_two_declarations_of_one_directory_are_refused(root: Path) -> None:
    findings = verify_tree(root, (REFERENCE, REFERENCE))
    assert [
        f.detail for f in findings if f.rule_id == "desired-state-path-not-derived"
    ] == ["another declared release has this directory"]


@pytest.mark.parametrize(
    ("field", "revision", "reason"),
    (
        ("renderer_revision", "a" * 40, "one repeated character"),
        ("platform_defaults_revision", "b" * 40, "one repeated character"),
        ("renderer_revision", "c056b97", "not 40 lowercase hexadecimal"),
        ("platform_defaults_revision", "main", "not 40 lowercase hexadecimal"),
        ("renderer_revision", "C056B977" * 5, "not 40 lowercase hexadecimal"),
    ),
)
def test_a_placeholder_or_short_revision_is_refused_in_a_declaration(
    root: Path, field: str, revision: str, reason: str
) -> None:
    """The test fixture's placeholders are not accepted for desired state."""
    declared = (
        replace(REFERENCE, renderer_revision=revision)
        if field == "renderer_revision"
        else replace(REFERENCE, platform_defaults_revision=revision)
    )
    invalid = [
        f
        for f in verify_tree(root, (declared,))
        if f.rule_id == "desired-state-declaration-invalid"
    ]
    assert [f.subject for f in invalid] == [f"{KEY}: {field}"]
    assert reason in invalid[0].detail


def test_a_declaration_that_selects_no_binding_by_name_is_refused(root: Path) -> None:
    declared = replace(REFERENCE, binding_name=None)
    invalid = [
        f
        for f in verify_tree(root, (declared,))
        if f.rule_id == "desired-state-declaration-invalid"
    ]
    assert len(invalid) == 1
    assert invalid[0].subject.endswith(": binding_name")


def test_findings_are_reported_in_rule_order(root: Path) -> None:
    write(root / "gitops/values.yaml", "api: {}\n")
    edit(root / REFERENCE.directory / VALUES, 'cpu: "6"', 'cpu: "8"')
    declared = replace(REFERENCE, renderer_revision="a" * 40)
    order = [rule.rule_id for rule in RULES]
    reported = [f.rule_id for f in verify_tree(root, (declared,))]
    assert reported == sorted(reported, key=order.index)
    assert set(reported) == {
        "desired-state-declaration-invalid",
        "desired-state-entry-undeclared",
        "desired-state-release-drifted",
    }


# --------------------------------------------------------------------------
# 4. The command, and regeneration
# --------------------------------------------------------------------------


def test_verification_writes_nothing(root: Path) -> None:
    write(root / "gitops/values.yaml", "api: {}\n")
    edit(root / REFERENCE.directory / VALUES, 'cpu: "6"', 'cpu: "8"')
    before = snapshot(root)
    assert verify_tree(root)
    assert main(["--check", "--root", str(root)]) == 1
    assert snapshot(root) == before


def test_the_check_command_reports_each_finding_with_its_rule(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(root / "gitops/values.yaml", "api: {}\n")
    assert main(["--check", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    statement = next(
        rule.statement
        for rule in RULES
        if rule.rule_id == "desired-state-entry-undeclared"
    )
    assert "REFUSED  desired-state-entry-undeclared" in out
    assert "gitops/values.yaml: the file is not a generated file" in out
    assert statement in out
    assert "1 findings in the desired-state tree" in out


def test_the_list_command_prints_each_key_and_its_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    for value in (
        KEY,
        REFERENCE.directory,
        REFERENCE.contract,
        REFERENCE.bindings[0],
        REFERENCE.renderer_revision,
    ):
        assert value in out


@pytest.mark.parametrize(
    "arguments",
    (
        ["--write"],
        ["--write", "support-assistant"],
        ["--check", KEY],
        ["--list", KEY],
        [],
    ),
)
def test_the_command_refuses_a_missing_or_unknown_key(
    arguments: list[str], root: Path
) -> None:
    before = snapshot(root)
    with pytest.raises(SystemExit) as refused:
        main([*arguments, "--root", str(root)])
    assert refused.value.code == 2
    assert snapshot(root) == before


def test_regeneration_repairs_a_hand_edit_and_leaves_a_clean_release_untouched(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    committed = (REPO_ROOT / REFERENCE.directory / VALUES).read_bytes()
    edit(root / REFERENCE.directory / VALUES, 'cpu: "6"', 'cpu: "8"')
    assert main(["--write", KEY, "--root", str(root)]) == 0
    assert f"WROTE    {REFERENCE.directory}" in capsys.readouterr().out
    assert (root / REFERENCE.directory / VALUES).read_bytes() == committed
    assert verify_tree(root) == ()

    before = snapshot(root)
    assert main(["--write", KEY, "--root", str(root)]) == 0
    assert f"UNCHANGED {REFERENCE.directory}" in capsys.readouterr().out
    assert snapshot(root) == before


def test_regeneration_writes_a_release_whose_directories_are_absent(root: Path) -> None:
    shutil.rmtree(root / DESIRED_STATE_ROOT)
    assert regenerate_release(REFERENCE, root) is True
    for name in GENERATED_FILES:
        assert (root / REFERENCE.directory / name).read_bytes() == (
            REPO_ROOT / REFERENCE.directory / name
        ).read_bytes()


def test_regeneration_refuses_a_release_the_rules_refuse_and_writes_nothing(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = snapshot(root)
    with pytest.raises(WriteRefused) as placeholder:
        regenerate_release(replace(REFERENCE, renderer_revision="a" * 40), root)
    assert [f.rule_id for f in placeholder.value.findings] == [
        "desired-state-declaration-invalid"
    ]
    with pytest.raises(WriteRefused) as misplaced:
        regenerate_release(replace(REFERENCE, directory="gitops/elsewhere"), root)
    assert {f.rule_id for f in misplaced.value.findings} == {
        "desired-state-path-not-derived"
    }
    assert snapshot(root) == before
    assert not (root / "gitops" / "elsewhere").exists()

    # Through the command: a binding that moved its destination refuses the write.
    edit(
        root / REFERENCE.bindings[0],
        "destinationPath: gitops/environments/local-docker-desktop",
        "destinationPath: gitops/environments/elsewhere",
    )
    before = snapshot(root)
    assert main(["--write", KEY, "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert f"REFUSED  {KEY}: nothing was written" in out
    assert "desired-state-path-not-derived" in out
    assert snapshot(root) == before


def test_regeneration_refuses_a_directory_that_holds_a_hand_written_file(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = root / REFERENCE.directory / f"extra{MANUAL_VALUES_SUFFIX}"
    write(stray, "api: {}\n")
    before = snapshot(root)
    assert main(["--write", KEY, "--root", str(root)]) == 1
    assert "generated-release-unexpected-entry" in capsys.readouterr().out
    assert snapshot(root) == before


def test_regeneration_refuses_sources_that_no_longer_render(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root / REFERENCE.contract, "name: support-assistant", "name: Not_A_Label")
    before = snapshot(root)
    assert main(["--write", KEY, "--root", str(root)]) == 1
    assert f"REFUSED  {KEY}: nothing was written" in capsys.readouterr().out
    assert snapshot(root) == before


# --------------------------------------------------------------------------
# 5. The documents that describe the tree
# --------------------------------------------------------------------------

RULE_ROW = re.compile(r"^\| `(desired-state-[a-z-]+)` \| (.+) \|$", re.MULTILINE)


def test_the_document_publishes_the_rules_the_check_applies() -> None:
    published = RULE_ROW.findall(DOCUMENT.read_text(encoding="utf-8"))
    assert published == [(rule.rule_id, rule.statement) for rule in RULES]


def test_the_document_and_the_tree_page_state_both_commands() -> None:
    check = "python -m tools.gitops_desired_state --check"
    regenerate = f"python -m tools.gitops_desired_state --write {KEY}"
    for path in (DOCUMENT, TREE_PAGE, CONTRIBUTING):
        text = path.read_text(encoding="utf-8")
        assert check in text, path.name
        assert regenerate in text, path.name


def test_the_document_names_every_release_and_its_revision() -> None:
    text = DOCUMENT.read_text(encoding="utf-8")
    for declared in DESIRED_STATE_RELEASES:
        assert f"`{release_key(declared)}`" in text
        assert declared.directory in text
        assert declared.renderer_revision in text
        release = load(f"{declared.directory}/{RELEASE}")
        assert release["metadata"]["releaseId"] in text


def test_the_tree_page_says_that_nothing_reconciles_the_tree() -> None:
    """The page sits where a reader would assume the opposite."""
    text = TREE_PAGE.read_text(encoding="utf-8")
    assert "**Nothing reconciles it\nyet.**" in text
    assert "Do not edit one by hand" in text
