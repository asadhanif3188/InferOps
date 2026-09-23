"""The clean-clone checklist and the rules of its ledger, in process.

`tools.clean_clone` decides what a clean-clone run may record. Each rule here is
a way a record could read as more than it is, and each is driven over an input
built to break it: a real step recorded as not run in a certification run, a step
passed before the one it stands on, an interval ending before it starts, a ledger
continued on another revision or after its own cleanup, a manual action carrying
a host path, and a checklist that disagrees with itself. The control cases --
inputs every rule accepts -- come first, so that no refusal below is vacuous.

The checklist itself is held to the repository: every workflow a step names
exists, and the step order is the one the workflow runs, which
`test_clean_clone_workflow.py` checks from the script's side.

Nothing here runs a shell, contacts a cluster, or reads anything but committed
files and a throwaway git repository.
"""

from __future__ import annotations

import copy
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tools.clean_clone import (
    CleanCloneError,
    assert_same_run,
    begin,
    checkout_problems,
    cleanup_problem,
    descriptor_problems,
    load_descriptor,
    note,
    pending_steps,
    record,
    steps,
    summarise,
)
from tools.clean_clone.__main__ import _workflow_problems
from tools.clean_clone.core import (
    check_authorizations,
    forward_authorizations,
    merge_values,
)

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR = load_descriptor()
STEP_IDS = [step.step_id for step in steps(DESCRIPTOR)]
FORWARD = [step.step_id for step in steps(DESCRIPTOR) if not step.after_failure]
REAL = [step.step_id for step in steps(DESCRIPTOR) if step.kind == "real"]
REVISION = "1" * 40
T0 = 1_760_000_000_000


def certification_ledger(provider: str = "docker-desktop") -> dict[str, Any]:
    return begin(
        DESCRIPTOR,
        mode="certification",
        provider=provider,
        cluster_name="inferops-dev" if provider == "kind" else None,
        revision=REVISION,
        authorizations=forward_authorizations(DESCRIPTOR),
        started_epoch_ms=T0,
    )


def preparation_ledger() -> dict[str, Any]:
    return begin(
        DESCRIPTOR,
        mode="preparation",
        provider=None,
        cluster_name=None,
        revision=REVISION,
        authorizations=[],
        started_epoch_ms=T0,
    )


def passed(ledger: dict[str, Any], step_id: str, at: int = 0) -> dict[str, Any]:
    return record(
        ledger,
        DESCRIPTOR,
        step_id=step_id,
        outcome="passed",
        exit_code=0,
        started_epoch_ms=T0 + at,
        finished_epoch_ms=T0 + at + 10,
    )


def all_passed(ledger: dict[str, Any], ids: list[str] = STEP_IDS) -> dict[str, Any]:
    for position, step_id in enumerate(ids):
        ledger = passed(ledger, step_id, at=position * 100)
    return ledger


# --------------------------------------------------------------------------
# The checklist
# --------------------------------------------------------------------------


def test_the_checklist_agrees_with_itself() -> None:
    assert descriptor_problems(DESCRIPTOR) == []


def test_every_workflow_the_checklist_names_exists() -> None:
    assert _workflow_problems(DESCRIPTOR) == []


def test_the_checklist_covers_every_part_of_the_journey_the_story_names() -> None:
    """The parent story's first acceptance criterion, as step identifiers."""
    for step_id in (
        "default-lane-checks",
        "model-acquisition",
        "local-real-inference",
        "workload-scaffold",
        "provider-verification",
        "terraform-prerequisites",
        "helm-deployment",
        "kubernetes-inference",
        "telemetry-verification",
        "load",
        "failure",
        "cleanup",
        "cluster-survived",
    ):
        assert step_id in STEP_IDS, step_id


def test_docker_desktop_is_the_certified_provider_and_kind_is_supported() -> None:
    assert DESCRIPTOR["certifiedProvider"] == "docker-desktop"
    assert set(DESCRIPTOR["supportedProviders"]) == {"kind", "docker-desktop"}


def test_every_evidence_label_the_checklist_uses_is_one_the_claim_register_defines() -> (
    None
):
    import json

    register = json.loads(
        (REPO_ROOT / "docs/testing/claim-evidence-matrix.v1alpha2.json").read_text(
            encoding="utf-8"
        )
    )
    defined = {row["classId"] for row in register["evidenceClasses"]}
    assert set(DESCRIPTOR["evidenceLabels"]) <= defined


def test_every_step_that_contacts_a_cluster_or_a_runtime_needs_consent() -> None:
    for step in steps(DESCRIPTOR):
        if (
            step.evidence_label == "local-real-cpu"
            and step.step_id != "cluster-survived"
        ):
            assert step.requires_authorization, step.step_id


@pytest.mark.parametrize(
    ("corrupt", "expected"),
    [
        (lambda d: d["steps"].append(copy.deepcopy(d["steps"][0])), "declared twice"),
        (lambda d: d["steps"][0].update(kind="optional"), "is not one of"),
        (
            lambda d: d["steps"][0].update(evidenceLabel="production-experience"),
            "is not declared",
        ),
        (
            lambda d: d["steps"][5].update(requiresAuthorization=["telepathy"]),
            "is not declared",
        ),
        (
            lambda d: d["steps"][5].update(requiresAuthorization=[]),
            "must name its authorization",
        ),
        (
            lambda d: d["steps"][2].update(requiresAuthorization=["real-runtime"]),
            "a step that does is real",
        ),
        (lambda d: d["steps"][0].update(resumable=True), "never resumable"),
        (lambda d: d["steps"][-2].update(resumable=True), "never skipped"),
        (
            lambda d: d["steps"][-2].update(runsAfterFailure=False),
            "reachable after a failure",
        ),
        (lambda d: d["steps"][5].update(runsAfterFailure=True), "only cleanup"),
        (
            lambda d: d["steps"].insert(3, d["steps"].pop(-1)),
            "must come after every step",
        ),
        (
            lambda d: d["authorizations"].append(copy.deepcopy(d["authorizations"][0])),
            "declared twice",
        ),
        (lambda d: d.update(contractVersion="v2"), "contractVersion"),
    ],
)
def test_a_checklist_that_breaks_a_rule_is_refused(corrupt: Any, expected: str) -> None:
    broken = copy.deepcopy(DESCRIPTOR)
    corrupt(broken)
    problems = descriptor_problems(broken)
    assert any(expected in problem for problem in problems), problems


def test_a_step_naming_a_workflow_that_does_not_exist_is_found() -> None:
    broken = copy.deepcopy(DESCRIPTOR)
    broken["steps"][11]["runs"] = [
        "scripts/environment/no-such-workflow.sh",
        "tools.no_such_tool",
    ]
    problems = _workflow_problems(broken)
    assert len(problems) == 2, problems


# --------------------------------------------------------------------------
# Beginning a run
# --------------------------------------------------------------------------


def test_a_certification_run_begins_with_a_provider_and_every_consent() -> None:
    ledger = certification_ledger()
    assert ledger["mode"] == "certification"
    assert ledger["attempts"] == []
    assert "cleanup" not in forward_authorizations(DESCRIPTOR)


@pytest.mark.parametrize(
    "withheld", ["artifact-download", "real-runtime", "real-kubernetes"]
)
def test_a_certification_run_without_every_forward_consent_is_refused(
    withheld: str,
) -> None:
    given = [a for a in forward_authorizations(DESCRIPTOR) if a != withheld]
    with pytest.raises(CleanCloneError, match=withheld):
        begin(
            DESCRIPTOR,
            mode="certification",
            provider="docker-desktop",
            cluster_name=None,
            revision=REVISION,
            authorizations=given,
            started_epoch_ms=T0,
        )


@pytest.mark.parametrize(
    ("provider", "cluster", "match"),
    [
        (None, None, "explicit provider"),
        ("minikube", None, "is not one of"),
        ("kind", None, "cluster name"),
        ("docker-desktop", "desktop", "takes no cluster name"),
    ],
)
def test_a_run_with_an_unusable_selection_is_refused(
    provider: str | None, cluster: str | None, match: str
) -> None:
    with pytest.raises(CleanCloneError, match=match):
        begin(
            DESCRIPTOR,
            mode="certification",
            provider=provider,
            cluster_name=cluster,
            revision=REVISION,
            authorizations=forward_authorizations(DESCRIPTOR),
            started_epoch_ms=T0,
        )


def test_an_unknown_consent_is_refused() -> None:
    with pytest.raises(CleanCloneError, match="unknown authorization"):
        check_authorizations(
            DESCRIPTOR, mode="preparation", authorizations=["everything"]
        )


def test_a_preparation_run_needs_no_consent_and_no_provider() -> None:
    assert preparation_ledger()["provider"] is None


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------


def test_a_complete_certification_run_on_docker_desktop_certifies() -> None:
    view = summarise(all_passed(certification_ledger()), DESCRIPTOR)
    assert view["status"] == "complete"
    assert view["certifiesProvider"] is True
    assert view["wallClockMs"] >= 0


def test_a_complete_run_on_kind_is_complete_and_certifies_nothing() -> None:
    view = summarise(all_passed(certification_ledger("kind")), DESCRIPTOR)
    assert view["status"] == "complete"
    assert view["certifiesProvider"] is False


def test_a_run_missing_its_cleanup_is_incomplete() -> None:
    view = summarise(all_passed(certification_ledger(), FORWARD), DESCRIPTOR)
    assert view["status"] == "incomplete"
    assert view["certifiesProvider"] is False


@pytest.mark.parametrize("step_id", REAL)
def test_a_certification_run_may_not_record_a_real_step_as_not_run(
    step_id: str,
) -> None:
    ledger = certification_ledger()
    with pytest.raises(CleanCloneError, match="may not record a step as not run"):
        record(
            ledger,
            DESCRIPTOR,
            step_id=step_id,
            outcome="not-run",
            exit_code=0,
            started_epoch_ms=T0,
            finished_epoch_ms=T0,
            reason="skipped",
        )


@pytest.mark.parametrize(
    "step_id", ["clean-checkout", "toolchain-sync", "default-lane-checks", "cleanup"]
)
def test_a_preparation_run_may_not_record_a_step_needing_no_consent_as_not_run(
    step_id: str,
) -> None:
    with pytest.raises(CleanCloneError, match="only a step that needs authorization"):
        record(
            preparation_ledger(),
            DESCRIPTOR,
            step_id=step_id,
            outcome="not-run",
            exit_code=0,
            started_epoch_ms=T0,
            finished_epoch_ms=T0,
            reason="skipped",
        )


def test_a_step_recorded_as_not_run_must_say_why() -> None:
    ledger = all_passed(preparation_ledger(), STEP_IDS[:5])
    with pytest.raises(CleanCloneError, match="must say why"):
        record(
            ledger,
            DESCRIPTOR,
            step_id="model-acquisition",
            outcome="not-run",
            exit_code=0,
            started_epoch_ms=T0,
            finished_epoch_ms=T0,
        )


def test_a_preparation_ledger_never_summarises_as_complete() -> None:
    ledger = all_passed(preparation_ledger(), STEP_IDS[:5])
    for step_id in STEP_IDS[5:]:
        step = next(s for s in steps(DESCRIPTOR) if s.step_id == step_id)
        if step.kind == "real":
            ledger = record(
                ledger,
                DESCRIPTOR,
                step_id=step_id,
                outcome="not-run",
                exit_code=0,
                started_epoch_ms=T0,
                finished_epoch_ms=T0,
                reason="preparation run",
            )
        else:
            ledger = passed(ledger, step_id)
    view = summarise(ledger, DESCRIPTOR)
    assert view["status"] == "preparation-only"
    assert view["certifiesProvider"] is False


def test_a_step_may_not_pass_before_the_step_it_stands_on() -> None:
    with pytest.raises(CleanCloneError, match="comes first"):
        passed(certification_ledger(), "helm-deployment")


def test_cleanup_may_be_recorded_after_a_failure() -> None:
    ledger = passed(certification_ledger(), "clean-checkout")
    ledger = record(
        ledger,
        DESCRIPTOR,
        step_id="host-prerequisites",
        outcome="refused",
        exit_code=3,
        started_epoch_ms=T0,
        finished_epoch_ms=T0 + 5,
    )
    ledger = passed(ledger, "cleanup")
    ledger = passed(ledger, "cluster-survived")
    assert summarise(ledger, DESCRIPTOR)["status"] == "failed"


def test_a_negative_interval_is_refused() -> None:
    with pytest.raises(CleanCloneError, match="negative interval"):
        record(
            certification_ledger(),
            DESCRIPTOR,
            step_id="clean-checkout",
            outcome="passed",
            exit_code=0,
            started_epoch_ms=T0 + 1,
            finished_epoch_ms=T0,
        )


@pytest.mark.parametrize(
    ("outcome", "exit_code"),
    [("passed", 1), ("failed", 0), ("refused", 0), ("finished", 0)],
)
def test_an_outcome_that_contradicts_its_exit_code_is_refused(
    outcome: str, exit_code: int
) -> None:
    with pytest.raises(CleanCloneError):
        record(
            certification_ledger(),
            DESCRIPTOR,
            step_id="clean-checkout",
            outcome=outcome,
            exit_code=exit_code,
            started_epoch_ms=T0,
            finished_epoch_ms=T0,
        )


def test_an_unknown_step_is_refused() -> None:
    with pytest.raises(CleanCloneError, match="unknown step"):
        passed(certification_ledger(), "deploy-to-production")


def test_a_failed_step_makes_the_run_failed_until_it_passes() -> None:
    ledger = all_passed(certification_ledger(), FORWARD[:3])
    ledger = record(
        ledger,
        DESCRIPTOR,
        step_id=FORWARD[3],
        outcome="failed",
        exit_code=1,
        started_epoch_ms=T0,
        finished_epoch_ms=T0 + 1,
    )
    assert summarise(ledger, DESCRIPTOR)["status"] == "failed"
    ledger = passed(ledger, FORWARD[3], at=10)
    view = summarise(ledger, DESCRIPTOR)
    assert view["status"] == "incomplete"
    assert next(r for r in view["steps"] if r["stepId"] == FORWARD[3])["attempts"] == 2


# --------------------------------------------------------------------------
# Resuming
# --------------------------------------------------------------------------


def test_resumption_skips_passed_resumable_steps_and_asks_every_check_again() -> None:
    ledger = all_passed(certification_ledger(), FORWARD[:9])
    pending = pending_steps(ledger, DESCRIPTOR)
    by_id = {s.step_id: s for s in steps(DESCRIPTOR)}
    for step_id in FORWARD[:9]:
        assert (step_id in pending) == (not by_id[step_id].resumable), step_id
    assert pending[-1] == FORWARD[-1]
    assert "cleanup" not in pending


def test_a_step_recorded_as_not_run_is_pending_again() -> None:
    ledger = all_passed(preparation_ledger(), STEP_IDS[:5])
    ledger = record(
        ledger,
        DESCRIPTOR,
        step_id="model-acquisition",
        outcome="not-run",
        exit_code=0,
        started_epoch_ms=T0,
        finished_epoch_ms=T0,
        reason="preparation run",
    )
    assert "model-acquisition" in pending_steps(ledger, DESCRIPTOR)


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"revision": "2" * 40}, "two revisions"),
        ({"provider": "kind"}, "began on provider"),
        ({"mode": "preparation"}, "never becomes a certification"),
    ],
)
def test_a_ledger_is_never_continued_as_a_different_run(
    change: dict[str, str], match: str
) -> None:
    arguments = {
        "mode": "certification",
        "revision": REVISION,
        "provider": "docker-desktop",
    }
    arguments.update(change)
    with pytest.raises(CleanCloneError, match=match):
        assert_same_run(certification_ledger(), cluster_name=None, **arguments)


def test_a_kind_ledger_is_never_continued_on_another_kind_cluster() -> None:
    with pytest.raises(CleanCloneError, match="kind cluster"):
        assert_same_run(
            certification_ledger("kind"),
            mode="certification",
            revision=REVISION,
            provider="kind",
            cluster_name="someone-else",
        )


def test_a_ledger_that_has_been_cleaned_up_is_never_continued() -> None:
    ledger = passed(certification_ledger(), "cleanup")
    with pytest.raises(CleanCloneError, match="already been cleaned up"):
        assert_same_run(
            ledger,
            mode="certification",
            revision=REVISION,
            provider="docker-desktop",
            cluster_name=None,
        )


# --------------------------------------------------------------------------
# Manual actions
# --------------------------------------------------------------------------


def test_a_manual_action_is_recorded_with_its_time_and_step() -> None:
    ledger = note(
        certification_ledger(),
        DESCRIPTOR,
        description="Started the container engine",
        at_epoch_ms=T0,
        step_id="host-prerequisites",
    )
    assert ledger["manualActions"] == [
        {
            "at": "2025-10-09T08:53:20.000Z",
            "stepId": "host-prerequisites",
            "description": "Started the container engine",
        }
    ]
    assert summarise(ledger, DESCRIPTOR)["manualActions"] == 1


@pytest.mark.parametrize(
    "text",
    [
        "Copied the cache from C:\\Users\\someone\\models",
        "Wrote d:/scratch/kubectl",
        "Edited /home/x",
        "Opened /Users/x",
        "Mounted \\\\fileserver\\share\\models",
        "Two\nlines",
        "",
        "x" * 301,
    ],
)
def test_a_manual_action_that_would_make_the_ledger_unpublishable_is_refused(
    text: str,
) -> None:
    with pytest.raises(CleanCloneError):
        note(certification_ledger(), DESCRIPTOR, description=text, at_epoch_ms=T0)


@pytest.mark.parametrize(
    "text",
    [
        "Placed kubectl v1.34.3 first on PATH; the host's own was two minors ahead",
        "Started Docker Desktop and waited for its Kubernetes to report Ready",
        "Set INFEROPS_DISK_VOLUME=/d because the engine's disk is not on the system volume",
    ],
)
def test_a_manual_action_described_without_a_host_path_is_accepted(text: str) -> None:
    ledger = note(certification_ledger(), DESCRIPTOR, description=text, at_epoch_ms=T0)
    assert ledger["manualActions"][0]["description"] == text


def test_a_manual_action_naming_an_unknown_step_is_refused() -> None:
    with pytest.raises(CleanCloneError, match="unknown step"):
        note(
            certification_ledger(),
            DESCRIPTOR,
            description="x",
            at_epoch_ms=T0,
            step_id="nope",
        )


# --------------------------------------------------------------------------
# Values, and the checkout
# --------------------------------------------------------------------------


def test_values_are_layered_the_way_helm_layers_them() -> None:
    merged = merge_values(
        [
            {
                "api": {
                    "image": {"repository": "r", "digest": "old"},
                    "replicaCount": 1,
                },
                "list": [1, 2],
            },
            {"api": {"image": {"digest": "new", "pullPolicy": "Never"}}, "list": [3]},
            {"model": {"acquisition": {"source": "seed-image"}}},
        ]
    )
    assert merged == {
        "api": {
            "image": {"repository": "r", "digest": "new", "pullPolicy": "Never"},
            "replicaCount": 1,
        },
        "list": [3],
        "model": {"acquisition": {"source": "seed-image"}},
    }


def test_a_values_file_that_is_not_a_mapping_is_refused() -> None:
    with pytest.raises(CleanCloneError, match="mapping"):
        merge_values([{"a": 1}, ["not", "a", "mapping"]])  # type: ignore[list-item]


GIT = shutil.which("git")


@pytest.mark.skipif(
    GIT is None, reason="git is not installed; the checkout tests skip, loudly"
)
def test_the_checkout_check_separates_uncommitted_changes_from_previous_run_state(
    tmp_path: Path,
) -> None:
    assert GIT is not None
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".artifacts/\n.kube/\n", encoding="utf-8")
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    for command in (
        ["init", "-q"],
        ["add", "-A"],
        [*identity, "commit", "-q", "-m", "t"],
    ):
        subprocess.run([GIT, *command], cwd=tmp_path, check=True, capture_output=True)

    assert checkout_problems(tmp_path, fresh=True) == []

    (tmp_path / ".kube").mkdir()
    assert checkout_problems(tmp_path, fresh=False) == []
    assert checkout_problems(tmp_path, fresh=True) == [
        "previous-run state: .kube exists"
    ]

    (tmp_path / "README.md").write_text("changed\n", encoding="utf-8")
    (tmp_path / "untracked.txt").write_text("new\n", encoding="utf-8")
    problems = checkout_problems(tmp_path, fresh=False)
    assert len(problems) == 2 and all(
        p.startswith("uncommitted: ") for p in problems
    ), problems


def test_the_runtime_image_a_step_pulls_is_the_pinned_one() -> None:
    from tools.runtime_packaging import load_runtime_package

    reference = load_runtime_package().image_reference
    assert "@sha256:" in reference


# --------------------------------------------------------------------------
# The steps after a failure keep their own order
# --------------------------------------------------------------------------
#
# Cleanup skips the forward path's ordering so that it can follow a failed step.
# The first draft let that exemption reach further than it should: an independent
# review found that nothing refused a second cleanup after one that passed, or a
# survival check recorded with no cleanup in front of it.


def _failed_cleanup(ledger: dict[str, Any]) -> dict[str, Any]:
    return record(
        ledger,
        DESCRIPTOR,
        step_id="cleanup",
        outcome="failed",
        exit_code=1,
        started_epoch_ms=T0,
        finished_epoch_ms=T0 + 1,
    )


def test_a_cleanup_after_one_that_passed_is_refused() -> None:
    ledger = passed(certification_ledger(), "cleanup")
    assert cleanup_problem(ledger) is not None
    with pytest.raises(CleanCloneError, match="already cleaned up"):
        passed(ledger, "cleanup", at=10)


def test_a_cleanup_after_one_that_failed_may_be_retried() -> None:
    ledger = _failed_cleanup(certification_ledger())
    assert cleanup_problem(ledger) is None
    ledger = passed(ledger, "cleanup", at=10)
    assert [a["outcome"] for a in ledger["attempts"]] == ["failed", "passed"]


def test_a_survival_check_with_no_cleanup_in_front_of_it_is_refused() -> None:
    with pytest.raises(CleanCloneError, match="directly after 'cleanup'"):
        passed(certification_ledger(), "cluster-survived")
    forward = all_passed(certification_ledger(), FORWARD[:3])
    with pytest.raises(CleanCloneError, match="directly after 'cleanup'"):
        passed(forward, "cluster-survived", at=500)


def test_a_survival_check_is_recorded_once_per_cleanup() -> None:
    ledger = passed(
        passed(certification_ledger(), "cleanup"), "cluster-survived", at=10
    )
    with pytest.raises(CleanCloneError, match="directly after 'cleanup'"):
        passed(ledger, "cluster-survived", at=20)


def test_a_survival_check_may_follow_a_cleanup_that_failed() -> None:
    """A failed cleanup is exactly when whether the cluster survived matters most."""
    ledger = passed(_failed_cleanup(certification_ledger()), "cluster-survived", at=10)
    assert summarise(ledger, DESCRIPTOR)["status"] == "failed"
