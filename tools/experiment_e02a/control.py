"""The procedure of one V2-E02A run, in the order of its freeze record.

:class:`Control` runs the preparation P1 to P8, the collection, the checks of the
stable pre-fault window, the fault F1 to F4, the observation, and the cleanup C1 to
C4, and it decides each step with :mod:`tools.experiment_e02a.core`. It reads and
acts only through a :class:`Port`, and it deletes a pod only through a
:class:`Fault`.

**A dry run cannot inject a fault.** The fault is a separate object. A run of the
procedure gets one, and a dry run gets None. With None the control issues no fault
command and records no fault event. ``python -m tools.experiment_e02a dry-run``
never constructs a fault, and its port reads a scenario file and executes nothing.

**A refusal is a result, and so is an abort.** The control writes what it decided
into ``control.json`` in the work directory of the run, whatever the result is. A
refusal before P5 leaves the cluster as it was. A refusal or an abort after the
start of P5 runs the cleanup.

**The control states no result of a run that reached the fault.** It states that
the run was observed, and the review of the run judges each criterion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final, Protocol

from tools.experiment_events import core as events

from . import core
from .core import Plan

__all__ = [
    "ABORTED",
    "CONTROL_FILE",
    "DECLARATION_FILE",
    "EVENTS_FILE",
    "OBSERVED",
    "P1_CHECKS",
    "PREPARATION",
    "REFUSED",
    "Background",
    "Control",
    "Fault",
    "Outcome",
    "Port",
]

#: The files that the control writes into the work directory of a run.
CONTROL_FILE: Final = "control.json"
DECLARATION_FILE: Final = "declaration.json"
EVENTS_FILE: Final = "operator-events.jsonl"

#: The four checks that P1 runs, by module.
P1_CHECKS: Final = (
    "tools.experiment_freeze",
    "tools.experiment_preregistration",
    "tools.environment_qualification",
    "tools.experiment_bounds",
)

#: The preparation acts of P5, in order. The Application is applied after them,
#: after the second capacity reading.
PREPARATION: Final = (
    "api-image",
    "seed-image",
    "prerequisites",
    "model-cache",
    "controller",
)

# The bounds of the waits of the control. The record states none of them. Each
# bounds a wait, and none changes a criterion, a window, or a figure of the run.
TOPOLOGY_POLL_SECONDS: Final = 10
SAMPLING_BOUND_SECONDS: Final = 120
JOB_END_SLACK_SECONDS: Final = 300
COLLECTOR_BOUND_SECONDS: Final = 3600
POLL_SECONDS: Final = 5

OBSERVED: Final = "OBSERVED"
REFUSED: Final = "REFUSED"
ABORTED: Final = "ABORTED"


class Background(Protocol):
    """A collector that runs beside the control."""

    def alive(self) -> bool: ...

    def output(self) -> str: ...

    def wait(self, seconds: float) -> int | None: ...

    def stop(self) -> None: ...


class Port(Protocol):
    """Every read and every act of the control, except the fault.

    ``read`` gives the text that a read printed, or None when the read did not
    answer. ``status`` gives the exit status of a read whose answer is its status.
    ``act`` gives the exit status of an act.
    """

    def head(self) -> str | None: ...

    def clean(self) -> bool | None: ...

    def check(self, module: str) -> int | None: ...

    def changes(self, record: str) -> int | None: ...

    def desired_revision(self) -> str | None: ...

    def delivery_paths_equal(self, desired: str) -> bool | None: ...

    def desired_state_digests(
        self, desired: str, directory: str
    ) -> dict[str, str | None]: ...

    def read(self, name: str, *arguments: str) -> str | None: ...

    def status(self, name: str, *arguments: str) -> int | None: ...

    def act(self, name: str, *arguments: str) -> int: ...

    def start(self, name: str, *arguments: str) -> Background: ...

    def taken_identifiers(self) -> list[str]: ...

    def runs_under(self, record: str) -> int: ...

    def now(self) -> datetime: ...

    def sleep(self, seconds: float) -> None: ...

    def keep(self, run_id: str, work: Path) -> list[str]: ...


class Fault(Protocol):
    """The one command that deletes a pod."""

    def delete(self, pod: str) -> int: ...


@dataclass(frozen=True)
class Outcome:
    """What the control decided: OBSERVED, REFUSED with a reason, or ABORTED with a code."""

    state: str
    reason: str | None
    step: str
    work: Path


class _Stop(Exception):
    def __init__(self, state: str, reason: str, step: str) -> None:
        super().__init__(reason)
        self.state = state
        self.reason = reason
        self.step = step


@dataclass
class _Journal:
    """The record of the decisions of one run, written as ``control.json``."""

    path: Path
    document: dict[str, Any] = field(default_factory=dict)

    def step(self, name: str, at: datetime, findings: list[str], **facts: Any) -> None:
        self.document.setdefault("steps", []).append(
            {
                "step": name,
                "at": core.format_instant(at),
                "held": not findings,
                "findings": findings,
                **facts,
            }
        )
        self.write()

    def write(self) -> None:
        text = json.dumps(self.document, indent=2, sort_keys=True) + "\n"
        self.path.write_bytes(text.encode("utf-8"))


def _json(text: str | None) -> Any:
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _names(text: str | None) -> tuple[str, ...] | None:
    if text is None:
        return None
    return tuple(sorted(line.strip() for line in text.splitlines() if line.strip()))


def _reading(reading: core.ClockReading | None) -> dict[str, str] | None:
    if reading is None:
        return None
    return {
        "hostBefore": core.format_instant(reading.host_before),
        "node": core.format_instant(reading.node),
        "hostAfter": core.format_instant(reading.host_after),
    }


class Control:
    """One run of the procedure, or one dry run of it."""

    def __init__(
        self,
        plan: Plan,
        port: Port,
        *,
        run_id: str,
        work_root: Path,
        controller_namespace: str,
        fault: Fault | None,
    ) -> None:
        self.plan = plan
        self.port = port
        self.run_id = run_id
        self.controller_namespace = controller_namespace
        self.fault = fault
        self.work = work_root / run_id
        self.journal = _Journal(self.work / CONTROL_FILE)
        self.events_path = self.work / EVENTS_FILE
        self.installed = False
        self.runner_started = False
        self.events_open = False
        self.fault_issued = False
        self.fault_reached = False
        self.collectors: dict[str, Background] = {}
        self.head = ""
        self.desired = ""
        self.namespaces: tuple[str, ...] = ()
        self.crds: tuple[str, ...] = ()
        self.prepared_namespaces: tuple[str, ...] = ()
        self.prepared_crds: tuple[str, ...] = ()
        self.unanswered_since: datetime | None = None
        self.window_end: datetime | None = None
        self.start_reading: core.ClockReading | None = None
        self.runner_pod_start: datetime | None = None

    @property
    def dry_run(self) -> bool:
        return self.fault is None

    # ------------------------------------------------------------------
    # The run
    # ------------------------------------------------------------------

    def identifier_findings(self) -> list[str]:
        """Why the identifier cannot be used, read before anything is written."""
        return core.identifier_findings(
            self.run_id,
            dry_run=self.dry_run,
            taken=self.port.taken_identifiers(),
            runs_under_revision=self.port.runs_under(self.plan.record_path),
        )

    def run(self) -> Outcome:
        """Run the procedure. The identifier is spent once the work directory exists.

        Raises:
            ValueError: the identifier cannot be used. Nothing is written.
        """
        findings = self.identifier_findings()
        if findings:
            raise ValueError("; ".join(findings))
        self.work.mkdir(parents=True, exist_ok=False)
        self.journal.document = {
            "experimentId": core.EXPERIMENT_ID,
            "runId": self.run_id,
            "dryRun": self.dry_run,
            "freezeRecord": {
                "path": self.plan.record_path,
                "revision": self.plan.revision,
                "contentSha256": self.plan.record_sha256,
            },
            "startedAt": core.format_instant(self.port.now()),
            "steps": [],
        }
        self.journal.write()
        try:
            self._procedure()
            outcome = Outcome(OBSERVED, None, "C4", self.work)
        except _Stop as stop:
            outcome = Outcome(stop.state, stop.reason, stop.step, self.work)
            self._after_stop(stop)
        self.journal.document["outcome"] = {
            "state": outcome.state,
            "reason": outcome.reason,
            "step": outcome.step,
            "statement": (
                "The control states no result of a run that reached the fault. "
                "The review of the run judges each criterion."
                if outcome.state == OBSERVED
                else "The control states this state and its reason."
            ),
        }
        self.journal.document["finishedAt"] = core.format_instant(self.port.now())
        self.journal.document["kept"] = self.port.keep(self.run_id, self.work)
        self.journal.write()
        return outcome

    def _refuse(self, step: str, findings: list[str], reason: str = "") -> None:
        self.journal.step(step, self.port.now(), findings)
        raise _Stop(REFUSED, reason or "precondition-not-held", step)

    def _hold(self, step: str, findings: list[str], **facts: Any) -> None:
        if findings:
            self._refuse(step, findings)
        self.journal.step(step, self.port.now(), [], **facts)

    def _procedure(self) -> None:
        self._p1()
        self._p2()
        self._p3()
        self._p4("before-install")
        self._p5()
        self._p6()
        self._p7()
        self.start_reading = self._p8("start")
        if self.start_reading is None:
            self._refuse("P8", ["the start reading of the clocks is unusable"])
        self._collection()
        target = self._stable_window_and_target()
        started, finished = self._fault(target)
        self._declare(started, finished)
        self._observe(finished)
        self._p8("end")
        self._cleanup()

    # ------------------------------------------------------------------
    # P1 to P8
    # ------------------------------------------------------------------

    def _p1(self) -> None:
        head = self.port.head()
        clean = self.port.clean()
        checks = {module: self.port.check(module) for module in P1_CHECKS}
        changes = self.port.changes(self.plan.record_path)
        findings = core.repository_findings(
            head=head, clean=clean, checks=checks, changes_exit=changes
        )
        self._hold("P1", findings, executingRevision=head)
        assert head is not None
        self.head = head

    def _p2(self) -> None:
        desired = self.port.desired_revision()
        equal = None
        digests: dict[str, str | None] = {}
        if desired is not None:
            equal = self.port.delivery_paths_equal(desired)
            digests = self.port.desired_state_digests(
                desired, self.plan.desired_state_path
            )
        findings = core.desired_state_findings(
            self.plan, desired=desired, paths_equal=equal, digests=digests
        )
        self._hold("P2", findings, desiredRevision=desired, desiredStateFiles=digests)
        assert desired is not None
        self.desired = desired

    def _p3(self) -> None:
        target = self.port.status("target")
        namespaces = _names(self.port.read("namespaces"))
        crds = _names(self.port.read("crds"))
        findings = core.cluster_findings(
            self.plan,
            target_exit=target,
            namespaces=namespaces,
            controller_namespace=self.controller_namespace,
        )
        if crds is None:
            findings.append("the custom resource definitions were not read")
        self._hold("P3", findings)
        assert namespaces is not None and crds is not None
        self.namespaces, self.crds = namespaces, crds

    def _p4(self, reading: str) -> None:
        name = f"{self.run_id}-{reading}"
        status = self.port.status("capacity", name)
        record = _json(self.port.read("capacity-record", name))
        findings = core.capacity_findings(
            self.plan,
            exit_status=status,
            record=record if isinstance(record, dict) else None,
        )
        self._hold(f"P4 {reading}", findings, collection=name)

    def _p5(self) -> None:
        # From here on the cleanup removes what the preparation installed.
        self.installed = True
        for act in PREPARATION:
            status = self.port.act(act)
            if status != 0:
                self._refuse("P5", [f"the preparation step {act} exited {status}"])
        digest = (self.port.read("api-image-digest") or "").strip()
        if not digest.startswith("sha256:"):
            self._refuse("P5", ["the API image digest was not read"])
        self._p4("before-apply")
        status = self.port.act("application-apply", digest)
        if status != 0:
            self._refuse("P5", [f"the Application apply exited {status}"])
        self.journal.step("P5", self.port.now(), [], apiImageDigest=digest)

    def _p6(self) -> None:
        deadline = self.port.now() + timedelta(seconds=core.TOPOLOGY_WAIT_SECONDS)
        while True:
            findings = core.topology_findings(
                self.plan,
                deployments=_json(self.port.read("deployments")),
                slices=_json(self.port.read("endpoints")),
                application=_json(self.port.read("application")),
                desired=self.desired,
            )
            if not findings:
                break
            if self.port.now() >= deadline:
                self._refuse("P6", findings)
            self.port.sleep(TOPOLOGY_POLL_SECONDS)
        if self.port.status("application-verify") != 0:
            self._refuse(
                "P6", ["the live Application or project differs from the manifests"]
            )
        self.journal.step("P6", self.port.now(), [])

    def _p7(self) -> None:
        findings = core.provenance_findings(
            self.plan, _json(self.port.read("provenance", self.desired))
        )
        pods = _json(self.port.read("runtime-pods"))
        logs = {
            name: self.port.read("verify-log", name)
            for name, _, tier in core.pod_identities(pods)
            if tier == core.RUNTIME_TIER
        }
        findings.extend(core.model_findings(self.plan, pods, logs))
        self._hold("P7", findings, releaseId=self.plan.release_id)
        # The abort conditions compare later readings with these.
        self.prepared_namespaces = _names(self.port.read("namespaces")) or ()
        self.prepared_crds = _names(self.port.read("crds")) or ()

    def _p8(self, reading: str) -> core.ClockReading | None:
        parsed = core.clock_reading(self.port.read("clock"))
        readings = self.journal.document.setdefault("clockReadings", {})
        readings[reading] = _reading(parsed)
        if reading == "end":
            bound = core.clock_bound_ms(self.start_reading, parsed)
            readings["boundMs"] = bound
            readings["reason"] = None if bound is not None else "clock-reading-missing"
        self.journal.write()
        return parsed

    # ------------------------------------------------------------------
    # The collection, the stable window, and the fault
    # ------------------------------------------------------------------

    def _record(
        self, kind: str, code: str | None = None, subject: str | None = None
    ) -> datetime:
        event = events.record(
            self.events_path,
            kind,
            "control-process",
            code=code,
            subject=subject,
            now=self.port.now,
        )
        instant = core.parse_instant(event["recordedAt"])
        assert instant is not None
        return instant

    def _collection(self) -> None:
        events.open_log(
            self.events_path, core.EXPERIMENT_ID, self.run_id, now=self.port.now
        )
        self.events_open = True
        for name, samples, interval in (
            ("timeline", core.TIMELINE_SAMPLES, core.TIMELINE_INTERVAL_SECONDS),
            ("telemetry", core.TELEMETRY_SAMPLES, core.TELEMETRY_INTERVAL_SECONDS),
        ):
            # The second collector starts when the first samples: both rewrite the
            # kubeconfig of the target when they start.
            collector = self.port.start(name, self.run_id, str(samples), str(interval))
            self.collectors[name] = collector
            waited = 0
            while "samples: " not in collector.output():
                if not collector.alive() or waited >= SAMPLING_BOUND_SECONDS:
                    self._refuse(
                        "collection", [f"the {name} collector did not start sampling"]
                    )
                self.port.sleep(1)
                waited += 1
        self.port.sleep(core.COLLECTOR_LEAD_SECONDS)
        self.runner_started = True
        status = self.port.act(
            "runner-start",
            self.run_id,
            self.plan.release_id,
            str(self.plan.duration_seconds),
            str(self.plan.request_ceiling),
        )
        if status != 0:
            self._refuse("collection", [f"the runner start exited {status}"])
        self.journal.step("collection", self.port.now(), [])

    def _observation(self) -> core.Observation:
        now = self.port.now()
        return core.Observation(
            at=now,
            head=self.port.head(),
            clean=self.port.clean(),
            namespaces=_names(self.port.read("namespaces")),
            crds=_names(self.port.read("crds")),
            node_ready=core.nodes_ready(_json(self.port.read("nodes"))),
            runner_pod=_json(self.port.read("runner-pod", self.run_id)),
            runner_job=_json(self.port.read("runner-job", self.run_id)),
            application=_json(self.port.read("application")),
            claims=_json(self.port.read("claims")),
            window_ended=self.window_end is not None and now >= self.window_end,
        )

    def _watch(self) -> None:
        """Read the abort conditions once, and abort when one is crossed."""
        observation = self._observation()
        if observation.node_ready is not True:
            self.unanswered_since = self.unanswered_since or observation.at
        else:
            self.unanswered_since = None
        code = core.abort_code(
            self.plan,
            observation,
            head=self.head,
            namespaces=self.prepared_namespaces,
            crds=self.prepared_crds,
            desired=self.desired,
            unanswered_since=self.unanswered_since,
        )
        if code is not None:
            self.journal.step("abort", observation.at, [code])
            if self.events_open:
                self._record("run-aborted", code=code)
            raise _Stop(ABORTED, code, "abort")

    def _wait_until(self, instant: datetime) -> None:
        while self.port.now() < instant:
            remaining = (instant - self.port.now()).total_seconds()
            self.port.sleep(min(remaining, POLL_SECONDS))

    def _stable_window_and_target(self) -> core.Target:
        started_at = self.port.now()
        while self.runner_pod_start is None:
            self.runner_pod_start = core.runner_pod_start(
                _json(self.port.read("runner-pod", self.run_id))
            )
            if self.runner_pod_start is not None:
                break
            if self.port.now() - started_at > timedelta(
                seconds=core.LAST_CHECK_SECONDS
            ):
                self._refuse(
                    "stable window",
                    ["the runner pod did not start"],
                    "stable-window-not-reached",
                )
            self.port.sleep(POLL_SECONDS)
        checks: list[dict[str, Any]] = []
        self.journal.document["stableWindowChecks"] = checks
        held = False
        for offset in core.check_offsets():
            self._wait_until(self.runner_pod_start + timedelta(seconds=offset))
            self._watch()
            requests = core.caller_requests(
                self.port.read("runner-log", self.run_id), self.run_id
            )
            replicas = core.ready_replicas(_json(self.port.read("deployments")))
            now = self.port.now()
            held, why = core.stable_window(
                self.plan, requests, check_at=now, replicas=replicas
            )
            checks.append(
                {
                    "offsetSeconds": offset,
                    "at": core.format_instant(now),
                    "holds": held,
                    "why": why,
                }
            )
            self.journal.write()
            if held:
                break
        if not held:
            self._refuse(
                "stable window",
                [
                    "the stable pre-fault window did not hold by "
                    f"{core.LAST_CHECK_SECONDS} s"
                ],
                "stable-window-not-reached",
            )
        target = core.fault_target(_json(self.port.read("release-pods")))
        if target is None:
            self._refuse("F1", ["no runtime pod of the release is Ready"])
        assert target is not None
        self.journal.step(
            "F1",
            self.port.now(),
            [],
            target={"name": target.name, "uid": target.uid},
            pods=[
                {"name": name, "uid": uid, "tier": tier}
                for name, uid, tier in target.pods
            ],
        )
        return target

    def _fault(self, target: core.Target) -> tuple[datetime, datetime]:
        argv = ["kubectl", *core.fault_argv_tail(self.plan, target)]
        self.fault_reached = True
        if self.fault is None:
            at = self.port.now()
            self.journal.step(
                "F2-F4",
                at,
                [],
                dryRun=True,
                command=argv,
                statement=(
                    "A dry run issues no fault command and records no fault event."
                ),
            )
            return at, at
        if self.fault_issued:
            # The fault is injected once. A second attempt is an abort condition.
            raise _Stop(ABORTED, "abort-fault-differs", "F3")
        subject = f"pod/{target.name}"
        started = self._record(
            "fault-injection-started", code=core.FAULT_CODE, subject=subject
        )
        self.fault_issued = True
        status = self.fault.delete(target.name)
        finished = self._record(
            "fault-injection-finished", code=core.FAULT_CODE, subject=subject
        )
        self.journal.step("F2-F4", finished, [], command=argv, exitStatus=status)
        return started, finished

    def _declare(self, started: datetime, finished: datetime) -> None:
        """Write the declaration of the analysis before any evidence is read."""
        document = core.declaration(
            self.plan,
            run_id=self.run_id,
            desired=self.desired,
            started=started,
            finished=finished,
        )
        text = json.dumps(document, indent=2, sort_keys=True) + "\n"
        (self.work / DECLARATION_FILE).write_bytes(text.encode("utf-8"))
        self.window_end = core.window(started, finished)[1]

    def _observe(self, finished: datetime) -> None:
        """Issue no mutating command, and read the abort conditions until the window ends."""
        assert self.window_end is not None and self.runner_pod_start is not None
        limit = finished + timedelta(seconds=core.OBSERVATION_LIMIT_SECONDS)
        next_check = self.port.now()
        while self.port.now() < self.window_end:
            if self.port.now() >= next_check:
                self._watch()
                next_check = self.port.now() + timedelta(
                    seconds=core.CHECK_INTERVAL_SECONDS
                )
            self.port.sleep(POLL_SECONDS)
        self.journal.step(
            "observation",
            self.port.now(),
            [],
            observationLimit=core.format_instant(limit),
            windowEnd=core.format_instant(self.window_end),
        )
        runner_end = self.runner_pod_start + timedelta(
            seconds=self.plan.duration_seconds + JOB_END_SLACK_SECONDS
        )
        while self.port.now() < runner_end and not core.job_ended(
            _json(self.port.read("runner-job", self.run_id))
        ):
            self.port.sleep(core.CHECK_INTERVAL_SECONDS)

    # ------------------------------------------------------------------
    # The cleanup
    # ------------------------------------------------------------------

    def _collect_and_stop_runner(self) -> list[str]:
        """C1: collect the caller record, then remove the objects of the run."""
        if not self.runner_started:
            return []
        findings = []
        status = self.port.act("runner-collect", self.run_id)
        if status != 0:
            findings.append(f"the caller record collection exited {status}")
        self.port.act("runner-cleanup", self.run_id)
        self.runner_started = False
        left = _names(self.port.read("run-objects", self.run_id))
        if left:
            findings.append(f"objects of the run are left: {', '.join(left)}")
        return findings

    def _wait_collectors(self) -> dict[str, int | None]:
        deadline = self.port.now() + timedelta(seconds=COLLECTOR_BOUND_SECONDS)
        exits: dict[str, int | None] = {}
        for name, collector in self.collectors.items():
            remaining = max(0.0, (deadline - self.port.now()).total_seconds())
            exits[name] = collector.wait(remaining)
            if exits[name] is None:
                collector.stop()
        return exits

    def _close_events(self) -> None:
        if self.events_open:
            events.close_log(self.events_path, now=self.port.now)
            self.events_open = False

    def _cleanup(self) -> None:
        """C1 to C4 after a run that reached the end of its window."""
        self.journal.step("C1", self.port.now(), self._collect_and_stop_runner())
        exits = self._wait_collectors()
        self._close_events()
        self.journal.step("C2", self.port.now(), [], collectorExits=exits)
        self._verify_before_removal()
        self._remove()

    def _verify_before_removal(self) -> None:
        """C3, recorded as remaining drift and not as a refusal: the run is over."""
        drift = []
        if self.port.status("application-verify") != 0:
            drift.append("the live Application or project differs from the manifests")
        replicas = core.ready_replicas(_json(self.port.read("deployments")))
        for tier, expected in self.plan.replicas.items():
            if replicas[tier] != expected:
                drift.append(f"{tier} readyReplicas is {replicas[tier]}")
        state = core.application_state(_json(self.port.read("application")))
        if state["revision"] != self.desired or state["sync"] != "Synced":
            drift.append("the Application is not Synced at the desired revision")
        self.journal.step("C3", self.port.now(), drift, recordedAsDrift=True)

    def _remove(self) -> None:
        """C4: remove the release, the controller, and the prerequisite layer."""
        status = self.port.act("release-remove")
        namespaces = _names(self.port.read("namespaces"))
        crds = _names(self.port.read("crds"))
        findings = []
        if status != 0:
            findings.append(f"the removal exited {status}")
        if namespaces != self.namespaces:
            findings.append("the namespaces differ from those read before P5")
        if crds != self.crds:
            findings.append(
                "the custom resource definitions differ from those read before P5"
            )
        self.installed = False
        self.journal.step("C4", self.port.now(), findings)

    def _after_stop(self, stop: _Stop) -> None:
        """The cleanup after a refusal or an abort. Each step is recorded.

        After an abort the collectors run to their samples, because their streams
        are evidence of the run. After a refusal no fault was injected, and the
        collectors are stopped.
        """
        findings = self._collect_and_stop_runner()
        if self.collectors:
            if stop.state == ABORTED:
                exits = self._wait_collectors()
            else:
                for collector in self.collectors.values():
                    collector.stop()
                exits = {name: None for name in self.collectors}
            self.journal.document["collectorExits"] = exits
        self._close_events()
        self.journal.step("cleanup", self.port.now(), findings)
        if self.installed:
            self._remove()
