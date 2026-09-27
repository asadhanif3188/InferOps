"""The `v1.0.0` release, held to the frozen evidence it is cut over.

`V1-S5-008-PR1` prepared the first versioned release: a version, a changelog section,
release notes, a checklist, and the data file both are held to. The failures this
module exists to prevent are the ones that make a release say more than its evidence:
a version that disagrees with the one place it is declared; a digest, gate, or count
that is not the evidence index's; a component identifier that no pinning file carries
or that some record contradicts; a figure that is not one the case study already reads
back from its record; a notes page that lost its reading path; and a surface that still
describes the repository before the release, left standing without the notes saying so
- or corrected quietly, so that the notes now describe a disagreement that has gone.

What it does not establish is that the release notes' prose says what the records
say, that a gate which only the hosting service can run has passed, or that the tag
exists. The first is a reading, and the other two are post-merge checks in the
checklist.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_index import PUBLICATION_PATH, load_index, load_ledger
from tools.evidence_model import load_register

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_PATH = REPO_ROOT / "docs" / "releases" / "v1.0.0.v1alpha1.json"
RELEASE: dict[str, Any] = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
EVIDENCE = RELEASE["evidence"]
INDEX = load_index()
SUMMARY = INDEX["summary"]
REGISTER = load_register()
PUBLICATION = load_ledger(PUBLICATION_PATH)
CASE_STUDY_DATA = json.loads(
    (REPO_ROOT / EVIDENCE["caseStudyDataRef"]).read_text(encoding="utf-8")
)

HEX = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")

#: A number written beside a unit of time, a percentage, a unit of memory, or a rate.
#: The case study declares and reads back exactly these; the notes may quote only the
#: ones it declares.
MEASUREMENT = re.compile(
    r"\b\d+(?:[ .,]\d+)*\s?(?:ms|%|GiB|MiB|GB|MB|seconds?|per second|min|times)(?!\w)"
)


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def normalised(text: str) -> str:
    return " ".join(text.split())


NOTES = normalised(read(RELEASE["notesRef"]))
CHECKLIST = normalised(read(RELEASE["checklistRef"]))


def _hex(value: str) -> str:
    match = HEX.search(value)
    assert match, value
    return match.group(0)


# ------------------------------------------------------------------ the version


def test_the_version_is_the_one_pyproject_declares_and_the_lock_records() -> None:
    project = tomllib.loads(read(RELEASE["versionSourceRef"]))["project"]
    assert project["version"] == RELEASE["version"] == "1.0.0"
    assert RELEASE["tag"] == f"v{RELEASE['version']}"
    lock = tomllib.loads(read("uv.lock"))
    (inferops,) = [row for row in lock["package"] if row["name"] == "inferops"]
    assert inferops["version"] == RELEASE["version"]


def test_the_changelog_has_the_release_section_under_an_empty_unreleased_one() -> None:
    changelog = read(RELEASE["changelogRef"])
    unreleased = changelog.index("\n## [Unreleased]\n")
    released = changelog.index(
        f"\n## [{RELEASE['version']}] - {RELEASE['preparedOn']}\n"
    )
    assert unreleased < released
    between = changelog[unreleased:released]
    assert "\n### " not in between, "an entry landed above the release section"
    assert changelog.count("\n## [") == 2, "a second release section appeared"
    for reference in (
        f"[Unreleased]: https://github.com/asadhanif3188/InferOps/compare/{RELEASE['tag']}...HEAD",
        f"[{RELEASE['version']}]: https://github.com/asadhanif3188/InferOps/releases/tag/{RELEASE['tag']}",
    ):
        assert reference in changelog


def test_every_release_surface_names_the_same_tag() -> None:
    tag = RELEASE["tag"]
    for relative in (
        RELEASE["notesRef"],
        RELEASE["checklistRef"],
        RELEASE["processRef"],
        "README.md",
        "SECURITY.md",
    ):
        assert f"`{tag}`" in read(relative), relative
    assert f"git tag -a {tag} " in CHECKLIST
    assert f"git push origin {tag}" in CHECKLIST


# -------------------------------------------------------------- the frozen evidence


def test_the_release_is_cut_over_the_frozen_pack_the_index_states() -> None:
    assert SUMMARY["releaseGate"] == EVIDENCE["releaseGate"] == "complete"
    assert SUMMARY["releaseBlockers"] == EVIDENCE["releaseBlockers"] == 0
    assert SUMMARY["blockersRaised"] == EVIDENCE["blockersRaised"]
    assert SUMMARY["evidenceFreeze"] == EVIDENCE["evidenceFreeze"] == "frozen"
    assert PUBLICATION["freeze"]["decidedIn"] == EVIDENCE["freezeDecidedIn"]
    assert SUMMARY["evidenceSetSha256"] == EVIDENCE["evidenceSetSha256"]
    assert SUMMARY["evidencePackSha256"] == EVIDENCE["evidencePackSha256"]


def test_the_case_study_was_verified_against_the_same_pack() -> None:
    verified = CASE_STUDY_DATA["verifiedAgainst"]
    assert CASE_STUDY_DATA["status"] == "published"
    assert verified["evidenceSetSha256"] == EVIDENCE["evidenceSetSha256"]
    assert verified["evidencePackSha256"] == EVIDENCE["evidencePackSha256"]
    assert verified["evidenceFreeze"] == EVIDENCE["evidenceFreeze"]


def test_the_notes_and_the_checklist_quote_both_digests_and_the_gate() -> None:
    for digest in (EVIDENCE["evidenceSetSha256"], EVIDENCE["evidencePackSha256"]):
        assert digest in NOTES
        assert digest in CHECKLIST
    assert f"Evidence pack sha256:{EVIDENCE['evidencePackSha256']}" in CHECKLIST
    assert "python -m tools.evidence_index --gate" in NOTES
    assert EVIDENCE["gateCommand"] in CHECKLIST


def test_no_release_file_is_inside_the_evidence_pack() -> None:
    """A release that edited a cited file, the register, or a ledger would move the pack."""
    pack = {row["path"] for row in INDEX["packSources"]}
    pack |= {row["path"] for record in INDEX["records"] for row in record["evidence"]}
    for relative in (
        RELEASE["notesRef"],
        RELEASE["checklistRef"],
        RELEASE_PATH.relative_to(REPO_ROOT).as_posix(),
    ):
        assert relative not in pack


# ------------------------------------------------------------------- the counts


def test_the_counts_are_the_index_s_and_the_register_s() -> None:
    counts = RELEASE["counts"]
    assert counts["claims"] == SUMMARY["claims"] == len(REGISTER["claims"])
    assert counts["claimsByStatus"] == SUMMARY["claimsByStatus"]
    by_status: dict[str, int] = {}
    for claim in REGISTER["claims"]:
        by_status[claim["status"]] = by_status.get(claim["status"], 0) + 1
    assert by_status == counts["claimsByStatus"]
    assert counts["records"] == SUMMARY["records"]
    assert counts["recordsByLevel"] == SUMMARY["recordsByLevel"]
    assert counts["executedRecords"] == SUMMARY["executedRecords"]
    assert (
        counts["executedRecordsNamingTheRevisionThatRan"]
        == SUMMARY["executedRecordsNamingTheRevisionThatRan"]
    )


def test_the_notes_state_the_counts_the_data_holds() -> None:
    counts = RELEASE["counts"]
    status = counts["claimsByStatus"]
    level = counts["recordsByLevel"]
    assert (
        f"{counts['claims']} claims, of which {status['certified']} are certified, "
        f"{status['planned']} planned, {status['deferred']} deferred, and "
        f"{status['not-claimed']} not claimed"
    ) in NOTES
    assert (
        f"{counts['records']} evidence records, of which {level['C0']} are `C0`, "
        f"{level['C1']} are `C1`, {level['C2']} are `C2`, and none is `C3` or `C4`"
    ) in NOTES
    assert level["C3"] == level["C4"] == 0
    assert (
        f"{counts['executedRecordsNamingTheRevisionThatRan']} of the "
        f"{counts['executedRecords']} records that executed"
    ) in NOTES


# --------------------------------------------------------------- the components


def _index_values(kind: str, names: list[str]) -> list[str]:
    return [
        row["value"]
        for record in INDEX["records"]
        for row in record["identifiers"].get(kind, [])
        if row["component"] in names
    ]


@pytest.mark.parametrize(
    "component", RELEASE["components"], ids=lambda row: row["componentId"]
)
def test_every_component_is_pinned_where_the_data_says(component: dict) -> None:
    for relative in component["pinnedIn"]:
        assert component["pinnedAs"] in read(relative), (
            relative,
            component["pinnedAs"],
        )


@pytest.mark.parametrize(
    "component", RELEASE["components"], ids=lambda row: row["componentId"]
)
def test_every_component_is_the_one_the_evidence_records_name(component: dict) -> None:
    values = _index_values(
        component["identifierKind"], component["evidenceComponentNames"]
    )
    assert values, "no record in the index names this component"
    if component["identifierKind"] == "chart-version":
        ours = component["value"].removeprefix("inferops-llm-")
        seen = {value.removeprefix("inferops-llm-") for value in values}
    else:
        ours = _hex(component["value"])
        seen = {_hex(value) for value in values}
    assert ours in seen
    others = sorted(seen - {ours})
    if component["everyRecordAgrees"]:
        assert not others, others
    else:
        assert others == component["otherValuesInTheIndex"], others


@pytest.mark.parametrize(
    "component", RELEASE["components"], ids=lambda row: row["componentId"]
)
def test_the_notes_name_every_component(component: dict) -> None:
    assert component["value"].removeprefix("inferops-llm-") in NOTES


def test_the_notes_say_nothing_but_the_tag_and_source_archives_is_published() -> None:
    assert "No InferOps container image" in NOTES
    assert "No package, chart, or model" in NOTES
    assert "No file is attached" in CHECKLIST
    assert "gh release upload" not in CHECKLIST


# ------------------------------------------------------------------ the figures


def test_every_quoted_figure_is_one_the_case_study_reads_back() -> None:
    declared = {row["figureId"]: row for row in CASE_STUDY_DATA["figures"]}
    for figure in RELEASE["figures"]:
        source = declared[figure["caseStudyFigureId"]]
        assert source["quoted"] == figure["quoted"], figure
        assert figure["quoted"] in NOTES, figure


def test_no_measurement_in_the_notes_lacks_a_declared_figure() -> None:
    """A figure the notes introduce themselves has no record behind it."""
    remainder = NOTES
    for figure in sorted(RELEASE["figures"], key=lambda row: -len(row["quoted"])):
        remainder = remainder.replace(figure["quoted"], " ")
    stray = MEASUREMENT.findall(remainder)
    assert not stray, stray


def test_the_measurement_scan_finds_what_it_is_for() -> None:
    for sentence in (
        "the outage lasted 31 960 ms",
        "it used 99.1% of its limit",
        "a 1.71 GiB download",
        "0.6 per second",
        "about 5.4 times the processor",
    ):
        assert MEASUREMENT.search(sentence), sentence


# ------------------------------------------------------------- the reading path


def test_the_notes_link_the_whole_reading_path() -> None:
    for target in (
        "../../README.md",
        "../case-study/v1-engineering-case-study.md",
        "../proof/dashboard.md",
        "../proof/v1-evidence-index.md",
        "../proof/README.md",
        "../architecture/README.md",
        "../environment/operator-runbook.md",
        "../architecture/system-architecture.md",
        "v1.0.0-checklist.md",
    ):
        assert f"]({target}" in NOTES, target
    path = NOTES.index("**The reading path.**")
    order = [
        NOTES.index(f"]({target}", path)
        for target in (
            "../../README.md",
            "../case-study/v1-engineering-case-study.md",
            "../proof/dashboard.md",
            "../proof/v1-evidence-index.md",
        )
    ]
    assert order == sorted(order), "the reading path is out of order"


def test_the_notes_lead_with_the_findings_before_the_capabilities() -> None:
    headings = [
        line
        for line in read(RELEASE["notesRef"]).splitlines()
        if line.startswith("## ")
    ]
    assert headings[:3] == [
        "## The problem V1 investigated",
        "## What the evidence showed",
        "## What the release contains",
    ], headings
    assert "## What it does not contain" in headings


def test_the_readme_and_the_process_link_the_release() -> None:
    readme = read("README.md")
    first_screen = readme.split("\n## Architecture\n", 1)[0]
    assert "](docs/releases/v1.0.0.md)" in first_screen
    process = read(RELEASE["processRef"])
    for target in (
        "releases/v1.0.0.md",
        "releases/v1.0.0-checklist.md",
        "releases/v1.0.0.v1alpha1.json",
    ):
        assert f"]({target})" in process, target
    assert "No versioned release currently exists." not in process


def test_the_notes_state_the_boundary_and_deny_production_readiness() -> None:
    assert "one Windows host, CPU only, one replica of each tier" in NOTES
    assert "V1 is not a production-ready or portable platform" in NOTES
    assert (
        "project-defined and not an ISO, NIST, regulatory, or industry certification standard"
        in NOTES
    )


# --------------------------------------- the surfaces the release leaves standing


def _surface(surface_id: str) -> dict:
    (row,) = [
        row
        for row in RELEASE["describesTheRepositoryBeforeTheRelease"]
        if row["surfaceId"] == surface_id
    ]
    return row


def test_the_register_still_lists_the_release_as_not_claimed() -> None:
    """A tripwire. When a later change moves this row, the notes' section must go too."""
    surface = _surface("register-release-row")
    index = int(surface["pointer"].rsplit("/", 1)[1])
    claim = REGISTER["claims"][index]
    assert claim["claimId"] == "a-v1-release-has-been-published"
    assert claim["status"] == "not-claimed"
    assert claim["notClaimedReason"] == surface["says"]
    assert "`a-v1-release-has-been-published`" in NOTES


def test_every_surface_left_standing_still_says_what_the_notes_say_it_says() -> None:
    for surface in RELEASE["describesTheRepositoryBeforeTheRelease"]:
        if surface["surfaceId"] == "register-release-row":
            continue
        if surface["surfaceId"] == "register-security-policy-reason":
            (row,) = [
                r for r in REGISTER["nonClaimSurfaces"] if r["path"] == "SECURITY.md"
            ]
            text = row["reason"]
        else:
            text = read(surface["path"])
        assert surface["says"] in normalised(text), surface["surfaceId"]


def test_the_notes_explain_every_surface_left_standing() -> None:
    section = NOTES.split(
        "## Where the frozen evidence still describes the repository before this release",
        1,
    )[1].split("## ", 1)[0]
    for phrase in (
        "The register and the proof dashboard",
        "gives, as the reason `SECURITY.md` claims nothing",
        "The case study",
    ):
        assert phrase in section, phrase
    assert len(RELEASE["describesTheRepositoryBeforeTheRelease"]) == 4


def _difference(difference_id: str) -> dict:
    (row,) = [
        row
        for row in RELEASE["differsFromWhatWasMeasured"]
        if row["differenceId"] == difference_id
    ]
    return row


def test_the_composition_s_service_version_is_the_release_version() -> None:
    """The composition tool requires it; the first draft of this release said otherwise.

    It left the composition at `0.0.0` and called `service.version` a label set at
    deployment rather than read from the distribution. `tools/local_composition`
    refuses exactly that, and the suite refused to collect until it was corrected.
    """
    difference = _difference("service-version-label")
    composition = json.loads(read(difference["path"]))
    environment = composition["adapter"]["environment"]
    assert environment["INFEROPS_SERVICE_VERSION"] == difference["released"]
    assert difference["released"] == RELEASE["version"]
    try:
        measured = subprocess.run(
            [
                "git",
                "show",
                f"bcad343133ba6fddfe38832a2694e71777cdd006:{difference['path']}",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the baseline rerun's revision is not in this clone")
    was = json.loads(measured)["adapter"]["environment"]["INFEROPS_SERVICE_VERSION"]
    assert was == difference["measured"]


def test_the_notes_state_every_difference_from_what_was_measured() -> None:
    section = NOTES.split(
        "## Where the released tree differs from what was measured", 1
    )[1].split("## ", 1)[0]
    assert "`service.version`" in section
    assert "`0.0.0` to `1.0.0`" in section
    assert "The InferOps API image" in section
    assert len(RELEASE["differsFromWhatWasMeasured"]) == 2


# ------------------------------------------------------------- the P0 stories


def _merge_subjects() -> list[str] | None:
    try:
        output = subprocess.run(
            ["git", "log", "--merges", "--format=%s", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    subjects = [
        line for line in output.splitlines() if line.startswith("Merge pull request #")
    ]
    return subjects or None


def test_every_p0_story_is_listed_once() -> None:
    stories = [row["storyId"] for row in RELEASE["p0Stories"]]
    assert len(stories) == len(set(stories))
    assert "V1-S5-008" not in stories, "the release cannot depend on itself"
    for row in RELEASE["p0Stories"]:
        assert row["mergedBy"] or row.get("note"), row["storyId"]


def test_every_listed_merge_carries_its_story_and_no_story_merge_is_missing() -> None:
    """Reads the repository's history; a shallow clone, as in continuous integration, skips."""
    subjects = _merge_subjects()
    if subjects is None or len(subjects) < 90:
        pytest.skip("the merge history is not in this clone")
    branches = {}
    for subject in subjects:
        match = re.match(r"Merge pull request (#\d+) from [^/]+/(\S+)", subject)
        if match:
            branches[match.group(1)] = match.group(2)
    listed = set()
    for row in RELEASE["p0Stories"]:
        slug = row["storyId"].lower()
        for number in row["mergedBy"]:
            assert slug in branches[number], (
                row["storyId"],
                number,
                branches.get(number),
            )
            listed.add(number)
    story_merges = {
        number
        for number, branch in branches.items()
        if re.search(r"v1-s\d-\d{3}", branch) and "v1-s5-008" not in branch
    }
    assert story_merges <= listed, sorted(story_merges - listed)


def _git_ok(*arguments: str) -> bool:
    try:
        return (
            subprocess.run(
                ["git", *arguments], cwd=REPO_ROOT, capture_output=True, check=False
            ).returncode
            == 0
        )
    except OSError:
        return False


def test_the_story_committed_without_a_merge_is_on_main() -> None:
    commits = ("7c15b6e", "bfe02c0")
    if not all(_git_ok("cat-file", "-e", f"{commit}^{{commit}}") for commit in commits):
        pytest.skip("those commits are not in this clone")
    for commit in commits:
        assert _git_ok("merge-base", "--is-ancestor", commit, "HEAD"), commit
    (row,) = [row for row in RELEASE["p0Stories"] if row["storyId"] == "V1-S1-008"]
    assert all(commit in row["note"] for commit in commits)
