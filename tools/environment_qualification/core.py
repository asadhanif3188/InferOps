"""Q1, the environment and identity qualification, as one record.

Q1 decides whether one local environment can hold the target topology of the
V2 reliability experiments before any of them runs: two platform API replicas
and two serving runtime replicas of the desired-state release. The result is
``QUALIFIED`` or ``REFUSED``. There is no third result.

A frozen driver runs the operating procedures and the collectors of the
repository, and writes what each of them wrote into one directory. This module
reads that directory and returns one record. It contacts no cluster, and it
runs no procedure. It holds each source record to the identity and the state
that Q1 requires, and it states each rule that refuses.

**A refusal is a result.** No rule lowers a replica count, a request, a limit,
or a bound to reach ``QUALIFIED``. The target release key, the topology, and
the provider are constants of this module. The model and the runtime image are
the ones whose pin files the freeze record pins by content: the driver copies
the two files into the directory, and a copy of other content refuses. No
option of the command changes any of them. A refused environment stays refused until the environment
or a frozen input changes, and a later qualification is a new qualification.

**A read that was not made is not a value.** An absent source gives the state
``not-observed`` to each rule that reads it, and a source of another form gives
``not-held``. Each of the two refuses.

**The record is not a reliability result.** It states that the declared
topology became Ready once, that the delivery controller reconciled it at the
declared revision, that both runtime replicas verified the pinned model, and
that the caller runner completed real requests through the API Service. It
states no recovery time, no availability, and no bound.

See docs/environment/environment-qualification.md, which describes the
directory, each rule, the identities, and the limits of a record, and
tests/domain/test_environment_qualification.py, which gives the module each
refusal.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from tools.reliability_runner.core import RunnerError, read_record

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The schema name of a record.
RECORD_SCHEMA: Final = "inferops.io/environment-qualification/v1alpha1"

#: The schema name that the driver writes into the header of a directory.
COLLECTION_SCHEMA: Final = "inferops.io/environment-qualification-collection/v1alpha1"

#: The qualification that a record decides. Later qualification work is not
#: decided here.
QUALIFICATION: Final = "Q1"

#: The experiment identifier that the driver gives the caller runner.
EXPERIMENT_ID: Final = "v2-q1-environment-qualification"

#: Revision 1 of the Q1 freeze record. Its records state the exact environment
#: identity, which holds the memory figures of the node and of the container
#: engine. It decided q1-1.
FREEZE_RECORD_R1: Final = "docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json"

#: The freeze record that governs the driver and this module. Revision 2
#: supersedes revision 1: its records state the stable environment identity,
#: which holds no memory figure. Memory is a capacity fact, and the capacity gate
#: decides it for each reading. See ADR-0021.
FREEZE_RECORD: Final = "docs/proof/experiments/v2-q1/freeze-r2.v1alpha1.json"

#: Every revision of the Q1 freeze record that a header may name. A record is
#: built again under the revision that its header names, with the identity of
#: that revision, so a later revision leaves the records of earlier revisions as
#: they were.
FREEZE_RECORDS: Final = (FREEZE_RECORD_R1, FREEZE_RECORD)

#: The member that names the revision of a stable environment identity, and its
#: value. An exact environment identity, of revision 1, holds no such member.
IDENTITY_REVISION_MEMBER: Final = "identityRevision"
STABLE_IDENTITY_REVISION: Final = 2

#: Where committed qualification directories are found.
RUNS_PATTERN: Final = "docs/proof/experiments/v2-q1/runs/*"

#: The target of Q1. These are the values of the desired-state release. A test
#: compares them with the declaration of that release. No option changes them.
TARGET_RELEASE_KEY: Final = "local-docker-desktop/support-assistant"
TARGET_API_REPLICAS: Final = 2
TARGET_RUNTIME_REPLICAS: Final = 2

#: The provider that Q1 qualifies, and the context that its target check uses.
SELECTED_PROVIDER: Final = "docker-desktop"
EXPECTED_CONTEXT: Final = "docker-desktop"

#: The release namespace and the Helm release name of the chart.
RELEASE_NAMESPACE: Final = "inferops-release"
RELEASE_INSTANCE: Final = "inferops"

#: The checkout files that hold the pinned model and the pinned runtime image.
#: The freeze record pins each by content. The driver copies each into the
#: directory, so a record is built again from the files the qualification read.
MODEL_SOURCE_FILE: Final = "docs/serving/model-source.v1.json"
RUNTIME_PACKAGE_FILE: Final = "deploy/serving/runtime/container-package.v1.json"

#: The files of a directory. The driver restates each name.
HEADER_FILE: Final = "run.json"
CAPACITY_RECORD: Final = "capacity/record.v1alpha1.json"
PROVENANCE_FILE: Final = "provenance.json"
RECONCILIATION_RECORD: Final = "reconciliation.record.json"
DEPLOYMENTS_FILE: Final = "deployments.json"
ENDPOINTS_RECORD: Final = "endpoints/record.v1alpha1.json"
MODEL_CACHE_RECORD: Final = "model-cache/record.v1alpha1.json"
CALLER_FILE: Final = "caller.jsonl"
CALLER_REFUSED_FILE: Final = "caller.refused.jsonl"
PLAN_FILE: Final = "plan.json"
MODEL_SOURCE_COPY: Final = "pins/model-source.v1.json"
RUNTIME_PACKAGE_COPY: Final = "pins/container-package.v1.json"
RECORD_FILE: Final = "record.v1alpha1.json"

#: Every file that a record reads from a directory, in the order it lists them.
SOURCE_FILES: Final = (
    HEADER_FILE,
    CAPACITY_RECORD,
    PROVENANCE_FILE,
    RECONCILIATION_RECORD,
    DEPLOYMENTS_FILE,
    ENDPOINTS_RECORD,
    MODEL_CACHE_RECORD,
    PLAN_FILE,
    CALLER_FILE,
    CALLER_REFUSED_FILE,
    MODEL_SOURCE_COPY,
    RUNTIME_PACKAGE_COPY,
)

#: The schema names of the source records. Each is written by its own tool.
CAPACITY_SCHEMA: Final = "inferops.io/capacity-preflight/v1alpha1"
PROVENANCE_SCHEMA: Final = "inferops.io/desired-state-provenance/v1alpha1"
RECONCILIATION_SCHEMA: Final = "inferops.io/reconciliation-observation/v1alpha1"
ENDPOINTS_SCHEMA: Final = "inferops.io/service-endpoint-state/v1alpha1"
MODEL_CACHE_SCHEMA: Final = "inferops.io/runtime-model-cache-observation/v1alpha1"

#: The rules of a model cache observation that Q1 requires to be held. The
#: observation also states the V1 multi-replica capacity preflight and the
#: readiness of each pod while it loads. Q1 reads neither: the V2 capacity gate
#: decides capacity, and the loading samples are not part of Q1.
MODEL_CACHE_RULES: Final = (
    "replica-count",
    "every-replica-ready",
    "one-runtime-image",
    "one-model-argument",
    "one-claim",
    "claim-is-the-prerequisite-claim",
    "no-second-claim",
    "read-only-declared",
    "read-only-in-effect",
    "revision-scoped-mount",
    "one-directory",
    "one-file",
    "artifact-verified-in-each-pod",
    "one-reported-model",
    "every-replica-completed",
)

#: The least number of reconciliation samples that Q1 reads.
MINIMUM_RECONCILIATION_SAMPLES: Final = 5

#: The end states of a caller record that Q1 reads as a run that ended by its
#: own bound.
CALLER_END_STATES: Final = ("duration", "request-ceiling")

#: The exit status of the command when the result is REFUSED.
REFUSED_EXIT: Final = 5

QUALIFIED: Final = "QUALIFIED"
REFUSED: Final = "REFUSED"

#: Every result that a record can state.
RESULT_STATES: Final = (QUALIFIED, REFUSED)

HELD: Final = "held"
NOT_HELD: Final = "not-held"
NOT_OBSERVED: Final = "not-observed"

#: Every state of a rule.
RULE_STATES: Final = (HELD, NOT_HELD, NOT_OBSERVED)

#: The refusal categories, in the order a record states them.
TARGET: Final = "target"
PROVIDER_MISMATCH: Final = "provider-mismatch"
AMBIGUOUS_CONTEXT: Final = "ambiguous-context"
DESIRED_STATE: Final = "desired-state"
CAPACITY: Final = "capacity"
RECONCILIATION: Final = "reconciliation"
TOPOLOGY: Final = "topology"
RELEASE_IDENTITY: Final = "release-identity"
MODEL_MISMATCH: Final = "model-mismatch"
CALLER: Final = "caller"
EVIDENCE: Final = "evidence"

CATEGORIES: Final = (
    TARGET,
    PROVIDER_MISMATCH,
    AMBIGUOUS_CONTEXT,
    DESIRED_STATE,
    CAPACITY,
    RECONCILIATION,
    TOPOLOGY,
    RELEASE_IDENTITY,
    MODEL_MISMATCH,
    CALLER,
    EVIDENCE,
)

#: The refusal categories of the target check of the operating procedures that
#: name a provider fault, and the one that names an ambiguous target.
PROVIDER_REFUSALS: Final = frozenset(
    {"no-provider-selected", "unsupported-provider", "provider-mismatch"}
)
AMBIGUOUS_REFUSALS: Final = frozenset({"ambiguous-target"})

WORKING_TREE_STATES: Final = ("clean", "dirty", "unread")
DESIRED_STATE_DIFF_STATES: Final = ("none", "differs", "unread")
FREEZE_CHANGE_STATES: Final = ("none", "listed", "unread")

#: Why the phase up of the driver stopped before the release was applied, when
#: it did. The driver writes one of these, or null when up completed.
UP_REFUSALS: Final = (
    "working-tree",
    "delivery-paths",
    "frozen-inputs",
    "release-present",
    "capacity",
    "preparation-failed",
)


@dataclass(frozen=True)
class Rule:
    """One rule of a record: the criterion of the freeze record that it decides."""

    rule_id: str
    criterion: str
    category: str
    statement: str


#: Every rule, in the order a record states them. Each one is one acceptance
#: criterion of the freeze record, with the same statement.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "target-reached",
        "Q1-AC1",
        TARGET,
        "The target check of the operating procedures selected the target and "
        "refused nothing.",
    ),
    Rule(
        "provider-selected",
        "Q1-AC2",
        PROVIDER_MISMATCH,
        "The qualification selects the docker-desktop provider explicitly, the "
        "target check refused no provider, and every source record that names a "
        "provider names docker-desktop.",
    ),
    Rule(
        "context-unambiguous",
        "Q1-AC3",
        AMBIGUOUS_CONTEXT,
        "The target check found one target, the cluster held no release and no "
        "controller before the phase up, the capacity collection names the context "
        "docker-desktop, the capacity record holds one node and a readable "
        "environment identity, and the runtime pods run on that node.",
    ),
    Rule(
        "working-tree-clean",
        "Q1-AC4",
        DESIRED_STATE,
        "The working tree was clean when the phase up started and when the "
        "qualification started.",
    ),
    Rule(
        "procedure-frozen",
        "Q1-AC5",
        DESIRED_STATE,
        "The driver names the Q1 freeze record, the record has the content that "
        "the checkout holds, and the freeze tool listed no changed material file "
        "in the phase up or in the qualification.",
    ),
    Rule(
        "desired-revision-known",
        "Q1-AC6",
        DESIRED_STATE,
        "The desired revision is one full commit identifier, and the chart, the "
        "desired-state tree, and the controller manifests of the executing commit "
        "equal those of that revision in the phase up and in the qualification.",
    ),
    Rule(
        "one-executing-commit",
        "Q1-AC7",
        DESIRED_STATE,
        "The capacity collection, the endpoint collection, the model cache "
        "collection, and the reconciliation collection name the executing commit "
        "of the qualification.",
    ),
    Rule(
        "release-provenance-resolved",
        "Q1-AC8",
        DESIRED_STATE,
        "The provenance record resolves the target release key at the desired "
        "revision to one release identifier.",
    ),
    Rule(
        "capacity-accepted",
        "Q1-AC9",
        CAPACITY,
        "The V2 capacity gate accepted the target release key with 2 API replicas "
        "and 2 runtime replicas before the release was applied.",
    ),
    Rule(
        "controller-identified",
        "Q1-AC10",
        RECONCILIATION,
        "The verification of the delivery controller by its bootstrap procedure "
        "exited 0, and the driver states the controller version.",
    ),
    Rule(
        "controller-reconciled",
        "Q1-AC11",
        RECONCILIATION,
        "The reconciliation record is complete, holds at least 5 samples, and in "
        "each sample the Application is settled at the desired revision, resolves "
        "to the provenance release, and has no finding in its revisions, its "
        "source, and its labels.",
    ),
    Rule(
        "deployments-ready",
        "Q1-AC12",
        TOPOLOGY,
        "The phase up completed its preparation, and the API Deployment and the "
        "runtime Deployment of the release each state 2 replicas, and each reports "
        "2 replicas, 2 Ready, 2 available, and 2 updated at its current generation.",
    ),
    Rule(
        "endpoints-ready",
        "Q1-AC13",
        TOPOLOGY,
        "The endpoint record is OBSERVED, and the API Service and the runtime "
        "Service each have 2 endpoints, and both are Ready.",
    ),
    Rule(
        "images-declared",
        "Q1-AC14",
        RELEASE_IDENTITY,
        "The api container of the API Deployment runs the API image digest that "
        "the driver built and declared, and the runtime container of the runtime "
        "Deployment runs the pinned runtime image.",
    ),
    Rule(
        "model-identity-verified",
        "Q1-AC15",
        MODEL_MISMATCH,
        "The copies of the model pin and the runtime image pin have the content "
        "that the freeze record pins, the model cache record expects that model "
        "and that runtime image for 2 runtime replicas of the target release, and "
        "it holds each of its model identity rules.",
    ),
    Rule(
        "caller-completed",
        "Q1-AC16",
        CALLER,
        "The runner's reader accepts the caller record with its plan, in the mode "
        "in-cluster, for this qualification and the provenance release, the run "
        "ended by its own bound, and at least one request has the outcome success.",
    ),
    Rule(
        "readings-in-order",
        "Q1-AC17",
        EVIDENCE,
        "The capacity reading precedes the qualification, and the endpoint "
        "reading, the model cache collection, the start of the caller run, and the "
        "first and the last reconciliation samples lie between the start and the "
        "end of the qualification.",
    ),
)

#: What no record of revision 1 establishes. Part of every such record, as it was
#: when q1-1 was decided.
DOES_NOT_ESTABLISH_R1: Final[tuple[str, ...]] = (
    "A record does not establish behaviour under a fault, the replacement of a "
    "pod, or a recovery from either.",
    "A record does not establish a runtime start time, a caller gap, or any "
    "bound that later work derives.",
    "A record does not establish a latency, a throughput, a success rate, or the "
    "reliability of the caller path. One completed request shows that the path "
    "answered once.",
    "A record does not establish that a later run uses the same environment. A "
    "later run must state its own environment identity. No tool compares two "
    "identities yet.",
    "A record does not establish that a source record is what its collection "
    "gives. The module reads the stored source records and does not build them "
    "again. It checks the caller record with the runner's reader.",
    "A record does not establish capacity beyond the stated requests and limits "
    "on one node, or that a pod is scheduled in another state of the cluster.",
    "A record does not establish production availability, high availability, a "
    "service level, or resilience to the loss of a node, a zone, or a region.",
    "A record does not establish anything about another provider, another node, "
    "another Kubernetes version, or another release.",
    "A record does not establish a representative workload. RP-1 is a fixed "
    "reliability profile.",
)

#: What no record of the current revision establishes. Part of every such record.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "A record does not establish behaviour under a fault, the replacement of a "
    "pod, or a recovery from either.",
    "A record does not establish a runtime start time, a caller gap, or any "
    "bound that later work derives.",
    "A record does not establish a latency, a throughput, a success rate, or the "
    "reliability of the caller path. One completed request shows that the path "
    "answered once.",
    "A record does not establish that a later run uses the same environment. A "
    "later run states its own environment identity, and the tool of that run "
    "compares it with the one this record states.",
    "A record does not establish the memory of a later environment of the same "
    "identity. The stable environment identity holds no memory figure. Each "
    "reading of an environment is held to the capacity gate, which decides "
    "whether the declared limits fit.",
    "A record does not establish that memory above the declared limits has no "
    "effect on a later measurement, or why the container engine and the node "
    "report other memory figures after each start of the virtual machine.",
    "A record does not establish that a source record is what its collection "
    "gives. The module reads the stored source records and does not build them "
    "again. It checks the caller record with the runner's reader.",
    "A record does not establish capacity beyond the stated requests and limits "
    "on one node, or that a pod is scheduled in another state of the cluster.",
    "A record does not establish production availability, high availability, a "
    "service level, or resilience to the loss of a node, a zone, or a region.",
    "A record does not establish anything about another provider, another node, "
    "another Kubernetes version, or another release.",
    "A record does not establish a representative workload. RP-1 is a fixed "
    "reliability profile.",
)

_REVISION: Final = re.compile(r"[0-9a-f]{40}")
_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}")
_HEX64: Final = re.compile(r"[0-9a-f]{64}")
_QUALIFICATION_ID: Final = re.compile(r"q1-[1-9][0-9]?")
_CATEGORY: Final = re.compile(r"[a-z][a-z-]{0,62}[a-z]")
_VERSION: Final = re.compile(r"v[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}")
_NAME: Final = re.compile(r"[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?")
_KEY: Final = re.compile(r"[a-z0-9][a-z0-9-]{0,62}/[a-z0-9][a-z0-9-]{0,62}")
_INSTANT: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{3})?Z"
)
_IMAGE: Final = re.compile(r"[a-z0-9][a-z0-9._/:-]{0,199}@sha256:[0-9a-f]{64}")

#: The members of a header, and the test of each value.
_HEADER: Final[dict[str, Callable[[object], bool]]] = {
    "schema": lambda value: value == COLLECTION_SCHEMA,
    "qualificationId": lambda value: _text(value, _QUALIFICATION_ID),
    "provider": lambda value: _text(value, _CATEGORY),
    "releaseKey": lambda value: _text(value, _KEY),
    "executingCommit": lambda value: _text(value, _REVISION),
    "desiredRevision": lambda value: value is None or _text(value, _REVISION),
    "workingTree": lambda value: value in WORKING_TREE_STATES,
    "desiredStateDiff": lambda value: value in DESIRED_STATE_DIFF_STATES,
    "freezeRecord": lambda value: (
        isinstance(value, str)
        and re.fullmatch(r"[a-z0-9][a-z0-9./-]{0,199}\.json", value) is not None
    ),
    "freezeRecordSha256": lambda value: value is None or _text(value, _HEX64),
    "freezeChanges": lambda value: value in FREEZE_CHANGE_STATES,
    "apiImageDigest": lambda value: value is None or _text(value, _DIGEST),
    "controllerVersion": lambda value: value is None or _text(value, _VERSION),
    "controllerVerified": lambda value: value is None or isinstance(value, bool),
    "targetRefusal": lambda value: value is None or _text(value, _CATEGORY),
    "upRefusal": lambda value: value is None or value in UP_REFUSALS,
    "startedAt": lambda value: _text(value, _INSTANT),
    "finishedAt": lambda value: _text(value, _INSTANT),
}


class CollectionRefused(ValueError):
    """The directory is not a qualification directory, so no record exists."""


def _text(value: object, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()


def _dig(document: object, *path: str) -> Any:
    for member in path:
        if not isinstance(document, Mapping):
            return None
        document = document.get(member)
    return document


def lf_digest(data: bytes) -> str:
    """The SHA-256 of a file's bytes with CRLF read as LF, as hexadecimal."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _instant(value: object) -> datetime | None:
    if not _text(value, _INSTANT):
        return None
    text = str(value)
    pattern = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in text else "%Y-%m-%dT%H:%M:%SZ"
    try:
        return datetime.strptime(text, pattern).replace(tzinfo=UTC)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Reading a directory
# --------------------------------------------------------------------------

ABSENT: Final = "absent"
UNREADABLE: Final = "unreadable"


@dataclass(frozen=True)
class Source:
    """One file of a directory: what it holds, or why it holds nothing."""

    name: str
    value: Any = None
    problem: str | None = None

    @property
    def read(self) -> bool:
        return self.problem is None


def _read_bytes(directory: Path, name: str) -> bytes | None:
    path = directory / name
    if not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _json_source(directory: Path, name: str, schema: str | None) -> Source:
    data = _read_bytes(directory, name)
    if data is None:
        return Source(name, problem=ABSENT)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError):
        return Source(name, problem=UNREADABLE)
    if schema is not None and _dig(value, "schema") != schema:
        return Source(name, problem=f"not a record of schema {schema}")
    return Source(name, value=value)


def read_header(directory: Path) -> dict[str, Any]:
    """The header of a directory. Raise when the directory is not one."""
    data = _read_bytes(directory, HEADER_FILE)
    if data is None:
        raise CollectionRefused(f"{HEADER_FILE} is absent or unreadable")
    try:
        header = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise CollectionRefused(f"{HEADER_FILE} is not JSON") from error
    if not isinstance(header, dict):
        raise CollectionRefused(f"{HEADER_FILE} is not an object")
    if set(header) != set(_HEADER):
        raise CollectionRefused(
            f"{HEADER_FILE} must state exactly the members {sorted(_HEADER)}"
        )
    wrong = sorted(name for name, test in _HEADER.items() if not test(header[name]))
    if wrong:
        raise CollectionRefused(f"{HEADER_FILE} states unusable values for {wrong}")
    return header


@dataclass(frozen=True)
class Sources:
    """Every source of one directory, read once."""

    header: Mapping[str, Any]
    capacity: Source
    provenance: Source
    reconciliation: Source
    deployments: Source
    endpoints: Source
    model_cache: Source
    plan: Source
    caller_text: str | None
    caller_refused: bool
    root: Path
    directory: Path


def read_sources(directory: Path, root: Path = REPO_ROOT) -> Sources:
    """Read the header and every source of a directory."""
    header = read_header(directory)
    caller = _read_bytes(directory, CALLER_FILE)
    plan = _read_bytes(directory, PLAN_FILE)
    try:
        caller_text = None if caller is None else caller.decode("utf-8")
        plan_source = (
            Source(PLAN_FILE, problem=ABSENT)
            if plan is None
            else Source(PLAN_FILE, value=plan.decode("utf-8"))
        )
    except UnicodeError:
        caller_text = None
        plan_source = Source(PLAN_FILE, problem=UNREADABLE)
    return Sources(
        header=header,
        capacity=_json_source(directory, CAPACITY_RECORD, CAPACITY_SCHEMA),
        provenance=_json_source(directory, PROVENANCE_FILE, None),
        reconciliation=_json_source(
            directory, RECONCILIATION_RECORD, RECONCILIATION_SCHEMA
        ),
        deployments=_json_source(directory, DEPLOYMENTS_FILE, None),
        endpoints=_json_source(directory, ENDPOINTS_RECORD, ENDPOINTS_SCHEMA),
        model_cache=_json_source(directory, MODEL_CACHE_RECORD, MODEL_CACHE_SCHEMA),
        plan=plan_source,
        caller_text=caller_text,
        caller_refused=(directory / CALLER_REFUSED_FILE).exists(),
        root=root,
        directory=directory,
    )


# --------------------------------------------------------------------------
# The derived parts of a record
# --------------------------------------------------------------------------


def _provenance_record(sources: Sources) -> Mapping[str, Any] | None:
    """The one provenance record of the directory, or nothing."""
    if not sources.provenance.read:
        return None
    records = _sequence(sources.provenance.value)
    if len(records) != 1 or _dig(records[0], "schema") != PROVENANCE_SCHEMA:
        return None
    return _mapping(records[0])


def _release_id(sources: Sources) -> str | None:
    value = _dig(_provenance_record(sources), "release", "releaseId")
    return value if _text(value, _HEX64) else None


def _deployment(sources: Sources, component: str) -> list[Mapping[str, Any]]:
    """The Deployments of the release with one component label."""
    if not sources.deployments.read:
        return []
    found = []
    for item in _sequence(_dig(sources.deployments.value, "items")):
        labels = _mapping(_dig(item, "metadata", "labels"))
        if (
            _dig(item, "kind") in (None, "Deployment")
            and labels.get("app.kubernetes.io/instance") == RELEASE_INSTANCE
            and labels.get("app.kubernetes.io/component") == component
        ):
            found.append(_mapping(item))
    return found


def _container_image(deployment: Mapping[str, Any], name: str) -> list[object]:
    containers = _sequence(_dig(deployment, "spec", "template", "spec", "containers"))
    return [_dig(item, "image") for item in containers if _dig(item, "name") == name]


def _pins(
    sources: Sources,
) -> tuple[Outcome | None, dict[str, Any] | None, str | None]:
    """The pinned model and runtime image reference, read from the copies.

    Each copy must have the content that the freeze record of the checkout pins
    for its file: the revision that the header names. The first member is the
    outcome of a copy that is absent or of other content, and None when both
    copies are usable.
    """
    try:
        record = json.loads(
            (sources.root / _freeze_record(sources)).read_text(encoding="utf-8")
        )
        pinned = {
            item["path"]: item["sha256"] for item in _sequence(record["pinnedInputs"])
        }
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return (
            (NOT_OBSERVED, "the checkout holds no readable freeze record"),
            None,
            None,
        )
    documents: dict[str, Any] = {}
    for copy, original in (
        (MODEL_SOURCE_COPY, MODEL_SOURCE_FILE),
        (RUNTIME_PACKAGE_COPY, RUNTIME_PACKAGE_FILE),
    ):
        data = _read_bytes(sources.directory, copy)
        if data is None:
            return (
                (NOT_OBSERVED, f"{copy} is absent: the copy was not made"),
                None,
                None,
            )
        if pinned.get(original) != lf_digest(data):
            return (
                (NOT_HELD, f"{copy} differs from the content the freeze record pins"),
                None,
                None,
            )
        try:
            documents[copy] = json.loads(data.decode("utf-8"))
        except (UnicodeError, ValueError):
            return (NOT_HELD, f"{copy} is unreadable"), None, None
    try:
        source = documents[MODEL_SOURCE_COPY]
        model = {
            "repository": source["repository"],
            "revision": source["revision"],
            "fileName": source["file"],
            "sha256": source["sha256"],
            "sizeBytes": source["expectedSizeBytes"],
        }
        reference = documents[RUNTIME_PACKAGE_COPY]["container"]["imageReference"]
    except (KeyError, TypeError):
        return (NOT_HELD, "a pin copy states no model or no runtime image"), None, None
    if not _text(reference, _IMAGE):
        return (
            (NOT_HELD, "the runtime image pin is not a reference by digest"),
            None,
            None,
        )
    return None, model, reference


def environment_identity(sources: Sources) -> dict[str, Any] | None:
    """The exact environment identity, revision 1, read from the capacity record.

    It is the provider, the server version, each node with its kubelet version
    and what it allocates, and the container engine, with the memory figures of
    the node and of the engine to the byte. It holds no address, no context name,
    and no path. Nothing is stated when one part is not readable. The records of
    revision 1 of the Q1 freeze record state it, and q1-1 is one of them.
    """
    return _identity(
        sources,
        engine_members=("cpus", "memoryBytes"),
        allocatable_members=("cpuMillis", "memoryBytes", "pods"),
    )


def stable_environment_identity(sources: Sources) -> dict[str, Any] | None:
    """The stable environment identity, revision 2, read from the capacity record.

    It is the provider, the server version, each node with its kubelet version
    and the CPU and the pods that it allocates, and the CPU count of the container
    engine: facts of the configuration of the environment, which a start of the
    virtual machine does not change. It holds no memory figure. Memory is a
    capacity fact: each reading states it, and the capacity gate decides for each
    reading whether the declared limits fit. It holds no address, no context name,
    and no path. Nothing is stated when one part is not readable.
    """
    identity = _identity(
        sources,
        engine_members=("cpus",),
        allocatable_members=("cpuMillis", "pods"),
    )
    if identity is None:
        return None
    return {**identity, IDENTITY_REVISION_MEMBER: STABLE_IDENTITY_REVISION}


def _identity(
    sources: Sources,
    *,
    engine_members: tuple[str, ...],
    allocatable_members: tuple[str, ...],
) -> dict[str, Any] | None:
    """The parts of an environment identity that name the given figures."""
    if not sources.capacity.read:
        return None
    record = sources.capacity.value
    environment = _mapping(_dig(record, "environment"))
    provider = environment.get("provider")
    version = environment.get("kubernetesServerVersion")
    engine = _mapping(environment.get("containerEngine"))
    if not _text(provider, _CATEGORY) or not _text(version, _VERSION):
        return None
    engine_figures = {name: _count(engine.get(name)) for name in engine_members}
    if None in engine_figures.values():
        return None
    nodes = []
    for node in _sequence(_dig(record, "nodes")):
        allocatable = _mapping(_dig(node, "allocatable"))
        figures = {name: _count(allocatable.get(name)) for name in allocatable_members}
        name = _dig(node, "name")
        kubelet = _dig(node, "kubeletVersion")
        if (
            None in figures.values()
            or not _text(name, _NAME)
            or not _text(kubelet, _VERSION)
        ):
            return None
        nodes.append({"name": name, "kubeletVersion": kubelet, "allocatable": figures})
    if not nodes:
        return None
    return {
        "provider": provider,
        "kubernetesServerVersion": version,
        "nodes": sorted(nodes, key=lambda item: item["name"]),
        "containerEngine": engine_figures,
    }


def environment_digest(environment: Mapping[str, Any]) -> str:
    """The SHA-256 of the canonical JSON text of an environment identity.

    A stable identity holds the member ``identityRevision`` and an exact identity
    holds the two memory figures, so no identity of one revision has the digest
    of an identity of the other.
    """
    text = json.dumps(environment, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Revision:
    """What one revision of the Q1 freeze record decides that another does not."""

    freeze_record: str
    identity: Callable[[Sources], dict[str, Any] | None]
    does_not_establish: tuple[str, ...]


#: Each revision of the Q1 freeze record that a header may name.
REVISIONS: Final[Mapping[str, Revision]] = MappingProxyType(
    {
        FREEZE_RECORD_R1: Revision(
            FREEZE_RECORD_R1, environment_identity, DOES_NOT_ESTABLISH_R1
        ),
        FREEZE_RECORD: Revision(
            FREEZE_RECORD, stable_environment_identity, DOES_NOT_ESTABLISH
        ),
    }
)


def identity_of(freeze_record: str) -> Callable[[Sources], dict[str, Any] | None]:
    """The environment identity that the records of a Q1 freeze revision state.

    Raises:
        KeyError: ``freeze_record`` is not a revision of the Q1 freeze record.
    """
    return REVISIONS[freeze_record].identity


def _freeze_record(sources: Sources) -> str:
    """The revision that the header names, or the current one when it names none."""
    named = sources.header.get("freezeRecord")
    return named if isinstance(named, str) and named in REVISIONS else FREEZE_RECORD


def _revision(sources: Sources) -> Revision:
    return REVISIONS[_freeze_record(sources)]


def _bounded(value: object, pattern: re.Pattern[str]) -> object:
    return value if _text(value, pattern) else None


def identities(sources: Sources) -> dict[str, Any]:
    """The immutable identities of the qualification. Unread ones are null."""
    header = sources.header
    provenance = _provenance_record(sources)
    release = _mapping(_dig(provenance, "release"))
    binding = _mapping(release.get("environmentBinding"))
    chart = _mapping(_dig(provenance, "chart"))
    expected = _mapping(_dig(sources.model_cache.value, "expected"))
    model = _mapping(expected.get("model"))
    image = _mapping(expected.get("runtimeImage"))
    capacity_environment = _mapping(_dig(sources.capacity.value, "environment"))
    profile: Mapping[str, Any] = {}
    if sources.caller_text is not None:
        first = sources.caller_text.split("\n", 1)[0]
        try:
            profile = _mapping(_dig(json.loads(first), "profile"))
        except ValueError:
            profile = {}
    return {
        "executingCommit": header["executingCommit"],
        "desiredStateRevision": header["desiredRevision"],
        "releaseKey": _bounded(_dig(provenance, "desiredState", "key"), _KEY),
        "releaseId": _bounded(release.get("releaseId"), _HEX64),
        "workloadVersion": _bounded(
            release.get("workloadVersion"), re.compile(r"[0-9a-z.+-]{1,64}")
        ),
        "contractSha256": _bounded(release.get("contractSha256"), _HEX64),
        "helmValuesSha256": _bounded(release.get("valuesSha256"), _HEX64),
        "environmentBinding": {
            "name": _bounded(binding.get("name"), _CATEGORY),
            "sha256": _bounded(binding.get("sha256"), _HEX64),
        },
        "rendererRevision": _bounded(release.get("rendererRevision"), _REVISION),
        "platformDefaultsRevision": _bounded(
            release.get("platformDefaultsRevision"), _REVISION
        ),
        "chart": {
            "name": _bounded(chart.get("name"), _CATEGORY),
            "version": _bounded(
                chart.get("version"), re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
            ),
        },
        "deliveryControllerVersion": header["controllerVersion"],
        "apiImageDigest": header["apiImageDigest"],
        "runtimeImage": {
            "reference": _bounded(image.get("reference"), _IMAGE),
            "digest": _bounded(image.get("digest"), _DIGEST),
        },
        "model": {
            "repository": _bounded(
                model.get("repository"),
                re.compile(r"[A-Za-z0-9._-]{1,96}/[A-Za-z0-9._-]{1,96}"),
            ),
            "revision": _bounded(model.get("revision"), _REVISION),
            "fileName": _bounded(
                model.get("fileName"), re.compile(r"[A-Za-z0-9._-]{1,128}")
            ),
            "sha256": _bounded(model.get("sha256"), _DIGEST),
            "sizeBytes": _count(model.get("sizeBytes")),
        },
        "kubernetes": {
            "provider": _bounded(capacity_environment.get("provider"), _CATEGORY),
            "serverVersion": _bounded(
                capacity_environment.get("kubernetesServerVersion"), _VERSION
            ),
        },
        "callerProfile": {
            "profileId": _bounded(
                profile.get("profileId"), re.compile(r"RP-[0-9]{1,3}")
            ),
            "profileRevision": _count(profile.get("profileRevision")),
            "profileSha256": _bounded(profile.get("profileSha256"), _HEX64),
        },
        "freezeRecord": {
            "path": header["freezeRecord"],
            "contentSha256": header["freezeRecordSha256"],
        },
    }


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------

Outcome = tuple[str, str]


def _missing(source: Source) -> Outcome:
    if source.problem == ABSENT:
        return NOT_OBSERVED, f"{source.name} is absent: the read was not made"
    return NOT_HELD, f"{source.name} is {source.problem}"


def _target_reached(sources: Sources) -> Outcome:
    refusal = sources.header["targetRefusal"]
    if refusal is not None:
        return NOT_HELD, f"the target check refused with the category {refusal}"
    if not sources.capacity.read:
        return _missing(sources.capacity)
    return HELD, "no refusal; the capacity collection read the selected target"


def _provider_selected(sources: Sources) -> Outcome:
    header = sources.header
    refusal = header["targetRefusal"]
    if header["provider"] != SELECTED_PROVIDER:
        return (
            NOT_HELD,
            f"the header selects {header['provider']}, not {SELECTED_PROVIDER}",
        )
    if refusal in PROVIDER_REFUSALS:
        return NOT_HELD, f"the target check refused with the category {refusal}"
    named = {
        CAPACITY_RECORD + " collection": _dig(
            sources.capacity.value, "collection", "provider"
        ),
        CAPACITY_RECORD + " environment": _dig(
            sources.capacity.value, "environment", "provider"
        ),
        ENDPOINTS_RECORD: _dig(sources.endpoints.value, "collection", "provider"),
        MODEL_CACHE_RECORD: _dig(sources.model_cache.value, "collection", "provider"),
        RECONCILIATION_RECORD: _dig(
            sources.reconciliation.value, "collection", "provider", "value"
        ),
    }
    read = {name: value for name, value in named.items() if value is not None}
    wrong = sorted(name for name, value in read.items() if value != SELECTED_PROVIDER)
    if wrong:
        return NOT_HELD, f"another provider is named by: {', '.join(wrong)}"
    if len(read) != len(named):
        absent = sorted(set(named) - set(read))
        return NOT_OBSERVED, f"no provider was read from: {', '.join(absent)}"
    return HELD, f"every source names {SELECTED_PROVIDER}"


def _context_unambiguous(sources: Sources) -> Outcome:
    refusal = sources.header["targetRefusal"]
    if refusal in AMBIGUOUS_REFUSALS:
        return NOT_HELD, f"the target check refused with the category {refusal}"
    if sources.header["upRefusal"] == "release-present":
        return (
            NOT_HELD,
            "the cluster held the release namespace or the controller namespace "
            "before the phase up",
        )
    if not sources.capacity.read:
        return _missing(sources.capacity)
    context = _dig(sources.capacity.value, "collection", "context")
    if context != EXPECTED_CONTEXT:
        return NOT_HELD, "the capacity collection names another context"
    nodes = [
        _dig(node, "name") for node in _sequence(_dig(sources.capacity.value, "nodes"))
    ]
    if len(nodes) != 1:
        return NOT_HELD, f"the capacity record holds {len(nodes)} nodes, not 1"
    if _revision(sources).identity(sources) is None:
        return NOT_HELD, "the capacity record states no readable environment identity"
    if not sources.model_cache.read:
        return _missing(sources.model_cache)
    placed = list(_sequence(_dig(sources.model_cache.value, "placement", "nodes")))
    if placed != nodes:
        return (
            NOT_HELD,
            "the runtime pods run on a node that the capacity record does not hold",
        )
    return HELD, "one target, one node, and the runtime pods run on it"


def _working_tree_clean(sources: Sources) -> Outcome:
    state = sources.header["workingTree"]
    if sources.header["upRefusal"] == "working-tree":
        return NOT_HELD, "the working tree was not clean when the phase up started"
    if state == "clean":
        return HELD, "the working tree was clean"
    if state == "unread":
        return NOT_OBSERVED, "the working tree was not read"
    return NOT_HELD, "the working tree differed from the executing commit"


def _procedure_frozen(sources: Sources) -> Outcome:
    header = sources.header
    if header["freezeRecord"] not in FREEZE_RECORDS:
        return (
            NOT_HELD,
            f"the driver names {header['freezeRecord']}, not {FREEZE_RECORD}",
        )
    if header["freezeChanges"] == "listed" or header["upRefusal"] == "frozen-inputs":
        return NOT_HELD, "the freeze tool listed a changed material file"
    if header["freezeChanges"] == "unread" or header["freezeRecordSha256"] is None:
        return NOT_OBSERVED, "the freeze check or the record digest was not read"
    try:
        held = lf_digest((sources.root / header["freezeRecord"]).read_bytes())
    except OSError:
        return NOT_OBSERVED, "the checkout holds no freeze record to compare"
    if held != header["freezeRecordSha256"]:
        return NOT_HELD, "the freeze record differs from the one the checkout holds"
    return HELD, "the freeze record is the checkout's, and no material file changed"


def _desired_revision_known(sources: Sources) -> Outcome:
    header = sources.header
    revision = header["desiredRevision"]
    if revision is None:
        return NOT_OBSERVED, "the desired revision was not read"
    if len(set(revision)) == 1:
        return NOT_HELD, "the desired revision is not a commit identifier"
    if header["upRefusal"] == "delivery-paths":
        return (
            NOT_HELD,
            "the delivery paths differed from the remote main when the phase up "
            "started",
        )
    if header["desiredStateDiff"] == "unread":
        return (
            NOT_OBSERVED,
            "the executing commit was not compared with the desired revision",
        )
    if header["desiredStateDiff"] == "differs":
        return (
            NOT_HELD,
            "the executing commit differs from the desired revision on a delivery path",
        )
    return (
        HELD,
        "the delivery paths of the executing commit equal those of the desired revision",
    )


def _one_executing_commit(sources: Sources) -> Outcome:
    commit = sources.header["executingCommit"]
    named = {
        CAPACITY_RECORD: (sources.capacity, ("collection", "executingCommit")),
        ENDPOINTS_RECORD: (sources.endpoints, ("collection", "executingCommit")),
        MODEL_CACHE_RECORD: (sources.model_cache, ("collection", "executingCommit")),
        RECONCILIATION_RECORD: (
            sources.reconciliation,
            ("collection", "repositoryRevision", "value"),
        ),
    }
    wrong = []
    unread = []
    for name, (source, path) in named.items():
        if not source.read:
            unread.append(name)
        elif _dig(source.value, *path) != commit:
            wrong.append(name)
    if wrong:
        return NOT_HELD, f"another commit is named by: {', '.join(sorted(wrong))}"
    if unread:
        return NOT_OBSERVED, f"not read: {', '.join(sorted(unread))}"
    return HELD, "each collection names the executing commit"


def _release_provenance_resolved(sources: Sources) -> Outcome:
    if not sources.provenance.read:
        return _missing(sources.provenance)
    record = _provenance_record(sources)
    if record is None:
        return NOT_HELD, f"{PROVENANCE_FILE} is not a list of one provenance record"
    if sources.header["desiredRevision"] is None:
        return NOT_OBSERVED, "the desired revision was not read"
    if _dig(record, "git", "revision") != sources.header["desiredRevision"]:
        return NOT_HELD, "the provenance record resolves another revision"
    key = _dig(record, "desiredState", "key")
    if key != TARGET_RELEASE_KEY or sources.header["releaseKey"] != TARGET_RELEASE_KEY:
        return NOT_HELD, f"the release key is not {TARGET_RELEASE_KEY}"
    if _release_id(sources) is None:
        return NOT_HELD, "the provenance record states no release identifier"
    return HELD, f"release {_release_id(sources)} at the desired revision"


def _capacity_accepted(sources: Sources) -> Outcome:
    if not sources.capacity.read:
        return _missing(sources.capacity)
    record = sources.capacity.value
    if _dig(record, "collection", "releaseKey") != TARGET_RELEASE_KEY:
        return NOT_HELD, f"the capacity record is not of {TARGET_RELEASE_KEY}"
    topology = _mapping(_dig(record, "footprint", "topology"))
    if (topology.get("apiReplicas"), topology.get("runtimeReplicas")) != (
        TARGET_API_REPLICAS,
        TARGET_RUNTIME_REPLICAS,
    ):
        return NOT_HELD, "the capacity footprint is not of 2 API and 2 runtime replicas"
    result = _dig(record, "result")
    if result != "ACCEPTED":
        categories = ", ".join(
            str(item) for item in _sequence(_dig(record, "refusal", "categories"))
        )
        return (
            NOT_HELD,
            f"the capacity gate result is {result} ({categories or 'no category'})",
        )
    return HELD, "ACCEPTED for 2 API and 2 runtime replicas"


def _controller_identified(sources: Sources) -> Outcome:
    header = sources.header
    if header["controllerVerified"] is False:
        return NOT_HELD, "the verification of the delivery controller did not exit 0"
    if header["controllerVerified"] is None or header["controllerVersion"] is None:
        return NOT_OBSERVED, "the controller verification or version was not read"
    return HELD, f"verified, version {header['controllerVersion']}"


def _sample_problem(sample: object, revision: str, release_id: str) -> str | None:
    if _dig(sample, "settled", "value") is not True:
        return "not settled"
    if _dig(sample, "fields", "resolvedRevision", "value") != revision:
        return "settled at another revision"
    consistency = _mapping(_dig(sample, "consistency"))
    if consistency.get("state") != "provenance-resolved":
        return "no provenance comparison"
    if consistency.get("releaseId") != release_id:
        return "resolved to another release"
    for part in ("revisions", "source", "labels"):
        section = _mapping(consistency.get(part))
        if section.get("state") != "compared" or _sequence(section.get("findings")):
            return f"the {part} comparison is not compared with no finding"
    return None


def _controller_reconciled(sources: Sources) -> Outcome:
    if not sources.reconciliation.read:
        return _missing(sources.reconciliation)
    revision = sources.header["desiredRevision"]
    release_id = _release_id(sources)
    if revision is None or release_id is None:
        return NOT_OBSERVED, "no desired revision or provenance release to compare"
    record = sources.reconciliation.value
    if _dig(record, "collection", "complete") is not True:
        return NOT_HELD, "the reconciliation collection is not complete"
    samples = list(_sequence(_dig(record, "samples")))
    if len(samples) < MINIMUM_RECONCILIATION_SAMPLES:
        return NOT_HELD, (
            f"{len(samples)} samples, fewer than {MINIMUM_RECONCILIATION_SAMPLES}"
        )
    for index, sample in enumerate(samples, start=1):
        problem = _sample_problem(sample, revision, release_id)
        if problem is not None:
            return NOT_HELD, f"sample {index}: {problem}"
    return HELD, f"{len(samples)} samples settled at the desired revision and release"


def _deployment_problem(deployment: Mapping[str, Any], replicas: int) -> str | None:
    status = _mapping(deployment.get("status"))
    if _dig(deployment, "spec", "replicas") != replicas:
        return f"states {_dig(deployment, 'spec', 'replicas')} replicas"
    for member in ("replicas", "readyReplicas", "availableReplicas", "updatedReplicas"):
        if status.get(member) != replicas:
            return f"reports {member} {status.get(member)}"
    generation = _dig(deployment, "metadata", "generation")
    if _count(generation) is None or status.get("observedGeneration") != generation:
        return "reports a generation that is not its current one"
    return None


def _deployments_ready(sources: Sources) -> Outcome:
    if sources.header["upRefusal"] == "preparation-failed":
        return NOT_HELD, "the phase up failed before the release was applied"
    if not sources.deployments.read:
        return _missing(sources.deployments)
    if not isinstance(_dig(sources.deployments.value, "items"), list):
        return NOT_HELD, f"{DEPLOYMENTS_FILE} is not a list of Deployments"
    for component, replicas in (
        ("platform-api", TARGET_API_REPLICAS),
        ("serving-runtime", TARGET_RUNTIME_REPLICAS),
    ):
        found = _deployment(sources, component)
        if len(found) != 1:
            return NOT_HELD, f"{len(found)} {component} Deployments, not 1"
        problem = _deployment_problem(found[0], replicas)
        if problem is not None:
            return NOT_HELD, f"the {component} Deployment {problem}"
    return HELD, "each Deployment states and reports 2 Ready replicas"


def _endpoints_ready(sources: Sources) -> Outcome:
    if not sources.endpoints.read:
        return _missing(sources.endpoints)
    record = sources.endpoints.value
    if _dig(record, "result") != "OBSERVED":
        return NOT_HELD, f"the endpoint record is {_dig(record, 'result')}"
    tiers = {
        _dig(tier, "tier"): _mapping(tier)
        for tier in _sequence(_dig(record, "tiers"))
        if isinstance(_dig(tier, "tier"), str)
    }
    for tier, expected in (
        ("platform-api", TARGET_API_REPLICAS),
        ("serving-runtime", TARGET_RUNTIME_REPLICAS),
    ):
        held = tiers.get(tier, {})
        if held.get("state") != "observed":
            return NOT_HELD, f"the {tier} tier is not observed"
        endpoints = _mapping(held.get("endpoints"))
        if endpoints.get("total") != expected or endpoints.get("ready") != expected:
            return NOT_HELD, (
                f"the {tier} Service has {endpoints.get('ready')} Ready of "
                f"{endpoints.get('total')} endpoints"
            )
    return HELD, "each Service has 2 endpoints, both Ready"


def _images_declared(sources: Sources) -> Outcome:
    digest = sources.header["apiImageDigest"]
    problem, _, runtime_image = _pins(sources)
    if digest is None:
        return NOT_OBSERVED, "the driver states no API image digest"
    if problem is not None or runtime_image is None:
        return problem or (NOT_OBSERVED, "no runtime image pin was read")
    if not sources.deployments.read:
        return _missing(sources.deployments)
    api = _deployment(sources, "platform-api")
    runtime = _deployment(sources, "serving-runtime")
    if len(api) != 1 or len(runtime) != 1:
        return NOT_HELD, "the release does not hold one API and one runtime Deployment"
    api_images = _container_image(api[0], "api")
    if len(api_images) != 1 or not _text(api_images[0], _IMAGE):
        return NOT_HELD, "the API Deployment does not run one api container by digest"
    if not str(api_images[0]).endswith("@" + digest):
        return NOT_HELD, "the api container runs another digest than the declared one"
    if _container_image(runtime[0], "runtime") != [runtime_image]:
        return NOT_HELD, "the runtime container does not run the pinned runtime image"
    return HELD, "the declared API digest and the pinned runtime image"


def _model_identity_verified(sources: Sources) -> Outcome:
    if not sources.model_cache.read:
        return _missing(sources.model_cache)
    problem, model_pin, image_pin = _pins(sources)
    if problem is not None or model_pin is None or image_pin is None:
        return problem or (NOT_OBSERVED, "no model pin was read")
    record = sources.model_cache.value
    expected = _mapping(_dig(record, "expected"))
    if _dig(expected, "release", "key") != TARGET_RELEASE_KEY:
        return NOT_HELD, f"the model cache record is not of {TARGET_RELEASE_KEY}"
    if expected.get("runtimeReplicas") != TARGET_RUNTIME_REPLICAS:
        return NOT_HELD, "the model cache record does not expect 2 runtime replicas"
    if dict(_mapping(expected.get("model"))) != model_pin:
        return NOT_HELD, f"the expected model differs from {MODEL_SOURCE_FILE}"
    if _dig(expected, "runtimeImage", "reference") != image_pin:
        return (
            NOT_HELD,
            f"the expected runtime image differs from {RUNTIME_PACKAGE_FILE}",
        )
    states = {
        _dig(rule, "id"): _dig(rule, "state")
        for rule in _sequence(_dig(record, "rules"))
        if isinstance(_dig(rule, "id"), str)
    }
    not_held = [rule for rule in MODEL_CACHE_RULES if states.get(rule) != "held"]
    if not_held:
        return NOT_HELD, f"model cache rules not held: {', '.join(not_held)}"
    return (
        HELD,
        f"{len(MODEL_CACHE_RULES)} model identity rules held for the pinned model",
    )


def _caller_completed(sources: Sources) -> Outcome:
    if sources.caller_refused:
        return NOT_HELD, "the runner script kept the caller record as refused"
    if sources.caller_text is None:
        return NOT_OBSERVED, f"{CALLER_FILE} is absent: the read was not made"
    if not sources.plan.read:
        return _missing(sources.plan)
    try:
        record = read_record(sources.caller_text, plan=sources.plan.value)
    except RunnerError as error:
        return NOT_HELD, f"the runner's reader refused the record: {error.rule}"
    header = record.header
    if header["mode"] != "in-cluster":
        return NOT_HELD, f"the record is of the mode {header['mode']}"
    if header["experimentId"] != EXPERIMENT_ID:
        return NOT_HELD, f"the record is of the experiment {header['experimentId']}"
    if header["runId"] != sources.header["qualificationId"]:
        return NOT_HELD, "the record is of another run identifier"
    release_id = _release_id(sources)
    if release_id is None:
        return NOT_OBSERVED, "no provenance release to compare"
    if _dig(header, "release", "releaseId") != release_id:
        return NOT_HELD, "the record declares another release"
    if record.end["endState"] not in CALLER_END_STATES:
        return NOT_HELD, f"the run ended with {record.end['endState']}"
    successes = record.end["outcomes"].get("success", 0)
    if successes < 1:
        return NOT_HELD, "no request has the outcome success"
    return (
        HELD,
        f"{successes} of {len(record.requests)} requests have the outcome success",
    )


def _readings_in_order(sources: Sources) -> Outcome:
    start = _instant(sources.header["startedAt"])
    end = _instant(sources.header["finishedAt"])
    if start is None or end is None or end < start:
        return NOT_HELD, "the qualification ends before it starts"
    capacity = _instant(_dig(sources.capacity.value, "collection", "collectedAt"))
    caller_start = None
    if sources.caller_text is not None:
        try:
            caller_start = _instant(
                _dig(json.loads(sources.caller_text.split("\n", 1)[0]), "startedAt")
            )
        except ValueError:
            caller_start = None
    samples = _sequence(_dig(sources.reconciliation.value, "samples"))
    instants = [_instant(_dig(sample, "observedAt", "value")) for sample in samples]
    observed = [] if None in instants else [item for item in instants if item]
    inside = {
        ENDPOINTS_RECORD: _instant(
            _dig(sources.endpoints.value, "collection", "readStartedAt")
        ),
        MODEL_CACHE_RECORD: _instant(
            _dig(sources.model_cache.value, "collection", "collectedAt")
        ),
        CALLER_FILE: caller_start,
        RECONCILIATION_RECORD + " first sample": min(observed) if observed else None,
        RECONCILIATION_RECORD + " last sample": max(observed) if observed else None,
    }
    if capacity is None or None in inside.values():
        absent = sorted(name for name, value in inside.items() if value is None)
        if capacity is None:
            absent.insert(0, CAPACITY_RECORD)
        return NOT_OBSERVED, f"no instant was read from: {', '.join(absent)}"
    if capacity > start:
        return NOT_HELD, "the capacity reading does not precede the qualification"
    outside = sorted(
        name
        for name, value in inside.items()
        if value is not None and not start <= value <= end
    )
    if outside:
        return NOT_HELD, f"outside the qualification: {', '.join(outside)}"
    return HELD, "the capacity reading precedes, and each other reading lies inside"


_EVALUATORS: Final[dict[str, Callable[[Sources], Outcome]]] = {
    "target-reached": _target_reached,
    "provider-selected": _provider_selected,
    "context-unambiguous": _context_unambiguous,
    "working-tree-clean": _working_tree_clean,
    "procedure-frozen": _procedure_frozen,
    "desired-revision-known": _desired_revision_known,
    "one-executing-commit": _one_executing_commit,
    "release-provenance-resolved": _release_provenance_resolved,
    "capacity-accepted": _capacity_accepted,
    "controller-identified": _controller_identified,
    "controller-reconciled": _controller_reconciled,
    "deployments-ready": _deployments_ready,
    "endpoints-ready": _endpoints_ready,
    "images-declared": _images_declared,
    "model-identity-verified": _model_identity_verified,
    "caller-completed": _caller_completed,
    "readings-in-order": _readings_in_order,
}


def evaluate(sources: Sources) -> list[dict[str, str]]:
    """The state of each rule, in the order of :data:`RULES`."""
    findings = []
    for rule in RULES:
        state, detail = _EVALUATORS[rule.rule_id](sources)
        findings.append(
            {
                "ruleId": rule.rule_id,
                "criterion": rule.criterion,
                "category": rule.category,
                "statement": rule.statement,
                "state": state,
                "detail": detail,
            }
        )
    return findings


def result_of(findings: Sequence[Mapping[str, str]]) -> str:
    """QUALIFIED when each rule is held, and REFUSED otherwise."""
    return QUALIFIED if all(item["state"] == HELD for item in findings) else REFUSED


def _files(directory: Path) -> list[dict[str, str]]:
    files = []
    for name in SOURCE_FILES:
        data = _read_bytes(directory, name)
        if data is not None:
            files.append({"name": name, "sha256": lf_digest(data)})
    return files


def build_record(directory: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    """The record of one qualification directory."""
    sources = read_sources(directory, root)
    findings = evaluate(sources)
    result = result_of(findings)
    refused = [item for item in findings if item["state"] != HELD]
    categories = [
        category
        for category in CATEGORIES
        if any(item["category"] == category for item in refused)
    ]
    revision = _revision(sources)
    environment = revision.identity(sources)
    return {
        "schema": RECORD_SCHEMA,
        "qualification": QUALIFICATION,
        "result": result,
        "refusal": {
            "categories": categories,
            "rules": [item["ruleId"] for item in refused],
        },
        "collection": dict(sources.header),
        "target": {
            "releaseKey": TARGET_RELEASE_KEY,
            "apiReplicas": TARGET_API_REPLICAS,
            "runtimeReplicas": TARGET_RUNTIME_REPLICAS,
            "provider": SELECTED_PROVIDER,
        },
        "identities": identities(sources),
        "environment": environment,
        "environmentSha256": None
        if environment is None
        else environment_digest(environment),
        "files": _files(directory),
        "findings": findings,
        "doesNotEstablish": list(revision.does_not_establish),
    }


def record_text(record: Mapping[str, Any]) -> str:
    """The text of a record: indented JSON with sorted members and one final LF."""
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def committed_runs(root: Path = REPO_ROOT) -> list[Path]:
    """Every committed qualification directory."""
    return sorted(path for path in root.glob(RUNS_PATTERN) if path.is_dir())


def check_committed(root: Path = REPO_ROOT) -> list[str]:
    """Build the record of each committed directory again. Return each difference."""
    findings = []
    for directory in committed_runs(root):
        name = directory.relative_to(root).as_posix()
        stored = _read_bytes(directory, RECORD_FILE)
        if stored is None:
            findings.append(f"{name}: no {RECORD_FILE}")
            continue
        try:
            built = record_text(build_record(directory, root))
        except CollectionRefused as refused:
            findings.append(f"{name}: not a collection: {refused}")
            continue
        if stored.replace(b"\r\n", b"\n").decode("utf-8") != built:
            findings.append(f"{name}: {RECORD_FILE} is not what the directory gives")
    return findings


__all__ = [
    "AMBIGUOUS_REFUSALS",
    "CALLER_END_STATES",
    "CALLER_FILE",
    "CALLER_REFUSED_FILE",
    "CAPACITY_RECORD",
    "CATEGORIES",
    "COLLECTION_SCHEMA",
    "DEPLOYMENTS_FILE",
    "DOES_NOT_ESTABLISH",
    "DOES_NOT_ESTABLISH_R1",
    "ENDPOINTS_RECORD",
    "EXPECTED_CONTEXT",
    "EXPERIMENT_ID",
    "FREEZE_RECORD",
    "FREEZE_RECORDS",
    "FREEZE_RECORD_R1",
    "HEADER_FILE",
    "HELD",
    "IDENTITY_REVISION_MEMBER",
    "MINIMUM_RECONCILIATION_SAMPLES",
    "MODEL_CACHE_RECORD",
    "MODEL_CACHE_RULES",
    "MODEL_SOURCE_COPY",
    "MODEL_SOURCE_FILE",
    "NOT_HELD",
    "NOT_OBSERVED",
    "PLAN_FILE",
    "PROVENANCE_FILE",
    "PROVIDER_REFUSALS",
    "QUALIFICATION",
    "QUALIFIED",
    "RECONCILIATION_RECORD",
    "RECORD_FILE",
    "RECORD_SCHEMA",
    "REFUSED",
    "REFUSED_EXIT",
    "REPO_ROOT",
    "RESULT_STATES",
    "REVISIONS",
    "RULES",
    "RULE_STATES",
    "RUNS_PATTERN",
    "RUNTIME_PACKAGE_COPY",
    "RUNTIME_PACKAGE_FILE",
    "SELECTED_PROVIDER",
    "SOURCE_FILES",
    "STABLE_IDENTITY_REVISION",
    "TARGET_API_REPLICAS",
    "TARGET_RELEASE_KEY",
    "TARGET_RUNTIME_REPLICAS",
    "UP_REFUSALS",
    "CollectionRefused",
    "Revision",
    "Rule",
    "Source",
    "Sources",
    "build_record",
    "check_committed",
    "committed_runs",
    "environment_digest",
    "environment_identity",
    "evaluate",
    "identities",
    "identity_of",
    "lf_digest",
    "read_header",
    "read_sources",
    "record_text",
    "result_of",
    "stable_environment_identity",
]
