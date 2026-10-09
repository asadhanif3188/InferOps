"""The Ready endpoint state of the two Services of a release, as a record.

``tools.service_endpoint_state`` reads one collection, which is two cluster
reads in one directory, and returns one record. This suite holds the tool to
four properties.

*It counts what the cluster published, for each tier.* The endpoints of a
Service, the ones that were Ready, and the pod that each names. A pod that two
slices name is one pod. Zero Ready endpoints is a reading, and it is OBSERVED.

*It refuses a collection that does not give one reading.* A read that was not
made is not zero endpoints. A Service that publishes addresses that are not
ready, an endpoint that states no condition, a slice that another writer made,
and a pod with two states each refuse the tier.

*The record is bounded and holds no address.* It states two tiers, at most 32
pods for each, and a pod name and a pod UID for each pod. It holds no address,
no node name, and no kubeconfig context.

*It says what it is not.* A record is not a request that a caller sent, it is
not a timeline, and it is not a Prometheus ``up`` series.

Every collection here is written by this suite. The pod names, the UIDs, and
the addresses are invented. No test contacts a cluster, and no record here
states what a cluster did.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import service_endpoint_state as state
from tools.service_endpoint_state import core
from tools.service_endpoint_state.__main__ import main

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "domain" / "fixtures" / "service-endpoint-state"
PAGE = REPO_ROOT / "docs" / "environment" / "service-endpoint-state.md"
REAL_RENDER = (
    REPO_ROOT / "charts" / "inferops-llm" / "ci" / "rendered" / "real.expected.yaml"
)
VALUES_SCHEMA = REPO_ROOT / "charts" / "inferops-llm" / "values.schema.json"

# Restated on purpose. A collection built from the tool's constants would agree
# with the tool by construction.
NAMESPACE = "inferops-release"
RELEASE = "inferops"
API_SERVICE = "inferops-inferops-llm"
RUNTIME_SERVICE = "inferops-inferops-llm-runtime"
API = "platform-api"
RUNTIME = "serving-runtime"
CONTROLLER = "endpointslice-controller.k8s.io"
NODE = "invented-node-name"

Document = dict[str, Any]


# --------------------------------------------------------------------------
# Builders: what a collector writes
# --------------------------------------------------------------------------


def header(**changes: object) -> Document:
    document: Document = {
        "schema": "inferops.io/service-endpoint-state-collection/v1alpha1",
        "provider": "docker-desktop",
        "namespace": NAMESPACE,
        "release": RELEASE,
        "executingCommit": "1" * 40,
        "readStartedAt": "2026-01-01T00:00:00Z",
        "readFinishedAt": "2026-01-01T00:00:01Z",
    }
    document.update(changes)
    return document


def service(name: str, component: str, **spec: object) -> Document:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": NAMESPACE,
            "labels": {
                "app.kubernetes.io/instance": RELEASE,
                "app.kubernetes.io/component": component,
            },
        },
        "spec": {"type": "ClusterIP", "clusterIP": "10.96.0.10", **spec},
    }


def uid(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012d}"


def endpoint(
    number: int,
    pod: str,
    *,
    ready: bool | None = True,
    serving: bool | None = None,
    terminating: bool | None = False,
    address: str | None = None,
) -> Document:
    """One endpoint. ``serving`` follows ``ready`` unless it is given."""
    return {
        "addresses": [address or f"10.1.0.{number}"],
        "conditions": {
            "ready": ready,
            "serving": ready if serving is None else serving,
            "terminating": terminating,
        },
        "nodeName": NODE,
        "targetRef": {
            "kind": "Pod",
            "name": pod,
            "namespace": NAMESPACE,
            "uid": uid(number),
        },
    }


def slice_of(
    service_name: str,
    endpoints: list[Document],
    *,
    suffix: str = "abcde",
    address_type: str = "IPv4",
    managed_by: str | None = CONTROLLER,
) -> Document:
    labels = {"kubernetes.io/service-name": service_name}
    if managed_by is not None:
        labels["endpointslice.kubernetes.io/managed-by"] = managed_by
    return {
        "apiVersion": "discovery.k8s.io/v1",
        "kind": "EndpointSlice",
        "metadata": {
            "name": f"{service_name}-{suffix}",
            "namespace": NAMESPACE,
            "labels": labels,
        },
        "addressType": address_type,
        "endpoints": endpoints,
        "ports": [{"name": "http", "port": 8080, "protocol": "TCP"}],
    }


def listed(items: list[Document]) -> Document:
    return {"apiVersion": "v1", "kind": "List", "items": items}


def api_pods() -> list[Document]:
    return [endpoint(1, "inferops-api-a"), endpoint(2, "inferops-api-b")]


def runtime_pods() -> list[Document]:
    return [endpoint(11, "inferops-runtime-a"), endpoint(12, "inferops-runtime-b")]


def services() -> list[Document]:
    return [service(API_SERVICE, API), service(RUNTIME_SERVICE, RUNTIME)]


def slices(
    api: list[Document] | None = None, runtime: list[Document] | None = None
) -> list[Document]:
    return [
        slice_of(API_SERVICE, api_pods() if api is None else api),
        slice_of(RUNTIME_SERVICE, runtime_pods() if runtime is None else runtime),
    ]


def write(
    directory: Path,
    *,
    run: Document | None = None,
    service_items: list[Document] | None = None,
    slice_items: list[Document] | None = None,
    without: tuple[str, ...] = (),
) -> Path:
    """Write one collection, without the files named in ``without``."""
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "run.json": header() if run is None else run,
        "services.json": listed(services() if service_items is None else service_items),
        "endpointslices.json": listed(slices() if slice_items is None else slice_items),
    }
    for name, document in files.items():
        if name in without:
            continue
        (directory / name).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return directory


def record_of(tmp_path: Path, **collection: Any) -> Document:
    return state.build_record(write(tmp_path / "collection", **collection))


def tier(record: Document, name: str) -> Document:
    [found] = [entry for entry in record["tiers"] if entry["tier"] == name]
    return found


def finding(record: Document, rule_id: str) -> Document:
    [found] = [entry for entry in record["findings"] if entry["ruleId"] == rule_id]
    return found


def not_held(record: Document) -> list[str]:
    return [
        entry["ruleId"] for entry in record["findings"] if entry["state"] == "not-held"
    ]


# --------------------------------------------------------------------------
# The committed cases
# --------------------------------------------------------------------------

# Each committed case, as what this suite writes for it. The committed files
# are these, and a test below compares them.
CASES: dict[str, Callable[[], dict[str, Any]]] = {
    "observed-two-ready-for-each-tier": lambda: {},
    "observed-no-ready-runtime-endpoint": lambda: {
        "slice_items": slices(
            runtime=[
                endpoint(
                    11,
                    "inferops-runtime-a",
                    ready=False,
                    serving=True,
                    terminating=True,
                ),
                endpoint(13, "inferops-runtime-c", ready=False),
            ]
        )
    },
    "observed-two-address-families": lambda: {
        "slice_items": [
            *slices(),
            slice_of(
                RUNTIME_SERVICE,
                [
                    endpoint(11, "inferops-runtime-a", address="fd00::11"),
                    endpoint(12, "inferops-runtime-b", address="fd00::12"),
                ],
                suffix="fghij",
                address_type="IPv6",
            ),
        ]
    },
    "refused-slice-read-not-made": lambda: {"without": ("endpointslices.json",)},
    "refused-no-runtime-service": lambda: {
        "service_items": [service(API_SERVICE, API)],
        "slice_items": [slice_of(API_SERVICE, api_pods())],
    },
    "refused-service-publishes-not-ready-addresses": lambda: {
        "service_items": [
            service(API_SERVICE, API),
            service(RUNTIME_SERVICE, RUNTIME, publishNotReadyAddresses=True),
        ]
    },
}

EXPECTED_RESULT = {
    "observed-two-ready-for-each-tier": ("OBSERVED", []),
    "observed-no-ready-runtime-endpoint": ("OBSERVED", []),
    "observed-two-address-families": ("OBSERVED", []),
    "refused-slice-read-not-made": (
        "REFUSED",
        ["each-read-was-made"],
    ),
    "refused-no-runtime-service": ("REFUSED", ["one-service-carries-each-tier"]),
    "refused-service-publishes-not-ready-addresses": (
        "REFUSED",
        ["the-service-publishes-ready-addresses-only"],
    ),
}


def test_the_committed_cases_are_the_cases_this_suite_writes(tmp_path: Path) -> None:
    """Each committed collection is, file for file, what the builders give.

    So a committed case holds invented pods only, and a reader can derive each
    file from this module.
    """
    assert sorted(path.name for path in FIXTURES.iterdir()) == sorted(CASES)
    for name, build in CASES.items():
        written = write(tmp_path / name, **build())
        expected = {path.name: path.read_bytes() for path in written.iterdir()}
        expected[state.RECORD_FILE] = state.record_text(
            state.build_record(written)
        ).encode("utf-8")
        committed = {
            path.name: path.read_bytes().replace(b"\r\n", b"\n")
            for path in (FIXTURES / name).iterdir()
        }
        assert committed == expected, name


@pytest.mark.parametrize("name", sorted(CASES))
def test_each_committed_case_has_the_result_its_name_states(name: str) -> None:
    record = json.loads((FIXTURES / name / state.RECORD_FILE).read_text("utf-8"))
    result, refusing = EXPECTED_RESULT[name]
    assert record["result"] == result
    assert not_held(record) == refusing
    assert name.startswith(result.lower() + "-")


def test_the_check_holds_each_committed_record_to_its_collection() -> None:
    assert state.committed_collections() == sorted(
        f"tests/domain/fixtures/service-endpoint-state/{name}" for name in CASES
    )
    assert state.check_committed() == []


def test_the_check_reports_a_record_that_its_collection_does_not_give(
    tmp_path: Path,
) -> None:
    case = tmp_path / "tests/domain/fixtures/service-endpoint-state/one"
    write(case)
    assert state.check_committed(tmp_path) == [
        "tests/domain/fixtures/service-endpoint-state/one: the collection holds no "
        "record.v1alpha1.json"
    ]
    record = state.build_record(case)
    record["tiers"][0]["endpoints"]["ready"] = 5
    (case / state.RECORD_FILE).write_text(state.record_text(record), encoding="utf-8")
    [reported] = state.check_committed(tmp_path)
    assert "is not the record that the collection gives" in reported
    (case / state.RECORD_FILE).write_text(
        state.record_text(state.build_record(case)), encoding="utf-8"
    )
    assert state.check_committed(tmp_path) == []


# --------------------------------------------------------------------------
# What a record counts
# --------------------------------------------------------------------------


def test_two_ready_endpoints_for_each_tier_are_counted_and_named(
    tmp_path: Path,
) -> None:
    record = record_of(tmp_path)
    assert record["schema"] == "inferops.io/service-endpoint-state/v1alpha1"
    assert record["result"] == "OBSERVED"
    assert record["refusedBy"] == []
    assert [entry["tier"] for entry in record["tiers"]] == [API, RUNTIME]
    assert tier(record, API) == {
        "tier": API,
        "state": "observed",
        "service": API_SERVICE,
        "slices": 1,
        "addressTypes": ["IPv4"],
        "endpoints": {
            "total": 2,
            "ready": 2,
            "notReady": 0,
            "serving": 2,
            "terminating": 0,
        },
        "ready": [
            {"podName": "inferops-api-a", "podUid": uid(1)},
            {"podName": "inferops-api-b", "podUid": uid(2)},
        ],
        "notReady": [],
    }
    assert tier(record, RUNTIME)["ready"] == [
        {"podName": "inferops-runtime-a", "podUid": uid(11)},
        {"podName": "inferops-runtime-b", "podUid": uid(12)},
    ]
    assert [entry["state"] for entry in record["findings"]] == ["held"] * len(
        state.RULES
    )


def test_zero_ready_endpoints_is_a_reading_and_not_a_refusal(tmp_path: Path) -> None:
    """One pod is terminating and still serving, and one has not become Ready.

    The count of Ready endpoints is zero, and the record is OBSERVED. The
    record states the two pods that are not Ready, with what each reports.
    """
    record = record_of(tmp_path, **CASES["observed-no-ready-runtime-endpoint"]())
    assert record["result"] == "OBSERVED"
    runtime = tier(record, RUNTIME)
    assert runtime["endpoints"] == {
        "total": 2,
        "ready": 0,
        "notReady": 2,
        "serving": 1,
        "terminating": 1,
    }
    assert runtime["ready"] == []
    assert runtime["notReady"] == [
        {
            "podName": "inferops-runtime-a",
            "podUid": uid(11),
            "serving": True,
            "terminating": True,
        },
        {
            "podName": "inferops-runtime-c",
            "podUid": uid(13),
            "serving": False,
            "terminating": False,
        },
    ]
    assert tier(record, API)["endpoints"]["ready"] == 2


@pytest.mark.parametrize("endpoints", [[], None])
def test_a_service_with_no_endpoint_has_zero_and_is_observed(
    tmp_path: Path, endpoints: list[Document] | None
) -> None:
    """A slice with an empty list, and a slice whose list is null."""
    items = slices()
    items[1]["endpoints"] = endpoints
    record = record_of(tmp_path, slice_items=items)
    assert record["result"] == "OBSERVED"
    assert tier(record, RUNTIME)["endpoints"]["total"] == 0
    assert tier(record, RUNTIME)["slices"] == 1


def test_a_service_with_no_slice_has_zero_endpoints_and_states_no_slice(
    tmp_path: Path,
) -> None:
    record = record_of(tmp_path, slice_items=[slice_of(API_SERVICE, api_pods())])
    assert record["result"] == "OBSERVED"
    runtime = tier(record, RUNTIME)
    assert (runtime["slices"], runtime["endpoints"]["total"]) == (0, 0)
    assert runtime["addressTypes"] == []


def test_a_pod_that_two_address_families_name_is_one_pod(tmp_path: Path) -> None:
    record = record_of(tmp_path, **CASES["observed-two-address-families"]())
    runtime = tier(record, RUNTIME)
    assert runtime["slices"] == 2
    assert runtime["addressTypes"] == ["IPv4", "IPv6"]
    assert runtime["endpoints"]["total"] == runtime["endpoints"]["ready"] == 2


def test_a_slice_of_another_service_is_not_counted(tmp_path: Path) -> None:
    items = [
        *slices(),
        slice_of("another-service", [endpoint(40, "another-pod")], suffix="zzzzz"),
    ]
    record = record_of(tmp_path, slice_items=items)
    assert record["result"] == "OBSERVED"
    for name in (API, RUNTIME):
        assert tier(record, name)["endpoints"]["total"] == 2


def test_a_service_of_another_release_does_not_carry_a_tier(tmp_path: Path) -> None:
    other = service("other-runtime", RUNTIME)
    other["metadata"]["labels"]["app.kubernetes.io/instance"] = "other"
    record = record_of(tmp_path, service_items=[*services(), other])
    assert record["result"] == "OBSERVED"
    assert tier(record, RUNTIME)["service"] == RUNTIME_SERVICE


def test_the_pure_function_gives_the_tiers_of_the_record(tmp_path: Path) -> None:
    """A caller that samples repeatedly uses this function for each sample."""
    tiers, broken = state.observe(
        services(), slices(), release=RELEASE, namespace=NAMESPACE
    )
    assert broken == {}
    assert tiers == record_of(tmp_path)["tiers"]


# --------------------------------------------------------------------------
# What a record refuses
# --------------------------------------------------------------------------


@pytest.mark.parametrize("absent", ["services.json", "endpointslices.json"])
def test_a_read_that_was_not_made_is_not_zero_endpoints(
    tmp_path: Path, absent: str
) -> None:
    record = record_of(tmp_path, without=(absent,))
    assert record["result"] == "REFUSED"
    assert not_held(record) == ["each-read-was-made"]
    assert absent in finding(record, "each-read-was-made")["detail"]
    for entry in record["tiers"]:
        assert entry == {
            "tier": entry["tier"],
            "state": "not-observed",
            "service": None,
            "slices": None,
            "addressTypes": None,
            "endpoints": None,
            "ready": None,
            "notReady": None,
        }
    states = {entry["ruleId"]: entry["state"] for entry in record["findings"]}
    assert set(states.values()) == {"not-held", "not-observed"}
    assert record["refusedBy"] == [rule.rule_id for rule in state.RULES]


def _not_json(directory: Path) -> None:
    (directory / "endpointslices.json").write_text("Unable to connect", "utf-8")


def _not_a_list(directory: Path) -> None:
    (directory / "services.json").write_text('{"kind": "Status"}', "utf-8")


@pytest.mark.parametrize("damage", [_not_json, _not_a_list])
def test_a_read_that_is_not_a_list_refuses_every_tier(
    tmp_path: Path, damage: Callable[[Path], None]
) -> None:
    directory = write(tmp_path / "collection")
    damage(directory)
    record = state.build_record(directory)
    assert record["result"] == "REFUSED"
    assert not_held(record) == ["each-read-has-the-shape-of-its-kind"]
    assert {entry["state"] for entry in record["tiers"]} == {"not-observed"}


def _change(path: str, value: object) -> Callable[[Document], None]:
    def apply(item: Document) -> None:
        node: Any = item
        *parents, last = path.split(".")
        for part in parents:
            node = node[int(part)] if part.isdigit() else node[part]
        if isinstance(node, list):
            node[int(last)] = value
        else:
            node[last] = value

    return apply


SLICE_SHAPE_FAULTS = {
    "kind": _change("kind", "Endpoints"),
    "metadata": _change("metadata", "text"),
    "name": _change("metadata.name", 7),
    "namespace": _change("metadata.namespace", "default"),
    "labels": _change("metadata.labels", ["a"]),
    "label-value": _change("metadata.labels.kubernetes.io/service-name", 1),
    "address-type": _change("addressType", "IPX"),
    "endpoints": _change("endpoints", {"0": {}}),
    "endpoint": _change("endpoints.0", "text"),
    "conditions": _change("endpoints.0.conditions", [True]),
    "ready-as-text": _change("endpoints.0.conditions.ready", "true"),
    "ready-as-number": _change("endpoints.0.conditions.ready", 1),
    "terminating-as-text": _change("endpoints.0.conditions.terminating", "false"),
    "target": _change("endpoints.0.targetRef", "pod/a"),
    "target-uid": _change("endpoints.0.targetRef.uid", 5),
}


@pytest.mark.parametrize("fault", sorted(SLICE_SHAPE_FAULTS))
def test_a_slice_member_of_another_type_is_not_read_as_absent(
    tmp_path: Path, fault: str
) -> None:
    """A wrong type is a fault. It is not an endpoint that was left out."""
    items = slices()
    if fault == "label-value":
        items[1]["metadata"]["labels"]["kubernetes.io/service-name"] = 1
    else:
        SLICE_SHAPE_FAULTS[fault](items[1])
    record = record_of(tmp_path, slice_items=items)
    assert record["result"] == "REFUSED"
    assert not_held(record) == ["each-read-has-the-shape-of-its-kind"]
    assert (
        "endpointslices.json: item 1"
        in finding(record, "each-read-has-the-shape-of-its-kind")["detail"]
    )
    assert {entry["state"] for entry in record["tiers"]} == {"not-observed"}


@pytest.mark.parametrize(
    "change",
    [
        _change("kind", "Pod"),
        _change("spec", None),
        _change("spec.publishNotReadyAddresses", "true"),
        _change("metadata.namespace", "kube-system"),
    ],
)
def test_a_service_member_of_another_type_refuses(
    tmp_path: Path, change: Callable[[Document], None]
) -> None:
    items = services()
    change(items[0])
    record = record_of(tmp_path, service_items=items)
    assert not_held(record) == ["each-read-has-the-shape-of-its-kind"]


def test_a_missing_tier_refuses_that_tier_and_states_the_other(
    tmp_path: Path,
) -> None:
    """The mock profile renders no runtime Service. Such a release is refused."""
    record = record_of(tmp_path, **CASES["refused-no-runtime-service"]())
    assert record["result"] == "REFUSED"
    assert not_held(record) == ["one-service-carries-each-tier"]
    assert tier(record, API)["state"] == "observed"
    assert tier(record, API)["endpoints"]["ready"] == 2
    runtime = tier(record, RUNTIME)
    assert runtime["state"] == "refused"
    assert runtime["service"] is None
    assert runtime["endpoints"] is None and runtime["ready"] is None
    later = [entry["state"] for entry in record["findings"][3:]]
    assert later == ["not-observed"] * 6


def test_two_services_for_one_tier_refuse_that_tier(tmp_path: Path) -> None:
    record = record_of(
        tmp_path, service_items=[*services(), service("second-runtime", RUNTIME)]
    )
    assert not_held(record) == ["one-service-carries-each-tier"]
    assert "2 Services" in finding(record, "one-service-carries-each-tier")["detail"]
    assert tier(record, RUNTIME)["state"] == "refused"


def test_a_service_that_publishes_not_ready_addresses_is_refused(
    tmp_path: Path,
) -> None:
    """Such a Service publishes each endpoint as ready, so ready says nothing."""
    record = record_of(
        tmp_path, **CASES["refused-service-publishes-not-ready-addresses"]()
    )
    assert not_held(record) == ["the-service-publishes-ready-addresses-only"]
    runtime = tier(record, RUNTIME)
    assert runtime["state"] == "refused"
    assert runtime["service"] == RUNTIME_SERVICE
    assert runtime["endpoints"] is None
    assert tier(record, API)["state"] == "observed"


def test_a_stated_false_for_publish_not_ready_addresses_is_held(
    tmp_path: Path,
) -> None:
    items = [
        service(API_SERVICE, API, publishNotReadyAddresses=False),
        service(RUNTIME_SERVICE, RUNTIME),
    ]
    assert record_of(tmp_path, service_items=items)["result"] == "OBSERVED"


@pytest.mark.parametrize("managed_by", [None, "another-controller.example"])
def test_a_slice_that_the_controller_did_not_write_is_refused(
    tmp_path: Path, managed_by: str | None
) -> None:
    items = [
        slice_of(API_SERVICE, api_pods()),
        slice_of(RUNTIME_SERVICE, runtime_pods(), managed_by=managed_by),
    ]
    record = record_of(tmp_path, slice_items=items)
    assert not_held(record) == ["the-slice-controller-wrote-each-slice"]
    assert tier(record, RUNTIME)["endpoints"] is None


@pytest.mark.parametrize("condition", ["ready", "serving", "terminating"])
@pytest.mark.parametrize("form", ["null", "absent"])
def test_an_endpoint_that_does_not_state_a_condition_is_not_counted_as_ready(
    tmp_path: Path, condition: str, form: str
) -> None:
    """Kubernetes documents an unstated ready as true. The record refuses it."""
    pods = runtime_pods()
    if form == "null":
        pods[0]["conditions"][condition] = None
    else:
        del pods[0]["conditions"][condition]
    record = record_of(tmp_path, slice_items=slices(runtime=pods))
    assert not_held(record) == ["each-endpoint-states-its-conditions"]
    assert condition in finding(record, "each-endpoint-states-its-conditions")["detail"]
    assert tier(record, RUNTIME)["endpoints"] is None


def test_an_endpoint_with_no_conditions_at_all_is_refused(tmp_path: Path) -> None:
    pods = runtime_pods()
    del pods[1]["conditions"]
    record = record_of(tmp_path, slice_items=slices(runtime=pods))
    assert not_held(record) == ["each-endpoint-states-its-conditions"]


def _no_target(item: Document) -> None:
    del item["targetRef"]


@pytest.mark.parametrize(
    "change",
    [
        _no_target,
        _change("targetRef.kind", "Node"),
        _change("targetRef.namespace", "default"),
        _change("targetRef.uid", "not-a-uid"),
        _change("targetRef.name", "Not_A_Name"),
    ],
)
def test_an_endpoint_that_names_no_pod_of_the_namespace_is_refused(
    tmp_path: Path, change: Callable[[Document], None]
) -> None:
    pods = runtime_pods()
    change(pods[0])
    record = record_of(tmp_path, slice_items=slices(runtime=pods))
    assert not_held(record) == ["each-endpoint-names-one-pod"]
    assert tier(record, RUNTIME)["ready"] is None


def test_a_pod_with_two_states_in_two_slices_is_refused(tmp_path: Path) -> None:
    items = [
        *slices(),
        slice_of(
            RUNTIME_SERVICE,
            [endpoint(11, "inferops-runtime-a", ready=False)],
            suffix="fghij",
        ),
    ]
    record = record_of(tmp_path, slice_items=items)
    assert not_held(record) == ["one-pod-has-one-state"]
    assert uid(11) in finding(record, "one-pod-has-one-state")["detail"]


def test_one_pod_name_with_two_uids_is_refused(tmp_path: Path) -> None:
    pods = [endpoint(11, "inferops-runtime-a"), endpoint(12, "inferops-runtime-a")]
    record = record_of(tmp_path, slice_items=slices(runtime=pods))
    assert not_held(record) == ["one-pod-has-one-state"]


def many(count: int) -> list[Document]:
    return [
        endpoint(100 + n, f"inferops-runtime-{n:03d}", address=f"10.1.1.{n}")
        for n in range(count)
    ]


def test_the_bound_admits_its_own_number_and_refuses_one_more(tmp_path: Path) -> None:
    assert state.MAX_ENDPOINTS == 32
    at_bound = record_of(tmp_path / "a", slice_items=slices(runtime=many(32)))
    assert at_bound["result"] == "OBSERVED"
    assert len(tier(at_bound, RUNTIME)["ready"]) == 32

    over = record_of(tmp_path / "b", slice_items=slices(runtime=many(33)))
    assert not_held(over) == ["the-endpoint-count-is-within-the-bound"]
    runtime = tier(over, RUNTIME)
    assert runtime["ready"] is None and runtime["endpoints"] is None
    assert "inferops-runtime-000" not in state.record_text(over)


def test_the_bound_is_the_replicas_and_the_surge_that_the_chart_admits() -> None:
    schema = json.loads(VALUES_SCHEMA.read_text(encoding="utf-8"))
    for name in ("api", "runtime"):
        replicas = schema["properties"][name]["properties"]["replicaCount"]["maximum"]
        surge = schema["$defs"]["rollout"]["properties"]["maxSurge"]["maximum"]
        assert replicas + surge == state.MAX_ENDPOINTS


def test_two_faults_in_one_tier_are_both_stated(tmp_path: Path) -> None:
    pods = runtime_pods()
    del pods[0]["targetRef"]
    pods[1]["conditions"]["ready"] = None
    record = record_of(tmp_path, slice_items=slices(runtime=pods))
    assert not_held(record) == [
        "each-endpoint-states-its-conditions",
        "each-endpoint-names-one-pod",
    ]


# --------------------------------------------------------------------------
# The header
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"schema": "inferops.io/capacity-preflight-collection/v1alpha1"},
        {"provider": "Docker Desktop"},
        {"namespace": ""},
        {"release": "a/b"},
        {"executingCommit": "1" * 39},
        {"readStartedAt": "2026-01-01 00:00:00"},
        {"readFinishedAt": "2026-01-01T00:00:01+00:00"},
        {"readStartedAt": "2026-01-01T00:00:02Z"},
        {"namespace": 5},
        {"context": "arn:aws:eks:eu-west-1:000000000000:cluster/x"},
    ],
    ids=lambda changes: (
        next(iter(changes)) + "=" + str(next(iter(changes.values())))[:24]
    ),
)
def test_a_header_that_is_not_the_collectors_is_not_a_collection(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    """The last case: a header with a kubeconfig context is refused, not copied."""
    directory = write(tmp_path / "collection", run=header(**changes))
    with pytest.raises(state.CollectionRefused):
        state.build_record(directory)


def test_a_header_without_a_member_is_not_a_collection(tmp_path: Path) -> None:
    run = header()
    del run["release"]
    with pytest.raises(state.CollectionRefused):
        state.build_record(write(tmp_path / "collection", run=run))


@pytest.mark.parametrize("text", ["", "[]", "not json"])
def test_a_header_that_is_not_an_object_is_not_a_collection(
    tmp_path: Path, text: str
) -> None:
    directory = write(tmp_path / "collection")
    (directory / "run.json").write_text(text, encoding="utf-8")
    with pytest.raises(state.CollectionRefused):
        state.build_record(directory)


def test_a_directory_without_a_header_is_not_a_collection(tmp_path: Path) -> None:
    with pytest.raises(state.CollectionRefused):
        state.build_record(write(tmp_path / "collection", without=("run.json",)))
    with pytest.raises(state.CollectionRefused):
        state.build_record(tmp_path / "absent")


# --------------------------------------------------------------------------
# What a record holds, and what it leaves out
# --------------------------------------------------------------------------


def test_a_record_holds_no_address_no_node_name_and_no_context(
    tmp_path: Path,
) -> None:
    """The collection holds each of them. The record holds none."""
    directory = write(
        tmp_path / "collection", **CASES["observed-two-address-families"]()
    )
    collected = (directory / "endpointslices.json").read_text(encoding="utf-8")
    services_read = (directory / "services.json").read_text(encoding="utf-8")
    text = state.record_text(state.build_record(directory))
    for present in ("10.1.0.11", "fd00::11", NODE):
        assert present in collected
        assert present not in text
    assert "10.96.0.10" in services_read
    assert "10.96.0.10" not in text
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text)
    record = json.loads(text)
    assert sorted(record["collection"]) == sorted(
        [
            "schema",
            "provider",
            "namespace",
            "release",
            "executingCommit",
            "readStartedAt",
            "readFinishedAt",
        ]
    )
    assert len(record["omitted"]) == 4


def test_a_record_states_two_tiers_and_its_bounds(tmp_path: Path) -> None:
    """The values that a consumer may use as a label are a closed set."""
    record = record_of(tmp_path)
    assert record["bounds"] == {
        "tiers": ["platform-api", "serving-runtime"],
        "maxEndpointsPerService": 32,
    }
    assert state.TIERS == (API, RUNTIME)
    assert state.RESULT_STATES == ("OBSERVED", "REFUSED")
    assert {entry["state"] for entry in record["tiers"]} <= {
        "observed",
        "refused",
        "not-observed",
    }
    assert sorted(record) == sorted(
        [
            "schema",
            "collection",
            "result",
            "refusedBy",
            "tiers",
            "findings",
            "bounds",
            "omitted",
            "limitations",
            "doesNotEstablish",
        ]
    )


def test_an_identity_is_a_pod_name_and_a_pod_uid_and_nothing_else(
    tmp_path: Path,
) -> None:
    record = record_of(tmp_path, **CASES["observed-no-ready-runtime-endpoint"]())
    for entry in record["tiers"]:
        for pod in entry["ready"]:
            assert sorted(pod) == ["podName", "podUid"]
        for pod in entry["notReady"]:
            assert sorted(pod) == ["podName", "podUid", "serving", "terminating"]


def test_a_record_is_the_same_text_for_the_same_collection(tmp_path: Path) -> None:
    """The order of the items in a read does not change the record."""
    first = write(tmp_path / "a")
    reversed_slices = list(reversed(slices()))
    for item in reversed_slices:
        item["endpoints"].reverse()
    second = write(
        tmp_path / "b",
        service_items=list(reversed(services())),
        slice_items=reversed_slices,
    )
    one = state.record_text(state.build_record(first))
    assert one == state.record_text(state.build_record(second))
    assert one.endswith("}\n") and "\r" not in one
    assert json.loads(one) == state.build_record(first)


def test_building_a_record_changes_no_file_of_the_collection(tmp_path: Path) -> None:
    directory = write(tmp_path / "collection")
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    state.build_record(directory)
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before


def test_a_record_says_what_it_does_not_establish(tmp_path: Path) -> None:
    """Caller truth, a timeline, and a scrape are each named as not this."""
    for record in (
        record_of(tmp_path / "a"),
        record_of(tmp_path / "b", without=("services.json",)),
    ):
        text = " ".join(record["doesNotEstablish"])
        assert "That a caller obtains a completion" in text
        assert "It is not a timeline" in text
        assert "Prometheus `up`" in text
        assert "deleted, evicted, or replaced" in text
        assert len(record["doesNotEstablish"]) == len(state.DOES_NOT_ESTABLISH) == 7
        assert len(record["limitations"]) == len(state.LIMITATIONS) == 5


def test_the_tool_reads_files_and_starts_nothing() -> None:
    """No process, no socket, and no cluster client is imported by the tool."""
    for path in sorted((REPO_ROOT / "tools" / "service_endpoint_state").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for word in ("subprocess", "socket", "urllib", "http.client", "kubernetes"):
            assert not re.search(
                rf"^\s*(import|from)\s+{re.escape(word)}\b", text, re.M
            )
        assert "write_text" not in text and "write_bytes" not in text, path.name
        assert not re.search(r"\bopen\(", text), path.name


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_exits_0_for_observed_and_prints_the_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = write(tmp_path / "collection")
    assert main([str(directory)]) == 0
    assert capsys.readouterr().out == state.record_text(state.build_record(directory))


def test_the_command_exits_0_for_zero_ready_endpoints(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Status 0 says OBSERVED. It does not say that an endpoint is Ready."""
    directory = write(
        tmp_path / "collection", **CASES["observed-no-ready-runtime-endpoint"]()
    )
    assert main([str(directory)]) == 0
    record = json.loads(capsys.readouterr().out)
    assert tier(record, RUNTIME)["endpoints"]["ready"] == 0


def test_the_command_exits_5_for_refused_and_still_prints_the_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = write(tmp_path / "collection", without=("endpointslices.json",))
    assert main([str(directory)]) == state.REFUSED_EXIT == 5
    assert json.loads(capsys.readouterr().out)["result"] == "REFUSED"


def test_the_command_exits_1_and_prints_no_record_for_a_directory_that_is_no_collection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("REFUSED  not-a-collection: ")


def test_the_command_checks_the_committed_collections(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--check"]) == 0
    assert capsys.readouterr().out.startswith(
        f"PASSED: {len(CASES)} committed collection(s)"
    )


@pytest.mark.parametrize("arguments", [[], ["--check", "directory"]])
def test_the_command_refuses_arguments_that_are_not_usable(
    arguments: list[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(arguments)
    assert raised.value.code == 2


# --------------------------------------------------------------------------
# The tool, the chart, and the page
# --------------------------------------------------------------------------


def test_the_tiers_are_the_component_labels_of_the_two_rendered_services() -> None:
    """The names this suite restates are the names the chart renders.

    The committed real render uses the release name of the chart's fixtures,
    which is also the release name that the environment scripts use.
    """
    rendered = [
        document
        for document in yaml.safe_load_all(REAL_RENDER.read_text(encoding="utf-8"))
        if isinstance(document, dict) and document["kind"] == "Service"
    ]
    by_component = {
        document["metadata"]["labels"]["app.kubernetes.io/component"]: document
        for document in rendered
    }
    assert set(state.TIERS) <= set(by_component)
    assert by_component[API]["metadata"]["name"] == API_SERVICE
    assert by_component[RUNTIME]["metadata"]["name"] == RUNTIME_SERVICE
    for name in state.TIERS:
        labels = by_component[name]["metadata"]["labels"]
        assert labels["app.kubernetes.io/instance"] == RELEASE
        spec = by_component[name]["spec"]
        assert "publishNotReadyAddresses" not in spec
        # The selector is what makes the controller write the slices.
        assert spec["selector"]["app.kubernetes.io/component"] == name


def test_the_charts_scrape_jobs_read_pods_and_not_the_state_of_a_service() -> None:
    """Why a Prometheus `up` series is not this signal.

    Both scrape jobs of the committed real render discover with the role `pod`.
    Neither discovers endpoints or slices, and neither selects on the Ready
    condition of a pod. So `up` states that a scrape of one pod answered. This
    reads a rendered file. No collector was asked.
    """
    [configuration] = [
        document
        for document in yaml.safe_load_all(REAL_RENDER.read_text(encoding="utf-8"))
        if isinstance(document, dict)
        and document["kind"] == "ConfigMap"
        and "scrape-config.yaml" in document.get("data", {})
    ]
    text = configuration["data"]["scrape-config.yaml"]
    jobs = yaml.safe_load(text)["scrape_configs"]
    roles = [
        discovery["role"] for job in jobs for discovery in job["kubernetes_sd_configs"]
    ]
    assert roles == ["pod", "pod"]
    assert "pod_ready" not in text
    assert "endpoint" not in text.lower()


def test_the_page_states_each_rule_and_each_file_of_a_collection() -> None:
    page = PAGE.read_text(encoding="utf-8")
    for rule in state.RULES:
        assert f"`{rule.rule_id}`" in page, rule.rule_id
    for name in (
        state.HEADER_FILE,
        state.SERVICES_FILE,
        state.SLICES_FILE,
        state.RECORD_FILE,
    ):
        assert f"`{name}`" in page, name
    assert f"`{state.RECORD_SCHEMA}`" in page
    assert f"{len(state.RULES)} rules" in page or "Nine rules" in page
    assert len(state.RULES) == 9
    assert str(state.MAX_ENDPOINTS) in page


def test_the_page_states_what_the_record_is_not() -> None:
    page = " ".join(PAGE.read_text(encoding="utf-8").split())
    for sentence in (
        "A record is not caller truth.",
        "A Prometheus `up` series is not this signal.",
        "A record is one reading. It is not a timeline.",
    ):
        assert sentence in page, sentence


def test_the_rule_identifiers_are_distinct_and_each_has_a_statement() -> None:
    identifiers = [rule.rule_id for rule in state.RULES]
    assert len(set(identifiers)) == len(identifiers)
    for rule in state.RULES:
        assert re.fullmatch(r"[a-z]+(-[a-z]+)+", rule.rule_id)
        assert rule.statement.endswith(".")
    assert tuple(identifiers[:2]) == core._COLLECTION_RULES


def test_a_collection_is_not_changed_by_the_builders(tmp_path: Path) -> None:
    """The builders give a new document on each call, so a case cannot leak."""
    first = slices()
    first[0]["endpoints"].clear()
    assert copy.deepcopy(slices())[0]["endpoints"] == api_pods()
