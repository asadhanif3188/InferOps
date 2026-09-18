"""The clean-clone checklist, and the ledger one run of it keeps.

The checklist is data: ``docs/environment/clean-clone.v1alpha1.json`` names every
step from host prerequisites to scoped cleanup, in order, with the workflow each
one runs, the authorization it needs, the evidence label its result may carry, and
whether a later invocation may treat a pass as still standing. The shell workflow
``scripts/environment/clean-clone.sh`` runs the steps; this module decides what
may be recorded about them.

Everything the rules below refuse is a way a clean-clone record could read as more
than it is:

* a real step quietly skipped. A certification run may not record ``not-run`` at
  all; only a preparation run may, only for a step that needs authorization, and
  only with a reason. A preparation ledger can never summarise as ``complete``;
* a step recorded out of order, so that a later pass stands on an earlier step
  that never passed;
* an interval that ends before it starts -- the defect ``V1-S4-006-PR1`` published
  twice before a check existed for it;
* a ledger resumed on a different revision, provider, or cluster than it began on,
  which would stitch two runs into one record;
* a manual action written with a host path in it, which would make the ledger
  unpublishable without an edit nobody could check.

Nothing here contacts a cluster, a runtime, a network, or a model. ``git`` is read
to learn the checkout's revision and whether it is clean; nothing else is run.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DESCRIPTOR_PATH: Final = (
    REPO_ROOT / "docs" / "environment" / "clean-clone.v1alpha1.json"
)
LEDGER_PATH: Final = REPO_ROOT / ".artifacts" / "clean-clone" / "ledger.v1alpha1.json"

CONTRACT_VERSION: Final = "v1alpha1"
LEDGER_KIND: Final = "clean-clone-ledger"

MODE_CERTIFICATION: Final = "certification"
MODE_PREPARATION: Final = "preparation"
MODES: Final = (MODE_CERTIFICATION, MODE_PREPARATION)

KIND_CHECK: Final = "check"
KIND_PREPARATION: Final = "preparation"
KIND_REAL: Final = "real"
KIND_CLEANUP: Final = "cleanup"
STEP_KINDS: Final = (KIND_CHECK, KIND_PREPARATION, KIND_REAL, KIND_CLEANUP)

OUTCOME_PASSED: Final = "passed"
OUTCOME_FAILED: Final = "failed"
OUTCOME_REFUSED: Final = "refused"
OUTCOME_NOT_RUN: Final = "not-run"
OUTCOMES: Final = (OUTCOME_PASSED, OUTCOME_FAILED, OUTCOME_REFUSED, OUTCOME_NOT_RUN)

SUMMARY_COMPLETE: Final = "complete"
SUMMARY_INCOMPLETE: Final = "incomplete"
SUMMARY_FAILED: Final = "failed"
SUMMARY_PREPARATION_ONLY: Final = "preparation-only"

MANUAL_ACTION_MAX_LENGTH: Final = 300

# A manual action is prose an operator types, and prose is where a host path gets
# in. These are the shapes the security baseline already refuses in committed
# evidence; refusing them here keeps the ledger publishable without an edit.
HOST_PATH_SHAPES: Final = (
    re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]"),
    re.compile(r"(?:^|[\s\"'=(])/(?:home|Users|root)/", re.IGNORECASE),
    re.compile(r"\\\\[A-Za-z0-9._-]+\\"),
)

# The project state a previous run leaves in a checkout. A clean clone has none of
# it, and a run that started beside any of it could not show that none of it was
# needed. Interpreter and tool caches are deliberately absent: the checks below
# create them, and none of them is configuration a workflow reads.
PROJECT_STATE_PATHS: Final = (
    ".artifacts",
    ".kube",
    ".cache/inferops",
    ".quickstart",
    "infra/terraform/environments/local/.terraform",
    "infra/terraform/environments/local/terraform.tfstate",
    "infra/terraform/environments/local/terraform.tfstate.backup",
)


class CleanCloneError(Exception):
    """A refusal: something the checklist's rules do not allow was asked for."""


@dataclass(frozen=True)
class Step:
    step_id: str
    title: str
    kind: str
    requires_authorization: tuple[str, ...]
    resumable: bool
    evidence_label: str
    after_failure: bool


# --------------------------------------------------------------------------
# The checklist
# --------------------------------------------------------------------------


def load_descriptor(path: Path = DESCRIPTOR_PATH) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def steps(descriptor: dict[str, Any]) -> list[Step]:
    return [
        Step(
            step_id=entry["stepId"],
            title=entry["title"],
            kind=entry["kind"],
            requires_authorization=tuple(entry["requiresAuthorization"]),
            resumable=bool(entry["resumable"]),
            evidence_label=entry["evidenceLabel"],
            after_failure=bool(entry["runsAfterFailure"]),
        )
        for entry in descriptor["steps"]
    ]


def step_by_id(descriptor: dict[str, Any], step_id: str) -> Step:
    for step in steps(descriptor):
        if step.step_id == step_id:
            return step
    raise CleanCloneError(f"unknown step '{step_id}'; the checklist does not name it")


def authorization_ids(descriptor: dict[str, Any]) -> list[str]:
    return [entry["authorizationId"] for entry in descriptor["authorizations"]]


def descriptor_problems(descriptor: dict[str, Any]) -> list[str]:
    """Every way the checklist disagrees with itself. Empty when it does not."""
    problems: list[str] = []
    if descriptor.get("contractVersion") != CONTRACT_VERSION:
        problems.append(f"contractVersion is not '{CONTRACT_VERSION}'")

    known_auth = authorization_ids(descriptor)
    if len(known_auth) != len(set(known_auth)):
        problems.append("an authorization is declared twice")
    labels = set(descriptor["evidenceLabels"])

    seen: set[str] = set()
    ordered = steps(descriptor)
    if not ordered:
        problems.append("the checklist has no steps")
    for position, step in enumerate(ordered):
        if step.step_id in seen:
            problems.append(f"{step.step_id}: declared twice")
        seen.add(step.step_id)
        if step.kind not in STEP_KINDS:
            problems.append(
                f"{step.step_id}: kind '{step.kind}' is not one of {STEP_KINDS}"
            )
        if step.evidence_label not in labels:
            problems.append(
                f"{step.step_id}: evidence label '{step.evidence_label}' is not declared"
            )
        for auth in step.requires_authorization:
            if auth not in known_auth:
                problems.append(
                    f"{step.step_id}: authorization '{auth}' is not declared"
                )
        needs_auth = bool(step.requires_authorization)
        if step.kind in (KIND_REAL, KIND_CLEANUP) and not needs_auth:
            problems.append(
                f"{step.step_id}: a {step.kind} step must name its authorization"
            )
        if step.kind in (KIND_CHECK, KIND_PREPARATION) and needs_auth:
            problems.append(
                f"{step.step_id}: a {step.kind} step needs no authorization; "
                "a step that does is real"
            )
        if step.kind == KIND_CHECK and step.resumable:
            problems.append(
                f"{step.step_id}: a check is asked again on every invocation and is never resumable"
            )
        if step.kind == KIND_CLEANUP and step.resumable:
            problems.append(
                f"{step.step_id}: cleanup is never skipped because it passed once"
            )
        if step.after_failure and step.kind not in (KIND_CLEANUP, KIND_CHECK):
            problems.append(
                f"{step.step_id}: only cleanup, and the checks that follow it, may run after a failure"
            )
        if step.kind == KIND_CLEANUP and not step.after_failure:
            problems.append(
                f"{step.step_id}: cleanup must be reachable after a failure"
            )
        if step.after_failure and any(
            not later.after_failure for later in ordered[position + 1 :]
        ):
            problems.append(
                f"{step.step_id}: a step that runs after a failure must come after every step that does not"
            )
    return problems


# --------------------------------------------------------------------------
# The checkout
# --------------------------------------------------------------------------


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CleanCloneError(
            f"git {' '.join(arguments)} failed; this command needs a git checkout"
        )
    return result.stdout


def repository_revision(root: Path = REPO_ROOT) -> str:
    return _git(root, "rev-parse", "HEAD").strip()


def uncommitted_changes(root: Path = REPO_ROOT) -> list[str]:
    """Tracked changes and untracked files that are not ignored, one per line."""
    return [
        line for line in _git(root, "status", "--porcelain=v1").splitlines() if line
    ]


def project_state_present(root: Path = REPO_ROOT) -> list[str]:
    """The previous-run state from PROJECT_STATE_PATHS that exists in this checkout."""
    return [rel for rel in PROJECT_STATE_PATHS if (root / rel).exists()]


def checkout_problems(root: Path = REPO_ROOT, *, fresh: bool) -> list[str]:
    """Why this checkout cannot stand for a clean clone. Empty when it can.

    A fresh run refuses previous-run state as well as uncommitted changes; a resumed
    run refuses only uncommitted changes, because the state it finds is its own.
    """
    problems = [f"uncommitted: {line}" for line in uncommitted_changes(root)]
    if fresh:
        problems.extend(
            f"previous-run state: {rel} exists" for rel in project_state_present(root)
        )
    return problems


# --------------------------------------------------------------------------
# The ledger
# --------------------------------------------------------------------------


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _epoch_ms_to_iso(epoch_ms: int) -> str:
    return _iso(datetime.fromtimestamp(epoch_ms / 1000, tz=UTC))


def forward_authorizations(descriptor: dict[str, Any]) -> list[str]:
    """The authorizations the forward path needs; cleanup's is asked for separately."""
    needed: list[str] = []
    for step in steps(descriptor):
        if step.after_failure:
            continue
        for auth in step.requires_authorization:
            if auth not in needed:
                needed.append(auth)
    return needed


def check_authorizations(
    descriptor: dict[str, Any], *, mode: str, authorizations: list[str]
) -> None:
    """Refuse an invocation whose consent does not fit its mode.

    Consent is given on every invocation and never read back out of a ledger: a
    ledger records what was granted when it began, and a later invocation that
    resumes it must grant it again. A certification run needs every forward-path
    authorization; a preparation run may hold any of them, and records every real
    step it was not authorized to run as not run.
    """
    if mode not in MODES:
        raise CleanCloneError(f"mode '{mode}' is not one of {MODES}")
    known = authorization_ids(descriptor)
    unknown = sorted(set(authorizations) - set(known))
    if unknown:
        raise CleanCloneError(
            f"unknown authorization(s) {unknown}; the checklist declares {known}"
        )
    if mode == MODE_CERTIFICATION:
        missing = [
            auth
            for auth in forward_authorizations(descriptor)
            if auth not in authorizations
        ]
        if missing:
            raise CleanCloneError(
                f"a certification run needs every authorization on every invocation, and "
                f"{missing} were not given. Grant them, or run a preparation run, which "
                "records each real step it may not run as not run and can never "
                "summarise as complete"
            )


def begin(
    descriptor: dict[str, Any],
    *,
    mode: str,
    provider: str | None,
    cluster_name: str | None,
    revision: str,
    authorizations: list[str],
    started_epoch_ms: int,
) -> dict[str, Any]:
    """A new ledger, or a refusal naming why a run may not start this way."""
    check_authorizations(descriptor, mode=mode, authorizations=authorizations)
    supported = descriptor["supportedProviders"]
    if provider is not None and provider not in supported:
        raise CleanCloneError(f"provider '{provider}' is not one of {supported}")
    if mode == MODE_CERTIFICATION and provider is None:
        raise CleanCloneError(
            "a certification run needs an explicit provider; there is no default"
        )
    if provider == "kind" and not cluster_name:
        raise CleanCloneError("the kind provider needs an explicit cluster name")
    if provider == "docker-desktop" and cluster_name not in (None, "docker-desktop"):
        raise CleanCloneError("the docker-desktop provider takes no cluster name")
    return {
        "contractVersion": CONTRACT_VERSION,
        "kind": LEDGER_KIND,
        "checklistRef": "docs/environment/clean-clone.v1alpha1.json",
        "mode": mode,
        "provider": provider,
        "clusterName": cluster_name if provider == "kind" else provider,
        "certifiedProvider": descriptor["certifiedProvider"],
        "repositoryRevision": revision,
        "startedAt": _epoch_ms_to_iso(started_epoch_ms),
        "authorizations": sorted(authorizations),
        "attempts": [],
        "manualActions": [],
    }


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise CleanCloneError(f"no ledger at {path.as_posix()}; begin a run first")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if (
        data.get("kind") != LEDGER_KIND
        or data.get("contractVersion") != CONTRACT_VERSION
    ):
        raise CleanCloneError(
            f"{path.as_posix()} is not a {CONTRACT_VERSION} clean-clone ledger"
        )
    return data


def write_ledger(ledger: dict[str, Any], path: Path = LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(ledger, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(path)


def assert_same_run(
    ledger: dict[str, Any],
    *,
    mode: str,
    revision: str,
    provider: str | None,
    cluster_name: str | None,
) -> None:
    """Refuse to continue a ledger on anything but the run that began it."""
    if ledger["mode"] != mode:
        raise CleanCloneError(
            f"the ledger began as a {ledger['mode']} run and this invocation is a {mode} "
            "run; a preparation record never becomes a certification one. Start a new run"
        )
    if any(attempt["stepId"] == "cleanup" for attempt in ledger["attempts"]):
        raise CleanCloneError(
            "this run has already been cleaned up; its prerequisites and release are "
            "gone while its ledger still records them as passed. Begin a new run"
        )
    if ledger["repositoryRevision"] != revision:
        raise CleanCloneError(
            f"the ledger began at revision {ledger['repositoryRevision']} and the checkout "
            f"is at {revision}; one record cannot span two revisions. Start a new run"
        )
    if provider is not None and ledger["provider"] not in (None, provider):
        raise CleanCloneError(
            f"the ledger began on provider '{ledger['provider']}', not '{provider}'"
        )
    if ledger["provider"] == "kind" and cluster_name not in (
        None,
        ledger["clusterName"],
    ):
        raise CleanCloneError(
            f"the ledger began on kind cluster '{ledger['clusterName']}', not '{cluster_name}'"
        )


def latest_outcomes(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The most recent attempt at each step, by step identifier."""
    latest: dict[str, dict[str, Any]] = {}
    for attempt in ledger["attempts"]:
        latest[attempt["stepId"]] = attempt
    return latest


def _stands(ledger: dict[str, Any], attempt: dict[str, Any] | None) -> bool:
    """Whether a step's latest attempt lets the steps after it proceed."""
    if attempt is None:
        return False
    if attempt["outcome"] == OUTCOME_PASSED:
        return True
    return bool(
        ledger["mode"] == MODE_PREPARATION and attempt["outcome"] == OUTCOME_NOT_RUN
    )


def record(
    ledger: dict[str, Any],
    descriptor: dict[str, Any],
    *,
    step_id: str,
    outcome: str,
    exit_code: int,
    started_epoch_ms: int,
    finished_epoch_ms: int,
    reason: str | None = None,
) -> dict[str, Any]:
    """The ledger with one more attempt appended, or a refusal saying why not."""
    step = step_by_id(descriptor, step_id)
    if outcome not in OUTCOMES:
        raise CleanCloneError(f"outcome '{outcome}' is not one of {OUTCOMES}")
    if finished_epoch_ms < started_epoch_ms:
        raise CleanCloneError(
            f"{step_id}: finished {finished_epoch_ms - started_epoch_ms} ms before it "
            "started; a negative interval is a clock or a bookkeeping error, never a result"
        )
    if outcome == OUTCOME_PASSED and exit_code != 0:
        raise CleanCloneError(
            f"{step_id}: a pass with exit code {exit_code} is not a pass"
        )
    if outcome in (OUTCOME_FAILED, OUTCOME_REFUSED) and exit_code == 0:
        raise CleanCloneError(f"{step_id}: a {outcome} step cannot have exited 0")
    if outcome == OUTCOME_NOT_RUN:
        if ledger["mode"] != MODE_PREPARATION:
            raise CleanCloneError(
                f"{step_id}: a certification run may not record a step as not run. "
                "Run it, or record why it failed or was refused"
            )
        if step.kind != KIND_REAL:
            raise CleanCloneError(
                f"{step_id}: only a step that needs authorization may be recorded as not "
                f"run, and this one is a {step.kind} step"
            )
        if not reason:
            raise CleanCloneError(f"{step_id}: a step recorded as not run must say why")
    if reason is not None:
        _refuse_host_paths(reason, f"{step_id}: the reason")

    latest = latest_outcomes(ledger)
    if not step.after_failure:
        for earlier in steps(descriptor):
            if earlier.step_id == step_id:
                break
            if not _stands(ledger, latest.get(earlier.step_id)):
                raise CleanCloneError(
                    f"{step_id}: '{earlier.step_id}' comes first and has not "
                    f"{'passed' if ledger['mode'] == MODE_CERTIFICATION else 'passed or been recorded as not run'}"
                )

    attempt = {
        "stepId": step_id,
        "attempt": sum(1 for a in ledger["attempts"] if a["stepId"] == step_id) + 1,
        "outcome": outcome,
        "exitCode": exit_code,
        "startedAt": _epoch_ms_to_iso(started_epoch_ms),
        "finishedAt": _epoch_ms_to_iso(finished_epoch_ms),
        "elapsedMs": finished_epoch_ms - started_epoch_ms,
        "evidenceLabel": step.evidence_label,
        "reason": reason,
    }
    return {**ledger, "attempts": [*ledger["attempts"], attempt]}


def _refuse_host_paths(text: str, what: str) -> None:
    if "\n" in text or "\r" in text:
        raise CleanCloneError(f"{what} must be one line")
    if len(text) > MANUAL_ACTION_MAX_LENGTH:
        raise CleanCloneError(
            f"{what} is longer than {MANUAL_ACTION_MAX_LENGTH} characters"
        )
    for shape in HOST_PATH_SHAPES:
        if shape.search(text):
            raise CleanCloneError(
                f"{what} carries a host path; describe the action without it so the "
                "ledger stays publishable"
            )


def note(
    ledger: dict[str, Any],
    descriptor: dict[str, Any],
    *,
    description: str,
    at_epoch_ms: int,
    step_id: str | None = None,
) -> dict[str, Any]:
    """The ledger with one manual action appended.

    A manual action is anything a person did that no step did for them: installing
    a tool, starting an engine, placing a client ahead on PATH, freeing memory. A
    clean-clone record that omits them describes a journey nobody could repeat.
    """
    if step_id is not None:
        step_by_id(descriptor, step_id)
    description = description.strip()
    if not description:
        raise CleanCloneError("a manual action must say what was done")
    _refuse_host_paths(description, "a manual action")
    action = {
        "at": _epoch_ms_to_iso(at_epoch_ms),
        "stepId": step_id,
        "description": description,
    }
    return {**ledger, "manualActions": [*ledger["manualActions"], action]}


def pending_steps(ledger: dict[str, Any], descriptor: dict[str, Any]) -> list[str]:
    """The steps one invocation of the forward path should run, in order.

    A step whose latest attempt passed is skipped only when the checklist marks it
    resumable; a check is asked again every time, because what it checked may have
    changed since. A step recorded as not run is pending again, so that a later
    invocation holding its authorization runs it. Cleanup is not on the forward path
    at all: it has its own command, and the checks after it run with it.
    """
    latest = latest_outcomes(ledger)
    pending: list[str] = []
    for step in steps(descriptor):
        if step.after_failure:
            continue
        attempt = latest.get(step.step_id)
        if (
            attempt is not None
            and step.resumable
            and attempt["outcome"] == OUTCOME_PASSED
        ):
            continue
        pending.append(step.step_id)
    return pending


def merge_values(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Helm's own layering of values files, for a workflow that takes only one.

    Six of the release workflows accept a single ``--values`` file, and until this
    change the file they were given on the reference host was composed by hand
    from the committed real values and the two overlays the image scripts print.
    A step a person performs by hand is a step a clean-clone record has to name,
    so this does it instead, the way ``helm -f a -f b -f c`` would: a later map is
    merged into an earlier one key by key, and anything that is not a map --
    a string, a number, a list -- replaces what was there.
    """
    merged: dict[str, Any] = {}
    for document in documents:
        if not isinstance(document, dict):
            raise CleanCloneError("a values file must hold a mapping at its top level")
        merged = _merge_mapping(merged, document)
    return merged


def _merge_mapping(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = _merge_mapping(current, value)
        else:
            result[key] = value
    return result


def summarise(ledger: dict[str, Any], descriptor: dict[str, Any]) -> dict[str, Any]:
    """What the ledger may be read as saying, and nothing more."""
    latest = latest_outcomes(ledger)
    ordered = steps(descriptor)
    rows = []
    for step in ordered:
        attempt = latest.get(step.step_id)
        rows.append(
            {
                "stepId": step.step_id,
                "kind": step.kind,
                "outcome": attempt["outcome"] if attempt else None,
                "attempts": sum(
                    1 for a in ledger["attempts"] if a["stepId"] == step.step_id
                ),
                "elapsedMs": attempt["elapsedMs"] if attempt else None,
                "evidenceLabel": step.evidence_label,
                "reason": attempt["reason"] if attempt else None,
            }
        )

    outcomes = [row["outcome"] for row in rows]
    if any(outcome in (OUTCOME_FAILED, OUTCOME_REFUSED) for outcome in outcomes):
        status = SUMMARY_FAILED
    elif ledger["mode"] == MODE_PREPARATION:
        status = SUMMARY_PREPARATION_ONLY
    elif all(outcome == OUTCOME_PASSED for outcome in outcomes):
        status = SUMMARY_COMPLETE
    else:
        status = SUMMARY_INCOMPLETE

    attempts = ledger["attempts"]
    wall_clock_ms = None
    if attempts:
        start = datetime.fromisoformat(ledger["startedAt"].replace("Z", "+00:00"))
        end = max(
            datetime.fromisoformat(a["finishedAt"].replace("Z", "+00:00"))
            for a in attempts
        )
        wall_clock_ms = int((end - start).total_seconds() * 1000)

    return {
        "status": status,
        "mode": ledger["mode"],
        "provider": ledger["provider"],
        "clusterName": ledger["clusterName"],
        "certifiedProvider": ledger["certifiedProvider"],
        "certifiesProvider": (
            status == SUMMARY_COMPLETE
            and ledger["provider"] == ledger["certifiedProvider"]
        ),
        "repositoryRevision": ledger["repositoryRevision"],
        "startedAt": ledger["startedAt"],
        "wallClockMs": wall_clock_ms,
        "stepElapsedMs": sum(a["elapsedMs"] for a in attempts),
        "attempts": len(attempts),
        "manualActions": len(ledger["manualActions"]),
        "steps": rows,
    }
