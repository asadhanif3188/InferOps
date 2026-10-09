"""Committed generated releases, compared with what their declared sources derive.

Every check reads files in this repository. Every planted drift is planted in a copy
of the declared inputs under pytest's temporary directory, never in the committed
files. No cluster, no network, no model, and no Helm.

Six things are asserted:

1. **Expected pass.** Every declared release is, byte for byte, what its declared
   inputs derive today, through the library and through the command, and its
   directory is pinned to LF.
2. **Expected failure: edited files.** A hand edit to the values file - a value, a
   comment, a line ending - is reported as a drifted file and as values the release
   does not record. A release file edited to name other provenance is reported at
   the field it changed, and an edit no field shows is still a drifted file.
3. **Expected failure: stale sources.** A contract, binding, or defaults change made
   after generation is reported at every release field it moves, and only those.
4. **Layout and refusal.** A missing directory or file, a stray entry, a left-over
   staging directory, and sources that no longer render are each reported under
   their own rule, without a crash and without a comparison that cannot be made.
5. **Verification is a check, not a fix.** It writes nothing, calls no writer, opens
   no socket, imports nothing that runs a process or reaches a network, and prints
   the same diff in two interpreters; the command exits 1 with the rule, the field,
   a unified diff, and the regenerate command.
6. **Regeneration is explicit.** It runs only for a named release, repairs drift,
   leaves an unchanged release untouched, and refuses to remove what the platform
   did not write.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from inferops.domain.render import RELEASE_FILE_NAME, VALUES_FILE_NAME
from inferops.domain.workload import (
    CompatibilityMatrixLoader,
    get_matrix_loader,
    set_matrix_loader,
)
from tools.baseline_profile import baseline_profile
from tools.experiment_e01 import RUNS_DIR, committed_runs
from tools.generated_release import (
    BLOCKING_RULES,
    DECLARED_RELEASES,
    FIELD_CAUSES,
    GENERATED_FILES,
    MATRIX_PATH,
    REPO_ROOT,
    RULES,
    DeclaredRelease,
    Finding,
    RegenerationRefused,
    SourcesRefused,
    derive,
    regenerate,
    regenerate_command,
    verify,
)
from tools.generated_release import core as core_module
from tools.generated_release.__main__ import main
from tools.gitops_desired_state import DESIRED_STATE_RELEASES

pytestmark = pytest.mark.unit

TOOL_DIR = REPO_ROOT / "tools" / "generated_release"
RENDERER_DOC = REPO_ROOT / "docs" / "domain" / "helm-values-renderer.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"

REFERENCE = DECLARED_RELEASES[0]
VALUES = str(VALUES_FILE_NAME)
RELEASE = RELEASE_FILE_NAME


# --------------------------------------------------------------------------
# A copy of the declared inputs, to plant drift in
# --------------------------------------------------------------------------


def copy_inputs(root: Path, declared: DeclaredRelease = REFERENCE) -> Path:
    """Copy one release's directory and every input it is derived from to ``root``."""
    for relative in (
        declared.directory,
        declared.contract,
        *declared.bindings,
        declared.platform_defaults,
        MATRIX_PATH,
    ):
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
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path.name, old)
    path.write_bytes(text.replace(old, new).encode("utf-8"))


def release_path(root: Path, name: str) -> Path:
    return root / REFERENCE.directory / name


def found(findings: tuple[Finding, ...]) -> list[tuple[str, str]]:
    return [(finding.rule_id, finding.subject) for finding in findings]


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    """Every file under ``root``, with its bytes and modification time."""
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


# --------------------------------------------------------------------------
# 1. Expected pass
# --------------------------------------------------------------------------


@pytest.mark.parametrize("declared", DECLARED_RELEASES, ids=lambda d: d.name)
def test_every_declared_release_is_what_its_declared_sources_derive(
    declared: DeclaredRelease,
) -> None:
    assert verify(declared) == ()


def test_the_check_command_passes_on_the_committed_releases() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.generated_release", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for declared in DECLARED_RELEASES:
        assert f"OK       {declared.name}:" in result.stdout


def test_a_copy_of_the_declared_inputs_verifies_so_every_planted_drift_is_its_own(
    root: Path,
) -> None:
    assert verify(REFERENCE, root) == ()


def test_the_reference_declaration_is_the_golden_suites_inputs() -> None:
    assert REFERENCE.name == "support-assistant-local-kind"
    assert REFERENCE.directory == (
        "tests/domain/fixtures/helm-values/support-assistant-local-kind"
    )
    assert REFERENCE.contract.endswith("/synchronous-llm-local.yaml")
    assert REFERENCE.bindings == (
        "contracts/environment/examples/valid/local-kind.yaml",
    )
    assert REFERENCE.platform_defaults == "charts/inferops-llm/values.yaml"
    # Placeholders that name no commit: the reference release is a test render.
    assert REFERENCE.renderer_revision == "a" * 40
    assert REFERENCE.platform_defaults_revision == "b" * 40


def test_declared_releases_have_distinct_names_and_directories() -> None:
    names = [declared.name for declared in DECLARED_RELEASES]
    directories = [declared.directory for declared in DECLARED_RELEASES]
    assert len(set(names)) == len(names)
    assert len(set(directories)) == len(directories)


#: The directories of an E01 run that hold renders, as the freeze record names them.
RUN_RENDERS = frozenset({"render-a", "render-b", "mutation"})


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
def test_every_committed_generated_file_is_in_a_declared_release_directory() -> None:
    """A release nobody declared would never be compared, so none may exist.

    A generated file may be committed in three other places. One is the Git desired
    state under ``gitops/``, whose releases ``tools.gitops_desired_state`` declares
    and derives again through this package's check. One is the single-runtime
    baseline profile, which ``tools.baseline_profile`` declares and derives again
    through this package's check. One is an E01 run's
    evidence, and only as a file the run's manifest records. Those renders are bound
    to the commit that ran them, so this check does not derive them again from
    today's sources; ``python -m tools.experiment_e01 --check`` holds each to its
    own bytes.
    """
    result = subprocess.run(
        ["git", "ls-files", "--", *(f"*{name}" for name in GENERATED_FILES)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    committed = sorted(result.stdout.splitlines())
    declared = [
        f"{release.directory}/{name}"
        for release in (
            *DECLARED_RELEASES,
            *DESIRED_STATE_RELEASES,
            baseline_profile(),
        )
        for name in GENERATED_FILES
    ]
    run_evidence = [
        f"{RUNS_DIR}/{run.name}/{relative}"
        for run in committed_runs(REPO_ROOT)
        for relative in json.loads(
            (run / "run.v1alpha1.json").read_text(encoding="utf-8")
        )["files"]
        if relative.split("/")[0] in RUN_RENDERS
        and relative.rsplit("/", 1)[-1] in GENERATED_FILES
    ]
    assert committed == sorted([*declared, *run_evidence])


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
@pytest.mark.parametrize("declared", DECLARED_RELEASES, ids=lambda d: d.name)
def test_every_declared_release_directory_is_pinned_to_lf(
    declared: DeclaredRelease,
) -> None:
    """A checkout that wrote CRLF would change both files' digests."""
    paths = [f"{declared.directory}/{name}" for name in GENERATED_FILES]
    result = subprocess.run(
        ["git", "check-attr", "eol", "--", *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == [f"{path}: eol: lf" for path in paths]


# --------------------------------------------------------------------------
# 2. Expected failure: edited files
# --------------------------------------------------------------------------


def test_an_edited_value_is_a_drifted_file_and_an_unrecorded_values_digest(
    root: Path,
) -> None:
    edit(release_path(root, VALUES), 'cpu: "6"', 'cpu: "8"')
    findings = verify(REFERENCE, root)
    assert found(findings) == [
        ("generated-release-values-unrecorded", VALUES),
        ("generated-release-file-drifted", VALUES),
    ]
    diff = findings[1].diff
    assert diff[0] == f"--- committed/{REFERENCE.directory}/{VALUES}"
    assert diff[1] == f"+++ derived/{REFERENCE.directory}/{VALUES}"
    assert '-      cpu: "8"' in diff
    assert '+      cpu: "6"' in diff


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("profile: ", "# reviewed by hand\nprofile: "),
        ("  enabled: true\n", "  enabled: true  \n"),
        ('profile: "real"', "profile: real"),
    ],
    ids=["comment", "trailing-space", "unquoted-string"],
)
def test_an_edit_helm_would_read_the_same_is_still_drift(
    root: Path, old: str, new: str
) -> None:
    edit(release_path(root, VALUES), old, new)
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-values-unrecorded", VALUES),
        ("generated-release-file-drifted", VALUES),
    ]


def test_a_crlf_checkout_is_named_as_a_line_ending_difference(root: Path) -> None:
    path = release_path(root, VALUES)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    findings = verify(REFERENCE, root)
    assert found(findings) == [
        ("generated-release-values-unrecorded", VALUES),
        ("generated-release-file-drifted", VALUES),
    ]
    assert "only in line endings" in findings[1].detail
    assert "eol=lf" in findings[1].detail
    assert findings[1].diff == ()


PROVENANCE_EDITS: dict[str, tuple[str, str, list[tuple[str, str]]]] = {
    "renderer-revision": (
        f'revision: "{"a" * 40}"',
        f'revision: "{"c" * 40}"',
        [("generated-release-field-drifted", "source.renderer.revision")],
    ),
    "platform-defaults-revision": (
        f'revision: "{"b" * 40}"',
        f'revision: "{"c" * 40}"',
        [("generated-release-field-drifted", "source.platformDefaults.revision")],
    ),
    "release-identifier": (
        'releaseId: "b82be6908264',
        'releaseId: "c82be6908264',
        [("generated-release-field-drifted", "metadata.releaseId")],
    ),
    "binding-name": (
        'name: "local-kind"',
        'name: "local-docker-desktop"',
        [("generated-release-field-drifted", "source.environmentBinding.name")],
    ),
    "contract-digest": (
        'sha256: "56f73f78a6d7',
        'sha256: "66f73f78a6d7',
        [("generated-release-field-drifted", "source.contract.sha256")],
    ),
    "values-path": (
        'path: "values.generated.yaml"',
        'path: "values.yaml"',
        [("generated-release-field-drifted", "output.helmValues.path")],
    ),
    "values-digest": (
        'sha256: "49538bea8fae',
        'sha256: "2849af0c88c2',
        [
            ("generated-release-values-unrecorded", VALUES),
            ("generated-release-field-drifted", "output.helmValues.sha256"),
        ],
    ),
    "header-only": (
        "Do not edit by hand",
        "Edited by hand",
        [],
    ),
}


@pytest.mark.parametrize("name", list(PROVENANCE_EDITS))
def test_a_release_edited_to_name_other_provenance_is_reported_at_that_field(
    root: Path, name: str
) -> None:
    old, new, fields = PROVENANCE_EDITS[name]
    edit(release_path(root, RELEASE), old, new)
    findings = verify(REFERENCE, root)
    assert found(findings) == [*fields, ("generated-release-file-drifted", RELEASE)]
    assert findings[-1].diff, "a drifted release carries a diff"


def test_a_field_finding_states_the_cause_and_both_values(root: Path) -> None:
    edit(
        release_path(root, RELEASE),
        f'revision: "{"a" * 40}"',
        f'revision: "{"c" * 40}"',
    )
    (finding,) = [
        f
        for f in verify(REFERENCE, root)
        if f.rule_id == "generated-release-field-drifted"
    ]
    assert finding.detail == (
        f"{FIELD_CAUSES['source.renderer.revision']}; "
        f'committed "{"c" * 40}", derived "{"a" * 40}"'
    )


def test_values_and_a_release_forged_to_agree_are_still_drift(root: Path) -> None:
    """A hand edit with the digest updated to match is consistent with itself and
    not with its sources."""
    values = release_path(root, VALUES)
    edit(values, 'cpu: "6"', 'cpu: "8"')
    forged = hashlib.sha256(values.read_bytes()).hexdigest()
    edit(
        release_path(root, RELEASE),
        "49538bea8fae419d021f3d3bd8d28184fe328109b76a1eeef7f68cce4b9ac9eb",
        forged,
    )
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-field-drifted", "output.helmValues.sha256"),
        ("generated-release-file-drifted", VALUES),
        ("generated-release-file-drifted", RELEASE),
    ]


def test_a_release_that_does_not_parse_is_compared_as_text(root: Path) -> None:
    release_path(root, RELEASE).write_bytes(b"metadata: [unclosed\n")
    findings = verify(REFERENCE, root)
    assert found(findings) == [("generated-release-file-drifted", RELEASE)]
    assert "-metadata: [unclosed" in findings[0].diff


def test_a_non_ascii_byte_is_escaped_in_the_diff(root: Path) -> None:
    path = release_path(root, VALUES)
    path.write_bytes(path.read_bytes().replace(b'"real"', b'"r\xc3\xa9al"'))
    findings = verify(REFERENCE, root)
    diff = next(
        f for f in findings if f.rule_id == "generated-release-file-drifted"
    ).diff
    assert '-profile: "r\\xc3\\xa9al"' in diff
    assert all(line.isascii() for line in diff)


# --------------------------------------------------------------------------
# 3. Expected failure: stale sources
# --------------------------------------------------------------------------


def test_a_contract_change_no_value_carries_moves_only_the_contract_digest(
    root: Path,
) -> None:
    edit(root / REFERENCE.contract, "used to exercise", "used to test")
    findings = verify(REFERENCE, root)
    assert found(findings) == [
        ("generated-release-field-drifted", "metadata.releaseId"),
        ("generated-release-field-drifted", "source.contract.sha256"),
        ("generated-release-file-drifted", RELEASE),
    ]
    assert "stale" in findings[1].detail


def test_a_claim_relevant_contract_change_moves_the_values_too(root: Path) -> None:
    contract = root / REFERENCE.contract
    edit(contract, "minimumReplicas: 1", "minimumReplicas: 2")
    edit(contract, "maximumReplicas: 1", "maximumReplicas: 2")
    findings = verify(REFERENCE, root)
    assert found(findings) == [
        ("generated-release-field-drifted", "metadata.releaseId"),
        ("generated-release-field-drifted", "output.helmValues.sha256"),
        ("generated-release-field-drifted", "source.contract.sha256"),
        ("generated-release-file-drifted", VALUES),
        ("generated-release-file-drifted", RELEASE),
    ]
    values_diff = findings[3].diff
    assert "-  replicaCount: 1" in values_diff
    assert "+  replicaCount: 2" in values_diff


def test_a_binding_change_moves_only_the_binding_digest(root: Path) -> None:
    edit(
        root / REFERENCE.bindings[0],
        "destinationPath: gitops/environments/local-kind",
        "destinationPath: gitops/environments/local-kind-next",
    )
    findings = verify(REFERENCE, root)
    assert found(findings) == [
        ("generated-release-field-drifted", "metadata.releaseId"),
        ("generated-release-field-drifted", "source.environmentBinding.sha256"),
        ("generated-release-file-drifted", RELEASE),
    ]
    assert "stale" in findings[1].detail


def test_a_defaults_change_moves_the_values_and_not_the_identifier(root: Path) -> None:
    """Measured: the defaults revision is declared, so changed defaults content
    moves the values and their digest and leaves the identifier where it was."""
    edit(
        root / REFERENCE.platform_defaults,
        "requestTimeoutMs: 120000",
        "requestTimeoutMs: 60000",
    )
    findings = verify(REFERENCE, root)
    assert found(findings) == [
        ("generated-release-field-drifted", "output.helmValues.sha256"),
        ("generated-release-file-drifted", VALUES),
        ("generated-release-file-drifted", RELEASE),
    ]


def test_a_declaration_with_another_revision_is_drift(root: Path) -> None:
    moved = DeclaredRelease(
        directory=REFERENCE.directory,
        contract=REFERENCE.contract,
        bindings=REFERENCE.bindings,
        binding_name=REFERENCE.binding_name,
        platform_defaults=REFERENCE.platform_defaults,
        platform_defaults_revision=REFERENCE.platform_defaults_revision,
        renderer_revision="d" * 40,
    )
    assert found(verify(moved, root)) == [
        ("generated-release-field-drifted", "metadata.releaseId"),
        ("generated-release-field-drifted", "source.renderer.revision"),
        ("generated-release-file-drifted", RELEASE),
    ]


# --------------------------------------------------------------------------
# 4. Layout and refusal
# --------------------------------------------------------------------------


def test_a_missing_directory_is_reported_and_nothing_is_compared(root: Path) -> None:
    shutil.rmtree(root / REFERENCE.directory)
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-missing", REFERENCE.directory)
    ]


@pytest.mark.parametrize("name", GENERATED_FILES)
def test_a_missing_file_is_reported_and_the_other_is_still_compared(
    root: Path, name: str
) -> None:
    release_path(root, name).unlink()
    assert found(verify(REFERENCE, root)) == [("generated-release-file-missing", name)]
    (other,) = [other for other in GENERATED_FILES if other != name]
    path = release_path(root, other)
    path.write_bytes(path.read_bytes() + b"# appended by hand\n")
    findings = found(verify(REFERENCE, root))
    assert ("generated-release-file-missing", name) in findings
    assert ("generated-release-file-drifted", other) in findings


def test_a_stray_file_or_directory_is_reported(root: Path) -> None:
    release_path(root, "notes.txt").write_text("x\n", encoding="utf-8")
    release_path(root, "nested").mkdir()
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-unexpected-entry", "nested"),
        ("generated-release-unexpected-entry", "notes.txt"),
    ]


def test_a_staging_directory_left_by_an_unfinished_write_is_reported(
    root: Path,
) -> None:
    staging = root / REFERENCE.directory
    staging = staging.with_name(f".{staging.name}.partial")
    staging.mkdir()
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-staging-left", staging.name)
    ]


def test_a_file_where_the_release_directory_belongs_is_unexpected(
    root: Path,
) -> None:
    directory = root / REFERENCE.directory
    shutil.rmtree(directory)
    directory.write_text("not a release\n", encoding="utf-8")
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-unexpected-entry", REFERENCE.directory)
    ]
    before = snapshot(root)
    with pytest.raises(RegenerationRefused):
        regenerate(REFERENCE, root)
    assert snapshot(root) == before


def symlink_or_skip(link: Path, target: Path, *, directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"this host cannot create a symbolic link: {error}")


def test_a_release_directory_that_is_a_symbolic_link_is_unexpected(
    root: Path, tmp_path: Path
) -> None:
    directory = root / REFERENCE.directory
    elsewhere = tmp_path / "elsewhere"
    shutil.move(directory, elsewhere)
    symlink_or_skip(directory, elsewhere, directory=True)
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-unexpected-entry", REFERENCE.directory)
    ]
    with pytest.raises(RegenerationRefused):
        regenerate(REFERENCE, root)
    assert sorted(p.name for p in elsewhere.iterdir()) == sorted(GENERATED_FILES)


def test_a_generated_file_that_is_a_symbolic_link_is_not_compared(
    root: Path, tmp_path: Path
) -> None:
    path = release_path(root, VALUES)
    target = tmp_path / "values-elsewhere.yaml"
    shutil.move(path, target)
    symlink_or_skip(path, target, directory=False)
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-file-missing", VALUES),
        ("generated-release-unexpected-entry", VALUES),
    ]


@pytest.mark.parametrize(
    "document", [b"- a list\n", b"a scalar\n", b""], ids=["list", "scalar", "empty"]
)
def test_a_release_that_parses_to_no_mapping_is_compared_as_text(
    root: Path, document: bytes
) -> None:
    release_path(root, RELEASE).write_bytes(document)
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-file-drifted", RELEASE)
    ]


def test_sources_that_no_longer_render_are_reported_and_nothing_is_compared(
    root: Path,
) -> None:
    edit(root / REFERENCE.contract, "maximumReplicas: 1", "maximumReplicas: 2")
    release_path(root, VALUES).write_bytes(b"edited\n")
    findings = verify(REFERENCE, root)
    assert found(findings) == [
        ("generated-release-sources-refused", REFERENCE.contract)
    ]
    assert "RenderRefused" in findings[0].detail
    assert "maximumReplicas" in findings[0].detail


@pytest.mark.parametrize(
    "remove",
    [
        lambda d: d.contract,
        lambda d: d.bindings[0],
        lambda d: d.platform_defaults,
        lambda d: MATRIX_PATH,
    ],
    ids=["contract", "binding", "defaults", "matrix"],
)
def test_a_missing_input_is_a_refusal_not_a_crash(
    root: Path, remove: Callable[[DeclaredRelease], str]
) -> None:
    (root / remove(REFERENCE)).unlink()
    findings = verify(REFERENCE, root)
    assert found(findings) == [
        ("generated-release-sources-refused", REFERENCE.contract)
    ]
    assert "FileNotFoundError" in findings[0].detail
    # Named by its path under the root, so the report is the same on every host.
    assert remove(REFERENCE) in findings[0].detail
    assert str(root) not in findings[0].detail
    assert str(root.as_posix()) not in findings[0].detail


@pytest.mark.parametrize(
    "text", ["[]", "{", '"a string"'], ids=["list", "broken", "string"]
)
def test_a_malformed_compatibility_matrix_is_a_refusal_not_a_crash(
    root: Path, text: str
) -> None:
    (root / MATRIX_PATH).write_text(text, encoding="utf-8")
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-sources-refused", REFERENCE.contract)
    ]


def test_deriving_restores_the_compatibility_matrix_it_replaced(root: Path) -> None:
    before = get_matrix_loader()
    marker = CompatibilityMatrixLoader({"marker": True})
    set_matrix_loader(marker)
    try:
        derive(REFERENCE, root)
        assert get_matrix_loader() is marker
        (root / MATRIX_PATH).write_text("[]", encoding="utf-8")
        with pytest.raises(SourcesRefused):
            derive(REFERENCE, root)
        assert get_matrix_loader() is marker
    finally:
        set_matrix_loader(before)


def test_defaults_the_chart_does_not_set_are_a_refusal(root: Path) -> None:
    edit(root / REFERENCE.platform_defaults, "requestTimeoutMs: 120000", "")
    with pytest.raises(SourcesRefused, match=r"sets no api\.requestTimeoutMs"):
        derive(REFERENCE, root)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("  rollout:\n    maxUnavailable: 1\n", "", r"sets no runtime\.rollout$"),
        (
            "  rollout:\n    maxUnavailable: 1\n    maxSurge: 0\n",
            "  rollout: Recreate\n",
            r"has no runtime\.rollout mapping",
        ),
        (
            "    maxUnavailable: 1\n    maxSurge: 0\n",
            "    maxUnavailable: 1\n",
            r"sets no runtime\.rollout\.maxSurge",
        ),
        (
            "    maxUnavailable: 1\n    maxSurge: 0\n",
            "    maxUnavailable: 0\n    maxSurge: 0\n",
            "must not both be 0",
        ),
        (
            "    maxUnavailable: 1\n    maxSurge: 0\n",
            "    maxUnavailable: 50%\n    maxSurge: 0\n",
            "unavailable-pod bound",
        ),
    ],
)
def test_runtime_rollout_defaults_the_chart_does_not_state_are_a_refusal(
    root: Path, old: str, new: str, message: str
) -> None:
    """The runtime bounds are read from the chart's values file. A file that leaves
    one out, or states one the defaults refuse, derives no release."""
    path = root / REFERENCE.platform_defaults
    text = path.read_text(encoding="utf-8")
    if new == "":
        # Remove the whole block: the key, both bounds, and nothing else.
        old = "  rollout:\n    maxUnavailable: 1\n    maxSurge: 0\n"
    edit(path, old, new)
    assert text != path.read_text(encoding="utf-8")
    with pytest.raises(SourcesRefused, match=message):
        derive(REFERENCE, root)


def test_every_rule_is_listed_once() -> None:
    order = [rule.rule_id for rule in RULES]
    assert len(set(order)) == len(order)


def test_findings_are_reported_in_rule_order_not_in_the_order_they_are_found(
    root: Path,
) -> None:
    """The directory is read before its files are counted, so a stray entry is found
    first; the report still lists the missing file first, as the rules do."""
    release_path(root, VALUES).unlink()
    release_path(root, "notes.txt").write_text("x\n", encoding="utf-8")
    assert found(verify(REFERENCE, root)) == [
        ("generated-release-file-missing", VALUES),
        ("generated-release-unexpected-entry", "notes.txt"),
    ]


# --------------------------------------------------------------------------
# 5. Verification is a check, not a fix
# --------------------------------------------------------------------------


def drift(root: Path) -> None:
    edit(root / REFERENCE.contract, "used to exercise", "used to test")
    edit(release_path(root, VALUES), 'cpu: "6"', 'cpu: "8"')


def test_verification_writes_nothing_and_calls_no_writer(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drift(root)
    before = snapshot(root)

    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("verification called the writer")

    monkeypatch.setattr(core_module, "write_release", refuse)
    assert verify(REFERENCE, root)
    assert main(["--check", "--root", str(root)]) == 1
    assert snapshot(root) == before


def test_verification_opens_no_socket(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("verification opened a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert verify(REFERENCE, root) == ()
    drift(root)
    assert verify(REFERENCE, root)


def test_the_tool_imports_nothing_that_runs_a_process_or_reaches_a_network() -> None:
    forbidden = {
        "http",
        "requests",
        "socket",
        "ssl",
        "subprocess",
        "urllib",
        "asyncio",
        "multiprocessing",
    }
    for path in sorted(TOOL_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module]
            for name in names:
                assert name.split(".")[0] not in forbidden, (path.name, name)


def test_the_command_reports_the_rule_the_field_the_diff_and_the_fix(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drift(root)
    assert main(["--check", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert f"DRIFTED  {REFERENCE.name}  generated-release-values-unrecorded" in out
    assert "source.contract.sha256: the recorded contract digest is stale" in out
    assert f"--- committed/{REFERENCE.directory}/{VALUES}" in out
    assert f"+++ derived/{REFERENCE.directory}/{RELEASE}" in out
    assert f"regenerate with: {regenerate_command(REFERENCE)}" in out
    assert "regeneration replaces a hand edit" in out
    assert out.rstrip().endswith("1 of 1 declared releases drifted")


def test_the_command_does_not_advise_a_regeneration_that_would_be_refused(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drift(root)
    release_path(root, "notes.txt").write_text("x\n", encoding="utf-8")
    assert main(["--check", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "regenerate with:" not in out
    assert "regeneration refuses this release until each is resolved:" in out
    assert "move or remove what the platform did not write: notes.txt" in out


def test_every_blocking_rule_is_a_rule() -> None:
    assert {rule.rule_id for rule in RULES} >= BLOCKING_RULES
    assert "generated-release-file-drifted" not in BLOCKING_RULES
    assert "generated-release-missing" not in BLOCKING_RULES


def test_the_command_prints_the_same_report_in_two_interpreters(root: Path) -> None:
    drift(root)
    outputs = []
    for seed in ("0", "1"):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.generated_release",
                "--check",
                "--root",
                str(root),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
            check=False,
        )
        assert result.returncode == 1, result.stderr
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].isascii()


def test_an_unknown_release_name_is_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["--check", "no-such-release"])
    assert stopped.value.code == 2
    assert REFERENCE.name in capsys.readouterr().err


# --------------------------------------------------------------------------
# 6. Regeneration is explicit
# --------------------------------------------------------------------------


def test_regeneration_needs_a_release_name() -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["--write"])
    assert stopped.value.code == 2


def test_regeneration_repairs_drift_and_then_the_check_passes(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drift(root)
    assert main(["--write", REFERENCE.name, "--root", str(root)]) == 0
    assert f"WROTE    {REFERENCE.directory}" in capsys.readouterr().out
    assert verify(REFERENCE, root) == ()
    assert sorted(p.name for p in (root / REFERENCE.directory).iterdir()) == sorted(
        GENERATED_FILES
    )


def test_regenerating_an_unchanged_release_touches_nothing(root: Path) -> None:
    before = snapshot(root)
    assert regenerate(REFERENCE, root) is False
    assert snapshot(root) == before


def test_regeneration_writes_a_missing_release(root: Path) -> None:
    shutil.rmtree(root / REFERENCE.directory)
    assert regenerate(REFERENCE, root) is True
    assert verify(REFERENCE, root) == ()


def test_regeneration_refuses_to_remove_what_the_platform_did_not_write(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drift(root)
    release_path(root, "notes.txt").write_text("keep me\n", encoding="utf-8")
    before = snapshot(root)
    with pytest.raises(RegenerationRefused) as refused:
        regenerate(REFERENCE, root)
    assert found(refused.value.findings) == [
        ("generated-release-unexpected-entry", "notes.txt")
    ]
    assert main(["--write", REFERENCE.name, "--root", str(root)]) == 1
    assert "REFUSED  support-assistant-local-kind: nothing was written" in (
        capsys.readouterr().out
    )
    assert snapshot(root) == before


def test_regeneration_refuses_a_left_over_staging_directory(root: Path) -> None:
    drift(root)
    directory = root / REFERENCE.directory
    directory.with_name(f".{directory.name}.partial").mkdir()
    before = snapshot(root)
    with pytest.raises(RegenerationRefused):
        regenerate(REFERENCE, root)
    assert snapshot(root) == before


def test_a_failed_write_is_reported_and_running_again_writes_the_release(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    drift(root)

    def fail(*_: object, **__: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(core_module, "write_release", fail)
    assert main(["--write", REFERENCE.name, "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert f"FAILED   {REFERENCE.name}: OSError: disk full" in out
    assert "run --write again" in out
    # The old release is gone before the new one is written; it is never half written.
    assert not (root / REFERENCE.directory).exists()
    monkeypatch.undo()
    assert main(["--write", REFERENCE.name, "--root", str(root)]) == 0
    assert verify(REFERENCE, root) == ()


def test_regeneration_from_refused_sources_writes_nothing(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root / REFERENCE.contract, "maximumReplicas: 1", "maximumReplicas: 2")
    before = snapshot(root)
    assert main(["--write", REFERENCE.name, "--root", str(root)]) == 1
    assert "nothing was written: RenderRefused" in capsys.readouterr().out
    assert snapshot(root) == before


# --------------------------------------------------------------------------
# The pages say what the code does
# --------------------------------------------------------------------------


def test_the_renderer_page_lists_the_rules_the_check_applies() -> None:
    page = RENDERER_DOC.read_text(encoding="utf-8")
    rows = re.findall(r"^\| `(generated-release-[a-z-]+)` \| (.+?) \|$", page, re.M)
    assert rows == [(rule.rule_id, rule.statement) for rule in RULES]


def test_the_contributor_guide_states_the_verify_and_regenerate_workflow() -> None:
    guide = CONTRIBUTING.read_text(encoding="utf-8")
    assert "uv run --locked python -m tools.generated_release --check" in guide
    assert "uv run --locked python -m tools.generated_release --write" in guide
