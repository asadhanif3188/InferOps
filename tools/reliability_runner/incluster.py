"""Send one reliability caller workload from inside a cluster and write caller records.

This is the one file that a runner pod executes. It imports the standard library and
nothing else, so a pod needs an interpreter and this file. The host tool beside it
builds the plan that this file reads.

    python -I incluster.py PLAN_FILE

**What a run does.** The plan states one request, a number of workers, a deadline, a
success rule, a duration, and a request ceiling. Each worker sends the request, waits
for the answer, and sends it again. The run writes one line of JSON for each request
to standard output, between one header line and one end line.

**What a run reads.** The plan file, this file, and the answers of the target. It
reads no Kubernetes API, no readiness answer, no model list, and no state of a
delivery controller. It sends its first request when it starts, and it does not wait
for the target to be ready. So a caller record states what a caller saw, and no
platform signal decides it.

**What a record never holds.** The prompt text, the completion text, a response
header, an address, and the message of an error. A value that is read from an answer
is kept only when it is a short plain token, and a value that is not one is written
as ``unrecognized``.

**The exit status does not grade the answers.** Status 0 says that the run reached
its duration or its ceiling and wrote its end line. A run in which each request
failed exits 0. Status 3 says that the plan was refused and no request was sent.
Status 1 says that a stop signal ended the run before its duration.

The classification restates the rule of ``tools.llm_load.core.classify``, and the
transport restates ``tools.llm_load.core.http_transport``. The V1 module is not
imported, because it reads the chart and the runtime profile, and a pod holds neither.
``tests/serving/test_reliability_runner.py`` compares both with the V1 functions.
"""

from __future__ import annotations

import hashlib
import json
import re
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from http.client import HTTPException
from typing import Any, TextIO

PLAN_SCHEMA = "inferops.io/reliability-run-plan/v1alpha1"
PLAN_KIND = "ReliabilityRunPlan"
RECORD_SCHEMA = "inferops.io/reliability-caller-record/v1alpha1"

MODE_IN_CLUSTER = "in-cluster"
MODE_REHEARSAL = "rehearsal"
MODES = (MODE_IN_CLUSTER, MODE_REHEARSAL)

RECORD_HEADER = "header"
RECORD_REQUEST = "request"
RECORD_END = "end"

OUTCOME_SUCCESS = "success"
OUTCOME_HTTP_ERROR = "http-error"
OUTCOME_INVALID = "invalid-response"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_TRANSPORT = "transport-error"
OUTCOME_IDENTITY = "identity-refused"
#: The six outcome names of the V1 load harness, in its order.
OUTCOMES: tuple[str, ...] = (
    OUTCOME_SUCCESS,
    OUTCOME_HTTP_ERROR,
    OUTCOME_INVALID,
    OUTCOME_TIMEOUT,
    OUTCOME_TRANSPORT,
    OUTCOME_IDENTITY,
)

END_DURATION = "duration"
END_CEILING = "request-ceiling"
END_INTERRUPTED = "interrupted"
END_STATES = (END_DURATION, END_CEILING, END_INTERRUPTED)

RELEASE_DECLARED = "declared"
RELEASE_NOT_DECLARED = "not-declared"

EXIT_OK = 0
EXIT_INTERRUPTED = 1
EXIT_REFUSED = 3

MAXIMUM_CONCURRENCY = 8
MAXIMUM_DURATION_SECONDS = 3600
MAXIMUM_REQUEST_CEILING = 10_000
MAXIMUM_REQUEST_TIMEOUT_MS = 300_000
MAXIMUM_PAUSE_MS = 10_000
#: The V1 transport reads at most this many bytes of a response, and it does not
#: parse a longer one.
MAXIMUM_RESPONSE_BYTES = 1_000_000

SAFE_TOKEN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
UNRECOGNIZED = "unrecognized"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}")
DNS_LABEL = re.compile(r"[a-z]([a-z0-9-]{0,61}[a-z0-9])?")
SHA256 = re.compile(r"[0-9a-f]{64}")
HEADER_NAME = re.compile(r"[A-Za-z][A-Za-z0-9-]{0,63}")
REQUEST_PATH = re.compile(r"/[A-Za-z0-9/._-]{0,127}")

PLAN_MEMBERS: Mapping[str, frozenset[str]] = {
    "root": frozenset(
        {
            "schemaVersion",
            "kind",
            "mode",
            "experimentId",
            "runId",
            "boundary",
            "profile",
            "release",
            "target",
            "request",
            "caller",
            "timeouts",
            "success",
            "answerMembers",
            "bounds",
        }
    ),
    "profile": frozenset({"profileId", "profileRevision", "profileSha256"}),
    "release": frozenset({"releaseId", "source"}),
    "target": frozenset({"kind", "service", "namespace", "port", "baseUrl"}),
    "request": frozenset(
        {
            "method",
            "path",
            "contentType",
            "requestIdHeader",
            "correlationIdHeader",
            "body",
        }
    ),
    "caller": frozenset({"concurrency"}),
    "timeouts": frozenset({"requestTimeoutMs"}),
    "success": frozenset(
        {
            "requiredStatus",
            "requiredAdapterKind",
            "requiredModelRef",
            "requireUsage",
            "requireChoice",
        }
    ),
    "answerMembers": frozenset(
        {"extension", "adapterKind", "modelRef", "errorDetails", "errorConditionId"}
    ),
    "bounds": frozenset(
        {"durationSeconds", "requestCeiling", "pauseAfterNonSuccessMs"}
    ),
}


class PlanRefused(Exception):
    """The plan is not one that this runner executes."""


class TransportTimeout(Exception):
    """No answer arrived within the client deadline."""


class TransportFailure(Exception):
    """The connection failed before an answer arrived."""


#: ``(method, url, json_body, headers, timeout_seconds) -> (status, parsed_body)``.
#: The parsed body is ``None`` where the body is not JSON.
Transport = Callable[
    [str, str, Mapping[str, Any], Mapping[str, str], float], tuple[int, object | None]
]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_: Any, **__: Any) -> None:
        return None


#: No proxy from the environment and no redirect. A request goes to the Service that
#: the plan names, or it fails.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _parse_body(data: bytes) -> object | None:
    if len(data) > MAXIMUM_RESPONSE_BYTES:
        return None
    try:
        parsed: object = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError):
        return None
    return parsed


def http_transport(
    method: str,
    url: str,
    body: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> tuple[int, object | None]:
    """Send one request over plain HTTP on a new connection, with no retry."""
    request = urllib.request.Request(
        url, data=json.dumps(dict(body)).encode("utf-8"), method=method
    )
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        with _OPENER.open(request, timeout=timeout_seconds) as response:
            data = response.read(MAXIMUM_RESPONSE_BYTES + 1)
            return int(response.status), _parse_body(data)
    except urllib.error.HTTPError as error:
        try:
            data = error.read(MAXIMUM_RESPONSE_BYTES + 1)
        except (OSError, HTTPException):
            data = b""
        return int(error.code), _parse_body(data)
    except TimeoutError as error:
        raise TransportTimeout() from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise TransportTimeout() from error
        raise TransportFailure() from error
    except (OSError, HTTPException) as error:
        raise TransportFailure() from error


# --------------------------------------------------------------------------
# The plan
# --------------------------------------------------------------------------


def _section(plan: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = plan.get(name)
    if not isinstance(value, dict):
        raise PlanRefused(f"member '{name}' must be an object")
    if set(value) != PLAN_MEMBERS[name]:
        raise PlanRefused(f"member '{name}' has missing or unsupported members")
    return value


def _text(value: object, field: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise PlanRefused(f"member '{field}' is not a supported value")
    return value


def _whole(value: object, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PlanRefused(f"member '{field}' must be an integer")
    if not minimum <= value <= maximum:
        raise PlanRefused(f"member '{field}' must be from {minimum} to {maximum}")
    return value


def _flag(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise PlanRefused(f"member '{field}' must be a boolean")
    return value


def service_base_url(service: str, namespace: str, port: int) -> str:
    """The base URL of a Service by its cluster DNS name.

    The name has the Service, the namespace, and ``svc``. A pod address, a loopback
    address, and a name of another shape cannot be written in this form.
    """
    return f"http://{service}.{namespace}.svc:{port}"


def check_plan(plan: object) -> Mapping[str, Any]:
    """Refuse a plan that this runner does not execute, and return an accepted one."""
    if not isinstance(plan, dict):
        raise PlanRefused("the plan must be an object")
    if set(plan) != PLAN_MEMBERS["root"]:
        raise PlanRefused("the plan has missing or unsupported members")
    if plan["schemaVersion"] != PLAN_SCHEMA or plan["kind"] != PLAN_KIND:
        raise PlanRefused("the schema version or the kind is not supported")
    if plan["mode"] not in MODES:
        raise PlanRefused("member 'mode' is not a supported value")
    _text(plan["experimentId"], "experimentId", IDENTIFIER)
    _text(plan["runId"], "runId", IDENTIFIER)
    if not isinstance(plan["boundary"], str) or not plan["boundary"]:
        raise PlanRefused("member 'boundary' must be a non-empty string")

    profile = _section(plan, "profile")
    _text(profile["profileId"], "profile.profileId", IDENTIFIER)
    _whole(profile["profileRevision"], "profile.profileRevision", 1, 1_000_000)
    _text(profile["profileSha256"], "profile.profileSha256", SHA256)

    release = _section(plan, "release")
    if release["source"] == RELEASE_DECLARED:
        _text(release["releaseId"], "release.releaseId", SHA256)
    elif release["source"] != RELEASE_NOT_DECLARED or release["releaseId"] is not None:
        raise PlanRefused(
            "member 'release' must declare a release identifier, or state that "
            "none is declared"
        )

    target = _section(plan, "target")
    service = _text(target["service"], "target.service", DNS_LABEL)
    namespace = _text(target["namespace"], "target.namespace", DNS_LABEL)
    port = _whole(target["port"], "target.port", 1, 65535)
    if target["kind"] != "api-service" or target["baseUrl"] != service_base_url(
        service, namespace, port
    ):
        raise PlanRefused(
            "the target must be the API Service by its cluster DNS name, and not a "
            "pod address, a loopback address, or another URL"
        )

    request = _section(plan, "request")
    if request["method"] != "POST" or request["contentType"] != "application/json":
        raise PlanRefused("the request must be a POST of application/json")
    _text(request["path"], "request.path", REQUEST_PATH)
    _text(request["requestIdHeader"], "request.requestIdHeader", HEADER_NAME)
    _text(request["correlationIdHeader"], "request.correlationIdHeader", HEADER_NAME)
    if not isinstance(request["body"], dict):
        raise PlanRefused("member 'request.body' must be an object")

    _whole(
        _section(plan, "caller")["concurrency"],
        "caller.concurrency",
        1,
        MAXIMUM_CONCURRENCY,
    )
    _whole(
        _section(plan, "timeouts")["requestTimeoutMs"],
        "timeouts.requestTimeoutMs",
        1,
        MAXIMUM_REQUEST_TIMEOUT_MS,
    )
    success = _section(plan, "success")
    _whole(success["requiredStatus"], "success.requiredStatus", 100, 599)
    _text(success["requiredAdapterKind"], "success.requiredAdapterKind", SAFE_TOKEN)
    _text(success["requiredModelRef"], "success.requiredModelRef", SAFE_TOKEN)
    _flag(success["requireUsage"], "success.requireUsage")
    if success["requireChoice"] is not True:
        raise PlanRefused("member 'success.requireChoice' must be true")
    for name, value in _section(plan, "answerMembers").items():
        if not isinstance(value, str) or not value:
            raise PlanRefused(f"member 'answerMembers.{name}' must be a string")
    bounds = _section(plan, "bounds")
    _whole(
        bounds["durationSeconds"], "bounds.durationSeconds", 1, MAXIMUM_DURATION_SECONDS
    )
    _whole(
        bounds["requestCeiling"], "bounds.requestCeiling", 1, MAXIMUM_REQUEST_CEILING
    )
    _whole(
        bounds["pauseAfterNonSuccessMs"],
        "bounds.pauseAfterNonSuccessMs",
        0,
        MAXIMUM_PAUSE_MS,
    )
    return plan


# --------------------------------------------------------------------------
# Classification: a pure function of what came back
# --------------------------------------------------------------------------


def _safe_token(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value if SAFE_TOKEN.fullmatch(value) else UNRECOGNIZED


def _count(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def classify(
    plan: Mapping[str, Any],
    *,
    status: int | None,
    body: object | None,
    failure: str | None,
    latency_ms: int,
) -> dict[str, Any]:
    """Decide the outcome of one request from what came back and from nothing else.

    The order is the order of the V1 classification:

    1. no answer within the deadline is ``timeout``, and a failed connection is
       ``transport-error``;
    2. an answer that names an adapter other than the required one is
       ``identity-refused``, at each status and at each latency;
    3. an answer that arrived after the deadline is ``timeout``;
    4. a status other than the required one is ``http-error``, with the canonical
       error code and the condition identifier, each kept only as a plain token;
    5. the required status with another model, no first choice, or no usage counts
       where the plan requires them is ``invalid-response``;
    6. each other answer is ``success``.

    A request with no answer has the HTTP status ``null``. The V1 record writes 0.
    """
    result: dict[str, Any] = {
        "outcome": OUTCOME_SUCCESS,
        "httpStatus": status,
        "errorCode": None,
        "errorCondition": None,
        "finishReason": None,
        "inputTokens": None,
        "outputTokens": None,
        "adapterKind": None,
        "modelRef": None,
    }
    if failure is not None or status is None:
        result["outcome"] = (
            OUTCOME_TIMEOUT if failure == OUTCOME_TIMEOUT else OUTCOME_TRANSPORT
        )
        result["httpStatus"] = None
        return result

    members = plan["answerMembers"]
    success = plan["success"]
    answer = body if isinstance(body, dict) else {}
    extension = answer.get(members["extension"])
    details = answer.get(members["errorDetails"])
    identity: Mapping[str, Any] = {}
    if isinstance(extension, dict):
        identity = extension
    elif isinstance(details, dict):
        identity = details
    adapter_kind = _safe_token(identity.get(members["adapterKind"]))
    model_ref = _safe_token(identity.get(members["modelRef"]))
    result["adapterKind"] = adapter_kind
    result["modelRef"] = model_ref

    if adapter_kind is not None and adapter_kind != success["requiredAdapterKind"]:
        result["outcome"] = OUTCOME_IDENTITY
        return result
    if latency_ms > plan["timeouts"]["requestTimeoutMs"]:
        result["outcome"] = OUTCOME_TIMEOUT
        return result
    if status != success["requiredStatus"]:
        result["outcome"] = OUTCOME_HTTP_ERROR
        result["errorCode"] = _safe_token(answer.get("code"))
        if isinstance(details, dict):
            result["errorCondition"] = _safe_token(
                details.get(members["errorConditionId"])
            )
        return result
    choices = answer.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    usage = answer.get("usage")
    input_tokens = (
        _count(usage.get("prompt_tokens")) if isinstance(usage, dict) else None
    )
    output_tokens = (
        _count(usage.get("completion_tokens")) if isinstance(usage, dict) else None
    )
    if (
        adapter_kind != success["requiredAdapterKind"]
        or model_ref != success["requiredModelRef"]
        or not isinstance(first, dict)
        or (success["requireUsage"] and (input_tokens is None or output_tokens is None))
    ):
        result["outcome"] = OUTCOME_INVALID
        return result
    result["finishReason"] = _safe_token(first.get("finish_reason"))
    result["inputTokens"] = input_tokens
    result["outputTokens"] = output_tokens
    return result


# --------------------------------------------------------------------------
# The bounded closed loop
# --------------------------------------------------------------------------


def utc_text(moment: datetime) -> str:
    """A UTC instant to one millisecond, in the one form a caller record uses."""
    moment = moment.astimezone(UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _line(document: Mapping[str, Any]) -> str:
    return json.dumps(document, separators=(",", ":"), sort_keys=True)


def _millis(seconds: float) -> int:
    return max(0, round(seconds * 1000))


#: How long a waiting thread sleeps between two looks at the stop reason.
POLL_SECONDS = 0.1


class Run:
    """One bounded run of a plan. ``stop`` may be called from a signal handler."""

    def __init__(
        self,
        plan: Mapping[str, Any],
        *,
        out: TextIO,
        runner_sha256: str,
        plan_sha256: str,
        transport: Transport | None = None,
        clock: Callable[[], float] = time.perf_counter,
        wall: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._plan = check_plan(plan)
        self._out = out
        self._runner_sha256 = runner_sha256
        self._plan_sha256 = plan_sha256
        self._transport = http_transport if transport is None else transport
        self._clock = clock
        self._wall = wall
        self._sleep = sleep
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._stop: str | None = None
        self._dispatched = 0
        self._counts = dict.fromkeys(OUTCOMES, 0)

    def stop(self, reason: str = END_INTERRUPTED) -> None:
        """Dispatch no further request. A request in flight still finishes."""
        if self._stop is None:
            self._stop = reason

    def _write(self, document: Mapping[str, Any]) -> None:
        with self._write_lock:
            self._out.write(_line(document) + "\n")
            self._out.flush()

    def _pause(self, seconds: float) -> None:
        """Wait, and return early when the run is told to stop."""
        waited = 0.0
        while waited < seconds and self._stop is None:
            step = min(POLL_SECONDS, seconds - waited)
            self._sleep(step)
            waited += step

    def _send(self, sequence: int, worker: int) -> str:
        plan = self._plan
        request = plan["request"]
        run_id = plan["runId"]
        request_id = f"{run_id}-{sequence:05d}"
        headers = {
            "Content-Type": request["contentType"],
            request["requestIdHeader"]: request_id,
            request["correlationIdHeader"]: run_id,
        }
        status: int | None = None
        body: object | None = None
        failure: str | None = None
        started_at = self._wall()
        started = self._clock()
        try:
            status, body = self._transport(
                request["method"],
                plan["target"]["baseUrl"] + request["path"],
                json.loads(json.dumps(request["body"])),
                headers,
                plan["timeouts"]["requestTimeoutMs"] / 1000,
            )
        except TransportTimeout:
            failure = OUTCOME_TIMEOUT
        except TransportFailure:
            failure = OUTCOME_TRANSPORT
        latency_ms = _millis(self._clock() - started)
        finished_at = self._wall()
        result = classify(
            plan, status=status, body=body, failure=failure, latency_ms=latency_ms
        )
        outcome: str = result["outcome"]
        with self._lock:
            self._counts[outcome] += 1
        self._write(
            {
                "record": RECORD_REQUEST,
                "sequence": sequence,
                "worker": worker,
                "requestId": request_id,
                "experimentId": plan["experimentId"],
                "runId": run_id,
                "releaseId": plan["release"]["releaseId"],
                "startedAt": utc_text(started_at),
                "finishedAt": utc_text(finished_at),
                "latencyMs": latency_ms,
                "success": outcome == OUTCOME_SUCCESS,
                **result,
            }
        )
        return outcome

    def _worker(self, index: int, started: float) -> None:
        bounds = self._plan["bounds"]
        try:
            while True:
                with self._lock:
                    if self._stop is not None:
                        return
                    if self._clock() - started >= bounds["durationSeconds"]:
                        self.stop(END_DURATION)
                        return
                    if self._dispatched >= bounds["requestCeiling"]:
                        self.stop(END_CEILING)
                        return
                    self._dispatched += 1
                    sequence = self._dispatched
                outcome = self._send(sequence, index)
                if outcome != OUTCOME_SUCCESS:
                    self._pause(bounds["pauseAfterNonSuccessMs"] / 1000)
        except BaseException:
            self.stop(END_INTERRUPTED)
            raise

    def execute(self) -> int:
        """Run the plan to its end, and return the exit status."""
        plan = self._plan
        started_at = self._wall()
        started = self._clock()
        self._write(
            {
                "record": RECORD_HEADER,
                "schemaVersion": RECORD_SCHEMA,
                "mode": plan["mode"],
                "experimentId": plan["experimentId"],
                "runId": plan["runId"],
                "boundary": plan["boundary"],
                "profile": plan["profile"],
                "release": plan["release"],
                "target": plan["target"],
                "concurrency": plan["caller"]["concurrency"],
                "requestTimeoutMs": plan["timeouts"]["requestTimeoutMs"],
                "success": plan["success"],
                "bounds": plan["bounds"],
                "planSha256": self._plan_sha256,
                "runnerSha256": self._runner_sha256,
                "promptText": False,
                "completionText": False,
                "startedAt": utc_text(started_at),
            }
        )
        threads = [
            threading.Thread(
                target=self._worker,
                args=(index, started),
                name=f"inferops-reliability-{index}",
                daemon=True,
            )
            for index in range(plan["caller"]["concurrency"])
        ]
        for thread in threads:
            thread.start()
        # A join with a timeout lets a signal handler run in this thread.
        for thread in threads:
            while thread.is_alive():
                thread.join(POLL_SECONDS)
        end_state = self._stop or END_INTERRUPTED
        self._write(
            {
                "record": RECORD_END,
                "experimentId": plan["experimentId"],
                "runId": plan["runId"],
                "endState": end_state,
                "dispatched": self._dispatched,
                "recorded": sum(self._counts.values()),
                "outcomes": dict(self._counts),
                "elapsedMs": _millis(self._clock() - started),
                "finishedAt": utc_text(self._wall()),
            }
        )
        return EXIT_INTERRUPTED if end_state == END_INTERRUPTED else EXIT_OK


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("REFUSED  usage: incluster.py PLAN_FILE", file=sys.stderr)
        return EXIT_REFUSED
    try:
        with open(arguments[0], "rb") as handle:
            plan_bytes = handle.read()
        with open(__file__, "rb") as handle:
            runner_bytes = handle.read()
        plan = json.loads(plan_bytes.decode("utf-8"))
        if isinstance(plan, dict) and plan.get("mode") != MODE_IN_CLUSTER:
            raise PlanRefused("this entry point executes an in-cluster plan only")
        run = Run(
            plan,
            out=sys.stdout,
            runner_sha256=_sha256(runner_bytes),
            plan_sha256=_sha256(plan_bytes),
        )
    except PlanRefused as error:
        print(f"REFUSED  {error}", file=sys.stderr)
        return EXIT_REFUSED
    except (OSError, UnicodeError, ValueError, RecursionError):
        print("REFUSED  the plan file is unreadable", file=sys.stderr)
        return EXIT_REFUSED
    signal.signal(signal.SIGTERM, lambda *_: run.stop())
    signal.signal(signal.SIGINT, lambda *_: run.stop())
    return run.execute()


if __name__ == "__main__":
    sys.exit(main())
