"""What the serving runtime replicas read from the model cache, as an evidence record.

A run driver reads a cluster and writes what each read returned into one
directory: the runtime pods, the claims and volumes, each pod's verification log,
each runtime container's mount table, the identity of the artifact file each
container sees, what each runtime reported about its model, and the outcome of
one completion that each runtime answered. This module reads that directory. It
reads no cluster. It returns one record.

**The expected identity comes from committed files, and not from the cluster.**
:func:`expected_identity` reads the desired-state release, the chart's defaults,
and the two pin records. A run stores that document in its directory before it
reads a pod, and :func:`build_record` compares every read with it.

**A read that was not made is not a value.** A file that the directory does not
hold, and a file that cannot be parsed, give ``not-read``. A rule that needs such
a read is ``not-observed``. It is never ``held``.

**Each rule has one of three states.** ``held`` and ``not-held`` are what the
reads show. ``not-observed`` means that a read the rule needs is absent. The
result is ``REFUSED`` when the capacity preflight refused and no pod was read,
``FAILED`` when one rule is not held, ``INCONCLUSIVE`` when no rule is not held
and one required rule was not observed, and ``PASSED`` when every required rule
is held.

**A rule that compares replicas needs two replicas.** One pod agrees with
itself. With fewer than two pods, each comparing rule is ``not-observed``.

See docs/environment/runtime-model-cache-observation.md, which describes the
collection, the rules, and what a record does not establish.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from tools.generated_release import REPO_ROOT, DeclaredRelease
from tools.gitops_desired_state import DESIRED_STATE_RELEASES, release_key

__all__ = [
    "CAPACITY_REFUSED_EXIT",
    "COLLECTION_SCHEMA",
    "DOES_NOT_ESTABLISH",
    "EXPECTED_SCHEMA",
    "HELD",
    "NOT_HELD",
    "NOT_OBSERVED",
    "RECORD_FILE",
    "RECORD_SCHEMA",
    "REPO_ROOT",
    "RESULT_STATES",
    "RULES",
    "RUNS_PATTERN",
    "RUNTIME_COMPONENT",
    "CollectionRefused",
    "ExpectedRefused",
    "Rule",
    "build_record",
    "cache_sub_path",
    "check_committed_runs",
    "committed_runs",
    "evaluate",
    "expected_identity",
    "pin_findings",
    "record_text",
    "result_state",
]

#: The identifier of the record :func:`build_record` returns.
RECORD_SCHEMA: Final = "inferops.io/runtime-model-cache-observation/v1alpha1"

#: The identifier of the document :func:`expected_identity` returns.
EXPECTED_SCHEMA: Final = "inferops.io/runtime-model-cache-expected/v1alpha1"

#: The identifier of the header a driver writes into a collection.
COLLECTION_SCHEMA: Final = "inferops.io/runtime-model-cache-collection/v1alpha1"

#: The component label of a serving runtime pod, as the chart renders it.
RUNTIME_COMPONENT: Final = "serving-runtime"

#: The file a committed run holds its record in.
RECORD_FILE: Final = "record.v1alpha1.json"

#: Where this repository holds a run: each directory that matches is one run.
#: A run is added by committing its directory. No list names it, so the tool's
#: bytes are the same before a run and after it.
RUNS_PATTERN: Final = "docs/proof/environment/*-runtime-model-cache-run-*"

#: The exit status with which the V1 capacity preflight refuses a host.
CAPACITY_REFUSED_EXIT: Final = 5

HELD: Final = "held"
NOT_HELD: Final = "not-held"
NOT_OBSERVED: Final = "not-observed"

PASSED: Final = "PASSED"
FAILED: Final = "FAILED"
INCONCLUSIVE: Final = "INCONCLUSIVE"
REFUSED: Final = "REFUSED"

#: The result states of a record.
RESULT_STATES: Final = (PASSED, FAILED, INCONCLUSIVE, REFUSED)

_RUNTIME_CONTAINER: Final = "runtime"
_VERIFY_CONTAINER: Final = "verify-model"
_CACHE_VOLUME: Final = "model-cache"
_COMPONENT_LABEL: Final = "app.kubernetes.io/component"
_INSTANCE_LABEL: Final = "app.kubernetes.io/instance"
_MANAGED_BY_LABEL: Final = "app.kubernetes.io/managed-by"
_LIFECYCLE_LABEL: Final = "inferops.io/lifecycle"
_CHART_LABEL: Final = "helm.sh/chart"
_RELEASE_ANNOTATION: Final = "meta.helm.sh/release-name"
_VERIFIED_LINE: Final = "model artifact verified: byte count and SHA-256"
_POD_NAME: Final = re.compile(r"[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?")
_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}")
_MODEL_SOURCE: Final = "docs/serving/model-source.v1.json"
_RUNTIME_PACKAGE: Final = "deploy/serving/runtime/container-package.v1.json"
_TEXT_LIMIT: Final = 240


@dataclass(frozen=True)
class Rule:
    """One statement a record decides, and whether the result needs it."""

    rule_id: str
    statement: str
    required: bool = True


#: Every rule of a record, in the order a record lists them.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "capacity-preflight-sufficient",
        "The V1 multi-replica capacity preflight exited 0 before the release was "
        "applied.",
    ),
    Rule(
        "replica-count",
        "The number of serving runtime pods that are not being deleted is the "
        "declared runtime replica count.",
    ),
    Rule(
        "every-replica-ready",
        "Each serving runtime pod reports the Ready condition as True.",
    ),
    Rule(
        "one-runtime-image",
        "Each runtime container declares the pinned image reference, and each "
        "reported image identifier holds the pinned digest.",
    ),
    Rule(
        "one-model-argument",
        "Each runtime container is given the expected artifact path as its model "
        "argument, and every replica is given the same alias.",
    ),
    Rule(
        "one-claim",
        "Each pod mounts the declared claim as its one persistent volume, and no "
        "pod mounts a host path.",
    ),
    Rule(
        "claim-is-the-prerequisite-claim",
        "The declared claim is Bound, carries the labels of the prerequisite "
        "layer, and carries no label or annotation of a Helm release.",
    ),
    Rule(
        "no-second-claim",
        "The namespace holds one PersistentVolumeClaim.",
    ),
    Rule(
        "read-only-declared",
        "Each pod declares the claim read only on the volume, on the runtime "
        "container's mount, and on the verification container's mount.",
    ),
    Rule(
        "read-only-in-effect",
        "The mount table of each runtime container lists the cache mount with the "
        "option ro.",
    ),
    Rule(
        "revision-scoped-mount",
        "Each of the two mounts of each pod names the expected "
        "repository-and-revision subdirectory.",
    ),
    Rule(
        "one-directory",
        "The mount table of every runtime container names one device and one "
        "root directory for the cache mount.",
    ),
    Rule(
        "one-file",
        "Every runtime container sees the artifact as one device, one inode, and "
        "the pinned byte count.",
    ),
    Rule(
        "artifact-verified-on-each-start",
        "In each pod the verification container's script holds the pinned SHA-256 "
        "and byte count, the container exited 0, and its log holds the "
        "verification line and the checksum line for the expected path.",
    ),
    Rule(
        "one-reported-model",
        "Each runtime answered its model listing with status 200 and the alias it "
        "was given, and every replica reported the same model metadata.",
    ),
    Rule(
        "every-replica-completed",
        "Each runtime answered one completion with status 200 and at least one "
        "completion token.",
    ),
    Rule(
        "not-ready-while-loading",
        "For each pod, one sample before its first Ready sample shows the runtime "
        "container running and not ready.",
        required=False,
    ),
)

#: What no record establishes. Part of every record.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "A record does not establish node-loss resilience. Kubernetes documents that "
    "pods which share a ReadWriteOnce claim run on one node. The record states "
    "the node of each pod.",
    "A record does not establish that a caller is served when one runtime pod is "
    "unavailable. No pod was removed, and no request was sent through the API "
    "Service by this collection.",
    "A record does not establish a rollout. No pod template changed during the "
    "collection.",
    "A record does not establish that readiness is false whenever inference is "
    "impossible. It states the samples in which a running runtime container was "
    "not ready, and the completion each runtime answered after it was Ready.",
    "A record does not establish which runtime replica serves a request that a "
    "caller sends. Each completion was sent to one pod through a port-forward, "
    "and not through a Service.",
    "A record does not establish behaviour on another provider, another storage "
    "class, another node count, or another day. It is one collection on one "
    "cluster.",
    "A record does not establish that the claim cannot be written. It states the "
    "declared mode and the mount option of each runtime container. No write was "
    "attempted, and the acquisition hook mounts the same claim writable.",
    "A record does not establish capacity for any other topology, and it is not "
    "a capacity gate for this one. It states one reading of the V1 preflight.",
    "A record does not establish a performance figure. No time in it is a "
    "latency, a throughput, or a model-load measurement.",
)


class ExpectedRefused(Exception):
    """The committed files do not give one expected identity."""


class CollectionRefused(Exception):
    """The directory is not a collection this module reads."""


def cache_sub_path(repository: str, revision: str) -> str:
    """The directory of one model revision inside the claim.

    Restated from the chart helper ``inferops-llm.model.cacheSubPath``. A test
    compares it with a render.
    """
    return f"{repository.replace('/', '--')}/{revision}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _declared(key: str | None) -> DeclaredRelease:
    if key is None:
        if len(DESIRED_STATE_RELEASES) != 1:
            raise ExpectedRefused("more than one desired-state release is declared")
        return DESIRED_STATE_RELEASES[0]
    for declared in DESIRED_STATE_RELEASES:
        if release_key(declared) == key:
            return declared
    raise ExpectedRefused(f"no desired-state release has the key {key!r}")


def _member(document: object, *path: str) -> Any:
    current: object = document
    for name in path:
        if not isinstance(current, Mapping) or name not in current:
            raise ExpectedRefused(f"the member {'.'.join(path)} is absent")
        current = current[name]
    return current


def expected_identity(key: str | None = None, root: Path = REPO_ROOT) -> dict[str, Any]:
    """What each runtime replica is declared to read, from committed files.

    The model pins, the runtime image, the replica count, and the claim name are
    the desired-state release's generated values. The mount path is the chart's
    default, which the release does not state. The digest of the values file is
    the SHA-256 of its bytes with every CRLF replaced by LF.
    """
    declared = _declared(key)
    values_path = f"{declared.directory}/values.generated.yaml"
    try:
        values_bytes = (root / values_path).read_bytes()
        chart_values = yaml.safe_load(
            (root / declared.platform_defaults).read_text(encoding="utf-8")
        )
    except OSError as error:
        raise ExpectedRefused(f"a committed file was not read: {error}") from error
    values = yaml.safe_load(values_bytes.decode("utf-8"))

    repository = str(_member(values, "model", "artifact", "repository"))
    revision = str(_member(values, "model", "revision"))
    file_name = str(_member(values, "model", "artifact", "fileName"))
    mount_path = str(_member(chart_values, "model", "cache", "mountPath"))
    image = _member(values, "runtime", "image")
    digest = str(_member(image, "digest"))
    replicas = _member(values, "runtime", "replicaCount")
    size = _member(values, "model", "artifact", "sizeBytes")
    for name, value in (("runtime.replicaCount", replicas), ("sizeBytes", size)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ExpectedRefused(f"{name} is not a whole number")
    return {
        "schema": EXPECTED_SCHEMA,
        "release": {
            "key": release_key(declared),
            "valuesFile": values_path,
            "valuesFileSha256": _sha256(_lf(values_bytes)),
        },
        "runtimeReplicas": replicas,
        "runtimeImage": {
            "reference": f"{_member(image, 'repository')}@{digest}",
            "digest": digest,
        },
        "model": {
            "repository": repository,
            "revision": revision,
            "fileName": file_name,
            "sha256": str(_member(values, "model", "artifact", "sha256")),
            "sizeBytes": size,
        },
        "claimName": str(_member(values, "model", "cache", "claimName")),
        "mountPath": mount_path,
        "cacheSubPath": cache_sub_path(repository, revision),
        "containerPath": f"{mount_path.rstrip('/')}/{file_name}",
    }


def pin_findings(expected: Mapping[str, Any], root: Path = REPO_ROOT) -> list[str]:
    """Each difference between an expected identity and the two pin records."""
    source = json.loads((root / _MODEL_SOURCE).read_text(encoding="utf-8"))
    package = json.loads((root / _RUNTIME_PACKAGE).read_text(encoding="utf-8"))
    model = expected["model"]
    pairs = (
        ("model.repository", model["repository"], source["repository"]),
        ("model.revision", model["revision"], source["revision"]),
        ("model.fileName", model["fileName"], source["file"]),
        ("model.sha256", model["sha256"], source["sha256"]),
        ("model.sizeBytes", model["sizeBytes"], source["expectedSizeBytes"]),
        (
            "runtimeImage.reference",
            expected["runtimeImage"]["reference"],
            package["container"]["imageReference"],
        ),
    )
    return [
        f"{name}: the release states {stated!r}, and the pin record states {pinned!r}"
        for name, stated, pinned in pairs
        if stated != pinned
    ]


# --------------------------------------------------------------------------
# Reading a collection
# --------------------------------------------------------------------------


def _read(directory: Path, name: str) -> bytes | None:
    path = directory / name
    if not path.is_file():
        return None
    return _lf(path.read_bytes())


def _json(directory: Path, name: str) -> Any:
    data = _read(directory, name)
    if data is None:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _text(directory: Path, name: str) -> str | None:
    data = _read(directory, name)
    if data is None:
        return None
    return data.decode("utf-8", errors="replace")


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    return value if isinstance(value, list) else ()


def _named(items: object, name: str) -> Mapping[str, Any]:
    for item in _sequence(items):
        if _mapping(item).get("name") == name:
            return _mapping(item)
    return {}


def _bounded(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:_TEXT_LIMIT]


def _argument(arguments: object, flag: str) -> str | None:
    listed = [a for a in _sequence(arguments) if isinstance(a, str)]
    if flag in listed and listed.index(flag) + 1 < len(listed):
        return listed[listed.index(flag) + 1]
    return None


def _mount(container: Mapping[str, Any]) -> dict[str, Any] | None:
    mount = _named(container.get("volumeMounts"), _CACHE_VOLUME)
    if not mount:
        return None
    return {
        "mountPath": mount.get("mountPath"),
        "readOnly": mount.get("readOnly"),
        "subPath": mount.get("subPath"),
    }


def _mount_table(text: str | None, mount_path: str) -> dict[str, Any]:
    """The line of a ``/proc/self/mountinfo`` text for one mount point."""
    if text is None:
        return {"state": "not-read"}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 7 or "-" not in fields or fields[4] != mount_path:
            continue
        separator = fields.index("-")
        return {
            "state": "read",
            "device": fields[2],
            "root": fields[3][:_TEXT_LIMIT],
            "options": fields[5].split(","),
            "filesystem": fields[separator + 1]
            if separator + 1 < len(fields)
            else None,
        }
    return {"state": "no-line"}


def _artifact(text: str | None) -> dict[str, Any]:
    """``stat -c '%d %i %s'`` of the artifact, as three whole numbers."""
    if text is None:
        return {"state": "not-read"}
    fields = text.split()
    if len(fields) != 3 or not all(field.isdigit() for field in fields):
        return {"state": "unreadable"}
    return {
        "state": "read",
        "device": int(fields[0]),
        "inode": int(fields[1]),
        "sizeBytes": int(fields[2]),
    }


def _reduced(document: object, members: Sequence[str]) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        return {"state": "not-read"}
    reduced: dict[str, Any] = {"state": "read"}
    for name in members:
        value = document.get(name)
        if isinstance(value, str):
            value = value[:_TEXT_LIMIT]
        reduced[name] = value
    return reduced


def _pod(item: Mapping[str, Any], directory: Path, mount_path: str) -> dict[str, Any]:
    metadata = _mapping(item.get("metadata"))
    spec = _mapping(item.get("spec"))
    status = _mapping(item.get("status"))
    name = str(metadata.get("name"))
    safe = name if _POD_NAME.fullmatch(name) else None

    runtime = _named(spec.get("containers"), _RUNTIME_CONTAINER)
    verify = _named(spec.get("initContainers"), _VERIFY_CONTAINER)
    runtime_status = _named(status.get("containerStatuses"), _RUNTIME_CONTAINER)
    verify_status = _named(status.get("initContainerStatuses"), _VERIFY_CONTAINER)
    terminated = _mapping(_mapping(verify_status.get("state")).get("terminated"))
    ready = _named(
        [
            {**_mapping(c), "name": _mapping(c).get("type")}
            for c in _sequence(status.get("conditions"))
        ],
        "Ready",
    )
    volume = _named(spec.get("volumes"), _CACHE_VOLUME)
    claim = _mapping(volume.get("persistentVolumeClaim"))
    volumes = [_mapping(v) for v in _sequence(spec.get("volumes"))]
    script = _sequence(verify.get("command"))
    script_text = script[-1] if script and isinstance(script[-1], str) else ""
    reported_mount = _named(runtime_status.get("volumeMounts"), _CACHE_VOLUME)
    log = _text(directory, f"verify-model.{safe}.txt") if safe else None

    return {
        "name": name,
        "node": spec.get("nodeName"),
        "phase": status.get("phase"),
        "ready": ready.get("status") == "True" if ready else None,
        "readySince": ready.get("lastTransitionTime") if ready else None,
        "restartCount": runtime_status.get("restartCount"),
        "runtimeImage": runtime.get("image"),
        "runtimeImageIdentifier": runtime_status.get("imageID"),
        "modelArgument": _argument(runtime.get("args"), "--model"),
        "aliasArgument": _argument(runtime.get("args"), "--alias"),
        "volume": {
            "claimName": claim.get("claimName"),
            "readOnly": claim.get("readOnly"),
        }
        if claim
        else None,
        "claimVolumes": sum(1 for v in volumes if "persistentVolumeClaim" in v),
        "hostPathVolumes": sum(1 for v in volumes if "hostPath" in v),
        "runtimeMount": _mount(runtime),
        "verificationMount": _mount(verify),
        "reportedMount": {
            "readOnly": reported_mount.get("readOnly"),
            "recursiveReadOnly": reported_mount.get("recursiveReadOnly"),
        }
        if reported_mount
        else None,
        "verification": {
            "exitCode": terminated.get("exitCode"),
            "finishedAt": terminated.get("finishedAt"),
            "script": script_text,
            "log": "not-read" if log is None else "read",
            "logLines": [] if log is None else log.splitlines()[:8],
        },
        "mountTable": _mount_table(
            _text(directory, f"mountinfo.{safe}.txt") if safe else None, mount_path
        ),
        "artifact": _artifact(
            _text(directory, f"artifact.{safe}.txt") if safe else None
        ),
        "reportedModel": _reduced(
            _json(directory, f"models.{safe}.json") if safe else None,
            ("httpStatus", "id", "meta"),
        ),
        "completion": _reduced(
            _json(directory, f"completion.{safe}.json") if safe else None,
            (
                "httpStatus",
                "model",
                "finishReason",
                "promptTokens",
                "completionTokens",
            ),
        ),
    }


def _claims(document: object, claim_name: str, volumes: object) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        return {"state": "not-read"}
    items = [_mapping(i) for i in _sequence(document.get("items"))]
    names = sorted(str(_mapping(i.get("metadata")).get("name")) for i in items)
    claim = next(
        (i for i in items if _mapping(i.get("metadata")).get("name") == claim_name),
        None,
    )
    read: dict[str, Any] = {"state": "read", "claimsInNamespace": names}
    if claim is None:
        read["declaredClaim"] = None
        return read
    metadata = _mapping(claim.get("metadata"))
    labels = _mapping(metadata.get("labels"))
    spec = _mapping(claim.get("spec"))
    volume_name = spec.get("volumeName")
    read["declaredClaim"] = {
        "name": claim_name,
        "phase": _mapping(claim.get("status")).get("phase"),
        "accessModes": list(_sequence(spec.get("accessModes"))),
        "storageClassName": spec.get("storageClassName"),
        "volumeName": volume_name,
        "managedBy": labels.get(_MANAGED_BY_LABEL),
        "lifecycle": labels.get(_LIFECYCLE_LABEL),
        "component": labels.get(_COMPONENT_LABEL),
        "releaseMarkers": sorted(
            [key for key in (_INSTANCE_LABEL, _CHART_LABEL) if key in labels]
            + [
                key
                for key in _mapping(metadata.get("annotations"))
                if key == _RELEASE_ANNOTATION
            ]
        ),
    }
    read["volume"] = {"state": "not-read"}
    for item in _sequence(_mapping(volumes).get("items")):
        volume = _mapping(item)
        if _mapping(volume.get("metadata")).get("name") != volume_name:
            continue
        volume_spec = _mapping(volume.get("spec"))
        source = next(
            (kind for kind in ("hostPath", "local", "csi") if kind in volume_spec),
            None,
        )
        terms = _sequence(
            _mapping(_mapping(volume_spec.get("nodeAffinity")).get("required")).get(
                "nodeSelectorTerms"
            )
        )
        read["volume"] = {
            "state": "read",
            "accessModes": list(_sequence(volume_spec.get("accessModes"))),
            "reclaimPolicy": volume_spec.get("persistentVolumeReclaimPolicy"),
            "source": source,
            "nodes": sorted(
                str(value)
                for term in terms
                for expression in [
                    *_sequence(_mapping(term).get("matchExpressions")),
                    *_sequence(_mapping(term).get("matchFields")),
                ]
                for value in _sequence(_mapping(expression).get("values"))
            ),
        }
    return read


def _samples(text: str | None) -> dict[str, Any]:
    """The readiness samples a driver wrote, counted for each pod.

    One line is ``time<TAB>pod<TAB>phase<TAB>verification exit<TAB>running
    since<TAB>started<TAB>ready``. A line of another shape is counted and not
    read.
    """
    if text is None:
        return {"state": "not-read"}
    pods: dict[str, dict[str, Any]] = {}
    unread = 0
    lines = [line for line in text.splitlines() if line.strip()]
    for line in lines:
        fields = line.split("\t")
        if len(fields) != 7:
            unread += 1
            continue
        time, pod, _phase, _exit, running_since, _started, ready = fields
        entry = pods.setdefault(
            pod,
            {
                "samples": 0,
                "runningAndNotReadyBeforeReady": 0,
                "firstSample": time,
                "firstReadySample": None,
            },
        )
        entry["samples"] += 1
        if ready == "true":
            if entry["firstReadySample"] is None:
                entry["firstReadySample"] = time
        elif running_since and entry["firstReadySample"] is None:
            entry["runningAndNotReadyBeforeReady"] += 1
    return {
        "state": "read",
        "lines": len(lines),
        "linesNotRead": unread,
        "pods": dict(sorted(pods.items())),
    }


def _events(text: str | None) -> dict[str, Any]:
    """Startup probe failures the cluster reported, counted for each pod.

    One line is ``pod<TAB>reason<TAB>count<TAB>first<TAB>last<TAB>message``.
    """
    if text is None:
        return {"state": "not-read"}
    pods: dict[str, dict[str, int]] = {}
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) != 6 or fields[1] != "Unhealthy":
            continue
        pod, _reason, count, _first, _last, message = fields
        if not message.startswith("Startup probe failed"):
            continue
        occurrences = int(count) if count.isdigit() else 1
        entry = pods.setdefault(pod, {"startupProbeFailures": 0, "withStatus503": 0})
        entry["startupProbeFailures"] += occurrences
        if "statuscode: 503" in message:
            entry["withStatus503"] += occurrences
    return {"state": "read", "pods": dict(sorted(pods.items()))}


def _capacity(directory: Path) -> dict[str, Any]:
    outcome = _json(directory, "capacity-preflight.json")
    facts = _json(directory, "capacity-facts.json")
    exit_status = _mapping(outcome).get("exitStatus")
    if isinstance(exit_status, bool) or not isinstance(exit_status, int):
        return {"state": "not-read"}
    return {
        "state": "read",
        "exitStatus": exit_status,
        "facts": facts if isinstance(facts, Mapping) else None,
    }


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------


def _finding(rule_id: str, state: str, detail: str) -> dict[str, Any]:
    rule = next(r for r in RULES if r.rule_id == rule_id)
    return {
        "id": rule.rule_id,
        "statement": rule.statement,
        "required": rule.required,
        "state": state,
        "detail": detail,
    }


def _each(pods: Sequence[Mapping[str, Any]], check: Any, held: str) -> tuple[str, str]:
    """One state for a rule that every pod must hold by itself."""
    if not pods:
        return NOT_OBSERVED, "No serving runtime pod was read."
    unobserved: list[str] = []
    failures: list[str] = []
    for pod in pods:
        outcome = check(pod)
        if outcome is None:
            unobserved.append(str(pod["name"]))
        elif outcome:
            failures.append(f"{pod['name']}: {outcome}")
    if failures:
        return NOT_HELD, "; ".join(failures)
    if unobserved:
        return NOT_OBSERVED, f"Not read for {', '.join(unobserved)}."
    return HELD, held


def _same(
    pods: Sequence[Mapping[str, Any]], read: Any, held: str
) -> tuple[str, str, Any]:
    """One state for a rule that compares a value across every replica."""
    if len(pods) < 2:
        return (
            NOT_OBSERVED,
            "Fewer than two serving runtime pods were read, and one pod agrees "
            "with itself.",
            None,
        )
    values = [read(pod) for pod in pods]
    if any(value is None for value in values):
        missing = [
            str(p["name"]) for p, v in zip(pods, values, strict=True) if v is None
        ]
        return NOT_OBSERVED, f"Not read for {', '.join(missing)}.", None
    if any(value != values[0] for value in values[1:]):
        shown = "; ".join(
            f"{p['name']}: {json.dumps(v, sort_keys=True)}"
            for p, v in zip(pods, values, strict=True)
        )
        return NOT_HELD, f"The replicas differ. {shown}"[:1000], None
    return HELD, held, values[0]


def evaluate(
    expected: Mapping[str, Any],
    pods: Sequence[Mapping[str, Any]],
    claims: Mapping[str, Any],
    samples: Mapping[str, Any],
    capacity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """The state of each rule, from the reduced reads and the expected identity."""
    findings: list[dict[str, Any]] = []
    model = _mapping(expected.get("model"))
    image = _mapping(expected.get("runtimeImage"))
    digest = str(model.get("sha256", "")).removeprefix("sha256:")
    size = model.get("sizeBytes")
    path = expected.get("containerPath")
    sub_path = expected.get("cacheSubPath")
    claim_name = expected.get("claimName")

    def add(rule_id: str, state: str, detail: str) -> None:
        findings.append(_finding(rule_id, state, detail))

    # capacity-preflight-sufficient
    if capacity.get("state") != "read":
        add("capacity-preflight-sufficient", NOT_OBSERVED, "No outcome was read.")
    elif capacity["exitStatus"] == 0:
        add("capacity-preflight-sufficient", HELD, "The preflight exited 0.")
    else:
        add(
            "capacity-preflight-sufficient",
            NOT_HELD,
            f"The preflight exited {capacity['exitStatus']}.",
        )

    # replica-count
    declared = expected.get("runtimeReplicas")
    if pods:
        add(
            "replica-count",
            HELD if len(pods) == declared else NOT_HELD,
            f"{len(pods)} pod(s) were read, and the release declares {declared}.",
        )
    else:
        add("replica-count", NOT_OBSERVED, "No serving runtime pod was read.")

    add(
        "every-replica-ready",
        *_each(
            pods,
            lambda p: (
                None
                if p["ready"] is None
                else ("" if p["ready"] else "the Ready condition is not True")
            ),
            "Each pod reports Ready as True.",
        ),
    )

    def image_check(pod: Mapping[str, Any]) -> str | None:
        if pod["runtimeImage"] is None or pod["runtimeImageIdentifier"] is None:
            return None
        if pod["runtimeImage"] != image.get("reference"):
            return f"declares {pod['runtimeImage']!r}"
        reported = _DIGEST.findall(str(pod["runtimeImageIdentifier"]))
        if reported != [image.get("digest")]:
            return f"reports {pod['runtimeImageIdentifier']!r}"
        return ""

    add(
        "one-runtime-image",
        *_each(pods, image_check, f"Each pod holds {image.get('reference')}."),
    )

    def argument_check(pod: Mapping[str, Any]) -> str | None:
        if pod["modelArgument"] is None:
            return None
        return (
            "" if pod["modelArgument"] == path else f"is given {pod['modelArgument']!r}"
        )

    state, detail = _each(pods, argument_check, f"Each pod is given {path}.")
    if state == HELD:
        state, detail, alias = _same(
            pods, lambda p: p["aliasArgument"], f"Each pod is given {path}."
        )
        if state == HELD:
            detail = f"Each pod is given {path} and the alias {alias}."
    add("one-model-argument", state, detail)

    def claim_check(pod: Mapping[str, Any]) -> str | None:
        if pod["volume"] is None:
            return "declares no claim under the cache volume"
        if pod["volume"]["claimName"] != claim_name:
            return f"mounts the claim {pod['volume']['claimName']!r}"
        if pod["claimVolumes"] != 1:
            return f"declares {pod['claimVolumes']} claim volumes"
        if pod["hostPathVolumes"]:
            return f"declares {pod['hostPathVolumes']} host path volume(s)"
        return ""

    add("one-claim", *_each(pods, claim_check, f"Each pod mounts {claim_name}."))

    # claim-is-the-prerequisite-claim, no-second-claim
    if claims.get("state") != "read":
        add("claim-is-the-prerequisite-claim", NOT_OBSERVED, "No claim was read.")
        add("no-second-claim", NOT_OBSERVED, "No claim was read.")
    else:
        claim = claims.get("declaredClaim")
        if claim is None:
            add(
                "claim-is-the-prerequisite-claim",
                NOT_HELD,
                f"The namespace holds no claim named {claim_name}.",
            )
        else:
            faults = [
                text
                for wrong, text in (
                    (claim["phase"] != "Bound", f"its phase is {claim['phase']!r}"),
                    (
                        claim["managedBy"] != "Terraform",
                        f"it is managed by {claim['managedBy']!r}",
                    ),
                    (
                        claim["lifecycle"] != "prerequisite",
                        f"its lifecycle is {claim['lifecycle']!r}",
                    ),
                    (
                        bool(claim["releaseMarkers"]),
                        f"it carries {claim['releaseMarkers']}",
                    ),
                )
                if wrong
            ]
            add(
                "claim-is-the-prerequisite-claim",
                NOT_HELD if faults else HELD,
                "; ".join(faults)
                if faults
                else "The claim is Bound, is managed by Terraform with the "
                "prerequisite lifecycle, and carries no release marker.",
            )
        names = claims["claimsInNamespace"]
        add(
            "no-second-claim",
            HELD if len(names) == 1 else NOT_HELD,
            f"The namespace holds {len(names)} claim(s): {', '.join(names)}.",
        )

    def declared_read_only(pod: Mapping[str, Any]) -> str | None:
        places = (
            ("the volume", pod["volume"], "readOnly"),
            ("the runtime mount", pod["runtimeMount"], "readOnly"),
            ("the verification mount", pod["verificationMount"], "readOnly"),
        )
        missing = [name for name, holder, _ in places if holder is None]
        if missing:
            return f"declares no {' and no '.join(missing)}"
        writable = [name for name, holder, key in places if holder[key] is not True]
        return f"{', '.join(writable)} is not read only" if writable else ""

    add(
        "read-only-declared",
        *_each(
            pods, declared_read_only, "Each of the three places states readOnly: true."
        ),
    )

    def effective_read_only(pod: Mapping[str, Any]) -> str | None:
        table = pod["mountTable"]
        if table["state"] == "not-read":
            return None
        if table["state"] != "read":
            return "the mount table has no line for the cache mount"
        return "" if "ro" in table["options"] else f"the options are {table['options']}"

    add(
        "read-only-in-effect",
        *_each(pods, effective_read_only, "Each mount table lists the option ro."),
    )

    def scoped(pod: Mapping[str, Any]) -> str | None:
        mounts = (pod["runtimeMount"], pod["verificationMount"])
        if any(mount is None for mount in mounts):
            return "one container declares no cache mount"
        wrong = [m["subPath"] for m in mounts if m["subPath"] != sub_path]
        return f"mounts {wrong}" if wrong else ""

    add(
        "revision-scoped-mount",
        *_each(pods, scoped, f"Each mount names {sub_path}."),
    )

    state, detail, _ = _same(
        pods,
        lambda p: (
            [p["mountTable"]["device"], p["mountTable"]["root"]]
            if p["mountTable"]["state"] == "read"
            else None
        ),
        "Every mount table names one device and one root directory.",
    )
    add("one-directory", state, detail)

    state, detail, seen = _same(
        pods,
        lambda p: (
            [p["artifact"][k] for k in ("device", "inode", "sizeBytes")]
            if p["artifact"]["state"] == "read"
            else None
        ),
        "Every runtime container sees one device, one inode, and the pinned "
        "byte count.",
    )
    if state == HELD and seen[2] != size:
        state = NOT_HELD
        detail = f"The file holds {seen[2]} bytes, and the pin is {size}."
    add("one-file", state, detail)

    def verified(pod: Mapping[str, Any]) -> str | None:
        check = pod["verification"]
        if digest not in check["script"] or str(size) not in check["script"]:
            return "the script does not hold the pinned SHA-256 and byte count"
        if check["exitCode"] is None:
            return "the verification container has not terminated"
        if check["exitCode"] != 0:
            return f"the verification container exited {check['exitCode']}"
        if check["log"] != "read":
            return None
        lines = [line.strip() for line in check["logLines"]]
        if _VERIFIED_LINE not in lines or f"{path}: OK" not in lines:
            return "the log does not hold the two expected lines"
        return ""

    add(
        "artifact-verified-on-each-start",
        *_each(
            pods,
            verified,
            "Each verification container compared the pinned digest and exited 0.",
        ),
    )

    def listed(pod: Mapping[str, Any]) -> str | None:
        answer = pod["reportedModel"]
        if answer["state"] != "read":
            return None
        if answer["httpStatus"] != 200:
            return f"the listing answered {answer['httpStatus']}"
        if answer["id"] != pod["aliasArgument"]:
            return f"the listing names {answer['id']!r}"
        return ""

    state, detail = _each(pods, listed, "")
    if state == HELD:
        state, detail, _ = _same(
            pods,
            lambda p: [p["reportedModel"]["meta"]],
            "Every runtime listed the alias it was given and the same metadata.",
        )
    add("one-reported-model", state, detail)

    def completed(pod: Mapping[str, Any]) -> str | None:
        answer = pod["completion"]
        if answer["state"] != "read":
            return None
        if answer["httpStatus"] != 200:
            return f"the completion answered {answer['httpStatus']}"
        tokens = answer["completionTokens"]
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 1:
            return f"the completion reports {tokens!r} completion tokens"
        return ""

    add(
        "every-replica-completed",
        *_each(pods, completed, "Each runtime answered 200 with completion tokens."),
    )

    sampled = _mapping(samples.get("pods")) if samples.get("state") == "read" else {}

    def loading(pod: Mapping[str, Any]) -> str | None:
        entry = sampled.get(pod["name"])
        if not entry or not entry["runningAndNotReadyBeforeReady"]:
            return None
        return ""

    add(
        "not-ready-while-loading",
        *_each(
            pods,
            loading,
            "Each pod was sampled running and not ready before it was Ready.",
        ),
    )
    return findings


def result_state(findings: Sequence[Mapping[str, Any]], pods_read: int) -> str:
    """The one result of a record, from the state of each rule."""
    states = {f["id"]: f["state"] for f in findings}
    if states.get("capacity-preflight-sufficient") == NOT_HELD and not pods_read:
        return REFUSED
    if NOT_HELD in states.values():
        return FAILED
    if any(f["required"] and f["state"] == NOT_OBSERVED for f in findings):
        return INCONCLUSIVE
    return PASSED


def build_record(directory: Path) -> dict[str, Any]:
    """The record of one collection directory."""
    header = _json(directory, "run.json")
    if not isinstance(header, Mapping) or header.get("schema") != COLLECTION_SCHEMA:
        raise CollectionRefused(
            f"{directory.name} holds no run.json with the schema {COLLECTION_SCHEMA}"
        )
    expected = _json(directory, "expected.json")
    if not isinstance(expected, Mapping) or expected.get("schema") != EXPECTED_SCHEMA:
        raise CollectionRefused(
            f"{directory.name} holds no expected.json with the schema {EXPECTED_SCHEMA}"
        )
    mount_path = str(expected.get("mountPath"))

    listing = _json(directory, "runtime-pods.json")
    items = [
        _mapping(item)
        for item in _sequence(_mapping(listing).get("items"))
        if _mapping(_mapping(_mapping(item).get("metadata")).get("labels")).get(
            _COMPONENT_LABEL
        )
        == RUNTIME_COMPONENT
        and "deletionTimestamp" not in _mapping(_mapping(item).get("metadata"))
    ]
    pods = sorted(
        (_pod(item, directory, mount_path) for item in items),
        key=lambda pod: str(pod["name"]),
    )
    claims = _claims(
        _json(directory, "claims.json"),
        str(expected.get("claimName")),
        _json(directory, "volumes.json"),
    )
    samples = _samples(_text(directory, "readiness-samples.txt"))
    capacity = _capacity(directory)
    findings = evaluate(expected, pods, claims, samples, capacity)
    nodes = sorted({str(pod["node"]) for pod in pods if pod["node"]})

    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.name != RECORD_FILE
    )
    return {
        "schema": RECORD_SCHEMA,
        "evidenceLevel": "C2",
        "result": result_state(findings, len(pods)),
        "collection": {
            name: _bounded(header.get(name))
            for name in (
                "runId",
                "provider",
                "namespace",
                "executingCommit",
                "reportedRevision",
                "startedAt",
                "collectedAt",
            )
        },
        "files": [
            {
                "name": path.name,
                "sha256": _sha256(_lf(path.read_bytes())),
            }
            for path in files
        ],
        "expected": dict(expected),
        "podListing": "read" if isinstance(listing, Mapping) else "not-read",
        "replicas": pods,
        "placement": {"nodes": nodes, "distinctNodes": len(nodes)},
        "claims": claims,
        "readinessSamples": samples,
        "startupProbeEvents": _events(_text(directory, "events.txt")),
        "capacityPreflight": capacity,
        "rules": findings,
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def record_text(record: Mapping[str, Any]) -> str:
    """The bytes a committed record holds."""
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def committed_runs(root: Path = REPO_ROOT) -> list[str]:
    """Each directory under the root that :data:`RUNS_PATTERN` matches."""
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.glob(RUNS_PATTERN)
        if path.is_dir()
    )


def check_committed_runs(root: Path = REPO_ROOT) -> list[str]:
    """Each committed run whose record is not what its collection gives."""
    findings: list[str] = []
    for run in committed_runs(root):
        directory = root / run
        committed = _read(directory, RECORD_FILE)
        if committed is None:
            findings.append(f"{run}: the directory holds no {RECORD_FILE}")
            continue
        try:
            built = record_text(build_record(directory))
        except CollectionRefused as refused:
            findings.append(f"{run}: {refused}")
            continue
        if built.encode("utf-8") != committed:
            findings.append(
                f"{run}: {RECORD_FILE} is not what the collection gives. Build it "
                f"again: python -m tools.runtime_model_cache {run}"
            )
    return findings
