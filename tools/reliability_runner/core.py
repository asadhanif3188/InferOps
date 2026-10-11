"""Build the plan and the Job of a reliability run, and check the caller record.

The runner is one file, ``incluster.py``, that a pod executes. This module is the
host side. It does three things, and each reads committed files and its arguments
and nothing else:

1. :func:`build_plan` loads the RP-1 profile through ``tools.reliability_profile``
   and writes the values of one run into a plan: the request, the two workers, the
   deadline, the success rule, the target, and the bounds of the run.
2. :func:`build_manifest` writes one ConfigMap and one Job. The ConfigMap holds the
   plan and the runner file. The Job mounts both and runs the file. No image is
   built, and no image holds the runner.
3. :func:`read_record` checks a caller record, which is what a run wrote to its
   standard output, and refuses one that is not complete or not consistent.

**This module contacts no cluster and sends no request.** It writes text. A script
applies the manifest and reads the log of the pod.

**A release identifier in a plan is a declared value.** The runner does not read it
from an answer, because no answer of the API states one. A record states the source
as ``declared`` or as ``not-declared``.

**A caller record that this module accepts is a well-formed record.** Acceptance
says nothing about how many requests succeeded.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from inferops.api.surface import (
    ERROR_CONDITION_ID,
    ERROR_DETAILS,
    EXTENSION_ADAPTER_KIND,
    EXTENSION_MEMBER,
    EXTENSION_MODEL_REF,
)
from tools import reliability_profile
from tools.reliability_profile import ProfileError, ReliabilityProfile

from . import incluster
from .incluster import (
    END_CEILING,
    END_DURATION,
    END_STATES,
    MAXIMUM_REQUEST_CEILING,
    MODE_IN_CLUSTER,
    MODE_REHEARSAL,
    OUTCOME_HTTP_ERROR,
    OUTCOME_IDENTITY,
    OUTCOME_INVALID,
    OUTCOME_SUCCESS,
    OUTCOME_TIMEOUT,
    OUTCOME_TRANSPORT,
    OUTCOMES,
    PLAN_KIND,
    PLAN_SCHEMA,
    RECORD_END,
    RECORD_HEADER,
    RECORD_REQUEST,
    RECORD_SCHEMA,
    RELEASE_DECLARED,
    RELEASE_NOT_DECLARED,
    SAFE_TOKEN,
    SHA256,
    PlanRefused,
    TransportFailure,
    TransportTimeout,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_REF = "tools/reliability_runner/incluster.py"
RUNNER_PATH = REPO_ROOT / RUNNER_REF

#: The API Service of the release that the environment scripts install: its name,
#: its namespace, and its port. The suite holds the name and the port against the
#: committed render of the chart, and the namespace against the script library.
API_SERVICE = "inferops-inferops-llm"
RELEASE_NAMESPACE = "inferops-release"
API_SERVICE_PORT = 8090

#: How long a worker waits after a request that is not a success. A refused
#: connection and an error answer return in milliseconds, and a closed loop with no
#: wait would then send without a bound on its rate. The profile states no such
#: wait. It is a bound of this runner and not a retry: the next request is a new
#: request with its own record.
PAUSE_AFTER_NON_SUCCESS_MS = 1000

#: A run identifier is part of the name of the Job, so it is a lower-case DNS label
#: of at most 40 characters.
RUN_ID = re.compile(r"[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?")
EXPERIMENT_ID = re.compile(r"[A-Za-z0-9]([A-Za-z0-9._-]{0,61}[A-Za-z0-9])?")
IMAGE_BY_DIGEST = re.compile(r"[a-z0-9][a-z0-9._/:-]{0,199}@sha256:[0-9a-f]{64}")
PULL_POLICIES = ("Never", "IfNotPresent")

JOB_NAME_PREFIX = "inferops-reliability-"
RUNNER_NAME = "inferops-reliability-runner"
MOUNT_PATH = "/opt/inferops-reliability"
RUNNER_FILE = "incluster.py"
PLAN_FILE = "plan.json"
#: The uid and the gid that the pod security context of the chart sets.
RUN_AS = 65534
#: A finished Job and its pod are deleted after this time when no person deleted
#: them. The log of the pod is deleted with the pod.
TTL_AFTER_FINISHED_SECONDS = 3600
#: Time that the Job is given beyond the duration and one client deadline.
DEADLINE_MARGIN_SECONDS = 120
GRACE_MARGIN_SECONDS = 30

#: No latency and no run length of a record is above this. A run is at most
#: 3,600 seconds, and a request is given one client deadline.
MAXIMUM_RECORDED_MS = 10_000_000

TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", re.ASCII)

RULE_PROFILE = "runner-profile-refused"
RULE_IDENTIFIER = "runner-identifier-unsupported"
RULE_PLAN = "runner-plan-refused"
RULE_IMAGE = "runner-image-not-pinned"
RULE_UNREADABLE = "caller-record-unreadable"
RULE_HEADER = "caller-record-header-missing"
RULE_MEMBERS = "caller-record-members-unsupported"
RULE_PROFILE_UNREGISTERED = "caller-record-profile-unregistered"
RULE_PLAN_DIFFERS = "caller-record-plan-differs"
RULE_IDENTITY = "caller-record-identity-differs"
RULE_TIME = "caller-record-time-invalid"
RULE_OUTCOME = "caller-record-outcome-inconsistent"
RULE_SEQUENCE = "caller-record-sequence-gap"
RULE_END = "caller-record-end-missing"
RULE_COUNTS = "caller-record-counts-differ"
RULE_CONTENT = "caller-record-holds-content"

#: The four rules of a plan and a manifest, and the twelve rules of a caller record.
#: Each function stops at the first refusal.
RULES: tuple[str, ...] = (
    RULE_PROFILE,
    RULE_IDENTIFIER,
    RULE_PLAN,
    RULE_IMAGE,
    RULE_UNREADABLE,
    RULE_HEADER,
    RULE_MEMBERS,
    RULE_PROFILE_UNREGISTERED,
    RULE_PLAN_DIFFERS,
    RULE_IDENTITY,
    RULE_TIME,
    RULE_OUTCOME,
    RULE_SEQUENCE,
    RULE_END,
    RULE_COUNTS,
    RULE_CONTENT,
)


class RunnerError(RuntimeError):
    """A plan, a manifest, or a caller record was refused."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule


def lf_digest(data: bytes) -> str:
    """The SHA-256 of bytes with each CRLF replaced by LF."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def runner_source(path: Path = RUNNER_PATH) -> str:
    """The text of the runner file with LF line endings, as a pod receives it."""
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")


def runner_digest(path: Path = RUNNER_PATH) -> str:
    """The digest that a pod computes of the runner file it executes."""
    return hashlib.sha256(runner_source(path).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# The plan
# --------------------------------------------------------------------------


def build_plan(
    *,
    experiment_id: str,
    run_id: str,
    duration_seconds: int,
    request_ceiling: int = MAXIMUM_REQUEST_CEILING,
    release_id: str | None = None,
    service: str = API_SERVICE,
    namespace: str = RELEASE_NAMESPACE,
    port: int = API_SERVICE_PORT,
    mode: str = MODE_IN_CLUSTER,
    profile: ReliabilityProfile | None = None,
) -> dict[str, Any]:
    """The plan of one run of the committed RP-1 profile.

    The request, the concurrency, the deadline, and the success rule are the values
    of the profile, and no option of the command changes one. The arguments are the
    identity of the run, its bounds, and its target. ``profile`` and the three
    members of the target are arguments of this function for the suite. The command
    has no option for them, and :func:`build_manifest` and :func:`read_record`
    refuse a target that is not the registered API Service.
    """
    if profile is None:
        try:
            profile = reliability_profile.load_profile()
        except ProfileError as error:
            raise RunnerError(
                RULE_PROFILE, f"the reliability profile is refused: {error}"
            ) from error
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise RunnerError(
            RULE_IDENTIFIER,
            "the run identifier must be a lower-case DNS label of at most 40 "
            "characters",
        )
    if not isinstance(experiment_id, str) or not EXPERIMENT_ID.fullmatch(experiment_id):
        raise RunnerError(
            RULE_IDENTIFIER,
            "the experiment identifier must be letters, digits, '.', '_', and '-', "
            "at most 63 characters, and must start and end with a letter or a digit",
        )
    plan: dict[str, Any] = {
        "schemaVersion": PLAN_SCHEMA,
        "kind": PLAN_KIND,
        "mode": mode,
        "experimentId": experiment_id,
        "runId": run_id,
        "boundary": reliability_profile.BOUNDARY_STATEMENT,
        "profile": {
            "profileId": profile.profile_id,
            "profileRevision": profile.profile_revision,
            "profileSha256": profile.profile_sha256,
        },
        "release": {
            "releaseId": release_id,
            "source": RELEASE_NOT_DECLARED if release_id is None else RELEASE_DECLARED,
        },
        "target": {
            "kind": "api-service",
            "service": service,
            "namespace": namespace,
            "port": port,
            "baseUrl": incluster.service_base_url(service, namespace, port),
        },
        "request": {
            "method": profile.request_method,
            "path": profile.request_path,
            "contentType": profile.request_content_type,
            "requestIdHeader": profile.request_id_header,
            "correlationIdHeader": profile.correlation_id_header,
            "body": profile.body(),
        },
        "caller": {"concurrency": profile.concurrency},
        "timeouts": {"requestTimeoutMs": profile.request_timeout_ms},
        "success": {
            "requiredStatus": profile.required_status,
            "requiredAdapterKind": profile.required_adapter_kind,
            "requiredModelRef": profile.required_model_ref,
            "requireUsage": profile.require_usage,
            "requireChoice": True,
        },
        "answerMembers": {
            "extension": EXTENSION_MEMBER,
            "adapterKind": EXTENSION_ADAPTER_KIND,
            "modelRef": EXTENSION_MODEL_REF,
            "errorDetails": ERROR_DETAILS,
            "errorConditionId": ERROR_CONDITION_ID,
        },
        "bounds": {
            "durationSeconds": duration_seconds,
            "requestCeiling": request_ceiling,
            "pauseAfterNonSuccessMs": PAUSE_AFTER_NON_SUCCESS_MS,
        },
    }
    try:
        incluster.check_plan(plan)
    except PlanRefused as error:
        raise RunnerError(RULE_PLAN, str(error)) from error
    return plan


def registered_target() -> dict[str, Any]:
    """The one target of a run: the API Service of the release."""
    return {
        "kind": "api-service",
        "service": API_SERVICE,
        "namespace": RELEASE_NAMESPACE,
        "port": API_SERVICE_PORT,
        "baseUrl": incluster.service_base_url(
            API_SERVICE, RELEASE_NAMESPACE, API_SERVICE_PORT
        ),
    }


def plan_text(plan: Mapping[str, Any]) -> str:
    """The one text of a plan: sorted members, two spaces, LF, one final newline."""
    return json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def plan_digest(text: str) -> str:
    return lf_digest(text.encode("utf-8"))


# --------------------------------------------------------------------------
# The Job
# --------------------------------------------------------------------------


def job_name(run_id: str) -> str:
    return f"{JOB_NAME_PREFIX}{run_id}"


def run_labels(plan: Mapping[str, Any]) -> dict[str, str]:
    """The labels of each object of a run.

    They do not hold ``app.kubernetes.io/instance``, and the name is not the name of
    the chart. So no selector of the release selects the runner: not a Service, not
    a disruption budget, and not the network policies of the release.
    """
    return {
        "app.kubernetes.io/name": RUNNER_NAME,
        "app.kubernetes.io/component": "experiment-caller",
        "app.kubernetes.io/managed-by": RUNNER_NAME,
        "inferops.io/experiment-id": plan["experimentId"],
        "inferops.io/run-id": plan["runId"],
    }


def build_manifest(
    plan: Mapping[str, Any],
    *,
    image: str,
    image_pull_policy: str = "Never",
    runner_path: Path = RUNNER_PATH,
) -> dict[str, Any]:
    """One ConfigMap and one Job that run the plan once, as a ``v1`` List.

    The image is an interpreter and no more: it must hold Python 3.12, and it is
    named by digest. The API image of the release is one such image. The runner file
    is mounted from the ConfigMap, so the image is not rebuilt for a run.
    """
    try:
        incluster.check_plan(plan)
    except PlanRefused as error:
        raise RunnerError(RULE_PLAN, str(error)) from error
    if plan["mode"] != MODE_IN_CLUSTER:
        raise RunnerError(RULE_PLAN, "a Job runs an in-cluster plan only")
    if not _same(plan["target"], registered_target()):
        raise RunnerError(
            RULE_PLAN,
            "the target of the plan is not the registered API Service of the release",
        )
    if not RUN_ID.fullmatch(plan["runId"]) or not EXPERIMENT_ID.fullmatch(
        plan["experimentId"]
    ):
        raise RunnerError(
            RULE_IDENTIFIER, "the run or the experiment identifier is not usable"
        )
    if not isinstance(image, str) or not IMAGE_BY_DIGEST.fullmatch(image):
        raise RunnerError(
            RULE_IMAGE, "the image must be named by a sha256 digest and not by a tag"
        )
    if image_pull_policy not in PULL_POLICIES:
        raise RunnerError(
            RULE_IMAGE, "the image pull policy must be Never or IfNotPresent"
        )
    text = plan_text(plan)
    source = runner_source(runner_path)
    name = job_name(plan["runId"])
    namespace = plan["target"]["namespace"]
    labels = run_labels(plan)
    deadline_seconds = -(-plan["timeouts"]["requestTimeoutMs"] // 1000)
    metadata = {
        "name": name,
        "namespace": namespace,
        "labels": labels,
        "annotations": {
            "inferops.io/plan-sha256": plan_digest(text),
            "inferops.io/runner-sha256": hashlib.sha256(
                source.encode("utf-8")
            ).hexdigest(),
        },
    }
    config_map = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": metadata,
        "immutable": True,
        "data": {RUNNER_FILE: source, PLAN_FILE: text},
    }
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": metadata,
        "spec": {
            "completions": 1,
            "parallelism": 1,
            # A second pod would be a second run under one run identifier.
            "backoffLimit": 0,
            "activeDeadlineSeconds": plan["bounds"]["durationSeconds"]
            + deadline_seconds
            + DEADLINE_MARGIN_SECONDS,
            "ttlSecondsAfterFinished": TTL_AFTER_FINISHED_SECONDS,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    # The runner reads no Kubernetes API, so it holds no token.
                    "automountServiceAccountToken": False,
                    "enableServiceLinks": False,
                    # A request in flight at a stop signal is given its deadline.
                    "terminationGracePeriodSeconds": deadline_seconds
                    + GRACE_MARGIN_SECONDS,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": RUN_AS,
                        "runAsGroup": RUN_AS,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": "runner",
                            "image": image,
                            "imagePullPolicy": image_pull_policy,
                            "command": [
                                "python",
                                "-I",
                                "-u",
                                "-B",
                                f"{MOUNT_PATH}/{RUNNER_FILE}",
                                f"{MOUNT_PATH}/{PLAN_FILE}",
                            ],
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "64Mi"},
                                "limits": {"cpu": "250m", "memory": "128Mi"},
                            },
                            "volumeMounts": [
                                {
                                    "name": "run",
                                    "mountPath": MOUNT_PATH,
                                    "readOnly": True,
                                }
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "run",
                            "configMap": {"name": name, "defaultMode": 0o444},
                        }
                    ],
                },
            },
        },
    }
    return {"apiVersion": "v1", "kind": "List", "items": [config_map, job]}


def manifest_text(manifest: Mapping[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


# --------------------------------------------------------------------------
# The caller record
# --------------------------------------------------------------------------

_HEADER_MEMBERS = frozenset(
    {
        "record",
        "schemaVersion",
        "mode",
        "experimentId",
        "runId",
        "boundary",
        "profile",
        "release",
        "target",
        "concurrency",
        "requestTimeoutMs",
        "success",
        "bounds",
        "planSha256",
        "runnerSha256",
        "promptText",
        "completionText",
        "startedAt",
    }
)
_REQUEST_MEMBERS = frozenset(
    {
        "record",
        "sequence",
        "worker",
        "requestId",
        "experimentId",
        "runId",
        "releaseId",
        "startedAt",
        "finishedAt",
        "latencyMs",
        "success",
        "outcome",
        "httpStatus",
        "errorCode",
        "errorCondition",
        "finishReason",
        "inputTokens",
        "outputTokens",
        "adapterKind",
        "modelRef",
    }
)
_END_MEMBERS = frozenset(
    {
        "record",
        "experimentId",
        "runId",
        "endState",
        "dispatched",
        "recorded",
        "outcomes",
        "elapsedMs",
        "finishedAt",
    }
)
#: The members of a plan that a header repeats, and where the header holds each.
_HEADER_FROM_PLAN: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("mode", ("mode",)),
    ("experimentId", ("experimentId",)),
    ("runId", ("runId",)),
    ("boundary", ("boundary",)),
    ("profile", ("profile",)),
    ("release", ("release",)),
    ("target", ("target",)),
    ("concurrency", ("caller", "concurrency")),
    ("requestTimeoutMs", ("timeouts", "requestTimeoutMs")),
    ("success", ("success",)),
    ("bounds", ("bounds",)),
)


@dataclass(frozen=True, slots=True)
class CallerRecord:
    """One caller record that each rule accepted."""

    header: Mapping[str, Any]
    requests: tuple[Mapping[str, Any], ...]
    end: Mapping[str, Any]

    def summary(self) -> dict[str, Any]:
        """Counts and identity. It holds no rate, no percentile, and no verdict."""
        return {
            "experimentId": self.header["experimentId"],
            "runId": self.header["runId"],
            "mode": self.header["mode"],
            "profile": self.header["profile"],
            "release": self.header["release"],
            "target": self.header["target"]["baseUrl"],
            "runnerSha256": self.header["runnerSha256"],
            "runnerIsThisTree": self.header["runnerSha256"] == runner_digest(),
            "planSha256": self.header["planSha256"],
            "startedAt": self.header["startedAt"],
            "finishedAt": self.end["finishedAt"],
            "endState": self.end["endState"],
            "requests": len(self.requests),
            "outcomes": dict(self.end["outcomes"]),
        }


class _Repeated(ValueError):
    """One JSON object states one member twice."""


def _no_repeat(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for name, value in pairs:
        if name in document:
            raise _Repeated(name)
        document[name] = value
    return document


def _same(left: Any, right: Any) -> bool:
    """Whether two JSON values are equal in value and in type."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            _same(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same(a, b) for a, b in zip(left, right, strict=True)
        )
    return bool(left == right)


def _is_int(value: object, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _is_token(value: object) -> bool:
    return value is None or (
        isinstance(value, str) and SAFE_TOKEN.fullmatch(value) is not None
    )


def _instant(value: object, where: str) -> datetime:
    if not isinstance(value, str) or not TIME.fullmatch(value):
        raise RunnerError(RULE_TIME, f"{where} is not a UTC instant to one millisecond")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise RunnerError(RULE_TIME, f"{where} is not a calendar instant") from error


def _lines(text: str) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise RunnerError(RULE_UNREADABLE, f"line {number} is empty")
        try:
            loaded = json.loads(line, object_pairs_hook=_no_repeat)
        except (ValueError, RecursionError) as error:
            raise RunnerError(
                RULE_UNREADABLE,
                f"line {number} is not one JSON object with each member once",
            ) from error
        if not isinstance(loaded, dict) or not isinstance(loaded.get("record"), str):
            raise RunnerError(
                RULE_UNREADABLE, f"line {number} is not a caller record line"
            )
        documents.append(loaded)
    return documents


def _check_header(header: Mapping[str, Any]) -> None:
    if set(header) != _HEADER_MEMBERS:
        raise RunnerError(RULE_MEMBERS, "the header has missing or unsupported members")
    if header["schemaVersion"] != RECORD_SCHEMA:
        raise RunnerError(RULE_MEMBERS, "the schema version is not supported")
    if header["promptText"] is not False or header["completionText"] is not False:
        raise RunnerError(
            RULE_CONTENT,
            "the header must state that the record holds no prompt text and no "
            "completion text",
        )
    for name in ("planSha256", "runnerSha256"):
        if not isinstance(header[name], str) or not SHA256.fullmatch(header[name]):
            raise RunnerError(RULE_MEMBERS, f"header member '{name}' is not a digest")
    if not _same(header["target"], registered_target()):
        raise RunnerError(
            RULE_MEMBERS,
            "the header does not target the registered API Service of the release",
        )
    # The header repeats a plan. The runner's own rule for a plan is the rule for
    # the repeated members, so a header is checked as the plan it came from.
    plan = {
        "schemaVersion": PLAN_SCHEMA,
        "kind": PLAN_KIND,
        "caller": {"concurrency": header["concurrency"]},
        "timeouts": {"requestTimeoutMs": header["requestTimeoutMs"]},
        "answerMembers": {
            "extension": EXTENSION_MEMBER,
            "adapterKind": EXTENSION_ADAPTER_KIND,
            "modelRef": EXTENSION_MODEL_REF,
            "errorDetails": ERROR_DETAILS,
            "errorConditionId": ERROR_CONDITION_ID,
        },
        "request": {
            "method": "POST",
            "path": "/",
            "contentType": "application/json",
            "requestIdHeader": "X",
            "correlationIdHeader": "X",
            "body": {},
        },
        **{
            name: header[name]
            for name in (
                "mode",
                "experimentId",
                "runId",
                "boundary",
                "profile",
                "release",
                "target",
                "success",
                "bounds",
            )
        },
    }
    try:
        incluster.check_plan(plan)
    except PlanRefused as error:
        raise RunnerError(RULE_MEMBERS, f"the header is refused: {error}") from error
    profile = header["profile"]
    registered = reliability_profile.REGISTERED_REVISIONS.get(
        profile["profileRevision"]
    )
    if (
        profile["profileId"] != reliability_profile.PROFILE_ID
        or registered != profile["profileSha256"]
        or header["boundary"] != reliability_profile.BOUNDARY_STATEMENT
    ):
        raise RunnerError(
            RULE_PROFILE_UNREGISTERED,
            "the header names a profile, a revision, a content digest, or a "
            "boundary sentence that the profile tool does not register",
        )
    _instant(header["startedAt"], "the header's startedAt")


def _check_request(
    request: Mapping[str, Any], header: Mapping[str, Any], line: int
) -> None:
    where = f"line {line}"
    if set(request) != _REQUEST_MEMBERS:
        raise RunnerError(RULE_MEMBERS, f"{where} has missing or unsupported members")
    outcome = request["outcome"]
    status = request["httpStatus"]
    if (
        not _is_int(request["sequence"], 1)
        or not _is_int(request["worker"])
        or not _is_int(request["latencyMs"])
        or request["latencyMs"] > MAXIMUM_RECORDED_MS
        or not isinstance(request["success"], bool)
        or outcome not in OUTCOMES
        or not (status is None or (_is_int(status, 100) and status <= 599))
        or not all(
            request[name] is None or _is_int(request[name])
            for name in ("inputTokens", "outputTokens")
        )
        or not all(
            _is_token(request[name])
            for name in (
                "errorCode",
                "errorCondition",
                "finishReason",
                "adapterKind",
                "modelRef",
            )
        )
    ):
        raise RunnerError(
            RULE_MEMBERS,
            f"{where} holds a member of another type, or a text that is not a short "
            "plain token",
        )
    if (
        request["experimentId"] != header["experimentId"]
        or request["runId"] != header["runId"]
        or not _same(request["releaseId"], header["release"]["releaseId"])
        or request["requestId"] != f"{header['runId']}-{request['sequence']:05d}"
        or request["worker"] >= header["concurrency"]
    ):
        raise RunnerError(
            RULE_IDENTITY,
            f"{where} names another experiment, run, release, or request "
            "identifier than the header gives it, or a worker that the run does "
            "not have",
        )
    started = _instant(request["startedAt"], f"{where}: startedAt")
    finished = _instant(request["finishedAt"], f"{where}: finishedAt")
    if finished < started or started < _instant(header["startedAt"], "header"):
        raise RunnerError(
            RULE_TIME,
            f"{where} finishes before it starts, or starts before the run starts",
        )
    required = header["success"]["requiredStatus"]
    late = request["latencyMs"] > header["requestTimeoutMs"]
    adapter = request["adapterKind"]
    consistent = {
        OUTCOME_SUCCESS: status == required,
        OUTCOME_INVALID: status == required,
        OUTCOME_HTTP_ERROR: status is not None and status != required,
        OUTCOME_IDENTITY: status is not None
        and request["adapterKind"]
        not in (None, header["success"]["requiredAdapterKind"]),
        OUTCOME_TRANSPORT: status is None,
        # No answer, or an answer after the deadline.
        OUTCOME_TIMEOUT: status is None or late,
    }[outcome]
    kept_only_for = (
        (("errorCode", "errorCondition"), OUTCOME_HTTP_ERROR),
        (("finishReason", "inputTokens", "outputTokens"), OUTCOME_SUCCESS),
    )
    if (
        request["success"] is not (outcome == OUTCOME_SUCCESS)
        or not consistent
        # The classification reads the adapter first, and then the deadline.
        or (
            outcome != OUTCOME_IDENTITY
            and adapter not in (None, header["success"]["requiredAdapterKind"])
        )
        or (late and outcome not in (OUTCOME_TIMEOUT, OUTCOME_IDENTITY))
        or (status is None and (adapter is not None or request["modelRef"] is not None))
        or any(
            request[name] is not None
            for names, kept in kept_only_for
            if outcome != kept
            for name in names
        )
        or (
            outcome == OUTCOME_SUCCESS
            and (
                request["latencyMs"] > header["requestTimeoutMs"]
                or request["adapterKind"] != header["success"]["requiredAdapterKind"]
                or request["modelRef"] != header["success"]["requiredModelRef"]
                or (
                    header["success"]["requireUsage"]
                    and (
                        request["inputTokens"] is None
                        or request["outputTokens"] is None
                    )
                )
            )
        )
    ):
        raise RunnerError(
            RULE_OUTCOME,
            f"{where} states an outcome that its other members do not agree with",
        )


def read_record(text: str, *, plan: str | None = None) -> CallerRecord:
    """Check one caller record, and return it when each rule accepts it.

    ``plan`` is the text of the plan that the run was started with. When it is
    given, the header must name its digest and repeat its values.

    No rule searches the record for a prompt or a completion. The rules give each
    line an exact set of members. A text member holds a registered value, a
    pattern, or at most 64 characters of ``[a-z0-9._-]``. So a line cannot hold a
    text with a space, with an upper-case letter, or of more than 64 characters.
    """
    documents = _lines(text)
    if not documents or documents[0]["record"] != RECORD_HEADER:
        raise RunnerError(
            RULE_HEADER,
            "the first line is not a header. A log that lost its first lines is "
            "not a caller record",
        )
    header = documents[0]
    _check_header(header)
    if plan is not None:
        try:
            stated = json.loads(plan, object_pairs_hook=_no_repeat)
            incluster.check_plan(stated)
        except (ValueError, RecursionError, PlanRefused) as error:
            raise RunnerError(RULE_PLAN_DIFFERS, "the plan is not readable") from error
        if header["planSha256"] != plan_digest(plan) or any(
            not _same(header[name], _dig(stated, path))
            for name, path in _HEADER_FROM_PLAN
        ):
            raise RunnerError(
                RULE_PLAN_DIFFERS,
                "the header does not name the digest of the plan, or it does not "
                "repeat the values of the plan",
            )

    requests: list[Mapping[str, Any]] = []
    end: Mapping[str, Any] | None = None
    for number, document in enumerate(documents[1:], start=2):
        kind = document["record"]
        if kind == RECORD_HEADER:
            raise RunnerError(
                RULE_HEADER,
                f"line {number} is a second header. One record is one run of one pod",
            )
        if end is not None:
            raise RunnerError(RULE_END, f"line {number} is after the end line")
        if kind == RECORD_REQUEST:
            _check_request(document, header, number)
            requests.append(document)
        elif kind == RECORD_END:
            end = document
        else:
            raise RunnerError(
                RULE_MEMBERS, f"line {number} has an unsupported record kind"
            )

    sequences = sorted(request["sequence"] for request in requests)
    if sequences != list(range(1, len(requests) + 1)):
        raise RunnerError(
            RULE_SEQUENCE,
            "the sequence numbers are not each number from 1 to the number of "
            "request lines, once",
        )
    if end is None:
        raise RunnerError(
            RULE_END,
            "the record has no end line. A run that did not write one did not end "
            "in a state that it stated",
        )
    counted = {
        outcome: sum(1 for request in requests if request["outcome"] == outcome)
        for outcome in OUTCOMES
    }
    if (
        set(end) != _END_MEMBERS
        or end["endState"] not in END_STATES
        or not _is_int(end["elapsedMs"])
        or end["elapsedMs"] > MAXIMUM_RECORDED_MS
        or not _is_int(end["dispatched"])
        or not _is_int(end["recorded"])
        or not isinstance(end["outcomes"], dict)
    ):
        raise RunnerError(
            RULE_MEMBERS, "the end line has missing or unsupported members"
        )
    finished = _instant(end["finishedAt"], "the end line's finishedAt")
    if any(
        _instant(request["finishedAt"], "a request") > finished for request in requests
    ):
        raise RunnerError(RULE_TIME, "a request finishes after the run ends")
    if finished < _instant(header["startedAt"], "header"):
        raise RunnerError(RULE_TIME, "the run ends before it starts")
    if end["experimentId"] != header["experimentId"] or end["runId"] != header["runId"]:
        raise RunnerError(RULE_IDENTITY, "the end line names another experiment or run")
    if (
        end["dispatched"] != len(requests)
        or end["recorded"] != len(requests)
        or not _same(end["outcomes"], counted)
        or len(requests) > header["bounds"]["requestCeiling"]
        # A run that ends at a bound reached the bound.
        or (
            end["endState"] == END_CEILING
            and len(requests) != header["bounds"]["requestCeiling"]
        )
        or (
            end["endState"] == END_DURATION
            and end["elapsedMs"] < header["bounds"]["durationSeconds"] * 1000
        )
    ):
        raise RunnerError(
            RULE_COUNTS,
            "the end line's counts are not the counts of the request lines, the run "
            "dispatched more requests than its ceiling, or its end state names a "
            "bound that its counts did not reach",
        )

    return CallerRecord(header=header, requests=tuple(requests), end=end)


def _dig(document: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = document
    for name in path:
        value = value[name]
    return value


# --------------------------------------------------------------------------
# The rehearsal: the runner's own loop against scripted answers
# --------------------------------------------------------------------------

REHEARSAL_EXPERIMENT_ID = "rehearsal"
REHEARSAL_REQUESTS = 12
#: Text that a scripted answer holds where a completion holds its text. A caller
#: record of a rehearsal must not hold it.
REHEARSAL_COMPLETION_TEXT = "Synthetic completion text of a scripted answer."


def scripted_answers(plan: Mapping[str, Any]) -> list[tuple[str, int, object | None]]:
    """One scripted answer for each of the six outcomes, as (failure, status, body)."""
    members = plan["answerMembers"]
    success = plan["success"]

    def identity(adapter: str) -> dict[str, Any]:
        return {
            members["adapterKind"]: adapter,
            members["modelRef"]: success["requiredModelRef"],
        }

    completion = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": REHEARSAL_COMPLETION_TEXT},
            }
        ],
        "usage": {"prompt_tokens": 30, "completion_tokens": 40, "total_tokens": 70},
        members["extension"]: identity(success["requiredAdapterKind"]),
    }
    return [
        ("", 200, completion),
        (
            "",
            503,
            {
                "code": "adapter-unavailable",
                "message": "Synthetic error message of a scripted answer.",
                members["errorDetails"]: {
                    **identity(success["requiredAdapterKind"]),
                    members["errorConditionId"]: "runtime-unreachable",
                },
            },
        ),
        ("", 200, {**completion, "choices": []}),
        (OUTCOME_TIMEOUT, 0, None),
        (OUTCOME_TRANSPORT, 0, None),
        ("", 200, {**completion, members["extension"]: identity("mock")}),
    ]


def rehearse(run_id: str = "rehearsal-1") -> str:
    """Run the runner's loop against scripted answers, and return the caller record.

    No request is sent. The answer of each request is one of six scripted answers,
    chosen by the sequence number, so each outcome occurs twice. The wall clock is
    one real reading, and one millisecond more for each later reading. The wait
    after a request that is not a success is not slept. The latency clock is real,
    and the two workers are real threads: the first two answers wait for each
    other, so each worker sends at least one request. Two rehearsals give the same
    outcomes and not the same bytes.
    """
    plan = build_plan(
        experiment_id=REHEARSAL_EXPERIMENT_ID,
        run_id=run_id,
        duration_seconds=60,
        request_ceiling=REHEARSAL_REQUESTS,
        mode=MODE_REHEARSAL,
    )
    text = plan_text(plan)
    answers = scripted_answers(plan)
    header_name = plan["request"]["requestIdHeader"]
    lock = threading.Lock()
    both = threading.Barrier(2, timeout=10)
    base = datetime.now(UTC)
    ticks = [0]

    def transport(
        method: str,
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> tuple[int, object | None]:
        sequence = int(headers[header_name].rsplit("-", 1)[1])
        failure, status, answer = answers[(sequence - 1) % len(answers)]
        if sequence <= 2:
            # Two requests in flight at one time, one from each worker.
            with contextlib.suppress(threading.BrokenBarrierError):
                both.wait()
        if failure == OUTCOME_TIMEOUT:
            raise TransportTimeout()
        if failure == OUTCOME_TRANSPORT:
            raise TransportFailure()
        return status, answer

    def wall() -> datetime:
        # One millisecond for each reading, so no two instants of a rehearsal are
        # equal and none is a measurement.
        with lock:
            ticks[0] += 1
            return base + timedelta(milliseconds=ticks[0])

    out = io.StringIO()
    incluster.Run(
        plan,
        out=out,
        runner_sha256=runner_digest(),
        plan_sha256=plan_digest(text),
        transport=transport,
        wall=wall,
        sleep=lambda _: None,
    ).execute()
    return out.getvalue()


def record_from(path: Path, *, plan_path: Path | None = None) -> CallerRecord:
    """Read and check the caller record in a file."""
    try:
        text = path.read_text(encoding="utf-8")
        plan = None if plan_path is None else plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RunnerError(
            RULE_UNREADABLE, "the caller record or the plan is unreadable"
        ) from error
    return read_record(text, plan=plan)
