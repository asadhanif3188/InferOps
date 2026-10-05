"""The reconciliation state a GitOps controller reported, as an evidence record.

The Application procedure's ``observe`` operation writes a bounded number of
reads into one directory. ``tools.reconciliation_evidence`` reads that directory
and returns one record. This suite writes such directories by hand and holds the
tool to them.

Five things are held:

* a field that was not reported stays not reported: an absent field, a null, a
  value of another type, an Application without a status, a read that did not
  answer, an absent Application, and an answer that is not one JSON object each
  give a state other than ``reported``, carry no value, and make ``settled``
  false with a reason;
* a transition is a difference between two consecutive samples, a reported
  value is not carried across a sample that did not report it, and a collection
  that stopped early is not complete;
* the record is built from an allowlist: a marker planted in every other part
  of an Application and of an object's labels does not reach it, and a message
  is cut and redacted;
* a sample is compared with the provenance of the desired-state release at the
  commit the sample reports, and a comparison that could not be made is
  recorded as not compared;
* the tool reads files and Git objects only, and the document publishes the
  record's fields, its states, and the boundary for a manual change.

What this establishes about a cluster: nothing. Every directory here is written
by the suite. The stub suite of the procedure executes ``observe`` against stub
tools and gives its directory to this tool. Five committed records are what the
tool built from collections on a cluster. One test reads them as files, and it
observes no cluster.

The comparison tests run Git and read the commit that ``HEAD`` names.
"""

from __future__ import annotations

import ast
import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain.release import is_credential_shaped
from tools.desired_state_provenance import resolve
from tools.gitops_desired_state import DESIRED_STATE_RELEASES
from tools.reconciliation_evidence import (
    APPLICATION_STATES,
    DOES_NOT_ESTABLISH,
    FIELD_STATES,
    OPTIONAL_FIELDS,
    RECORD_SCHEMA,
    REPOSITORY,
    REQUIRED_FIELDS,
    TRANSITION_FIELDS,
    CollectionRefused,
    build_record,
    diagnostic_text,
    read_collection,
    settled,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
DECLARED = DESIRED_STATE_RELEASES[0]
TOOL_DIRECTORY = REPO_ROOT / "tools" / "reconciliation_evidence"
DOCUMENT_PATH = REPO_ROOT / "docs" / "environment" / "reconciliation-evidence.md"
APPLICATION_PATH = (
    REPO_ROOT / "infra" / "argocd" / "local-docker-desktop-support-assistant.yaml"
)
RUN_RECORD_PREFIX = "v2-s3-003-pr2-reconciliation-observation-"

# The committed records of the run of 2026-10-05, restated: the samples, the
# reads of the Application by state, the settled samples, and whether the
# collection is complete. A value read from a record would agree with the record
# by construction.
RUN_RECORDS: dict[str, tuple[int, dict[str, int], int, bool]] = {
    "attempt-1-apply": (80, {"absent": 5, "reported": 18, "not-taken": 57}, 0, False),
    "attempt-1-after-abort": (3, {"reported": 3}, 0, True),
    "run-2-apply": (80, {"absent": 6, "reported": 74}, 59, True),
    "run-2-steady": (5, {"reported": 5}, 5, True),
    "run-2-remove": (40, {"absent": 30, "reported": 10}, 5, True),
}
RUN_RESOLVED_REVISION = "40452957d8f602357ecc512dc643cb820db57202"

REVISION = "1234567890abcdef1234567890abcdef12345678"
OTHER_REVISION = "abcdef1234567890abcdef1234567890abcdef12"
MARKER = "planted-marker-7f3a"

#: Any spelling of the controller's name, as the bootstrap suite matches it.
CONTROLLER_REFERENCE = re.compile(r"argoproj|argo[-_. ]?cd", flags=re.IGNORECASE)

#: The cells the boundary table may hold in its enforcement column.
ENFORCEMENTS = ("tested", "observed on a run", "review", "not enforced")

#: The rules of the boundary for a manual change, in the order the document
#: states them.
BOUNDARY_RULES = (
    "change-through-git",
    "experiment-mutation-is-frozen-first",
    "break-glass-removes-the-application-first",
    "break-glass-is-recorded",
    "manual-change-returns-to-git",
    "controller-state-is-not-edited",
)


def application(revision: str = REVISION) -> dict[str, Any]:
    """An Application as the controller reports one after a succeeded sync."""
    return {
        "apiVersion": "example.invalid/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": "local-docker-desktop-support-assistant",
            "annotations": {"note": MARKER},
            "managedFields": [{"manager": MARKER}],
        },
        "spec": {
            "project": MARKER,
            "source": {
                "repoURL": REPOSITORY,
                "targetRevision": "main",
                "path": "charts/inferops-llm",
                "helm": {
                    "valueFiles": [f"/{DECLARED.directory}/values.generated.yaml"],
                    "valuesObject": {"api": {"image": {"repository": MARKER}}},
                    "parameters": [{"name": "api.image.digest", "value": MARKER}],
                },
            },
            "syncPolicy": {"automated": {"selfHeal": True, "prune": False}},
        },
        "status": {
            "sync": {"status": "Synced", "revision": revision},
            "health": {"status": "Healthy"},
            "reconciledAt": "2026-01-01T00:00:05Z",
            "operationState": {
                "phase": "Succeeded",
                "message": "successfully synced (all tasks run)",
                "startedAt": "2026-01-01T00:00:01Z",
                "finishedAt": "2026-01-01T00:00:03Z",
                "operation": {"initiatedBy": {"automated": True}},
                "syncResult": {"revision": revision, "resources": [{"name": MARKER}]},
            },
            "history": [
                {"id": 0, "revision": OTHER_REVISION, "deployedAt": "2025-12-31"},
                {"id": 1, "revision": revision, "deployedAt": "2026-01-01T00:00:03Z"},
            ],
            "resources": [{"kind": "Deployment", "name": MARKER}],
            "summary": {"images": [MARKER]},
        },
    }


def without(document: dict[str, Any], *path: str) -> dict[str, Any]:
    changed = copy.deepcopy(document)
    current = changed
    for key in path[:-1]:
        current = current[key]
    del current[path[-1]]
    return changed


def with_value(document: dict[str, Any], value: object, *path: str) -> dict[str, Any]:
    changed = copy.deepcopy(document)
    current = changed
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
    return changed


UNANSWERED = "unanswered"
ABSENT = "absent"
DEFAULT_OBJECTS = (("Deployment", "inferops-inferops-llm", {"a": "b"}),)


def write_collection(
    directory: Path,
    samples: list[Any],
    *,
    objects: Any = DEFAULT_OBJECTS,
    requested: int | None = None,
    ended: bool = True,
) -> Path:
    """One directory as ``observe`` writes it. Each sample is an Application
    document, raw text, ``ABSENT``, or ``UNANSWERED``."""
    directory.mkdir()
    count = len(samples) if requested is None else requested
    (directory / "collection.meta").write_text(
        "provider=docker-desktop\nserverVersion=v1.34.3\n"
        f"repositoryRevision={REVISION}\nprocedureSha256={'a' * 64}\n"
        f"librarySha256={'b' * 64}\napplication=local-docker-desktop-support-assistant\n"
        "applicationNamespace=controller\nworkloadNamespace=inferops-release\n"
        f"requestedSamples={count}\nintervalSeconds=2\n",
        encoding="utf-8",
    )
    for index, sample in enumerate(samples, start=1):
        stem = directory / f"sample-{index:03d}"
        read = "answered"
        if sample == UNANSWERED:
            read = "unanswered"
        elif sample == ABSENT:
            (stem.parent / f"{stem.name}.application.json").write_text("", "utf-8")
        elif isinstance(sample, str):
            (stem.parent / f"{stem.name}.application.json").write_text(sample, "utf-8")
        else:
            (stem.parent / f"{stem.name}.application.json").write_text(
                json.dumps(sample), "utf-8"
            )
        objects_read = "answered"
        if objects == UNANSWERED:
            objects_read = "unanswered"
        else:
            lines = [
                f"{kind}\t{name}\t{labels if isinstance(labels, str) else json.dumps(labels)}"
                for kind, name, labels in objects
            ]
            (stem.parent / f"{stem.name}.objects.txt").write_text(
                "".join(line + "\n" for line in lines), "utf-8"
            )
        (stem.parent / f"{stem.name}.meta").write_text(
            f"observedAt=2026-01-01T00:00:{index:02d}Z\n"
            f"applicationRead={read}\nobjectsRead={objects_read}\n",
            "utf-8",
        )
    if ended:
        (directory / "collection.end").write_text(
            f"completedSamples={count}\n", "utf-8"
        )
    return directory


def record_of(tmp_path: Path, samples: list[Any], **options: Any) -> dict[str, Any]:
    return build_record(write_collection(tmp_path / "observation", samples, **options))


def head_revision() -> str:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not on PATH")
    result = subprocess.run(
        [git, "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        pytest.skip("this checkout has no HEAD commit")
    return result.stdout.strip()


# --------------------------------------------------------------------------
# A complete report
# --------------------------------------------------------------------------


def test_a_complete_report_gives_every_required_field_and_is_settled(
    tmp_path: Path,
) -> None:
    record = record_of(tmp_path, [application()])
    (sample,) = record["samples"]
    assert record["schema"] == RECORD_SCHEMA
    assert sample["applicationRead"] == "reported"
    assert sample["notReported"] == []
    for name in REQUIRED_FIELDS:
        assert sample["fields"][name]["state"] == "reported", name
    assert sample["fields"]["resolvedRevision"]["value"] == REVISION
    assert sample["fields"]["historyId"] == {"state": "reported", "value": 1}
    assert sample["fields"]["operationAutomated"] == {
        "state": "reported",
        "value": True,
    }
    assert sample["settled"] == {"value": True, "reasons": []}
    assert record["summary"]["samplesSettled"] == 1
    assert record["collection"]["complete"] is True
    assert record["doesNotEstablish"] == list(DOES_NOT_ESTABLISH)


def test_the_field_tables_do_not_overlap_and_transitions_track_known_fields() -> None:
    assert not set(REQUIRED_FIELDS) & set(OPTIONAL_FIELDS)
    assert set(TRANSITION_FIELDS) <= {*REQUIRED_FIELDS, *OPTIONAL_FIELDS, "historyId"}
    assert FIELD_STATES == ("reported", "missing", "malformed", "not-collected")
    assert set(APPLICATION_STATES) == {
        "reported",
        "absent",
        "unanswered",
        "unreadable",
        "not-taken",
    }


# --------------------------------------------------------------------------
# Missing stays missing
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", tuple(REQUIRED_FIELDS))
@pytest.mark.parametrize(
    ("change", "state"),
    (
        ("absent", "missing"),
        ("null", "missing"),
        ("empty", "malformed"),
        ("number", "malformed"),
        ("mapping", "malformed"),
    ),
)
def test_a_required_field_that_is_not_reported_is_not_a_value(
    tmp_path: Path, name: str, change: str, state: str
) -> None:
    path = REQUIRED_FIELDS[name][0]
    document = application()
    if change == "absent":
        document = without(document, *path)
    else:
        value = {"null": None, "empty": "", "number": 7, "mapping": {"x": "Healthy"}}
        document = with_value(document, value[change], *path)
    record = record_of(tmp_path, [document])
    (sample,) = record["samples"]
    assert sample["fields"][name] == {"state": state}
    assert "value" not in sample["fields"][name]
    assert sample["notReported"] == [name]
    assert sample["settled"]["value"] is False
    assert f"{name} is {state}" in sample["settled"]["reasons"]
    assert record["summary"]["samplesWithEveryRequiredField"] == 0
    assert record["summary"]["samplesSettled"] == 0


@pytest.mark.parametrize(
    "path",
    (
        ("status",),
        ("status", "sync"),
        ("status", "health"),
        ("status", "operationState"),
        ("status", "operationState", "syncResult"),
    ),
    ids="/".join,
)
def test_a_missing_parent_leaves_each_field_below_it_missing(
    tmp_path: Path, path: tuple[str, ...]
) -> None:
    record = record_of(tmp_path, [without(application(), *path)])
    (sample,) = record["samples"]
    below = [
        name
        for name, (field_path, _) in REQUIRED_FIELDS.items()
        if field_path[: len(path)] == path
    ]
    assert below
    assert sample["notReported"] == below
    for name in below:
        assert sample["fields"][name] == {"state": "missing"}
    assert sample["settled"]["value"] is False


def test_an_application_with_no_status_reports_no_state(tmp_path: Path) -> None:
    """A new Application, before the controller first wrote to it."""
    record = record_of(tmp_path, [without(application(), "status")])
    (sample,) = record["samples"]
    assert sample["applicationRead"] == "reported"
    assert sample["notReported"] == list(REQUIRED_FIELDS)
    assert sample["fields"]["historyId"] == {"state": "missing"}
    assert sample["fields"]["followedRevision"] == {
        "state": "reported",
        "value": "main",
    }
    assert sample["operationMessage"] == {"state": "missing"}
    assert sample["consistency"]["state"] == "not-compared"


@pytest.mark.parametrize(
    ("sample", "state"),
    (
        (UNANSWERED, "unanswered"),
        (ABSENT, "absent"),
        ("Error from server (ServiceUnavailable)", "unreadable"),
        ('["Synced", "Healthy"]', "unreadable"),
        ('"Healthy"', "unreadable"),
    ),
    ids=("unanswered", "absent", "not-json", "a-list", "a-string"),
)
def test_a_read_that_gave_no_object_reports_no_field(
    tmp_path: Path, sample: str, state: str
) -> None:
    record = record_of(tmp_path, [sample])
    (found,) = record["samples"]
    assert found["applicationRead"] == state
    for name, field in found["fields"].items():
        assert field == {"state": "not-collected"}, name
    assert found["notReported"] == list(REQUIRED_FIELDS)
    assert found["settled"] == {
        "value": False,
        "reasons": [f"the Application read is {state}"],
    }
    assert found["consistency"] == {
        "state": "not-compared",
        "reason": f"the Application read is {state}",
    }
    assert record["summary"]["applicationReads"][state] == 1
    assert record["summary"]["samplesSettled"] == 0
    assert record["summary"]["resolvedRevisions"] == []


def test_an_answered_read_without_its_file_is_unanswered(tmp_path: Path) -> None:
    directory = write_collection(tmp_path / "observation", [application()])
    (directory / "sample-001.application.json").unlink()
    (directory / "sample-001.objects.txt").unlink()
    (sample,) = build_record(directory)["samples"]
    assert sample["applicationRead"] == "unanswered"
    assert sample["objectsRead"] == "unanswered"


@pytest.mark.parametrize(
    ("path", "value", "reason"),
    (
        (
            ("status", "sync", "status"),
            "OutOfSync",
            "syncStatus is reported as OutOfSync, and not Synced",
        ),
        (
            ("status", "sync", "status"),
            "Unknown",
            "syncStatus is reported as Unknown, and not Synced",
        ),
        (
            ("status", "health", "status"),
            "Progressing",
            "healthStatus is reported as Progressing, and not Healthy",
        ),
        (
            ("status", "health", "status"),
            "Missing",
            "healthStatus is reported as Missing, and not Healthy",
        ),
        (
            ("status", "operationState", "phase"),
            "Running",
            "operationPhase is reported as Running, and not Succeeded",
        ),
        (
            ("status", "operationState", "syncResult", "revision"),
            OTHER_REVISION,
            "operationRevision is not the resolved revision",
        ),
        (
            ("status", "sync", "revision"),
            "main",
            "resolvedRevision is not a full commit identifier",
        ),
    ),
)
def test_a_reported_state_that_is_not_the_settled_one_is_not_settled(
    tmp_path: Path, path: tuple[str, ...], value: str, reason: str
) -> None:
    record = record_of(tmp_path, [with_value(application(), value, *path)])
    (sample,) = record["samples"]
    assert sample["notReported"] == []
    assert sample["settled"]["value"] is False
    assert reason in sample["settled"]["reasons"]


@pytest.mark.parametrize("value", ("2026-01-01T00:00:09Z", 7, ""))
def test_an_application_that_is_being_deleted_is_not_settled(
    tmp_path: Path, value: object
) -> None:
    """It keeps its last sync state and health state while it is deleted. A
    deletion timestamp of another type is not read as no deletion."""
    document = with_value(application(), value, "metadata", "deletionTimestamp")
    (sample,) = record_of(tmp_path, [document])["samples"]
    assert sample["notReported"] == []
    assert sample["settled"] == {
        "value": False,
        "reasons": ["the Application has a deletion timestamp"],
    }


def test_settled_is_never_true_for_a_sample_that_lacks_a_required_field(
    tmp_path: Path,
) -> None:
    """Every subset of absent required fields, with every other field settled."""
    names = tuple(REQUIRED_FIELDS)
    documents = []
    for mask in range(1, 2 ** len(names)):
        document = application()
        for bit, name in enumerate(names):
            if mask & (1 << bit):
                document = with_value(document, None, *REQUIRED_FIELDS[name][0])
        documents.append(document)
    _, samples = read_collection(write_collection(tmp_path / "o", documents))
    assert len(samples) == 31
    assert not any(settled(sample)[0] for sample in samples)


# --------------------------------------------------------------------------
# Transitions and the collection
# --------------------------------------------------------------------------


def test_equal_samples_give_no_transition(tmp_path: Path) -> None:
    record = record_of(tmp_path, [application(), application(), application()])
    assert record["transitions"] == []


def test_a_change_between_two_samples_is_one_transition_for_each_field(
    tmp_path: Path,
) -> None:
    drifted = with_value(application(), "OutOfSync", "status", "sync", "status")
    record = record_of(tmp_path, [application(), drifted, application()])
    assert [
        (
            t["field"],
            t["fromSample"],
            t["toSample"],
            t["from"]["value"],
            t["to"]["value"],
        )
        for t in record["transitions"]
    ] == [
        ("syncStatus", 1, 2, "Synced", "OutOfSync"),
        ("syncStatus", 2, 3, "OutOfSync", "Synced"),
    ]
    first = record["transitions"][0]
    assert first["fromObservedAt"] == {
        "state": "reported",
        "value": "2026-01-01T00:00:01Z",
    }
    assert first["toObservedAt"] == {
        "state": "reported",
        "value": "2026-01-01T00:00:02Z",
    }


def test_a_value_is_not_carried_across_a_read_that_did_not_answer(
    tmp_path: Path,
) -> None:
    record = record_of(tmp_path, [application(), UNANSWERED, application()])
    middle = record["samples"][1]
    assert middle["fields"]["healthStatus"] == {"state": "not-collected"}
    assert middle["settled"]["value"] is False
    to_middle = [t for t in record["transitions"] if t["toSample"] == 2]
    assert {t["field"] for t in to_middle} == {"applicationRead", *TRANSITION_FIELDS}
    for transition in to_middle:
        if transition["field"] == "applicationRead":
            assert transition["to"] == {"state": "reported", "value": "unanswered"}
        else:
            assert transition["to"] == {"state": "not-collected"}
    assert record["summary"]["samplesSettled"] == 2


def test_a_new_revision_and_a_new_operation_are_transitions(tmp_path: Path) -> None:
    later = application(OTHER_REVISION)
    later["status"]["history"].append(
        {"id": 2, "revision": OTHER_REVISION, "deployedAt": "2026-01-01T00:01:00Z"}
    )
    later["status"]["operationState"]["startedAt"] = "2026-01-01T00:00:58Z"
    later["status"]["operationState"]["finishedAt"] = "2026-01-01T00:01:00Z"
    record = record_of(tmp_path, [application(), later])
    assert [t["field"] for t in record["transitions"]] == [
        "resolvedRevision",
        "operationRevision",
        "operationStartedAt",
        "operationFinishedAt",
        "historyId",
    ]
    assert record["summary"]["resolvedRevisions"] == sorted([REVISION, OTHER_REVISION])


def test_a_collection_that_stopped_early_is_not_complete(tmp_path: Path) -> None:
    record = record_of(tmp_path, [application()], requested=3, ended=False)
    assert record["collection"]["complete"] is False
    assert record["collection"]["requestedSamples"] == 3
    assert record["collection"]["completedSamples"] == {"state": "missing"}
    assert [s["applicationRead"] for s in record["samples"]] == [
        "reported",
        "not-taken",
        "not-taken",
    ]
    assert record["samples"][1]["observedAt"] == {"state": "missing"}
    # A sample that was not taken is not an observation: nothing changed "to" it.
    assert record["transitions"] == []
    assert record["samples"][1]["settled"]["value"] is False
    assert record["summary"]["applicationReads"]["not-taken"] == 2


def test_a_sample_beyond_the_requested_count_is_still_read(tmp_path: Path) -> None:
    record = record_of(tmp_path, [application(), application()], requested=1)
    assert len(record["samples"]) == 2
    assert record["collection"]["complete"] is True


@pytest.mark.parametrize(
    "header",
    (
        "",
        "requestedSamples=\n",
        "requestedSamples=many\n",
        "requestedSamples=0\n",
        "requestedSamples=1000\n",
        "requestedSamples=-1\n",
    ),
)
def test_a_directory_that_is_not_a_collection_is_refused(
    tmp_path: Path, header: str
) -> None:
    directory = tmp_path / "observation"
    directory.mkdir()
    with pytest.raises(CollectionRefused):
        build_record(directory)
    (directory / "collection.meta").write_text(header, "utf-8")
    with pytest.raises(CollectionRefused):
        build_record(directory)


def test_a_header_value_that_was_not_written_is_missing(tmp_path: Path) -> None:
    directory = write_collection(tmp_path / "observation", [application()])
    (directory / "collection.meta").write_text("requestedSamples=1\n", "utf-8")
    collection = build_record(directory)["collection"]
    for name in ("provider", "serverVersion", "repositoryRevision", "intervalSeconds"):
        assert collection[name] == {"state": "missing"}, name


# --------------------------------------------------------------------------
# The allowlist and the diagnostics
# --------------------------------------------------------------------------


def test_no_part_of_an_object_outside_the_allowlist_reaches_the_record(
    tmp_path: Path,
) -> None:
    objects = (
        ("Deployment", "inferops-inferops-llm", {"other-label": MARKER}),
        ("Pod", "inferops-runtime-0", {"pod-template-hash": MARKER}),
    )
    record = record_of(tmp_path, [application()], objects=objects)
    assert MARKER in json.dumps(application())
    assert MARKER not in json.dumps(record)


def test_a_condition_is_recorded_by_type_with_a_bounded_message(tmp_path: Path) -> None:
    document = application()
    document["status"]["conditions"] = [
        {"type": "ComparisonError", "message": "x" * 1000, "lastTransitionTime": "t"},
        {"type": "SyncError"},
        "not a mapping",
        *({"type": f"Extra{n}", "message": "m"} for n in range(20)),
    ]
    (sample,) = record_of(tmp_path, [document])["samples"]
    assert len(sample["conditions"]) == 10
    first, second = sample["conditions"][:2]
    assert first["type"] == {"state": "reported", "value": "ComparisonError"}
    assert len(first["message"]["value"]) == 240
    assert first["message"]["value"].endswith("...")
    assert second["message"] == {"state": "missing"}
    assert second["lastTransitionTime"] == {"state": "missing"}
    assert sample["operationMessage"] == {
        "state": "reported",
        "value": "successfully synced (all tasks run)",
    }


def test_a_message_is_one_line_without_an_address_user_or_a_known_credential() -> None:
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    assert is_credential_shaped(token)
    text = diagnostic_text(
        f"fetch failed\n  for https://user:pass@example.invalid/r.git\twith {token}"
    )
    assert text == (
        "fetch failed for https://<redacted>@example.invalid/r.git with <redacted>"
    )
    assert diagnostic_text("short") == "short"
    assert len(diagnostic_text("y" * 240)) == 240
    assert len(diagnostic_text("y" * 241)) == 240


@pytest.mark.parametrize(
    ("labels", "state"),
    (
        ("", "missing"),
        ("not json", "malformed"),
        ('["helm.sh/chart"]', "malformed"),
        ('{"helm.sh/chart": 3}', "malformed"),
        ('{"unrelated": "x"}', "missing"),
    ),
)
def test_a_label_that_was_not_read_is_not_a_label(
    tmp_path: Path, labels: str, state: str
) -> None:
    objects = (("Service", "inferops-inferops-llm", labels),)
    record = record_of(tmp_path, [application()], objects=objects)
    (sample,) = record["samples"]
    assert sample["objectCount"] == 1
    (entry,) = record["objectSets"][sample["objectSet"]]
    assert entry["kind"] == "Service"
    assert entry["labels"]["helm.sh/chart"] == {"state": state}


def test_an_object_read_that_did_not_answer_holds_no_object(tmp_path: Path) -> None:
    record = record_of(tmp_path, [application()], objects=UNANSWERED)
    (sample,) = record["samples"]
    assert sample["objectsRead"] == "unanswered"
    assert sample["objectSet"] is None
    assert sample["objectCount"] == 0
    assert record["objectSets"] == {}


def test_each_distinct_list_of_objects_is_held_once(tmp_path: Path) -> None:
    """Samples that read the same objects name one list. A read that returned
    no object names the empty list, which is not the same as no read."""
    record = record_of(tmp_path, [application(), application(), application()])
    names = {sample["objectSet"] for sample in record["samples"]}
    assert len(names) == 1
    assert list(record["objectSets"]) == list(names)
    (entries,) = record["objectSets"].values()
    assert [entry["name"] for entry in entries] == ["inferops-inferops-llm"]

    (tmp_path / "second").mkdir()
    empty = record_of(tmp_path / "second", [application()], objects=())
    (sample,) = empty["samples"]
    assert sample["objectsRead"] == "collected"
    assert empty["objectSets"] == {sample["objectSet"]: []}


# --------------------------------------------------------------------------
# A sample beside the provenance at the commit it reports
# --------------------------------------------------------------------------


def committed_source() -> dict[str, Any]:
    return yaml.safe_load(APPLICATION_PATH.read_text(encoding="utf-8"))["spec"][
        "source"
    ]


def test_the_restated_repository_is_the_committed_applications() -> None:
    assert committed_source()["repoURL"] == REPOSITORY


def reported_at_head(tmp_path: Path, **changes: Any) -> dict[str, Any]:
    """One sample that reports ``HEAD``, with the committed source and the
    labels the provenance at ``HEAD`` derives."""
    revision = head_revision()
    provenance = resolve(revision, DECLARED, REPO_ROOT)
    document = application(revision)
    source = committed_source()
    document["spec"]["source"]["helm"]["valueFiles"] = source["helm"]["valueFiles"]
    document["spec"]["source"]["path"] = source["path"]
    for path, value in changes.get("application", {}).items():
        document = with_value(document, value, *path)
    labels = {**provenance.workload_labels(), **changes.get("labels", {})}
    objects = changes.get(
        "objects",
        (("Deployment", "inferops-inferops-llm", labels), ("Pod", "p-0", labels)),
    )
    directory = write_collection(tmp_path / "observation", [document], objects=objects)
    record = build_record(directory, changes.get("declared", DECLARED), REPO_ROOT)
    return {"record": record, "provenance": provenance, "revision": revision}


def test_a_sample_that_agrees_with_the_commit_it_reports_has_no_finding(
    tmp_path: Path,
) -> None:
    found = reported_at_head(tmp_path)
    consistency = found["record"]["samples"][0]["consistency"]
    assert consistency == {
        "state": "compared",
        "releaseId": found["provenance"].release_id,
        "revisionFindings": [],
        "revisionsNotReported": [],
        "source": {"state": "compared", "findings": []},
        "labels": {"state": "compared", "objects": 2, "findings": []},
    }


def test_each_disagreement_with_the_reported_commit_is_a_finding(
    tmp_path: Path,
) -> None:
    found = reported_at_head(
        tmp_path,
        application={
            ("status", "operationState", "syncResult", "revision"): OTHER_REVISION,
            ("spec", "source", "helm", "valueFiles"): ["/a.yaml", "/b.yaml"],
        },
        labels={"inferops.io/workload": "another-workload"},
    )
    consistency = found["record"]["samples"][0]["consistency"]
    assert [f["rule"] for f in consistency["revisionFindings"]] == [
        "observed-revision-mismatch"
    ]
    assert consistency["revisionFindings"][0]["subject"] == "operationRevision"
    assert [f["rule"] for f in consistency["source"]["findings"]] == [
        "source-not-the-release"
    ]
    assert [f["subject"] for f in consistency["labels"]["findings"]] == [
        "Deployment/inferops-inferops-llm: inferops.io/workload",
        "Pod/p-0: inferops.io/workload",
    ]


def test_a_comparison_that_could_not_be_made_is_not_compared(tmp_path: Path) -> None:
    found = reported_at_head(
        tmp_path,
        application={
            ("status", "operationState", "syncResult"): None,
            ("status", "history"): None,
            ("spec", "source", "repoURL"): None,
        },
        objects=UNANSWERED,
    )
    consistency = found["record"]["samples"][0]["consistency"]
    assert consistency["state"] == "compared"
    assert consistency["revisionFindings"] == []
    assert consistency["revisionsNotReported"] == [
        "operationRevision",
        "historyRevision",
    ]
    assert consistency["source"] == {
        "state": "not-compared",
        "reason": "not reported: repository is missing",
    }
    assert consistency["labels"] == {
        "state": "not-compared",
        "reason": "the object read is unanswered",
    }


def test_no_object_is_not_read_as_objects_that_carry_the_labels(
    tmp_path: Path,
) -> None:
    found = reported_at_head(tmp_path, objects=())
    assert found["record"]["samples"][0]["consistency"]["labels"] == {
        "state": "not-compared",
        "reason": "the object read returned no object",
    }


def test_an_object_without_labels_is_three_findings(tmp_path: Path) -> None:
    found = reported_at_head(tmp_path, objects=(("ConfigMap", "c", ""),))
    labels = found["record"]["samples"][0]["consistency"]["labels"]
    assert len(labels["findings"]) == 3


def test_a_commit_the_clone_does_not_hold_is_not_compared(tmp_path: Path) -> None:
    head_revision()
    directory = write_collection(tmp_path / "observation", [application()])
    (sample,) = build_record(directory, DECLARED, REPO_ROOT)["samples"]
    assert sample["consistency"] == {
        "state": "not-compared",
        "reason": "the provenance at the reported commit was refused: "
        "revision-not-readable",
    }
    (sample,) = build_record(directory)["samples"]
    assert sample["consistency"] == {
        "state": "not-compared",
        "reason": "no provenance was asked for",
    }


def test_a_reported_branch_name_is_refused_as_a_revision(tmp_path: Path) -> None:
    document = with_value(application(), "main", "status", "sync", "revision")
    directory = write_collection(tmp_path / "observation", [document])
    (sample,) = build_record(directory, DECLARED, REPO_ROOT)["samples"]
    assert sample["consistency"]["reason"].endswith("revision-not-immutable")


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def run_command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.reconciliation_evidence", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_the_command_prints_a_record_of_reads_that_did_not_answer(
    tmp_path: Path,
) -> None:
    directory = write_collection(tmp_path / "observation", [UNANSWERED, UNANSWERED])
    completed = run_command(str(directory), "--no-provenance")
    assert completed.returncode == 0, completed.stderr
    record = json.loads(completed.stdout)
    assert record["summary"]["applicationReads"]["unanswered"] == 2
    assert record["summary"]["samplesSettled"] == 0


def test_the_command_refuses_a_directory_that_is_not_a_collection(
    tmp_path: Path,
) -> None:
    completed = run_command(str(tmp_path))
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "not-a-collection" in completed.stderr


@pytest.mark.parametrize(
    "arguments",
    ((), ("--key", "no/such-release"), ("--key", "a/b", "--no-provenance")),
)
def test_the_command_needs_a_directory_and_a_known_key(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    directory = () if not arguments else (str(tmp_path),)
    completed = run_command(*directory, *arguments)
    assert completed.returncode == 2
    assert completed.stdout == ""


# --------------------------------------------------------------------------
# The tool, as text
# --------------------------------------------------------------------------


def tool_sources() -> list[Path]:
    return sorted(TOOL_DIRECTORY.glob("*.py"))


def test_the_tool_does_not_name_the_controller() -> None:
    """The tool is under a build directory, and one suite holds which build
    files address the controller."""
    assert len(tool_sources()) == 3
    for path in tool_sources():
        assert not CONTROLLER_REFERENCE.search(path.read_text(encoding="utf-8")), path


def test_the_tool_runs_no_process_and_writes_no_file() -> None:
    forbidden_modules = {"subprocess", "socket", "os", "shutil", "urllib", "http"}
    forbidden_calls = {"write_text", "write_bytes", "mkdir", "unlink", "rmdir", "open"}
    for path in tool_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                names = set()
            assert not names & forbidden_modules, (path, names)
            if isinstance(node, ast.Call):
                called = node.func
                name = getattr(called, "attr", getattr(called, "id", ""))
                assert name not in forbidden_calls, (path, name)


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------


def test_the_document_publishes_the_record_and_its_states() -> None:
    text = DOCUMENT_PATH.read_text(encoding="utf-8")
    assert RECORD_SCHEMA in text
    for name in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS, *TRANSITION_FIELDS):
        assert f"`{name}`" in text, name
    for state in (*FIELD_STATES, *APPLICATION_STATES):
        assert f"`{state}`" in text, state
    for statement in DOES_NOT_ESTABLISH:
        assert " ".join(statement.split()) in " ".join(text.split()), statement


def test_the_document_states_the_boundary_and_how_each_rule_is_held() -> None:
    text = DOCUMENT_PATH.read_text(encoding="utf-8")
    rows = re.findall(
        r"^\|\s*`([a-z0-9][a-z0-9-]*)`\s*\|[^|]*\|\s*([^|]+?)\s*\|\s*$",
        text.split("## The boundary for a manual change", 1)[1].split("\n## ", 1)[0],
        flags=re.MULTILINE,
    )
    assert tuple(rule for rule, _ in rows) == BOUNDARY_RULES
    for rule, enforcement in rows:
        assert enforcement.split(":")[0].split(".")[0].strip() in ENFORCEMENTS, rule
    # The boundary is a rule for people. The document must not read as a control.
    assert "No admission control" in text
    assert "not a caller outcome" in text


# --------------------------------------------------------------------------
# The summary
# --------------------------------------------------------------------------


def test_the_summary_counts_what_the_samples_hold(tmp_path: Path) -> None:
    drifted = with_value(application(), "OutOfSync", "status", "sync", "status")
    partial = without(application(), "status", "health")
    record = record_of(
        tmp_path,
        [application(), drifted, partial, UNANSWERED, ABSENT, "not json"],
        requested=7,
        ended=False,
    )
    samples = record["samples"]
    summary = record["summary"]
    assert summary["samples"] == len(samples) == 7
    assert summary["applicationReads"] == {
        "reported": 3,
        "absent": 1,
        "unanswered": 1,
        "unreadable": 1,
        "not-taken": 1,
    }
    assert summary["samplesWithEveryRequiredField"] == 2
    assert summary["samplesSettled"] == 1
    assert [sample["settled"]["value"] for sample in samples] == [True] + [False] * 6
    for sample in samples:
        if sample["settled"]["value"]:
            assert sample["notReported"] == []
        for field in sample["fields"].values():
            assert ("value" in field) == (field["state"] == "reported")


# --------------------------------------------------------------------------
# The committed records of the run
# --------------------------------------------------------------------------


def run_record(name: str) -> dict[str, Any]:
    path = REPO_ROOT / "docs" / "proof" / "environment"
    return json.loads(
        (path / f"{RUN_RECORD_PREFIX}{name}.record.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("name", tuple(RUN_RECORDS))
def test_a_committed_record_counts_what_its_samples_hold(name: str) -> None:
    """A record of the run, read as a file. Nothing here observes a cluster,
    and nothing here builds the record again: its directory is not committed."""
    count, reads, settled_count, complete = RUN_RECORDS[name]
    record = run_record(name)
    assert record["schema"] == RECORD_SCHEMA
    assert record["doesNotEstablish"] == list(DOES_NOT_ESTABLISH)
    assert record["collection"]["complete"] is complete
    samples = record["samples"]
    summary = record["summary"]
    assert summary["samples"] == len(samples) == count
    assert summary["applicationReads"] == {
        state: reads.get(state, 0) for state in APPLICATION_STATES
    }
    for state in APPLICATION_STATES:
        assert reads.get(state, 0) == sum(
            1 for sample in samples if sample["applicationRead"] == state
        )
    assert summary["samplesSettled"] == settled_count
    assert settled_count == sum(1 for sample in samples if sample["settled"]["value"])
    assert summary["resolvedRevisions"] == [RUN_RESOLVED_REVISION]

    for sample in samples:
        for field in sample["fields"].values():
            assert ("value" in field) == (field["state"] == "reported")
        if sample["settled"]["value"]:
            assert sample["notReported"] == []
            assert sample["fields"]["deletionTimestamp"] == {"state": "missing"}
            assert sample["fields"]["syncStatus"]["value"] == "Synced"
            assert sample["fields"]["healthStatus"]["value"] == "Healthy"
        if sample["applicationRead"] != "reported":
            assert set(sample["notReported"]) == set(REQUIRED_FIELDS)
        if sample["objectsRead"] == "collected":
            assert (
                len(record["objectSets"][sample["objectSet"]]) == sample["objectCount"]
            )
        # Every comparison on the cluster agreed. A finding here would be a
        # fact that the run record does not state.
        consistency = sample["consistency"]
        if consistency["state"] == "compared":
            assert consistency["revisionFindings"] == []
            assert consistency["source"]["findings"] == []
            assert consistency["labels"].get("findings", []) == []
    taken = {s["index"] for s in samples if s["applicationRead"] != "not-taken"}
    for transition in record["transitions"]:
        assert {transition["fromSample"], transition["toSample"]} <= taken

    text = json.dumps(record)
    for host_detail in ("Users", ":\\\\", "AppData", "/home/"):
        assert host_detail not in text, host_detail


def test_the_run_reported_every_field_and_no_condition() -> None:
    """What the run does and does not show about the paths the tool reads."""
    records = [run_record(name) for name in RUN_RECORDS]
    names = (*REQUIRED_FIELDS, *OPTIONAL_FIELDS, "historyId", "historyRevision")
    for name in (*names, "historyDeployedAt"):
        assert any(
            sample["fields"][name]["state"] == "reported"
            for record in records
            for sample in record["samples"]
        ), name
    assert len((*names, "historyDeployedAt")) == 19
    assert not any(
        sample["conditions"] for record in records for sample in record["samples"]
    )
    # A new Application, read before the controller first wrote to it.
    apply = run_record("run-2-apply")["samples"]
    unreported = [
        sample["index"]
        for sample in apply
        if sample["applicationRead"] == "reported"
        and sample["notReported"] == list(REQUIRED_FIELDS)
    ]
    assert unreported == [7, 8, 9, 10, 11, 12]
    assert [s["index"] for s in apply if s["settled"]["value"]] == list(range(22, 81))
    # An Application that is being deleted, and still reports its last states.
    remove = run_record("run-2-remove")["samples"]
    assert [
        sample["index"]
        for sample in remove
        if sample["settled"]["reasons"] == ["the Application has a deletion timestamp"]
    ] == [6, 7]
