"""The Ready endpoint state of the two Services of one release, as one record.

A collector reads the Services and the EndpointSlices of one namespace, once,
and writes what each read returned into one directory. This module reads that
directory and returns one record. For the API Service and for the serving
runtime Service, the record states how many endpoints the cluster published,
how many of them were Ready, and which pods they were.

The module decides nothing about a release. It does not say whether a count is
the expected count, and a record with zero Ready endpoints is ``OBSERVED``: zero
is a reading. The result is ``REFUSED`` only when the collection does not give
one unambiguous reading. A read that was not made is not zero endpoints.

**The record is not caller truth.** A Ready endpoint is a pod whose readiness
the cluster published. It is not a request that a caller sent and had answered.
The record is also not a Prometheus ``up`` series, which states that a scrape of
one pod's metrics port succeeded.

See docs/environment/service-endpoint-state.md, which describes the collection,
the rules, the identities, and the limits of a record, and
tests/domain/test_service_endpoint_state.py, which gives the module each
ambiguous collection.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The schema name of a record.
RECORD_SCHEMA: Final = "inferops.io/service-endpoint-state/v1alpha1"

#: The schema name that a collector writes into the header of a collection.
COLLECTION_SCHEMA: Final = "inferops.io/service-endpoint-state-collection/v1alpha1"

#: The files of a collection. The collector restates each name.
HEADER_FILE: Final = "run.json"
SERVICES_FILE: Final = "services.json"
SLICES_FILE: Final = "endpointslices.json"
RECORD_FILE: Final = "record.v1alpha1.json"

#: Where committed collections are found: the cases of the suite, and each run.
CASES_PATTERN: Final = "tests/domain/fixtures/service-endpoint-state/*"
RUNS_PATTERN: Final = "docs/proof/environment/*-service-endpoint-state-run-*"

#: The exit status of the command when the result is REFUSED.
REFUSED_EXIT: Final = 5

OBSERVED: Final = "OBSERVED"
REFUSED: Final = "REFUSED"

#: Every result that a record can state.
RESULT_STATES: Final = (OBSERVED, REFUSED)

HELD: Final = "held"
NOT_HELD: Final = "not-held"
NOT_OBSERVED: Final = "not-observed"

#: The states of one tier of a record. ``observed`` states figures. The other
#: two state none.
TIER_OBSERVED: Final = "observed"
TIER_REFUSED: Final = "refused"
TIER_NOT_OBSERVED: Final = "not-observed"

#: The two tiers of a record, as the value of the component label that the chart
#: gives the Service of each. A record states these two and no other.
TIERS: Final = ("platform-api", "serving-runtime")

#: The largest number of pods that a record states for one Service. The values
#: schema of the chart admits 16 replicas for a tier and 16 pods of surge. A
#: Service with more is refused, and the record lists none of them.
MAX_ENDPOINTS: Final = 32

#: What a record leaves out of each endpoint, on purpose.
OMITTED: Final[tuple[str, ...]] = (
    "The addresses of an endpoint.",
    "The node name, the zone, and the hostname of an endpoint.",
    "The ports and the hints of a slice.",
    "The name of the kubeconfig context. A context name can hold an account identifier.",
)

INSTANCE_LABEL: Final = "app.kubernetes.io/instance"
COMPONENT_LABEL: Final = "app.kubernetes.io/component"
SERVICE_NAME_LABEL: Final = "kubernetes.io/service-name"
MANAGED_BY_LABEL: Final = "endpointslice.kubernetes.io/managed-by"

#: The value of the managed-by label that the Kubernetes EndpointSlice
#: controller writes. A slice with another value was written by something else.
SLICE_CONTROLLER: Final = "endpointslice-controller.k8s.io"

_CONDITIONS: Final = ("ready", "serving", "terminating")
_ADDRESS_TYPES: Final = frozenset({"IPv4", "IPv6", "FQDN"})
_HEADER_MEMBERS: Final = (
    "schema",
    "provider",
    "namespace",
    "release",
    "executingCommit",
    "readStartedAt",
    "readFinishedAt",
)
_LABEL: Final = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
_NAME: Final = re.compile(r"[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?")
_UID: Final = re.compile(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}")
_REVISION: Final = re.compile(r"[0-9a-f]{40}")
_INSTANT: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


@dataclass(frozen=True)
class Rule:
    """One rule of a record: what it holds a collection to."""

    rule_id: str
    statement: str


#: Every rule, in the order a record states them. The first two are about the
#: collection. The others are evaluated for each tier.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "each-read-was-made",
        "The collection holds the Service read and the EndpointSlice read. A read "
        "that did not answer is not an empty list.",
    ),
    Rule(
        "each-read-has-the-shape-of-its-kind",
        "Each read is a list of objects of its kind, in the namespace that the "
        "collection names. Each member that a rule reads has its type, each "
        "object has a name of its own, and each slice names its Service.",
    ),
    Rule(
        "one-service-carries-each-tier",
        "For each tier, exactly one Service of the release carries the component "
        "label of that tier.",
    ),
    Rule(
        "the-service-publishes-ready-addresses-only",
        "The Service does not set publishNotReadyAddresses. Kubernetes documents "
        "that such a Service publishes each endpoint as ready, whatever its pod "
        "reports.",
    ),
    Rule(
        "the-service-has-a-slice",
        "The read holds at least one EndpointSlice of the Service. A Service with "
        "no slice is not read as zero endpoints: the record cannot tell a Service "
        "with no pod from a Service whose slices were not written yet.",
    ),
    Rule(
        "the-slice-controller-wrote-each-slice",
        "Each EndpointSlice of the Service carries the managed-by label of the "
        "Kubernetes EndpointSlice controller.",
    ),
    Rule(
        "each-endpoint-states-its-conditions",
        "Each endpoint states ready, serving, and terminating, each as true or "
        "false. Kubernetes documents that a consumer reads an unstated ready as "
        "true. This record does not apply that reading.",
    ),
    Rule(
        "each-endpoint-names-one-pod",
        "Each endpoint names one Pod of the namespace, by name and by UID.",
    ),
    Rule(
        "one-pod-has-one-state",
        "A pod that more than one endpoint names has the same three conditions in "
        "each. One pod and one name have one UID.",
    ),
    Rule(
        "the-endpoint-count-is-within-the-bound",
        f"The Service has at most {MAX_ENDPOINTS} pods behind it.",
    ),
)

_COLLECTION_RULES: Final = (RULES[0].rule_id, RULES[1].rule_id)

#: What a record does not establish, whatever its result.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "That a caller obtains a completion. A Ready endpoint is a pod whose "
    "readiness the cluster published. It is not a request that was sent and "
    "answered, and this record sends none.",
    "That a request reaches a Ready endpoint. The node's proxy applies a slice "
    "after the slice changes, and this record does not read the proxy.",
    "That a pod behind a Ready endpoint can serve inference. Ready states the "
    "result of the pod's readiness probe, as the kubelet reported it.",
    "The state before the read started or after it finished. A record is one "
    "reading. It is not a timeline, and it holds no transition.",
    "What a Prometheus `up` series states. That series says that one scrape of "
    "one pod's metrics port succeeded. It is not the state of a Service.",
    "That the release is the declared release. The record reads no image, no "
    "revision, and no state of a GitOps controller.",
    "What a caller observes when a pod is deleted, evicted, or replaced, and "
    "that the release survives the loss of a node.",
)

#: The limits of one reading.
LIMITATIONS: Final[tuple[str, ...]] = (
    "The two reads are two calls. They are not one atomic reading, and a pod "
    "can change between them.",
    "The two instants are the collecting host's clock, to one second. They are "
    "not compared with a clock of the cluster.",
    "An identity is a pod name and a pod UID. It is valid for the life of that "
    "pod on that cluster, and it is not a stable identity of a replica.",
    "The record reads one namespace and the Services of one release in it.",
    f"A Service with more than {MAX_ENDPOINTS} pods behind it is refused.",
)


class CollectionRefused(Exception):
    """The directory is not a collection, so no record can be built from it."""


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _read(directory: Path, name: str) -> bytes | None:
    """The bytes of one file of a collection, or None when it is not there."""
    path = directory / name
    if not path.is_file():
        return None
    return path.read_bytes()


def _header(directory: Path) -> dict[str, str]:
    """The header that the collector wrote, held to its members and their form."""
    data = _read(directory, HEADER_FILE)
    if data is None:
        raise CollectionRefused(f"the directory holds no {HEADER_FILE}")
    try:
        header = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as fault:
        raise CollectionRefused(f"{HEADER_FILE} is not JSON") from fault
    if not isinstance(header, dict):
        raise CollectionRefused(f"{HEADER_FILE} is not an object")
    if sorted(header) != sorted(_HEADER_MEMBERS):
        raise CollectionRefused(
            f"{HEADER_FILE} holds the members {sorted(header)}, and a collection "
            f"holds {sorted(_HEADER_MEMBERS)}"
        )
    forms = {
        "provider": _LABEL,
        "namespace": _LABEL,
        "release": _LABEL,
        "executingCommit": _REVISION,
        "readStartedAt": _INSTANT,
        "readFinishedAt": _INSTANT,
    }
    for name, pattern in forms.items():
        if not _matches(pattern, header[name]):
            raise CollectionRefused(f"{HEADER_FILE} states no usable {name}")
    if header["schema"] != COLLECTION_SCHEMA:
        raise CollectionRefused(
            f"{HEADER_FILE} states another schema than {COLLECTION_SCHEMA}"
        )
    # Both instants have one fixed form in UTC, so their text orders as they do.
    if header["readFinishedAt"] < header["readStartedAt"]:
        raise CollectionRefused(
            f"{HEADER_FILE} states a read that finished before it started"
        )
    return {name: header[name] for name in _HEADER_MEMBERS}


# --------------------------------------------------------------------------
# The shape of the two reads
# --------------------------------------------------------------------------


def _labels(metadata: Mapping[str, Any], label: str, faults: list[str]) -> None:
    labels = metadata.get("labels")
    if labels is None:
        return
    if not isinstance(labels, dict):
        faults.append(f"{label}: metadata.labels is not an object")
        return
    for key, value in labels.items():
        if not isinstance(value, str):
            faults.append(f"{label}: the label {key!r} is not text")


def _object_shape(
    item: object, kind: str, namespace: str, label: str, faults: list[str]
) -> bool:
    """The members that every rule reads of one listed object."""
    if not isinstance(item, dict):
        faults.append(f"{label} is not an object")
        return False
    if item.get("kind") != kind:
        faults.append(f"{label} is not a {kind}")
        return False
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        faults.append(f"{label}: metadata is not an object")
        return False
    if not _matches(_NAME, metadata.get("name")):
        faults.append(f"{label}: metadata.name is not a name")
        return False
    if metadata.get("namespace") != namespace:
        faults.append(f"{label}: the object is not in the namespace {namespace}")
    _labels(metadata, label, faults)
    return True


def _service_shape(item: Mapping[str, Any], label: str, faults: list[str]) -> None:
    spec = item.get("spec")
    if not isinstance(spec, dict):
        faults.append(f"{label}: spec is not an object")
        return
    publish = spec.get("publishNotReadyAddresses")
    if publish is not None and not isinstance(publish, bool):
        faults.append(f"{label}: spec.publishNotReadyAddresses is not true or false")


def _endpoint_shape(endpoint: object, label: str, faults: list[str]) -> None:
    if not isinstance(endpoint, dict):
        faults.append(f"{label} is not an object")
        return
    conditions = endpoint.get("conditions")
    if conditions is not None:
        if not isinstance(conditions, dict):
            faults.append(f"{label}: conditions is not an object")
        else:
            for name in _CONDITIONS:
                value = conditions.get(name)
                if value is not None and not isinstance(value, bool):
                    faults.append(f"{label}: conditions.{name} is not true or false")
    reference = endpoint.get("targetRef")
    if reference is not None:
        if not isinstance(reference, dict):
            faults.append(f"{label}: targetRef is not an object")
        else:
            for name in ("kind", "name", "namespace", "uid"):
                value = reference.get(name)
                if value is not None and not isinstance(value, str):
                    faults.append(f"{label}: targetRef.{name} is not text")


def _slice_shape(item: Mapping[str, Any], label: str, faults: list[str]) -> None:
    # A slice that names no Service cannot be given to a tier, and it is not
    # left out: its endpoints would then be missing from a count.
    labels = item["metadata"].get("labels")
    named = labels.get(SERVICE_NAME_LABEL) if isinstance(labels, dict) else None
    if not isinstance(named, str) or not named:
        faults.append(f"{label}: the slice does not name its Service by label")
    if item.get("addressType") not in _ADDRESS_TYPES:
        faults.append(f"{label}: addressType is not one of {sorted(_ADDRESS_TYPES)}")
    endpoints = item.get("endpoints")
    if endpoints is None:
        return
    if not isinstance(endpoints, list):
        faults.append(f"{label}: endpoints is not a list")
        return
    for index, endpoint in enumerate(endpoints):
        _endpoint_shape(endpoint, f"{label}: endpoint {index}", faults)


def _items(data: bytes, kind: str, what: str, faults: list[str]) -> list[Any] | None:
    """The items of one read, or None when the read is not a list of objects."""
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        faults.append(f"{what} is not JSON")
        return None
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        faults.append(f"{what} is not a list of {kind} objects")
        return None
    # `kubectl get -o json` names a list of several objects `List`. The API
    # names it after its kind.
    if document.get("kind") not in ("List", f"{kind}List"):
        faults.append(f"{what} is not a list of {kind} objects: its kind is another")
        return None
    return list(document["items"])


def _shape_faults(
    services: Sequence[Any] | None,
    slices: Sequence[Any] | None,
    namespace: str,
    faults: list[str],
) -> None:
    for file, items in ((SERVICES_FILE, services), (SLICES_FILE, slices)):
        names = [
            item["metadata"]["name"]
            for item in items or ()
            if isinstance(item, dict)
            and isinstance(item.get("metadata"), dict)
            and isinstance(item["metadata"].get("name"), str)
        ]
        for name in sorted({name for name in names if names.count(name) > 1}):
            faults.append(f"{file}: {names.count(name)} objects have the name {name}")
    for index, item in enumerate(services or ()):
        label = f"{SERVICES_FILE}: item {index}"
        if _object_shape(item, "Service", namespace, label, faults):
            _service_shape(item, label, faults)
    for index, item in enumerate(slices or ()):
        label = f"{SLICES_FILE}: item {index}"
        if _object_shape(item, "EndpointSlice", namespace, label, faults):
            _slice_shape(item, label, faults)


# --------------------------------------------------------------------------
# One tier
# --------------------------------------------------------------------------


def _label_of(item: Mapping[str, Any], name: str) -> str | None:
    labels = item["metadata"].get("labels") or {}
    value = labels.get(name)
    return value if isinstance(value, str) else None


def _pod(endpoint: Mapping[str, Any], namespace: str) -> tuple[str, str] | None:
    """The name and the UID of the pod an endpoint names, or None."""
    reference = endpoint.get("targetRef")
    if not isinstance(reference, dict):
        return None
    if reference.get("kind") != "Pod":
        return None
    if reference.get("namespace") not in (None, namespace):
        return None
    name, uid = reference.get("name"), reference.get("uid")
    if not isinstance(name, str) or not isinstance(uid, str):
        return None
    if not _matches(_NAME, name) or not _matches(_UID, uid):
        return None
    return name, uid


def _empty_tier(tier: str, state: str) -> dict[str, Any]:
    return {
        "tier": tier,
        "state": state,
        "service": None,
        "slices": None,
        "addressTypes": None,
        "endpoints": None,
        "ready": None,
        "notReady": None,
    }


def _tier(
    tier: str,
    release: str,
    namespace: str,
    services: Sequence[Mapping[str, Any]],
    slices: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """The state of one tier, and the detail of each rule that it does not hold.

    A tier with no one Service is read no further: the later rules are not
    evaluated for it, and the caller states that. For a tier with one Service,
    every later rule is evaluated, also after one of them is not held.
    """
    broken: dict[str, list[str]] = {}
    refused = _empty_tier(tier, TIER_REFUSED)

    carrying = sorted(
        item["metadata"]["name"]
        for item in services
        if _label_of(item, INSTANCE_LABEL) == release
        and _label_of(item, COMPONENT_LABEL) == tier
    )
    if len(carrying) != 1:
        found = f"{len(carrying)} Services" if carrying else "no Service"
        broken["one-service-carries-each-tier"] = [
            f"{tier}: {found} of the release {release} carry this component label"
        ]
        return refused, broken
    [name] = carrying
    refused["service"] = name
    [service] = [item for item in services if item["metadata"]["name"] == name]

    if service["spec"].get("publishNotReadyAddresses") is True:
        broken["the-service-publishes-ready-addresses-only"] = [
            f"{tier}: the Service {name} sets publishNotReadyAddresses"
        ]

    own = [item for item in slices if _label_of(item, SERVICE_NAME_LABEL) == name]
    if not own:
        broken["the-service-has-a-slice"] = [
            f"{tier}: the read holds no EndpointSlice of the Service {name}"
        ]
    foreign = sorted(
        item["metadata"]["name"]
        for item in own
        if _label_of(item, MANAGED_BY_LABEL) != SLICE_CONTROLLER
    )
    if foreign:
        broken["the-slice-controller-wrote-each-slice"] = [
            f"{tier}: the slice {slice_name} does not carry the controller's "
            "managed-by label"
            for slice_name in foreign
        ]

    unstated: list[str] = []
    unnamed: list[str] = []
    states: dict[str, set[tuple[str, bool, bool, bool]]] = {}
    for item in own:
        for index, endpoint in enumerate(item.get("endpoints") or ()):
            where = f"{tier}: the slice {item['metadata']['name']}, endpoint {index}"
            conditions = endpoint.get("conditions") or {}
            ready, serving, terminating = (
                conditions.get(condition) for condition in _CONDITIONS
            )
            pod = _pod(endpoint, namespace)
            stated = (
                isinstance(ready, bool)
                and isinstance(serving, bool)
                and isinstance(terminating, bool)
            )
            if not stated:
                missing = [
                    condition
                    for condition in _CONDITIONS
                    if not isinstance(conditions.get(condition), bool)
                ]
                unstated.append(f"{where} does not state {', '.join(missing)}")
            if pod is None:
                unnamed.append(f"{where} names no Pod of the namespace by name and UID")
            if (
                pod is None
                or not isinstance(ready, bool)
                or not isinstance(serving, bool)
                or not isinstance(terminating, bool)
            ):
                continue
            pod_name, uid = pod
            states.setdefault(uid, set()).add((pod_name, ready, serving, terminating))
    if unstated:
        broken["each-endpoint-states-its-conditions"] = unstated
    if unnamed:
        broken["each-endpoint-names-one-pod"] = unnamed

    conflicts = [
        f"{tier}: the pod UID {uid} has {len(found)} different states in the slices "
        f"of {name}"
        for uid, found in sorted(states.items())
        if len(found) > 1
    ]
    names: dict[str, set[str]] = {}
    for uid, pod_states in states.items():
        for pod_state in pod_states:
            names.setdefault(pod_state[0], set()).add(uid)
    conflicts += [
        f"{tier}: the pod name {pod_name} has {len(uids)} UIDs in the slices of {name}"
        for pod_name, uids in sorted(names.items())
        if len(uids) > 1
    ]
    if conflicts:
        broken["one-pod-has-one-state"] = conflicts

    if len(states) > MAX_ENDPOINTS:
        broken["the-endpoint-count-is-within-the-bound"] = [
            f"{tier}: the Service {name} has {len(states)} pods behind it"
        ]

    if broken:
        return refused, broken

    pods = sorted(
        (pod_name, uid, ready, serving, terminating)
        for uid, found in states.items()
        for pod_name, ready, serving, terminating in found
    )
    return {
        "tier": tier,
        "state": TIER_OBSERVED,
        "service": name,
        "slices": len(own),
        "addressTypes": sorted({item["addressType"] for item in own}),
        "endpoints": {
            "total": len(pods),
            "ready": sum(1 for pod in pods if pod[2]),
            "notReady": sum(1 for pod in pods if not pod[2]),
            "serving": sum(1 for pod in pods if pod[3]),
            "terminating": sum(1 for pod in pods if pod[4]),
        },
        "ready": [
            {"podName": pod_name, "podUid": uid}
            for pod_name, uid, ready, _serving, _terminating in pods
            if ready
        ],
        "notReady": [
            {
                "podName": pod_name,
                "podUid": uid,
                "serving": serving,
                "terminating": terminating,
            }
            for pod_name, uid, ready, serving, terminating in pods
            if not ready
        ],
    }, {}


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


def _finding(rule: Rule, state: str, detail: str) -> dict[str, str]:
    return {
        "ruleId": rule.rule_id,
        "statement": rule.statement,
        "state": state,
        "detail": detail,
    }


def observe(
    services: Sequence[Mapping[str, Any]],
    slices: Sequence[Mapping[str, Any]],
    *,
    release: str,
    namespace: str,
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """The state of each tier from two reads that already have their shape.

    Returns the tiers, in the order of ``TIERS``, and the detail of each rule
    that a tier does not hold. The reads are the ``items`` of a Service list and
    of an EndpointSlice list of one namespace. ``build_record`` holds them to
    their shape first. A caller that samples a cluster repeatedly must do the
    same, and must treat a read that did not answer as no reading.
    """
    tiers: list[dict[str, Any]] = []
    broken: dict[str, list[str]] = {}
    for tier in TIERS:
        state, faults = _tier(tier, release, namespace, services, slices)
        tiers.append(state)
        for rule_id, details in faults.items():
            broken.setdefault(rule_id, []).extend(details)
    return tiers, broken


def build_record(directory: Path) -> dict[str, Any]:
    """The record of one collection.

    Raises ``CollectionRefused`` when the directory holds no usable header. Any
    other defect of a collection is a rule that the record states as not held.
    """
    header = _header(directory)
    namespace, release = header["namespace"], header["release"]

    reads = {name: _read(directory, name) for name in (SERVICES_FILE, SLICES_FILE)}
    absent = [name for name, data in reads.items() if data is None]

    shape: list[str] = []
    services = slices = None
    if not absent:
        services = _items(reads[SERVICES_FILE], "Service", SERVICES_FILE, shape)  # type: ignore[arg-type]
        slices = _items(reads[SLICES_FILE], "EndpointSlice", SLICES_FILE, shape)  # type: ignore[arg-type]
        _shape_faults(services, slices, namespace, shape)

    broken: dict[str, list[str]] = {}
    if absent:
        broken[RULES[0].rule_id] = [
            f"the collection holds no {name}: that read was not made" for name in absent
        ]
    if shape:
        broken[RULES[1].rule_id] = shape

    usable = not absent and not shape
    if usable:
        assert services is not None and slices is not None
        tiers, tier_faults = observe(
            services, slices, release=release, namespace=namespace
        )
        broken.update(tier_faults)
    else:
        tiers = [_empty_tier(tier, TIER_NOT_OBSERVED) for tier in TIERS]

    # A rule of a tier is not observed when an earlier rule left it unread: the
    # collection rules for every tier, and the Service rule for that tier. A
    # finding names each tier that its rule was not read for.
    unread = [tier["tier"] for tier in tiers if usable and tier["service"] is None]
    read = [name for name in TIERS if name not in unread]
    findings: list[dict[str, str]] = []
    for position, rule in enumerate(RULES):
        if rule.rule_id in broken:
            detail = "; ".join(broken[rule.rule_id])
            if position > 2 and unread:
                detail += (
                    f"; not read for {', '.join(unread)}, which has no one Service"
                )
            findings.append(_finding(rule, NOT_HELD, detail))
        elif position == 1 and absent:
            findings.append(
                _finding(
                    rule, NOT_OBSERVED, "a read was not made, so no shape was read"
                )
            )
        elif rule.rule_id not in _COLLECTION_RULES and not usable:
            findings.append(
                _finding(
                    rule,
                    NOT_OBSERVED,
                    "the collection gives no usable reads, so no tier was read",
                )
            )
        elif position > 2 and unread:
            detail = f"not read for {', '.join(unread)}, which has no one Service"
            if read:
                detail += f"; held for {', '.join(read)}"
            findings.append(_finding(rule, NOT_OBSERVED, detail))
        else:
            findings.append(_finding(rule, HELD, "held"))

    refusing = [finding["ruleId"] for finding in findings if finding["state"] != HELD]
    return {
        "schema": RECORD_SCHEMA,
        "collection": header,
        "result": REFUSED if refusing else OBSERVED,
        "refusedBy": refusing,
        "tiers": tiers,
        "findings": findings,
        "bounds": {"tiers": list(TIERS), "maxEndpointsPerService": MAX_ENDPOINTS},
        "omitted": list(OMITTED),
        "limitations": list(LIMITATIONS),
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def record_text(record: Mapping[str, Any]) -> str:
    """A record as the text that is stored: sorted members, one trailing newline."""
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def committed_collections(root: Path = REPO_ROOT) -> list[str]:
    """Each committed collection, as a path under the repository root."""
    found: set[str] = set()
    for pattern in (CASES_PATTERN, RUNS_PATTERN):
        for path in root.glob(pattern):
            if path.is_dir():
                found.add(path.relative_to(root).as_posix())
    return sorted(found)


def check_committed(root: Path = REPO_ROOT) -> list[str]:
    """One finding for each committed record that its collection does not give."""
    findings: list[str] = []
    for relative in committed_collections(root):
        directory = root / relative
        stored = _read(directory, RECORD_FILE)
        if stored is None:
            findings.append(f"{relative}: the collection holds no {RECORD_FILE}")
            continue
        try:
            derived = record_text(build_record(directory))
        except CollectionRefused as refused:
            findings.append(f"{relative}: not a collection: {refused}")
            continue
        if stored.replace(b"\r\n", b"\n") != derived.encode("utf-8"):
            findings.append(
                f"{relative}: {RECORD_FILE} is not the record that the collection gives"
            )
    return findings
