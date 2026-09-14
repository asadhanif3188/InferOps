"""Generate a repeatable, bounded LLM inference load and keep its raw record.

The committed profile at ``deploy/serving/load/llm-load-profile.v1.json`` is the
authority for what a load run sends. Loading it reads committed files and nothing
else: the fixture is read by the same parser the InferOps API uses at request time,
the generation settings are compared with the runtime profile and the chart's
values, and the client deadline is held above the API's own deadline, so a drift
between any of them is a refusal at load time rather than a run nobody can repeat.

A run has three stages, in this order, and each one refuses before the next:

1. **Identity.** The target must be a loopback HTTP base URL. Its readiness answer
   and its model list are read, and the served model, model revision, runtime name,
   and adapter kind must be the ones the profile requires. A mock answer here, or
   anywhere later, is never recorded as a success.
2. **Warm-up.** A fixed number of requests at a fixed concurrency. They are recorded
   and excluded from every level. If any one of them is not a success the run stops
   before any level, because a level measured behind a failed warm-up describes the
   failure.
3. **Levels.** Each level runs a closed loop: ``concurrency`` workers each send the
   fixture, wait for the answer, and send again, until the level's request ceiling
   or its duration is reached. A request dispatched before the duration ends is
   always allowed to finish, and is always recorded.

**Accounting is a pure function.** Every dispatched request receives exactly one
sequence number and exactly one outcome, decided by :func:`classify` from the status,
the parsed body, the transport failure kind, and the latency, and from nothing else.
The raw reader refuses a record set whose sequence numbers have a gap, whose phase
counts disagree with its request records, or which claims to be a benchmark.
Summarizing reads only the raw record set, with integer arithmetic throughout, so the
same raw file always produces the same summary.

**What this module never keeps:** the prompt text in any result, the completion
text, a response header, a hostname, a user name, or an absolute path. It records
how long an answer took, how it was classified, and how many tokens it carried.

**What its figures are not.** Every latency and rate a run produces describes that
one run on its one provider, host, model, runtime, and profile. The project
boundaries forbid presenting any of them as portable capacity, a production SLO, or
a benchmark, and every record this module writes says so in its own fields.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import platform
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import HTTPException
from pathlib import Path
from typing import Any, cast

import yaml

from inferops.api.errors import RequestRefused
from inferops.api.surface import (
    CHAT_COMPLETIONS_PATH,
    CORRELATION_ID_HEADER,
    ERROR_CONDITION_ID,
    EXTENSION_ADAPTER_KIND,
    EXTENSION_MEMBER,
    EXTENSION_MODEL_REF,
    MODELS_PATH,
    READY_PATH,
    REQUEST_ID_HEADER,
)
from inferops.api.validation import parse_chat_completion
from tools.model_acquisition import load_manifest
from tools.runtime_configuration import load_runtime_profile
from tools.runtime_packaging import load_runtime_package
from tools.serving_baseline.core import total_memory_bytes

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = REPO_ROOT / "deploy/serving/load/llm-load-profile.v1.json"

EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_PROFILE_ID = "inferops-llm-load"
EXPECTED_BOUNDARIES_REF = "docs/architecture/project-boundaries.md"
EXPECTED_PROVIDER_CONTRACT_REF = (
    "docs/environment/local-cluster-provider-contract.v1alpha1.json"
)
EXPECTED_CHART_REF = "charts/inferops-llm/Chart.yaml"
EXPECTED_VALUES_REF = "charts/inferops-llm/values.yaml"
EXPECTED_REAL_VALUES_REF = "charts/inferops-llm/ci/real-values.yaml"
EXPECTED_RUNTIME_PROFILE_REF = "docs/serving/runtime-profile.local.v1.json"
EXPECTED_RESULT_DIRECTORY = Path(".cache/inferops/load")
EXPECTED_PERCENTILE_METHOD = "nearest-rank"
EXPECTED_PERCENTILES = (50, 95, 99)
LOOPBACK_HOST = "127.0.0.1"

#: The two evidence classes a raw record set may carry, and what each one means
#: for the run that wrote it. A real run is `local-real-cpu` and is capped at C2 by
#: the certification ladder; a rehearsal against the in-process stub is `synthetic`
#: and is capped at C1, whatever its numbers look like.
EVIDENCE_REAL = "local-real-cpu"
EVIDENCE_SYNTHETIC = "synthetic"
LABEL_REAL = "local real Kubernetes"
LABEL_SYNTHETIC = "synthetic rehearsal"
CEILING_FOR_CLASS: Mapping[str, str] = {EVIDENCE_REAL: "C2", EVIDENCE_SYNTHETIC: "C1"}

MODE_REAL = "real"
MODE_REHEARSAL = "rehearsal"

ADAPTER_MOCK = "mock"

#: The sentence every run header and every summary carries. It is a field, not a
#: comment, so that a record lifted out of this repository still says it.
BOUNDARY_STATEMENT = (
    "A bounded observation of this one run, on the provider, host, model, runtime, "
    "and profile recorded beside it. It is not a portable capacity figure, a "
    "production SLO, or a benchmark of Kubernetes, the model, the runtime, or any "
    "provider, and no figure in it may be published as one."
)

# --------------------------------------------------------------------------
# Ceilings that a profile cannot raise
# --------------------------------------------------------------------------
#
# Every bound on how much load a run may send is a constant here rather than a value
# read from the profile, so a heavier run cannot be authorized by editing the record
# that is supposed to bound it.

MAXIMUM_LEVELS = 6
MAXIMUM_CONCURRENCY = 8
MAXIMUM_WARMUP_REQUESTS = 20
MAXIMUM_REQUESTS_PER_LEVEL = 500
MAXIMUM_LEVEL_DURATION_SECONDS = 900
MAXIMUM_REQUEST_TIMEOUT_MS = 300_000

#: The worst case a whole run may take: both identity probe requests and every
#: warm-up request timing out, and every level running its full duration and then waiting one full
#: request deadline for what it already dispatched.
MAXIMUM_RUN_SECONDS = 3600

#: The ceiling on a raw record set this module reads back. A summary is computed in
#: memory, and an unbounded input is how that stops being true.
MAXIMUM_RAW_RECORDS = 20_000

#: The ceiling on one response body this module reads. A completion capped at the
#: profile's output tokens is a few kilobytes; anything near this is not one.
MAXIMUM_RESPONSE_BYTES = 1_000_000

# --------------------------------------------------------------------------
# Outcomes, phases, stop reasons, and end states
# --------------------------------------------------------------------------

#: The API answered with the required status, identity, model, and usage.
OUTCOME_SUCCESS = "success"
#: The API answered with a status other than the required one.
OUTCOME_HTTP_ERROR = "http-error"
#: The API answered with the required status and a body the criteria reject.
OUTCOME_INVALID = "invalid-response"
#: No answer arrived within the client deadline, or one arrived after it.
OUTCOME_TIMEOUT = "timeout"
#: The connection failed before any answer: refused, reset, or closed early.
OUTCOME_TRANSPORT = "transport-error"
#: An answer carried an adapter identity other than the required one. The run is
#: aborted when this happens, and the request is recorded as this and never as a
#: success.
OUTCOME_IDENTITY = "identity-refused"

#: Every outcome, in the order a summary reports them. Every request lands on
#: exactly one. Collapsing any two would hide a distinction an operator needs: an
#: API that refuses is not a runtime that timed out, and neither is a forward that
#: dropped the connection.
OUTCOMES: tuple[str, ...] = (
    OUTCOME_SUCCESS,
    OUTCOME_HTTP_ERROR,
    OUTCOME_INVALID,
    OUTCOME_TIMEOUT,
    OUTCOME_TRANSPORT,
    OUTCOME_IDENTITY,
)

PHASE_WARMUP = "warmup"
PHASE_MEASURED = "measured"
WARMUP_LEVEL_ID = "warmup"

STOP_CEILING = "request-ceiling"
STOP_DURATION = "duration"
STOP_ABORTED = "aborted"
STOP_INTERRUPTED = "interrupted"
STOP_TRANSPORT_LOST = "transport-lost"
STOP_REASONS = (
    STOP_CEILING,
    STOP_DURATION,
    STOP_ABORTED,
    STOP_INTERRUPTED,
    STOP_TRANSPORT_LOST,
)

END_COMPLETED = "completed"
END_WARMUP_FAILED = "warmup-failed"
END_ABORTED = "aborted"
END_INTERRUPTED = "interrupted"
END_TRANSPORT_LOST = "transport-lost"
END_STATES = (
    END_COMPLETED,
    END_WARMUP_FAILED,
    END_ABORTED,
    END_INTERRUPTED,
    END_TRANSPORT_LOST,
)

#: How many transport errors in a row end a run. A connection that fails before any
#: answer is not the platform answering: it is the forward, or the path to it, gone.
#: Without this, a dead `kubectl port-forward` fails every request in about a
#: millisecond, each level spends its whole request ceiling in seconds, and the run
#: ends `completed` with a record made entirely of the load generator's own loss of
#: its target. Answers the API does give -- a 503 while a model loads, a 504 at its
#: deadline -- are the platform's behaviour and never stop a run.
MAXIMUM_CONSECUTIVE_TRANSPORT_ERRORS = 5

#: A token a raw record may keep from a response: an error code, a finish reason, an
#: adapter kind, or a model reference. Anything outside this alphabet is replaced,
#: because a raw record is committed and a response body is not a trusted source of
#: text to commit.
SAFE_TOKEN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
UNRECOGNIZED = "unrecognized"

#: What an environment fact may look like when it is a version or a reference.
SAFE_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}")
IMAGE_BY_DIGEST = re.compile(r"[a-z0-9][a-z0-9._/:-]{0,199}@sha256:[0-9a-f]{64}")
GIT_REVISION = re.compile(r"[0-9a-f]{40}")

#: The labelled placeholder the chart's render fixtures carry for the API image: the
#: SHA-256 of a public ASCII string, which anyone can recompute and no image has.
API_DIGEST_PLACEHOLDER = (
    "sha256:" + hashlib.sha256(b"inferops-api-image-not-yet-published").hexdigest()
)


class LoadError(RuntimeError):
    """The load profile, an environment fact, a bounded step, or a raw set failed."""


class LoadRefused(LoadError):
    """A precondition for sending load was not satisfied."""


# --------------------------------------------------------------------------
# The committed profile
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Fixture:
    """The one request every load request sends, byte for byte."""

    fixture_id: str
    request_path: str
    model: str
    stream: bool
    messages: tuple[Mapping[str, str], ...]

    def body(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [dict(message) for message in self.messages],
            "stream": self.stream,
        }


@dataclass(frozen=True, slots=True)
class Level:
    """One concurrency level of the measured phase."""

    level_id: str
    concurrency: int


@dataclass(frozen=True, slots=True)
class Profile:
    """The committed load profile after every field has been validated."""

    schema_version: str
    profile_id: str
    profile_version: str
    profile_sha256: str
    evidence_class: str
    evidence_label: str
    certification_ceiling: str
    production_benchmark: bool
    portable_capacity_claim: bool
    boundary: str
    boundaries_ref: str
    provider_contract_ref: str
    chart_ref: str
    values_ref: str
    real_values_ref: str
    runtime_profile_ref: str
    target_scheme: str
    target_host: str
    readiness_path: str
    models_path: str
    identity_probe_timeout_ms: int
    fixture: Fixture
    max_output_tokens: int
    temperature: float
    context_size_tokens: int
    parallel_slots: int
    warmup_requests: int
    warmup_concurrency: int
    levels: tuple[Level, ...]
    duration_seconds: int
    max_requests_per_level: int
    request_timeout_ms: int
    required_status: int
    required_adapter_kind: str
    required_model_ref: str
    required_runtime_name: str
    require_usage: bool
    result_directory: Path
    raw_file: str
    summary_file: str
    raw_format: str
    summary_format: str
    percentile_method: str
    reported_percentiles: tuple[int, ...]

    def worst_case_seconds(self) -> int:
        """How long a run may take if every bound is reached, in whole seconds."""
        timeout_seconds = -(-self.request_timeout_ms // 1000)
        # The identity probe sends two requests, readiness and the model list, each
        # bounded by its own deadline, before any load.
        identity = 2 * -(-self.identity_probe_timeout_ms // 1000)
        warmup = identity + self.warmup_requests * timeout_seconds
        levels = len(self.levels) * (self.duration_seconds + timeout_seconds)
        return warmup + levels


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LoadError(f"load field '{field}' must be an object")
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise LoadError(f"load field '{field}' must be a non-empty string")
    return value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise LoadError(
            f"load field '{field}' must be an integer of at least {minimum}"
        )
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise LoadError(f"load field '{field}' must be a boolean")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LoadError(f"load field '{field}' must be a number")
    return float(value)


def _require_keys(record: Mapping[str, Any], field: str, expected: set[str]) -> None:
    if set(record) != expected:
        raise LoadError(f"load field '{field}' has missing or unsupported members")


def _messages(value: Any, field: str) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list) or not value:
        raise LoadError(f"load field '{field}' must be a non-empty list")
    messages: list[Mapping[str, str]] = []
    for index, item in enumerate(value):
        message = _object(item, f"{field}[{index}]")
        _require_keys(message, f"{field}[{index}]", {"role", "content"})
        messages.append(
            {
                "role": _string(message.get("role"), f"{field}[{index}].role"),
                "content": _string(message.get("content"), f"{field}[{index}].content"),
            }
        )
    return tuple(messages)


def _levels(value: Any) -> tuple[Level, ...]:
    if not isinstance(value, list) or not value:
        raise LoadError("load field 'levels' must be a non-empty list")
    levels: list[Level] = []
    for index, item in enumerate(value):
        record = _object(item, f"levels[{index}]")
        _require_keys(record, f"levels[{index}]", {"levelId", "concurrency"})
        levels.append(
            Level(
                level_id=_string(record.get("levelId"), f"levels[{index}].levelId"),
                concurrency=_integer(
                    record.get("concurrency"), f"levels[{index}].concurrency"
                ),
            )
        )
    return tuple(levels)


def _percentiles(value: Any, field: str) -> tuple[int, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(
            not isinstance(item, int) or isinstance(item, bool) or not 1 <= item <= 99
            for item in value
        )
    ):
        raise LoadError(f"load field '{field}' must list percentiles 1-99")
    return tuple(cast(list[int], value))


def profile_digest(path: Path) -> str:
    """The SHA-256 of a profile file with its line endings normalized to LF.

    Normalized because a Windows checkout may hold the committed file with CRLF, and
    a digest that changes with the checkout's line endings would make one committed
    profile look like two.
    """
    try:
        data = path.read_bytes()
    except OSError as error:
        raise LoadError("the load profile is unreadable") from error
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path, what: str) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), "root")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LoadError(f"the {what} is unreadable") from error


def load_profile(path: Path = PROFILE_PATH, *, repo_root: Path = REPO_ROOT) -> Profile:
    """Load and cross-check the committed load profile without sending anything."""
    record = _read_json(path, "load profile")
    _require_keys(
        record,
        "root",
        {
            "schemaVersion",
            "profileId",
            "profileVersion",
            "evidenceClass",
            "evidenceLabel",
            "certificationCeiling",
            "productionBenchmark",
            "portableCapacityClaim",
            "boundary",
            "boundariesRef",
            "providerContractRef",
            "release",
            "target",
            "fixture",
            "generation",
            "warmup",
            "levels",
            "measured",
            "timeouts",
            "success",
            "results",
        },
    )
    release = _object(record.get("release"), "release")
    target = _object(record.get("target"), "target")
    fixture = _object(record.get("fixture"), "fixture")
    generation = _object(record.get("generation"), "generation")
    warmup = _object(record.get("warmup"), "warmup")
    measured = _object(record.get("measured"), "measured")
    timeouts = _object(record.get("timeouts"), "timeouts")
    success = _object(record.get("success"), "success")
    results = _object(record.get("results"), "results")
    _require_keys(
        release,
        "release",
        {"chartRef", "valuesRef", "realValuesRef", "runtimeProfileRef"},
    )
    _require_keys(
        target,
        "target",
        {"scheme", "host", "readinessPath", "modelsPath", "identityProbeTimeoutMs"},
    )
    _require_keys(
        fixture, "fixture", {"fixtureId", "requestPath", "model", "stream", "messages"}
    )
    _require_keys(
        generation,
        "generation",
        {"maxOutputTokens", "temperature", "contextSizeTokens", "parallelSlots"},
    )
    _require_keys(warmup, "warmup", {"requests", "concurrency"})
    _require_keys(measured, "measured", {"durationSeconds", "maxRequestsPerLevel"})
    _require_keys(timeouts, "timeouts", {"requestTimeoutMs"})
    _require_keys(
        success,
        "success",
        {
            "requiredStatus",
            "requiredAdapterKind",
            "requiredModelRef",
            "requiredRuntimeName",
            "requireUsage",
        },
    )
    _require_keys(
        results,
        "results",
        {
            "directory",
            "rawFile",
            "summaryFile",
            "rawFormat",
            "summaryFormat",
            "percentileMethod",
            "reportedPercentiles",
        },
    )
    profile = Profile(
        schema_version=_string(record.get("schemaVersion"), "schemaVersion"),
        profile_id=_string(record.get("profileId"), "profileId"),
        profile_version=_string(record.get("profileVersion"), "profileVersion"),
        profile_sha256=profile_digest(path),
        evidence_class=_string(record.get("evidenceClass"), "evidenceClass"),
        evidence_label=_string(record.get("evidenceLabel"), "evidenceLabel"),
        certification_ceiling=_string(
            record.get("certificationCeiling"), "certificationCeiling"
        ),
        production_benchmark=_boolean(
            record.get("productionBenchmark"), "productionBenchmark"
        ),
        portable_capacity_claim=_boolean(
            record.get("portableCapacityClaim"), "portableCapacityClaim"
        ),
        boundary=_string(record.get("boundary"), "boundary"),
        boundaries_ref=_string(record.get("boundariesRef"), "boundariesRef"),
        provider_contract_ref=_string(
            record.get("providerContractRef"), "providerContractRef"
        ),
        chart_ref=_string(release.get("chartRef"), "release.chartRef"),
        values_ref=_string(release.get("valuesRef"), "release.valuesRef"),
        real_values_ref=_string(release.get("realValuesRef"), "release.realValuesRef"),
        runtime_profile_ref=_string(
            release.get("runtimeProfileRef"), "release.runtimeProfileRef"
        ),
        target_scheme=_string(target.get("scheme"), "target.scheme"),
        target_host=_string(target.get("host"), "target.host"),
        readiness_path=_string(target.get("readinessPath"), "target.readinessPath"),
        models_path=_string(target.get("modelsPath"), "target.modelsPath"),
        identity_probe_timeout_ms=_integer(
            target.get("identityProbeTimeoutMs"), "target.identityProbeTimeoutMs"
        ),
        fixture=Fixture(
            fixture_id=_string(fixture.get("fixtureId"), "fixture.fixtureId"),
            request_path=_string(fixture.get("requestPath"), "fixture.requestPath"),
            model=_string(fixture.get("model"), "fixture.model"),
            stream=_boolean(fixture.get("stream"), "fixture.stream"),
            messages=_messages(fixture.get("messages"), "fixture.messages"),
        ),
        max_output_tokens=_integer(
            generation.get("maxOutputTokens"), "generation.maxOutputTokens"
        ),
        temperature=_number(generation.get("temperature"), "generation.temperature"),
        context_size_tokens=_integer(
            generation.get("contextSizeTokens"), "generation.contextSizeTokens"
        ),
        parallel_slots=_integer(
            generation.get("parallelSlots"), "generation.parallelSlots"
        ),
        warmup_requests=_integer(warmup.get("requests"), "warmup.requests"),
        warmup_concurrency=_integer(warmup.get("concurrency"), "warmup.concurrency"),
        levels=_levels(record.get("levels")),
        duration_seconds=_integer(
            measured.get("durationSeconds"), "measured.durationSeconds"
        ),
        max_requests_per_level=_integer(
            measured.get("maxRequestsPerLevel"), "measured.maxRequestsPerLevel"
        ),
        request_timeout_ms=_integer(
            timeouts.get("requestTimeoutMs"), "timeouts.requestTimeoutMs"
        ),
        required_status=_integer(
            success.get("requiredStatus"), "success.requiredStatus"
        ),
        required_adapter_kind=_string(
            success.get("requiredAdapterKind"), "success.requiredAdapterKind"
        ),
        required_model_ref=_string(
            success.get("requiredModelRef"), "success.requiredModelRef"
        ),
        required_runtime_name=_string(
            success.get("requiredRuntimeName"), "success.requiredRuntimeName"
        ),
        require_usage=_boolean(success.get("requireUsage"), "success.requireUsage"),
        result_directory=Path(_string(results.get("directory"), "results.directory")),
        raw_file=_string(results.get("rawFile"), "results.rawFile"),
        summary_file=_string(results.get("summaryFile"), "results.summaryFile"),
        raw_format=_string(results.get("rawFormat"), "results.rawFormat"),
        summary_format=_string(results.get("summaryFormat"), "results.summaryFormat"),
        percentile_method=_string(
            results.get("percentileMethod"), "results.percentileMethod"
        ),
        reported_percentiles=_percentiles(
            results.get("reportedPercentiles"), "results.reportedPercentiles"
        ),
    )
    validate_profile(profile, repo_root=repo_root)
    return profile


def _yaml_object(path: Path, what: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise LoadError(f"the {what} the load profile names is unreadable") from error
    return _object(loaded, what)


def _overlay(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _overlay(current, value)
        else:
            merged[key] = value
    return merged


def _chart_values(repo_root: Path) -> dict[str, Any]:
    """The chart's defaults with the real-profile values layered over them.

    The same two files, in the same order, the documented real install passes to
    `helm install`, merged the way Helm merges maps: a later map member replaces a
    scalar and merges into a map.
    """
    return _overlay(
        _yaml_object(repo_root / EXPECTED_VALUES_REF, "chart values"),
        _yaml_object(repo_root / EXPECTED_REAL_VALUES_REF, "real-profile values"),
    )


def _chart_version(repo_root: Path) -> str:
    chart = _yaml_object(repo_root / EXPECTED_CHART_REF, "chart")
    return f"{_string(chart.get('name'), 'chart.name')}-{_string(chart.get('version'), 'chart.version')}"


def supported_providers(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    """The provider identifiers the accepted provider contract publishes."""
    contract = _read_json(
        repo_root / EXPECTED_PROVIDER_CONTRACT_REF, "provider contract"
    )
    providers = contract.get("providers")
    if not isinstance(providers, list) or not providers:
        raise LoadError("the provider contract publishes no provider")
    return tuple(
        _string(_object(entry, "providers[]").get("providerId"), "providerId")
        for entry in providers
    )


def validate_profile(profile: Profile, *, repo_root: Path = REPO_ROOT) -> None:
    """Refuse a profile that drifted from the records it must agree with."""
    if (
        profile.schema_version != EXPECTED_SCHEMA
        or profile.profile_id != EXPECTED_PROFILE_ID
        or profile.evidence_class != EVIDENCE_REAL
        or profile.evidence_label != LABEL_REAL
        or profile.certification_ceiling != CEILING_FOR_CLASS[EVIDENCE_REAL]
    ):
        raise LoadError("the load profile identity is unsupported")
    if (
        profile.production_benchmark
        or profile.portable_capacity_claim
        or profile.boundary != BOUNDARY_STATEMENT
    ):
        raise LoadError(
            "the load profile may not declare a production benchmark or a portable "
            "capacity claim, and must carry the boundary statement verbatim"
        )
    if (
        profile.boundaries_ref != EXPECTED_BOUNDARIES_REF
        or profile.provider_contract_ref != EXPECTED_PROVIDER_CONTRACT_REF
        or profile.chart_ref != EXPECTED_CHART_REF
        or profile.values_ref != EXPECTED_VALUES_REF
        or profile.real_values_ref != EXPECTED_REAL_VALUES_REF
        or profile.runtime_profile_ref != EXPECTED_RUNTIME_PROFILE_REF
    ):
        raise LoadError("the load profile references an unexpected document")
    if (
        profile.target_scheme != "http"
        or profile.target_host != LOOPBACK_HOST
        or profile.readiness_path != READY_PATH
        or profile.models_path != MODELS_PATH
        or profile.identity_probe_timeout_ms > MAXIMUM_REQUEST_TIMEOUT_MS
    ):
        raise LoadError("the load profile target must be the loopback InferOps API")

    runtime = load_runtime_profile()
    if (
        profile.fixture.request_path != CHAT_COMPLETIONS_PATH
        or profile.fixture.stream
        or profile.fixture.model != runtime.platform_identifier
    ):
        raise LoadError("the load fixture does not match the served model")
    # The same reader the API runs at request time, over the profile's own body.
    # `V1-S2-005-PR2` paid for learning that a fixture can satisfy every other check
    # here and still be refused by the API on every request.
    try:
        parse_chat_completion(
            json.dumps(profile.fixture.body()).encode("utf-8"),
            served_model=profile.fixture.model,
        )
    except RequestRefused as error:
        raise LoadError(
            f"the load fixture is refused by the InferOps API: {error}"
        ) from error

    values = _chart_values(repo_root)
    api = _object(values.get("api"), "chart values api")
    chart_runtime = _object(values.get("runtime"), "chart values runtime")
    chart_model = _object(values.get("model"), "chart values model")
    if (
        profile.max_output_tokens != runtime.default_max_output_tokens
        or profile.temperature != runtime.default_temperature
        or profile.context_size_tokens != runtime.context_size_tokens
        or profile.parallel_slots != runtime.parallel_slots
    ):
        raise LoadError("the load generation settings drifted from the runtime profile")
    if (
        profile.max_output_tokens != api.get("maxOutputTokens")
        or profile.max_output_tokens != chart_runtime.get("defaultMaxOutputTokens")
        or profile.temperature != chart_runtime.get("defaultTemperature")
        or profile.context_size_tokens != chart_runtime.get("contextSizeTokens")
        or profile.parallel_slots != chart_runtime.get("parallelSlots")
        or profile.fixture.model != chart_model.get("identifier")
    ):
        raise LoadError("the load generation settings drifted from the chart values")

    api_timeout = api.get("requestTimeoutMs")
    if not isinstance(api_timeout, int) or isinstance(api_timeout, bool):
        raise LoadError("the chart values carry no API request deadline")
    # The client deadline sits above the API's own. Below it, a slow completion is
    # recorded as a client timeout and the platform's own answer at its deadline is
    # never seen; the record would describe the load generator's patience rather than
    # the platform's behaviour. In the API container that answer is usually the HTTP
    # carrier's empty-bodied 504, not the adapter's canonical `upstream-timeout`: both
    # budgets are the same `requestTimeoutMs`, and the carrier's starts first. The
    # record keeps the status, and an empty body leaves the error code null.
    if not api_timeout < profile.request_timeout_ms <= MAXIMUM_REQUEST_TIMEOUT_MS:
        raise LoadError(
            "the load request deadline must exceed the API's own deadline and stay "
            "within the ceiling"
        )

    if not 1 <= len(profile.levels) <= MAXIMUM_LEVELS:
        raise LoadError("the load profile names an unsupported number of levels")
    identifiers = [level.level_id for level in profile.levels]
    if len(set(identifiers)) != len(identifiers) or WARMUP_LEVEL_ID in identifiers:
        raise LoadError("the load levels must have distinct, non-reserved identifiers")
    if any(SAFE_TOKEN.fullmatch(identifier) is None for identifier in identifiers):
        raise LoadError("a load level identifier is not a safe token")
    concurrencies = [level.concurrency for level in profile.levels]
    if any(
        value > MAXIMUM_CONCURRENCY for value in concurrencies
    ) or concurrencies != sorted(set(concurrencies)):
        raise LoadError(
            "the load levels must rise strictly in concurrency within the ceiling"
        )
    if (
        profile.warmup_requests > MAXIMUM_WARMUP_REQUESTS
        or profile.warmup_concurrency > MAXIMUM_CONCURRENCY
        or profile.warmup_concurrency > profile.warmup_requests
        or profile.max_requests_per_level > MAXIMUM_REQUESTS_PER_LEVEL
        or profile.duration_seconds > MAXIMUM_LEVEL_DURATION_SECONDS
        or profile.max_requests_per_level < max(concurrencies)
    ):
        raise LoadError("the load execution envelope is unsupported")
    # A duration shorter than one request deadline can stop a level before any
    # request has had the chance to be answered or to time out, which is a level
    # that measured its own stop condition.
    if profile.duration_seconds * 1000 < profile.request_timeout_ms:
        raise LoadError("the load duration is shorter than one request deadline")
    if profile.worst_case_seconds() > MAXIMUM_RUN_SECONDS:
        raise LoadError("the load profile's worst case exceeds the run ceiling")
    if (
        profile.required_status != 200
        or profile.required_adapter_kind != MODE_REAL
        or profile.required_model_ref != runtime.platform_identifier
        or not profile.require_usage
    ):
        raise LoadError(
            "the load success criteria must require an explicitly real answer"
        )
    if (
        profile.result_directory != EXPECTED_RESULT_DIRECTORY
        or "/" in profile.raw_file
        or "\\" in profile.raw_file
        or "/" in profile.summary_file
        or "\\" in profile.summary_file
        or profile.raw_format != "application/jsonl"
        or profile.summary_format != "application/json"
        or profile.percentile_method != EXPECTED_PERCENTILE_METHOD
        or profile.reported_percentiles != EXPECTED_PERCENTILES
    ):
        raise LoadError("the load result layout is unsupported")
    if chart_model.get("revision") != load_manifest().revision:
        raise LoadError("the chart's model revision disagrees with the model record")


# --------------------------------------------------------------------------
# Environment: the host, the declared facts, and the served identity
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HostRecord:
    """The load generator's host, with nothing that identifies a machine or a person."""

    operating_system: str
    release: str
    architecture: str
    logical_cpus: int
    total_memory_bytes: int | None
    python_version: str

    def document(self) -> dict[str, Any]:
        return {
            "operatingSystem": self.operating_system,
            "release": self.release,
            "architecture": self.architecture,
            "logicalCpus": self.logical_cpus,
            "totalMemoryBytes": self.total_memory_bytes,
            "pythonVersion": self.python_version,
        }


def capture_host() -> HostRecord:
    """Record the generator host. No hostname, user, network identity, or path."""
    return HostRecord(
        operating_system=platform.system() or "unknown",
        release=platform.release() or "unknown",
        architecture=platform.machine() or "unknown",
        logical_cpus=os.cpu_count() or 0,
        total_memory_bytes=total_memory_bytes(),
        python_version=platform.python_version(),
    )


#: The environment facts a real run is given, and the provenance of each one. The
#: split is recorded in every raw header, because a fact this tool compared with the
#: repository and a fact it simply wrote down are different kinds of evidence and a
#: reader must not have to guess which is which. "Checked against the repository"
#: means the stated value agrees with a committed record -- the provider is one the
#: contract publishes, the chart and pins are this checkout's. It never means the
#: cluster was asked: this module contacts no cluster.
FACT_FIELDS = (
    "provider",
    "kubernetesServerVersion",
    "chart",
    "releaseRevision",
    "apiImage",
    "runtimeImage",
    "modelRevision",
    "apiReplicas",
    "runtimeReplicas",
    "repositoryRevision",
)
FACTS_CHECKED_AGAINST_REPOSITORY = (
    "provider",
    "chart",
    "runtimeImage",
    "modelRevision",
)
FACTS_DECLARED_ONLY = (
    "kubernetesServerVersion",
    "releaseRevision",
    "apiImage",
    "apiReplicas",
    "runtimeReplicas",
    "repositoryRevision",
)
#: What the target's own readiness and model-list answers report. These are the
#: API's statements about its configuration, read before any load: `modelRevision`
#: and `runtimeName` are values the API was built or configured with, and
#: `runtimeVersion` is the pinned image digest unless something asked the runtime
#: for its build. None of them is an independent observation of the model file or
#: the image a pod runs.
IDENTITY_REPORTED_BY_API = (
    "readinessStatus",
    "adapterKind",
    "modelId",
    "modelRevision",
    "runtimeName",
    "runtimeVersion",
)


@dataclass(frozen=True, slots=True)
class EnvironmentFacts:
    """What the operator states about the release a real run is sent to."""

    provider: str
    kubernetes_server_version: str
    chart: str
    release_revision: int
    api_image: str
    runtime_image: str
    model_revision: str
    api_replicas: int
    runtime_replicas: int
    repository_revision: str

    def document(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "kubernetesServerVersion": self.kubernetes_server_version,
            "chart": self.chart,
            "releaseRevision": self.release_revision,
            "apiImage": self.api_image,
            "runtimeImage": self.runtime_image,
            "modelRevision": self.model_revision,
            "apiReplicas": self.api_replicas,
            "runtimeReplicas": self.runtime_replicas,
            "repositoryRevision": self.repository_revision,
        }


def _fact_reference(value: Any, field: str) -> str:
    text = _string(value, f"facts.{field}")
    if SAFE_REFERENCE.fullmatch(text) is None:
        raise LoadError(f"environment fact '{field}' is not a plain reference")
    return text


def parse_facts(
    document: Mapping[str, Any], *, repo_root: Path = REPO_ROOT
) -> EnvironmentFacts:
    """Validate the environment facts and hold the pinned ones to the repository.

    A provider the accepted contract does not publish, a chart version, runtime image,
    or model revision other than the committed one, and an API image not pinned by
    digest are each refused. The chart's API digest placeholder is refused by name:
    no image with that digest exists, so a record naming it describes no release.
    """
    _require_keys(document, "facts", set(FACT_FIELDS))
    facts = EnvironmentFacts(
        provider=_fact_reference(document.get("provider"), "provider"),
        kubernetes_server_version=_fact_reference(
            document.get("kubernetesServerVersion"), "kubernetesServerVersion"
        ),
        chart=_fact_reference(document.get("chart"), "chart"),
        release_revision=_integer(
            document.get("releaseRevision"), "facts.releaseRevision"
        ),
        api_image=_fact_reference(document.get("apiImage"), "apiImage"),
        runtime_image=_fact_reference(document.get("runtimeImage"), "runtimeImage"),
        model_revision=_fact_reference(document.get("modelRevision"), "modelRevision"),
        api_replicas=_integer(document.get("apiReplicas"), "facts.apiReplicas"),
        runtime_replicas=_integer(
            document.get("runtimeReplicas"), "facts.runtimeReplicas"
        ),
        repository_revision=_fact_reference(
            document.get("repositoryRevision"), "repositoryRevision"
        ),
    )
    if facts.provider not in supported_providers(repo_root):
        raise LoadRefused(
            "the environment facts name a provider the provider contract does not "
            "publish"
        )
    if facts.chart != _chart_version(repo_root):
        raise LoadRefused(
            "the environment facts name a chart other than this checkout's"
        )
    if facts.runtime_image != load_runtime_package().image_reference:
        raise LoadRefused(
            "the environment facts name a runtime image other than the pin"
        )
    if facts.model_revision != load_manifest().revision:
        raise LoadRefused(
            "the environment facts name a model revision other than the pin"
        )
    if IMAGE_BY_DIGEST.fullmatch(facts.api_image) is None:
        raise LoadRefused("the environment facts must name the API image by digest")
    if facts.api_image.rsplit("@", 1)[1] == API_DIGEST_PLACEHOLDER:
        raise LoadRefused(
            "the environment facts name the chart's placeholder API digest, which no "
            "image has"
        )
    if GIT_REVISION.fullmatch(facts.repository_revision) is None:
        raise LoadRefused(
            "the environment facts must name the repository revision as a full commit"
        )
    return facts


def load_facts(path: Path, *, repo_root: Path = REPO_ROOT) -> EnvironmentFacts:
    """Read the environment facts file an operator wrote for one real run."""
    return parse_facts(_read_json(path, "environment facts file"), repo_root=repo_root)


@dataclass(frozen=True, slots=True)
class ServedIdentity:
    """What the target's own readiness and model-list answers said, before any load."""

    readiness_status: str
    adapter_kind: str
    model_id: str
    model_revision: str
    runtime_name: str
    runtime_version: str

    def document(self) -> dict[str, Any]:
        return {
            "readinessStatus": self.readiness_status,
            "adapterKind": self.adapter_kind,
            "modelId": self.model_id,
            "modelRevision": self.model_revision,
            "runtimeName": self.runtime_name,
            "runtimeVersion": self.runtime_version,
        }


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HttpAnswer:
    """A status and a parsed JSON body, or ``None`` where the body was not JSON."""

    status: int
    body: object | None


class TransportTimeout(Exception):
    """No answer arrived within the client deadline."""


class TransportFailure(Exception):
    """The connection failed before any answer arrived."""


#: ``(method, url, json_body_or_None, headers, timeout_seconds) -> HttpAnswer``.
Transport = Callable[
    [str, str, Mapping[str, Any] | None, Mapping[str, str], float], HttpAnswer
]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_: Any, **__: Any) -> None:
        return None


#: No proxy from the environment and no redirect: a request goes to the loopback
#: address it names, or it fails. A proxy variable on the operator's shell must not be
#: able to route load somewhere else.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _parse_body(data: bytes) -> object | None:
    if len(data) > MAXIMUM_RESPONSE_BYTES:
        return None
    try:
        parsed: object = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    return parsed


def http_transport(
    method: str,
    url: str,
    body: Mapping[str, Any] | None,
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> HttpAnswer:
    """Send one request over plain HTTP and return what came back."""
    payload = None if body is None else json.dumps(dict(body)).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method=method)
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        with _OPENER.open(request, timeout=timeout_seconds) as response:
            data = response.read(MAXIMUM_RESPONSE_BYTES + 1)
            return HttpAnswer(int(response.status), _parse_body(data))
    except urllib.error.HTTPError as error:
        try:
            data = error.read(MAXIMUM_RESPONSE_BYTES + 1)
        except (OSError, HTTPException):
            data = b""
        return HttpAnswer(int(error.code), _parse_body(data))
    except TimeoutError as error:
        raise TransportTimeout() from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise TransportTimeout() from error
        raise TransportFailure() from error
    except (OSError, HTTPException) as error:
        raise TransportFailure() from error


def require_loopback_base_url(base_url: str, profile: Profile) -> str:
    """Refuse a target that is not a plain loopback HTTP base URL.

    A load generator that followed whatever address it was handed could send real
    load to a service nobody meant to load, and write a record carrying this project's
    evidence label while doing so. The port is the operator's, because the forward has
    to be able to move when something else already holds a port.
    """
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != profile.target_scheme:
        raise LoadRefused("the load target must be plain loopback HTTP")
    if parsed.username is not None or parsed.password is not None:
        raise LoadRefused("the load target must carry no credentials")
    if parsed.hostname != profile.target_host:
        raise LoadRefused(f"the load target must name {profile.target_host}")
    try:
        port = parsed.port
    except ValueError as error:
        raise LoadRefused("the load target names an invalid port") from error
    if port is None:
        raise LoadRefused("the load target must name the forwarded port")
    if parsed.path.rstrip("/") or parsed.query or parsed.fragment:
        raise LoadRefused("the load target must carry no path, query, or fragment")
    return f"http://{profile.target_host}:{port}"


def _safe_token(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value if SAFE_TOKEN.fullmatch(value) else UNRECOGNIZED


def _printable(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise LoadRefused(f"the target's model list carries no {field}")
    if len(value) > 200 or not value.isprintable():
        raise LoadRefused(f"the target's {field} is not a plain printable value")
    return value


def probe_identity(
    profile: Profile,
    base_url: str,
    *,
    transport: Transport = http_transport,
) -> ServedIdentity:
    """Read readiness and the model list, and refuse a target that is not the release.

    Nothing is sent to the completion endpoint until both answers name the required
    adapter kind, the served model, its revision, and the runtime. A mock adapter is
    refused here by name, so that a mock release is stopped before it is loaded rather
    than after its answers have been counted.
    """
    timeout = profile.identity_probe_timeout_ms / 1000
    try:
        ready = transport(
            "GET", f"{base_url}{profile.readiness_path}", None, {}, timeout
        )
        models = transport("GET", f"{base_url}{profile.models_path}", None, {}, timeout)
    except (TransportTimeout, TransportFailure) as error:
        raise LoadRefused(
            "the load target did not answer its identity probe"
        ) from error
    ready_body = ready.body if isinstance(ready.body, dict) else {}
    if ready.status != 200 or ready_body.get("status") != "ready":
        raise LoadRefused("the load target is not ready")
    ready_adapter = ready_body.get("adapterKind")
    if ready_adapter == ADAPTER_MOCK or ready_adapter != profile.required_adapter_kind:
        raise LoadRefused(
            "the load target's readiness names an adapter other than the required one"
        )
    if models.status != 200 or not isinstance(models.body, dict):
        raise LoadRefused("the load target did not list its model")
    data = models.body.get("data")
    extension = models.body.get(EXTENSION_MEMBER)
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise LoadRefused("the load target must list exactly one model")
    if not isinstance(extension, dict):
        raise LoadRefused("the load target's model list carries no InferOps extension")
    runtime = extension.get("runtime")
    if not isinstance(runtime, dict):
        raise LoadRefused("the load target's model list carries no runtime descriptor")
    adapter_kind = extension.get(EXTENSION_ADAPTER_KIND)
    if adapter_kind != profile.required_adapter_kind:
        raise LoadRefused(
            "the load target's model list names an adapter other than the required one"
        )
    identity = ServedIdentity(
        readiness_status="ready",
        adapter_kind=profile.required_adapter_kind,
        model_id=_printable(data[0].get("id"), "model identifier"),
        model_revision=_printable(runtime.get("modelRevision"), "model revision"),
        runtime_name=_printable(runtime.get("name"), "runtime name"),
        runtime_version=_printable(runtime.get("version"), "runtime version"),
    )
    if identity.model_id != profile.required_model_ref:
        raise LoadRefused("the load target serves a model other than the fixture's")
    if identity.runtime_name != profile.required_runtime_name:
        raise LoadRefused("the load target reports a runtime other than the pinned one")
    if identity.model_revision != load_manifest().revision:
        raise LoadRefused("the load target reports a model revision other than the pin")
    return identity


# --------------------------------------------------------------------------
# Classification: a pure function of what came back
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Classification:
    """The outcome of one request, and the non-sensitive observations kept from it."""

    outcome: str
    status: int
    error_code: str | None
    error_condition: str | None
    finish_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    adapter_kind: str | None
    model_ref: str | None


def _count(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _identity(body: object) -> Mapping[str, Any]:
    """Adapter and model identity from a completion's extension or an error's details."""
    if not isinstance(body, dict):
        return {}
    extension = body.get(EXTENSION_MEMBER)
    if isinstance(extension, dict):
        return cast(dict[str, Any], extension)
    details = body.get("details")
    if isinstance(details, dict):
        return cast(dict[str, Any], details)
    return {}


def classify(
    profile: Profile,
    *,
    answer: HttpAnswer | None,
    failure: str | None,
    latency_ms: int,
) -> Classification:
    """Decide one request's outcome from what came back and nothing else.

    The order is the rule, and it is written once, here:

    1. a client timeout is ``timeout``; a connection failure is ``transport-error``;
    2. an answer naming an adapter other than the required one is
       ``identity-refused``, whatever its status and however late it arrived, so a
       late mock answer still stops the run;
    3. an answer that arrived after the client deadline is ``timeout`` whatever it
       says, because the deadline is part of the profile and a success that broke it
       is not a success the profile describes;
    4. a status other than the required one is ``http-error``, with the canonical
       error code and the condition identifier from its details kept only if each is
       a plain token. A body that is not a canonical error leaves both null;
    5. the required status with a body that names another model, has no choice, or
       lacks the required usage counts is ``invalid-response``;
    6. anything left is ``success``.

    Token counts are kept only for a success. A refusal's counts are not counts of
    work the profile asked for.
    """
    if failure is not None or answer is None:
        outcome = OUTCOME_TIMEOUT if failure == OUTCOME_TIMEOUT else OUTCOME_TRANSPORT
        return Classification(outcome, 0, None, None, None, None, None, None, None)

    identity = _identity(answer.body)
    adapter_kind = _safe_token(identity.get(EXTENSION_ADAPTER_KIND))
    model_ref = _safe_token(identity.get(EXTENSION_MODEL_REF))
    body = answer.body if isinstance(answer.body, dict) else {}
    status = answer.status

    details = body.get("details")
    condition = (
        _safe_token(details.get(ERROR_CONDITION_ID))
        if isinstance(details, dict)
        else None
    )

    def refused(
        outcome: str,
        error_code: str | None = None,
        error_condition: str | None = None,
    ) -> Classification:
        return Classification(
            outcome,
            status,
            error_code,
            error_condition,
            None,
            None,
            None,
            adapter_kind,
            model_ref,
        )

    if adapter_kind is not None and adapter_kind != profile.required_adapter_kind:
        return refused(OUTCOME_IDENTITY)
    if latency_ms > profile.request_timeout_ms:
        return refused(OUTCOME_TIMEOUT)
    if status != profile.required_status:
        return refused(OUTCOME_HTTP_ERROR, _safe_token(body.get("code")), condition)
    choices = body.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    usage = body.get("usage")
    input_tokens = (
        _count(usage.get("prompt_tokens")) if isinstance(usage, dict) else None
    )
    output_tokens = (
        _count(usage.get("completion_tokens")) if isinstance(usage, dict) else None
    )
    valid = (
        adapter_kind == profile.required_adapter_kind
        and model_ref == profile.required_model_ref
        and isinstance(first, dict)
        and (
            not profile.require_usage
            or (input_tokens is not None and output_tokens is not None)
        )
    )
    if not valid or not isinstance(first, dict):
        return refused(OUTCOME_INVALID)
    return Classification(
        OUTCOME_SUCCESS,
        status,
        None,
        None,
        _safe_token(first.get("finish_reason")),
        input_tokens,
        output_tokens,
        adapter_kind,
        model_ref,
    )


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RequestRecord:
    """One dispatched request, as it is written to the raw record set."""

    sequence: int
    phase: str
    level_id: str
    concurrency: int
    worker: int
    dispatch_offset_ms: int
    latency_ms: int
    outcome: str
    status: int
    error_code: str | None
    error_condition: str | None
    finish_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    adapter_kind: str | None
    model_ref: str | None

    def document(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "phase": self.phase,
            "levelId": self.level_id,
            "concurrency": self.concurrency,
            "worker": self.worker,
            "dispatchOffsetMs": self.dispatch_offset_ms,
            "latencyMs": self.latency_ms,
            "outcome": self.outcome,
            "status": self.status,
            "errorCode": self.error_code,
            "errorCondition": self.error_condition,
            "finishReason": self.finish_reason,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "adapterKind": self.adapter_kind,
            "modelRef": self.model_ref,
        }


@dataclass(frozen=True, slots=True)
class PhaseRecord:
    """One warm-up or level: how it was bounded, how long it ran, and why it stopped."""

    phase: str
    level_id: str
    concurrency: int
    request_ceiling: int
    duration_seconds: int | None
    started_offset_ms: int
    window_ms: int
    dispatched: int
    stop_reason: str

    def document(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "levelId": self.level_id,
            "concurrency": self.concurrency,
            "requestCeiling": self.request_ceiling,
            "durationSeconds": self.duration_seconds,
            "startedOffsetMs": self.started_offset_ms,
            "windowMs": self.window_ms,
            "dispatched": self.dispatched,
            "stopReason": self.stop_reason,
        }


@dataclass(frozen=True, slots=True)
class LoadRun:
    """Everything one run produced, in the shape the raw record set is written in."""

    header: Mapping[str, Any]
    phases: tuple[PhaseRecord, ...]
    records: tuple[RequestRecord, ...]
    end_state: str
    end_reason: str | None
    elapsed_ms: int
    completed_at: str


# --------------------------------------------------------------------------
# The bounded closed loop
# --------------------------------------------------------------------------


class StopSignal:
    """A run-wide stop request that remembers the first reason it was given."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reason: str | None = None

    def request(self, reason: str) -> None:
        with self._lock:
            if self._reason is None:
                self._reason = reason

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason


def _millis(seconds: float) -> int:
    return max(0, round(seconds * 1000))


def send_one(
    profile: Profile,
    base_url: str,
    *,
    run_id: str,
    sequence: int,
    phase: str,
    level_id: str,
    concurrency: int,
    worker: int,
    dispatch_offset_ms: int,
    transport: Transport,
    clock: Callable[[], float],
) -> RequestRecord:
    """Send the fixture once and keep only the classification of what came back."""
    headers = {
        REQUEST_ID_HEADER: f"{run_id}-{sequence:05d}",
        CORRELATION_ID_HEADER: run_id,
    }
    started = clock()
    answer: HttpAnswer | None = None
    failure: str | None = None
    try:
        answer = transport(
            "POST",
            f"{base_url}{profile.fixture.request_path}",
            profile.fixture.body(),
            headers,
            profile.request_timeout_ms / 1000,
        )
    except TransportTimeout:
        failure = OUTCOME_TIMEOUT
    except TransportFailure:
        failure = OUTCOME_TRANSPORT
    latency_ms = _millis(clock() - started)
    result = classify(profile, answer=answer, failure=failure, latency_ms=latency_ms)
    return RequestRecord(
        sequence=sequence,
        phase=phase,
        level_id=level_id,
        concurrency=concurrency,
        worker=worker,
        dispatch_offset_ms=dispatch_offset_ms,
        latency_ms=latency_ms,
        outcome=result.outcome,
        status=result.status,
        error_code=result.error_code,
        error_condition=result.error_condition,
        finish_reason=result.finish_reason,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        adapter_kind=result.adapter_kind,
        model_ref=result.model_ref,
    )


#: How often the waiting thread wakes to let an interrupt through. A blocking wait on
#: a future cannot be interrupted on every platform; a short poll can.
WAIT_POLL_SECONDS = 0.25


def run_phase(
    profile: Profile,
    base_url: str,
    *,
    run_id: str,
    phase: str,
    level_id: str,
    concurrency: int,
    request_ceiling: int,
    duration_seconds: int | None,
    first_sequence: int,
    run_started: float,
    stop: StopSignal,
    transport: Transport,
    clock: Callable[[], float],
) -> tuple[PhaseRecord, tuple[RequestRecord, ...]]:
    """Run one closed-loop phase and return every request it dispatched.

    Sequence numbers are claimed under one lock, together with the check of every
    stop condition, so a phase never dispatches past its ceiling and never assigns a
    number twice. A dispatched request is always allowed to finish: it is bounded by
    the client deadline, and a request that was sent and then left out of the record
    is exactly the accounting gap this module exists to prevent.
    """
    lock = threading.Lock()
    records: list[RequestRecord] = []
    state: dict[str, Any] = {
        "next": first_sequence,
        "dispatched": 0,
        "last": 0.0,
        "reason": None,
        "transportStreak": 0,
    }
    started = clock()

    def stop_with(reason: str) -> None:
        if state["reason"] is None:
            state["reason"] = reason

    def worker(index: int) -> None:
        try:
            while True:
                with lock:
                    run_reason = stop.reason
                    elapsed = clock() - started
                    if run_reason is not None:
                        stop_with(run_reason)
                        return
                    if state["dispatched"] >= request_ceiling:
                        stop_with(STOP_CEILING)
                        return
                    if duration_seconds is not None and elapsed >= duration_seconds:
                        stop_with(STOP_DURATION)
                        return
                    sequence = state["next"]
                    state["next"] += 1
                    state["dispatched"] += 1
                    offset_ms = _millis(elapsed)
                record = send_one(
                    profile,
                    base_url,
                    run_id=run_id,
                    sequence=sequence,
                    phase=phase,
                    level_id=level_id,
                    concurrency=concurrency,
                    worker=index,
                    dispatch_offset_ms=offset_ms,
                    transport=transport,
                    clock=clock,
                )
                with lock:
                    records.append(record)
                    state["last"] = max(state["last"], clock() - started)
                    if record.outcome == OUTCOME_TRANSPORT:
                        state["transportStreak"] += 1
                    else:
                        state["transportStreak"] = 0
                    transport_lost = (
                        state["transportStreak"] >= MAXIMUM_CONSECUTIVE_TRANSPORT_ERRORS
                    )
                if record.outcome == OUTCOME_IDENTITY:
                    stop.request(STOP_ABORTED)
                if transport_lost:
                    stop.request(STOP_TRANSPORT_LOST)
        except BaseException:
            stop.request(STOP_ABORTED)
            raise

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=concurrency, thread_name_prefix="inferops-load"
    ) as executor:
        futures = [executor.submit(worker, index) for index in range(concurrency)]
        pending = set(futures)
        while pending:
            try:
                _, pending = concurrent.futures.wait(pending, timeout=WAIT_POLL_SECONDS)
            except KeyboardInterrupt:
                stop.request(STOP_INTERRUPTED)
        for future in futures:
            future.result()

    ordered = tuple(sorted(records, key=lambda record: record.sequence))
    if len(ordered) != state["dispatched"]:
        raise LoadError("a load phase dispatched a request it did not record")
    reason = state["reason"] or stop.reason or STOP_CEILING
    return (
        PhaseRecord(
            phase=phase,
            level_id=level_id,
            concurrency=concurrency,
            request_ceiling=request_ceiling,
            duration_seconds=duration_seconds,
            started_offset_ms=_millis(started - run_started),
            window_ms=_millis(state["last"]),
            dispatched=state["dispatched"],
            stop_reason=reason,
        ),
        ordered,
    )


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_header(
    profile: Profile,
    *,
    run_id: str,
    started_at: str,
    mode: str,
    host: HostRecord,
    facts: EnvironmentFacts | None,
    served: ServedIdentity,
) -> dict[str, Any]:
    """The run header: what was sent, where, to what, and how each fact is known."""
    evidence_class = EVIDENCE_REAL if mode == MODE_REAL else EVIDENCE_SYNTHETIC
    return {
        "schemaVersion": EXPECTED_SCHEMA,
        "runId": run_id,
        "startedAt": started_at,
        "mode": mode,
        "evidenceClass": evidence_class,
        "evidenceLabel": LABEL_REAL if mode == MODE_REAL else LABEL_SYNTHETIC,
        "certificationCeiling": CEILING_FOR_CLASS[evidence_class],
        "productionBenchmark": False,
        "portableCapacityClaim": False,
        "boundary": BOUNDARY_STATEMENT,
        "profile": {
            "profileId": profile.profile_id,
            "profileVersion": profile.profile_version,
            "profileSha256": profile.profile_sha256,
            "fixtureId": profile.fixture.fixture_id,
            "requestPath": profile.fixture.request_path,
            "model": profile.fixture.model,
            "stream": profile.fixture.stream,
            "messageCount": len(profile.fixture.messages),
        },
        "generation": {
            "maxOutputTokens": profile.max_output_tokens,
            "temperature": profile.temperature,
            "contextSizeTokens": profile.context_size_tokens,
            "parallelSlots": profile.parallel_slots,
        },
        "execution": {
            "warmupRequests": profile.warmup_requests,
            "warmupConcurrency": profile.warmup_concurrency,
            "levels": [
                {"levelId": level.level_id, "concurrency": level.concurrency}
                for level in profile.levels
            ],
            "durationSeconds": profile.duration_seconds,
            "maxRequestsPerLevel": profile.max_requests_per_level,
            "requestTimeoutMs": profile.request_timeout_ms,
        },
        "success": {
            "requiredStatus": profile.required_status,
            "requiredAdapterKind": profile.required_adapter_kind,
            "requiredModelRef": profile.required_model_ref,
            "requiredRuntimeName": profile.required_runtime_name,
            "requireUsage": profile.require_usage,
        },
        "percentileMethod": profile.percentile_method,
        "reportedPercentiles": list(profile.reported_percentiles),
        "environment": {
            "target": {
                "kind": "loopback-forward" if mode == MODE_REAL else "in-process-stub",
                "host": profile.target_host,
            },
            "generatorHost": host.document(),
            "facts": None if facts is None else facts.document(),
            "served": served.document(),
            "provenance": {
                "checkedAgainstRepository": (
                    list(FACTS_CHECKED_AGAINST_REPOSITORY) if facts else []
                ),
                "declaredOnly": list(FACTS_DECLARED_ONLY) if facts else [],
                "reportedByApi": list(IDENTITY_REPORTED_BY_API),
            },
        },
    }


def execute(
    profile: Profile,
    *,
    base_url: str,
    mode: str,
    confirmed: bool,
    facts: EnvironmentFacts | None,
    transport: Transport = http_transport,
    clock: Callable[[], float] = time.perf_counter,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    epoch_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
    host: HostRecord | None = None,
) -> LoadRun:
    """Verify the target, run the warm-up, then run every level in order.

    A real run requires confirmation and environment facts; a rehearsal forbids facts,
    because a synthetic record carrying a provider would be one step from being read
    as a run on that provider.

    ``startedAtEpochMs`` is the wall-clock millisecond read beside the performance
    counter that every phase and request offset is measured from. ``startedAt`` is
    truncated to the second, which is too coarse to place a phase against samples
    taken outside this process, such as a cluster's resource counters.
    """
    if mode == MODE_REAL:
        if not confirmed:
            raise LoadRefused("a real load run requires --confirm-real-load")
        if facts is None:
            raise LoadRefused("a real load run requires --environment-facts")
    elif mode == MODE_REHEARSAL:
        if facts is not None:
            raise LoadRefused("a rehearsal may not carry environment facts")
    else:
        raise LoadError("a load run is either real or a rehearsal")
    target = require_loopback_base_url(base_url, profile)
    served = probe_identity(profile, target, transport=transport)
    started_moment = now()
    run_id = f"load-{started_moment.astimezone(UTC):%Y%m%dT%H%M%SZ}"
    header = build_header(
        profile,
        run_id=run_id,
        started_at=_utc(started_moment),
        mode=mode,
        host=host if host is not None else capture_host(),
        facts=facts,
        served=served,
    )
    stop = StopSignal()
    run_started = clock()
    header["startedAtEpochMs"] = epoch_ms()
    phases: list[PhaseRecord] = []
    records: list[RequestRecord] = []
    end_state = END_COMPLETED
    end_reason: str | None = None

    warmup, warmup_records = run_phase(
        profile,
        target,
        run_id=run_id,
        phase=PHASE_WARMUP,
        level_id=WARMUP_LEVEL_ID,
        concurrency=profile.warmup_concurrency,
        request_ceiling=profile.warmup_requests,
        duration_seconds=None,
        first_sequence=0,
        run_started=run_started,
        stop=stop,
        transport=transport,
        clock=clock,
    )
    phases.append(warmup)
    records.extend(warmup_records)
    if stop.reason is None and any(
        record.outcome != OUTCOME_SUCCESS for record in warmup_records
    ):
        end_state = END_WARMUP_FAILED
        end_reason = "a warm-up request was not a success, so no level was run"
    else:
        for level in profile.levels:
            if stop.reason is not None:
                break
            phase, level_records = run_phase(
                profile,
                target,
                run_id=run_id,
                phase=PHASE_MEASURED,
                level_id=level.level_id,
                concurrency=level.concurrency,
                request_ceiling=profile.max_requests_per_level,
                duration_seconds=profile.duration_seconds,
                first_sequence=len(records),
                run_started=run_started,
                stop=stop,
                transport=transport,
                clock=clock,
            )
            phases.append(phase)
            records.extend(level_records)
    if stop.reason == STOP_ABORTED:
        end_state = END_ABORTED
        end_reason = (
            "an answer named an adapter other than the required one, or a worker "
            "failed; the run stopped and that answer is not counted as a success"
        )
    elif stop.reason == STOP_TRANSPORT_LOST:
        end_state = END_TRANSPORT_LOST
        end_reason = (
            f"{MAXIMUM_CONSECUTIVE_TRANSPORT_ERRORS} requests in a row failed before "
            "any answer; the target was lost, and the run stopped rather than record "
            "its own loss of the target as the platform's behaviour"
        )
    elif stop.reason == STOP_INTERRUPTED:
        end_state = END_INTERRUPTED
        end_reason = "the operator interrupted the run; dispatched requests finished"
    return LoadRun(
        header=header,
        phases=tuple(phases),
        records=tuple(records),
        end_state=end_state,
        end_reason=end_reason,
        elapsed_ms=_millis(clock() - run_started),
        completed_at=_utc(now()),
    )


# --------------------------------------------------------------------------
# Raw record set
# --------------------------------------------------------------------------


def _line(document: Mapping[str, Any]) -> str:
    return json.dumps(dict(document), separators=(",", ":"), sort_keys=True)


def raw_lines(run: LoadRun) -> list[str]:
    """The raw record set: a run header, each phase then its requests, an end record."""
    lines = [_line({"record": "run", **run.header})]
    for phase in run.phases:
        lines.append(_line({"record": "phase", **phase.document()}))
        lines.extend(
            _line({"record": "request", **record.document()})
            for record in run.records
            if record.phase == phase.phase and record.level_id == phase.level_id
        )
    lines.append(
        _line(
            {
                "record": "end",
                "state": run.end_state,
                "reason": run.end_reason,
                "elapsedMs": run.elapsed_ms,
                "completedAt": run.completed_at,
                "dispatched": len(run.records),
            }
        )
    )
    return lines


def result_directory(
    profile: Profile, *, mode: str = MODE_REAL, repo_root: Path = REPO_ROOT
) -> Path:
    """The workspace-scoped result directory, after refusing an unsafe path."""
    root = repo_root.resolve()
    if profile.result_directory != EXPECTED_RESULT_DIRECTORY:
        raise LoadError("the load result path is unsafe")
    relative = EXPECTED_RESULT_DIRECTORY / (
        MODE_REHEARSAL if mode == MODE_REHEARSAL else "real"
    )
    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink() or os.path.isjunction(candidate):
            raise LoadError("the load result path is unsafe")
    directory = root / relative
    if not directory.resolve().is_relative_to(root):
        raise LoadError("the load result path is unsafe")
    return directory


def _write(path: Path, text: str, what: str) -> None:
    try:
        path.write_text(text, encoding="utf-8", newline="\n")
    except OSError as error:
        raise LoadError(f"the load {what} could not be written") from error


def write_raw(profile: Profile, run: LoadRun, *, repo_root: Path = REPO_ROOT) -> Path:
    """Write the raw record set under the result directory for the run's mode."""
    mode = str(run.header["mode"])
    result_directory(profile, mode=mode, repo_root=repo_root).mkdir(
        parents=True, exist_ok=True
    )
    # Re-checked after `mkdir`, because the components it just created did not exist
    # to be inspected by the first check. This narrows the window rather than closing
    # it, the same way `tools.serving_baseline` does and for the same reason.
    path = result_directory(profile, mode=mode, repo_root=repo_root) / profile.raw_file
    _write(path, "\n".join(raw_lines(run)) + "\n", "raw record set")
    return path


def write_summary(
    profile: Profile,
    summary: Mapping[str, Any],
    *,
    mode: str,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Write the deterministic summary beside the raw record set it came from."""
    result_directory(profile, mode=mode, repo_root=repo_root).mkdir(
        parents=True, exist_ok=True
    )
    path = (
        result_directory(profile, mode=mode, repo_root=repo_root) / profile.summary_file
    )
    _write(path, render_summary(summary), "summary")
    return path


def render_summary(summary: Mapping[str, Any]) -> str:
    """A summary as the bytes it is written as."""
    return json.dumps(dict(summary), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True, slots=True)
class RawSet:
    """A raw record set after every accounting rule has been checked."""

    header: Mapping[str, Any]
    phases: tuple[PhaseRecord, ...]
    records: tuple[RequestRecord, ...]
    end: Mapping[str, Any]


def _optional_int(document: Mapping[str, Any], field: str) -> int | None:
    value = document.get(field)
    return None if value is None else _integer(value, field, minimum=0)


def _optional_token(document: Mapping[str, Any], field: str) -> str | None:
    value = document.get(field)
    if value is None:
        return None
    text = _string(value, field)
    if text != UNRECOGNIZED and SAFE_TOKEN.fullmatch(text) is None:
        raise LoadError(f"raw field '{field}' is not a plain token")
    return text


def _request(document: Mapping[str, Any]) -> RequestRecord:
    _require_keys(
        document,
        "request",
        {
            "record",
            "sequence",
            "phase",
            "levelId",
            "concurrency",
            "worker",
            "dispatchOffsetMs",
            "latencyMs",
            "outcome",
            "status",
            "errorCode",
            "errorCondition",
            "finishReason",
            "inputTokens",
            "outputTokens",
            "adapterKind",
            "modelRef",
        },
    )
    phase = _string(document.get("phase"), "phase")
    outcome = _string(document.get("outcome"), "outcome")
    if phase not in (PHASE_WARMUP, PHASE_MEASURED) or outcome not in OUTCOMES:
        raise LoadError("a raw request record has an unsupported phase or outcome")
    record = RequestRecord(
        sequence=_integer(document.get("sequence"), "sequence", minimum=0),
        phase=phase,
        level_id=_string(document.get("levelId"), "levelId"),
        concurrency=_integer(document.get("concurrency"), "concurrency"),
        worker=_integer(document.get("worker"), "worker", minimum=0),
        dispatch_offset_ms=_integer(
            document.get("dispatchOffsetMs"), "dispatchOffsetMs", minimum=0
        ),
        latency_ms=_integer(document.get("latencyMs"), "latencyMs", minimum=0),
        outcome=outcome,
        status=_integer(document.get("status"), "status", minimum=0),
        error_code=_optional_token(document, "errorCode"),
        error_condition=_optional_token(document, "errorCondition"),
        finish_reason=_optional_token(document, "finishReason"),
        input_tokens=_optional_int(document, "inputTokens"),
        output_tokens=_optional_int(document, "outputTokens"),
        adapter_kind=_optional_token(document, "adapterKind"),
        model_ref=_optional_token(document, "modelRef"),
    )
    if record.outcome != OUTCOME_SUCCESS and (
        record.input_tokens is not None or record.output_tokens is not None
    ):
        raise LoadError("a raw request record counts tokens for a request that failed")
    if record.worker >= record.concurrency:
        raise LoadError("a raw request record names a worker its phase did not have")
    return record


def _phase(document: Mapping[str, Any]) -> PhaseRecord:
    _require_keys(
        document,
        "phase",
        {
            "record",
            "phase",
            "levelId",
            "concurrency",
            "requestCeiling",
            "durationSeconds",
            "startedOffsetMs",
            "windowMs",
            "dispatched",
            "stopReason",
        },
    )
    phase = _string(document.get("phase"), "phase")
    reason = _string(document.get("stopReason"), "stopReason")
    if phase not in (PHASE_WARMUP, PHASE_MEASURED) or reason not in STOP_REASONS:
        raise LoadError("a raw phase record has an unsupported phase or stop reason")
    duration = document.get("durationSeconds")
    return PhaseRecord(
        phase=phase,
        level_id=_string(document.get("levelId"), "levelId"),
        concurrency=_integer(document.get("concurrency"), "concurrency"),
        request_ceiling=_integer(document.get("requestCeiling"), "requestCeiling"),
        duration_seconds=(
            None if duration is None else _integer(duration, "durationSeconds")
        ),
        started_offset_ms=_integer(
            document.get("startedOffsetMs"), "startedOffsetMs", minimum=0
        ),
        window_ms=_integer(document.get("windowMs"), "windowMs", minimum=0),
        dispatched=_integer(document.get("dispatched"), "dispatched", minimum=0),
        stop_reason=reason,
    )


def _check_header(header: Mapping[str, Any], repo_root: Path) -> None:
    if (
        header.get("productionBenchmark") is not False
        or header.get("portableCapacityClaim") is not False
    ):
        raise LoadError(
            "a raw load record set may not claim a benchmark or a portable capacity"
        )
    if header.get("schemaVersion") != EXPECTED_SCHEMA:
        raise LoadError("a raw load record set has an unsupported schema")
    mode = header.get("mode")
    evidence_class = header.get("evidenceClass")
    environment = _object(header.get("environment"), "environment")
    facts = environment.get("facts")
    if mode == MODE_REAL:
        if evidence_class != EVIDENCE_REAL or header.get("evidenceLabel") != LABEL_REAL:
            raise LoadError("a real raw record set carries the wrong evidence class")
        provider = _object(facts, "environment.facts").get("provider")
        if provider not in supported_providers(repo_root):
            raise LoadError("a real raw record set names no supported provider")
    elif mode == MODE_REHEARSAL:
        if (
            evidence_class != EVIDENCE_SYNTHETIC
            or header.get("evidenceLabel") != LABEL_SYNTHETIC
        ):
            raise LoadError("a rehearsal raw record set must be labelled synthetic")
        if facts is not None:
            raise LoadError("a rehearsal raw record set may not name a provider")
    else:
        raise LoadError("a raw load record set has an unsupported mode")
    if header.get("certificationCeiling") != CEILING_FOR_CLASS[str(evidence_class)]:
        raise LoadError("a raw load record set claims the wrong certification ceiling")
    if header.get("boundary") != BOUNDARY_STATEMENT:
        raise LoadError("a raw load record set dropped its boundary statement")
    _percentiles(header.get("reportedPercentiles"), "reportedPercentiles")
    # Optional, because record sets written before the field existed are committed
    # evidence and must still read. Present, it must be a plausible whole number.
    if "startedAtEpochMs" in header:
        _integer(header.get("startedAtEpochMs"), "startedAtEpochMs", minimum=1)
    if header.get("percentileMethod") != EXPECTED_PERCENTILE_METHOD:
        raise LoadError("a raw load record set uses an unsupported percentile method")


def parse_raw(text: str, *, repo_root: Path = REPO_ROOT) -> RawSet:
    """Parse a raw record set and refuse any accounting that does not balance."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 3 or len(lines) > MAXIMUM_RAW_RECORDS:
        raise LoadError("the raw load record set is too short or too large")
    documents: list[dict[str, Any]] = []
    for line in lines:
        try:
            documents.append(_object(json.loads(line), "record"))
        except json.JSONDecodeError as error:
            raise LoadError("a raw load record is not valid JSON") from error
    if documents[0].get("record") != "run" or documents[-1].get("record") != "end":
        raise LoadError("a raw load record set must start with run and end with end")
    header = {key: value for key, value in documents[0].items() if key != "record"}
    _check_header(header, repo_root)
    end = documents[-1]
    _require_keys(
        end,
        "end",
        {"record", "state", "reason", "elapsedMs", "completedAt", "dispatched"},
    )
    if end.get("state") not in END_STATES:
        raise LoadError("a raw load record set ends in an unsupported state")

    phases: list[PhaseRecord] = []
    records: list[RequestRecord] = []
    per_phase: list[int] = []
    for document in documents[1:-1]:
        kind = document.get("record")
        if kind == "phase":
            phases.append(_phase(document))
            per_phase.append(0)
        elif kind == "request":
            if not phases:
                raise LoadError("a raw request record precedes every phase record")
            record = _request(document)
            current = phases[-1]
            if (
                record.phase != current.phase
                or record.level_id != current.level_id
                or record.concurrency != current.concurrency
            ):
                raise LoadError("a raw request record is not under its own phase")
            records.append(record)
            per_phase[-1] += 1
        else:
            raise LoadError("a raw load record has an unsupported kind")

    if not phases or phases[0].phase != PHASE_WARMUP:
        raise LoadError("a raw load record set must begin with its warm-up")
    if any(phase.phase != PHASE_MEASURED for phase in phases[1:]):
        raise LoadError("a raw load record set has more than one warm-up")
    for phase, counted in zip(phases, per_phase, strict=True):
        if phase.dispatched != counted:
            raise LoadError(
                f"phase '{phase.level_id}' says it dispatched {phase.dispatched} "
                f"requests and records {counted}"
            )
        if counted > phase.request_ceiling:
            raise LoadError(f"phase '{phase.level_id}' dispatched past its ceiling")
    if [record.sequence for record in records] != list(range(len(records))):
        raise LoadError("the raw request sequence numbers have a gap or a repeat")
    if end.get("dispatched") != len(records):
        raise LoadError("the raw end record disagrees with the requests recorded")
    return RawSet(header=header, phases=tuple(phases), records=tuple(records), end=end)


def read_raw(path: Path, *, repo_root: Path = REPO_ROOT) -> RawSet:
    """Read a raw record set from a file and check its accounting."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise LoadError("the raw load record set is unreadable") from error
    return parse_raw(text, repo_root=repo_root)


# --------------------------------------------------------------------------
# The deterministic summary
# --------------------------------------------------------------------------


def percentile_ms(latencies: Sequence[int], percentile: int) -> int:
    """The nearest-rank percentile of a latency sample, in whole milliseconds.

    The same rule `tools.serving_baseline` publishes: the value at rank
    ``ceil(percentile * n / 100)`` of the sorted sample, so the figure returned is a
    latency some request actually produced rather than an interpolation between two.
    """
    if not 1 <= percentile <= 99:
        raise LoadError("a reported percentile must be between 1 and 99")
    if not latencies:
        raise LoadError("a percentile needs at least one observation")
    ordered = sorted(latencies)
    rank = -((-percentile * len(ordered)) // 100)
    return ordered[rank - 1]


def _phase_summary(
    phase: PhaseRecord,
    records: Sequence[RequestRecord],
    percentiles: Sequence[int],
) -> dict[str, Any]:
    successes = [record for record in records if record.outcome == OUTCOME_SUCCESS]
    latencies = [record.latency_ms for record in successes]
    output_tokens = [
        record.output_tokens for record in successes if record.output_tokens is not None
    ]
    input_tokens = [
        record.input_tokens for record in successes if record.input_tokens is not None
    ]
    latency: dict[str, int | None] = {
        f"p{value}Ms": percentile_ms(latencies, value) if latencies else None
        for value in percentiles
    }
    latency["minMs"] = min(latencies) if latencies else None
    latency["maxMs"] = max(latencies) if latencies else None
    window = phase.window_ms
    return {
        "levelId": phase.level_id,
        "concurrency": phase.concurrency,
        "stopReason": phase.stop_reason,
        "requestCeiling": phase.request_ceiling,
        "durationSeconds": phase.duration_seconds,
        "dispatched": phase.dispatched,
        "outcomes": {
            outcome: sum(1 for record in records if record.outcome == outcome)
            for outcome in OUTCOMES
        },
        "httpStatuses": {
            str(status): sum(1 for record in records if record.status == status)
            for status in sorted({record.status for record in records if record.status})
        },
        "successful": len(successes),
        "unsuccessful": len(records) - len(successes),
        "windowMs": window,
        "latencyOfSuccesses": latency,
        "successfulRequestsPerSecondMilli": (
            (len(successes) * 1_000_000) // window if window > 0 else None
        ),
        "outputTokensPerSecondMilli": (
            (sum(output_tokens) * 1_000_000) // window
            if window > 0 and output_tokens
            else None
        ),
        "tokens": {
            "inputTotal": sum(input_tokens) if input_tokens else None,
            "outputTotal": sum(output_tokens) if output_tokens else None,
        },
    }


def summarize(raw: RawSet) -> dict[str, Any]:
    """Reduce a checked raw record set to its summary, with no clock and no I/O.

    Warm-up requests are counted and reported on their own and never reach a level.
    Latency percentiles are over successful requests only, and say so in the name of
    the member that holds them, because a percentile that mixed fast refusals with
    completions would read faster than any completion was. Rates are integers in
    thousandths per second over the phase window, because a float in a committed
    record differs between platforms. No member judges saturation.
    """
    header = raw.header
    percentiles = cast(list[int], header["reportedPercentiles"])
    by_phase = {
        (phase.phase, phase.level_id): [
            record
            for record in raw.records
            if record.phase == phase.phase and record.level_id == phase.level_id
        ]
        for phase in raw.phases
    }
    outcomes = {
        outcome: sum(1 for record in raw.records if record.outcome == outcome)
        for outcome in OUTCOMES
    }
    return {
        "schemaVersion": EXPECTED_SCHEMA,
        "runId": header["runId"],
        "mode": header["mode"],
        "evidenceClass": header["evidenceClass"],
        "evidenceLabel": header["evidenceLabel"],
        "certificationCeiling": header["certificationCeiling"],
        "productionBenchmark": False,
        "portableCapacityClaim": False,
        "boundary": BOUNDARY_STATEMENT,
        "profile": header["profile"],
        "environment": header["environment"],
        "percentileMethod": header["percentileMethod"],
        "end": {"state": raw.end["state"], "reason": raw.end["reason"]},
        "usable": raw.end["state"] == END_COMPLETED,
        "accounting": {
            "dispatched": len(raw.records),
            "outcomes": outcomes,
        },
        "warmup": _phase_summary(
            raw.phases[0], by_phase[(PHASE_WARMUP, WARMUP_LEVEL_ID)], percentiles
        ),
        "levels": [
            _phase_summary(phase, by_phase[(phase.phase, phase.level_id)], percentiles)
            for phase in raw.phases[1:]
        ],
    }


def run_to_raw(run: LoadRun, *, repo_root: Path = REPO_ROOT) -> RawSet:
    """Round-trip a run through its own raw lines, so a summary never skips a check."""
    return parse_raw("\n".join(raw_lines(run)) + "\n", repo_root=repo_root)
