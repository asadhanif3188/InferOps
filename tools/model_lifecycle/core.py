"""The model lifecycle: which state the deployment is in, and what each probe says.

The pieces this reads were all decided elsewhere. `ADR 0002` selected the model
and the runtime; the acquisition workflow owns the cache; the container package
owns the startup budget, the readiness path, and the liveness probe; and
:mod:`inferops.api.lifecycle` owns the drain. What did not exist was the single
record that says how those fit together, so this module and the record beside it
are that: **one ordered state model spanning artifact and runtime, with the
answer each probe gives in each state written down rather than inferred.**

**The state model exists because two probes have to disagree.** The runtime
answers ``503`` on its health endpoint while it loads the model. That is correct
readiness and wrong liveness, and a liveness probe aimed at the same endpoint
restarts a healthy process mid-load and never converges. So
``runtime-loading`` records ``liveness: pass`` and ``readiness: false``, and
:func:`load_lifecycle` refuses a record where the two agree there. The rule is a
validated invariant of committed data, not a paragraph.

**The record is checked against the things it describes, in both directions.**
The probe ports, statuses, and paths are compared to the container package; the
startup budget and stop timeout to the same; the drain budget to the API's own
default; the cache root to the model source record. A lifecycle document that
drifted from any of them fails to load, which is what stops this becoming a
fourth place the same numbers are written down.

**Measurement is bounded, authorized, and does not invent a cache miss.** The
comparison :func:`compare_starts` runs is two real starts of the same pinned
container against the same verified artifact — both of them cache *hits*. What
differs is that the artifact is read end to end between them, so the second start
finds the host's own file cache warm. A real cache *miss* is a 1.71 GiB download,
which this module never performs and never simulates: the miss and partial rows
of the cache model are exercised with synthetic bytes by the acquisition suite
and are reported as such.

**Cleanup is scoped to the directory this tool writes.** :func:`clean_results`
removes ``.cache/inferops/lifecycle`` and refuses anything else. The model cache
is refused first and by name, before the pinned-directory equality that would
otherwise make that refusal unreachable, and it is compared against the cache
root the loaded record carries rather than against a copy of the path kept here.
Deleting the artifact is the acquisition workflow's own confirmed operation, and
a lifecycle tool that could reach it would be one bad path away from turning a
measurement into a 1.71 GiB re-download.
"""

from __future__ import annotations

import json
import platform
import shutil
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from inferops.api.lifecycle import DEFAULT_DRAIN_TIMEOUT_MS
from tools.model_acquisition.core import (
    ModelAcquisitionError,
    ModelManifest,
    load_manifest,
    verify_artifact,
)
from tools.runtime_packaging.core import (
    Clock,
    CommandRunner,
    HttpGet,
    HttpPost,
    HttpResponse,
    RuntimeEndpointUnavailable,
    RuntimePackage,
    RuntimePackagingError,
    Sleeper,
    TcpProbe,
    container_is_running,
    inference_probe,
    load_runtime_package,
    model_artifact_path,
    owned_container_exists,
    start,
    stop,
    tcp_is_live,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_PATH = REPO_ROOT / "deploy/serving/lifecycle/model-lifecycle.v1.json"

EXPECTED_SCHEMA_VERSION = "inferops.io/v1alpha1"
EXPECTED_LIFECYCLE_ID = "inferops-local-model-lifecycle"
EXPECTED_PACKAGE_REF = "deploy/serving/runtime/container-package.v1.json"
EXPECTED_MODEL_SOURCE_REF = "docs/serving/model-source.v1.json"
EXPECTED_DOCUMENT_REF = "docs/serving/model-lifecycle.md"
EXPECTED_EVIDENCE_CLASS = "local-real-cpu"
EXPECTED_CEILING = "C2"

#: The only directory this tool is allowed to create or remove. It is a sibling
#: of the model cache and never the model cache itself.
EXPECTED_RESULT_DIRECTORY = Path(".cache/inferops/lifecycle")

#: The cache root the acquisition workflow owns. Named here so that the cleanup
#: guard can refuse it by identity rather than by hoping the paths differ.
MODEL_CACHE_DIRECTORY = Path(".cache/inferops/models")

#: The startup and shutdown steps, in the only order this V1 accepts. They are
#: identifiers rather than sentences so that rewording a record's prose is a
#: documentation change and reordering its steps is a loading failure.
STARTUP_STEPS: tuple[str, ...] = (
    "verify-image-local",
    "establish-cache-state",
    "create-container",
    "poll-to-readiness",
)

#: The first entry is the whole graceful-shutdown property: readiness goes false
#: before anything is drained. The last is the one that leaves no residue.
SHUTDOWN_STEPS: tuple[str, ...] = (
    "stop-accepting-and-report-unready",
    "drain-within-budget",
    "close-adapter-transport",
    "stop-and-remove-container",
)

#: How often the observation loop asks both probes. Faster than the package's own
#: readiness poll because the point of the loop is to catch the window in which
#: liveness passes and readiness does not.
OBSERVATION_POLL_SECONDS = 0.25

#: A cap on the samples one observation retains, so an unexpectedly long load
#: cannot write an unbounded result file. Generous against the bound that
#: actually stops the loop — the package's startup budget divided by the poll
#: interval — because reaching it means the loop did not behave as this module
#: believes, and that is a refusal rather than a truncation.
MAXIMUM_SAMPLES = 20_000


class ModelLifecycleError(RuntimeError):
    """An expected, safely reportable lifecycle refusal."""


class LifecycleRefused(ModelLifecycleError):
    """A real-runtime operation was requested without its confirmation."""


class LifecycleState(StrEnum):
    """The eight states a deployment passes through, in order."""

    ARTIFACT_ABSENT = "artifact-absent"
    ARTIFACT_PARTIAL = "artifact-partial"
    ARTIFACT_VERIFIED = "artifact-verified"
    RUNTIME_STARTING = "runtime-starting"
    RUNTIME_LOADING = "runtime-loading"
    RUNTIME_READY = "runtime-ready"
    RUNTIME_DRAINING = "runtime-draining"
    RUNTIME_STOPPED = "runtime-stopped"


class CacheState(StrEnum):
    """What the documented model cache holds, established without a network call."""

    MISS = "miss"
    PARTIAL = "partial"
    HIT = "hit"


class ProbeOutcome(StrEnum):
    """What a liveness probe would answer in a state."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not-applicable"


#: The order the states are declared in, which is the order a deployment reaches
#: them. Compared against the record so that a reordered document fails to load.
STATE_ORDER: tuple[LifecycleState, ...] = tuple(LifecycleState)


@dataclass(frozen=True, slots=True)
class StateRule:
    """One state and the answer every probe gives while a deployment is in it."""

    state: LifecycleState
    phase: str
    liveness: ProbeOutcome
    readiness: bool
    accepts_work: bool
    description: str


@dataclass(frozen=True, slots=True)
class Transition:
    """One declared move between two states, and what causes it."""

    source: LifecycleState
    target: LifecycleState
    trigger: str


@dataclass(frozen=True, slots=True)
class CacheRule:
    """One cache state, the lifecycle state it maps to, and whether it needs a network."""

    cache_state: CacheState
    maps_to: LifecycleState
    requires_network: bool
    description: str


@dataclass(frozen=True, slots=True)
class ModelLifecycle:
    """The validated lifecycle record, agreeing with everything it describes."""

    schema_version: str
    lifecycle_id: str
    package_ref: str
    model_source_ref: str
    document_ref: str
    states: tuple[StateRule, ...]
    transitions: tuple[Transition, ...]
    liveness_kind: str
    liveness_port: int
    liveness_passes_in: tuple[LifecycleState, ...]
    readiness_path: str
    readiness_ready_status: int
    readiness_loading_status: int
    readiness_true_in: tuple[LifecycleState, ...]
    cache_root: Path
    cache_rules: tuple[CacheRule, ...]
    startup_budget_ms: int
    startup_poll_interval_ms: int
    startup_steps: tuple[str, ...]
    startup_order: tuple[str, ...]
    drain_timeout_ms: int
    stop_timeout_seconds: int
    shutdown_steps: tuple[str, ...]
    shutdown_order: tuple[str, ...]
    artifact_survives_restart: bool
    readiness_resets_on_restart: bool
    reacquires_on_miss: bool
    restart_description: str
    result_directory: Path
    raw_file: str
    summary_file: str
    evidence_class: str
    certification_ceiling: str
    observation_ids: tuple[str, ...]

    def rule(self, state: LifecycleState) -> StateRule:
        """The rule for one state. A missing state is a defect, not a default."""
        for rule in self.states:
            if rule.state is state:
                return rule
        raise ModelLifecycleError(f"the lifecycle record declares no state {state}")


@dataclass(frozen=True, slots=True)
class CacheObservation:
    """What the documented cache holds right now, established offline."""

    cache_state: CacheState
    artifact: Path
    bytes_present: int
    expected_bytes: int
    verified: bool

    @property
    def lifecycle_state(self) -> LifecycleState:
        """The lifecycle state this cache state maps to."""
        if self.cache_state is CacheState.HIT:
            return LifecycleState.ARTIFACT_VERIFIED
        if self.cache_state is CacheState.PARTIAL:
            return LifecycleState.ARTIFACT_PARTIAL
        return LifecycleState.ARTIFACT_ABSENT


@dataclass(frozen=True, slots=True)
class ProbeSample:
    """Both probes asked at one moment, which is the only way to compare them."""

    elapsed_ms: int
    liveness: bool
    readiness_status: int


@dataclass(frozen=True, slots=True)
class StartObservation:
    """One measured start, from container creation to a removed container."""

    observation_id: str
    cache_state: CacheState
    artifact_bytes: int
    ready_status: int
    loading_status: int
    create_ms: int
    first_liveness_ms: int | None
    ready_ms: int
    inference_ms: int
    inference_status: int
    stop_ms: int
    samples: tuple[ProbeSample, ...]

    @property
    def loading_samples(self) -> tuple[ProbeSample, ...]:
        """The samples taken while the runtime was still answering that it loads.

        The status is carried on the observation rather than written here, so
        that this cannot become a fourth copy of a number the package pins.
        """
        return tuple(
            sample
            for sample in self.samples
            if sample.readiness_status == self.loading_status
        )

    @property
    def liveness_held_while_loading(self) -> bool:
        """Whether liveness passed at least once while readiness was still false.

        This is the measurement behind "liveness does not restart a healthy
        loading process": the two probes were asked together, and there was a
        window in which one said live and the other said not ready.
        """
        return any(sample.liveness for sample in self.loading_samples)

    @property
    def readiness_false_until_ready(self) -> bool:
        """Whether every sample but the last reported the runtime's loading status.

        Derived from the loading count rather than from "no early sample said
        ready", because the sampling loop returns on the first ready answer and
        so that weaker form is true of every observation this tool can build —
        a property that cannot fail is not worth publishing. This one fails on a
        sample that reached no socket, or on any status other than the two the
        record publishes.
        """
        if not self.samples:
            return False
        return (
            len(self.loading_samples) == len(self.samples) - 1
            and self.samples[-1].readiness_status == self.ready_status
        )

    @property
    def liveness_never_dropped_after_it_passed(self) -> bool:
        """Whether liveness, once passing, kept passing for the rest of the load.

        A liveness probe with any sane failure threshold does not restart a
        process that never stopped answering. A single drop after the first pass
        is what would make the restart risk real, so it is measured rather than
        assumed.
        """
        seen = False
        for sample in self.samples:
            if sample.liveness:
                seen = True
            elif seen:
                return False
        return True


@dataclass(frozen=True, slots=True)
class Environment:
    """The host facts a timing figure is only meaningful alongside."""

    platform: str
    python_version: str
    engine_version: str | None
    image_reference: str
    model_revision: str
    model_sha256: str


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """A cold and a warm start of the same artifact, and the verification between."""

    lifecycle_id: str
    started_at: str
    environment: Environment
    cold: StartObservation
    warm: StartObservation
    verify_ms: int
    verified_before_warm: bool
    verified_after_warm: bool

    @property
    def artifact_survived_restart(self) -> bool:
        """Whether the same verified bytes were still in place after both starts."""
        return (
            self.verified_before_warm
            and self.verified_after_warm
            and self.cold.artifact_bytes == self.warm.artifact_bytes
            and self.cold.cache_state is CacheState.HIT
            and self.warm.cache_state is CacheState.HIT
        )


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """What scoped cleanup found in its own directory, and whether it removed it."""

    directory: Path
    bytes_found: int
    removed: bool


# --------------------------------------------------------------------------
# Reading the record
# --------------------------------------------------------------------------


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ModelLifecycleError(f"lifecycle field '{field}' must be an object")
    return cast(dict[str, Any], value)


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ModelLifecycleError(
            f"lifecycle field '{field}' must be a non-empty array"
        )
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ModelLifecycleError(f"lifecycle field '{field}' must be a string")
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    return tuple(_string(item, field) for item in _array(value, field))


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ModelLifecycleError(
            f"lifecycle field '{field}' must be an integer of at least {minimum}"
        )
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ModelLifecycleError(f"lifecycle field '{field}' must be a boolean")
    return value


def _state(value: Any, field: str) -> LifecycleState:
    text = _string(value, field)
    try:
        return LifecycleState(text)
    except ValueError as error:
        raise ModelLifecycleError(
            f"lifecycle field '{field}' names an unknown state"
        ) from error


def _read(path: Path) -> dict[str, Any]:
    try:
        document: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ModelLifecycleError("the lifecycle record is unreadable") from error
    return _object(document, "root")


def load_lifecycle(
    path: Path = LIFECYCLE_PATH,
    *,
    repo_root: Path = REPO_ROOT,
) -> ModelLifecycle:
    """Load the lifecycle record and refuse drift from everything it describes."""
    record = _read(path)
    probes = _object(record.get("probes"), "probes")
    liveness = _object(probes.get("liveness"), "probes.liveness")
    readiness = _object(probes.get("readiness"), "probes.readiness")
    cache = _object(record.get("cache"), "cache")
    startup = _object(record.get("startup"), "startup")
    shutdown = _object(record.get("shutdown"), "shutdown")
    restart = _object(record.get("restart"), "restart")
    measurement = _object(record.get("measurement"), "measurement")

    lifecycle = ModelLifecycle(
        schema_version=_string(record.get("schemaVersion"), "schemaVersion"),
        lifecycle_id=_string(record.get("lifecycleId"), "lifecycleId"),
        package_ref=_string(record.get("packageRef"), "packageRef"),
        model_source_ref=_string(record.get("modelSourceRef"), "modelSourceRef"),
        document_ref=_string(record.get("documentRef"), "documentRef"),
        states=_states(record.get("states")),
        transitions=_transitions(record.get("transitions")),
        liveness_kind=_string(liveness.get("kind"), "probes.liveness.kind"),
        liveness_port=_integer(liveness.get("port"), "probes.liveness.port"),
        liveness_passes_in=tuple(
            _state(item, "probes.liveness.passesIn")
            for item in _array(liveness.get("passesIn"), "probes.liveness.passesIn")
        ),
        readiness_path=_string(readiness.get("path"), "probes.readiness.path"),
        readiness_ready_status=_integer(
            readiness.get("readyStatus"), "probes.readiness.readyStatus"
        ),
        readiness_loading_status=_integer(
            readiness.get("loadingStatus"), "probes.readiness.loadingStatus"
        ),
        readiness_true_in=tuple(
            _state(item, "probes.readiness.trueIn")
            for item in _array(readiness.get("trueIn"), "probes.readiness.trueIn")
        ),
        cache_root=Path(_string(cache.get("rootPath"), "cache.rootPath")),
        cache_rules=_cache_rules(cache.get("states")),
        startup_budget_ms=_integer(startup.get("budgetMs"), "startup.budgetMs"),
        startup_poll_interval_ms=_integer(
            startup.get("pollIntervalMs"), "startup.pollIntervalMs"
        ),
        startup_steps=_ordered_steps(startup.get("order"), "startup.order")[0],
        startup_order=_ordered_steps(startup.get("order"), "startup.order")[1],
        drain_timeout_ms=_integer(
            shutdown.get("drainTimeoutMs"), "shutdown.drainTimeoutMs"
        ),
        stop_timeout_seconds=_integer(
            shutdown.get("stopTimeoutSeconds"), "shutdown.stopTimeoutSeconds"
        ),
        shutdown_steps=_ordered_steps(shutdown.get("order"), "shutdown.order")[0],
        shutdown_order=_ordered_steps(shutdown.get("order"), "shutdown.order")[1],
        artifact_survives_restart=_boolean(
            restart.get("artifactSurvives"), "restart.artifactSurvives"
        ),
        readiness_resets_on_restart=_boolean(
            restart.get("readinessResets"), "restart.readinessResets"
        ),
        reacquires_on_miss=_boolean(
            restart.get("reacquiresOnMiss"), "restart.reacquiresOnMiss"
        ),
        restart_description=_string(restart.get("description"), "restart.description"),
        result_directory=Path(
            _string(measurement.get("directory"), "measurement.directory")
        ),
        raw_file=_string(measurement.get("rawFile"), "measurement.rawFile"),
        summary_file=_string(measurement.get("summaryFile"), "measurement.summaryFile"),
        evidence_class=_string(
            measurement.get("evidenceClass"), "measurement.evidenceClass"
        ),
        certification_ceiling=_string(
            measurement.get("certificationCeiling"),
            "measurement.certificationCeiling",
        ),
        observation_ids=tuple(
            _string(
                _object(item, "measurement.observations[]").get("observationId"),
                "measurement.observations[].observationId",
            )
            for item in _array(
                measurement.get("observations"), "measurement.observations"
            )
        ),
    )
    _validate(lifecycle, repo_root=repo_root)
    return lifecycle


def _states(value: Any) -> tuple[StateRule, ...]:
    rules: list[StateRule] = []
    for item in _array(value, "states"):
        entry = _object(item, "states[]")
        liveness = _string(entry.get("liveness"), "states[].liveness")
        try:
            outcome = ProbeOutcome(liveness)
        except ValueError as error:
            raise ModelLifecycleError(
                "a state declares a liveness outcome this model does not publish"
            ) from error
        rules.append(
            StateRule(
                state=_state(entry.get("stateId"), "states[].stateId"),
                phase=_string(entry.get("phase"), "states[].phase"),
                liveness=outcome,
                readiness=_boolean(entry.get("readiness"), "states[].readiness"),
                accepts_work=_boolean(entry.get("acceptsWork"), "states[].acceptsWork"),
                description=_string(entry.get("description"), "states[].description"),
            )
        )
    return tuple(rules)


def _ordered_steps(value: Any, field: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split an ordered list of `{step, description}` into its ids and its prose."""
    steps: list[str] = []
    descriptions: list[str] = []
    for item in _array(value, field):
        entry = _object(item, f"{field}[]")
        steps.append(_string(entry.get("step"), f"{field}[].step"))
        descriptions.append(_string(entry.get("description"), f"{field}[].description"))
    return tuple(steps), tuple(descriptions)


def _transitions(value: Any) -> tuple[Transition, ...]:
    return tuple(
        Transition(
            source=_state(_object(item, "transitions[]").get("from"), "transitions[]"),
            target=_state(_object(item, "transitions[]").get("to"), "transitions[]"),
            trigger=_string(
                _object(item, "transitions[]").get("trigger"), "transitions[].trigger"
            ),
        )
        for item in _array(value, "transitions")
    )


def _cache_rules(value: Any) -> tuple[CacheRule, ...]:
    rules: list[CacheRule] = []
    for item in _array(value, "cache.states"):
        entry = _object(item, "cache.states[]")
        name = _string(entry.get("cacheState"), "cache.states[].cacheState")
        try:
            cache_state = CacheState(name)
        except ValueError as error:
            raise ModelLifecycleError(
                "the cache model names a state this tool does not publish"
            ) from error
        rules.append(
            CacheRule(
                cache_state=cache_state,
                maps_to=_state(entry.get("mapsTo"), "cache.states[].mapsTo"),
                requires_network=_boolean(
                    entry.get("requiresNetwork"), "cache.states[].requiresNetwork"
                ),
                description=_string(
                    entry.get("description"), "cache.states[].description"
                ),
            )
        )
    return tuple(rules)


def _validate(lifecycle: ModelLifecycle, *, repo_root: Path) -> None:
    """Hold the record to its identity, its own invariants, and every neighbour."""
    if lifecycle.schema_version != EXPECTED_SCHEMA_VERSION:
        raise ModelLifecycleError(
            "the lifecycle record has an unsupported schema version"
        )
    if lifecycle.lifecycle_id != EXPECTED_LIFECYCLE_ID:
        raise ModelLifecycleError("the lifecycle record has an unexpected identifier")
    for field, actual, expected in (
        ("packageRef", lifecycle.package_ref, EXPECTED_PACKAGE_REF),
        ("modelSourceRef", lifecycle.model_source_ref, EXPECTED_MODEL_SOURCE_REF),
        ("documentRef", lifecycle.document_ref, EXPECTED_DOCUMENT_REF),
    ):
        if actual != expected:
            raise ModelLifecycleError(
                f"the lifecycle record's {field} is not the accepted one"
            )
        if not (repo_root / actual).is_file():
            raise ModelLifecycleError(f"the lifecycle record's {field} does not exist")

    _validate_states(lifecycle)
    _validate_transitions(lifecycle)
    _validate_against_package(lifecycle)
    _validate_cache(lifecycle)
    _validate_measurement(lifecycle)


def _validate_states(lifecycle: ModelLifecycle) -> None:
    declared = tuple(rule.state for rule in lifecycle.states)
    if len(set(declared)) != len(declared):
        raise ModelLifecycleError("the lifecycle record declares a state twice")
    if declared != STATE_ORDER:
        raise ModelLifecycleError(
            "the lifecycle record's states are not the accepted set in the accepted order"
        )

    ready = [rule.state for rule in lifecycle.states if rule.readiness]
    if ready != [LifecycleState.RUNTIME_READY]:
        raise ModelLifecycleError(
            "exactly one state may report readiness, and it is runtime-ready"
        )
    accepting = [rule.state for rule in lifecycle.states if rule.accepts_work]
    if accepting != ready:
        raise ModelLifecycleError(
            "a state accepts work if and only if it reports readiness"
        )

    # The property the whole record exists for: while the model loads, the
    # liveness probe passes and readiness is false. A record where the two agree
    # would describe a deployment a liveness probe restarts mid-load.
    loading = lifecycle.rule(LifecycleState.RUNTIME_LOADING)
    if loading.liveness is not ProbeOutcome.PASS or loading.readiness:
        raise ModelLifecycleError(
            "runtime-loading must pass liveness and report readiness false"
        )
    draining = lifecycle.rule(LifecycleState.RUNTIME_DRAINING)
    if draining.liveness is not ProbeOutcome.PASS or draining.readiness:
        raise ModelLifecycleError(
            "runtime-draining must pass liveness and report readiness false"
        )
    if lifecycle.rule(LifecycleState.RUNTIME_STOPPED).liveness is not ProbeOutcome.FAIL:
        raise ModelLifecycleError("runtime-stopped must fail liveness")
    for rule in lifecycle.states:
        if (
            rule.phase == "artifact"
            and rule.liveness is not ProbeOutcome.NOT_APPLICABLE
        ):
            raise ModelLifecycleError(
                "an artifact state has no process for a liveness probe to reach"
            )

    passing = {
        rule.state for rule in lifecycle.states if rule.liveness is ProbeOutcome.PASS
    }
    if set(lifecycle.liveness_passes_in) != passing:
        raise ModelLifecycleError(
            "the liveness probe's declared states disagree with the state table"
        )
    if set(lifecycle.readiness_true_in) != set(ready):
        raise ModelLifecycleError(
            "the readiness probe's declared states disagree with the state table"
        )


def _validate_transitions(lifecycle: ModelLifecycle) -> None:
    seen: set[tuple[LifecycleState, LifecycleState]] = set()
    for transition in lifecycle.transitions:
        if transition.source is transition.target:
            raise ModelLifecycleError("a transition may not name one state twice")
        edge = (transition.source, transition.target)
        if edge in seen:
            raise ModelLifecycleError(
                "the lifecycle record declares a transition twice"
            )
        seen.add(edge)

    reachable = {LifecycleState.ARTIFACT_ABSENT}
    changed = True
    while changed:
        changed = False
        for transition in lifecycle.transitions:
            if transition.source in reachable and transition.target not in reachable:
                reachable.add(transition.target)
                changed = True
    unreachable = set(STATE_ORDER) - reachable
    if unreachable:
        raise ModelLifecycleError(
            "the lifecycle record declares a state nothing reaches: "
            + ", ".join(sorted(unreachable))
        )
    # The restart edge is what makes "restart behaviour is predictable" a
    # property of the record rather than a sentence in a document.
    if (LifecycleState.RUNTIME_STOPPED, LifecycleState.RUNTIME_STARTING) not in seen:
        raise ModelLifecycleError("the lifecycle record declares no restart transition")
    if (LifecycleState.RUNTIME_READY, LifecycleState.RUNTIME_DRAINING) not in seen:
        raise ModelLifecycleError("the lifecycle record declares no drain transition")
    if (LifecycleState.RUNTIME_DRAINING, LifecycleState.RUNTIME_STOPPED) not in seen:
        raise ModelLifecycleError("a drain that never stops is not a shutdown")


def _validate_against_package(lifecycle: ModelLifecycle) -> None:
    package = load_runtime_package()
    if lifecycle.liveness_kind != package.liveness_kind:
        raise ModelLifecycleError("the liveness probe kind disagrees with the package")
    if lifecycle.liveness_port != package.liveness_port:
        raise ModelLifecycleError("the liveness probe port disagrees with the package")
    if lifecycle.readiness_path != package.readiness_path:
        raise ModelLifecycleError("the readiness path disagrees with the package")
    if lifecycle.readiness_ready_status != package.ready_status:
        raise ModelLifecycleError("the ready status disagrees with the package")
    if lifecycle.readiness_loading_status != package.loading_status:
        raise ModelLifecycleError("the loading status disagrees with the package")
    if lifecycle.startup_budget_ms != package.startup_budget_ms:
        raise ModelLifecycleError("the startup budget disagrees with the package")
    if lifecycle.startup_poll_interval_ms != package.poll_interval_ms:
        raise ModelLifecycleError(
            "the readiness poll interval disagrees with the package"
        )
    if lifecycle.stop_timeout_seconds != package.stop_timeout_seconds:
        raise ModelLifecycleError(
            "the container stop timeout disagrees with the package"
        )
    if lifecycle.drain_timeout_ms != DEFAULT_DRAIN_TIMEOUT_MS:
        raise ModelLifecycleError(
            "the drain budget disagrees with the API's own default"
        )


def _validate_cache(lifecycle: ModelLifecycle) -> None:
    manifest = load_manifest()
    if lifecycle.cache_root != manifest.cache_path:
        raise ModelLifecycleError(
            "the cache root disagrees with the model source record"
        )
    # The convenience constant is held to the record that owns the path. Without
    # this it would be a second, silent copy of something this module does not
    # own, and a moved cache would leave it pointing at the wrong directory.
    if manifest.cache_path != MODEL_CACHE_DIRECTORY:
        raise ModelLifecycleError(
            "this module's model-cache constant has drifted from the source record"
        )
    declared = tuple(rule.cache_state for rule in lifecycle.cache_rules)
    if set(declared) != set(CacheState) or len(declared) != len(set(declared)):
        raise ModelLifecycleError("the cache model must declare each cache state once")
    for rule in lifecycle.cache_rules:
        expected_network = rule.cache_state is not CacheState.HIT
        if rule.requires_network is not expected_network:
            raise ModelLifecycleError(
                "only a cache hit may proceed without a network connection"
            )
    mapping = {rule.cache_state: rule.maps_to for rule in lifecycle.cache_rules}
    if mapping != {
        CacheState.MISS: LifecycleState.ARTIFACT_ABSENT,
        CacheState.PARTIAL: LifecycleState.ARTIFACT_PARTIAL,
        CacheState.HIT: LifecycleState.ARTIFACT_VERIFIED,
    }:
        raise ModelLifecycleError("a cache state maps to the wrong lifecycle state")
    if not lifecycle.artifact_survives_restart:
        raise ModelLifecycleError(
            "an artifact that does not survive a restart makes every restart a download"
        )
    if not lifecycle.readiness_resets_on_restart:
        raise ModelLifecycleError(
            "a restart that inherits readiness reports a fresh process ready before it is"
        )
    if not lifecycle.reacquires_on_miss:
        raise ModelLifecycleError(
            "a restart against a missing artifact must reacquire rather than serve nothing"
        )


def _validate_measurement(lifecycle: ModelLifecycle) -> None:
    # This runs first, before the pinned-directory equality below. Ordered the
    # other way it would be unreachable — the equality already refuses every
    # directory that is not the managed one — and an unreachable guard is a
    # guard nobody can test. The failure it refuses is a cleanup that deletes
    # 1.71 GiB of model bytes.
    if lifecycle.result_directory == lifecycle.cache_root:
        raise ModelLifecycleError(
            "the measurement directory may not be the model cache"
        )
    if lifecycle.result_directory != EXPECTED_RESULT_DIRECTORY:
        raise ModelLifecycleError("the measurement directory is not the managed one")
    if lifecycle.result_directory.is_absolute():
        raise ModelLifecycleError(
            "the measurement directory must be workspace-relative"
        )
    if lifecycle.evidence_class != EXPECTED_EVIDENCE_CLASS:
        raise ModelLifecycleError(
            "the measurement declares an unexpected evidence class"
        )
    if lifecycle.certification_ceiling != EXPECTED_CEILING:
        raise ModelLifecycleError("the measurement declares an unexpected ceiling")
    if lifecycle.observation_ids != ("cold", "warm"):
        raise ModelLifecycleError("a comparison is exactly one cold and one warm start")
    if not lifecycle.startup_order or not lifecycle.shutdown_order:
        raise ModelLifecycleError("the startup and shutdown orders may not be empty")
    # Matched on step identifiers rather than on the prose beside them.
    # Substring-matching the description would make rewording the record a
    # loading failure, and would let a reworded step silently stop being checked.
    if lifecycle.shutdown_steps != SHUTDOWN_STEPS:
        raise ModelLifecycleError(
            "the shutdown order is not the accepted sequence: readiness false, "
            "then drain, then close the adapter, then remove the container"
        )
    if lifecycle.startup_steps != STARTUP_STEPS:
        raise ModelLifecycleError(
            "the startup order is not the accepted sequence: image, cache, "
            "container, then poll to readiness"
        )


# --------------------------------------------------------------------------
# Cache state, established without a network connection
# --------------------------------------------------------------------------


def observe_cache(
    manifest: ModelManifest | None = None,
    *,
    repo_root: Path = REPO_ROOT,
    verify: bool = False,
) -> CacheObservation:
    """Classify the documented cache. Opens no socket and downloads nothing.

    Args:
        verify: Whether to read the artifact end to end and compare its SHA-256.
            Left off by default because the read is 1.71 GiB and warms the host's
            own file cache, which is the variable a cold observation is measuring.
    """
    resolved = manifest or load_manifest()
    artifact = resolved.artifact_path(repo_root)
    partial = resolved.partial_path(repo_root)

    if artifact.is_file():
        size = artifact.stat().st_size
        # The byte count is checked first because it is the cheaper and more
        # specific answer: a truncated artifact should be reported as the wrong
        # size rather than as a digest that happened not to match.
        if size != resolved.expected_size_bytes:
            raise ModelLifecycleError(
                "the cached artifact does not match the pinned byte count"
            )
        verified = False
        if verify:
            try:
                verify_artifact(artifact, resolved)
            except ModelAcquisitionError as error:
                raise ModelLifecycleError(
                    "the cached artifact does not match the pinned source record"
                ) from error
            verified = True
        return CacheObservation(
            cache_state=CacheState.HIT,
            artifact=artifact,
            bytes_present=size,
            expected_bytes=resolved.expected_size_bytes,
            verified=verified,
        )
    if partial.is_file():
        return CacheObservation(
            cache_state=CacheState.PARTIAL,
            artifact=artifact,
            bytes_present=partial.stat().st_size,
            expected_bytes=resolved.expected_size_bytes,
            verified=False,
        )
    return CacheObservation(
        cache_state=CacheState.MISS,
        artifact=artifact,
        bytes_present=0,
        expected_bytes=resolved.expected_size_bytes,
        verified=False,
    )


# --------------------------------------------------------------------------
# One measured start
# --------------------------------------------------------------------------


def _require_confirmation(confirmed: bool) -> None:
    if not confirmed:
        raise LifecycleRefused(
            "operating the real runtime requires --confirm-real-runtime"
        )


def _elapsed_ms(clock: Clock, since: float) -> int:
    return max(0, round((clock() - since) * 1000))


def observe_start(
    lifecycle: ModelLifecycle,
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    observation_id: str,
    confirmed: bool,
    http_get: HttpGet,
    http_post: HttpPost,
    tcp_probe: TcpProbe | None = None,
    manifest: ModelManifest | None = None,
    repo_root: Path = REPO_ROOT,
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
) -> StartObservation:
    """Start the pinned container once, sample both probes together, then stop it.

    The container is removed in a ``finally``, so a failed observation does not
    leave a running runtime behind for the next one to collide with.
    """
    _require_confirmation(confirmed)
    if observation_id not in lifecycle.observation_ids:
        raise ModelLifecycleError("the lifecycle record declares no such observation")
    cache = observe_cache(manifest, repo_root=repo_root)
    if cache.cache_state is not CacheState.HIT:
        raise ModelLifecycleError(
            "a measured start requires the pinned artifact already in the cache; "
            "acquire it explicitly first"
        )

    started = clock()
    start(package, runner, confirmed=True, repo_root=repo_root)
    create_ms = _elapsed_ms(clock, started)
    try:
        samples = _sample_until_ready(
            lifecycle,
            package,
            runner,
            http_get=http_get,
            tcp_probe=tcp_probe,
            clock=clock,
            sleeper=sleeper,
            since=started,
        )
        ready_ms = samples[-1].elapsed_ms
        inference_started = clock()
        inference_status = inference_probe(package, http_post=http_post)
        inference_ms = _elapsed_ms(clock, inference_started)
    finally:
        stop_started = clock()
        removed = stop(package, runner, confirmed=True)
        stop_ms = _elapsed_ms(clock, stop_started)
        if not removed:
            # Raised inside the `finally` on purpose, so that an observation
            # which failed *and* leaked its container reports the leak. A
            # container left behind blocks every subsequent start; the failure
            # it replaces is chained onto this one rather than lost.
            raise ModelLifecycleError(
                "the measured container could not be verified removed"
            )

    first_liveness = next(
        (sample.elapsed_ms for sample in samples if sample.liveness), None
    )
    return StartObservation(
        observation_id=observation_id,
        cache_state=cache.cache_state,
        artifact_bytes=cache.bytes_present,
        ready_status=lifecycle.readiness_ready_status,
        loading_status=lifecycle.readiness_loading_status,
        create_ms=create_ms,
        first_liveness_ms=first_liveness,
        ready_ms=ready_ms,
        inference_ms=inference_ms,
        inference_status=inference_status,
        stop_ms=stop_ms,
        samples=samples,
    )


def _sample_until_ready(
    lifecycle: ModelLifecycle,
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    http_get: HttpGet,
    tcp_probe: TcpProbe | None,
    clock: Clock,
    sleeper: Sleeper,
    since: float,
) -> tuple[ProbeSample, ...]:
    """Ask both probes together until readiness reports ready or the budget ends.

    Asking them *together* is the whole point. A readiness trace on its own
    cannot show that the process was alive during the load, and a liveness trace
    on its own cannot show that readiness was still false. The pair can.
    """
    deadline = since + lifecycle.startup_budget_ms / 1000
    samples: list[ProbeSample] = []
    while True:
        if not container_is_running(package, runner):
            raise ModelLifecycleError(
                "the runtime container stopped before it became ready"
            )
        live = tcp_is_live(
            package,
            probe=tcp_probe,
            timeout_seconds=OBSERVATION_POLL_SECONDS,
        )
        try:
            response = http_get(
                package.readiness_url,
                min(OBSERVATION_POLL_SECONDS, max(deadline - clock(), 0.001)),
            )
        except RuntimeEndpointUnavailable:
            response = HttpResponse(0)
        if len(samples) >= MAXIMUM_SAMPLES:
            # Dropping samples here would leave `samples[-1]` a loading sample
            # and publish its timestamp as the ready time. A wrong number is
            # worse than a refusal, so this refuses.
            raise ModelLifecycleError(
                "the observation retained more samples than this tool publishes"
            )
        samples.append(
            ProbeSample(
                elapsed_ms=_elapsed_ms(clock, since),
                liveness=live,
                readiness_status=response.status,
            )
        )
        if response.status == lifecycle.readiness_ready_status:
            return tuple(samples)
        if response.status not in (0, lifecycle.readiness_loading_status):
            raise ModelLifecycleError(
                "the runtime reported a readiness status this model does not publish"
            )
        if clock() >= deadline:
            raise ModelLifecycleError(
                "the runtime did not become ready within the startup budget"
            )
        sleeper(min(OBSERVATION_POLL_SECONDS, max(deadline - clock(), 0.001)))


def capture_environment(
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    manifest: ModelManifest | None = None,
) -> Environment:
    """The host facts a timing figure only means anything alongside."""
    resolved = manifest or load_manifest()
    result = runner.run((package.engine, "version", "--format", "{{.Server.Version}}"))
    engine = result.stdout.strip() if result.returncode == 0 else None
    return Environment(
        platform=f"{platform.system()} {platform.release()} {platform.machine()}",
        python_version=platform.python_version(),
        engine_version=engine or None,
        image_reference=package.image_reference,
        model_revision=resolved.revision,
        model_sha256=resolved.sha256,
    )


def compare_starts(
    lifecycle: ModelLifecycle,
    package: RuntimePackage,
    runner: CommandRunner,
    *,
    confirmed: bool,
    http_get: HttpGet,
    http_post: HttpPost,
    tcp_probe: TcpProbe | None = None,
    manifest: ModelManifest | None = None,
    repo_root: Path = REPO_ROOT,
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
    now: Clock = time.time,
) -> ComparisonResult:
    """Two real starts of the same artifact, with the integrity read between them.

    Both starts are cache **hits**. What differs is that the artifact is read end
    to end between them, so the second one finds the host's own file cache warm.
    That is the only cold/warm variable this comparison controls, and calling it
    anything more would be claiming a cache miss nobody paid for.
    """
    _require_confirmation(confirmed)
    if owned_container_exists(package, runner):
        raise ModelLifecycleError(
            "a container with the package's own name already exists; stop it first"
        )
    resolved = manifest or load_manifest()
    environment = capture_environment(package, runner, manifest=resolved)
    started_at = datetime.fromtimestamp(now(), tz=UTC).isoformat(timespec="seconds")

    cold = observe_start(
        lifecycle,
        package,
        runner,
        observation_id="cold",
        confirmed=True,
        http_get=http_get,
        http_post=http_post,
        tcp_probe=tcp_probe,
        manifest=resolved,
        repo_root=repo_root,
        clock=clock,
        sleeper=sleeper,
    )

    verify_started = clock()
    before = observe_cache(resolved, repo_root=repo_root, verify=True)
    verify_ms = _elapsed_ms(clock, verify_started)

    warm = observe_start(
        lifecycle,
        package,
        runner,
        observation_id="warm",
        confirmed=True,
        http_get=http_get,
        http_post=http_post,
        tcp_probe=tcp_probe,
        manifest=resolved,
        repo_root=repo_root,
        clock=clock,
        sleeper=sleeper,
    )
    after = observe_cache(resolved, repo_root=repo_root, verify=True)

    return ComparisonResult(
        lifecycle_id=lifecycle.lifecycle_id,
        started_at=started_at,
        environment=environment,
        cold=cold,
        warm=warm,
        verify_ms=verify_ms,
        verified_before_warm=before.verified,
        verified_after_warm=after.verified,
    )


# --------------------------------------------------------------------------
# Results, and the cleanup that may only reach them
# --------------------------------------------------------------------------


def result_directory(
    lifecycle: ModelLifecycle,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """The one directory this tool writes, guarded before it is handed back.

    The model-cache refusal comes first because it has to be reachable. Behind
    the pinned-directory equality it would never fire, and a guard that cannot
    fire is a guard nobody can test. It compares against the cache root the
    loaded record carries — which ``_validate_cache`` has already held to the
    model source record — rather than against a second copy of the same path.
    """
    directory = repo_root / lifecycle.result_directory
    resolved_repo = repo_root.resolve()
    resolved = directory.resolve(strict=False)
    if lifecycle.result_directory == lifecycle.cache_root or resolved == (
        repo_root / lifecycle.cache_root
    ).resolve(strict=False):
        raise ModelLifecycleError(
            "the measurement directory may not be the model cache"
        )
    if lifecycle.result_directory != EXPECTED_RESULT_DIRECTORY:
        raise ModelLifecycleError("the measurement directory is not the managed one")
    try:
        resolved.relative_to(resolved_repo)
    except ValueError as error:
        raise ModelLifecycleError(
            "the measurement directory resolves outside the repository"
        ) from error
    candidate = repo_root
    for part in lifecycle.result_directory.parts:
        candidate = candidate / part
        if candidate.exists() and candidate.is_symlink():
            raise ModelLifecycleError(
                "a symbolic link in the measurement path is refused"
            )
    return directory


def _sample_document(sample: ProbeSample) -> dict[str, Any]:
    return {
        "elapsedMs": sample.elapsed_ms,
        "liveness": sample.liveness,
        "readinessStatus": sample.readiness_status,
    }


def observation_document(observation: StartObservation) -> dict[str, Any]:
    """One observation as the record this tool writes. Carries no prompt or content."""
    return {
        "observationId": observation.observation_id,
        "cacheState": str(observation.cache_state),
        "artifactBytes": observation.artifact_bytes,
        "readyStatus": observation.ready_status,
        "loadingStatus": observation.loading_status,
        "createMs": observation.create_ms,
        "firstLivenessMs": observation.first_liveness_ms,
        "readyMs": observation.ready_ms,
        "inferenceMs": observation.inference_ms,
        "inferenceStatus": observation.inference_status,
        "stopMs": observation.stop_ms,
        "loadingObservations": len(observation.loading_samples),
        "livenessHeldWhileLoading": observation.liveness_held_while_loading,
        "livenessNeverDroppedAfterItPassed": (
            observation.liveness_never_dropped_after_it_passed
        ),
        "readinessFalseUntilReady": observation.readiness_false_until_ready,
        "samples": [_sample_document(sample) for sample in observation.samples],
    }


def summarize(lifecycle: ModelLifecycle, result: ComparisonResult) -> dict[str, Any]:
    """The comparison as a deterministic document, derived only from what was measured."""
    delta = result.warm.ready_ms - result.cold.ready_ms
    return {
        "schemaVersion": EXPECTED_SCHEMA_VERSION,
        "lifecycleId": result.lifecycle_id,
        "evidenceClass": lifecycle.evidence_class,
        "certificationCeiling": lifecycle.certification_ceiling,
        "startedAt": result.started_at,
        "environment": {
            "platform": result.environment.platform,
            "pythonVersion": result.environment.python_version,
            "engineVersion": result.environment.engine_version,
            "imageReference": result.environment.image_reference,
            "modelRevision": result.environment.model_revision,
            "modelSha256": result.environment.model_sha256,
        },
        "cold": observation_document(result.cold),
        "warm": observation_document(result.warm),
        "artifactVerifyMs": result.verify_ms,
        "verifiedBeforeWarm": result.verified_before_warm,
        "verifiedAfterWarm": result.verified_after_warm,
        "artifactSurvivedRestart": result.artifact_survived_restart,
        "readyMsDelta": delta,
        "acceptance": {
            "cacheHitInBothStarts": (
                result.cold.cache_state is CacheState.HIT
                and result.warm.cache_state is CacheState.HIT
            ),
            "livenessHeldWhileLoading": (
                result.cold.liveness_held_while_loading
                and result.warm.liveness_held_while_loading
            ),
            "readinessFalseUntilReady": (
                result.cold.readiness_false_until_ready
                and result.warm.readiness_false_until_ready
            ),
            "artifactSurvivedRestart": result.artifact_survived_restart,
        },
    }


def write_results(
    lifecycle: ModelLifecycle,
    result: ComparisonResult,
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[Path, Path]:
    """Write the raw observations and the summary into the managed directory."""
    directory = result_directory(lifecycle, repo_root=repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    raw = directory / lifecycle.raw_file
    summary = directory / lifecycle.summary_file
    lines = [
        json.dumps(observation_document(observation), sort_keys=True)
        for observation in (result.cold, result.warm)
    ]
    raw.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary.write_text(
        json.dumps(summarize(lifecycle, result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return raw, summary


def read_results(
    lifecycle: ModelLifecycle,
    *,
    repo_root: Path = REPO_ROOT,
) -> Sequence[Mapping[str, Any]]:
    """Read back the raw observations, refusing a line that is not one."""
    raw = result_directory(lifecycle, repo_root=repo_root) / lifecycle.raw_file
    if not raw.is_file():
        raise ModelLifecycleError("no raw lifecycle result has been written")
    documents: list[Mapping[str, Any]] = []
    for line in raw.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            document: Any = json.loads(line)
        except json.JSONDecodeError as error:
            raise ModelLifecycleError(
                "a raw lifecycle result line is not JSON"
            ) from error
        entry = _object(document, "raw line")
        if entry.get("observationId") not in lifecycle.observation_ids:
            raise ModelLifecycleError("a raw result names an undeclared observation")
        documents.append(entry)
    return tuple(documents)


def clean_results(
    lifecycle: ModelLifecycle,
    *,
    repo_root: Path = REPO_ROOT,
    confirm: bool = False,
) -> CleanupResult:
    """Inspect or remove only this tool's own results directory.

    It cannot reach the model cache. :func:`result_directory` refuses that
    target before it refuses anything else, comparing both the declared path and
    its resolution against the cache root the record carries, and refuses a
    symbolic link anywhere in or above the managed tree — so a link pointed at
    the model cache is refused rather than followed.
    """
    directory = result_directory(lifecycle, repo_root=repo_root)
    existed = directory.exists()
    bytes_found = 0
    if existed:
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ModelLifecycleError(
                    "cleanup refused a symbolic link inside the results directory"
                )
            if path.is_file():
                bytes_found += path.stat().st_size
    if confirm and existed:
        try:
            shutil.rmtree(directory)
        except OSError as error:
            raise ModelLifecycleError(
                "the lifecycle results directory could not be removed"
            ) from error
    return CleanupResult(
        directory=directory,
        bytes_found=bytes_found,
        removed=confirm and existed,
    )


__all__ = [
    "EXPECTED_RESULT_DIRECTORY",
    "LIFECYCLE_PATH",
    "MODEL_CACHE_DIRECTORY",
    "CacheObservation",
    "CacheRule",
    "CacheState",
    "CleanupResult",
    "ComparisonResult",
    "Environment",
    "LifecycleRefused",
    "LifecycleState",
    "ModelLifecycle",
    "ModelLifecycleError",
    "ProbeOutcome",
    "ProbeSample",
    "RuntimePackagingError",
    "StartObservation",
    "StateRule",
    "Transition",
    "capture_environment",
    "clean_results",
    "compare_starts",
    "load_lifecycle",
    "model_artifact_path",
    "observation_document",
    "observe_cache",
    "observe_start",
    "read_results",
    "result_directory",
    "summarize",
    "write_results",
]
