"""What the serving runtime replicas read from the model cache, as an evidence record.

A run driver writes a bounded set of cluster reads into one directory.
``tools.runtime_model_cache`` reads that directory and returns one record. This
suite writes such directories by hand and holds the tool to them.

Five things are held:

* the expected identity comes from committed files: the desired-state release,
  the chart's default mount path, and the two pin records, and a disagreement
  between the release and a pin record is a finding;
* a complete collection of two replicas holds every rule, and each read that
  disagrees with the expected identity, or with the other replica, makes its
  rule ``not-held`` and the result ``FAILED``;
* a read that was not made is not a value: each absent or unreadable file makes
  the rule that needs it ``not-observed``, and one pod is never compared with
  itself;
* the record is built from an allowlist, and a pod name that is not a name
  reads no file;
* the tool reads files only, and the document publishes the record's schema,
  each rule, each result state, and what a record does not establish.

What this establishes about a cluster: nothing. Every directory that the tool is
given in the cases above is written by this suite. The committed runs are what
the tool built from collections on a cluster. The last tests read them as files,
and they observe no cluster.
"""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tools.gitops_desired_state import DESIRED_STATE_RELEASES
from tools.runtime_model_cache import (
    CAPACITY_REFUSED_EXIT,
    COLLECTION_SCHEMA,
    DOES_NOT_ESTABLISH,
    EXPECTED_SCHEMA,
    HELD,
    NOT_HELD,
    NOT_OBSERVED,
    RECORD_FILE,
    RECORD_SCHEMA,
    RESULT_STATES,
    RULES,
    RUNS_PATTERN,
    CollectionRefused,
    ExpectedRefused,
    build_record,
    cache_sub_path,
    check_committed_runs,
    committed_runs,
    expected_identity,
    pin_findings,
    record_text,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_DIRECTORY = REPO_ROOT / "tools" / "runtime_model_cache"
DOCUMENT_PATH = (
    REPO_ROOT / "docs" / "environment" / "runtime-model-cache-observation.md"
)
PREREQUISITE_MODULE = (
    REPO_ROOT / "infra" / "terraform" / "modules" / "platform-prerequisites" / "main.tf"
)

EXPECTED = expected_identity()
MODEL = EXPECTED["model"]
DIGEST = MODEL["sha256"].removeprefix("sha256:")
PATH = EXPECTED["containerPath"]
ALIAS = "reference-alias"
PODS = ("runtime-7d9c-aaaaa", "runtime-7d9c-bbbbb")
MARKER = "planted-marker-that-no-record-holds"

SCRIPT = (
    f"set -eu\nartifact={PATH}\n"
    f'[ "$(wc -c < "$artifact")" = "{MODEL["sizeBytes"]}" ]\n'
    f'echo "{DIGEST}  $artifact" | sha256sum -c -\n'
)


def _mount() -> dict[str, Any]:
    return {
        "name": "model-cache",
        "mountPath": EXPECTED["mountPath"],
        "readOnly": True,
        "subPath": EXPECTED["cacheSubPath"],
    }


def _pod(name: str) -> dict[str, Any]:
    """One runtime pod, as the cluster would report it for the expected release."""
    return {
        "metadata": {
            "name": name,
            "labels": {"app.kubernetes.io/component": "serving-runtime"},
            "annotations": {"note": MARKER},
        },
        "spec": {
            "nodeName": "node-one",
            "containers": [
                {
                    "name": "runtime",
                    "image": EXPECTED["runtimeImage"]["reference"],
                    "args": ["--model", PATH, "--alias", ALIAS, "--port", "8080"],
                    "env": [{"name": "PLANTED", "value": MARKER}],
                    "volumeMounts": [
                        _mount(),
                        {"name": "tmp", "mountPath": "/tmp"},
                    ],
                }
            ],
            "initContainers": [
                {
                    "name": "verify-model",
                    "command": ["/bin/sh", "-c", SCRIPT],
                    "volumeMounts": [_mount()],
                }
            ],
            "volumes": [
                {
                    "name": "model-cache",
                    "persistentVolumeClaim": {
                        "claimName": EXPECTED["claimName"],
                        "readOnly": True,
                    },
                },
                {"name": "tmp", "emptyDir": {"medium": "Memory"}},
            ],
        },
        "status": {
            "phase": "Running",
            "conditions": [
                {"type": "Initialized", "status": "True"},
                {
                    "type": "Ready",
                    "status": "True",
                    "lastTransitionTime": "2026-01-01T00:05:00Z",
                },
            ],
            "containerStatuses": [
                {
                    "name": "runtime",
                    "imageID": EXPECTED["runtimeImage"]["reference"],
                    "restartCount": 0,
                    "volumeMounts": [
                        {
                            "name": "model-cache",
                            "readOnly": True,
                            "recursiveReadOnly": "Disabled",
                        }
                    ],
                }
            ],
            "initContainerStatuses": [
                {
                    "name": "verify-model",
                    "state": {
                        "terminated": {
                            "exitCode": 0,
                            "finishedAt": "2026-01-01T00:01:00Z",
                        }
                    },
                }
            ],
        },
    }


def _claim(name: str) -> dict[str, Any]:
    return {
        "metadata": {
            "name": name,
            "labels": {
                "app.kubernetes.io/managed-by": "Terraform",
                "inferops.io/lifecycle": "prerequisite",
                "app.kubernetes.io/component": "model-cache-volume-claim",
            },
            "annotations": {"note": MARKER},
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "storageClassName": "standard",
            "volumeName": "pvc-0001",
        },
        "status": {"phase": "Bound"},
    }


def _mount_table(options: str = "ro,relatime", root: str = "/pvc-0001/rev") -> str:
    return (
        "100 90 0:50 / / rw,relatime - overlay overlay rw\n"
        f"101 100 8:48 {root} {EXPECTED['mountPath']} {options} - ext4 /dev/sdd rw\n"
        "102 100 0:60 / /tmp rw,nosuid - tmpfs tmpfs rw\n"
    )


def complete() -> dict[str, Any]:
    """Every file of a collection in which two replicas hold every rule."""
    files: dict[str, Any] = {
        "run.json": {
            "schema": COLLECTION_SCHEMA,
            "runId": "a-run",
            "provider": "a-provider",
            "namespace": "a-namespace",
            "executingCommit": "a" * 40,
            "reportedRevision": "b" * 40,
            "startedAt": "2026-01-01T00:00:00Z",
            "collectedAt": "2026-01-01T00:10:00Z",
            "planted": MARKER,
        },
        "expected.json": copy.deepcopy(EXPECTED),
        "runtime-pods.json": {"items": [_pod(name) for name in PODS]},
        "claims.json": {"items": [_claim(EXPECTED["claimName"])]},
        "volumes.json": {
            "items": [
                {
                    "metadata": {"name": "pvc-0001"},
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "persistentVolumeReclaimPolicy": "Delete",
                        "hostPath": {"path": "/planted/" + MARKER},
                        "nodeAffinity": {
                            "required": {
                                "nodeSelectorTerms": [
                                    {
                                        "matchExpressions": [
                                            {
                                                "key": "kubernetes.io/hostname",
                                                "operator": "In",
                                                "values": ["node-one"],
                                            }
                                        ]
                                    }
                                ]
                            }
                        },
                    },
                }
            ]
        },
        "capacity-preflight.json": {"exitStatus": 0},
        "capacity-facts.json": {"engine": {"cpus": 8}, "cluster": {}},
        "readiness-samples.txt": "".join(
            f"2026-01-01T00:0{minute}:00Z\t{name}\tRunning\t0\t{since}\t{state}\t{state}\n"
            for minute, since, state in (
                (1, "", "false"),
                (2, "2026-01-01T00:01:30Z", "false"),
                (5, "2026-01-01T00:01:30Z", "true"),
            )
            for name in PODS
        ),
        "events.txt": "".join(
            f"{name}\tUnhealthy\t7\t-\t-\tStartup probe failed: HTTP probe failed "
            "with statuscode: 503\n"
            f"{name}\tUnhealthy\t2\t-\t-\tStartup probe failed: dial tcp: "
            "connection refused\n"
            f"{name}\tPulled\t1\t-\t-\tContainer image already present\n"
            for name in PODS
        ),
    }
    for name in PODS:
        files[f"verify-model.{name}.txt"] = (
            f"{PATH}: OK\nmodel artifact verified: byte count and SHA-256\n"
        )
        files[f"mountinfo.{name}.txt"] = _mount_table()
        files[f"artifact.{name}.txt"] = f"2096 131 {MODEL['sizeBytes']}\n"
        files[f"models.{name}.json"] = {
            "httpStatus": 200,
            "id": ALIAS,
            "meta": {"n_params": 1720574976, "size": 1828474880},
            "chat_template": MARKER,
        }
        files[f"completion.{name}.json"] = {
            "httpStatus": 200,
            "model": ALIAS,
            "finishReason": "stop",
            "promptTokens": 12,
            "completionTokens": 3,
            "content": MARKER,
        }
    return files


def write(directory: Path, files: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        text = content if isinstance(content, str) else json.dumps(content, indent=1)
        (directory / name).write_text(text, encoding="utf-8", newline="\n")
    return directory


def states(record: dict[str, Any]) -> dict[str, str]:
    return {rule["id"]: rule["state"] for rule in record["rules"]}


def first_pod(files: dict[str, Any]) -> dict[str, Any]:
    pod: dict[str, Any] = files["runtime-pods.json"]["items"][0]
    return pod


# --------------------------------------------------------------------------
# The expected identity
# --------------------------------------------------------------------------


def test_the_expected_identity_is_the_two_pin_records() -> None:
    """The release states the model and the runtime image that the pins state."""
    assert EXPECTED["schema"] == EXPECTED_SCHEMA
    assert pin_findings(EXPECTED) == []
    assert EXPECTED["runtimeReplicas"] == 2
    assert EXPECTED["cacheSubPath"] == cache_sub_path(
        MODEL["repository"], MODEL["revision"]
    )
    assert EXPECTED["cacheSubPath"] == (
        "Qwen--Qwen3-1.7B-GGUF/90862c4b9d2787eaed51d12237eafdfe7c5f6077"
    )
    assert f"{EXPECTED['mountPath']}/{MODEL['fileName']}" == PATH


@pytest.mark.parametrize(
    ("section", "member", "value"),
    [
        ("model", "repository", "another/repository"),
        ("model", "revision", "0" * 40),
        ("model", "fileName", "another.gguf"),
        ("model", "sha256", "sha256:" + "0" * 64),
        ("model", "sizeBytes", 1),
        ("runtimeImage", "reference", "example.invalid/runtime@sha256:" + "0" * 64),
    ],
)
def test_a_release_that_states_another_pin_is_a_finding(
    section: str, member: str, value: object
) -> None:
    expected = copy.deepcopy(EXPECTED)
    expected[section][member] = value
    [finding] = pin_findings(expected)
    assert finding.startswith(f"{section}.{member}: ")


def test_an_unknown_release_key_gives_no_expected_identity() -> None:
    with pytest.raises(ExpectedRefused, match="no desired-state release has the key"):
        expected_identity("no-binding/no-workload")


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("  replicaCount: 2\n  resources", "  replicaCount: two\n  resources", "whole"),
        (
            "  replicaCount: 2\n  resources",
            "  replicaCount: true\n  resources",
            "whole",
        ),
        ("    claimName:", "    claim:", "model.cache.claimName is absent"),
        ("  revision:", "  revised:", "model.revision is absent"),
    ],
)
def test_a_values_file_without_a_usable_member_gives_no_expected_identity(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    declared = DESIRED_STATE_RELEASES[0]
    values = REPO_ROOT / declared.directory / "values.generated.yaml"
    text = values.read_text(encoding="utf-8")
    assert old in text
    target = tmp_path / declared.directory / "values.generated.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(text.replace(old, new), encoding="utf-8")
    defaults = tmp_path / declared.platform_defaults
    defaults.parent.mkdir(parents=True)
    defaults.write_bytes((REPO_ROOT / declared.platform_defaults).read_bytes())
    with pytest.raises(ExpectedRefused, match=message):
        expected_identity(root=tmp_path)


def test_the_claim_labels_the_rule_reads_are_the_prerequisite_layers() -> None:
    """The rule names two label values. The prerequisite layer states both.

    It also states the access mode. This reads the module as text: no plan was
    made, and nothing was applied.
    """
    text = PREREQUISITE_MODULE.read_text(encoding="utf-8")
    assert '"app.kubernetes.io/managed-by" = "Terraform"' in text
    assert '"inferops.io/lifecycle"        = "prerequisite"' in text
    assert 'access_modes = ["ReadWriteOnce"]' in text


# --------------------------------------------------------------------------
# A complete collection, and each read that disagrees
# --------------------------------------------------------------------------


def test_two_replicas_that_read_one_verified_artifact_hold_every_rule(
    tmp_path: Path,
) -> None:
    record = build_record(write(tmp_path, complete()))
    assert record["schema"] == RECORD_SCHEMA
    assert record["result"] == "PASSED"
    assert states(record) == {rule.rule_id: HELD for rule in RULES}
    assert [rule["id"] for rule in record["rules"]] == [r.rule_id for r in RULES]
    assert [pod["name"] for pod in record["replicas"]] == list(PODS)
    assert record["placement"] == {"nodes": ["node-one"], "distinctNodes": 1}
    assert record["doesNotEstablish"] == list(DOES_NOT_ESTABLISH)
    assert record["claims"]["volume"]["nodes"] == ["node-one"]
    assert record["claims"]["volume"]["source"] == "hostPath"
    assert record["startupProbeEvents"]["pods"][PODS[0]] == {
        "startupProbeFailures": 9,
        "withStatus503": 7,
    }
    assert record["readinessSamples"]["pods"][PODS[1]] == {
        "samples": 3,
        "runningAndNotReadyBeforeReady": 1,
        "firstSample": "2026-01-01T00:01:00Z",
        "firstReadySample": "2026-01-01T00:05:00Z",
    }
    assert {f["name"] for f in record["files"]} == set(complete())


def _other_image(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["containers"][0]["image"] = "example.invalid/other"


def _other_image_identifier(files: dict[str, Any]) -> None:
    first_pod(files)["status"]["containerStatuses"][0]["imageID"] = (
        "ghcr.io/ggml-org/llama.cpp@sha256:" + "0" * 64
    )


def _other_model_argument(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["containers"][0]["args"][1] = "/models/another.gguf"


def _other_alias(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["containers"][0]["args"][3] = "another-alias"
    files[f"models.{PODS[0]}.json"]["id"] = "another-alias"


def _other_claim(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["volumes"][0]["persistentVolumeClaim"]["claimName"] = "x"


def _second_claim_volume(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["volumes"].append(
        {"name": "extra", "persistentVolumeClaim": {"claimName": "another"}}
    )


def _host_path_volume(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["volumes"].append(
        {"name": "extra", "hostPath": {"path": "/models"}}
    )


def _claim_pending(files: dict[str, Any]) -> None:
    files["claims.json"]["items"][0]["status"]["phase"] = "Pending"


def _claim_of_a_release(files: dict[str, Any]) -> None:
    labels = files["claims.json"]["items"][0]["metadata"]["labels"]
    labels["app.kubernetes.io/managed-by"] = "Helm"


def _claim_with_an_instance_label(files: dict[str, Any]) -> None:
    labels = files["claims.json"]["items"][0]["metadata"]["labels"]
    labels["app.kubernetes.io/instance"] = "inferops"


def _claim_with_a_release_annotation(files: dict[str, Any]) -> None:
    annotations = files["claims.json"]["items"][0]["metadata"]["annotations"]
    annotations["meta.helm.sh/release-name"] = "inferops"


def _claim_without_the_lifecycle(files: dict[str, Any]) -> None:
    del files["claims.json"]["items"][0]["metadata"]["labels"]["inferops.io/lifecycle"]


def _claim_absent(files: dict[str, Any]) -> None:
    files["claims.json"]["items"][0]["metadata"]["name"] = "another-claim"


def _second_claim(files: dict[str, Any]) -> None:
    files["claims.json"]["items"].append(_claim("a-second-claim"))


def _writable_volume(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["volumes"][0]["persistentVolumeClaim"]["readOnly"] = False


def _volume_without_the_mode(files: dict[str, Any]) -> None:
    del first_pod(files)["spec"]["volumes"][0]["persistentVolumeClaim"]["readOnly"]


def _writable_runtime_mount(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["containers"][0]["volumeMounts"][0]["readOnly"] = False


def _writable_verification_mount(files: dict[str, Any]) -> None:
    del first_pod(files)["spec"]["initContainers"][0]["volumeMounts"][0]["readOnly"]


def _writable_in_effect(files: dict[str, Any]) -> None:
    files[f"mountinfo.{PODS[0]}.txt"] = _mount_table(options="rw,relatime")


def _no_mount_line(files: dict[str, Any]) -> None:
    files[f"mountinfo.{PODS[0]}.txt"] = "100 90 0:50 / / rw - overlay overlay rw\n"


def _other_revision(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["containers"][0]["volumeMounts"][0]["subPath"] = (
        "Qwen--Qwen3-1.7B-GGUF/" + "0" * 40
    )


def _verification_at_the_claim_root(files: dict[str, Any]) -> None:
    del first_pod(files)["spec"]["initContainers"][0]["volumeMounts"][0]["subPath"]


def _other_directory(files: dict[str, Any]) -> None:
    files[f"mountinfo.{PODS[0]}.txt"] = _mount_table(root="/pvc-0002/rev")


def _other_inode(files: dict[str, Any]) -> None:
    files[f"artifact.{PODS[0]}.txt"] = f"2096 132 {MODEL['sizeBytes']}\n"


def _other_device(files: dict[str, Any]) -> None:
    files[f"artifact.{PODS[0]}.txt"] = f"2097 131 {MODEL['sizeBytes']}\n"


def _another_size(files: dict[str, Any]) -> None:
    for name in PODS:
        files[f"artifact.{name}.txt"] = "2096 131 1834426015\n"


def _script_without_the_digest(files: dict[str, Any]) -> None:
    first_pod(files)["spec"]["initContainers"][0]["command"][-1] = "exit 0"


def _verification_failed(files: dict[str, Any]) -> None:
    status = first_pod(files)["status"]["initContainerStatuses"][0]
    status["state"]["terminated"]["exitCode"] = 1


def _verification_running(files: dict[str, Any]) -> None:
    first_pod(files)["status"]["initContainerStatuses"][0]["state"] = {"running": {}}


def _log_without_the_checksum_line(files: dict[str, Any]) -> None:
    files[f"verify-model.{PODS[0]}.txt"] = (
        "model artifact verified: byte count and SHA-256\n"
    )


def _log_of_a_weaker_mode(files: dict[str, Any]) -> None:
    files[f"verify-model.{PODS[0]}.txt"] = (
        "model artifact verified: byte count only (model.integrity.verifyOnStart=size)\n"
    )


def _listing_unavailable(files: dict[str, Any]) -> None:
    files[f"models.{PODS[0]}.json"]["httpStatus"] = 503


def _listing_names_another_model(files: dict[str, Any]) -> None:
    files[f"models.{PODS[0]}.json"]["id"] = "another-model"


def _other_metadata(files: dict[str, Any]) -> None:
    files[f"models.{PODS[0]}.json"]["meta"]["size"] = 1


def _completion_refused(files: dict[str, Any]) -> None:
    files[f"completion.{PODS[0]}.json"]["httpStatus"] = 503


def _completion_without_a_token(files: dict[str, Any]) -> None:
    files[f"completion.{PODS[0]}.json"]["completionTokens"] = 0


def _completion_with_no_count(files: dict[str, Any]) -> None:
    del files[f"completion.{PODS[0]}.json"]["completionTokens"]


def _not_ready(files: dict[str, Any]) -> None:
    first_pod(files)["status"]["conditions"][1]["status"] = "False"


def _third_replica(files: dict[str, Any]) -> None:
    files["runtime-pods.json"]["items"].append(_pod("runtime-7d9c-ccccc"))
    for kind, extension in (
        ("verify-model", "txt"),
        ("mountinfo", "txt"),
        ("artifact", "txt"),
        ("models", "json"),
        ("completion", "json"),
    ):
        files[f"{kind}.runtime-7d9c-ccccc.{extension}"] = copy.deepcopy(
            files[f"{kind}.{PODS[0]}.{extension}"]
        )


def _capacity_refused_and_installed_anyway(files: dict[str, Any]) -> None:
    files["capacity-preflight.json"]["exitStatus"] = CAPACITY_REFUSED_EXIT


DEFECTS = [
    (_other_image, "one-runtime-image"),
    (_other_image_identifier, "one-runtime-image"),
    (_other_model_argument, "one-model-argument"),
    (_other_alias, "one-model-argument"),
    (_other_claim, "one-claim"),
    (_second_claim_volume, "one-claim"),
    (_host_path_volume, "one-claim"),
    (_claim_pending, "claim-is-the-prerequisite-claim"),
    (_claim_of_a_release, "claim-is-the-prerequisite-claim"),
    (_claim_with_an_instance_label, "claim-is-the-prerequisite-claim"),
    (_claim_with_a_release_annotation, "claim-is-the-prerequisite-claim"),
    (_claim_without_the_lifecycle, "claim-is-the-prerequisite-claim"),
    (_claim_absent, "claim-is-the-prerequisite-claim"),
    (_second_claim, "no-second-claim"),
    (_writable_volume, "read-only-declared"),
    (_volume_without_the_mode, "read-only-declared"),
    (_writable_runtime_mount, "read-only-declared"),
    (_writable_verification_mount, "read-only-declared"),
    (_writable_in_effect, "read-only-in-effect"),
    (_no_mount_line, "read-only-in-effect"),
    (_other_revision, "revision-scoped-mount"),
    (_verification_at_the_claim_root, "revision-scoped-mount"),
    (_other_directory, "one-directory"),
    (_other_inode, "one-file"),
    (_other_device, "one-file"),
    (_another_size, "one-file"),
    (_script_without_the_digest, "artifact-verified-on-each-start"),
    (_verification_failed, "artifact-verified-on-each-start"),
    (_verification_running, "artifact-verified-on-each-start"),
    (_log_without_the_checksum_line, "artifact-verified-on-each-start"),
    (_log_of_a_weaker_mode, "artifact-verified-on-each-start"),
    (_listing_unavailable, "one-reported-model"),
    (_listing_names_another_model, "one-reported-model"),
    (_other_metadata, "one-reported-model"),
    (_completion_refused, "every-replica-completed"),
    (_completion_without_a_token, "every-replica-completed"),
    (_completion_with_no_count, "every-replica-completed"),
    (_not_ready, "every-replica-ready"),
    (_third_replica, "replica-count"),
    (_capacity_refused_and_installed_anyway, "capacity-preflight-sufficient"),
]


@pytest.mark.parametrize(
    ("plant", "rule"), DEFECTS, ids=[plant.__name__.lstrip("_") for plant, _ in DEFECTS]
)
def test_a_read_that_disagrees_fails_its_rule(
    tmp_path: Path, plant: Any, rule: str
) -> None:
    """One planted defect makes its rule not held, and the result FAILED.

    A defect may also move another rule: a mount table without the cache line
    cannot be compared with the other replica's. So the test names the rule the
    defect must fail, and holds that no rule the defect cannot reach is failed.
    """
    files = complete()
    plant(files)
    record = build_record(write(tmp_path, files))
    assert states(record)[rule] == NOT_HELD
    assert record["result"] == "FAILED"
    failed = {name for name, state in states(record).items() if state == NOT_HELD}
    assert failed == {rule}, failed


def test_every_rule_but_the_optional_one_has_a_defect_that_fails_it() -> None:
    """No rule of the record is held only because nothing ever fails it."""
    failed_by_a_case = {rule for _plant, rule in DEFECTS}
    assert failed_by_a_case == {r.rule_id for r in RULES if r.required}
    assert [r.rule_id for r in RULES if not r.required] == ["not-ready-while-loading"]


# --------------------------------------------------------------------------
# A read that was not made
# --------------------------------------------------------------------------


UNMADE_READS = [
    (f"verify-model.{PODS[1]}.txt", {"artifact-verified-on-each-start"}),
    (f"mountinfo.{PODS[1]}.txt", {"read-only-in-effect", "one-directory"}),
    (f"artifact.{PODS[1]}.txt", {"one-file"}),
    (f"models.{PODS[1]}.json", {"one-reported-model"}),
    (f"completion.{PODS[1]}.json", {"every-replica-completed"}),
    ("claims.json", {"claim-is-the-prerequisite-claim", "no-second-claim"}),
    ("capacity-preflight.json", {"capacity-preflight-sufficient"}),
]


@pytest.mark.parametrize(
    ("name", "rules", "how"),
    [(name, rules, "absent") for name, rules in UNMADE_READS]
    + [
        (name, rules, "unreadable")
        for name, rules in UNMADE_READS
        if name.endswith(".json")
    ],
)
def test_a_read_that_was_not_made_is_not_observed(
    tmp_path: Path, name: str, rules: set[str], how: str
) -> None:
    """An absent file, and a JSON file that does not parse, leave their rules
    not observed. Seven files are removed, and four are made unreadable."""
    files = complete()
    if how == "absent":
        del files[name]
    else:
        files[name] = "{ this is not JSON"
    record = build_record(write(tmp_path, files))
    unobserved = {n for n, state in states(record).items() if state == NOT_OBSERVED}
    assert unobserved == rules
    assert NOT_HELD not in states(record).values()
    assert record["result"] == "INCONCLUSIVE"


def test_an_artifact_read_of_another_shape_is_not_a_value(tmp_path: Path) -> None:
    files = complete()
    files[f"artifact.{PODS[0]}.txt"] = "stat: cannot stat: No such file\n"
    record = build_record(write(tmp_path, files))
    assert record["replicas"][0]["artifact"] == {"state": "unreadable"}
    assert states(record)["one-file"] == NOT_OBSERVED
    assert record["result"] == "INCONCLUSIVE"


def test_one_replica_is_not_compared_with_itself(tmp_path: Path) -> None:
    """With one pod, each comparing rule is not observed, and the count fails."""
    files = complete()
    del files["runtime-pods.json"]["items"][1]
    record = build_record(write(tmp_path, files))
    assert states(record)["replica-count"] == NOT_HELD
    for rule in (
        "one-model-argument",
        "one-directory",
        "one-file",
        "one-reported-model",
    ):
        assert states(record)[rule] == NOT_OBSERVED, rule
    assert record["result"] == "FAILED"


def test_a_pod_listing_that_was_not_read_gives_no_replica(tmp_path: Path) -> None:
    files = complete()
    del files["runtime-pods.json"]
    record = build_record(write(tmp_path, files))
    assert record["podListing"] == "not-read"
    assert record["replicas"] == []
    per_pod = {
        r.rule_id
        for r in RULES
        if r.rule_id
        not in {
            "capacity-preflight-sufficient",
            "claim-is-the-prerequisite-claim",
            "no-second-claim",
        }
    }
    assert {n for n, s in states(record).items() if s == NOT_OBSERVED} == per_pod
    assert record["result"] == "INCONCLUSIVE"


def test_a_refused_preflight_with_no_pod_is_a_refusal(tmp_path: Path) -> None:
    """The preflight refused, and nothing was installed: the result is REFUSED."""
    files = {
        name: content
        for name, content in complete().items()
        if name in {"run.json", "expected.json", "capacity-facts.json"}
    }
    files["capacity-preflight.json"] = {"exitStatus": CAPACITY_REFUSED_EXIT}
    record = build_record(write(tmp_path, files))
    assert record["result"] == "REFUSED"
    assert states(record)["capacity-preflight-sufficient"] == NOT_HELD
    assert record["replicas"] == []


def test_samples_that_caught_no_loading_pod_do_not_change_the_result(
    tmp_path: Path,
) -> None:
    """The one optional rule is not observed, and the result stays PASSED."""
    files = complete()
    files["readiness-samples.txt"] = "".join(
        f"2026-01-01T00:05:00Z\t{name}\tRunning\t0\t-\ttrue\ttrue\n" for name in PODS
    )
    record = build_record(write(tmp_path, files))
    assert states(record)["not-ready-while-loading"] == NOT_OBSERVED
    assert record["result"] == "PASSED"
    del files["readiness-samples.txt"]
    record = build_record(write(tmp_path / "second", files))
    assert record["readinessSamples"] == {"state": "not-read"}
    assert record["result"] == "PASSED"


def test_a_sample_line_of_another_shape_is_counted_and_not_read(tmp_path: Path) -> None:
    files = complete()
    files["readiness-samples.txt"] += "a line with no tab\n"
    record = build_record(write(tmp_path, files))
    assert record["readinessSamples"]["linesNotRead"] == 1
    assert record["readinessSamples"]["lines"] == 7


def test_a_pod_that_is_being_deleted_and_a_pod_of_another_tier_are_not_replicas(
    tmp_path: Path,
) -> None:
    files = complete()
    leaving = _pod("runtime-7d9c-leaving")
    leaving["metadata"]["deletionTimestamp"] = "2026-01-01T00:09:00Z"
    api = _pod("api-5f6b-aaaaa")
    api["metadata"]["labels"]["app.kubernetes.io/component"] = "platform-api"
    files["runtime-pods.json"]["items"] += [leaving, api]
    record = build_record(write(tmp_path, files))
    assert [pod["name"] for pod in record["replicas"]] == list(PODS)
    assert record["result"] == "PASSED"


# --------------------------------------------------------------------------
# The allowlist, and the collection
# --------------------------------------------------------------------------


def test_a_marker_outside_the_allowlist_does_not_reach_the_record(
    tmp_path: Path,
) -> None:
    """The header, a pod's environment and annotations, a claim's annotations,
    a volume's path, the model listing, and the completion each hold the marker."""
    files = complete()
    assert json.dumps(files).count(MARKER) >= 9
    record = build_record(write(tmp_path, files))
    assert MARKER not in record_text(record)


def test_a_pod_name_that_is_not_a_name_reads_no_file(tmp_path: Path) -> None:
    """A name with a path separator is not used to build a file name."""
    files = complete()
    outside = tmp_path / "outside.txt"
    outside.write_text(f"{PATH}: OK\n", encoding="utf-8")
    first_pod(files)["metadata"]["name"] = "../outside"
    (tmp_path / "collection").mkdir()
    record = build_record(write(tmp_path / "collection", files))
    [pod] = [p for p in record["replicas"] if p["name"] == "../outside"]
    assert pod["verification"]["log"] == "not-read"
    assert pod["mountTable"] == {"state": "not-read"}
    assert pod["artifact"] == {"state": "not-read"}


@pytest.mark.parametrize("name", ["run.json", "expected.json"])
def test_a_directory_without_its_two_headers_is_not_a_collection(
    tmp_path: Path, name: str
) -> None:
    files = complete()
    del files[name]
    with pytest.raises(CollectionRefused, match=name):
        build_record(write(tmp_path, files))
    files = complete()
    files[name]["schema"] = "inferops.io/another/v1"
    with pytest.raises(CollectionRefused, match=name):
        build_record(write(tmp_path / "second", files))


def test_the_record_names_each_file_of_the_collection_and_not_itself(
    tmp_path: Path,
) -> None:
    """A CRLF copy of a file has the digest of its LF bytes."""
    directory = write(tmp_path, complete())
    first = build_record(directory)
    (directory / RECORD_FILE).write_text(record_text(first), encoding="utf-8")
    events = directory / "events.txt"
    events.write_bytes(events.read_bytes().replace(b"\n", b"\r\n"))
    second = build_record(directory)
    assert second == first
    assert RECORD_FILE not in {f["name"] for f in second["files"]}


def test_a_committed_record_that_its_collection_does_not_give_is_a_finding(
    tmp_path: Path,
) -> None:
    run = RUNS_PATTERN.replace("*", "one")
    assert committed_runs(tmp_path) == []
    directory = write(tmp_path / run, complete())
    assert committed_runs(tmp_path) == [run]
    assert check_committed_runs(tmp_path) == [
        f"{run}: the directory holds no {RECORD_FILE}"
    ]
    record = directory / RECORD_FILE
    record.write_text(record_text(build_record(directory)), encoding="utf-8")
    assert check_committed_runs(tmp_path) == []
    record.write_text(
        record.read_text(encoding="utf-8").replace('"PASSED"', '"FAILED"'),
        encoding="utf-8",
    )
    [finding] = check_committed_runs(tmp_path)
    assert "is not what the collection gives" in finding
    (directory / "run.json").unlink()
    [finding] = check_committed_runs(tmp_path)
    assert "holds no run.json" in finding


# --------------------------------------------------------------------------
# The command, the tool's sources, and the document
# --------------------------------------------------------------------------


def _command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.runtime_model_cache", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_command_prints_a_record_and_refuses_what_is_not_a_collection(
    tmp_path: Path,
) -> None:
    directory = write(tmp_path / "collection", complete())
    printed = _command(str(directory))
    assert printed.returncode == 0, printed.stderr
    assert json.loads(printed.stdout) == build_record(directory)

    failing = complete()
    _not_ready(failing)
    printed = _command(str(write(tmp_path / "failing", failing)))
    assert printed.returncode == 0, "a record of a failed rule is a record"
    assert json.loads(printed.stdout)["result"] == "FAILED"

    (tmp_path / "empty").mkdir()
    refused = _command(str(tmp_path / "empty"))
    assert refused.returncode == 1
    assert refused.stderr.startswith("REFUSED  not-a-collection: ")
    assert refused.stdout == ""


def test_the_command_prints_the_expected_identity_and_checks_the_committed_runs() -> (
    None
):
    printed = _command("--expected")
    assert printed.returncode == 0, printed.stderr
    assert json.loads(printed.stdout) == EXPECTED
    checked = _command("--check")
    assert checked.returncode == 0, checked.stderr
    assert checked.stdout.startswith(
        f"PASSED: {len(committed_runs())} committed run(s)"
    )
    for arguments in ([], ["--expected", "--check"], ["--key", "a/b", "--check"]):
        assert _command(*arguments).returncode == 2, arguments
    unknown = _command("--expected", "--key", "no-binding/no-workload")
    assert unknown.returncode == 1
    assert unknown.stderr.startswith("REFUSED  no-expected-identity: ")


def test_the_tool_reads_files_and_runs_nothing() -> None:
    """Its three source files import no module that runs a process or opens a
    connection, call nothing that writes a file, and do not name the controller."""
    sources = sorted(TOOL_DIRECTORY.glob("*.py"))
    assert [path.name for path in sources] == ["__init__.py", "__main__.py", "core.py"]
    forbidden = {"subprocess", "os", "socket", "shutil", "urllib", "http", "requests"}
    writers = {"write_text", "write_bytes", "unlink", "mkdir", "rename", "open"}
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert "argo" not in text.lower(), path.name
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                names = set()
            assert not names & forbidden, (path.name, names)
            if isinstance(node, ast.Call):
                called = node.func
                name = (
                    called.attr
                    if isinstance(called, ast.Attribute)
                    else getattr(called, "id", "")
                )
                assert name not in writers, (path.name, name)


def test_the_document_publishes_the_record() -> None:
    text = " ".join(DOCUMENT_PATH.read_text(encoding="utf-8").split())
    for identifier in (RECORD_SCHEMA, EXPECTED_SCHEMA, COLLECTION_SCHEMA):
        assert f"`{identifier}`" in text, identifier
    for rule in RULES:
        assert f"`{rule.rule_id}`" in text, rule.rule_id
        assert rule.statement in text, rule.rule_id
    for state in (*RESULT_STATES, HELD, NOT_HELD, NOT_OBSERVED):
        assert f"`{state}`" in text, state
    for statement in DOES_NOT_ESTABLISH:
        assert statement in text, statement
    assert len(DOES_NOT_ESTABLISH) == 9
    assert len(RULES) == 17


# --------------------------------------------------------------------------
# The committed runs
# --------------------------------------------------------------------------


def test_each_committed_record_is_what_its_collection_gives() -> None:
    """The tool builds each committed record again from the committed files."""
    assert check_committed_runs() == []
    for run in committed_runs():
        directory = REPO_ROOT / run
        record = json.loads((directory / RECORD_FILE).read_text(encoding="utf-8"))
        assert record["schema"] == RECORD_SCHEMA
        assert record["result"] in RESULT_STATES
        assert pin_findings(record["expected"]) == [], run
