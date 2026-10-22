"""The decisions of the control of one V2-E02A run, and the record they come from.

V2-E02A deletes the one runtime pod of the single-runtime baseline release while
the RP-1 runner sends requests. Its freeze record states the procedure: the
preparation P1 to P8, the collection, the stable pre-fault window, the fault F1 to
F4, the observation, the abort conditions, and the cleanup C1 to C5. This module
holds each decision that the procedure gives to the control process, as a pure
function of what the control read. :mod:`tools.experiment_e02a.control` runs the
procedure and calls these functions. It reads and writes no cluster itself.

**The record is the source.** :func:`load_plan` reads the latest V2-E02A record
that the freeze registry registers, holds its bytes to the registry pin, and takes
every structured value from it: the topology, the release, the model, the
environment identity, the caller run, the fault code, the abort codes, the
exclusion reasons, and the rule of the analysis declaration. The procedure also
states figures in prose: the 150 s of the first check, the 600 s of the
observation limit, the 900 timeline samples, and others. This module restates
each such figure as a constant, and :data:`BOUND_PHRASES` names the text of the
record that states it. :func:`binding_findings` refuses a record whose text does
not hold each phrase, so a later revision that changes a figure refuses this
control until the control changes too.

**What it does not do.** It does not judge a criterion, and it states no result
of a run that reached the fault. The review of the run judges the criteria and
writes the result page. It does not check that a reading is true: it decides from
what a reading states.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Final

from tools.environment_qualification.core import (
    Source,
    Sources,
    environment_digest,
    stable_environment_identity,
)
from tools.experiment_freeze.core import content_digest, load_registry

__all__ = [
    "ABORT_CODES",
    "BOUND_PHRASES",
    "CHECK_INTERVAL_SECONDS",
    "COLLECTOR_LEAD_SECONDS",
    "DIRECTORY",
    "DRY_RUN_ID",
    "EXPERIMENT_ID",
    "FAULT_CODE",
    "FIRST_CHECK_SECONDS",
    "FIRST_CONTROL_REVISION",
    "LAST_CHECK_SECONDS",
    "MAXIMUM_RUNS",
    "OBSERVATION_LIMIT_SECONDS",
    "REPO_ROOT",
    "RUN_ID",
    "STABLE_LOOKBACK_SECONDS",
    "STABLE_MINIMUM_SUCCESSES",
    "TELEMETRY_INTERVAL_SECONDS",
    "TELEMETRY_SAMPLES",
    "TIMELINE_INTERVAL_SECONDS",
    "TIMELINE_SAMPLES",
    "TOPOLOGY_WAIT_SECONDS",
    "WINDOW_AFTER_MS",
    "WINDOW_BEFORE_MS",
    "ClockReading",
    "Observation",
    "Plan",
    "PlanRefused",
    "Request",
    "Target",
    "abort_code",
    "binding_findings",
    "caller_requests",
    "capacity_findings",
    "check_offsets",
    "clock_bound_ms",
    "clock_reading",
    "cluster_findings",
    "declaration",
    "desired_state_findings",
    "fault_argv_tail",
    "fault_target",
    "format_instant",
    "identifier_findings",
    "job_ended",
    "load_plan",
    "model_findings",
    "nodes_ready",
    "parse_instant",
    "pod_identities",
    "provenance_findings",
    "ready_replicas",
    "repository_findings",
    "runner_pod_start",
    "stable_window",
    "topology_findings",
    "window",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

EXPERIMENT_ID: Final = "V2-E02A"
DIRECTORY: Final = "docs/proof/experiments/v2-e02a"
RECORD_NAME: Final = re.compile(r"^freeze-r([1-9][0-9]*)\.v1alpha1\.json$")

#: The first revision of the record that freezes this control. Revisions 1 and 2
#: state that no driver exists, so the control refuses to run under them.
FIRST_CONTROL_REVISION: Final = 3

#: A run identifier, and the identifier of a dry run. They never match each other,
#: so a dry run cannot take an identifier of a run.
RUN_ID: Final = re.compile(r"^e02a-([1-9][0-9]*)$")
DRY_RUN_ID: Final = re.compile(r"^dry-run-([1-9][0-9]*)$")

# The figures that the record states in prose. Each is held to its phrase by
# :data:`BOUND_PHRASES`.
STABLE_MINIMUM_SUCCESSES: Final = 10
STABLE_LOOKBACK_SECONDS: Final = 60
FIRST_CHECK_SECONDS: Final = 150
CHECK_INTERVAL_SECONDS: Final = 30
LAST_CHECK_SECONDS: Final = 600
OBSERVATION_LIMIT_SECONDS: Final = 600
WINDOW_BEFORE_MS: Final = 60_000
WINDOW_AFTER_MS: Final = 720_000
COLLECTOR_LEAD_SECONDS: Final = 30
TIMELINE_SAMPLES: Final = 900
TIMELINE_INTERVAL_SECONDS: Final = 2
TELEMETRY_SAMPLES: Final = 120
TELEMETRY_INTERVAL_SECONDS: Final = 15
TOPOLOGY_WAIT_SECONDS: Final = 1800
MAXIMUM_RUNS: Final = 6
CLUSTER_INCIDENT_SECONDS: Final = 60
FAULT_CODE: Final = "delete-runtime-pod"

#: The abort codes, in the order of the record. :func:`load_plan` refuses a record
#: that states another set.
ABORT_CODES: Final = (
    "abort-wrong-target",
    "abort-fault-differs",
    "abort-caller-lost",
    "abort-revision-unknown",
    "abort-model-risk",
    "abort-cluster-incident",
    "abort-checkout-changed",
    "abort-unrelated-change",
    "abort-cleanup-unsafe",
)

#: Each phrase that the record must hold for a constant of this module, by the
#: location of the text.
BOUND_PHRASES: Final[tuple[tuple[str, str], ...]] = (
    (
        "/definition/stablePreFaultWindow",
        "holds at least 10 successful requests that completed in the 60 s before "
        "the check, the last completed request succeeded, and both Deployments "
        "report the replica counts of topology as readyReplicas",
    ),
    (
        "/definition/stablePreFaultWindow",
        "The control checks at 150 s after the runner pod started, and every 30 s "
        "after that, until 600 s after it started.",
    ),
    (
        "/definition/stablePreFaultWindow",
        "When it does not hold at 600 s, no fault is injected, the runner is "
        "removed, and the run is REFUSED.",
    ),
    ("/definition/window/from", "less 60,000 ms"),
    ("/definition/window/to", "plus 720,000 ms"),
    (
        "/definition/observation",
        "The observation limit is 600 s after the fault-injection-finished event.",
    ),
    ("/definition/collection/order", "wait 30 s, and start the runner"),
    ("/definition/collection/timeline", "--samples 900 --interval 2"),
    ("/definition/collection/telemetry", "--samples 120 --interval 15"),
    ("/definition/preparation/5", "Wait at most 1,800 s for the topology"),
    ("/definition/repetitionRule", "At most 6 runs start under one revision."),
    (
        "/definition/faultProcedure/2",
        "Run kubectl delete pod <name> --namespace inferops-release --wait=false once.",
    ),
    (
        "/fields/fault/0/value/target",
        "The Ready runtime pod of the release whose name is first in ascending order "
        "at the fault check.",
    ),
    ("/fields/fault/0/value/type", FAULT_CODE),
    (
        "/fields/evidencePaths/0/value/directory",
        "where <run> is e02a-N, from 1, never reused",
    ),
    (
        "/fields/abortConditions/0/value/5/condition",
        "for more than 60 s",
    ),
)

#: The two tiers of the release, by the component label that the chart sets.
API_TIER: Final = "platform-api"
RUNTIME_TIER: Final = "serving-runtime"
TIERS: Final = (API_TIER, RUNTIME_TIER)
COMPONENT_LABEL: Final = "app.kubernetes.io/component"
INSTANCE_LABEL: Final = "app.kubernetes.io/instance"
SERVICE_NAME_LABEL: Final = "kubernetes.io/service-name"
HELM_RELEASE: Final = "inferops"
#: The Services of the two tiers, as the chart names them for the Helm release.
SERVICES: Final[Mapping[str, str]] = {
    API_TIER: "inferops-inferops-llm",
    RUNTIME_TIER: "inferops-inferops-llm-runtime",
}

#: What the verification init container of a runtime pod prints when the model
#: file has its pinned byte count and SHA-256.
MODEL_VERIFIED_LINE: Final = "model artifact verified: byte count and SHA-256"
VERIFY_CONTAINER: Final = "verify-model"

_INSTANT: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_COMMIT: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_POD_NAME: Final = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")


class PlanRefused(ValueError):
    """The record cannot drive a run: it is absent, edited, or not of this control."""


# --------------------------------------------------------------------------
# Instants
# --------------------------------------------------------------------------


def parse_instant(value: object) -> datetime | None:
    """A UTC instant to one millisecond, ``YYYY-MM-DDTHH:MM:SS.mmmZ``, or None."""
    if not isinstance(value, str) or _INSTANT.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def format_instant(instant: datetime) -> str:
    """An instant in UTC to one millisecond, in the form that :func:`parse_instant` reads."""
    instant = instant.astimezone(UTC)
    return (
        instant.strftime("%Y-%m-%dT%H:%M:%S.") + f"{instant.microsecond // 1000:03d}Z"
    )


def _kubernetes_instant(value: object) -> datetime | None:
    """A Kubernetes timestamp, ``YYYY-MM-DDTHH:MM:SSZ``, to the second, or None."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# The plan, from the record
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Plan:
    """What one run takes from the latest registered V2-E02A record."""

    record_path: str
    revision: int
    record_sha256: str
    api_replicas: int
    runtime_replicas: int
    namespace: str
    release_key: str
    desired_state_path: str
    desired_state_files: Mapping[str, str]
    release_id: str
    model_sha256: str
    environment_sha256: str
    application: str
    chart: str
    controller_manifest: str
    duration_seconds: int
    request_ceiling: int
    reasons: Mapping[str, str]
    analysis_declaration: Mapping[str, Any]

    @property
    def replicas(self) -> dict[str, int]:
        """The replica count of each tier."""
        return {API_TIER: self.api_replicas, RUNTIME_TIER: self.runtime_replicas}


def _pointer(document: Any, pointer: str) -> Any:
    """The member at a JSON pointer of plain names and indexes, or None."""
    value = document
    for part in pointer.strip("/").split("/"):
        if isinstance(value, Mapping):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def _field(document: Mapping[str, Any], name: str) -> Any:
    entries = _pointer(document, f"/fields/{name}")
    if not isinstance(entries, list) or len(entries) != 1:
        return None
    entry = entries[0]
    if not isinstance(entry, Mapping) or entry.get("status") != "value":
        return None
    return entry.get("value")


def binding_findings(document: Any) -> list[str]:
    """Each place where the record does not state what this control does.

    Each phrase of :data:`BOUND_PHRASES` must be in the text at its location, and
    the record must state the abort codes of :data:`ABORT_CODES` in that order.
    """
    findings: list[str] = []
    for pointer, phrase in BOUND_PHRASES:
        text = _pointer(document, pointer)
        if not isinstance(text, str) or phrase not in text:
            findings.append(f"{pointer} does not state: {phrase}")
    aborts = _field(document, "abortConditions")
    codes = (
        [item.get("code") for item in aborts if isinstance(item, Mapping)]
        if isinstance(aborts, list)
        else None
    )
    if codes != list(ABORT_CODES):
        findings.append("/fields/abortConditions does not state the abort codes")
    return findings


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _latest(registry: Mapping[str, str]) -> tuple[int, str]:
    revisions: dict[int, str] = {}
    for path in registry:
        posix = PurePosixPath(path)
        match = RECORD_NAME.fullmatch(posix.name)
        if posix.parent.as_posix() == DIRECTORY and match is not None:
            revisions[int(match.group(1))] = path
    if not revisions:
        raise PlanRefused(f"the freeze registry registers no record of {EXPERIMENT_ID}")
    revision = max(revisions)
    return revision, revisions[revision]


def load_plan(root: Path = REPO_ROOT) -> Plan:
    """The plan of a run, from the latest V2-E02A record that the registry pins.

    Raises:
        PlanRefused: the registry is unreadable or registers no record; the record
            file is absent or differs from its pin; its revision precedes this
            control; it does not state a phrase or a value that the control uses.
    """
    try:
        registry = load_registry(root)
    except ValueError as error:
        raise PlanRefused("the freeze registry is not readable") from error
    revision, path = _latest(registry)
    if revision < FIRST_CONTROL_REVISION:
        raise PlanRefused(
            f"the latest {EXPERIMENT_ID} record is revision {revision}, which freezes "
            "no driver; this control needs revision "
            f"{FIRST_CONTROL_REVISION} or later"
        )
    try:
        data = (root / path).read_bytes()
    except OSError as error:
        raise PlanRefused(f"{path} is not readable") from error
    digest = content_digest(data)
    if digest != registry[path]:
        raise PlanRefused(f"{path} differs from its registry pin")
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise PlanRefused(f"{path} is not JSON") from error
    if (
        _pointer(document, "/metadata/experiment") != EXPERIMENT_ID
        or _pointer(document, "/metadata/revision") != revision
    ):
        raise PlanRefused(f"{path} does not state {EXPERIMENT_ID} revision {revision}")
    findings = binding_findings(document)
    if findings:
        raise PlanRefused(f"{path}: " + "; ".join(findings))
    return _plan(path, revision, digest, document)


def _plan(path: str, revision: int, digest: str, document: Any) -> Plan:
    topology = _field(document, "topology")
    environment = _field(document, "environmentIdentity")
    caller = _pointer(document, "/definition/callerRun")
    reasons = _pointer(document, "/exclusionReasons/reasons")
    declaration_rule = _pointer(document, "/definition/analysisDeclaration")
    release = _pointer(topology, "/release")
    files = _pointer(release, "/desiredStateFiles")
    model = _pointer(topology, "/model/sha256")
    values: dict[str, Any] = {
        "api_replicas": _integer(_pointer(topology, "/apiReplicas")),
        "runtime_replicas": _integer(_pointer(topology, "/runtimeReplicas")),
        "namespace": _text(_pointer(topology, "/namespace")),
        "release_key": _text(_pointer(topology, "/releaseKey")),
        "desired_state_path": _text(_pointer(topology, "/desiredStatePath")),
        "release_id": _text(_pointer(release, "/releaseId")),
        "environment_sha256": _text(_pointer(environment, "/environmentSha256")),
        "application": _text(_pointer(topology, "/delivery/application")),
        "chart": _text(_pointer(topology, "/chart/path")),
        "controller_manifest": _text(_pointer(topology, "/delivery/manifest/path")),
        "duration_seconds": _integer(_pointer(caller, "/durationSeconds")),
        "request_ceiling": _integer(_pointer(caller, "/requestCeiling")),
    }
    missing = sorted(name for name, value in values.items() if value is None)
    model_hex = (
        model.removeprefix("sha256:")
        if isinstance(model, str) and model.startswith("sha256:")
        else None
    )
    if model_hex is None or _SHA256.fullmatch(model_hex) is None:
        missing.append("model_sha256")
    if (
        not isinstance(files, Mapping)
        or not files
        or not all(
            isinstance(name, str) and isinstance(sha, str) and _SHA256.fullmatch(sha)
            for name, sha in files.items()
        )
    ):
        missing.append("desired_state_files")
    if not isinstance(reasons, list) or not all(
        isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("resultState"), str)
        for item in reasons
    ):
        missing.append("reasons")
    if not isinstance(declaration_rule, Mapping):
        missing.append("analysis_declaration")
    if missing:
        raise PlanRefused(f"{path} does not state {', '.join(sorted(missing))}")
    assert isinstance(files, Mapping)
    assert isinstance(reasons, list)
    assert isinstance(declaration_rule, Mapping)
    assert model_hex is not None
    return Plan(
        record_path=path,
        revision=revision,
        record_sha256=digest,
        desired_state_files=dict(files),
        model_sha256=model_hex,
        reasons={item["id"]: item["resultState"] for item in reasons},
        analysis_declaration=declaration_rule,
        **values,
    )


# --------------------------------------------------------------------------
# The run identifier
# --------------------------------------------------------------------------


def identifier_findings(
    run_id: str,
    *,
    dry_run: bool,
    taken: Iterable[str],
    runs_under_revision: int,
) -> list[str]:
    """Why ``run_id`` cannot be used, or nothing.

    A dry run takes ``dry-run-N`` and never ``e02a-N``. A run takes ``e02a-N``: the
    next identifier after every one taken, so none is reused and none is skipped,
    and at most :data:`MAXIMUM_RUNS` runs start under one revision. An identifier
    is taken once a run starts with it, whatever its result.
    """
    if dry_run:
        if DRY_RUN_ID.fullmatch(run_id) is None:
            return [f"a dry run takes an identifier dry-run-N, not {run_id!r}"]
        return []
    match = RUN_ID.fullmatch(run_id)
    if match is None:
        return [f"a run takes an identifier e02a-N, not {run_id!r}"]
    numbers = sorted(
        int(found.group(1))
        for found in (RUN_ID.fullmatch(name) for name in taken)
        if found is not None
    )
    findings = []
    expected = (numbers[-1] + 1) if numbers else 1
    if int(match.group(1)) != expected:
        findings.append(f"the next run identifier is e02a-{expected}, not {run_id}")
    if runs_under_revision >= MAXIMUM_RUNS:
        findings.append(
            f"{runs_under_revision} runs started under this revision; at most "
            f"{MAXIMUM_RUNS} start under one revision"
        )
    return findings


# --------------------------------------------------------------------------
# P1 and P2: the repository and the desired revision
# --------------------------------------------------------------------------


def repository_findings(
    *,
    head: str | None,
    clean: bool | None,
    checks: Mapping[str, int | None],
    changes_exit: int | None,
) -> list[str]:
    """P1: the executing revision, the working tree, and the four checks.

    ``checks`` holds the exit status of each check that P1 names, and
    ``changes_exit`` that of ``--changes`` for the record. Each must be 0. None
    states a check that did not run.
    """
    findings = []
    if head is None or _COMMIT.fullmatch(head) is None:
        findings.append("the executing revision was not read")
    if clean is not True:
        findings.append("the working tree is not clean")
    findings.extend(
        f"python -m {name} --check exited {status}"
        for name, status in sorted(checks.items())
        if status != 0
    )
    if changes_exit != 0:
        findings.append("the freeze tool lists a moved input of the record")
    return findings


def desired_state_findings(
    plan: Plan,
    *,
    desired: str | None,
    paths_equal: bool | None,
    digests: Mapping[str, str | None],
) -> list[str]:
    """P2: the desired revision, its delivery paths, and its two desired-state files.

    ``digests`` holds the SHA-256 of each file of ``topology.desiredStatePath`` at
    the desired revision, or None for a file that the revision does not hold. Each
    must be the digest that ``topology.release.desiredStateFiles`` states, so a
    desired state of another topology refuses the run.
    """
    findings = []
    if desired is None or _COMMIT.fullmatch(desired) is None:
        findings.append("the desired revision was not read")
    if paths_equal is not True:
        findings.append(
            "the chart, the desired-state tree, or the controller manifests of the "
            "executing revision differ from the desired revision"
        )
    for name, expected in sorted(plan.desired_state_files.items()):
        found = digests.get(name)
        if found != expected:
            findings.append(
                f"{plan.desired_state_path}/{name} at the desired revision has "
                f"{found or 'no file'}, and the record states {expected}"
            )
    for name in sorted(set(digests) - set(plan.desired_state_files)):
        findings.append(f"{plan.desired_state_path}/{name} is not a file of the record")
    return findings


# --------------------------------------------------------------------------
# P3 and P4: the target and the capacity
# --------------------------------------------------------------------------


def cluster_findings(
    plan: Plan,
    *,
    target_exit: int | None,
    namespaces: Sequence[str] | None,
    controller_namespace: str,
) -> list[str]:
    """P3: the target check, and a cluster that holds no release and no controller."""
    findings = []
    if target_exit != 0:
        findings.append("the target check did not select the docker-desktop provider")
    if namespaces is None:
        findings.append("the namespaces were not read")
        return findings
    for name in (plan.namespace, controller_namespace):
        if f"namespace/{name}" in namespaces or name in namespaces:
            findings.append(f"the cluster already holds the namespace {name}")
    return findings


def capacity_findings(
    plan: Plan, *, exit_status: int | None, record: Mapping[str, Any] | None
) -> list[str]:
    """P4: the capacity gate accepted the reading, in the environment of the record.

    The stable environment identity is computed from the gate record by the
    function of ``tools.environment_qualification`` that computed the identity of
    the qualification.
    """
    if exit_status != 0 or record is None:
        return [f"the capacity gate did not accept the reading (exit {exit_status})"]
    identity = stable_environment_identity(_capacity_sources(record))
    if identity is None:
        return ["the capacity record states no stable environment identity"]
    digest = environment_digest(identity)
    if digest != plan.environment_sha256:
        return [
            f"the stable environment identity is {digest}, and the record states "
            f"{plan.environment_sha256}"
        ]
    return []


def _capacity_sources(record: Mapping[str, Any]) -> Sources:
    """The sources of a qualification that hold one capacity record and nothing else.

    The identity functions of the qualification read the capacity record alone.
    """
    absent = Source("absent", problem="absent")
    return Sources(
        header={},
        capacity=Source("capacity", value=record),
        provenance=absent,
        reconciliation=absent,
        deployments=absent,
        endpoints=absent,
        model_cache=absent,
        plan=absent,
        caller_text=None,
        caller_refused=False,
        root=REPO_ROOT,
        directory=REPO_ROOT,
    )


# --------------------------------------------------------------------------
# P6: the topology
# --------------------------------------------------------------------------


def _items(document: Any) -> list[Mapping[str, Any]]:
    items = _pointer(document, "/items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, Mapping)]


def _tier(item: Mapping[str, Any]) -> str | None:
    labels = _pointer(item, "/metadata/labels")
    if not isinstance(labels, Mapping) or labels.get(INSTANCE_LABEL) != HELM_RELEASE:
        return None
    tier = labels.get(COMPONENT_LABEL)
    return tier if tier in TIERS else None


def ready_replicas(deployments: Any) -> dict[str, int | None]:
    """The readyReplicas of the one Deployment of each tier, or None.

    A tier with no Deployment, with more than one, or whose Deployment states no
    readyReplicas is None. Kubernetes omits readyReplicas when it is zero, so an
    omitted count is not read as zero.
    """
    found: dict[str, list[Mapping[str, Any]]] = {tier: [] for tier in TIERS}
    for item in _items(deployments):
        tier = _tier(item)
        if tier is not None:
            found[tier].append(item)
    counts: dict[str, int | None] = {}
    for tier, items in found.items():
        counts[tier] = (
            _integer(_pointer(items[0], "/status/readyReplicas"))
            if len(items) == 1
            else None
        )
    return counts


def ready_endpoints(slices: Any) -> dict[str, int | None]:
    """The Ready endpoints of the Service of each tier, over its EndpointSlices.

    A Service with no slice is None.
    """
    counts: dict[str, int | None] = {tier: None for tier in TIERS}
    for item in _items(slices):
        labels = _pointer(item, "/metadata/labels")
        service = (
            labels.get(SERVICE_NAME_LABEL) if isinstance(labels, Mapping) else None
        )
        tiers = [tier for tier, name in SERVICES.items() if name == service]
        if not tiers:
            continue
        endpoints = item.get("endpoints") or []
        ready = sum(
            1
            for endpoint in endpoints
            if isinstance(endpoint, Mapping)
            and _pointer(endpoint, "/conditions/ready") is True
        )
        counts[tiers[0]] = (counts[tiers[0]] or 0) + ready
    return counts


def application_state(application: Any) -> dict[str, str | None]:
    """The resolved revision, the sync state, and the health state of the Application."""
    return {
        "revision": _text(_pointer(application, "/status/sync/revision")),
        "sync": _text(_pointer(application, "/status/sync/status")),
        "health": _text(_pointer(application, "/status/health/status")),
    }


def topology_findings(
    plan: Plan,
    *,
    deployments: Any,
    slices: Any,
    application: Any,
    desired: str,
) -> list[str]:
    """P6: both Deployments, both Services, and the Application at the desired revision."""
    findings = []
    replicas = ready_replicas(deployments)
    endpoints = ready_endpoints(slices)
    for tier, expected in plan.replicas.items():
        if replicas[tier] != expected:
            findings.append(f"{tier} readyReplicas is {replicas[tier]}, not {expected}")
        if endpoints[tier] != expected:
            findings.append(
                f"{tier} Ready endpoints are {endpoints[tier]}, not {expected}"
            )
    state = application_state(application)
    if state != {"revision": desired, "sync": "Synced", "health": "Healthy"}:
        findings.append(
            "the Application is not Synced and Healthy at the desired revision"
        )
    return findings


# --------------------------------------------------------------------------
# P7: the release and the model
# --------------------------------------------------------------------------


def provenance_findings(plan: Plan, provenance: Any) -> list[str]:
    """P7: the provenance of the release key at the desired revision names the release."""
    records = provenance if isinstance(provenance, list) else [provenance]
    identifiers = [
        _pointer(item, "/release/releaseId")
        for item in records
        if _pointer(item, "/desiredState/key") == plan.release_key
    ]
    if identifiers != [plan.release_id]:
        return [
            f"the provenance of {plan.release_key} does not name the release "
            f"{plan.release_id}"
        ]
    return []


def model_findings(
    plan: Plan, runtime_pods: Any, logs: Mapping[str, str | None]
) -> list[str]:
    """P7: each runtime pod verified the model file of the record.

    The verification container prints that the file has its pinned byte count and
    SHA-256, and the script that the chart renders into it holds the SHA-256 of the
    record. A pod with no log, or with another digest, is a finding.
    """
    findings = []
    pods = [item for item in _items(runtime_pods) if _tier(item) == RUNTIME_TIER]
    if len(pods) != plan.runtime_replicas:
        findings.append(
            f"{len(pods)} runtime pods were read, not {plan.runtime_replicas}"
        )
    for pod in pods:
        name = _pointer(pod, "/metadata/name")
        containers = _pointer(pod, "/spec/initContainers")
        script = [
            json.dumps(container.get("command"))
            for container in (containers if isinstance(containers, list) else [])
            if isinstance(container, Mapping)
            and container.get("name") == VERIFY_CONTAINER
        ]
        if len(script) != 1 or plan.model_sha256 not in script[0]:
            findings.append(f"{name} does not verify the model digest of the record")
        log = logs.get(name) if isinstance(name, str) else None
        if log is None or MODEL_VERIFIED_LINE not in log:
            findings.append(f"{name} did not report the verified model file")
    return findings


# --------------------------------------------------------------------------
# P8: the clocks
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ClockReading:
    """One P8 reading: a host instant, the node instant, and a second host instant."""

    host_before: datetime
    node: datetime
    host_after: datetime

    @property
    def difference_ms(self) -> int:
        """d: the difference between the node instant and the nearer host instant."""
        nearer = min(
            abs(_ms(self.node - self.host_before)),
            abs(_ms(self.node - self.host_after)),
        )
        return nearer

    @property
    def width_ms(self) -> int:
        """w: the time from the first host instant to the second."""
        return _ms(self.host_after - self.host_before)


def _ms(delta: timedelta) -> int:
    return round(delta.total_seconds() * 1000)


def clock_reading(text: str | None) -> ClockReading | None:
    """A P8 reading from three lines of instants, or None when it is unusable.

    A reading is unusable when an instant is missing or is not a UTC instant to the
    millisecond, or when its second host instant is before its first.
    """
    if text is None:
        return None
    lines = [
        line.strip() for line in text.replace("\r", "").split("\n") if line.strip()
    ]
    if len(lines) != 3:
        return None
    instants = [parse_instant(line) for line in lines]
    before, node, after = instants
    if before is None or node is None or after is None or after < before:
        return None
    return ClockReading(before, node, after)


def clock_bound_ms(start: ClockReading | None, end: ClockReading | None) -> int | None:
    """The clock bound of the run, in ms, or None when a reading is unusable.

    The larger d of the two readings plus the larger w of the two readings, as
    ``definition.clockPolicy.bound.computation`` states it.
    """
    if start is None or end is None:
        return None
    return max(start.difference_ms, end.difference_ms) + max(
        start.width_ms, end.width_ms
    )


# --------------------------------------------------------------------------
# The stable pre-fault window
# --------------------------------------------------------------------------


def check_offsets() -> tuple[int, ...]:
    """The seconds after the runner pod started at which the control checks."""
    return tuple(
        range(FIRST_CHECK_SECONDS, LAST_CHECK_SECONDS + 1, CHECK_INTERVAL_SECONDS)
    )


@dataclass(frozen=True)
class Request:
    """One completed request of the caller record: when it finished, and whether it succeeded."""

    finished_at: datetime
    success: bool


def caller_requests(text: str | None, run_id: str) -> list[Request]:
    """The completed requests of the caller record that the runner wrote so far.

    The log of the runner pod is read while it runs, so its last line can be cut,
    and a line of another stream can be among its lines. A line that is not a
    complete JSON object, or that is not a request line of the run, is skipped.
    """
    if not text:
        return []
    lines = text.replace("\r", "").split("\n")
    if not text.endswith("\n"):
        lines = lines[:-1]
    requests = []
    for line in lines:
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if (
            not isinstance(value, dict)
            or value.get("record") != "request"
            or value.get("runId") != run_id
            or not isinstance(value.get("success"), bool)
        ):
            continue
        finished = parse_instant(value.get("finishedAt"))
        if finished is not None:
            requests.append(Request(finished, value["success"]))
    return requests


def stable_window(
    plan: Plan,
    requests: Sequence[Request],
    *,
    check_at: datetime,
    replicas: Mapping[str, int | None],
) -> tuple[bool, str]:
    """Whether the stable pre-fault window holds at a check, and why.

    It holds when at least :data:`STABLE_MINIMUM_SUCCESSES` successful requests
    completed in the :data:`STABLE_LOOKBACK_SECONDS` before the check, the last
    completed request succeeded, and both Deployments report the replica counts of
    the topology as readyReplicas. A request completed before the check when its
    completion instant is not after the check. The caller instants are on the node
    clock and the check is on the host clock, and this decision orders them with no
    margin, as the record states.
    """
    completed = [request for request in requests if request.finished_at <= check_at]
    since = check_at - timedelta(seconds=STABLE_LOOKBACK_SECONDS)
    recent = sum(
        1 for request in completed if request.success and request.finished_at > since
    )
    reasons = []
    if recent < STABLE_MINIMUM_SUCCESSES:
        reasons.append(f"{recent} successful requests in the last 60 s")
    last = max(completed, key=lambda request: request.finished_at, default=None)
    if last is None or not last.success:
        reasons.append("the last completed request did not succeed")
    for tier, expected in plan.replicas.items():
        if replicas.get(tier) != expected:
            reasons.append(f"{tier} readyReplicas is {replicas.get(tier)}")
    if reasons:
        return False, "; ".join(reasons)
    return True, f"{recent} successful requests in the last 60 s, the last succeeded"


# --------------------------------------------------------------------------
# F1: the fault target
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Target:
    """The pod that the fault deletes, and every pod of the release when it was selected."""

    name: str
    uid: str
    pods: tuple[tuple[str, str, str], ...]


def _ready(pod: Mapping[str, Any]) -> bool:
    conditions = _pointer(pod, "/status/conditions")
    return isinstance(conditions, list) and any(
        isinstance(condition, Mapping)
        and condition.get("type") == "Ready"
        and condition.get("status") == "True"
        for condition in conditions
    )


def pod_identities(pods: Any) -> tuple[tuple[str, str, str], ...]:
    """The name, the UID, and the tier of each pod of the release, sorted by name."""
    found = []
    for pod in _items(pods):
        tier = _tier(pod)
        name = _pointer(pod, "/metadata/name")
        uid = _pointer(pod, "/metadata/uid")
        if tier is not None and isinstance(name, str) and isinstance(uid, str):
            found.append((name, uid, tier))
    return tuple(sorted(found))


def fault_target(pods: Any) -> Target | None:
    """F1: the Ready runtime pod of the release whose name is first in ascending order.

    A pod that is being deleted is not a target. None when no runtime pod is Ready.
    """
    ready = sorted(
        (pod["metadata"]["name"], pod["metadata"]["uid"])
        for pod in _items(pods)
        if _tier(pod) == RUNTIME_TIER
        and _ready(pod)
        and _pointer(pod, "/metadata/deletionTimestamp") is None
        and isinstance(_pointer(pod, "/metadata/name"), str)
        and isinstance(_pointer(pod, "/metadata/uid"), str)
    )
    if not ready:
        return None
    name, uid = ready[0]
    if _POD_NAME.fullmatch(name) is None:
        return None
    return Target(name=name, uid=uid, pods=pod_identities(pods))


def fault_argv_tail(plan: Plan, target: Target) -> list[str]:
    """F3: the arguments of the one fault command after ``kubectl``.

    ``delete pod <name> --namespace <namespace> --wait=false``: by name, once, with
    the default grace period.
    """
    if _POD_NAME.fullmatch(target.name) is None:
        raise ValueError("the target is not a pod name")
    return ["delete", "pod", target.name, "--namespace", plan.namespace, "--wait=false"]


# --------------------------------------------------------------------------
# Abort conditions
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Observation:
    """What the control read at one check while the run executes.

    None states a read that did not answer.
    """

    at: datetime
    head: str | None
    clean: bool | None
    namespaces: tuple[str, ...] | None
    crds: tuple[str, ...] | None
    node_ready: bool | None
    runner_pod: Any
    runner_job: Any
    application: Any
    claims: Any
    window_ended: bool


def runner_pod_start(runner_pod: Any) -> datetime | None:
    """The start instant of the one runner pod, to the second, or None."""
    pods = _items(runner_pod)
    if len(pods) != 1:
        return None
    return _kubernetes_instant(_pointer(pods[0], "/status/startTime"))


def nodes_ready(nodes: Any) -> bool | None:
    """Whether every node reports Ready, or None when no node was read."""
    items = _items(nodes)
    if not items:
        return None
    return all(_ready(node) for node in items)


def job_ended(runner_job: Any) -> bool:
    """Whether the Job of the runner reports a succeeded or a failed pod."""
    return bool(
        _integer(_pointer(runner_job, "/status/succeeded"))
        or _integer(_pointer(runner_job, "/status/failed"))
    )


def _runner_lost(runner_pod: Any, runner_job: Any, window_ended: bool) -> bool:
    """The runner pod is gone, evicted, or restarted, or its Job failed, before the window ends."""
    if window_ended:
        return False
    if _integer(_pointer(runner_job, "/status/failed")):
        return True
    pods = _items(runner_pod)
    if len(pods) != 1:
        return True
    pod = pods[0]
    if _pointer(pod, "/metadata/deletionTimestamp") is not None:
        return True
    if _pointer(pod, "/status/reason") == "Evicted":
        return True
    if _pointer(pod, "/status/phase") == "Failed":
        return True
    statuses = _pointer(pod, "/status/containerStatuses")
    return isinstance(statuses, list) and any(
        isinstance(status, Mapping) and (_integer(status.get("restartCount")) or 0) > 0
        for status in statuses
    )


def abort_code(
    plan: Plan,
    observation: Observation,
    *,
    head: str,
    namespaces: tuple[str, ...],
    crds: tuple[str, ...],
    desired: str,
    unanswered_since: datetime | None,
) -> str | None:
    """The first abort condition that an observation crosses, or None.

    ``head``, ``namespaces``, and ``crds`` are what the control read after the
    preparation, and ``unanswered_since`` is the first check since which the node
    was not Ready or the Kubernetes API did not answer. The control detects six of
    the nine conditions here. ``abort-wrong-target`` is the target check of P3, and
    ``abort-fault-differs`` is the one-time fault of the control. A change that a
    person makes by hand is not read here, and ``abort-cleanup-unsafe`` is decided
    at the cleanup.
    """
    if observation.head != head or observation.clean is not True:
        return "abort-checkout-changed"
    if unanswered_since is not None and observation.at - unanswered_since > timedelta(
        seconds=CLUSTER_INCIDENT_SECONDS
    ):
        return "abort-cluster-incident"
    if (
        observation.namespaces is not None and observation.namespaces != namespaces
    ) or (observation.crds is not None and observation.crds != crds):
        return "abort-unrelated-change"
    if observation.runner_pod is not None and _runner_lost(
        observation.runner_pod, observation.runner_job, observation.window_ended
    ):
        return "abort-caller-lost"
    revision = application_state(observation.application)["revision"]
    if observation.application is not None and revision not in (None, desired):
        return "abort-revision-unknown"
    if observation.claims is not None and not _items(observation.claims):
        return "abort-model-risk"
    return None


# --------------------------------------------------------------------------
# The window and the declaration
# --------------------------------------------------------------------------


def window(started: datetime, finished: datetime) -> tuple[datetime, datetime]:
    """The window: the fault-injection-started instant less 60,000 ms, to the
    fault-injection-finished instant plus 720,000 ms."""
    return (
        started - timedelta(milliseconds=WINDOW_BEFORE_MS),
        finished + timedelta(milliseconds=WINDOW_AFTER_MS),
    )


_TOPOLOGY_MEMBER: Final = re.compile(r"^topology\.(apiReplicas|runtimeReplicas)$")


def declaration(
    plan: Plan,
    *,
    run_id: str,
    desired: str,
    started: datetime,
    finished: datetime,
) -> dict[str, Any]:
    """The declaration of the analysis, from ``definition.analysisDeclaration``.

    Each value of the rule is copied, and each member that the rule describes in
    words is replaced by its value: the experiment identifier, the run identifier,
    the window, the desired revision, and each topology member.
    """
    rule = plan.analysis_declaration
    start, end = window(started, finished)

    def substitute(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: substitute(member) for key, member in value.items()}
        if isinstance(value, list):
            return [substitute(member) for member in value]
        if isinstance(value, str):
            match = _TOPOLOGY_MEMBER.fullmatch(value)
            if match is not None:
                return (
                    plan.api_replicas
                    if match.group(1) == "apiReplicas"
                    else plan.runtime_replicas
                )
        return value

    document: dict[str, Any] = {
        "schema": rule["schema"],
        "experimentId": EXPERIMENT_ID,
        "runId": run_id,
        "window": {"from": format_instant(start), "to": format_instant(end)},
        "expected": substitute(rule["expected"]),
        "signals": substitute(rule["signals"]),
    }
    document["expected"]["desiredRevision"] = desired
    return document
