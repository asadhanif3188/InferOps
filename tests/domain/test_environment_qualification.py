"""Q1, the environment and identity qualification, as a record.

``tools.environment_qualification`` reads one directory that the frozen Q1
driver writes, and returns one record. This suite holds the tool to four
properties.

*Each rule refuses what it names.* A directory that holds every source at the
state Q1 requires is QUALIFIED. One defect in one source refuses one rule, with
the category of that rule, and the record is REFUSED. A source that is absent
gives the state not-observed, and that refuses too.

*A refusal is not converted into a weaker target.* The target release key, the
topology, the provider, and the model are constants. The command has no option
for any of them, and a source for one replica refuses.

*The rules are the frozen criteria.* Each rule is one acceptance criterion of
the Q1 freeze record, with the same identifier and statement, and the page
restates each rule. The driver names the freeze record, the experiment, and
each file that the tool reads.

*It says what it is not.* A record states no recovery, no bound, and no
reliability figure, and each sentence of what it does not establish says so.

Every directory in this suite is synthetic. Its figures are invented, except
the pinned model, the pinned runtime image, and the RP-1 profile, which are the
committed files. The caller record is written by the runner's own loop against
scripted answers. No test contacts a cluster.
"""

from __future__ import annotations

import copy
import io
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import environment_qualification as q1
from tools.capacity_preflight import core as capacity_core
from tools.environment_qualification import __main__ as cli
from tools.experiment_freeze import core as freeze
from tools.reliability_runner import core as runner
from tools.reliability_runner import incluster

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs/environment/environment-qualification.md"
DRIVER = ROOT / "docs/proof/experiments/v2-q1/procedure/q1-driver.txt"
FREEZE = ROOT / "docs/proof/experiments/v2-q1/freeze-r2.v1alpha1.json"
FREEZE_R1 = ROOT / "docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json"
VALUES = (
    ROOT / "gitops/environments/local-docker-desktop/workloads/support-assistant"
    "/values.generated.yaml"
)

COMMIT = "1" * 39 + "2"
DESIRED = "3" * 39 + "4"
RELEASE_ID = "5" * 64
API_DIGEST = "sha256:" + "6" * 64
NODE = "desktop-control-plane"
RUN_ID = "q1-1"

MODEL_SOURCE = json.loads(
    (ROOT / "docs/serving/model-source.v1.json").read_text("utf-8")
)
RUNTIME_IMAGE = json.loads(
    (ROOT / "deploy/serving/runtime/container-package.v1.json").read_text("utf-8")
)["container"]["imageReference"]
#: The two pin files, as the driver copies them: with LF line ends.
PIN_TEXT = {
    q1.MODEL_SOURCE_COPY: (ROOT / q1.MODEL_SOURCE_FILE)
    .read_text("utf-8")
    .replace("\r\n", "\n"),
    q1.RUNTIME_PACKAGE_COPY: (ROOT / q1.RUNTIME_PACKAGE_FILE)
    .read_text("utf-8")
    .replace("\r\n", "\n"),
}
PINNED_MODEL = {
    "repository": MODEL_SOURCE["repository"],
    "revision": MODEL_SOURCE["revision"],
    "fileName": MODEL_SOURCE["file"],
    "sha256": MODEL_SOURCE["sha256"],
    "sizeBytes": MODEL_SOURCE["expectedSizeBytes"],
}

# The rule identifiers and categories, restated on purpose.
RULE_CATEGORIES = {
    "target-reached": "target",
    "provider-selected": "provider-mismatch",
    "context-unambiguous": "ambiguous-context",
    "working-tree-clean": "desired-state",
    "procedure-frozen": "desired-state",
    "desired-revision-known": "desired-state",
    "one-executing-commit": "desired-state",
    "release-provenance-resolved": "desired-state",
    "capacity-accepted": "capacity",
    "controller-identified": "reconciliation",
    "controller-reconciled": "reconciliation",
    "deployments-ready": "topology",
    "endpoints-ready": "topology",
    "images-declared": "release-identity",
    "model-identity-verified": "model-mismatch",
    "caller-completed": "caller",
    "readings-in-order": "evidence",
}


# --------------------------------------------------------------------------
# A directory
# --------------------------------------------------------------------------


def instant(seconds: int) -> str:
    moment = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def header(**changes: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema": q1.COLLECTION_SCHEMA,
        "qualificationId": RUN_ID,
        "provider": "docker-desktop",
        "releaseKey": "local-docker-desktop/support-assistant",
        "executingCommit": COMMIT,
        "desiredRevision": DESIRED,
        "workingTree": "clean",
        "desiredStateDiff": "none",
        "freezeRecord": "docs/proof/experiments/v2-q1/freeze-r2.v1alpha1.json",
        "freezeRecordSha256": q1.lf_digest(FREEZE.read_bytes()),
        "freezeChanges": "none",
        "apiImageDigest": API_DIGEST,
        "controllerVersion": "v3.5.3",
        "controllerVerified": True,
        "targetRefusal": None,
        "upRefusal": None,
        "startedAt": instant(0),
        "finishedAt": instant(600),
    }
    document.update(changes)
    return document


def capacity() -> dict[str, Any]:
    return {
        "schema": "inferops.io/capacity-preflight/v1alpha1",
        "result": "ACCEPTED",
        "refusal": {"categories": [], "rules": []},
        "collection": {
            "provider": "docker-desktop",
            "context": "docker-desktop",
            "releaseKey": "local-docker-desktop/support-assistant",
            "namespace": "inferops-release",
            "executingCommit": COMMIT,
            "collectedAt": instant(-300),
        },
        "environment": {
            "provider": "docker-desktop",
            "kubernetesServerVersion": "v1.36.1",
            "containerEngine": {"cpus": 12, "memoryBytes": 10_000_000_000},
        },
        "nodes": [
            {
                "name": NODE,
                "kubeletVersion": "v1.36.1",
                "allocatable": {
                    "cpuMillis": 12000,
                    "memoryBytes": 10_000_000_000,
                    "pods": 110,
                    "ephemeralStorageBytes": 1,
                },
            }
        ],
        "footprint": {"topology": {"apiReplicas": 2, "runtimeReplicas": 2}},
    }


def provenance() -> list[dict[str, Any]]:
    return [
        {
            "schema": "inferops.io/desired-state-provenance/v1alpha1",
            "git": {"revision": DESIRED},
            "desiredState": {"key": "local-docker-desktop/support-assistant"},
            "release": {
                "releaseId": RELEASE_ID,
                "workloadVersion": "0.2.0",
                "contractSha256": "7" * 64,
                "valuesSha256": "8" * 64,
                "environmentBinding": {
                    "name": "local-docker-desktop",
                    "sha256": "9" * 64,
                },
                "rendererRevision": "a" * 40,
                "platformDefaultsRevision": "a" * 40,
            },
            "chart": {"name": "inferops-llm", "version": "0.6.0"},
        }
    ]


def sample(index: int) -> dict[str, Any]:
    compared = {"state": "compared", "findings": []}
    return {
        "index": index,
        "observedAt": {"state": "reported", "value": instant(10 + index)},
        "settled": {"value": True, "reasons": []},
        "fields": {"resolvedRevision": {"state": "reported", "value": DESIRED}},
        "consistency": {
            "state": "provenance-resolved",
            "releaseId": RELEASE_ID,
            "revisions": dict(compared),
            "source": dict(compared),
            "labels": dict(compared),
        },
    }


def reconciliation() -> dict[str, Any]:
    return {
        "schema": "inferops.io/reconciliation-observation/v1alpha1",
        "collection": {
            "complete": True,
            "provider": {"state": "reported", "value": "docker-desktop"},
            "repositoryRevision": {"state": "reported", "value": COMMIT},
        },
        "samples": [sample(index) for index in range(1, 6)],
    }


def deployment(component: str, name: str, container: str, image: str) -> dict[str, Any]:
    return {
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "generation": 1,
            "labels": {
                "app.kubernetes.io/instance": "inferops",
                "app.kubernetes.io/component": component,
            },
        },
        "spec": {
            "replicas": 2,
            "template": {"spec": {"containers": [{"name": container, "image": image}]}},
        },
        "status": {
            "observedGeneration": 1,
            "replicas": 2,
            "readyReplicas": 2,
            "availableReplicas": 2,
            "updatedReplicas": 2,
        },
    }


def deployments() -> dict[str, Any]:
    return {
        "kind": "List",
        "items": [
            deployment(
                "platform-api",
                "inferops-inferops-llm",
                "api",
                "localhost/inferops-api@" + API_DIGEST,
            ),
            deployment(
                "serving-runtime",
                "inferops-inferops-llm-runtime",
                "runtime",
                RUNTIME_IMAGE,
            ),
        ],
    }


def endpoints() -> dict[str, Any]:
    def tier(name: str) -> dict[str, Any]:
        return {
            "tier": name,
            "state": "observed",
            "endpoints": {"total": 2, "ready": 2, "notReady": 0},
        }

    return {
        "schema": "inferops.io/service-endpoint-state/v1alpha1",
        "result": "OBSERVED",
        "collection": {
            "provider": "docker-desktop",
            "executingCommit": COMMIT,
            "readStartedAt": instant(20),
        },
        "tiers": [tier("platform-api"), tier("serving-runtime")],
    }


def model_cache() -> dict[str, Any]:
    rules = [{"id": rule, "state": "held"} for rule in q1.MODEL_CACHE_RULES]
    rules.append({"id": "capacity-preflight-sufficient", "state": "not-observed"})
    return {
        "schema": "inferops.io/runtime-model-cache-observation/v1alpha1",
        "result": "INCONCLUSIVE",
        "collection": {
            "provider": "docker-desktop",
            "executingCommit": COMMIT,
            "collectedAt": instant(30),
        },
        "expected": {
            "release": {"key": "local-docker-desktop/support-assistant"},
            "runtimeReplicas": 2,
            "model": dict(PINNED_MODEL),
            "runtimeImage": {
                "reference": RUNTIME_IMAGE,
                "digest": RUNTIME_IMAGE.split("@", 1)[1],
            },
        },
        "placement": {"nodes": [NODE], "distinctNodes": 1},
        "rules": rules,
    }


def caller(answer: tuple[int, object] | None = None, **changes: Any) -> tuple[str, str]:
    """A plan and the caller record that the runner's own loop writes for it."""
    arguments: dict[str, Any] = {
        "experiment_id": q1.EXPERIMENT_ID,
        "run_id": RUN_ID,
        "duration_seconds": 60,
        "request_ceiling": 4,
        "release_id": RELEASE_ID,
    }
    arguments.update(changes)
    plan = runner.build_plan(**arguments)
    text = runner.plan_text(plan)
    body = {
        "choices": [{"finish_reason": "stop", "message": {"content": "x"}}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 40},
        "x_inferops": {"adapterKind": "real", "modelRef": "qwen3-1-7b-q8-0"},
    }
    status, payload = answer if answer is not None else (200, body)
    out = io.StringIO()
    ticks = [0]
    now = [0.0]

    def wall() -> datetime:
        ticks[0] += 1
        return datetime(2026, 1, 1, 0, 1, tzinfo=UTC) + timedelta(milliseconds=ticks[0])

    def clock() -> float:
        return now[0]

    def transport(*_: object) -> tuple[int, object]:
        now[0] += 1.0
        return status, payload

    incluster.Run(
        plan,
        out=out,
        runner_sha256=runner.runner_digest(),
        plan_sha256=runner.plan_digest(text),
        transport=transport,
        clock=clock,
        wall=wall,
        sleep=lambda _: None,
    ).execute()
    return text, out.getvalue()


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write(
    directory: Path,
    changes: dict[str, Any] | None = None,
    *,
    without: tuple[str, ...] = (),
) -> Path:
    """Write one directory that is QUALIFIED unless a change or an absence says not."""
    plan_text, caller_text = caller()
    files: dict[str, Any] = {
        q1.HEADER_FILE: header(),
        q1.CAPACITY_RECORD: capacity(),
        q1.PROVENANCE_FILE: provenance(),
        q1.RECONCILIATION_RECORD: reconciliation(),
        q1.DEPLOYMENTS_FILE: deployments(),
        q1.ENDPOINTS_RECORD: endpoints(),
        q1.MODEL_CACHE_RECORD: model_cache(),
        q1.PLAN_FILE: plan_text,
        q1.CALLER_FILE: caller_text,
        q1.MODEL_SOURCE_COPY: PIN_TEXT[q1.MODEL_SOURCE_COPY],
        q1.RUNTIME_PACKAGE_COPY: PIN_TEXT[q1.RUNTIME_PACKAGE_COPY],
    }
    files.update(changes or {})
    for name, document in files.items():
        if name in without:
            continue
        if isinstance(document, str):
            (directory / name).parent.mkdir(parents=True, exist_ok=True)
            (directory / name).write_text(document, encoding="utf-8", newline="\n")
        else:
            write_json(directory / name, document)
    return directory


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A checkout that holds the four files the tool reads from one."""
    checkout = tmp_path / "checkout"
    for name in (
        "docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json",
        "docs/proof/experiments/v2-q1/freeze-r2.v1alpha1.json",
        "docs/serving/model-source.v1.json",
        "deploy/serving/runtime/container-package.v1.json",
    ):
        (checkout / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, checkout / name)
    return checkout


def record_of(directory: Path, root: Path) -> dict[str, Any]:
    return q1.build_record(directory, root)


def states(record: dict[str, Any]) -> dict[str, str]:
    return {item["ruleId"]: item["state"] for item in record["findings"]}


def changed(document: Any, edit: Callable[[Any], Any]) -> Any:
    copied = copy.deepcopy(document)
    edit(copied)
    return copied


def _set(path: tuple[Any, ...], value: Any) -> Callable[[Any], None]:
    def edit(document: Any) -> None:
        for member in path[:-1]:
            document = document[member]
        document[path[-1]] = value

    return edit


def _drop(path: tuple[Any, ...]) -> Callable[[Any], None]:
    def edit(document: Any) -> None:
        for member in path[:-1]:
            document = document[member]
        del document[path[-1]]

    return edit


def header_r1(**changes: Any) -> dict[str, Any]:
    """A header of a qualification under revision 1, which decided q1-1."""
    return header(
        freezeRecord="docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json",
        freezeRecordSha256=q1.lf_digest(FREEZE_R1.read_bytes()),
        **changes,
    )


# --------------------------------------------------------------------------
# A qualified directory
# --------------------------------------------------------------------------


def test_a_directory_with_every_source_at_its_state_is_qualified(
    tmp_path: Path, root: Path
) -> None:
    record = record_of(write(tmp_path / "run"), root)
    assert record["result"] == "QUALIFIED"
    assert set(states(record).values()) == {"held"}
    assert record["refusal"] == {"categories": [], "rules": []}
    assert record["schema"] == "inferops.io/environment-qualification/v1alpha1"
    assert record["qualification"] == "Q1"
    assert record["target"] == {
        "releaseKey": "local-docker-desktop/support-assistant",
        "apiReplicas": 2,
        "runtimeReplicas": 2,
        "provider": "docker-desktop",
    }


def test_the_record_states_each_identity_of_the_qualification(
    tmp_path: Path, root: Path
) -> None:
    identities = record_of(write(tmp_path / "run"), root)["identities"]
    assert identities["executingCommit"] == COMMIT
    assert identities["desiredStateRevision"] == DESIRED
    assert identities["releaseId"] == RELEASE_ID
    assert identities["releaseKey"] == "local-docker-desktop/support-assistant"
    assert identities["contractSha256"] == "7" * 64
    assert identities["helmValuesSha256"] == "8" * 64
    assert identities["environmentBinding"] == {
        "name": "local-docker-desktop",
        "sha256": "9" * 64,
    }
    assert identities["platformDefaultsRevision"] == "a" * 40
    assert identities["chart"] == {"name": "inferops-llm", "version": "0.6.0"}
    assert identities["deliveryControllerVersion"] == "v3.5.3"
    assert identities["apiImageDigest"] == API_DIGEST
    assert identities["runtimeImage"]["reference"] == RUNTIME_IMAGE
    assert identities["model"] == PINNED_MODEL
    assert identities["kubernetes"] == {
        "provider": "docker-desktop",
        "serverVersion": "v1.36.1",
    }
    assert identities["callerProfile"] == {
        "profileId": "RP-1",
        "profileRevision": 1,
        "profileSha256": "ff3cbab5a3bde8d4e25defe940cbcfb4ea3ff1ba028f1bc25c577636c261c1c3",
    }
    assert identities["freezeRecord"]["path"] == q1.FREEZE_RECORD


def test_the_stable_environment_identity_holds_no_memory_figure_and_has_a_digest(
    tmp_path: Path, root: Path
) -> None:
    """Revision 2: the facts of the configuration, and no memory figure."""
    record = record_of(write(tmp_path / "run"), root)
    assert record["environment"] == {
        "provider": "docker-desktop",
        "kubernetesServerVersion": "v1.36.1",
        "nodes": [
            {
                "name": NODE,
                "kubeletVersion": "v1.36.1",
                "allocatable": {"cpuMillis": 12000, "pods": 110},
            }
        ],
        "containerEngine": {"cpus": 12},
        "identityRevision": 2,
    }
    assert record["environmentSha256"] == q1.environment_digest(record["environment"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", record["environmentSha256"])
    assert "memoryBytes" not in json.dumps(record["environment"])


def test_the_exact_environment_identity_of_revision_1_holds_the_memory_figures(
    tmp_path: Path, root: Path
) -> None:
    """Revision 1, which decided q1-1, states memory to the byte, unchanged."""
    record = record_of(write(tmp_path / "run", {q1.HEADER_FILE: header_r1()}), root)
    assert record["result"] == "QUALIFIED"
    assert record["environment"] == {
        "provider": "docker-desktop",
        "kubernetesServerVersion": "v1.36.1",
        "nodes": [
            {
                "name": NODE,
                "kubeletVersion": "v1.36.1",
                "allocatable": {
                    "cpuMillis": 12000,
                    "memoryBytes": 10_000_000_000,
                    "pods": 110,
                },
            }
        ],
        "containerEngine": {"cpus": 12, "memoryBytes": 10_000_000_000},
    }
    assert record["doesNotEstablish"] == list(q1.DOES_NOT_ESTABLISH_R1)


def test_under_revision_1_another_memory_reading_is_another_environment(
    tmp_path: Path, root: Path
) -> None:
    changed = capacity()
    changed["nodes"][0]["allocatable"]["memoryBytes"] -= 1
    first = record_of(write(tmp_path / "a", {q1.HEADER_FILE: header_r1()}), root)
    second = record_of(
        write(
            tmp_path / "b",
            {q1.HEADER_FILE: header_r1(), q1.CAPACITY_RECORD: changed},
        ),
        root,
    )
    assert first["environmentSha256"] != second["environmentSha256"]


#: The memory that this host reported after three starts of its Docker Desktop
#: virtual machine: q1-1 and q3-1, whose capacity records state it for the
#: container engine and for the node alike, and the reading by hand after a later
#: start that the q3-1 result page states. Each differs from the others.
OBSERVED_MEMORY = (
    pytest.param(10_429_960_192, id="q1-1"),
    pytest.param(10_429_972_480, id="q3-1"),
    pytest.param(10_429_956_096, id="later-start"),
)


@pytest.mark.parametrize("memory", OBSERVED_MEMORY)
def test_a_memory_reading_of_another_start_is_the_same_stable_environment(
    tmp_path: Path, root: Path, memory: int
) -> None:
    """The decided semantics: a memory figure is a capacity fact, not identity."""
    reading = capacity()
    reading["environment"]["containerEngine"]["memoryBytes"] = memory
    reading["nodes"][0]["allocatable"]["memoryBytes"] = memory
    reference = record_of(write(tmp_path / "a"), root)
    record = record_of(write(tmp_path / "b", {q1.CAPACITY_RECORD: reading}), root)
    assert record["result"] == "QUALIFIED"
    assert record["environmentSha256"] == reference["environmentSha256"]


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(_set(("environment", "containerEngine", "cpus"), 8), id="cpus"),
        pytest.param(
            _set(("nodes", 0, "allocatable", "cpuMillis"), 8000), id="cpu-millis"
        ),
        pytest.param(_set(("nodes", 0, "allocatable", "pods"), 100), id="pods"),
        pytest.param(_set(("nodes", 0, "kubeletVersion"), "v1.35.0"), id="kubelet"),
        pytest.param(
            _set(("environment", "kubernetesServerVersion"), "v1.35.0"),
            id="server-version",
        ),
        pytest.param(_set(("nodes", 0, "name"), "another-node"), id="node-name"),
        pytest.param(_set(("environment", "provider"), "kind"), id="provider"),
    ],
)
def test_each_fact_of_the_configuration_is_part_of_the_stable_identity(
    tmp_path: Path, root: Path, change: Callable[[Any], None]
) -> None:
    reference = record_of(write(tmp_path / "a"), root)
    record = record_of(
        write(tmp_path / "b", {q1.CAPACITY_RECORD: changed(capacity(), change)}),
        root,
    )
    assert record["environmentSha256"] is not None
    assert record["environmentSha256"] != reference["environmentSha256"]


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(_drop(("environment", "provider")), id="no-provider"),
        pytest.param(
            _set(("environment", "provider"), "Docker Desktop"), id="provider-form"
        ),
        pytest.param(
            _drop(("environment", "kubernetesServerVersion")), id="no-version"
        ),
        pytest.param(
            _set(("environment", "kubernetesServerVersion"), "1.36"), id="version-form"
        ),
        pytest.param(_drop(("environment", "containerEngine", "cpus")), id="no-cpus"),
        pytest.param(
            _set(("environment", "containerEngine", "cpus"), -1), id="cpus-negative"
        ),
        pytest.param(
            _set(("environment", "containerEngine", "cpus"), True), id="cpus-bool"
        ),
        pytest.param(
            _set(("environment", "containerEngine", "cpus"), "12"), id="cpus-text"
        ),
        pytest.param(
            _drop(("nodes", 0, "allocatable", "cpuMillis")), id="no-cpu-millis"
        ),
        pytest.param(
            _set(("nodes", 0, "allocatable", "pods"), 1.5), id="pods-fraction"
        ),
        pytest.param(_drop(("nodes", 0, "kubeletVersion")), id="no-kubelet"),
        pytest.param(_set(("nodes", 0, "name"), "Not A Name"), id="name-form"),
        pytest.param(_set(("nodes",), []), id="no-node"),
        pytest.param(_set(("environment",), "docker-desktop"), id="environment-form"),
    ],
)
def test_an_absent_or_malformed_identity_input_refuses_and_states_no_identity(
    tmp_path: Path, root: Path, change: Callable[[Any], None]
) -> None:
    record = record_of(
        write(tmp_path / "run", {q1.CAPACITY_RECORD: changed(capacity(), change)}),
        root,
    )
    assert record["result"] == "REFUSED"
    assert record["environment"] is None
    assert record["environmentSha256"] is None
    assert states(record)["context-unambiguous"] == "not-held"


def test_an_unreadable_capacity_record_states_no_identity(
    tmp_path: Path, root: Path
) -> None:
    record = record_of(write(tmp_path / "run", {q1.CAPACITY_RECORD: "{not json"}), root)
    assert record["result"] == "REFUSED"
    assert record["environment"] is None
    assert record["environmentSha256"] is None


def test_the_identity_does_not_depend_on_the_order_of_the_capacity_record(
    tmp_path: Path, root: Path
) -> None:
    def reversed_members(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: reversed_members(value[k]) for k in reversed(list(value))}
        if isinstance(value, list):
            return [reversed_members(item) for item in value]
        return value

    directory = write(tmp_path / "b")
    (directory / q1.CAPACITY_RECORD).write_text(
        json.dumps(reversed_members(capacity())), encoding="utf-8", newline="\n"
    )
    assert (
        record_of(directory, root)["environmentSha256"]
        == record_of(write(tmp_path / "a"), root)["environmentSha256"]
    )


def test_no_identity_of_one_revision_has_the_digest_of_one_of_the_other(
    tmp_path: Path, root: Path
) -> None:
    sources = q1.read_sources(write(tmp_path / "run"), root)
    exact = q1.environment_identity(sources)
    stable = q1.stable_environment_identity(sources)
    assert exact is not None and stable is not None
    assert q1.IDENTITY_REVISION_MEMBER not in exact
    assert stable[q1.IDENTITY_REVISION_MEMBER] == q1.STABLE_IDENTITY_REVISION
    assert q1.environment_digest(exact) != q1.environment_digest(stable)
    assert q1.identity_of(q1.FREEZE_RECORD_R1) is q1.environment_identity
    assert q1.identity_of(q1.FREEZE_RECORD) is q1.stable_environment_identity
    assert tuple(q1.REVISIONS) == q1.FREEZE_RECORDS


def test_insufficient_memory_is_refused_although_the_stable_identity_matches(
    tmp_path: Path, root: Path
) -> None:
    """The capacity gate decides memory for each reading, apart from identity.

    The real gate is run on the committed capacity collection of q1-1 with the
    node and the engine at 8 GiB, which is less than the declared limits and the
    reserve. The gate refuses, and the stable identity is unchanged. A Q1
    directory whose capacity reading the gate refused is REFUSED on
    capacity-accepted, while its stable identity has the accepted digest.
    """
    collection = tmp_path / "capacity"
    shutil.copytree(
        ROOT / "docs/proof/experiments/v2-q1/runs/q1-1/capacity", collection
    )
    (collection / "record.v1alpha1.json").unlink()
    nodes = json.loads((collection / "nodes.json").read_text("utf-8"))
    for figures in ("allocatable", "capacity"):
        nodes["items"][0]["status"][figures]["memory"] = "8388608Ki"
    write_json(collection / "nodes.json", nodes)
    write_json(collection / "engine.json", {"cpus": 12, "memoryBytes": 8 * 2**30})
    accepted = json.loads(
        (
            ROOT
            / "docs/proof/experiments/v2-q1/runs/q1-1/capacity/record.v1alpha1.json"
        ).read_text("utf-8")
    )
    refused = capacity_core.build_record(collection)
    assert accepted["result"] == "ACCEPTED"
    assert refused["result"] == "REFUSED"
    assert "memory-limits-fit" in refused["refusal"]["rules"]

    def stable(record: dict[str, Any]) -> dict[str, Any] | None:
        return q1.stable_environment_identity(
            q1.Sources(
                header={},
                capacity=q1.Source("capacity", value=record),
                provenance=q1.Source("", problem="absent"),
                reconciliation=q1.Source("", problem="absent"),
                deployments=q1.Source("", problem="absent"),
                endpoints=q1.Source("", problem="absent"),
                model_cache=q1.Source("", problem="absent"),
                plan=q1.Source("", problem="absent"),
                caller_text=None,
                caller_refused=False,
                root=root,
                directory=collection,
            )
        )

    assert stable(refused) is not None
    assert stable(refused) == stable(accepted)

    reading = capacity()
    reading["result"] = "REFUSED"
    reading["refusal"] = {"categories": ["capacity"], "rules": ["memory-limits-fit"]}
    reading["environment"]["containerEngine"]["memoryBytes"] = 8 * 2**30
    reading["nodes"][0]["allocatable"]["memoryBytes"] = 8 * 2**30
    reference = record_of(write(tmp_path / "a"), root)
    record = record_of(write(tmp_path / "b", {q1.CAPACITY_RECORD: reading}), root)
    assert record["environmentSha256"] == reference["environmentSha256"]
    assert record["result"] == "REFUSED"
    assert record["refusal"]["rules"] == ["capacity-accepted"]
    assert states(record)["capacity-accepted"] == "not-held"


def test_the_record_lists_each_file_it_read_by_its_digest(
    tmp_path: Path, root: Path
) -> None:
    directory = write(tmp_path / "run")
    record = record_of(directory, root)
    names = [item["name"] for item in record["files"]]
    assert names == [name for name in q1.SOURCE_FILES if (directory / name).exists()]
    for item in record["files"]:
        assert item["sha256"] == q1.lf_digest((directory / item["name"]).read_bytes())


# --------------------------------------------------------------------------
# Each rule refuses
# --------------------------------------------------------------------------


Defect = tuple[str, dict[str, Any], str, str]

_NO_SUCCESS_PLAN, _NO_SUCCESS_CALLER = caller(
    answer=(503, {"code": "adapter-unavailable"})
)

DEFECTS: list[Defect] = [
    (
        "a model pin copy of other content",
        {
            q1.MODEL_SOURCE_COPY: PIN_TEXT[q1.MODEL_SOURCE_COPY].replace(
                MODEL_SOURCE["revision"], "0" * 40
            )
        },
        "model-identity-verified",
        "not-held",
    ),
    (
        "a runtime pin copy of other content",
        {q1.RUNTIME_PACKAGE_COPY: PIN_TEXT[q1.RUNTIME_PACKAGE_COPY] + "\n"},
        "images-declared",
        "not-held",
    ),
    (
        "up refused on a dirty working tree",
        {q1.HEADER_FILE: header(upRefusal="working-tree")},
        "working-tree-clean",
        "not-held",
    ),
    (
        "up refused on differing delivery paths",
        {q1.HEADER_FILE: header(upRefusal="delivery-paths")},
        "desired-revision-known",
        "not-held",
    ),
    (
        "up refused on a changed material file",
        {q1.HEADER_FILE: header(upRefusal="frozen-inputs")},
        "procedure-frozen",
        "not-held",
    ),
    (
        "up refused on a release already present",
        {q1.HEADER_FILE: header(upRefusal="release-present")},
        "context-unambiguous",
        "not-held",
    ),
    (
        "up failed at a preparation step",
        {q1.HEADER_FILE: header(upRefusal="preparation-failed")},
        "deployments-ready",
        "not-held",
    ),
    (
        "no readable environment identity",
        {
            q1.CAPACITY_RECORD: changed(
                capacity(), lambda doc: doc["environment"].pop("containerEngine")
            )
        },
        "context-unambiguous",
        "not-held",
    ),
    (
        "a reconciliation sample after the end",
        {
            q1.RECONCILIATION_RECORD: changed(
                reconciliation(),
                _set(("samples", 4, "observedAt", "value"), instant(900)),
            )
        },
        "readings-in-order",
        "not-held",
    ),
    (
        "a start that is not a date",
        {q1.HEADER_FILE: header(startedAt="2026-13-45T00:00:00Z")},
        "readings-in-order",
        "not-held",
    ),
    (
        "a caller run with no success",
        {q1.PLAN_FILE: _NO_SUCCESS_PLAN, q1.CALLER_FILE: _NO_SUCCESS_CALLER},
        "caller-completed",
        "not-held",
    ),
    (
        "target refused, provider",
        {q1.HEADER_FILE: header(targetRefusal="provider-mismatch")},
        "provider-selected",
        "not-held",
    ),
    (
        "target refused, missing",
        {q1.HEADER_FILE: header(targetRefusal="target-missing")},
        "target-reached",
        "not-held",
    ),
    (
        "target refused, ambiguous",
        {q1.HEADER_FILE: header(targetRefusal="ambiguous-target")},
        "context-unambiguous",
        "not-held",
    ),
    (
        "another provider selected",
        {q1.HEADER_FILE: header(provider="kind")},
        "provider-selected",
        "not-held",
    ),
    (
        "a source names another provider",
        {
            q1.ENDPOINTS_RECORD: changed(
                endpoints(), _set(("collection", "provider"), "kind")
            )
        },
        "provider-selected",
        "not-held",
    ),
    (
        "another context",
        {
            q1.CAPACITY_RECORD: changed(
                capacity(), _set(("collection", "context"), "other")
            )
        },
        "context-unambiguous",
        "not-held",
    ),
    (
        "two nodes",
        {
            q1.CAPACITY_RECORD: changed(
                capacity(),
                lambda doc: doc["nodes"].append(copy.deepcopy(doc["nodes"][0])),
            )
        },
        "context-unambiguous",
        "not-held",
    ),
    (
        "runtime pods on another node",
        {
            q1.MODEL_CACHE_RECORD: changed(
                model_cache(), _set(("placement", "nodes"), ["other"])
            )
        },
        "context-unambiguous",
        "not-held",
    ),
    (
        "dirty working tree",
        {q1.HEADER_FILE: header(workingTree="dirty")},
        "working-tree-clean",
        "not-held",
    ),
    (
        "working tree not read",
        {q1.HEADER_FILE: header(workingTree="unread")},
        "working-tree-clean",
        "not-observed",
    ),
    (
        "another freeze record",
        {
            q1.HEADER_FILE: header(
                freezeRecord="docs/proof/experiments/v2-q1/freeze-r3.v1alpha1.json"
            )
        },
        "procedure-frozen",
        "not-held",
    ),
    (
        "a material file changed",
        {q1.HEADER_FILE: header(freezeChanges="listed")},
        "procedure-frozen",
        "not-held",
    ),
    (
        "freeze record of other content",
        {q1.HEADER_FILE: header(freezeRecordSha256="0" * 64)},
        "procedure-frozen",
        "not-held",
    ),
    (
        "desired revision unknown",
        {q1.HEADER_FILE: header(desiredRevision=None)},
        "desired-revision-known",
        "not-observed",
    ),
    (
        "desired revision of one repeated character",
        {q1.HEADER_FILE: header(desiredRevision="0" * 40)},
        "desired-revision-known",
        "not-held",
    ),
    (
        "delivery paths differ from the desired revision",
        {q1.HEADER_FILE: header(desiredStateDiff="differs")},
        "desired-revision-known",
        "not-held",
    ),
    (
        "a collection of another commit",
        {
            q1.MODEL_CACHE_RECORD: changed(
                model_cache(), _set(("collection", "executingCommit"), "f" * 40)
            )
        },
        "one-executing-commit",
        "not-held",
    ),
    (
        "provenance at another revision",
        {
            q1.PROVENANCE_FILE: changed(
                provenance(), _set((0, "git", "revision"), "e" * 40)
            )
        },
        "release-provenance-resolved",
        "not-held",
    ),
    (
        "provenance of another key",
        {
            q1.PROVENANCE_FILE: changed(
                provenance(),
                _set((0, "desiredState", "key"), "local-docker-desktop/other"),
            )
        },
        "release-provenance-resolved",
        "not-held",
    ),
    (
        "two provenance records",
        {q1.PROVENANCE_FILE: provenance() + provenance()},
        "release-provenance-resolved",
        "not-held",
    ),
    (
        "capacity refused",
        {
            q1.CAPACITY_RECORD: changed(
                capacity(),
                lambda doc: doc.update(
                    result="REFUSED",
                    refusal={"categories": ["insufficient"], "rules": ["x"]},
                ),
            )
        },
        "capacity-accepted",
        "not-held",
    ),
    (
        "capacity of one runtime replica",
        {
            q1.CAPACITY_RECORD: changed(
                capacity(), _set(("footprint", "topology", "runtimeReplicas"), 1)
            )
        },
        "capacity-accepted",
        "not-held",
    ),
    (
        "controller verification failed",
        {q1.HEADER_FILE: header(controllerVerified=False)},
        "controller-identified",
        "not-held",
    ),
    (
        "controller not verified",
        {q1.HEADER_FILE: header(controllerVerified=None)},
        "controller-identified",
        "not-observed",
    ),
    (
        "reconciliation incomplete",
        {
            q1.RECONCILIATION_RECORD: changed(
                reconciliation(), _set(("collection", "complete"), False)
            )
        },
        "controller-reconciled",
        "not-held",
    ),
    (
        "four samples",
        {
            q1.RECONCILIATION_RECORD: changed(
                reconciliation(), lambda doc: doc["samples"].pop()
            )
        },
        "controller-reconciled",
        "not-held",
    ),
    (
        "a sample not settled",
        {
            q1.RECONCILIATION_RECORD: changed(
                reconciliation(), _set(("samples", 2, "settled", "value"), False)
            )
        },
        "controller-reconciled",
        "not-held",
    ),
    (
        "a sample at another revision",
        {
            q1.RECONCILIATION_RECORD: changed(
                reconciliation(),
                _set(("samples", 0, "fields", "resolvedRevision", "value"), "e" * 40),
            )
        },
        "controller-reconciled",
        "not-held",
    ),
    (
        "a sample of another release",
        {
            q1.RECONCILIATION_RECORD: changed(
                reconciliation(),
                _set(("samples", 1, "consistency", "releaseId"), "e" * 64),
            )
        },
        "controller-reconciled",
        "not-held",
    ),
    (
        "a label finding",
        {
            q1.RECONCILIATION_RECORD: changed(
                reconciliation(),
                _set(
                    ("samples", 1, "consistency", "labels", "findings"), [{"rule": "x"}]
                ),
            )
        },
        "controller-reconciled",
        "not-held",
    ),
    (
        "labels compared in part",
        {
            q1.RECONCILIATION_RECORD: changed(
                reconciliation(),
                _set(
                    ("samples", 1, "consistency", "labels", "state"), "compared-in-part"
                ),
            )
        },
        "controller-reconciled",
        "not-held",
    ),
    (
        "one runtime replica Ready",
        {
            q1.DEPLOYMENTS_FILE: changed(
                deployments(), _set(("items", 1, "status", "readyReplicas"), 1)
            )
        },
        "deployments-ready",
        "not-held",
    ),
    (
        "a runtime Deployment of one replica",
        {
            q1.DEPLOYMENTS_FILE: changed(
                deployments(), _set(("items", 1, "spec", "replicas"), 1)
            )
        },
        "deployments-ready",
        "not-held",
    ),
    (
        "a rollout that is not observed",
        {
            q1.DEPLOYMENTS_FILE: changed(
                deployments(), _set(("items", 0, "metadata", "generation"), 2)
            )
        },
        "deployments-ready",
        "not-held",
    ),
    (
        "a third pod in a rollout",
        {
            q1.DEPLOYMENTS_FILE: changed(
                deployments(), _set(("items", 0, "status", "replicas"), 3)
            )
        },
        "deployments-ready",
        "not-held",
    ),
    (
        "no API Deployment",
        {q1.DEPLOYMENTS_FILE: changed(deployments(), lambda doc: doc["items"].pop(0))},
        "deployments-ready",
        "not-held",
    ),
    (
        "one Ready runtime endpoint",
        {
            q1.ENDPOINTS_RECORD: changed(
                endpoints(), _set(("tiers", 1, "endpoints", "ready"), 1)
            )
        },
        "endpoints-ready",
        "not-held",
    ),
    (
        "a third API endpoint",
        {
            q1.ENDPOINTS_RECORD: changed(
                endpoints(), _set(("tiers", 0, "endpoints", "total"), 3)
            )
        },
        "endpoints-ready",
        "not-held",
    ),
    (
        "endpoint record refused",
        {q1.ENDPOINTS_RECORD: changed(endpoints(), _set(("result",), "REFUSED"))},
        "endpoints-ready",
        "not-held",
    ),
    (
        "another API image",
        {
            q1.DEPLOYMENTS_FILE: changed(
                deployments(),
                _set(
                    ("items", 0, "spec", "template", "spec", "containers", 0, "image"),
                    "localhost/inferops-api@sha256:" + "0" * 64,
                ),
            )
        },
        "images-declared",
        "not-held",
    ),
    (
        "another runtime image",
        {
            q1.DEPLOYMENTS_FILE: changed(
                deployments(),
                _set(
                    ("items", 1, "spec", "template", "spec", "containers", 0, "image"),
                    "ghcr.io/ggml-org/llama.cpp@sha256:" + "0" * 64,
                ),
            )
        },
        "images-declared",
        "not-held",
    ),
    (
        "no API image digest declared",
        {q1.HEADER_FILE: header(apiImageDigest=None)},
        "images-declared",
        "not-observed",
    ),
    (
        "another model revision expected",
        {
            q1.MODEL_CACHE_RECORD: changed(
                model_cache(), _set(("expected", "model", "revision"), "0" * 40)
            )
        },
        "model-identity-verified",
        "not-held",
    ),
    (
        "another model digest expected",
        {
            q1.MODEL_CACHE_RECORD: changed(
                model_cache(),
                _set(("expected", "model", "sha256"), "sha256:" + "0" * 64),
            )
        },
        "model-identity-verified",
        "not-held",
    ),
    (
        "one runtime replica expected",
        {
            q1.MODEL_CACHE_RECORD: changed(
                model_cache(), _set(("expected", "runtimeReplicas"), 1)
            )
        },
        "model-identity-verified",
        "not-held",
    ),
    (
        "a model rule not held",
        {
            q1.MODEL_CACHE_RECORD: changed(
                model_cache(), _set(("rules", 13, "state"), "not-held")
            )
        },
        "model-identity-verified",
        "not-held",
    ),
    (
        "a model rule absent",
        {
            q1.MODEL_CACHE_RECORD: changed(
                model_cache(), lambda doc: doc["rules"].pop(12)
            )
        },
        "model-identity-verified",
        "not-held",
    ),
    (
        "a capacity reading after the start",
        {
            q1.CAPACITY_RECORD: changed(
                capacity(), _set(("collection", "collectedAt"), instant(5))
            )
        },
        "readings-in-order",
        "not-held",
    ),
    (
        "an endpoint reading after the end",
        {
            q1.ENDPOINTS_RECORD: changed(
                endpoints(), _set(("collection", "readStartedAt"), instant(900))
            )
        },
        "readings-in-order",
        "not-held",
    ),
]


@pytest.mark.parametrize(
    ("changes", "rule", "state"),
    [
        pytest.param(changes, rule, state, id=name)
        for name, changes, rule, state in DEFECTS
    ],
)
def test_one_defect_refuses_its_rule_with_its_category(
    tmp_path: Path, root: Path, changes: dict[str, Any], rule: str, state: str
) -> None:
    record = record_of(write(tmp_path / "run", changes), root)
    assert record["result"] == "REFUSED"
    assert states(record)[rule] == state
    assert rule in record["refusal"]["rules"]
    assert RULE_CATEGORIES[rule] in record["refusal"]["categories"]


def test_each_rule_has_a_defect_in_this_suite() -> None:
    assert {rule for _, _, rule, _ in DEFECTS} == set(RULE_CATEGORIES)


def test_the_categories_are_listed_in_their_order_without_repetition(
    tmp_path: Path, root: Path
) -> None:
    directory = write(
        tmp_path / "run",
        {
            q1.HEADER_FILE: header(
                workingTree="dirty", targetRefusal="provider-mismatch"
            )
        },
    )
    categories = record_of(directory, root)["refusal"]["categories"]
    assert categories == [item for item in q1.CATEGORIES if item in categories]
    assert len(categories) == len(set(categories))
    assert {"target", "provider-mismatch", "desired-state"} <= set(categories)


@pytest.mark.parametrize(
    ("name", "rules"),
    [
        (
            q1.CAPACITY_RECORD,
            {"capacity-accepted", "target-reached", "context-unambiguous"},
        ),
        (q1.PROVENANCE_FILE, {"release-provenance-resolved", "controller-reconciled"}),
        (q1.RECONCILIATION_RECORD, {"controller-reconciled", "one-executing-commit"}),
        (q1.DEPLOYMENTS_FILE, {"deployments-ready", "images-declared"}),
        (q1.ENDPOINTS_RECORD, {"endpoints-ready", "one-executing-commit"}),
        (q1.MODEL_CACHE_RECORD, {"model-identity-verified", "context-unambiguous"}),
        (q1.CALLER_FILE, {"caller-completed", "readings-in-order"}),
        (q1.PLAN_FILE, {"caller-completed"}),
        (q1.MODEL_SOURCE_COPY, {"model-identity-verified", "images-declared"}),
        (q1.RUNTIME_PACKAGE_COPY, {"model-identity-verified", "images-declared"}),
    ],
)
def test_an_absent_source_is_not_observed_and_refuses(
    tmp_path: Path, root: Path, name: str, rules: set[str]
) -> None:
    record = record_of(write(tmp_path / "run", without=(name,)), root)
    assert record["result"] == "REFUSED"
    for rule in rules:
        assert states(record)[rule] == "not-observed", rule


def test_a_source_of_another_schema_is_not_held_and_not_absent(
    tmp_path: Path, root: Path
) -> None:
    wrong = changed(capacity(), _set(("schema",), "inferops.io/other/v1alpha1"))
    record = record_of(write(tmp_path / "run", {q1.CAPACITY_RECORD: wrong}), root)
    assert states(record)["capacity-accepted"] == "not-held"
    unreadable = write(tmp_path / "text", {q1.ENDPOINTS_RECORD: "not json"})
    assert states(record_of(unreadable, root))["endpoints-ready"] == "not-held"


# --------------------------------------------------------------------------
# The caller record
# --------------------------------------------------------------------------


def test_a_caller_record_with_no_success_refuses(tmp_path: Path, root: Path) -> None:
    plan_text, caller_text = caller(answer=(503, {"code": "adapter-unavailable"}))
    directory = write(
        tmp_path / "run", {q1.PLAN_FILE: plan_text, q1.CALLER_FILE: caller_text}
    )
    record = record_of(directory, root)
    assert states(record)["caller-completed"] == "not-held"
    finding = next(
        item for item in record["findings"] if item["ruleId"] == "caller-completed"
    )
    assert "success" in finding["detail"]


def test_a_caller_record_of_another_plan_is_refused_by_the_runners_reader(
    tmp_path: Path, root: Path
) -> None:
    other_plan, _ = caller(duration_seconds=61)
    directory = write(tmp_path / "run", {q1.PLAN_FILE: other_plan})
    finding = next(
        item
        for item in record_of(directory, root)["findings"]
        if item["ruleId"] == "caller-completed"
    )
    assert finding["state"] == "not-held"
    assert "runner-plan" in finding["detail"] or "caller-record" in finding["detail"]


@pytest.mark.parametrize(
    ("changes", "word"),
    [
        ({"experiment_id": "another-experiment"}, "experiment"),
        ({"run_id": "q1-2"}, "run identifier"),
        ({"release_id": "e" * 64}, "release"),
    ],
)
def test_a_caller_record_of_another_run_refuses(
    tmp_path: Path, root: Path, changes: dict[str, Any], word: str
) -> None:
    plan_text, caller_text = caller(**changes)
    directory = write(
        tmp_path / "run", {q1.PLAN_FILE: plan_text, q1.CALLER_FILE: caller_text}
    )
    finding = next(
        item
        for item in record_of(directory, root)["findings"]
        if item["ruleId"] == "caller-completed"
    )
    assert finding["state"] == "not-held"
    assert word in finding["detail"]


def test_a_caller_record_kept_as_refused_refuses(tmp_path: Path, root: Path) -> None:
    directory = write(tmp_path / "run")
    (directory / q1.CALLER_REFUSED_FILE).write_text("{}\n", encoding="utf-8")
    assert states(record_of(directory, root))["caller-completed"] == "not-held"


# --------------------------------------------------------------------------
# What is not a collection
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(None, id="absent"),
        pytest.param("not json", id="not-json"),
        pytest.param([], id="not-an-object"),
        pytest.param({**header(), "context": "docker-desktop"}, id="extra-member"),
        pytest.param(
            {k: v for k, v in header().items() if k != "finishedAt"}, id="member-absent"
        ),
        pytest.param(header(schema="inferops.io/other/v1alpha1"), id="another-schema"),
        pytest.param(header(qualificationId="q2-1"), id="another-qualification"),
        pytest.param(header(executingCommit="HEAD"), id="commit-not-a-sha"),
        pytest.param(
            header(targetRefusal="refusing: provider-mismatch: x"), id="refusal-text"
        ),
        pytest.param(header(controllerVerified="yes"), id="verified-not-a-boolean"),
    ],
)
def test_a_directory_without_a_usable_header_is_not_a_collection(
    tmp_path: Path, document: Any
) -> None:
    directory = write(tmp_path / "run", without=(q1.HEADER_FILE,))
    if isinstance(document, str):
        (directory / q1.HEADER_FILE).write_text(document, encoding="utf-8")
    elif document is not None:
        write_json(directory / q1.HEADER_FILE, document)
    with pytest.raises(q1.CollectionRefused):
        q1.build_record(directory)
    assert cli.main([str(directory)]) == 1


def test_the_command_exits_0_for_qualified_and_5_for_refused(
    tmp_path: Path,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli, "build_record", lambda directory: q1.build_record(directory, root)
    )
    assert cli.main([str(write(tmp_path / "good"))]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["result"] == "QUALIFIED"
    refused = write(tmp_path / "bad", {q1.HEADER_FILE: header(workingTree="dirty")})
    assert cli.main([str(refused)]) == 5
    assert json.loads(capsys.readouterr().out)["result"] == "REFUSED"


def test_the_command_has_no_option_for_the_target() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--key", "local-docker-desktop/other", "directory"])
    assert exit_info.value.code == 2
    with pytest.raises(SystemExit):
        cli.main([])
    source = (ROOT / "tools/environment_qualification/__main__.py").read_text("utf-8")
    assert re.findall(r"add_argument\(\s*\"([^\"]+)\"", source) == [
        "directory",
        "--check",
    ]


def test_the_command_runs_as_a_module_and_refuses_a_missing_directory(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.environment_qualification",
            str(tmp_path / "none"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert completed.stderr.startswith("REFUSED  not-a-collection:")


def test_check_compares_each_committed_record_with_its_directory(
    tmp_path: Path, root: Path
) -> None:
    assert q1.check_committed(root) == []
    run = write(root / "docs/proof/experiments/v2-q1/runs/q1-1")
    assert q1.check_committed(root) == [
        "docs/proof/experiments/v2-q1/runs/q1-1: no record.v1alpha1.json"
    ]
    (run / q1.RECORD_FILE).write_text(
        q1.record_text(q1.build_record(run, root)), encoding="utf-8", newline="\n"
    )
    assert q1.check_committed(root) == []
    write_json(
        run / q1.DEPLOYMENTS_FILE,
        changed(deployments(), _set(("items", 1, "spec", "replicas"), 1)),
    )
    assert q1.check_committed(root) == [
        "docs/proof/experiments/v2-q1/runs/q1-1: record.v1alpha1.json is not what the directory gives"
    ]


def test_the_one_committed_qualification_is_what_its_directory_gives() -> None:
    """V2-S6-001-PR2 committed q1-1. Its record is built again from the directory,
    with the two pin copies of the directory and the registered freeze record."""
    assert [path.name for path in q1.committed_runs()] == ["q1-1"]
    assert q1.check_committed() == []
    assert cli.main(["--check"]) == 0


def test_the_committed_qualification_is_qualified_with_every_rule_held() -> None:
    (run,) = q1.committed_runs()
    record = json.loads((run / q1.RECORD_FILE).read_text(encoding="utf-8"))
    assert record["result"] == "QUALIFIED"
    assert record["refusal"] == {"categories": [], "rules": []}
    assert [f["state"] for f in record["findings"]] == ["held"] * 17
    assert record["environmentSha256"] is not None
    assert record["target"] == {
        "apiReplicas": 2,
        "provider": "docker-desktop",
        "releaseKey": "local-docker-desktop/support-assistant",
        "runtimeReplicas": 2,
    }


# --------------------------------------------------------------------------
# The target is the desired-state release
# --------------------------------------------------------------------------


def test_the_target_is_the_desired_state_release_with_two_and_two_replicas() -> None:
    from tools.gitops_desired_state import DESIRED_STATE_RELEASES, release_key

    keys = [release_key(release) for release in DESIRED_STATE_RELEASES]
    assert q1.TARGET_RELEASE_KEY in keys
    values = yaml.safe_load(VALUES.read_text("utf-8"))
    assert values["api"]["replicaCount"] == q1.TARGET_API_REPLICAS == 2
    assert values["runtime"]["replicaCount"] == q1.TARGET_RUNTIME_REPLICAS == 2


def test_the_model_rules_that_q1_reads_are_rules_of_the_observation() -> None:
    from tools.runtime_model_cache import RULES as MODEL_RULES

    identifiers = [rule.rule_id for rule in MODEL_RULES]
    assert set(q1.MODEL_CACHE_RULES) <= set(identifiers)
    assert set(identifiers) - set(q1.MODEL_CACHE_RULES) == {
        "capacity-preflight-sufficient",
        "not-ready-while-loading",
    }


def test_the_runtime_image_pin_is_the_one_the_observation_expects() -> None:
    from tools.runtime_model_cache import expected_identity

    expected = expected_identity()
    assert expected["runtimeImage"]["reference"] == RUNTIME_IMAGE
    assert expected["model"] == PINNED_MODEL
    assert expected["runtimeReplicas"] == q1.TARGET_RUNTIME_REPLICAS


# --------------------------------------------------------------------------
# The rules are the frozen criteria, and the page and the driver restate them
# --------------------------------------------------------------------------


def test_the_rules_are_the_restated_rules_in_order() -> None:
    assert [rule.rule_id for rule in q1.RULES] == list(RULE_CATEGORIES)
    assert {rule.rule_id: rule.category for rule in q1.RULES} == RULE_CATEGORIES
    assert [rule.criterion for rule in q1.RULES] == [
        f"Q1-AC{index}" for index in range(1, len(q1.RULES) + 1)
    ]
    assert len(q1.RULES) == 17
    assert set(RULE_CATEGORIES.values()) == set(q1.CATEGORIES)


def test_each_rule_is_one_acceptance_criterion_of_the_freeze_record() -> None:
    record = json.loads(FREEZE.read_text("utf-8"))
    (entry,) = record["fields"]["acceptanceCriteria"]
    assert entry["parts"] == ["Q1"]
    assert entry["value"] == [
        {"id": rule.criterion, "statement": rule.statement} for rule in q1.RULES
    ]


def test_the_freeze_record_freezes_the_q1_target_and_holds_no_result() -> None:
    record = json.loads(FREEZE.read_text("utf-8"))
    assert record["kind"] == "ExperimentFreeze"
    assert record["metadata"]["experiment"] == q1.EXPERIMENT_ID
    assert record["metadata"]["revision"] == 2
    assert record["metadata"]["supersedes"] == {
        "path": "docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json",
        "contentSha256": freeze.content_digest(FREEZE_R1.read_bytes()),
    }
    fields = record["fields"]
    (topology,) = fields["topology"]
    assert topology["value"]["apiReplicas"] == 2
    assert topology["value"]["runtimeReplicas"] == 2
    assert topology["value"]["releaseKey"] == q1.TARGET_RELEASE_KEY
    (profile,) = fields["callerProfileRevision"]
    assert profile["value"]["contentSha256"] == (
        "ff3cbab5a3bde8d4e25defe940cbcfb4ea3ff1ba028f1bc25c577636c261c1c3"
    )
    (level,) = fields["intendedEvidenceLevel"]
    assert level["value"] == "C2"
    (fault,) = fields["fault"]
    assert fault["status"] == "not-applicable"
    (bounds,) = fields["derivedNumericBounds"]
    assert bounds["status"] == "not-applicable"
    # The result is in a qualification directory, not in the freeze record. Since
    # V2-S6-001-PR2 the one directory is q1-1.
    assert "result" not in record
    assert [path.name for path in (FREEZE.parent / "runs").iterdir()] == ["q1-1"]


def test_revision_2_supersedes_revision_1_and_changes_no_criterion() -> None:
    """Revision 2 changes the identity that a record states, and nothing that a
    rule holds: the same seventeen criteria, the same target, the same scope."""
    r1 = json.loads(FREEZE_R1.read_text("utf-8"))
    r2 = json.loads(FREEZE.read_text("utf-8"))
    assert r1["metadata"]["revision"] == 1
    assert r1["metadata"]["supersedes"] is None
    assert r2["fields"]["acceptanceCriteria"] == r1["fields"]["acceptanceCriteria"]
    assert r2["fields"]["topology"] == r1["fields"]["topology"]
    assert r2["materialScope"] == r1["materialScope"]
    assert {change["path"]: change["material"] for change in r2["inputChanges"]} == {
        "docs/proof/experiments/v2-q1/procedure/q1-driver.txt": False,
        "tools/environment_qualification/__init__.py": False,
        "tools/environment_qualification/core.py": True,
    }
    (identity,) = r2["fields"]["environmentIdentity"]
    assert "no memory figure" in identity["value"]["recordedPerQualification"]
    assert "Q1-AC9" in identity["value"]["capacity"]
    assert (ROOT / identity["value"]["decision"]).is_file()
    assert freeze.changed_inputs(r2) == []


def test_revision_1_can_no_longer_govern_a_new_qualification() -> None:
    """A driver run under revision 1 finds the moved Q1 tool, so the freeze check
    lists a changed material file and procedure-frozen refuses it."""
    r1 = json.loads(FREEZE_R1.read_text("utf-8"))
    changed_paths = {change.path for change in freeze.changed_inputs(r1)}
    assert "tools/environment_qualification/core.py" in changed_paths
    driver = DRIVER.read_text("utf-8")
    assert f'FREEZE_RECORD="{q1.FREEZE_RECORD}"' in driver
    assert "freeze-r1.v1alpha1.json" not in driver


def test_the_committed_q1_1_keeps_its_exact_identity_and_digest() -> None:
    """q1-1 was decided under revision 1. It is built again under revision 1,
    with the exact identity, its memory figures, and the digest it states."""
    (run,) = q1.committed_runs()
    record = json.loads((run / q1.RECORD_FILE).read_text(encoding="utf-8"))
    assert record["collection"]["freezeRecord"] == q1.FREEZE_RECORD_R1
    assert record["environment"]["containerEngine"]["memoryBytes"] == 10_429_960_192
    assert record["environment"]["nodes"][0]["allocatable"]["memoryBytes"] == (
        10_429_960_192
    )
    assert q1.IDENTITY_REVISION_MEMBER not in record["environment"]
    assert record["environmentSha256"] == (
        "sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461"
    )
    assert record["doesNotEstablish"] == list(q1.DOES_NOT_ESTABLISH_R1)
    assert q1.record_text(q1.build_record(run)) == record_text_of(run)


def record_text_of(run: Path) -> str:
    return (run / q1.RECORD_FILE).read_bytes().replace(b"\r\n", b"\n").decode()


def test_the_freeze_record_pins_the_tool_and_the_driver() -> None:
    record = json.loads(FREEZE.read_text("utf-8"))
    pinned = {item["path"]: item for item in record["pinnedInputs"]}
    for path in (
        "tools/environment_qualification/core.py",
        "tools/environment_qualification/__main__.py",
        "docs/proof/experiments/v2-q1/procedure/q1-driver.txt",
        "scripts/environment/capacity-preflight.sh",
        "docs/serving/model-source.v1.json",
        "deploy/serving/runtime/container-package.v1.json",
        "deploy/serving/reliability/rp-1-profile.v1.json",
    ):
        assert path in pinned, path
        assert pinned[path]["sha256"] == freeze.content_digest(
            (ROOT / path).read_bytes()
        )
    assert (
        pinned["docs/proof/experiments/v2-q1/procedure/q1-driver.txt"]["role"]
        == "procedure"
    )


def test_the_page_restates_each_rule_and_each_category() -> None:
    page = PAGE.read_text("utf-8")
    for rule in q1.RULES:
        row = f"| `{rule.criterion}` | `{rule.rule_id}` | `{rule.category}` | {rule.statement} |"
        assert row in page, rule.rule_id
    assert f"{len(q1.RULES)} rules." in page
    for category in q1.CATEGORIES:
        assert f"`{category}`" in page


def test_the_driver_names_the_freeze_record_the_experiment_and_each_file() -> None:
    driver = DRIVER.read_text("utf-8")
    assert f'FREEZE_RECORD="{q1.FREEZE_RECORD}"' in driver
    assert f'EXPERIMENT="{q1.EXPERIMENT_ID}"' in driver
    assert "python -m tools.experiment_freeze --changes" in driver
    assert "python -m tools.environment_qualification" in driver
    for name in q1.SOURCE_FILES:
        assert name in driver, name
    assert "refusing to select a target: " in driver
    assert "--context docker-desktop" in driver


def test_the_driver_is_valid_bash_with_lf_line_ends() -> None:
    data = DRIVER.read_bytes()
    assert b"\r\n" not in data
    bash = shutil.which("bash")
    if bash is None:  # pragma: no cover - every supported host has bash
        pytest.skip("bash is not installed")
    completed = subprocess.run(
        [bash, "-n", str(DRIVER)], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr


def test_the_driver_sets_one_value_and_only_on_the_preparation_release() -> None:
    """The driver scales nothing. Its one Helm value is the memory limit of the
    acquisition job of the preparation release, which is removed before the
    Application is applied. It states no value of the qualified release."""
    driver = DRIVER.read_text("utf-8")
    assert "kubectl scale" not in driver and "k scale" not in driver
    assert "replicaCount" not in driver
    assert re.findall(r"--set(?:-string|-json)?\s+(\S+)", driver) == [
        "model.acquisition.resources.limits.memory=2Gi"
    ]
    install = driver.index("helm --kube-context docker-desktop install inferops")
    uninstall = driver.index("helm --kube-context docker-desktop uninstall inferops")
    assert install < driver.index("--set model.acquisition") < uninstall
    assert uninstall < driver.index('run bash "${APPLICATION_SCRIPT}" apply')


# --------------------------------------------------------------------------
# What a record says it is not
# --------------------------------------------------------------------------


def test_each_sentence_of_what_a_record_does_not_establish_says_so() -> None:
    for sentence in (*q1.DOES_NOT_ESTABLISH, *q1.DOES_NOT_ESTABLISH_R1):
        assert sentence.startswith("A record does not establish "), sentence
        assert not re.search(r"\b(reliable|robust|guarantee|proves?)\b", sentence, re.I)


def test_the_record_text_is_sorted_indented_json_with_one_final_lf(
    tmp_path: Path, root: Path
) -> None:
    record = record_of(write(tmp_path / "run"), root)
    text = q1.record_text(record)
    assert text.endswith("}\n") and not text.endswith("\n\n")
    assert json.loads(text) == record
    assert text == json.dumps(record, indent=2, sort_keys=True) + "\n"


# --------------------------------------------------------------------------
# A source of another form refuses and does not raise
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "rule", "state"),
    [
        pytest.param(
            {
                q1.ENDPOINTS_RECORD: changed(
                    endpoints(), _set(("tiers", 0, "tier"), ["platform-api"])
                )
            },
            "endpoints-ready",
            "not-held",
            id="tier-not-text",
        ),
        pytest.param(
            {
                q1.MODEL_CACHE_RECORD: changed(
                    model_cache(), _set(("rules", 0, "id"), {"id": "replica-count"})
                )
            },
            "model-identity-verified",
            "not-held",
            id="rule-id-not-text",
        ),
        pytest.param(
            {
                q1.ENDPOINTS_RECORD: changed(
                    endpoints(),
                    _set(("collection", "readStartedAt"), "2026-01-01T24:00:00Z"),
                )
            },
            "readings-in-order",
            "not-observed",
            id="instant-not-a-time",
        ),
        pytest.param(
            {
                q1.RECONCILIATION_RECORD: changed(
                    reconciliation(), _set(("samples", 2, "observedAt"), None)
                )
            },
            "readings-in-order",
            "not-observed",
            id="sample-without-instant",
        ),
        pytest.param(
            {q1.HEADER_FILE: header(desiredRevision=None)},
            "release-provenance-resolved",
            "not-observed",
            id="no-desired-revision-to-compare",
        ),
    ],
)
def test_a_member_of_another_form_refuses_and_does_not_raise(
    tmp_path: Path, root: Path, changes: dict[str, Any], rule: str, state: str
) -> None:
    record = record_of(write(tmp_path / "run", changes), root)
    assert record["result"] == "REFUSED"
    assert states(record)[rule] == state


def test_a_qualified_record_always_states_its_environment(
    tmp_path: Path, root: Path
) -> None:
    record = record_of(write(tmp_path / "run"), root)
    assert record["result"] == "QUALIFIED"
    assert record["environment"] is not None
    assert record["environmentSha256"] is not None


def test_the_driver_keeps_the_record_of_a_refused_qualification() -> None:
    driver = DRIVER.read_text("utf-8")
    assert (
        r"""0 | 5) tr -d '\r' <"${WORK}/record.tmp" >"${A}/${RECORD_FILE}" ;;"""
        in driver
    )
    assert 'read_into "${A}/${RECORD_FILE}"' not in driver


def test_the_driver_states_each_reason_of_a_refusal_of_up() -> None:
    driver = DRIVER.read_text("utf-8")
    stated = set(re.findall(r"up_refuse ([a-z-]+) ", driver))
    stated |= set(re.findall(r"printf '([a-z-]+)' >\"\$\{WORK\}/up-refusal\"", driver))
    assert stated == set(q1.UP_REFUSALS)
    assert driver.index('now >"${WORK}/started-at"') < driver.index(
        "up_refuse working-tree"
    )


def test_the_driver_refuses_a_reused_identifier_of_a_collection() -> None:
    driver = DRIVER.read_text("utf-8")
    assert (
        'for used in "${OBSERVATIONS}/${QID}" "${ENDPOINT_COLLECTIONS}/${QID}" '
        '"${RUNNER_RUNS}/${QID}"; do'
    ) in driver
