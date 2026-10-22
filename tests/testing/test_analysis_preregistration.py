"""The freeze records of the two analysis experiments, held to their sources.

V2-S6-006-PR1 registered revision 1 of the freeze records of V2-E03 (signal
truthfulness) and V2-E06 (reliability resource and cost overhead), before any run
of an experiment whose runs they read. V2-S6-008-PR1 registered revision 2 of the
record of V2-E03, which binds revision 3 of V2-E04. ``tools.experiment_freeze`` checks that each
record answers every freeze field. ``tools.analysis_preregistration`` reads the
answers: the source bindings, the values that each record states for its sources,
and the rules of each record.

The first part holds the committed records, with their identities written out so
that a change to one is visible in review. The second part plants each defect that
the V2-E03 rules refuse in a copy of the files that the check reads, and asserts the
exact findings. The third part does the same for the V2-E06 rules. Those parts read
a copy of the records as they were before V2-S6-008-PR1, so that revision 1 of
V2-E03 is the latest one in it and its rules read as they did. The fifth part holds
revision 2 of V2-E03 and the three rules of a later revision in a copy of every
committed record. No test runs an analysis, computes a figure, or contacts a cluster.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tools.analysis_preregistration import (
    E03,
    E03_SIGNALS,
    E06,
    E06_METRICS,
    RULES,
    check_repository,
    core,
    policy_digest,
)
from tools.experiment_freeze.core import (
    FROZEN_RECORDS,
    changed_inputs,
    check_record,
    content_digest,
    material_files,
)
from tools.experiment_freeze.core import (
    check_repository as check_freezes,
)
from tools.experiment_preregistration import (
    check_repository as check_reliability_records,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "docs/proof/experiments/registry.v1alpha1.json"

E03_RECORD = "docs/proof/experiments/v2-e03/freeze-r1.v1alpha1.json"
E06_RECORD = "docs/proof/experiments/v2-e06/freeze-r1.v1alpha1.json"
#: The registered pins of the two records, written out so that a change is visible.
E03_PIN = "e0aeb1d228df5dfe28adede301fd038c2445f505a196a73b3dbae6461c4e0bca"
E06_PIN = "e774e5f1d46f7c544a65d449ec7f512b6aca8f004ddbbf8298a2ac1d7375b468"
#: Revision 2 of V2-E03 and revision 3 of V2-E04, registered by V2-S6-008-PR1.
E03_R2 = "docs/proof/experiments/v2-e03/freeze-r2.v1alpha1.json"
E03_R2_PIN = "d29572a6c6eab24068d1c4aecdb4cb1ad31bed5a79d3683471b0a933cf0c715a"
E04_R3 = "docs/proof/experiments/v2-e04/freeze-r3.v1alpha1.json"
E04_R3_PIN = "41fa69cd4a84940f587577a3278083d86f9c2b970e7ba5179aded10a07fc1f05"

#: The freeze record of each source that revision 1 of each record binds: the
#: latest of each before V2-S6-008-PR1.
SOURCE_RECORDS = {
    "V2-E02A": "docs/proof/experiments/v2-e02a/freeze-r2.v1alpha1.json",
    "V2-E02B": "docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json",
    "V2-E02C": "docs/proof/experiments/v2-e02c/freeze-r2.v1alpha1.json",
    "V2-E04": "docs/proof/experiments/v2-e04/freeze-r2.v1alpha1.json",
}
#: The latest freeze record of each source, which revision 2 of V2-E03 binds.
LATEST_SOURCES = {**SOURCE_RECORDS, "V2-E04": E04_R3}
#: The records that V2-S6-008-PR1 added. The second to the fourth part read a copy
#: without them.
ADDED = (E03_R2, E04_R3)
#: The records that V2-S7-001-PR1 added: revision 3 of V2-E02A, which pins its
#: driver, and revision 3 of V2-E03 and revision 2 of V2-E06, which bind it. Every
#: copy leaves them out except :func:`later_root`, so that the earlier parts read
#: revision 2 of V2-E03 and revision 1 of V2-E06 as the latest records.
E02A_R3 = "docs/proof/experiments/v2-e02a/freeze-r3.v1alpha1.json"
E03_R3 = "docs/proof/experiments/v2-e03/freeze-r3.v1alpha1.json"
E03_R3_PIN = "c95d8bc5a11871f6138088ee62917ecff1920584e427f6f4a9c5189d97e8bb10"
E06_R2 = "docs/proof/experiments/v2-e06/freeze-r2.v1alpha1.json"
E06_R2_PIN = "3c70ee508893be8df42aacea1dbb391be3f3228ca1768401ec6dd3d9a029139a"
LATER = (E02A_R3, E03_R3, E06_R2)
DRIVER = "docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt"
SUPERSEDED_E02A = "docs/proof/experiments/v2-e02a/freeze-r1.v1alpha1.json"
PREREGISTRATION_CORE = "tools/experiment_preregistration/core.py"
EXPERIMENT_DIRECTORIES = ("v2-e02a", "v2-e02b", "v2-e02c", "v2-e04", "v2-e05")


def load(path: str, root: Path = REPO_ROOT) -> dict[str, Any]:
    document = json.loads((root / path).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def found(findings: list[Any]) -> set[tuple[str, str]]:
    return {(f.rule_id, f.location) for f in findings}


# --------------------------------------------------------------------------
# 1. The committed records
# --------------------------------------------------------------------------


def test_the_committed_records_hold_every_rule() -> None:
    assert check_repository() == []


def test_the_command_passes_over_the_committed_records() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.analysis_preregistration", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == (
        "PASSED: 2 analysis experiment(s), every rule held"
    )


def test_each_revision_1_keeps_the_row_it_was_registered_with() -> None:
    """Revision 1 of each record keeps its row and its pin. Revision 3 of V2-E04 and
    revision 2 of V2-E03, registered by V2-S6-008-PR1, are the two rows after them."""
    registry = load(REGISTRY)["records"]
    rows = {row["path"]: row for row in registry}
    for path, pin in ((E03_RECORD, E03_PIN), (E06_RECORD, E06_PIN)):
        assert rows[path] == {
            "path": path,
            "contentSha256": pin,
            "registeredBy": "V2-S6-006-PR1",
        }
        assert FROZEN_RECORDS[path] == pin
        assert content_digest((REPO_ROOT / path).read_bytes()) == pin
        metadata = load(path)["metadata"]
        assert metadata["revision"] == 1
        assert metadata["supersedes"] is None
        assert metadata["registeredBy"] == "V2-S6-006-PR1"
    # No earlier row moved, the two rows of V2-S6-008-PR1 follow, and then the three
    # rows of V2-S7-001-PR1.
    assert [row["path"] for row in registry[-7:]] == [
        E03_RECORD,
        E06_RECORD,
        E04_R3,
        E03_R2,
        *LATER,
    ]
    for path, pin, story in (
        (E04_R3, E04_R3_PIN, "V2-S6-008-PR1"),
        (E03_R2, E03_R2_PIN, "V2-S6-008-PR1"),
        (E03_R3, E03_R3_PIN, "V2-S7-001-PR1"),
        (E06_R2, E06_R2_PIN, "V2-S7-001-PR1"),
    ):
        assert rows[path] == {
            "path": path,
            "contentSha256": pin,
            "registeredBy": story,
        }
        assert content_digest((REPO_ROOT / path).read_bytes()) == pin


def test_each_record_binds_the_latest_source_revisions_by_digest() -> None:
    """Revision 1 of each record bound the latest source revisions when it was
    registered. The latest record of each binds the latest ones now."""
    roles = {
        E03_RECORD: (core.E03_SOURCES, SOURCE_RECORDS),
        E06_RECORD: (core.E06_SOURCES, SOURCE_RECORDS),
        E03_R2: (core.E03_SOURCES, LATEST_SOURCES),
        E03_R3: (core.E03_SOURCES, {**LATEST_SOURCES, "V2-E02A": E02A_R3}),
        E06_R2: (core.E06_SOURCES, {**SOURCE_RECORDS, "V2-E02A": E02A_R3}),
    }
    for path, (expected, bound) in roles.items():
        sources = load(path)["definition"]["sources"]
        assert {s["experiment"]: s["role"] for s in sources} == dict(expected)
        for source in sources:
            assert source["path"] == bound[source["experiment"]]
            assert source["revision"] == load(source["path"])["metadata"]["revision"]
            assert source["contentSha256"] == FROZEN_RECORDS[source["path"]]
            assert (
                source["preregistrationRules"]
                == (load(source["path"])["metadata"]["preregistrationRules"])
            )


def test_both_records_state_the_one_clock_policy_of_their_sources() -> None:
    digests = {
        policy_digest(load(p)["definition"]["clockPolicy"])
        for p in SOURCE_RECORDS.values()
    }
    assert len(digests) == 1
    assert policy_digest(load(E04_R3)["definition"]["clockPolicy"]) in digests
    for path in (E03_RECORD, E06_RECORD, E03_R2):
        assert load(path)["definition"]["sourceClockPolicy"]["sha256"] in digests


def test_the_e03_population_and_signals_are_as_frozen() -> None:
    definition = load(E03_RECORD)["definition"]
    population = definition["population"]
    assert population["initial"]["experiments"] == ["V2-E02A", "V2-E02B", "V2-E02C"]
    assert population["extension"]["experiments"] == ["V2-E04"]
    assert [e["experiment"] for e in population["excluded"]] == ["V2-E05"]
    signals = definition["signals"]
    assert [(s["number"], s["id"], s["stream"]) for s in signals] == [
        (number, ident, stream) for number, (ident, stream) in E03_SIGNALS.items()
    ]
    assert [s["role"] for s in signals] == ["reference", *["candidate"] * 9]
    assert not any("exploratory" in s or "winner" in s for s in signals)
    candidate = definition["operationalCandidate"]
    assert (candidate["signal"], candidate["role"], candidate["rankingPreference"]) == (
        2,
        "comparator",
        "none",
    )
    assert candidate["predeterminedWinner"] is False
    assert definition["ranking"]["comparator"] == "api-error-rate"
    assert [o["outcome"] for o in definition["callerFailures"]["outcomes"]] == [
        "http-error",
        "invalid-response",
        "timeout",
        "transport-error",
        "identity-refused",
    ]


def test_the_e06_views_metrics_and_statistic_are_as_frozen() -> None:
    definition = load(E06_RECORD)["definition"]
    assert [(v["id"], v["label"], v["reads"]) for v in definition["views"]] == [
        ("view-a", "static-allocation", ["requests"]),
        ("view-b", "static-allocation", ["requests"]),
    ]
    assert [m["id"] for m in definition["metrics"]] == list(E06_METRICS)
    measured = [m["id"] for m in definition["metrics"] if m["label"] == "measured"]
    assert measured == ["utilization"]
    utilization = definition["utilization"]
    assert utilization["stream"] == "resources"
    assert utilization["sourceRuns"]["experiments"] == ["V2-E02A", "V2-E02B"]
    assert "api-cpu-seconds" in utilization["queries"]
    assert definition["costBasis"]["basis"] == "local"
    assert definition["costBasis"]["cloud"]["used"] is False
    assert definition["evidenceTarget"]["allocation"] == "C0"
    assert definition["evidenceTarget"]["runDerived"] == "C2"


def test_each_record_pins_exactly_its_material_scope() -> None:
    """A tripwire: a file added to a scope, or one that moves, fails here. The latest
    record of each pins its scope. Revision 1 of V2-E03 differs from it by revision 3
    of V2-E04, which its scope names and which it does not pin, and by the two checks
    that V2-S6-008-PR1 edited. Revision 1 of V2-E06 differs by those two checks.
    Since V2-S7-001-PR1 each earlier revision also differs by revision 3 of V2-E02A,
    which revision 3 of V2-E03 and revision 2 of V2-E06 pin."""
    checks = [
        ("tools/analysis_preregistration/core.py", "changed"),
        (PREREGISTRATION_CORE, "changed"),
    ]
    later = (E02A_R3, "added")
    expected = {
        E03_R3: [],
        E06_R2: [],
        E03_R2: [later],
        E03_RECORD: [(E04_R3, "added"), later, *checks],
        E06_RECORD: [later, *checks],
    }
    for path, moved in expected.items():
        document = load(path)
        pinned = {item["path"] for item in document["pinnedInputs"]}
        scoped = material_files(document["materialScope"], REPO_ROOT)
        assert scoped - pinned == {p for p, kind in moved if kind == "added"}, path
        changes = changed_inputs(document, REPO_ROOT)
        assert sorted((c.path, c.kind) for c in changes) == sorted(moved), path


def test_every_source_revision_file_is_in_the_scope_so_a_later_one_is_added() -> None:
    for path, roles in ((E03_RECORD, core.E03_SOURCES), (E06_RECORD, core.E06_SOURCES)):
        paths = load(path)["materialScope"]["paths"]
        for source in roles:
            pattern = f"{core.SOURCE_DIRECTORIES[source]}/freeze-r*.v1alpha1.json"
            assert pattern in paths


def test_no_run_analysis_or_procedure_exists() -> None:
    """Nothing ran: no source run, no analysis, and no analysis code. The one
    procedure is the driver of V2-E02A, which V2-S7-001-PR1 added."""
    experiments = REPO_ROOT / "docs" / "proof" / "experiments"
    for directory in (*EXPERIMENT_DIRECTORIES, "v2-e03", "v2-e06"):
        assert not (experiments / directory / "runs").exists()
        assert (experiments / directory / "procedure").exists() == (
            directory == "v2-e02a"
        )
    assert sorted(p.name for p in (experiments / "v2-e03").iterdir()) == [
        "freeze-r1.v1alpha1.json",
        "freeze-r2.v1alpha1.json",
        "freeze-r3.v1alpha1.json",
    ]
    assert sorted(p.name for p in (experiments / "v2-e06").iterdir()) == [
        "freeze-r1.v1alpha1.json",
        "freeze-r2.v1alpha1.json",
    ]


def test_every_existing_record_still_passes() -> None:
    assert check_freezes() == []
    assert check_reliability_records() == []


def test_each_source_record_differs_from_its_pins_in_the_check_alone() -> None:
    """The four revisions 2 of rule set 2 and revision 2 of V2-E04 differ from their
    pins in one file, core.py of tools/experiment_preregistration, which
    V2-S6-005-PR1 and V2-S6-008-PR1 edited. Revision 3 of V2-E04 differs in none. A
    file that a change adds or edits would be listed here. Since V2-S7-001-PR1
    revision 2 of V2-E02A also lists the driver of V2-E02A as added, and revision 3
    of V2-E02A differs in none."""
    for experiment, path in SOURCE_RECORDS.items():
        changes = changed_inputs(load(path), REPO_ROOT)
        added = [(DRIVER, "added")] if experiment == "V2-E02A" else []
        assert sorted((c.path, c.kind) for c in changes) == sorted(
            [*added, (PREREGISTRATION_CORE, "changed")]
        )
    assert changed_inputs(load(E04_R3), REPO_ROOT) == []
    assert changed_inputs(load(E02A_R3), REPO_ROOT) == []
    e05 = load("docs/proof/experiments/v2-e05/freeze-r2.v1alpha1.json")
    assert [c.path for c in changed_inputs(e05, REPO_ROOT)] == [PREREGISTRATION_CORE]


def test_the_rules_of_each_record_are_separate() -> None:
    e03 = [rule for rule in RULES if rule.startswith("e03-")]
    e06 = [rule for rule in RULES if rule.startswith("e06-")]
    assert len(e03) + len(e06) == len(RULES)
    assert len(e03) == 17
    assert len(e06) == 13
    assert list(core.E03_LATER_RULES) == e03[-3:]


def test_the_streams_of_each_source_are_read_from_its_collection() -> None:
    for path in SOURCE_RECORDS.values():
        assert core._collected(load(path)) == {
            "caller": ("caller", None),
            "endpoints": ("timeline", 2000),
            "pods": ("timeline", 2000),
            "deployments": ("timeline", 2000),
            "argo": ("timeline", 2000),
            "telemetry": ("telemetry", 15000),
            "resources": ("telemetry", 15000),
        }


def test_no_public_text_names_a_section_of_another_document() -> None:
    for path in (E03_RECORD, E06_RECORD, E03_R2, E04_R3):
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        assert "§" not in text


# --------------------------------------------------------------------------
# A copy of the files that the check reads
# --------------------------------------------------------------------------


def _copy(tmp_path: Path, *, added: bool, later: bool = False) -> Path:
    """The registry and the freeze records that the check reads. Without ``added``,
    the records and the rows of V2-S6-008-PR1 are left out, and without ``later``
    those of V2-S7-001-PR1."""
    left_out = (() if added else ADDED) + (() if later else LATER)
    registry = load(REGISTRY)
    registry["records"] = [r for r in registry["records"] if r["path"] not in left_out]
    target = tmp_path / REGISTRY
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    base = REPO_ROOT / "docs" / "proof" / "experiments"
    for directory in (*EXPERIMENT_DIRECTORIES, "v2-e03", "v2-e06"):
        for record in sorted((base / directory).glob("freeze-r*.v1alpha1.json")):
            relative = record.relative_to(REPO_ROOT)
            if relative.as_posix() in left_out:
                continue
            (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(record, tmp_path / relative)
    return tmp_path


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A root that holds the registry and every freeze record of the check as they
    were before V2-S6-008-PR1: revision 1 of V2-E03 is the latest one in it."""
    return _copy(tmp_path, added=False)


@pytest.fixture
def full_root(tmp_path: Path) -> Path:
    """A root that holds the registry and every freeze record of the check as they
    were after V2-S6-008-PR1 and before V2-S7-001-PR1: revision 2 of V2-E03 is the
    latest one in it."""
    return _copy(tmp_path, added=True)


@pytest.fixture
def later_root(tmp_path: Path) -> Path:
    """A root that holds the registry and every committed freeze record."""
    return _copy(tmp_path, added=True, later=True)


def test_the_later_records_hold_every_rule_in_a_copy(later_root: Path) -> None:
    assert core.check_records(later_root) == []


def test_revision_3_of_v2_e03_and_revision_2_of_v2_e06_move_the_v2_e02a_binding_alone() -> (
    None
):
    """Each binds revision 3 of V2-E02A, and every other source binding, the
    definition, and the fields keep their earlier values, except the history, the
    list of changes, the freeze revision, and the revision of main."""
    for later, earlier in ((E03_R3, E03_R2), (E06_R2, E06_RECORD)):
        new, old = load(later), load(earlier)
        new_sources = {s["experiment"]: s for s in new["definition"]["sources"]}
        old_sources = {s["experiment"]: s for s in old["definition"]["sources"]}
        assert new_sources["V2-E02A"] == {
            **old_sources["V2-E02A"],
            "path": E02A_R3,
            "revision": 3,
            "contentSha256": FROZEN_RECORDS[E02A_R3],
        }
        assert {k: v for k, v in new_sources.items() if k != "V2-E02A"} == {
            k: v for k, v in old_sources.items() if k != "V2-E02A"
        }
        skipped = {"sources", "history", "changesFromSupersededRevision"}
        for key in set(new["definition"]) | set(old["definition"]):
            if key not in skipped:
                assert new["definition"].get(key) == old["definition"].get(key), key
        for key in new["fields"]:
            if key not in ("experimentIdVersion", "gitRevision"):
                assert new["fields"][key] == old["fields"][key], key
        assert new["materialScope"] == old["materialScope"]
        assert new["metadata"]["supersedes"] == {
            "path": earlier,
            "contentSha256": FROZEN_RECORDS[earlier],
        }


def edit(root: Path, path: str, change: Callable[[dict[str, Any]], None]) -> None:
    document = load(path, root)
    change(document)
    (root / path).write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def e03_findings(root: Path) -> set[tuple[str, str]]:
    return found(core.check_records(root, [E03]))


def e06_findings(root: Path) -> set[tuple[str, str]]:
    return found(core.check_records(root, [E06]))


def test_the_copy_holds_every_rule(root: Path) -> None:
    assert core.check_records(root) == []


# --------------------------------------------------------------------------
# 2. V2-E03
# --------------------------------------------------------------------------


def _signal(number: int) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def get(document: dict[str, Any]) -> dict[str, Any]:
        signal = document["definition"]["signals"][number - 1]
        assert signal["number"] == number
        return signal

    return get


def test_e03_refuses_a_removed_signal(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["definition"]["signals"].pop(7))
    assert e03_findings(root) == {("e03-signal-set", "definition.signals")}


def test_e03_refuses_an_eleventh_signal_without_the_exploratory_label(
    root: Path,
) -> None:
    def add(document: dict[str, Any]) -> None:
        extra = copy.deepcopy(document["definition"]["signals"][6])
        extra.update(number=11, id="deployment-available-replicas")
        document["definition"]["signals"].append(extra)

    edit(root, E03_RECORD, add)
    assert e03_findings(root) == {("e03-signal-set", "definition.signals")}


def test_e03_accepts_an_eleventh_signal_labeled_exploratory_and_not_ranked(
    root: Path,
) -> None:
    def add(document: dict[str, Any], ranked: bool) -> None:
        extra = copy.deepcopy(document["definition"]["signals"][6])
        extra.update(
            number=11,
            id="deployment-available-replicas",
            exploratory=True,
            ranked=ranked,
        )
        document["definition"]["signals"].append(extra)

    edit(root, E03_RECORD, lambda d: add(d, False))
    assert e03_findings(root) == set()
    edit(root, E03_RECORD, lambda d: d["definition"]["signals"][10].update(ranked=True))
    assert e03_findings(root) == {("e03-signal-set", "definition.signals[10].ranked")}


def test_e03_refuses_a_stale_source_digest(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["sources"][1].update(contentSha256="0" * 64),
    )
    assert e03_findings(root) == {
        ("e03-sources-stale", "definition.sources[1].contentSha256")
    }


def test_e03_refuses_a_source_that_is_a_superseded_revision(root: Path) -> None:
    def supersede(document: dict[str, Any]) -> None:
        document["definition"]["sources"][0].update(
            path=SUPERSEDED_E02A,
            revision=1,
            contentSha256=FROZEN_RECORDS[SUPERSEDED_E02A],
        )

    edit(root, E03_RECORD, supersede)
    # Revision 1 states no clock policy, so its policy digest differs as well.
    assert e03_findings(root) == {
        ("e03-sources-stale", "definition.sources[0].revision"),
        ("e03-source-fields-differ", "definition.sourceClockPolicy.sha256"),
    }


def test_e03_refuses_once_a_later_source_revision_is_registered(root: Path) -> None:
    """A later source revision needs a later revision of the analysis record."""
    later = "docs/proof/experiments/v2-e02c/freeze-r3.v1alpha1.json"
    source = load(SOURCE_RECORDS["V2-E02C"], root)
    source["metadata"].update(
        revision=3,
        supersedes={
            "path": SOURCE_RECORDS["V2-E02C"],
            "contentSha256": FROZEN_RECORDS[SOURCE_RECORDS["V2-E02C"]],
        },
    )
    text = json.dumps(source, indent=2, ensure_ascii=False) + "\n"
    (root / later).write_text(text, encoding="utf-8")
    registry = load(REGISTRY, root)
    registry["records"].append(
        {
            "path": later,
            "contentSha256": content_digest(text.encode("utf-8")),
            "registeredBy": "a later change",
        }
    )
    (root / REGISTRY).write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )
    assert e03_findings(root) == {
        ("e03-sources-stale", "definition.sources[2].revision")
    }
    # V2-E06 does not read V2-E02C, so it is not stale.
    assert e06_findings(root) == set()


def test_e03_refuses_a_signal_stream_that_no_source_collects(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: _signal(8)(d).update(stream="scrape-targets"))
    findings = core.check_records(root, [E03])
    assert {f.rule_id for f in findings} == {"e03-signal-streams"}
    details = {
        f.detail for f in findings if f.location == "definition.signals[7].stream"
    }
    assert details == {
        "telemetry",
        *(f"{s} does not collect 'scrape-targets'" for s in SOURCE_RECORDS),
    }


def test_e03_refuses_a_sampling_interval_other_than_the_source_collection(
    root: Path,
) -> None:
    edit(root, E03_RECORD, lambda d: _signal(3)(d)["sampling"].update(intervalMs=1000))
    assert e03_findings(root) == {
        ("e03-signal-streams", "definition.signals[2].sampling")
    }


def test_e03_refuses_a_query_outside_the_registered_telemetry_queries(
    root: Path,
) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: _signal(2)(d)["derivation"].update(queries=["api-cpu-seconds"]),
    )
    assert e03_findings(root) == {
        ("e03-signal-streams", "definition.signals[1].derivation.queries")
    }


def test_e03_refuses_e05_in_the_ranking_population(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["population"]["initial"]["experiments"].append(
            "V2-E05"
        ),
    )
    assert e03_findings(root) == {
        ("e03-population", "definition.population.initial"),
        ("e03-population", "definition.population"),
    }


def test_e03_refuses_an_e05_scope_rule_without_its_reason(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["population"]["excluded"][0].pop("reason"),
    )
    assert e03_findings(root) == {("e03-population", "definition.population.excluded")}


def test_e03_refuses_e04_in_the_initial_population(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["population"]["initial"]["experiments"].append(
            "V2-E04"
        ),
    )
    assert e03_findings(root) == {
        ("e03-population", "definition.population.initial"),
        ("e03-population", "definition.population"),
    }


def test_e03_refuses_a_missing_operational_signal_candidate(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["definition"].pop("operationalCandidate"))
    assert e03_findings(root) == {("e03-candidate", "definition.operationalCandidate")}


def test_e03_refuses_a_candidate_declared_a_winner(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["operationalCandidate"].update(
            predeterminedWinner=True, rankingPreference="first"
        ),
    )
    assert e03_findings(root) == {
        ("e03-candidate", "definition.operationalCandidate.predeterminedWinner"),
        ("e03-candidate", "definition.operationalCandidate.rankingPreference"),
    }


def test_e03_refuses_any_signal_declared_a_winner(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: _signal(4)(d).update(winner=True))
    assert e03_findings(root) == {("e03-candidate", "definition.signals[3].winner")}


def test_e03_refuses_another_signal_as_the_candidate(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["operationalCandidate"].update(
            signal=3, id="api-ready-endpoints"
        ),
    )
    assert e03_findings(root) == {
        ("e03-candidate", "definition.operationalCandidate.signal")
    }


def test_e03_refuses_a_removed_comparator_role_statement(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["operationalCandidate"].pop("comparatorCondition"),
    )
    assert e03_findings(root) == {
        ("e03-candidate", "definition.operationalCandidate.comparatorCondition")
    }


@pytest.mark.parametrize("removed", ["compared with itself", "no ranking preference"])
def test_e03_refuses_a_comparator_statement_without_its_phrases(
    root: Path, removed: str
) -> None:
    def cut(document: dict[str, Any]) -> None:
        candidate = document["definition"]["operationalCandidate"]
        candidate["comparatorCondition"] = candidate["comparatorCondition"].replace(
            removed, "x"
        )

    edit(root, E03_RECORD, cut)
    assert e03_findings(root) == {
        ("e03-candidate", "definition.operationalCandidate.comparatorCondition")
    }


def test_e03_refuses_a_removed_uncounted_caller_failure_rule(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["definition"].pop("callerFailures"))
    assert e03_findings(root) == {("e03-caller-failures", "definition.callerFailures")}


def test_e03_refuses_a_failure_rule_that_misses_an_outcome_or_a_figure(
    root: Path,
) -> None:
    def cut(document: dict[str, Any]) -> None:
        failures = document["definition"]["callerFailures"]
        failures["outcomes"].pop(2)
        failures["report"].pop(1)
        failures["outcomes"][1]["canonicalErrorCode"] = "when-stated"

    edit(root, E03_RECORD, cut)
    assert e03_findings(root) == {
        ("e03-caller-failures", "definition.callerFailures.outcomes"),
        (
            "e03-caller-failures",
            "definition.callerFailures.outcomes[1].canonicalErrorCode",
        ),
        ("e03-caller-failures", "definition.callerFailures.report"),
    }


def test_e03_refuses_an_unanswered_freeze_field(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["fields"].pop("cleanupProcedure"))
    assert e03_findings(root) == {("e03-fields-unanswered", "fields.cleanupProcedure")}


def test_e03_refuses_a_pending_freeze_field(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["fields"]["topology"][0].update(
            status="pending", reason="later", owner="someone"
        ),
    )
    findings = e03_findings(root)
    assert ("e03-fields-unanswered", "fields.topology") in findings
    assert {rule for rule, _ in findings} == {
        "e03-fields-unanswered",
        "e03-source-fields-differ",
    }


def test_e03_refuses_a_source_field_that_differs_from_its_source(root: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        fields = document["fields"]
        fields["fault"][0]["value"]["sources"]["V2-E02C"] = "delete-runtime-pod"
        fields["topology"][0]["value"]["sources"]["V2-E02A"]["runtimeReplicas"] = 2
        fields["repetitionCount"][0]["value"]["sources"]["V2-E04"] = "2 runs"
        fields["environmentIdentity"][0]["value"]["environmentSha256"] = (
            "sha256:" + "0" * 64
        )

    edit(root, E03_RECORD, change)
    assert e03_findings(root) == {
        ("e03-source-fields-differ", "fields.fault.sources.V2-E02C"),
        ("e03-source-fields-differ", "fields.topology.sources.V2-E02A"),
        ("e03-source-fields-differ", "fields.repetitionCount.sources.V2-E04"),
        ("e03-source-fields-differ", "fields.environmentIdentity"),
    }


def test_e03_refuses_a_claim_of_synchronized_clocks(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["timeline"].update(
            meaning="The timelines are synchronized to the node clock."
        ),
    )
    assert e03_findings(root) == {
        ("e03-clock-contradiction", "definition.timeline.meaning")
    }


def test_e03_refuses_an_ordering_rule_without_the_margin(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"].update(ordering="A lag is stated when it is known."),
    )
    assert e03_findings(root) == {("e03-computations", "definition.ordering")}


def test_e03_refuses_a_missing_signal_read_as_healthy(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["computations"].update(
            notObserved="A signal that is not observed counts as healthy."
        ),
    )
    assert e03_findings(root) == {
        ("e03-computations", "definition.computations.notObserved")
    }


def test_e03_refuses_a_ranking_on_one_figure_alone(root: Path) -> None:
    edit(
        root, E03_RECORD, lambda d: d["definition"]["ranking"].update(figures=["outer"])
    )
    assert e03_findings(root) == {("e03-ranking", "definition.ranking.figures")}


def test_e03_refuses_a_scope_without_its_procedure_directory(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["materialScope"]["paths"].pop(0))
    assert e03_findings(root) == {("e03-analysis-code", "materialScope.paths")}


def test_e03_refuses_a_missing_record(root: Path) -> None:
    (root / E03_RECORD).unlink()
    assert e03_findings(root) == {("e03-record-missing", "$")}


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(definition=[]),
        lambda d: d["definition"].update(sources="V2-E02A"),
        lambda d: d["definition"].update(signals={"1": "caller"}),
        lambda d: d["definition"].update(population=[]),
        lambda d: d["definition"].update(operationalCandidate="api-error-rate"),
        lambda d: d["definition"].update(callerFailures=["timeout"]),
        lambda d: d["definition"]["signals"].__setitem__(1, "api-error-rate"),
        lambda d: d["definition"]["sources"].__setitem__(0, ["V2-E02A"]),
        lambda d: d.update(fields=[]),
        lambda d: d.update(materialScope=None),
    ],
)
def test_e03_reports_a_malformed_member_and_never_raises(
    root: Path, change: Callable[[dict[str, Any]], None]
) -> None:
    edit(root, E03_RECORD, change)
    findings = core.check_records(root, [E03])
    assert findings
    assert all(f.rule_id.startswith("e03-") for f in findings)


# --------------------------------------------------------------------------
# 3. V2-E06
# --------------------------------------------------------------------------


def test_e06_refuses_a_stale_source_digest(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["sources"][0].update(contentSha256="f" * 64),
    )
    assert e06_findings(root) == {
        ("e06-sources-stale", "definition.sources[0].contentSha256")
    }


def test_e06_refuses_a_view_labeled_measured_that_reads_requests_only(
    root: Path,
) -> None:
    edit(
        root, E06_RECORD, lambda d: d["definition"]["views"][0].update(label="measured")
    )
    assert e06_findings(root) == {("e06-labels", "definition.views[0].label")}


@pytest.mark.parametrize(
    "reads", [["limits"], ["claim-request"], ["requests", "limits"]]
)
def test_e06_refuses_a_metric_labeled_measured_that_reads_configuration_only(
    root: Path, reads: list[str]
) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["metrics"][4].update(label="measured", reads=reads),
    )
    assert e06_findings(root) == {("e06-labels", "definition.metrics[4].label")}


def test_e06_refuses_a_missing_utilization_statistic(root: Path) -> None:
    edit(root, E06_RECORD, lambda d: d["definition"]["utilization"].pop("statistic"))
    assert e06_findings(root) == {
        ("e06-utilization", "definition.utilization.statistic")
    }
    edit(root, E06_RECORD, lambda d: d["definition"].pop("utilization"))
    assert e06_findings(root) == {("e06-utilization", "definition.utilization")}


def test_e06_refuses_utilization_source_runs_that_are_not_fixed(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["utilization"]["sourceRuns"].update(
            experiments=["V2-E02B"]
        ),
    )
    assert e06_findings(root) == {
        ("e06-utilization", "definition.utilization.sourceRuns")
    }


def test_e06_refuses_a_missing_cost_basis(root: Path) -> None:
    edit(root, E06_RECORD, lambda d: d["definition"].pop("costBasis"))
    assert e06_findings(root) == {("e06-cost-basis", "definition.costBasis")}


def test_e06_refuses_a_cloud_cost_without_a_later_revision(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["costBasis"].update(
            basis="aws", cloud={"used": True}
        ),
    )
    assert e06_findings(root) == {
        ("e06-cost-basis", "definition.costBasis.basis"),
        ("e06-cost-basis", "definition.costBasis.cloud"),
    }


def test_e06_refuses_an_unanswered_freeze_field(root: Path) -> None:
    edit(root, E06_RECORD, lambda d: d["fields"].pop("evidencePaths"))
    assert e06_findings(root) == {("e06-fields-unanswered", "fields.evidencePaths")}


def test_e06_refuses_a_view_b_that_is_not_reconstructed(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["views"][1]["sides"][0].update(reconstructed=False),
    )
    assert e06_findings(root) == {("e06-views", "definition.views[view-b].sides")}


def test_e06_refuses_a_view_a_side_that_differs_from_its_source(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["views"][0]["sides"][0].update(runtimeReplicas=2),
    )
    assert e06_findings(root) == {("e06-views", "definition.views[view-a].sides")}


def test_e06_refuses_another_evidence_target(root: Path) -> None:
    edit(
        root,
        E06_RECORD,
        lambda d: d["definition"]["evidenceTarget"].update(allocation="C2"),
    )
    assert e06_findings(root) == {
        ("e06-evidence-target", "definition.evidenceTarget.allocation")
    }


def test_e06_refuses_a_missing_metric_or_headroom_definition(root: Path) -> None:
    def cut(document: dict[str, Any]) -> None:
        document["definition"]["metrics"].pop(5)
        document["definition"].pop("rolloutHeadroom")

    edit(root, E06_RECORD, cut)
    assert e06_findings(root) == {
        ("e06-metrics", "definition.metrics"),
        ("e06-metrics", "definition.rolloutHeadroom"),
    }


def test_e06_rules_do_not_read_the_e03_record(root: Path) -> None:
    edit(root, E03_RECORD, lambda d: d["definition"].pop("signals"))
    assert e06_findings(root) == set()
    assert {rule for rule, _ in e03_findings(root)} >= {"e03-signal-set"}


def test_the_command_refuses_a_planted_defect(root: Path) -> None:
    edit(root, E06_RECORD, lambda d: d["definition"].pop("costBasis"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.analysis_preregistration",
            "--check",
            "--root",
            str(root),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "e06-cost-basis" in result.stdout
    assert "FAILED: 1 finding(s) across 2 analysis experiment(s)" in result.stdout


# --------------------------------------------------------------------------
# 4. What the independent review of the first commit found
# --------------------------------------------------------------------------


def _set(*path: Any, value: Any) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        target: Any = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _append(*path: Any, value: Any) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        target: Any = document
        for key in path:
            target = target[key]
        target.append(value)

    return change


@pytest.mark.parametrize(
    ("path", "change"),
    [
        (E03_RECORD, _set("definition", "signals", 2, "stream", value=["x"])),
        (
            E03_RECORD,
            _append(
                "definition",
                "signals",
                value={
                    "number": 11,
                    "exploratory": True,
                    "ranked": False,
                    "stream": ["x"],
                },
            ),
        ),
        (
            E03_RECORD,
            _set("definition", "signals", 1, "derivation", "queries", value=[[]]),
        ),
        (E03_RECORD, _set("fields", "fault", 0, "parts", value={"a": 1})),
        (
            E03_RECORD,
            _set("fields", "acceptanceCriteria", 0, "value", 0, "id", value=["x"]),
        ),
        (E06_RECORD, _append("definition", "views", value={"id": ["x"]})),
        (E06_RECORD, _set("definition", "views", 0, "id", value={"a": 1})),
        (E06_RECORD, _set("definition", "metrics", 0, "reads", value=[[]])),
        (
            E06_RECORD,
            _set("definition", "utilization", "queries", value=["api-cpu-seconds", []]),
        ),
        (E06_RECORD, _set("fields", "topology", 0, "parts", value={"a": 1})),
    ],
)
def test_an_unhashable_or_malformed_member_is_a_finding_and_never_raises(
    root: Path, path: str, change: Callable[[dict[str, Any]], None]
) -> None:
    """Each of these raised a TypeError in the first commit."""
    edit(root, path, change)
    experiment = E03 if path == E03_RECORD else E06
    findings = core.check_records(root, [experiment])
    assert findings
    assert all(f.rule_id.startswith(f"{experiment.prefix}-") for f in findings)


def test_a_malformed_pin_path_never_raises_and_is_the_freeze_check_finding(
    root: Path,
) -> None:
    """The pins are the freeze check's to refuse. This check reads only their paths."""
    edit(root, E03_RECORD, _append("pinnedInputs", value={"path": ["x"]}))
    assert core.check_records(root, [E03]) == []
    rules = {f.rule_id for f in check_record(load(E03_RECORD, root), E03_RECORD)}
    assert rules == {"freeze-pinned-input-malformed"}


def test_a_freeze_field_that_the_freeze_check_cannot_read_is_unanswered(
    root: Path,
) -> None:
    """tools.experiment_freeze raises on an identifier that is a list. It is not
    edited, because earlier records pin it, so this check reports the field."""
    edit(
        root,
        E06_RECORD,
        _set("fields", "acceptanceCriteria", 0, "value", 0, "id", value=["x"]),
    )
    assert e06_findings(root) == {("e06-fields-unanswered", "fields")}


@pytest.mark.parametrize(
    ("change", "location"),
    [
        (
            _set("definition", "signals", 3, "winner", value=0),
            "definition.signals[3].winner",
        ),
        (
            _set("definition", "signals", 3, "predeterminedWinner", value=True),
            "definition.signals[3].predeterminedWinner",
        ),
        (
            _set("definition", "ranking", "winner", value="api-error-rate"),
            "definition.ranking.winner",
        ),
        (
            _set("definition", "operationalCandidate", "winner", value=True),
            "definition.operationalCandidate.winner",
        ),
        (
            _set("definition", "signals", 1, "rankingPreference", value="first"),
            "definition.signals[1].rankingPreference",
        ),
    ],
)
def test_e03_refuses_a_winner_or_a_preference_anywhere_in_the_definition(
    root: Path, change: Callable[[dict[str, Any]], None], location: str
) -> None:
    edit(root, E03_RECORD, change)
    assert e03_findings(root) == {("e03-candidate", location)}


def test_e03_refuses_an_exploratory_second_reference(root: Path) -> None:
    def add(document: dict[str, Any]) -> None:
        extra = copy.deepcopy(document["definition"]["signals"][6])
        extra.update(number=1, exploratory=True, ranked=False, role="reference")
        document["definition"]["signals"].append(extra)

    edit(root, E03_RECORD, add)
    assert e03_findings(root) == {
        ("e03-signal-set", "definition.signals[10].number"),
        ("e03-signal-set", "definition.signals[10].role"),
    }


def test_e03_refuses_a_duplicated_signal(root: Path) -> None:
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["signals"].insert(
            4, copy.deepcopy(d["definition"]["signals"][3])
        ),
    )
    assert e03_findings(root) == {("e03-signal-set", "definition.signals")}


def test_e03_refuses_a_source_in_another_role_or_bound_twice(root: Path) -> None:
    edit(root, E03_RECORD, _set("definition", "sources", 3, "role", value="initial"))
    assert e03_findings(root) == {("e03-sources-stale", "definition.sources[3].role")}
    edit(root, E03_RECORD, _set("definition", "sources", 3, "role", value="extension"))
    edit(
        root,
        E03_RECORD,
        lambda d: d["definition"]["sources"].append(
            copy.deepcopy(d["definition"]["sources"][0])
        ),
    )
    assert e03_findings(root) == {("e03-sources-stale", "definition.sources")}


@pytest.mark.parametrize(
    ("change", "location"),
    [
        (
            _set(
                "definition",
                "callerFailures",
                "falseHealthy",
                value="Each failure counts.",
            ),
            "definition.callerFailures.falseHealthy",
        ),
        (
            _set("definition", "population", "laterSourceRevision", value="x"),
            "definition.population.laterSourceRevision",
        ),
        (
            _set(
                "definition", "analysisCode", "rule", value="Pinned before any figure."
            ),
            "definition.analysisCode",
        ),
    ],
)
def test_e03_refuses_a_rule_text_without_its_named_phrases(
    root: Path, change: Callable[[dict[str, Any]], None], location: str
) -> None:
    edit(root, E03_RECORD, change)
    assert {loc for _, loc in e03_findings(root)} == {location}


def test_e03_reads_only_the_phrases_it_names(root: Path) -> None:
    """A known gap: a text that holds the phrases and then says otherwise passes."""
    edit(
        root,
        E03_RECORD,
        _set(
            "definition",
            "computations",
            "notObserved",
            value="A signal is not never healthy; it counts as healthy.",
        ),
    )
    assert e03_findings(root) == set()


@pytest.mark.parametrize(
    ("changes", "location"),
    [
        (
            [_set("definition", "metrics", 3, "label", value="static-allocation")],
            "definition.metrics[3].label",
        ),
        (
            [
                _set("definition", "metrics", 0, "label", value="measured"),
                _set(
                    "definition",
                    "metrics",
                    0,
                    "reads",
                    value=["requests", "resources-stream"],
                ),
            ],
            "definition.metrics[0].label",
        ),
        (
            [_set("definition", "views", 0, "reads", value=["resources-stream"])],
            "definition.views[0].label",
        ),
    ],
)
def test_e06_refuses_a_label_that_contradicts_what_it_reads(
    root: Path, changes: list[Callable[[dict[str, Any]], None]], location: str
) -> None:
    """Only the utilization is measured, and a static allocation reads configuration."""
    for change in changes:
        edit(root, E06_RECORD, change)
    assert e06_findings(root) == {("e06-labels", location)}


def test_e06_refuses_a_price_or_a_cloud_rule_without_its_phrase(root: Path) -> None:
    edit(root, E06_RECORD, _set("definition", "costBasis", "price", value=0.5))
    assert e06_findings(root) == {("e06-cost-basis", "definition.costBasis.price")}
    edit(root, E06_RECORD, lambda d: d["definition"]["costBasis"].pop("price"))
    edit(root, E06_RECORD, _set("definition", "costBasis", "cloud", "rule", value="x"))
    assert e06_findings(root) == {("e06-cost-basis", "definition.costBasis.cloud")}


def test_a_superseded_revision_is_not_held_to_the_latest_sources(
    full_root: Path,
) -> None:
    """Revision 1 is superseded by revision 2, and binds revision 2 of V2-E04, which
    revision 3 supersedes. Once a later source revision is registered, only the
    latest revision is stale. (Until V2-S6-008-PR1 this test planted a revision 2.)"""
    root = full_root
    revision_2 = E03_R2
    assert e03_findings(root) == set()
    later = "docs/proof/experiments/v2-e02c/freeze-r3.v1alpha1.json"
    source = load(SOURCE_RECORDS["V2-E02C"], root)
    source["metadata"]["revision"] = 3
    text = json.dumps(source, indent=2) + "\n"
    (root / later).write_text(text, encoding="utf-8")
    registry = load(REGISTRY, root)
    registry["records"].append(
        {
            "path": later,
            "contentSha256": content_digest(text.encode()),
            "registeredBy": "x",
        }
    )
    (root / REGISTRY).write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )
    findings = core.check_records(root, [E03])
    assert {(f.record, f.rule_id, f.location) for f in findings} == {
        (revision_2, "e03-sources-stale", "definition.sources[2].revision")
    }


def test_another_experiment_is_refused_and_not_read_under_the_e06_rules() -> None:
    other = core.AnalysisExperiment(
        "V2-E07", "docs/proof/experiments/v2-e07", "E07", "e07"
    )
    with pytest.raises(ValueError, match="V2-E07"):
        core._record_findings(REPO_ROOT, "x", load(E06_RECORD), other, {}, latest=True)


# --------------------------------------------------------------------------
# 5. Revision 2 of V2-E03, which binds revision 3 of V2-E04
# --------------------------------------------------------------------------

#: The members in which revision 2 differs from revision 1, as it lists them.
E03_R2_CHANGED = [
    "definition.sources",
    "definition.population.extension",
    "definition.history",
    "fields.experimentIdVersion",
    "fields.gitRevision",
    "metadata",
    "pinnedInputs",
    "inputChanges",
]
E04_BINDING = "definition.sources[3]"


def _binding(document: dict[str, Any]) -> dict[str, Any]:
    (result,) = [
        s for s in document["definition"]["sources"] if s["experiment"] == "V2-E04"
    ]
    assert isinstance(result, dict)
    return result


def _extension(document: dict[str, Any]) -> dict[str, Any]:
    result = document["definition"]["population"]["extension"]
    assert isinstance(result, dict)
    return result


def test_e03_revision_2_holds_every_rule(full_root: Path) -> None:
    assert core.check_records(full_root) == []
    assert e03_findings(full_root) == set()


def test_e03_revision_2_differs_from_revision_1_only_in_the_listed_members() -> None:
    one, two = load(E03_RECORD), load(E03_R2)
    assert core._changed_members(one, two) == sorted(E03_R2_CHANGED)
    listed = two["definition"]["changesFromSupersededRevision"]
    assert [entry["member"] for entry in listed] == E03_R2_CHANGED
    assert all(entry["reason"] for entry in listed)
    assert two["metadata"] == {
        **one["metadata"],
        "revision": 2,
        "registered": "2026-10-20",
        "registeredBy": "V2-S6-008-PR1",
        "supersedes": {"path": E03_RECORD, "contentSha256": E03_PIN},
    }
    sources_1 = {s["experiment"]: s for s in one["definition"]["sources"]}
    sources_2 = {s["experiment"]: s for s in two["definition"]["sources"]}
    for experiment in ("V2-E02A", "V2-E02B", "V2-E02C"):
        assert sources_2[experiment] == sources_1[experiment]
    assert sources_2["V2-E04"] == {
        "experiment": "V2-E04",
        "role": "extension",
        "path": E04_R3,
        "revision": 3,
        "contentSha256": E04_R3_PIN,
        "preregistrationRules": 4,
    }
    extension = _extension(two)
    assert extension["experiments"] == ["V2-E04"]
    assert extension["executedUnder"] == {"path": E04_R3, "revision": 3}
    assert "revision 2 included, is not in the population" in extension["runs"]
    population_1 = one["definition"]["population"]
    population_2 = two["definition"]["population"]
    for member in ("initial", "excluded", "laterSourceRevision"):
        assert population_2[member] == population_1[member], member
    for member in (
        "signals",
        "operationalCandidate",
        "ranking",
        "callerFailures",
        "computations",
        "ordering",
        "sourceClockPolicy",
        "limitations",
    ):
        assert two["definition"][member] == one["definition"][member], member
    assert two["definition"]["history"][:-1] == one["definition"]["history"]
    moved = [c["path"] for c in two["inputChanges"]]
    assert moved == [
        E04_R3,
        "tools/analysis_preregistration/core.py",
        PREREGISTRATION_CORE,
    ]


def test_e03_revision_1_is_read_under_its_own_rules_and_unchanged() -> None:
    """Revision 1 states none of what the three later rules read, and they do not
    read it: it keeps its pin and its row, and it holds every rule it was read under,
    except that it is no longer the latest: its V2-E04 binding and, since
    V2-S7-001-PR1, its V2-E02A binding are superseded."""
    assert content_digest((REPO_ROOT / E03_RECORD).read_bytes()) == E03_PIN
    findings = core._record_findings(
        REPO_ROOT,
        E03_RECORD,
        load(E03_RECORD),
        E03,
        dict(FROZEN_RECORDS),
        latest=False,
    )
    assert findings == []
    latest = core._record_findings(
        REPO_ROOT,
        E03_RECORD,
        load(E03_RECORD),
        E03,
        dict(FROZEN_RECORDS),
        latest=True,
    )
    assert found(latest) == {
        ("e03-sources-stale", f"{E04_BINDING}.revision"),
        ("e03-sources-stale", "definition.sources[0].revision"),
    }
    assert "executedUnder" not in _extension(load(E03_RECORD))
    assert "changesFromSupersededRevision" not in load(E03_RECORD)["definition"]


def _bind_revision_2(document: dict[str, Any]) -> None:
    previous = load(SOURCE_RECORDS["V2-E04"])
    _binding(document).update(
        path=SOURCE_RECORDS["V2-E04"],
        revision=2,
        contentSha256=FROZEN_RECORDS[SOURCE_RECORDS["V2-E04"]],
        preregistrationRules=previous["metadata"]["preregistrationRules"],
    )


def _extend_text(
    *path: str, text: str = " A later sentence."
) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        target: Any = document["definition"]
        for step in path[:-1]:
            target = target[int(step)] if step.isdigit() else target[step]
        target[path[-1]] += text

    return change


EXTENSION_AT = "definition.population.extension"
CHANGES_AT = "definition.changesFromSupersededRevision"


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        pytest.param(
            _bind_revision_2,
            {
                ("e03-sources-stale", f"{E04_BINDING}.revision"),
                ("e03-extension-revision", f"{EXTENSION_AT}.executedUnder"),
                ("e03-revision-changes", CHANGES_AT),
            },
            id="it-binds-the-superseded-revision-2",
        ),
        pytest.param(
            lambda d: _binding(d).__setitem__("contentSha256", "0" * 64),
            {("e03-sources-stale", f"{E04_BINDING}.contentSha256")},
            id="a-wrong-digest",
        ),
        pytest.param(
            lambda d: _binding(d).__setitem__("preregistrationRules", 3),
            {("e03-binding-rule-set", f"{E04_BINDING}.preregistrationRules")},
            id="a-wrong-rule-set",
        ),
        pytest.param(
            lambda d: _binding(d).__setitem__("preregistrationRules", "4"),
            {("e03-binding-rule-set", f"{E04_BINDING}.preregistrationRules")},
            id="a-rule-set-that-is-text",
        ),
        pytest.param(
            lambda d: _binding(d).pop("preregistrationRules"),
            {("e03-binding-rule-set", f"{E04_BINDING}.preregistrationRules")},
            id="no-rule-set",
        ),
        pytest.param(
            lambda d: _extension(d).__setitem__(
                "executedUnder", {"path": SOURCE_RECORDS["V2-E04"], "revision": 2}
            ),
            {("e03-extension-revision", f"{EXTENSION_AT}.executedUnder")},
            id="the-extension-counts-the-runs-of-revision-2",
        ),
        pytest.param(
            lambda d: _extension(d).__setitem__(
                "runs",
                load(E03_RECORD)["definition"]["population"]["extension"]["runs"],
            ),
            {("e03-extension-revision", f"{EXTENSION_AT}.runs")},
            id="the-extension-counts-the-runs-of-the-latest-revision",
        ),
        pytest.param(
            _extend_text(
                "population",
                "extension",
                "runs",
                text=" Runs of any latest revision count.",
            ),
            {("e03-extension-revision", f"{EXTENSION_AT}.runs")},
            id="the-extension-admits-the-latest-revision-in-its-text",
        ),
        pytest.param(
            _extend_text("population", "excluded", "0", "reason"),
            {("e03-revision-changes", CHANGES_AT)},
            id="a-population-member-changed-and-not-listed",
        ),
        pytest.param(
            _extend_text("signals", "3", "healthy"),
            {("e03-revision-changes", CHANGES_AT)},
            id="a-signal-changed-and-not-listed",
        ),
        pytest.param(
            _extend_text("operationalCandidate", "statement"),
            {("e03-revision-changes", CHANGES_AT)},
            id="the-candidate-changed-and-not-listed",
        ),
        pytest.param(
            _extend_text("ranking", "mostCallerTruthful"),
            {("e03-revision-changes", CHANGES_AT)},
            id="the-ranking-changed-and-not-listed",
        ),
        pytest.param(
            _extend_text("callerFailures", "falseHealthy"),
            {("e03-revision-changes", CHANGES_AT)},
            id="the-caller-failure-rule-changed-and-not-listed",
        ),
        pytest.param(
            lambda d: d["definition"]["changesFromSupersededRevision"].append(
                {"member": "definition.ranking", "reason": "It does not differ."}
            ),
            {("e03-revision-changes", CHANGES_AT)},
            id="a-member-listed-that-does-not-differ",
        ),
        pytest.param(
            lambda d: d["definition"]["changesFromSupersededRevision"].append(
                {"member": "definition.sources", "reason": "Twice."}
            ),
            {("e03-revision-changes", CHANGES_AT)},
            id="a-member-listed-twice",
        ),
        pytest.param(
            lambda d: d["definition"]["changesFromSupersededRevision"][0].pop("reason"),
            {
                ("e03-revision-changes", f"{CHANGES_AT}[0]"),
                ("e03-revision-changes", CHANGES_AT),
            },
            id="a-change-without-its-reason",
        ),
        pytest.param(
            lambda d: d["definition"]["changesFromSupersededRevision"].pop(5),
            {("e03-revision-changes", CHANGES_AT)},
            id="the-metadata-changed-and-not-listed",
        ),
        pytest.param(
            lambda d: d["metadata"]["supersedes"].__setitem__(
                "contentSha256", "0" * 64
            ),
            {("e03-revision-changes", "metadata.supersedes")},
            id="it-supersedes-another-digest",
        ),
    ],
)
def test_each_defect_of_a_later_e03_revision_is_refused(
    full_root: Path,
    change: Callable[[dict[str, Any]], None],
    expected: set[tuple[str, str]],
) -> None:
    edit(full_root, E03_R2, change)
    findings = core.check_records(full_root, [E03])
    assert {f.record for f in findings} == {E03_R2}
    assert found(findings) == expected


def test_a_change_names_the_member_that_differs(full_root: Path) -> None:
    edit(full_root, E03_R2, _extend_text("signals", "3", "healthy"))
    (finding,) = core.check_records(full_root, [E03])
    assert (
        finding.detail == "definition.signals differs from revision 1 and is not listed"
    )


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda d: d["definition"].__setitem__("changesFromSupersededRevision", "x"),
            id="changes-text",
        ),
        pytest.param(
            lambda d: d["definition"].__setitem__(
                "changesFromSupersededRevision", [["x"], {"member": ["y"]}]
            ),
            id="changes-unhashable",
        ),
        pytest.param(
            lambda d: _extension(d).__setitem__("executedUnder", ["x"]),
            id="executed-under-a-list",
        ),
        pytest.param(
            lambda d: _binding(d).__setitem__("preregistrationRules", [4]),
            id="rule-set-a-list",
        ),
        pytest.param(
            lambda d: d["metadata"].__setitem__("supersedes", ["x"]),
            id="supersedes-a-list",
        ),
        pytest.param(
            lambda d: d["definition"]["population"].__setitem__("extension", "x"),
            id="extension-text",
        ),
    ],
)
def test_a_malformed_later_revision_is_a_finding_and_never_raises(
    full_root: Path, change: Callable[[dict[str, Any]], None]
) -> None:
    edit(full_root, E03_R2, change)
    findings = core.check_records(full_root, [E03])
    assert findings
    assert {f.record for f in findings} == {E03_R2}
