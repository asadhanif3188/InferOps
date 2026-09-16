"""Losing the inference pod under load: what it runs, what it reads, what it records.

`scripts/environment/inference-pod-recovery.sh` owns every contact with the cluster.
It verifies the target, installs the release, starts the committed load profile,
deletes one serving runtime pod by name while that load is mid-flight, samples what
readiness looked like from three places, and removes the release. This module owns
everything that can be decided without a cluster:

- the **descriptor** -- the committed experiment, checked against the load profile it
  pins by digest and against ceilings kept here rather than in it;
- the **environment** -- the fields a record keeps out of the cluster's own JSON, and
  the load facts file derived from the same JSON rather than typed by an operator;
- the **record** -- a pure function of the committed inputs. It slices the raw load
  record set into what callers saw before, during, and after the disruption, places
  the readiness samples and the collector's answers on the same wall clock, and lists
  what it saw.

**The question this answers, and the one it does not.** `V1-S3-003-PR2` established
that the model artifact survives a pod replacement, and recorded as its own limitation
that nothing there measured the replacement window from a caller's side. That is what
this measures. It does not re-prove persistence: the artifact's inode and modification
time are not compared here, and the record says so rather than implying otherwise.

**What it refuses to become.** Every figure is one observation of one pod lost once.
Nothing here is an availability figure, a service-level objective, an error budget, or
a number anything may be compared against, and the descriptor, the raw set, and the
record each carry the boundary that says so (ADR 0013 D3).

Reuse is explicit rather than incidental. `tools.llm_load` parses and summarises the
raw load record set; `tools.performance_scenarios.core` contributes the serialization,
digest, and private-shape helpers every committed record in this repository shares;
`tools.performance_scenarios.live` contributes the loopback-only HTTP asker. Nothing
here re-implements any of them.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from tools.llm_load import core as load
from tools.performance_scenarios.core import (
    ScenarioRefused,
    dumps,
    file_digest,
    read_json,
    text_digest,
)
from tools.performance_scenarios.core import refuse_private as _shared_refuse_private

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR_PATH = (
    REPO_ROOT / "deploy" / "serving" / "experiments" / "inference-pod-recovery.v1.json"
)

EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_EXPERIMENT_ID = "inferops-inference-pod-recovery"
EXPECTED_EVIDENCE_CLASS = "local-real-cpu"
EXPECTED_EVIDENCE_LABEL = "local real Kubernetes"
EXPECTED_CEILING = "C2"
EXPECTED_LANE = "real-runtime"
EXPECTED_LOAD_MODULE = "tools.llm_load"
RECORD_SCHEMA = "inferops.io/v1alpha1"
RECORD_KIND = "inferops-inference-pod-recovery-record"

#: This experiment's disruption, as a literal. A descriptor naming any other mechanism
#: belongs to another experiment, and widening this would let one record describe two.
DISRUPTION_MECHANISM = "delete-serving-runtime-pod-under-load"
DISRUPTION_TARGET = "serving-runtime"
DISRUPTION_SCOPE = "pod"
DISRUPTION_REVERSED_BY = "deployment-controller"

#: The answerability vocabulary the telemetry correlation record already publishes.
#: A tenth word invented here would be a tenth word nothing else in the repository
#: means anything by.
ANSWERABILITY = (
    "answerable-once-collected",
    "not-answerable-nothing-emits",
    "no-source",
)

#: What a series is expected to do across the disruption, registered before the run.
#: A signal that did not expose the event is recorded as such rather than left out.
EXPOSURE = (
    "expected-to-expose",
    "expected-not-to-expose",
    "nothing-emits",
    "no-source",
)

#: What a person may have had to do. `none` is the answer this experiment expects and
#: the only one that supports the claim that the Deployment controller did the work.
INTERVENTIONS = (
    "none",
    "restarted-a-workload",
    "rolled-back-a-release",
    "edited-a-declared-object",
    "recreated-a-prerequisite",
)

#: The two load runs, in the order they are sent. The first is disrupted mid-flight;
#: the second starts once the replacement reports Ready and measures what callers get
#: back. Both are the same committed profile at the same concurrency levels.
RUN_ROLES = ("disrupted", "recovered")

#: The release tiers a record keeps, by the component label the chart gives them.
ROLE_COMPONENTS: dict[str, str] = {
    "api": "platform-api",
    "runtime": "serving-runtime",
    "collector": "telemetry-collector",
}
ROLES: tuple[str, ...] = tuple(ROLE_COMPONENTS)

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
    "deploy/serving/experiments/inference-pod-recovery.v1.json",
    "deploy/serving/load/llm-load-profile.v1.json",
    "scripts/environment/inference-pod-recovery.sh",
    "scripts/environment/lib.sh",
    "tools/llm_load/core.py",
    "tools/llm_load/__main__.py",
    "tools/inference_pod_recovery/core.py",
    "tools/inference_pod_recovery/live.py",
    "tools/inference_pod_recovery/__main__.py",
    "charts/inferops-llm/Chart.yaml",
    "charts/inferops-llm/values.yaml",
    "charts/inferops-llm/ci/real-values.yaml",
)

# Ceilings kept in code, for the reason tools.llm_load keeps its own: a heavier or
# longer run must not be authorizable by editing the record that is supposed to bound
# it. The disruption offset has a floor as well as a ceiling, because a delete issued
# before the profile's warm-up finishes would disrupt a phase this experiment does not
# measure.
MINIMUM_DISRUPTION_OFFSET_MS = 10_000
MAXIMUM_DISRUPTION_OFFSET_MS = 600_000
MINIMUM_POLL_INTERVAL_MS = 1_000
MAXIMUM_POLL_INTERVAL_MS = 10_000
MINIMUM_READINESS_SAMPLES = 3
MINIMUM_IDLE_SECONDS = 30
MAXIMUM_IDLE_SECONDS = 600
MAXIMUM_SETTLE_SECONDS = 600
MAXIMUM_SERIES = 20
MAXIMUM_TOTAL_SECONDS = 7200

#: How far apart two readiness samples may be before the window between them is a gap
#: this record cannot describe. Four polls: one slow kubectl answer is not a gap.
READINESS_GAP_MULTIPLE = 4

DNS_LABEL = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
SERIES_ID = re.compile(r"[a-z][a-z0-9-]{1,62}")
DOTTED_PATH = re.compile(r"[A-Za-z][A-Za-z0-9]*(\.[A-Za-z][A-Za-z0-9]*)*")
RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z")


class RecoveryError(RuntimeError):
    """The experiment, its evidence, or its record is not what it must be."""


class RecoveryRefused(RecoveryError):
    """A precondition refused before anything was recorded as a result."""


def refuse_private(text: str, what: str) -> None:
    """Refuse a document carrying a host path, a user directory, or an address.

    The shapes are the ones every committed record in this repository is held to, so
    the check is `tools.performance_scenarios`' rather than a second list that could
    drift from it. Only the exception is this module's, because a caller of this
    package should not have to catch another package's.
    """
    try:
        _shared_refuse_private(text, what)
    except ScenarioRefused as error:
        raise RecoveryRefused(str(error)) from error


# --------------------------------------------------------------------------
# Small readers
# --------------------------------------------------------------------------


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RecoveryError(f"'{field}' must be an object")
    return cast(dict[str, Any], value)


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise RecoveryError(f"'{field}' must be a list")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecoveryError(f"'{field}' must be a non-empty string")
    return value


def _integer(
    value: Any, field: str, *, minimum: int = 0, maximum: int | None = None
) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise RecoveryError(f"'{field}' must be an integer of at least {minimum}")
    if maximum is not None and value > maximum:
        raise RecoveryError(f"'{field}' must be at most {maximum}")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise RecoveryError(f"'{field}' must be true or false")
    return value


def _true(value: Any, field: str) -> None:
    if value is not True:
        raise RecoveryError(f"'{field}' must be true")


def _false(value: Any, field: str) -> None:
    if value is not False:
        raise RecoveryError(f"'{field}' must be false")


def _read_json_text(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise RecoveryError(f"the {what} is not valid JSON") from error


def _member(value: Any, field: str, allowed: Sequence[str]) -> str:
    text = _string(value, field)
    if text not in allowed:
        raise RecoveryError(f"'{field}' must be one of {', '.join(allowed)}")
    return text


# --------------------------------------------------------------------------
# The descriptor
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Scenario:
    """One phase of the committed load profile, as this experiment names it."""

    scenario_id: str
    role: str
    load_phase: str
    concurrency: int


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
    profile: load.Profile
    profile_sha256: str
    scenarios: tuple[Scenario, ...]
    series: tuple[Series, ...]
    disrupted_scenario_id: str
    disruption_offset_ms: int
    poll_interval_ms: int
    minimum_samples: int
    range_step_seconds: int
    scrape_interval_seconds: int
    limitations: tuple[str, ...]

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        return tuple(scenario.scenario_id for scenario in self.scenarios)


def _validate_identity(document: Mapping[str, Any]) -> None:
    if document.get("schemaVersion") != EXPECTED_SCHEMA:
        raise RecoveryError(f"the schema version must be '{EXPECTED_SCHEMA}'")
    if document.get("experimentId") != EXPECTED_EXPERIMENT_ID:
        raise RecoveryError(f"the experiment id must be '{EXPECTED_EXPERIMENT_ID}'")
    if document.get("evidenceClass") != EXPECTED_EVIDENCE_CLASS:
        raise RecoveryError(f"the evidence class must be '{EXPECTED_EVIDENCE_CLASS}'")
    if document.get("evidenceLabel") != EXPECTED_EVIDENCE_LABEL:
        raise RecoveryError(f"the evidence label must be '{EXPECTED_EVIDENCE_LABEL}'")
    if document.get("certificationCeiling") != EXPECTED_CEILING:
        raise RecoveryError(f"the certification ceiling must be '{EXPECTED_CEILING}'")
    if document.get("lane") != EXPECTED_LANE:
        raise RecoveryError(f"the lane must be '{EXPECTED_LANE}'")
    _false(document.get("productionBenchmark"), "productionBenchmark")
    _false(document.get("portableCapacityClaim"), "portableCapacityClaim")
    _false(document.get("availabilityClaim"), "availabilityClaim")
    boundary = _string(document.get("boundary"), "boundary")
    for word in ("availability", "benchmark", "portable capacity"):
        if word not in boundary:
            raise RecoveryError(f"the boundary sentence does not refuse '{word}'")
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


def _validate_scenarios(document: Mapping[str, Any]) -> tuple[Scenario, ...]:
    entries = _list(document.get("scenarios"), "scenarios")
    if not entries:
        raise RecoveryError("the experiment declares no scenarios")
    scenarios = []
    for entry in entries:
        item = _object(entry, "scenarios[]")
        scenario = Scenario(
            scenario_id=_string(item.get("scenarioId"), "scenarioId"),
            role=_string(item.get("role"), "role"),
            load_phase=_member(
                item.get("loadPhase"), "loadPhase", ("warmup", "measured")
            ),
            concurrency=_integer(item.get("concurrency"), "concurrency", minimum=1),
        )
        scenarios.append(scenario)
    identifiers = [scenario.scenario_id for scenario in scenarios]
    if len(set(identifiers)) != len(identifiers):
        raise RecoveryError("two scenarios carry the same identifier")
    return tuple(scenarios)


def _validate_scenarios_against_profile(
    scenarios: Sequence[Scenario], profile: load.Profile
) -> None:
    """Every scenario is a phase the committed load profile actually sends."""
    expected = [("warmup", "warmup", profile.warmup_concurrency)] + [
        ("measured", level.level_id, level.concurrency) for level in profile.levels
    ]
    observed = [
        (scenario.load_phase, scenario.scenario_id, scenario.concurrency)
        for scenario in scenarios
    ]
    if observed != expected:
        raise RecoveryError(
            "the scenarios are not the phases the committed load profile sends, in "
            "the order it sends them"
        )


def _validate_disruption(
    document: Mapping[str, Any], scenarios: Sequence[Scenario]
) -> tuple[str, int]:
    disruption = _object(document.get("disruption"), "disruption")
    _string(disruption.get("description"), "disruption.description")
    if disruption.get("mechanism") != DISRUPTION_MECHANISM:
        raise RecoveryError(f"the mechanism must be '{DISRUPTION_MECHANISM}'")
    if disruption.get("target") != DISRUPTION_TARGET:
        raise RecoveryError(f"the disruption target must be '{DISRUPTION_TARGET}'")
    if disruption.get("scope") != DISRUPTION_SCOPE:
        raise RecoveryError(f"the disruption scope must be '{DISRUPTION_SCOPE}'")
    if disruption.get("reversedBy") != DISRUPTION_REVERSED_BY:
        raise RecoveryError(
            f"the disruption must be reversed by {DISRUPTION_REVERSED_BY}"
        )
    _false(disruption.get("deletesDeclaredObject"), "deletesDeclaredObject")
    for field in (
        "changesNoDeployment",
        "changesNoPersistentVolumeClaim",
        "changesNoReleaseRevision",
        "changesNoClusterScopedObject",
        "touchesNoOtherNamespace",
    ):
        _true(disruption.get(field), f"disruption.{field}")
    # A grace period this experiment set would be a second thing its figures depend
    # on, and one a reader would have to be told about beside every one of them.
    if disruption.get("gracePeriodSeconds") is not None:
        raise RecoveryError(
            "this experiment does not set a termination grace period; the workload's "
            "own is what a caller would meet"
        )
    during = _string(disruption.get("duringScenarioId"), "duringScenarioId")
    measured = {
        scenario.scenario_id
        for scenario in scenarios
        if scenario.load_phase == "measured"
    }
    if during not in measured:
        raise RecoveryError(
            "the disruption names a scenario that is not one of the measured phases"
        )
    offset = _integer(
        disruption.get("issueAfterLoadStartMs"),
        "issueAfterLoadStartMs",
        minimum=MINIMUM_DISRUPTION_OFFSET_MS,
        maximum=MAXIMUM_DISRUPTION_OFFSET_MS,
    )
    return during, offset


def _validate_human_action(document: Mapping[str, Any]) -> None:
    human = _object(document.get("humanAction"), "humanAction")
    _string(human.get("description"), "humanAction.description")
    _true(human.get("authorisationRequired"), "humanAction.authorisationRequired")
    _true(
        human.get("valuesFileSuppliedByOperator"),
        "humanAction.valuesFileSuppliedByOperator",
    )
    _false(
        human.get("recoveryInterventionExpected"),
        "humanAction.recoveryInterventionExpected",
    )
    vocabulary = [
        _string(entry, "interventionVocabulary[]")
        for entry in _list(
            human.get("interventionVocabulary"), "interventionVocabulary"
        )
    ]
    if tuple(vocabulary) != INTERVENTIONS:
        raise RecoveryError(
            "the intervention vocabulary is not the one this module records against"
        )


def _validate_observation(document: Mapping[str, Any]) -> tuple[int, int]:
    observation = _object(document.get("observation"), "observation")
    _string(observation.get("description"), "observation.description")
    _true(observation.get("requireReadinessRecord"), "requireReadinessRecord")
    _true(observation.get("requireEndpointSamples"), "requireEndpointSamples")
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
    return poll, minimum


def _validate_recovery(document: Mapping[str, Any]) -> None:
    recovery = _object(document.get("recovery"), "recovery")
    _string(recovery.get("description"), "recovery.description")
    _string(recovery.get("twoRunsBecause"), "recovery.twoRunsBecause")
    for field, expected in (
        ("replacementScheduledFrom", "deletion"),
        ("replacementReadyFrom", "deletion"),
        ("firstServedCompletionFrom", "deletion"),
        ("modelReloadFrom", "replacement-container-started"),
        ("callerVisibleOutageFrom", "first-unsuccessful-request-after-deletion"),
        ("recoveredRunStartsWhen", "replacement-reports-ready"),
    ):
        if recovery.get(field) != expected:
            raise RecoveryError(f"'recovery.{field}' must be '{expected}'")
    _true(
        recovery.get("requireServedCompletionAfterRecovery"),
        "requireServedCompletionAfterRecovery",
    )
    _true(
        recovery.get("requireUnsuccessfulRequestsDuringOutage"),
        "requireUnsuccessfulRequestsDuringOutage",
    )


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
        raise RecoveryError(
            f"the experiment must ask between 1 and {MAXIMUM_SERIES} series"
        )
    series = []
    for entry in entries:
        item = _object(entry, "series[]")
        series_id = _string(item.get("seriesId"), "seriesId")
        if SERIES_ID.fullmatch(series_id) is None:
            raise RecoveryError(f"'{series_id}' is not a series identifier")
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
            raise RecoveryError(
                f"series '{series_id}' pairs an answerability and an exposure that "
                "cannot both be true"
            )
        if (answerability == "no-source") != (exposure == "no-source"):
            raise RecoveryError(
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
        raise RecoveryError("two series carry the same identifier")
    if not any(entry.exposure == "expected-to-expose" for entry in series):
        raise RecoveryError(
            "no series is registered as expected to expose the disruption, so the "
            "record could not say whether anything did"
        )
    if not any(entry.exposure == "expected-not-to-expose" for entry in series):
        raise RecoveryError(
            "no series is registered as expected not to expose the disruption, and a "
            "record naming only the signals that worked is not a classification"
        )
    return tuple(series), step, scrape


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
            raise RecoveryError(f"'release.{field}' is not a Kubernetes name")
    _string(release.get("instanceSelector"), "release.instanceSelector")
    for field in ("apiServicePort", "collectorServicePort"):
        _integer(release.get(field), f"release.{field}", minimum=1, maximum=65535)
    for field in ("apiReplicas", "runtimeReplicas"):
        replicas = _integer(release.get(field), f"release.{field}", minimum=1)
        if replicas != 1:
            raise RecoveryError(
                f"'release.{field}' is {replicas}; this experiment is defined for one "
                "replica of each tier, because a second would change what a caller saw"
            )
    if release.get("namespace") != "inferops-release":
        raise RecoveryError(
            "the release namespace is not the one these scripts operate"
        )


def _validate_readiness(document: Mapping[str, Any]) -> None:
    readiness = _object(document.get("readiness"), "readiness")
    budgets = {}
    for field in (
        "runtimeRolloutBudgetMs",
        "apiRolloutBudgetMs",
        "collectorRolloutBudgetMs",
        "forwardBudgetMs",
        "replacementBudgetMs",
        "recoveryBudgetMs",
        "uninstallBudgetMs",
    ):
        budgets[field] = _integer(
            readiness.get(field), f"readiness.{field}", minimum=1000
        )
    if budgets["replacementBudgetMs"] < budgets["runtimeRolloutBudgetMs"]:
        raise RecoveryError(
            "the replacement budget is smaller than the rollout budget the same "
            "workload was given to start the first time"
        )
    if budgets["recoveryBudgetMs"] <= budgets["replacementBudgetMs"]:
        raise RecoveryError(
            "a served completion cannot come back before the pod that serves it is "
            "ready, so the recovery budget must exceed the replacement budget"
        )


def _validate_evidence(document: Mapping[str, Any]) -> None:
    evidence = _object(document.get("evidence"), "evidence")
    directory = _string(evidence.get("directory"), "evidence.directory")
    # A descriptor that could name any directory could name one outside the ignored
    # tree, and a record written there would carry this project's evidence label into
    # version control by accident.
    if not directory.startswith(".cache/inferops/experiments/"):
        raise RecoveryError(
            "run evidence is written under .cache/inferops/experiments/ and nowhere else"
        )
    for field in (
        "environmentFile",
        "lifecycleFile",
        "readinessFile",
        "telemetryFile",
        "disruptedRawFile",
        "recoveredRawFile",
        "recordDirectory",
    ):
        value = _string(evidence.get(field), f"evidence.{field}")
        if Path(value).name != value:
            raise RecoveryError(f"'evidence.{field}' carries a directory component")
    _false(evidence.get("retainGeneratedText"), "evidence.retainGeneratedText")


def _validate_schedule(document: Mapping[str, Any]) -> None:
    schedule = _object(document.get("schedule"), "schedule")
    # Two runs, and exactly two: the first is disrupted and the second measures what
    # callers get back. A third would be a repetition study, which this is not.
    if schedule.get("repetitions") != len(RUN_ROLES):
        raise RecoveryError(f"this experiment sends {len(RUN_ROLES)} load runs")
    roles = [
        _string(entry, "runRoles[]")
        for entry in _list(schedule.get("runRoles"), "runRoles")
    ]
    if tuple(roles) != RUN_ROLES:
        raise RecoveryError(
            "the run roles are not the ones this module records against"
        )
    _integer(
        schedule.get("idleBaselineSeconds"),
        "idleBaselineSeconds",
        minimum=MINIMUM_IDLE_SECONDS,
        maximum=MAXIMUM_IDLE_SECONDS,
    )
    for field in ("settleBetweenRunsSeconds", "settleAfterRunSeconds"):
        _integer(schedule.get(field), field, minimum=0, maximum=MAXIMUM_SETTLE_SECONDS)


def _validate_cluster(document: Mapping[str, Any]) -> None:
    providers = _list(
        _object(document.get("cluster"), "cluster").get("providers"), "providers"
    )
    if not providers:
        raise RecoveryError("the experiment describes no provider")
    for entry in providers:
        provider = _object(entry, "providers[]")
        for field in ("providerId", "name", "context"):
            _string(provider.get(field), f"providers[].{field}")
    identifiers = [_object(entry, "providers[]")["providerId"] for entry in providers]
    if len(set(identifiers)) != len(identifiers):
        raise RecoveryError("two providers carry the same identifier")


def _validate_forwards(document: Mapping[str, Any]) -> None:
    forwards = _object(document.get("forwards"), "forwards")
    # The API behind the forward carries no authentication, so binding it anywhere
    # but loopback would publish an unauthenticated LLM endpoint on every interface.
    if forwards.get("host") != "127.0.0.1":
        raise RecoveryError("these forwards bind 127.0.0.1 only")
    ports = [
        _integer(forwards.get(field), f"forwards.{field}", minimum=1024, maximum=65535)
        for field in ("apiPort", "collectorPort")
    ]
    if len(set(ports)) != len(ports):
        raise RecoveryError("the forwards name the same local port twice")


def _validate_cleanup(document: Mapping[str, Any]) -> None:
    cleanup = _object(document.get("cleanup"), "cleanup")
    _true(cleanup.get("uninstallsRelease"), "cleanup.uninstallsRelease")
    for field in (
        "removesPrerequisites",
        "removesCluster",
        "removesModelCacheClaim",
    ):
        _false(cleanup.get(field), f"cleanup.{field}")


def _validate_limitations(document: Mapping[str, Any]) -> tuple[str, ...]:
    limitations = tuple(
        _string(entry, "limitations[]")
        for entry in _list(document.get("limitations"), "limitations")
    )
    if len(limitations) < 5:
        raise RecoveryError("an experiment of this kind states more than four limits")
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

    scenarios = _validate_scenarios(document)
    during, offset = _validate_disruption(document, scenarios)
    poll, minimum_samples = _validate_observation(document)
    series, step, scrape = _validate_telemetry(document)
    limitations = _validate_limitations(document)

    load_block = _object(document.get("load"), "load")
    if load_block.get("module") != EXPECTED_LOAD_MODULE:
        raise RecoveryError(f"the load module must be '{EXPECTED_LOAD_MODULE}'")
    profile_ref = _string(load_block.get("profileRef"), "load.profileRef")
    if profile_ref != str(load.PROFILE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"):
        raise RecoveryError("the load profile reference is not the committed profile")
    profile_path = repo_root / profile_ref
    profile_sha256 = file_digest(profile_path)
    if load_block.get("profileSha256") != profile_sha256:
        raise RecoveryError(
            "the descriptor pins a load profile digest the committed profile does not "
            "have"
        )
    profile = load.load_profile()
    if profile.evidence_class != EXPECTED_EVIDENCE_CLASS:
        raise RecoveryError("the load profile is not the real-evidence profile")
    if profile.production_benchmark or profile.portable_capacity_claim:
        raise RecoveryError("the load profile does not carry its own boundary")
    _validate_scenarios_against_profile(scenarios, profile)

    # The whole profile must fit inside the ceiling, and the delete must be issued
    # while it is still running rather than after it.
    if profile.worst_case_seconds() > MAXIMUM_TOTAL_SECONDS:
        raise RecoveryError(
            "the load profile's worst case exceeds this experiment's ceiling"
        )
    if offset >= profile.worst_case_seconds() * 1000:
        raise RecoveryError(
            "the disruption is scheduled for after the load profile's own worst case, "
            "so there would be no traffic to disrupt"
        )

    return Descriptor(
        document=document,
        sha256=text_digest(text),
        profile=profile,
        profile_sha256=profile_sha256,
        scenarios=scenarios,
        series=series,
        disrupted_scenario_id=during,
        disruption_offset_ms=offset,
        poll_interval_ms=poll,
        minimum_samples=minimum_samples,
        range_step_seconds=step,
        scrape_interval_seconds=scrape,
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
            raise RecoveryError(f"'{path}' is not a dotted descriptor path")
        cursor: Any = descriptor.document
        for member in path.split("."):
            if not isinstance(cursor, Mapping) or member not in cursor:
                raise RecoveryError(f"the descriptor has no '{path}'")
            cursor = cursor[member]
        if isinstance(cursor, bool) or not isinstance(cursor, str | int):
            raise RecoveryError(f"'{path}' is not a value a shell can read")
        values.append(str(cursor))
    return values


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
        f"load profile {document['load']['profileRef']} "
        f"({descriptor.profile_sha256[:12]})",
        f"scenarios    {', '.join(descriptor.scenario_ids)}",
        f"disruption   {disruption['mechanism']} in scenario "
        f"'{descriptor.disrupted_scenario_id}', "
        f"{descriptor.disruption_offset_ms} ms after the load starts",
        f"release      {release['name']} in {release['namespace']}, "
        f"{release['runtimeReplicas']} runtime replica",
        f"readiness    sampled every {descriptor.poll_interval_ms} ms, at least "
        f"{descriptor.minimum_samples} samples",
        "telemetry    "
        + ", ".join(f"{count} {name}" for name, count in exposures.items() if count),
        "claim        bounded observations of one pod lost once; not an availability "
        "figure, an SLO, an error budget, or a benchmark",
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


def _pods(document: Any, *, expect_one_of_each: bool) -> list[dict[str, Any]]:
    """The release's running tier pods, one entry each, ordered by role."""
    pods: list[dict[str, Any]] = []
    for item in _items(document, "pods"):
        role = _role_of(item)
        status = _object(item.get("status"), "pod.status")
        if role is None or status.get("phase") != "Running":
            continue
        statuses = [
            _object(entry, "containerStatuses[]")
            for entry in status.get("containerStatuses") or []
        ]
        metadata = _object(item.get("metadata"), "pod.metadata")
        pods.append(
            {
                "role": role,
                "name": _string(metadata.get("name"), "pod.name"),
                "uid": _string(metadata.get("uid"), "pod.uid"),
                "ready": bool(statuses)
                and all(entry.get("ready") is True for entry in statuses),
                "restartCount": sum(
                    _integer(entry.get("restartCount"), "restartCount")
                    for entry in statuses
                ),
                "imageIds": sorted(
                    _string(entry.get("imageID"), "imageID") for entry in statuses
                ),
            }
        )
    if expect_one_of_each:
        roles = [pod["role"] for pod in pods]
        for role in ROLES:
            if roles.count(role) != 1:
                raise RecoveryRefused(
                    f"the release has {roles.count(role)} running '{role}' pod(s); "
                    "this experiment is defined for exactly one of each"
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
            raise RecoveryRefused(f"the release has no Deployment named '{name}'")
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


def _image_by_container(workloads: Mapping[str, Any], role: str, container: str) -> str:
    for entry in workloads[role]["containers"]:
        if entry["name"] == container:
            return str(entry["image"])
    raise RecoveryRefused(f"the {role} Deployment has no container named '{container}'")


#: The tiers whose image a record binds to the pod that ran it, and the file holding
#: the node container runtime's own description of each template reference.
IMAGE_RECORDS: dict[str, str] = {
    "api": "image-api.json",
    "runtime": "image-runtime.json",
}


def _resolved_image(
    cluster_dir: Path, pods: Sequence[Mapping[str, Any]], role: str, image: str
) -> dict[str, Any]:
    """Bind a tier's template reference to the image its pod actually runs.

    A pod's ``imageID`` is not enough on its own: the node's container runtime reports
    one repository digest for an image and one image can carry several, so the same
    build imported twice under two OCI index digests is one image with two names and
    the pod reports whichever came first (`V1-S4-004-PR1`). What binds the two is the
    node's own answer for the template reference.
    """
    if "@sha256:" not in image:
        raise RecoveryRefused(f"the {role} image is not pinned by digest")
    matching = [pod for pod in pods if pod["role"] == role]
    if len(matching) != 1:
        raise RecoveryRefused(f"the release has other than one running '{role}' pod")
    status = _object(
        _object(_cluster_json(cluster_dir, IMAGE_RECORDS[role]), "image").get("status"),
        "image.status",
    )
    repo_digests = sorted(
        _string(entry, "repoDigests[]")
        for entry in _list(status.get("repoDigests"), "image.status.repoDigests")
    )
    if image not in repo_digests:
        raise RecoveryRefused(
            f"the node resolves the {role} template reference to an image that does "
            "not carry that reference's digest"
        )
    if not set(matching[0]["imageIds"]) & set(repo_digests):
        raise RecoveryRefused(
            f"the {role} pod reports a container image that is not the one its "
            "template reference resolves to"
        )
    return {
        "template": image,
        "podImageIds": list(matching[0]["imageIds"]),
        "configId": _string(status.get("id"), "image.status.id"),
        "repoDigests": repo_digests,
    }


def extract_facts(cluster_dir: Path, descriptor: Descriptor) -> dict[str, Any]:
    """The load facts file, read out of the cluster's own answers rather than typed."""
    target = _object(_cluster_json(cluster_dir, "target.json"), "target")
    version = _object(_cluster_json(cluster_dir, "version.json"), "version")
    releases = _list(_cluster_json(cluster_dir, "helm-release.json"), "helm release")
    if len(releases) != 1:
        raise RecoveryRefused(
            "helm reports other than exactly one release under the expected name"
        )
    release = _object(releases[0], "helm release[]")
    workloads = _workloads(_cluster_json(cluster_dir, "deployments.json"), descriptor)
    pods = _pods(
        _cluster_json(cluster_dir, "pods-before.json"), expect_one_of_each=True
    )
    configuration = _object(
        _object(_cluster_json(cluster_dir, "configmap.json"), "configmap").get("data"),
        "data",
    )
    repository = _object(_cluster_json(cluster_dir, "repository.json"), "repository")
    api_image = _image_by_container(workloads, "api", "api")
    runtime_image = _image_by_container(workloads, "runtime", "runtime")
    _resolved_image(cluster_dir, pods, "api", api_image)
    _resolved_image(cluster_dir, pods, "runtime", runtime_image)
    revision = str(release.get("revision", ""))
    if not revision.isdigit():
        raise RecoveryRefused("helm reports a release revision that is not a number")
    return {
        "provider": _string(target.get("provider"), "target.provider"),
        "kubernetesServerVersion": _string(
            _object(version.get("serverVersion"), "serverVersion").get("gitVersion"),
            "serverVersion.gitVersion",
        ),
        "chart": _string(release.get("chart"), "helm release chart"),
        "releaseRevision": int(revision),
        "apiImage": api_image,
        "runtimeImage": runtime_image,
        "modelRevision": _string(
            configuration.get("INFEROPS_MODEL_REVISION"), "INFEROPS_MODEL_REVISION"
        ),
        "apiReplicas": workloads["api"]["desiredReplicas"],
        "runtimeReplicas": workloads["runtime"]["desiredReplicas"],
        "repositoryRevision": _string(
            repository.get("revision"), "repository.revision"
        ),
    }


def executed_file_digests(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """The LF-normalized digest of every file that decides what a run does."""
    return {relative: file_digest(repo_root / relative) for relative in EXECUTED_FILES}


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
    workloads = _workloads(_cluster_json(cluster_dir, "deployments.json"), descriptor)
    pods_before = _pods(
        _cluster_json(cluster_dir, "pods-before.json"), expect_one_of_each=True
    )
    # After the disruption the runtime pod is a different one by design, so the
    # "exactly one of each" rule is applied before and relaxed after: what the record
    # says about the tiers afterwards is a comparison, not a precondition.
    pods_after = _pods(
        _cluster_json(cluster_dir, "pods-after.json"), expect_one_of_each=False
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
        "workloads": workloads,
        "images": {
            role: _resolved_image(
                cluster_dir,
                pods_before,
                role,
                _image_by_container(workloads, role, role),
            )
            for role in IMAGE_RECORDS
        },
        "podsBefore": pods_before,
        "podsAfter": pods_after,
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
        raise RecoveryError(f"'{field}' is not an RFC 3339 instant in UTC")
    return text


def _pod_identity(document: Mapping[str, Any], what: str) -> dict[str, Any]:
    return {
        "name": _string(document.get("name"), f"{what}.name"),
        "uid": _string(document.get("uid"), f"{what}.uid"),
        "ownerKind": _string(document.get("ownerKind"), f"{what}.ownerKind"),
        "ownerName": _string(document.get("ownerName"), f"{what}.ownerName"),
        "nodeName": _string(document.get("nodeName"), f"{what}.nodeName"),
    }


def parse_lifecycle(document: Any, descriptor: Descriptor) -> dict[str, Any]:
    """The instants the operating script stamped, checked for order and for shape.

    Every instant here is the host's wall clock, read by the same shell that ran the
    load, so the intervals derived from them are differences on one clock. The two
    instants the *cluster* reports are kept as the strings it emitted and never
    subtracted from anything: the node is a container whose clock this record has no
    reason to assume is the host's.
    """
    lifecycle = _object(document, "lifecycle")
    idle = _object(lifecycle.get("idleBaseline"), "idleBaseline")
    idle_start = _integer(
        idle.get("startEpochMs"), "idleBaseline.startEpochMs", minimum=1
    )
    idle_end = _integer(
        idle.get("endEpochMs"), "idleBaseline.endEpochMs", minimum=idle_start
    )
    runs = [_object(entry, "runs[]") for entry in _list(lifecycle.get("runs"), "runs")]
    if len(runs) != len(RUN_ROLES):
        raise RecoveryError(
            f"the lifecycle records {len(runs)} run(s), not {len(RUN_ROLES)}"
        )
    launched = _integer(
        runs[0].get("launchedEpochMs"), "runs[0].launchedEpochMs", minimum=idle_end
    )
    deletion = _object(lifecycle.get("deletion"), "deletion")
    deleted = _integer(
        deletion.get("issuedEpochMs"), "deletion.issuedEpochMs", minimum=launched
    )
    replacement = _object(lifecycle.get("replacement"), "replacement")
    observed = _integer(
        replacement.get("observedEpochMs"),
        "replacement.observedEpochMs",
        minimum=deleted,
    )
    ready = _integer(
        replacement.get("readyEpochMs"), "replacement.readyEpochMs", minimum=observed
    )
    parsed_runs: list[dict[str, Any]] = []
    previous = launched
    for index, (role, entry) in enumerate(zip(RUN_ROLES, runs, strict=True)):
        if entry.get("role") != role:
            raise RecoveryError(f"run {index + 1} is not the '{role}' run")
        # The disrupted run must have been running when the delete was issued, and
        # the recovered run must have started after the replacement was ready: a run
        # that started earlier would be measuring something else.
        floor = previous if index == 0 else max(previous, ready)
        run_launched = _integer(
            entry.get("launchedEpochMs"),
            f"runs[{index}].launchedEpochMs",
            minimum=floor,
        )
        run_exited = _integer(
            entry.get("exitedEpochMs"),
            f"runs[{index}].exitedEpochMs",
            minimum=max(run_launched, deleted if index == 0 else run_launched),
        )
        parsed_runs.append(
            {
                "repetition": index + 1,
                "role": role,
                "rawFile": _string(entry.get("rawFile"), f"runs[{index}].rawFile"),
                "launchedEpochMs": run_launched,
                "exitedEpochMs": run_exited,
                "exitCode": _integer(
                    entry.get("exitCode"),
                    f"runs[{index}].exitCode",
                    minimum=0,
                    maximum=255,
                ),
            }
        )
        previous = run_exited
    exited = parsed_runs[-1]["exitedEpochMs"]
    settled = _integer(
        lifecycle.get("settledEpochMs"), "settledEpochMs", minimum=exited
    )
    matched = _integer(
        deletion.get("podsMatchingSelector"), "deletion.podsMatchingSelector", minimum=0
    )
    interventions = [
        _member(entry, "interventionsAfterDeletion[]", INTERVENTIONS)
        for entry in _list(
            lifecycle.get("interventionsAfterDeletion"), "interventionsAfterDeletion"
        )
    ]
    release = _object(lifecycle.get("release"), "release")
    acquisition = _object(lifecycle.get("acquisition"), "acquisition")
    claims = _object(lifecycle.get("claims"), "claims")
    requested = _integer(
        deletion.get("requestedAfterLoadStartMs"),
        "deletion.requestedAfterLoadStartMs",
        minimum=0,
    )
    if requested != descriptor.disruption_offset_ms:
        raise RecoveryRefused(
            "the operating script issued the delete at an offset the descriptor did "
            "not register"
        )
    parsed: dict[str, Any] = {
        "idleBaseline": {"startEpochMs": idle_start, "endEpochMs": idle_end},
        "runs": parsed_runs,
        "settledEpochMs": settled,
        "deletion": {
            **_pod_identity(deletion, "deletion"),
            "issuedEpochMs": deleted,
            "issuedAfterLoadStartMs": deleted - launched,
            "requestedAfterLoadStartMs": requested,
            "podsMatchingSelector": matched,
        },
        "replacement": {
            **_pod_identity(replacement, "replacement"),
            "observedEpochMs": observed,
            "readyEpochMs": ready,
            "containerStartedAt": _rfc3339(
                replacement.get("containerStartedAt"), "replacement.containerStartedAt"
            ),
            "readyConditionAt": _rfc3339(
                replacement.get("readyConditionAt"), "replacement.readyConditionAt"
            ),
            "initContainerName": _string(
                replacement.get("initContainerName"), "replacement.initContainerName"
            ),
            "initExitCode": _integer(
                replacement.get("initExitCode"), "replacement.initExitCode", maximum=255
            ),
            "restartCount": _integer(
                replacement.get("restartCount"), "replacement.restartCount"
            ),
        },
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
        "interventionsAfterDeletion": interventions,
    }
    return parsed


def parse_readiness(document: Any, descriptor: Descriptor) -> list[dict[str, Any]]:
    """The readiness samples, checked for order, shape, and count."""
    samples = [
        _object(entry, "samples[]")
        for entry in _list(_object(document, "readiness").get("samples"), "samples")
    ]
    if len(samples) < descriptor.minimum_samples:
        raise RecoveryRefused(
            f"the run kept {len(samples)} readiness sample(s) and the descriptor asks "
            f"for at least {descriptor.minimum_samples}"
        )
    parsed: list[dict[str, Any]] = []
    previous = 0
    for sample in samples:
        at = _integer(sample.get("atEpochMs"), "sample.atEpochMs", minimum=previous)
        previous = at
        names = [
            _string(name, "sample.runtimePodNames[]")
            for name in _list(sample.get("runtimePodNames"), "sample.runtimePodNames")
        ]
        parsed.append(
            {
                "atEpochMs": at,
                "readTookMs": _integer(sample.get("readTookMs"), "sample.readTookMs"),
                "runtimePodNames": names,
                "runtimePodsPresent": len(names),
                "runtimePodsReady": _integer(
                    sample.get("runtimePodsReady"), "sample.runtimePodsReady"
                ),
                "runtimeEndpointsReady": _integer(
                    sample.get("runtimeEndpointsReady"), "sample.runtimeEndpointsReady"
                ),
            }
        )
    return parsed


# --------------------------------------------------------------------------
# Placing the raw load records on the same wall clock
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Placed:
    """One dispatched request, with both of its ends on the host's wall clock."""

    record: load.RequestRecord
    dispatched_at_ms: int
    completed_at_ms: int


def place_requests(raw: load.RawSet) -> list[Placed]:
    """Every request in a raw set, placed on the clock the operating script stamped.

    ``dispatchOffsetMs`` is relative to its own phase, not to the run, so a request's
    absolute dispatch is the run's origin plus its phase's offset plus its own. The
    origin is the one absolute instant the load generator writes, and it comes from
    the same host clock the operating script reads.
    """
    origin = raw.header.get("startedAtEpochMs")
    if not isinstance(origin, int) or isinstance(origin, bool):
        raise RecoveryRefused(
            "the raw load record set carries no startedAtEpochMs, so its requests "
            "cannot be placed against the disruption"
        )
    starts: dict[str, int] = {}
    for phase in raw.phases:
        if phase.level_id in starts:
            raise RecoveryRefused("the raw set sends one level twice")
        starts[phase.level_id] = origin + phase.started_offset_ms
    placed = []
    for record in raw.records:
        if record.level_id not in starts:
            raise RecoveryRefused(
                "a raw request names a level the raw set has no phase for"
            )
        dispatched = starts[record.level_id] + record.dispatch_offset_ms
        placed.append(
            Placed(
                record=record,
                dispatched_at_ms=dispatched,
                completed_at_ms=dispatched + record.latency_ms,
            )
        )
    return placed


def _latency(entries: Sequence[Placed], percentiles: Sequence[int]) -> dict[str, Any]:
    """The latency of the successes in a window, or nulls where there are none."""
    latencies = [
        entry.record.latency_ms
        for entry in entries
        if entry.record.outcome == "success"
    ]
    if not latencies:
        return {
            "observations": 0,
            "minMs": None,
            "maxMs": None,
            **{f"p{percentile}Ms": None for percentile in percentiles},
        }
    return {
        "observations": len(latencies),
        "minMs": min(latencies),
        "maxMs": max(latencies),
        **{
            f"p{percentile}Ms": load.percentile_ms(latencies, percentile)
            for percentile in percentiles
        },
    }


def _window(
    name: str,
    entries: Sequence[Placed],
    percentiles: Sequence[int],
    *,
    start_ms: int | None,
    end_ms: int | None,
) -> dict[str, Any]:
    """One of before, during, and after: what was dispatched into it and what came back."""
    outcomes = {outcome: 0 for outcome in load.OUTCOMES}
    statuses: dict[str, int] = {}
    error_codes: dict[str, int] = {}
    by_scenario: dict[str, int] = {}
    for entry in entries:
        outcomes[entry.record.outcome] += 1
        statuses[str(entry.record.status)] = (
            statuses.get(str(entry.record.status), 0) + 1
        )
        if entry.record.error_code is not None:
            error_codes[entry.record.error_code] = (
                error_codes.get(entry.record.error_code, 0) + 1
            )
        by_scenario[entry.record.level_id] = (
            by_scenario.get(entry.record.level_id, 0) + 1
        )
    return {
        "window": name,
        "startEpochMs": start_ms,
        "endEpochMs": end_ms,
        "dispatched": len(entries),
        "successful": outcomes["success"],
        "unsuccessful": len(entries) - outcomes["success"],
        "outcomes": outcomes,
        "httpStatuses": dict(sorted(statuses.items())),
        "errorCodes": dict(sorted(error_codes.items())),
        "dispatchedByScenario": dict(sorted(by_scenario.items())),
        "latencyOfSuccesses": _latency(entries, percentiles),
    }


# --------------------------------------------------------------------------
# What the collector answered
# --------------------------------------------------------------------------


def _label_key(labels: Mapping[str, Any]) -> str:
    return ",".join(f"{key}={labels[key]}" for key in sorted(labels))


def _series_readings(element: Mapping[str, Any], at_ms: int | None) -> str | None:
    """The last value at or before an instant, as the string Prometheus returned."""
    if at_ms is None:
        return None
    latest: str | None = None
    for point in _list(element.get("values"), "series.values"):
        pair = _list(point, "series.values[]")
        if len(pair) != 2:
            raise RecoveryError("a range sample is not a pair")
        if float(pair[0]) * 1000 <= at_ms:
            latest = str(pair[1])
    return latest


def _telemetry_series(
    descriptor: Descriptor,
    telemetry: Mapping[str, Any],
    *,
    deleted_ms: int,
    settled_ms: int,
) -> list[dict[str, Any]]:
    """Each registered expression, what it answered, and what it was registered to do.

    Nothing here decides whether a signal exposed the disruption. The readings either
    side are recorded and the registered expectation is recorded beside them; saying
    what the pair means is an analysis, and ADR 0013 D4 keeps that in a reviewed
    document rather than in a tool.
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
            raise RecoveryRefused(
                f"the collector was not asked for '{registered.series_id}'"
            )
        if entry.get("expr") != registered.expr:
            raise RecoveryRefused(
                f"'{registered.series_id}' was asked with an expression the descriptor "
                "does not register"
            )
        status = _string(entry.get("status"), "telemetry.series[].status")
        elements = [
            _object(element, "telemetry.series[].result[]")
            for element in _list(entry.get("result"), "telemetry.series[].result")
        ]
        before: dict[str, str | None] = {}
        after: dict[str, str | None] = {}
        for element in elements:
            key = _label_key(_object(element.get("labels"), "series.labels"))
            before[key] = _series_readings(element, deleted_ms)
            after[key] = _series_readings(element, settled_ms)
        present_before = sorted(
            key for key, value in before.items() if value is not None
        )
        present_after = sorted(key for key, value in after.items() if value is not None)
        shared = sorted(set(present_before) & set(present_after))
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
                "labelSetsBeforeDeletion": present_before,
                "labelSetsAfterTheRun": present_after,
                "labelSetsThatAppeared": sorted(
                    set(present_after) - set(present_before)
                ),
                "labelSetsThatDisappeared": sorted(
                    set(present_before) - set(present_after)
                ),
                "sharedLabelSetsWithChangedValues": [
                    key for key in shared if before[key] != after[key]
                ],
                "readingBeforeDeletion": dict(sorted(before.items())),
                "readingAfterTheRun": dict(sorted(after.items())),
            }
        )
    return rows


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"checkId": name, "passed": passed, "detail": detail}


def _scenario_at(raw: load.RawSet, at_ms: int) -> str | None:
    """Which phase of the load profile an instant fell inside, or None if between two."""
    origin = raw.header["startedAtEpochMs"]
    for phase in raw.phases:
        start = int(origin) + phase.started_offset_ms
        if start <= at_ms < start + phase.window_ms:
            return phase.level_id
    return None


def _served(entries: Sequence[Placed]) -> list[Placed]:
    return [entry for entry in entries if entry.record.outcome == "success"]


def _unserved(entries: Sequence[Placed]) -> list[Placed]:
    return [entry for entry in entries if entry.record.outcome != "success"]


def _first_dispatched(entries: Sequence[Placed]) -> Placed | None:
    return min(entries, key=lambda entry: entry.dispatched_at_ms, default=None)


def build_record(
    descriptor: Descriptor,
    *,
    environment_text: str,
    lifecycle_text: str,
    readiness_text: str,
    telemetry_text: str,
    disrupted_raw_text: str,
    recovered_raw_text: str,
) -> dict[str, Any]:
    """The record, as a pure function of the six committed inputs.

    Every input is refused before it is read if it carries a host path, a user
    directory, or an address that is not loopback: a record is published and the run
    that produced it was not.

    **Where the outage begins and ends, and why it is not the deletion.** The first
    run of this experiment found the pod's own drain answering a request dispatched
    166 ms *after* the delete was issued, in 4 984 ms, served. An earlier version of
    this module stamped the recovery from that completion, which made the published
    "deletion to a served completion" figure describe the pod that was going away and
    produced two negative intervals. The outage a caller experiences begins at the
    first request after the delete that did **not** come back served, and ends at the
    first one dispatched from then on that did -- which is what the descriptor's
    ``callerVisibleOutageFrom`` registered before any of this ran, and what this now
    implements. Requests the draining pod still served are kept in their own window
    rather than folded into either side.

    **Why there are two load runs.** A second run of the same profile, started once
    the replacement reports Ready, is what makes a like-for-like comparison at the
    same concurrency levels possible. The descriptor registers a reason for that which
    the first execution did not bear out; see the record it is published beside.
    """
    for text, what in (
        (environment_text, "environment"),
        (lifecycle_text, "lifecycle record"),
        (readiness_text, "readiness record"),
        (telemetry_text, "telemetry record"),
        (disrupted_raw_text, "disrupted raw load record set"),
        (recovered_raw_text, "recovered raw load record set"),
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
    telemetry = _object(
        _read_json_text(telemetry_text, "telemetry record"), "telemetry record"
    )
    raws = {
        "disrupted": load.parse_raw(disrupted_raw_text),
        "recovered": load.parse_raw(recovered_raw_text),
    }
    for role, raw in raws.items():
        header = raw.header
        if header.get("evidenceClass") != EXPECTED_EVIDENCE_CLASS:
            raise RecoveryRefused(
                f"the {role} raw load record set is not real-evidence output"
            )
        if header.get("productionBenchmark") is not False or (
            header.get("portableCapacityClaim") is not False
        ):
            raise RecoveryRefused(
                f"the {role} raw load record set does not carry its own boundary"
            )

    percentiles = list(descriptor.profile.reported_percentiles)
    deleted_ms = int(lifecycle["deletion"]["issuedEpochMs"])
    ready_ms = int(lifecycle["replacement"]["readyEpochMs"])
    observed_ms = int(lifecycle["replacement"]["observedEpochMs"])
    settled_ms = int(lifecycle["settledEpochMs"])

    disrupted = place_requests(raws["disrupted"])
    recovered = place_requests(raws["recovered"])

    before = [entry for entry in disrupted if entry.dispatched_at_ms < deleted_ms]
    after_delete = [
        entry for entry in disrupted if entry.dispatched_at_ms >= deleted_ms
    ]

    # The outage a caller experiences: from the first request after the delete that
    # did not come back served, to the first one dispatched from then on that did.
    lost = _first_dispatched(_unserved(after_delete))
    restored: Placed | None = None
    restored_in = "nowhere"
    if lost is not None:
        candidates = [
            entry
            for entry in _served(after_delete)
            if entry.dispatched_at_ms >= lost.dispatched_at_ms
        ]
        restored = min(
            candidates, key=lambda entry: entry.completed_at_ms, default=None
        )
        if restored is not None:
            restored_in = "disrupted-run"
        else:
            restored = min(
                _served(recovered),
                key=lambda entry: entry.completed_at_ms,
                default=None,
            )
            if restored is not None:
                restored_in = "recovered-run"

    # What the pod that was going away still served. Kept separate from both sides:
    # folding it into the outage would understate it, and into the before window would
    # claim the replacement served it.
    draining = [
        entry
        for entry in after_delete
        if lost is None or entry.dispatched_at_ms < lost.dispatched_at_ms
    ]
    during = [
        entry
        for entry in after_delete
        if lost is not None
        and entry.dispatched_at_ms >= lost.dispatched_at_ms
        and (restored is None or entry.dispatched_at_ms <= restored.dispatched_at_ms)
    ]
    after_in_disrupted = [
        entry
        for entry in after_delete
        if restored is not None
        and restored_in == "disrupted-run"
        and entry.dispatched_at_ms > restored.dispatched_at_ms
    ]

    disrupted_scenario = descriptor.disrupted_scenario_id
    level_before = [
        entry for entry in before if entry.record.level_id == disrupted_scenario
    ]
    level_after = [
        entry
        for entry in recovered + after_in_disrupted
        if entry.record.level_id == disrupted_scenario
    ]
    comparable = bool(_served(level_before)) and bool(_served(level_after))

    landed_in = _scenario_at(raws["disrupted"], deleted_ms)
    series_rows = _telemetry_series(
        descriptor, telemetry, deleted_ms=deleted_ms, settled_ms=settled_ms
    )

    pods_before = _list(environment.get("podsBefore"), "podsBefore")
    pods_after = _list(environment.get("podsAfter"), "podsAfter")
    by_role_after = {
        str(_object(pod, "podsAfter[]")["role"]): _object(pod, "podsAfter[]")
        for pod in pods_after
    }
    by_role_before = {
        str(_object(pod, "podsBefore[]")["role"]): _object(pod, "podsBefore[]")
        for pod in pods_before
    }
    untouched_unchanged = all(
        role in by_role_after
        and by_role_after[role]["name"] == by_role_before[role]["name"]
        and by_role_after[role]["restartCount"] == 0
        for role in ("api", "collector")
    )
    every_tier_ready_after = all(
        role in by_role_after and by_role_after[role]["ready"] is True for role in ROLES
    )

    endpoints = [int(sample["runtimeEndpointsReady"]) for sample in readiness]
    zero_index = next(
        (index for index, value in enumerate(endpoints) if value == 0), None
    )
    recovered_endpoints = zero_index is not None and any(
        value >= 1 for value in endpoints[zero_index + 1 :]
    )
    gap_ms = max(
        (
            int(readiness[index + 1]["atEpochMs"]) - int(readiness[index]["atEpochMs"])
            for index in range(len(readiness) - 1)
            if int(readiness[index + 1]["atEpochMs"]) <= ready_ms
        ),
        default=0,
    )
    gap_ceiling = descriptor.poll_interval_ms * READINESS_GAP_MULTIPLE

    budgets = _object(descriptor.document.get("readiness"), "readiness")
    replacement_ms = ready_ms - deleted_ms
    lost_at_ms = None if lost is None else lost.completed_at_ms
    restored_at_ms = None if restored is None else restored.completed_at_ms
    outage_ms = (
        None
        if lost_at_ms is None or restored_at_ms is None
        else restored_at_ms - lost_at_ms
    )
    restored_from_deletion_ms = (
        None if restored_at_ms is None else restored_at_ms - deleted_ms
    )
    drained_served = _served(draining)
    last_drained_ms = (
        max(entry.completed_at_ms for entry in drained_served) - deleted_ms
        if drained_served
        else None
    )

    timings: dict[str, Any] = {
        "deletionToReplacementObservedMs": observed_ms - deleted_ms,
        "deletionToReplacementReadyMs": replacement_ms,
        "modelReloadObservedToReadyMs": ready_ms - observed_ms,
        "deletionToFirstUnservedCompletionMs": (
            None if lost_at_ms is None else lost_at_ms - deleted_ms
        ),
        "callerVisibleOutageMs": outage_ms,
        "deletionToServiceRestoredMs": restored_from_deletion_ms,
        "lastCompletionServedWhileDrainingMs": last_drained_ms,
        "firstUnservedCompletionEpochMs": lost_at_ms,
        "serviceRestoredEpochMs": restored_at_ms,
        "serviceRestoredObservedIn": restored_in,
        # Deliberately allowed to be negative, and the only figure here that is. A
        # negative value means a request was served before this workflow's own poll
        # saw the replacement report Ready, which bounds the polling error rather
        # than describing the platform.
        "serviceRestoredRelativeToObservedReadyMs": (
            None if restored_at_ms is None else restored_at_ms - ready_ms
        ),
        "note": (
            "One pod, deleted once, on one host, at one moment, under one load "
            "profile. Not an availability figure, a service-level objective, an "
            "error budget, a recovery benchmark, or a number anything may be "
            "compared against. The outage is measured from the first request after "
            "the delete that did not come back served to the first one dispatched "
            "from then on that did; it does not begin at the delete, because the pod "
            "that was going away went on serving for a while."
        ),
    }

    #: Every interval a reader would take as a duration. A negative one is a figure
    #: stamped from the wrong end, which is the defect the first execution of this
    #: experiment found in this module, so it is refused rather than published.
    non_negative = (
        "deletionToReplacementObservedMs",
        "deletionToReplacementReadyMs",
        "modelReloadObservedToReadyMs",
        "deletionToFirstUnservedCompletionMs",
        "callerVisibleOutageMs",
        "deletionToServiceRestoredMs",
        "lastCompletionServedWhileDrainingMs",
    )
    negative = {
        name: timings[name]
        for name in non_negative
        if isinstance(timings[name], int) and timings[name] < 0
    }

    absences = [
        row for row in series_rows if row["exposure"] in ("nothing-emits", "no-source")
    ]
    registered_present = [
        row
        for row in series_rows
        if row["exposure"] in ("expected-to-expose", "expected-not-to-expose")
    ]
    runs_completed = [
        run
        for run in lifecycle["runs"]
        if run["exitCode"] == 0
        and raws[str(run["role"])].end.get("state") == "completed"
    ]

    checks = [
        _check(
            "deleted-exactly-one-pod",
            lifecycle["deletion"]["podsMatchingSelector"] == 1,
            f"the selector matched {lifecycle['deletion']['podsMatchingSelector']} "
            "running serving-runtime pod(s) when the delete was issued",
        ),
        _check(
            "replacement-is-a-different-pod",
            lifecycle["replacement"]["name"] != lifecycle["deletion"]["name"]
            and lifecycle["replacement"]["uid"] != lifecycle["deletion"]["uid"],
            "the pod after the deletion carries a different name and a different uid",
        ),
        _check(
            "replacement-kept-the-same-owner",
            lifecycle["replacement"]["ownerKind"] == lifecycle["deletion"]["ownerKind"]
            and lifecycle["replacement"]["ownerName"]
            == lifecycle["deletion"]["ownerName"],
            f"owned by {lifecycle['replacement']['ownerKind']} "
            f"'{lifecycle['replacement']['ownerName']}' either side",
        ),
        _check(
            "no-release-revision-change",
            lifecycle["release"]["revisionBefore"]
            == lifecycle["release"]["revisionAfter"],
            f"revision {lifecycle['release']['revisionBefore']} either side; deleting "
            "a pod is not a release change",
        ),
        _check(
            "no-new-acquisition-job",
            lifecycle["acquisition"]["jobCountBefore"]
            == lifecycle["acquisition"]["jobCountAfter"],
            f"{lifecycle['acquisition']['jobCountBefore']} acquisition Job(s) either "
            "side; the hook runs on install and upgrade and a deletion is neither",
        ),
        _check(
            "claim-count-unchanged",
            lifecycle["claims"]["countBefore"] == lifecycle["claims"]["countAfter"],
            f"{lifecycle['claims']['countBefore']} claim(s) either side",
        ),
        _check(
            "disruption-landed-in-the-intended-scenario",
            landed_in == disrupted_scenario,
            f"the delete was issued inside phase '{landed_in}' and the descriptor "
            f"registered '{disrupted_scenario}'",
        ),
        _check(
            "traffic-served-before-the-deletion",
            bool(_served(before)),
            f"{len(_served(before))} of {len(before)} requests dispatched before the "
            "delete came back served",
        ),
        _check(
            "a-request-after-the-deletion-was-not-served",
            lost is not None,
            f"{len(_unserved(after_delete))} request(s) dispatched at or after the "
            "delete did not come back served",
        ),
        _check(
            "the-service-was-restored-to-a-caller",
            restored is not None,
            f"the first request served after the outage began came back in the "
            f"{restored_in}"
            if restored is not None
            else "no request dispatched after the first unserved one came back served",
        ),
        _check(
            "traffic-served-after-the-service-was-restored",
            bool(_served(after_in_disrupted)) or bool(_served(recovered)),
            f"{len(_served(after_in_disrupted))} served later in the disrupted run and "
            f"{len(_served(recovered))} in the recovered run",
        ),
        _check(
            "no-published-interval-is-negative",
            not negative,
            "; ".join(f"{name} is {value} ms" for name, value in negative.items())
            or "every interval a reader would take as a duration is zero or more",
        ),
        _check(
            "the-runtime-service-lost-every-ready-endpoint",
            zero_index is not None,
            f"the lowest ready-endpoint count sampled was {min(endpoints)}"
            if endpoints
            else "no readiness sample was taken",
        ),
        _check(
            "the-runtime-service-had-a-ready-endpoint-again",
            recovered_endpoints,
            "a sample after the one with no ready endpoint reported at least one",
        ),
        _check(
            "readiness-samples-cover-the-replacement",
            len(readiness) >= descriptor.minimum_samples and gap_ms <= gap_ceiling,
            f"{len(readiness)} sample(s), widest gap before the replacement was ready "
            f"{gap_ms} ms against a ceiling of {gap_ceiling} ms",
        ),
        _check(
            "no-intervention-after-the-deletion",
            lifecycle["interventionsAfterDeletion"] == [],
            "the operating script issued no mutating command between the delete and "
            "the uninstall, and recorded none",
        ),
        _check(
            "both-load-runs-completed",
            len(runs_completed) == len(lifecycle["runs"]) == 2,
            "; ".join(
                f"{run['role']} exited {run['exitCode']} and ended "
                f"'{raws[str(run['role'])].end.get('state')}'"
                for run in lifecycle["runs"]
            ),
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
        _check(
            "the-tiers-that-were-not-deleted-did-not-restart",
            untouched_unchanged,
            "the platform-api and telemetry-collector pods carry the same names as "
            "before the disruption and report no container restart",
        ),
        _check(
            "every-tier-had-a-ready-pod-afterwards",
            every_tier_ready_after,
            "each of the three tiers reports one running pod with every container ready",
        ),
        _check(
            "the-replacement-was-ready-within-its-budget",
            replacement_ms <= _integer(budgets.get("replacementBudgetMs"), "budget"),
            f"{replacement_ms} ms against a budget of "
            f"{budgets['replacementBudgetMs']} ms",
        ),
        _check(
            "the-service-was-restored-within-the-recovery-budget",
            restored_from_deletion_ms is not None
            and restored_from_deletion_ms
            <= _integer(budgets.get("recoveryBudgetMs"), "budget"),
            f"{restored_from_deletion_ms} ms against a budget of "
            f"{budgets['recoveryBudgetMs']} ms"
            if restored_from_deletion_ms is not None
            else "the service was not observed restored to a caller",
        ),
    ]

    observations = [
        "The outage is stamped from the raw load record sets: it begins at the "
        "completion of the first request after the delete that was not served, and "
        "ends at the completion of the first one dispatched from then on that was. "
        "Neither end is a forward accepting a connection. V1-S3-003-PR2 published a "
        "figure stamped that way and an independent review of that change corrected "
        "it; the first execution of this experiment found this module stamping the "
        "start of the outage at the delete instead, which published two negative "
        "intervals, and the check named no-published-interval-is-negative exists "
        "because of it.",
        "The replacement interval ends at the replacement pod reporting itself Ready, "
        "not at the Deployment aggregate, which still counts a deleted pod inside its "
        "termination grace period.",
        f"Requests dispatched after the delete that the draining pod still served: "
        f"{len(drained_served)} of {len(draining)}. They are kept in their own window "
        "rather than counted on either side of the outage.",
        f"The service was observed restored in the {restored_in}.",
        f"Requests in flight when the delete was issued: "
        f"{sum(1 for entry in disrupted if entry.dispatched_at_ms < deleted_ms <= entry.completed_at_ms)}.",
        "The model reload is reported as the replacement pod from the operating "
        "script's first sighting of it to its own Ready condition. That interval is "
        "bounded by the sampling interval and includes scheduling and the integrity "
        "init container as well as loading the weights.",
        "The two instants the cluster reported for the replacement container are kept "
        "as the strings it emitted. They come from the node's clock and nothing here "
        "subtracts them from an instant read on the host's.",
        "That the model artifact survived the replacement is not established here. "
        "V1-S3-003-PR2 established it by comparing the artifact's inode and "
        "modification time either side of a replacement, and this run did not.",
    ]

    inputs = {
        "environment": text_digest(environment_text),
        "lifecycle": text_digest(lifecycle_text),
        "readiness": text_digest(readiness_text),
        "telemetry": text_digest(telemetry_text),
        "disruptedRaw": text_digest(disrupted_raw_text),
        "recoveredRaw": text_digest(recovered_raw_text),
    }

    record = {
        "schemaVersion": RECORD_SCHEMA,
        "kind": RECORD_KIND,
        "experimentId": EXPECTED_EXPERIMENT_ID,
        "experimentVersion": descriptor.document["experimentVersion"],
        "descriptorSha256": descriptor.sha256,
        "loadProfileSha256": descriptor.profile_sha256,
        "evidenceClass": EXPECTED_EVIDENCE_CLASS,
        "evidenceLabel": EXPECTED_EVIDENCE_LABEL,
        "certificationCeiling": EXPECTED_CEILING,
        "productionBenchmark": False,
        "portableCapacityClaim": False,
        "availabilityClaim": False,
        "boundary": descriptor.document["boundary"],
        "distinctProofQuestion": descriptor.document["distinctProofQuestion"],
        "environment": environment,
        "schedule": {
            "idleBaseline": lifecycle["idleBaseline"],
            "runs": [
                {
                    **run,
                    "runId": raws[str(run["role"])].header.get("runId"),
                    "endState": raws[str(run["role"])].end.get("state"),
                    "dispatched": len(raws[str(run["role"])].records),
                }
                for run in lifecycle["runs"]
            ],
            "settledEpochMs": settled_ms,
        },
        "disruption": {
            "mechanism": DISRUPTION_MECHANISM,
            "target": DISRUPTION_TARGET,
            "scope": DISRUPTION_SCOPE,
            "reversedBy": DISRUPTION_REVERSED_BY,
            "registeredScenarioId": disrupted_scenario,
            "landedInScenarioId": landed_in,
            "registeredOffsetMs": descriptor.disruption_offset_ms,
            "issuedAfterLoadStartMs": lifecycle["deletion"]["issuedAfterLoadStartMs"],
            "issuedEpochMs": deleted_ms,
            "pod": {
                "name": lifecycle["deletion"]["name"],
                "uid": lifecycle["deletion"]["uid"],
                "ownerKind": lifecycle["deletion"]["ownerKind"],
                "ownerName": lifecycle["deletion"]["ownerName"],
                "nodeName": lifecycle["deletion"]["nodeName"],
            },
            "podsMatchingSelector": lifecycle["deletion"]["podsMatchingSelector"],
        },
        "replacement": {
            "pod": {
                "name": lifecycle["replacement"]["name"],
                "uid": lifecycle["replacement"]["uid"],
                "ownerKind": lifecycle["replacement"]["ownerKind"],
                "ownerName": lifecycle["replacement"]["ownerName"],
                "nodeName": lifecycle["replacement"]["nodeName"],
            },
            "observedEpochMs": observed_ms,
            "readyEpochMs": ready_ms,
            "containerStartedAt": lifecycle["replacement"]["containerStartedAt"],
            "readyConditionAt": lifecycle["replacement"]["readyConditionAt"],
            "integrityInitContainer": lifecycle["replacement"]["initContainerName"],
            "integrityInitExitCode": lifecycle["replacement"]["initExitCode"],
            "restartCount": lifecycle["replacement"]["restartCount"],
            "releaseRevisionBefore": lifecycle["release"]["revisionBefore"],
            "releaseRevisionAfter": lifecycle["release"]["revisionAfter"],
            "acquisitionJobsBefore": lifecycle["acquisition"]["jobCountBefore"],
            "acquisitionJobsAfter": lifecycle["acquisition"]["jobCountAfter"],
        },
        "timings": timings,
        "callerImpact": {
            "percentileMethod": descriptor.profile.percentile_method,
            "windowsNote": (
                "Membership is by dispatch instant. 'servedWhileDraining' holds "
                "requests dispatched after the delete but before the first one that "
                "was not served; 'during' runs from that first unserved request to "
                "the one that ended the outage, inclusive of both; "
                "'afterInTheDisruptedRun' is what the same run sent afterwards, and "
                "'afterRecovery' is the whole second run."
            ),
            "windows": [
                _window(
                    "before", before, percentiles, start_ms=None, end_ms=deleted_ms
                ),
                _window(
                    "servedWhileDraining",
                    draining,
                    percentiles,
                    start_ms=deleted_ms,
                    end_ms=None if lost is None else lost.dispatched_at_ms,
                ),
                _window(
                    "during",
                    during,
                    percentiles,
                    start_ms=None if lost is None else lost.dispatched_at_ms,
                    end_ms=restored_at_ms,
                ),
                _window(
                    "afterInTheDisruptedRun",
                    after_in_disrupted,
                    percentiles,
                    start_ms=None if restored is None else restored.dispatched_at_ms,
                    end_ms=None,
                ),
                _window(
                    "afterRecovery",
                    recovered,
                    percentiles,
                    start_ms=lifecycle["runs"][1]["launchedEpochMs"],
                    end_ms=lifecycle["runs"][1]["exitedEpochMs"],
                ),
            ],
            "inFlightAtDeletion": {
                "dispatched": sum(
                    1
                    for entry in disrupted
                    if entry.dispatched_at_ms < deleted_ms <= entry.completed_at_ms
                ),
                "outcomes": {
                    outcome: sum(
                        1
                        for entry in disrupted
                        if entry.dispatched_at_ms < deleted_ms <= entry.completed_at_ms
                        and entry.record.outcome == outcome
                    )
                    for outcome in load.OUTCOMES
                },
            },
            "withinTheDisruptedScenario": {
                "scenarioId": disrupted_scenario,
                "comparable": comparable,
                "note": (
                    "The after side is every request of this scenario dispatched "
                    "after the service was restored, in either run."
                ),
                "before": _latency(level_before, percentiles),
                "after": _latency(level_after, percentiles),
            },
        },
        "readinessSamples": readiness,
        "humanAction": {
            "authorisationRequired": True,
            "valuesFileSuppliedByOperator": True,
            "interventionsAfterDeletion": lifecycle["interventionsAfterDeletion"],
            "recoveryIntervention": (
                "none"
                if lifecycle["interventionsAfterDeletion"] == []
                else lifecycle["interventionsAfterDeletion"][0]
            ),
            "note": (
                "What this can and cannot say. The operating script issues one "
                "mutating command after the delete -- the uninstall that ends the "
                "run -- and a test reads the script to establish that. So an empty "
                "list here means nothing in this workflow intervened; it does not "
                "establish that nothing outside it did."
            ),
        },
        "telemetry": {
            "collectorVersion": telemetry.get("collectorVersion"),
            "range": telemetry.get("range"),
            "series": series_rows,
            "note": (
                "Whether a signal exposed the disruption is not decided here. Each "
                "expression's registered expectation and its readings either side are "
                "recorded, and the reading of the pair belongs to a reviewed document."
            ),
        },
        "checks": checks,
        "usable": all(check["passed"] for check in checks),
        "observations": observations,
        "inputs": inputs,
        "limitations": list(descriptor.limitations),
    }
    refuse_private(dumps(record), "recovery record")
    return record
