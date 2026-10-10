"""Load the RP-1 reliability caller profile and refuse one that drifted.

The committed profile at ``deploy/serving/reliability/rp-1-profile.v1.json`` states
what one caller request is, how many callers send it, and what counts as a success.
It reuses the fixture, the generation settings, the client deadline, and the success
rule of the V1 load profile at ``deploy/serving/load/llm-load-profile.v1.json``, and it
pins that file by content digest.

Loading reads committed files and nothing else. It sends no request, contacts no
cluster, and reads no model byte. The steps are, in this order:

1. The profile file is read with exact member sets. An unknown member is refused.
2. The V1 load profile is loaded by its own loader, which compares it with the
   runtime profile, the chart values, and the request parser of the API.
3. Each reused value of this profile is compared with the loaded V1 value.
4. Each member that the V1 file states is given one disposition: reused, pinned,
   changed, or not carried.
5. The content digest of the profile file is compared with the digest that this
   module registers for the profile's revision.

**The revision digest is a tripwire and not a lock.** A change that edits the profile
and the registered digest together passes this module. The digest makes such a change
visible in two files. It does not prevent it.

**What a profile is not.** A profile is not evidence. It states what a run sends. No
run executed under it in the change that added it, and no runner reads it yet.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from inferops.api.surface import (
    CHAT_COMPLETIONS_PATH,
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
)
from tools import llm_load
from tools.llm_load import core as source_core
from tools.model_acquisition import ModelAcquisitionError
from tools.runtime_configuration import RuntimeConfigurationError
from tools.runtime_packaging import RuntimePackagingError

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_REF = "deploy/serving/reliability/rp-1-profile.v1.json"
PROFILE_PATH = REPO_ROOT / PROFILE_REF
SOURCE_PROFILE_REF = "deploy/serving/load/llm-load-profile.v1.json"

EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_KIND = "ReliabilityCallerProfile"
PROFILE_ID = "RP-1"
WORKLOAD_CLASS = "reliability"
EVIDENCE_LEVEL_CEILING = "C2"
EXPECTED_BOUNDARIES_REF = "docs/architecture/project-boundaries.md"

#: The sentence the profile carries. It is a member and not a comment, so a profile
#: that is copied out of this repository still states it.
BOUNDARY_STATEMENT = (
    "RP-1 is a reliability workload: one fixed public request, sent by two "
    "closed-loop workers. It is not a representative production workload, an "
    "overload test, or a benchmark. Concurrency 2 is a fixed choice and not a "
    "measured threshold. No figure from a run under it is a portable capacity "
    "figure or a production SLO."
)

#: The concurrency of RP-1. It is a constant here and not a value that the profile
#: may choose. A different concurrency needs a new revision, a new registered digest,
#: and a change to this line.
CONCURRENCY = 2

CALLER_LOCATION = "in-cluster"
CALLER_LOOP = "closed"
TARGET_KIND = "api-service"
TARGET_SCHEME = "http"
REQUEST_METHOD = "POST"
REQUEST_CONTENT_TYPE = "application/json"

#: No committed record sets a sampling seed for the runtime. The profile says so.
SAMPLING_SEED = "not-set"

#: What the V1 transport does on each request. The suite holds each of these four
#: values against that transport. This module compares the profile with them.
CONNECTION: Mapping[str, object] = {
    "newConnectionPerRequest": True,
    "followRedirects": False,
    "proxyFromEnvironment": False,
    "retries": 0,
}

#: The V1 classification gives an answer that arrives after the deadline the outcome
#: `timeout`, whatever the answer says.
ANSWER_AFTER_DEADLINE = "not-a-success"

REUSED = "reused"
REUSED_IN_PART = "reused-in-part"
PINNED = "pinned"
CHANGED = "changed"
NOT_CARRIED = "not-carried"
DISPOSITIONS = (REUSED, REUSED_IN_PART, PINNED, CHANGED, NOT_CARRIED)

#: The disposition of each member that the V1 load profile states. A member that the
#: V1 file states and this table does not name is refused: nothing is left out
#: without a reason.
SOURCE_DISPOSITION: Mapping[str, str] = {
    "schemaVersion": REUSED,
    "profileId": PINNED,
    "profileVersion": PINNED,
    "evidenceClass": NOT_CARRIED,
    "evidenceLabel": NOT_CARRIED,
    "certificationCeiling": REUSED,
    "productionBenchmark": REUSED,
    "portableCapacityClaim": REUSED,
    "boundary": CHANGED,
    "boundariesRef": REUSED,
    "providerContractRef": NOT_CARRIED,
    "release": NOT_CARRIED,
    "target": CHANGED,
    "fixture": REUSED,
    "generation": REUSED,
    "warmup": NOT_CARRIED,
    "levels": CHANGED,
    "measured": NOT_CARRIED,
    "timeouts": REUSED,
    "success": REUSED_IN_PART,
    "results": NOT_CARRIED,
}

#: The content digest of each revision of the profile: the SHA-256 of the file with
#: each CRLF replaced by LF. A revision is added here when it is committed, and its
#: digest is not changed afterwards.
REGISTERED_REVISIONS: Mapping[int, str] = {
    1: "853b6e92c8ef45790a80756fffa4d5001fcc572dac95fc86625613eda70deb22",
}

RULE_UNREADABLE = "rp1-profile-unreadable"
RULE_MEMBERS = "rp1-members-unsupported"
RULE_IDENTITY = "rp1-identity-unsupported"
RULE_PURPOSE = "rp1-purpose-overstated"
RULE_SOURCE_REFUSED = "rp1-source-refused"
RULE_SOURCE_PIN = "rp1-source-pin-differs"
RULE_CALLER = "rp1-concurrency-not-fixed"
RULE_TARGET = "rp1-target-not-api-service"
RULE_REQUEST = "rp1-request-differs"
RULE_GENERATION = "rp1-generation-differs"
RULE_CONNECTION = "rp1-connection-differs"
RULE_TIMEOUT = "rp1-timeout-differs"
RULE_SUCCESS = "rp1-success-differs"
RULE_RESULTS = "rp1-results-hold-content"
RULE_DISPOSITION = "rp1-disposition-incomplete"
RULE_REVISION = "rp1-revision-digest-differs"

#: Each rule, in the order the loader applies it. The loader stops at the first rule
#: that refuses.
RULES: tuple[str, ...] = (
    RULE_UNREADABLE,
    RULE_MEMBERS,
    RULE_IDENTITY,
    RULE_PURPOSE,
    RULE_SOURCE_REFUSED,
    RULE_SOURCE_PIN,
    RULE_CALLER,
    RULE_TARGET,
    RULE_REQUEST,
    RULE_GENERATION,
    RULE_CONNECTION,
    RULE_TIMEOUT,
    RULE_SUCCESS,
    RULE_RESULTS,
    RULE_DISPOSITION,
    RULE_REVISION,
)


class ProfileError(RuntimeError):
    """The reliability profile, or the V1 load profile it pins, was refused."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule


@dataclass(frozen=True, slots=True)
class ReliabilityProfile:
    """The committed RP-1 profile after each rule has accepted it."""

    profile_id: str
    profile_revision: int
    profile_sha256: str
    source_profile_ref: str
    source_profile_version: str
    source_profile_sha256: str
    concurrency: int
    fixture_id: str
    request_method: str
    request_path: str
    request_content_type: str
    request_id_header: str
    correlation_id_header: str
    request_body: Mapping[str, Any]
    max_output_tokens: int
    temperature: float
    sampling_seed: str
    context_size_tokens: int
    parallel_slots: int
    request_timeout_ms: int
    required_status: int
    required_adapter_kind: str
    required_model_ref: str
    require_usage: bool

    def body(self) -> dict[str, Any]:
        """A copy of the request body that each caller request sends."""
        return copy.deepcopy(dict(self.request_body))


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileError(RULE_MEMBERS, f"member '{field}' must be an object")
    return cast(dict[str, Any], value)


def _members(record: Mapping[str, Any], field: str, expected: set[str]) -> None:
    if set(record) != expected:
        raise ProfileError(
            RULE_MEMBERS, f"member '{field}' has missing or unsupported members"
        )


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProfileError(RULE_MEMBERS, f"member '{field}' must be a non-empty string")
    return value


def _integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProfileError(RULE_MEMBERS, f"member '{field}' must be an integer")
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileError(RULE_MEMBERS, f"member '{field}' must be a boolean")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProfileError(RULE_MEMBERS, f"member '{field}' must be a number")
    return float(value)


def profile_digest(path: Path) -> str:
    """The SHA-256 of a profile file with each CRLF replaced by LF.

    A Windows checkout can hold the committed file with CRLF. A digest that follows
    the line endings of a checkout would give one committed profile two digests.
    """
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ProfileError(
            RULE_UNREADABLE, "the reliability profile is unreadable"
        ) from error
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileError(
            RULE_UNREADABLE, "the reliability profile is unreadable"
        ) from error
    if not isinstance(loaded, dict):
        raise ProfileError(RULE_UNREADABLE, "the reliability profile is not an object")
    return cast(dict[str, Any], loaded)


def _load_source(source_path: Path, repo_root: Path) -> source_core.Profile:
    """The V1 load profile, accepted by its own loader."""
    try:
        return llm_load.load_profile(source_path, repo_root=repo_root)
    except (
        llm_load.LoadError,
        ModelAcquisitionError,
        RuntimeConfigurationError,
        RuntimePackagingError,
    ) as error:
        raise ProfileError(
            RULE_SOURCE_REFUSED, f"the V1 load profile is refused: {error}"
        ) from error


def _source_members(source_path: Path) -> set[str]:
    try:
        loaded = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileError(
            RULE_SOURCE_REFUSED, "the V1 load profile is unreadable"
        ) from error
    return set(cast(dict[str, Any], loaded))


def _check_disposition(value: Any, source_members: set[str]) -> None:
    if not isinstance(value, list):
        raise ProfileError(RULE_MEMBERS, "member 'sourceDisposition' must be a list")
    stated: dict[str, str] = {}
    for index, item in enumerate(value):
        field = f"sourceDisposition[{index}]"
        entry = _object(item, field)
        _members(entry, field, {"member", "disposition", "reason"})
        member = _string(entry.get("member"), f"{field}.member")
        _string(entry.get("reason"), f"{field}.reason")
        if member in stated:
            raise ProfileError(
                RULE_DISPOSITION, f"the V1 member '{member}' has two dispositions"
            )
        stated[member] = _string(entry.get("disposition"), f"{field}.disposition")
    for member in sorted(source_members - set(SOURCE_DISPOSITION)):
        raise ProfileError(
            RULE_DISPOSITION,
            f"the V1 load profile states '{member}', and this tool has no "
            "disposition for it",
        )
    for member in sorted(source_members - set(stated)):
        raise ProfileError(
            RULE_DISPOSITION, f"the V1 member '{member}' has no disposition"
        )
    for member in sorted(set(stated) - source_members):
        raise ProfileError(
            RULE_DISPOSITION,
            f"'{member}' has a disposition, and the V1 load profile does not state it",
        )
    for member, disposition in sorted(stated.items()):
        if disposition != SOURCE_DISPOSITION[member]:
            raise ProfileError(
                RULE_DISPOSITION,
                f"the V1 member '{member}' must have the disposition "
                f"'{SOURCE_DISPOSITION[member]}'",
            )


def load_profile(
    path: Path = PROFILE_PATH,
    *,
    source_path: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> ReliabilityProfile:
    """Load the RP-1 profile and compare it with the V1 load profile it pins.

    ``source_path`` is where the V1 load profile is read from. It defaults to the
    committed file under ``repo_root``. The profile's ``source.profileRef`` must still
    name the committed path.
    """
    record = _read(path)
    _members(
        record,
        "root",
        {
            "schemaVersion",
            "kind",
            "profileId",
            "profileRevision",
            "workloadClass",
            "evidenceLevelCeiling",
            "representativeWorkload",
            "overloadBenchmark",
            "productionBenchmark",
            "portableCapacityClaim",
            "boundary",
            "boundariesRef",
            "source",
            "caller",
            "target",
            "request",
            "generation",
            "connection",
            "timeouts",
            "success",
            "results",
            "sourceDisposition",
        },
    )
    source = _object(record.get("source"), "source")
    caller = _object(record.get("caller"), "caller")
    target = _object(record.get("target"), "target")
    request = _object(record.get("request"), "request")
    generation = _object(record.get("generation"), "generation")
    connection = _object(record.get("connection"), "connection")
    timeouts = _object(record.get("timeouts"), "timeouts")
    success = _object(record.get("success"), "success")
    results = _object(record.get("results"), "results")
    _members(
        source, "source", {"profileRef", "profileId", "profileVersion", "contentSha256"}
    )
    _members(caller, "caller", {"location", "loop", "concurrency"})
    _members(target, "target", {"kind", "scheme", "podAddress", "portForward"})
    _members(
        request,
        "request",
        {
            "fixtureId",
            "method",
            "path",
            "contentType",
            "requestIdHeader",
            "correlationIdHeader",
            "body",
        },
    )
    _members(
        generation,
        "generation",
        {
            "sentInRequest",
            "maxOutputTokens",
            "temperature",
            "samplingSeed",
            "contextSizeTokens",
            "parallelSlots",
        },
    )
    _members(connection, "connection", set(CONNECTION))
    _members(timeouts, "timeouts", {"requestTimeoutMs", "answerAfterDeadline"})
    _members(
        success,
        "success",
        {"requiredStatus", "requiredAdapterKind", "requiredModelRef", "requireUsage"},
    )
    _members(results, "results", {"promptText", "completionText"})
    body = _object(request.get("body"), "request.body")

    revision = _integer(record.get("profileRevision"), "profileRevision")
    if (
        _string(record.get("schemaVersion"), "schemaVersion") != EXPECTED_SCHEMA
        or _string(record.get("kind"), "kind") != EXPECTED_KIND
        or _string(record.get("profileId"), "profileId") != PROFILE_ID
        or revision not in REGISTERED_REVISIONS
    ):
        raise ProfileError(
            RULE_IDENTITY,
            "the schema version, the kind, the profile identifier, or the revision "
            "is not one this tool registers",
        )
    if (
        _string(record.get("workloadClass"), "workloadClass") != WORKLOAD_CLASS
        or _string(record.get("evidenceLevelCeiling"), "evidenceLevelCeiling")
        != EVIDENCE_LEVEL_CEILING
        or _boolean(record.get("representativeWorkload"), "representativeWorkload")
        or _boolean(record.get("overloadBenchmark"), "overloadBenchmark")
        or _boolean(record.get("productionBenchmark"), "productionBenchmark")
        or _boolean(record.get("portableCapacityClaim"), "portableCapacityClaim")
        or _string(record.get("boundary"), "boundary") != BOUNDARY_STATEMENT
        or _string(record.get("boundariesRef"), "boundariesRef")
        != EXPECTED_BOUNDARIES_REF
    ):
        raise ProfileError(
            RULE_PURPOSE,
            "the profile must be a reliability workload with the ceiling C2, must "
            "not declare a representative workload, an overload benchmark, a "
            "production benchmark, or a portable capacity claim, and must carry the "
            "boundary statement verbatim",
        )

    if source_path is None:
        source_path = repo_root / SOURCE_PROFILE_REF
    loaded = _load_source(source_path, repo_root)
    if (
        _string(source.get("profileRef"), "source.profileRef") != SOURCE_PROFILE_REF
        or _string(source.get("profileId"), "source.profileId") != loaded.profile_id
        or _string(source.get("profileVersion"), "source.profileVersion")
        != loaded.profile_version
        or _string(source.get("contentSha256"), "source.contentSha256")
        != loaded.profile_sha256
    ):
        raise ProfileError(
            RULE_SOURCE_PIN,
            "the V1 load profile is not the file this profile pins: its path, "
            "identifier, version, or content digest differs. State the difference "
            "in a new revision of this profile before a run uses it",
        )

    concurrency = _integer(caller.get("concurrency"), "caller.concurrency")
    if (
        _string(caller.get("location"), "caller.location") != CALLER_LOCATION
        or _string(caller.get("loop"), "caller.loop") != CALLER_LOOP
        or concurrency != CONCURRENCY
        or concurrency not in {level.concurrency for level in loaded.levels}
        or concurrency > source_core.MAXIMUM_CONCURRENCY
    ):
        raise ProfileError(
            RULE_CALLER,
            f"the caller must be {CONCURRENCY} closed-loop workers inside the "
            "cluster, and the V1 load profile must have a level at that concurrency",
        )
    if (
        _string(target.get("kind"), "target.kind") != TARGET_KIND
        or _string(target.get("scheme"), "target.scheme") != TARGET_SCHEME
        or _boolean(target.get("podAddress"), "target.podAddress")
        or _boolean(target.get("portForward"), "target.portForward")
    ):
        raise ProfileError(
            RULE_TARGET,
            "the target must be the API Service over plain HTTP, and not a pod "
            "address or a port-forward",
        )

    if (
        _string(request.get("fixtureId"), "request.fixtureId")
        != loaded.fixture.fixture_id
        or _string(request.get("method"), "request.method") != REQUEST_METHOD
        or _string(request.get("path"), "request.path") != loaded.fixture.request_path
        or loaded.fixture.request_path != CHAT_COMPLETIONS_PATH
        or _string(request.get("contentType"), "request.contentType")
        != REQUEST_CONTENT_TYPE
        or _string(request.get("requestIdHeader"), "request.requestIdHeader")
        != REQUEST_ID_HEADER
        or _string(request.get("correlationIdHeader"), "request.correlationIdHeader")
        != CORRELATION_ID_HEADER
        or body != loaded.fixture.body()
    ):
        raise ProfileError(
            RULE_REQUEST,
            "the request differs from the request the V1 load harness sends: its "
            "fixture identifier, method, path, content type, header names, or body",
        )
    temperature = _number(generation.get("temperature"), "generation.temperature")
    if (
        _boolean(generation.get("sentInRequest"), "generation.sentInRequest")
        or _integer(generation.get("maxOutputTokens"), "generation.maxOutputTokens")
        != loaded.max_output_tokens
        or temperature != loaded.temperature
        or _string(generation.get("samplingSeed"), "generation.samplingSeed")
        != SAMPLING_SEED
        or _integer(generation.get("contextSizeTokens"), "generation.contextSizeTokens")
        != loaded.context_size_tokens
        or _integer(generation.get("parallelSlots"), "generation.parallelSlots")
        != loaded.parallel_slots
    ):
        raise ProfileError(
            RULE_GENERATION,
            "the generation settings differ from the V1 load profile, or the "
            "profile states that the request sends them",
        )
    for name, expected in CONNECTION.items():
        stated = connection.get(name)
        if type(stated) is not type(expected) or stated != expected:
            raise ProfileError(
                RULE_CONNECTION,
                f"connection.{name} differs from what the V1 transport does",
            )
    if (
        _integer(timeouts.get("requestTimeoutMs"), "timeouts.requestTimeoutMs")
        != loaded.request_timeout_ms
        or _string(timeouts.get("answerAfterDeadline"), "timeouts.answerAfterDeadline")
        != ANSWER_AFTER_DEADLINE
    ):
        raise ProfileError(
            RULE_TIMEOUT,
            "the client deadline differs from the V1 load profile, or an answer "
            "after the deadline is not stated as not a success",
        )
    if (
        _integer(success.get("requiredStatus"), "success.requiredStatus")
        != loaded.required_status
        or _string(success.get("requiredAdapterKind"), "success.requiredAdapterKind")
        != loaded.required_adapter_kind
        or _string(success.get("requiredModelRef"), "success.requiredModelRef")
        != loaded.required_model_ref
        or _boolean(success.get("requireUsage"), "success.requireUsage")
        != loaded.require_usage
    ):
        raise ProfileError(
            RULE_SUCCESS, "the success rule differs from the V1 load profile"
        )
    if _boolean(results.get("promptText"), "results.promptText") or _boolean(
        results.get("completionText"), "results.completionText"
    ):
        raise ProfileError(
            RULE_RESULTS,
            "a result under this profile may hold no prompt text and no completion "
            "text",
        )

    _check_disposition(record.get("sourceDisposition"), _source_members(source_path))

    digest = profile_digest(path)
    if digest != REGISTERED_REVISIONS[revision]:
        raise ProfileError(
            RULE_REVISION,
            f"the content digest of the profile is not the digest registered for "
            f"revision {revision}. A changed profile is a new revision",
        )

    return ReliabilityProfile(
        profile_id=PROFILE_ID,
        profile_revision=revision,
        profile_sha256=digest,
        source_profile_ref=SOURCE_PROFILE_REF,
        source_profile_version=loaded.profile_version,
        source_profile_sha256=loaded.profile_sha256,
        concurrency=concurrency,
        fixture_id=loaded.fixture.fixture_id,
        request_method=REQUEST_METHOD,
        request_path=loaded.fixture.request_path,
        request_content_type=REQUEST_CONTENT_TYPE,
        request_id_header=REQUEST_ID_HEADER,
        correlation_id_header=CORRELATION_ID_HEADER,
        request_body=body,
        max_output_tokens=loaded.max_output_tokens,
        temperature=temperature,
        sampling_seed=SAMPLING_SEED,
        context_size_tokens=loaded.context_size_tokens,
        parallel_slots=loaded.parallel_slots,
        request_timeout_ms=loaded.request_timeout_ms,
        required_status=loaded.required_status,
        required_adapter_kind=loaded.required_adapter_kind,
        required_model_ref=loaded.required_model_ref,
        require_usage=loaded.require_usage,
    )
