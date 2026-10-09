"""Whether one cluster can hold the two-replica release, as a gate record.

A collector reads a cluster and writes what each read returned into one
directory: the nodes, every pod, the quota and limit-range objects and the
claims of the release namespace, and the declared footprint of the release. This
module reads that directory. It reads no cluster. It returns one record, whose
result is ``ACCEPTED`` or ``REFUSED``.

**The footprint comes from files of one working tree, and not from the cluster.**
:func:`declared_footprint` reads the Application of one desired-state release,
the chart's defaults, the values file that the Application names, and the values
that the Application states. It reads the files as the tree holds them. It does
not read a commit, and it does not compare the tree with the revision that the
Application names. It states each pod the chart renders for those values, with the
requests and limits of each container.

**The gate compares stated figures.** It compares the requests and the memory
limits that the footprint states with the allocatable figures of one node, less
the requests of the pods that the node already holds. It measures no memory and
no processor time in use.

**A read that was not made is not a value.** A file that the directory does not
hold, and a file that cannot be parsed, give ``not-observed`` for each rule that
needs it. A rule that is ``not-observed`` is never ``held``, and a required rule
that is not ``held`` refuses the cluster.

**A refusal has a category.** ``insufficient`` means that a stated figure does
not fit. ``ambiguous`` means that the gate cannot decide from what it read: a
read is absent, a document does not have the form that this tool reads, a
quantity is not readable, or the cluster or the release has a property that this
arithmetic does not describe.

**A member of another type is not read as absent.** A node or a pod whose kind,
name, or member has another type than the one this tool reads refuses the
cluster. It is not counted as zero.

**No figure is lowered to obtain an acceptance.** The reserve is this module's
constant, and a collection that states another reserve is not a collection. A
derived figure in a stored footprint is computed again from the stated
quantities, and a footprint whose derived figures differ is not a collection.

See docs/environment/capacity-preflight.md, which describes the collection, the
rules, the units, and what a record does not establish.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Final

import yaml

#: The root of this repository.
REPO_ROOT: Final = Path(__file__).resolve().parents[2]

__all__ = [
    "ACCEPTED",
    "AMBIGUOUS",
    "APPLICATIONS",
    "CASES_PATTERN",
    "COLLECTION_SCHEMA",
    "DOES_NOT_ESTABLISH",
    "FOOTPRINT_SCHEMA",
    "HELD",
    "INSUFFICIENT",
    "NOT_HELD",
    "NOT_OBSERVED",
    "RECORD_FILE",
    "RECORD_SCHEMA",
    "REFUSED",
    "REFUSED_EXIT",
    "REPO_ROOT",
    "RESERVE",
    "RESULT_STATES",
    "RULES",
    "RUNS_PATTERN",
    "UNITS",
    "CollectionRefused",
    "FootprintRefused",
    "QuantityRefused",
    "Rule",
    "build_record",
    "check_committed",
    "committed_collections",
    "declared_footprint",
    "footprint_digest",
    "footprint_text",
    "parse_quantity",
    "pod_request",
    "record_text",
    "stale_footprint",
]

#: The identifier of the record :func:`build_record` returns.
RECORD_SCHEMA: Final = "inferops.io/capacity-preflight/v1alpha1"

#: The identifier of the document :func:`declared_footprint` returns.
FOOTPRINT_SCHEMA: Final = "inferops.io/capacity-preflight-footprint/v1alpha1"

#: The identifier of the header a collector writes into a collection.
COLLECTION_SCHEMA: Final = "inferops.io/capacity-preflight-collection/v1alpha1"

#: The file a committed collection holds its record in.
RECORD_FILE: Final = "record.v1alpha1.json"

#: Where this repository holds the committed cases that no cluster produced.
CASES_PATTERN: Final = "tests/domain/fixtures/capacity-preflight/*"

#: Where this repository holds a collection that a cluster produced. A run is
#: added by committing its directory. No list names it.
RUNS_PATTERN: Final = "docs/proof/environment/*-capacity-preflight-run-*"

#: The exit status of a refusal. It is the status with which the V1
#: multi-replica capacity preflight refuses a host.
REFUSED_EXIT: Final = 5

ACCEPTED: Final = "ACCEPTED"
REFUSED: Final = "REFUSED"

#: The result states of a record.
RESULT_STATES: Final = (ACCEPTED, REFUSED)

HELD: Final = "held"
NOT_HELD: Final = "not-held"
NOT_OBSERVED: Final = "not-observed"

INSUFFICIENT: Final = "insufficient"
AMBIGUOUS: Final = "ambiguous"

#: What the gate requires beyond the footprint, in the units of :data:`UNITS`.
#: These are the two headroom figures of the V1 multi-replica certification
#: descriptor. They are not attributed to a pod.
RESERVE: Final[Mapping[str, int]] = {"cpuMillis": 500, "memoryBytes": 536870912}

#: The unit of each kind of figure in a footprint and in a record.
UNITS: Final[Mapping[str, str]] = {
    "cpuMillis": "millicores: one thousandth of one processor",
    "cpuRequestMillis": "millicores: one thousandth of one processor",
    "memoryBytes": "bytes",
    "memoryRequestBytes": "bytes",
    "memoryLimitBytes": "bytes",
    "storageBytes": "bytes",
    "pods": "pods",
}

#: The Application that reads each desired-state release, by the release's key.
#: The Application names the chart and the release's values file, and it states
#: values that the values file does not hold. This tool reads no release
#: declaration: a test compares each entry with the declared desired state.
APPLICATIONS: Final[Mapping[str, str]] = {
    "local-docker-desktop/support-assistant": (
        "infra/argocd/local-docker-desktop-support-assistant.yaml"
    ),
}

_CHART_FILE: Final = "Chart.yaml"
_DEFAULTS_FILE: Final = "values.yaml"
_INSTANCE_LABEL: Final = "app.kubernetes.io/instance"
_STEADY: Final = "steady"
_TRANSIENT: Final = "transient"
_FINISHED: Final = frozenset({"Succeeded", "Failed"})
_BLOCKING_EFFECTS: Final = frozenset({"NoSchedule", "NoExecute"})
_TAINT_EFFECTS: Final = _BLOCKING_EFFECTS | {"PreferNoSchedule"}
#: The three pressure conditions. A node that reports one of them as anything
#: other than False, or that does not report it, does not hold the node rule.
_PRESSURE_CONDITIONS: Final = ("MemoryPressure", "DiskPressure", "PIDPressure")
#: A condition that a node need not report, and that must be False when it does.
_NETWORK_CONDITION: Final = "NetworkUnavailable"
_RESOURCES: Final = frozenset({"cpu", "memory"})
_APPLICATION_MEMBERS: Final[Mapping[str, frozenset[str]]] = {
    "spec": frozenset({"project", "source", "destination", "syncPolicy"}),
    "spec.source": frozenset({"repoURL", "targetRevision", "path", "helm"}),
    "spec.source.helm": frozenset({"releaseName", "valueFiles", "valuesObject"}),
}
_PLACEMENT_MEMBERS: Final = ("nodeSelector", "tolerations", "affinity")
_REVISION: Final = re.compile(r"[0-9a-f]{40}")
_NAME: Final = re.compile(r"[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?")

#: The surge a Deployment has when it states no strategy: 25 percent of its
#: replicas, rounded up. The Kubernetes documentation of the Deployment's
#: ``.spec.strategy.rollingUpdate.maxSurge`` states this default.
_DEFAULT_SURGE_PERCENT: Final = 25

_BINARY: Final[Mapping[str, int]] = {
    "Ki": 2**10,
    "Mi": 2**20,
    "Gi": 2**30,
    "Ti": 2**40,
    "Pi": 2**50,
    "Ei": 2**60,
}
_DECIMAL: Final[Mapping[str, Fraction]] = {
    "n": Fraction(1, 10**9),
    "u": Fraction(1, 10**6),
    "m": Fraction(1, 10**3),
    "": Fraction(1),
    "k": Fraction(10**3),
    "M": Fraction(10**6),
    "G": Fraction(10**9),
    "T": Fraction(10**12),
    "P": Fraction(10**15),
    "E": Fraction(10**18),
}
_QUANTITY: Final = re.compile(
    r"(?P<number>[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
    r"(?:(?P<exponent>[eE][+-]?[0-9]{1,3})|(?P<suffix>Ki|Mi|Gi|Ti|Pi|Ei|[numkMGTPE]))?",
    re.ASCII,
)


@dataclass(frozen=True)
class Rule:
    """One thing the gate decides, and the kind of refusal it gives."""

    rule_id: str
    category: str
    required: bool
    statement: str


#: Every rule, in the order a record states them.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "cluster-reads-complete",
        AMBIGUOUS,
        True,
        "The collection holds each of the four cluster reads, and each is a list.",
    ),
    Rule(
        "reads-well-formed",
        AMBIGUOUS,
        True,
        "Each node and each unfinished pod has the kind, the name, and the member "
        "types that this tool reads, each placed pod names a node of the read, and "
        "the pod list is not empty.",
    ),
    Rule(
        "quantities-readable",
        AMBIGUOUS,
        True,
        "Each processor, memory, pod, and ephemeral-storage figure of each node, "
        "each request of each counted pod, and each size of the model cache claim "
        "is a Kubernetes quantity that is not negative.",
    ),
    Rule(
        "one-schedulable-node",
        AMBIGUOUS,
        True,
        "The cluster has exactly one schedulable node.",
    ),
    Rule(
        "node-ready-without-pressure",
        AMBIGUOUS,
        True,
        "The schedulable node reports Ready as True, it reports each of the memory, "
        "disk, and process pressure conditions as False, and it does not report "
        "the network as unavailable.",
    ),
    Rule(
        "node-states-no-blocking-taint",
        AMBIGUOUS,
        True,
        "The schedulable node states no taint with the effect NoSchedule or NoExecute.",
    ),
    Rule(
        "release-states-no-placement-constraint",
        AMBIGUOUS,
        True,
        "The footprint states no node selector, no toleration, and no affinity.",
    ),
    Rule(
        "namespace-states-no-quota-or-limit-range",
        AMBIGUOUS,
        True,
        "The release namespace holds no ResourceQuota and no LimitRange.",
    ),
    Rule(
        "release-is-not-installed",
        AMBIGUOUS,
        True,
        "The release namespace holds no unfinished pod of the release.",
    ),
    Rule(
        "pod-count-fits",
        INSUFFICIENT,
        True,
        "The pods of the footprint fit in the pod count that the node allocates, "
        "less the unfinished pods that the node holds.",
    ),
    Rule(
        "cpu-requests-fit",
        INSUFFICIENT,
        True,
        "The processor requests of the footprint and the reserve fit in the "
        "processor that the node allocates, less the processor that the unfinished "
        "pods request.",
    ),
    Rule(
        "memory-limits-fit",
        INSUFFICIENT,
        True,
        "The memory limits of the footprint and the reserve fit in the memory that "
        "the node allocates, less the memory that the unfinished pods request.",
    ),
    Rule(
        "model-cache-claim-holds-artifact",
        INSUFFICIENT,
        False,
        "The model cache claim is not Lost, and the smaller of its capacity and its "
        "request is at least the byte count of the model artifact.",
    ),
)

#: What an accepted record does not establish, in the words a record carries.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "A record does not establish that a pod of the release is scheduled, starts, "
    "becomes Ready, or answers a request.",
    "A record does not establish the memory or the processor time that a pod uses. "
    "The gate compares stated requests and stated limits with the figures that the "
    "node allocates.",
    "A record does not establish the use of a pod that states no request. The gate "
    "counts that request as zero. The record states how many counted pods have a "
    "container or an init container that states none.",
    "A record does not establish that the footprint is the release that a "
    "controller applies. The footprint is read from the files of one working tree. "
    "The record does not compare that tree with a commit, or with the revision "
    "that the Application names.",
    "A record does not establish capacity for a pod that is terminating. The "
    "footprint counts the replicas and the surge pods. During a rollout, a pod "
    "that is terminating can hold its request beside the pod that replaces it.",
    "A record does not establish that the node's disk holds the images, the volume "
    "of the model cache claim, or an emptyDir volume.",
    "A record does not establish capacity at another time. It is one reading, and "
    "the cluster can change after it.",
    "A record does not establish capacity for a pod that the footprint does not "
    "state. A load generator and an experiment driver are not in the footprint.",
    "A record does not establish capacity on more than one node, and it does not "
    "establish that the release continues to serve when the node fails.",
    "A record does not establish throughput, latency, an overload threshold, or "
    "availability.",
    "A record does not establish an evidence level, and it registers no claim.",
)


class FootprintRefused(Exception):
    """The committed files do not give one footprint."""


class CollectionRefused(Exception):
    """The directory is not a collection that this tool reads."""


class QuantityRefused(Exception):
    """A value is not a Kubernetes quantity that this tool reads exactly."""


# --------------------------------------------------------------------------
# Quantities
# --------------------------------------------------------------------------


def parse_quantity(value: object) -> Fraction:
    """One Kubernetes quantity as an exact number.

    A whole number, a decimal number, a decimal exponent, one binary suffix, and
    one decimal suffix are read. A sign, a blank, a boolean, and any other text
    are refused. No value is rounded here.

    Raises:
        QuantityRefused: the value is not such a quantity.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise QuantityRefused(f"{value!r} is not a quantity")
    text = repr(value) if isinstance(value, float) else str(value)
    match = _QUANTITY.fullmatch(text)
    if match is None:
        raise QuantityRefused(f"{text!r} is not a quantity")
    number = Fraction(match["number"])
    if match["exponent"]:
        return number * Fraction(10) ** int(match["exponent"][1:])
    suffix = match["suffix"] or ""
    if suffix in _BINARY:
        return number * _BINARY[suffix]
    return number * _DECIMAL[suffix]


def _up(value: Fraction) -> int:
    """The smallest whole number that is not below the value."""
    return -(-value.numerator // value.denominator)


def _down(value: Fraction) -> int:
    """The largest whole number that is not above the value."""
    return value.numerator // value.denominator


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    return value if isinstance(value, list) else ()


def _stated(container: object, kind: str, resource: str) -> object:
    return _mapping(_mapping(_mapping(container).get("resources")).get(kind)).get(
        resource
    )


def _quantity_or_zero(value: object) -> Fraction:
    return Fraction(0) if value is None else parse_quantity(value)


def pod_request(spec: Mapping[str, Any], resource: str) -> tuple[Fraction, bool]:
    """What one pod requests of one resource, and whether each container states it.

    This is the arithmetic that the Kubernetes documentation gives for the
    effective request of a pod. A request that the pod states for itself is the
    request. Without one, the request is the larger of two figures: the sum over
    the containers and the restartable init containers, and the largest init
    container beside the restartable init containers that start before it. The
    pod's overhead is added.

    The second member is False when the pod states no request for itself and one
    of its containers or init containers states none. That container is counted
    as zero.

    Raises:
        QuantityRefused: a stated request is not a quantity.
    """
    overhead = _quantity_or_zero(_mapping(spec.get("overhead")).get(resource))
    own = _mapping(_mapping(spec.get("resources")).get("requests")).get(resource)
    containers = _sequence(spec.get("containers"))
    if own is not None:
        return parse_quantity(own) + overhead, True

    every = all(
        _stated(container, "requests", resource) is not None
        for container in (*containers, *_sequence(spec.get("initContainers")))
    )
    running = sum(
        (
            _quantity_or_zero(_stated(container, "requests", resource))
            for container in containers
        ),
        Fraction(0),
    )
    restartable = Fraction(0)
    largest = Fraction(0)
    for container in _sequence(spec.get("initContainers")):
        request = _quantity_or_zero(_stated(container, "requests", resource))
        if _mapping(container).get("restartPolicy") == "Always":
            restartable += request
        else:
            largest = max(largest, request + restartable)
    return max(running + restartable, largest) + overhead, every


# --------------------------------------------------------------------------
# The declared footprint
# --------------------------------------------------------------------------


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _application_path(key: str | None) -> tuple[str, str]:
    """The key of one release, and the Application that reads it."""
    if key is None:
        if len(APPLICATIONS) != 1:
            raise FootprintRefused("more than one Application is declared; give a key")
        key = next(iter(APPLICATIONS))
    if key not in APPLICATIONS:
        raise FootprintRefused(f"no Application is declared for the release {key!r}")
    return key, APPLICATIONS[key]


def _repository_path(value: object, what: str) -> str:
    """A path that a committed file names, relative to the repository root."""
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise FootprintRefused(f"{what} is not a path inside the repository: {value!r}")
    return value


def _merged(base: object, over: object) -> object:
    """The second document over the first, as Helm merges two values documents.

    A mapping is merged member by member, and any other value replaces the
    earlier one. A null in the second document removes the member, as the Helm
    documentation states for a null in a later values document.
    """
    if isinstance(base, Mapping) and isinstance(over, Mapping):
        merged = dict(base)
        for name, value in over.items():
            if value is None:
                merged.pop(name, None)
            elif name in base:
                merged[name] = _merged(base[name], value)
            else:
                merged[name] = value
        return merged
    return over


def _member(document: object, *path: str) -> Any:
    current: object = document
    for name in path:
        if not isinstance(current, Mapping) or name not in current:
            raise FootprintRefused(f"the value {'.'.join(path)} is absent")
        current = current[name]
    return current


def _whole(document: object, *path: str) -> int:
    value = _member(document, *path)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FootprintRefused(f"the value {'.'.join(path)} is not a whole number")
    return value


def _container(values: object, name: str, *path: str) -> dict[str, Any]:
    resources = _member(values, *path)
    stated: dict[str, Any] = {"name": name, "source": ".".join(path)}
    for kind in ("requests", "limits"):
        block = _mapping(resources).get(kind)
        if block is not None and not isinstance(block, Mapping):
            raise FootprintRefused(
                f"the value {'.'.join(path)}.{kind} is not a mapping"
            )
        other = sorted(set(_mapping(block)) - _RESOURCES)
        if other:
            raise FootprintRefused(
                f"the value {'.'.join(path)}.{kind} states a resource that this gate "
                f"does not compare: {', '.join(other)}"
            )
    for kind, members in (("requests", ("cpu", "memory")), ("limits", ("memory",))):
        stated[kind] = {}
        for resource in members:
            value = _mapping(_mapping(resources).get(kind)).get(resource)
            if value is None:
                raise FootprintRefused(
                    f"the value {'.'.join(path)}.{kind}.{resource} is absent, so "
                    f"the container {name} states no bound for it"
                )
            stated[kind][resource] = str(value)
    return stated


def _component(
    component: str,
    kind: str,
    *,
    replicas: int,
    surge: int,
    surge_source: str,
    containers: Sequence[Mapping[str, Any]],
    init: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "component": component,
        "kind": kind,
        "class": _STEADY if kind == "Deployment" else _TRANSIENT,
        "replicas": replicas,
        "surgePods": surge,
        "surgeSource": surge_source,
        "containers": [dict(container) for container in containers],
        "initContainers": [dict(container) for container in init],
    }


def _pod_figures(component: Mapping[str, Any]) -> dict[str, int]:
    """What one pod of a component requests, and its memory limit."""
    spec = {
        "containers": [
            {"resources": {"requests": c["requests"]}} for c in component["containers"]
        ],
        "initContainers": [
            {"resources": {"requests": c["requests"]}}
            for c in component["initContainers"]
        ],
    }
    limit = sum(
        (parse_quantity(c["limits"]["memory"]) for c in component["containers"]),
        Fraction(0),
    )
    for container in component["initContainers"]:
        limit = max(limit, parse_quantity(container["limits"]["memory"]))
    return {
        "cpuRequestMillis": _up(pod_request(spec, "cpu")[0] * 1000),
        "memoryRequestBytes": _up(pod_request(spec, "memory")[0]),
        "memoryLimitBytes": _up(limit),
    }


_FIGURES: Final = ("cpuRequestMillis", "memoryRequestBytes", "memoryLimitBytes")


def _derived(stated: Mapping[str, Any]) -> dict[str, Any]:
    """A footprint with each derived figure computed from its stated quantities."""
    footprint = {name: value for name, value in stated.items() if name != "totals"}
    components = []
    totals = {
        name: dict.fromkeys(("pods", *_FIGURES), 0)
        for name in (_STEADY, "rolloutHeadroom", _TRANSIENT)
    }
    for entry in stated["components"]:
        component = {name: value for name, value in entry.items() if name != "pod"}
        pod = _pod_figures(component)
        if pod["memoryLimitBytes"] < pod["memoryRequestBytes"]:
            raise QuantityRefused(
                f"the memory limit of one {component['component']} pod is below its "
                "memory request"
            )
        component["pod"] = pod
        components.append(component)
        for name, count in (
            (component["class"], component["replicas"]),
            ("rolloutHeadroom", component["surgePods"]),
        ):
            totals[name]["pods"] += count
            for figure in _FIGURES:
                totals[name][figure] += count * pod[figure]
    footprint["components"] = components
    summed = {
        name: sum(totals[part][name] for part in totals) for name in ("pods", *_FIGURES)
    }
    footprint["totals"] = {
        **totals,
        "reserve": dict(RESERVE),
        "required": {
            "pods": summed["pods"],
            "cpuRequestMillis": summed["cpuRequestMillis"] + RESERVE["cpuMillis"],
            "memoryRequestBytes": summed["memoryRequestBytes"] + RESERVE["memoryBytes"],
            "memoryLimitBytes": summed["memoryLimitBytes"] + RESERVE["memoryBytes"],
        },
    }
    return footprint


def declared_footprint(
    key: str | None = None, root: Path = REPO_ROOT
) -> dict[str, Any]:
    """Each pod that the chart renders for one desired-state release, with its bounds.

    The Application that reads the release names the chart and one values file.
    The values are the chart's defaults, then that file, then the values that
    the Application states itself. A later document replaces a member of an
    earlier one, as Helm merges values documents.

    The pods are restated here from the chart's templates. A test renders the
    chart with the same three documents and compares each pod of the render with
    this footprint.

    Raises:
        FootprintRefused: no Application is declared for the key, a committed
            file is absent, the Application names no one values file inside the
            repository, a value is absent, or the release is not the real
            profile.
    """
    release, application_path = _application_path(key)
    try:
        application_bytes = (root / application_path).read_bytes()
        application = yaml.safe_load(application_bytes.decode("utf-8"))
    except OSError as error:
        raise FootprintRefused(f"a committed file was not read: {error}") from error
    except (UnicodeError, yaml.YAMLError) as error:
        raise FootprintRefused(f"a committed file is not YAML: {error}") from error

    if _mapping(application).get("kind") != "Application":
        raise FootprintRefused(f"{application_path} is not an Application")
    source = _member(application, "spec", "source")
    helm = _member(source, "helm")
    for label, block in (
        ("spec", _member(application, "spec")),
        ("spec.source", source),
        ("spec.source.helm", helm),
    ):
        if not isinstance(block, Mapping):
            raise FootprintRefused(f"{label} of {application_path} is not a mapping")
        other = sorted(set(block) - _APPLICATION_MEMBERS[label])
        if other:
            raise FootprintRefused(
                f"{application_path} states a member of {label} that this tool does "
                f"not read: {', '.join(other)}"
            )
    overlay = helm.get("valuesObject", {})
    if not isinstance(overlay, Mapping):
        raise FootprintRefused(
            f"spec.source.helm.valuesObject of {application_path} is not a mapping"
        )
    chart_directory = _repository_path(
        _member(source, "path"), f"the chart path of {application_path}"
    )
    files = _member(helm, "valueFiles")
    if (
        not isinstance(files, list)
        or len(files) != 1
        or not isinstance(files[0], str)
        or not files[0].startswith("/")
    ):
        raise FootprintRefused(
            f"{application_path} does not read one values file from the root of the "
            "repository"
        )
    values_path = _repository_path(
        files[0][1:], f"the values file of {application_path}"
    )
    defaults_path = f"{chart_directory}/{_DEFAULTS_FILE}"
    try:
        defaults_bytes = (root / defaults_path).read_bytes()
        values_bytes = (root / values_path).read_bytes()
        chart = yaml.safe_load(
            (root / chart_directory / _CHART_FILE).read_text(encoding="utf-8")
        )
        defaults = yaml.safe_load(defaults_bytes.decode("utf-8"))
        generated = yaml.safe_load(values_bytes.decode("utf-8"))
    except OSError as error:
        raise FootprintRefused(f"a committed file was not read: {error}") from error
    except (UnicodeError, yaml.YAMLError) as error:
        raise FootprintRefused(f"a committed file is not YAML: {error}") from error
    values = _merged(_merged(defaults, generated), overlay)
    if _member(values, "profile") != "real":
        raise FootprintRefused("the release is not the real profile")

    api_replicas = _whole(values, "api", "replicaCount")
    runtime_replicas = _whole(values, "runtime", "replicaCount")
    components = [
        _component(
            "platform-api",
            "Deployment",
            replicas=api_replicas,
            surge=_whole(values, "api", "rollout", "maxSurge"),
            surge_source="api.rollout.maxSurge",
            containers=[_container(values, "api", "api", "resources")],
        ),
        _component(
            "serving-runtime",
            "Deployment",
            replicas=runtime_replicas,
            surge=_whole(values, "runtime", "rollout", "maxSurge"),
            surge_source="runtime.rollout.maxSurge",
            containers=[_container(values, "runtime", "runtime", "resources")],
            init=[
                _container(values, "verify-model", "model", "integrity", "resources")
            ],
        ),
    ]
    telemetry = _member(values, "telemetry")
    collection = _member(telemetry, "collection")
    if (
        _member(telemetry, "enabled")
        and _member(collection, "enabled")
        and _member(collection, "collector", "deploy")
    ):
        components.append(
            _component(
                "telemetry-collector",
                "Deployment",
                replicas=1,
                surge=_up(Fraction(_DEFAULT_SURGE_PERCENT, 100)),
                surge_source=(
                    "Kubernetes default: the chart states no strategy for this "
                    f"Deployment, and the default surge is {_DEFAULT_SURGE_PERCENT} "
                    "percent of the replicas, rounded up"
                ),
                containers=[
                    _container(
                        values,
                        "collector",
                        "telemetry",
                        "collection",
                        "collector",
                        "resources",
                    )
                ],
            )
        )
    if _member(values, "model", "acquisition", "enabled"):
        components.append(
            _component(
                "model-acquisition",
                "Job",
                replicas=1,
                surge=0,
                surge_source="none: a hook Job has no rollout",
                containers=[
                    _container(
                        values, "acquire-model", "model", "acquisition", "resources"
                    )
                ],
            )
        )
    if _member(values, "tests", "enabled"):
        components.append(
            _component(
                "connection-test",
                "Pod",
                replicas=1,
                surge=0,
                surge_source="none: a test pod has no rollout",
                containers=[_container(values, "connection", "tests", "resources")],
            )
        )

    placement = sorted(
        f"{tier}.{member}"
        for tier in ("api", "runtime")
        for member in _PLACEMENT_MEMBERS
        if _member(values, tier, member)
    )
    try:
        return _derived(
            {
                "schema": FOOTPRINT_SCHEMA,
                "release": {
                    "key": release,
                    "name": str(_member(helm, "releaseName")),
                    "namespace": str(
                        _member(application, "spec", "destination", "namespace")
                    ),
                },
                "sources": {
                    "chart": {
                        "path": chart_directory,
                        "name": str(_member(chart, "name")),
                        "version": str(_member(chart, "version")),
                    },
                    "chartDefaults": {
                        "path": defaults_path,
                        "sha256": _sha256(_lf(defaults_bytes)),
                    },
                    "generatedValues": {
                        "path": values_path,
                        "sha256": _sha256(_lf(values_bytes)),
                    },
                    "application": {
                        "path": application_path,
                        "sha256": _sha256(_lf(application_bytes)),
                        "repoURL": str(_member(source, "repoURL")),
                        "targetRevision": str(_member(source, "targetRevision")),
                    },
                },
                "topology": {
                    "apiReplicas": api_replicas,
                    "runtimeReplicas": runtime_replicas,
                },
                "model": {
                    "identifier": str(_member(values, "model", "identifier")),
                    "artifactBytes": _whole(values, "model", "artifact", "sizeBytes"),
                    "cacheClaimName": str(
                        _member(values, "model", "cache", "claimName")
                    ),
                },
                "placementConstraints": placement,
                "components": components,
            }
        )
    except QuantityRefused as refused:
        raise FootprintRefused(
            f"a stated resource is not readable: {refused}"
        ) from refused


def footprint_text(footprint: Mapping[str, Any]) -> str:
    """The bytes a collection holds its footprint in."""
    return json.dumps(footprint, indent=2, sort_keys=True) + "\n"


def footprint_digest(footprint: Mapping[str, Any]) -> str:
    """The SHA-256 of a footprint's canonical bytes."""
    return _sha256(footprint_text(footprint).encode("utf-8"))


def stale_footprint(directory: Path, root: Path = REPO_ROOT) -> str | None:
    """Why a collection's footprint is not the one the committed files give now.

    Returns None when the stored footprint is the declared footprint of its
    release in this tree.

    Raises:
        CollectionRefused: the directory holds no usable footprint.
        FootprintRefused: this tree gives no footprint for the release.
    """
    stored = _stored_footprint(directory)
    current = declared_footprint(str(stored["release"]["key"]), root)
    if stored == current:
        return None
    return (
        f"the stored footprint {footprint_digest(stored)} is not the footprint "
        f"{footprint_digest(current)} that the committed files give"
    )


# --------------------------------------------------------------------------
# Reading a collection
# --------------------------------------------------------------------------


_READS: Final[Mapping[str, str]] = {
    "nodes": "nodes.json",
    "pods": "pods.json",
    "namespaceLimits": "namespace-limits.json",
    "claims": "claims.json",
}
_HEADER_FILE: Final = "run.json"
_FOOTPRINT_FILE: Final = "footprint.json"
_ENGINE_FILE: Final = "engine.json"
_VERSION_FILE: Final = "version.json"


def _read(directory: Path, name: str) -> bytes | None:
    try:
        return (directory / name).read_bytes()
    except OSError:
        return None


def _json(directory: Path, name: str) -> Any:
    data = _read(directory, name)
    if data is None:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None


def _items(directory: Path, name: str) -> list[Any] | None:
    """The items of one list read, or None when the read is not a list."""
    document = _json(directory, name)
    if not isinstance(document, Mapping):
        return None
    items = document.get("items")
    if not isinstance(items, list) or not all(isinstance(i, Mapping) for i in items):
        return None
    return items


def _text_member(header: Mapping[str, Any], name: str) -> str:
    value = header.get(name)
    if not isinstance(value, str) or not value.strip():
        raise CollectionRefused(f"{_HEADER_FILE} states no {name}")
    return value


def _header(directory: Path) -> dict[str, str]:
    header = _json(directory, _HEADER_FILE)
    if not isinstance(header, Mapping):
        raise CollectionRefused(f"the directory holds no readable {_HEADER_FILE}")
    if header.get("schema") != COLLECTION_SCHEMA:
        raise CollectionRefused(f"{_HEADER_FILE} does not state {COLLECTION_SCHEMA}")
    members = {
        name: _text_member(header, name)
        for name in (
            "provider",
            "context",
            "releaseKey",
            "namespace",
            "executingCommit",
            "collectedAt",
        )
    }
    if _REVISION.fullmatch(members["executingCommit"]) is None:
        raise CollectionRefused(f"{_HEADER_FILE} states no full executing commit")
    return members


def _stored_footprint(directory: Path) -> dict[str, Any]:
    stored = _json(directory, _FOOTPRINT_FILE)
    if not isinstance(stored, dict) or stored.get("schema") != FOOTPRINT_SCHEMA:
        raise CollectionRefused(f"the directory holds no readable {_FOOTPRINT_FILE}")
    try:
        derived = _derived(stored)
        release = stored["release"]
        usable = (
            all(isinstance(release[name], str) for name in ("key", "name", "namespace"))
            and isinstance(stored["model"]["artifactBytes"], int)
            and not isinstance(stored["model"]["artifactBytes"], bool)
            and isinstance(stored["model"]["cacheClaimName"], str)
            and isinstance(stored["placementConstraints"], list)
            and bool(stored["components"])
            and all(
                isinstance(component[name], int)
                and not isinstance(component[name], bool)
                and component[name] >= 0
                for component in stored["components"]
                for name in ("replicas", "surgePods")
            )
        )
    except (AttributeError, KeyError, TypeError, ValueError, QuantityRefused) as error:
        raise CollectionRefused(
            f"{_FOOTPRINT_FILE} lacks a member, or states a quantity that is not "
            f"readable: {error!r}"
        ) from error
    if not usable:
        raise CollectionRefused(f"{_FOOTPRINT_FILE} states a member of another type")
    if derived != stored:
        raise CollectionRefused(
            f"{_FOOTPRINT_FILE} states a derived figure or a reserve that its stated "
            "quantities and this tool's reserve do not give"
        )
    return stored


def _typed(value: object, kind: type, what: str, faults: list[str]) -> bool:
    """True when a member is absent or has the type. Another type is a fault."""
    if value is None or isinstance(value, kind):
        return True
    faults.append(f"{what} is not of the type that this tool reads")
    return False


def _name(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _node_shape(item: Mapping[str, Any], label: str, faults: list[str]) -> None:
    if item.get("kind") != "Node":
        faults.append(f"{label} is not a Node")
    spec = item.get("spec")
    status = item.get("status")
    _typed(spec, Mapping, f"{label}: spec", faults)
    if not isinstance(status, Mapping):
        faults.append(f"{label}: status is not a mapping")
    spec, status = _mapping(spec), _mapping(status)
    _typed(spec.get("unschedulable"), bool, f"{label}: spec.unschedulable", faults)
    if _typed(spec.get("taints"), list, f"{label}: spec.taints", faults):
        for taint in _sequence(spec.get("taints")):
            if (
                not isinstance(taint, Mapping)
                or taint.get("effect") not in _TAINT_EFFECTS
            ):
                faults.append(f"{label}: a taint states no effect that this tool reads")
    for member in ("capacity", "allocatable"):
        _typed(status.get(member), Mapping, f"{label}: status.{member}", faults)
    conditions = status.get("conditions")
    if _typed(conditions, list, f"{label}: status.conditions", faults):
        seen: set[object] = set()
        for condition in _sequence(conditions):
            kind = _mapping(condition).get("type")
            if (
                not isinstance(condition, Mapping)
                or _name(kind) is None
                or _name(condition.get("status")) is None
            ):
                faults.append(f"{label}: a condition states no type or no status")
            elif kind in seen:
                faults.append(f"{label}: the condition {kind} is stated two times")
            seen.add(kind)


def _containers_shape(spec: Mapping[str, Any], label: str, faults: list[str]) -> None:
    containers = spec.get("containers")
    if not isinstance(containers, list) or not containers:
        faults.append(f"{label}: spec.containers is not a list of containers")
    _typed(spec.get("initContainers"), list, f"{label}: spec.initContainers", faults)
    for member in ("overhead", "resources"):
        _typed(spec.get(member), Mapping, f"{label}: spec.{member}", faults)
    _typed(
        _mapping(spec.get("resources")).get("requests"),
        Mapping,
        f"{label}: spec.resources.requests",
        faults,
    )
    for container in (
        *_sequence(containers),
        *_sequence(spec.get("initContainers")),
    ):
        if not isinstance(container, Mapping):
            faults.append(f"{label}: a container is not a mapping")
            continue
        resources = container.get("resources")
        _typed(resources, Mapping, f"{label}: a container's resources", faults)
        _typed(
            _mapping(resources).get("requests"),
            Mapping,
            f"{label}: a container's requests",
            faults,
        )
        _typed(
            container.get("restartPolicy"),
            str,
            f"{label}: a container's restartPolicy",
            faults,
        )


def _shape_faults(
    nodes: Sequence[Mapping[str, Any]], pods: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Each node and each unfinished pod that does not have the form this tool reads.

    A member of another type is not read as absent. A pod list without a pod is
    not read as a cluster that holds nothing: a cluster with a Ready node holds
    the pods of its own system.
    """
    faults: list[str] = []
    names: list[str] = []
    for index, node in enumerate(nodes):
        name = _name(_mapping(node.get("metadata")).get("name"))
        label = f"node {name}" if name else f"node at index {index}"
        if name is None:
            faults.append(f"{label} states no name")
        elif name in names:
            faults.append(f"{label} is listed two times")
        else:
            names.append(name)
        _node_shape(node, label, faults)
    if not pods:
        faults.append("the pod list holds no pod")
    for index, pod in enumerate(pods):
        metadata = _mapping(pod.get("metadata"))
        name = _name(metadata.get("name"))
        namespace = _name(metadata.get("namespace"))
        label = (
            f"pod {namespace}/{name}" if name and namespace else f"pod at index {index}"
        )
        if name is None or namespace is None:
            faults.append(f"{label} states no name or no namespace")
        if pod.get("kind") != "Pod":
            faults.append(f"{label} is not a Pod")
        status = pod.get("status")
        if not isinstance(status, Mapping):
            faults.append(f"{label}: status is not a mapping")
            continue
        _typed(status.get("phase"), str, f"{label}: status.phase", faults)
        if status.get("phase") in _FINISHED:
            continue
        spec = pod.get("spec")
        if not isinstance(spec, Mapping):
            faults.append(f"{label}: spec is not a mapping")
            continue
        placed = spec.get("nodeName")
        if placed is not None and placed not in names:
            faults.append(f"{label}: nodeName names no node of the read")
        _typed(metadata.get("labels"), Mapping, f"{label}: metadata.labels", faults)
        _containers_shape(spec, label, faults)
    return faults


def _condition(node: Mapping[str, Any], name: str) -> str | None:
    for condition in _sequence(_mapping(node.get("status")).get("conditions")):
        if _mapping(condition).get("type") == name:
            status = _mapping(condition).get("status")
            return status if isinstance(status, str) else None
    return None


def _node(node: Mapping[str, Any], faults: list[str]) -> dict[str, Any]:
    name = _mapping(node.get("metadata")).get("name")
    status = _mapping(node.get("status"))

    def figures(member: str) -> dict[str, int | None]:
        stated = _mapping(status.get(member))
        out: dict[str, int | None] = {}
        for label, resource, scale in (
            ("cpuMillis", "cpu", 1000),
            ("memoryBytes", "memory", 1),
            ("pods", "pods", 1),
            ("ephemeralStorageBytes", "ephemeral-storage", 1),
        ):
            try:
                out[label] = (
                    None
                    if stated.get(resource) is None
                    else _down(parse_quantity(stated[resource]) * scale)
                )
            except QuantityRefused as refused:
                faults.append(f"node {name}: {member}.{resource}: {refused}")
                out[label] = None
        return out

    return {
        "name": name if isinstance(name, str) else None,
        "schedulable": _mapping(node.get("spec")).get("unschedulable") is not True,
        "ready": _condition(node, "Ready"),
        "pressure": sorted(
            f"{condition}={_condition(node, condition)}"
            for condition in (*_PRESSURE_CONDITIONS, _NETWORK_CONDITION)
            if _condition(node, condition) != "False"
            and not (
                condition == _NETWORK_CONDITION and _condition(node, condition) is None
            )
        ),
        "blockingTaints": sorted(
            f"{_mapping(taint).get('key')}:{_mapping(taint).get('effect')}"
            for taint in _sequence(_mapping(node.get("spec")).get("taints"))
            if _mapping(taint).get("effect") in _BLOCKING_EFFECTS
        ),
        "kubeletVersion": _mapping(status.get("nodeInfo")).get("kubeletVersion"),
        "capacity": figures("capacity"),
        "allocatable": figures("allocatable"),
    }


def _reservations(
    pods: Sequence[Mapping[str, Any]],
    node_name: str | None,
    footprint: Mapping[str, Any],
    faults: list[str],
) -> dict[str, Any]:
    """What the unfinished pods request on one node, by namespace.

    Without exactly one schedulable node there is no node to count against. The
    counts are then null, and the pods of the release are still named.
    """
    by_namespace: dict[str, dict[str, int]] = {}
    counted = finished = elsewhere = unscheduled = no_cpu = no_memory = 0
    release_pods: list[str] = []
    release = footprint["release"]
    for pod in pods:
        metadata = _mapping(pod.get("metadata"))
        spec = _mapping(pod.get("spec"))
        namespace = str(metadata.get("namespace"))
        label = f"{namespace}/{metadata.get('name')}"
        if _mapping(pod.get("status")).get("phase") in _FINISHED:
            finished += 1
            continue
        if (
            namespace == release["namespace"]
            and _mapping(metadata.get("labels")).get(_INSTANCE_LABEL) == release["name"]
        ):
            release_pods.append(label)
        placed = spec.get("nodeName")
        if placed is None:
            unscheduled += 1
        elif placed != node_name:
            elsewhere += 1
            continue
        try:
            cpu, cpu_stated = pod_request(spec, "cpu")
            memory, memory_stated = pod_request(spec, "memory")
        except QuantityRefused as refused:
            faults.append(f"pod {label}: {refused}")
            continue
        counted += 1
        no_cpu += not cpu_stated
        no_memory += not memory_stated
        row = by_namespace.setdefault(
            namespace, {"pods": 0, "cpuRequestMillis": 0, "memoryRequestBytes": 0}
        )
        row["pods"] += 1
        row["cpuRequestMillis"] += _up(cpu * 1000)
        row["memoryRequestBytes"] += _up(memory)
    if node_name is None:
        return {
            "node": None,
            "unfinishedPods": None,
            "finishedPodsNotCounted": finished,
            "podsOnAnotherNodeNotCounted": None,
            "unscheduledPodsCounted": None,
            "podsWithAContainerThatStatesNoCpuRequest": None,
            "podsWithAContainerThatStatesNoMemoryRequest": None,
            "cpuRequestMillis": None,
            "memoryRequestBytes": None,
            "byNamespace": [],
            "releasePods": sorted(release_pods),
        }
    return {
        "node": node_name,
        "unfinishedPods": counted,
        "finishedPodsNotCounted": finished,
        "podsOnAnotherNodeNotCounted": elsewhere,
        "unscheduledPodsCounted": unscheduled,
        "podsWithAContainerThatStatesNoCpuRequest": no_cpu,
        "podsWithAContainerThatStatesNoMemoryRequest": no_memory,
        "cpuRequestMillis": sum(r["cpuRequestMillis"] for r in by_namespace.values()),
        "memoryRequestBytes": sum(
            r["memoryRequestBytes"] for r in by_namespace.values()
        ),
        "byNamespace": [
            {"namespace": namespace, **by_namespace[namespace]}
            for namespace in sorted(by_namespace)
        ],
        "releasePods": sorted(release_pods),
    }


def _claim(
    claims: Sequence[Mapping[str, Any]] | None, name: str, faults: list[str]
) -> dict[str, Any] | None:
    for claim in claims or ():
        if _mapping(claim.get("metadata")).get("name") != name:
            continue
        spec = _mapping(claim.get("spec"))
        status = _mapping(claim.get("status"))
        figures: dict[str, int | None] = {}
        for label, value in (
            (
                "requestedStorageBytes",
                _mapping(_mapping(spec.get("resources")).get("requests")).get(
                    "storage"
                ),
            ),
            ("capacityStorageBytes", _mapping(status.get("capacity")).get("storage")),
        ):
            try:
                figures[label] = None if value is None else _down(parse_quantity(value))
            except QuantityRefused as refused:
                faults.append(f"claim {name}: {label}: {refused}")
                figures[label] = None
        return {
            "name": name,
            "phase": status.get("phase"),
            "accessModes": list(_sequence(spec.get("accessModes"))),
            "storageClassName": spec.get("storageClassName"),
            **figures,
        }
    return None


def _engine(directory: Path) -> dict[str, int] | None:
    engine = _json(directory, _ENGINE_FILE)
    if not isinstance(engine, Mapping):
        return None
    figures = {name: engine.get(name) for name in ("cpus", "memoryBytes")}
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in figures.values()
    ):
        return None
    return {name: int(value) for name, value in figures.items() if value is not None}


def _server_version(directory: Path) -> str | None:
    version = _mapping(_mapping(_json(directory, _VERSION_FILE)).get("serverVersion"))
    stated = version.get("gitVersion")
    return stated if isinstance(stated, str) else None


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------


def _finding(
    rule: Rule, state: str, detail: str, measure: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "ruleId": rule.rule_id,
        "category": rule.category,
        "required": rule.required,
        "statement": rule.statement,
        "state": state,
        "detail": detail,
    }
    if measure is not None:
        finding["measure"] = dict(measure)
    return finding


def _fit(required: int, allocatable: int, reserved: int, unit: str) -> dict[str, Any]:
    available = allocatable - reserved
    return {
        "required": required,
        "allocatable": allocatable,
        "requestedByUnfinishedPods": reserved,
        "available": available,
        "shortfall": max(0, required - available),
        "unit": unit,
    }


def _evaluate(
    *,
    footprint: Mapping[str, Any],
    absent: Sequence[str],
    shape: Sequence[str] | None,
    faults: Sequence[str],
    nodes: Sequence[Mapping[str, Any]] | None,
    reservations: Mapping[str, Any] | None,
    limits: Sequence[Mapping[str, Any]] | None,
    claim: Mapping[str, Any] | None,
    claims_read: bool,
) -> list[dict[str, Any]]:
    rules = {rule.rule_id: rule for rule in RULES}
    findings: list[dict[str, Any]] = []

    def add(
        rule_id: str, state: str, detail: str, measure: Mapping[str, Any] | None = None
    ) -> None:
        findings.append(_finding(rules[rule_id], state, detail, measure))

    add(
        "cluster-reads-complete",
        NOT_OBSERVED if absent else HELD,
        (
            "not read, or not a list: " + ", ".join(absent)
            if absent
            else "each of the four reads is a list"
        ),
    )

    if shape is None:
        add("reads-well-formed", NOT_OBSERVED, "the nodes or the pods were not read")
    elif shape:
        add("reads-well-formed", NOT_HELD, "; ".join(shape))
    else:
        add("reads-well-formed", HELD, "each node and each unfinished pod was read")

    readable = nodes is not None and reservations is not None
    if not readable:
        add("quantities-readable", NOT_OBSERVED, "the nodes or the pods were not read")
    elif faults:
        add("quantities-readable", NOT_HELD, "; ".join(faults))
    else:
        add("quantities-readable", HELD, "each stated quantity was read exactly")

    schedulable = [node for node in nodes or () if node["schedulable"]]
    node = schedulable[0] if len(schedulable) == 1 else None
    if nodes is None:
        add("one-schedulable-node", NOT_OBSERVED, "the nodes were not read")
    elif node is None:
        add(
            "one-schedulable-node",
            NOT_HELD,
            f"{len(schedulable)} schedulable node(s) of {len(nodes)} node(s). The "
            "gate adds figures for one node. It does not decide where a pod is "
            "placed among nodes, and both serving runtime pods mount one claim.",
        )
    else:
        add("one-schedulable-node", HELD, f"the node {node['name']}")

    for rule_id, missing in (
        ("node-ready-without-pressure", "ready"),
        ("node-states-no-blocking-taint", "taints"),
    ):
        if node is None:
            add(rule_id, NOT_OBSERVED, "this rule needs one schedulable node")
        elif missing == "ready":
            held = node["ready"] == "True" and not node["pressure"]
            add(
                rule_id,
                HELD if held else NOT_HELD,
                f"Ready is {node['ready']}; conditions that are not reported as "
                f"False: {', '.join(node['pressure']) or 'none'}",
            )
        else:
            add(
                rule_id,
                NOT_HELD if node["blockingTaints"] else HELD,
                "blocking taints: " + (", ".join(node["blockingTaints"]) or "none"),
            )

    constraints = footprint["placementConstraints"]
    add(
        "release-states-no-placement-constraint",
        NOT_HELD if constraints else HELD,
        "values that state a constraint: " + (", ".join(constraints) or "none"),
    )

    if limits is None:
        add(
            "namespace-states-no-quota-or-limit-range",
            NOT_OBSERVED,
            "the quota and limit-range objects were not read",
        )
    else:
        named = sorted(
            f"{item.get('kind')}/{_mapping(item.get('metadata')).get('name')}"
            for item in limits
        )
        add(
            "namespace-states-no-quota-or-limit-range",
            NOT_HELD if named else HELD,
            "objects: " + (", ".join(named) or "none"),
        )

    if reservations is None:
        add("release-is-not-installed", NOT_OBSERVED, "the pods were not read")
    else:
        present = reservations["releasePods"]
        add(
            "release-is-not-installed",
            NOT_HELD if present else HELD,
            (
                "unfinished pods of the release: " + ", ".join(present) + ". Their "
                "requests are in the node's figures, so the gate would count the "
                "release two times."
                if present
                else "no unfinished pod of the release"
            ),
        )

    required = footprint["totals"]["required"]
    usable = (
        node is not None
        and reservations is not None
        and shape is not None
        and not shape
        and not faults
        and all(
            node["allocatable"][name] is not None
            for name in ("pods", "cpuMillis", "memoryBytes")
        )
    )
    fits = (
        ("pod-count-fits", "pods", "pods", "unfinishedPods", "pods"),
        (
            "cpu-requests-fit",
            "cpuRequestMillis",
            "cpuMillis",
            "cpuRequestMillis",
            "millicores",
        ),
        (
            "memory-limits-fit",
            "memoryLimitBytes",
            "memoryBytes",
            "memoryRequestBytes",
            "bytes",
        ),
    )
    for rule_id, need, allocatable, reserved, unit in fits:
        if not usable or node is None or reservations is None:
            add(
                rule_id,
                NOT_OBSERVED,
                "this rule needs well-formed reads, one schedulable node whose "
                "allocatable figures are stated, and readable quantities",
            )
            continue
        measure = _fit(
            required[need],
            node["allocatable"][allocatable],
            reservations[reserved],
            unit,
        )
        add(
            rule_id,
            NOT_HELD if measure["shortfall"] else HELD,
            f"{measure['required']} {unit} required, {measure['available']} {unit} "
            f"available"
            + (
                f", {measure['shortfall']} {unit} short" if measure["shortfall"] else ""
            ),
            measure,
        )

    artifact = footprint["model"]["artifactBytes"]
    if not claims_read:
        add(
            "model-cache-claim-holds-artifact", NOT_OBSERVED, "the claims were not read"
        )
    elif claim is None:
        add(
            "model-cache-claim-holds-artifact",
            NOT_OBSERVED,
            f"the namespace holds no claim named "
            f"{footprint['model']['cacheClaimName']}. Each serving runtime pod "
            "mounts that claim, and the release does not create it.",
        )
    else:
        sizes = {
            basis: claim[member]
            for basis, member in (
                ("capacity", "capacityStorageBytes"),
                ("request", "requestedStorageBytes"),
            )
            if claim[member] is not None
        }
        basis = min(sizes, key=lambda name: sizes[name]) if sizes else ""
        size = sizes.get(basis)
        if claim["phase"] == "Lost":
            add(
                "model-cache-claim-holds-artifact",
                NOT_HELD,
                "the claim reports the phase Lost",
            )
        elif size is None:
            add(
                "model-cache-claim-holds-artifact",
                NOT_OBSERVED,
                "the claim states no readable size",
            )
        else:
            add(
                "model-cache-claim-holds-artifact",
                HELD if size >= artifact else NOT_HELD,
                f"the claim's {basis} is {size} bytes, and the artifact is "
                f"{artifact} bytes",
                {
                    "required": artifact,
                    "available": size,
                    "shortfall": max(0, artifact - size),
                    "unit": "bytes",
                },
            )
    return findings


def _refusal(findings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Each rule that refuses, and the category of each."""
    refusing = [
        finding
        for finding in findings
        if finding["state"] == NOT_HELD
        or (finding["state"] == NOT_OBSERVED and finding["required"])
    ]
    return {
        "categories": sorted(
            {
                AMBIGUOUS if f["state"] == NOT_OBSERVED else f["category"]
                for f in refusing
            }
        ),
        "rules": [finding["ruleId"] for finding in refusing],
    }


def build_record(directory: Path) -> dict[str, Any]:
    """The record of one collection.

    The record is built from the footprint that the collection stores. This does
    not show that the stored footprint is the one a tree declares:
    :func:`stale_footprint` compares it with a tree.

    Raises:
        CollectionRefused: the directory holds no header or no footprint, the
            footprint's derived figures are not what its stated quantities give,
            or the header names another release or namespace than the footprint.
    """
    header = _header(directory)
    footprint = _stored_footprint(directory)
    release = footprint["release"]
    if header["releaseKey"] != release["key"]:
        raise CollectionRefused(
            f"{_HEADER_FILE} names the release {header['releaseKey']}, and the "
            f"footprint names {release['key']}"
        )
    if header["namespace"] != release["namespace"]:
        raise CollectionRefused(
            f"{_HEADER_FILE} names the namespace {header['namespace']}, and the "
            f"footprint names {release['namespace']}"
        )

    reads = {name: _items(directory, file) for name, file in _READS.items()}
    absent = [file for name, file in _READS.items() if reads[name] is None]
    faults: list[str] = []
    nodes = (
        None
        if reads["nodes"] is None
        else [_node(node, faults) for node in reads["nodes"]]
    )
    schedulable = [node for node in nodes or () if node["schedulable"]]
    reservations = (
        None
        if reads["pods"] is None
        else _reservations(
            reads["pods"],
            schedulable[0]["name"] if len(schedulable) == 1 else None,
            footprint,
            faults,
        )
    )
    limits = reads["namespaceLimits"]
    strangers = sorted(
        {
            str(_mapping(item.get("metadata")).get("namespace"))
            for item in [*(limits or []), *(reads["claims"] or [])]
        }
        - {release["namespace"]}
    )
    if strangers:
        raise CollectionRefused(
            "a namespaced read holds an object of another namespace: "
            + ", ".join(strangers)
        )
    shape = (
        None
        if reads["nodes"] is None or reads["pods"] is None
        else _shape_faults(reads["nodes"], reads["pods"])
    )
    claim = _claim(reads["claims"], footprint["model"]["cacheClaimName"], faults)
    findings = _evaluate(
        footprint=footprint,
        absent=absent,
        shape=shape,
        faults=faults,
        nodes=nodes,
        reservations=reservations,
        limits=limits,
        claim=claim,
        claims_read=reads["claims"] is not None,
    )
    refusal = _refusal(findings)
    return {
        "schema": RECORD_SCHEMA,
        "result": REFUSED if refusal["rules"] else ACCEPTED,
        "refusal": refusal,
        "collection": header,
        "environment": {
            "provider": header["provider"],
            "kubernetesServerVersion": _server_version(directory),
            "containerEngine": _engine(directory),
        },
        "nodes": nodes,
        "reservations": reservations,
        "footprint": footprint,
        "footprintSha256": footprint_digest(footprint),
        "modelCache": {
            "claimName": footprint["model"]["cacheClaimName"],
            "artifactBytes": footprint["model"]["artifactBytes"],
            "claim": claim,
        },
        "units": dict(UNITS),
        "findings": findings,
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def record_text(record: Mapping[str, Any]) -> str:
    """The bytes a committed record holds."""
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def committed_collections(root: Path = REPO_ROOT) -> list[str]:
    """Each directory under the root that holds a committed collection."""
    return sorted(
        path.relative_to(root).as_posix()
        for pattern in (CASES_PATTERN, RUNS_PATTERN)
        for path in root.glob(pattern)
        if path.is_dir()
    )


def check_committed(root: Path = REPO_ROOT) -> list[str]:
    """Each committed collection whose record is not what its collection gives.

    The stored footprint of a collection is not compared with the tree. A later
    tree can declare other replicas or other resources.
    """
    findings: list[str] = []
    for name in committed_collections(root):
        directory = root / name
        committed = _read(directory, RECORD_FILE)
        if committed is None:
            findings.append(f"{name}: the directory holds no {RECORD_FILE}")
            continue
        try:
            built = record_text(build_record(directory))
        except CollectionRefused as refused:
            findings.append(f"{name}: {refused}")
            continue
        if built.encode("utf-8") != _lf(committed):
            findings.append(
                f"{name}: {RECORD_FILE} is not what the collection gives. Build it "
                f"again: python -m tools.capacity_preflight --as-collected {name}"
            )
    return findings
