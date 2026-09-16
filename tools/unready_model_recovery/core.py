"""A model that does not become ready: what it runs, what it reads, what it records.

`scripts/environment/unready-model-recovery.sh` owns every contact with the cluster.
It verifies the target, installs the release with one committed values overlay that
starves the serving runtime container of processor time, holds the release in that
state for a registered window while it asks four request surfaces and samples
readiness, captures the diagnostics an operator would look at, corrects the values
and upgrades, and removes the release. This module owns everything that can be
decided without a cluster:

- the **descriptor** -- the committed experiment, checked against the overlay it
  pins by digest and against ceilings kept here rather than in it;
- the **environment** -- the fields a record keeps out of the cluster's own JSON;
- the **record** -- a pure function of the committed inputs. It splits the probe
  record set by phase, places the readiness samples and the collector's answers on
  the same wall clock, and lists what it saw.

**The question this answers, and the ones it does not.** ADR 0010 D8 publishes
`model-not-ready` as the single row of the accepted error mapping that anything ever
observed, and observed it incidentally, from one control-plane line during the
Sprint 0 feasibility trial. `MockScenario.MODEL_NOT_READY` reproduces the shape in a
fixture, and `docs/serving/mock-and-real-boundary.md` states as its rule that a mock
serving path may never be used to certify real local runtime behaviour, however
faithfully it reproduces the API surface. So this installs a release whose model does not
become ready, on a real cluster, and records what readiness, liveness, the canonical
error surface, the diagnostics, and the telemetry actually do.

It is not `V1-S3-008`, whose artifact mismatch is refused by the `verify-model` init
container before the runtime container is ever started, and it is not `V1-S4-006`,
which deleted a pod that was healthy and ready. The descriptor carries the list of
mechanisms that were tried and rejected, with the reason each one was rejected, so
that the choice is readable rather than asserted.

**What it refuses to become.** Every figure is one observation of one release
misconfigured once. Nothing here is an availability figure, a service-level
objective, an error budget, a recovery-time objective, or a number anything may be
compared against, and the descriptor and the record each carry the boundary that says
so (ADR 0013 D3).

Reuse is explicit rather than incidental. `tools.performance_scenarios.core`
contributes the serialization, digest, and private-shape helpers every committed
record in this repository shares; `tools.performance_scenarios.live` contributes the
loopback-only HTTP asker, through `live.py`. Nothing here re-implements either.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from tools.performance_scenarios.core import (
    PRIVATE_SHAPES,
    ScenarioRefused,
    dumps,
    file_digest,
    read_json,
    text_digest,
)
from tools.performance_scenarios.core import refuse_private as _shared_refuse_private

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR_PATH = (
    REPO_ROOT / "deploy" / "serving" / "experiments" / "unready-model-recovery.v1.json"
)

EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_EXPERIMENT_ID = "inferops-unready-model-recovery"
EXPECTED_EVIDENCE_CLASS = "local-real-cpu"
EXPECTED_EVIDENCE_LABEL = "local real Kubernetes"
EXPECTED_CEILING = "C2"
EXPECTED_LANE = "real-runtime"
RECORD_SCHEMA = "inferops.io/v1alpha1"
RECORD_KIND = "inferops-unready-model-recovery-record"

#: This experiment's disruption, as a literal. A descriptor naming any other
#: mechanism belongs to another experiment, and widening this would let one record
#: describe two.
DISRUPTION_MECHANISM = "starve-serving-runtime-cpu-at-install"
DISRUPTION_TARGET = "serving-runtime"
DISRUPTION_SCOPE = "release-values"
DISRUPTION_APPLIED_AT = "install"
DISRUPTION_REVERSED_BY = "values-fix-and-upgrade"
RECOVERY_MECHANISM = "helm-upgrade-without-the-overlay"

#: The only two values the committed overlay is allowed to set. An overlay that
#: touched a model value would be a different experiment wearing this one's name:
#: the whole argument that the artifact is fine rests on nothing having changed it.
OVERLAY_KEYS = (
    "runtime.resources.requests.cpu",
    "runtime.resources.limits.cpu",
)

#: The two phases, in the order they happen.
PHASES = ("unready", "recovered")

#: The answerability vocabulary the telemetry correlation record already publishes.
ANSWERABILITY = (
    "answerable-once-collected",
    "not-answerable-nothing-emits",
    "no-source",
)

#: What a series is expected to do across the run, registered before it.
EXPOSURE = (
    "expected-to-expose",
    "expected-not-to-expose",
    "nothing-emits",
    "no-source",
)

#: What a person may have had to do. Unlike `V1-S4-006`, this experiment *expects*
#: an intervention: a model that cannot load is not a state any controller reverses.
#: The expected one is registered, and anything else is a finding.
INTERVENTIONS = (
    "none",
    "corrected-the-values-and-upgraded",
    "restarted-a-workload",
    "rolled-back-a-release",
    "edited-a-declared-object",
    "recreated-a-prerequisite",
)
EXPECTED_INTERVENTION = "corrected-the-values-and-upgraded"

#: How confidently a capture is registered as naming the cause.
IDENTIFIES_CAUSE = ("yes", "probable", "partial", "no")

#: The release tiers a record keeps, by the component label the chart gives them.
ROLE_COMPONENTS: dict[str, str] = {
    "api": "platform-api",
    "runtime": "serving-runtime",
    "collector": "telemetry-collector",
}
ROLES: tuple[str, ...] = tuple(ROLE_COMPONENTS)

#: The request tiers a probe may name.
PROBE_TIERS = ("platform-api", "serving-runtime")

#: The configuration keys a record keeps. Everything else in the ConfigMap stays in
#: the cluster: the record names what shapes a measurement, not the whole release.
CONFIGURATION_KEYS: tuple[str, ...] = (
    "INFEROPS_SERVING_ADAPTER",
    "INFEROPS_REQUEST_TIMEOUT_MS",
    "INFEROPS_MAX_OUTPUT_TOKENS",
    "INFEROPS_MODEL_IDENTIFIER",
    "INFEROPS_MODEL_REVISION",
    "INFEROPS_RUNTIME_IMAGE_DIGEST",
    "INFEROPS_LLAMA_SERVER_CONTEXT_SIZE",
    "INFEROPS_LLAMA_SERVER_THREADS",
    "INFEROPS_LLAMA_SERVER_METRICS_ENABLED",
)

#: The files whose content decides what a run does. Their digests are recorded at run
#: time, so a record can say which code produced it even from an uncommitted tree.
EXECUTED_FILES: tuple[str, ...] = (
    "deploy/serving/experiments/unready-model-recovery.v1.json",
    "deploy/serving/experiments/unready-model-values.v1.yaml",
    "scripts/environment/unready-model-recovery.sh",
    "scripts/environment/lib.sh",
    "tools/unready_model_recovery/core.py",
    "tools/unready_model_recovery/live.py",
    "tools/unready_model_recovery/__main__.py",
    "charts/inferops-llm/Chart.yaml",
    "charts/inferops-llm/values.yaml",
    "charts/inferops-llm/ci/real-values.yaml",
)

# Ceilings kept in code, for the reason tools.llm_load keeps its own: a longer or
# heavier run must not be authorizable by editing the record that is supposed to
# bound it. The unready window has a floor as well as a ceiling -- a window shorter
# than a few probe rounds could not establish that readiness stayed false -- and its
# ceiling is the chart's own runtime startup budget, because past that the kubelet
# restarts the container and the experiment would be measuring a restart loop.
MINIMUM_UNREADY_WINDOW_SECONDS = 60
MAXIMUM_UNREADY_WINDOW_SECONDS = 540
MINIMUM_RECOVERED_WINDOW_SECONDS = 15
MAXIMUM_RECOVERED_WINDOW_SECONDS = 600
MINIMUM_POLL_INTERVAL_MS = 1_000
MAXIMUM_POLL_INTERVAL_MS = 15_000
MINIMUM_ROUND_INTERVAL_MS = 5_000
MAXIMUM_ROUND_INTERVAL_MS = 120_000
MINIMUM_READINESS_SAMPLES = 4
MINIMUM_IDLE_SECONDS = 30
MAXIMUM_IDLE_SECONDS = 600
MAXIMUM_SETTLE_SECONDS = 600
MAXIMUM_SERIES = 20
MAXIMUM_CAPTURES = 12

#: The kubelet's own bound on this experiment, in milliseconds, as the chart's
#: default `runtime.probes.startup.budgetMs`. The descriptor's unready window must
#: fit inside it with room for the container to have started at all, or the run
#: would be measuring the startup probe giving up rather than a healthy process.
RUNTIME_STARTUP_BUDGET_MS = 600_000

#: How far apart two readiness samples may be before the window between them is a gap
#: this record cannot describe. Six polls rather than the four the pod-recovery
#: experiment uses, and the difference is measured rather than chosen: each sample here
#: asks the API server seven questions instead of two, every one of them through a
#: kubectl process on a Windows host, and the first complete execution of this
#: experiment recorded a widest gap of 20 221 ms against a four-poll ceiling of 20 000.
#: Six still catches a gap; it does not catch one slow answer.
READINESS_GAP_MULTIPLE = 6

DNS_LABEL = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]{1,62}")
DOTTED_PATH = re.compile(r"[A-Za-z][A-Za-z0-9]*(\.[A-Za-z][A-Za-z0-9]*)*")
RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z")
HTTP_PATH = re.compile(r"/[A-Za-z0-9/_.-]*")
SHA256 = re.compile(r"[0-9a-f]{64}")


class UnreadyError(RuntimeError):
    """The experiment, its evidence, or its record is not what it must be."""


class UnreadyRefused(UnreadyError):
    """A precondition refused before anything was recorded as a result."""


def carries_private_value(line: str) -> bool:
    """Whether one line carries a host path, a user directory, or an address.

    The same shapes `refuse_private` refuses, asked one line at a time rather than of
    a whole document, so that a capture can be published with the lines that carry one
    withheld and counted instead of being refused whole. It is the same tuple, not a
    second list: a redaction that used a narrower rule than the refusal would let
    through exactly what the refusal exists to stop.
    """
    return any(shape.search(line) is not None for shape in PRIVATE_SHAPES)


def refuse_private(text: str, what: str) -> None:
    """Refuse a document carrying a host path, a user directory, or an address.

    The shapes are the ones every committed record in this repository is held to, so
    the check is `tools.performance_scenarios`' rather than a second list that could
    drift from it. Only the exception is this module's, because a caller of this
    package should not have to catch another package's.

    It matters more here than in any other experiment in this repository: this one
    commits a diagnostic bundle, and a diagnostic bundle is exactly where a host path
    or a token reaches a commit.
    """
    try:
        _shared_refuse_private(text, what)
    except ScenarioRefused as error:
        raise UnreadyRefused(str(error)) from error


# --------------------------------------------------------------------------
# Small readers
# --------------------------------------------------------------------------


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UnreadyError(f"'{field}' must be an object")
    return cast(dict[str, Any], value)


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise UnreadyError(f"'{field}' must be a list")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnreadyError(f"'{field}' must be a non-empty string")
    return value


def _integer(
    value: Any, field: str, *, minimum: int = 0, maximum: int | None = None
) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise UnreadyError(f"'{field}' must be an integer of at least {minimum}")
    if maximum is not None and value > maximum:
        raise UnreadyError(f"'{field}' must be at most {maximum}")
    return value


def _true(value: Any, field: str) -> None:
    if value is not True:
        raise UnreadyError(f"'{field}' must be true")


def _false(value: Any, field: str) -> None:
    if value is not False:
        raise UnreadyError(f"'{field}' must be false")


def _member(value: Any, field: str, allowed: Sequence[str]) -> str:
    text = _string(value, field)
    if text not in allowed:
        raise UnreadyError(f"'{field}' must be one of {', '.join(allowed)}")
    return text


def _read_json_text(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise UnreadyError(f"the {what} is not valid JSON") from error


# --------------------------------------------------------------------------
# The descriptor
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Surface:
    """One request surface this experiment asks, and what it was registered to do."""

    probe_id: str
    tier: str
    method: str
    path: str
    phases: tuple[str, ...]
    unready_status: int
    recovered_status: int
    expectation: str


@dataclass(frozen=True, slots=True)
class Capture:
    """One diagnostic an operator would look at, and how far it names the cause."""

    capture_id: str
    what: str
    identifies_cause: str
    expectation: str


@dataclass(frozen=True, slots=True)
class Series:
    """One collector expression, and what it was registered as expected to do."""

    series_id: str
    expr: str
    answerability: str
    exposure: str
    expectation: str


@dataclass(frozen=True, slots=True)
class Descriptor:
    """The committed experiment, after every rule it must satisfy has been applied."""

    document: Mapping[str, Any]
    sha256: str
    overlay_sha256: str
    surfaces: tuple[Surface, ...]
    captures: tuple[Capture, ...]
    series: tuple[Series, ...]
    poll_interval_ms: int
    minimum_samples: int
    unready_window_seconds: int
    recovered_window_seconds: int
    round_interval_ms: int
    range_step_seconds: int
    scrape_interval_seconds: int
    refusal_codes: tuple[str, ...]
    limitations: tuple[str, ...]

    @property
    def probe_ids(self) -> tuple[str, ...]:
        return tuple(surface.probe_id for surface in self.surfaces)


def _validate_identity(document: Mapping[str, Any]) -> None:
    if document.get("schemaVersion") != EXPECTED_SCHEMA:
        raise UnreadyError(f"the schema version must be '{EXPECTED_SCHEMA}'")
    if document.get("experimentId") != EXPECTED_EXPERIMENT_ID:
        raise UnreadyError(f"the experiment id must be '{EXPECTED_EXPERIMENT_ID}'")
    if document.get("evidenceClass") != EXPECTED_EVIDENCE_CLASS:
        raise UnreadyError(f"the evidence class must be '{EXPECTED_EVIDENCE_CLASS}'")
    if document.get("evidenceLabel") != EXPECTED_EVIDENCE_LABEL:
        raise UnreadyError(f"the evidence label must be '{EXPECTED_EVIDENCE_LABEL}'")
    if document.get("certificationCeiling") != EXPECTED_CEILING:
        raise UnreadyError(f"the certification ceiling must be '{EXPECTED_CEILING}'")
    if document.get("lane") != EXPECTED_LANE:
        raise UnreadyError(f"the lane must be '{EXPECTED_LANE}'")
    _false(document.get("productionBenchmark"), "productionBenchmark")
    _false(document.get("portableCapacityClaim"), "portableCapacityClaim")
    _false(document.get("availabilityClaim"), "availabilityClaim")
    boundary = _string(document.get("boundary"), "boundary")
    for word in ("availability", "benchmark", "portable capacity", "recovery-time"):
        if word not in boundary:
            raise UnreadyError(f"the boundary sentence does not refuse '{word}'")
    _string(document.get("experimentVersion"), "experimentVersion")
    for reference in (
        "decisionRef",
        "procedureRef",
        "reportTemplateRef",
        "chartRef",
        "extendsRef",
        "distinctProofQuestion",
    ):
        _string(document.get(reference), reference)


def _validate_cluster(document: Mapping[str, Any]) -> None:
    providers = _list(
        _object(document.get("cluster"), "cluster").get("providers"), "providers"
    )
    if not providers:
        raise UnreadyError("the experiment describes no provider")
    identifiers = []
    for entry in providers:
        provider = _object(entry, "providers[]")
        for field in ("providerId", "name", "context"):
            _string(provider.get(field), f"providers[].{field}")
        identifiers.append(provider["providerId"])
    if len(set(identifiers)) != len(identifiers):
        raise UnreadyError("two providers carry the same identifier")


def _validate_release(document: Mapping[str, Any]) -> None:
    release = _object(document.get("release"), "release")
    for field in (
        "name",
        "namespace",
        "profile",
        "apiServiceName",
        "apiDeploymentName",
        "runtimeServiceName",
        "runtimeDeploymentName",
        "collectorServiceName",
        "collectorDeploymentName",
        "configMapName",
        "apiComponent",
        "runtimeComponent",
        "collectorComponent",
        "acquisitionComponent",
    ):
        value = _string(release.get(field), f"release.{field}")
        if DNS_LABEL.fullmatch(value) is None:
            raise UnreadyError(f"'release.{field}' is not a Kubernetes name")
    _string(release.get("instanceSelector"), "release.instanceSelector")
    for field in (
        "apiServicePort",
        "apiContainerPort",
        "runtimeServicePort",
        "runtimeContainerPort",
        "collectorServicePort",
    ):
        _integer(release.get(field), f"release.{field}", minimum=1, maximum=65535)
    for field in ("apiReplicas", "runtimeReplicas"):
        replicas = _integer(release.get(field), f"release.{field}", minimum=1)
        if replicas != 1:
            raise UnreadyError(
                f"'release.{field}' is {replicas}; this experiment is defined for one "
                "replica of each tier, because a second would give a caller somewhere "
                "else to go and the question is what one unready model does"
            )
    if release.get("profile") != "real":
        raise UnreadyError(
            "this experiment installs the real profile. A mock release loads no model, "
            "so a mock 'unready model' is a fixture answering on cue"
        )
    if release.get("namespace") != "inferops-release":
        raise UnreadyError("the release namespace is not the one these scripts operate")


def _validate_disruption(
    document: Mapping[str, Any], *, repo_root: Path
) -> tuple[str, str]:
    """The mechanism, and the digest of the one overlay that carries it."""
    disruption = _object(document.get("disruption"), "disruption")
    _string(disruption.get("description"), "disruption.description")
    for field, expected in (
        ("mechanism", DISRUPTION_MECHANISM),
        ("target", DISRUPTION_TARGET),
        ("scope", DISRUPTION_SCOPE),
        ("appliedAt", DISRUPTION_APPLIED_AT),
        ("reversedBy", DISRUPTION_REVERSED_BY),
    ):
        if disruption.get(field) != expected:
            raise UnreadyError(f"'disruption.{field}' must be '{expected}'")
    for field in (
        "passesChartValidation",
        "passesModelIntegrityInitContainer",
        "changesNoModelValue",
        "changesNoPersistentVolumeClaim",
        "changesNoClusterScopedObject",
        "touchesNoOtherNamespace",
        "deletesNoPod",
    ):
        _true(disruption.get(field), f"disruption.{field}")
    keys = tuple(
        _string(entry, "overlaySetsOnly[]")
        for entry in _list(disruption.get("overlaySetsOnly"), "overlaySetsOnly")
    )
    if keys != OVERLAY_KEYS:
        raise UnreadyError(
            "the overlay is registered as setting something other than the two "
            "processor values this experiment is defined for"
        )
    rejected = [
        _string(entry, "rejectedMechanisms[]")
        for entry in _list(disruption.get("rejectedMechanisms"), "rejectedMechanisms")
    ]
    if len(rejected) < 3:
        raise UnreadyError(
            "the descriptor names fewer than three rejected mechanisms. The choice of "
            "disruption is the design decision this experiment turns on, and a "
            "descriptor that states only the one that was taken hides it"
        )
    overlay_ref = _string(disruption.get("valuesOverlayRef"), "valuesOverlayRef")
    overlay_path = repo_root / overlay_ref
    if not overlay_path.is_file():
        raise UnreadyError("the descriptor pins a values overlay that is not committed")
    overlay_text = overlay_path.read_text(encoding="utf-8")
    # The overlay is read as text as well as digested. A file that set a model value
    # would make the record's whole "the artifact was never in question" argument
    # false, and the digest alone would not have noticed.
    body = "\n".join(
        line for line in overlay_text.splitlines() if not line.lstrip().startswith("#")
    )
    for forbidden in ("model:", "profile:", "image:", "secretRefs", "probes:"):
        if forbidden in body:
            raise UnreadyError(
                f"the values overlay sets '{forbidden}', and this experiment's overlay "
                "may set nothing but the serving runtime's processor request and limit"
            )
    if "cpu:" not in body or "resources:" not in body:
        raise UnreadyError(
            "the values overlay does not set a processor value, so it is not the "
            "disruption this experiment is defined for"
        )
    return overlay_ref, file_digest(overlay_path)


def _validate_human_action(document: Mapping[str, Any]) -> None:
    human = _object(document.get("humanAction"), "humanAction")
    _string(human.get("description"), "humanAction.description")
    _true(human.get("authorisationRequired"), "humanAction.authorisationRequired")
    _true(
        human.get("valuesFileSuppliedByOperator"),
        "humanAction.valuesFileSuppliedByOperator",
    )
    # The one place this experiment differs from V1-S4-006 on purpose. A model that
    # cannot load is not a state a controller reverses, and a descriptor claiming it
    # expected no intervention would be claiming a self-healing property.
    _true(
        human.get("recoveryInterventionExpected"),
        "humanAction.recoveryInterventionExpected",
    )
    if human.get("expectedRecoveryIntervention") != EXPECTED_INTERVENTION:
        raise UnreadyError(
            f"the expected recovery intervention must be '{EXPECTED_INTERVENTION}'"
        )
    vocabulary = tuple(
        _string(entry, "interventionVocabulary[]")
        for entry in _list(
            human.get("interventionVocabulary"), "interventionVocabulary"
        )
    )
    if vocabulary != INTERVENTIONS:
        raise UnreadyError(
            "the intervention vocabulary is not the one this module records against"
        )


def _validate_observation(document: Mapping[str, Any]) -> tuple[int, int, int, int]:
    observation = _object(document.get("observation"), "observation")
    _string(observation.get("description"), "observation.description")
    for field in (
        "requireReadinessRecord",
        "requireEndpointSamples",
        "requireRestartCounts",
    ):
        _true(observation.get(field), f"observation.{field}")
    poll = _integer(
        observation.get("pollIntervalMs"),
        "pollIntervalMs",
        minimum=MINIMUM_POLL_INTERVAL_MS,
        maximum=MAXIMUM_POLL_INTERVAL_MS,
    )
    minimum = _integer(
        observation.get("minimumSamples"),
        "minimumSamples",
        minimum=MINIMUM_READINESS_SAMPLES,
    )
    unready = _integer(
        observation.get("unreadyWindowSeconds"),
        "unreadyWindowSeconds",
        minimum=MINIMUM_UNREADY_WINDOW_SECONDS,
        maximum=MAXIMUM_UNREADY_WINDOW_SECONDS,
    )
    recovered = _integer(
        observation.get("recoveredWindowSeconds"),
        "recoveredWindowSeconds",
        minimum=MINIMUM_RECOVERED_WINDOW_SECONDS,
        maximum=MAXIMUM_RECOVERED_WINDOW_SECONDS,
    )
    # The kubelet's bound, applied here rather than discovered during a run. Past the
    # runtime's startup budget the container is killed and restarted into the same
    # load, and a window that ran past it would publish a restart count describing
    # the probe rather than the model.
    if unready * 1000 >= RUNTIME_STARTUP_BUDGET_MS:
        raise UnreadyError(
            "the unready window is not shorter than the chart's own runtime startup "
            "budget, so the kubelet would restart the container inside it and the "
            "restart count would describe the startup probe rather than the model"
        )
    if unready * 1000 < minimum * poll:
        raise UnreadyError(
            "the unready window is too short to hold the minimum number of readiness "
            "samples at the registered poll interval"
        )
    return poll, minimum, unready, recovered


def _validate_probes(
    document: Mapping[str, Any],
) -> tuple[
    tuple[Surface, ...],
    int,
    tuple[str, ...],
]:
    probes = _object(document.get("probes"), "probes")
    _string(probes.get("description"), "probes.description")
    _false(probes.get("retainGeneratedText"), "probes.retainGeneratedText")
    interval = _integer(
        probes.get("roundIntervalMs"),
        "roundIntervalMs",
        minimum=MINIMUM_ROUND_INTERVAL_MS,
        maximum=MAXIMUM_ROUND_INTERVAL_MS,
    )
    _integer(probes.get("requestTimeoutMs"), "requestTimeoutMs", minimum=1000)
    surfaces: list[Surface] = []
    for entry in _list(probes.get("surfaces"), "probes.surfaces"):
        item = _object(entry, "surfaces[]")
        probe_id = _string(item.get("probeId"), "probeId")
        if IDENTIFIER.fullmatch(probe_id) is None:
            raise UnreadyError(f"'{probe_id}' is not a probe identifier")
        path = _string(item.get("path"), "path")
        if HTTP_PATH.fullmatch(path) is None:
            raise UnreadyError(f"'{path}' is not a request path")
        phases = tuple(
            _member(value, "surfaces[].phases[]", PHASES)
            for value in _list(item.get("phases"), "phases")
        )
        if phases != PHASES:
            raise UnreadyError(
                f"probe '{probe_id}' is not asked in both phases; a surface asked in "
                "one of them cannot say what changed"
            )
        surfaces.append(
            Surface(
                probe_id=probe_id,
                tier=_member(item.get("tier"), "tier", PROBE_TIERS),
                method=_member(item.get("method"), "method", ("GET", "POST")),
                path=path,
                phases=phases,
                unready_status=_integer(
                    item.get("expectedUnreadyStatus"),
                    "expectedUnreadyStatus",
                    minimum=100,
                    maximum=599,
                ),
                recovered_status=_integer(
                    item.get("expectedRecoveredStatus"),
                    "expectedRecoveredStatus",
                    minimum=100,
                    maximum=599,
                ),
                expectation=_string(item.get("expectation"), "expectation"),
            )
        )
    identifiers = [surface.probe_id for surface in surfaces]
    if len(set(identifiers)) != len(identifiers):
        raise UnreadyError("two probe surfaces carry the same identifier")
    if not any(surface.tier == "serving-runtime" for surface in surfaces):
        raise UnreadyError(
            "no probe asks the serving runtime directly. Whether the model is ready is "
            "the runtime's own answer, and a record that only asked the API would be "
            "recording what the API concluded rather than what the runtime said"
        )
    completions = [
        surface
        for surface in surfaces
        if surface.method == "POST" and surface.tier == "platform-api"
    ]
    if len(completions) != 1:
        raise UnreadyError(
            "this experiment asks for exactly one completion surface, because the "
            "recovery is stamped from a served completion"
        )
    if completions[0].recovered_status != 200:
        raise UnreadyError(
            "the completion surface is not registered as expected to be served after "
            "the fix, so nothing here would establish that the release recovered"
        )
    codes = tuple(
        _string(entry, "canonicalRefusalCodes[]")
        for entry in _list(probes.get("canonicalRefusalCodes"), "canonicalRefusalCodes")
    )
    if len(codes) < 2 or len(set(codes)) != len(codes):
        raise UnreadyError(
            "the canonical refusal vocabulary is empty, too small, or repeats itself. "
            "It holds more than the one code this experiment expects on purpose: which "
            "refusal arrives is the result, not the arrangement"
        )
    for expected in ("model-not-ready", "capability-unavailable"):
        if expected not in codes:
            raise UnreadyError(
                f"the canonical refusal vocabulary omits '{expected}', which is one of "
                "the two codes ADR 0010 D8 maps this situation to"
            )
    return tuple(surfaces), interval, codes


def _validate_diagnostics(document: Mapping[str, Any]) -> tuple[Capture, ...]:
    diagnostics = _object(document.get("diagnostics"), "diagnostics")
    _string(diagnostics.get("description"), "diagnostics.description")
    _true(diagnostics.get("requireNoSecretInCaptures"), "requireNoSecretInCaptures")
    _true(diagnostics.get("requireNoHostPathInCaptures"), "requireNoHostPathInCaptures")
    _integer(diagnostics.get("logTailLines"), "logTailLines", minimum=1, maximum=5000)
    captures: list[Capture] = []
    entries = _list(diagnostics.get("captures"), "diagnostics.captures")
    if not entries or len(entries) > MAXIMUM_CAPTURES:
        raise UnreadyError(
            f"the experiment captures between 1 and {MAXIMUM_CAPTURES} diagnostics"
        )
    for entry in entries:
        item = _object(entry, "captures[]")
        capture_id = _string(item.get("captureId"), "captureId")
        if IDENTIFIER.fullmatch(capture_id) is None:
            raise UnreadyError(f"'{capture_id}' is not a capture identifier")
        captures.append(
            Capture(
                capture_id=capture_id,
                what=_string(item.get("what"), "what"),
                identifies_cause=_member(
                    item.get("identifiesCause"), "identifiesCause", IDENTIFIES_CAUSE
                ),
                expectation=_string(item.get("expectation"), "expectation"),
            )
        )
    identifiers = [capture.capture_id for capture in captures]
    if len(set(identifiers)) != len(identifiers):
        raise UnreadyError("two captures carry the same identifier")
    if not any(capture.identifies_cause == "yes" for capture in captures):
        raise UnreadyError(
            "no capture is registered as naming the cause, so the record could not say "
            "whether the diagnostics identified it"
        )
    return tuple(captures)


def _validate_recovery(document: Mapping[str, Any]) -> None:
    recovery = _object(document.get("recovery"), "recovery")
    _string(recovery.get("description"), "recovery.description")
    _string(recovery.get("sameReleaseBecause"), "recovery.sameReleaseBecause")
    if recovery.get("mechanism") != RECOVERY_MECHANISM:
        raise UnreadyError(f"'recovery.mechanism' must be '{RECOVERY_MECHANISM}'")
    for field, expected in (
        ("upgradeIssuedFrom", "operating-script"),
        ("runtimeReadyFrom", "upgrade-issued"),
        ("apiReadyFrom", "upgrade-issued"),
        ("firstServedCompletionFrom", "upgrade-issued"),
    ):
        if recovery.get(field) != expected:
            raise UnreadyError(f"'recovery.{field}' must be '{expected}'")
    for field in (
        "requireServedCompletionAfterRecovery",
        "requireCanonicalRefusalWhileUnready",
        "requireReleaseRevisionToMove",
    ):
        _true(recovery.get(field), f"recovery.{field}")


def _validate_telemetry(
    document: Mapping[str, Any],
) -> tuple[tuple[Series, ...], int, int]:
    telemetry = _object(document.get("telemetry"), "telemetry")
    _string(telemetry.get("description"), "telemetry.description")
    step = _integer(
        telemetry.get("rangeStepSeconds"), "rangeStepSeconds", minimum=1, maximum=300
    )
    scrape = _integer(
        telemetry.get("scrapeIntervalSeconds"),
        "scrapeIntervalSeconds",
        minimum=1,
        maximum=300,
    )
    entries = _list(telemetry.get("series"), "telemetry.series")
    if not entries or len(entries) > MAXIMUM_SERIES:
        raise UnreadyError(
            f"the experiment must ask between 1 and {MAXIMUM_SERIES} series"
        )
    series: list[Series] = []
    for entry in entries:
        item = _object(entry, "series[]")
        series_id = _string(item.get("seriesId"), "seriesId")
        if IDENTIFIER.fullmatch(series_id) is None:
            raise UnreadyError(f"'{series_id}' is not a series identifier")
        answerability = _member(
            item.get("answerability"), "answerability", ANSWERABILITY
        )
        exposure = _member(item.get("exposure"), "exposure", EXPOSURE)
        # A signal nothing emits cannot be expected to expose anything, and a signal
        # with no source cannot be expected to answer. Registering the pair together
        # is what stops a row claiming both.
        if (answerability == "not-answerable-nothing-emits") != (
            exposure == "nothing-emits"
        ):
            raise UnreadyError(
                f"series '{series_id}' pairs an answerability and an exposure that "
                "cannot both be true"
            )
        if (answerability == "no-source") != (exposure == "no-source"):
            raise UnreadyError(
                f"series '{series_id}' pairs an answerability and an exposure that "
                "cannot both be true"
            )
        series.append(
            Series(
                series_id=series_id,
                expr=_string(item.get("expr"), "expr"),
                answerability=answerability,
                exposure=exposure,
                expectation=_string(item.get("expectation"), "expectation"),
            )
        )
    identifiers = [entry.series_id for entry in series]
    if len(set(identifiers)) != len(identifiers):
        raise UnreadyError("two series carry the same identifier")
    if not any(entry.exposure == "expected-to-expose" for entry in series):
        raise UnreadyError(
            "no series is registered as expected to expose the state, so the record "
            "could not say whether anything did"
        )
    if not any(entry.exposure == "expected-not-to-expose" for entry in series):
        raise UnreadyError(
            "no series is registered as expected not to expose the state, and a record "
            "naming only the signals that worked is not a classification"
        )
    # The one metric in this repository whose declared question is this experiment's
    # question. A telemetry set that left it out would be a set that quietly avoided
    # its own worst answer.
    if not any(entry.expr == "inferops_model_ready" for entry in series):
        raise UnreadyError(
            "the experiment does not ask 'inferops_model_ready'. The telemetry catalog "
            "declares it for exactly this question and marks it not emitted; a record "
            "that did not ask it would be a record that avoided its own worst answer"
        )
    return tuple(series), step, scrape


def _validate_readiness(document: Mapping[str, Any]) -> None:
    readiness = _object(document.get("readiness"), "readiness")
    budgets: dict[str, int] = {}
    for field in (
        "runtimeContainerRunningBudgetMs",
        "apiContainerRunningBudgetMs",
        "collectorRolloutBudgetMs",
        "forwardBudgetMs",
        "recoveryRolloutBudgetMs",
        "recoveryBudgetMs",
        "uninstallBudgetMs",
    ):
        budgets[field] = _integer(
            readiness.get(field), f"readiness.{field}", minimum=1000
        )
    if budgets["recoveryBudgetMs"] <= budgets["recoveryRolloutBudgetMs"]:
        raise UnreadyError(
            "a served completion cannot come back before the workload that serves it "
            "has rolled out, so the recovery budget must exceed the rollout budget"
        )


def _validate_schedule(document: Mapping[str, Any]) -> None:
    schedule = _object(document.get("schedule"), "schedule")
    phases = tuple(
        _string(entry, "phases[]") for entry in _list(schedule.get("phases"), "phases")
    )
    if phases != PHASES:
        raise UnreadyError("the phases are not the ones this module records against")
    _integer(
        schedule.get("idleBaselineSeconds"),
        "idleBaselineSeconds",
        minimum=MINIMUM_IDLE_SECONDS,
        maximum=MAXIMUM_IDLE_SECONDS,
    )
    _integer(
        schedule.get("settleAfterRecoverySeconds"),
        "settleAfterRecoverySeconds",
        minimum=0,
        maximum=MAXIMUM_SETTLE_SECONDS,
    )


def _validate_forwards(document: Mapping[str, Any]) -> None:
    forwards = _object(document.get("forwards"), "forwards")
    # The API behind the forward carries no authentication, so binding it anywhere
    # but loopback would publish an unauthenticated LLM endpoint on every interface.
    if forwards.get("host") != "127.0.0.1":
        raise UnreadyError("these forwards bind 127.0.0.1 only")
    _string(forwards.get("description"), "forwards.description")
    ports = [
        _integer(forwards.get(field), f"forwards.{field}", minimum=1024, maximum=65535)
        for field in (
            "apiPort",
            "runtimePort",
            "recoveredRuntimePort",
            "collectorPort",
        )
    ]
    # Four distinct ports, and the serving runtime's two are distinct from each other
    # for a reason the descriptor states: a forward this script closes does not release
    # its socket, so the forward opened after the upgrade is opened somewhere else.
    if len(set(ports)) != len(ports):
        raise UnreadyError("the forwards name the same local port twice")


def _validate_evidence(document: Mapping[str, Any]) -> None:
    evidence = _object(document.get("evidence"), "evidence")
    directory = _string(evidence.get("directory"), "evidence.directory")
    # A descriptor that could name any directory could name one outside the ignored
    # tree, and a record written there would carry this project's evidence label into
    # version control by accident.
    if not directory.startswith(".cache/inferops/experiments/"):
        raise UnreadyError(
            "run evidence is written under .cache/inferops/experiments/ and nowhere else"
        )
    for field in (
        "environmentFile",
        "lifecycleFile",
        "readinessFile",
        "probesFile",
        "diagnosticsFile",
        "telemetryFile",
        "recordDirectory",
    ):
        value = _string(evidence.get(field), f"evidence.{field}")
        if Path(value).name != value:
            raise UnreadyError(f"'evidence.{field}' carries a directory component")
    _false(evidence.get("retainGeneratedText"), "evidence.retainGeneratedText")


def _validate_cleanup(document: Mapping[str, Any]) -> None:
    cleanup = _object(document.get("cleanup"), "cleanup")
    _true(cleanup.get("uninstallsRelease"), "cleanup.uninstallsRelease")
    for field in ("removesPrerequisites", "removesCluster", "removesModelCacheClaim"):
        _false(cleanup.get(field), f"cleanup.{field}")


def _validate_limitations(document: Mapping[str, Any]) -> tuple[str, ...]:
    limitations = tuple(
        _string(entry, "limitations[]")
        for entry in _list(document.get("limitations"), "limitations")
    )
    if len(limitations) < 5:
        raise UnreadyError("an experiment of this kind states more than four limits")
    return limitations


def validate_descriptor(
    document: Mapping[str, Any], text: str, *, repo_root: Path = REPO_ROOT
) -> Descriptor:
    """The committed experiment, or a named refusal saying which rule it breaks."""
    _validate_identity(document)
    _validate_cluster(document)
    _validate_release(document)
    _validate_forwards(document)
    _validate_readiness(document)
    _validate_schedule(document)
    _validate_evidence(document)
    _validate_cleanup(document)
    _validate_human_action(document)
    _validate_recovery(document)

    _, overlay_sha256 = _validate_disruption(document, repo_root=repo_root)
    poll, samples, unready, recovered = _validate_observation(document)
    surfaces, round_interval, codes = _validate_probes(document)
    captures = _validate_diagnostics(document)
    series, step, scrape = _validate_telemetry(document)
    limitations = _validate_limitations(document)

    # Enough rounds to say that nothing changed, rather than that nothing changed
    # between two asks. Registered here rather than in the descriptor for the reason
    # every ceiling in this repository is: a shorter run must not be authorizable by
    # editing the document that is supposed to bound it.
    if unready * 1000 < round_interval * 3:
        raise UnreadyError(
            "the unready window holds fewer than three probe rounds, which is not "
            "enough to say that readiness stayed false rather than that it was false "
            "twice"
        )

    return Descriptor(
        document=document,
        sha256=text_digest(text),
        overlay_sha256=overlay_sha256,
        surfaces=surfaces,
        captures=captures,
        series=series,
        poll_interval_ms=poll,
        minimum_samples=samples,
        unready_window_seconds=unready,
        recovered_window_seconds=recovered,
        round_interval_ms=round_interval,
        range_step_seconds=step,
        scrape_interval_seconds=scrape,
        refusal_codes=codes,
        limitations=limitations,
    )


def load_descriptor(
    path: Path = DESCRIPTOR_PATH, *, repo_root: Path = REPO_ROOT
) -> Descriptor:
    """The committed descriptor, validated."""
    text = path.read_text(encoding="utf-8")
    document = _object(read_json(path, "experiment descriptor"), "descriptor")
    return validate_descriptor(document, text, repo_root=repo_root)


def descriptor_fields(descriptor: Descriptor, paths: Sequence[str]) -> list[str]:
    """The values at dotted paths, one per line, for the operating script to read."""
    values = []
    for path in paths:
        if DOTTED_PATH.fullmatch(path) is None:
            raise UnreadyError(f"'{path}' is not a dotted descriptor path")
        cursor: Any = descriptor.document
        for member in path.split("."):
            if not isinstance(cursor, Mapping) or member not in cursor:
                raise UnreadyError(f"the descriptor has no '{path}'")
            cursor = cursor[member]
        if isinstance(cursor, bool) or not isinstance(cursor, str | int):
            raise UnreadyError(f"'{path}' is not a value a shell can read")
        values.append(str(cursor))
    return values


def probe_lines(descriptor: Descriptor) -> list[str]:
    """The probe surfaces, one space-separated row each, for the shell to loop over.

    A shell that built this list itself could ask a surface the descriptor never
    registered, and the record would then hold a reading nothing pre-registered an
    expectation for.
    """
    return [
        " ".join(
            (
                surface.probe_id,
                surface.tier,
                surface.method,
                surface.path,
                str(surface.unready_status),
                str(surface.recovered_status),
            )
        )
        for surface in descriptor.surfaces
    ]


def summary_lines(descriptor: Descriptor) -> list[str]:
    """What `check` prints: what would run, and what it would refuse to claim."""
    document = descriptor.document
    release = _object(document.get("release"), "release")
    disruption = _object(document.get("disruption"), "disruption")
    exposures = {
        exposure: sum(1 for entry in descriptor.series if entry.exposure == exposure)
        for exposure in EXPOSURE
    }
    return [
        f"descriptor   {DESCRIPTOR_PATH.relative_to(REPO_ROOT).as_posix()} "
        f"({descriptor.sha256[:12]})",
        f"overlay      {disruption['valuesOverlayRef']} "
        f"({descriptor.overlay_sha256[:12]})",
        f"disruption   {disruption['mechanism']}, applied at "
        f"{disruption['appliedAt']}, reversed by {disruption['reversedBy']}",
        f"release      {release['name']} in {release['namespace']}, "
        f"{release['runtimeReplicas']} runtime replica, profile "
        f"{release['profile']}",
        f"unready      held for {descriptor.unready_window_seconds} s, inside the "
        f"chart's {RUNTIME_STARTUP_BUDGET_MS // 1000} s runtime startup budget",
        f"probes       {', '.join(descriptor.probe_ids)}, every "
        f"{descriptor.round_interval_ms} ms in both phases",
        f"readiness    sampled every {descriptor.poll_interval_ms} ms, at least "
        f"{descriptor.minimum_samples} samples",
        f"diagnostics  {', '.join(capture.capture_id for capture in descriptor.captures)}",
        "telemetry    "
        + ", ".join(f"{count} {name}" for name, count in exposures.items() if count),
        "claim        bounded observations of one release misconfigured once; not an "
        "availability figure, an SLO, an error budget, a recovery-time objective, or "
        "a benchmark",
    ]


# --------------------------------------------------------------------------
# What the cluster reported
# --------------------------------------------------------------------------


def _cluster_json(cluster_dir: Path, name: str) -> Any:
    return read_json(cluster_dir / name, f"cluster reading '{name}'")


def _items(document: Any, what: str) -> list[dict[str, Any]]:
    return [
        _object(item, f"{what}.items[]")
        for item in _list(_object(document, what).get("items"), f"{what}.items")
    ]


def _role_of(item: Mapping[str, Any]) -> str | None:
    labels = _object(item.get("metadata"), "metadata").get("labels") or {}
    component = (
        labels.get("app.kubernetes.io/component") if isinstance(labels, dict) else None
    )
    for role, expected in ROLE_COMPONENTS.items():
        if component == expected:
            return role
    return None


def _pods(document: Any) -> list[dict[str, Any]]:
    """The release's tier pods, one entry each, ordered by role.

    Unlike every other experiment in this repository, a pod is kept here whether or
    not it is ready and whether or not every container in it has started: a release
    whose model does not load has no ready pod at all, and a reader that skipped them
    would describe an empty release.
    """
    pods: list[dict[str, Any]] = []
    for item in _items(document, "pods"):
        role = _role_of(item)
        if role is None:
            continue
        status = _object(item.get("status"), "pod.status")
        statuses = [
            _object(entry, "containerStatuses[]")
            for entry in status.get("containerStatuses") or []
        ]
        init_statuses = [
            _object(entry, "initContainerStatuses[]")
            for entry in status.get("initContainerStatuses") or []
        ]
        metadata = _object(item.get("metadata"), "pod.metadata")
        conditions = {
            str(_object(entry, "conditions[]").get("type")): str(
                _object(entry, "conditions[]").get("status")
            )
            for entry in status.get("conditions") or []
        }
        pods.append(
            {
                "role": role,
                "name": _string(metadata.get("name"), "pod.name"),
                "uid": _string(metadata.get("uid"), "pod.uid"),
                "phase": _string(status.get("phase"), "pod.phase"),
                "ready": conditions.get("Ready") == "True",
                "containersStarted": bool(statuses)
                and all(entry.get("started") is True for entry in statuses),
                "containersReady": bool(statuses)
                and all(entry.get("ready") is True for entry in statuses),
                "restartCount": sum(
                    _integer(entry.get("restartCount"), "restartCount")
                    for entry in statuses
                ),
                "initExitCodes": [
                    _integer(
                        _object(entry.get("state") or {}, "state")
                        .get("terminated", {})
                        .get("exitCode", -1),
                        "initExitCode",
                        minimum=-1,
                    )
                    for entry in init_statuses
                ],
                "imageIds": sorted(
                    str(entry.get("imageID") or "") for entry in statuses
                ),
            }
        )
    return sorted(
        pods, key=lambda pod: (ROLES.index(str(pod["role"])), str(pod["name"]))
    )


def _containers(deployment: Mapping[str, Any]) -> list[dict[str, Any]]:
    spec = _object(
        _object(
            _object(deployment.get("spec"), "spec").get("template"), "template"
        ).get("spec"),
        "podSpec",
    )
    containers = []
    for entry in _list(spec.get("containers"), "containers"):
        container = _object(entry, "containers[]")
        resources = container.get("resources") or {}
        containers.append(
            {
                "name": _string(container.get("name"), "container.name"),
                "image": _string(container.get("image"), "container.image"),
                "resources": {
                    "requests": dict(sorted((resources.get("requests") or {}).items())),
                    "limits": dict(sorted((resources.get("limits") or {}).items())),
                },
            }
        )
    return containers


def _workloads(document: Any, descriptor: Descriptor) -> dict[str, Any]:
    release = descriptor.document["release"]
    names = {
        "api": release["apiDeploymentName"],
        "runtime": release["runtimeDeploymentName"],
        "collector": release["collectorDeploymentName"],
    }
    by_name = {
        _object(item.get("metadata"), "metadata").get("name"): item
        for item in _items(document, "deployments")
    }
    workloads: dict[str, Any] = {}
    for role, name in names.items():
        if name not in by_name:
            raise UnreadyRefused(f"the release has no Deployment named '{name}'")
        deployment = by_name[name]
        status = deployment.get("status") or {}
        workloads[role] = {
            "deployment": name,
            "desiredReplicas": _integer(
                _object(deployment.get("spec"), "spec").get("replicas"), "replicas"
            ),
            "availableReplicas": int(status.get("availableReplicas") or 0),
            "containers": _containers(deployment),
        }
    return workloads


def executed_file_digests(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """The LF-normalized digest of every file that decides what a run does."""
    return {relative: file_digest(repo_root / relative) for relative in EXECUTED_FILES}


def _cpu(workloads: Mapping[str, Any], role: str, container: str) -> dict[str, str]:
    for entry in workloads[role]["containers"]:
        if entry["name"] == container:
            return {
                "request": str(entry["resources"]["requests"].get("cpu", "")),
                "limit": str(entry["resources"]["limits"].get("cpu", "")),
            }
    raise UnreadyRefused(f"the {role} Deployment has no container named '{container}'")


def extract_environment(cluster_dir: Path, descriptor: Descriptor) -> dict[str, Any]:
    """The environment a record keeps, and nothing else the cluster reported."""
    target = _object(_cluster_json(cluster_dir, "target.json"), "target")
    version = _object(_cluster_json(cluster_dir, "version.json"), "version")
    node = _object(_cluster_json(cluster_dir, "node.json"), "node")
    engine = _object(_cluster_json(cluster_dir, "engine.json"), "engine")
    releases = _list(_cluster_json(cluster_dir, "helm-release.json"), "helm release")
    repository = _object(_cluster_json(cluster_dir, "repository.json"), "repository")
    configuration = _object(
        _object(_cluster_json(cluster_dir, "configmap.json"), "configmap").get("data"),
        "data",
    )
    background = _items(_cluster_json(cluster_dir, "running-pods.json"), "running pods")
    namespace = descriptor.document["release"]["namespace"]
    node_status = _object(node.get("status"), "node.status")
    node_info = _object(node_status.get("nodeInfo"), "nodeInfo")
    outside = [
        item
        for item in background
        if _object(item.get("metadata"), "metadata").get("namespace") != namespace
    ]
    release = _object(releases[0], "helm release[]") if len(releases) == 1 else {}
    unready_workloads = _workloads(
        _cluster_json(cluster_dir, "deployments-unready.json"), descriptor
    )
    recovered_workloads = _workloads(
        _cluster_json(cluster_dir, "deployments-recovered.json"), descriptor
    )
    environment = {
        "provider": _string(target.get("provider"), "target.provider"),
        "cluster": _string(target.get("cluster"), "target.cluster"),
        "context": _string(target.get("context"), "target.context"),
        "verifiedAt": _string(target.get("verifiedAt"), "target.verifiedAt"),
        "kubernetes": {
            "serverVersion": _object(version.get("serverVersion"), "serverVersion").get(
                "gitVersion"
            ),
            "kubectlVersion": _object(
                version.get("clientVersion"), "clientVersion"
            ).get("gitVersion"),
            "helmVersion": _string(target.get("helmVersion"), "target.helmVersion"),
        },
        "node": {
            "name": _object(node.get("metadata"), "node.metadata").get("name"),
            "imageDigest": target.get("nodeImageDigest") or None,
            "osImage": node_info.get("osImage"),
            "kernelVersion": node_info.get("kernelVersion"),
            "containerRuntimeVersion": node_info.get("containerRuntimeVersion"),
            "kubeletVersion": node_info.get("kubeletVersion"),
            "capacity": {
                key: node_status["capacity"][key] for key in ("cpu", "memory")
            },
            "allocatable": {
                key: node_status["allocatable"][key] for key in ("cpu", "memory")
            },
        },
        "engine": {
            "serverVersion": _string(
                engine.get("serverVersion"), "engine.serverVersion"
            ),
            "cpus": _integer(engine.get("cpus"), "engine.cpus", minimum=1),
            "memoryBytes": _integer(
                engine.get("memoryBytes"), "engine.memoryBytes", minimum=1
            ),
        },
        "release": {
            "name": release.get("name"),
            "namespace": namespace,
            "chart": release.get("chart"),
            "appVersion": release.get("app_version"),
            "revision": int(str(release.get("revision", "0"))),
            "status": release.get("status"),
        },
        "configuration": {key: configuration.get(key) for key in CONFIGURATION_KEYS},
        "workloads": {
            "unready": unready_workloads,
            "recovered": recovered_workloads,
        },
        # The misconfiguration and its correction, read from the cluster's own answer
        # about the Deployment rather than from the values file the operator passed.
        # A record that quoted the overlay would be quoting an intention.
        "servingRuntimeCpu": {
            "unready": _cpu(unready_workloads, "runtime", "runtime"),
            "recovered": _cpu(recovered_workloads, "runtime", "runtime"),
        },
        "podsUnready": _pods(_cluster_json(cluster_dir, "pods-unready.json")),
        "podsRecovered": _pods(_cluster_json(cluster_dir, "pods-recovered.json")),
        "background": {
            "runningPodsOutsideRelease": len(outside),
            "namespacesWithRunningPodsOutsideRelease": len(
                {
                    _object(item.get("metadata"), "metadata").get("namespace")
                    for item in outside
                }
            ),
        },
        "repository": {
            "revision": _string(repository.get("revision"), "repository.revision"),
            "trackedChangesPresent": bool(repository.get("trackedChangesPresent")),
            "untrackedFilesPresent": bool(repository.get("untrackedFilesPresent")),
            "executedFiles": dict(
                sorted(
                    _object(repository.get("executedFiles"), "executedFiles").items()
                )
            ),
        },
    }
    refuse_private(dumps(environment), "environment")
    return environment


# --------------------------------------------------------------------------
# What the operating script stamped
# --------------------------------------------------------------------------


def _rfc3339(value: Any, field: str) -> str:
    text = _string(value, field)
    if RFC3339.fullmatch(text) is None:
        raise UnreadyError(f"'{field}' is not an RFC 3339 instant in UTC")
    return text


def parse_lifecycle(document: Any, descriptor: Descriptor) -> dict[str, Any]:
    """The instants the operating script stamped, checked for order and for shape.

    Every instant here is the host's wall clock, read by the same shell that sent the
    probes, so the intervals derived from them are differences on one clock. The
    instants the *cluster* reports are kept as the strings it emitted and never
    subtracted from anything: the node is a container whose clock this record has no
    reason to assume is the host's.
    """
    # In the order the run performs them. The release is installed first, its runtime
    # container starts, its socket opens, and only then is the idle baseline taken --
    # because a baseline taken before the install would be a baseline of an empty
    # namespace. An earlier version of this reader had the baseline first and refused
    # the first complete run for it.
    lifecycle = _object(document, "lifecycle")
    install = _object(lifecycle.get("install"), "install")
    installed = _integer(
        install.get("issuedEpochMs"), "install.issuedEpochMs", minimum=1
    )
    running = _integer(
        install.get("runtimeContainerRunningEpochMs"),
        "install.runtimeContainerRunningEpochMs",
        minimum=installed,
    )
    # The instant the runtime first answered anything on its own port. It is not
    # plumbing: the chart's liveness probe is a TCP connect, so this is the instant
    # liveness starts being satisfied, and every statement this record makes about a
    # healthy process not being killed is made about the window that begins after it.
    socket_open = _integer(
        install.get("runtimeSocketOpenEpochMs"),
        "install.runtimeSocketOpenEpochMs",
        minimum=running,
    )

    idle = _object(lifecycle.get("idleBaseline"), "idleBaseline")
    idle_start = _integer(
        idle.get("startEpochMs"), "idleBaseline.startEpochMs", minimum=socket_open
    )
    idle_end = _integer(
        idle.get("endEpochMs"), "idleBaseline.endEpochMs", minimum=idle_start
    )

    unready = _object(lifecycle.get("unreadyWindow"), "unreadyWindow")
    unready_start = _integer(
        unready.get("startEpochMs"), "unreadyWindow.start", minimum=idle_end
    )
    unready_end = _integer(
        unready.get("endEpochMs"), "unreadyWindow.end", minimum=unready_start
    )
    held = unready_end - unready_start
    # The window the descriptor registered, applied to the window the run actually
    # held. A run that stopped early would publish "readiness stayed false" over a
    # shorter span than the one that was pre-registered for it.
    if held + descriptor.poll_interval_ms < descriptor.unready_window_seconds * 1000:
        raise UnreadyRefused(
            f"the unready window was held for {held} ms and the descriptor registered "
            f"{descriptor.unready_window_seconds * 1000} ms"
        )

    upgrade = _object(lifecycle.get("upgrade"), "upgrade")
    upgraded = _integer(
        upgrade.get("issuedEpochMs"), "upgrade.issuedEpochMs", minimum=unready_end
    )
    runtime_ready = _integer(
        upgrade.get("runtimeReadyEpochMs"),
        "upgrade.runtimeReadyEpochMs",
        minimum=upgraded,
    )
    api_ready = _integer(
        upgrade.get("apiReadyEpochMs"), "upgrade.apiReadyEpochMs", minimum=upgraded
    )

    recovered = _object(lifecycle.get("recoveredWindow"), "recoveredWindow")
    recovered_start = _integer(
        recovered.get("startEpochMs"),
        "recoveredWindow.start",
        minimum=max(runtime_ready, api_ready),
    )
    recovered_end = _integer(
        recovered.get("endEpochMs"), "recoveredWindow.end", minimum=recovered_start
    )
    settled = _integer(
        lifecycle.get("settledEpochMs"), "settledEpochMs", minimum=recovered_end
    )

    release = _object(lifecycle.get("release"), "release")
    acquisition = _object(lifecycle.get("acquisition"), "acquisition")
    claims = _object(lifecycle.get("claims"), "claims")
    interventions = [
        _member(entry, "interventions[]", INTERVENTIONS)
        for entry in _list(lifecycle.get("interventions"), "interventions")
    ]

    return {
        "idleBaseline": {"startEpochMs": idle_start, "endEpochMs": idle_end},
        "install": {
            "issuedEpochMs": installed,
            "runtimeContainerRunningEpochMs": running,
            "runtimeSocketOpenEpochMs": socket_open,
            "runtimePodName": _string(
                install.get("runtimePodName"), "install.runtimePodName"
            ),
            "runtimePodUid": _string(
                install.get("runtimePodUid"), "install.runtimePodUid"
            ),
            "runtimeContainerStartedAt": _rfc3339(
                install.get("runtimeContainerStartedAt"),
                "install.runtimeContainerStartedAt",
            ),
            "initContainerName": _string(
                install.get("initContainerName"), "install.initContainerName"
            ),
            "initExitCode": _integer(
                install.get("initExitCode"), "install.initExitCode", maximum=255
            ),
        },
        "unreadyWindow": {
            "startEpochMs": unready_start,
            "endEpochMs": unready_end,
            "heldMs": held,
        },
        "upgrade": {
            "issuedEpochMs": upgraded,
            "runtimeReadyEpochMs": runtime_ready,
            "apiReadyEpochMs": api_ready,
            "runtimePodName": _string(
                upgrade.get("runtimePodName"), "upgrade.runtimePodName"
            ),
            "runtimePodUid": _string(
                upgrade.get("runtimePodUid"), "upgrade.runtimePodUid"
            ),
            "initContainerName": _string(
                upgrade.get("initContainerName"), "upgrade.initContainerName"
            ),
            "initExitCode": _integer(
                upgrade.get("initExitCode"), "upgrade.initExitCode", maximum=255
            ),
        },
        "recoveredWindow": {
            "startEpochMs": recovered_start,
            "endEpochMs": recovered_end,
        },
        "settledEpochMs": settled,
        "release": {
            "revisionBefore": _integer(
                release.get("revisionBefore"), "release.revisionBefore", minimum=1
            ),
            "revisionAfter": _integer(
                release.get("revisionAfter"), "release.revisionAfter", minimum=1
            ),
        },
        "acquisition": {
            "jobCountBefore": _integer(
                acquisition.get("jobCountBefore"), "acquisition.jobCountBefore"
            ),
            "jobCountAfter": _integer(
                acquisition.get("jobCountAfter"), "acquisition.jobCountAfter"
            ),
        },
        "claims": {
            "countBefore": _integer(claims.get("countBefore"), "claims.countBefore"),
            "countAfter": _integer(claims.get("countAfter"), "claims.countAfter"),
        },
        "interventions": interventions,
    }


def parse_readiness(document: Any, descriptor: Descriptor) -> list[dict[str, Any]]:
    """The readiness samples, checked for order, shape, phase, and count."""
    # The operating script writes the samples under a "readiness" member so that the
    # file says what it is; a bare list of samples is accepted as well, because a
    # reader of this function should not have to know which one it was handed.
    body = _object(document, "readiness record")
    body = _object(body.get("readiness", body), "readiness")
    samples = [
        _object(entry, "samples[]") for entry in _list(body.get("samples"), "samples")
    ]
    # Counted over the unready window rather than over the file. The claim this record
    # makes is that readiness stayed false for a window, and samples taken after the
    # fix do not support it however many of them there are.
    unready = sum(1 for sample in samples if sample.get("phase") == "unready")
    if unready < descriptor.minimum_samples:
        raise UnreadyRefused(
            f"the run kept {unready} readiness sample(s) inside the unready window and "
            f"the descriptor asks for at least {descriptor.minimum_samples}"
        )
    parsed: list[dict[str, Any]] = []
    previous = 0
    for sample in samples:
        at = _integer(sample.get("atEpochMs"), "sample.atEpochMs", minimum=previous)
        previous = at
        parsed.append(
            {
                "atEpochMs": at,
                "phase": _member(sample.get("phase"), "sample.phase", PHASES),
                "readTookMs": _integer(sample.get("readTookMs"), "sample.readTookMs"),
                "runtimePodsPresent": _integer(
                    sample.get("runtimePodsPresent"), "sample.runtimePodsPresent"
                ),
                "runtimePodsReady": _integer(
                    sample.get("runtimePodsReady"), "sample.runtimePodsReady"
                ),
                "runtimeEndpointsReady": _integer(
                    sample.get("runtimeEndpointsReady"), "sample.runtimeEndpointsReady"
                ),
                "apiPodsReady": _integer(
                    sample.get("apiPodsReady"), "sample.apiPodsReady"
                ),
                "apiEndpointsReady": _integer(
                    sample.get("apiEndpointsReady"), "sample.apiEndpointsReady"
                ),
                "runtimeRestartCount": _integer(
                    sample.get("runtimeRestartCount"), "sample.runtimeRestartCount"
                ),
                "apiRestartCount": _integer(
                    sample.get("apiRestartCount"), "sample.apiRestartCount"
                ),
            }
        )
    if not any(sample["phase"] == "unready" for sample in parsed):
        raise UnreadyRefused(
            "no readiness sample was taken while the model was unready"
        )
    return parsed


def parse_probes(text: str, descriptor: Descriptor) -> list[dict[str, Any]]:
    """Every probe the run sent, checked against the surfaces the descriptor registers.

    A probe naming a surface, a method, or a path the descriptor does not register is
    refused rather than kept: an expectation registered before a run is only worth
    something if what ran is what was registered.
    """
    by_id = {surface.probe_id: surface for surface in descriptor.surfaces}
    parsed: list[dict[str, Any]] = []
    previous = 0
    for number, line in enumerate(text.replace("\r\n", "\n").splitlines(), start=1):
        if not line.strip():
            continue
        entry = _object(
            _read_json_text(line, f"probe record on line {number}"), "probe"
        )
        probe_id = _string(entry.get("probeId"), "probe.probeId")
        surface = by_id.get(probe_id)
        if surface is None:
            raise UnreadyRefused(
                f"a probe names surface '{probe_id}', which the descriptor does not "
                "register"
            )
        for field, expected in (
            ("tier", surface.tier),
            ("method", surface.method),
            ("path", surface.path),
        ):
            if entry.get(field) != expected:
                raise UnreadyRefused(
                    f"probe '{probe_id}' was sent with a {field} the descriptor does "
                    "not register"
                )
        at = _integer(entry.get("atEpochMs"), "probe.atEpochMs", minimum=previous)
        previous = at
        status = _integer(entry.get("status"), "probe.status", minimum=0, maximum=599)
        code = entry.get("errorCode")
        if code is not None:
            code = _string(code, "probe.errorCode")
            if code not in descriptor.refusal_codes:
                raise UnreadyRefused(
                    f"probe '{probe_id}' reports canonical code '{code}', which is not "
                    "in the vocabulary the descriptor registers"
                )
        condition = entry.get("conditionId")
        if condition is not None:
            condition = _string(condition, "probe.conditionId")
        retryable = entry.get("retryable")
        if retryable is not None and not isinstance(retryable, bool):
            raise UnreadyError("'probe.retryable' must be true, false, or absent")
        tokens = entry.get("outputTokens")
        if tokens is not None:
            tokens = _integer(tokens, "probe.outputTokens")
        digest = entry.get("bodySha256")
        if (
            digest is not None
            and SHA256.fullmatch(_string(digest, "bodySha256")) is None
        ):
            raise UnreadyError("'probe.bodySha256' is not a SHA-256 digest")
        parsed.append(
            {
                "probeId": probe_id,
                "phase": _member(entry.get("phase"), "probe.phase", PHASES),
                "round": _integer(entry.get("round"), "probe.round", minimum=1),
                "tier": surface.tier,
                "method": surface.method,
                "path": surface.path,
                "atEpochMs": at,
                "latencyMs": _integer(entry.get("latencyMs"), "probe.latencyMs"),
                "status": status,
                "errorCode": code,
                "conditionId": condition,
                "retryable": retryable,
                "detail": _string(entry.get("detail"), "probe.detail"),
                "bodyBytes": _integer(entry.get("bodyBytes"), "probe.bodyBytes"),
                "bodySha256": digest,
                "outputTokens": tokens,
            }
        )
    if not parsed:
        raise UnreadyRefused("the probe record set is empty")
    return parsed


def build_diagnostics(index_path: Path, *, excerpt_lines: int) -> dict[str, Any]:
    """The diagnostics document, from the captures the operating script wrote.

    **Why the excerpt is filtered rather than the capture refused.** `kubectl describe
    pod` prints the pod's address. A record is published and an address is one of the
    three shapes a published record may not carry, so the first complete execution of
    this experiment was refused at the last step by its own privacy check -- correctly,
    and uselessly, because the diagnostic an operator needs is in the events and not in
    the address. So the excerpt keeps the lines that carry none of the three shapes and
    **counts the ones it withheld**, which the record publishes beside it. The capture
    itself is written whole into the run directory, which version control ignores.

    Nothing is rewritten: a line is kept entire or withheld entire. There is no
    masking, because a masked line reads as a line somebody checked.
    """
    captures: list[dict[str, Any]] = []
    for row in index_path.read_text(encoding="utf-8").splitlines():
        if not row.strip():
            continue
        capture_id, phase, path = row.split(" ", 2)
        raw = Path(path).read_bytes()
        text = raw.decode("utf-8", errors="replace")
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        # From the end: a log's last lines are where it stopped, and where it stopped
        # is the diagnostic.
        tail = lines[-excerpt_lines:]
        kept = [line for line in tail if not carries_private_value(line)]
        captures.append(
            {
                "captureId": capture_id,
                "phase": phase,
                "lines": len(lines),
                "bytes": len(raw),
                "sha256": text_digest(text),
                "excerptLinesWithheld": len(tail) - len(kept),
                "excerpt": "\n".join(kept)
                or "(every line of this excerpt was withheld)",
            }
        )
    return {"diagnostics": {"captures": captures}}


def parse_diagnostics(document: Any, descriptor: Descriptor) -> list[dict[str, Any]]:
    """The captures, checked against the ones the descriptor registers."""
    body = _object(document, "diagnostics record")
    body = _object(body.get("diagnostics", body), "diagnostics")
    captured = {
        _string(_object(entry, "captures[]").get("captureId"), "captureId"): _object(
            entry, "captures[]"
        )
        for entry in _list(body.get("captures"), "captures")
    }
    rows: list[dict[str, Any]] = []
    for registered in descriptor.captures:
        entry = captured.get(registered.capture_id)
        if entry is None:
            raise UnreadyRefused(
                f"the run captured no '{registered.capture_id}', which the descriptor "
                "registers"
            )
        lines = _integer(entry.get("lines"), "capture.lines")
        rows.append(
            {
                "captureId": registered.capture_id,
                "what": registered.what,
                "identifiesCause": registered.identifies_cause,
                "expectation": registered.expectation,
                "phase": _member(entry.get("phase"), "capture.phase", PHASES),
                "lines": lines,
                "bytes": _integer(entry.get("bytes"), "capture.bytes"),
                "sha256": _string(entry.get("sha256"), "capture.sha256"),
                "empty": lines == 0,
                # How many lines of the excerpt were withheld because they carried a
                # host path, a user directory, or an address. Published rather than
                # silently dropped: a redaction nobody can count is a redaction
                # nobody can review.
                "excerptLinesWithheld": _integer(
                    entry.get("excerptLinesWithheld"), "capture.excerptLinesWithheld"
                ),
                # The excerpt is the only place a capture's own words reach a record.
                # It is refused for private shapes with everything else, and it is a
                # bounded excerpt rather than the capture, because the capture is a
                # log and a log is unbounded.
                "excerpt": _string(entry.get("excerpt"), "capture.excerpt"),
            }
        )
    return rows


# --------------------------------------------------------------------------
# What the collector answered
# --------------------------------------------------------------------------


def _label_key(labels: Mapping[str, Any]) -> str:
    return ",".join(f"{key}={labels[key]}" for key in sorted(labels))


def _reading(element: Mapping[str, Any], at_ms: int | None) -> str | None:
    """The last value at or before an instant, as the string Prometheus returned."""
    if at_ms is None:
        return None
    latest: str | None = None
    for point in _list(element.get("values"), "series.values"):
        pair = _list(point, "series.values[]")
        if len(pair) != 2:
            raise UnreadyError("a range sample is not a pair")
        if float(pair[0]) * 1000 <= at_ms:
            latest = str(pair[1])
    return latest


def _telemetry_series(
    descriptor: Descriptor,
    telemetry: Mapping[str, Any],
    *,
    unready_end_ms: int,
    settled_ms: int,
) -> list[dict[str, Any]]:
    """Each registered expression, what it answered, and what it was registered to do.

    Nothing here decides whether a signal exposed the state. The readings either side
    are recorded and the registered expectation is recorded beside them; saying what
    the pair means is an analysis, and ADR 0013 D4 keeps that in a reviewed document
    rather than in a tool.
    """
    answered = {
        _string(entry.get("seriesId"), "telemetry.series[].seriesId"): _object(
            entry, "telemetry.series[]"
        )
        for entry in _list(telemetry.get("series"), "telemetry.series")
    }
    rows = []
    for registered in descriptor.series:
        entry = answered.get(registered.series_id)
        if entry is None:
            raise UnreadyRefused(
                f"the collector was not asked for '{registered.series_id}'"
            )
        if entry.get("expr") != registered.expr:
            raise UnreadyRefused(
                f"'{registered.series_id}' was asked with an expression the descriptor "
                "does not register"
            )
        status = _string(entry.get("status"), "telemetry.series[].status")
        elements = [
            _object(element, "telemetry.series[].result[]")
            for element in _list(entry.get("result"), "telemetry.series[].result")
        ]
        while_unready: dict[str, str | None] = {}
        after_recovery: dict[str, str | None] = {}
        for element in elements:
            key = _label_key(_object(element.get("labels"), "series.labels"))
            while_unready[key] = _reading(element, unready_end_ms)
            after_recovery[key] = _reading(element, settled_ms)
        present_unready = sorted(
            key for key, value in while_unready.items() if value is not None
        )
        present_after = sorted(
            key for key, value in after_recovery.items() if value is not None
        )
        shared = sorted(set(present_unready) & set(present_after))
        rows.append(
            {
                "seriesId": registered.series_id,
                "expr": registered.expr,
                "answerability": registered.answerability,
                "exposure": registered.exposure,
                "expectation": registered.expectation,
                "status": status,
                "error": str(entry.get("error", "")) or None,
                "seriesReturned": len(elements),
                "labelSetsWhileUnready": present_unready,
                "labelSetsAfterRecovery": present_after,
                "labelSetsThatAppeared": sorted(
                    set(present_after) - set(present_unready)
                ),
                "labelSetsThatDisappeared": sorted(
                    set(present_unready) - set(present_after)
                ),
                "sharedLabelSetsWithChangedValues": [
                    key for key in shared if while_unready[key] != after_recovery[key]
                ],
                "readingWhileUnready": dict(sorted(while_unready.items())),
                "readingAfterRecovery": dict(sorted(after_recovery.items())),
            }
        )
    return rows


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"checkId": name, "passed": passed, "detail": detail}


def _in_phase(rows: Sequence[Mapping[str, Any]], phase: str) -> list[Mapping[str, Any]]:
    return [row for row in rows if row["phase"] == phase]


def _for_probe(
    rows: Sequence[Mapping[str, Any]], probe_id: str, phase: str
) -> list[Mapping[str, Any]]:
    return [row for row in rows if row["probeId"] == probe_id and row["phase"] == phase]


def _counted(values: Sequence[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = "null" if value is None else str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def build_record(
    descriptor: Descriptor,
    *,
    environment_text: str,
    lifecycle_text: str,
    readiness_text: str,
    probes_text: str,
    diagnostics_text: str,
    telemetry_text: str,
) -> dict[str, Any]:
    """The record, as a pure function of the six committed inputs.

    Every input is refused before it is read if it carries a host path, a user
    directory, or an address that is not loopback: a record is published and the run
    that produced it was not. That check does more work here than in any other
    experiment in this repository, because one of the six inputs is a diagnostic
    bundle.

    **What the record decides and what it leaves alone.** It decides whether the
    model was ever ready, whether the runtime process stayed up, whether the container
    was restarted, which canonical code a caller actually met, whether the registered
    diagnostics were captured, and whether a real completion came back after the fix.
    It does not decide whether a telemetry signal exposed the state: each expression's
    registered expectation and its readings either side are recorded, and reading the
    pair belongs to a reviewed document (ADR 0013 D4).
    """
    for text, what in (
        (environment_text, "environment"),
        (lifecycle_text, "lifecycle record"),
        (readiness_text, "readiness record"),
        (probes_text, "probe record set"),
        (diagnostics_text, "diagnostics record"),
        (telemetry_text, "telemetry record"),
    ):
        refuse_private(text, what)

    environment = _object(
        _read_json_text(environment_text, "environment"), "environment"
    )
    lifecycle = parse_lifecycle(
        _read_json_text(lifecycle_text, "lifecycle record"), descriptor
    )
    readiness = parse_readiness(
        _read_json_text(readiness_text, "readiness record"), descriptor
    )
    probes = parse_probes(probes_text, descriptor)
    diagnostics = parse_diagnostics(
        _read_json_text(diagnostics_text, "diagnostics record"), descriptor
    )
    telemetry = _object(
        _read_json_text(telemetry_text, "telemetry record"), "telemetry record"
    )

    unready_end = int(lifecycle["unreadyWindow"]["endEpochMs"])
    upgraded_ms = int(lifecycle["upgrade"]["issuedEpochMs"])
    runtime_ready_ms = int(lifecycle["upgrade"]["runtimeReadyEpochMs"])
    api_ready_ms = int(lifecycle["upgrade"]["apiReadyEpochMs"])
    settled_ms = int(lifecycle["settledEpochMs"])

    unready_samples = _in_phase(readiness, "unready")
    recovered_samples = _in_phase(readiness, "recovered")
    unready_probes = _in_phase(probes, "unready")
    recovered_probes = _in_phase(probes, "recovered")

    completion = next(
        surface
        for surface in descriptor.surfaces
        if surface.method == "POST" and surface.tier == "platform-api"
    )
    runtime_health = next(
        surface for surface in descriptor.surfaces if surface.tier == "serving-runtime"
    )

    refused = _for_probe(probes, completion.probe_id, "unready")
    served = [
        row
        for row in _for_probe(probes, completion.probe_id, "recovered")
        if row["status"] == 200
    ]
    first_served = min(served, key=lambda row: int(row["atEpochMs"]), default=None)
    observed_codes = sorted(
        {str(row["errorCode"]) for row in refused if row["errorCode"] is not None}
    )
    observed_conditions = sorted(
        {str(row["conditionId"]) for row in refused if row["conditionId"] is not None}
    )

    restart_counts = [int(sample["runtimeRestartCount"]) for sample in unready_samples]
    highest_restart = max(restart_counts, default=0)
    gap_ms = max(
        (
            int(unready_samples[index + 1]["atEpochMs"])
            - int(unready_samples[index]["atEpochMs"])
            for index in range(len(unready_samples) - 1)
        ),
        default=0,
    )
    gap_ceiling = descriptor.poll_interval_ms * READINESS_GAP_MULTIPLE

    budgets = _object(descriptor.document.get("readiness"), "readiness")
    served_at_ms = None if first_served is None else int(first_served["atEpochMs"])
    recovery_ms = None if served_at_ms is None else served_at_ms - upgraded_ms

    timings: dict[str, Any] = {
        "installToRuntimeContainerRunningMs": int(
            lifecycle["install"]["runtimeContainerRunningEpochMs"]
        )
        - int(lifecycle["install"]["issuedEpochMs"]),
        "runtimeContainerRunningToSocketOpenMs": int(
            lifecycle["install"]["runtimeSocketOpenEpochMs"]
        )
        - int(lifecycle["install"]["runtimeContainerRunningEpochMs"]),
        "unreadyWindowHeldMs": int(lifecycle["unreadyWindow"]["heldMs"]),
        "registeredUnreadyWindowMs": descriptor.unready_window_seconds * 1000,
        "runtimeStartupProbeBudgetMs": RUNTIME_STARTUP_BUDGET_MS,
        "unreadyWindowAsShareOfStartupBudget": round(
            int(lifecycle["unreadyWindow"]["heldMs"]) / RUNTIME_STARTUP_BUDGET_MS, 4
        ),
        "upgradeToRuntimeReadyMs": runtime_ready_ms - upgraded_ms,
        "upgradeToApiReadyMs": api_ready_ms - upgraded_ms,
        "upgradeToFirstServedCompletionMs": recovery_ms,
        "firstServedCompletionEpochMs": served_at_ms,
        "note": (
            "One release, misconfigured once, on one host. Not an availability figure, "
            "a service-level objective, an error budget, a recovery-time objective, or "
            "a number anything may be compared against. The unready window is how long "
            "this run held the release in that state, not how long the model would "
            "have taken to load: the load was starved rather than failed, and the "
            "kubelet's own startup budget is the upper bound on how long Kubernetes "
            "would have left it there."
        ),
    }

    #: Every interval a reader would take as a duration. A negative one is a figure
    #: stamped from the wrong end, which is the defect an independent review of
    #: V1-S3-003-PR2 found and the first execution of V1-S4-006 repeated, so it is
    #: refused rather than published.
    non_negative = (
        "installToRuntimeContainerRunningMs",
        "runtimeContainerRunningToSocketOpenMs",
        "unreadyWindowHeldMs",
        "upgradeToRuntimeReadyMs",
        "upgradeToApiReadyMs",
        "upgradeToFirstServedCompletionMs",
    )
    negative = {
        name: timings[name]
        for name in non_negative
        if isinstance(timings[name], int) and timings[name] < 0
    }

    series_rows = _telemetry_series(
        descriptor, telemetry, unready_end_ms=unready_end, settled_ms=settled_ms
    )
    absences = [
        row for row in series_rows if row["exposure"] in ("nothing-emits", "no-source")
    ]
    registered_present = [
        row
        for row in series_rows
        if row["exposure"] in ("expected-to-expose", "expected-not-to-expose")
    ]

    naming = [row for row in diagnostics if row["identifiesCause"] == "yes"]
    pods_unready = {
        str(_object(pod, "podsUnready[]")["role"]): _object(pod, "podsUnready[]")
        for pod in _list(environment.get("podsUnready"), "podsUnready")
    }
    # A tier can carry two pods for a few seconds after an upgrade: the replacement and
    # the predecessor on its way out. A ready one is what the question "did this tier
    # come back" is about, so a ready pod wins where both are present. Neither is
    # hidden: the environment keeps the whole list.
    pods_recovered: dict[str, Any] = {}
    for entry in _list(environment.get("podsRecovered"), "podsRecovered"):
        pod = _object(entry, "podsRecovered[]")
        role = str(pod["role"])
        held = pods_recovered.get(role)
        if held is None or (pod.get("ready") and not held.get("ready")):
            pods_recovered[role] = pod
    cpu = _object(environment.get("servingRuntimeCpu"), "servingRuntimeCpu")

    def _expected(probe_id: str, phase: str, status: int) -> tuple[int, int]:
        rows = _for_probe(probes, probe_id, phase)
        return sum(1 for row in rows if row["status"] == status), len(rows)

    checks = [
        _check(
            "the-release-installed-with-the-misconfiguration",
            int(lifecycle["release"]["revisionBefore"]) >= 1
            and int(lifecycle["install"]["initExitCode"]) == 0,
            f"revision {lifecycle['release']['revisionBefore']} installed and the "
            f"'{lifecycle['install']['initContainerName']}' init container exited "
            f"{lifecycle['install']['initExitCode']}; chart validation and the model "
            "integrity check both accepted it",
        ),
        _check(
            "the-model-artifact-was-never-in-question",
            int(lifecycle["install"]["initExitCode"]) == 0
            and int(lifecycle["upgrade"]["initExitCode"]) == 0,
            "the byte count and SHA-256 check passed in both the misconfigured pod and "
            "the corrected one, which is what separates this from an artifact fault",
        ),
        _check(
            "the-runtime-container-started-and-opened-its-port",
            all(int(sample["runtimePodsPresent"]) >= 1 for sample in unready_samples)
            and bool(unready_samples),
            f"{len(unready_samples)} sample(s) across the unready window, every one of "
            "them with a serving runtime pod present; the process answered on its own "
            f"port {timings['runtimeContainerRunningToSocketOpenMs']} ms after the "
            "container was reported running, which is what satisfies the chart's TCP "
            "liveness probe",
        ),
        _check(
            "readiness-was-false-for-the-whole-unready-window",
            bool(unready_samples)
            and all(int(sample["runtimePodsReady"]) == 0 for sample in unready_samples),
            "no sample in the unready window reported a ready serving runtime pod",
        ),
        _check(
            "the-runtime-service-had-no-ready-endpoint-while-unready",
            bool(unready_samples)
            and all(
                int(sample["runtimeEndpointsReady"]) == 0 for sample in unready_samples
            ),
            "the runtime Service was willing to send traffic to no address for the "
            "whole window",
        ),
        _check(
            "the-runtime-answered-the-loading-status-throughout",
            _expected(runtime_health.probe_id, "unready", runtime_health.unready_status)
            == (
                len(_for_probe(probes, runtime_health.probe_id, "unready")),
                len(_for_probe(probes, runtime_health.probe_id, "unready")),
            )
            and bool(_for_probe(probes, runtime_health.probe_id, "unready")),
            f"{_expected(runtime_health.probe_id, 'unready', runtime_health.unready_status)[0]}"
            f" of {_expected(runtime_health.probe_id, 'unready', runtime_health.unready_status)[1]}"
            f" asks answered {runtime_health.unready_status}, which is the status the "
            "adapter maps to LOADING",
        ),
        _check(
            "liveness-did-not-restart-a-healthy-process",
            highest_restart == 0,
            f"the serving runtime container's restart count was {highest_restart} at "
            f"every sample. The chart's liveness probe is a TCP connect and the socket "
            "was open throughout, which is why a model that never became ready did not "
            "become a restart loop inside this window",
        ),
        _check(
            "every-completion-while-unready-was-refused-canonically",
            bool(refused)
            and all(
                row["status"] == completion.unready_status
                and row["errorCode"] in descriptor.refusal_codes
                for row in refused
            ),
            f"{len(refused)} completion(s) asked while the model was unready; statuses "
            f"{_counted([row['status'] for row in refused])}, codes "
            f"{_counted([row['errorCode'] for row in refused])}",
        ),
        _check(
            "one-canonical-code-answered-the-whole-unready-window",
            len(observed_codes) == 1,
            f"the codes observed were {', '.join(observed_codes) or 'none'}. More than "
            "one would mean a caller could not have been told the same thing twice",
        ),
        _check(
            "every-canonical-refusal-was-retryable",
            bool(refused) and all(row["retryable"] is True for row in refused),
            "each refusal carried retryable=true, which is what both codes ADR 0010 D8 "
            "maps this situation to are defined as",
        ),
        _check(
            "the-api-stayed-answerable-while-its-adapter-could-not-serve",
            _expected("api-liveness", "unready", 200)[0]
            == _expected("api-liveness", "unready", 200)[1]
            and _expected("api-liveness", "unready", 200)[1] > 0,
            "the API's liveness path answered 200 at every ask while its readiness path "
            "refused, which is the split that stops a not-ready API being restarted",
        ),
        _check(
            "the-api-reported-itself-not-ready-while-unready",
            _expected("api-readiness", "unready", 503)[0]
            == _expected("api-readiness", "unready", 503)[1]
            and _expected("api-readiness", "unready", 503)[1] > 0,
            "the API's readiness path answered 503 at every ask in the unready window",
        ),
        _check(
            "every-registered-diagnostic-was-captured",
            all(not row["empty"] for row in diagnostics),
            "; ".join(
                f"{row['captureId']} kept {row['lines']} line(s)" for row in diagnostics
            ),
        ),
        _check(
            "every-capture-excerpt-is-publishable",
            all(not carries_private_value(str(row["excerpt"])) for row in diagnostics),
            "; ".join(
                f"{row['captureId']} withheld {row['excerptLinesWithheld']} line(s)"
                for row in diagnostics
            ),
        ),
        _check(
            "a-diagnostic-registered-as-naming-the-cause-was-captured",
            bool(naming) and all(not row["empty"] for row in naming),
            "; ".join(f"{row['captureId']}" for row in naming)
            or "no capture was registered as naming the cause",
        ),
        _check(
            "the-misconfiguration-is-readable-from-the-cluster",
            _object(cpu.get("unready"), "cpu.unready")
            != _object(cpu.get("recovered"), "cpu.recovered"),
            f"the serving runtime container's processor limit was "
            f"{_object(cpu.get('unready'), 'cpu.unready').get('limit')} while unready "
            f"and {_object(cpu.get('recovered'), 'cpu.recovered').get('limit')} after "
            "the fix, read from the Deployment rather than from the values file",
        ),
        _check(
            "the-fix-moved-the-release-revision",
            int(lifecycle["release"]["revisionAfter"])
            > int(lifecycle["release"]["revisionBefore"]),
            f"revision {lifecycle['release']['revisionBefore']} became "
            f"{lifecycle['release']['revisionAfter']}",
        ),
        _check(
            "the-corrected-pod-is-not-the-misconfigured-one",
            lifecycle["upgrade"]["runtimePodUid"]
            != lifecycle["install"]["runtimePodUid"],
            "the serving runtime pod after the fix carries a different uid from the "
            "one that was starved; a first execution of this experiment stamped the "
            "recovery from the misconfigured pod, whose starved load had finished, and "
            "the check exists because of it",
        ),
        _check(
            "the-runtime-became-ready-after-the-fix",
            bool(recovered_samples)
            and any(
                int(sample["runtimePodsReady"]) >= 1 for sample in recovered_samples
            )
            and pods_recovered.get("runtime", {}).get("ready") is True,
            "a sample after the upgrade reported a ready serving runtime pod, and the "
            "pod's own Ready condition agrees",
        ),
        _check(
            "a-real-completion-came-back-after-the-fix",
            first_served is not None and int(first_served.get("outputTokens") or 0) > 0,
            f"a completion came back {recovery_ms} ms after the upgrade with "
            f"{(first_served or {}).get('outputTokens')} output token(s)"
            if first_served is not None
            else "no completion was served after the fix",
        ),
        _check(
            "the-runtime-reported-ready-to-a-caller-after-the-fix",
            _expected(runtime_health.probe_id, "recovered", 200)[0] > 0,
            f"the runtime answered 200 at "
            f"{_expected(runtime_health.probe_id, 'recovered', 200)[0]} of "
            f"{_expected(runtime_health.probe_id, 'recovered', 200)[1]} asks after the fix",
        ),
        _check(
            "every-tier-was-ready-after-the-fix",
            all(pods_recovered.get(role, {}).get("ready") is True for role in ROLES),
            "each of the three tiers reports a pod whose Ready condition is true",
        ),
        _check(
            "the-service-was-restored-within-the-recovery-budget",
            recovery_ms is not None
            and recovery_ms <= _integer(budgets.get("recoveryBudgetMs"), "budget"),
            f"{recovery_ms} ms against a budget of {budgets['recoveryBudgetMs']} ms"
            if recovery_ms is not None
            else "the service was not observed restored to a caller",
        ),
        _check(
            "no-published-interval-is-negative",
            not negative,
            "; ".join(f"{name} is {value} ms" for name, value in negative.items())
            or "every interval a reader would take as a duration is zero or more",
        ),
        _check(
            "readiness-samples-cover-the-unready-window",
            len(unready_samples) >= descriptor.minimum_samples
            and gap_ms <= gap_ceiling,
            f"{len(unready_samples)} sample(s), widest gap {gap_ms} ms against a "
            f"ceiling of {gap_ceiling} ms",
        ),
        _check(
            "the-only-intervention-was-the-registered-fix",
            lifecycle["interventions"] == [EXPECTED_INTERVENTION],
            f"the operating script recorded {lifecycle['interventions']}. This "
            "experiment expects exactly one intervention: a model that cannot load is "
            "not a state a controller reverses",
        ),
        _check(
            "claim-count-unchanged",
            lifecycle["claims"]["countBefore"] == lifecycle["claims"]["countAfter"],
            f"{lifecycle['claims']['countBefore']} claim(s) either side",
        ),
        _check(
            "telemetry-registered-absences-are-absent",
            all(row["seriesReturned"] == 0 for row in absences),
            "; ".join(
                f"{row['seriesId']} returned {row['seriesReturned']} series"
                for row in absences
            )
            or "no absence was registered",
        ),
        _check(
            "telemetry-registered-signals-answered",
            all(
                row["status"] == "success" and row["seriesReturned"] > 0
                for row in registered_present
            ),
            "; ".join(
                f"{row['seriesId']} {row['status']} with {row['seriesReturned']} series"
                for row in registered_present
            ),
        ),
    ]

    observations = [
        "The model's readiness is read from the runtime's own answer, not inferred "
        "from the API's conclusion. 503 is the status "
        "src/inferops/adapters/llama_cpp/readiness.py maps to LOADING and 200 is the "
        "only one it maps to READY, so asking the runtime directly is asking the "
        "question the adapter asks.",
        "Both request surfaces are reached through a forward to a pod rather than to "
        "a Service. A release whose model is not ready has no ready endpoint on "
        "either Service, so a Service forward would have measured kube-proxy refusing "
        "a connection rather than a workload answering.",
        f"The canonical code a caller met while the model was not ready: "
        f"{', '.join(observed_codes) or 'none observed'}. ADR 0010 D8 maps a loading "
        "runtime to model-not-ready and an unreachable one to capability-unavailable, "
        "and which one arrives depends on whether the adapter could reach the runtime "
        "at all -- a question the release's own readiness gating answers before the "
        "adapter does. The condition the API named for it: "
        f"{', '.join(observed_conditions) or 'none reported'}.",
        "The socket is the liveness answer. The runtime answered on its own port "
        f"{timings['runtimeContainerRunningToSocketOpenMs']} ms after its container "
        "was reported running and went on answering for the whole window, which is "
        "what a TCP-connect liveness probe asks and is why a model that never became "
        "ready did not look like a dead process to the kubelet.",
        f"The serving runtime container's restart count across the unready window: "
        f"{highest_restart}. The window was held for "
        f"{lifecycle['unreadyWindow']['heldMs']} ms against a startup probe budget of "
        f"{RUNTIME_STARTUP_BUDGET_MS} ms, so this says the process was not killed "
        "inside that budget and says nothing about what happens past it.",
        "The model load was starved rather than failed. Nothing here establishes that "
        "the model would never have loaded; it establishes that it had not, that the "
        "process was healthy while it had not, and that correcting one value got it "
        "back.",
        "That the artifact is intact is not inferred. The integrity init container ran "
        "in both pods and exited zero in both, which is the same check a replacement "
        "pod runs and is why an artifact fault is excluded rather than assumed away.",
        "The diagnostics an operator would look at are safe to publish only after "
        f"{sum(int(row['excerptLinesWithheld']) for row in diagnostics)} line(s) were "
        "withheld from their excerpts. `kubectl describe pod` prints the pod's "
        "address, and an address is one of the three shapes a committed record in "
        "this repository may not carry. The captures themselves are written whole "
        "into the run directory, which version control ignores.",
        "The instants the cluster reported for the runtime container are kept as the "
        "strings it emitted. They come from the node's clock and nothing here "
        "subtracts them from an instant read on the host's.",
    ]

    inputs = {
        "environment": text_digest(environment_text),
        "lifecycle": text_digest(lifecycle_text),
        "readiness": text_digest(readiness_text),
        "probes": text_digest(probes_text),
        "diagnostics": text_digest(diagnostics_text),
        "telemetry": text_digest(telemetry_text),
    }

    record = {
        "schemaVersion": RECORD_SCHEMA,
        "kind": RECORD_KIND,
        "experimentId": EXPECTED_EXPERIMENT_ID,
        "experimentVersion": descriptor.document["experimentVersion"],
        "descriptorSha256": descriptor.sha256,
        "valuesOverlaySha256": descriptor.overlay_sha256,
        "evidenceClass": EXPECTED_EVIDENCE_CLASS,
        "evidenceLabel": EXPECTED_EVIDENCE_LABEL,
        "certificationCeiling": EXPECTED_CEILING,
        "productionBenchmark": False,
        "portableCapacityClaim": False,
        "availabilityClaim": False,
        "boundary": descriptor.document["boundary"],
        "distinctProofQuestion": descriptor.document["distinctProofQuestion"],
        "environment": environment,
        "disruption": {
            "mechanism": DISRUPTION_MECHANISM,
            "target": DISRUPTION_TARGET,
            "scope": DISRUPTION_SCOPE,
            "appliedAt": DISRUPTION_APPLIED_AT,
            "reversedBy": DISRUPTION_REVERSED_BY,
            "valuesOverlayRef": descriptor.document["disruption"]["valuesOverlayRef"],
            "overlaySetsOnly": list(OVERLAY_KEYS),
            "rejectedMechanisms": list(
                descriptor.document["disruption"]["rejectedMechanisms"]
            ),
            "servingRuntimeCpu": cpu,
            "integrityInitContainer": lifecycle["install"]["initContainerName"],
            "integrityInitExitCode": lifecycle["install"]["initExitCode"],
        },
        "schedule": {
            "idleBaseline": lifecycle["idleBaseline"],
            "install": lifecycle["install"],
            "unreadyWindow": lifecycle["unreadyWindow"],
            "upgrade": lifecycle["upgrade"],
            "recoveredWindow": lifecycle["recoveredWindow"],
            "settledEpochMs": settled_ms,
        },
        "timings": timings,
        "readinessAcrossTheWindow": {
            "note": (
                "Four places that disagree on purpose: the runtime pod's own Ready "
                "condition, the addresses the runtime Service is willing to use, the "
                "API pod's own Ready condition, and the runtime container's restart "
                "count. The last is the one this experiment is really asking about."
            ),
            "unready": {
                "samples": len(unready_samples),
                "runtimePodsReady": _counted(
                    [sample["runtimePodsReady"] for sample in unready_samples]
                ),
                "runtimeEndpointsReady": _counted(
                    [sample["runtimeEndpointsReady"] for sample in unready_samples]
                ),
                "apiPodsReady": _counted(
                    [sample["apiPodsReady"] for sample in unready_samples]
                ),
                "apiEndpointsReady": _counted(
                    [sample["apiEndpointsReady"] for sample in unready_samples]
                ),
                "highestRuntimeRestartCount": highest_restart,
                "highestApiRestartCount": max(
                    (int(sample["apiRestartCount"]) for sample in unready_samples),
                    default=0,
                ),
                "widestSampleGapMs": gap_ms,
            },
            "recovered": {
                "samples": len(recovered_samples),
                "runtimePodsReady": _counted(
                    [sample["runtimePodsReady"] for sample in recovered_samples]
                ),
                "runtimeEndpointsReady": _counted(
                    [sample["runtimeEndpointsReady"] for sample in recovered_samples]
                ),
                "apiEndpointsReady": _counted(
                    [sample["apiEndpointsReady"] for sample in recovered_samples]
                ),
            },
            "samples": readiness,
        },
        "callerSurface": {
            "note": (
                "One round of probes every registered interval, not a load profile. "
                "Membership is by the phase the round was sent in. The canonical code "
                "is the one the API reported in its own error body, not one this "
                "record inferred from a status."
            ),
            "canonicalCodesObserved": observed_codes,
            "conditionsObserved": observed_conditions,
            "surfaces": [
                {
                    "probeId": surface.probe_id,
                    "tier": surface.tier,
                    "method": surface.method,
                    "path": surface.path,
                    "expectation": surface.expectation,
                    "expectedUnreadyStatus": surface.unready_status,
                    "expectedRecoveredStatus": surface.recovered_status,
                    "unready": {
                        "asked": len(_for_probe(probes, surface.probe_id, "unready")),
                        "statuses": _counted(
                            [
                                row["status"]
                                for row in _for_probe(
                                    probes, surface.probe_id, "unready"
                                )
                            ]
                        ),
                        "errorCodes": _counted(
                            [
                                row["errorCode"]
                                for row in _for_probe(
                                    probes, surface.probe_id, "unready"
                                )
                            ]
                        ),
                    },
                    "recovered": {
                        "asked": len(_for_probe(probes, surface.probe_id, "recovered")),
                        "statuses": _counted(
                            [
                                row["status"]
                                for row in _for_probe(
                                    probes, surface.probe_id, "recovered"
                                )
                            ]
                        ),
                        "errorCodes": _counted(
                            [
                                row["errorCode"]
                                for row in _for_probe(
                                    probes, surface.probe_id, "recovered"
                                )
                            ]
                        ),
                    },
                }
                for surface in descriptor.surfaces
            ],
            "probes": probes,
            "roundsWhileUnready": len({row["round"] for row in unready_probes}),
            "roundsAfterRecovery": len({row["round"] for row in recovered_probes}),
        },
        "diagnostics": {
            "note": (
                "What an operator would look at, captured while the release was in the "
                "unready state. The excerpts are bounded and every capture is refused "
                "if it carries a host path, a user directory, or an address that is "
                "not loopback. Whether a capture *explains* the cause is a reviewed "
                "judgement and is not decided here; what is decided is whether it was "
                "captured and whether it is safe to publish."
            ),
            "captures": diagnostics,
        },
        "humanAction": {
            "authorisationRequired": True,
            "valuesFileSuppliedByOperator": True,
            "recoveryInterventionExpected": True,
            "interventions": lifecycle["interventions"],
            "note": (
                "This experiment expects one intervention and registers it in advance. "
                "A model that cannot load is not a state the Deployment controller "
                "reverses -- unlike a deleted pod, which V1-S4-006 measured -- and a "
                "record claiming otherwise would be claiming a self-healing property "
                "this platform does not have. The operating script issues exactly two "
                "mutating commands after the install: the corrected upgrade and the "
                "uninstall, and a test reads the script to establish that."
            ),
        },
        "telemetry": {
            "collectorVersion": telemetry.get("collectorVersion"),
            "range": telemetry.get("range"),
            "series": series_rows,
            "note": (
                "Whether a signal exposed the state is not decided here. Each "
                "expression's registered expectation and its readings while unready "
                "and after the recovery are recorded, and the reading of the pair "
                "belongs to a reviewed document."
            ),
        },
        "checks": checks,
        "usable": all(check["passed"] for check in checks),
        "observations": observations,
        "podsUnready": [pods_unready.get(role) for role in ROLES],
        "inputs": inputs,
        "limitations": list(descriptor.limitations),
    }
    refuse_private(dumps(record), "unready model recovery record")
    return record
